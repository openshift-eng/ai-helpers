---
name: Prow Job Analyze Test Failure
description: Analyze failed Prow CI tests by inspecting test code, downloading artifacts, and optionally integrating must-gather cluster diagnostics for root cause analysis
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

2. **Test name** (optional) - specific test name that failed
   - When provided, focus the analysis on that test's stack trace and logs
   - When omitted, analyze all failed CI steps by inspecting the JUnit XML, build logs,
     and step artifacts to identify the root cause — this is the common case for
     multi-step CI workflows (e.g. HyperShift, bare-metal OADP jobs) where the failure
     is in a step rather than a named unit test
   - Examples:
     - `TestKarpenter/EnsureHostedCluster/ValidateMetricsAreExposed`
     - `TestCreateClusterCustomConfig`
     - `The openshift-console downloads pods [apigroup:console.openshift.io] should be scheduled on different nodes`

3. Optional flags (optional):
   - `--fast` - Skip must-gather extraction and analysis; continue with log/JUnit/step-artifact analysis only (scope is preserved: test-level when `test-name` is provided, step-level across all failed CI steps when omitted)

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

Use the `fetch-prowjob-json` skill to fetch the prowjob.json for this job. See `plugins/ci/skills/fetch-prowjob-json/SKILL.md` for complete implementation details.

1. **Fetch prowjob.json** using the Prow job URL (convert to gcsweb URL per the `fetch-prowjob-json` skill)
2. **Save locally** to `.work/prow-job-analyze-test-failure/{build_id}/logs/prowjob.json`
3. **Parse and validate**
   - Search for pattern: `--target=([a-zA-Z0-9-]+)` in the ci-operator args
   - If not found:
     - Display: "This is not a ci-operator job. The prowjob cannot be analyzed by this skill."
     - Explain: ci-operator jobs have a --target argument specifying the test target
     - Exit skill
4. **Extract target name and JOB_NAME**
   - Capture the target value (e.g., `e2e-aws-ovn`) from the `--target=` arg
   - Extract `JOB_NAME` from `.spec.job` in prowjob.json (the artifact directory key):
     ```bash
     JOB_NAME=$(jq -r '.spec.job' .work/prow-job-analyze-test-failure/{build_id}/logs/prowjob.json)
     ```
   - Note: on PR jobs `{target}` and `{JOB_NAME}` often differ. All artifact-path lookups
     (JUnit XML, step logs, step artifacts) must use `{JOB_NAME}`, not `{target}`

### Step 4: Analyze Test Failure

### Step 4.0: Detect Aggregated Jobs

Aggregated jobs run the same job in parallel (typically 10 times) and perform statistical
analysis of test results. Detect aggregation by checking for `aggregated-` prefix in the job
name or an `aggregator` container/step in prowjob.json.

If the job is aggregated, the failure modes are different from normal jobs:

1. **Statistically significant test failure** — The test itself fails frequently enough across
   runs to be flagged as a regression. This is a real regression that needs investigation.

2. **Insufficient completed runs** — Not enough runs completed successfully to perform the
   statistical test (e.g., only 5 of 10 jobs produced results). This manifests as mass test
   failures across many unrelated tests. The root cause is whatever prevented the other runs
   from completing — this could be infrastructure issues, install failures, or an actual product
   bug causing crashes. Investigate the underlying job runs that did not complete to determine
   why.

3. **Non-deterministic test presence** — A test only ran in a small subset of completed jobs,
   even though the other jobs completed successfully. The failure message will say something like
   "Passed 1 times, failed 0 times, skipped 0 times: we require at least 6 attempts to have a
   chance at success". Every test must produce results in every job run; it is a bug if it does
   not. This is a regression — someone introduced a test that doesn't produce results
   deterministically. Investigate which test is non-deterministic and why it only runs in some
   jobs.

When analyzing an aggregated job failure, first determine which failure mode applies before
diving into individual test analysis. For mode 2, focus on why runs failed rather than
individual test results. For mode 3, investigate why the test only ran in some jobs.

**Finding underlying job run URLs:**

The aggregated junit XML contains links to every underlying job run. Download it from:
```
gs://test-platform-results/{bucket-path}/artifacts/release-analysis-aggregator/openshift-release-analysis-aggregator/artifacts/release-analysis-aggregator/{job-name}/{payload-tag}/junit-aggregated.xml
```

Each `<testcase>` element has a `<system-out>` with YAML-formatted data including `passes:`,
`failures:`, and `skips:` lists. Each entry has:
- `jobrunid`: The build ID of the underlying job run
- `humanurl`: Prow URL for the job run (e.g., `https://prow.ci.openshift.org/view/gs/test-platform-results/logs/{job-name}/{jobrunid}`)
- `gcsartifacturl`: Direct link to GCS artifacts

Use the `humanurl` links to investigate individual job run failures with the normal
(non-aggregated) analysis steps below.

### Step 4.1: Download build-log.txt

```bash
gcloud storage cp gs://test-platform-results/{bucket-path}/build-log.txt .work/prow-job-analyze-test-failure/{build_id}/logs/build-log.txt --no-user-output-enabled
```

### Step 4.2: Parse and validate

- Read `.work/prow-job-analyze-test-failure/{build_id}/logs/build-log.txt`

**Branch on whether {test_name} was provided:**

#### Branch A: test_name provided
- Search build-log.txt for the exact test name string
- Gather the stack trace and surrounding context for that specific test
- Store the single failing test's error output for use in Steps 4.4 and 4.9

#### Branch B: test_name NOT provided (multi-step discovery)

This is the common case for multi-step CI workflows (e.g., HyperShift, bare-metal, OADP jobs)
where failures occur in CI steps rather than named unit tests.

1. **Discover failed CI steps from JUnit XML**

   Use `{JOB_NAME}` (from Step 3, extracted from `.spec.job`) for all GCS artifact paths —
   not `{target}`. On PR jobs these values differ and `{target}` will miss the artifacts.

   Search for JUnit XML files under the artifacts directory:
   ```bash
   gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/{JOB_NAME}/**/junit*.xml" 2>/dev/null
   ```
   Download all found JUnit XML files:
   ```bash
   gcloud storage cp "gs://test-platform-results/{bucket-path}/artifacts/{JOB_NAME}/**/junit*.xml" \
     .work/prow-job-analyze-test-failure/{build_id}/logs/ --no-user-output-enabled --recursive 2>/dev/null || true
   ```
   Parse each downloaded XML file and collect every `<testcase>` element where:
   - A `<failure>` or `<error>` child element is present, OR
   - The `<testcase>` has attribute `status="failed"`

   For each failed testcase record:
   - `step_name`: value of `classname` or `name` attribute (whichever identifies the CI step)
   - `failure_message`: text content of the `<failure>` or `<error>` element
   - `junit_file`: path of the XML file it came from

2. **Classify each failed step by phase**

   The ci-operator JUnit XML (`junit_operator.xml`) includes phase-level testcases:
   - `"Run multi-stage test pre phase"` — setup/installation steps
   - `"Run multi-stage test test phase"` — functional test steps
   - `"Run multi-stage test post phase"` — gather/cleanup steps

   Use the phase entries to classify each failed `step_name`:

   - Look at the failed **phase-level** testcases (those with `"pre phase"`, `"test phase"`,
     or `"post phase"` in their name) — these tell you which phase failed
   - Cross-reference the individual step testcases against their phase:
     - Steps in the **`pre` phase** → installation/setup steps
     - Steps in the **`test` phase** → functional test steps
     - Steps in the **`post` phase** → gather/cleanup steps (rarely the root cause)

   If the phase-level testcases are absent from the JUnit XML (some jobs omit them),
   fall back to the `ci-operator-step-graph.json` artifact, which lists all steps with
   their dependencies and timing — use execution order and naming conventions as a
   secondary signal. When still ambiguous, prefer classifying as a **test step** so
   must-gather analysis is not skipped.

3. **Route each failed step to the appropriate analysis path**

   - **`pre` phase steps (installation)** → invoke the `ci:analyze-prow-job-install-failure`
     skill for each such step, passing the same Prow job URL. Must-gather is **not**
     attempted for `pre` phase failures: must-gather requires a live apiserver, and when
     the installation phase fails the cluster is not fully up, so collection will fail.
     **Capture the delegated output** and store it
     as a per-step entry in the shared results collection used by Step 5 and Step 5.5:
     ```
     {
       step_name:      {step_name},
       type:           "installation",
       summary:        {one-line summary from ci:analyze-prow-job-install-failure},
       evidence:       {key error / stack trace from delegated analysis},
       recommendation: {recommended action from delegated analysis}
     }
     ```
   - **`test` phase steps (functional tests)** → proceed with the iteration in item 4
     below (download step log, artifacts, extract stack trace) and include must-gather
     analysis (Steps 4.4–4.9). Store findings in the same per-step results collection:
     ```
     {
       step_name:      {step_name},
       type:           "test",
       summary:        {one-line failure summary},
       evidence:       {stack trace / error output},
       recommendation: {recommended action}
     }
     ```
   - **`post` phase steps (gather/cleanup)** → treat as informational. Download the step
     log and note the failure in the report, but do not perform must-gather analysis for
     post-phase failures alone (they are usually a consequence of earlier failures).

4. **Iterate over each `test` phase step** (`pre` and `post` phase steps already routed above)

   For each `step_name` in the **`test` phase**, perform the following sub-steps:

   a. **Download step-specific log**
      ```bash
      gcloud storage cp \
        "gs://test-platform-results/{bucket-path}/artifacts/{JOB_NAME}/{step_name}/build-log.txt" \
        .work/prow-job-analyze-test-failure/{build_id}/logs/{step_name}-build-log.txt \
        --no-user-output-enabled 2>/dev/null || true
      ```
      If the step log is not found at that path, fall back to scanning build-log.txt for
      lines mentioning `{step_name}` and collect surrounding context (±50 lines).

   b. **Download step-specific artifacts**
      ```bash
      gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/{JOB_NAME}/{step_name}/" \
        2>/dev/null
      ```
      Download any relevant artifacts (e.g., `*.json`, `*.yaml`, `events*.txt`) to
      `.work/prow-job-analyze-test-failure/{build_id}/logs/{step_name}/`.

   c. **Extract stack trace and context**
      - Scan the step log for panic traces, `FAIL`, `Error:`, `fatal`, or assertion failures
      - Collect the full stack trace block (from the triggering line to the end of the trace)
      - Note the failure message from the JUnit XML as additional context

   d. **Store per-step findings**
      Record for each step:
      - `step_name`
      - `failure_message` (from JUnit XML)
      - `stack_trace` (from step log or build-log.txt context)
      - `artifacts` (list of downloaded artifact paths)

3. **Produce a multi-step failure summary**

   After iterating all failed steps, produce an ordered list of findings:
   ```
   Failed Steps Discovered:
   1. {step_name_1}: {one-line failure summary}
   2. {step_name_2}: {one-line failure summary}
   ...
   ```
   This list is used in Step 4.4 (evidence gathering) and Step 5 (report) to drive
   per-step analysis rather than singular test analysis.

### Step 4.3: Examine intervals files for cluster activity during E2E failures

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

### Step 4.3b: Check for Known Symptom Labels

The CI system may attach **symptom labels** to job runs — machine-detected patterns (e.g., "test failures during high CPU events") stored as JSON artifacts. These are **not root causes** but provide useful environmental context that may help explain failures when no other cause is found.

1. **List the job_labels directory**
   ```bash
   gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/job_labels/" 2>/dev/null
   ```
   - If the directory does not exist or returns an error, skip this step silently

2. **Download any JSON symptom files** (exclude `label-summary.html`)
   ```bash
   gcloud storage cp "gs://test-platform-results/{bucket-path}/artifacts/job_labels/*.json" \
     .work/prow-job-analyze-test-failure/{build_id}/logs/job_labels/ --no-user-output-enabled 2>/dev/null || true
   ```

3. **Parse symptom labels** — each JSON file describes a detected symptom with a summary and explanation. Collect all symptom summaries for inclusion in the report.

4. **Use symptoms as investigative context** — symptoms are environmental observations, NOT definitive causes. They should inform your investigation (e.g., if 2 tests failed while high CPU was measured, CPU pressure could explain the failures if no other cause is found) but you must still perform thorough root cause analysis. Include them in the "Known Symptoms Seen" section of the report.

### Step 4.4: Gather initial evidence

- Analyze stack traces from build-log.txt
- Analyze related code in the code repository
- Store artifacts from Prow CI job (json/yaml files) related to the failure under `.work/prow-job-analyze-test-failure/{build_id}/tmp`
- Store logs under `.work/prow-job-analyze-test-failure/{build_id}/logs/`
- Collect evidence from logs and events and other json/yaml files

### Step 4.5: Check for Must-Gather Availability

1. **Parse optional flags**
   - Parse user input for `--fast` flag
   - If `--fast` flag present:
     - Skip must-gather detection and analysis entirely
     - Proceed directly to Step 5 — scope is preserved:
       - If `test_name` was provided → produce singular test report (Branch A)
       - If `test_name` was omitted → produce multi-step report (Branch B)
     - Do NOT prompt user about must-gather

2. **Extract actual test name from prowjob.json**

   The artifacts directory uses the test name from prowjob.json, NOT the full URL path.

   ```bash
   # Extract test name from prowjob.json (e.g., "e2e-aws-operator-serial-ote")
   JOB_NAME=$(jq -r '.spec.job' .work/prow-job-analyze-test-failure/{build_id}/logs/prowjob.json)

   # Note: For PR jobs, TARGET contains the full PR path like:
   #   pr-logs/pull/openshift_service-ca-operator/306/pull-ci-openshift-service-ca-operator-main-e2e-aws-operator-serial-ote
   # But artifacts are stored under just the test name:
   #   e2e-aws-operator-serial-ote
   ```

3. **Detect must-gather archive** (only if --fast not present)

   Use JOB_NAME (not TARGET) for artifact paths.

   HyperShift jobs may have **different must-gather patterns**:

   **Pattern 1: Unified Archive** (dump-management-cluster)
   - Single archive with both management and hosted cluster data
   - Used by: hypershift-aws-e2e-external workflow

   **Pattern 2: Dual Archives** (gather-must-gather + dump)
   - Standard must-gather for management cluster
   - Separate hypershift-dump for additional data (may or may not have hosted cluster)
   - Used by: hypershift-kubevirt-e2e-aws workflow

   **Pattern 3: Standard Only** (gather-must-gather)
   - Standard OpenShift must-gather only
   - No HyperShift-specific dump

   **Detection logic**:
   ```bash
   # Check for Pattern 1: Unified archive (dump-management-cluster)
   UNIFIED_DUMP=$(gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/$JOB_NAME/dump-management-cluster/artifacts/artifacts.tar*" 2>/dev/null | head -1 || true)

   # Check for Pattern 2/3: Standard must-gather
   STANDARD_MG=$(gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/$JOB_NAME/gather-must-gather/artifacts/must-gather.tar" 2>/dev/null || true)

   # Check for Pattern 2: Additional hypershift-dump (multiple possible locations)
   # Use wildcards to match all current and future HyperShift dump patterns:
   # 1. **/artifacts/hypershift-dump.tar (covers dump/, hypershift-mce-dump/, etc.)
   # 2. **/artifacts/**/hostedcluster.tar (covers all E2E test patterns)
   HYPERSHIFT_DUMP=""
   for pattern in \
       "**/artifacts/hypershift-dump.tar" \
       "**/artifacts/**/hostedcluster.tar"; do
       FOUND=$(gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/$JOB_NAME/$pattern" 2>/dev/null | head -1 || true)
       if [ -n "$FOUND" ]; then
           HYPERSHIFT_DUMP="$FOUND"
           break
       fi
   done

   # Determine pattern and check for hosted cluster data
   if [ -n "$UNIFIED_DUMP" ]; then
     # Pattern 1: Unified archive
     PATTERN="unified"

     # Download temporarily to check for hosted cluster data
     TMP_CHECK="/tmp/check-unified-$$.tar"
     gcloud storage cp "$UNIFIED_DUMP" "$TMP_CHECK" --no-user-output-enabled

     # Check if archive contains hostedcluster-* directory
     HAS_HOSTED_CLUSTER=$(tar -tf "$TMP_CHECK" 2>/dev/null | grep -q "hostedcluster-" && echo "true" || echo "false")
     rm -f "$TMP_CHECK"

   elif [ -n "$STANDARD_MG" ] && [ -n "$HYPERSHIFT_DUMP" ]; then
     # Pattern 2: Dual archives
     PATTERN="dual"

     # Download hypershift-dump temporarily to check for hosted cluster
     TMP_CHECK="/tmp/check-dump-$$.tar"
     gcloud storage cp "$HYPERSHIFT_DUMP" "$TMP_CHECK" --no-user-output-enabled

     # Check if hypershift-dump contains hostedcluster-* directory
     HAS_HOSTED_CLUSTER=$(tar -tf "$TMP_CHECK" 2>/dev/null | grep -q "hostedcluster-" && echo "true" || echo "false")
     rm -f "$TMP_CHECK"

   elif [ -n "$STANDARD_MG" ]; then
     # Pattern 3: Standard must-gather only
     PATTERN="standard"
     HAS_HOSTED_CLUSTER=false

   else
     # No must-gather found
     PATTERN="none"
     HAS_HOSTED_CLUSTER=false
   fi
   ```

   Possible outcomes:
   - **PATTERN="none"**: No must-gather found → Skip to Step 5 (silent, expected for some jobs)
   - **PATTERN="standard"**: Standard OpenShift must-gather only → Extract single cluster
   - **PATTERN="unified" + HAS_HOSTED_CLUSTER=false**: HyperShift unified archive with management only
   - **PATTERN="unified" + HAS_HOSTED_CLUSTER=true**: HyperShift unified archive with both clusters
   - **PATTERN="dual" + HAS_HOSTED_CLUSTER=false**: Two archives but hosted cluster not in hypershift-dump
   - **PATTERN="dual" + HAS_HOSTED_CLUSTER=true**: Two archives with hosted cluster in hypershift-dump

   **Important Pattern Notes**:
   - **Pattern 1 (unified)**: Management at `logs/artifacts/output/`, hosted at `logs/artifacts/output/hostedcluster-{name}/`
   - **Pattern 2 (dual)**: Management in standard must-gather, hosted MAY be in hypershift-dump.tar or hostedcluster.tar (not guaranteed)
     - Wildcard patterns match all current and future dump locations
   - **Pattern 3 (standard)**: Management cluster only, no HyperShift-specific data

4. **Ask user if they want must-gather analysis**
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
       - Validate content directories exist and are not empty (see validation in step 4.6)
       - If validation fails, fall back to re-extraction
       - If validation succeeds, skip to Step 4.7

3. **Create must-gather directories**

   Based on PATTERN from Step 4.5.3:

   For Pattern 3 (standard only):
   ```bash
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/must-gather/logs
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/must-gather/tmp
   ```

   For Pattern 1 (unified) or Pattern 2 (dual):
   ```bash
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/logs
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/tmp
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/logs
   mkdir -p .work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/tmp
   ```

4. **Download must-gather archives**

   Use JOB_NAME (from Step 4.5.2) for artifact paths, not {target}:

   For Pattern 3 (standard only):
   ```bash
   gcloud storage cp "$STANDARD_MG" \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather/tmp/must-gather.tar \
     --no-user-output-enabled
   ```

   For Pattern 1 (unified):
   ```bash
   # Download unified archive (contains both management and hosted cluster data)
   gcloud storage cp "$UNIFIED_DUMP" \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/tmp/unified-dump.tar \
     --no-user-output-enabled
   ```

   For Pattern 2 (dual):
   ```bash
   # Download management cluster must-gather
   gcloud storage cp "$STANDARD_MG" \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/tmp/must-gather.tar \
     --no-user-output-enabled

   # Download hypershift-dump (may or may not contain hosted cluster)
   gcloud storage cp "$HYPERSHIFT_DUMP" \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/tmp/hypershift-dump.tar \
     --no-user-output-enabled
   ```

5. **Extract archives**

   For Pattern 3 (standard only):
   ```bash
   # Use existing extract_archives.py script for standard must-gather
   python3 plugins/ci/skills/prow-job-extract-must-gather/extract_archives.py \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather/tmp/must-gather.tar \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather/logs
   ```

   For Pattern 1 (unified):
   ```bash
   # Extract unified archive to temporary location
   TMP_EXTRACT=".work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/tmp/extracted"
   mkdir -p "$TMP_EXTRACT"

   # Handle both .tar and .tar.gz
   if [[ "$UNIFIED_DUMP" == *.tar.gz ]]; then
     tar -xzf .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/tmp/unified-dump.tar -C "$TMP_EXTRACT"
   else
     tar -xf .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/tmp/unified-dump.tar -C "$TMP_EXTRACT"
   fi

   # Find the output directory (may be at logs/artifacts/output or just output)
   OUTPUT_DIR=$(find "$TMP_EXTRACT" -type d -name "output" | head -1)

   if [ -z "$OUTPUT_DIR" ]; then
     echo "ERROR: Could not find output directory in unified dump"
     rm -rf "$TMP_EXTRACT"
     # Clear variables to prevent subsequent usage
     HAS_HOSTED_CLUSTER="false"
     unset HOSTED_DIR
     unset OUTPUT_DIR
     # Skip to Step 5 - no must-gather analysis possible
   else
     # Move management cluster data (root level in output/)
     # Exclude hostedcluster-* directories
     for item in "$OUTPUT_DIR"/*; do
       if [ -e "$item" ] && [[ ! "$(basename "$item")" =~ ^hostedcluster- ]]; then
         mv "$item" .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/logs/
       fi
     done

     # Move hosted cluster data (hostedcluster-* subdirectory)
     if [ "$HAS_HOSTED_CLUSTER" = "true" ]; then
       HOSTED_DIR=$(find "$OUTPUT_DIR" -maxdepth 1 -type d -name "hostedcluster-*" | head -1)
       if [ -n "$HOSTED_DIR" ]; then
         mv "$HOSTED_DIR"/* .work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/logs/
         echo "✓ Hosted cluster data extracted from unified archive"
       else
         echo "WARNING: Expected hosted cluster data but hostedcluster-* directory not found"
       fi
     fi

     # Cleanup temporary extraction directory
     rm -rf "$TMP_EXTRACT"
   fi
   ```

   For Pattern 2 (dual):
   ```bash
   # Extract management cluster must-gather (standard format)
   python3 plugins/prow-job/skills/prow-job-extract-must-gather/extract_archives.py \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/tmp/must-gather.tar \
     .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/logs

   # Extract hypershift-dump (may contain hosted cluster)
   TMP_EXTRACT=".work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/tmp/extracted"
   mkdir -p "$TMP_EXTRACT"
   tar -xf .work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/tmp/hypershift-dump.tar -C "$TMP_EXTRACT"

   if [ "$HAS_HOSTED_CLUSTER" = "true" ]; then
     # Look for hostedcluster-* directory in dump
     HOSTED_DIR=$(find "$TMP_EXTRACT" -maxdepth 2 -type d -name "hostedcluster-*" | head -1)
     if [ -n "$HOSTED_DIR" ]; then
       mv "$HOSTED_DIR"/* .work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/logs/
       echo "✓ Hosted cluster data extracted from hypershift-dump"
     else
       echo "WARNING: HAS_HOSTED_CLUSTER=true but no hostedcluster-* directory found in dump"
       echo "Hypershift-dump likely contains only management cluster data"
       HAS_HOSTED_CLUSTER=false  # Update flag since hosted cluster not actually present
     fi
   else
     echo "INFO: Hypershift-dump does not contain hosted cluster data (management cluster only)"
   fi

   # Cleanup temporary extraction directory
   rm -rf "$TMP_EXTRACT"
   ```

6. **Locate and validate content directories**

   For Pattern 3 (standard only):
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
       # Skip to Step 5 (scope preserved: Branch A or Branch B per test_name presence)
   elif [ -z "$(ls -A "$MUST_GATHER_PATH" 2>/dev/null)" ]; then
       echo "ERROR: Must-gather content directory is empty"
       # Skip to Step 5 (scope preserved: Branch A or Branch B per test_name presence)
   else
       echo "✓ Must-gather content located at: $MUST_GATHER_PATH"
       # Continue to Step 4.7 with MUST_GATHER_PATH set
   fi
   ```

   For Pattern 1 (unified) or Pattern 2 (dual):
   ```bash
   # Management cluster validation
   if [ "$PATTERN" = "unified" ]; then
       # Pattern 1: Data extracted directly to logs/ directory
       MUST_GATHER_MGMT_PATH=".work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/logs"
   else
       # Pattern 2: Standard must-gather extraction (look for content/ or hash directory)
       if [ -d ".work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/logs/content" ]; then
           MUST_GATHER_MGMT_PATH=".work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/logs/content"
       else
           MUST_GATHER_MGMT_PATH=$(find .work/prow-job-analyze-test-failure/{build_id}/must-gather-mgmt/logs -maxdepth 1 -type d -name "*-ci-*" | head -1)
       fi
   fi

   # Validate management cluster path
   if [ -z "$MUST_GATHER_MGMT_PATH" ] || [ ! -d "$MUST_GATHER_MGMT_PATH" ]; then
       echo "ERROR: Management cluster directory not found"
       # Skip to Step 5 (scope preserved: Branch A or Branch B per test_name presence)
   elif [ -z "$(ls -A "$MUST_GATHER_MGMT_PATH" 2>/dev/null)" ]; then
       echo "ERROR: Management cluster directory is empty"
       # Skip to Step 5 (scope preserved: Branch A or Branch B per test_name presence)
   else
       echo "✓ Management cluster data located at: $MUST_GATHER_MGMT_PATH"
   fi

   # Hosted cluster validation - only if HAS_HOSTED_CLUSTER is true
   if [ "$HAS_HOSTED_CLUSTER" = "true" ]; then
       MUST_GATHER_HOSTED_PATH=".work/prow-job-analyze-test-failure/{build_id}/must-gather-hosted/logs"

       # Validate hosted cluster path
       if [ ! -d "$MUST_GATHER_HOSTED_PATH" ]; then
           echo "WARNING: Hosted cluster directory not found (expected based on archive detection)"
           MUST_GATHER_HOSTED_PATH=""  # Clear the path
       elif [ -z "$(ls -A "$MUST_GATHER_HOSTED_PATH" 2>/dev/null)" ]; then
           echo "WARNING: Hosted cluster directory is empty"
           MUST_GATHER_HOSTED_PATH=""  # Clear the path
       else
           echo "✓ Hosted cluster data located at: $MUST_GATHER_HOSTED_PATH"
       fi
   else
       echo "✓ Management cluster must-gather located at: $MUST_GATHER_MGMT_PATH"
   fi

   # Only validate hosted cluster if HAS_HOSTED_CLUSTER is true
   if [ "$HAS_HOSTED_CLUSTER" = "true" ]; then
       if [ -z "$MUST_GATHER_HOSTED_PATH" ] || [ ! -d "$MUST_GATHER_HOSTED_PATH" ]; then
           echo "ERROR: Hosted cluster must-gather content directory not found"
       elif [ -z "$(ls -A "$MUST_GATHER_HOSTED_PATH" 2>/dev/null)" ]; then
           echo "ERROR: Hosted cluster must-gather content directory is empty"
       else
           echo "✓ Hosted cluster must-gather located at: $MUST_GATHER_HOSTED_PATH"
           echo "✓ Hosted cluster namespace: $HOSTED_NAMESPACE"
       fi
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
   # Core diagnostics (only if scripts and path are available)
   if [ -n "$SCRIPTS_DIR" ] && [ -n "$MUST_GATHER_PATH" ]; then
       python3 "$SCRIPTS_DIR/analyze_clusteroperators.py" "$MUST_GATHER_PATH"
       python3 "$SCRIPTS_DIR/analyze_pods.py" "$MUST_GATHER_PATH" --problems-only
       python3 "$SCRIPTS_DIR/analyze_nodes.py" "$MUST_GATHER_PATH" --problems-only
       python3 "$SCRIPTS_DIR/analyze_events.py" "$MUST_GATHER_PATH" --type Warning --count 50
   else
       echo "WARNING: Skipping must-gather analysis (scripts or path not available)"
   fi
   ```

   **For dual must-gather (HyperShift):**

   ```bash
   # Management cluster diagnostics (only if scripts and path are available)
   if [ -n "$SCRIPTS_DIR" ] && [ -n "$MUST_GATHER_MGMT_PATH" ]; then
       echo "=== Analyzing Management Cluster ==="
       python3 "$SCRIPTS_DIR/analyze_clusteroperators.py" "$MUST_GATHER_MGMT_PATH"
       python3 "$SCRIPTS_DIR/analyze_pods.py" "$MUST_GATHER_MGMT_PATH" --problems-only
       python3 "$SCRIPTS_DIR/analyze_nodes.py" "$MUST_GATHER_MGMT_PATH" --problems-only
       python3 "$SCRIPTS_DIR/analyze_events.py" "$MUST_GATHER_MGMT_PATH" --type Warning --count 50
   else
       echo "WARNING: Skipping management cluster analysis (scripts or path not available)"
   fi

   # Hosted cluster diagnostics (only if scripts and path are available)
   if [ -n "$SCRIPTS_DIR" ] && [ -n "$MUST_GATHER_HOSTED_PATH" ]; then
       echo "=== Analyzing Hosted Cluster (Namespace: $HOSTED_NAMESPACE) ==="
       python3 "$SCRIPTS_DIR/analyze_clusteroperators.py" "$MUST_GATHER_HOSTED_PATH"
       python3 "$SCRIPTS_DIR/analyze_pods.py" "$MUST_GATHER_HOSTED_PATH" --problems-only
       python3 "$SCRIPTS_DIR/analyze_nodes.py" "$MUST_GATHER_HOSTED_PATH" --problems-only
       python3 "$SCRIPTS_DIR/analyze_events.py" "$MUST_GATHER_HOSTED_PATH" --type Warning --count 50
   else
       echo "INFO: Skipping hosted cluster analysis (scripts or path not available)"
   fi
   ```

3. **Run conditional diagnostics based on test context**

   ```bash
   # Network diagnostics (if test name suggests network issues)
   if [[ "$JOB_NAME" =~ network|ovn|sdn|connectivity|route|ingress|egress ]]; then
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
   if [[ "$JOB_NAME" =~ etcd|apiserver|control-plane|kube-apiserver ]]; then
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

   - Store these insights for inclusion in Step 4.9 root cause determination

### Step 4.9: Determine Root Cause

Synthesize all gathered evidence to determine the most likely root cause for the test failure:

1. **Analyze all available evidence**
   - Stack traces from Step 4.2
   - Test code analysis from Step 4.4
   - Interval file events from Step 4.3
   - Known symptom labels from Step 4.3b (if available — use as supporting context, not as root cause)
   - Cluster diagnostics from Step 4.7 (if available)
   - Correlations from Step 4.8 (if available)

2. **Prioritize evidence based on temporal proximity**
   - Issues occurring during test execution time (from interval files) are most relevant
   - Cluster issues that occurred shortly before test failure (±5 minutes) are highly relevant
   - Pre-existing cluster issues may be contributing factors but not root causes

3. **Generate root cause hypothesis**
   - Primary cause: The most direct, immediate cause of test failure
   - Contributing factors: Cluster or environmental issues that enabled the failure
   - Evidence summary: Key evidence supporting the hypothesis

   **For HyperShift jobs:**
   - Distinguish between management cluster vs hosted cluster root causes
   - Identify cross-cluster dependencies (e.g., management node pressure → hosted control plane unavailable)

4. **Formulate actionable recommendations**
   - What needs to be fixed (code, configuration, cluster state)
   - Where to look for more information
   - Suggested next steps for debugging or resolution

### Step 5: Present Results to User

1. **Display structured summary with enhanced formatting**

   **Branch on whether test_name was provided (mirrors Step 4.2 branching):**

   - **Branch A (test_name provided):** Use the singular `{test_name}` report shape below.
   - **Branch B (test_name NOT provided):** Use the multi-step report shape further below,
     iterating over each failed step discovered in Step 4.2 Branch B and aggregating
     their findings into a combined report.

   **For single must-gather or no must-gather (Branch A — test_name provided):**

   ```text
   # Test Failure Analysis Complete

   ## Job Information
   - **Prow Job**: {prowjob-name}
   - **Build ID**: {build_id}
   - **Target**: {target}
   - **Test**: {test_name}

   ## Known Symptoms Seen
   *(Only if symptom labels were found in Step 4.3b — omit section entirely if none)*
   - {symptom summary}: {symptom explanation}
   > **Note**: Symptoms are machine-detected environmental observations, not definitive causes. They add context to help explain failures when correlated with other evidence.

   ## Test Failure Analysis

   ### Error
   {error message from stack trace}

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

   ## Known Symptoms Seen
   *(Only if symptom labels were found in Step 4.3b — omit section entirely if none)*
   - {symptom summary}: {symptom explanation}
   > **Note**: Symptoms are machine-detected environmental observations, not definitive causes. They add context to help explain failures when correlated with other evidence.

   ## Test Failure Analysis

   ### Error
   {error message from stack trace}

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

   **For Branch B (test_name NOT provided — multi-step failure report):**

   Iterate over the ordered list of failed steps discovered in Step 4.2 Branch B and produce
   one section per step, then aggregate into a combined root cause section.

   ```text
   # Test Failure Analysis Complete (Multi-Step)

   ## Job Information
   - **Prow Job**: {prowjob-name}
   - **Build ID**: {build_id}
   - **Target**: {target}
   - **Failed Steps**: {count of discovered failed steps}

   ## Known Symptoms Seen
   *(Only if symptom labels were found in Step 4.3b — omit section entirely if none)*
   - {symptom summary}: {symptom explanation}
   > **Note**: Symptoms are machine-detected environmental observations, not definitive causes.

   ---

   ## Failed Step Analyses

   *(Repeat the following block for each failed step discovered in Step 4.2 Branch B)*

   ### Step: {step_name}

   #### Error
   {failure_message from JUnit XML for this step}

   #### Summary
   {analysis of this step's stack trace and log context}

   #### Evidence
   {stack trace extracted from {step_name}-build-log.txt or build-log.txt context}

   #### Artifacts Examined
   - `.work/prow-job-analyze-test-failure/{build_id}/logs/{step_name}-build-log.txt`
   - `.work/prow-job-analyze-test-failure/{build_id}/logs/{step_name}/` *(step artifacts if downloaded)*

   ---

   ## Cluster Diagnostics
   *(Only if must-gather was analyzed — same structure as Branch A; include per-cluster
   sections as appropriate for standard or HyperShift patterns)*

   ---

   ## Aggregated Root Cause

   ### Failed Steps Summary
   | Step | One-line Failure |
   |------|-----------------|
   | {step_name_1} | {summary} |
   | {step_name_2} | {summary} |
   | ... | ... |

   ### Timeline
   *(Emit one entry per failed step. If interval data cannot be mapped to a specific
   step, omit the Timeline section entirely rather than showing a misleading single window.)*

   - **{step_name_1}**: started {from timestamp} — failed {to timestamp}
     - Cluster events during this window: {cluster-event} at {timestamp}
   - **{step_name_2}**: started {from timestamp} — failed {to timestamp}
     - Cluster events during this window: {cluster-event} at {timestamp}
   - *(repeat for each failed step with mappable interval data)*

   ### Root Cause Hypothesis
   {synthesized root cause drawn from all per-step findings (install + test steps),
   per-step interval events, symptom labels, and cluster diagnostics; clearly
   identify whether one step is the root cause or whether multiple independent
   failures occurred}

   ### Recommendations
   - {actionable next step 1}
   - {actionable next step 2}

   ---

   ## Artifacts
   - **Test artifacts**: `.work/prow-job-analyze-test-failure/{build_id}/logs/`
   - **Must-gather**: `.work/prow-job-analyze-test-failure/{build_id}/must-gather*/logs/` *(if extracted)*
   ```

### Step 5.5: Ask User About JIRA Export

After completing the analysis, ask the user if they want to export to JIRA format.

1. **Ask user using AskUserQuestion tool**

   ```
   Question: "Analysis complete! Would you like to export this to JIRA format?"
   Header: "JIRA Export"
   Options:
     - Label: "Yes - Export to JIRA (OCPBUGS format)"
       Description: "Generate JIRA-formatted output using OCPBUGS template for easy copy-paste"
     - Label: "No - Skip JIRA export"
       Description: "Only keep the Markdown analysis file"
   ```

2. **If user chooses "Yes - Export to JIRA (OCPBUGS format)"**

   Generate `.work/prow-job-analyze-test-failure/{build_id}/analysis-jira.txt` using OCPBUGS format.
   Branch on whether `test_name` was provided:

   **Branch A (test_name provided — singular test):**

   ```
   Description of problem:
   [Summarize the test failure in 1-2 sentences]

   Version-Release number of selected component (if applicable):
   [OpenShift version from prowjob, if available]

   How reproducible:
   [Based on test history - e.g., "Intermittent", "Always", "Sometimes in this job configuration"]

   Steps to Reproduce:
   1. Run Prow CI job: [job-name]
   2. Execute test: [test-name]
   3. [Any specific conditions that triggered the failure]

   Actual results:
   [What actually happened - include error messages, stack traces]
   {noformat}
   [Stack trace or error output]
   {noformat}

   Expected results:
   [What should have happened - test should pass]

   Additional info:
   [Include correlation analysis, timeline, affected components]

   Job Details:
   - Job URL: [prow-job-url]
   - Build ID: {{build_id}}
   - Test artifacts: {{.work/prow-job-analyze-test-failure/{build_id}/}}

   [If must-gather was analyzed, include cluster diagnostics summary]

   Root Cause Analysis:
   [Detailed analysis from Step 5]
   ```

   **Branch B (test_name omitted — multi-step report):**

   ```
   Description of problem:
   [Summarize the overall CI job failure — which steps failed and the likely root cause]

   Version-Release number of selected component (if applicable):
   [OpenShift version from prowjob, if available]

   How reproducible:
   [Based on test history - e.g., "Intermittent", "Always", "Sometimes in this job configuration"]

   Steps to Reproduce:
   1. Run Prow CI job: [job-name]
   2. Observe failures in the following CI steps: [step_name_1], [step_name_2], ...

   Failed Steps:
   [For each failed step discovered in Step 4.2 Branch B, emit one block:]

   === Step: [step_name] ===
   Failure message: [failure_message from JUnit XML]

   Actual results:
   {noformat}
   [Stack trace or error output for this step]
   {noformat}

   Expected results:
   [This step should complete successfully]

   [Repeat for each failed step]

   Additional info:
   [Aggregated root cause hypothesis, timeline, affected components from the multi-step report]

   Job Details:
   - Job URL: [prow-job-url]
   - Build ID: {{build_id}}
   - Test artifacts: {{.work/prow-job-analyze-test-failure/{build_id}/}}

   [If must-gather was analyzed, include cluster diagnostics summary]

   Root Cause Analysis:
   [Synthesized root cause from the "Aggregated Root Cause" section of Step 5]
   ```

3. **Display completion message**

   If JIRA export chosen:
   ```text
   ✅ Analysis complete!
   📄 Reports generated:
   - Markdown: .work/prow-job-analyze-test-failure/{build_id}/analysis.md
   - JIRA (OCPBUGS format): .work/prow-job-analyze-test-failure/{build_id}/analysis-jira.txt

   💡 Tip: Copy the contents of analysis-jira.txt directly into a JIRA OCPBUGS issue
   ```

   If JIRA export skipped:
   ```text
   ✅ Analysis complete!
   📄 Report generated:
   - Markdown: .work/prow-job-analyze-test-failure/{build_id}/analysis.md
   ```

## Error Handling

Handle errors in the same way as "Error handling" in "Prow Job Analyze Resource" skill, with these additional must-gather-specific cases:

1. **Must-gather not available**
   - If `gcloud storage ls` returns 404 for must-gather.tar, this is expected (not all jobs have must-gather)
   - Silently skip must-gather analysis - do NOT warn the user
   - Continue to Step 5 preserving scope: Branch A (singular test) or Branch B (multi-step) as determined by whether `test_name` was provided

2. **Must-gather extraction fails**
   - If download or extraction fails, warn the user but continue with test analysis
   - Display: "WARNING: Must-gather extraction failed: {error}. Continuing without cluster diagnostics."
   - Continue to Step 5 preserving scope: Branch A (singular test) or Branch B (multi-step) as determined by whether `test_name` was provided

3. **Analysis scripts not found**
   - If `find` command returns empty (no scripts found), warn the user
   - Display: "WARNING: Must-gather analysis scripts not installed. Install the must-gather plugin from openshift-eng/ai-helpers for cluster diagnostics."
   - Continue to Step 5 preserving scope: Branch A (singular test) or Branch B (multi-step) as determined by whether `test_name` was provided

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
