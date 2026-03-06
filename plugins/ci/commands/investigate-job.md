---
description: Deep-dive a single failing CI job to identify root cause and assess fixability
argument-hint: "<job-name> <release>"
---

## Name

ci:investigate-job

## Synopsis

```
/ci:investigate-job <job-name> <release>
```

## Description

The `ci:investigate-job` command performs a deep investigation of a single failing CI job. It fetches recent runs from Sippy, classifies the failure type, analyzes multiple failed runs using the appropriate analysis skill, synthesizes findings into a root cause, and assesses fixability.

The output is a self-contained HTML report saved to the current directory.

### Key Features

- **Automatic failure classification**: Detects install failures, test failures, and metal-specific failures
- **Multi-run analysis**: Analyzes 2-3 recent failed runs to identify consistent patterns vs flakes
- **Root cause synthesis**: Combines findings across runs into a single root cause assessment
- **Fixability scoring**: Rates each job as High/Medium/Low fixability with rationale
- **Structured output**: Both human-readable HTML report and machine-readable investigation result block

## Implementation

Load the "Investigate Job" skill and follow its implementation steps.

## Return Value

- **Format**: Self-contained HTML report + structured `INVESTIGATION_RESULT` block
- **Filename**: `investigate-{job-short-name}-{date}.html`
- **HTML Contents**:
  - Job summary (pass rate, run count, regression delta)
  - Failure classification and pattern analysis
  - Per-run analysis summaries
  - Synthesized root cause
  - Fixability assessment with rationale
  - Existing bugs (if any)
- **Structured Block** (printed to stdout):
  ```
  INVESTIGATION_RESULT:
    job_name: <full job name>
    root_cause: <description>
    classification: <infra|product|test>
    fixability: <high|medium|low>
    proposed_fix: <description>
    existing_bugs: <list of bug URLs or "none">
  ```

## Examples

1. **Investigate a specific failing job**:
   ```
   /ci:investigate-job periodic-ci-openshift-release-main-nightly-4.22-e2e-vsphere-ovn-techpreview 4.22
   ```

2. **Investigate a metal job**:
   ```
   /ci:investigate-job periodic-ci-openshift-release-main-nightly-4.22-e2e-metal-ipi-ovn-ipv6 4.22
   ```

## Arguments

- $1: Full Prow job name (required)
- $2: OpenShift release version (required, e.g., "4.22")

## Skills Used

- `investigate-job`: Orchestrates the investigation workflow
- `prow-job-analyze-test-failure`: Analyzes test failures (used by subagents)
- `prow-job-analyze-install-failure`: Analyzes install failures (used by subagents)
- `prow-job-analyze-metal-install-failure`: Analyzes metal install failures (used by subagents)
