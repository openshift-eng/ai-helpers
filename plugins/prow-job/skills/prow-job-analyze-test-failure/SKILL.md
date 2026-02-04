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

3. Optional flags (optional):
   - `--fast` - Skip must-gather extraction and analysis (test-level analysis only)

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

1. **Check for --fast flag**
   - Parse user input for `--fast` flag
   - If `--fast` flag present:
     - Skip must-gather detection and analysis entirely
     - Proceed directly to Step 5 (test-level results only)
     - Do NOT prompt user about must-gather

2. **Detect must-gather archive** (only if --fast not present)

   Check for single must-gather (standard OpenShift):
   ```bash
   gcloud storage ls gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-must-gather/artifacts/must-gather.tar
   ```

   Check for dual must-gather (HyperShift):
   ```bash
   # Management cluster must-gather
   gcloud storage ls gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-must-gather/artifacts/must-gather.tar

   # Hosted cluster must-gather (nested path)
   gcloud storage ls 'gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-*must-gather/artifacts/must-gather.tar'
   ```

   Possible outcomes:
   - **No must-gather found**: Skip to Step 5 (silent, expected for some jobs)
   - **Single must-gather found**: Standard OpenShift cluster
   - **Two must-gather archives found**: HyperShift (management + hosted cluster)

3. **Ask user if they want must-gather analysis**
   - Only if must-gather(s) were found and --fast not present
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

1. **Determine extraction strategy**
   - If single must-gather detected → extract to `must-gather/logs/`
   - If dual must-gather detected (HyperShift) → extract both:
     - Management cluster → `must-gather-mgmt/logs/`
     - Hosted cluster → `must-gather-hosted/logs/`

2. **Check for existing extraction**

   For single must-gather:
   - Check if `.work/prow-job-analyze-test-failure/{build_id}/must-gather/logs/` exists with content

   For dual must-gather (HyperShift):
   - Check if `.work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/logs/` exists with content
   - Check if `.work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/logs/` exists with content

   If either exists:
     - Use AskUserQuestion tool:
       - Question: "Must-gather already extracted for this build. Use existing data?"
       - Header: "Reuse"
       - Options:
         - Label: "Use existing"
           Description: "Reuse previously extracted must-gather data (faster)"
         - Label: "Re-extract"
           Description: "Download and extract fresh must-gather data"
     - If "Re-extract":
       - `rm -rf .work/prow-job-analyze-test-failure/{build_id}/must-gather*/`
       - Continue to step 3 (fresh extraction)
     - If "Use existing":
       - Validate content directories exist and are not empty (see validation in step 5)
       - If validation fails, fall back to re-extraction
       - If validation succeeds, skip to Step 4.7

3. **Create must-gather directories**

   For single must-gather:
   ```bash
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/must-gather/logs
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/must-gather/tmp
   ```

   For dual must-gather (HyperShift):
   ```bash
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/logs
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/tmp
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/logs
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/tmp
   ```

4. **Download must-gather archives**

   For single must-gather:
   ```bash
   gcloud storage cp gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-must-gather/artifacts/must-gather.tar \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather/tmp/must-gather.tar \
     --no-user-output-enabled
   ```

   For dual must-gather (HyperShift):
   ```bash
   # Management cluster must-gather
   gcloud storage cp gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-must-gather/artifacts/must-gather.tar \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/tmp/must-gather.tar \
     --no-user-output-enabled

   # Hosted cluster must-gather
   # First, find the exact path (gather-*-must-gather)
   HOSTED_MG_PATH=$(gcloud storage ls 'gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-*must-gather/artifacts/must-gather.tar' | grep -v 'gather-must-gather')

   gcloud storage cp "$HOSTED_MG_PATH" \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/tmp/must-gather.tar \
     --no-user-output-enabled

   # Extract namespace from path (e.g., gather-clusters-default-must-gather → default)
   HOSTED_NAMESPACE=$(echo "$HOSTED_MG_PATH" | sed -n 's/.*gather-clusters-\([^-]*\)-must-gather.*/\1/p')
   echo "Hosted cluster namespace: $HOSTED_NAMESPACE"
   ```

5. **Extract archives using existing script**

   For single must-gather:
   ```bash
   python3 plugins/prow-job/skills/prow-job-extract-must-gather/extract_archives.py \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather/tmp/must-gather.tar \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather/logs
   ```

   For dual must-gather (HyperShift):
   ```bash
   # Extract management cluster
   python3 plugins/prow-job/skills/prow-job-extract-must-gather/extract_archives.py \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/tmp/must-gather.tar \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/logs

   # Extract hosted cluster
   python3 plugins/prow-job/skills/prow-job-extract-must-gather/extract_archives.py \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/tmp/must-gather.tar \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/logs
   ```

6. **Locate and validate content directories**

   For single must-gather:
   ```bash
   # Check for content/ directory first (renamed by extraction script)
   if [ -d ".work/prow-job-analyze-test-failure/{build_id}/must-gather/logs/content" ]; then
       MUST_GATHER_PATH=".work/prow-job-analyze-test-failure/{build_id}/must-gather/logs/content"
   else
       # Fall back to finding the directory containing -ci- (e.g., registry-build09-ci-...)
       MUST_GATHER_PATH=$(find .work/prow-job-analyze-test-failure/{build_id}/must-gather/logs -maxdepth 1 -type d -name "*-ci-*" | head -1)
   fi

   # Validate MUST_GATHER_PATH is set and directory exists
   if [ -z "$MUST_GATHER_PATH" ] || [ ! -d "$MUST_GATHER_PATH" ]; then
       echo "ERROR: Must-gather content directory not found after extraction"
       # Skip to Step 5 (continue with test-level analysis only)
   elif [ -z "$(ls -A "$MUST_GATHER_PATH" 2>/dev/null)" ]; then
       echo "ERROR: Must-gather content directory is empty"
       # Skip to Step 5 (continue with test-level analysis only)
   else
       echo "✓ Must-gather content located at: $MUST_GATHER_PATH"
       # Continue to Step 4.7 with MUST_GATHER_PATH set
   fi
   ```

   For dual must-gather (HyperShift):
   ```bash
   # Management cluster
   if [ -d ".work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/logs/content" ]; then
       MUST_GATHER_MGMT_PATH=".work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/logs/content"
   else
       MUST_GATHER_MGMT_PATH=$(find .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/logs -maxdepth 1 -type d -name "*-ci-*" | head -1)
   fi

   # Hosted cluster
   if [ -d ".work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/logs/content" ]; then
       MUST_GATHER_HOSTED_PATH=".work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/logs/content"
   else
       MUST_GATHER_HOSTED_PATH=$(find .work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/logs -maxdepth 1 -type d -name "*-ci-*" | head -1)
   fi

   # Validate both paths
   if [ -z "$MUST_GATHER_MGMT_PATH" ] || [ ! -d "$MUST_GATHER_MGMT_PATH" ]; then
       echo "ERROR: Management cluster must-gather content directory not found"
       # Fall back to single cluster analysis if only one succeeds
   elif [ -z "$(ls -A "$MUST_GATHER_MGMT_PATH" 2>/dev/null)" ]; then
       echo "ERROR: Management cluster must-gather content directory is empty"
   else
       echo "✓ Management cluster must-gather located at: $MUST_GATHER_MGMT_PATH"
   fi

   if [ -z "$MUST_GATHER_HOSTED_PATH" ] || [ ! -d "$MUST_GATHER_HOSTED_PATH" ]; then
       echo "ERROR: Hosted cluster must-gather content directory not found"
   elif [ -z "$(ls -A "$MUST_GATHER_HOSTED_PATH" 2>/dev/null)" ]; then
       echo "ERROR: Hosted cluster must-gather content directory is empty"
   else
       echo "✓ Hosted cluster must-gather located at: $MUST_GATHER_HOSTED_PATH"
       echo "✓ Hosted cluster namespace: $HOSTED_NAMESPACE"
   fi
   ```
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
         # Fall back to finding the directory containing -ci- (e.g., registry-build09-ci-...)
         MUST_GATHER_PATH=$(find .work/prow-job-analyze-test-failure/{build_id}/must-gather/logs -maxdepth 1 -type d -name "*-ci-*" | head -1)
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

   Focus on issues relevant to test failures (not full cluster analysis).

   **For single must-gather (standard OpenShift):**

   ```bash
   # Core diagnostics - always run
   python3 "$SCRIPTS_DIR/analyze_clusteroperators.py" "$MUST_GATHER_PATH"
   python3 "$SCRIPTS_DIR/analyze_pods.py" "$MUST_GATHER_PATH" --problems-only
   python3 "$SCRIPTS_DIR/analyze_nodes.py" "$MUST_GATHER_PATH" --problems-only
   python3 "$SCRIPTS_DIR/analyze_events.py" "$MUST_GATHER_PATH" --type Warning --count 50
   ```

   **For dual must-gather (HyperShift):**

   ```bash
   echo "=== Analyzing Management Cluster ==="

   # Management cluster diagnostics
   python3 "$SCRIPTS_DIR/analyze_clusteroperators.py" "$MUST_GATHER_MGMT_PATH"
   python3 "$SCRIPTS_DIR/analyze_pods.py" "$MUST_GATHER_MGMT_PATH" --problems-only
   python3 "$SCRIPTS_DIR/analyze_nodes.py" "$MUST_GATHER_MGMT_PATH" --problems-only
   python3 "$SCRIPTS_DIR/analyze_events.py" "$MUST_GATHER_MGMT_PATH" --type Warning --count 50

   echo "=== Analyzing Hosted Cluster (Namespace: $HOSTED_NAMESPACE) ==="

   # Hosted cluster diagnostics
   python3 "$SCRIPTS_DIR/analyze_clusteroperators.py" "$MUST_GATHER_HOSTED_PATH"
   python3 "$SCRIPTS_DIR/analyze_pods.py" "$MUST_GATHER_HOSTED_PATH" --problems-only
   python3 "$SCRIPTS_DIR/analyze_nodes.py" "$MUST_GATHER_HOSTED_PATH" --problems-only
   python3 "$SCRIPTS_DIR/analyze_events.py" "$MUST_GATHER_HOSTED_PATH" --type Warning --count 50
   ```

3. **Run conditional diagnostics based on test context**

   ```bash
   # Network diagnostics (if test name suggests network issues)
   if [[ "$test_name" =~ network|ovn|sdn|connectivity|route|ingress|egress ]]; then
       if [ -n "$MUST_GATHER_PATH" ]; then
           python3 "$SCRIPTS_DIR/analyze_network.py" "$MUST_GATHER_PATH"
       fi
       if [ -n "$MUST_GATHER_MGMT_PATH" ]; then
           echo "=== Management Cluster Network ==="
           python3 "$SCRIPTS_DIR/analyze_network.py" "$MUST_GATHER_MGMT_PATH"
       fi
       if [ -n "$MUST_GATHER_HOSTED_PATH" ]; then
           echo "=== Hosted Cluster Network ==="
           python3 "$SCRIPTS_DIR/analyze_network.py" "$MUST_GATHER_HOSTED_PATH"
       fi
   fi

   # etcd diagnostics (if test name suggests control-plane issues)
   if [[ "$test_name" =~ etcd|apiserver|control-plane|kube-apiserver ]]; then
       if [ -n "$MUST_GATHER_PATH" ]; then
           python3 "$SCRIPTS_DIR/analyze_etcd.py" "$MUST_GATHER_PATH"
       fi
       if [ -n "$MUST_GATHER_MGMT_PATH" ]; then
           echo "=== Management Cluster etcd ==="
           python3 "$SCRIPTS_DIR/analyze_etcd.py" "$MUST_GATHER_MGMT_PATH"
       fi
       if [ -n "$MUST_GATHER_HOSTED_PATH" ]; then
           echo "=== Hosted Cluster etcd ==="
           python3 "$SCRIPTS_DIR/analyze_etcd.py" "$MUST_GATHER_HOSTED_PATH"
       fi
   fi
   ```

   See `plugins/must-gather/skills/must-gather-analyzer/SKILL.md` for all available analysis scripts.

4. **Capture analysis output**
   - Store script output for correlation in Step 4.8
   - Keep management and hosted cluster outputs separate
   - Use in final report in Step 5

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

   **For HyperShift (dual must-gather):**
   - Correlate issues from BOTH management and hosted clusters
   - Note which cluster (management vs hosted) each issue occurred in
   - Example: "Test failed at 10:23:45. Hosted cluster network operator became degraded at 10:23:12."

2. **Component correlation**
   - Map test failure to cluster components:
     - **Namespace correlation**: Test runs in specific namespace → check for pod failures in that namespace
       - For HyperShift: Tests typically run in hosted cluster namespace (e.g., `clusters-{namespace}`)
     - **Test assertions correlation**: Test type suggests affected components
       - Network tests → network operator status, CNI pods, network policies
       - Storage tests → storage operator, CSI pods, PVs/PVCs
       - API tests → kube-apiserver pods, API server operator
     - **Stack trace correlation**: Error messages in stack trace → related Kubernetes resources
       - "connection refused" → check pod restarts, network issues
       - "timeout" → check node pressure, resource constraints
       - "not found" → check resource deletion events

   **For HyperShift (dual must-gather):**
   - **Management cluster issues** typically affect:
     - HostedControlPlane pods (kube-apiserver, etcd, etc. in `clusters-{namespace}` namespace)
     - HyperShift operator
     - Management cluster nodes hosting control plane
   - **Hosted cluster issues** typically affect:
     - Worker node pods
     - Cluster operators
     - Application workloads

3. **Generate correlated insights**
   - Create specific, actionable correlations like:
     - "Test failed at {time}. {Operator} became degraded at {time} with reason: {reason}"
     - "Pod crash-looping in test namespace: {namespace}/{pod-name}"
     - "Node {node-name} reported {condition} at {time}, test pod was scheduled on this node"
     - "Warning event: {event-message} at {time} (during test execution)"

   **For HyperShift (dual must-gather):**
   - Prefix correlations with cluster type:
     - "[Management Cluster] HostedControlPlane pod restarting: clusters-{namespace}/kube-apiserver-*"
     - "[Hosted Cluster] Network operator degraded with reason: {reason}"
   - Cross-cluster correlations:
     - "Management cluster node pressure → Hosted cluster control plane unavailable"
     - "HyperShift operator error → HostedControlPlane rollout failed"

   - Store these insights for inclusion in Step 5 final report

### Step 5: Present Results to User

1. **Display structured summary with enhanced formatting**

   **For single must-gather or no must-gather:**

   ```text
   # Test Failure Analysis Complete

   ## Job Information
   - **Prow Job**: {prowjob-name}
   - **Build ID**: {build_id}
   - **Target**: {target}
   - **Test**: {test_name}

   ## Test Failure Analysis

   ### Error
   ```
   {error message from stack trace}
   ```

   ### Summary
   {failure analysis from stack trace and code}

   ### Evidence
   {evidence from build-log.txt and interval files}

   ### Additional Evidence
   {additional evidence from logs/events}

   ---

   ## Cluster Diagnostics
   *(Only if must-gather was analyzed)*

   ### Cluster Operators
   {output from analyze_clusteroperators.py}

   ### Problematic Pods
   {output from analyze_pods.py --problems-only}

   ### Node Issues
   {output from analyze_nodes.py --problems-only}

   ### Recent Warning Events
   {output from analyze_events.py}

   ### Network Analysis
   *(Only if network-related test)*
   {output from analyze_network.py}

   ### etcd Analysis
   *(Only if etcd-related test)*
   {output from analyze_etcd.py}

   ---

   ## Correlation
   *(Only if must-gather was analyzed)*

   ### Timeline
   - **Test started**: {from timestamp}
   - **Test failed**: {to timestamp}
   - **Cluster events during test**:
     - {cluster-event} at {timestamp}
     - {cluster-event} at {timestamp}

   ### Affected Components
   - {affected operators/pods/nodes}

   ### Root Cause Hypothesis
   {correlated analysis combining test-level and cluster-level evidence}

   ---

   ## Artifacts
   - **Test artifacts**: `.work/prow-job-analyze-test-failure/{build_id}/logs/`
   - **Must-gather**: `.work/prow-job-analyze-test-failure/{build_id}/must-gather/logs/` *(if extracted)*
   ```

   **For dual must-gather (HyperShift):**

   ```text
   # Test Failure Analysis Complete (HyperShift)

   ## Job Information
   - **Prow Job**: {prowjob-name}
   - **Build ID**: {build_id}
   - **Target**: {target}
   - **Test**: {test_name}
   - **Hosted Cluster Namespace**: {HOSTED_NAMESPACE}

   ## Test Failure Analysis

   ### Error
   ```
   {error message from stack trace}
   ```

   ### Summary
   {failure analysis from stack trace and code}

   ### Evidence
   {evidence from build-log.txt and interval files}

   ### Additional Evidence
   {additional evidence from logs/events}

   ---

   ## Management Cluster Diagnostics

   ### Cluster Operators
   {output from analyze_clusteroperators.py for management cluster}

   ### Problematic Pods
   {output from analyze_pods.py --problems-only for management cluster}

   ### Node Issues
   {output from analyze_nodes.py --problems-only for management cluster}

   ### Recent Warning Events
   {output from analyze_events.py for management cluster}

   ### Network Analysis
   *(Only if network-related test)*
   {output from analyze_network.py for management cluster}

   ### etcd Analysis
   *(Only if etcd-related test)*
   {output from analyze_etcd.py for management cluster}

   ---

   ## Hosted Cluster Diagnostics

   **Namespace**: `{HOSTED_NAMESPACE}`

   ### Cluster Operators
   {output from analyze_clusteroperators.py for hosted cluster}

   ### Problematic Pods
   {output from analyze_pods.py --problems-only for hosted cluster}

   ### Node Issues
   {output from analyze_nodes.py --problems-only for hosted cluster}

   ### Recent Warning Events
   {output from analyze_events.py for hosted cluster}

   ### Network Analysis
   *(Only if network-related test)*
   {output from analyze_network.py for hosted cluster}

   ### etcd Analysis
   *(Only if etcd-related test)*
   {output from analyze_etcd.py for hosted cluster}

   ---

   ## Correlation

   ### Timeline
   - **Test started**: {from timestamp}
   - **Test failed**: {to timestamp}
   - **Management cluster events during test**:
     - {cluster-event} at {timestamp}
   - **Hosted cluster events during test**:
     - {cluster-event} at {timestamp}

   ### Affected Components

   **Management Cluster**:
   - {affected operators/pods/nodes}

   **Hosted Cluster**:
   - {affected operators/pods/nodes}

   ### Root Cause Hypothesis
   {correlated analysis combining:
   - Test-level evidence
   - Management cluster diagnostics
   - Hosted cluster diagnostics
   - Cross-cluster interactions}

   ---

   ## Artifacts
   - **Test artifacts**: `.work/prow-job-analyze-test-failure/{build_id}/logs/`
   - **Management cluster must-gather**: `.work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/logs/`
   - **Hosted cluster must-gather**: `.work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/logs/`
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
