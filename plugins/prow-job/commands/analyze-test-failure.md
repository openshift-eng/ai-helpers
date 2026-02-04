---
description: Analyzes test errors from console logs and Prow CI job artifacts
argument-hint: prowjob-url test-name [--fast]
---

## Name
prow-job:analyze-test-failure

## Synopsis
Generate a test failure analysis for the given test:
```
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
- **Enhanced output**: Structured markdown format with clear sections and artifact organization

### User Experience

**Default (comprehensive analysis)**:
```
/prow-job:analyze-test-failure <url> <test-name>
```
- Detects must-gather availability
- Prompts user whether to include cluster diagnostics
- Provides correlated test + cluster analysis

**Fast mode (skip must-gather)**:
```
/prow-job:analyze-test-failure <url> <test-name> --fast
```
- Skips must-gather detection and extraction
- Only analyzes test-level artifacts (build-log, intervals)
- Faster results, but may miss cluster-level root causes

### HyperShift Support

For HyperShift jobs with hosted clusters, the command automatically:
- Detects dual must-gather archives (management + hosted cluster)
- Extracts and analyzes both clusters separately
- Identifies hosted cluster namespace from must-gather path
- Provides separate diagnostic sections for each cluster
- Correlates issues across both clusters in root cause analysis

## Implementation
Pass the user's request to the skill, which will:
- Parse optional `--fast` flag to skip must-gather analysis
- Download the artifacts from Google Cloud Storage
- Check source code of the test
- Extract artifacts from Prow CI job and analyze the given test failure
- **Detect must-gather availability** (single for standard OpenShift, dual for HyperShift)
- **Optionally extract and analyze must-gather data** for cluster-level diagnostics (unless --fast)
- **For HyperShift**: Extract and analyze both management and hosted cluster must-gather
- **Correlate cluster events and operator status** with test failure timing
- **Provide structured output** with clear sections and enhanced formatting

The skill handles all the implementation details including URL parsing, artifact downloading, archive extraction, must-gather analysis (if requested), and providing correlated evidence combining test-level and cluster-level insights.

## Return Value

- **Format**: Structured markdown report with multiple sections
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
