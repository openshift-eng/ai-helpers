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

The user will provide one of the following as input:

**Option A — Prow job URLs (direct analysis):**

1. **One or more Prow job URLs** (at least 1)
   - Example: `https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.21-e2e-aws-ovn/1983307151598161920`

**Option B — Grafana disruption dashboard URL (run discovery + analysis):**

1. **A Grafana disruption dashboard URL** — the skill extracts filter parameters, finds
   matching job runs via Sippy, and presents candidates for the user to select before analysis
   - Example: `https://grafana-loki.ci.openshift.org/d/gEdw_aLvk/disruption-for-5-0-os-agnostic?var-platform=gcp&var-backend=host-to-host-new-connections&var-upgrade_type=micro&var-architectures=amd64&var-topologies=ha&var-networks=ovn&var-releases=5.0`
   - Recognized by hostname `grafana-loki.ci.openshift.org` and path starting with `/d/`
   - The `var-backend` value automatically sets the `--backends` filter unless overridden

**Optional flags (both input options):**

2. **`--backends` flag** (optional) — comma-separated list of backend names to focus on
   - Example: `--backends kube-api,oauth-api,openshift-api`
   - If omitted, analyze all backends that show disruption (Option A) or use the Grafana
     `var-backend` value (Option B)

3. **`--skip-jira` flag** (optional) — skip the Jira search for known disruption cards
   - By default, the skill searches TRT and OCPBUGS for existing disruption cards after analysis

## Implementation Steps

### Step 1: Parse and Validate Input

1. **Extract URLs and flags**
   - Parse `--backends` flag if present, split on comma to get backend filter list
   - Parse `--skip-jira` flag as a boolean option (default: false)
   - Collect all positional URL arguments

2. **Detect input type** based on the first URL provided:
   - **Grafana URL**: hostname is `grafana-loki.ci.openshift.org` and path starts with `/d/`
     → proceed directly to **Step 1.5** to parse URL parameters and find job runs via Sippy.
     Do NOT fetch the URL, do NOT open or access the dashboard — it is behind SSO.
     Skip steps 3 and 4 (they run after Step 1.5 resolves Prow URLs).
   - **Prow URL**: any other URL (e.g., `prow.ci.openshift.org`, `gcsweb-ci`)
     → continue to step 3 below
   - Validate at least one URL is provided

3. **Parse each Prow URL** to extract bucket path, job name, and build ID
   - Use the same URL parsing logic as the "prow-job-analysis" skill
   - Accept both `prow.ci.openshift.org` and `gcsweb-ci` URL formats
   - Extract `build_id` and `job_name` from each URL

4. **Construct deep links** for each job run — these go **inline throughout the report**
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

### Step 1.5: Resolve Grafana URL to Job Runs

Skip this step if the input is Prow job URL(s). This step resolves a Grafana disruption
dashboard URL into specific Prow job runs for analysis.

**IMPORTANT: Do NOT fetch or open the Grafana URL.** The dashboard is behind Red Hat SSO
and will redirect to a login page. Do NOT manually query Sippy API endpoints — the script
below handles all URL parsing, Sippy querying, and disruption filtering in one call.

#### 1.5.1: Run the Disruption Run Finder

Run `find_disruption_runs.py` with the full Grafana URL and `--auto-select 5` to get a
recommended default selection. This script parses all `var-*` query parameters, maps them
to Sippy variant filters, queries Sippy for matching runs, enriches with disruption data,
and auto-selects a diverse sample:

```bash
python3 "${CLAUDE_SKILL_DIR}/find_disruption_runs.py" \
  --grafana-url "{grafana_url}" \
  --auto-select 5 \
  --format table
```

The script returns all runs matching the dashboard's variant filters. Each run is
enriched with actual disruption seconds from BigQuery (via the Sippy
`/api/jobs/runs/disruption` endpoint), showing how many seconds of disruption were
recorded for the target backend — not just whether a test failure occurred. Recommended
runs are marked with `*` in the `Rec` column. When available, a clean comparison run
(0s disruption from the same job as a disrupted run) is included and marked with `C`.
The output looks like:

```text
Dashboard: disruption-for-5-0-os-agnostic
Filters: Platform=gcp | Architecture=amd64 | Topology=ha | Network=ovn | Upgrade=micro
Release: 5.0 | Percentile: P50 | Backend: kube-api-new-connections

Found 10 runs, 8 with disruption > 0s for kube-api:

| # | Rec | Job | Build ID | Result | Disruption (s) | Disruption Failures | Timestamp |
|---|-----|-----|----------|--------|----------------|---------------------|-----------|
| 1 | *   | ...e2e-gcp-ovn-upgrade | 2084247445587365888 | F | 75 | cache-kube-api, kube-api | 2026-08-03 14:33 |
| 2 |     | ...e2e-gcp-ovn-upgrade | 2084186427159334912 | S | 31 | — | 2026-08-02 12:00 |
| 3 | *   | ...e2e-gcp-runc-upgrade | 2084097565123456789 | S | 12 | — | 2026-08-01 06:00 |
| 4 | C   | ...e2e-gcp-ovn-upgrade | 2084097565987654321 | S | 0  | — | 2026-07-31 18:00 |

Auto-selected 5 runs (* = disrupted, C = clean comparison from same job) for diverse coverage.
```

The auto-selection algorithm:
1. Deduplicates same-job runs within 60s and cross-job runs within 5s
2. Categorizes remaining runs into high/moderate/low disruption tiers
3. Round-robins across different jobs within each tier for diversity
4. Reserves one slot for a clean comparison (0s disruption from the same job as a selected
   disrupted run) — used in Step 6.3 for same-job A/B comparison to filter out red herrings

The `Disruption (s)` column shows the max disruption seconds for the target backend
from BigQuery. A `—` means BigQuery data is not yet available for that run (data is
refreshed every 4 hours).

To get machine-readable output for downstream processing, use `--format json`:

```bash
python3 "${CLAUDE_SKILL_DIR}/find_disruption_runs.py" \
  --grafana-url "{grafana_url}" \
  --auto-select 5 \
  --format json
```

Each JSON row includes `build_id` (Prow build ID), `job` (job name),
`disruption_seconds` (max seconds for target backend),
`disruption_backends` (all matching backends with their disruption seconds),
`disruption_failures` (test failures), `url` (Prow URL), `recommended` (boolean),
and `role` (`"clean-comparison"` for the 0s same-job A/B run, absent otherwise).

Use `--disruption-only` to filter to runs with disruption > 0 for the target backend.
This uses actual BigQuery data, not just test failures.

Additional flags:
- `--since-hours N` — change lookback window (default: 720 = 30 days)
- `--limit N` — max runs to fetch (default: 50)
- `--auto-select N` — change number of auto-selected runs (default when used: 5)
- Individual flags (`--release`, `--platform`, `--backend`, etc.) can override URL params

#### 1.5.2: Present Candidates and Collect Selection

**Show the COMPLETE table output to the user exactly as printed by the script.** Do NOT
filter, reformat, or omit rows. The user needs to see all runs to make an informed
selection. Recommended runs are marked with `*` in the `Rec` column — these are
auto-selected for diverse coverage across jobs, disruption severity levels, and
timestamps. The algorithm deduplicates runs that likely share the same infrastructure
event and then selects a mix of high, moderate, and low disruption for comparison.

After showing the full table, ask:

```text
Recommended runs are marked with * (auto-selected for diverse coverage).
Proceed with recommended runs, or specify different numbers? (e.g., "1,3,5" or "all" or "yes" for recommended)
```

If the user confirms the recommendation (or says "yes"), use the recommended runs.
If the user provides specific numbers, use those instead.

If no runs have disruption test failures for the target backend, note this and offer to
analyze the most recent failed runs anyway (disruption may be within threshold but elevated).

#### 1.5.3: Convert Selections to Prow URLs

Re-run `find_disruption_runs.py` with `--format json` to get machine-readable output with `url`
fields. Use the `url` field from the JSON output to get Prow URLs for the selected runs. Set:
- `--backends` defaults to the Grafana `var-backend` value (unless explicitly overridden)
- The resolved Prow URLs proceed to Step 1, item 3 (Parse each Prow URL) and then Step 2

### Step 2: Download Artifacts for All Runs

Compute `{date}` as today's date in `YYYY-MM-DD` format (e.g., `2026-03-23`).

Check for existing artifacts first. If `.work/disruption-analysis/{date}/{build_id}/logs/` exists
with timeline files, ask the user whether to reuse or re-download.

Use `download_timelines.py` to download prowjob.json and timeline files for all runs in a single
invocation. The script handles creating directories, downloading prowjob.json, extracting the
`--target=` value, finding timeline files via `gcloud storage ls`, and downloading them — all in
parallel across runs:

```bash
python3 "${CLAUDE_SKILL_DIR}/download_timelines.py" \
  --runs "{job_name_1}:{build_id_1},{job_name_2}:{build_id_2}" \
  --output-dir .work/disruption-analysis/{date} \
  --format text
```

**Important GCS bucket note**: Prow URLs may contain `origin-ci-test` in the path (e.g.,
`/view/gs/origin-ci-test/logs/...`), but the actual GCS bucket is always `test-platform-results`.
The script handles this automatically.

The `--runs` flag takes comma-separated `job_name:build_id` pairs. Extract these from the Prow
URLs parsed in Step 1.

Output shows the target and downloaded timeline file paths per run:

```text
2084417286357127168: target=e2e-gcp-runc-upgrade
  .work/disruption-analysis/2026-08-04/2084417286357127168/logs/e2e-timelines_spyglass_20260804-000654.json
  .work/disruption-analysis/2026-08-04/2084417286357127168/logs/e2e-timelines_spyglass_20260804-012513.json

2084701838124257280: target=e2e-gcp-ovn-upgrade
  .work/disruption-analysis/2026-08-04/2084701838124257280/logs/e2e-timelines_spyglass_20260804-190035.json
```

Use `--format json` for machine-readable output with `build_id`, `job`, `target`, and
`timeline_files` fields per run.

**Timeline file locations vary by job type**:

- **Non-upgrade jobs**: Usually one timeline file
- **Upgrade jobs**: Usually two timeline files (one per phase — upgrade and conformance)

If the script reports errors for specific runs, check the error message and continue analysis
with the runs that succeeded.

### Step 3: Analyze Interval/Timeline Data

#### 3.1: Triage All Runs with Summary Mode

**For multi-run analysis, always start with `--format summary`** to triage all runs before
deep-diving. This prevents large JSON output from consuming context:

```bash
for build_id in {build_id_1} {build_id_2} {build_id_3}; do
  python3 "${CLAUDE_SKILL_DIR}/parse_disruption.py" \
    .work/disruption-analysis/{date}/${build_id}/logs/e2e-timelines_spyglass_*.json \
    --build-id ${build_id} --backends {backend_filter} --format summary
done
```

Example summary output:
```text
2084831773824389120: 11 disruptions | host-to-host:8 cache-host-to-host:3 | OVS:12 (max 9000ms) | etcd:5 | CPU: master-0 | src-node: abc12 | phase: upgrade:11
2084701838124257280: 3 disruptions | kube-api:3 | net-liveness: degraded | phase: conformance:3
2084417286357127168: 0 disruptions
```

Use the summary output to identify which runs need deep investigation (highest disruption,
interesting signal combinations, or unusual patterns). If the auto-selection included a
clean comparison run (0s disruption from the same job as a disrupted run), note which
disrupted run it pairs with — you will use this pair in Step 6.3 to filter out red herrings.

#### 3.2: Get Blast Radius for Each Run

To see which other backends were disrupted during the same time window (for the "Other Disrupted
Backends" report section), use `--blast-radius` with `--format summary`:

```bash
python3 "${CLAUDE_SKILL_DIR}/parse_disruption.py" \
  .work/disruption-analysis/{date}/{build_id}/logs/e2e-timelines_spyglass_*.json \
  --backends {backend_filter} --blast-radius --format summary
```

This appends a compact list of all disrupted backends (not just the filtered ones) with counts
to the summary output, without full event details.

#### 3.3: Deep-Dive Selected Runs

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

If the parser output is insufficient for a particular signal, query the timeline JSON directly.

#### 3.4: Signal Interpretation Reference

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

### Step 4: Deep-Dive Artifact Download (Optional)

**Only perform this step if the parser output from Step 3 is insufficient for root cause
determination** — for example, when you need to see the full audit log request details or
etcd log context beyond what the timeline summaries provide.

#### 4.1: Download Audit Logs (if needed)

```bash
gcloud storage cp -r "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/audit_logs/" \
  .work/disruption-analysis/{date}/{build_id}/logs/audit_logs/ --no-user-output-enabled 2>/dev/null || true
```

Query for sampler requests during disruption windows to identify request gaps.

#### 4.2: Download etcd Pod Logs (if needed)

```bash
gcloud storage cp -r "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-extra/artifacts/pods/openshift-etcd/" \
  .work/disruption-analysis/{date}/{build_id}/logs/etcd-pods/ --no-user-output-enabled 2>/dev/null || true
```

Search for leader changes, write delays, member issues, and disk problems.

#### 4.3: PromQL Queries for Manual Investigation

If the analysis needs live cluster metrics (not available in artifacts), provide these queries:

```promql
-- Top CPU consumers across all nodes
topk(25, sum by (namespace) (rate(container_cpu_usage_seconds_total{container!="",pod!=""}[5m])))

-- CPU on a specific node
topk(25, sum by (namespace) (rate(container_cpu_usage_seconds_total{container!="",pod!="",node="<node-name>"}[5m])))

-- E2E test CPU on a specific node
topk(10, sum by (namespace) (rate(container_cpu_usage_seconds_total{container!="",pod!="",node="<node-name>",namespace=~"^e2e-.*"}[5m])))
```

### Step 5: Additional Diagnostic Checks

#### 5.1: Node Shutdown Sequencing

If disruption coincides with node events, check:

- Did the poller go `readyz=false` as expected when the node was shutting down?
- Were endpoint slices updated accordingly?
- Did the test framework watcher see the endpoint was removed and stop disruption polling?

Look for these signals in interval files and node-related logs.

#### 5.2: Endpoint Slice Updates

Check audit logs for endpoint slice modification events during disruption windows:

- Look for audit events related to `endpointslices` resources
- Verify that readiness changes triggered appropriate endpoint updates

### Step 6: Cross-Run Comparison (Multiple Runs Only)

When multiple job run URLs are provided:

#### 6.1: Align Disruption Events

For each backend that shows disruption across multiple runs:

- Compare which backends are disrupted in each run
- Identify backends that are **consistently disrupted** across all runs (systemic issue)
- Identify backends that are **disrupted in only some runs** (intermittent or infrastructure-specific)

#### 6.2: Pattern Detection

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

#### 6.3: Clean Comparison Analysis (Same-Job A/B)

When the auto-selection included a clean comparison run (0s disruption from the same job as a
disrupted run), perform a same-job A/B comparison to filter out red herrings:

1. **Identify the pair**: The clean run shares a job name with one or more disrupted runs.
   Compare their concurrent events side by side.

2. **Signals present in both**: Any concurrent events that appear in *both* the clean and
   disrupted runs are **not the cause** of disruption — they are normal job behavior. Examples:
   - E2E tests that run during disruption windows but also run in clean runs
   - OVS log entries that appear at similar relative times in both runs
   - Operator rollouts that happen in both upgrade phases

3. **Signals unique to disrupted runs**: Concurrent events that appear *only* in disrupted runs
   (and not in the clean comparison) are the strongest root cause candidates. Highlight these
   in the Cross-Run Comparison section.

4. **Infrastructure differences**: Note any differences in the cluster setup (node types, regions,
   etc.) between the clean and disrupted runs if visible in the artifacts.

This comparison is especially valuable for filtering out E2E test correlation noise — if the same
tests run during disruption windows and during clean runs, they are not causing the disruption.

#### 6.4: Correlate etcd and CPU Findings

- Are etcd leader changes present in all runs showing cache-backend disruption?
- Do runs with mass disruption consistently show high CPU or node pressure?
- Are audit log gaps consistent across runs?

### Step 7: Generate Report

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

{If triggered from a Grafana URL, include this section:}
## Dashboard Context
- **Source**: [{dashboard_name}]({grafana_url})
- **Filters**: Platform={platform} | Upgrade={upgrade_type} | Topology={topology} | Network={network} | Architecture={architecture}
- **Backend**: {var-backend}
- **Percentile**: {var-percentile} | **Release**: {var-releases}

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
{Analysis with inline links to supporting evidence}

## Other Disrupted Backends
{When --backends filter was used, list other backends that were disrupted during the
same time window and due to the same root cause. This helps readers understand the full
blast radius — e.g., if openshift-api was requested but kube-api, oauth-api, and
metrics-api were also disrupted simultaneously, that confirms a control plane problem
rather than an openshift-api-specific issue. Only include backends whose disruption
overlaps the same window; exclude unrelated disruption at other times.}

## Known Disruption Issues
{Results from Step 8 Jira search, or "Jira search skipped (--skip-jira)"}
```

**For multiple runs — use the same inline linking pattern:**

```text
# Disruption Analysis: {backend_names}

{If triggered from a Grafana URL, include this section:}
## Dashboard Context
- **Source**: [{dashboard_name}]({grafana_url})
- **Filters**: Platform={platform} | Upgrade={upgrade_type} | Topology={topology} | Network={network} | Architecture={architecture}
- **Backend**: {var-backend}
- **Percentile**: {var-percentile} | **Release**: {var-releases}

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
{Synthesis with links to key evidence}

## Other Disrupted Backends
{When --backends filter was used, list other backends that were disrupted during the
same time window and due to the same root cause — not all disruption in the run, just
what overlaps the identified disruption event. Show a consolidated table with backend
name, type (cache/non-cache/cloud/canary), and how many runs (out of N) showed that
backend disrupted in the same window. Sort by runs-affected descending, then by count.
This reveals the full blast radius and helps confirm root cause — e.g., if every API
backend fails together, the problem is control-plane-wide, not backend-specific.}

## Known Disruption Issues
{Results from Step 8 Jira search, or "Jira search skipped (--skip-jira)"}
```

Save the report using a filename that references the backends being analyzed:

- **Single run**: `.work/disruption-analysis/{date}/{backend_names}-analysis.md`
- **Multiple runs**: `.work/disruption-analysis/{date}/{backend_names}-analysis.md`

Where `{backend_names}` is a kebab-case join of the disrupted backend base names (e.g.,
`image-registry-new-connections-analysis.md` or `kube-api-oauth-api-analysis.md`).
If all backends are analyzed (no `--backends` filter), use the backends that actually showed
disruption. If the resulting filename would be excessively long (more than 5 backends),
truncate to the first 5 and append `-and-more` (e.g., `kube-api-oauth-api-openshift-api-cache-oauth-api-cache-openshift-api-and-more-analysis.md`).

### Step 8: Known Disruption Issue Lookup

Skip this step if `--skip-jira` was passed. This step searches Jira for existing cards that
may already track the disruption pattern identified in the analysis, and offers to file a new
bug if none are found.

#### 8.1: Search for Known Disruption Cards

Extract the base backend names from the analysis (e.g., `openshift-api`, `kube-api`, `oauth-api`
— strip `cache-` prefix and `-new-connections`/`-reused-connections` suffixes to get the base name).

Run two JQL queries using `searchJiraIssuesUsingJql` (cloudId: `redhat.atlassian.net`) —
one for open cards, one for closed. Combine all backend names into a single query to avoid
excessive API calls:

**Query 1 — Open cards:**

```jql
project in (TRT, OCPBUGS) AND status != Closed AND (labels = "disruption" OR text ~ "disruption") AND (text ~ "{backend_name_1}" OR text ~ "{backend_name_2}") ORDER BY updated DESC
```

**Query 2 — Closed cards (prior investigations):**

```jql
project in (TRT, OCPBUGS) AND status = Closed AND (labels = "disruption" OR text ~ "disruption") AND (text ~ "{backend_name_1}" OR text ~ "{backend_name_2}") ORDER BY updated DESC
```

Use `maxResults: 10` and `fields: ["summary", "status", "labels", "assignee", "updated", "priority", "resolution"]`
for each query. Deduplicate results across queries by issue key.

Closed cards are valuable — they may document a prior investigation into the same disruption
pattern that provides context (root cause, fix applied, affected versions).

#### 8.2: Present Results and Offer Actions

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

If yes, proceed to Step 8.3.

#### 8.3: File a Disruption Bug (Interactive)

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

6. **Jira MCP unavailable** — If the Jira MCP tools are not available or authentication fails, skip Step 8 and note "Jira search skipped (MCP unavailable)" in the Known Disruption Issues section. Do not block the disruption analysis on Jira availability.

7. **Grafana URL missing required parameters** — If `var-releases` or `var-backend` are missing from the Grafana URL, prompt the user for the missing values rather than failing.

8. **No Sippy results for Grafana filters** — If no runs match the variant filters from the Grafana URL, suggest widening the time window or relaxing filters. Report the exact query parameters that were attempted so the user can diagnose the mismatch.

9. **No disruption test failures in matching runs** — If matching runs exist but none have disruption test failures for the target backend, note this (disruption may be within threshold but elevated compared to baseline). Offer to analyze the most recent runs anyway.

10. **Sippy API unavailable** — If the Sippy API is unreachable during Grafana URL resolution, report the error and suggest providing Prow job URLs directly as a fallback.

## Performance Considerations

- Download artifacts for multiple runs in parallel when analyzing more than one run
- When analyzing multiple runs, process each run independently first, then perform cross-run comparison
- Use `--max-bytes` limits when fetching large log files to avoid excessive downloads
- Filter audit logs by timestamp range rather than downloading and scanning entire files when possible
