---
name: Hunt Problems
description: End-to-end CI problem hunting -- find regressions, investigate, and fix
---

# Hunt Problems

This skill is the top-level orchestrator for CI problem hunting. It finds regressing jobs, investigates the worst ones in parallel, generates a master report, and optionally fixes what it can.

## When to Use This Skill

Use this skill when you need to:

- Do a full CI triage session for a release
- Find, investigate, and fix regressions end-to-end
- Generate a comprehensive CI health report
- Proactively hunt for problems before they block payloads

## Prerequisites

1. **Network Access**: Must be able to reach Sippy, Prow, Jira, and GitHub
2. **gcloud CLI**: For downloading Prow job artifacts
3. **GitHub CLI (`gh`)**: For creating PRs (only needed with `--fix`)
4. **Jira MCP**: For searching/creating bugs (only needed with `--fix`)
5. **Python 3**: For API requests

## Implementation Steps

### Step 1: Parse Arguments

Parse the command arguments:

- `release` (required): OpenShift version (e.g., "4.22")
- `--count` (optional, default: 5): Number of jobs to investigate
- `--fix` (optional, default: false): Whether to attempt fixes after investigation

### Step 2: Find Regressing Jobs

Execute the `find-regressing-jobs` skill with the provided release:

- Use default parameters: `--period twoDay --min-runs 5 --limit 50`
- Request more results than `--count` to have selection candidates (use limit=50)

Capture both the markdown table output and the structured `REGRESSING_JOBS_DATA` block.

### Step 3: Select Candidates for Investigation

From the regression results, select the top N jobs (where N = `--count`) based on these criteria:

1. **Must meet threshold**: `current_pass_percentage < 50%` AND `net_improvement < -20`
2. **Prefer untracked**: Jobs with `open_bugs == 0` get priority (fresh problems)
3. **Include severely regressing tracked jobs**: Up to 2 jobs with `open_bugs > 0` if `net_improvement < -40` (existing bug may be stale or wrong)
4. **Sort by severity**: Among qualifying jobs, sort by `net_improvement` ascending (worst first)

If fewer than N jobs meet the criteria, investigate all that qualify.

### Step 4: Present Selection and Confirm

Show the user the selected jobs in a summary table:

```markdown
## Selected Jobs for Investigation

| # | Job | Current % | Delta | Open Bugs | Why Selected |
|---|-----|-----------|-------|-----------|--------------|
| 1 | {name} | {pct}% | {delta} | {bugs} | {reason} |
```

Where `reason` is one of:
- "Untracked regression" (no open bugs, meets threshold)
- "Severe regression despite existing bug" (has bugs but net_improvement < -40)

Ask the user: "Proceed with investigating these {N} jobs? (y/n)"

Wait for confirmation before proceeding. If the user wants to modify the selection, adjust accordingly.

### Step 5: Investigate in Parallel

Launch parallel `investigate-job` agents for all selected jobs using the Agent tool.

For each job, create a subagent with:
- `subagent_type`: "general-purpose"
- Task: Run the `investigate-job` skill with the job name and release
- Each agent produces an HTML report and structured `INVESTIGATION_RESULT`

**Important**: Run all investigations in parallel (all Agent calls in a single message) since they are independent.

Collect results from all agents. For any agent that fails, note the failure and continue.

### Step 6: Generate Master HTML Report

Create a comprehensive master report saved as `hunt-{release}-{date}.html`.

Report structure:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CI Problem Hunt: {release} - {date}</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #e0e0e0; margin: 0; padding: 20px; }
  .container { max-width: 1400px; margin: 0 auto; }
  h1 { color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 10px; }
  h2 { color: #7dd3fc; margin-top: 30px; }
  h3 { color: #a5b4fc; }
  .executive-summary { background: #16213e; border-radius: 8px; padding: 20px; margin: 20px 0; border-left: 4px solid #00d4ff; }
  .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 16px 0; }
  .stat-card { background: #0f172a; border-radius: 8px; padding: 16px; text-align: center; }
  .stat-value { font-size: 2em; font-weight: 700; color: #00d4ff; }
  .stat-label { color: #94a3b8; font-size: 0.9em; margin-top: 4px; }
  .job-section { background: #16213e; border-radius: 8px; padding: 20px; margin: 20px 0; }
  .fixability-high { border-left: 4px solid #4ade80; }
  .fixability-medium { border-left: 4px solid #fbbf24; }
  .fixability-low { border-left: 4px solid #f87171; }
  .badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 0.85em; font-weight: 600; }
  .badge-high { background: #065f46; color: #4ade80; }
  .badge-medium { background: #78350f; color: #fbbf24; }
  .badge-low { background: #7f1d1d; color: #f87171; }
  .badge-infra { background: #1e3a5f; color: #7dd3fc; }
  .badge-product { background: #5b21b6; color: #c4b5fd; }
  .badge-test { background: #3f3f46; color: #d4d4d8; }
  table { width: 100%; border-collapse: collapse; margin: 15px 0; }
  th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #2d2d44; }
  th { background: #0f172a; color: #7dd3fc; }
  tr:hover { background: #1e293b; }
  a { color: #00d4ff; text-decoration: none; }
  a:hover { text-decoration: underline; }
  details { margin: 10px 0; }
  summary { cursor: pointer; color: #7dd3fc; font-weight: 600; padding: 8px; }
  .action-plan { background: #0f172a; border: 2px solid #00d4ff; border-radius: 8px; padding: 20px; margin: 20px 0; }
  .action-item { padding: 8px 0; border-bottom: 1px solid #2d2d44; }
  .action-item:last-child { border-bottom: none; }
</style>
</head>
<body>
<div class="container">
  <h1>CI Problem Hunt: {release}</h1>
  <p>Generated: {date}</p>

  <!-- Executive Summary -->
  <div class="executive-summary">
    <h2>Executive Summary</h2>
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-value">{total_regressing}</div>
        <div class="stat-label">Total Regressing Jobs</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{investigated_count}</div>
        <div class="stat-label">Investigated</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{high_fix_count}</div>
        <div class="stat-label">High Fixability</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{medium_fix_count}</div>
        <div class="stat-label">Medium Fixability</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{low_fix_count}</div>
        <div class="stat-label">Low Fixability</div>
      </div>
    </div>
  </div>

  <!-- Full Regression Table -->
  <h2>All Regressing Jobs</h2>
  <table>
    <tr><th>#</th><th>Job</th><th>Current %</th><th>Prev %</th><th>Delta</th><th>Runs</th><th>Bugs</th><th>Status</th></tr>
    <!-- rows from find-regressing-jobs -->
  </table>

  <!-- Per-Job Investigation Sections -->
  <h2>Investigation Results</h2>
  <!-- For each investigated job: -->
  <div class="job-section fixability-{fixability}">
    <h3>{job_short_name}</h3>
    <p>
      <span class="badge badge-{classification}">{classification}</span>
      <span class="badge badge-{fixability}">{fixability} fixability</span>
      | Pass rate: {pct}% | Delta: {delta}
    </p>
    <p><strong>Root Cause:</strong> {root_cause}</p>
    <p><strong>Proposed Fix:</strong> {proposed_fix}</p>
    <details>
      <summary>Full Investigation Details</summary>
      <!-- Embedded content from individual investigation -->
    </details>
  </div>

  <!-- Action Plan -->
  <div class="action-plan">
    <h2>Action Plan</h2>
    <h3>Fix Now (High Fixability)</h3>
    <!-- List of high-fixability jobs with proposed fixes -->
    <h3>Fix Soon (Medium Fixability)</h3>
    <!-- List of medium-fixability jobs with proposed fixes -->
    <h3>Needs Product Team Attention (Low Fixability)</h3>
    <!-- List of low-fixability jobs with root causes -->
  </div>

  <!-- Actions Taken (only if --fix was used) -->
  <!-- <h2>Actions Taken</h2> -->
  <!-- <table with bugs filed and PRs opened> -->
</div>
</body>
</html>
```

All `<a>` links must use `target="_blank"` to open in a new tab.

### Step 7: Fix Mode (Optional)

If `--fix` flag is set, for each investigated job with High or Medium fixability:

1. Run the `fix-job` skill **sequentially** (not in parallel -- fixes may need user interaction for PRs)
2. Order: High fixability first, then Medium
3. For each fix attempt, record:
   - Bug filed (or existing bug found)
   - PR opened (or manual fix needed)
4. Update the master HTML report with an "Actions Taken" section

### Step 8: Final Summary

Output a text summary to stdout:

```markdown
## Hunt Complete: {release}

### Report
- Master report: {html_file_path}
- Individual reports: {list of per-job html files}

### Findings
- {investigated_count} jobs investigated
- {high_count} high fixability, {medium_count} medium, {low_count} low
- {classification_breakdown}

### Actions Taken
- Bugs filed: {count} ({list of OCPBUGS keys})
- PRs opened: {count} ({list of PR URLs})
- Manual attention needed: {count} jobs
```

## Error Handling

1. **No regressing jobs found**: Report that CI looks healthy for this release. Generate a minimal report confirming good health.
2. **No jobs meet investigation criteria**: Report the regression table but note that no jobs are severe enough for investigation. Lower the threshold suggestion.
3. **Investigation agent failures**: Note which jobs failed to investigate, continue with successful ones. Include partial results in the report.
4. **Fix failures**: Note which fixes failed, continue with remaining. Include all results in the report.

## Notes

- The skill uses parallel subagents for investigation (Step 5) but sequential execution for fixes (Step 7) because fixes may require user interaction.
- The `--count` default of 5 is a good balance between thoroughness and time. Each investigation takes 2-5 minutes.
- The master report embeds summaries from individual investigations, not full reports. Individual HTML reports are saved separately for deep-dives.
- The selection algorithm (Step 3) prefers untracked regressions because those are the most actionable -- nobody is looking at them yet.
- Severely regressing jobs with existing bugs are still investigated (up to 2) because the bug may be stale or the failure may have a different root cause than what's tracked.

## See Also

- Related Command: `/ci:hunt-problems` - The user-facing command
- Related Skill: `find-regressing-jobs` - Step 1: find regressions
- Related Skill: `investigate-job` - Step 2: investigate each job
- Related Skill: `fix-job` - Step 3: file bugs and open PRs
