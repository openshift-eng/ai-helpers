---
name: Prow Job Analyze Test Failure
description: Analyze a failed test by inspecting the code in the current project and artifacts in Prow CI job. Provide a detailed analysis of the test failure in a pre-defined format.
---

# Prow Job Analyze Test Failure

This skill analyzes the given test failure by downloading artifacts using the "Prow Job Analyze Resource" skill, checking test logs, inspecting resources, logs and events from the artifacts, and the test source code.

## When to Use This Skill

Use this skill when the user wants to do an initial analysis of a Prow CI test failure.

## Prerequisites

Identical with "Prow Job Analyze Resource" skill.

## Input Format

The user will provide:

1. **Prow job URL** - gcsweb URL containing `test-platform-results/`

   - Example: `https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/pr-logs/pull/openshift_hypershift/6731/pull-ci-openshift-hypershift-main-e2e-aws/1962527613477982208`
   - URL may or may not have trailing slash

2. **Test name** - test name that failed
   - Examples:
     - `TestKarpenter/EnsureHostedCluster/ValidateMetricsAreExposed`
     - `TestCreateClusterCustomConfig`
     - `The openshift-console downloads pods [apigroup:console.openshift.io] should be scheduled on different nodes`

## Implementation Steps

### Step 1: Parse and Validate URL

Use the "Parse and Validate URL" steps from "Prow Job Analyze Resource" skill

### Step 2: Create Working Directory

1. **Check for existing artifacts first**

   - Check if `.work/prow-job-analyze-test-failure/{build_id}/logs/` directory exists and has content
   - If it exists with content:
     - Use AskUserQuestion tool to ask:
       - Question: "Artifacts already exist for build {build_id}. Would you like to use the existing download or re-download?"
       - Options:
         - "Use existing" - Skip to step Analyze Test Failure
         - "Re-download" - Continue to clean and re-download
     - If user chooses "Re-download":
       - Remove all existing content: `rm -rf .work/prow-job-analyze-test-failure/{build_id}/logs/`
       - Also remove tmp directory: `rm -rf .work/prow-job-analyze-test-failure/{build_id}/tmp/`
       - This ensures clean state before downloading new content
     - If user chooses "Use existing":
       - Skip directly to Step 4 (Analyze Test Failure)
       - Still need to download prowjob.json if it doesn't exist

2. **Create directory structure**
   ```bash
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/logs
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/tmp
   ```
   - Use `.work/prow-job-analyze-test-failure/` as the base directory (already in .gitignore)
   - Use build_id as subdirectory name
   - Create `logs/` subdirectory for all downloads
   - Create `tmp/` subdirectory for temporary files (intermediate JSON, etc.)
   - Working directory: `.work/prow-job-analyze-test-failure/{build_id}/`

### Step 3: Download and Validate prowjob.json

Use the "Download and Validate prowjob.json" steps from "Prow Job Analyze Resource" skill.

### Step 4: Analyze Test Failure

1. **Download build-log.txt**

   ```bash
   gcloud storage cp gs://test-platform-results/{bucket-path}/build-log.txt .work/prow-job-analyze-test-failure/{build_id}/logs/build-log.txt --no-user-output-enabled
   ```

2. **Parse and validate**

   - Read `.work/prow-job-analyze-resource/{build_id}/logs/build-log.txt`
   - Search for the Test name
   - Gather stack trace related to the test

3. **Examine intervals files for cluster activity during E2E failures**

   - Search recursively for E2E timeline artifacts (known as "interval files") within the bucket-path:
     ```bash
     gcloud storage ls 'gs://test-platform-results/{bucket-path}/**/e2e-timelines_spyglass_*json'
     ```
   - The files can be nested at unpredictable levels below the bucket-path
   - There could be as many as two matching files
   - Download all matching interval files (use the full paths from the search results):
     ```bash
     gcloud storage cp gs://test-platform-results/{bucket-path}/**/e2e-timelines_spyglass_*.json .work/prow-job-analyze-test-failure/{build_id}/logs/ --no-user-output-enabled
     ```
   - If the wildcard copy doesn't work, copy each file individually using the full paths from the search results
   - **Scan interval files for test failure timing:**
     - Look for intervals where `source = "E2ETest"` and `message.annotations.status = "Failed"`
     - Note the `from` and `to` timestamps on this interval - this indicates when the test was running
   - **Scan interval files for related cluster events:**
     - Look for intervals that overlap the timeframe when the failed test was running
     - Filter for intervals with:
       - `level = "Error"` or `level = "Warning"`
       - `source = "OperatorState"`
     - These events may indicate cluster issues that caused or contributed to the test failure

4. **Determine root cause**
   - Determine a possible root cause for the test failure
   - Analyze stack traces
   - Analyze related code in the code repository
   - Store artifacts from Prow CI job (json/yaml files) related to the failure under `.work/prow-job-analyze-resource/{build_id}/tmp`
   - Store logs under `.work/prow-job-analyze-resource/{build_id}/logs/`
   - Provide evidence for the failure
   - Try to find additional evidence. For example, in logs and events and other json/yaml files

### Step 5: Present Results to User

1. **Display summary**

   ```text
   Test Failure Analysis Complete

   Prow Job: {prowjob-name}
   Build ID: {build_id}
   Error: {error message}

   Summary: {failure analysis}
   Evidence: {evidence}
   Additional evidence: {additional evidence}

   Artifacts downloaded to: .work/prow-job-analyze-test-failure/{build_id}/logs/
   ```

## Error Handling

Handle errors in the same way as "Error handling" in "Prow Job Analyze Resource" skill

## Performance Considerations

Follow the instructions in "Performance Considerations" in "Prow Job Analyze Resource" skill
