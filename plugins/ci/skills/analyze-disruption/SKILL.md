---
name: analyze-disruption
description: Analyze and compare disruption across one or more Prow CI job runs by examining interval data, audit logs, pod logs, and CPU metrics
---

# Analyze Disruption

This skill analyzes disruption events recorded in Prow CI job runs. It downloads interval/timeline data,
audit logs, and pod logs, then correlates disruption across backends and job runs to identify root causes.

## Prerequisites

1. **gcloud CLI Installation**
   - Check if installed: `which gcloud`
   - The `test-platform-results` bucket is publicly accessible — no authentication required

2. **Python 3** (3.7 or later)

## Input Format

The user will provide:

1. **One or more Prow job URLs** (required, at least 1)
   - Example: `https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.21-e2e-aws-ovn/1983307151598161920`

2. **`--backends` flag** (optional) — comma-separated list of backend names to focus on
   - Example: `--backends kube-api,oauth-api,openshift-api`
   - If omitted, analyze all backends that show disruption

3. **`--skip-jira` flag** (optional) — skip the Jira search for known disruption cards
   - By default, the skill searches TRT and OCPBUGS for existing disruption cards after analysis

## Implementation Steps

### Step 1: Parse and Validate Input

1. **Extract job URLs and flags**
   - Parse all positional arguments as Prow job URLs
   - Parse `--backends` flag if present, split on comma to get backend filter list
   - Parse `--skip-jira` flag as a boolean option (default: false)
   - Validate at least one URL is provided

2. **Parse each URL** to extract bucket path, job name, and build ID
   - Use the same URL parsing logic as the "prow-job-analysis" skill
   - Accept both `prow.ci.openshift.org` and `gcsweb-ci` URL formats
   - Extract `build_id` and `job_name` from each URL

3. **Construct deep links** for each job run — these go **inline throughout the report**
   wherever the run or a specific artifact is referenced, not in a separate table:

   **Run-level links** (use when first mentioning a run):
   - **Prow job page**: `https://prow.ci.openshift.org/view/gs/test-platform-results/logs/{job_name}/{build_id}`
   - **Sippy intervals**: `https://sippy.dptools.openshift.org/sippy-ng/job_runs/{build_id}/{job_name}/intervals`

   **GCS artifact deep links** (use when citing specific evidence):
   - Base: `https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/{job_name}/{build_id}/artifacts/`
   - Timeline file: `{gcs_base}{target}/openshift-e2e-test/artifacts/junit/e2e-timelines_spyglass_{timestamp}.json`
   - Audit logs dir: `{gcs_base}{target}/gather-extra/artifacts/audit_logs/`
   - etcd pod logs: `{gcs_base}{target}/gather-extra/artifacts/pods/openshift-etcd/`
   - Journal logs: `{gcs_base}{target}/gather-extra/artifacts/journal_logs/`
   - Must-gather: `{gcs_base}{target}/gather-extra/artifacts/must-gather/`

   Where `{target}` is the ci-operator target extracted from prowjob.json (e.g., `e2e-azure-ovn-upgrade`).

   **Inline linking style**: When discussing evidence, link directly to the artifact.
   For example: "Run 1 ([Prow][prow1] | [Intervals][int1]) showed 11 disruptions in
   the [timeline data][timeline1]..." — where `[timeline1]` links to the specific
   `e2e-timelines_spyglass_*.json` file on gcsweb.

### Step 2: Create Working Directories

Compute `{date}` as today's date in `YYYY-MM-DD` format (e.g., `2026-03-23`).

For each job run:

```bash
mkdir -p .work/disruption-analysis/{date}/{build_id}/logs
mkdir -p .work/disruption-analysis/{date}/{build_id}/tmp
```

Check for existing artifacts first. If `.work/disruption-analysis/{date}/{build_id}/logs/` exists with content,
ask user whether to reuse or re-download.

### Step 3: Download prowjob.json for Each Run

Use the `fetch-prowjob-json` skill for each job run URL.

1. Save to `.work/disruption-analysis/{date}/{build_id}/logs/prowjob.json`
2. Extract `JOB_NAME` from `.spec.job`
3. Extract the `--target=` value from ci-operator args

### Step 4: Download and Analyze Interval/Timeline Data

For each job run:

#### 4.1: Find and Download Interval Files

**Important GCS bucket note**: Prow URLs may contain `origin-ci-test` in the path (e.g.,
`/view/gs/origin-ci-test/logs/...`), but the actual GCS bucket is always `test-platform-results`.
Always use `gs://test-platform-results/...` for `gcloud storage` commands.

**Recommended approach — use `gcloud storage ls` then download individually**:

The artifact search script and wildcard `gcloud storage cp` are unreliable for finding timeline
files, especially in upgrade jobs where files are nested under multiple workflow step directories.
Instead, list files first, then download each one:

```bash
# Step 1: List all timeline files in the job's artifact tree
gcloud storage ls "gs://test-platform-results/logs/{job_name}/{build_id}/artifacts/**/e2e-timelines_spyglass_*.json"
```

This returns the full GCS paths for each timeline file. Then download each one individually:

```bash
# Step 2: Download each file
gcloud storage cp "gs://test-platform-results/logs/{job_name}/{build_id}/artifacts/{target}/openshift-e2e-test/artifacts/junit/e2e-timelines_spyglass_{timestamp}.json" \
  .work/disruption-analysis/{date}/{build_id}/logs/ --no-user-output-enabled
```

**Timeline file locations vary by job type**:

- **Non-upgrade jobs**: Usually one timeline file at
  `artifacts/{target}/openshift-e2e-test/artifacts/junit/e2e-timelines_spyglass_{timestamp}.json`

- **Upgrade jobs**: Usually two timeline files (one per phase — upgrade and conformance), which
  may be under different workflow step directories. The `gcloud storage ls` approach handles this
  automatically.

**Fallback — artifact search script**:

If `gcloud storage ls` doesn't find files, try the artifact search script:

```bash
python3 plugins/ci/skills/prow-job-analysis/prow_job_artifact_search.py \
  <prow-url> search "**/e2e-timelines_spyglass_*.json"
```

Note: The GCS URIs returned by this script may not always be directly downloadable with
`gcloud storage cp`. If downloads fail, extract the path components and construct the
`gs://test-platform-results/...` URI manually, or use `gcloud storage ls` to verify the
actual file locations.

#### 4.2: Run the Disruption Parser

Use the included `parse_disruption.py` script to extract and classify disruption events:

```bash
python3 plugins/ci/skills/analyze-disruption/parse_disruption.py \
  .work/disruption-analysis/{date}/{build_id}/logs/e2e-timelines_spyglass_*.json \
  --backends {backend_filter} \
  --window 60 \
  --format text
```

Use `--format json` when you need structured data for further analysis. Omit `--backends` to
analyze all disrupted backends.

The script automatically:
- Extracts all disruption events (Error/Warning level)
- Classifies each backend (cache, non-cache, canary, cloud)
- Detects which **phase** each disruption occurred in (upgrade vs conformance) — the first
  timeline file (sorted by filename) is the upgrade phase, the second is the conformance/e2e
  test phase. The phase is reported in the summary (`phase_breakdown`) and on each disruption event.
- Detects source-node fan-out patterns (critical for host-to-host analysis)
- Extracts concurrent events within the disruption window (±`--window` seconds)
- Summarizes OVS vswitchd stalls, CPU pressure, Azure disk metrics, etcd pressure
- Assesses network-liveness status (clean, minor, degraded, unreliable)

Review the parser output and use it as the foundation for the analysis. The parser handles
Steps 4.2 through 4.6 below.

#### 4.3: Interval File JSON Structure Reference

Each item in the timeline JSON has this structure:

```json
{
  "level": "Error",
  "source": "Disruption",
  "locator": {
    "type": "Disruption",
    "keys": {
      "backend-disruption-name": "host-to-host-new-connections",
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

Key fields:
- **`source`**: Event category. `"Disruption"` for disruption events. Other useful sources:
  `OVSVswitchdLog`, `CPUMonitor`, `CloudMetrics`, `EtcdLog`, `EtcdDiskCommitDuration`,
  `EtcdDiskWalFsyncDuration`, `AuditLog`, `Alert`, `NodeMonitor`, `MachineMonitor`,
  `ClusterVersion`, `ClusterOperator`, `E2ETest`, `KubeletLog`
- **`level`**: `"Error"`, `"Warning"`, `"Info"`. Disruption events are Error or Warning.
- **`locator.keys.backend-disruption-name`**: The backend being monitored
- **`locator.keys.disruption`**: For host-to-host backends, encodes source node, target node,
  and endpoint IP in the format `host-to-host-from-node-{src}-to-node-{dst}-endpoint-{ip}`
- **`locator.keys.connection`**: `"new"` or `"reused"`
- **`message.reason`**: `"DisruptionBegan"` or `"DisruptionEnded"`
- **`message.humanMessage`**: Human-readable description with error details

#### 4.4: Classify Disruption by Backend Type

The parser classifies backends automatically. For reference:

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

#### 4.5: Source-Node Analysis

The parser detects source-node patterns automatically. Key patterns:

- **single-source-fan-out**: All disruptions from one node to many targets. Indicates a
  source-side issue (OVS stall, CPU starvation, disk I/O) — not a network-wide problem.
- **multi-source**: Disruptions from multiple source nodes. Suggests a network-wide,
  destination-side, or infrastructure-level issue.
- **unknown**: Backend type doesn't include node info in the disruption path (e.g.,
  ingress-routed backends like image-registry).

When a single-source-fan-out pattern is detected, focus the investigation on that specific
node: check its CPU, disk I/O, OVS vswitchd logs, and whether it was running heavy workloads.

#### 4.6: Identify Concurrent Cluster Activity

The parser extracts concurrent events from these sources within the disruption window:

| Source | What it tells you |
|--------|-------------------|
| `OVSVswitchdLog` | OVS packet processing stalls (poll intervals >500ms = networking frozen) |
| `CPUMonitor` | Nodes with CPU >95% (starves OVS and other system processes) |
| `CloudMetrics` | Azure disk IOPS saturation, queue depth, bandwidth (disk I/O pressure) |
| `EtcdLog` | apply took too long, slow fdatasync, ReadIndex delays |
| `EtcdDiskCommitDuration` | etcd disk commit above 25ms threshold |
| `EtcdDiskWalFsyncDuration` | etcd WAL fsync above 10ms threshold |
| `AuditLog` | API request failures during disruption |
| `Alert` | Firing Prometheus alerts (ExtremelyHighIndividualControlPlaneCPU, etc.) |
| `NodeMonitor` / `MachineMonitor` | Node NotReady, machine phase changes |
| `ClusterVersion` / `ClusterOperator` | Upgrade progress, operator status |
| `E2ETest` | Active test phase (upgrade vs post-upgrade e2e tests) |

If the parser output is insufficient for a particular signal, you can query the timeline
JSON directly for deeper investigation.

### Step 5: Review Key Signals from Parser Output

The parser output from Step 4.2 already includes audit log events, etcd events, CPU warnings,
OVS stalls, and cloud metrics extracted from the timeline files. For most analyses, this is
sufficient — the timeline files aggregate the same data that would be found in separate
artifact downloads.

Review the parser's `concurrent_events` and `key_signals` sections and assess:

#### 5.1: Audit Log Signals

The timeline files contain `AuditLog` entries showing request failures during disruption windows
(e.g., "1 requests made during this time failed out of 611 total").

For kube-api, oauth-api, and openshift-api disruption, check whether:
- **Audit entries show failures during disruption** → API server received requests but couldn't process them (internal issue)
- **No audit entries during disruption** → requests never reached the API server (connectivity issue)

#### 5.2: etcd Signals

The timeline files contain `EtcdLog`, `EtcdDiskCommitDuration`, and `EtcdDiskWalFsyncDuration` entries.
Key messages to look for:
- `"apply request took too long"` — etcd under write pressure
- `"slow fdatasync"` — disk I/O bottleneck
- `"waiting for ReadIndex response took too long"` — etcd read latency
- Commit duration above 25ms or WAL fsync above 10ms thresholds

#### 5.3: CPU and Resource Pressure

The timeline files contain `CPUMonitor` (>95% threshold) and `CloudMetrics` (Azure disk IOPS,
queue depth, bandwidth, latency) entries.

Key patterns:
- **CPU >95% on the disruption source node** → OVS/networking starvation
- **Azure disk IOPS at 100%** → disk I/O saturation cascading to CPU and etcd
- **Disk queue depth >10x threshold** → severe I/O contention

#### 5.4: OVS vswitchd Stalls

`OVSVswitchdLog` entries report "Unreasonably long poll interval" warnings when OVS cannot
process packets. Poll intervals >1000ms mean OVS was essentially frozen — no packets forwarded.
This is the most direct cause of host-to-host and pod-to-host disruption.

#### 5.5: E2E Test Correlation

Query the timeline files for `E2ETest` source items that overlap the disruption window. The test
name is in `locator.keys.e2e-test`. For each test active during disruption, note:
- Test name, start time, end time
- Whether it passed (`level: "Info"`) or failed (`level: "Error"`)

**For multi-run analysis**: Cross-reference tests active during disruption across runs. Tests
appearing in 3+ runs during the disruption window are especially interesting — they may be
triggering the resource pressure that causes disruption (e.g., tests that create many resources,
run heavy workloads, or cause pod evictions). Include a table of correlated tests in the report
with pass/fail status per run.

Note: Tests that *fail* during the disruption window are usually *victims* of the disruption,
not causes. Tests that *pass* but consistently appear during disruption across runs are more
likely to be contributing to the resource pressure that triggers it.

#### 5.6: Root-Cause Attribution Rules (learned from real triage incidents)

Apply these before naming an owning component in the report — disruption is almost always a
*symptom chain*, and attributing it one link too early has misdirected owning teams for weeks
in real incidents:

1. **A component whose error names a missing upstream dependency is a victim, not an owner —
   but corroborate before reassigning.** If a disrupted backend's serving pods log
   "cannot list/watch/reach X" (e.g., a router crash-looping on
   `failed to list *v1.Route: the server could not find the requested resource`), check X's
   provider directly (ClusterOperator conditions, APIService availability, endpoints) before
   blaming either side: provider unhealthy → the disruption belongs upstream (in one real case,
   router disruption traced through openshift-apiserver to etcd never deploying its static
   pods); provider healthy → the fault is inside the "victim" after all (RBAC — a real
   crash-looper failed on `configmaps is forbidden` — client config, or network reachability).
2. **The end-state oracle is `clusteroperators.json`, not pod existence.** Check the etcd and
   apiserver ClusterOperator conditions from gather-extra before declaring the control plane
   healthy — pods scheduled and Running prove nothing about whether cluster etcd/apiservers
   were actually serving (during bootstrap and some upgrade windows, a different control plane
   serves the API).
3. **Extract condition *messages*, not just condition flips.** `ClusterVersion` and
   `ClusterOperator` interval entries carry the underlying controller error string — a bare
   "Available=False" interval hides the cause, but its message often names it outright (a real
   ClusterVersion flap's message named the exact broken controller). Quote the recovered
   message in the report.
4. **Read `*_previous.log` for any container that restarted during the disruption window.**
   The crashed instance's last lines are primary evidence and outrank inferences from the
   replacement container's healthy logs; a container with `restartCount > 0` whose previous
   log you did not read is an analysis gap.
5. **Condition churn ≠ slow rollout.** If an operator's condition flaps continuously (many
   transitions with `DurationSinceTransition` of ~1s), that is a sync-loop bug (permafail
   class), not a transient — count transitions before classifying severity.

### Step 6: Deep-Dive Artifact Download (Optional)

**Only perform this step if the parser output from Step 4.2 is insufficient for root cause
determination** — for example, when you need to see the full audit log request details or
etcd log context beyond what the timeline summaries provide.

#### 6.1: Download Audit Logs (if needed)

```bash
gcloud storage cp -r "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/audit_logs/" \
  .work/disruption-analysis/{date}/{build_id}/logs/audit_logs/ --no-user-output-enabled 2>/dev/null || true
```

Query for sampler requests during disruption windows to identify request gaps.

#### 6.2: Download etcd Pod Logs (if needed)

```bash
gcloud storage cp -r "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/pods/openshift-etcd/" \
  .work/disruption-analysis/{date}/{build_id}/logs/etcd-pods/ --no-user-output-enabled 2>/dev/null || true
```

Search for leader changes, write delays, member issues, and disk problems.

#### 6.3: PromQL Queries for Manual Investigation

If the analysis needs live cluster metrics (not available in artifacts), provide these queries:

```promql
-- Top CPU consumers across all nodes
topk(25, sum by (namespace) (rate(container_cpu_usage_seconds_total{container!="",pod!=""}[5m])))

-- CPU on a specific node
topk(25, sum by (namespace) (rate(container_cpu_usage_seconds_total{container!="",pod!="",node="<node-name>"}[5m])))

-- E2E test CPU on a specific node
topk(10, sum by (namespace) (rate(container_cpu_usage_seconds_total{container!="",pod!="",node="<node-name>",namespace=~"^e2e-.*"}[5m])))
```

### Step 7: Additional Diagnostic Checks

#### 7.1: Node Shutdown Sequencing

If disruption coincides with node events, check:

- Did the poller go `readyz=false` as expected when the node was shutting down?
- Were endpoint slices updated accordingly?
- Did the test framework watcher see the endpoint was removed and stop disruption polling?

Look for these signals in interval files and node-related logs.

#### 7.2: Endpoint Slice Updates

Check audit logs for endpoint slice modification events during disruption windows:

- Look for audit events related to `endpointslices` resources
- Verify that readiness changes triggered appropriate endpoint updates

#### 7.3: Onset Determination and Suspect PRs (when disruption is new or worsening)

If the disruption pattern is a *change* (a backend that used to be clean now disrupts, or
counts jumped), anchor the onset before hypothesizing:

1. Find the newest **clean** run and the oldest **disrupted** run of the same job (job-history)
   and compare their payloads (`artifacts/release/artifacts/release-images-latest`, and
   `release-images-initial` for upgrade jobs — upgrade jobs can regress via either endpoint,
   and a *skew* between initial and target payloads is itself a known failure mode).
2. Feed the failing payload to the `fetch-new-prs-in-payload` skill and vet candidates with
   `gh` — a LIKELY PR names the owning component.
3. **Scan the owning repo's newest merges for revert PRs**: a fresh `Revert "..."` title citing
   a TRT/OCPBUGS key hands you the trigger PR, the tracking ticket, and the expected recovery
   in one query — for currently-live breakage this is frequently faster than any artifact
   analysis.
4. Never write "resolved/appeared due to an unidentified payload change" without having run
   steps 1–3; a real duplicate bug was filed because a cessation was written off as
   unidentified while the owning repo had merged an `OCPBUGS-*`-titled fix at exactly that
   boundary.

#### 7.4: Existing Bugs and Known Disruption Families

Before presenting a root-cause hypothesis as novel, check whether it is already tracked:

1. Query `fetch-related-triages` for any Component Readiness regression associated with the
   disrupted backends' tests, and treat confidence scores as clustering hints — verify against
   this run's evidence before adopting a match.
2. Run a **component-scoped JIRA listing** for the suspected owner
   (`project = OCPBUGS AND component = "<owner>" AND created >= -21d`) and read summaries —
   owning teams describe defects in developer vocabulary that shares no keywords with the
   disruption symptom, so text search alone misses existing bugs.
3. Known recurring disruption families worth ruling in/out first: etcd slow-fdatasync /
   disk-pressure on Azure control planes (cache-backend disruption), CNI gaps during OVN
   upgrades (host-to-host + API disruption in the upgrade phase), single-node OVS stalls under
   CPU starvation (single-source fan-out), and cloud LB/DNS churn (ingress-routed backends
   only). Each has had tracking tickets — search before filing.

### Step 8: Cross-Run Comparison (Multiple Runs Only)

When multiple job run URLs are provided:

#### 8.1: Align Disruption Events

For each backend that shows disruption across multiple runs:

- Compare which backends are disrupted in each run
- Identify backends that are **consistently disrupted** across all runs (systemic issue)
- Identify backends that are **disrupted in only some runs** (intermittent or infrastructure-specific)

#### 8.2: Pattern Detection

Look for common patterns:

- **Same backends disrupted at similar relative times** → likely a product bug or test sequencing issue
- **Same backends but different times** → likely infrastructure-sensitive but product-related
- **Different backends across runs** → likely infrastructure/environment-specific
- **ci-cluster-network-liveness disrupted in some runs** → those runs have unreliable disruption
  data. Still include them in the analysis, but note the caveat prominently (in the Runs Analyzed
  table and wherever citing evidence from that run). Do not exclude unreliable runs entirely —
  they can still confirm patterns seen in reliable runs, and their non-disruption signals (etcd
  logs, CPU, alerts) remain valid. The key is to avoid drawing conclusions *solely* from an
  unreliable run's disruption counts.
- **Cache backends consistently disrupted** → systemic etcd or networking issue
- **Non-cache backends consistently disrupted** → component-specific problem

#### 8.3: Correlate etcd and CPU Findings

- Are etcd leader changes present in all runs showing cache-backend disruption?
- Do runs with mass disruption consistently show high CPU or node pressure?
- Are audit log gaps consistent across runs?

### Step 9: Generate Report

Produce a structured Markdown report with **inline deep links** throughout. Links go where the
evidence is discussed, not in a separate section at the end. Use Markdown reference-style links
to keep the text readable.

### Inline Linking Rules

1. **First mention of a run** — include `([Prow]({prow_url}) | [Intervals]({sippy_url}))` after
   the build ID or run number
2. **Citing evidence from a specific artifact** — deep-link to the exact file on gcsweb, e.g.:
   - `[timeline data]({gcsweb_timeline_url})` when discussing disruption events
   - `[audit logs]({gcsweb_audit_url})` when discussing request gaps
   - `[etcd pod logs]({gcsweb_etcd_url})` when discussing etcd pressure
   - `[OVS vswitchd logs]({gcsweb_journal_url})` when discussing OVS stalls
3. **Tables listing runs** — include Prow and Intervals links in a column
4. **Do NOT create a separate "Artifacts" or "Links" table** — all links belong inline where
   the reader would want to click through to verify the evidence
5. **Do NOT truncate or abbreviate job names** — always use the full job name (e.g.,
   `periodic-ci-openshift-release-main-ci-4.22-e2e-azure-ovn-upgrade`, not `periodic-ci-...-e2e-azure-ovn-upgrade`)

### Report Structure

**For single run:**

```text
# Disruption Analysis

## Job Information
- **Prow Job**: [{job-name}]({prow_url})
- **Build ID**: {build_id}
- **Target**: {target}
- **Sippy Intervals**: [View intervals]({sippy_intervals_url})

## Disruption Summary
{Disruption count, backend classification, network-liveness assessment}

## Disruption Timeline
- **{from} — {to}** ({duration}s): {message}
  - Concurrent activity from [timeline]({gcsweb_timeline_url}): {events}
  - [Audit logs]({gcsweb_audit_url}): {gap analysis}

## Cluster Activity Correlation
{Reference specific artifacts inline, e.g.:}
The [timeline data]({gcsweb_timeline_url}) shows OVS vswitchd poll intervals up to 9s...
[etcd pod logs]({gcsweb_etcd_url}) confirm apply-too-long warnings at 03:56:00Z...

## Root Cause Hypothesis
{Analysis with inline links to supporting evidence. State the full causal chain (trigger →
intermediate symptoms → disrupted backends), the owning component with the corroboration
required by Step 5.6 (upstream health checked, condition messages quoted, previous.log read
for any restarted container), and whether the issue matches an existing bug/triage or known
disruption family (Step 7.4) — with the ticket reference if so.}

## Other Disrupted Backends
{When --backends filter was used, list other backends that were disrupted during the
same time window and due to the same root cause. This helps readers understand the full
blast radius — e.g., if openshift-api was requested but kube-api, oauth-api, and
metrics-api were also disrupted simultaneously, that confirms a control plane problem
rather than an openshift-api-specific issue. Only include backends whose disruption
overlaps the same window; exclude unrelated disruption at other times.}

## Known Disruption Issues
{Results from Step 10 Jira search, or "Jira search skipped (--skip-jira)"}
```

**For multiple runs — use the same inline linking pattern:**

```text
# Disruption Analysis: {backend_names}

## Runs Analyzed
| # | Build ID | Job | Disrupted Backends | Network Liveness |
|---|----------|-----|-------------------|------------------|
| 1 | {build_id_1} ([Prow]({prow_url}) \| [Intervals]({sippy_url})) | {job} | {backends} | {status} |
| 2 | {build_id_2} ([Prow]({prow_url}) \| [Intervals]({sippy_url})) | {job} | {backends} | {status} |

## Disruption Events
### Run 1 ({build_id_1})
Phase: {upgrade|conformance} — Disruption details with [timeline]({gcsweb_timeline_url}) links

## Cluster Activity Correlation
Run 1 [timeline]({gcsweb_timeline_url_1}) shows OVS stalls at 21:50:24Z...
Run 2 [timeline]({gcsweb_timeline_url_2}) shows disk IOPS at 100% ([cloud metrics]({gcsweb_timeline_url_2}))...

## Cross-Run Comparison
{Pattern analysis referencing specific runs with inline links}

## Root Cause Hypothesis
{Synthesis with links to key evidence. Apply the Step 5.6 attribution rules (victim-vs-owner
with upstream corroboration, quoted condition messages, previous.log for restarted containers)
and cite any existing bug/triage or known family match from Step 7.4.}

## Other Disrupted Backends
{When --backends filter was used, list other backends that were disrupted during the
same time window and due to the same root cause — not all disruption in the run, just
what overlaps the identified disruption event. Show a consolidated table with backend
name, type (cache/non-cache/cloud/canary), and how many runs (out of N) showed that
backend disrupted in the same window. Sort by runs-affected descending, then by count.
This reveals the full blast radius and helps confirm root cause — e.g., if every API
backend fails together, the problem is control-plane-wide, not backend-specific.}

## Known Disruption Issues
{Results from Step 10 Jira search, or "Jira search skipped (--skip-jira)"}
```

Save the report using a filename that references the backends being analyzed:

- **Single run**: `.work/disruption-analysis/{date}/{backend_names}-analysis.md`
- **Multiple runs**: `.work/disruption-analysis/{date}/{backend_names}-analysis.md`

Where `{backend_names}` is a kebab-case join of the disrupted backend base names (e.g.,
`image-registry-new-connections-analysis.md` or `kube-api-oauth-api-analysis.md`).
If all backends are analyzed (no `--backends` filter), use the backends that actually showed
disruption. If the resulting filename would be excessively long (more than 5 backends),
truncate to the first 5 and append `-and-more` (e.g., `kube-api-oauth-api-openshift-api-cache-oauth-api-cache-openshift-api-and-more-analysis.md`).

### Step 10: Known Disruption Issue Lookup

Skip this step if `--skip-jira` was passed. This step searches Jira for existing cards that
may already track the disruption pattern identified in the analysis, and offers to file a new
bug if none are found.

#### 10.1: Search for Known Disruption Cards

Extract the base backend names from the analysis (e.g., `openshift-api`, `kube-api`, `oauth-api`
— strip `cache-` prefix and `-new-connections`/`-reused-connections` suffixes to get the base name).

For each distinct base backend name, run two JQL queries using `searchJiraIssuesUsingJql`
(cloudId: `redhat.atlassian.net`):

**Query 1 — Labeled disruption cards (high confidence):**

```jql
project in (TRT, OCPBUGS) AND labels = "disruption" AND status != Closed AND text ~ "{backend_name}" ORDER BY updated DESC
```

**Query 2 — Broader search for open unlabeled cards:**

```jql
project in (TRT, OCPBUGS) AND status != Closed AND text ~ "disruption {backend_name}" ORDER BY updated DESC
```

**Query 3 — Closed labeled disruption cards (prior investigations):**

```jql
project in (TRT, OCPBUGS) AND labels = "disruption" AND status = Closed AND text ~ "{backend_name}" ORDER BY updated DESC
```

**Query 4 — Closed broader search:**

```jql
project in (TRT, OCPBUGS) AND status = Closed AND text ~ "disruption {backend_name}" ORDER BY updated DESC
```

Use `maxResults: 10` and `fields: ["summary", "status", "labels", "assignee", "updated", "priority", "resolution"]`
for each query. Deduplicate results across queries by issue key.

Separating open and closed queries ensures `maxResults` doesn't cause one category to crowd
out the other. Closed cards are valuable — they may have been closed prematurely, or they
document a prior investigation into the same disruption pattern that provides context for the
current occurrence (root cause, fix applied, affected versions).

#### 10.2: Present Results and Offer Actions

**If matching cards are found:**

Add a "Known Disruption Issues" section to the report. Group results into open and closed,
with open cards listed first (most actionable), then closed cards (useful for context):

```markdown
## Known Disruption Issues

### Open
| Key | Summary | Status | Labels | Assignee | Updated |
|-----|---------|--------|--------|----------|---------|
| [OCPBUGS-1234](url) | openshift-api disruption on AWS | In Progress | disruption | @engineer | 2026-07-28 |

### Previously Resolved
| Key | Summary | Resolution | Labels | Updated |
|-----|---------|------------|--------|---------|
| [OCPBUGS-999](url) | openshift-api disruption on Azure | Done - Errata | disruption | 2026-03-15 |
```

For each card missing the "disruption" label, note it:

```text
> OCPBUGS-5678 does not have the "disruption" label. Consider adding it for tracking.
```

Ask the user:
1. Whether any of the found cards match this specific disruption
2. Whether to add the "disruption" label to any unlabeled cards that match — use `editJiraIssue`
   to append `"disruption"` to the existing labels array

**If no matching cards are found:**

Add to the report:

```markdown
## Known Disruption Issues

No existing Jira cards were found tracking this disruption pattern.
```

Then ask:

```text
No existing Jira cards were found tracking this disruption pattern.

Would you like to file a disruption bug? (yes/no)
```

If yes, proceed to Step 10.3.

#### 10.3: File a Disruption Bug (Interactive)

Use the `jira:create` skill to file a bug. Propose the following details for the user to review
and edit before creation:

- **Project**: `OCPBUGS` (default; ask user if TRT is more appropriate)
- **Type**: Bug
- **Summary**: Derived from the analysis — e.g., `"{backend_name} disruption in {job_name} on {platform}"`
- **Description**: Populated from the analysis report including:
  - Root cause hypothesis
  - Affected backends and their types (cache/non-cache)
  - Job run links (Prow and Sippy Intervals)
  - Key evidence (timeline data links, etcd signals, OVS stalls, CPU metrics)
  - Disruption counts and durations
- **Labels**: `["disruption", "ai-generated-jira"]`

Present the proposed summary and description to the user. Allow them to confirm, edit, or cancel
before creating. Follow the `jira:create` skill's interactive workflow and project conventions
(load `jira:jira-conventions` for the target project).

After creation, update the report's "Known Disruption Issues" section with the new bug's key and URL.

## Error Handling

1. **No disruption found** — If interval files show no disruption events, report that the run is clean and no disruption was detected. This is a valid result, not an error.

2. **Audit logs not available** — Some jobs may not have audit logs. Note this in the report and continue analysis with available data.

3. **etcd logs not available** — If etcd pod logs are not present in gather-extra, note this and skip etcd analysis.

4. **Interval files not found** — If no interval/timeline files are found for a job run, this is a critical error for that run. Report it and skip that run if analyzing multiple runs.

5. **gcloud errors** — When `gcloud storage` commands fail, log the error, report which artifacts could not be downloaded, and continue analysis with the remaining available data.

6. **Jira MCP unavailable** — If the Jira MCP tools are not available or authentication fails, skip Step 10 and note "Jira search skipped (MCP unavailable)" in the Known Disruption Issues section. Do not block the disruption analysis on Jira availability.

## Performance Considerations

- Download artifacts for multiple runs in parallel when analyzing more than one run
- When analyzing multiple runs, process each run independently first, then perform cross-run comparison
- Use `--max-bytes` limits when fetching large log files to avoid excessive downloads
- Filter audit logs by timestamp range rather than downloading and scanning entire files when possible
