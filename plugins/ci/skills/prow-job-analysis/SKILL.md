---
name: prow-job-analysis
description: Use this skill when debugging a failed Prow CI job.
---

# Prow Job Analysis

Analyze failures in OpenShift Prow CI jobs. Identify the job type, inspect artifacts, classify
the failure, and route to the specialized reference for deep analysis.

## Input Format

The user will provide:

1. **Prow job URL** (required) — Prow UI or gcsweb URL
   - `https://prow.ci.openshift.org/view/gs/test-platform-results/logs/<job>/<build_id>`
   - `https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/...`

2. **Test name** (optional) — specific failed test to focus on

3. **Flags** (optional):
   - `--backends <list>` — focus disruption analysis on specific backends

## Prerequisites

- **gcloud CLI**: `which gcloud` (public bucket — no auth required)
- **Python 3.6+**: `which python3`
- **jq**: `which jq`

## Investigation Workflow

### Step 1: Parse URL and Extract Metadata

1. Find `test-platform-results/` in the URL and extract the bucket path
2. Extract `build_id` — pattern `(\d{10,})` in the path
3. Construct GCS base: `gs://test-platform-results/{bucket-path}/`

### Step 2: Fetch prowjob.json

Use the `fetch-prowjob-json` skill to get job metadata. Extract:
- **Job name** from `.spec.job`
- **Target** from `--target=` in ci-operator args
- **Job state** from `.status.state`
- **Refs** (org, repo, PR number) from `.spec.refs`

### Step 3: Classify Job Type from Name

Parse the job name to determine the environment and expected failure modes:

| Pattern in Name | Job Type | Key Implications |
|-----------------|----------|------------------|
| `upgrade` | Upgrade job | Installs first, then upgrades — see [upgrade reference](references/upgrade.md) |
| `metal`, `baremetal` | Bare metal | Uses dev-scripts + Metal3/Ironic — see [metal install reference](references/install/metal.md) |
| `hypershift` | HyperShift | Hosted control planes — see [hypershift reference](references/hypershift.md) |
| `fips` | FIPS-enabled | Watch for crypto/TLS errors |
| `ipv6`, `dualstack` | IPv6/dualstack | Often disconnected, uses mirror registry |
| `single-node`, `sno` | Single-node | Resource exhaustion more likely |
| `aggregated-` prefix | Aggregated | Statistical analysis of multiple runs — see [aggregated reference](references/aggregated.md) |
| `aws`, `gcp`, `azure` | Cloud platform | Platform-specific errors — see [cloud provider reference](references/cloud-provider-errors.md) |
| `techpreview` | Tech preview | Feature gates enabled, features may be unstable |
| `rhcos9`, `rhcos10`, `rhcos9_10`, `rt` | RHCOS variant / RT kernel | OS variant pinned or heterogeneous; OS-level differences (kernel/systemd/SELinux) — see [operating system changes reference](references/operating-system-changes.md) |

### Step 4: Download Key Artifacts

```bash
mkdir -p .work/prow-job-analysis/{build_id}/logs

# Build log (always)
gcloud storage cp gs://test-platform-results/{bucket-path}/build-log.txt \
  .work/prow-job-analysis/{build_id}/logs/ --no-user-output-enabled

# JUnit XML (always — identifies failed tests/steps)
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/**/junit*.xml" 2>/dev/null

# Node journals (always, when the job created a cluster) — required input for the
# Step 5 OS-layer check. Gzip-compressed WITHOUT a .gz extension: zcat/zgrep only.
gcloud storage cp -r \
  "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/nodes" \
  .work/prow-job-analysis/{build_id}/ --no-user-output-enabled 2>/dev/null || true
```

### Step 5: Classify Failure and Route to Reference

Examine the build log and JUnit results to classify the failure, then consult the
appropriate reference file for detailed analysis procedures.

#### OS-layer evidence check (mandatory for every job, before routing)

Operating-system (RHCOS) layer breakage frequently masquerades as an unrelated product
failure: a single RHCOS bump swaps the kernel, cri-o, systemd, NetworkManager, and SELinux
policy across the whole cluster at once, so the real cause surfaces as a symptom in some
other domain. Before selecting a row from the routing table, complete BOTH steps:

**1. Compare runtime versions across boots in the node journals** (downloaded in
Step 4; gzip-compressed **without** a `.gz` extension — plain `grep` silently matches
nothing, use `zcat`/`zgrep`):

```bash
# Runtime versions per boot. End-of-run snapshots (oc_cmds/nodes, nodes.json)
# show only the final version; changes within the run are visible only here.
zgrep -hE "Starting CRI-O, version|Container runtime initialized" \
  .work/prow-job-analysis/{build_id}/nodes/*/journal | sort | uniq -c
```

**2. Scan the build log, JUnit, `oc_cmds` (node / clusteroperator status),
MachineConfig data, and the journals for these signals:**

- `NetworkPluginNotReady`, or a missing CNI config (`/etc/cni/net.d` empty / no CNI plugin)
- A `ContainerRuntimeVersion` change on nodes (cri-o version bump between runs)
- A MachineConfigDaemon (MCD) rendered-config diff touching `passwd`, `files`, or `units`
- Multiple nodes going `NotReady` after a reboot
- `CreateContainerError`, `RunContainerError`, or OCI runtime errors (`crun` / `runc`)
- Kernel `panic`, `BUG`, `Oops`, or `soft lockup` in node journals or the serial console
- `avc: denied` / SELinux denials
- The same failure spanning multiple unrelated jobs at a payload boundary

If step 1 shows more than one runtime version on any node, or any step-2 signal is
present, the RHCOS layer is implicated: still route via the table below using whichever
reference matches the surface symptom, but **also** read
[operating-system-changes.md](references/operating-system-changes.md) alongside it.
Never clear the OS layer from end-of-run snapshots alone.

## Failure Routing Table

| Failure Signal | Reference | When to Use |
|----------------|-----------|-------------|
| `install should succeed` fails in JUnit | [Install — General](references/install/general.md) | Install failed at config/infra/bootstrap/cluster-creation/operator-stability stage |
| Metal/baremetal job + install failure | [Install — Metal](references/install/metal.md) | Bare-metal install (dev-scripts, Metal3/Ironic, libvirt) — use alongside Install — General |
| A test failed (start here) | [Flaky Test Identification](references/flaky-test-identification.md) | Triage entry for any failing test: classify infra vs product regression vs flake, then route onward |
| Confirmed regression in a plain e2e test | [Test Failure Root-Cause](references/test-failure.md) | Root-cause a real product regression in a plain (non-extension/install/upgrade) e2e test — e.g. `[sig-network] ... should serve endpoints`: test source, cluster state, originating error |
| `*-tests-ext` extension binary error | [Test Extension Binaries](references/test-extension-binaries.md) | OTE extension-binary extraction/discovery/version-skew failures — not core `openshift-tests` |
| Disruption events in intervals | [Disruption](references/disruption.md) | API backends stopped responding; interpret interval/timeline data (cause vs symptom vs noise) |
| Upgrade-phase failure or regression | [Upgrade](references/upgrade.md) | CVO stuck, operators degraded, MCO drain/reboot stalls, or version skew during upgrade |
| HyperShift / HCP job failure | [HyperShift](references/hypershift.md) | Hosted control planes — correlate management and hosted clusters |
| `aggregated-` job failure | [Aggregated Jobs](references/aggregated.md) | Statistical regression analysis across parallel child runs |
| Cloud API errors, quota, throttling | [Cloud Provider Errors](references/cloud-provider-errors.md) | AWS/GCP/Azure API/quota/provisioning failures before/during cluster creation |
| Node NotReady, OOM, disk pressure | [Resource Exhaustion](references/resource-exhaustion.md) | CPU/memory/disk/PID/etcd exhaustion, eviction, unschedulable pods |
| DNS, OVN, registry/pull, ingress errors | [Networking](references/networking.md) | OVN-Kubernetes/SDN, DNS, image pull/registry, load balancer/ingress, network policy |
| Container-start (cri-o), kernel panic, NetworkManager, RHCOS variant-isolated failure | [Operating System Changes](references/operating-system-changes.md) | Node OS (RHCOS) layer — cri-o/crun, kernel, systemd, NetworkManager, SELinux, or an RHCOS bump in the payload |
| Lease/quota, ci-operator, Prow infra | [CI Infrastructure](references/ci-infrastructure-changes.md) | Distinguish "product broke" from "CI config changed"; ci-operator, step registry, leases |
| Need a specific artifact file | [Artifacts](references/artifacts.md) | Artifact directory structure, paths, and gcloud fetch commands |

## Common Artifact Paths

These are the most frequently needed artifacts. See [artifacts reference](references/artifacts.md) for the complete directory structure.

| Path | Description |
|------|-------------|
| `build-log.txt` | Top-level ci-operator log |
| `artifacts/{target}/openshift-e2e-test/build-log.txt` | E2E test console log |
| `artifacts/{target}/openshift-e2e-test/artifacts/junit/` | JUnit XML results |
| `artifacts/{target}/openshift-e2e-test/artifacts/junit/e2e-timelines_spyglass_*.json` | Disruption timeline data |
| `artifacts/{target}/gather-extra/artifacts/oc_cmds/` | Cluster state snapshots |
| `artifacts/{target}/gather-extra/artifacts/pods/` | Pod logs by namespace |
| `artifacts/{target}/gather-extra/artifacts/audit_logs/` | API server audit logs |
| `artifacts/{target}/gather-must-gather/artifacts/must-gather.tar` | Must-gather archive |
| `prowjob.json` | Job metadata and timing |

## URL Formats

Both formats are accepted and interchangeable:

```text
# Prow UI
https://prow.ci.openshift.org/view/gs/test-platform-results/logs/{job}/{build_id}

# gcsweb (direct GCS browser)
https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/{job}/{build_id}
```

The GCS bucket is always `test-platform-results`, publicly accessible, no auth required.

## Tips

- **Start with build-log.txt** — it shows the ci-operator orchestration and which steps failed
- **JUnit XML is the source of truth** for test pass/fail status
- **Job name encodes environment** — always parse it before diving into logs
- **Check `prowjob.json`** for timing, payload tag, and whether the job timed out
- **Upgrade jobs install first** — an "upgrade" job failing at install is an install failure, not an upgrade failure
- **Aggregated jobs** need statistical analysis, not individual test debugging
- **Use `.work/prow-job-analysis/{build_id}/`** as the working directory for downloads
