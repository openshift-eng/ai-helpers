---
description: Analyzes test errors from console logs and Prow CI job artifacts
argument-hint: prowjob-url test-name [--fast]
---

## Name
prow-job:analyze-test-failure

## Synopsis
Generate a test failure analysis for the given test:
```text
/prow-job:analyze-test-failure <prowjob-url> <test-name> [--fast]
```

## Description
Analyze a failed test by inspecting the test code in the current project and artifacts in Prow CI job. This is done by invoking the "Prow Job Analyze Test Failure" skill.

The command provides comprehensive analysis by:
- Examining test failure stack traces and source code
- Analyzing test execution timeline and cluster events during the test
- **Optionally** extracting and analyzing must-gather data for cluster-level diagnostics
- **HyperShift support**: Detects and analyzes both management cluster and hosted cluster must-gather data
- Correlating cluster issues (degraded operators, failing pods, node problems) with test failures
- **Enhanced output**: Structured Markdown format with clear sections and artifact organization

### User Experience

**Default (comprehensive analysis)**:
```text
/prow-job:analyze-test-failure <url> <test-name>
```
- Detects must-gather availability
- Prompts user whether to include cluster diagnostics
- Provides correlated test + cluster analysis

**Fast mode (skip must-gather)**:
```text
/prow-job:analyze-test-failure <url> <test-name> --fast
```
- Skips must-gather detection and extraction
- Only analyzes test-level artifacts (build-log, intervals)
- Faster results, but may miss cluster-level root causes

### HyperShift Support

For HyperShift jobs with hosted clusters, the command automatically:
- Detects HyperShift dump archives in various locations (dump-management-cluster, hypershift-mce-dump, run-e2e-local, etc.)
- Extracts archives containing management and/or hosted cluster data
- Splits data into separate directories for independent analysis
- Detects hosted cluster data within archives (hostedcluster-* directory)
- Provides separate diagnostic sections for each cluster
- Correlates issues across both clusters in root cause analysis

**Note**: HyperShift jobs may use different artifact structures depending on the workflow and test type.

## Implementation
- Load the "Prow Job Analyze Test Failure" skill
- Proceed with the analysis by following the implementation steps from the skill

The skill handles all the implementation details including URL parsing, artifact downloading, archive extraction, must-gather analysis (if requested), and providing correlated evidence combining test-level and cluster-level insights.

## Return Value

- **Format**: Structured Markdown report with multiple sections
- **Sections**:
  - **Test Failure Analysis**: Error summary, stack trace analysis, evidence from build-log and interval files
  - **Cluster Diagnostics** (if must-gather analyzed): Cluster operator status, problematic pods, node issues, warning events
  - **Correlation** (if must-gather analyzed): Temporal correlation (test timing vs cluster events) and component correlation (affected operators/pods/nodes)
  - **Root Cause Hypothesis**: Integrated analysis combining test-level and cluster-level insights
- **Artifacts**: Downloaded to `.work/prow-job-analyze-test-failure/{build_id}/`
  - `logs/` - Test artifacts (build-log, interval files)
  - `must-gather/logs/` - Cluster diagnostics (if extracted, standard OpenShift)
  - `must-gather-mgmt/logs/` and `must-gather-hosted/logs/` - Dual cluster diagnostics (if extracted, HyperShift)

## Arguments:
- $1: Prow job URL (required)
- $2: Test name (required)
- $3: Optional flags:
  - `--fast` - Skip must-gather extraction and analysis for faster results
