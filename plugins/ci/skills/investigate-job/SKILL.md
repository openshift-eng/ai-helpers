---
name: Investigate Job
description: Deep-dive a single failing CI job to identify root cause and assess fixability
---

# Investigate Job

This skill performs a comprehensive investigation of a single failing CI job, analyzing multiple recent runs, synthesizing root causes, and assessing fixability.

## When to Use This Skill

Use this skill when you need to:

- Understand why a specific CI job is failing
- Determine the root cause of a regression
- Assess whether a failure is fixable and estimate complexity
- Generate a detailed investigation report for a job

## Prerequisites

1. **Network Access**: Must be able to reach `sippy.dptools.openshift.org` and Prow artifact storage
2. **gcloud CLI**: For downloading Prow job artifacts (used by analysis subagents)
3. **Python 3**: For URL encoding in API requests

## Implementation Steps

### Step 1: Parse Arguments

Parse the command arguments:

- `job_name` (required): Full Prow job name (e.g., `periodic-ci-openshift-release-main-nightly-4.22-e2e-vsphere-ovn-techpreview`)
- `release` (required): OpenShift version (e.g., "4.22")

### Step 2: Fetch Job Summary from Sippy

Query the Sippy jobs API to get summary statistics for this specific job:

```
GET https://sippy.dptools.openshift.org/api/jobs?release={release}&period=twoDay&sortField=net_improvement&sort=asc&perPage=1&page=0&filter={filter_json}
```

Filter JSON:

```json
{
  "items": [
    {
      "columnField": "name",
      "operatorValue": "equals",
      "value": "{job_name}"
    }
  ]
}
```

Extract from the response:
- `current_pass_percentage`, `previous_pass_percentage`, `net_improvement`
- `current_runs`, `open_bugs`
- `variants`

If the job is not found, try a `contains` filter instead of `equals` in case of partial name match.

### Step 3: Fetch Recent Runs from Sippy

Query the Sippy job runs API to get the last 5 runs:

```
GET https://sippy.dptools.openshift.org/api/jobs/runs?release={release}&filter={filter_json}&sortField=timestamp&sort=desc&perPage=5&page=0
```

Filter JSON:

```json
{
  "items": [
    {
      "columnField": "job",
      "operatorValue": "equals",
      "value": "{job_name}"
    }
  ]
}
```

Each run object contains:
- `url`: Prow job URL (e.g., `https://prow.ci.openshift.org/view/gs/...`)
- `id` or `prow_id`: Unique run identifier
- `test_failures`: Number of test failures
- `test_flakes`: Number of test flakes
- `failed_test_names`: Array of failed test names
- `cluster`: Cluster where the job ran
- `timestamp`: When the run completed
- `overall_result`: "S" (success), "F" (failure), etc.

### Step 4: Classify Failure Type

Examine the failed runs to determine the failure type:

1. **Install failure**: If `failed_test_names` includes any test containing "install should succeed", "Infrastructure setup", or similar install-related test names
2. **Metal install failure**: If the job name contains "metal" AND it's an install failure
3. **Test failure**: All other failures (specific tests failing after successful install)

If runs show a mix of failure types, use the most common one. Note mixed failures in the report.

### Step 5: Analyze Failed Runs

Select 2-3 recent failed runs (where `overall_result` is "F") for detailed analysis.

For each failed run, launch a subagent using the Agent tool with the appropriate analysis skill:

- **Test failures**: Use the `ci:analyze-prow-job-test-failure` skill
  - Provide the Prow URL and the most common failing test name
  - Use `--fast` mode to skip must-gather (we're analyzing multiple runs)
- **Install failures**: Use the `ci:analyze-prow-job-install-failure` skill
  - Provide the Prow URL
- **Metal install failures**: Use the `ci:analyze-prow-job-metal-install-failure` skill
  - Provide the Prow URL

**Run subagents in parallel** for independent runs to save time.

Each subagent should return:
- Error messages and stack traces
- Root cause hypothesis
- Affected component(s)
- Whether the failure appears to be infrastructure or product related

### Step 6: Synthesize Findings

Combine the results from all analyzed runs:

1. **Identify consistent patterns**: Are the same errors appearing across runs? Same component? Same error messages?
2. **Classify root cause**:
   - **infra**: Cloud provider issues, resource limits, network flakiness, CI infrastructure problems
   - **product**: Bug in an OpenShift component (code change, regression)
   - **test**: Test itself is broken, flaky, or has incorrect expectations
3. **Determine root cause description**: One-paragraph summary of what's going wrong and why

### Step 7: Assess Fixability

Rate the fixability based on the root cause:

- **High**: Fix is in `openshift/release` (config change, test skip, workflow update) or a simple component fix (1-2 files, clear root cause). Examples:
  - Test needs to be skipped for a platform/variant
  - CI configuration needs updating
  - Simple code fix (off-by-one, wrong constant, missing nil check)
  - Step registry change needed

- **Medium**: Fix requires a component change but root cause is understood and change is moderate complexity. Examples:
  - IPv6 binding bug (wrong listen address)
  - Missing feature gate handling
  - Incorrect API field usage
  - Test needs refactoring (not just a skip)

- **Low**: Requires deep product changes, unclear root cause, or infrastructure issue outside our control. Examples:
  - Cloud provider API changes
  - Deep architectural issues
  - Intermittent race conditions with no clear fix
  - Infrastructure capacity problems

### Step 8: Generate HTML Report

Create a self-contained, dark-mode HTML report saved to the current directory as `investigate-{job-short-name}-{date}.html`.

The `job-short-name` is derived by removing common prefixes like `periodic-ci-openshift-release-main-nightly-{version}-`.

Report structure:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Investigation: {job_short_name}</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #e0e0e0; margin: 0; padding: 20px; }
  .container { max-width: 1200px; margin: 0 auto; }
  h1 { color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 10px; }
  h2 { color: #7dd3fc; margin-top: 30px; }
  .summary-card { background: #16213e; border-radius: 8px; padding: 20px; margin: 20px 0; border-left: 4px solid #00d4ff; }
  .fixability-high { border-left-color: #4ade80; }
  .fixability-medium { border-left-color: #fbbf24; }
  .fixability-low { border-left-color: #f87171; }
  .badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 0.85em; font-weight: 600; }
  .badge-high { background: #065f46; color: #4ade80; }
  .badge-medium { background: #78350f; color: #fbbf24; }
  .badge-low { background: #7f1d1d; color: #f87171; }
  .badge-infra { background: #1e3a5f; color: #7dd3fc; }
  .badge-product { background: #5b21b6; color: #c4b5fd; }
  .badge-test { background: #3f3f46; color: #d4d4d8; }
  table { width: 100%; border-collapse: collapse; margin: 15px 0; }
  th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #2d2d44; }
  th { background: #16213e; color: #7dd3fc; }
  tr:hover { background: #1e293b; }
  .run-analysis { background: #0f172a; border-radius: 8px; padding: 16px; margin: 12px 0; border: 1px solid #2d2d44; }
  pre { background: #0a0a1a; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 0.9em; }
  a { color: #00d4ff; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .error-msg { color: #f87171; font-family: monospace; }
  details { margin: 10px 0; }
  summary { cursor: pointer; color: #7dd3fc; font-weight: 600; padding: 8px; }
  summary:hover { color: #00d4ff; }
</style>
</head>
<body>
<div class="container">
  <h1>Investigation: {job_short_name}</h1>
  <p>Generated: {date} | Release: {release}</p>

  <!-- Job Summary Card -->
  <div class="summary-card">
    <h2>Job Summary</h2>
    <table>
      <tr><th>Full Name</th><td>{job_name}</td></tr>
      <tr><th>Current Pass Rate</th><td>{current_pass_percentage}%</td></tr>
      <tr><th>Previous Pass Rate</th><td>{previous_pass_percentage}%</td></tr>
      <tr><th>Regression</th><td>{net_improvement}</td></tr>
      <tr><th>Runs (current period)</th><td>{current_runs}</td></tr>
      <tr><th>Open Bugs</th><td>{open_bugs}</td></tr>
      <tr><th>Variants</th><td>{variants}</td></tr>
    </table>
  </div>

  <!-- Root Cause -->
  <div class="summary-card fixability-{fixability}">
    <h2>Root Cause</h2>
    <p><span class="badge badge-{classification}">{classification}</span>
       <span class="badge badge-{fixability}">{fixability} fixability</span></p>
    <p>{root_cause_description}</p>
    <h3>Proposed Fix</h3>
    <p>{proposed_fix}</p>
  </div>

  <!-- Recent Runs -->
  <h2>Analyzed Runs</h2>
  <!-- For each analyzed run: -->
  <div class="run-analysis">
    <h3>Run: {timestamp}</h3>
    <p><a href="{prow_url}" target="_blank">Prow Link</a> | Result: {result} | Failed tests: {count}</p>
    <details>
      <summary>Analysis Details</summary>
      <div>{subagent_analysis_summary}</div>
    </details>
  </div>

  <!-- Existing Bugs -->
  <h2>Existing Bugs</h2>
  <p>{existing_bugs_or_none}</p>
</div>
</body>
</html>
```

All `<a>` links must use `target="_blank"` to open in a new tab.

### Step 9: Output Structured Result

After saving the HTML report, print the structured investigation result to stdout:

```
INVESTIGATION_RESULT:
  job_name: {full_job_name}
  root_cause: {root_cause_description}
  classification: {infra|product|test}
  fixability: {high|medium|low}
  proposed_fix: {proposed_fix_description}
  existing_bugs: {bug_urls_or_none}
  report_file: {html_file_path}
```

This structured block is used by downstream skills like `fix-job` and `hunt-problems`.

## Error Handling

1. **Job not found in Sippy**: Report that the job was not found. Suggest checking the job name.
2. **No failed runs**: If all recent runs passed, report that the job appears healthy now. Still generate a minimal report.
3. **Subagent failure**: If a subagent fails to analyze a run, note the failure and continue with remaining runs. Synthesize from whatever data is available.
4. **Network errors**: Report the error and suggest retrying.

## Notes

- The skill uses `--fast` mode for test failure analysis by default since it's analyzing multiple runs. The goal is pattern identification, not deep single-run analysis.
- When analyzing metal jobs, both `prow-job-analyze-metal-install-failure` and `prow-job-analyze-install-failure` may be useful -- the metal skill handles dev-scripts specific artifacts.
- The fixability assessment is a judgment call based on the root cause. When in doubt, rate as Medium.
- The HTML report is self-contained (no external CSS/JS dependencies) for easy sharing.

## See Also

- Related Command: `/ci:investigate-job` - The user-facing command
- Related Skill: `find-regressing-jobs` - Find jobs to investigate
- Related Skill: `fix-job` - Take action on investigated jobs
- Related Skill: `prow-job-analyze-test-failure` - Test failure analysis
- Related Skill: `prow-job-analyze-install-failure` - Install failure analysis
- Related Skill: `prow-job-analyze-metal-install-failure` - Metal install failure analysis
