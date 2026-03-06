---
description: End-to-end CI problem hunting -- find regressions, investigate, and fix
argument-hint: "<release> [--count 5] [--fix]"
---

## Name

ci:hunt-problems

## Synopsis

```
/ci:hunt-problems <release> [--count 5] [--fix]
```

## Description

The `ci:hunt-problems` command is the top-level orchestrator that ties together the entire CI problem hunting workflow. It finds regressing jobs, investigates the worst ones, and optionally fixes what it can.

This is the "do everything" command -- it answers "find what's broken, figure out why, and fix it."

### Key Features

- **Automated discovery**: Uses `find-regressing-jobs` to identify the worst regressions
- **Smart selection**: Prioritizes jobs without existing bugs, but includes severely regressing jobs even with bugs
- **Parallel investigation**: Launches multiple `investigate-job` agents in parallel
- **Master report**: Generates a comprehensive HTML report with all findings
- **Optional fix mode**: With `--fix`, attempts to file bugs and open PRs for fixable issues

### Workflow

1. Query Sippy for regressing jobs
2. Select top N candidates for investigation
3. Present selection to user for confirmation
4. Investigate all selected jobs in parallel
5. Generate master HTML report
6. If `--fix`: run `fix-job` for High/Medium fixability jobs

## Implementation

Load the "Hunt Problems" skill and follow its implementation steps.

## Return Value

- **Format**: Master HTML report + per-job investigation reports
- **Filename**: `hunt-{release}-{date}.html`
- **Contents**:
  - Executive summary: N investigated, fixability breakdown
  - Full regression table from Sippy
  - Per-job investigation sections
  - Action plan: which jobs to fix, which need product team attention
  - Links to filed bugs and opened PRs (if `--fix` was used)

## Examples

1. **Hunt problems in 4.22 (investigate top 5)**:
   ```
   /ci:hunt-problems 4.22
   ```

2. **Investigate top 3 regressions**:
   ```
   /ci:hunt-problems 4.22 --count 3
   ```

3. **Hunt and fix everything possible**:
   ```
   /ci:hunt-problems 4.22 --count 5 --fix
   ```

4. **Quick triage of top 1 with fix**:
   ```
   /ci:hunt-problems 4.22 --count 1 --fix
   ```

## Arguments

- $1: OpenShift release version (required, e.g., "4.22")
- `--count N`: Number of jobs to investigate (optional, default: 5)
- `--fix`: After investigation, attempt to file bugs and open PRs for fixable jobs (optional, default: off)

## Skills Used

- `hunt-problems`: Top-level orchestrator
- `find-regressing-jobs`: Query Sippy for regressions
- `investigate-job`: Deep-dive individual jobs (run in parallel)
- `fix-job`: File bugs and open PRs (run sequentially when `--fix` is set)
