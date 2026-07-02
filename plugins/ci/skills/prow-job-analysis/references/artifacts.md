# Artifacts Reference

Directory structure, file contents, and access patterns for Prow CI job artifacts in the
`test-platform-results` GCS bucket. Use it to locate and interpret files when investigating
job failures.

---

## GCS Bucket and Access

- **Bucket**: `test-platform-results` (publicly accessible, no authentication required)
- **Base URI**: `gs://test-platform-results/{bucket-path}/`
- **Prow UI URL**: `https://prow.ci.openshift.org/view/gs/test-platform-results/{bucket-path}`
- **gcsweb URL**: `https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/{bucket-path}`

**Important**: Prow URLs may show `origin-ci-test` in the path (e.g.,
`/view/gs/origin-ci-test/logs/...`), but the actual GCS bucket is always
`test-platform-results`. Always use `gs://test-platform-results/...` for `gcloud storage`
commands.

### URL Formats

Both formats are interchangeable:

```text
# Prow UI
https://prow.ci.openshift.org/view/gs/test-platform-results/{type}/{job-name}/{build-id}

# gcsweb (direct GCS browser)
https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/{type}/{job-name}/{build-id}
```

### Bucket Path by Job Type

| Job Type | Bucket Path Pattern | Example |
|----------|-------------------|---------|
| **Periodic** | `logs/{job-name}/{build-id}` | `logs/periodic-ci-openshift-release-master-ci-4.21-e2e-aws-ovn/1983307151598161920` |
| **Presubmit** | `pr-logs/pull/{org}_{repo}/{pr-number}/{job-name}/{build-id}` | `pr-logs/pull/openshift_installer/8123/pull-ci-openshift-installer-main-e2e-aws/1962527613477982208` |
| **Postsubmit** | `logs/{job-name}/{build-id}` | `logs/branch-ci-openshift-installer-main-images/1983307151598161920` |

Note: Periodic and postsubmit jobs share the same `logs/` prefix. Presubmit jobs use
`pr-logs/pull/` and include the org, repo, and PR number in the path.

---

## Top-Level Structure

Every Prow CI job produces these files at the root of its artifact directory:

```text
{build-id}/
├── build-log.txt                  # ci-operator orchestration log
├── prowjob.json                   # Job metadata, timing, refs, state
├── clone-log.txt                  # Git clone output (stdout/stderr)
├── clone-records.json             # Structured clone timing data
├── finished.json                  # Job completion metadata (result, timestamp)
├── started.json                   # Job start metadata (timestamp, pull refs)
├── podinfo.json                   # Pod lifecycle, container statuses, events
└── artifacts/
    ├── {target}/                  # Main test step artifacts (see below)
    ├── ci-operator-step-graph.json   # Step dependency graph with timing
    ├── ci-operator.log            # ci-operator internal log
    └── job_labels/                # Machine-detected symptom labels (JSON)
```

---

## Root-Level Files

### `build-log.txt` — ci-operator Orchestration Log

The **primary entry point** for any job investigation: stdout/stderr of the ci-operator
process that orchestrates the multi-stage test.

**What it contains**:
- ci-operator startup and configuration
- Image resolution and building steps
- Lease acquisition attempts
- Multi-stage test step execution (pre/test/post phases)
- Step pass/fail status with timing
- Final job result

**Common patterns to search for**:
```text
# Failures
level=error                        # ci-operator errors
"failed to"                        # General failure messages
"context deadline exceeded"        # Timeout failures
"failed to acquire lease"          # Cloud quota lease timeout
"failed to resolve release"        # Image resolution failure

# Step execution
"Running multi-stage test"         # Multi-stage test begins
"Step .* succeeded"                # Individual step completed
"Step .* failed"                   # Individual step failed
"Run multi-stage test pre phase"   # Phase execution
```

**Size**: Typically 10KB–500KB. Use `--max-bytes` when fetching via the artifact search script.

### `prowjob.json` — Job Metadata

The serialized ProwJob Kubernetes resource, with full metadata about the job run.

**Key fields**:

| JSON Path | Description |
|-----------|-------------|
| `.spec.job` | Full job name (e.g., `periodic-ci-openshift-release-master-ci-4.21-e2e-aws-ovn`) |
| `.spec.type` | Job type: `periodic`, `presubmit`, or `postsubmit` |
| `.spec.refs` | Git refs — org, repo, base_ref, pulls (for presubmit) |
| `.spec.extra_refs` | Additional repo checkouts |
| `.spec.pod_spec.containers[0].args` | ci-operator arguments including `--target=` |
| `.status.state` | Final state: `success`, `failure`, `aborted`, `pending`, `error` |
| `.status.build_id` | Unique build identifier |
| `.status.startTime` | ISO 8601 job start timestamp |
| `.status.pendingTime` | When the job entered pending state |
| `.status.completionTime` | ISO 8601 job completion timestamp |
| `.status.description` | Human-readable status message |
| `.metadata.labels` | Labels including `prow.k8s.io/type`, `prow.k8s.io/job` |
| `.metadata.annotations` | Annotations including release tag information |

**Extracting key values**:
```bash
# Job name (used for artifact paths)
jq -r '.spec.job' prowjob.json

# Target name (the ci-operator --target value)
jq -r '.spec.pod_spec.containers[0].args[]' prowjob.json | grep -oP '(?<=--target=)\S+'

# Job timing
jq '{start: .status.startTime, completion: .status.completionTime, state: .status.state}' prowjob.json

# PR info (presubmit only)
jq '.spec.refs.pulls[0] | {number, author, sha}' prowjob.json

# Release payload tag
jq -r '.metadata.annotations["release.openshift.io/tag"] // empty' prowjob.json

# Upgrade source (upgrade jobs)
jq -r '.metadata.annotations["release.openshift.io/from-tag"] // empty' prowjob.json
```

**Important for PR jobs**: The `{target}` (from `--target=`) and the `{JOB_NAME}` (from
`.spec.job`) often differ for presubmit jobs. Use `{JOB_NAME}` **only** for the top-level Prow
bucket path (e.g., `logs/{JOB_NAME}/{build-id}`); keep `artifacts/{target}/...` for step-level
artifacts. Do not substitute one for the other.

### `podinfo.json` — Pod Lifecycle Details

Full Kubernetes Pod spec/status and events for the job pod — infrastructure-level detail on
the execution environment.

**What it contains**:
- Which build cluster node the pod ran on
- Init and main container exit codes and durations
- Image pull times and container startup sequence
- Scheduling events and warnings (OOM kills, evictions, preemptions)
- Container resource limits and requests

**When to check**: Infrastructure-level issues — why a pod was slow to start, whether
containers crashed or were OOM-killed, or which node hosted the job.

### `finished.json` — Job Completion Metadata

Written by Prow when the job completes. Contains:

| Field | Description |
|-------|-------------|
| `timestamp` | Unix timestamp of job completion |
| `passed` | Boolean — whether the job passed |
| `result` | Result string: `SUCCESS`, `FAILURE`, `ABORTED` |
| `revision` | Git SHA tested |

### `started.json` — Job Start Metadata

Written by Prow when the job starts. Contains:

| Field | Description |
|-------|-------------|
| `timestamp` | Unix timestamp of job start |
| `pull` | PR refs (for presubmit jobs) |
| `repos` | Map of repo → SHA being tested |

### `clone-log.txt` — Git Clone Output

Raw stdout/stderr from git clone. Use to debug clone failures or confirm which commits were
checked out.

### `clone-records.json` — Clone Timing Data

Structured per-step clone timing. Use to diagnose slow or failed clones.

---

## Artifacts Directory

### `ci-operator-step-graph.json` — Step Dependency Graph

Shows all multi-stage test steps, their dependencies, execution order, and timing. Each
step entry includes:
- Step name and phase (pre/test/post)
- Start and completion timestamps
- Dependencies on other steps
- Pass/fail status

**When to use**: When the phase-level testcases in JUnit XML are absent, use this artifact
to determine which phase a failed step belongs to and the overall execution timeline.

### `ci-operator.log` — ci-operator Internal Log

More detailed than `build-log.txt`: image resolution details, step scheduling decisions, and
error details.

### `job_labels/` — Symptom Labels

Machine-detected symptom labels attached by the CI system. Each JSON file describes a
detected environmental pattern (e.g., "test failures during high CPU events").

These are environmental observations, NOT root causes. Use them as investigative context —
they may explain failures when correlated with other evidence, but root cause analysis is
still required.

```bash
# List symptom labels
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/job_labels/" 2>/dev/null

# Download all symptom JSON files (exclude HTML summary)
gcloud storage cp "gs://test-platform-results/{bucket-path}/artifacts/job_labels/*.json" \
  local/job_labels/ --no-user-output-enabled 2>/dev/null || true
```

---

## Test Step Artifacts (`artifacts/{target}/`)

The `{target}` directory is named after the ci-operator `--target=` value (e.g.,
`e2e-aws-ovn`, `e2e-gcp-ovn-rt-rhcos10-techpreview`). It contains subdirectories for each
multi-stage test step that ran.

### Step Directory Naming Conventions

Step directories follow the step-registry naming in `openshift/release`. Common patterns:

| Step Directory | Purpose |
|---------------|---------|
| `ipi-install-install` | IPI installation step |
| `ipi-install-heterogeneous` | Heterogeneous cluster install |
| `ipi-deprovision-deprovision` | Cloud resource teardown |
| `openshift-e2e-test` | E2E test execution |
| `gather-extra` | Extra diagnostics collection |
| `gather-must-gather` | Must-gather archive collection |
| `gather-audit-logs` | API audit log collection |
| `baremetalds-devscripts-setup` | Metal dev-scripts setup |
| `baremetalds-devscripts-gather` | Metal artifact gathering |
| `ofcir-acquire` | Metal host acquisition (OFCIR) |
| `dump-management-cluster` | HyperShift management dump |

Each step directory typically contains:
```text
{step-name}/
├── build-log.txt          # Step console output (stdout/stderr)
└── artifacts/             # Step-specific artifacts (varies by step)
```

---

## E2E Test Artifacts

### `openshift-e2e-test/` — E2E Test Output

The primary test step for most OpenShift CI jobs.

```text
artifacts/{target}/openshift-e2e-test/
├── build-log.txt                              # E2E test console output (test runner log)
└── artifacts/
    ├── junit/
    │   ├── junit_e2e_*.xml                    # E2E test results (JUnit XML)
    │   └── e2e-timelines_spyglass_*.json      # Disruption interval/timeline data
    └── e2e-*.json                             # Additional test metadata
```

### `build-log.txt` (Step-Level)

Each step has its own `build-log.txt` (stdout/stderr of that step). For `openshift-e2e-test`
it holds the full E2E test runner output:
- Test names as they execute
- Pass/fail results per test
- Stack traces for failed tests
- Timing information

**Common patterns**:
```text
FAIL                              # Test failure marker
panic:                            # Go panic in test code
"Error:"                          # Assertion errors
"Timed out"                       # Timeout failures
"STEP:"                           # Ginkgo test step markers
```

---

## JUnit XML Files

Structured test results — the primary source for which tests failed and why.

### Locations and Naming Patterns

```bash
# Find all JUnit XML files
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/**/junit*.xml"
```

Common JUnit file patterns:

| File | Location | Contents |
|------|----------|----------|
| `junit_e2e_*.xml` | `{target}/openshift-e2e-test/artifacts/junit/` | E2E test results |
| `junit_operator.xml` | `artifacts/{target}/` or `artifacts/` | ci-operator step results (phase-level) |
| `junit_install.xml` | `{target}/{install-step}/artifacts/` | Installation test results |
| `junit_metal_setup.xml` | `{target}/ofcir-acquire/artifacts/` | Metal host acquisition results |
| `junit-aggregated.xml` | (see aggregated jobs below) | Aggregated job statistical results |

### JUnit XML Structure

```xml
<testsuite name="..." tests="N" failures="N" errors="N">
  <testcase name="test name" classname="class" time="seconds">
    <!-- Passing test: no child elements -->
  </testcase>
  <testcase name="test name" classname="class" time="seconds">
    <failure message="error summary">
      Full error output and stack trace
    </failure>
  </testcase>
  <testcase name="test name" classname="class">
    <error message="error summary">
      Error details
    </error>
  </testcase>
  <testcase name="test name" classname="class">
    <skipped message="reason"/>
  </testcase>
</testsuite>
```

### ci-operator Phase-Level JUnit (`junit_operator.xml`)

The ci-operator JUnit includes phase-level testcases that classify each step:

- `"Run multi-stage test pre phase"` — setup/installation steps
- `"Run multi-stage test test phase"` — functional test steps
- `"Run multi-stage test post phase"` — gather/cleanup steps

Use these to determine which phase a failed step belongs to. If these entries are absent
(some jobs omit them), fall back to `ci-operator-step-graph.json`.

### Installation JUnit (`junit_install.xml`)

Testcases for the installation process. Failed test names follow the pattern
`install should succeed: <stage>`. Installation failure stages:

| Stage | Meaning | Primary Artifacts |
|-------|---------|-------------------|
| `configuration` | Install-config validation failed | Installer log only |
| `infrastructure` | Cloud resource creation failed | Installer log, cloud API errors |
| `cluster bootstrap` | Bootstrap node failed | Log bundle (bootkube, etcd, kube-apiserver) |
| `cluster creation` | Operators failed to deploy | gather-must-gather, operator logs |
| `cluster operator stability` | Operators didn't stabilize | gather-must-gather, operator status |
| `other` | Unknown failure mode | All available logs |

### Aggregated Job JUnit (`junit-aggregated.xml`)

Located at:
```text
artifacts/release-analysis-aggregator/openshift-release-analysis-aggregator/artifacts/
  release-analysis-aggregator/{job-name}/{payload-tag}/junit-aggregated.xml
```

Each `<testcase>` contains `<system-out>` with YAML-formatted data including `passes:`,
`failures:`, and `skips:` lists. Each entry includes:
- `jobrunid` — build ID of the underlying job run
- `humanurl` — Prow URL for the job run
- `gcsartifacturl` — direct GCS artifact link

---

## Interval / Timeline Files (`e2e-timelines_spyglass_*.json`)

Structured event data from the E2E test framework — the primary source for disruption
analysis and cluster activity correlation.

### Location

```bash
# Find all interval/timeline files
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/**/e2e-timelines_spyglass_*.json"
```

Typical location:
```text
artifacts/{target}/openshift-e2e-test/artifacts/junit/e2e-timelines_spyglass_{timestamp}.json
```

**Upgrade jobs** typically have two timeline files — one per phase (upgrade and conformance).
The first file (sorted by filename) is the upgrade phase; the second is the conformance/e2e
test phase.

### JSON Structure

Each item in the timeline JSON array:

```json
{
  "level": "Error",
  "source": "Disruption",
  "locator": {
    "type": "Disruption",
    "keys": {
      "backend-disruption-name": "kube-api-new-connections",
      "connection": "new",
      "disruption": "host-to-host-from-node-...-worker-X-to-node-...-master-0-endpoint-10.0.0.5"
    }
  },
  "message": {
    "reason": "DisruptionBegan",
    "humanMessage": "... stopped responding to GET requests over new connections",
    "annotations": { "reason": "DisruptionBegan" }
  },
  "from": "2026-03-21T21:50:24Z",
  "to": "2026-03-21T21:50:26Z"
}
```

### Event Sources

| Source | What it Contains |
|--------|-----------------|
| `Disruption` | API backend disruption events (Error/Warning level) |
| `E2ETest` | Test execution intervals (start/end, pass/fail) |
| `OVSVswitchdLog` | OVS packet processing stalls (poll intervals >500ms) |
| `CPUMonitor` | Nodes with CPU >95% utilization |
| `CloudMetrics` | Azure disk IOPS, queue depth, bandwidth, latency |
| `EtcdLog` | etcd apply-too-long, slow fdatasync, ReadIndex delays |
| `EtcdDiskCommitDuration` | etcd disk commit above 25ms threshold |
| `EtcdDiskWalFsyncDuration` | etcd WAL fsync above 10ms threshold |
| `AuditLog` | API request failure counts during disruption |
| `Alert` | Prometheus alerts firing (e.g., ExtremelyHighIndividualControlPlaneCPU) |
| `NodeMonitor` | Node NotReady events, condition changes |
| `MachineMonitor` | Machine phase changes |
| `ClusterVersion` | CVO upgrade progress |
| `ClusterOperator` | Operator status transitions (available, progressing, degraded) |
| `OperatorState` | Operator state change events |
| `KubeletLog` | Kubelet log events |

### Using Timeline Data for Failure Correlation

1. Find when the failed test ran — look for `source = "E2ETest"` with
   `message.annotations.status = "Failed"`
2. Note the `from` and `to` timestamps
3. Search for overlapping events with `level = "Error"` or `level = "Warning"`
4. Focus on `OperatorState`, `NodeMonitor`, and `Disruption` sources

---

## Gather-Extra Artifacts

The `gather-extra` step collects extensive cluster state after test execution — one of the
richest diagnostic sources available.

```text
artifacts/{target}/gather-extra/
└── artifacts/
    ├── oc_cmds/               # Cluster state snapshots (oc get output)
    ├── pods/                  # Pod logs organized by namespace
    ├── audit_logs/            # API server audit logs
    ├── journal_logs/          # Node journal logs (systemd)
    └── must-gather/           # Inline must-gather data (sometimes)
```

### `oc_cmds/` — Cluster State Snapshots

Captured `oc get` output for key cluster resources — one file per command (YAML or text).

| File | Command Equivalent | Use For |
|------|--------------------|---------|
| `nodes` | `oc get nodes -o yaml` | Node status, conditions, resource capacity |
| `pods` | `oc get pods --all-namespaces` | Pod status across the cluster |
| `events` | `oc get events --all-namespaces` | Kubernetes events (warnings, errors) |
| `clusterversion` | `oc get clusterversion` | OCP version and upgrade status |
| `co` | `oc get clusteroperators` | Cluster operator status (available, degraded) |
| `machines` | `oc get machines -A` | Machine objects and status |
| `machinesets` | `oc get machinesets -A` | MachineSet scaling status |
| `pv` | `oc get pv` | Persistent volume status |
| `csr` | `oc get csr` | Certificate signing requests |

### `pods/` — Pod Logs by Namespace

Pod logs organized by namespace. Each namespace directory holds logs for pods running there
at collection time.

```text
pods/
├── openshift-etcd/
│   ├── etcd-master-0/
│   │   ├── etcd/
│   │   │   ├── current.log      # Current container log
│   │   │   └── previous.log     # Previous container log (if restarted)
│   │   └── etcd-readiness/
│   │       └── current.log
│   └── ...
├── openshift-kube-apiserver/
│   └── kube-apiserver-master-0/
│       └── ...
├── openshift-ingress/
├── openshift-ovn-kubernetes/
├── openshift-monitoring/
├── openshift-machine-api/
└── ...
```

**Key namespaces for troubleshooting**:
- `openshift-etcd` — etcd health, leader changes, disk performance
- `openshift-kube-apiserver` — API server errors, request handling
- `openshift-ingress` — Ingress/router issues
- `openshift-ovn-kubernetes` — OVN-Kubernetes networking
- `openshift-monitoring` — Prometheus, alerting issues
- `openshift-machine-api` — Machine lifecycle, scaling
- `openshift-cluster-version` — CVO upgrade progress

### `audit_logs/` — API Server Audit Logs

API server audit logs, one JSON audit event per line:
- Request verb, resource, namespace, name
- User/service account making the request
- Response code and status
- Timestamps

**Use for**: Tracing API request patterns during disruption, identifying request gaps,
correlating API failures with test failures.

```bash
# Download audit logs
gcloud storage cp -r "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/audit_logs/" \
  local/audit_logs/ --no-user-output-enabled 2>/dev/null || true
```

### `journal_logs/` — Node Journal Logs

Systemd journal logs from cluster nodes: kernel messages, service logs, and system-level
events.

**Key entries to look for**:
- OVS vswitchd stalls: "Unreasonably long poll interval"
- Kernel OOM kills: "Out of memory: Kill process"
- Disk I/O errors
- Network interface events
- kubelet log entries

---

## Must-Gather Archives

Comprehensive cluster state captured by `oc adm must-gather` — the richest source of cluster
diagnostics.

### Location Patterns

Location depends on job type:

| Pattern | Location | Job Type |
|---------|----------|----------|
| Standard | `{target}/gather-must-gather/artifacts/must-gather.tar` | Most jobs |
| HyperShift Unified | `{target}/dump-management-cluster/artifacts/artifacts.tar` or `.tar.gz` | HyperShift (unified) |
| HyperShift Dump | `{target}/**/artifacts/hypershift-dump.tar` | HyperShift (dual) |
| HyperShift Hosted | `{target}/**/artifacts/**/hostedcluster.tar` | HyperShift (dual) |

```bash
# Find must-gather archives
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/**/must-gather*"

# Find HyperShift dumps
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/**/hypershift-dump.tar" 2>/dev/null
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/**/hostedcluster.tar" 2>/dev/null
```

### Must-Gather Contents (After Extraction)

After extracting the tar archive, the must-gather directory typically contains:

```text
must-gather/
├── {hash-directory}/              # Long registry hash name (renamed to "content/" by extraction script)
│   ├── cluster-scoped-resources/
│   │   ├── config.openshift.io/
│   │   ├── machine.openshift.io/
│   │   ├── operator.openshift.io/
│   │   └── ...
│   ├── namespaces/
│   │   ├── openshift-etcd/
│   │   │   ├── pods/
│   │   │   ├── core/
│   │   │   └── ...
│   │   ├── openshift-kube-apiserver/
│   │   └── ...
│   ├── host_service_logs/
│   │   └── masters/
│   │       ├── crio_service.log
│   │       ├── kubelet_service.log
│   │       └── ...
│   └── event-filter.html          # HTML event viewer
├── timestamp
└── version
```

**Key data in must-gather**:
- **Cluster operators**: Status, conditions, and operator logs
- **Pod YAMLs**: Full pod specs including `containerStatuses` with `exitCode`,
  `lastState.terminated.reason`, `restartCount`
- **Container logs**: Current and previous container logs for all pods
- **Events**: Kubernetes events per namespace
- **Node info**: Node conditions, resource usage, taints
- **Operator conditions**: Detailed operator status and degraded reasons

### HyperShift Must-Gather Patterns

HyperShift jobs use one of three must-gather patterns:

1. **Unified Archive** (`dump-management-cluster`) — Single archive with both management
   and hosted cluster data. Management at root `output/`, hosted at
   `output/hostedcluster-{name}/`.

2. **Dual Archives** (`gather-must-gather` + hypershift-dump) — Standard must-gather for
   management cluster, separate dump for hosted cluster data.

3. **Standard Only** (`gather-must-gather`) — Standard must-gather only, no
   HyperShift-specific dump.

### Must-Gather Availability

- Exists only if the cluster was stable enough to run `oc adm must-gather`; no `.tar` means
  the cluster was too unstable to collect diagnostics
- Early installation failures (bootstrap, infrastructure) have no must-gather
- Typically collected in the `post` phase (gather steps)

---

## Installer Artifacts

Produced by the OpenShift installer during cluster creation.

### Installer Logs

```bash
# Find installer logs (exclude deprovision — those are from teardown)
gcloud storage ls -r "gs://test-platform-results/{bucket-path}/artifacts/" 2>&1 \
  | grep -E "\.openshift_install.*\.log$" | grep -v "deprovision"
```

**Location**: Varies by job configuration. Commonly found at:
```text
artifacts/{target}/{install-step}/artifacts/.openshift_install.log
artifacts/{target}/{install-step}/artifacts/.openshift_install_state.json
```

**Log format**: Structured text with timestamp, level, and message:
```text
time="2026-01-15T10:23:45Z" level=info msg="Consuming Install Config from target directory"
time="2026-01-15T10:45:12Z" level=error msg="bootstrap failed to complete"
time="2026-01-15T10:45:12Z" level=fatal msg="failed waiting for bootstrapping to complete"
```

**Key patterns** (always work backwards from the end):
- `level=error` or `level=fatal` — Error messages (focus on **last** ones, not first)
- `"Still waiting for"` — Components not yet ready at timeout
- `"Cluster operators X, Y, Z are not available"` — Final operator status
- `"context deadline exceeded"` — Installation timeout
- `"terraform"` — Terraform errors (older versions)
- `"clusterapi"` or `"machine-api"` — Cluster API errors (newer versions)

**Critical analysis principle**: OpenShift installations exhibit **eventual consistency**.
Components report errors while waiting for dependencies — early errors are expected and
usually resolve. Always analyze backwards from the final timeout, not forwards from the start.

### `install-status.txt`

The installer's exit code (a single number). `junit_install.xml` translates this into a
human-readable failure mode — prefer it.

### Installer Log Bundle (`log-bundle-*.tar`)

```bash
# Find log bundles
gcloud storage ls -r "gs://test-platform-results/{bucket-path}/artifacts/" 2>&1 \
  | grep -E "log-bundle.*\.tar$"
```

A tar archive (NOT `.tar.gz`) of detailed node-level diagnostics. Prefer non-deprovision
bundles.

**Log bundle structure**:
```text
log-bundle-{timestamp}/
├── bootstrap/
│   ├── journals/
│   │   ├── bootkube.log               # Bootstrap control plane init
│   │   ├── kubelet.log                # Bootstrap kubelet
│   │   ├── crio.log                   # Container runtime logs
│   │   ├── ironic.log                 # Ironic logs (metal jobs only)
│   │   ├── metal3-baremetal-operator.log  # Metal3 BMO (metal jobs only)
│   │   └── journal.log.gz            # Complete system journal
│   └── network/
│       ├── ip-addr.txt                # IP addresses
│       ├── ip-route.txt               # Routing table
│       └── hostname.txt               # Hostname
├── control-plane/
│   └── {node-ip}/
│       └── containers/
│           ├── metal3-ironic-*.log    # Worker provisioning Ironic logs (metal)
│           └── metal3-baremetal-operator-*.log
├── serial/                            # Serial console logs
│   ├── {cluster}-bootstrap-serial.log
│   └── {cluster}-master-N-serial.log
├── clusterapi/
│   ├── *.yaml                         # Cluster API resources
│   ├── etcd.log                       # etcd logs
│   └── kube-apiserver.log             # API server logs
├── failed-units.txt                   # Failed systemd units
└── gather.log                         # Log bundle collection log
```

**Analysis by failure mode**:
- **Bootstrap failures**: Check `bootstrap/journals/bootkube.log`, `clusterapi/etcd.log`,
  `clusterapi/kube-apiserver.log`, `serial/*-bootstrap-serial.log`
- **Infrastructure failures**: Focus on installer log — cloud API errors, quota, rate limiting
- **Cluster creation**: Check must-gather operator logs
- **Operator stability**: Check must-gather operator conditions and logs

### `metadata.json` — Cluster Metadata

Cluster name, ID, infrastructure platform, and region. In the install step artifacts
directory.

---

## Serial Console Logs

Raw console output of VMs or bare metal nodes, as if watching a physical console.

### Location

In log bundles:
```text
log-bundle-{timestamp}/serial/{cluster}-bootstrap-serial.log
log-bundle-{timestamp}/serial/{cluster}-master-N-serial.log
```

For metal jobs (libvirt console logs):
```text
artifacts/{target}/baremetalds-devscripts-gather/artifacts/libvirt-logs.tar
```
Extract to find `{cluster}-bootstrap_console.log`, `{cluster}-master-{N}_console.log`.

### What They Reveal

- **Kernel panics**: `panic`, `kernel`, `oops`
- **Ignition failures**: `ignition`, `config fetch failed`, `Ignition failed`
- **Hardware/disk issues**: `mount`, `disk`, `filesystem`, `I/O error`
- **Network configuration**: `dhcp`, `network unreachable`, `DNS`, `timeout`
- **Boot sequence**: Kernel messages, initramfs, CoreOS startup
- **Service failures**: systemd errors, unit failures

---

## Metal (Bare Metal) Job Artifacts

Metal IPI jobs use dev-scripts with Metal3 and Ironic, producing artifacts not found in cloud
jobs.

### OFCIR Acquisition

```text
artifacts/{target}/ofcir-acquire/
├── build-log.txt                                  # Host acquisition log (JSON with pool, provider, host)
└── artifacts/
    └── junit_metal_setup.xml                      # JUnit: "[sig-metal] should get working host from infra provider"
```

If OFCIR acquisition fails, the installation never starts. Check the JUnit for the test
`[sig-metal] should get working host from infra provider`.

### Dev-Scripts Logs

```text
artifacts/{target}/baremetalds-devscripts-setup/artifacts/root/dev-scripts/logs/
├── 01_*.log                    # Requirements and host config
├── 02_*.log                    # Network setup
├── 03_*.log                    # Ironic/Metal3 setup
├── 04_*.log                    # Installer build
├── 05_*.log                    # Pre-install configuration
├── 06_create_cluster.log       # Cluster installation (invokes installer)
├── .openshift_install*.log     # Installer logs (dev-scripts invokes the installer)
└── ...
```

Dev-scripts invokes the installer, so `.openshift_install*.log` files appear in the devscripts
directories.

- Failures in steps 01–05 are **dev-scripts setup failures** (host config, Ironic/Metal3 setup)
- Failures in step 06+ are **cluster installation failures** (also analyzed by the standard
  install failure analysis)

### Libvirt Console Logs

```text
artifacts/{target}/baremetalds-devscripts-gather/artifacts/libvirt-logs.tar
```

Extract to get VM/node console logs showing the complete boot sequence.

### Ironic Logs (in Log Bundle)

The log bundle contains two sets of Ironic logs. Check by what failed: masters → bootstrap
Ironic; workers → control-plane Ironic.

- **Bootstrap Ironic** (`bootstrap/journals/ironic.log`) — Master node provisioning
- **Control-plane Ironic** (`control-plane/{node-ip}/containers/metal3-ironic-*.log`) — Worker
  node provisioning

### sosreport

```text
artifacts/{target}/baremetalds-devscripts-gather/artifacts/sosreport-*.tar.xz
```

Hypervisor system diagnostics: system logs, libvirt configuration, and diagnostic command
output. Useful for hypervisor-level issues.

### Squid Proxy Logs

```text
artifacts/{target}/baremetalds-devscripts-gather/artifacts/squid-logs-*.tar
```

The squid proxy runs on the hypervisor. Logs show **inbound** CI access to the cluster
(CI → cluster), NOT outbound access (cluster → registry). Important for debugging CI
connectivity to the cluster in IPv6/disconnected environments.

---

## Cluster Event Artifacts

### Kubernetes Events (`oc_cmds/events`)

Cluster-wide Kubernetes events captured at gather time — warnings, errors, and informational
events across all namespaces.

### etcd Events and Logs

Available in multiple locations:
- **Timeline files**: `EtcdLog`, `EtcdDiskCommitDuration`, `EtcdDiskWalFsyncDuration` sources
- **Pod logs**: `gather-extra/artifacts/pods/openshift-etcd/`
- **Log bundle**: `clusterapi/etcd.log`

Key etcd indicators:
- `"apply request took too long"` — write pressure
- `"slow fdatasync"` — disk I/O bottleneck
- `"waiting for ReadIndex response took too long"` — read latency
- Leader election events — cluster instability
- Commit duration above 25ms or WAL fsync above 10ms thresholds

---

## Monitoring and Metrics Artifacts

### CloudMetrics (in Timeline Files)

Azure disk metrics under `source: "CloudMetrics"`:
- Disk IOPS (read/write)
- Queue depth
- Bandwidth
- Latency

### CPUMonitor (in Timeline Files)

Node CPU utilization above 95%, under `source: "CPUMonitor"`.

### Prometheus Alerts (in Timeline Files)

Firing alerts under `source: "Alert"`. Common critical alerts:
- `ExtremelyHighIndividualControlPlaneCPU`
- `etcdHighCommitDurations`
- `etcdHighNumberOfFailedGRPCRequests`

### Monitoring Stack Logs

Monitoring pod logs (if available):
```text
gather-extra/artifacts/pods/openshift-monitoring/
```

---

## Cluster State Artifacts

### Operator Status

Cluster operator status is available in several places:
- `gather-extra/artifacts/oc_cmds/co` — `oc get clusteroperators` output
- Must-gather `cluster-scoped-resources/config.openshift.io/clusteroperators/` — Full YAML
- Timeline files `source: "ClusterOperator"` — Status transitions over time

### Node Status

- `gather-extra/artifacts/oc_cmds/nodes` — `oc get nodes -o yaml`
- Timeline files `source: "NodeMonitor"` — Node condition changes
- Must-gather `cluster-scoped-resources/core/nodes/` — Full node YAML

### Machine Info

- `gather-extra/artifacts/oc_cmds/machines` — Machine objects
- `gather-extra/artifacts/oc_cmds/machinesets` — MachineSet status
- Timeline files `source: "MachineMonitor"` — Machine phase changes

---

## Multi-Step Job Navigation

### Understanding Step Directories

Multi-stage tests run steps in three phases — **pre** (setup/install), **test** (functional
tests), **post** (gather/cleanup) — each in its own directory under `artifacts/{target}/`.

To determine which phase a step belongs to:
1. Check `junit_operator.xml` for phase-level testcases
2. Fall back to `ci-operator-step-graph.json` for step dependencies and timing
3. Use naming conventions (e.g., `ipi-install-*` → pre, `gather-*` → post)

### Navigating Multiple Steps

```bash
# List all step directories
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/{target}/"

# List artifacts for a specific step
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/{target}/{step-name}/"
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/{target}/{step-name}/artifacts/"
```

### Step-Level Build Logs

For a failed step, download its `build-log.txt`:

```bash
gcloud storage cp "gs://test-platform-results/{bucket-path}/artifacts/{target}/{step-name}/build-log.txt" \
  local/{step-name}-build-log.txt --no-user-output-enabled
```

---

## Upgrade Job Artifacts

Upgrade jobs produce artifacts under **multiple workflow step directories**, one per phase.
Key differences from non-upgrade jobs:

### Multiple Timeline Files

Upgrade jobs typically produce two timeline files (one per phase):
```bash
gcloud storage ls "gs://test-platform-results/logs/{job_name}/{build_id}/artifacts/**/e2e-timelines_spyglass_*.json"
```

The first file (sorted by filename) is the **upgrade phase**; the second is the
**conformance/e2e test phase**.

### Upgrade-Specific Cluster State

```bash
# Cluster version (shows upgrade progress)
gcloud storage cp "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/oc_cmds/clusterversion" \
  local/clusterversion --no-user-output-enabled

# Cluster operators (shows operator status post-upgrade)
gcloud storage cp "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/oc_cmds/co" \
  local/co --no-user-output-enabled
```

### Upgrade Source Information

Extract upgrade source from `prowjob.json`:
```bash
# Upgrade source tag
jq -r '.metadata.annotations["release.openshift.io/from-tag"] // empty' prowjob.json

# Release images
jq -r '.spec.pod_spec.containers[0].env[] | select(.name == "RELEASE_IMAGE_INITIAL") | .value' prowjob.json
jq -r '.spec.pod_spec.containers[0].env[] | select(.name == "RELEASE_IMAGE_LATEST") | .value' prowjob.json
```

---

## Artifact Discovery and Search

### Using `gcloud storage ls`

The most reliable way to find artifacts:

```bash
# List top-level contents
gcloud storage ls "gs://test-platform-results/{bucket-path}/"

# List step directories
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/{target}/"

# Recursive search with glob
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/**/junit*.xml"
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/**/e2e-timelines_spyglass_*.json"
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/**/must-gather*"
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/**/*.tar"

# Recursive listing (pipe to grep for filtering)
gcloud storage ls -r "gs://test-platform-results/{bucket-path}/artifacts/" 2>&1 \
  | grep -E "\.openshift_install.*\.log$" | grep -v "deprovision"
```

### Using the Artifact Search Script

This skill bundles a Python script (`prow_job_artifact_search.py`) for structured artifact access
with JSON output. Default fetch limit is 512KB; use `--max-bytes` for larger files.

```bash
# List directory contents
python3 plugins/ci/skills/prow-job-analysis/prow_job_artifact_search.py <url> list [subpath]

# Search for files by glob pattern
python3 plugins/ci/skills/prow-job-analysis/prow_job_artifact_search.py <url> search "<pattern>" [subpath]

# Fetch a specific file (default 512KB limit)
python3 plugins/ci/skills/prow-job-analysis/prow_job_artifact_search.py <url> fetch <filepath> [--max-bytes N]
```

### Common Search Patterns

```bash
# Find all interval/disruption data
python3 .../prow_job_artifact_search.py <url> search "**/e2e-timelines_spyglass_*.json"
python3 .../prow_job_artifact_search.py <url> search "**/*intervals*.json"

# Find JUnit results
python3 .../prow_job_artifact_search.py <url> search "**/junit*.xml"

# Find must-gather archives
python3 .../prow_job_artifact_search.py <url> search "**/must-gather*"

# Find node journal logs for a specific node
python3 .../prow_job_artifact_search.py <url> search "**/*worker-c-7t6ng*" artifacts

# Find specific oc_cmds output
python3 .../prow_job_artifact_search.py <url> search "**/nodes" artifacts
```

---

## Quick Reference: Artifact Location Summary

### By Investigation Type

| What You Need | Where to Look |
|---------------|--------------|
| Job pass/fail and timing | `prowjob.json` |
| ci-operator log | `build-log.txt` (top-level) |
| Test results (which tests failed) | `artifacts/**/junit*.xml` |
| Test console output | `artifacts/{target}/openshift-e2e-test/build-log.txt` |
| Disruption data | `artifacts/**/e2e-timelines_spyglass_*.json` |
| Cluster operator status | `gather-extra/artifacts/oc_cmds/co` |
| Pod status and logs | `gather-extra/artifacts/pods/{namespace}/` |
| API audit logs | `gather-extra/artifacts/audit_logs/` |
| Node journal logs | `gather-extra/artifacts/journal_logs/` |
| Cluster events | `gather-extra/artifacts/oc_cmds/events` |
| Must-gather (full cluster state) | `gather-must-gather/artifacts/must-gather.tar` |
| Installer log | `{install-step}/artifacts/.openshift_install.log` |
| Installer log bundle | `{install-step}/artifacts/log-bundle-*.tar` |
| Serial console (VM boot) | `log-bundle-*/serial/` or `libvirt-logs.tar` |
| Step dependency graph | `artifacts/ci-operator-step-graph.json` |
| Symptom labels | `artifacts/job_labels/*.json` |
| Pod lifecycle (job pod) | `podinfo.json` |

### By Failure Type

| Failure Type | Primary Artifacts | Secondary Artifacts |
|-------------|-------------------|---------------------|
| **Installation** | Installer log, `junit_install.xml`, log bundle | Must-gather, serial console |
| **E2E test** | JUnit XML, E2E build-log, timeline files | Gather-extra, must-gather |
| **Disruption** | Timeline files, audit logs, etcd logs | Pod logs, journal logs |
| **Upgrade** | ClusterVersion, timeline files, operator status | Gather-extra, must-gather |
| **Infrastructure** | Installer log, cloud API errors | `prowjob.json` timing |
| **CI infrastructure** | `build-log.txt`, `podinfo.json` | `ci-operator-step-graph.json` |
| **Metal install** | Dev-scripts logs, console logs, Ironic logs | sosreport, squid logs |
| **Resource exhaustion** | Timeline files (CPU, cloud metrics), node status | Pod logs, events |
| **Networking** | OVN pod logs, journal logs, timeline files | Audit logs, events |
