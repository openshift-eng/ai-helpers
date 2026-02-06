---
description: Analyzes test errors from console logs and Prow CI job artifacts
argument-hint: prowjob-url test-name [--fast] [--export-jira]
---

## Name
prow-job:analyze-test-failure

## Synopsis
Generate a test failure analysis for the given test:
```text
/prow-job:analyze-test-failure <prowjob-url> <test-name> [--fast] [--export-jira]
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

**JIRA export mode**:
```text
/prow-job:analyze-test-failure <url> <test-name> --export-jira
```
- Generates additional JIRA-formatted output alongside standard Markdown
- Uses JIRA markup: `{code}`, `{noformat}`, `{panel}`, `{expand}`
- Creates collapsible sections for large logs and stack traces
- Includes linked artifacts for easy navigation
- Can be combined with `--fast`: `--fast --export-jira`

### HyperShift Support

For HyperShift jobs with hosted clusters, the command automatically:
- Detects HyperShift dump archives in various locations (dump-management-cluster, hypershift-mce-dump, run-e2e-local, etc.)
- Extracts archives containing management and/or hosted cluster data
- Splits data into separate directories for independent analysis
- Detects hosted cluster data within archives (hostedcluster-* directory)
- Provides separate diagnostic sections for each cluster
- Correlates issues across both clusters in root cause analysis

**Note**: HyperShift jobs may use different artifact structures depending on the workflow and test type.

## Output Files

The command generates multiple output files in `.work/prow-job-analyze-test-failure/{build_id}/`:

### Standard Output
- **`analysis.md`**: Primary Markdown report with structured sections
  - Viewable in any Markdown viewer
  - GitHub-compatible formatting
  - Includes collapsible sections for large content

### JIRA Export (with --export-jira flag)
- **`analysis-jira.txt`**: JIRA-formatted version for pasting into JIRA comments
  - Uses JIRA markup: `{code}`, `{noformat}`, `{panel}`, `{expand}`
  - Collapsible sections for stack traces and logs
  - Linked artifacts with absolute paths

### Artifacts
- **`logs/`**: Test artifacts (build-log.txt, interval files, etc.)
- **`must-gather/logs/`**: Extracted must-gather data (if analyzed)
- **`must-gather-mgmt/logs/`**: Management cluster must-gather (HyperShift)
- **`must-gather-hosted/logs/`**: Hosted cluster must-gather (HyperShift)

## Implementation
Pass the user's request to the skill, which will:
- Parse optional flags: `--fast` (skip must-gather), `--export-jira` (JIRA output)
- Download the artifacts from Google Cloud Storage
- Check source code of the test
- Extract artifacts from Prow CI job and analyze the given test failure
- **Detect must-gather availability** (single for standard OpenShift, dual for HyperShift)
- **Optionally extract and analyze must-gather data** for cluster-level diagnostics (unless --fast)
- **For HyperShift**: Extract and analyze both management and hosted cluster must-gather
- **Correlate cluster events and operator status** with test failure timing
- **Generate formatted outputs**: Markdown (.md) and optionally JIRA (.txt)

The skill handles all the implementation details including URL parsing, artifact downloading, archive extraction, must-gather analysis (if requested), output formatting, and providing correlated evidence combining test-level and cluster-level insights.

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
  - `--export-jira` - Export analysis results to JIRA-formatted output file
