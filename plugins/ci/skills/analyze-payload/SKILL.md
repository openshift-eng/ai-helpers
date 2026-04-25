---
name: Analyze Payload
description: Analyze a payload (rejected, accepted, or in-progress) with historical lookback to identify root causes of blocking job failures and produce an HTML report
---

# Analyze Payload

This skill analyzes a payload for a given OCP version, walks back through consecutive rejected payloads to determine when each failure started, correlates failures with newly introduced PRs, investigates each failed job in parallel, and produces a comprehensive HTML report.

It supports **Rejected** payloads (full analysis of all failed blocking jobs), **Ready** payloads (early analysis of blocking jobs that have already failed, with a determination of whether the payload is on track for rejection), and **Accepted** payloads (payloads can be force-accepted despite blocking failures, so any failed blocking jobs are still analyzed).

## When to Use This Skill

Use this skill when you need to:

- Understand why a payload was rejected
- Investigate failures in a force-accepted payload (Accepted payloads may still have failed blocking jobs)
- Assess whether an in-progress ("Ready") payload is likely to be rejected based on already-failed blocking jobs
- Determine whether failures are new or persistent (permafailing)
- Identify which PRs likely caused new failures
- Get a comprehensive overview of payload health with actionable root cause analysis

## Required Skills

Before starting, you **MUST** load the following skills (they define output schemas used in Steps 6, 8, and 9):

1. **`payload-results-yaml`** — schema for the payload results YAML file
2. **`payload-autodl-json`** — schema for the autodl JSON data file

## Prerequisites

1. **Network Access**: Must be able to reach:
   - OpenShift release controller (`amd64.ocp.releases.ci.openshift.org`)
   - Sippy API (`sippy.dptools.openshift.org`)
   - Prow (`prow.ci.openshift.org`)
2. **Python 3**: For running fetch scripts
3. **gcloud CLI**: For downloading Prow job artifacts

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
  - `4.22.0-0.nightly-s390x-2026-02-25-152806` → `s390x`
  - `4.22.0-0.nightly-multi-2026-02-25-152806` → `multi`
- `lookback`: From `--lookback N` (default: `10`)

### Step 2: Fetch Recent Payloads

Fetch recent payloads without filtering by phase, so the full payload history is available for analysis and lookback:

```bash
FETCH_PAYLOADS="${CLAUDE_PLUGIN_ROOT}/skills/fetch-payloads/fetch_payloads.py"
if [ ! -f "$FETCH_PAYLOADS" ]; then
  FETCH_PAYLOADS=$(find ~/.claude/plugins -type f -path "*/ci/skills/fetch-payloads/fetch_payloads.py" 2>/dev/null | sort | head -1)
fi
if [ -z "$FETCH_PAYLOADS" ] || [ ! -f "$FETCH_PAYLOADS" ]; then echo "ERROR: fetch_payloads.py not found" >&2; exit 2; fi
python3 "$FETCH_PAYLOADS" <architecture> <version> <stream> --limit <lookback * 2>
```

The output is a JSON object with `hours_since_last_accepted` and `last_accepted_tag` at the top level and `payloads` as an array. Extract the payloads array for analysis and retain `hours_since_last_accepted` and `last_accepted_tag` for Step 6.4.

Find the **target payload** (the tag from Step 1) in the payloads array. Based on its phase:

- **Rejected**: Extract all failed blocking job names, their Prow URLs, and any previous attempt URLs. Proceed with full analysis.
- **Ready**: Extract blocking jobs that have already **failed** (with their Prow URLs and previous attempt URLs). These are jobs that will not pass — they indicate the payload is on track for rejection. Proceed with analysis of those failed jobs and note in the report that the payload is still in progress.
- **Accepted**: Extract any failed blocking job names, their Prow URLs, and previous attempt URLs. Payloads can be force-accepted despite blocking job failures, so do NOT assume all blocking jobs passed. If there are failed blocking jobs, proceed with full analysis and note in the report that the payload was accepted despite these failures. If there are truly no failed blocking jobs, report "Payload was accepted with all blocking jobs passing, no analysis needed" and exit.

The release controller API returns `previousAttemptURLs` for jobs that were retried. For each failed job, collect the final Prow URL and all previous attempt URLs. These are available in the `fetch-payloads` output as `attempt N: <url>` lines below the main URL.

### Step 3: Build Failure History (Lookback)

The goal is to determine **when each failing job first started failing** and understand its failure pattern across recent payloads.

Using the full payload list from Step 2 (which includes all phases):

1. Starting from the target payload, collect the set of failed blocking jobs.
2. Walk backwards through **all** previous payloads in the lookback window (up to `lookback` limit), regardless of phase (Rejected, Accepted, or Ready). Accepted payloads can have failed blocking jobs (force-accepted), so check every payload.
3. For each failed job in the target payload, record whether it passed or failed in each previous payload across the entire lookback window. Do NOT stop at the first pass — a job may show an intermittent pattern like F-F-S-F-F due to flaky behavior, and understanding this pattern is important.

For each failed job, record:
- **streak_length**: How many consecutive payloads (counting backwards from the target) this job has been failing in (stops counting at the first pass)
- **originating_payload**: The first payload in the current consecutive failure streak where this job started failing
- **is_new_failure**: Whether the job first started failing in the target payload (streak_length == 1)
- **failure_pattern**: The full pass/fail history across the lookback window (e.g., "F F F S F F"). This helps contextualize whether the failure is a solid regression or intermittent. Intermittent failures are still fully investigated — the pattern is informational context, not a reason to skip analysis or discount the failure.

### Step 4: Fetch New PRs in Originating Payloads

For each unique originating payload identified in Step 3, fetch the PRs that were new in that payload:

```bash
FETCH_NEW_PRS="${CLAUDE_PLUGIN_ROOT}/skills/fetch-new-prs-in-payload/fetch_new_prs_in_payload.py"
if [ ! -f "$FETCH_NEW_PRS" ]; then
  FETCH_NEW_PRS=$(find ~/.claude/plugins -type f -path "*/ci/skills/fetch-new-prs-in-payload/fetch_new_prs_in_payload.py" 2>/dev/null | sort | head -1)
fi
if [ -z "$FETCH_NEW_PRS" ] || [ ! -f "$FETCH_NEW_PRS" ]; then echo "ERROR: fetch_new_prs_in_payload.py not found" >&2; exit 2; fi
python3 "$FETCH_NEW_PRS" <originating_payload_tag> --format json
```

Store the PR data keyed by originating payload tag. These PRs are the **candidates** for the failures that started in that payload.

### Step 5: Investigate Each Failed Job in Parallel

For each failed blocking job in the **target payload**, launch a **parallel subagent** to investigate the failure. Pass the subagent the final Prow URL **and** all previous attempt URLs from Step 2.

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
> - **Install failure**: Use the `ci:prow-job-analyze-install-failure` skill. For metal/bare-metal jobs (job name contains "metal"), perform additional analysis using the `ci:prow-job-analyze-metal-install-failure` skill as needed for dev-scripts, Metal3/Ironic, and BareMetalHost-specific diagnostics.
> - **Test failure**: Use the `ci:prow-job-analyze-test-failure` skill. Do NOT use `--fast` — always perform the full analysis including must-gather extraction and analysis.
>
> **IMPORTANT** — Trace every failure to its specific root cause by examining actual logs. Never stop at high-level symptoms like "0 nodes ready", "operator degraded", or "containers are crash-looping". Download and read the actual log bundles, pod logs, and container previous logs. Cite specific error messages. The root cause must be actionable, not a restatement of the symptom.
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

This structured format enables downstream consumers (like the `/ci:payload-revert` and `/ci:payload-experiment` commands) to programmatically extract analysis results for confidence scoring.

**Important**: Launch ALL subagents in parallel for maximum speed. Do NOT set the `model` parameter — let subagents inherit the parent model, as these analysis tasks require a capable model.

#### Cross-Platform and Cross-Job Failure Pattern Recognition

After collecting subagent results, look for patterns across multiple jobs:

- **Same failure across a job family** (e.g., all `techpreview` jobs, all `fips` jobs, all `upgrade` jobs): This often indicates a failure specific to that feature set or configuration. Look at what differentiates that job family (feature gates, install-config options, test parameters).
- **Same failure across multiple platforms**: Consider whether this points to a product bug in shared code, though note that cross-platform infrastructure issues (e.g., CI platform problems) are also possible.

When patterns emerge, query Sippy for pass rates of related non-blocking jobs to see if the pattern extends beyond blocking jobs.

### Step 5b: Consult Previous Claude Analyses

If the `fetch-payloads` output shows a `claude-payload-agent` async job with state `Succeeded` on any payload in the current rejection streak, fetch the HTML report from its Prow artifacts to review the previous analysis. The report is located at:

```
{prow_artifacts_url}/artifacts/claude-payload-agent/openshift-release-analysis-claude-payload-agent/artifacts/payload-analysis-{tag}-summary.html
```

Convert the Prow URL to a gcsweb URL and use WebFetch to read it.

**Important**: Previous analyses are a secondary input — they may contain insights you missed (e.g., deeper artifact investigation) or they may be wrong. Always complete your own analysis first (Steps 1-5), then compare. Use previous findings to:
- **Bolster confidence** when your analysis reaches the same conclusion
- **Challenge assumptions** when a previous analysis disagrees with yours — re-examine the evidence
- **Fill gaps** when a previous analysis examined logs or artifacts you didn't — go back and examine those same artifacts in the current payload to verify whether the findings still apply

Never adopt a previous analysis conclusion without verifying it against the current payload's artifacts.

### Step 6.0: Validate Failure Streaks

After collecting all subagent results, verify that consecutive failures across payloads share the same root cause. A consecutive failure streak does NOT automatically mean the same root cause. Compare the subagent's root cause analysis for the target payload against previous payload analyses (from Step 5b) or the failure signatures in the lookback data.

If a job fails in two consecutive payloads but for **different reasons** (e.g., payload N failed due to a KAS crashloop and payload N-1 failed due to an etcd timeout), treat each as a separate streak=1 failure with its own originating payload and candidate PRs. Re-split the streak and re-assign originating payloads before proceeding to scoring.

### Step 6: Collect Investigation Results and Identify Revert Candidates

Wait for all subagents to complete and collect their analysis results. For each failed job, you should now have:

- **Job name**
- **Prow URL**
- **Failure analysis** (from subagent)
- **Streak length** (from Step 3)
- **Originating payload** (from Step 3)
- **Candidate PRs** (from Step 4)

#### 6.1: Correlate Failures with Candidate PRs

For each failed job, cross-reference the failure analysis from the subagent with the candidate PRs from the originating payload. Additionally, if a subagent traced the root cause to a PR outside the payload (e.g., an `openshift/release` PR that modified a CI step registry script), include that PR as a candidate — it is a regression like any other and should be scored and treated the same way as payload PRs.

Score each (failed job, candidate PR) pair using the following weighted rubric:

| Signal | Weight | Criteria |
|--------|--------|----------|
| New failure mode | +30 | The specific failure mode (error messages, symptoms) was not present in previous payloads — the job may have been failing before, but not in this way |
| Component exclusivity | +10 to +30 | The failure involves a component modified by this PR, and fewer other PRs in the originating payload touch the same component. Score: sole modifier = +30, 2-3 PRs touch component = +20, 4+ PRs = +10 |
| Error message match | +40 | Error messages or stack traces directly reference code, packages, or functionality changed by this PR |
| Multi-job correlation | +10 | The same PR is a candidate for failures in multiple independent jobs — the more jobs that point to the same PR, the stronger the signal |
| Presubmit coverage gap | +10 | The failing job tests a scenario (upgrade, FIPS, SNO, techpreview, etc.) that wasn't covered by the PR's presubmit tests |
| Single candidate | +10 | Only one PR landed in the originating payload that touches the affected component |

The maximum possible score is 130, but scores above 100 should be capped at 100. Record the numeric score for each (job, candidate PR) pair alongside the qualitative rationale.

#### 6.2: Propose Revert Candidates

For each candidate PR with a rubric score of **>= 85**, mark it as a **revert candidate**. A PR qualifies as a revert candidate when:

1. **The failure clearly maps to the PR's changes** — e.g., the error stack trace references the exact code changed, or the failing component is the one modified by the PR
2. **The timing is exact** — the job was passing in the payload before the originating payload and started failing in the originating payload
3. **No other plausible explanation** — infrastructure flakiness, quota issues, or unrelated platform problems have been ruled out by the subagent analysis

Per OCP policy, PRs that break payloads MUST be reverted. When confidence is high, the report must clearly state that a revert is required — not optional. A fix may be suggested as direction for a follow-up PR after the revert, but the revert itself is mandatory and must not be presented as one option among alternatives.

For each revert candidate, record:
- **PR URL**: The GitHub pull request URL
- **PR description**: Title/summary of the PR
- **Component**: The affected component
- **Confidence score**: The numeric rubric score (e.g., 95) and a qualitative summary (e.g., "95 — temporal match + component match + error references code changed by this PR")
- **Rationale**: A 1-2 sentence explanation of why this PR is the likely cause

**Do NOT propose reverts for**:
- Infrastructure failures (cloud quota, API rate limits, network issues)
- Flaky tests that also fail intermittently on accepted payloads
- Jobs where the failure analysis is inconclusive or the root cause is unclear
- PRs where the correlation is circumstantial (e.g., same component but unrelated code path)

**Older or pre-existing failures**: If the root cause can be traced to a PR from an older payload (outside the current lookback window), identify it and recommend it for revert. If the root cause is identifiable and a fix can be suggested — even if the failure wasn't introduced in this payload — include the diagnosis and suggested fix in the report.

#### 6.3: Check if Revert Candidates Were Already Reverted

For each revert candidate identified in 6.2, check whether a revert PR already exists:

```bash
gh pr list --repo <org>/<repo> --search "revert <pr_number>" --json number,title,url,state,mergedAt --limit 5
```

If a revert PR is found:

1. **Report the revert PR's state** (open, merged, or closed):
   - **Merged**: Note when it merged relative to the analyzed payload's timestamp. If the revert merged after the payload was cut, the fix is expected in the next payload. If it merged before, investigate why the failure persists.
   - **Open**: Note that a revert is in progress but not yet merged. Link to the PR.
   - **Closed (not merged)**: Ignore — the revert was abandoned.

2. **Do not recommend reverting a PR that already has a merged revert.** The report should still mention the culprit PR and link to the revert, but the action item should reflect the current state (e.g., "Already reverted by #291, fix expected in next payload").

3. **If a revert PR is open but not merged**, still recommend the revert but note that a revert PR already exists and link to it, so the reader can help expedite the merge.

#### 6.4: Determine Force-Accept Recommendation

Recommend force-accepting the payload when **all** of the following are true:

1. **All failures are temporary infrastructure issues**: Every failed blocking job has `failure_type: "infra"` and the subagent analysis confirms the failures are transient infrastructure problems (cloud quota, API rate limits, CI platform issues, network timeouts) — not product regressions masquerading as infrastructure. If any job has a non-infra failure type, or if any infrastructure failure appears to be caused by a product change, do not recommend.

2. **No more than 2 blocking jobs failed**: A small number of infrastructure failures (1-2) indicates enough signal that the payload is otherwise healthy. If 3 or more blocking jobs failed, do not recommend — too many simultaneous failures reduce confidence even if each appears infrastructure-related.

3. **No payload has been accepted in this stream for more than 18 hours**: Use the `hours_since_last_accepted` field from the `fetch-payloads` output (Step 2). If the value is `null` (no accepted payload in the fetched history) or >= 18, this condition is met.

Record the determination in the payload results YAML and autodl JSON (see their respective schemas for the field).

#### 6.5: Write Payload Results YAML

After scoring all (job, candidate PR) pairs and checking for existing reverts, use the `payload-results-yaml` skill to create the results file in the current working directory: `payload-results-{tag}.yaml` (sanitize the tag for filename safety).

This file contains ALL scored candidates across all confidence tiers (HIGH, MEDIUM, and LOW), enabling downstream commands (`/ci:payload-revert`, `/ci:payload-experiment`) to filter by their own criteria.

When a PR appears as a candidate for multiple jobs, merge into one entry using the highest confidence score and combining all `failing_jobs` into a single list.

Candidates start with `actions: []` unless a pre-existing revert PR was found in Step 6.3. If found, append an action with `type: "revert"`, `status: "open"` or `"merged"`, `revert_pr_url` set, and remaining action fields empty. Downstream skills (`stage-payload-reverts`, `payload-experimental-reverts`) append additional actions.

See the `payload-results-yaml` skill for the complete schema.

### Step 7: Generate HTML Report

Create a self-contained HTML file named `payload-analysis-<tag>-summary.html` in the current working directory. The tag should be sanitized for use as a filename (replace colons and slashes). The `-summary.html` suffix is required for automatic rendering in downstream tools.

The report must include the following sections:

#### 7.1: Header and Executive Summary

```html
<!-- Header with payload info -->
<h1>Payload Analysis: {payload_tag}</h1>
<div class="metadata">
  <p>Architecture: {architecture} | Stream: {stream} | Generated: {timestamp}</p>
  <p>Release Controller: <a href="{release_controller_url}">{payload_tag}</a></p>
</div>

<!-- Executive summary -->
<div class="executive-summary">
  <h2>Executive Summary</h2>
  <p>{total_blocking} blocking jobs: {succeeded} passed, {failed} failed</p>
  <p>{new_failures} new failure(s), {persistent_failures} persistent failure(s)</p>
  <p>Rejected payload streak: {streak} consecutive rejected payloads</p>
</div>
```

#### 7.2: Blocking Jobs Summary Table

A table showing ALL blocking jobs with columns:
- Job Name
- Status (color-coded: green for passed, red for failed)
- Streak (how many consecutive payloads it has been failing; "N/A" for passed jobs)
- History (the failure_pattern across the lookback window, e.g., "F F F S F F", showing most recent first; use color-coded markers — red for F, green for S. Each marker should be a link to that job's Prow URL from that payload, when available from the lookback data)
- First Failed In (originating payload tag, linked to release controller)

#### 7.3: Failed Job Details

For each failed job, a collapsible section containing:

```html
<details>
  <summary class="failed-job">
    <span class="job-name">{job_name}</span>
    <span class="badge badge-{new|persistent}">{New Failure|Failing for N payloads}</span>
  </summary>
  <div class="job-detail">
    <h4>Prow Job</h4>
    <p><a href="{prow_url}">{prow_url}</a></p>

    <h4>Failure Analysis</h4>
    <div class="analysis">{analysis_from_subagent}</div>

    <!-- Only include if subagent reported known symptoms -->
    <h4>Known Symptoms Seen</h4>
    <p class="symptoms">{comma-separated symptom summaries, or omit this section if "none"}</p>
    <p class="symptoms-note"><em>Symptoms are machine-detected environmental observations, not definitive causes.</em></p>

    <h4>First Failed In</h4>
    <p><a href="{originating_payload_url}">{originating_payload_tag}</a></p>

    <h4>Candidate PRs (introduced in {originating_payload_tag})</h4>
    <table>
      <tr><th>Component</th><th>PR</th><th>Description</th><th>Bug</th></tr>
      <!-- One row per candidate PR -->
    </table>
  </div>
</details>
```

#### 7.4: Recommended Reverts

Include this section **before** the per-job details. It should immediately follow the executive summary so it is the first actionable item a reader sees.

If any revert candidates were identified in Step 6.2, show copy-paste revert instructions:

```html
<div class="revert-recommendations">
  <h2>Recommended Reverts</h2>
  <p><strong>OCP Policy: PRs that break payloads MUST be reverted.</strong> The following PRs have been
     identified with high confidence as causes of blocking job failures and must be reverted immediately
     to restore payload acceptance. Fixes can be re-landed in a follow-up PR after the revert restores
     payload health.</p>
  <table>
    <tr>
      <th>PR</th>
      <th>Component</th>
      <th>Description</th>
      <th>Caused Failure In</th>
      <th>Failing Since</th>
      <th>Rationale</th>
    </tr>
    <tr>
      <td><a href="{pr_url}">#{pr_number}</a></td>
      <td>{component}</td>
      <td>{pr_description}</td>
      <td>{job_name(s) this PR is blamed for}</td>
      <td>{originating_payload_tag} ({streak_length} payloads ago)</td>
      <td>{confidence_rationale}</td>
    </tr>
  </table>
  <!-- Automated revert instructions -->
  <h3>Automated Reverts</h3>
  <p>Download the payload results YAML and run <code>/ci:payload-revert</code> to automatically
     create TRT JIRA bugs, open revert PRs, and trigger payload validation jobs for all
     high-confidence candidates:</p>
  <div class="revert-prompt">
    <button onclick="navigator.clipboard.writeText(this.nextElementSibling.textContent.trim())">Copy</button>
    <pre>/ci:payload-revert {payload_tag}</pre>
  </div>
  <p class="revert-note">The payload results YAML (<code>payload-results-{tag}.yaml</code>) must be
     in the current working directory. If running from CI artifacts, download it first.</p>
</div>
```

Use `verdict-revert` for the revert section when there are revert candidates, and `verdict-none` when there are none. The revert prompt copy button should use the same variable-based styling:

```html
.revert-prompt {
  position: relative;
  margin: 0.75rem 0;
}
.revert-prompt pre {
  white-space: pre-wrap;
}
.revert-prompt button {
  position: absolute;
  top: 8px;
  right: 8px;
  background: var(--surface);
  color: var(--text-muted);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 12px;
}
.revert-prompt button:hover {
  border-color: var(--blue);
  color: var(--text);
}
```

If **no** revert candidates were identified, include a brief note instead:

```html
<div class="verdict verdict-none">
  <strong>No Recommended Reverts</strong>
  <p>No PRs were identified with sufficient confidence for revert recommendation.
     Failures may be caused by infrastructure issues, flaky tests, or require further investigation.</p>
</div>
```

#### 7.5: Force-Accept Recommendation

If a force-accept was recommended (Step 6.4), include a prominent callout immediately after the revert/no-revert verdict:

```html
<div class="verdict verdict-infra">
  <strong>Force-Accept Recommended</strong>
  <p>All blocking job failures are temporary infrastructure issues and no payload has been accepted
     in this stream for more than 18 hours. Consider force-accepting this payload to unblock
     the release stream.</p>
  <p class="last-accepted">Last accepted payload: <a href="{last_accepted_url}">{last_accepted_tag}</a>
     ({hours_since} hours ago)</p>
</div>
```

Use the `last_accepted_tag` from the `fetch-payloads` output (Step 2) and construct the release controller URL for the link. If `last_accepted_tag` is `null`, replace the last-accepted line with "No accepted payload found in recent history."

If a force-accept was not recommended, omit this section entirely.

#### 7.6: Styling

The HTML must be fully self-contained with embedded CSS. Use a GitHub-inspired dark mode design. Wrap all content in a `<div class="container">`. Use CSS variables for the color palette and the following base styles as a guide:

```html
<style>
  :root {
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --text-muted: #8b949e;
    --green: #3fb950;
    --red: #f85149;
    --orange: #d29922;
    --blue: #58a6ff;
    --purple: #bc8cff;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; padding: 2rem; }
  .container { max-width: 1100px; margin: 0 auto; }
  h1 { font-size: 1.8rem; margin-bottom: 0.5rem; }
  h2 { font-size: 1.4rem; margin: 1.5rem 0 0.75rem; border-bottom: 1px solid var(--border); padding-bottom: 0.4rem; }
  h3 { font-size: 1.1rem; margin: 1rem 0 0.5rem; }
  a { color: var(--blue); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .badge { display: inline-block; padding: 0.15rem 0.6rem; border-radius: 1rem; font-size: 0.8rem; font-weight: 600; }
  .badge-rejected { background: rgba(248,81,73,0.2); color: var(--red); border: 1px solid var(--red); }
  .badge-accepted { background: rgba(63,185,80,0.2); color: var(--green); border: 1px solid var(--green); }
  .badge-new { background: rgba(248,81,73,0.15); color: var(--red); }
  .badge-persistent { background: rgba(210,153,34,0.15); color: var(--orange); }
  .badge-infra { background: rgba(210,153,34,0.2); color: var(--orange); border: 1px solid var(--orange); }
  .badge-pass { background: rgba(63,185,80,0.15); color: var(--green); font-size: 0.75rem; padding: 0.1rem 0.5rem; }
  .badge-fail { background: rgba(248,81,73,0.15); color: var(--red); font-size: 0.75rem; padding: 0.1rem 0.5rem; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 0.5rem; padding: 1.25rem; margin: 1rem 0; }
  .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin: 1rem 0; }
  .stat { background: var(--surface); border: 1px solid var(--border); border-radius: 0.5rem; padding: 1rem; text-align: center; }
  .stat .num { font-size: 2rem; font-weight: 700; }
  .stat .label { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
  table { width: 100%; border-collapse: collapse; margin: 0.75rem 0; }
  th, td { padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }
  th { color: var(--text-muted); font-weight: 600; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.03em; }
  details { margin: 0.75rem 0; }
  summary { cursor: pointer; padding: 0.6rem 0.75rem; background: var(--surface); border: 1px solid var(--border); border-radius: 0.4rem; font-weight: 600; user-select: none; }
  summary:hover { border-color: var(--blue); }
  details[open] summary { border-radius: 0.4rem 0.4rem 0 0; border-bottom: 1px solid var(--border); }
  details .detail-body { border: 1px solid var(--border); border-top: 0; border-radius: 0 0 0.4rem 0.4rem; padding: 1rem; background: var(--surface); }
  pre { background: var(--bg); border: 1px solid var(--border); border-radius: 0.3rem; padding: 0.75rem; overflow-x: auto; font-size: 0.85rem; color: var(--text-muted); }
  code { font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; font-size: 0.85em; }
  .verdict { padding: 1rem; border-radius: 0.5rem; margin: 1rem 0; font-size: 0.95rem; }
  .verdict-revert { background: rgba(248,81,73,0.1); border-left: 4px solid var(--red); }
  .verdict-infra { background: rgba(210,153,34,0.1); border-left: 4px solid var(--orange); }
  .verdict-none { background: rgba(139,148,158,0.1); border-left: 4px solid var(--text-muted); }
  .candidate-prs th { font-size: 0.85rem; }
  .candidate-prs td { font-size: 0.85rem; }
  .footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border); color: var(--text-muted); font-size: 0.8rem; text-align: center; }
</style>
```

You may add additional classes as needed (e.g., history markers, timeline items, pattern groups) following the same variable-based color palette. Use `var(--red)` / `var(--green)` for fail/pass indicators, `var(--orange)` for infrastructure issues, and `var(--blue)` for links and highlights.

### Step 8: Generate JSON Data File

After generating the HTML report, use the `payload-autodl-json` skill to produce a structured JSON data file for database ingestion. The file is named `payload-analysis-<sanitized_tag>-autodl.json`.

See the `payload-autodl-json` skill for the complete schema, row cardinality rules, and field rules.

### Step 9: Save and Present

1. Save all output files to the current working directory:
   - HTML report: `payload-analysis-<sanitized_tag>-summary.html`
   - JSON data file: `payload-analysis-<sanitized_tag>-autodl.json`
   - Payload results YAML: `payload-results-<sanitized_tag>.yaml` (written in Step 6.5)
   - Sanitize the tag: replace any characters not safe for filenames

2. Tell the user:
   - The path to the saved HTML report
   - The path to the JSON data file
   - The path to the payload results YAML file
   - A brief text summary of findings (number of failures, new vs persistent, key candidate PRs)
   - Mention that downstream commands `/ci:payload-revert` and `/ci:payload-experiment` can consume the payload results YAML for automated actions

## Error Handling

### No Payloads to Analyze

If no rejected or ready-with-failures payloads are found for the given version:
```
No payloads requiring analysis found for {version} ({architecture}) in the last {limit} payloads.
The most recent payloads may all be Accepted. Try increasing --lookback or check a different version.
```

### Subagent Failure

If a subagent fails to analyze a job, include the job in the report with a note:
```
Analysis unavailable: {error_message}
```

Do not let one failed subagent block the entire report.

### Network Errors

If the release controller or Sippy API is unreachable, report the error clearly and exit.

## Notes

- The lookback examines the job across **all payloads in the lookback window**, regardless of phase. A job may have a pattern like F-F-F-S-F-F-F due to flaky behavior — the lookback captures the full history so the report can distinguish persistent/intermittent failures from new regressions.
- Subagents should perform a **thorough analysis** — do not skip steps like must-gather extraction to save time. A proper root cause analysis is more important than speed.
- The HTML report is fully self-contained — no external CSS/JS dependencies.
- For very large numbers of failed jobs (>8), consider whether some share the same underlying failure and group them in the report.

## See Also

- Related Skill: `payload-results-yaml` - Schema for the results YAML
- Related Skill: `payload-autodl-json` - Schema for the autodl JSON data file
- Related Skill: `fetch-payloads` - Fetches payload data from release controller
- Related Skill: `fetch-new-prs-in-payload` - Fetches PRs new in a payload
- Related Command: `/ci:payload-revert` - Stages reverts for high-confidence candidates
- Related Command: `/ci:payload-experiment` - Tests medium-confidence candidates experimentally
