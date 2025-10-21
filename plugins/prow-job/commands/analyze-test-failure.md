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

## Implementation
Pass the user's request to the skill, which will:
- Download the artifacts from Google Cloud Storage
- Check source code of the test
- Extract artifacts from Prow CI job and analyze the given test failure

The skill handles all the implementation details including URL parsing, artifact downloading, archive extraction, analyzing the error and providing evidence.

## Arguments:
- $1: Prow job URL (required)
- $2: Test name (required)
