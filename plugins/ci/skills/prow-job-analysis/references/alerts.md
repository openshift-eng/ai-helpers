# Alert Test Failures

Use when a failing test asserts on Prometheus alerts rather than on a product behavior. A
firing alert is a **symptom**: the test failed because some component misbehaved long
enough for an alert rule to fire. The job is to find which alert, from which component, why
it fired — and whether the test that caught it is a blocking failure or a flake.

Use a different reference when the alert is downstream of a cause another reference owns:
API/backend disruption alerts → [disruption.md](disruption.md); node pressure, OOM, etcd disk
alerts → [resource-exhaustion.md](resource-exhaustion.md); network/DNS/ingress alerts →
[networking.md](networking.md); alerts during an upgrade rollout → [upgrade.md](upgrade.md).

---

## Which alert test failed

| Test name pattern | Kind | What it checks |
|-------------------|------|----------------|
| `[sig-instrumentation] Prometheus ... shouldn't report any alerts in firing state apart from Watchdog and AlertmanagerReceiversNotConfigured [Early]` | Conformance (usually blocking) | A one-shot `ALERTS{alertstate="firing"}` query at the **start** of the suite, minus an allow-list. Anything firing then — usually left over from install — fails it |
| `[<component>][invariant] alert/<Alert> should not be at or above pending` / `... at or above info` | Monitor test | Over the whole run, the alert must not reach that state for longer than the historical allowance (`maxAllowed`). Optional `in ns/<namespace>` suffix scopes it |
| `[sig-trt][invariant] No alerts without an explicit test should be firing/pending more than historically` | Monitor test | Catch-all for alerts that have no dedicated invariant test; compares against historical data (`result=reject`) |

The bracketed prefix on invariant tests (`[bz-etcd]`, `[Networking]`, `[Routing]`,
`[Machine Config Operator]`, …) is the **owning component** — use it for routing and for the
Jira component. `[Unknown]` means no owner is mapped for that namespace; derive the owner from
the alert's namespace and labels instead.

**Check blocking vs flake first.** Invariant alert tests are frequently recorded as a
same-name fail+pass pair in `e2e-monitor-tests__*.xml` — that is a flake and did not fail the
job (see [flaky-test-identification.md](flaky-test-identification.md#pass--fail--skip--flake)).
Only failures listed under `Blocking test failures:` in the e2e step `build-log.txt`, or in
`test-failures-summary_*.json`, failed the job.

---

## Step 1 — Name the alert

**Early test.** The failure text starts with a very long `ALERTS{alertname!~"Watchdog|...` regex
— that is the allow-list, not the answer. The culprit is in the JSON **after** the regex:

```bash
# alertname/namespace/labels of the alerts that matched. Use the e2e step's build-log.txt:
# in junit_e2e__*.xml the same JSON is entity-escaped (&#34;) and plain grep misses it.
grep -A40 '"__name__": "ALERTS"' openshift-e2e-test/build-log.txt \
  | grep -E '"(alertname|namespace|job_name|pod|severity)"' | sort | uniq -c
```

**Invariant tests.** The failure text names the alert, state durations, and the allowance,
followed by one interval line per alert instance with its labels:

```text
etcdGRPCRequestsSlow was at or above pending for at least 10m54s on ... (maxAllowed=0s): pending for 10m54s, firing for 0s:
Oct 09 03:54:34.791 - 568s  I namespace/openshift-etcd ... alert/etcdGRPCRequestsSlow alertstate/pending severity/critical ALERTS{...}
```

**Whole-run view.** `openshift-e2e-test/artifacts/junit/alerts_*.json` lists every alert
that fired during the run with `Name`, `Namespace`, `Level`, and `Duration`. Alerts expected
for the job's configuration (e.g. `TechPreviewNoUpgrade` on techpreview jobs,
`AlertmanagerReceiversNotConfigured`) are noise; focus on the ones named in the failure.

## Step 2 — Pin when it fired

Alert intervals are in the timeline files with `"source": "Alert"` and the alert name in
`locator.keys.alert`; `from`/`to` bound the firing or pending window:

```bash
jq -c '.items[] | select(.source=="Alert" and .locator.keys.alert=="KubeJobFailed")
       | {from, to, ns: .locator.keys.namespace, state: .message.annotations.alertstate}' \
  e2e-timelines_everything_*.json
```

The `_everything_` file can be tens of MB; the per-area files
(`e2e-timelines_openshift-monitoring_*`, `_kube-apiserver_*`, …) are smaller but do not all
carry alert intervals. Compare the window to the test phases:

- **Starts before the e2e suite** (before the first `E2ETest` interval) → the problem began
  during install or cluster settling. The Early test catches exactly this.
- **Starts during the suite** → correlate with the tests running at that time and with
  disruption, node, and operator events in the same window.
- **Starts during an upgrade window** → route to [upgrade.md](upgrade.md).

## Step 3 — Find why it fired

The alert's labels point at the object to inspect. Common cases:

| Alert | Labels to read | Where to look |
|-------|----------------|---------------|
| `KubeJobFailed` | `namespace`, `job_name` | Pod logs for that Job in `gather-extra/artifacts/pods/<namespace>/` and its events in `oc_cmds/events` |
| `KubePodNotReady`, `KubePodCrashLooping`, `KubeDeploymentReplicasMismatch` | `namespace`, `pod` | The pod's `previous.log` / `current.log` and container status — continue with [test-failure.md](test-failure.md#step-5--trace-crash-looping--failing-containers-to-the-originating-error) |
| `etcd*` (`etcdGRPCRequestsSlow`, `etcdHighFsyncDurations`, `etcdMembersDown`) | `pod`, `instance` | etcd pod logs, disk/CPU pressure → [resource-exhaustion.md](resource-exhaustion.md) |
| `KubeAPIErrorBudgetBurn`, API availability alerts | — | [disruption.md](disruption.md) |
| `ClusterOperatorDown` / `ClusterOperatorDegraded` | `name` | `junit_install_status.xml`, `oc_cmds/clusteroperators`, then that operator's pod logs |
| `KubePersistentVolumeErrors` | `persistentvolume`, `phase` | `oc_cmds/persistentvolumes`, `oc_cmds/events` (`ProvisioningFailed`) |

Short-lived `KubePodNotReady` pending intervals on test- or gather-created pods (for example
`*-debug-*` pods or `openshift-must-gather-*` namespaces) are usually test churn, not a
product defect — confirm against the Sippy pass rate before chasing them.

## Step 4 — Decide whether it is new

An alert that fires on most runs of this job is a known issue; one that started recently is a
regression. Check the alert test's pass rate in Sippy with `ci:fetch-test-report` (exact test
name, same release) and compare with sibling jobs. Then classify with the three-way split in
[flaky-test-identification.md](flaky-test-identification.md).

## Root-cause synthesis

A complete alert analysis states:

1. **Alert and state** — name, namespace, the state that tripped the test, and the duration
   versus `maxAllowed`.
2. **Window** — when it started relative to install, the e2e suite, and any upgrade.
3. **Source object and error** — the pod/Job/operator its labels point at, and that object's
   own originating error (not "the alert fired").
4. **Owner** — from the invariant test's bracketed prefix or the alert's namespace.
5. **Verdict** — blocking vs flake, and known vs new.

## See Also

- [flaky-test-identification.md](flaky-test-identification.md) — fail+pass flake pairs, Sippy
  baselines, infra vs flake vs regression
- [test-failure.md](test-failure.md) — tracing a failing pod to its originating error
- [disruption.md](disruption.md) — interval files and API availability alerts
- [resource-exhaustion.md](resource-exhaustion.md) — etcd, node pressure, and OOM alerts
- [artifacts.md](artifacts.md) — `alerts_*.json`, timeline files, and gather-extra paths
