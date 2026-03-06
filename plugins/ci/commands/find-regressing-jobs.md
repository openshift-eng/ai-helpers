---
description: Query Sippy for regressing CI jobs and rank them by severity
argument-hint: "<release> [--period twoDay|default] [--min-runs 5] [--limit 20]"
---

## Name

ci:find-regressing-jobs

## Synopsis

```
/ci:find-regressing-jobs <release> [--period twoDay|default] [--min-runs 5] [--limit 20]
```

## Description

The `ci:find-regressing-jobs` command queries the public Sippy API for jobs that are regressing in a given OpenShift release. It returns a ranked table of jobs sorted by net regression (worst first), highlighting jobs that need immediate investigation.

This is the starting point for CI problem hunting -- it answers "what's broken right now?" for a release.

### Key Features

- **Public API**: Uses `sippy.dptools.openshift.org` -- no authentication required
- **Smart filtering**: Excludes `never-stable` jobs that have never been expected to pass
- **Regression ranking**: Sorts by `net_improvement` (most negative first) to surface the worst regressions
- **Bug awareness**: Flags jobs that already have open bugs tracked in Jira
- **Actionable output**: Highlights jobs meeting investigation criteria for downstream skills

## Implementation

Load the "Find Regressing Jobs" skill and follow its implementation steps.

## Return Value

- **Format**: Markdown table to stdout + structured summary
- **Columns**: Job name, current %, previous %, delta, runs, open bugs, variants
- **Flags**:
  - Jobs with `open_bugs > 0` marked as "already tracked"
  - Jobs with `current_pass_percentage < 50%` AND `net_improvement < -20` marked as "needs investigation"

## Examples

1. **Find regressions in 4.22 (defaults: 2-day period, min 5 runs, top 20)**:
   ```
   /ci:find-regressing-jobs 4.22
   ```

2. **Use default period with higher minimum runs**:
   ```
   /ci:find-regressing-jobs 4.22 --min-runs 10
   ```

3. **Get more results**:
   ```
   /ci:find-regressing-jobs 4.21 --limit 50
   ```

## Arguments

- $1: OpenShift release version (required, e.g., "4.22", "4.21")
- `--period`: Time period for comparison (optional, default: "twoDay"). Options: "twoDay", "default"
- `--min-runs`: Minimum number of runs to include a job (optional, default: 5)
- `--limit`: Maximum number of jobs to return (optional, default: 20)

## Skills Used

- `find-regressing-jobs`: Queries Sippy API and processes results
