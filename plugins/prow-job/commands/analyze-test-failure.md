---
description: Analyzes test errors from console logs and Prow CI job artifacts
argument-hint: prowjob-url test-name
---

## Name
prow-job:analyze-test-failure

## Synopsis
Generate a test failure analysis for the given test:
```
/prow-job:analyze-test-failure <prowjob-url> <test-name>
```

## Description
Analyze a failed test by inspecting the test code in the current project and artifacts in Prow CI job. This is done by invoking the "Prow Job Analyze Test Failure" skill.

The command provides comprehensive analysis by:
- Examining test failure stack traces and source code
- Analyzing test execution timeline and cluster events during the test
- **Optionally** extracting and analyzing must-gather data for cluster-level diagnostics
- Correlating cluster issues (degraded operators, failing pods, node problems) with test failures

## Implementation
Pass the user's request to the skill, which will:
- Download the artifacts from Google Cloud Storage
- Check source code of the test
- Extract artifacts from Prow CI job and analyze the given test failure
- **Detect and optionally extract must-gather data for cluster-level diagnostics**
- **Correlate cluster events and operator status with test failure timing**

The skill handles all the implementation details including URL parsing, artifact downloading, archive extraction, must-gather analysis (if requested), and providing correlated evidence combining test-level and cluster-level insights.

## Arguments:
- $1: Prow job URL (required)
- $2: Test name (required)
