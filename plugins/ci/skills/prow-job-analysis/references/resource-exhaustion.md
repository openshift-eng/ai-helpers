# Resource Exhaustion Reference

CPU, memory, disk, ephemeral-storage, PID, etcd-space, and PVC exhaustion in Prow CI —
OOM kills, node pressure and eviction, unschedulable pods, and the cascades they trigger.

First question is always **which cluster ran out**: the ephemeral **cluster under test**,
or the **CI build-farm** running the job. Different failure domains, owners, and fixes —
see [Two Failure Domains](#two-failure-domains) first.

## When to Use

- Pods/containers show `OOMKilled`, exit code `137`, or high `restartCount`
- Nodes report `MemoryPressure`, `DiskPressure`, or `PIDPressure`; pods `Evicted`
- Pods stuck `Pending` with `FailedScheduling` (`Insufficient cpu/memory`, taints, PVC)
- Pods stuck `ContainerCreating` on storage/IP allocation; PVCs stuck `Pending`
- etcd logs `mvcc: database space exceeded` / `NOSPACE` alarm
- Job dies in `build-log.txt` with `pod_pending` or a truncated log (sidecar OOM)

**Use a different reference for:**

- CPU starvation / disk-I/O latency driving disruption (`CPUMonitor`, `CloudMetrics`,
  `EtcdDiskWalFsyncDuration`, OVS stalls) → [disruption.md](disruption.md#key-signal-sources)
- Build-farm capacity, `pod_pending` mechanics, lease exhaustion, `openshift/release`
  correlation → [ci-infrastructure-changes.md](ci-infrastructure-changes.md#pod_pending)
- Cloud **quota** at install time (vCPU, EBS/PD volume limits, EIP) →
  [cloud-provider-errors.md](cloud-provider-errors.md)
- Resource pressure *during install* (bootstrap OOM, undersized control plane) →
  [install/general.md](install/general.md)
- OVN node-subnet / CNI IP exhaustion mechanics → [networking.md](networking.md#ovn-kubernetes-and-sdn)

## Two Failure Domains

Every Prow CI run involves two clusters; exhaustion means opposite things in each.

| | **CI build-farm cluster** | **Cluster under test** |
|---|---|---|
| What runs there | ci-operator pod, the multi-container test pod (`test` + `sidecar`), build pods | The ephemeral OpenShift cluster being installed and exercised |
| Exhaustion looks like | `pod_pending`, `test`/`sidecar` container `OOMKilled`, evicted ci-op pod, truncated `build-log.txt` | Product pods `OOMKilled`, nodes `NotReady`/pressure, etcd `NOSPACE`, PVCs `Pending` |
| Evidence lives in | top-level `build-log.txt`, `prowjob.json`, `podinfo.json` | `gather-extra/`, must-gather, `e2e-timelines_spyglass_*.json` |
| Owner / fix | Test Platform; retry, adjust step resource requests | Product team or job config; real bug vs undersized cluster |
| Verdict | Almost always **CI infrastructure** | Product bug **or** infra, must disambiguate |

**Decision rule:** if the failure is in the **top-level** `build-log.txt` before/around
test start, or in `podinfo.json` container statuses, it is the **build-farm** pod — CI
infra. If it is in gather-extra/must-gather/interval data from the provisioned cluster, it
is the **cluster under test**. See
[ci-infrastructure-changes.md](ci-infrastructure-changes.md#distinguishing-ci-infrastructure-vs-product-failures)
for the full CI-vs-product framework.

## Fast Triage

| Symptom / log string | Area | Section |
|----------------------|------|---------|
| exit code `137`, `reason: OOMKilled` | OOM kill | [OOM Kills](#oom-kills) |
| `Out of memory: Killed process`, `oom-kill:`, `Memory cgroup out of memory` | Kernel/cgroup OOM | [OOM Kills](#oom-kills) |
| `System OOM encountered`, `SystemOOM` event | Node-level OOM | [OOM Kills](#oom-kills) |
| node cond `MemoryPressure`/`DiskPressure`/`PIDPressure=True`, pods `Evicted` | Node pressure | [Node Pressure & Eviction](#node-pressure-and-eviction) |
| `The node was low on resource: [memory\|ephemeral-storage]` | Eviction | [Node Pressure & Eviction](#node-pressure-and-eviction) |
| `FailedScheduling`, `Insufficient cpu/memory`, `untolerated taint` | Scheduling | [Pod Scheduling Failures](#pod-scheduling-failures) |
| `Usage of EmptyDir`/`ephemeral local storage usage exceeds` | Ephemeral storage | [Ephemeral Storage](#ephemeral-storage-exhaustion) |
| `mvcc: database space exceeded`, `alarm:NOSPACE`, `etcdserver: no space` | etcd space | [etcd Storage](#etcd-storage-exhaustion) |
| PVC `Pending`, `ProvisioningFailed`, `failed to provision volume` | Storage provisioning | [PVC & Storage](#pvc-and-storage-provisioning) |
| truncated `build-log.txt`, `sidecar` `OOMKilled` in `podinfo.json` | CI sidecar | [CI Pod & Sidecar](#ci-pod-and-sidecar-resources) |
| `pod_pending`, `did not start running within ...` | Build-farm capacity | [ci-infrastructure-changes.md](ci-infrastructure-changes.md#pod_pending) |

## Where to Look

Paths are relative to `artifacts/{target}/` (cluster under test). Full form:
`gs://test-platform-results/{bucket-path}/artifacts/{target}/...`. See
[artifacts.md](artifacts.md#gather-extra-artifacts) for the complete tree.

| Artifact | Path | Use for |
|----------|------|---------|
| Node conditions/capacity | `gather-extra/artifacts/oc_cmds/nodes` | `MemoryPressure`/`DiskPressure`/`PIDPressure`, allocatable |
| Cluster events | `gather-extra/artifacts/oc_cmds/events` | `Evicted`, `OOMKilling`, `FailedScheduling`, `ProvisioningFailed` |
| Pod snapshot | `gather-extra/artifacts/oc_cmds/pods` | `RESTARTS`, `Pending`, `Evicted`, `OOMKilled` status |
| PV/PVC | `gather-extra/artifacts/oc_cmds/pv` | Bound vs available volumes |
| Node journals | `gather-extra/artifacts/journal_logs/` | Kernel OOM (`Out of memory`), kubelet eviction |
| etcd pod logs | `gather-extra/artifacts/pods/openshift-etcd/` | `NOSPACE`, quota exceeded, compaction |
| Pod YAML (container status) | must-gather `namespaces/<ns>/pods/<pod>/<pod>.yaml` | `lastState.terminated.{reason,exitCode}`, `restartCount` |
| Host service logs | must-gather `host_service_logs/masters/{kubelet,crio}_service.log` | kubelet eviction/OOM decisions |
| CI test pod status | `podinfo.json` | build-farm container exit codes / `OOMKilled` |
| Timeline | `**/e2e-timelines_spyglass_*.json` | `NodeMonitor`, `Alert`, `KubeletLog`, `CPUMonitor` |

If must-gather is present, the must-gather-analyzer scripts summarize node/pod/event health
(`analyze_nodes.py --problems-only`, `analyze_pods.py --problems-only`,
`analyze_events.py --type Warning`, `analyze_etcd.py`) — invoked by the
`prow-job-analysis` skill. See
`plugins/must-gather/skills/must-gather-analyzer/SKILL.md`.

---

## OOM Kills

A container is OOM-killed when it exceeds its memory `limit` (cgroup OOM) or the node runs
out of memory and the kernel OOM killer reaps a victim (node OOM). The signals differ.

### Exit code 137 and the OOMKilled reason

- **`exitCode: 137`** = `128 + 9` (SIGKILL). Strong hint, not proof — SIGKILL from other
  sources (liveness-probe hard kill, node shutdown) also yields 137.
- **`reason: OOMKilled`** in the container's terminated state is the definitive signal.
- `exitCode: 143` = `128 + 15` (SIGTERM) — graceful stop or liveness restart, **not** OOM.

### Which container was killed

Read the pod YAML (must-gather) and inspect every container, not just container 0:

```bash
# must-gather: find OOM-killed containers cluster-wide
grep -rl "OOMKilled" */namespaces/*/pods/*/*.yaml
```

In the YAML, the killed container has:

```yaml
lastState:
  terminated:
    reason: OOMKilled
    exitCode: 137
restartCount: 5          # repeated OOM → CrashLoopBackOff
```

`state.running` with a high `restartCount` and `lastState.terminated.reason: OOMKilled`
means it is OOM-looping now. `gather-extra/oc_cmds/pods` shows `RESTARTS` counts to spot
the pod first; the YAML confirms the reason.

### Container-limit OOM vs node-level OOM

| | Container-limit (cgroup) OOM | Node-level OOM |
|---|---|---|
| Trigger | One container exceeds its `resources.limits.memory` | Node memory exhausted; kernel picks victims |
| Event | None by default — only `containerStatuses.lastState` | Kubelet node event `SystemOOM` (`System OOM encountered`) |
| Journal | `Memory cgroup out of memory: Killed process ...` | `Out of memory: Killed process ...`, `oom-kill:constraint=CONSTRAINT_NONE` |
| Meaning | That workload needs more memory / has a leak | Node oversubscribed or a noisy neighbor; look at `MemoryPressure` |
| Fix | Raise the container limit or fix the leak | Right-size requests, spread load, add capacity |

### Where OOM evidence lives

1. **Pod status** (most reliable): must-gather pod YAML `containerStatuses[].lastState.terminated`.
2. **Events**: `oc_cmds/events` / must-gather events — node-level OOM shows `SystemOOM`;
   Node Problem Detector (when present) emits `OOMKilling`.
3. **Node journal**: `journal_logs/` — grep `Out of memory`, `oom-kill:`, `Killed process`,
   `Memory cgroup out of memory`. The victim's `(comm)` and RSS are logged here.
4. **Kernel/dmesg**: on nodes that never became Ready, kernel OOM appears in the install
   log bundle serial console (see [install/general.md](install/general.md)) rather than the journal.

```bash
grep -rEi "out of memory|oom-kill|killed process|cgroup out of memory" \
  gather-extra/artifacts/journal_logs/
```

---

## Node Pressure and Eviction

Kubelet sets a node condition and evicts pods when a resource crosses an eviction threshold.

| Condition | Resource | Downstream |
|-----------|----------|------------|
| `MemoryPressure` | node `memory.available` low | Evict `BestEffort`, then `Burstable` over request; taint `node.kubernetes.io/memory-pressure` |
| `DiskPressure` | `nodefs`/`imagefs` low (`.available`/`.inodesFree`) | Image & dead-container GC, then pod eviction; taint `node.kubernetes.io/disk-pressure` |
| `PIDPressure` | node PIDs exhausted | New pods blocked; existing may be killed; taint `node.kubernetes.io/pid-pressure` |

### The eviction chain

```text
resource threshold crossed → node condition True → kubelet evicts lowest-priority pods
  → pod .status.phase=Failed, reason=Evicted → rescheduled elsewhere
  → if every node is pressured: reschedule storm → more pressure → nodes NotReady
```

Evicted pods carry a message naming the resource:

- `The node was low on resource: memory.`
- `The node was low on resource: ephemeral-storage. Threshold quantity: ...`
- `Pod ephemeral local storage usage exceeds the total limit of containers ...`

### Where to look

- `oc_cmds/nodes` → `.status.conditions[]` for `*Pressure` (`status: "True"`) and
  `.status.allocatable`; `.spec.taints` for the pressure taints.
- `oc_cmds/events` → `Evicted`, `NodeHasDiskPressure`, `NodeHasInsufficientMemory`,
  `EvictionThresholdMet`; recovery shows `NodeHasSufficientMemory`/`NodeHasNoDiskPressure`.
- Timeline `NodeMonitor` intervals → node Ready/NotReady transitions with timing.
- kubelet journal → `attempting to reclaim`, `eviction manager: must evict pod(s)`.

A node flapping between pressure and recovery evicts and reschedules repeatedly — a common
root cause of "random" unrelated test failures ([Cascades](#how-exhaustion-cascades)).

---

## Pod Scheduling Failures

Unschedulable pods stay `Pending` with `PodScheduled=False` and a `FailedScheduling` event.
The scheduler message enumerates why each node was rejected.

| Message fragment | Cause |
|------------------|-------|
| `Insufficient cpu`, `Insufficient memory` | Requests exceed allocatable on every node |
| `Insufficient ephemeral-storage` | Ephemeral-storage request unsatisfiable |
| `node(s) had untolerated taint {...}` | Taint (incl. pressure/`NotReady` taints) without matching toleration |
| `node(s) didn't match Pod's node affinity/selector` | nodeSelector/affinity too restrictive |
| `node(s) had volume node affinity conflict` | PV zone/topology ≠ where the pod can run |
| `pod has unbound immediate PersistentVolumeClaims` | PVC not bound (see [PVC & Storage](#pvc-and-storage-provisioning)) |
| `too many pods` / `node(s) exceed max volume count` | Node pod-count or per-node volume-attach cap reached |

```bash
grep -rE "FailedScheduling|Insufficient|untolerated taint|volume node affinity" \
  gather-extra/artifacts/oc_cmds/events
```

**Subnet / IP exhaustion** also strands pods, but at `ContainerCreating`, not scheduling:
the node's pod subnet or the cloud ENI/secondary-IP pool is empty (`no IP addresses
available in range`, `failed to assign an IP address`). Mechanics live in
[networking.md](networking.md#ovn-kubernetes-and-sdn); cloud IP/subnet limits in
[cloud-provider-errors.md](cloud-provider-errors.md).

Distinguish real exhaustion from config: `Insufficient cpu/memory` on **all** nodes = the
cluster is genuinely full (undersized, or a workload requests too much); an `untolerated
taint`/affinity message = placement constraints, not capacity.

---

## Ephemeral Storage Exhaustion

Ephemeral storage is the node's `nodefs`/`imagefs` (container writable layers, `emptyDir`,
logs, images). Filling it triggers `DiskPressure` → image GC → eviction.

Common CI causes:

- **Test artifacts written to the pod filesystem** instead of an artifact dir — large
  dumps, cores, or captures balloon the writable layer.
- **Container logs growing unbounded** — a chatty/looping container fills `/var/log/pods`;
  kubelet rotates, but burst rate can outrun rotation.
- **Image layer buildup** — many large images pulled onto one node fill `imagefs`.
- **`emptyDir` with no `sizeLimit`** — a workload fills the medium until node-level pressure.

Signals:

- Pod evicted with `low on resource: ephemeral-storage` or
  `Usage of EmptyDir volume "X" exceeds the limit "Y"`.
- Node `DiskPressure=True`; `oc_cmds/nodes` `.status.allocatable`/`.capacity`
  `ephemeral-storage`; kubelet reclaim of `imagefs`/`nodefs`.
- Journal: filesystem-full / GC messages; `free disk space failed`.

kubelet garbage-collects `imagefs` at its image-GC high threshold before evicting; if
eviction still fires, disk is filling faster than GC frees it. This is distinct from
**disk-I/O saturation** (throughput, not capacity) — that is a disruption signal
(`CloudMetrics`, `EtcdDisk*`) in [disruption.md](disruption.md#key-signal-sources).

---

## etcd Storage Exhaustion

etcd enforces a backend DB size quota. Hitting it puts the cluster into a **read-only**
alarm state — writes fail cluster-wide, the API returns errors, and operators degrade.
OpenShift raises the quota above the 2 GiB upstream default (commonly ~8 GiB).

Log/alarm strings (`gather-extra/artifacts/pods/openshift-etcd/`):

- `mvcc: database space exceeded`, `etcdserver: mvcc: database space exceeded`
- `alarm:NOSPACE`, `etcdserver: no space`
- `database space exceeded` in kube-apiserver logs (writes rejected downstream)
- `apply request took too long`, `took too long ... to execute` (also disk-I/O — correlate)

Causes:

- **Object bloat** — an explosion of secrets, configmaps, events, or CRs (a controller
  hot-looping create/delete, or a test creating thousands of objects) grows the DB and the
  history keyspace faster than compaction reclaims it.
- **Compaction/defrag not keeping up** — space is freed logically by compaction but only
  returned to the FS by defragmentation; without defrag the DB stays near quota.
- **Slow disk** amplifies the above (WAL fsync latency) — see
  [disruption.md](disruption.md#key-signal-sources).

Evidence: etcd `current.log`/`previous.log` for the alarm and compaction lines; alerts
`etcdBackendQuotaLowSpace` / `etcdExcessiveDatabaseGrowth` (timeline `Alert`); count objects
via must-gather (`namespaces/*/core/` sizes, event counts) to find the bloated resource.
This is etcd out of **space** — etcd slow due to disk **I/O latency** is separate.

---

## PVC and Storage Provisioning

Dynamic provisioning can fail at bind time, leaving PVCs `Pending` and their consuming pods
`Pending` (`unbound immediate PersistentVolumeClaims`).

| PVC/event signal | Cause |
|------------------|-------|
| `ProvisioningFailed`, `failed to provision volume with StorageClass "X"` | CSI driver/provisioner error |
| `waiting for a volume to be created, either by external provisioner ...` | Provisioner not running/responding; missing CSI driver |
| `rpc error: code = ... exceeded`, `VolumeLimitExceeded`, `exceeded quota` | Cloud volume count/size limit or namespace quota |
| `node(s) exceed max volume count`, `Multi-Attach error for volume` | Per-node attach cap; volume already attached elsewhere |
| PVC `Pending` with no events, pod not yet scheduled | `WaitForFirstConsumer` — **normal** until a pod consumes it |

Notes:

- **`WaitForFirstConsumer`** binds only once a pod is scheduled; a `Pending` PVC here is
  expected, not a failure. Only investigate if the *pod* is also stuck.
- **Topology conflict** — a bound PV in zone A with the pod forced to zone B yields
  `volume node affinity conflict` at scheduling ([Pod Scheduling](#pod-scheduling-failures)).
- Cloud-side volume **quota/attach limits** are the storage face of
  [cloud-provider-errors.md](cloud-provider-errors.md); CSI-driver crashes are a product/infra
  bug — check the driver pods under `gather-extra/artifacts/pods/`.

Look in `oc_cmds/pv`, `oc_cmds/events` (grep `ProvisioningFailed|Multi-Attach|exceed`), and
the CSI driver/`openshift-cluster-csi-drivers` pod logs.

---

## CI Pod and Sidecar Resources

The Prow test pod is multi-container: `test` (the workload/ci-operator entrypoint) plus a
Prow **`sidecar`** that streams, censors (redacts secrets from), and uploads logs and
artifacts; init containers include `clonerefs`, `initupload`, and `place-entrypoint`. All
run on the **build-farm**, not the cluster under test.

- **`sidecar` OOM** — very large artifact/log volume makes the sidecar buffer/censor a lot;
  it can be `OOMKilled` (exit `137`). Result: `build-log.txt` ends abruptly, artifacts are
  truncated or missing, and the job errors even if tests passed. Confirm in `podinfo.json`
  (container `sidecar`, `reason: OOMKilled`).
- **`test` container OOM/evicted** — the ci-operator/test process exceeds its step resource
  request, or the build node is under pressure → `pod_pending`, `Process interrupted`, or a
  truncated log.

This is a **build-farm** (CI infrastructure) failure — retry, and reduce artifact size or
adjust the step's resource requests in `openshift/release`. Mechanics and `pod_pending`
detail: [ci-infrastructure-changes.md](ci-infrastructure-changes.md#pod_pending). Do not
mistake it for a cluster-under-test problem.

---

## How Exhaustion Cascades

Resource exhaustion rarely stays local; one shortage fans out into many unrelated failures:

```text
memory limit hit → container OOMKilled → CrashLoopBackOff → dependency unavailable
  → dependent test times out → many "unrelated" tests fail together

node pressure → kubelet evicts pods → reschedule onto other nodes → those pressure too
  → nodes NotReady → API/etcd on those nodes disrupted → cluster-wide disruption

etcd NOSPACE → writes rejected → apiserver errors → operators degrade → conformance mass-fails
```

**Victim vs cause:** a test that *fails* during pressure is usually a **victim**. A test
that *runs* (and often passes) while consistently present during pressure across multiple
runs is a more likely **cause**. Identify the *first* resource event in time and trace
forward; the earliest OOM/eviction/alarm is typically the trigger, later failures are
fallout. CPU-starvation fan-out (OVS stalls, backend disruption) is analyzed in
[disruption.md](disruption.md).

---

## Diagnosing from Must-Gather and Interval Files

**Interval files** (`e2e-timelines_spyglass_*.json`) give a time-ordered view. Relevant
sources ([disruption.md](disruption.md#key-signal-sources) has the full catalog):

- `NodeMonitor` / `MachineMonitor` — node Ready↔NotReady, pressure transitions
- `Alert` — `KubeletTooManyPods`, `etcdBackendQuotaLowSpace`, memory/disk alerts firing
- `KubeletLog` / `PodLog` — eviction and OOM lifecycle events
- `CPUMonitor`, `CloudMetrics`, `EtcdDisk*` — CPU/disk-I/O pressure (disruption territory)

```bash
grep -oE '"(NodeMonitor|Alert|KubeletLog)"[^}]*"humanMessage":"[^"]*"' \
  *e2e-timelines_spyglass_*.json
```

**Must-gather** gives cluster state at collection time:

1. `analyze_nodes.py --problems-only` → node conditions, allocatable, pressure/taints.
2. `analyze_pods.py --problems-only` → OOMKilled/Evicted/Pending pods, restart counts.
3. `analyze_events.py --type Warning` → `Evicted`, `FailedScheduling`, `ProvisioningFailed`, `SystemOOM`.
4. `analyze_etcd.py` → etcd DB size, alarms, compaction health.
5. Read the flagged pod YAMLs for `containerStatuses[].lastState.terminated`.

Correlate the earliest resource event's timestamp against the failed test's window (from
`E2ETest` intervals) to separate cause from fallout.

> Must-gather only exists if the cluster was stable enough to run `oc adm must-gather`. If
> absent, the cluster likely collapsed under the exhaustion — rely on `gather-extra`,
> journals, and interval files. See [artifacts.md](artifacts.md#must-gather-availability).

---

## Quick Triage Checklist

1. **Which domain?** Top-level `build-log.txt` / `podinfo.json` → build-farm (CI infra,
   retry). gather-extra / must-gather / intervals → cluster under test.
   ([Two Failure Domains](#two-failure-domains))
2. **Which resource?** memory (OOM), disk/inodes (DiskPressure/ephemeral), PIDs, etcd space,
   PVC — grep the strings in [Fast Triage](#fast-triage).
3. **Container-limit or node-level?** `containerStatuses` reason only → cgroup limit; node
   `SystemOOM`/`MemoryPressure` → node oversubscribed. ([OOM Kills](#oom-kills))
4. **Earliest event.** Find the first OOM/eviction/`FailedScheduling`/`NOSPACE` in time;
   trace the cascade forward from there. ([Cascades](#how-exhaustion-cascades))
5. **Cause or victim?** A failing test during pressure is usually a victim; a heavy test
   present across runs during pressure is a candidate cause.
6. **Undersized or leak?** `Insufficient` on all nodes / SNO → capacity; steadily growing
   memory/DB with restarts → leak. Retry-passes ⇒ transient infra; reproduces ⇒ real.

## See Also

- [disruption.md](disruption.md) — CPU starvation, disk-I/O latency, etcd I/O, OVS stalls, backend disruption
- [ci-infrastructure-changes.md](ci-infrastructure-changes.md) — build-farm capacity, `pod_pending`, CI-vs-product framework
- [cloud-provider-errors.md](cloud-provider-errors.md) — cloud quota, volume/EIP limits at install time
- [networking.md](networking.md) — OVN node-subnet / CNI IP exhaustion
- [install/general.md](install/general.md) — resource pressure during installation
- [artifacts.md](artifacts.md) — full artifact tree, gather-extra, must-gather layout
