# HyperShift Reference

HyperShift (Hosted Control Planes / HCP) runs a guest cluster's control plane as **pods in a
management cluster** instead of on dedicated control-plane machines. Every HyperShift job
therefore spans **two clusters**, and root cause almost always requires correlating both.

## When to Use

- Job name contains `hypershift`, `hcp`, or an HCP platform variant (`e2e-aws`, `e2e-kubevirt`,
  `e2e-agent`, `e2e-azure`, `e2e-powervs` under the `openshift/hypershift` repo)
- Refs point at `openshift/hypershift` (org `openshift_hypershift` in PR-job paths)
- Failure references `HostedCluster`, `NodePool`, `HostedControlPlane`, or a `clusters-*` namespace
- Two must-gathers are present, or a `dump-management-cluster` / `hypershift-dump` artifact exists

## Architecture: Two Clusters, One Job

| Thing | Where it runs | What it is |
|-------|---------------|------------|
| **Management cluster** | Real nodes (the CI-installed OCP cluster) | Hosts hosted control planes as pods; runs the HyperShift operator |
| **Hosted (guest) cluster** | Worker nodes only | Tenant cluster — no control-plane machines; its API server is a pod on the mgmt cluster |
| **HostedCluster (HC)** | CR in mgmt ns `clusters` | Desired state + top-level status of one hosted cluster |
| **NodePool (NP)** | CR in mgmt ns `clusters` | Worker-node scaling/config for the hosted cluster (replaces MachineConfigPool) |
| **HostedControlPlane (HCP)** | CR in mgmt ns `clusters-<name>` | Rendered control-plane state; owns the control-plane pods |

**Naming rule:** a HostedCluster `<ns>/<name>` (default ns `clusters`) has its control-plane
pods in namespace `<ns>-<name>` — i.e. `clusters-<name>`. This `clusters-<name>` namespace is
the single most important location in a HyperShift job.

## Identifying HyperShift Jobs

| Signal | Example |
|--------|---------|
| PR job, hypershift repo | `pull-ci-openshift-hypershift-main-e2e-aws` |
| Periodic conformance | `periodic-ci-openshift-hypershift-release-4.22-periodics-e2e-aws-ovn-conformance` |
| Aggregated | `aggregated-hypershift-ovn-conformance-4.22` → see [aggregated.md](aggregated.md) |
| Step-registry usage | job uses `ci-operator/step-registry/hypershift/*` steps → see [ci-infrastructure-changes.md](ci-infrastructure-changes.md) |

These are plain Go tests run as CI steps, not OTE extension binaries. When no specific test
name is provided, analyze the failed CI steps from the build log and step graph (see
[artifacts.md](artifacts.md) and [ci-infrastructure-changes.md](ci-infrastructure-changes.md)),
not the JUnit XML. Example Go test names: `TestCreateCluster`,
`TestCreateClusterCustomConfig`, `TestNodePool`, `TestKarpenter/EnsureHostedCluster/...`.

## Artifacts: Where Each Cluster's Data Lives

Full path table and directory tree are in [artifacts.md](artifacts.md#hypershift-must-gather-patterns).
The three patterns, and which cluster each half maps to:

| Pattern | Detect (under `artifacts/<job-name>/`) | Management data | Hosted data |
|---------|----------------------------------------|-----------------|-------------|
| **Unified** | `dump-management-cluster/artifacts/artifacts.tar[.gz]` | extracted `output/` root | `output/hostedcluster-<name>/` |
| **Dual** | `gather-must-gather/…/must-gather.tar` **and** `**/artifacts/hypershift-dump.tar` (or `**/hostedcluster.tar`) | standard must-gather | the `hostedcluster-*` dir inside the dump (may be absent) |
| **Standard only** | `gather-must-gather/…/must-gather.tar` alone | standard must-gather | none — management only |

### Finding the hosted cluster namespace from artifacts

The hosted namespace name (`clusters-<name>`) is rarely printed directly — derive it:

```bash
# 1. Unified/dual dump: the hostedcluster-<name> dir names the cluster
find . -type d -name 'hostedcluster-*'          # -> hostedcluster-<name>  =>  ns clusters-<name>

# 2. Management must-gather: the control-plane namespace IS clusters-<name>
ls <mgmt-must-gather>/namespaces/ | grep '^clusters-'

# 3. build-log.txt: the hypershift CLI names it at create time
grep -Eo 'clusters-[a-z0-9-]+' build-log.txt | sort -u
```

### Key log/CR locations (paths relative to each cluster's must-gather root)

| Data | Location |
|------|----------|
| HCP component pods & logs | **mgmt** `namespaces/clusters-<name>/pods/` (unified: `output/namespaces/clusters-<name>/`) |
| HyperShift operator logs | **mgmt** `namespaces/hypershift/pods/operator-*/` |
| HostedCluster / NodePool CRs | **mgmt** dump `hostedcluster.yaml` / `nodepool.yaml`, or `namespaces/clusters/hypershift.openshift.io/` |
| Hosted cluster operators / workloads | **hosted** `cluster-scoped-resources/config.openshift.io/clusteroperators*` and `namespaces/<app-ns>/` |

## Correlating Across Both Clusters

1. **Download and extract both halves separately.** HyperShift jobs produce a management-side and a
   hosted-side archive (e.g. `hypershift-dump.tar` / `hostedcluster.tar`, or a unified
   `dump-management-cluster/artifacts/artifacts.tar` — see the [artifacts reference](artifacts.md)
   for exact paths and general extraction steps):

   ```bash
   mkdir -p must-gather-mgmt && tar -xf hypershift-dump.tar -C must-gather-mgmt/
   mkdir -p must-gather-hosted && tar -xf hostedcluster.tar -C must-gather-hosted/
   # Decompress any nested archives in either root
   find must-gather-mgmt must-gather-hosted -name '*.gz' -exec gunzip -f {} +
   ```

   Then run the [must-gather-analyzer](../../../../must-gather/skills/must-gather-analyzer/SKILL.md)
   scripts (`analyze_clusteroperators.py`, `analyze_pods.py --problems-only`,
   `analyze_nodes.py --problems-only`, `analyze_events.py --type Warning`, `analyze_etcd.py`)
   against **each root independently** and label every finding `[Management]` or `[Hosted]`.
2. **Check for mgmt → hosted causation.** The hosted control plane *is*
   management-cluster pods, so a hosted-API symptom can have a management-side cause.
3. **Cross-cluster dependency chains** to trace (don't stop at the first symptom):

   ```text
   Mgmt node MemoryPressure/NotReady ─▶ HCP pods (clusters-<name>) evicted/Pending
       ─▶ hosted kube-apiserver down ─▶ hosted ClusterOperators Degraded ─▶ tests fail
   HyperShift operator reconcile error ─▶ HostedControlPlane rollout stalls ─▶ HC !Available
   Mgmt registry/etcd/disk-IOPS issue ─▶ HCP ImagePullBackOff / etcd slow ─▶ hosted API 5xx
   NodePool not ready ─▶ no hosted workers ─▶ hosted pods Pending ─▶ workload tests fail
   ```

4. **Correlate on time** — align the test-failure window (interval files, see
   [disruption.md](disruption.md)) with warning events in *both* clusters (±5 min).

## HostedCluster & NodePool Status

Read `.status.conditions[]` — `reason` and `message` carry the actionable detail. For HC,
healthy = `Available=True`, `Degraded=False`, `Progressing=False` (once settled).

**HostedCluster** — check in this order:
`Available` → `ValidConfiguration` / `ValidReleaseImage` → `InfrastructureReady` →
`EtcdAvailable` → `KubeAPIServerAvailable` → `ValidHostedControlPlaneConfiguration` →
`ClusterVersionSucceeding` → `Degraded`. Also `.status.version.history[0]` for the target/state.

**NodePool** — `Ready`, `AllMachinesReady`, `AllNodesHealthy`, `ValidReleaseImage`,
`UpdatingVersion`/`UpdatingConfig` (stuck = rollout wedged), `AutoscalingEnabled`. Compare
`.spec.replicas` vs `.status.replicas`; a mismatch with `AllMachinesReady=False` means workers
never provisioned — check the CAPI provider pods (`capi-provider`, `cluster-api`) in
`clusters-<name>` and cloud capacity/quota ([cloud-provider-errors.md](cloud-provider-errors.md)).

## Failure Patterns

### Management-side (in `clusters-<name>` or `hypershift` ns)

- **HyperShift operator errors** — `namespaces/hypershift/pods/operator-*`: reconcile failures,
  admission-webhook rejects, missing RBAC/pull-secret. Blocks HCP creation for *all* hosted clusters.
- **HostedControlPlane rollout failure** — control-plane pods not rolling out: `control-plane-operator`
  (orchestrates the HCP), `kube-apiserver`, `etcd`, `kube-controller-manager`, `kube-scheduler`,
  `openshift-apiserver`, `oauth-openshift`, `konnectivity-server`, `ignition-server`,
  `hosted-cluster-config-operator`, `cluster-version-operator`. Look for `CrashLoopBackOff`,
  `ImagePullBackOff`, `Pending` (mgmt scheduling/quota), high `restartCount`.
- **Management node pressure** — a mgmt cluster packing many HCPs hits CPU/memory/disk limits;
  cascades to every hosted cluster on that node. See [resource-exhaustion.md](resource-exhaustion.md).

### Hosted-side (in the hosted must-gather)

- **Worker nodes / NodePool** — nodes `NotReady` or absent → NodePool not `Ready`; hosted pods `Pending`.
- **Hosted ClusterOperators Degraded** — can be *downstream* of a management-side control-plane
  outage; confirm the HCP pods were healthy during the window before blaming the hosted operator.
- **Application workloads** — the test's own pods in the hosted cluster (namespace correlation).

### Common failure modes

- **Hosted etcd** — `etcd-0/1/2` pods in `clusters-<name>`; `etcdserver: request timed out`,
  `leader changed`, `slow fdatasync`. Backed by mgmt-cluster PVCs, so mgmt disk-IOPS pressure
  surfaces here as hosted API latency. Cross-ref [resource-exhaustion.md](resource-exhaustion.md).
- **Ingress / connectivity** — `konnectivity-server` (mgmt) ↔ `konnectivity-agent` (hosted) tunnel
  the control plane to guest workers; `router` pods serve `*.apps.<hosted>`. `failed to dial`,
  tunnel drops, or router not ready → hosted routes/webhooks unreachable. (Konnectivity is
  HCP-specific — debug it here; router/ingress mechanics: [networking.md](networking.md#load-balancer-and-ingress).)
- **Kubelet connectivity** — hosted kubelets reach the hosted apiserver via its exposed endpoint
  (LB/route/NodePort). `context deadline exceeded` / `the server is currently unable to handle the
  request` from kubelets → apiserver pod down or endpoint mis-provisioned (check `InfrastructureReady`,
  AWS endpoint service).

## Common Failure Patterns — Quick Reference

| Symptom | Likely cause | Where to look |
|---------|--------------|---------------|
| `HostedCluster` never `Available` | HyperShift operator or HCP rollout stalled | `hypershift/operator-*` logs; HC `.status.conditions` reason |
| HCP pods `Pending`/`Evicted` | Mgmt node pressure / quota | `[Management]` nodes+events, [resource-exhaustion.md](resource-exhaustion.md) |
| HCP pods `ImagePullBackOff` | Mgmt pull-secret / registry / mirror | `[Management]` pod events, [networking.md](networking.md) |
| Hosted operators Degraded, HCP healthy | Genuine hosted-side issue | `[Hosted]` clusteroperators + pods |
| NodePool `Ready=False`, replicas short | CAPI provisioning / cloud capacity | `capi-provider`/`cluster-api` in `clusters-<name>`, [cloud-provider-errors.md](cloud-provider-errors.md) |
| Hosted API 5xx / timeouts | HCP etcd or kube-apiserver | `etcd-*`/`kube-apiserver-*` in `clusters-<name>` |
| `*.apps.<hosted>` unreachable | Router / konnectivity tunnel | `router`, `konnectivity-*`, [networking.md](networking.md) |
| Only management must-gather present | Standard-only pattern or hosted collection failed | confirm no `hostedcluster-*` dir; note in report |

## See Also

- [Artifacts](artifacts.md) — full must-gather path table, extraction, directory tree
- [Test Extension Binaries](test-extension-binaries.md) — component `*-tests-ext` (OTE) binary failures
- [Upgrade](upgrade.md) — HyperShift management-plane vs hosted-cluster upgrades, dual ClusterVersion
- [Aggregated Jobs](aggregated.md) — HyperShift conformance/aggregated child-run analysis
- [Resource Exhaustion](resource-exhaustion.md) — node CPU/memory/disk pressure and eviction
  mechanics (the mgmt→HCP cascade is described above)
- [Networking](networking.md) — OVN/DNS/ingress/registry within either cluster
- [Cloud Provider Errors](cloud-provider-errors.md) — NodePool/infrastructure provisioning failures
- [must-gather-analyzer](../../../../must-gather/skills/must-gather-analyzer/SKILL.md) — per-cluster diagnostic scripts
