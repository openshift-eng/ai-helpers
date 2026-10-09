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
   - `https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/<job>/<build_id>`
   - `https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results-public/...`

2. **Test name** (optional) — specific failed test to focus on

3. **Flags** (optional):
   - `--backends <list>` — focus disruption analysis on specific backends

## Prerequisites

- **Python 3.7+**: `which python3`
- **jq**: `which jq`
- **gcloud CLI** (recommended, not required): `which gcloud` — fastest access to the
  public bucket (no auth required). Without it, every artifact operation works over
  plain HTTPS: [prow_job_artifact_search.py](prow_job_artifact_search.py)
  (stdlib-only `list`/`search`/`fetch`; `fetch --tail` reads a log's end) or `curl` against
  `https://storage.googleapis.com/test-platform-results-public/...`.

## Investigation Workflow

### Step 1: Parse URL and Extract Metadata

1. Find `/view/gs/<bucket>/` (Prow UI) or `/gcs/<bucket>/` (gcsweb) in the URL.
   Any non-empty bucket segment is accepted.
2. Extract the object path after the bucket name, then `build_id` — pattern
   `(\d{10,})` in the path.
3. Construct GCS base: `gs://{bucket}/{bucket-path}/` using the URL bucket
   as-is, including `prow-artifact-archive`. A private bucket will 403.

### Step 2: Fetch prowjob.json

Use the `fetch-prowjob-json` skill to get job metadata. Extract:
- **Job name** from `.spec.job`
- **Target** from `--target=` in ci-operator args
- **Job state** from `.status.state`
- **Refs** (org, repo, PR number) from `.spec.refs`

### Step 3: Read the Pre-Digested Failure Summaries

openshift-tests and the gather steps already summarize most of what you need. Read these
small (KB-sized) files **before** downloading logs, journals, or must-gather — they usually
name the failed step, the failed tests, the cluster shape, and known failure signatures.
Each may be absent; absence is itself a signal (noted below).

```bash
# 1. ci-operator verdict: which step failed and why (tail only — the log can exceed 500 KB)
curl -s -r -20000 "https://storage.googleapis.com/{bucket}/{bucket-path}/build-log.txt" \
  | grep -aE "Reporting job state|could not run steps|step .* failed"

# 2. Locate the per-job summaries (one per test step that ran openshift-tests)
gcloud storage ls "gs://{bucket}/{bucket-path}/artifacts/**/test-failures-summary_*.json"
gcloud storage ls "gs://{bucket}/{bucket-path}/artifacts/job_labels/*.json"
gcloud storage ls "gs://{bucket}/{bucket-path}/artifacts/{target}/gather-extra/artifacts/junit/"
```

| Artifact | What it answers | Notes |
|----------|-----------------|-------|
| `build-log.txt` (tail) | Failed step and ci-operator `reason` (e.g. `...:executing_multi_stage_test`) | A setup reason (`importing_release`, `acquiring_lease`, `pod_pending`, …) means the test never got a fair run — see [flaky-test-identification.md](references/flaky-test-identification.md#a-ci-operator-failure-reason-means-the-test-never-got-a-fair-run) |
| `{target}/*/artifacts/junit/test-failures-summary_*.json` | `.Tests[].Test.Name` — the failed tests; `.ClusterData` — release, platform, network, topology, region/zone, `ClusterVersionHistory` | Names only, no error text (get that from `junit_e2e_*.xml` or the step `build-log.txt`). `test-failures-summary_monitor_*.json` covers monitor tests. More than one `ClusterVersionHistory` entry means an upgrade ran. **Absent** → openshift-tests never ran: treat as install/infra |
| `artifacts/job_labels/*.json` | Sippy symptoms already matched on this run (e.g. `OVSExcessivePollIntervals200`, `QuayCDNImageConfigEOF`) | Skip `label-summary.html`. Context, not cause — see [flaky-test-identification.md](references/flaky-test-identification.md#symptom-labels-correlation-not-cause). `ci:diagnose-job-run-symptoms` explains each label |
| `gather-extra/artifacts/junit/junit_install_status.xml` | One testcase per ClusterOperator; a failure means it was unavailable, degraded, or progressing **at gather time** | Despite the name it is not install-specific; useful for every job that created a cluster |
| `gather-extra/artifacts/junit/junit_symptoms.xml` | Gather-time grep of pods and node journals for panics, segfaults, quota errors | A failure here is an OS-layer trigger (Step 6) |
| `{target}/*/artifacts/junit/alerts_*.json` | Every alert that fired, with namespace, level, and duration | Read when an alert test failed — see [alerts.md](references/alerts.md) |

Optionally, `ci:fetch-job-run-summary {build_id}` returns the failed tests **with** error
messages, grouped by SIG. It works only after Sippy imports the run (typically a few hours
after it finishes), and its output can run to megabytes — write it to a file under
`.work/prow-job-analysis/{build_id}/` and read the per-test headers rather than printing it.

### Step 4: Classify Job Type from Name

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
| `runc`, `crun` | Container runtime override | Non-default OCI runtime; compare against the sibling job without the override before blaming the product — see [operating system changes reference](references/operating-system-changes.md) |
| `rhcos9`, `rhcos10`, `rhcos9_10`, `rt` | RHCOS variant / RT kernel | OS variant pinned or heterogeneous; OS-level differences (kernel/systemd/SELinux) — see [operating system changes reference](references/operating-system-changes.md) |

### Step 5: Download Key Artifacts

```bash
mkdir -p .work/prow-job-analysis/{build_id}/logs

# Build log (always)
gcloud storage cp gs://{bucket}/{bucket-path}/build-log.txt \
  .work/prow-job-analysis/{build_id}/logs/ --no-user-output-enabled

# JUnit XML (always — identifies failed tests/steps)
gcloud storage ls "gs://{bucket}/{bucket-path}/artifacts/**/junit*.xml" 2>/dev/null

# Node journals — ONLY when the Step 6 OS-layer check is triggered (often 10-30 MB).
# Gzip-compressed WITHOUT a .gz extension: zcat/zgrep only.
gcloud storage cp -r \
  "gs://{bucket}/{bucket-path}/artifacts/{target}/gather-extra/artifacts/nodes" \
  .work/prow-job-analysis/{build_id}/ --no-user-output-enabled 2>/dev/null || true
```

### Step 6: Classify Failure and Route to Reference

Use the Step 3 summaries, the build log, and JUnit results to classify the failure, then consult the
appropriate reference file for detailed analysis procedures.

#### OS-layer evidence check (conditional, before routing)

Operating-system (RHCOS) layer breakage frequently masquerades as an unrelated product
failure: a single RHCOS bump swaps the kernel, cri-o, systemd, NetworkManager, and SELinux
policy across the whole cluster at once, so the real cause surfaces as a symptom in some
other domain. The full check needs the node journals, so first decide whether it applies
using artifacts you already have.

**Triggers — run the full check if ANY holds:**

1. **Upgrade job**, or `ClusterVersionHistory` in `test-failures-summary_*.json` has more
   than one entry. Nodes reboot into a new RHCOS mid-run, and OS-layer causes (cri-o
   regressions, systemd stop timeouts on reboot) are often visible only in the journals.
2. **OS/runtime variant in the job name**: `rhcos9`, `rhcos10`, `rhcos9_10`, `rt`, `runc`, `crun`.
3. **Node-scoped failure**: a failed `[sig-node]` test, a node-lifecycle monitor test
   (e.g. `detects unexpected not ready node`), or `machine-config` unavailable/degraded in
   `junit_install_status.xml` or `oc_cmds/clusteroperators`.
4. **Any signal below** in the build log, JUnit failure text, `job_labels/`,
   `junit_symptoms.xml`, or `oc_cmds/nodes` / `oc_cmds/clusteroperators`:
   - `NetworkPluginNotReady`, or a missing CNI config (`/etc/cni/net.d` empty / no CNI plugin)
   - A `ContainerRuntimeVersion` change on nodes (cri-o version bump between runs)
   - A MachineConfigDaemon (MCD) rendered-config diff touching `passwd`, `files`, or `units`
   - Multiple nodes going `NotReady` after a reboot
   - `CreateContainerError`, `RunContainerError`, or OCI runtime errors (`crun` / `runc`)
   - Kernel `panic`, `BUG`, `Oops`, or `soft lockup`, or a failed panic/segfault case in
     `junit_symptoms.xml`
   - `avc: denied` / SELinux denials
   - The same failure spanning multiple unrelated jobs at a payload boundary
5. **Unexplained failure**: routing below did not yield a root cause, and you are about to
   conclude "flake" or "unknown".

**Full check** (download the journals per Step 5, then complete BOTH steps):

**1. Compare runtime versions across boots in the node journals** (gzip-compressed
**without** a `.gz` extension — plain `grep` silently matches nothing, use `zcat`/`zgrep`):

```bash
# Runtime versions per boot. End-of-run snapshots (oc_cmds/nodes, nodes.json)
# show only the final version; changes within the run are visible only here.
zgrep -hE "Starting CRI-O, version|Container runtime initialized" \
  .work/prow-job-analysis/{build_id}/nodes/*/journal | sort | uniq -c
```

**2. Scan the journals** for the trigger-4 signals, plus failed units and stop timeouts
around reboots (`Stopping timed out. Killing.`, `Failed with result 'timeout'`).

If step 1 shows more than one runtime version on any node, or step 2 finds a signal, the
RHCOS layer is implicated: still route via the table below using whichever reference
matches the surface symptom, but **also** read
[operating-system-changes.md](references/operating-system-changes.md) alongside it.
Never clear the OS layer from end-of-run snapshots alone.

**No trigger** (e.g. a ci-operator setup reason with no cluster, or failures confined to
tests whose error text names a non-node cause): skip the journals, and state in the
report that the OS-layer check was skipped because no trigger applied. Skipping is not
clearing — do not claim the OS layer was ruled out.

## Failure Routing Table

| Failure Signal | Reference | When to Use |
|----------------|-----------|-------------|
| `install should succeed` fails in JUnit | [Install — General](references/install/general.md) | Install failed at config/infra/bootstrap/cluster-creation/operator-stability stage |
| Metal/baremetal job + install failure | [Install — Metal](references/install/metal.md) | Bare-metal install (dev-scripts, Metal3/Ironic, libvirt) — use alongside Install — General |
| A test failed (start here) | [Flaky Test Identification](references/flaky-test-identification.md) | Triage entry for any failing test: classify infra vs product regression vs flake, then route onward |
| Confirmed regression in a plain e2e test | [Test Failure Root-Cause](references/test-failure.md) | Root-cause a real product regression in a plain (non-extension/install/upgrade) e2e test — e.g. `[sig-network] ... should serve endpoints`: test source, cluster state, originating error |
| `*-tests-ext` extension binary error | [Test Extension Binaries](references/test-extension-binaries.md) | OTE extension-binary extraction/discovery/version-skew failures — not core `openshift-tests` |
| Alert test fails (`... alerts in firing state ...`, `[invariant] alert/...`, `No alerts without an explicit test ...`) | [Alerts](references/alerts.md) | Name the alert, pin its window, trace the labelled object to its originating error, and separate blocking failures from fail+pass flakes |
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

Job-name routing (Step 4) picks which reference to read. Failure classification (`install` | `test` | `upgrade` | `infra`) follows the root cause, not the job name.

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
| `artifacts/{target}/gather-must-gather/artifacts/must-gather.tar.gz` | Must-gather archive |
| `prowjob.json` | Job metadata and timing |

## URL Formats

Both formats are accepted and interchangeable:

```text
# Prow UI
https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/{job}/{build_id}

# gcsweb (direct GCS browser)
https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results-public/logs/{job}/{build_id}
```

Use the bucket from Step 1 as named in the URL (`test-platform-results-public`
or `prow-artifact-archive` when the URL names it).

## Tips

- **Start with the Step 3 summaries** — the build-log tail, `test-failures-summary_*.json`, and `job_labels/` answer most first questions for a few KB
- **JUnit XML is the source of truth** for test pass/fail status and error text
- **Job name encodes environment** — always parse it before diving into logs
- **Check `prowjob.json`** for timing, payload tag, and whether the job timed out
- **Upgrade jobs install first** — an "upgrade" job failing at install is an install failure, not an upgrade failure
- **Aggregated jobs** need statistical analysis, not individual test debugging
- **Use `.work/prow-job-analysis/{build_id}/`** as the working directory for downloads
