# Disruption Analysis Reference

Interpreting disruption and interval data from OpenShift CI jobs: what the data means, how
to read it, and how to determine whether disruption is a cause, a symptom, or incidental
background noise.

---

## Table of Contents

1. [What Disruption Data Is](#what-disruption-data-is)
2. [How Disruption Monitoring Works](#how-disruption-monitoring-works)
3. [Interval File Format and Structure](#interval-file-format-and-structure)
4. [Key Signal Sources](#key-signal-sources)
5. [Backend Classification](#backend-classification)
6. [API Backend Disruption Monitoring](#api-backend-disruption-monitoring)
7. [Source-Node Analysis](#source-node-analysis)
8. [Disruption During Upgrade vs Conformance](#disruption-during-upgrade-vs-conformance)
9. [Symptom Labels](#symptom-labels)
10. [Correlating Disruption with Cluster Events](#correlating-disruption-with-cluster-events)
11. [Interpreting Disruption for Root Cause Analysis](#interpreting-disruption-for-root-cause-analysis)
12. [Common Root Cause Patterns](#common-root-cause-patterns)
13. [Cross-Run Comparison](#cross-run-comparison)
14. [Disruption Allowance Thresholds](#disruption-allowance-thresholds)
15. [Tooling: The Disruption Parser](#tooling-the-disruption-parser)
16. [Sippy Intervals Viewer](#sippy-intervals-viewer)

---

## What Disruption Data Is

### The OpenShift Disruption Monitoring Framework

A continuous disruption monitoring framework runs alongside E2E tests. It probes key API
backends and records any period when those backends stop responding. Probes run for the
entire test job — from before the first test through the last test completing — giving a
complete picture of API availability over time.

Disruption data is NOT a test result — it is an observational record. Separate disruption
*tests* evaluate whether observed disruption exceeded acceptable thresholds. Disruption
events appear in the interval data whether or not a disruption test ultimately fails.

### What Constitutes "Disruption"

A disruption event is recorded when a probe request to an API backend fails:

- **Connection refused** — the backend's TCP port is not accepting connections
- **Connection timeout** — the connection attempt timed out without a response
- **EOF** — the connection was reset or closed unexpectedly
- **HTTP error** — the backend returned an error status code (5xx)
- **Elevated latency** — the response took longer than the configured threshold
- **DNS failure** — the backend hostname could not be resolved
- **Stopped responding** — the backend accepted the connection but did not respond

Each failure is recorded as an interval event with `from` and `to` timestamps marking the
window when the backend was unresponsive.

### What Disruption Is NOT

- **Disruption is not a root cause.** It is always a symptom of something else — a node
  draining, etcd leader election, OVS stall, or CPU starvation. Always look for the
  underlying event.
- **Disruption is not the same as a test failure.** A job can have disruption events and still
  pass (if within allowance thresholds), or it can fail with zero disruption (if a functional
  test fails for unrelated reasons).
- **Brief transient disruption is not always a bug.** During upgrades, brief disruption is
  expected as control plane components restart. The CI framework has allowances for this.

---

## How Disruption Monitoring Works

### Probe Architecture

Lightweight HTTP pollers continuously issue GET requests to cluster API endpoints. Each poller:

1. Establishes a connection (new or reused) to the target endpoint
2. Sends a GET request (typically to a health or readiness endpoint)
3. Records the result (success or failure with error type)
4. Waits a short interval, then repeats

Probes run on **worker nodes** by default, simulating a workload trying to reach the control
plane. This matters: disruption observed from a specific worker node may be caused by issues
local to that node (OVS stall, CPU starvation) rather than a cluster-wide problem.

### Connection Types: New vs Reused

Every API backend is monitored with two connection strategies:

- **New connections** (`connection: "new"`): Each probe creates a fresh TCP connection,
  exercising DNS resolution, TCP handshake, TLS negotiation, and load balancer routing.
  Disruption on new but not reused connections typically indicates a connection-establishment
  problem (DNS, load balancer, TCP accept queue).

- **Reused connections** (`connection: "reused"`): Probes reuse persistent HTTP connections,
  exercising the request-processing path without connection overhead. Disruption on reused
  but not new connections typically indicates a request-processing stall (slow backend,
  resource contention) rather than a connectivity problem.

**Why this matters for diagnosis:**

| New Conn | Reused Conn | Likely Issue |
|----------|-------------|-------------|
| ✅ Disrupted | ✅ Disrupted | Backend or node is genuinely down — nothing gets through |
| ✅ Disrupted | ❌ Clean | Connection establishment problem — DNS, load balancer, TLS |
| ❌ Clean | ✅ Disrupted | Request processing problem — slow handler, connection draining |
| ❌ Clean | ❌ Clean | No disruption on this backend |

Most genuine disruption affects both connection types simultaneously, pointing to a
backend-level or infrastructure-level issue rather than a connection-layer problem.

### Host-to-Host Monitoring

The framework also monitors direct host-to-host connectivity between nodes. These probes
send requests directly from a worker node to specific control plane endpoints using IP
addresses (bypassing DNS and load balancers).

Host-to-host data localizes the problem to specific network paths. The disruption locator
encodes the source node, destination node, and endpoint IP:

```text
host-to-host-from-node-{src-node}-to-node-{dst-node}-endpoint-{ip}
```

This lets the parser detect **single-source fan-out** patterns — all disruption originating
from one node — which immediately localizes the problem to that node.

---

## Interval File Format and Structure

### File Naming and Location

Disruption data is stored in E2E timeline files (also called interval files):

```text
artifacts/{target}/openshift-e2e-test/artifacts/junit/e2e-timelines_spyglass_{timestamp}.json
```

`{timestamp}` is a `YYYYMMDD-HHMMSS` string of when the file was generated.

**Upgrade jobs** typically produce **two** timeline files — one per phase:
- First file (sorted by filename timestamp) → **upgrade phase**
- Second file → **conformance/E2E test phase**

**Non-upgrade jobs** typically produce **one** timeline file covering the entire test phase.

```bash
# Find all timeline files for a job run
gcloud storage ls "gs://test-platform-results/logs/{job_name}/{build_id}/artifacts/**/e2e-timelines_spyglass_*.json"
```

### JSON Structure

The timeline file is a JSON array (or object with an `items` array) of event records. Each
record represents an observed event over a time interval:

```json
{
  "level": "Error",
  "source": "Disruption",
  "locator": {
    "type": "Disruption",
    "keys": {
      "backend-disruption-name": "kube-api-new-connections",
      "connection": "new"
    }
  },
  "message": {
    "reason": "DisruptionBegan",
    "humanMessage": "kube-api-new-connections stopped responding to GET requests over new connections",
    "annotations": {
      "reason": "DisruptionBegan"
    }
  },
  "from": "2026-03-21T21:50:24Z",
  "to": "2026-03-21T21:50:26Z"
}
```

Host-to-host backends additionally carry a `disruption` locator key encoding the source node,
target node, and endpoint (see the Field Reference below). Plain API backends like the example
above do not — don't mix the two when writing jq filters.

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `level` | string | Severity: `"Error"`, `"Warning"`, or `"Info"`. Disruption events are Error or Warning. |
| `source` | string | Event category. `"Disruption"` for disruption events. See [Key Signal Sources](#key-signal-sources) for all sources. |
| `locator.type` | string | Event type classification (e.g., `"Disruption"`, `"Node"`, `"Pod"`) |
| `locator.keys` | object | Key-value pairs identifying the specific resource or backend |
| `locator.keys.backend-disruption-name` | string | The backend being monitored (e.g., `"kube-api-new-connections"`) |
| `locator.keys.connection` | string | `"new"` or `"reused"` — the connection strategy used |
| `locator.keys.disruption` | string | For host-to-host backends: encodes source node, target node, and endpoint IP |
| `message.reason` | string | Event reason: `"DisruptionBegan"`, `"DisruptionEnded"`, etc. |
| `message.humanMessage` | string | Human-readable description including error details |
| `message.annotations` | object | Structured metadata (varies by source) |
| `from` | string | ISO 8601 timestamp — when the event started |
| `to` | string | ISO 8601 timestamp — when the event ended |

### Duration Calculation and Significance

Duration is `to - from`, in seconds:

| Duration | Interpretation |
|----------|---------------|
| 1–2 seconds | Brief blip — may be a transient network hiccup or load balancer failover |
| 3–10 seconds | Moderate disruption — likely a real event (node drain, pod restart, OVS stall) |
| 10–30 seconds | Significant disruption — sustained backend unavailability, likely impactful |
| 30+ seconds | Severe disruption — prolonged outage, almost certainly causes test failures |
| 60+ seconds | Critical disruption — something is fundamentally broken on the cluster |

**Clustering**: Disruption events on the same backend close together in time (within seconds)
often represent the same incident observed by multiple probes. The parser uses a configurable
`--window` parameter (default 60 seconds) to group events and find concurrent cluster activity.

---

## Key Signal Sources

The timeline JSON contains events from many sources beyond disruption. These concurrent
events are essential for understanding **why** disruption occurred.

### `Disruption` — API Backend Disruption Events

The core disruption events. Level is `Error` or `Warning`. Always the starting point for
analysis.

### `CPUMonitor` — CPU Starvation Indicators

Reports when a node's CPU utilization exceeds 95%. CPU starvation cascades to everything on
the node:

```json
{
  "source": "CPUMonitor",
  "level": "Warning",
  "message": {
    "humanMessage": "99% of all CPU cores on node ip-10-0-23-45.ec2.internal are in use"
  },
  "from": "2026-03-21T21:49:00Z",
  "to": "2026-03-21T21:52:00Z"
}
```

**Interpretation**: When CPU >95% appears on the same node that is the source of disruption
events, CPU starvation is almost certainly the proximate cause. OVS vswitchd (the network
packet processor) is especially sensitive — when it cannot get CPU cycles, all network
traffic on that node freezes.

### `EtcdLog` — etcd Health and Performance

Reports etcd operational events:

| Message Pattern | Meaning | Severity |
|----------------|---------|----------|
| `"apply request took too long"` | etcd is under write pressure — raft proposals are slow | High |
| `"slow fdatasync"` | Disk I/O bottleneck preventing WAL writes | Critical |
| `"waiting for ReadIndex response took too long"` | etcd read latency elevated | Medium |
| `"leader changed"` or `"elected leader"` | Leader election occurred — brief unavailability | Medium |
| `"failed to send out heartbeat"` | Network or load issue between etcd members | High |
| `"database space exceeded"` | etcd database size limit hit | Critical |
| `"took too long to execute"` | General slow operation warning | Medium |

```json
{
  "source": "EtcdLog",
  "level": "Warning",
  "locator": { "keys": { "node": "ci-op-xxx-master-0" } },
  "message": {
    "humanMessage": "apply request took too long (1.234s)"
  },
  "from": "2026-03-21T21:50:10Z",
  "to": "2026-03-21T21:50:10Z"
}
```

**Interpretation**: etcd issues cascade to the API server (which depends on etcd for all
reads and writes), causing API disruption across all backends. etcd warnings concurrent with
disruption across multiple API backends make etcd pressure almost certainly the root cause.

### `EtcdDiskCommitDuration` — etcd Disk Commit Latency

Reports when etcd's disk commit duration exceeds the 25ms threshold — a direct measure of
disk write performance for etcd transactions.

### `EtcdDiskWalFsyncDuration` — etcd WAL Fsync Latency

Reports when etcd's Write-Ahead Log fsync duration exceeds the 10ms threshold. WAL fsync
is the most latency-sensitive disk operation in etcd — slow fsync directly delays raft
proposal commits.

**Interpretation for both**: Elevated disk latency → etcd cannot commit transactions
quickly → API server requests backed up → API disruption. This is the most common cascade
path on cloud platforms, especially Azure where managed disk IOPS are explicitly capped.

### `OVSVswitchdLog` — OVN/OVS Packet Processing Stalls

Reports when Open vSwitch (OVS) vswitchd experiences unreasonably long poll intervals — it
was unable to process network packets:

```json
{
  "source": "OVSVswitchdLog",
  "level": "Warning",
  "locator": { "keys": { "node": "ci-op-xxx-worker-westus-db64f" } },
  "message": {
    "humanMessage": "Unreasonably long 9235ms poll interval (9000ms user, 0ms system)"
  },
  "from": "2026-03-21T21:50:20Z",
  "to": "2026-03-21T21:50:20Z"
}
```

**Poll interval severity scale:**

| Interval | Impact |
|----------|--------|
| 500–1000ms | Degraded networking — packets delayed but eventually forwarded |
| 1000–5000ms | Networking effectively frozen for 1–5 seconds |
| 5000ms+ | Severe — node was completely unable to process network traffic |
| 10000ms+ | Extreme — OVS was starved for 10+ seconds, expect all connections to fail |

**Interpretation**: OVS stalls are the most direct cause of host-to-host disruption. OVS
stalls on the same node that is the source of disruption events give a clear causal chain:
CPU starvation → OVS cannot run → packets not forwarded → disruption recorded. Check
CPUMonitor events on the same node to confirm the root cause.

### `CloudMetrics` — Cloud Provider Metrics

Reports cloud provider infrastructure metrics that exceed thresholds. Currently focused on
Azure disk I/O:

```json
{
  "source": "CloudMetrics",
  "level": "Warning",
  "message": {
    "humanMessage": "Average value of 100.00 for metric OS Disk IOPS Consumed Percentage is over the threshold of 50.00"
  },
  "from": "2026-03-21T21:49:00Z",
  "to": "2026-03-21T21:52:00Z"
}
```

**Azure disk metrics and their thresholds:**

| Metric | Threshold | What it Means |
|--------|-----------|---------------|
| OS Disk IOPS Consumed Percentage | 50% warning, 90%+ critical | How much of the disk's IOPS budget is being used |
| OS Disk Queue Depth | 3.0 (warning), 10+ (critical) | How many I/O operations are queued waiting for the disk |
| OS Disk Bandwidth Consumed Percentage | 50% | How much of the disk's throughput is being used |
| Data Disk IOPS Consumed Percentage | 50% | Same as above for data disks |

**Interpretation**: Azure managed disks have hard IOPS caps based on disk tier. At 100% IOPS,
all additional I/O queues up, directly impacting etcd (which needs low-latency disk writes)
and cascading to API disruption. Disk I/O saturation is the single most common root cause of
disruption on Azure.

### `AuditLog` — API Server Audit Events

Reports API request failure rates during disruption windows:

```json
{
  "source": "AuditLog",
  "level": "Info",
  "message": {
    "humanMessage": "1 requests made during this time failed out of 611 total"
  }
}
```

**Interpretation for disruption diagnosis** — this distinction separates "the API server was
overloaded" from "the API server was unreachable":
- **Audit entries show failures during disruption** → API server received requests but
  couldn't process them (internal issue — etcd slow, resource pressure)
- **No audit entries during disruption** → requests never reached the API server
  (connectivity issue — network failure, load balancer problem, node isolation)

### `Alert` — Prometheus Alerts

Reports Prometheus alerts that were firing during the test:

```json
{
  "source": "Alert",
  "level": "Warning",
  "locator": { "keys": { "alert": "ExtremelyHighIndividualControlPlaneCPU" } },
  "message": {
    "humanMessage": "alert ExtremelyHighIndividualControlPlaneCPU is firing"
  }
}
```

**Key alerts related to disruption:**

| Alert | What it Means |
|-------|---------------|
| `ExtremelyHighIndividualControlPlaneCPU` | A control plane node has extremely high CPU — confirms CPU starvation |
| `etcdHighCommitDurations` | etcd commits are taking too long — confirms disk pressure |
| `etcdHighNumberOfFailedGRPCRequests` | etcd gRPC requests are failing — etcd is degraded |
| `KubeAPILatencyHigh` | API server latency is elevated — confirms API slowness |
| `MCDDrainError` | Machine Config Daemon cannot drain a node — upgrade may be stalled |

### `NodeMonitor` / `MachineMonitor` — Node and Machine State

Reports node condition changes (NotReady, pressure conditions) and machine phase transitions:

```json
{
  "source": "NodeMonitor",
  "level": "Warning",
  "locator": { "keys": { "node": "ci-op-xxx-master-0" } },
  "message": {
    "humanMessage": "node condition Ready changed to Unknown"
  }
}
```

**Interpretation**: Node state changes during disruption windows distinguish planned
operations (node drain during upgrade) from unexpected events (node going NotReady due to
resource pressure).

### `ClusterVersion` / `ClusterOperator` — Operator Lifecycle

Reports CVO upgrade progress and operator status transitions:

```json
{
  "source": "ClusterOperator",
  "locator": { "keys": { "name": "kube-apiserver" } },
  "message": {
    "humanMessage": "condition/Progressing changed: True → operator is updating"
  }
}
```

**Interpretation**: These events establish the upgrade timeline — when each operator started
updating, finished, and whether it became degraded. Correlating disruption with operator
transitions shows whether it is expected (operator restarting during upgrade) or unexpected.

### `PodLog` — Pod Lifecycle Events

Reports specific pod lifecycle events observed during the test.

### `KubeletLog` — Kubelet Events

Reports kubelet log events from cluster nodes, including pod start/stop, volume mount,
and node health activities.

### `E2ETest` — Test Execution Events

Reports which E2E tests were running at any given time:

```json
{
  "source": "E2ETest",
  "level": "Info",
  "locator": { "keys": { "e2e-test": "[sig-api-machinery] API server should handle large requests" } },
  "message": {
    "annotations": { "status": "Passed" }
  },
  "from": "2026-03-21T21:45:00Z",
  "to": "2026-03-21T21:50:00Z"
}
```

**Interpretation for disruption analysis**: Tests running during a disruption window matter
for two reasons:

1. **Tests that fail during disruption** are usually *victims* — the disruption caused them
   to fail, not the reverse.
2. **Tests that pass but consistently appear during disruption across multiple runs** are
   potentially *causes* — they may be creating the resource pressure that triggers disruption.

In multi-run analysis, cross-referencing which tests were active during disruption across all
runs is one of the most powerful techniques for identifying workload-induced disruption.

---

## Backend Classification

### What "Backends" Are

A "backend" is a specific API endpoint or service that is continuously polled. Each backend
has a unique name encoding what is monitored and how.

### Backend Types

The parser classifies backends into four categories:

| Type | Name Pattern | Example | Root Cause Indicator |
|------|-------------|---------|---------------------|
| **Non-cache** | Standard API names | `kube-api-new-connections` | Component or cluster networking problem |
| **Cache** | Contains `cache` prefix | `cache-kube-api-new-connections` | Likely etcd or global networking problem |
| **Canary** | `ci-cluster-network-liveness` | `ci-cluster-network-liveness-new-connections` | Test infrastructure network issues |
| **Cloud** | Cloud network-liveness | `cloud-network-liveness-azure-new-connections` | Cloud provider issues |

### Cache vs Non-Cache Backends

The distinction is architecturally significant:

- **Non-cache backends** hit the API server's normal request path, including reading from
  etcd for any non-cached resource.
- **Cache backends** are served from the API server's watch cache (an in-memory cache of
  etcd state). They do NOT hit etcd directly for reads.

**Why this matters:**

- **Only non-cache backends** disrupted, cache clean → likely etcd read performance (cache
  hits avoid the problem).
- **Both cache and non-cache** fail simultaneously → problem is at the API server or network
  level (below the cache layer).
- **Only cache backends** fail (rare) → watch-cache corruption or API server memory pressure.

### The "All Four Variants" Diagnostic Pattern

**Critical diagnostic signal**: When all four variants of a backend fail simultaneously:

```text
openshift-api-new-connections           (non-cache, new)
openshift-api-reused-connections        (non-cache, reused)
cache-openshift-api-new-connections     (cache, new)
cache-openshift-api-reused-connections  (cache, reused)
```

The root cause is almost always **control plane node resource exhaustion**:

```text
Disk I/O saturation → etcd stalls → API server cannot process any requests → all variants fail
```

This is NOT a networking issue — it is a resource issue. Confirming evidence:
- `EtcdLog` events showing `slow fdatasync` or `apply took too long`
- `CPUMonitor` events on control plane nodes
- `Alert` events for `ExtremelyHighIndividualControlPlaneCPU`
- `CloudMetrics` showing disk IOPS at 100%

### Network Liveness Backends

Two special backend types monitor infrastructure health:

- **`ci-cluster-network-liveness`** (canary): Polls an external endpoint from within the CI
  cluster. Disruption here means the CI infrastructure's own network is unreliable.
  **When this is disrupted, the run's disruption data for other backends is unreliable** —
  disruption events on normal backends may be test-infrastructure artifacts, not real cluster
  issues.

- **Cloud network-liveness** (e.g., `cloud-network-liveness-azure`): Polls within the cloud
  provider's network. Disruption here points to cloud provider networking, not OpenShift.

### Common Backend Names

| Backend Name | What It Monitors |
|-------------|-----------------|
| `kube-api-new-connections` | Kubernetes API server (new TCP connections) |
| `kube-api-reused-connections` | Kubernetes API server (persistent connections) |
| `openshift-api-new-connections` | OpenShift API server (new connections) |
| `openshift-api-reused-connections` | OpenShift API server (persistent connections) |
| `oauth-api-new-connections` | OAuth API server (new connections) |
| `oauth-api-reused-connections` | OAuth API server (persistent connections) |
| `image-registry-new-connections` | Internal image registry |
| `service-load-balancer-with-pdb-reused` | Service load balancer with pod disruption budget |
| `host-to-host-new-connections` | Direct node-to-node connectivity (new) |
| `host-to-host-reused-connections` | Direct node-to-node connectivity (reused) |
| `cache-kube-api-new-connections` | Kubernetes API via watch cache (new) |
| `cache-openshift-api-reused-connections` | OpenShift API via watch cache (reused) |

---

## API Backend Disruption Monitoring

### How the Framework Monitors API Endpoints

Each API backend has a dedicated polling goroutine that:

1. Creates a connection (new or reuses existing)
2. Sends a GET request to the API server's health or resource endpoint
3. Records success (response within timeout) or failure (error or timeout)
4. Generates interval events for disruption begin/end transitions

Polling runs continuously from test start to finish, typically every 1–2 seconds, giving
second-level resolution of when disruption starts and stops.

### Grace Periods During Upgrades

Some upgrade disruption is expected and the framework accounts for it:

- **API server rolling restarts**: kube-apiserver or openshift-apiserver pods restarting may
  briefly stop serving requests
- **Load balancer drain**: cloud load balancers may take time to remove a draining backend
  and route to a healthy one
- **etcd member restart**: etcd pod restart causes a brief quorum disruption

Disruption tests have **allowance thresholds** permitting some upgrade disruption before
counting it as a failure. See [Disruption Allowance Thresholds](#disruption-allowance-thresholds).

### Sustained vs Transient Disruption

| Pattern | Duration | Typical Cause |
|---------|----------|---------------|
| **Single blip** | 1–2s | Load balancer failover, brief network hiccup |
| **Brief burst** | 3–10s | API server pod restart, etcd leader election |
| **Sustained** | 10–60s | Node drain, severe resource pressure, component crash |
| **Prolonged** | 60s+ | Fundamental infrastructure issue, hung process, failed drain |

**Rule of thumb**: Transient blips (1–2s) during upgrade are almost always expected.
Sustained disruption (10s+) during conformance testing is almost always a real problem.

---

## Source-Node Analysis

### Why Source-Node Analysis Matters

For host-to-host backends, the disruption locator encodes which nodes are involved,
determining whether disruption is:

- **Localized to one node** → problem on that specific node
- **Spread across many nodes** → cluster-wide or destination-side problem

This is one of the most powerful diagnostic signals in disruption data.

### Pattern: Single-Source Fan-Out

**All disruptions originate from one source node, hitting many target nodes.**

```text
Worker-A → Master-0   ✗ disrupted
Worker-A → Master-1   ✗ disrupted
Worker-A → Master-2   ✗ disrupted
Worker-B → Master-0   ✓ clean
Worker-B → Master-1   ✓ clean
Worker-C → Master-0   ✓ clean
```

**Interpretation**: The problem is on Worker-A, not the masters or the network. The node
cannot send packets to *any* destination — classic symptoms:
- OVS vswitchd stall on Worker-A (check `OVSVswitchdLog` events for that node)
- CPU starvation on Worker-A (check `CPUMonitor` events)
- Disk I/O pressure causing system-wide slowdown on Worker-A

**Action**: Focus entirely on that node — what workloads ran on it, whether it was under
resource pressure, and whether OVS stalled.

### Pattern: Multi-Source

**Disruptions originate from multiple source nodes.**

```text
Worker-A → Master-0   ✗ disrupted
Worker-B → Master-0   ✗ disrupted
Worker-C → Master-0   ✗ disrupted
Worker-A → Master-1   ✓ clean
Worker-B → Master-1   ✓ clean
```

**Interpretation**: Multiple sources hitting the same destination suggests a destination-side
problem. If Master-0 receives all the disruption, check:
- Master-0's health (resource pressure, etcd status)
- Whether Master-0 is the etcd leader (leader election during restart)
- Network path specifically to Master-0

### Pattern: Cluster-Wide

**Disruptions from many sources to many destinations.**

```text
Worker-A → Master-0   ✗ disrupted
Worker-B → Master-1   ✗ disrupted
Worker-C → Master-2   ✗ disrupted
```

**Interpretation**: A cluster-wide issue affecting the entire network or control plane
simultaneously:
- Cloud provider network issue
- All control plane nodes under resource pressure simultaneously
- etcd quorum loss
- Widespread CPU starvation (typically from heavy E2E test workloads)

### Pattern: Unknown

**Backend type does not include node information in the disruption path.** Applies to
ingress-routed backends like `image-registry`, where the connection goes through the router
and the framework cannot determine which nodes are involved.

---

## Disruption During Upgrade vs Conformance

### Completely Different Significance

The same disruption event has radically different significance depending on phase:

| Phase | Context | Expected Disruption | Concern Level |
|-------|---------|-------------------|---------------|
| **Upgrade** | Control plane components are restarting, nodes are draining | Yes — brief disruption during API server and etcd restarts is normal | Low (if brief and within allowance) |
| **Conformance** | Cluster should be stable, running E2E tests | No — the cluster should be fully operational | High (any sustained disruption is unexpected) |

### Phase Detection in Timeline Files

The parser assigns a phase per event based on which timeline file it came from (in upgrade
jobs with two files):
- First file (sorted by filename) → `"upgrade"` phase
- Second file → `"conformance"` phase

In single-file (non-upgrade) jobs, all events are `"conformance"` phase.

### Interpreting Upgrade Phase Disruption

During upgrade, these are **expected** and not bugs:

- Brief (1–5s) API disruption during kube-apiserver rolling restart
- Brief (1–5s) disruption during etcd member restart
- Node NotReady events during node drain/reboot (MCO upgrade)
- Operator condition transitions (Progressing=True, briefly Degraded)

These become **concerning** when:
- Disruption exceeds the allowance threshold (typically 10–30s depending on backend)
- Multiple control plane components are disrupted simultaneously for extended periods
- A node fails to come back after drain/reboot
- An operator stays degraded after the upgrade window closes

### Interpreting Conformance Phase Disruption

During conformance testing, **any sustained disruption is unexpected**. Common causes:
- Resource pressure from E2E test workloads
- Leftover instability from a problematic upgrade
- Infrastructure issues (cloud provider, CI cluster networking)
- Product bugs triggered by specific test scenarios

---

## Symptom Labels

### What Symptom Labels Are

The CI system may attach **symptom labels** to job runs — machine-detected environmental
observations stored as JSON files in `artifacts/job_labels/`.

**Critical distinction: Symptom labels are NOT root causes.** They describe environmental
conditions detected during the run, which may or may not relate to the failure being
investigated.

### How Labels Are Generated

Automated analyzers scan the job's interval data and artifacts after completion, look for
specific patterns (e.g., "disruption events concurrent with high CPU measurements"), and
attach a label describing the observation.

### Accessing Symptom Labels

```bash
# List available symptom labels
gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/job_labels/" 2>/dev/null

# Download JSON symptom files (exclude the HTML summary)
gcloud storage cp "gs://test-platform-results/{bucket-path}/artifacts/job_labels/*.json" \
  local/job_labels/ --no-user-output-enabled 2>/dev/null || true
```

Each JSON file contains a summary and explanation of the detected symptom.

### Common Symptom Labels and Their Meaning

**Node-related symptoms:**
- **Node pressure / NotReady**: A node reported memory, disk, or PID pressure, or went
  NotReady. Find what caused the pressure — heavy workloads, resource leaks, pod evictions.
- **Node cordon/uncordon**: A node was cordoned (drained) and uncordoned. Expected during
  upgrades (MCO rolling reboot); during conformance suggests node maintenance or recovery.

**Operator-related symptoms:**
- **Operator degraded**: A cluster operator entered Degraded. Check which one and whether it
  recovered. Operators degraded at job completion are especially significant.
- **Operator unavailable**: An operator lost Available=True. More severe than Degraded —
  usually means the operator's workloads are not running.
- **Operator progressing**: An operator was still updating. Normal during upgrade; abnormal
  during conformance.

**Network-related symptoms:**
- **Disruption duration exceeded threshold**: Total disruption on one or more backends
  exceeded allowances. The most direct disruption-related symptom.
- **Network error rates elevated**: Higher than normal error rates on network probes.

**Resource-related symptoms:**
- **CPU starvation detected**: One or more nodes showed sustained CPU above 95%. Correlate
  with disruption source nodes.
- **Disk I/O pressure**: Cloud metrics showed disk I/O saturation. Correlate with etcd
  performance and API disruption.

### How to Use Symptom Labels

1. **Inform investigation direction** — "CPU starvation detected" → prioritize CPUMonitor
   events and OVS stalls.
2. **Corroborate findings** — a "disk I/O pressure" label strengthens a disk-I/O root-cause
   hypothesis.
3. **Never use as conclusions** — a symptom label alone is not sufficient for root cause.
   Always perform the full investigation.
4. **Include in reports** — mention relevant labels in the "Known Symptoms Seen" section, with
   the caveat that they are environmental observations.

---

## Correlating Disruption with Cluster Events

### The Time-Alignment Challenge

All event sources in the timeline file use the same clock (the cluster's system time), so
timestamps are directly comparable within a single file. Watch for:

- **Different granularity**: Some events are second-precise, others minute-precise
- **Event reporting lag**: Some events (like CloudMetrics) are aggregated over time windows
  and may report at the end of the window rather than the start
- **Multi-file analysis**: Two timeline files (upgrade + conformance) share the same clock
  and can be compared directly

### Building a Timeline of What Happened

The most effective technique is a chronological timeline overlaying disruption events with
cluster activity:

```text
21:49:00Z  CPUMonitor: worker-db64f CPU at 98%
21:49:05Z  OVSVswitchdLog: worker-db64f poll interval 9235ms
21:49:10Z  Disruption: host-to-host from worker-db64f to master-0 BEGAN
21:49:10Z  Disruption: host-to-host from worker-db64f to master-1 BEGAN
21:49:10Z  Disruption: host-to-host from worker-db64f to master-2 BEGAN
21:49:15Z  EtcdLog: master-0 apply request took too long
21:49:20Z  AuditLog: 3 of 200 requests failed
21:49:25Z  Disruption: kube-api-new-connections BEGAN
21:49:30Z  E2ETest: [sig-api-machinery] test FAILED
21:50:00Z  OVSVswitchdLog: worker-db64f poll interval recovered
21:50:05Z  Disruption: host-to-host endpoints ENDED
21:50:10Z  Disruption: kube-api-new-connections ENDED
```

From this timeline, the causal chain is clear:
1. CPU starvation on worker-db64f
2. OVS stalled (cannot process packets)
3. Host-to-host disruption from that node
4. API disruption (requests from that node's probes fail)
5. E2E test fails (running on or probing through that node)

### Overlaying Disruption with Specific Event Types

**Node drain/reboot events (MCO upgrades):**
- `NodeMonitor` events showing node condition changes
- `MachineMonitor` events showing machine phase transitions
- `ClusterOperator` events for `machine-config` operator showing Progressing=True
- Expect disruption during the drain window; investigate if it persists after

**Operator transitions:**
- `ClusterOperator` events showing Available/Degraded/Progressing changes
- Correlate with specific backend disruption (e.g., `kube-apiserver` operator progressing
  → kube-api disruption)
- Check if the operator recovered (Progressing=False, Available=True)

**Pod restarts and evictions:**
- `PodLog` events showing pod lifecycle changes
- `KubeletLog` events showing eviction decisions
- Correlate with the namespace of the disrupted backend's underlying pods

**Certificate rotations:**
- May cause brief TLS handshake failures
- `new-connections` disruption without `reused-connections` disruption
- Usually very brief (1–2s) and self-resolving

---

## Interpreting Disruption for Root Cause Analysis

### Disruption as Symptom, Not Cause

**This is the most important principle**: Disruption events describe what happened (API
became unavailable), not why it happened. The investigation must always trace from the
disruption event backwards to the underlying cause.

The investigation flow:
```text
Disruption detected → What was the source pattern? → What concurrent events occurred?
→ What does the causal chain look like? → What is the root cause?
```

### How to Determine if Disruption Caused Test Failures

Not all disruption causes test failures, and not all test failures come from disruption.
To determine the relationship:

1. **Check temporal overlap**: Did the test fail during an active disruption window?
   - Yes → disruption may have caused the failure (but could also be coincidental)
   - No → disruption is not the direct cause

2. **Check test type**: Does the failing test depend on API availability?
   - Tests that make API calls, create resources, or check operator status → likely
     affected by API disruption
   - Tests that check static configuration or audit policies → unlikely affected

3. **Check test error**: Does the test error reference connectivity?
   - `"connection refused"`, `"timeout"`, `"EOF"` → likely affected by disruption
   - `"assertion failed"`, `"expected X got Y"` → probably a functional bug, not disruption

4. **Check multiple runs**: Does the test consistently fail with disruption and consistently
   pass without disruption?
   - Consistent correlation → disruption is likely causal
   - Inconsistent → may be coincidental

### The Difference Between "Disruption Happened" and "Disruption Is the Bug"

**Scenario A**: "During upgrade, kube-api showed 3 seconds of disruption while the
kube-apiserver pod was restarting."
- **Expected behavior.** The upgrade restarts the API server, causing brief disruption. Not
  a bug.

**Scenario B**: "During conformance testing, kube-api showed 45 seconds of disruption
concurrent with 98% CPU on worker-db64f and OVS stalls."
- **A real problem.** CPU starvation froze networking. The disruption is the symptom; the CPU
  starvation is the proximate cause; the workload causing it is the root cause.

**Scenario C**: "During upgrade, kube-api showed 120 seconds of sustained disruption."
- **A real problem even during upgrade.** Brief disruption is expected; 120 seconds is not.
  The upgrade process itself may be broken (stuck drain, failed etcd restart).

---

## Common Root Cause Patterns

### Pattern 1: CPU Starvation → OVS Stall → Network Disruption

**The most common disruption pattern.** A node runs out of CPU, OVS cannot process packets,
and all network traffic from/to that node fails.

**Identifying signals:**
- Single-source fan-out in source-node analysis
- `CPUMonitor` >95% on the source node
- `OVSVswitchdLog` stalls on the source node (often >5000ms poll intervals)
- `Alert`: `ExtremelyHighIndividualControlPlaneCPU`

**Cascade:**
```text
Heavy workloads/tests → CPU exhaustion → OVS vswitchd starved → packets frozen
→ host-to-host disruption → API requests timeout → API disruption recorded
→ tests using API fail
```

**Root cause**: Whatever workloads consumed the CPU. Check `E2ETest` events for tests running
during the window.

### Pattern 2: Disk I/O Saturation → etcd Stalls → API Disruption

**Common on Azure.** Disk IOPS hit the cap, etcd cannot write, API server cannot commit
transactions.

**Identifying signals:**
- `CloudMetrics` showing disk IOPS at 100%
- `EtcdDiskCommitDuration` above 25ms
- `EtcdDiskWalFsyncDuration` above 10ms
- `EtcdLog` showing `slow fdatasync`, `apply took too long`
- All four variants of API backends fail (cache + non-cache, new + reused)
- `Alert`: `etcdHighCommitDurations`

**Cascade:**
```text
Disk I/O pressure → etcd WAL fsync slow → etcd cannot commit proposals
→ API server writes stall → API reads also stall (backpressure)
→ all API backends show disruption
```

**Root cause**: Whatever caused disk I/O pressure. On Azure, often the base VM disk tier
being too slow for the combined workload. Can also come from heavy logging, test workloads
writing to disk, or etcd compaction running during high load.

### Pattern 3: etcd Leader Election → Brief API Unavailability

**Normal during upgrades.** When etcd pods restart, a leader election occurs and the API
server briefly cannot process writes.

**Identifying signals:**
- `EtcdLog` showing `leader changed` or `elected leader`
- Brief (1–5s) disruption on all API backends
- Correlated with `ClusterOperator` etcd showing Progressing=True
- Usually during upgrade phase, not conformance

**Expected during upgrade** if brief. Becomes a problem if leader elections happen repeatedly
or outside the upgrade window.

### Pattern 4: Node Drain → Expected API Disruption

**Normal during upgrades.** MCO drains and reboots nodes one at a time for OS updates.

**Identifying signals:**
- `NodeMonitor` showing node condition changes (Ready → NotReady)
- `ClusterOperator` machine-config showing Progressing=True
- API disruption timed to the drain window
- Node comes back Ready after reboot

**Expected during upgrade.** Becomes a problem if:
- The drain takes too long (stuck draining pods)
- The node doesn't come back after reboot
- Multiple nodes drain simultaneously (breaking quorum)

### Pattern 5: OVN Restart → Network Disruption Window

**OVN-Kubernetes pod restart causes a brief networking outage on the affected node.**

**Identifying signals:**
- `OVSVswitchdLog` stalls correlated with OVN pod restart
- Disruption localized to one node (single-source fan-out)
- Brief duration (typically 5–15s during restart)
- May correlate with OVN-Kubernetes operator update during upgrade

### Pattern 6: Single-Node Disruption vs Cluster-Wide

**How to tell the difference:**

| Signal | Single-Node | Cluster-Wide |
|--------|------------|--------------|
| Source pattern | Single-source fan-out | Multi-source |
| CPU alerts | One node | Multiple nodes |
| OVS stalls | One node | Multiple nodes |
| API disruption | May be limited to probes from one node | All probes fail |
| etcd events | Usually clean (unless on control plane) | Often shows pressure |

### Pattern 7: CI Infrastructure Network Issue

**The test infrastructure itself has network problems, contaminating disruption data.**

**Identifying signals:**
- `ci-cluster-network-liveness` backend shows disruption
- Network liveness status = "degraded" or "unreliable"
- Disruption events may be artifacts of CI network, not cluster issues
- Other backends' disruption may be inflated or spurious

**Action**: Note the unreliable network liveness status prominently in the report. Do not
draw conclusions solely from disruption counts in runs with unreliable network liveness.
Non-disruption signals (etcd logs, CPU, alerts) remain valid even when network liveness is
unreliable.

---

## Cross-Run Comparison

### Why Cross-Run Analysis Matters

Single-run analysis can mislead — one occurrence might be an infrastructure fluke, a transient
cloud issue, or a rare race condition. Comparing across multiple runs of the same job reveals
whether disruption is:

- **Systematic** (same pattern every run) → likely a product bug or configuration issue
- **Intermittent** (some runs affected) → may be infrastructure-sensitive or a race condition
- **Isolated** (only one run affected) → likely infrastructure or environmental

### How to Compare Disruption Across Runs

1. **Identify common backends**: Which backends show disruption across runs?

   | Backend | Run 1 | Run 2 | Run 3 | Pattern |
   |---------|-------|-------|-------|---------|
   | kube-api-new | 5 events | 3 events | 0 events | Intermittent |
   | host-to-host-new | 11 events | 8 events | 12 events | Consistent |
   | cache-openshift-api | 0 events | 0 events | 0 events | Clean |

2. **Compare timing (relative)**: Are disruptions at similar points in the job?
   - Same relative time across runs → likely triggered by a specific test or phase
   - Random timing across runs → more likely infrastructure-dependent

3. **Compare source patterns**: Is the source node pattern consistent?
   - Same node type (e.g., always a worker) → workload scheduling issue
   - Different nodes each run → infrastructure-dependent

### Cross-Run Comparison Patterns

| Pattern | What It Means | Investigation Focus |
|---------|--------------|---------------------|
| Same backends at similar times | Product bug or test sequencing issue | Which test is running at that relative time? |
| Same backends at different times | Infrastructure-sensitive but product-related | What makes this backend vulnerable? |
| Different backends across runs | Environment-specific | Cloud provider, node types, resource allocation |
| `ci-cluster-network-liveness` disrupted in some runs | Those runs' disruption data is unreliable | Note caveat; still include for non-disruption signals |
| Cache backends consistently disrupted | Systemic etcd or networking issue | etcd health, disk I/O across all runs |
| Non-cache only | Component-specific problem | Focus on the specific API server/operator |
| Consistent source-node fan-out (same node type) | Workload scheduling → CPU starvation pattern | What's scheduled on those nodes? |

### Using Historical Data (Sippy)

For systematic comparison beyond the runs you're analyzing, use Sippy:

- **Disruption dashboard**: historical disruption rates for specific backends and job types
- **Test pass rates**: whether disruption-related test failures are increasing
- **Sippy intervals viewer**: visual comparison of interval data across runs:
  `https://sippy.dptools.openshift.org/sippy-ng/job_runs/{build_id}/{job_name}/intervals`

### Determining Code Change vs Infrastructure Issue

When a disruption regression appears:

1. **Check code-change correlation** — did a PR land that could affect the disrupted
   component? Use the `fetch-new-prs-in-payload` skill to identify recent changes.
2. **Check multiple job types** — disruption in only one job type (e.g., only Azure) may be
   infrastructure-specific; disruption across AWS, Azure, and GCP is more likely a product
   issue.
3. **Check the baseline** — use Sippy historical data to establish whether current disruption
   is elevated versus the job's normal rate.
4. **Check infrastructure changes** — CI infrastructure, cloud provider, or VM type changes
   that could explain the disruption.

---

## Disruption Allowance Thresholds

### What Allowances Are

The CI framework defines allowable disruption thresholds per backend per job type — the
maximum disruption (in seconds) considered acceptable for a scenario. Exceeding the allowance
fails the corresponding disruption test.

### How Thresholds Work

- Each disruption test monitors a specific backend
- The test sums total disruption seconds during its phase
- Total exceeds the allowance → test fails
- Allowances differ by phase (upgrade vs non-upgrade) and by backend

### Why Allowances Exist

Some disruption is architecturally unavoidable:
- API server rolling restart during upgrade → brief (1–3s) disruption per restart
- etcd member restart → brief quorum disruption
- Load balancer health check propagation delay

Allowances prevent these expected transients from failing tests while still catching genuine
regressions.

### Interpreting Failures Against Thresholds

A failed disruption test means disruption **exceeded** the baseline for that scenario — a
meaningful signal that something made it worse. Investigate the disruption beyond the expected
upgrade-related amount; the root cause is whatever pushed it over the threshold (a product
regression, heavier test workloads, infrastructure degradation).

---

## Tooling: The Disruption Parser

### Overview

`parse_disruption.py` is the primary tool for structured disruption analysis. It automates
extraction, classification, and correlation of disruption data from timeline files.

### Usage

```bash
python3 plugins/ci/skills/analyze-disruption/parse_disruption.py \
  <timeline.json> [timeline2.json ...] \
  [--backends backend1,backend2] \
  [--window 60] \
  [--format text|json] \
  [--job-name <name>] \
  [--build-id <id>] \
  [--target <target>]
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `files` | (required) | One or more timeline JSON file paths |
| `--backends` | all | Comma-separated backend name filters (substring match) |
| `--window` | 60 | Seconds to expand around disruption window for concurrent events |
| `--format` | text | Output format: `text` for human reading, `json` for structured analysis |
| `--job-name` | none | Prow job name (enables deep link generation) |
| `--build-id` | none | Prow build ID (enables deep link generation) |
| `--target` | none | CI operator target (enables artifact deep links) |

### What the Parser Produces

The parser output (JSON format) contains:

```json
{
  "disruptions": [...],           // Individual disruption events with classification
  "concurrent_events": {...},     // Events concurrent with disruption windows
  "source_node_analysis": {...},  // Single-source fan-out detection
  "network_liveness": {...},      // Network liveness backend summary
  "summary": {
    "disruption_count": 11,
    "backends": {"kube-api-new-connections": 5, ...},
    "time_range": {"from": "...", "to": "..."},
    "phase_breakdown": {"upgrade": 3, "conformance": 8},
    "network_liveness_status": "clean",
    "source_node_pattern": "single-source-fan-out",
    "key_signals": ["OVS stalls: 4 events, max 9235ms", ...]
  },
  "links": {
    "prow": "https://prow.ci.openshift.org/...",
    "sippy_intervals": "https://sippy.dptools.openshift.org/...",
    "gcsweb_timelines": ["https://gcsweb-ci.../e2e-timelines_..."]
  }
}
```

### Key Parser Features

- **Automatic backend classification** (cache/non-cache/canary/cloud)
- **Phase detection** for upgrade jobs (upgrade vs conformance)
- **Source-node fan-out detection** (single-source vs multi-source vs unknown)
- **Concurrent event extraction** with configurable time window
- **OVS stall summarization** with per-node max poll intervals
- **CPU pressure summarization** with affected node list
- **Cloud metrics summarization** (Azure disk IOPS, queue depth)
- **etcd pressure detection** from EtcdLog/EtcdDisk* events
- **Network liveness assessment** (clean/minor/degraded/unreliable)
- **Deep link generation** for Prow, Sippy, and GCS artifacts

### Network Liveness Assessment Scale

| Status | Total Liveness Events | Meaning |
|--------|----------------------|---------|
| `clean` | 0 | No test infra or cloud network issues |
| `minor` | 1–5 | Negligible blips — disruption data is reliable |
| `degraded` | 6–50 | Some disruption may be from infra/cloud — use caution |
| `unreliable` | 50+ | Massive network-liveness disruption — other disruption data is unreliable |

---

## Sippy Intervals Viewer

### Visual Analysis

The Sippy intervals viewer shows all interval data for a job run — disruption events, cluster
activity, and test execution:

```text
https://sippy.dptools.openshift.org/sippy-ng/job_runs/{build_id}/{job_name}/intervals
```

### What It Shows

- Horizontal timeline with all events plotted against time
- Color-coded events by source and severity
- Disruption events prominently highlighted
- Test execution intervals showing when each test ran
- Cluster operator state transitions
- Node state changes

### When to Use

- **Quick visual overview** before diving into detailed analysis
- **Pattern recognition** — visual correlation of multiple event types is often faster than
  reading raw data
- **Sharing with humans** — the easiest way to show someone what happened during a run
- **Cross-run visual comparison** — open multiple tabs to compare disruption patterns

---

## Key Artifacts for Disruption Analysis

Quick reference for locating disruption-relevant artifacts:

| Artifact | Path | Purpose |
|----------|------|---------|
| Timeline data | `artifacts/{target}/openshift-e2e-test/artifacts/junit/e2e-timelines_spyglass_*.json` | Disruption events + concurrent cluster activity |
| Audit logs | `artifacts/{target}/gather-extra/artifacts/audit_logs/` | API request details during disruption |
| etcd pod logs | `artifacts/{target}/gather-extra/artifacts/pods/openshift-etcd/` | etcd health and leader changes |
| Journal logs | `artifacts/{target}/gather-extra/artifacts/journal_logs/` | Node-level OVS and systemd logs |
| Symptom labels | `artifacts/job_labels/*.json` | Machine-detected symptom patterns |
| Cluster operators | `artifacts/{target}/gather-extra/artifacts/oc_cmds/co` | Operator status at gather time |
| Node status | `artifacts/{target}/gather-extra/artifacts/oc_cmds/nodes` | Node conditions at gather time |
| Pod status | `artifacts/{target}/gather-extra/artifacts/pods/` | Pod logs organized by namespace |

---

## Analysis Decision Tree

When starting a disruption investigation:

```text
1. Was ci-cluster-network-liveness disrupted?
   ├─ Yes → Mark run as potentially unreliable; note caveat in report
   │        Continue analysis — non-disruption signals are still valid
   └─ No → Disruption data is reliable

2. What is the source-node pattern?
   ├─ Single-source fan-out → Focus on that specific node
   │   ├─ Check CPUMonitor on that node
   │   ├─ Check OVSVswitchdLog on that node
   │   └─ Identify workloads running on that node
   ├─ Multi-source → Check if targeting same destination
   │   ├─ Same destination → Destination node issue
   │   └─ Different destinations → Cluster-wide issue
   └─ Unknown → Cannot localize; check all signal sources

3. Which backend types are disrupted?
   ├─ All four variants of a backend → Control plane resource exhaustion
   │   └─ Check etcd, disk I/O, CPU on control plane nodes
   ├─ Non-cache only → Component-specific or networking issue
   ├─ Cache only (rare) → Watch-cache or memory issue
   └─ Cloud/canary liveness → Infrastructure issue

4. What phase was disruption in?
   ├─ Upgrade → Expected if brief; concerning if prolonged
   │   └─ Check: is disruption within allowance thresholds?
   └─ Conformance → Unexpected; investigate root cause

5. What concurrent events are present?
   ├─ OVS stalls → CPU starvation chain (see Pattern 1)
   ├─ etcd pressure → Disk I/O chain (see Pattern 2)
   ├─ CloudMetrics → Cloud provider resource limits
   ├─ Node state changes → Planned operation or node failure
   └─ Alerts firing → Confirms severity; check alert details
```

---

## Example: Complete Disruption Analysis

### Scenario

A periodic e2e-azure-ovn-upgrade job shows 11 disruption events on `host-to-host-new-connections`
during the conformance phase.

### Step-by-Step Analysis

**1. Run the parser:**
```bash
python3 plugins/ci/skills/analyze-disruption/parse_disruption.py \
  timeline_upgrade.json timeline_conformance.json \
  --window 60 --format text
```

**2. Check network liveness:**
```text
Network liveness: clean — No test infra or cloud network issues
```
→ Disruption data is reliable.

**3. Check source pattern:**
```text
Source node analysis: All 11 disruptions originate from worker-db64f hitting 3 target nodes.
This indicates a source-side networking issue (OVS/CPU/disk pressure on the source node).
```
→ Single-source fan-out from worker-db64f. Problem is on that one node.

**4. Check concurrent events:**
```text
Key signals:
  - OVS vswitchd stalls: 4 events, max poll interval 9235ms on 1 node
  - CPU >95%: worker-db64f
  - Azure disk IOPS saturated (100%)
```
→ CPU starvation on worker-db64f caused OVS to stall, which caused the disruption.

**5. Check phase:**
```text
Phase breakdown: conformance: 11
```
→ All disruption during conformance phase (unexpected, not during upgrade).

**6. Root cause hypothesis:**

CPU starvation on worker node `worker-db64f` during conformance testing caused OVS vswitchd
to stall for up to 9.2 seconds, freezing all network traffic from that node. This caused
11 host-to-host disruption events across all three control plane nodes. Concurrent Azure
disk IOPS saturation (100%) suggests the underlying cause may be disk I/O pressure
cascading to CPU contention.

**Investigation next steps:**
- What E2E tests were running during the disruption window?
- What workloads were scheduled on worker-db64f?
- Is this pattern consistent across multiple runs of this job?
