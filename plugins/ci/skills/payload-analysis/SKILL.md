---
name: payload-analysis
description: Analyze a payload snapshot to identify root causes of blocking job failures, score candidate PRs, and produce an HTML report with revert recommendations
---

# Payload Analysis

This skill analyzes a payload using a local snapshot (produced by `payload-snapshot`) to identify root causes of blocking job failures and produce a comprehensive HTML report. The snapshot pre-gathers all release controller, GitHub, and CI data so this skill can focus purely on analysis — no live API orchestration required.

It supports **Rejected** payloads (full analysis of all failed blocking jobs), **Ready** payloads (early analysis of blocking jobs that have already failed), and **Accepted** payloads (which may have been force-accepted despite blocking failures).

## When to Use This Skill

Use this skill when you need to:

- Understand why a payload was rejected
- Investigate failures in a force-accepted payload
- Assess whether an in-progress ("Ready") payload is likely to be rejected
- Determine whether failures are new or persistent
- Identify which PRs likely caused new failures
- Get a comprehensive overview of payload health with actionable root cause analysis
- Re-analyze a historical payload against its original snapshot data

## Required Skills

Before starting, you **MUST** load the following skills (they define output schemas used in Steps 6 and 8):

1. **`payload-results-yaml`** — schema for the payload results YAML file
2. **`payload-autodl-json`** — schema for the autodl JSON data file

## Prerequisites

1. **Python 3** (3.10 or later) — for running the snapshot script if needed
2. **gcloud CLI** — for subagent artifact download (must-gather, pod logs)
3. **GitHub CLI (`gh`)** — for checking existing revert PRs (Step 6.3)

## Implementation Steps

### Step 1: Parse Arguments

The first argument is a **full payload tag** (e.g., `4.22.0-0.nightly-2026-02-25-152806`). Parse from it:
- `tag`: The specific payload tag to analyze
- `version`: Extract from the tag (e.g., `4.22` from `4.22.0-0.nightly-...`)
- `stream`: Extract from the tag (e.g., `nightly` from `4.22.0-0.nightly-...`)
- `architecture`: Inferred from the tag. The tag format is `<version>-0.<stream>[-<arch>]-<timestamp>`. If no architecture is present between the stream and timestamp, it is `amd64`. Otherwise, the architecture is the segment between the stream and timestamp. Examples:
  - `4.22.0-0.nightly-2026-02-25-152806` → `amd64`
  - `4.22.0-0.nightly-arm64-2026-02-25-152806` → `arm64`
  - `4.22.0-0.nightly-ppc64le-2026-02-25-152806` → `ppc64le`

### Step 2: Locate or Create Snapshot

The analysis requires a local snapshot produced by the `payload-snapshot` skill. Search for an existing snapshot in this order:

1. **Explicit `--snapshot-dir DIR`**: If provided, look for `DIR/summary.json`. If not found, exit with an error.
2. **Current directory**: Check if `./summary.json` exists and its `payload_tag` field matches the requested tag.
3. **Standard relative path**: Check if `payload/<version>/<stream>/summary.json` exists and matches the tag.

If no matching snapshot is found, create one:

```bash
SNAPSHOT_SCRIPT="${CLAUDE_PLUGIN_ROOT}/skills/payload-snapshot/scripts/payload_snapshot.py"
if [ ! -f "$SNAPSHOT_SCRIPT" ]; then
  SNAPSHOT_SCRIPT=$(find ~/.claude/plugins -type f -path "*/ci/skills/payload-snapshot/scripts/payload_snapshot.py" 2>/dev/null | sort | head -1)
fi
if [ -z "$SNAPSHOT_SCRIPT" ] || [ ! -f "$SNAPSHOT_SCRIPT" ]; then echo "ERROR: payload_snapshot.py not found" >&2; exit 2; fi
python3 "$SNAPSHOT_SCRIPT" <payload_tag>
```

After locating `summary.json`, set `SNAPSHOT_DIR` to the directory containing it. All relative paths in `summary.json` (e.g., `job_json`, `junit_results`, `build_log`, PR paths) resolve from this directory.

### Step 3: Extract Failure Data from Snapshot

Read `summary.json` to extract all data needed for analysis. The snapshot has already done the work of fetching payloads, building the chain, tracking streaks, and collecting PR data.

#### 3.1: Payload Metadata

From `summary.json` top-level fields:
- `payload_tag`, `phase`, `release_url`, `architecture`, `stream`, `version`
- `chain_length`, `baseline_tag`, `hours_since_baseline`

#### 3.2: Failed Blocking Jobs

From `summary.json` → `blocking_jobs.failed_jobs[]`, each entry contains:
- `name`, `state`, `prow_url`, `gcs_url`, `is_aggregated`, `retries`
- `streak`: `streak_length`, `originating_payload`, `is_new_failure`, `failure_pattern`
- `build_log_errors`, `test_failure_count`
- Paths: `job_json`, `junit_results`, `build_log`

For each failed job, read its `job.json` (at `SNAPSHOT_DIR/<job_json>` path) to get `previousAttemptURLs`.

#### 3.3: Candidate PRs

For each failed job's `streak.originating_payload`, find the matching entry in `summary.json` → `payloads[]`. Its `prs[]` array contains the PRs introduced in that payload:
- `url`, `component`, `number`, `description`
- Paths to local artifacts: `diff`, `comments`, `jobs`

These PRs are the **candidates** for failures that started in that originating payload.

#### 3.4: Test Failure Details

From `summary.json` → `test_failures.blocking[]`:
- `test_name`, `jobs`, `first_failed_in`, `payloads_failing`
- `failure_message`, `failure_text` (full, not truncated)

#### 3.5: Build Log Errors

For deeper context, read `build_log.json` (at the `build_log` path) for any failed job. It contains `error_warning_lines[]` with `line_number` and `text`, plus `tail_lines[]` (last 20% of the log).

### Step 4: Investigate Each Failed Job in Parallel

For each failed blocking job in the **target payload**, launch a **parallel subagent** to investigate the failure. Pass the subagent the Prow URL and all previous attempt URLs from Step 3.2.

Each subagent should determine whether the failure is an install failure or a test failure by checking the JUnit results (e.g., look for `install should succeed*` test failures), then use the appropriate analysis skill. Almost all blocking jobs install a cluster and then run tests, so the job name alone does not tell you the failure type.

You MUST use the following prompt verbatim (substituting the placeholder values) when launching each subagent. Do NOT paraphrase, shorten, or write your own prompt — the specific instructions below are critical for analysis quality:

> Analyze the failure at <prow_url>. This job had <N> retries. The previous attempt URLs are: <previous_attempt_urls>.
>
> **Aggregated jobs**: If this is an aggregated job (has `aggregated-` prefix or an `aggregator` step), retries only re-run the aggregation analysis — they do NOT re-run the underlying test jobs. Therefore, only examine the most recent attempt; previous attempts contain the same underlying results and do not provide additional signal.
>
> **Non-aggregated jobs**: **Examine the final attempt first**, then compare with previous attempts to determine whether all retries failed the same way. If retries show different failure modes, note this — it distinguishes consistent regressions from intermittent/infrastructure issues. Consistent failures across all attempts strongly indicate a product regression rather than flakiness.
>
> First, check the JUnit results or build log to determine whether this is an install failure (look for `install should succeed: overall` or similar install-related test failures) or a test failure (install passed, specific tests failed).
>
> Based on the failure type, use the appropriate skill:
> - **Install failure**: Use the `ci:prow-job-analyze-install-failure` skill. For metal/bare-metal jobs (job name contains "metal"), also perform analysis using the `ci:prow-job-analyze-metal-install-failure` skill for dev-scripts, Metal3/Ironic, and BareMetalHost-specific diagnostics.
> - **Test failure**: Use the `ci:prow-job-analyze-test-failure` skill. Do NOT use `--fast` — always perform the full analysis including must-gather extraction and analysis.
>
> **IMPORTANT** — Trace every failure to its specific root cause by examining actual logs. Never stop at high-level symptoms like "0 nodes ready", "operator degraded", or "containers are crash-looping". Download and read the actual log bundles, pod logs, and container previous logs. Cite specific error messages. The root cause must be actionable, not a restatement of the symptom.
>
> **Do NOT classify a failure as "infrastructure flake" or "transient" unless you have affirmative evidence** of an infrastructure problem (cloud API errors, quota exceeded, network timeouts from the cloud provider, Boskos lease failures, CI platform outages). The absence of an obvious code-level explanation does NOT make something infrastructure — it means you need to investigate deeper. Default to treating failures as potential product regressions until evidence proves otherwise.
>
> Return a concise summary including: failure type (install vs test), root cause, key error messages, and any relevant log excerpts. Do not ask user questions. Keep the output concise for inclusion in a summary report.
>
> If the job is an aggregated job (has `aggregated-` prefix in the name or an `aggregator` container/step), also return the **underlying job name** (e.g., `periodic-ci-openshift-release-main-ci-4.22-e2e-aws-upgrade-ovn-single-node`). This is found in the junit-aggregated.xml artifacts — each `<testcase>` has `<system-out>` YAML data with a `humanurl` field linking to individual runs whose URL path contains the underlying job name. The underlying job name cannot be derived from the aggregated job name — it must be extracted from the artifacts.

**Structured Return Format**: Instruct each subagent to include an `ANALYSIS_RESULT` block at the end of its response:

```
ANALYSIS_RESULT:
- failure_type: install|test|upgrade|infra
- root_cause_summary: <one-line summary>
- affected_components: <comma-separated list of affected operators/components>
- key_error_patterns: <comma-separated key error strings for matching>
- known_symptoms: <comma-separated symptom summaries from job_labels, or "none">
- underlying_job_name: <for aggregated jobs only, extracted from junit artifacts>
- retries_consistent: yes|no|no_retries|only_final_examined
- retry_summary: <brief comparison of failure modes across attempts, e.g. "all 3 attempts failed with same KAS crashloop" or "attempt 1 infra timeout, attempts 2-3 test failure", or "no retries" when there was only a single attempt>
```

**Note for aggregated jobs**: Since only the final attempt is examined (retries re-run aggregation only), set `retries_consistent: only_final_examined` and `retry_summary: "Aggregated job — only final attempt examined (retries re-run aggregation only)"`.

**Important**: Launch ALL subagents in parallel for maximum speed. Do NOT set the `model` parameter — let subagents inherit the parent model, as these analysis tasks require a capable model.

#### Cross-Platform and Cross-Job Failure Pattern Recognition

After collecting subagent results, look for patterns across multiple jobs:

- **Same failure across a job family** (e.g., all `techpreview` jobs, all `fips` jobs, all `upgrade` jobs): This often indicates a failure specific to that feature set or configuration.
- **Same failure across multiple platforms**: This often points to a product bug in shared code.

### Step 4b: Consult Previous Claude Analyses

Read the target payload's `payload.json` (at `SNAPSHOT_DIR/<payloads[0].payload>`) and check if a `claude-payload-agent` async job exists with state `Succeeded`. If so, fetch the HTML report from its Prow artifacts:

```
{prow_artifacts_url}/artifacts/claude-payload-agent/openshift-release-analysis-claude-payload-agent/artifacts/payload-analysis-{tag}-summary.html
```

Convert the Prow URL to a gcsweb URL and use WebFetch to read it.

**Important**: Previous analyses are a secondary input. Always complete your own analysis first, then compare. Use previous findings to bolster confidence, challenge assumptions, or fill gaps — never adopt conclusions without verifying against the snapshot data.

### Step 5: Validate Failure Streaks

After collecting all subagent results, verify that consecutive failures across payloads share the same root cause. A consecutive failure streak does NOT automatically mean the same root cause.

Compare the subagent's root cause analysis for the target payload against previous payload analyses (from Step 4b) or the failure signatures in the snapshot's streak data.

If a job fails in two consecutive payloads but for **different reasons**, treat each as a separate streak=1 failure with its own originating payload and candidate PRs. Re-split the streak and re-assign originating payloads before proceeding to scoring.

### Step 6: Collect Investigation Results and Identify Revert Candidates

Wait for all subagents to complete and collect their analysis results. For each failed job, you now have:

- **Job name** and **Prow URL** (from snapshot)
- **Failure analysis** (from subagent)
- **Streak data** (from snapshot: `streak_length`, `originating_payload`, `failure_pattern`)
- **Candidate PRs** (from snapshot: originating payload's `prs[]`)

#### 6.1: Correlate Failures with Candidate PRs

For each failed job, cross-reference the failure analysis from the subagent with the candidate PRs from the originating payload. Read the PR's `code.diff` file (at the path from `summary.json` → `payloads[].prs[].diff`) to check for code-level correlation.

If a subagent traced the root cause to a PR outside the payload (e.g., an `openshift/release` PR that modified a CI step registry script), include that PR as a candidate.

Score each (failed job, candidate PR) pair using the following weighted rubric:

| Signal | Weight | Criteria |
|--------|--------|----------|
| New failure mode | +30 | The specific failure mode was not present in previous payloads |
| Component exclusivity | +10 to +30 | The failure involves a component modified by this PR. Sole modifier = +30, 2-3 PRs = +20, 4+ PRs = +10 |
| Error message match | +40 | Error messages or stack traces directly reference code, packages, or functionality changed by this PR |
| Multi-job correlation | +10 | The same PR is a candidate for failures in multiple independent jobs |
| Presubmit coverage gap | +10 | The failing job tests a scenario not covered by the PR's presubmit tests |
| Single candidate | +10 | Only one PR landed in the originating payload that touches the affected component |

Maximum possible score is 130, capped at 100. Record the numeric score alongside qualitative rationale.

**Apply the rubric mechanically.** Calculate the score by summing the weights for each signal that fires based on concrete evidence. Do NOT adjust the score downward based on speculative counter-arguments like "if this were the sole cause, other jobs would also fail" or "this could be a coincidence." If the error messages reference the PR's changes, that's +40 — the fact that some other jobs didn't fail doesn't negate the match. If the failure is new (streak=1) and the PR is the only one touching the component, those signals fire regardless of theoretical alternatives. Trust the rubric — it exists to prevent both over- and under-attribution.

#### 6.2: Propose Revert Candidates

For each candidate PR with a rubric score of **>= 85**, mark it as a **revert candidate**. A PR qualifies when:

1. The failure clearly maps to the PR's changes
2. The timing is exact — the job was passing before the originating payload
3. No other plausible explanation — infrastructure flakiness and platform problems have been ruled out

Per OCP policy, PRs that break payloads MUST be reverted. When confidence is high, the report must clearly state that a revert is required — not optional.

For each revert candidate, record: PR URL, description, component, confidence score with rationale.

**Do NOT propose reverts for**: Infrastructure failures, flaky tests that also fail on accepted payloads, jobs where analysis is inconclusive.

#### 6.3: Check if Revert Candidates Were Already Reverted

For each revert candidate:

```bash
gh pr list --repo <org>/<repo> --search "revert <pr_number>" --json number,title,url,state,mergedAt --limit 5
```

If a revert PR is found:
- **Merged**: Note when it merged relative to the payload. If after the payload was cut, the fix is expected in the next payload. Do not recommend reverting again.
- **Open**: Mention the existing revert PR and link to it.
- **Closed (not merged)**: Ignore.

#### 6.4: Determine Force-Accept Recommendation

Recommend force-accepting when **all** of the following are true:

1. All failures are temporary infrastructure issues (`failure_type: "infra"`)
2. No more than 2 blocking jobs failed
3. `hours_since_baseline` from `summary.json` is >= 18 (or null)

#### 6.5: Write Payload Results YAML

Use the `payload-results-yaml` skill to create: `payload-results-{tag}.yaml`

This file contains ALL scored candidates across all confidence tiers (HIGH, MEDIUM, LOW), enabling downstream commands to filter by their own criteria.

### Step 7: Generate HTML Report

Create a self-contained HTML file named `payload-analysis-<tag>-summary.html` in the current working directory. The tag should be sanitized for use as a filename.

The report must include the following sections:

#### 7.1: Header and Executive Summary

```html
<h1>Payload Analysis: {payload_tag}</h1>
<div class="metadata">
  <p>Architecture: {architecture} | Stream: {stream} | Generated: {timestamp}</p>
  <p>Release Controller: <a href="{release_url}">{payload_tag}</a></p>
  <p>Snapshot: {snapshot_dir}</p>
</div>

<div class="executive-summary">
  <h2>Executive Summary</h2>
  <p>{total_blocking} blocking jobs: {succeeded} passed, {failed} failed</p>
  <p>{new_failures} new failure(s), {persistent_failures} persistent failure(s)</p>
  <p>Chain: {chain_length} payloads, {hours_since_baseline}h since baseline</p>
</div>
```

#### 7.2: Blocking Jobs Summary Table

A table showing ALL blocking jobs with columns:
- Job Name
- Status (color-coded: green for passed, red for failed)
- Streak (consecutive failing payloads; "N/A" for passed)
- History (the `failure_pattern` from the snapshot, e.g., "F F F S F F", with color-coded markers)
- First Failed In (originating payload tag, linked to release controller)

#### 7.3: Failed Job Details

For each failed job, a collapsible section containing:

```html
<details>
  <summary class="failed-job">
    <span class="job-name">{job_name}</span>
    <span class="badge badge-{new|persistent}">{New Failure|Failing for N payloads}</span>
  </summary>
  <div class="detail-body">
    <h4>Prow Job</h4>
    <p><a href="{prow_url}">{prow_url}</a> | <a href="{gcs_url}">GCS Artifacts</a></p>

    <h4>Failure Analysis</h4>
    <div class="analysis">{analysis_from_subagent}</div>

    <h4>Known Symptoms Seen</h4>
    <p class="symptoms">{comma-separated symptom summaries, or omit if "none"}</p>

    <h4>First Failed In</h4>
    <p><a href="{originating_payload_url}">{originating_payload_tag}</a></p>

    <h4>Candidate PRs (introduced in {originating_payload_tag})</h4>
    <table>
      <tr><th>Component</th><th>PR</th><th>Description</th><th>Score</th></tr>
    </table>
  </div>
</details>
```

#### 7.4: Recommended Reverts

Include this section **before** the per-job details, immediately after the executive summary.

If revert candidates were identified (score >= 85):

```html
<div class="verdict verdict-revert">
  <h2>Recommended Reverts</h2>
  <p><strong>OCP Policy: PRs that break payloads MUST be reverted.</strong></p>
  <table>
    <tr><th>PR</th><th>Component</th><th>Description</th><th>Caused Failure In</th><th>Failing Since</th><th>Rationale</th></tr>
  </table>
  <h3>Automated Reverts</h3>
  <div class="revert-prompt">
    <button onclick="navigator.clipboard.writeText(this.nextElementSibling.textContent.trim())">Copy</button>
    <pre>/ci:payload-revert {payload_tag}</pre>
  </div>
</div>
```

If no revert candidates:

```html
<div class="verdict verdict-none">
  <strong>No Recommended Reverts</strong>
  <p>No PRs were identified with sufficient confidence for revert recommendation.</p>
</div>
```

#### 7.5: Force-Accept Recommendation

If recommended (Step 6.4):

```html
<div class="verdict verdict-infra">
  <strong>Force-Accept Recommended</strong>
  <p>All blocking job failures are temporary infrastructure issues and no payload has been
     accepted in this stream for more than 18 hours.</p>
  <p>Baseline: <a href="{baseline_url}">{baseline_tag}</a> ({hours_since_baseline}h ago)</p>
</div>
```

#### 7.6: Review Notes

Include this section at the end of the report, before the footer:

```html
<div class="card">
  <h2>Adversarial Review</h2>
  <p>{review_summary}</p>
  <!-- If reviewer identified issues: -->
  <h4>Issues Found</h4>
  <ul>
    <li>{issue_description} — {action_taken}</li>
  </ul>
</div>
```

#### 7.7: Styling

The HTML must be fully self-contained with embedded CSS. Use a GitHub-inspired dark mode design. Use CSS variables for the color palette:

```css
:root {
  --bg: #0d1117; --surface: #161b22; --border: #30363d;
  --text: #e6edf3; --text-muted: #8b949e;
  --green: #3fb950; --red: #f85149; --orange: #d29922;
  --blue: #58a6ff; --purple: #bc8cff;
}
```

Follow the styling conventions from the existing report format. All `<a>` links must use `target="_blank"`.

### Step 8: Generate JSON Data File

Use the `payload-autodl-json` skill to produce `payload-analysis-<sanitized_tag>-autodl.json`.

See the `payload-autodl-json` skill for the complete schema, row cardinality rules, and field rules.

### Step 9: Completeness Review

After generating the initial report and output files, launch a **dedicated subagent** to check that the analysis is complete and well-supported. The reviewer catches lazy or shallow work — it does NOT challenge or re-score rubric-based confidence scores.

The reviewer should receive **only** the following (NOT the full conversation history):

1. The `summary.json` snapshot data (payload metadata, failed jobs, streaks, test regressions)
2. The scored candidate list with per-component rubric breakdowns from Step 6
3. The `ANALYSIS_RESULT` blocks from all subagents in Step 4
4. The revert recommendations (if any)

Use this prompt for the reviewer:

> You are a completeness reviewer for a payload failure analysis. Your job is to catch gaps in coverage and shallow analysis — NOT to challenge correct conclusions or lower confidence scores.
>
> **Snapshot data**: {summary.json contents — metadata, failed jobs with streaks, test regressions}
>
> **Subagent analyses**: {ANALYSIS_RESULT blocks for each failed job}
>
> **Scored candidates**: {list of (job, PR, score, rubric breakdown) tuples}
>
> **Revert recommendations**: {list of PRs recommended for revert, or "none"}
>
> Check for these specific problems:
>
> 1. **Missing skill invocations**: Were `prow-job-analyze-install-failure` and `prow-job-analyze-test-failure` skills actually loaded and used? A subagent that improvises without loading the appropriate skill produces shallow analysis.
>
> 2. **Shallow root causes**: Do root cause summaries cite specific error messages, code paths, or log excerpts? Or do they just restate test names and job status? "Test X failed" is not a root cause. "Test X failed because pod Y OOMKilled at 512Mi limit after PR Z increased memory usage in function F" is a root cause.
>
> 3. **Incomplete coverage**: Are there failed jobs with no subagent analysis or with only a one-line summary? Every failed blocking job deserves a thorough investigation.
>
> 4. **Wrong skill for failure type**: Was an install failure analyzed with the test failure skill or vice versa?
>
> **Rules**:
> - Do NOT suggest lowering confidence scores. If the rubric signals fired (error message match, new failure, component exclusivity), the score is correct. Period.
> - Do NOT suggest that a failure "might be infrastructure" when there is positive evidence linking it to a PR. Infrastructure classification requires affirmative evidence (cloud API errors, quota limits, network timeouts) — not just uncertainty about the code change.
> - Do NOT second-guess revert recommendations. When confidence >= 85 based on the rubric, the revert is warranted per OCP policy.
>
> For each issue found, provide:
> - **Issue**: One-line description
> - **Affected job(s)**: Which jobs are affected
> - **Recommendation**: Re-run subagent with correct skill, deepen analysis, or add missing coverage
>
> If the analysis is thorough, say so: "Analysis is complete — all jobs investigated with appropriate skills and specific root causes identified."

After receiving the reviewer's response:

- If coverage gaps are found (missing skill invocation, shallow analysis, wrong skill): re-run the affected subagent analyses, then re-score. Update the HTML report and YAML/JSON files.
- If the analysis is already thorough: note this in the report.
- **Never lower rubric-based confidence scores** based on the reviewer's response. The rubric is mechanical — if the signals fired, the score stands.
- Populate the "Adversarial Review" section (Step 7.6) in the HTML report with the reviewer's findings and any actions taken.

### Step 10: Save and Present

1. Save all output files to the current working directory:
   - HTML report: `payload-analysis-<sanitized_tag>-summary.html`
   - JSON data file: `payload-analysis-<sanitized_tag>-autodl.json`
   - Payload results YAML: `payload-results-<sanitized_tag>.yaml`

2. Tell the user:
   - Path to each saved file
   - Brief text summary (number of failures, new vs persistent, key candidate PRs)
   - Whether the adversarial review changed any conclusions
   - Mention that `/ci:payload-revert` and `/ci:payload-experiment` can consume the YAML for automated actions

## Error Handling

### No Snapshot Available

If no snapshot is found and the snapshot script fails to create one:
```
Error: Could not locate or create a snapshot for {tag}. Run the payload-snapshot skill manually first.
```

### Subagent Failure

If a subagent fails to analyze a job, include the job in the report with:
```
Analysis unavailable: {error_message}
```
Do not let one failed subagent block the entire report.

### Missing PR Data

If the snapshot was created without `gh` authentication, PR diffs/comments will be absent. Note this in the report:
```
Note: PR diff data not available in snapshot. Scoring based on component match and timing only.
```

## Notes

- The snapshot is a **frozen archive** — it captures release controller, GitHub, and CI data as it was when the snapshot was taken. This enables re-analysis of historical payloads and provides reproducible results.
- Subagents still download artifacts from GCS (must-gather, pod logs, step logs) because these are not included in the snapshot. The snapshot provides the data scaffolding; subagents provide deep investigation.
- The adversarial review adds one subagent call but catches misattributions before they reach the report.
- For very large numbers of failed jobs (>8), consider whether some share the same underlying failure and group them in the report.

## See Also

- Related Skill: `payload-snapshot` — creates the snapshot data this skill consumes
- Related Skill: `payload-results-yaml` — schema for the results YAML
- Related Skill: `payload-autodl-json` — schema for the autodl JSON data file
- Related Skill: `prow-job-analyze-test-failure` — deep test failure investigation (used by subagents)
- Related Skill: `prow-job-analyze-install-failure` — deep install failure investigation (used by subagents)
- Related Command: `/ci:payload-revert` — stages reverts for high-confidence candidates
- Related Command: `/ci:payload-experiment` — tests medium-confidence candidates experimentally
