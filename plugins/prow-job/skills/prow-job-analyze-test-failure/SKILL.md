---
name: Prow Job Analyze Test Failure
description: |
  Analyze failed Prow CI tests by inspecting test code, downloading artifacts, and optionally integrating must-gather cluster diagnostics.

  Use this skill when the user wants to analyze a Prow CI test failure. This skill downloads test artifacts (build-log, interval files),
  analyzes test stack traces and timing, optionally extracts and analyzes must-gather data for cluster-level diagnostics,
  and correlates test failures with cluster issues to provide root cause analysis.

  Triggers: "analyze test failure", "prow test failed", "test failure analysis", "why did test fail",
  "debug prow job", "investigate test failure", "analyze failed test"
---

# Prow Job Analyze Test Failure

This skill analyzes test failures by downloading Prow CI artifacts, checking test logs, inspecting resources and events,
analyzing test source code, and optionally integrating cluster diagnostics from must-gather data.

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

### Step 4.5: Check for Must-Gather Availability

1. **Detect must-gather archive**
   ```bash
   gcloud storage ls gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-must-gather/artifacts/must-gather.tar
   ```
   - If found, must-gather is available
   - If not found (404 error), skip must-gather analysis - proceed to Step 5

2. **Ask user if they want must-gather analysis**
   - Only if must-gather was found
   - Use AskUserQuestion tool:
     - Question: "Must-gather data is available. Include cluster diagnostics in the analysis?"
     - Header: "Must-gather"
     - Options:
       - Label: "Yes - Extract and analyze must-gather (Recommended)"
         Description: "Provides cluster-level diagnostics that may reveal root causes (pods, operators, nodes, events). Takes additional time to download and analyze."
       - Label: "No - Skip must-gather (faster)"
         Description: "Only analyze test-level artifacts (build-log, intervals). Faster but may miss cluster-level issues."
   - If user chooses "No", skip to Step 5

### Step 4.6: Extract Must-Gather (Conditional)

Only if user chose "Yes" in Step 4.5:

1. **Check for existing extraction**
   - Check if `.work/prow-job-analyze-test-failure/{build_id}/must-gather/logs/` exists with content
   - If exists:
     - Use AskUserQuestion tool:
       - Question: "Must-gather already extracted for this build. Use existing data?"
       - Header: "Reuse"
       - Options:
         - Label: "Use existing"
           Description: "Reuse previously extracted must-gather data (faster)"
         - Label: "Re-extract"
           Description: "Download and extract fresh must-gather data"
     - If "Re-extract":
       - `rm -rf .work/prow-job-analyze-test-failure/{build_id}/must-gather/`
       - Continue to step 2 (fresh extraction)
     - If "Use existing":
       - Locate the content directory:
         ```bash
         # Check for content/ directory first (renamed by extraction script)
         if [ -d ".work/prow-job-analyze-test-failure/{build_id}/must-gather/logs/content" ]; then
             MUST_GATHER_PATH=".work/prow-job-analyze-test-failure/{build_id}/must-gather/logs/content"
         else
             # Fall back to finding the quay-io-* directory
             MUST_GATHER_PATH=$(find .work/prow-job-analyze-test-failure/{build_id}/must-gather/logs -maxdepth 1 -type d -name "quay-io-*" | head -1)
         fi
         ```
       - Validate the content directory exists and is not empty:
         ```bash
         if [ -z "$MUST_GATHER_PATH" ] || [ ! -d "$MUST_GATHER_PATH" ]; then
             echo "ERROR: Must-gather content directory not found in cached extraction"
             echo "Falling back to re-extraction..."
             rm -rf .work/prow-job-analyze-test-failure/{build_id}/must-gather/
             # Continue to step 2 (fresh extraction)
         elif [ -z "$(ls -A "$MUST_GATHER_PATH" 2>/dev/null)" ]; then
             echo "ERROR: Must-gather content directory is empty"
             echo "Falling back to re-extraction..."
             rm -rf .work/prow-job-analyze-test-failure/{build_id}/must-gather/
             # Continue to step 2 (fresh extraction)
         else
             echo "✓ Using cached must-gather at: $MUST_GATHER_PATH"
             # Skip to Step 4.7 with MUST_GATHER_PATH set
         fi
         ```

2. **Create must-gather directory**
   ```bash
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/must-gather/logs
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/must-gather/tmp
   ```

3. **Download must-gather.tar**
   ```bash
   gcloud storage cp gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-must-gather/artifacts/must-gather.tar \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather/tmp/must-gather.tar \
     --no-user-output-enabled
   ```

4. **Extract archives using existing script**
   ```bash
   python3 plugins/prow-job/skills/prow-job-extract-must-gather/extract_archives.py \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather/tmp/must-gather.tar \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather/logs
   ```

5. **Locate must-gather content directory and set MUST_GATHER_PATH**
   - After extraction, the content is in `.work/prow-job-analyze-test-failure/{build_id}/must-gather/logs/`
   - The extraction script renames the long hash directory to `content/`
   - Locate and validate the content directory:
     ```bash
     # Check for content/ directory first (renamed by extraction script)
     if [ -d ".work/prow-job-analyze-test-failure/{build_id}/must-gather/logs/content" ]; then
         MUST_GATHER_PATH=".work/prow-job-analyze-test-failure/{build_id}/must-gather/logs/content"
     else
         # Fall back to finding the quay-io-* directory
         MUST_GATHER_PATH=$(find .work/prow-job-analyze-test-failure/{build_id}/must-gather/logs -maxdepth 1 -type d -name "quay-io-*" | head -1)
     fi

     # Validate MUST_GATHER_PATH is set and directory exists
     if [ -z "$MUST_GATHER_PATH" ] || [ ! -d "$MUST_GATHER_PATH" ]; then
         echo "ERROR: Must-gather content directory not found after extraction"
         # Skip to Step 5 (continue with test-level analysis only)
     else
         echo "✓ Must-gather content located at: $MUST_GATHER_PATH"
         # Continue to Step 4.7 with MUST_GATHER_PATH set
     fi
     ```

### Step 4.7: Analyze Must-Gather (Conditional)

Only if Step 4.6 completed successfully:

1. **Locate must-gather-analyzer scripts**

   The must-gather plugin provides analysis scripts. Locate the scripts directory:

   ```bash
   # Try to find the must-gather-analyzer scripts in common locations
   for SEARCH_PATH in \
       "plugins/must-gather/skills/must-gather-analyzer/scripts" \
       "~/.claude/plugins/cache/*/plugins/must-gather/skills/must-gather-analyzer/scripts" \
       "$(find ~ -type d -path "*/must-gather/skills/must-gather-analyzer/scripts" 2>/dev/null | head -1)"; do
       SCRIPTS_DIR=$(eval echo "$SEARCH_PATH")
       if [ -d "$SCRIPTS_DIR" ] && [ -f "$SCRIPTS_DIR/analyze_clusteroperators.py" ]; then
           break
       fi
       SCRIPTS_DIR=""
   done

   if [ -z "$SCRIPTS_DIR" ]; then
       echo "WARNING: Must-gather analysis scripts not found."
       echo "Install the must-gather plugin: /plugin install must-gather@ai-helpers"
       # Continue to Step 5 without cluster analysis
   fi
   ```

2. **Run targeted cluster diagnostics**

   Focus on issues relevant to test failures (not full cluster analysis):

   ```bash
   # Core diagnostics - always run
   python3 "$SCRIPTS_DIR/analyze_clusteroperators.py" "$MUST_GATHER_PATH"
   python3 "$SCRIPTS_DIR/analyze_pods.py" "$MUST_GATHER_PATH" --problems-only
   python3 "$SCRIPTS_DIR/analyze_nodes.py" "$MUST_GATHER_PATH" --problems-only
   python3 "$SCRIPTS_DIR/analyze_events.py" "$MUST_GATHER_PATH" --type Warning --count 50
   ```

3. **Run conditional diagnostics based on test context**

   ```bash
   # Network diagnostics (if test name suggests network issues)
   if [[ "$test_name" =~ network|ovn|sdn|connectivity|route|ingress|egress ]]; then
       python3 "$SCRIPTS_DIR/analyze_network.py" "$MUST_GATHER_PATH"
   fi

   # etcd diagnostics (if test name suggests control-plane issues)
   if [[ "$test_name" =~ etcd|apiserver|control-plane|kube-apiserver ]]; then
       python3 "$SCRIPTS_DIR/analyze_etcd.py" "$MUST_GATHER_PATH"
   fi
   ```

   See `plugins/must-gather/skills/must-gather-analyzer/SKILL.md` for all available analysis scripts.

4. **Capture analysis output**
   - Store script output for correlation in Step 4.8
   - Use in final report in Step 5

### Step 4.8: Correlate Cluster Issues with Test Failure

Only if Step 4.7 completed:

1. **Temporal correlation**
   - From Step 4 (interval files), you identified when the test was running (from/to timestamps)
   - Review cluster operator conditions, pod events, and warning events for timing alignment
   - Identify cluster issues that occurred during or shortly before test failure (±5 minutes)
   - Example: "Test failed at 10:23:45. Network operator became degraded at 10:23:12."

2. **Component correlation**
   - Map test failure to cluster components:
     - **Namespace correlation**: Test runs in specific namespace → check for pod failures in that namespace
     - **Test assertions correlation**: Test type suggests affected components
       - Network tests → network operator status, CNI pods, network policies
       - Storage tests → storage operator, CSI pods, PVs/PVCs
       - API tests → kube-apiserver pods, API server operator
     - **Stack trace correlation**: Error messages in stack trace → related Kubernetes resources
       - "connection refused" → check pod restarts, network issues
       - "timeout" → check node pressure, resource constraints
       - "not found" → check resource deletion events

3. **Generate correlated insights**
   - Create specific, actionable correlations like:
     - "Test failed at {time}. {Operator} became degraded at {time} with reason: {reason}"
     - "Pod crash-looping in test namespace: {namespace}/{pod-name}"
     - "Node {node-name} reported {condition} at {time}, test pod was scheduled on this node"
     - "Warning event: {event-message} at {time} (during test execution)"
   - Store these insights for inclusion in Step 5 final report

### Step 5: Present Results to User

1. **Display summary**

   ```text
   Test Failure Analysis Complete

   Prow Job: {prowjob-name}
   Build ID: {build_id}
   Target: {target}
   Error: {error message}

   === TEST FAILURE ANALYSIS ===
   Summary: {failure analysis from stack trace and code}
   Evidence: {evidence from build-log.txt and interval files}
   Additional evidence: {additional evidence from logs/events}

   === CLUSTER DIAGNOSTICS === (if must-gather was analyzed)

   Cluster Operators:
   {output from analyze_clusteroperators.py}

   Problematic Pods:
   {output from analyze_pods.py --problems-only}

   Node Issues:
   {output from analyze_nodes.py --problems-only}

   Recent Warning Events:
   {output from analyze_events.py}

   Network Analysis: (if network-related test)
   {output from analyze_network.py}

   etcd Analysis: (if etcd-related test)
   {output from analyze_etcd.py}

   === CORRELATION === (if must-gather was analyzed)
   {Temporal and component correlation insights from Step 4.8}

   Timeline:
   - Test failure at {timestamp}
   - {cluster-event} at {timestamp}

   Components:
   - {affected operators/pods/nodes}

   Root Cause Hypothesis:
   {correlated analysis combining test-level and cluster-level evidence}

   Artifacts downloaded to:
   - Test artifacts: .work/prow-job-analyze-test-failure/{build_id}/logs/
   - Must-gather: .work/prow-job-analyze-test-failure/{build_id}/must-gather/logs/ (if extracted)
   ```

## Error Handling

Handle errors in the same way as "Error handling" in "Prow Job Analyze Resource" skill, with these additional must-gather-specific cases:

1. **Must-gather not available**
   - If `gcloud storage ls` returns 404 for must-gather.tar, this is expected (not all jobs have must-gather)
   - Silently skip must-gather analysis - do NOT warn the user
   - Continue with test-level analysis only

2. **Must-gather extraction fails**
   - If download or extraction fails, warn the user but continue with test analysis
   - Display: "WARNING: Must-gather extraction failed: {error}. Continuing with test-level analysis."
   - Continue to Step 5 with test-level results only

3. **Analysis scripts not found**
   - If `find` command returns empty (no scripts found), warn the user
   - Display: "WARNING: Must-gather analysis scripts not installed. Install the must-gather plugin from openshift-eng/ai-helpers for cluster diagnostics."
   - Continue with test-level analysis only

4. **Partial analysis script failures**
   - If one script fails (non-zero exit code), continue with other scripts
   - Capture and report which analyses succeeded/failed
   - Display failed analyses as: "WARNING: {script-name} analysis failed: {error}"
   - Include successful analyses in final report

5. **Empty analysis results**
   - If a script runs successfully but produces no output or no issues found
   - Display: "{Analysis-type}: No issues detected"
   - This is informational, not an error

## Performance Considerations

Follow the instructions in "Performance Considerations" in "Prow Job Analyze Resource" skill
