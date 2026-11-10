# Timeline Analysis (Steps 3 and 5)

## 3.1: Triage All Runs with Summary Mode

**For multi-run analysis, always start with `--format summary`** to triage all runs before
deep-diving. This prevents large JSON output from consuming context:

`{backend_filter}` is the exact comma-separated backend list from the Grafana URL or
`--backends` (for example `kube-api-new-connections,pod-to-host-new-connections`).
The parser matches those names exactly. A shortened name such as `kube-api` matches
only `kube-api-new-connections` and `kube-api-reused-connections`, not
`kube-api-http2-localhost-new-connections` or other derived probes. Derived probes
still appear in blast-radius output so they can be discussed as context.

```bash
for build_id in {build_id_1} {build_id_2} {build_id_3}; do
  python3 "${CLAUDE_SKILL_DIR}/parse_disruption.py" \
    .work/disruption-analysis/{date}/${build_id}/logs/e2e-timelines_spyglass_*.json \
    --build-id ${build_id} --backends {backend_filter} --format summary
done
```

Example summary output:
```text
2084831773824389120: 11 disruptions | 4 episodes in 1 wave, ~6.2m apart | host-to-host:8 cache-host-to-host:3 | OVS:12 (max 9000ms) | etcd:5 | CPU: master-0 | src-node: abc12 | phase: upgrade:11
2084701838124257280: 3 disruptions | 1 episode | kube-api:3 | net-liveness: degraded | phase: conformance:3
2119804233229275136: 24 disruptions | 3 episodes in 1 wave, ~3.5m apart | openshift-api-http2-localhost:12 kube-api-http1-localhost:6 kube-api-http2-localhost:6 | etcd:4 | phase: upgrade:24 | rollouts: etcd 8->9 (w1 2/3), KAS 10->11 (w1 3/3), +2 without disruption | payload: 5.1.0-0.nightly-2026-11-08-173648 -> 5.1.0-0.nightly-2026-11-09-143447
2119937168964063232: 48 disruptions | 6 episodes in 2 waves (3+3), wave gap 12m (starts 19m apart) | openshift-api-http2-localhost:24 kube-api-http1-localhost:12 kube-api-http2-localhost:12 | etcd:1 | phase: upgrade:48 | rollouts: KAS 8->9 (w1 3/3), KAS 9->10 (w2 3/3), +2 without disruption | payload: rc_payload__5.1.0-0.ci-2026-11-09-112923 -> rc_payload__5.1.0-0.ci-2026-11-09-232923
2084417286357127168: 0 disruptions
```

Compare runs by **episodes and waves**, not by the disruption count. The count adds up
every interval on every selected backend, so six probes failing together in one outage
count six times. In the last two lines, 24 and 48 disruptions are really 3 outages in one
kube-apiserver rollout against 6 outages in two rollouts. How to read each field is in 3.4.

Use the summary output to identify which runs need deep investigation (highest disruption,
interesting signal combinations, or unusual patterns). If the auto-selection included a
clean comparison run (0s disruption from the same job as a disrupted run), note which
disrupted run it pairs with — you will use this pair in Step 6.3 to filter out red herrings.

## 3.2: Get Blast Radius for Each Run

To see which other backends were disrupted during the same time window (for the "Other Disrupted
Backends" report section), use `--blast-radius` with `--format summary`:

```bash
python3 "${CLAUDE_SKILL_DIR}/parse_disruption.py" \
  .work/disruption-analysis/{date}/{build_id}/logs/e2e-timelines_spyglass_*.json \
  --backends {backend_filter} --blast-radius --format summary
```

This appends a compact list of all disrupted backends (not just the filtered ones) with counts
to the summary output, without full event details.

## 3.3: Deep-Dive Selected Runs

For runs that need detailed investigation, use `--format text` or `--format json`:

```bash
python3 "${CLAUDE_SKILL_DIR}/parse_disruption.py" \
  .work/disruption-analysis/{date}/{build_id}/logs/e2e-timelines_spyglass_*.json \
  --backends {backend_filter} \
  --window 60 \
  --format text
```

Use `--format json` when you need structured data for programmatic analysis. Only use JSON for
runs that need deep investigation — the output can be 30KB+ per run and will consume context.

Omit `--backends` to analyze all disrupted backends.

The parser automatically:
- Extracts all disruption events (Error/Warning level)
- Classifies each backend (cache, non-cache, canary, cloud)
- Detects which **phase** each disruption occurred in (upgrade vs conformance) — the first
  timeline file (sorted by filename) is the upgrade phase, the second is the conformance/e2e
  test phase. The phase is reported in the summary (`phase_breakdown`) and on each disruption event.
- Detects source-node fan-out patterns (critical for host-to-host analysis)
- Extracts concurrent events within the disruption window (±`--window` seconds), including
  E2E test names active during disruption (for cross-run test correlation)
- Summarizes OVS vswitchd stalls, CPU pressure, Azure disk metrics, etcd pressure
- Assesses network-liveness status (clean, minor, degraded, unreliable)
- Groups the selected backends' intervals into **episodes** and **waves** (`episodes` in
  JSON, `Disruption episodes` in text)
- Extracts **static-pod revision rollouts** for kube-apiserver, etcd,
  kube-controller-manager, and kube-scheduler, and says which episodes and waves fall
  inside each (`revision_rollouts` in JSON)
- Reports the run's **payload pair** (`payloads` in JSON): initial and target payload
  from the `prowjob.json` saved beside the timelines (or `--prowjob`), falling back to
  `../gather/clusterversion.json`; `timeline_target_version` is the target the timeline's
  ClusterVersion "Working towards" message names

If the parser output is insufficient for a particular signal, query the timeline JSON directly.

## 3.4: Signal Interpretation Reference

The parser extracts and summarizes all of the following. Use this reference to interpret
the output — you should not need to query the timeline files directly for most analyses.

**Backend classification:**
1. **Cache backends** — name contains `cache` → likely **etcd or global networking** problem
2. **Non-cache backends** — standard backends → likely **component or cluster networking** problem
3. **ci-cluster-network-liveness** — canary polling external endpoint → **test infra network** issues
4. **Cloud network-liveness backends** — cloud provider canaries → **cloud provider** issues

**Key diagnostic pattern**: When all 4 variants of a backend fail simultaneously (e.g.,
`openshift-api-new-connections`, `openshift-api-reused-connections`, `cache-openshift-api-new-connections`,
`cache-openshift-api-reused-connections`), the root cause is almost always **control plane node
resource exhaustion** (disk I/O → etcd stalls → apiserver timeouts), not a networking issue.
Look for etcd `slow fdatasync`, `apply took too long`, and `ExtremelyHighIndividualControlPlaneCPU`
alerts as confirming evidence.

**Episodes and waves:**
- An **episode** is one outage across the selected backends: intervals that overlap or start
  within 30s of the previous one's end (`episode_gap_seconds`). JSON has `from`, `to`,
  `duration_seconds`, `backends`, `interval_count`, and `phases` per episode.
- A **wave** is a run of episodes with no large idle gap. A new wave starts where the idle
  time between two episodes is more than twice the typical idle time, clamped to 5–10
  minutes (`wave_split_threshold_seconds`). JSON has `episode_indices`,
  `median_spacing_seconds`, `gap_before_seconds` (idle time since the previous wave), and
  `start_spacing_before_seconds` per wave. The summary's "wave gap 12m (starts 20m apart)"
  shows those two numbers.
- **Three episodes about 3 minutes apart** in one wave is the shape of one static-pod rollout
  taking each master's local apiserver down in turn. That is the normal baseline for
  `*-localhost-*` probes on upgrade jobs. **Two such waves** means two rollouts.

**Static-pod revision rollouts (`rollouts:`):**
- Each entry is `{operator} {from}->{to}` from the OperatorState
  `NodeInstallerProgressing: N nodes are at revision X; M nodes have achieved new revision Y`
  interval, from when Progressing went True until it went False. `KAS` is kube-apiserver,
  `KCM` kube-controller-manager, `sched` kube-scheduler.
- `(w2 3/3)` means 3 of the 3 episodes in wave 2 fall inside that rollout (±15s).
  `+N without disruption` counts rollouts that contain no episode. JSON
  `revision_rollouts[].episode_indices` and `waves` carry the same data, and text output
  lists every rollout with its time range.
- A gap in revision numbers (`KAS 6->7`, then `KAS 8->9`) means revision 8 was created and
  superseded before it rolled out.
- The parser adds a key signal when a run has more than one kube-apiserver rollout.
- **When a wave sits inside a rollout that a comparison run does not have** (for example
  two KAS rollouts after a change and one before), the disruption is explained by the extra
  rollout, and the question becomes what triggered it. Go to Step 4 and follow
  **4.3 Revision Trigger** and then **4.4 Payload Diff** in `references/artifacts.md`.
  Check both runs' payload pairs first: an extra rollout on upgrade often depends on the
  payload the run started from, not only the one it upgraded to.

**Source-node patterns:**
- **single-source-fan-out**: All disruptions from one node → source-side issue (OVS stall,
  CPU starvation, disk I/O). Focus investigation on that node.
- **multi-source**: Disruptions from multiple nodes → network-wide or destination-side issue.
- **unknown**: Backend doesn't include node info (e.g., ingress-routed backends).

**Concurrent event signals:**

| Source | What it tells you |
|--------|-------------------|
| `OVSVswitchdLog` | OVS packet processing stalls (>1000ms = networking frozen) |
| `CPUMonitor` | Nodes with CPU >95% (starves OVS and system processes) |
| `CloudMetrics` | Azure disk IOPS saturation, queue depth (disk I/O pressure) |
| `EtcdLog` | apply took too long, slow fdatasync, ReadIndex delays |
| `EtcdDiskCommitDuration` | etcd disk commit above 25ms threshold |
| `AuditLog` | API request failures or gaps during disruption |
| `Alert` | Firing alerts (ExtremelyHighIndividualControlPlaneCPU, etc.) |
| `E2ETest` | Tests active during disruption (with test names for cross-run correlation) |
| `NodeMonitor` / `MachineMonitor` | Node NotReady, machine phase changes |
| `ClusterVersion` / `ClusterOperator` | Upgrade progress, operator status |

**E2E test correlation (multi-run):** The parser includes test names from `E2ETest` events.
Tests appearing during disruption in 3+ runs are especially interesting — they may trigger
the resource pressure causing disruption. Tests that *fail* during disruption are usually
*victims*; tests that *pass* consistently during disruption windows are more likely causes.

## 5: Additional Diagnostic Checks

Do these when disruption coincides with node events.

### 5.1: Node Shutdown Sequencing

If disruption coincides with node events, check:

- Did the poller go `readyz=false` as expected when the node was shutting down?
- Were endpoint slices updated accordingly?
- Did the test framework watcher see the endpoint was removed and stop disruption polling?

Look for these signals in interval files and node-related logs.

### 5.2: Endpoint Slice Updates

Check audit logs for endpoint slice modification events during disruption windows:

- Look for audit events related to `endpointslices` resources
- Verify that readiness changes triggered appropriate endpoint updates
