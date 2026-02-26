---
name: Analyze Payload
description: Analyze a rejected or in-progress payload with historical lookback to identify root causes of blocking job failures and produce an HTML report
---

# Analyze Payload

This skill analyzes a payload for a given OCP version, walks back through consecutive rejected payloads to determine when each failure started, correlates failures with newly introduced PRs, investigates each failed job in parallel, and produces a comprehensive HTML report.

It supports both **Rejected** payloads (full analysis of all failed blocking jobs) and **Ready** payloads (early analysis of blocking jobs that have already failed, with a determination of whether the payload is on track for rejection).

## When to Use This Skill

Use this skill when you need to:

- Understand why a payload was rejected
- Assess whether an in-progress ("Ready") payload is likely to be rejected based on already-failed blocking jobs
- Determine whether failures are new or persistent (permafailing)
- Identify which PRs likely caused new failures
- Get a comprehensive overview of payload health with actionable root cause analysis

## Prerequisites

1. **Network Access**: Must be able to reach:
   - OpenShift release controller (`amd64.ocp.releases.ci.openshift.org`)
   - Sippy API (`sippy.dptools.openshift.org`)
   - Prow (`prow.ci.openshift.org`)
2. **Python 3**: For running fetch scripts
3. **gcloud CLI**: For downloading Prow job artifacts

## Implementation Steps

### Step 1: Parse Arguments

The first argument can be either a **full payload tag** (e.g., `4.22.0-0.nightly-2026-02-25-152806`) or just a **version** (e.g., `4.22`). Detect which by checking if it matches the pattern `X.Y.0-0.<stream>-YYYY-MM-DD-HHMMSS`.

**If a full payload tag is provided**, parse from it:
- `tag`: The specific payload tag to analyze
- `version`: Extract from the tag (e.g., `4.22` from `4.22.0-0.nightly-...`)
- `stream`: Extract from the tag (e.g., `nightly` from `4.22.0-0.nightly-...`)
- `architecture`: From the second argument (default: `amd64`)
- `lookback`: From `--lookback N` (default: `10`)

**If a version is provided** (or nothing):
- `version`: OCP version (e.g., `4.22`). If not provided, use `fetch_payloads.py` with no version arg to auto-detect.
- `architecture`: CPU architecture (default: `amd64`)
- `stream`: Release stream (default: `nightly`) — nightly, ci
- `lookback`: Max number of rejected payloads to walk back through (default: `10`)

### Step 2: Fetch Recent Payloads

Fetch recent payloads without filtering by phase, so the full payload history is available for analysis and lookback:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch-payloads/fetch_payloads.py <architecture> <version> <stream> --limit <lookback * 2>
```

Parse the output to extract payload tag names, phases, and job details.

Identify the **target payload**:
- If a specific tag was provided in Step 1, use that payload as the target.
- Otherwise, select the most recent payload that is either **Rejected** or **Ready** (with at least one failed blocking job).

Based on the target payload's phase:

- **Rejected**: Extract all failed blocking job names and their Prow URLs. Proceed with full analysis.
- **Ready**: Extract blocking jobs that have already **failed** (with their Prow URLs). These are jobs that will not pass — they indicate the payload is on track for rejection. Proceed with analysis of those failed jobs and note in the report that the payload is still in progress.
- **Accepted**: Report "Payload was accepted, no analysis needed" and exit.

### Step 3: Build Failure History (Lookback)

The goal is to determine **when each failing job first started failing** in the chain of consecutive rejected payloads.

Using the full payload list from Step 2 (which includes all phases):

1. Starting from the target payload, collect the set of failed blocking jobs.
2. Walk backwards through consecutive rejected payloads (up to `lookback` limit).
3. For each failed job in the target payload, check whether it also failed in the previous rejected payload.
4. Continue until either:
   - The job was NOT failing in an earlier payload (meaning you found the originating payload)
   - You reach a non-rejected (Accepted) payload
   - You exhaust the lookback window

For each failed job, record:
- **streak_length**: How many consecutive rejected payloads it has been failing in
- **originating_payload**: The first payload in the streak where this job started failing
- **is_new_failure**: Whether the job first started failing in the latest payload

### Step 4: Fetch New PRs in Originating Payloads

For each unique originating payload identified in Step 3, fetch the PRs that were new in that payload:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch-new-prs-in-payload/fetch_new_prs_in_payload.py <originating_payload_tag> --format json
```

Store the PR data keyed by originating payload tag. These PRs are the **suspects** for the failures that started in that payload.

### Step 5: Investigate Each Failed Job in Parallel

For each failed blocking job in the **target payload**, launch a **parallel subagent** (using the Task tool) to investigate the failure. Use the Prow URL from Step 2.

Each subagent should determine whether the failure is an install failure or a test failure by checking the JUnit results (e.g., look for `install should succeed*` test failures), then use the appropriate analysis skill. Almost all blocking jobs install a cluster and then run tests, so the job name alone does not tell you the failure type.

Instruct each subagent as follows:

> Analyze the failure at <prow_url>. First, check the JUnit results or build log to determine whether this is an install failure (look for `install should succeed: overall` or similar install-related test failures) or a test failure (install passed, specific tests failed).
>
> Based on the failure type, use the appropriate skill:
> - **Install failure**: Use the `ci:prow-job-analyze-install-failure` skill. For metal/bare-metal jobs (job name contains "metal"), perform additional analysis using the `ci:prow-job-analyze-metal-install-failure` skill as needed for dev-scripts, Metal3/Ironic, and BareMetalHost-specific diagnostics.
> - **Test failure**: Use the `ci:prow-job-analyze-test-failure` skill.
>
> Return a concise summary including: failure type (install vs test), root cause, key error messages, and any relevant log excerpts. Do not ask user questions. Keep the output concise for inclusion in a summary report.

**Important**: Launch ALL subagents in parallel (single message with multiple Task tool calls) for maximum speed. Each subagent should be given `subagent_type: "general-purpose"`.

### Step 6: Collect Investigation Results and Identify Revert Candidates

Wait for all subagents to complete and collect their analysis results. For each failed job, you should now have:

- **Job name**
- **Prow URL**
- **Failure analysis** (from subagent)
- **Streak length** (from Step 3)
- **Originating payload** (from Step 3)
- **Suspect PRs** (from Step 4)

#### 6.1: Correlate Failures with Suspect PRs

For each failed job, cross-reference the failure analysis from the subagent with the suspect PRs from the originating payload. Look for strong correlations:

- **Component match**: The failure involves a component (operator, controller, API) that was modified by a suspect PR
- **Error message match**: Error messages or stack traces reference code, packages, or functionality changed by a suspect PR
- **Temporal match**: The job was passing before the originating payload and started failing exactly when the suspect PR landed
- **Single suspect**: Only one PR landed in the originating payload that touches the affected component

#### 6.2: Propose Revert Candidates

For each suspect PR where you have **high confidence (>= 90%)** that it caused the regression, mark it as a **revert candidate**. A PR qualifies as a revert candidate when:

1. **The failure clearly maps to the PR's changes** — e.g., the error stack trace references the exact code changed, or the failing component is the one modified by the PR
2. **The timing is exact** — the job was passing in the payload before the originating payload and started failing in the originating payload
3. **No other plausible explanation** — infrastructure flakiness, quota issues, or unrelated platform problems have been ruled out by the subagent analysis

For each revert candidate, record:
- **PR URL**: The GitHub pull request URL
- **PR description**: Title/summary of the PR
- **Component**: The affected component
- **Confidence**: Your confidence level (e.g., "High — error directly references code changed by this PR")
- **Rationale**: A 1-2 sentence explanation of why this PR is the likely cause

**Do NOT propose reverts for**:
- Infrastructure failures (cloud quota, API rate limits, network issues)
- Flaky tests that also fail intermittently on accepted payloads
- Jobs where the failure analysis is inconclusive or the root cause is unclear
- PRs where the correlation is circumstantial (e.g., same component but unrelated code path)

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

    <h4>First Failed In</h4>
    <p><a href="{originating_payload_url}">{originating_payload_tag}</a></p>

    <h4>Suspect PRs (introduced in {originating_payload_tag})</h4>
    <table>
      <tr><th>Component</th><th>PR</th><th>Description</th><th>Bug</th></tr>
      <!-- One row per suspect PR -->
    </table>
  </div>
</details>
```

#### 7.4: Recommended Reverts

If any revert candidates were identified in Step 6.2, include a prominent section **before** the per-job details. This section should immediately follow the executive summary so it is the first actionable item a reader sees.

```html
<div class="revert-recommendations">
  <h2>Recommended Reverts</h2>
  <p>The following PRs have been identified with high confidence as causes of blocking job failures.
     Consider reverting them to restore payload acceptance.</p>
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
  <p class="revert-note">To revert a PR, use: <code>/ci:revert-pr &lt;pr-url&gt; &lt;jira-ticket&gt;</code></p>
</div>
```

If **no** revert candidates were identified, include a brief note instead:

```html
<div class="revert-recommendations revert-none">
  <h2>Recommended Reverts</h2>
  <p>No PRs were identified with sufficient confidence for revert recommendation.
     Failures may be caused by infrastructure issues, flaky tests, or require further investigation.</p>
</div>
```

Add the following styles for the revert section:

```html
.revert-recommendations {
  background: white;
  border-left: 4px solid #d93025;
  padding: 16px 20px;
  margin: 20px 0;
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.revert-recommendations h2 {
  color: #d93025;
  border-bottom: none;
}
.revert-none {
  border-left-color: #5f6368;
}
.revert-none h2 {
  color: #5f6368;
}
.revert-note {
  margin-top: 12px;
  font-size: 13px;
  color: #5f6368;
}
.revert-note code {
  background: #f1f3f4;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 12px;
}
```

#### 7.5: Styling

The HTML must be fully self-contained with embedded CSS. Use a clean, professional design:

```html
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
    background: #f5f5f5;
    color: #333;
  }
  .executive-summary {
    background: white;
    border-left: 4px solid #1a73e8;
    padding: 16px 20px;
    margin: 20px 0;
    border-radius: 4px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }
  table {
    width: 100%;
    border-collapse: collapse;
    background: white;
    border-radius: 4px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }
  th {
    background: #f8f9fa;
    padding: 12px 16px;
    text-align: left;
    font-weight: 600;
    border-bottom: 2px solid #dee2e6;
  }
  td {
    padding: 10px 16px;
    border-bottom: 1px solid #eee;
  }
  .status-passed { color: #1e8e3e; font-weight: 600; }
  .status-failed { color: #d93025; font-weight: 600; }
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
    margin-left: 8px;
  }
  .badge-new { background: #fce8e6; color: #d93025; }
  .badge-persistent { background: #fef7e0; color: #e37400; }
  details {
    background: white;
    margin: 12px 0;
    border-radius: 4px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }
  details summary {
    padding: 14px 20px;
    cursor: pointer;
    font-weight: 500;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  details summary:hover { background: #f8f9fa; }
  .job-detail {
    padding: 0 20px 20px;
    border-top: 1px solid #eee;
  }
  .analysis {
    background: #f8f9fa;
    padding: 16px;
    border-radius: 4px;
    white-space: pre-wrap;
    font-family: 'SFMono-Regular', Consolas, monospace;
    font-size: 13px;
    overflow-x: auto;
  }
  a { color: #1a73e8; text-decoration: none; }
  a:hover { text-decoration: underline; }
  h1 { color: #202124; }
  h2 { color: #3c4043; border-bottom: 1px solid #eee; padding-bottom: 8px; }
  .metadata { color: #5f6368; font-size: 14px; }
  .suspect-prs th { font-size: 13px; }
  .suspect-prs td { font-size: 13px; }
</style>
```

### Step 8: Save and Present

1. Save the HTML file to the current working directory:
   - Filename: `payload-analysis-<sanitized_tag>-summary.html`
   - Sanitize the tag: replace any characters not safe for filenames

2. Tell the user:
   - The path to the saved HTML report
   - A brief text summary of findings (number of failures, new vs persistent, key suspect PRs)

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

- The lookback only examines **consecutive** rejected payloads. If an Accepted payload breaks the chain, the lookback stops there.
- Subagents should run in **fast mode** (skip optional prompts like must-gather extraction) to keep analysis time reasonable.
- The HTML report is fully self-contained — no external CSS/JS dependencies.
- For very large numbers of failed jobs (>8), consider whether some share the same underlying failure and group them in the report.
