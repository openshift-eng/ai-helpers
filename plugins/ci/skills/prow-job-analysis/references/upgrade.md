# Upgrade Failure Analysis Reference

Use when the job name contains `upgrade` and the failure occurs during or after the upgrade
phase — the CVO (Cluster Version Operator) reports errors or gets stuck, operators go degraded
or unavailable, the MCO (Machine Config Operator) fails to drain or reboot nodes, ClusterVersion
is stuck `Progressing=True`, or tests fail in the upgrade window or post-upgrade conformance.
This is the most complex failure category: multi-phase orchestration, rolling node updates,
operator reconvergence, and version skew between components.

## Upgrade Job Classification

### Identifying Upgrade Jobs from Name

Parse the job name for upgrade type and environment:

| Pattern in Job Name | Upgrade Type | Description |
|---------------------|-------------|-------------|
| `upgrade-from-stable-4.X` | Minor upgrade | Installs GA 4.X, upgrades to 4.(X+1) nightly/CI build |
| `upgrade-from-stable` (no version) | Minor upgrade | Installs previous GA minor, upgrades to current |
| `upgrade-micro` | Micro (z-stream) | Installs previous z-stream of same minor, upgrades to current build |
| `upgrade` (bare, no `from-stable`) | Micro (z-stream) | Usually same-minor upgrade within the version stream |
| `upgrade-from-stable-4.X-to-4.Y` | Multi-minor | Installs 4.X GA, upgrades through 4.Y (may skip versions) |

### Minor vs Micro vs Major Upgrades

**Micro (z-stream) upgrades** (e.g., 4.18.3 → 4.18.5):
- Components within the same minor version — API changes are rare
- Machine config changes are typically minimal (no OS-level changes)
- MCO may skip node drain/reboot if no machine config changes exist
- Fastest upgrade type, fewest moving parts
- Failures here often indicate regressions in specific operators

**Minor upgrades** (e.g., 4.17 → 4.18):
- All operators update to new versions with potentially new APIs
- Machine config changes are common — new kubelet config, OS updates, crio config
- MCO will drain and reboot every node (control plane and workers)
- Takes significantly longer than micro upgrades (30-60+ minutes)
- Version skew between components is expected during the transition
- Most complex upgrade path — highest failure rate

**Major upgrades** (e.g., 3.x → 4.x):
- Not tested in current CI. If encountered, treat as a special case and investigate manually.

**EUS-to-EUS upgrades** (e.g., 4.14 → 4.16 via 4.15): the worker MachineConfigPool is
deliberately **paused** (`oc patch mcp/worker --type merge -p '{"spec":{"paused":true}}'`) while
the control plane makes two minor hops, then unpaused once so workers drain/reboot a single time.
A worker MCP stuck `Paused=True` mid-EUS is **expected** — confirm the job is EUS before
diagnosing it as a drain stall.

### Single-Node (SNO) Upgrade Jobs

Jobs with `single-node` or `sno` in the name:

- One node serves as both control plane and worker — no rolling update possible; it must be drained and rebooted in place
- All workloads disrupted during the reboot window
- etcd runs as a single member — no quorum concerns but no redundancy
- MCO drain evicts ALL pods simultaneously; every PDB will be violated (universal and expected)
- Upgrade timeout is typically shorter (one node to update)
- Recovery depends on the single node coming back healthy

### HyperShift Upgrade Jobs

HyperShift jobs have two distinct upgrade targets:

**Management plane upgrade** — HyperShift operator and control plane components on the management cluster:
- HostedControlPlane pods (kube-apiserver, etcd, kas, etc.)
- HyperShift operator itself
- Control plane infrastructure in the management cluster's namespace

**Hosted cluster upgrade** — the hosted cluster's data plane:
- Worker nodes get new machine configs
- Hosted cluster operators reconverge
- NodePool rolling update

Key differences from standalone upgrades:
- Control plane runs as pods in the management cluster — no node drain for control plane
- etcd runs as a StatefulSet, not static pods
- Worker node updates are driven by NodePool, not MachineConfigPool
- Two separate ClusterVersion objects exist (management and hosted) — failures can originate in either; always check both

See [hypershift reference](hypershift.md) for HyperShift-specific diagnostics.

## Upgrade Phases and How to Identify Which Failed

Determining which phase failed is the critical first step — it determines the entire
investigation path.

### Phase 1: Pre-Upgrade Installation

The cluster is installed with the base version before upgrade begins.

**How to identify**: JUnit XML contains `install should succeed` — if this test fails,
the job never reached the upgrade phase.

**Routing**: This is an **install failure**, not an upgrade failure. Use the install guide
that matches the job type:

- [install failure reference](install/general.md) for cloud jobs
- [metal install reference](install/metal.md) for bare-metal jobs (job name contains `metal`)

### Phase 2: Pre-Upgrade Health Checks

Before initiating the upgrade, the test framework verifies:
- All ClusterOperators are Available, not Degraded, not Progressing
- All nodes are Ready
- All MachineConfigPools are updated and not degraded

**How to identify**: Build log shows `Waiting for cluster operators to stabilize`
or `cluster is not healthy` before any `ClusterVersion` update.

**Common causes**: Flaky install that left an operator degraded, node that didn't
fully join, or a preexisting condition from the base version.

### Phase 3: Upgrade Initiation

The test framework patches the ClusterVersion to set the desired update:

```bash
oc adm upgrade --to-image=<payload-image>
```

**How to identify**: Build log shows `Starting upgrade to <version>` or
`Upgrading cluster to <payload>`. The ClusterVersion object transitions to
`Progressing=True`.

**Common causes**: Invalid payload image, precondition failures (e.g., admin ack
required for minor upgrades), ClusterVersion webhook rejections.

### Phase 4: Control Plane Rollout

The CVO drives operator updates in dependency order. Control plane components first:

1. **etcd** — Rolling restart of etcd members (one at a time, maintaining quorum)
2. **kube-apiserver** — Rolling restart with new binary and config
3. **kube-controller-manager** — Depends on kube-apiserver
4. **kube-scheduler** — Depends on kube-apiserver
5. **openshift-apiserver** — Depends on kube-apiserver
6. **openshift-controller-manager** — Depends on openshift-apiserver
7. **Other operators** — Authentication, console, monitoring, etc.

**How to identify**: Timeline/interval data shows `ClusterOperator` source events
with `condition/Progressing changed: True` for control plane operators. Build log
shows CVO applying manifests.

**Common causes**:
- etcd member fails to restart (disk I/O, corrupt WAL)
- kube-apiserver rollout stuck (cert rotation failure, webhook blocking)
- Operator manifest incompatible with new version
- Resource exhaustion on control plane nodes during rolling restart

### Phase 5: MCO Node Updates (Drain, Apply, Reboot)

After control plane operators converge, the MCO updates nodes:

1. **Cordon** the node (mark unschedulable)
2. **Drain** all pods from the node (respecting PDBs)
3. **Apply** new machine config (kubelet, crio, OS config)
4. **Reboot** the node with new config
5. **Uncordon** the node (mark schedulable)
6. Repeat for next node (one at a time per pool)

Control plane nodes update first (master MachineConfigPool), then workers.

**How to identify**: Timeline data shows `MachineConfigPool` events with
`condition/Updating changed: True`. Build log shows MCO drain operations.
Node events show `Draining`, `Rebooting`, `NodeNotReady` transitions.

**Common causes**: See the dedicated [MCO Drain Failures](#mco-drain-failures)
section below.

**The upgrade also swaps the OS** (kernel, cri-o, systemd, NetworkManager, SELinux).
If a node misbehaves after its upgrade reboot, weigh RPM package changes between the
two releases alongside operator explanations: node journals record each boot's
package versions, and the release changelog lists the RHCOS diff. If the implicated
subsystem's packages changed across the boundary, read
[operating-system-changes.md](operating-system-changes.md).

### Phase 6: Operator Reconvergence

After all nodes are updated, operators stabilize on the new version:
- All ClusterOperators should reach `Available=True, Progressing=False, Degraded=False`
- CVO marks `Progressing=False` on ClusterVersion
- MachineConfigPools show `Updated=True, Updating=False`

**How to identify**: ClusterVersion transitions from `Progressing=True` to
`Progressing=False`. If it stays `Progressing=True` with `Failing=True`,
an operator failed to reconverge.

**Common causes**:
- Operator pod crash-looping on new version
- New operator version incompatible with existing custom resources
- Webhook or admission controller blocking operator reconciliation
- Storage or network driver not yet updated, blocking dependent operators

### Phase 7: Post-Upgrade Conformance Testing

After the upgrade completes, the test framework runs e2e conformance tests
against the upgraded cluster.

**How to identify**: This is the second timeline file (sorted by filename).
Build log shows `Running e2e tests` or `openshift-tests run` after the upgrade
completes. JUnit XML shows individual test failures.

**Common causes**: Tests fail due to post-upgrade cluster issues (operator still
degraded, nodes not fully ready, version-skew related API issues).

### Determining Which Phase Failed from Artifacts

Follow this decision tree:

```text
1. Does JUnit XML contain "install should succeed" failure?
   YES → Phase 1 (install failure) → use install reference
   NO  → continue

2. Does build-log.txt show upgrade never started?
   (No "Starting upgrade" or "Upgrading cluster" message)
   YES → Phase 2 (pre-upgrade health check) → check operator health before upgrade
   NO  → continue

3. Does build-log.txt show "Cluster did not complete upgrade"
   or ClusterVersion stuck at Progressing=True?
   YES → Phase 4, 5, or 6 — determine which:

   3a. Are ClusterOperator events showing control plane operators
       stuck at Progressing=True?
       YES → Phase 4 (control plane rollout)

   3b. Are MachineConfigPool events showing Updating=True stuck?
       YES → Phase 5 (MCO node updates)

   3c. Are all nodes updated but operators not stabilizing?
       YES → Phase 6 (reconvergence)

   NO  → continue

4. Did the upgrade complete but conformance tests fail?
   (ClusterVersion shows Progressing=False but tests fail)
   YES → Phase 7 (post-upgrade conformance)
```

## MCO Drain Failures

A failed or stuck drain halts the node-update sequence and, with it, the upgrade.

### How MCO Drain Works

To update a node's configuration, the MCO follows this sequence:

```text
1. Cordon node (SchedulingDisabled)
2. Start draining the node (MCD retries eviction until it succeeds or the node update fails)
   - For each pod on the node:
     a. Check if pod is managed by a controller (DaemonSet pods are skipped)
     b. Check PodDisruptionBudget — if eviction would violate PDB, wait and retry
     c. Send eviction request to the API server
     d. Wait for pod to terminate
   - If drain doesn't complete within timeout → drain failure
3. Apply new MachineConfig (write files, update systemd units)
4. Reboot node
5. Wait for node to come back Ready
6. Uncordon node (SchedulingDisabled removed)
```

### PDB (PodDisruptionBudget) Conflicts

PDBs protect workloads from voluntary disruption (like drains). A drain stalls if
evicting a pod would violate the budget.

**How PDB blocking works**:
- A PDB specifies `minAvailable` or `maxUnavailable` for a set of pods
- During drain, the API server checks: "If I evict this pod, does the PDB still hold?"
- If eviction would violate the PDB, the request is rejected (HTTP 429)
- MCO retries the eviction, but if the pod can't be rescheduled elsewhere (node
  affinity, resource constraints, or the only replica), the drain stalls

**Common PDB culprits in CI**:

| Component | PDB | Why It Blocks |
|-----------|-----|---------------|
| `prometheus-k8s` | `minAvailable: 1` | 2 replicas, both may be on the same node being drained |
| `alertmanager-main` | `minAvailable: 1` | Similar to prometheus — small replica count |
| `image-registry` | `minAvailable: 1` | Single replica in some CI configurations |
| `router-default` | `maxUnavailable: 25%` | With 2 replicas, can't evict one if other is down |
| E2E test pods | Various | Tests may create PDBs that aren't cleaned up |
| `openshift-monitoring/*` | Various | Monitoring stack PDBs during node drain |

### Disruption Poller Pods That Block Their Own Node's Drain

An insidious failure mode unique to CI. The test framework deploys **disruption
poller pods** on every node to monitor API backend availability, managed by a
DaemonSet-like controller:

1. Poller pod runs on Node A
2. MCO tries to drain Node A
3. Poller pod is part of the drain target
4. If the poller pod has a PDB, or the framework fails to evict it before the drain,
   the drain can stall
5. While the drain stalls, the poller pod reports disruption (node is cordoned,
   services disrupted)
6. Feedback loop: drain blocked → disruption detected → drain still blocked

**How to identify**: Look for drain timeout messages mentioning pods in
`openshift-e2e-*` namespace or pods with names containing `disruption` or `sampler`.

### The Cascading Failure Pattern

MCO drain failures trigger a cascade that explains most mass test failures in
upgrade jobs. Additionally the drained node is cordoned (workloads can't schedule
there); if it's a control plane node, etcd/apiserver run on fewer nodes; remaining
nodes bear extra load → potential resource exhaustion; and PDB violations propagate
(pod can't evict → other node picks up load → that node overloads → more failures).

```text
MCO drain timeout on node X
  → MachineConfigPool stuck at Updating=True
    → CVO sees MCP not progressing
      → ClusterVersion stays Progressing=True, eventually Failing=True
        → machine-config operator reports Degraded=True
          → Operators gated on node/MCP health report Degraded
            → kube-apiserver may restart due to revision changes
              → API disruption during restart
                → Tests see API errors → mass test failures
```

**How to identify the cascade**:

1. **Check MachineConfigPool status**:
   ```bash
   gcloud storage cp "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/oc_cmds/machineconfigpool" \
     .work/prow-job-analysis/{build_id}/logs/ --no-user-output-enabled
   ```
   Look for pools with `UPDATED=False UPDATING=True DEGRADED=True`

2. **Check machine-config-daemon logs**:
   ```bash
   gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/pods/openshift-machine-config-operator/"
   ```
   Search for `drain` and `evict` messages in the MCD pod logs

3. **Check node events in interval data**:
   Look for `NodeMonitor` and `MachineMonitor` source events showing the drain
   and reboot sequence. A gap between `Draining` and `Rebooting` longer than
   30 minutes suggests a drain stall.

4. **Check for PDB violation messages**:
   Search the MCD logs and build log for:
   ```text
   error when evicting pods
   Cannot evict pod as it would violate the pod's disruption budget
   pod disruption budget
   ```

### MCO Drain Artifacts to Examine

| Artifact | Path | What to Look For |
|----------|------|------------------|
| MachineConfigPool status | `gather-extra/artifacts/oc_cmds/machineconfigpool` | Pool update status, degraded reason |
| Machine-config-daemon logs | `gather-extra/artifacts/pods/openshift-machine-config-operator/machine-config-daemon-*` | Drain progress, eviction errors |
| Node events | Timeline JSON `NodeMonitor` source | Drain start/end, reboot, NotReady transitions |
| MachineConfig status | `gather-extra/artifacts/oc_cmds/machineconfig` | Current vs desired config per pool |
| Node list | `gather-extra/artifacts/oc_cmds/nodes` | SchedulingDisabled status |
| PDB list | `gather-extra/artifacts/oc_cmds/poddisruptionbudgets` | PDB definitions and current disruptions allowed |

## Operator Degradation Cascades

Operators update in a dependency chain, so one failure often cascades to others.
Trace the chain to separate root cause from symptoms.

### Common Degradation Chains

**Authentication → API Server → Everything**:
```text
authentication operator degraded
  → oauth-apiserver cannot serve tokens
    → kube-apiserver health checks fail (webhook auth)
      → openshift-apiserver reports degraded
        → console, monitoring, registry lose API access
          → mass operator degradation
```

**Machine-API → Machine-Config → Node Lifecycle**:
```text
machine-api-operator unable to reconcile machines
  → new machines don't join the cluster
    → machine-config-operator can't update nodes that don't exist
      → MachineConfigPool stuck at Updating
        → CVO timeout waiting for MCP
```

**etcd → kube-apiserver → Everything**:
```text
etcd member restart during upgrade
  → temporary quorum loss (if unlucky timing)
    → kube-apiserver loses etcd backend
      → all API requests fail
        → all operators report degraded (can't read/write to API)
          → mass test failures
```

**Ingress → Route-dependent services**:
```text
ingress operator updating router pods
  → router pods temporarily unavailable
    → console route unreachable
    → oauth route unreachable → authentication disrupted
      → monitoring routes disrupted
```

### Reading ClusterOperator Conditions Timeline

The interval/timeline data contains `ClusterOperator` events showing condition
transitions. To trace a cascade:

1. **Find the first operator to become Degraded or Unavailable**:
   ```bash
   # In the timeline JSON, search for ClusterOperator events
   jq '[.[] | select(.source == "ClusterOperator" and .level == "Warning")] |
     sort_by(.from) | .[:20]' timeline.json
   ```

2. **Check the time ordering**: The first operator to degrade is usually the root
   cause. Later degradations are often cascading effects.

3. **Look at the degradation reason**: The `humanMessage` field contains the
   condition details:
   ```json
   {
     "source": "ClusterOperator",
     "locator": { "keys": { "name": "authentication" } },
     "message": {
       "humanMessage": "condition/Degraded changed: False -> True (OAuthServerDeploymentDegraded: deployment/oauth-openshift: 1/2 pods are available)"
     },
     "from": "2026-03-21T22:15:00Z"
   }
   ```

4. **Map the cascade**: List all operator degradation events in time order and
   identify which operators degraded before vs after the suspected root cause.

### Distinguishing Transient vs Persistent Degradation

**Transient degradation (expected during upgrade)**:
- Operator Degraded or Unavailable for < 5 minutes during its own rollout
- Progressing=True while updating; brief Degraded=True while old pods terminate and new pods start
- Returns to Available=True, Degraded=False after its rollout completes

**Persistent degradation (real problem)**:
- Operator stays Degraded for > 10 minutes after its rollout should have completed
- Never transitions back to Available=True
- Pods crash-looping on the new version
- Degraded condition message shows a specific error, not just "rolling update in progress"

**How to tell the difference**:
```text
1. Check the ClusterOperator's Progressing condition:
   - Progressing=True + Degraded=True → may be transient (still updating)
   - Progressing=False + Degraded=True → persistent (update finished but broken)

2. Check pod status for the operator:
   - Pods in CrashLoopBackOff → persistent problem
   - Pods in ContainerCreating → may be transient (image pull, startup)
   - Multiple restarts in last 10 minutes → persistent problem

3. Check the timeline for condition oscillation:
   - Degraded True → False → True rapidly → flapping (persistent problem)
   - Degraded True → False (stays) → transient (resolved)
```

## ClusterVersion Analysis

The ClusterVersion (CV) object is the central resource for upgrade status; the CVO
watches it and drives the entire upgrade.

### ClusterVersion Object Structure

```yaml
apiVersion: config.openshift.io/v1
kind: ClusterVersion
metadata:
  name: version
spec:
  channel: stable-4.18
  desiredUpdate:
    image: quay.io/openshift-release-dev/ocp-release@sha256:...
    version: 4.18.5
status:
  availableUpdates: [...]
  conditions:
    - type: Available
      status: "True"
      lastTransitionTime: "2026-03-21T20:00:00Z"
    - type: Failing
      status: "False"
    - type: Progressing
      status: "True"
      message: "Working towards 4.18.5: 85% complete"
    - type: RetrievedUpdates
      status: "True"
  desired:
    image: quay.io/openshift-release-dev/ocp-release@sha256:...
    version: 4.18.5
  history:
    - completionTime: null          # null = still in progress
      image: quay.io/openshift-release-dev/ocp-release@sha256:...
      startedTime: "2026-03-21T21:00:00Z"
      state: Partial                # Partial = in progress, Completed = done
      version: 4.18.5
    - completionTime: "2026-03-21T20:30:00Z"
      image: quay.io/openshift-release-dev/ocp-release@sha256:...
      startedTime: "2026-03-21T20:00:00Z"
      state: Completed
      version: 4.17.12
  observedGeneration: 3
```

### ClusterVersion Conditions

| Condition | Status | Meaning |
|-----------|--------|---------|
| `Progressing=True` | Normal during upgrade | CVO is actively reconciling operators to new version |
| `Progressing=True` + `Failing=True` | Problem | CVO is trying to upgrade but encountering errors |
| `Progressing=False` + `Available=True` | Normal post-upgrade | Upgrade completed successfully |
| `Progressing=True` + stale message | Problem | CVO stuck at a particular percentage |

### Progressing=True Stuck — Common Causes

When ClusterVersion stays `Progressing=True` for too long (>60 minutes for minor upgrade):

1. **Operator not converging**: The message field shows which operator is blocking:
   ```text
   "Working towards 4.18.5: 85% complete, waiting on kube-apiserver"
   ```
   Check that operator's ClusterOperator conditions and pod status.

2. **MachineConfigPool not completing**: MCPs must finish updating all nodes:
   ```text
   "Working towards 4.18.5: 95% complete, waiting on machine-config"
   ```
   Check MCP status for drain failures or stuck nodes.

3. **Precondition not met**: Some upgrades require admin acknowledgments:
   ```text
   "Precondition: admin-acks/ack-4.17-kube-1.31-api-removals-in-4.18 not found"
   ```
   The CI test framework should handle this — if it doesn't, it's a test bug.

4. **Manifest application failure**: CVO can't apply a particular manifest:
   ```text
   "Unable to apply ... : admission webhook denied the request"
   ```
   A webhook is blocking a required change.

### Failing=True During Upgrade

`Failing=True` means the CVO encountered errors while reconciling. The `message`
field contains the specific error:

```yaml
- type: Failing
  status: "True"
  message: |
    ClusterOperator kube-apiserver is degraded:
    StaticPodsDegraded: nodes/ip-10-0-0-5.ec2.internal pods
    "kube-apiserver-ip-10-0-0-5.ec2.internal" is not ready
```

**Key**: `Failing=True` during upgrade does NOT always mean permanent failure. The
CVO retries, and transient failures may resolve. The upgrade is only considered
failed if `Failing=True` persists until the test framework timeout.

### Reading ClusterVersion status.history

The `status.history` array tracks all upgrade attempts:

- **`state: Completed`** — upgrade finished successfully
- **`state: Partial`** — upgrade is in progress or failed before completing
- **`completionTime: null`** — upgrade hasn't finished (in progress or stalled)
- **`startedTime`** — when the upgrade began

Check the history to determine:
- How long the upgrade has been running (`now - startedTime`)
- Whether previous upgrades completed (base version should show `Completed`)
- Whether the upgrade ever reached `Completed` or stayed at `Partial`

### Partial Upgrade States

A partial upgrade means some components are on the new version and some on the old.
This is the most dangerous state because:

- API compatibility is not guaranteed between versions
- etcd may have been upgraded but apiserver hasn't (or vice versa)
- Some operators are running new code against old CRD schemas
- Workloads may see inconsistent behavior

**Identifying partial upgrade state**:
```bash
# Check ClusterOperator versions
gcloud storage cp "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/oc_cmds/co" \
  .work/prow-job-analysis/{build_id}/logs/ --no-user-output-enabled

# In the output, check VERSION column — mixed versions indicate partial upgrade
```

## Version Skew During Upgrade

During a minor upgrade, components update at different times, creating expected
version skew where some run the new version while others still run the old.

### Expected N/N+1 Skew

During a 4.17 → 4.18 upgrade:

```text
Time T0: All components at 4.17
Time T1: etcd updated to 4.18, apiserver still at 4.17
Time T2: apiserver updated to 4.18, controllers still at 4.17
Time T3: All control plane at 4.18, workers still at 4.17
Time T4: Workers updating (MCO drain/reboot cycle)
Time T5: All components at 4.18
```

Operators are designed to handle this skew, but bugs in skew handling are a common
source of upgrade failures.

### Unexpected Stuck Skew

If the upgrade stalls, you can end up with persistent skew where:
- Control plane is at 4.18 but workers are at 4.17 (MCO drain failure)
- Most operators are at 4.18 but one is stuck at 4.17 (operator bug)
- etcd is at 4.18 but kube-apiserver is still at 4.17 (rollout failure)

**Detecting skew from must-gather**:

Files under `must-gather/cluster-scoped-resources/` are YAML — parse them with `yq` (or
`yq -o=json … | jq`), never `jq` directly. The plain-text `gather-extra/artifacts/oc_cmds/`
dumps are often faster for a version scan.

1. ClusterOperator versions (spot a CO lagging the rest):
   ```bash
   cat gather-extra/artifacts/oc_cmds/co       # VERSION column, plain text
   # From must-gather YAML instead:
   yq '.items[] | {name: .metadata.name, versions: .status.versions}' \
     must-gather/cluster-scoped-resources/config.openshift.io/clusteroperators.yaml
   ```

2. Node kubelet versions (mixed versions = workers mid-rollout):
   ```bash
   cat gather-extra/artifacts/oc_cmds/nodes    # `oc get nodes -o wide`; VERSION = kubelet
   # From must-gather YAML instead:
   yq '.items[] | [.metadata.name, .status.nodeInfo.kubeletVersion] | @tsv' \
     must-gather/cluster-scoped-resources/core/nodes.yaml
   ```

3. MachineConfigPool rendered config (compare `.spec.configuration.name` vs
   `.status.configuration.name` — a mismatch means the pool has not finished updating):
   ```bash
   cat must-gather/cluster-scoped-resources/machineconfiguration.openshift.io/machineconfigpools/worker.yaml
   ```

### API Compatibility Under Version Skew

During minor upgrades, API version changes can cause issues:
- APIs deprecated in the new version may still be used by old-version components
- New CRD fields added by updated operators may not be understood by old-version controllers
- Webhook configurations from the new version may reject requests from old-version clients

**Common skew-related failures**:
- `error: the server doesn't have a resource type "X"` — API removal during upgrade
- `unknown field "newField"` — CRD schema mismatch between versions
- Admission webhook timeouts — new webhook not yet available during rollout

## Upgrade-Specific Artifact Patterns

### Key Files to Examine

| File / Path | What It Contains | When to Check |
|-------------|-----------------|---------------|
| `gather-extra/artifacts/oc_cmds/clusterversion` | ClusterVersion CR with status, conditions, history | Always — first artifact to check |
| `gather-extra/artifacts/oc_cmds/co` | All ClusterOperator statuses | Always — identify degraded operators |
| `gather-extra/artifacts/oc_cmds/machineconfigpool` | MCP status (Updated, Updating, Degraded) | MCO failures, node update issues |
| `gather-extra/artifacts/oc_cmds/machineconfig` | Machine configs and their rendered versions | MCP configuration mismatches |
| `gather-extra/artifacts/oc_cmds/nodes` | Node status, kubelet versions, conditions | Node readiness, version skew |
| `gather-extra/artifacts/oc_cmds/poddisruptionbudgets` | PDB status across all namespaces | Drain failures, PDB blocking |
| `gather-extra/artifacts/pods/openshift-machine-config-operator/` | MCO and MCD pod logs | Drain details, reboot timing |
| `gather-extra/artifacts/pods/openshift-cluster-version/` | CVO pod logs | Upgrade orchestration errors |
| Timeline JSON (`e2e-timelines_spyglass_*.json`) | Upgrade events, operator transitions, disruption | Temporal correlation of failures |
| `gather-extra/artifacts/pods/openshift-etcd/` | etcd pod logs | etcd health during upgrade |
| `gather-extra/artifacts/audit_logs/` | API server audit logs | Request failures during upgrade |

### MCO Logs and Machine-Config-Daemon Logs

Two key components:
- **machine-config-operator** pod: orchestrates MCP updates
- **machine-config-daemon** pods (one per node): perform the drain/apply/reboot

Look in the MCD logs for:
```text
# Drain start
I ... msg="initiating drain of node ..."

# PDB blocking
W ... msg="eviction request failed" error="Cannot evict pod ... it would violate the pod's disruption budget"

# Drain not completing: MCD retries eviction (~1h) then fails the node update; the
# MCDDrainError alert fires (see disruption.md)
E ... msg="error when evicting pods ... (will retry after 5s)"

# Config apply
I ... msg="applying machine config ..."

# Reboot
I ... msg="initiating reboot"

# Post-reboot
I ... msg="node has rebooted, applying config"
```

### Node Events During Upgrade

The timeline JSON captures node lifecycle events:

```json
{
  "source": "NodeMonitor",
  "locator": { "keys": { "node": "ip-10-0-0-5.ec2.internal" } },
  "message": { "humanMessage": "condition/Ready changed: True -> False (NodeStatusUnknown: Kubelet stopped posting node status)" },
  "from": "2026-03-21T22:30:00Z"
}
```

Key `NodeMonitor` transitions to watch for during upgrade:
- `Ready=True → Ready=False` — node going down for reboot
- `Ready=False → Ready=True` — node back after reboot
- `SchedulingDisabled` annotation — node is cordoned for drain

**Time between `Ready=False` and `Ready=True`**: This is the reboot duration.
Typically 5-10 minutes. If > 20 minutes, the node may have failed to come back.

### Interval/Timeline Data: Upgrade Phase vs Conformance Phase

Upgrade jobs produce **two timeline files** (sorted by filename):
1. **First file** = upgrade phase timeline
2. **Second file** = conformance/e2e test phase timeline

The disruption parser (`parse_disruption.py`) attributes each disruption event to
a phase. Use the `phase_breakdown` output to separate upgrade-phase disruption
(expected within bounds) from conformance-phase disruption (unexpected — a
persistent problem).

```bash
python3 plugins/ci/skills/analyze-disruption/parse_disruption.py \
  .work/prow-job-analysis/{build_id}/logs/e2e-timelines_spyglass_*.json \
  --window 60 --format text
```

The parser output includes phase attribution for each event:
- `phase: upgrade` — disruption during upgrade (expected within thresholds)
- `phase: conformance` — disruption after upgrade completed (unexpected)

## The "Eventual Consistency" Pattern

OpenShift upgrades are eventually consistent — errors and transient failures during
the upgrade are expected and most resolve on their own. Recognize this to avoid
chasing false positives.

### Expected Transient Errors

These errors during the first 30-60 minutes of an upgrade are **normal and expected**:

| Error | Why It's Expected | When It's a Problem |
|-------|-------------------|---------------------|
| `connection refused` to API server | API server pod restarting during rollout | Persists > 10 min after rollout |
| Operator `Degraded=True` | Operator transitioning between versions | Persists > 15 min after operator pods are running |
| `etcd leader changed` | etcd member restart during rolling update | More than 3 leader changes, or happens during conformance |
| `node NotReady` | Node rebooting for MCO update | Node doesn't return to Ready within 20 min |
| `pod eviction` events | Node drain during MCO update | Evictions happening outside drain windows |
| `503 Service Unavailable` | Endpoints updating during pod rollout | Persists after all pods are running |
| `certificate not yet valid` | Cert rotation during upgrade | Persists > 5 min |
| `webhook timeout` | Webhook pod restarting | Persists > 5 min after pod is running |

### Time-Window Analysis

Correlate errors with the upgrade timeline:

```text
Upgrade started: T0
Control plane update: T0 to T0+20min
MCO node drain/reboot: T0+20min to T0+60min
Operator reconvergence: T0+60min to T0+70min
Upgrade completed: T0+70min (approximate)
Conformance tests start: T0+70min
Conformance tests end: T0+140min (approximate)

Errors in [T0, T0+70min] → Likely transient upgrade noise
Errors in [T0+70min, T0+140min] → Likely real post-upgrade issues
Errors persisting across both windows → Real problem
```

**Key rule**: If an error appears during the upgrade window but **resolves by
the time conformance tests start**, it was transient. If it persists into
conformance testing, it's a real issue.

### Why Some Test Failures During Upgrade Are Expected

The CI framework runs disruption monitoring during the upgrade phase. Some
disruption is expected:
- API backends briefly stop responding during server restarts (typically < 30s)
- Node-local connections fail when nodes reboot (MCO update)
- In-flight requests fail during pod rollover (zero-downtime rollout)

Each backend has a **disruption threshold** — an allowed amount of disruption
during upgrade. Only disruption exceeding the threshold is a failure:

```text
# Example thresholds (from openshift/origin test framework)
# kube-api new connections: 10s allowed during upgrade
# openshift-api reused connections: 5s allowed during upgrade
# image-registry: 30s allowed during upgrade (longer because of image pulls)
```

Disruption within thresholds → test passes (expected upgrade behavior)
Disruption exceeding thresholds → test fails (regression)

## Common Upgrade Failure Categories

### 1. Infrastructure Failures During Upgrade

Cloud provider issues that manifest during upgrade.

**Symptoms**:
- Node fails to reboot (instance terminated by cloud provider)
- New node fails to join after reboot (cloud networking issue)
- etcd disk I/O spike during upgrade (cloud disk performance)
- API throttling during upgrade (too many cloud API calls from MCO)

**Diagnosis**:
- Check `CloudMetrics` events in timeline data
- Check cloud provider status page for region issues
- Look for `Machine` object status changes in must-gather
- Check for cloud-specific error messages in MCO logs

**Key artifacts**:
```bash
# Machine objects
gcloud storage cp "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/oc_cmds/machines" \
  .work/prow-job-analysis/{build_id}/logs/ --no-user-output-enabled

# Cloud controller manager logs
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/pods/openshift-cloud-controller-manager*/"
```

### 2. MCO Drain/Reboot Failures

See the dedicated [MCO Drain Failures](#mco-drain-failures) section above.

**Quick identification**:
- MachineConfigPool shows `UPDATING=True DEGRADED=True`
- MCD logs show repeated `error when evicting pods ... (will retry after 5s)` and the `MCDDrainError` alert fires
- Build log shows `timeout waiting for MachineConfigPool`

### 3. Operator Incompatibility with New Version

An operator's new version crashes or can't reconcile.

**Symptoms**:
- Operator pods in CrashLoopBackOff after update
- New version logs show panic, nil pointer, or schema errors
- ClusterOperator stays Degraded after its pods were updated

**Diagnosis**:
- Check the operator's pod logs for the new version:
  ```bash
  gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/pods/openshift-{operator-namespace}/"
  ```
- Look for Go panics, nil pointer dereferences, or `unknown field` errors
- Check if the operator's CRDs were updated before or after the operator pods
- Use `fetch-new-prs-in-payload` skill to identify what PRs changed the operator

### 4. etcd Member Issues During Control Plane Rollout

etcd is the most sensitive component during upgrade.

**Symptoms**:
- `etcd leader changed` events in timeline data
- `slow fdatasync` and `apply took too long` in etcd logs
- kube-apiserver health checks failing (etcd backend unavailable)
- Quorum loss (2 of 3 members unavailable simultaneously)

**Diagnosis**:
- Check etcd logs for member restart sequencing:
  ```text
  # Healthy: one member restarts at a time, quorum maintained
  member A: stopped → started → healthy
  (pause)
  member B: stopped → started → healthy
  (pause)
  member C: stopped → started → healthy

  # Problematic: overlapping restarts
  member A: stopped → started
  member B: stopped         ← overlap, quorum may be lost
  ```
- Check `EtcdDiskCommitDuration` and `EtcdDiskWalFsyncDuration` events
- Look for `EtcdLog` events with `"apply request took too long"` or `"waiting for ReadIndex response took too long"`

**Key artifacts**:
```bash
# etcd pod logs
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/pods/openshift-etcd/"
```

### 5. Webhook/Admission Failures Blocking Upgrades

Webhooks can block CVO manifest application.

**Symptoms**:
- CVO logs show `admission webhook denied the request`
- ClusterVersion Failing=True with webhook-related message
- CVO stuck at a particular manifest in the upgrade graph

**Diagnosis**:
- Check CVO logs for the specific webhook and manifest:
  ```bash
  gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/pods/openshift-cluster-version/"
  ```
- Identify which webhook is blocking and why
- Check if the webhook pod itself is healthy

**Common culprits**:
- OLM webhooks blocking CRD updates
- Policy webhooks (Gatekeeper, Kyverno) rejecting new resource versions
- Conversion webhooks for CRD version migration

### 6. Custom Resource Migration Failures

When CRD schemas change between versions, existing CRs may need migration.

**Symptoms**:
- Operator logs show `unable to decode` or `unknown field` errors
- CRD conversion webhook failures
- Operator can't read existing CRs after CRD update

**Diagnosis**:
- Check if CRD was updated before operator pods (schema mismatch)
- Check conversion webhook logs if the CRD has multiple stored versions
- Look for `StoredVersions` mismatches in CRD status

### 7. Storage/CSI Driver Upgrade Issues

CSI drivers updating during upgrade can cause storage disruption.

**Symptoms**:
- PVCs stuck in `Pending` state after upgrade
- Pods can't mount volumes post-upgrade
- CSI driver pods not running on all nodes post-reboot

**Diagnosis**:
- Check CSI driver pod status across nodes
- Verify CSI node plugin DaemonSet has pods on all nodes
- Check for `FailedAttachVolume` or `FailedMount` events
- Check the storage operator's ClusterOperator status

### 8. Networking (OVN/SDN) Upgrade Issues

Network plugin upgrades are particularly sensitive.

**Symptoms**:
- Pod-to-pod connectivity loss after node reboot
- OVN-Kubernetes pods crash-looping on updated nodes
- Network policy not enforced on some nodes
- DNS resolution failures (CoreDNS pods disrupted)

**Diagnosis**:
- Check OVN pod status on each node:
  ```bash
  gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/pods/openshift-ovn-kubernetes/"
  ```
- Look for `OVSVswitchdLog` events in timeline data
- Check node-to-node connectivity in disruption data (host-to-host backends)
- Verify CoreDNS pods are running and responding

**OVN/OVS upgrade sequence**:
During node reboot, OVS and OVN restart with new versions. If the new OVN version
is incompatible with the old OVN on not-yet-updated nodes, networking can break for
that node.

### 9. Certificate Rotation Failures

Certificates may rotate during upgrade windows.

**Symptoms**:
- `x509: certificate has expired` or `certificate is not yet valid`
- API server rejects connections with TLS errors
- Service-to-service communication fails with cert errors

**Diagnosis**:
- Check kube-apiserver logs for certificate-related errors
- Check if cert-manager or service-ca operator is degraded
- Verify certificate validity windows overlap the upgrade period
- Look for `certificate not valid before` errors (clock skew or premature rotation)

### 10. Timeout Failures (Upgrade Took Too Long)

The test framework has a global timeout for the upgrade phase.

**Symptoms**:
- Build log shows `timed out waiting for the condition` or `upgrade did not complete within`
- All the individual components may be fine, but the total time exceeded the limit
- ClusterVersion shows `Progressing=True` at the time of timeout

**Diagnosis**:
- Check how far the upgrade progressed (percentage in ClusterVersion message)
- Identify the slowest component (the bottleneck):
  ```text
  Check ClusterOperator events in timeline data — which operator was the last
  to reach Progressing=False?
  ```
- Check MCO node update times — if each node takes 20 minutes and there are 6
  nodes, that's 2 hours of MCO time alone
- Consider resource pressure: under-provisioned CI clusters take longer for
  everything

**Common timeout causes**:
- Slow MCO drain (PDB blocking) — 5 minutes per node adds up
- Slow image pulls (large payload images, rate limiting)
- Slow etcd compaction after upgrade
- Infrastructure bottleneck (cloud disk I/O limits)

## Distinguishing Install Failures from Upgrade Failures

Upgrade jobs install first — **an install-time failure is not an upgrade failure**.
Always determine which phase failed first.

### How to Tell: Install Phase vs Upgrade Phase

| Signal | Indicates |
|--------|-----------|
| JUnit: `install should succeed` failed | Install failure |
| JUnit: `Cluster upgrade should succeed` failed | Upgrade failure |
| Build log: no `Starting upgrade` message | Install failure (upgrade never started) |
| Build log: `Starting upgrade` present, then timeout | Upgrade failure |
| ClusterVersion history: only one entry (base version) at `Partial` | Install failure |
| ClusterVersion history: base at `Completed`, target at `Partial` | Upgrade failure |
| ClusterVersion history: base at `Completed`, target at `Completed` | Upgrade succeeded, conformance test failure |

### When to Route to Install References

If the failure is during installation (upgrade-specific analysis does not apply):
- [install failure reference](install/general.md) for general install analysis
- [metal install reference](install/metal.md) for bare metal jobs

### When to Stay in Upgrade Analysis

If install completed (ClusterVersion history shows base version at `Completed`) but
the upgrade or post-upgrade tests failed, use this document, and cross-reference:
- [disruption reference](disruption.md) for disruption during upgrade
- [resource exhaustion reference](resource-exhaustion.md) for resource issues

## Upgrade Analysis Workflow — Putting It All Together

1. **Classify the upgrade type** from the job name: minor (from-stable) vs micro, platform
   (aws/gcp/azure/metal), network plugin (ovn/sdn), special config (fips/sno/techpreview).
2. **Determine which phase failed.** Download the top-level `build-log.txt` and grep for the
   phase markers: `install should succeed` (install phase); `Starting upgrade` /
   `Upgrading cluster` (upgrade initiated); `Cluster upgrade should succeed` /
   `upgrade did not complete` (upgrade result). See also "Distinguishing Install Failures from
   Upgrade Failures" above.
3. **Gather ClusterVersion, ClusterOperator, MachineConfigPool, and node status.** Download the
   artifacts from [Key Files to Examine](#key-files-to-examine) — those paths cover every file
   needed for this step and step 5.
4. **Analyze timeline/interval data.** Locate `e2e-timelines_spyglass_*.json` and run the
   disruption parser for a phased view:
   ```bash
   python3 plugins/ci/skills/analyze-disruption/parse_disruption.py \
     .work/prow-job-analysis/{build_id}/logs/e2e-timelines_spyglass_*.json \
     --window 60 --format text
   ```
5. **Drill into the implicated component** (MCO, CVO, etcd, kube-apiserver) using the pod-log
   paths in the same table.
6. **Identify the root cause**: which phase failed, which component is at the root (trace
   degradation cascades back to the first failure), transient vs persistent (time-window
   analysis), infrastructure vs product, and whether a specific PR is implicated
   (`fetch-new-prs-in-payload`).
7. **Report**: upgrade type, failed phase, root cause with evidence, event timeline, affected
   components, and recommendation (revert PR, file bug, or infrastructure issue).

## Quick Reference: Log Patterns

### CVO Log Patterns

```text
# Upgrade started
"Cluster version operator started ... desiredUpdate=..."

# Applying manifests
"Running sync for ... (attempt N)"
"Done syncing ... (N seconds)"

# Manifest failure
"error running apply for ..."
"Unable to apply ...: ..."

# Operator not available
"Cluster operator ... is not available"
"Cluster operator ... is degraded"

# Upgrade complete
"Cluster version ... reached completion state"
```

### MCO/MCD Log Patterns

```text
# Drain initiated
"initiating drain of node ..."

# Drain progress
"drain is ongoing for node ..."
"evicted pod ... from node ..."

# PDB blocking drain
"Cannot evict pod ... it would violate the pod's disruption budget"
"eviction request failed ... pod disruption budget"

# Drain not completing (MCD retries eviction until the node update fails)
"error when evicting pods"
"will retry after"

# Config apply
"applying machine config ... to node ..."
"applying OS update"

# Reboot
"initiating reboot of node ..."
"node ... has rebooted"

# Node ready
"node ... has become ready"
"node ... config matches desired"
```

### etcd Log Patterns During Upgrade

```text
# Member restart (expected, one at a time)
"etcdserver: starting member ..."
"rafthttp: started HTTP pipelining with peer ..."

# Leader change (expected during rolling update, one per member restart)
"raft.node: ... elected leader ..."

# Disk pressure (potential problem)
"slow fdatasync ... took ..."
"apply request took too long ... took ..."

# Quorum concern
"etcdserver: request timed out"
"etcdserver: leader changed"
"waiting for ReadIndex response took too long"

# WAL sync issue
"wal: sync duration ... exceeded threshold ..."
```

### ClusterOperator Condition Patterns in Timeline

Timeline `ClusterOperator` events carry these `humanMessage` patterns (full event structure is
shown under [Reading ClusterOperator Conditions Timeline](#reading-clusteroperator-conditions-timeline)):

- `condition/Progressing changed: False -> True` — operator starting update (expected)
- `condition/Degraded changed: False -> True` — operator degraded (may be transient)
- `condition/Degraded changed: True -> False` — transient degradation resolved
- `condition/Progressing changed: True -> False` — operator update complete (expected)

## Advanced: Identifying Suspect PRs After Upgrade Failure

Once the root cause involves a specific operator or component, use the
`fetch-new-prs-in-payload` skill to identify what changed:

1. **Get the payload tag** from prowjob.json or ClusterVersion
2. **List PRs new in this payload** compared to the previous accepted payload
3. **Filter to the affected component/repo**
4. **Review those PRs** for changes that could cause the failure

This is especially powerful for micro-upgrade failures where the delta between
versions is small — you can often pinpoint the exact PR that introduced the
regression.
