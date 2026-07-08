# Test Failure Root-Cause Analysis

Use when [flaky-test-identification.md](flaky-test-identification.md) has classified a failure
as a real product regression in a plain e2e test (non-extension, non-install, non-upgrade) and
you need the root cause — for example, a conformance test like
`[sig-network] services should serve endpoints` that was stable on Sippy until it began failing
in `e2e-aws-ovn`.

This assumes the three-way triage is already done: the failure is not a ci-operator `reason`,
not a fail+pass flake twin, not a `<skipped>`, and not shared infra across 3+ jobs. If that is
not yet settled, start at [flaky-test-identification.md](flaky-test-identification.md).

Use a different reference when the failing test is: an extension binary (`*-tests-ext`) →
[test-extension-binaries.md](test-extension-binaries.md); `install should succeed` →
[install/general.md](install/general.md); an upgrade-phase regression →
[upgrade.md](upgrade.md); an `aggregated-` job verdict → [aggregated.md](aggregated.md).

---

## The method

**Never stop at a high-level symptom.** "The pod is crash-looping", "the operator went
Degraded", "the request timed out" are restatements of the failure, not causes. Each one has
an originating error one or two hops upstream. The job is to follow that chain:

```text
JUnit assertion  →  test source (what it asserted, on what resource)
                 →  cluster state in that namespace at the failure window
                 →  the failing container's own error (previous.log, exitCode)
                 →  the specific root cause (config, code, dependency)
```

Work it in that order. Each step narrows *where* and *when* to look for the next.

---

## Step 1 — Read the JUnit failure

The `<failure>` message and its stack trace are the entry point: they name the assertion, the
resource, and the moment of failure. JUnit is the source of truth over any alarming build-log
line (see [flaky-test-identification.md](flaky-test-identification.md#junit-interpretation)).

```bash
# openshift-tests results
gcloud storage cp "gs://test-platform-results/{bucket-path}/artifacts/{target}/openshift-e2e-test/artifacts/junit/junit_e2e_*.xml" \
  .work/prow-job-analysis/{build_id}/ --no-user-output-enabled
```

Extract three things from the failing `<testcase>`:

| Extract | From | Feeds |
|---------|------|-------|
| **Assertion** — expected vs actual, resource name/namespace | `<failure message=...>` | Step 2 (source), Step 3 (scope) |
| **Stack trace** — the code path that failed | `<failure>` body | Step 2 (source file/line) |
| **Failure window** — when the test ran and failed | `time=` attr + interval files (Step 4) | Step 4 (correlation) |

Read the stack-trace shape — it tells you the failure *kind* before you read a single log:

| Trace shape | Kind | Where the cause lives |
|-------------|------|-----------------------|
| `Expected <x> to equal <y>` / Gomega matcher | Assertion on cluster state | The resource the assertion names — Steps 3–5 |
| `timed out waiting for ... condition` / `context deadline exceeded` | The awaited state never arrived | The component that should have produced it — Steps 3–5 |
| `panic:` + goroutine stack | Test-code or client-go bug | Test source (Step 2); a nil/response from the API |
| `connection refused` / `no route to host` / `EOF` | Endpoint unreachable | Networking or the backend pod — Steps 3–5 |

---

## Step 2 — Locate the test source from the test name

The test name is the concatenation of its Ginkgo node texts, so it maps back to source. Read
the source to learn **what the test actually asserts** and **which resources it touches** —
that is what you correlate in Steps 3–5.

- The `[sig-*]` prefix names the owning SIG. OpenShift-authored e2e tests live in
  [`openshift/origin`](https://github.com/openshift/origin) under `test/extended/`; upstream
  Kubernetes conformance tests are vendored there from `k8s.io/kubernetes/test/e2e/`.
- Find the source by grepping a distinctive **literal fragment** of the name (the `It(...)`
  text, not the full `[sig-x]` string) in `openshift/origin`:

```bash
# In a local openshift/origin checkout — quote a stable, unique phrase from the test name
grep -rn "should serve endpoints" test/extended/ vendor/k8s.io/kubernetes/test/e2e/
```

- For an extension test (`*-tests-ext`), the source repo and file are reported directly: the
  `codeLocations` field in the binary's `list`/`run-suite` metadata gives `file:line`. See
  [test-extension-binaries.md](test-extension-binaries.md).

Read the assertion and the setup it depends on (namespaces created, images pulled, services
or CRs applied). A test failing at a `Consistently`/`Eventually` on some resource is telling
you *that resource* misbehaved — go check it, do not re-debug the test harness.

---

## Step 3 — Scope to namespace and component from the test name

The SIG prefix and the assertion's target namespace point at the operator and pod logs worth
reading. Pull those, not the whole cluster.

| Test signal | Component / namespaces to inspect | Domain reference |
|-------------|-----------------------------------|------------------|
| `[sig-network]`, service/endpoint/DNS/ingress | `openshift-ovn-kubernetes`, `openshift-dns`, `openshift-ingress`, `openshift-network-operator` | [networking.md](networking.md) |
| `[sig-storage]`, PV/PVC/CSI | `openshift-cluster-csi-drivers`, `openshift-cluster-storage-operator` | [resource-exhaustion.md](resource-exhaustion.md) (capacity) |
| `[sig-api-machinery]`, apiserver/CRD/webhook | `openshift-kube-apiserver`, `openshift-apiserver` | [disruption.md](disruption.md) (apiserver availability) |
| `[sig-etcd]`, quorum/leader | `openshift-etcd` | [resource-exhaustion.md](resource-exhaustion.md) (etcd disk/space) |
| `[sig-node]`, kubelet/scheduling/eviction | node journals, `openshift-machine-config-operator` | [resource-exhaustion.md](resource-exhaustion.md) |
| `[sig-auth]`, RBAC/oauth/SCC | `openshift-authentication`, `openshift-oauth-apiserver` | — |
| `[sig-arch]` / monitor / invariant | Cluster-wide post-run invariant, not one component | [disruption.md](disruption.md) |

Cluster state for these namespaces is in `gather-extra` and must-gather (paths below;
full tree in [artifacts.md](artifacts.md)):

```bash
# Cluster operator status and events at gather time
gcloud storage cp "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/oc_cmds/co" .work/prow-job-analysis/{build_id}/ --no-user-output-enabled
gcloud storage cp "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/oc_cmds/events" .work/prow-job-analysis/{build_id}/ --no-user-output-enabled
```

---

## Step 4 — Pin the failure window and correlate cluster events

A cluster event is a cause only if it **precedes and overlaps** the failure. Establish the
window, then look for an operator/event transition inside it.

```bash
# Interval (timeline) files — nested at unpredictable depth
gcloud storage ls 'gs://test-platform-results/{bucket-path}/**/e2e-timelines_spyglass_*.json'
```

1. **Window** — find the interval with `source="E2ETest"` and
   `message.annotations.status="Failed"` for your test. Its `from`/`to` timestamps are the
   failure window.
2. **Overlap** — filter intervals to `level="Error"|"Warning"` and `source="OperatorState"`
   that overlap that window. An operator going Degraded/Unavailable *before* the test failed,
   in the namespace from Step 3, is a prime suspect.
3. **Direction of causation** — a transition that starts before the window and clears after is
   a cause; one that starts only after the test already failed is a downstream effect. State
   the timing explicitly, e.g. "test failed at 10:23:45; network operator went Degraded at
   10:23:12 (reason: `OVNKubernetesController`)".

`oc_cmds/events` and must-gather per-namespace events give the same signal with reasons and
counts. Cross-check apiserver audit logs when the assertion involves API calls
([artifacts.md](artifacts.md#audit_logs--api-server-audit-logs)). For deep timeline
interpretation — cause vs symptom vs noise — see [disruption.md](disruption.md).

---

## Step 5 — Trace crash-looping / failing containers to the originating error

When Steps 3–4 point at a pod that restarted or never became ready, the cause is in that
pod's own status and prior log — not in the phrase "crash-looping".

**Container status** — the richest single source is the pod YAML in must-gather
(`namespaces/{ns}/pods/{pod}/{pod}.yaml`), field `status.containerStatuses[]`:

| Field | Read as |
|-------|---------|
| `lastState.terminated.exitCode` | **137** = SIGKILL — OOMKilled or liveness-probe kill; **143** = SIGTERM (graceful); **1/2** = application error/panic; **0** + restart = clean exit then restart |
| `lastState.terminated.reason` | `OOMKilled` → memory ([resource-exhaustion.md](resource-exhaustion.md)); `Error` → read the log; `ContainerCannotRun` → image/command |
| `restartCount` | High and climbing = CrashLoopBackOff; correlate the restart times with Step 4's window |
| `state.waiting.reason` | `ImagePullBackOff`/`ErrImagePull` → pull path ([networking.md](networking.md)); `CreateContainerError` → config/secret/mount |

**Previous log** — the current log shows the healthy restart; the crash is in the *previous*
container. That log holds the originating error:

```bash
# gather-extra keeps current.log and previous.log per container
gcloud storage cp -r "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/pods/{namespace}/" \
  .work/prow-job-analysis/{build_id}/pods/ --no-user-output-enabled
# read {pod}/{container}/previous.log — the panic/fatal/config error that caused the restart
```

**Follow the dependency chain.** A crashing pod usually blames something upstream: a config it
read, a dependency it dialed, a volume it mounted, a CR it reconciled. Trace one hop further
until you reach an error that is actionable (a specific bad value, a missing object, a code
path), not another "X is unavailable".

---

## Common e2e failure categories → typical root cause

| Category | Signature in JUnit / logs | Typical root cause | Route / next step |
|----------|---------------------------|--------------------|-------------------|
| Endpoint/service unreachable | `connection refused`, `no endpoints available`, `i/o timeout` | No ready backend, OVN programming lag, DNS | [networking.md](networking.md) |
| Eventual-condition timeout | `timed out waiting for condition` on a resource | The producing controller/operator stalled | Step 3 operator → Step 5 pod |
| Pod never Ready | `CrashLoopBackOff`, non-zero `exitCode` in status | The container's own `previous.log` error | Step 5 |
| OOM / node pressure | `exitCode 137`, `OOMKilled`, `NodeNotReady`, evictions | Memory/disk/PID exhaustion | [resource-exhaustion.md](resource-exhaustion.md) |
| API flakiness during test | `the server was unable to return a response`, audit gaps | apiserver/etcd disruption in the window | [disruption.md](disruption.md), [resource-exhaustion.md](resource-exhaustion.md) |
| Image pull failure | `ImagePullBackOff`, `manifest unknown`, `x509` | Registry/mirror/trust | [networking.md](networking.md) |
| Test-code panic | `panic:` + goroutine stack in the test binary | Test bug (nil deref, bad type-assert) | Step 2 source; likely a test-repo fix |
| Cloud API error mid-test | `RequestLimitExceeded`, quota, `InsufficientInstanceCapacity` | Cloud throttling/capacity | [cloud-provider-errors.md](cloud-provider-errors.md) |

A `panic:` in the *test binary* points at the test repo; a `panic:` or fatal in a *product
pod* points at the product. Distinguish by which process the trace belongs to (Step 1 shape,
Step 5 pod log).

---

## Root-cause synthesis

Before writing the conclusion, confirm the chain holds end to end:

1. **Assertion identified** — the exact expected-vs-actual and the resource it names (Step 1).
2. **Source read** — what the test asserted and depended on, not a guess from the name
   (Step 2).
3. **Window pinned** — the failure's `from`/`to`, with the correlated event *preceding* it and
   in the right namespace (Steps 3–4).
4. **Originating error reached** — a specific `previous.log` line, `exitCode`+`reason`, or
   config value — not "pod crash-looping" or "operator degraded" (Step 5).
5. **Domain confirmed** — if the root cause landed in networking/storage/resource/cloud,
   the matching reference agrees and owns the fix.

State the primary cause, the evidence (with timestamps), any contributing factors, and where
the fix lives (product repo, test repo, or a domain reference). If the chain breaks — no
correlated event, source doesn't match the symptom — re-check the flake/infra classification
in [flaky-test-identification.md](flaky-test-identification.md) before concluding.

## See Also

- [flaky-test-identification.md](flaky-test-identification.md) — the triage that routes here;
  JUnit interpretation, Sippy baselines, infra-vs-flake-vs-regression
- [artifacts.md](artifacts.md) — full artifact tree: `gather-extra`, must-gather, pod YAMLs,
  interval and audit paths
- [networking.md](networking.md) — service/DNS/OVN/ingress and image-pull root causes
- [resource-exhaustion.md](resource-exhaustion.md) — OOM (`exitCode 137`), node pressure,
  etcd/disk exhaustion behind timeouts
- [disruption.md](disruption.md) — interval/timeline interpretation; apiserver availability in
  the failure window
- [cloud-provider-errors.md](cloud-provider-errors.md) — cloud API/quota/capacity errors
  during a test
- [test-extension-binaries.md](test-extension-binaries.md) — `*-tests-ext` source
  (`codeLocations`) and extension-specific failures
- [hypershift.md](hypershift.md) — plain test failures in HCP jobs; correlate management vs
  hosted cluster
- [aggregated.md](aggregated.md) — statistical verdict when the failing test is in an
  `aggregated-` job
