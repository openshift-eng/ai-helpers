---
description: Analyze details about a Component Readiness regression and suggest next steps
argument-hint: <regression id>
---

## Name

ci:analyze-regression

## Synopsis

```
/ci:analyze-regression <regression id>
```

## Description

The `ci:analyze-regression` command analyzes details for a specific Component Readiness regression and suggests next steps for investigation.

The command performs a full analysis regardless of whether the regression has been triaged. For triaged regressions, it also fetches the linked JIRA issue to analyze whether someone is actively working on the fix or if the issue needs attention.

This command is useful for:

- Understanding regression patterns and failure modes
- Checking if a triaged regression is being actively worked on or needs attention
- Identifying related regressions that might be caused by the same issue
- Getting pointers on where to investigate next

## Implementation

1. **Load CI Context**: Read all documentation files in `plugins/ci/docs/` for context on tests, jobs, and CI conventions. These contain important notes on specific test frameworks, job ownership, and debugging guidance that should inform the analysis.

   ```bash
   ls plugins/ci/docs/
   ```

   Read each file found. Keep this context in mind throughout the analysis — it may affect how you interpret failure patterns, who to recommend contacting, or what the root cause is likely to be.

2. **Parse Arguments**: Extract regression ID

   - Regression ID format: Integer ID from Component Readiness
   - Example: 34446

3. **Fetch Regression Details**: Use the `fetch-regression-details` skill

   Run the Python script to fetch comprehensive regression data:

   ```bash
   script_path="plugins/ci/skills/fetch-regression-details/fetch_regression_details.py"
   regression_data=$(python3 "$script_path" <regression_id> --format json)
   ```

   The skill automatically:
   - Fetches regression metadata from: https://sippy.dptools.openshift.org/api/component_readiness/regressions/<regression_id>
   - Fetches test details and parses job statistics
   - Groups failed job runs by job name with pass sequences

   Extract the following from the JSON response:
   - `test_name`: Full test name
   - `release` and `base_release`: Version information
   - `component` and `capability`: Ownership mapping
   - `variants`: Platform/topology combinations where test is failing
   - `opened` and `closed`: Regression timeline
   - `triages`: Existing JIRA tickets
   - `analysis_status`: Integer status code (negative indicates problems, -1000 indicates failed fix)
   - `analysis_explanations`: Human-readable explanations for the status
   - `test_details_url`: Link to Sippy test details (API URL - must be converted to UI URL before displaying, see note below)
   - `sample_failed_jobs`: Dictionary keyed by job name, each containing:
     - `pass_sequence`: Chronological S/F pattern (newest to oldest)
     - `failed_runs`: List of failed runs with job_url, job_run_id, start_time

   **Converting `test_details_url` to UI URL**: The `test_details_url` from the API is an API endpoint not suitable for display or bug reports. Convert it to the UI URL by replacing the base path. The query parameters are identical:

   ```bash
   # Convert API URL to UI URL
   test_details_ui_url=$(echo "$test_details_url" | sed 's|https://sippy.dptools.openshift.org/api/component_readiness/test_details|https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/test_details|')
   ```

   Always use the converted `test_details_ui_url` when displaying the link in the report or including it in bug descriptions.

   See `plugins/ci/skills/fetch-regression-details/SKILL.md` for complete implementation details.

4. **Fetch Global Test Report**: Use the `fetch-test-report` skill to check how this test is doing globally

   Use the test name and release from the regression data to fetch the global test report with per-variant breakdown:

   ```bash
   # Extract test name and release from regression data
   test_name=$(echo "$regression_data" | jq -r '.test_name')
   release=$(echo "$regression_data" | jq -r '.release')

   # Fetch per-variant breakdown to see which job types are affected
   script_path="plugins/ci/skills/fetch-test-report/fetch_test_report.py"
   test_report=$(python3 "$script_path" "$test_name" --release "$release" --no-collapse --format json)
   ```

   **Analyze the test report**:

   - **Global pass rate**: Check the overall pass rate across all variants. A low pass rate confirms a widespread issue; a high pass rate with the regression suggests the problem is variant-specific.
   - **Per-variant breakdown**: With `--no-collapse`, each row shows a specific variant combo (e.g., `["aws", "ovn", "amd64", "upgrade-micro"]`). Compare pass rates across variants to identify if the failure is platform-specific, network-specific, or upgrade-specific.
   - **Open bugs**: If `open_bugs > 0`, someone has already filed a Jira bug mentioning this test. This bug may not yet be triaged in Component Readiness. Note these bugs in the report — they could be used to triage the regression without filing a duplicate.
   - **Trend**: Check `net_working_improvement` — positive means improving, negative means getting worse.

   Include the global test report findings in Section 1 of the final report.

5. **Check Triage Status and Fetch JIRA Progress**: Determine triage state and analyze bug progress

   Check if the regression has already been triaged and fetch JIRA details:

   ```bash
   # Check if regression has triages
   triage_count=$(echo "$regression_data" | jq '.triages | length')
   ```

   **If `triage_count > 0` (regression is triaged)**:

   This means a human has already attributed this regression to a specific bug. For each triage entry, fetch the JIRA issue to analyze progress. Also check if step 4's test report found open bugs that may be related.

   ```bash
   # Check if JIRA_TOKEN environment variable is set
   if [ -z "$JIRA_TOKEN" ]; then
     echo "Warning: JIRA_TOKEN environment variable not set. Skipping JIRA progress analysis."
   else
     # For each triage, fetch JIRA details using the fetch-jira-issue skill
     jira_script="plugins/ci/skills/fetch-jira-issue/fetch_jira_issue.py"
     for jira_key in $(echo "$regression_data" | jq -r '.triages[].jira_key'); do
       jira_data=$(python3 "$jira_script" "$jira_key" --format json)
     done
   fi
   ```

   The `fetch-jira-issue` skill automatically classifies progress. Extract the classification:

   ```bash
   progress_level=$(echo "$jira_data" | jq -r '.progress.level')
   progress_reason=$(echo "$jira_data" | jq -r '.progress.reason')
   assignee=$(echo "$jira_data" | jq -r '.assignee.display_name // "Unassigned"')
   linked_prs=$(echo "$jira_data" | jq -r '.linked_prs | length')
   ```

   See `plugins/ci/skills/fetch-jira-issue/SKILL.md` for complete implementation details.

   **Progress levels returned by the skill**:

   - **ACTIVE**: Status is ASSIGNED/IN PROGRESS with recent activity, PRs linked, or recent comments
   - **STALLED**: Status is ASSIGNED but no activity in 14+ days
   - **NEEDS_ATTENTION**: Status is NEW/OPEN with no assignee or no recent progress
   - **RESOLVED**: Status is Closed/Verified

   **Classification Output**:

   ```
   JIRA Progress Analysis:
   - OCPBUGS-12345: 🟢 ACTIVE - Assigned to user@redhat.com, PR in review (2 days ago)
   - OCPBUGS-12345: 🟡 STALLED - Assigned but no activity in 21 days
   - OCPBUGS-12345: 🔴 NEEDS ATTENTION - Status NEW, no assignee, no comments
   ```

   **Note for Failed Fixes (analysis_status == -1000)**:
   - This indicates the test is still failing AFTER the triage was resolved
   - Flag: "⚠️ FAILED FIX: Test continues to fail after triage was resolved"
   - Recommend: Re-opening the bug or filing a new one

   **If `triage_count == 0` (regression is NOT triaged)**:
   - Note that no bug has been filed yet
   - If step 4's test report found `open_bugs > 0`, note these — someone may have filed a bug that hasn't been triaged yet
   - Continue with full investigation (steps 6-11)
   - Bug filing recommendations will be provided in step 12

   **Always continue to step 6** regardless of triage status to provide full analysis.

6. **Interpret Regression Data**: Analyze failure patterns from `sample_failed_jobs`

   Parse the `sample_failed_jobs` dictionary from the regression data:

   ```bash
   # Extract and analyze each job
   echo "$regression_data" | jq -r '.sample_failed_jobs | to_entries | .[] | "\(.key)|\(.value.pass_sequence)|\(.value.failed_runs | length)"'
   ```

   - **Identify Jobs with Most Failures**:
     - Iterate through the `sample_failed_jobs` dictionary keys (job names)
     - Count `failed_runs` array length for each job: `echo "$regression_data" | jq '.sample_failed_jobs["job-name"].failed_runs | length'`
     - Sort jobs by failure count (descending) to identify the most impacted jobs
     - Example: Job A has 18 failures, Job B has 1 failure → Job A is the primary concern

   - **Analyze Pass Sequence Patterns**: For each job, examine the `pass_sequence` string.

     **CRITICAL: Reading Direction**
     - The pass_sequence is ordered **newest to oldest** (left = most recent, right = oldest)
     - First character = most recent job run
     - Last character = oldest job run
     - Example: `FFFSSSSSSS` means: 3 most recent runs failed, 7 older runs passed

     **Pattern 1: Permafailing Test**
     - `pass_sequence` starts with many "F"s at the LEFT (e.g., `FFFFFFFFFF` or `FFFFFFFSS`)
     - The LEFT side (most recent runs) shows consistent failures
     - Example: `FFFFFFFFFFFFFFFFFF` - leftmost 18 characters are all F = 18 most recent runs all failed
     - Interpretation: Test is currently broken and consistently failing
     - Action: High priority - test is completely broken for this job variant

     **Pattern 2: Resolved Issue**
     - `pass_sequence` starts with "S"s at the LEFT, with "F"s toward the RIGHT (e.g., `SSSSSFFFFF` or `SSSSSFFFFFSS`)
     - The LEFT side (most recent runs) shows successes, RIGHT side (older runs) shows failures
     - Example: `SSSSFFFFFFFFFFFF` - leftmost 4 chars are S (recent passes), rightward chars are F (older failures)
     - Example: `SSSSSSSSSSSSSSSSSSFFSFFF` - many S's on left (recent passes), F's on right (older failures)
     - Interpretation: The problem existed in older runs but has been resolved in recent runs
     - Action: Lower priority - verify if issue is truly resolved or if more monitoring is needed

     **Pattern 3: Flaky Test**
     - `pass_sequence` shows "F"s and "S"s interspersed throughout (e.g., `SFSFSFSFSF` or `FSSFFSSFF`)
     - No consistent block of failures - failures are scattered across the sequence
     - Example: `SSFSSFSSFSSF` shows intermittent failures mixed with successes
     - Interpretation: Test appears flaky rather than consistently failing
     - Action: May require test stabilization or flake investigation rather than product bug

     **Pattern 4: Recent Regression**
     - `pass_sequence` starts with "F"s at the LEFT, followed by "S"s toward the RIGHT (e.g., `FFSSSSSSSSS`)
     - The LEFT side (most recent runs) shows new failures, RIGHT side (older runs) shows the test was passing
     - Example: `FFFFFSSSSSSSSSS` - leftmost 5 chars are F (recent failures), rightward chars are S (older successes)
     - Interpretation: Test was passing historically but has recently started failing
     - Action: High priority - recent regression, investigate recent code changes

   - **Generate Pattern Summary**: Create a summary for each job:
     - Job name
     - Total failed runs
     - Pass sequence pattern classification (permafail / resolved / flaky / recent regression)
     - Recommended priority level
     - Suggested next steps

   **Example Analysis**:

   Given this `sample_failed_jobs` structure:
   ```json
   {
     "periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-ipv4-rhcos10-techpreview": {
       "pass_sequence": "FFFFFFFFFFFFFFFFFF",
       "failed_runs": [/* 18 failed runs */]
     },
     "periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-techpreview": {
       "pass_sequence": "SSFSSSSSSSS",
       "failed_runs": [/* 1 failed run */]
     },
     "periodic-ci-openshift-release-master-nightly-4.22-e2e-aws-example": {
       "pass_sequence": "SSSSSSSSSSSSSSSSSSFFSFFF",
       "failed_runs": [/* 5 failed runs */]
     }
   }
   ```

   **Remember: LEFT = newest, RIGHT = oldest**

   Pattern analysis output:
   - **Job 1** (18 failures): `FFFFFFFFFFFFFFFFFF`
     - Reading: All 18 characters are F, starting from the LEFT (newest)
     - Classification: **Permafail** - most recent runs are all failing
     - Priority: **High**
     - Action: "Test is completely broken for this metal+ovn+ipv4+rhcos10 variant. Investigate immediately."
   - **Job 2** (1 failure): `SSFSSSSSSSS`
     - Reading: LEFT (newest) starts with SS, then one F in position 3, rest are S
     - Classification: **Flaky** - isolated failure in mostly passing runs
     - Priority: **Low**
     - Action: "Single recent failure in mostly passing job. Monitor for pattern or investigate if recurring."
   - **Job 3** (5 failures): `SSSSSSSSSSSSSSSSSSFFSFFF`
     - Reading: LEFT (newest) has 18 S's = most recent 18 runs passed; RIGHT (oldest) has FFSFFF = older runs had failures
     - Classification: **Resolved** - failures were in OLDER runs, recent runs are passing
     - Priority: **Low**
     - Action: "Issue appears to have been resolved. The failures occurred in older runs, not recent ones."

7. **Analyze Failure Output Consistency**: Use the `fetch-test-runs` skill

   Use the `fetch-test-runs` skill to fetch and analyze actual test failure outputs from all failed job runs. This helps determine if all failures have the same root cause or if there are multiple issues.

   **Implementation**:

   ```bash
   # Extract test_id from regression data (already fetched in step 3)
   test_id=$(echo "$regression_data" | jq -r '.test_id')

   # Collect all job_run_ids from sample_failed_jobs
   # This creates a comma-separated list of all failed job run IDs across all jobs
   job_run_ids=$(echo "$regression_data" | jq -r '
     .sample_failed_jobs
     | to_entries[]
     | .value.failed_runs[]
     | .job_run_id
   ' | tr '\n' ',' | sed 's/,$//')

   # Use the fetch-test-runs skill
   script_path="plugins/ci/skills/fetch-test-runs/fetch_test_runs.py"
   output_analysis=$(python3 "$script_path" "$test_id" "$job_run_ids" --format json)
   ```

   The skill fetches raw test failure outputs from Sippy API.

   See `plugins/ci/skills/fetch-test-runs/SKILL.md` for complete implementation details.

   **Parse Results and Analyze with AI**:

   ```bash
   # Check if fetch was successful
   success=$(echo "$output_analysis" | jq -r '.success')

   if [ "$success" = "true" ]; then
     # Extract outputs array
     outputs=$(echo "$output_analysis" | jq -r '.outputs')
     num_outputs=$(echo "$outputs" | jq 'length')

     echo "Fetched $num_outputs test failure outputs"

     # AI ANALYSIS: Compare the outputs for similarity
     # Examine each output message to determine:
     # 1. How many failures show the same or very similar error messages
     # 2. What percentage of failures are consistent
     # 3. What the common error pattern is (if any)
     # 4. Extract file references, API paths, or resource names from error messages
     #
     # The outputs are in format: {"url": "...", "output": "error text", "test_name": "..."}
     #
     # Classify consistency:
     # - Highly Consistent (>90%): All/nearly all show same error -> single root cause
     # - Moderately Consistent (50-90%): Most share patterns -> primary issue with variation
     # - Inconsistent (<50%): Different errors -> multiple causes or environmental issues
     #
     # Extract from error messages:
     # - File/line references (e.g., "discovery.go:145")
     # - API/resource paths (e.g., "/apis/stable.e2e-validating-admission-policy-1181/")
     # - Common error phrases (e.g., "server could not find the requested resource")

   else
     # API not available - this is acceptable, continue without output analysis
     error=$(echo "$output_analysis" | jq -r '.error')
     echo "Note: Test output analysis unavailable - $error"
     echo "Continuing with other analysis steps..."
   fi
   ```

   **How to Analyze Outputs with AI**:

   Read through the failure outputs and identify patterns:

   1. **Compare Error Messages**: Count how many outputs have identical or very similar messages
      - Example: If 17 out of 18 say "the server could not find the requested resource", that's 94% consistency

   2. **Extract Common Elements**: Look for shared components in the error messages
      - File references: "k8s.io/kubernetes/test/e2e/apimachinery/discovery.go:145"
      - API paths: "/apis/stable.e2e-validating-admission-policy-1181/"
      - Error phrases: "server could not find the requested resource"

   3. **Classify Consistency**:
      - **Highly Consistent** (>90%): Single root cause - all failures show same error
      - **Moderately Consistent** (50-90%): Primary issue - most share patterns with some variation
      - **Inconsistent** (<50%): Multiple causes - failures show different error types

   4. **Determine Root Cause**: Based on the common error message and extracted information, infer what the underlying issue likely is
      - Example: "API endpoint not available" if errors mention missing API resources
      - Example: "Timeout issue" if errors mention timeouts or waiting conditions

8. **Determine Regression Start Date**: Use the `fetch-test-runs` skill with full history

   For the job with the most failures (identified in step 6), fetch the complete test run history including successes to determine when the regression started. Use 28 days of history to ensure we can find the regression start point.

   **Implementation**:

   ```bash
   # Get the job name with the most failures from step 6 analysis
   # This is the first job in the sorted list (sorted by failure count descending)
   most_failed_job=$(echo "$regression_data" | jq -r '
     .sample_failed_jobs
     | to_entries
     | sort_by(.value.failed_runs | length)
     | reverse
     | .[0].key
   ')

   # Fetch all test runs (including successes) for this specific job, going back 28 days
   script_path="plugins/ci/skills/fetch-test-runs/fetch_test_runs.py"
   job_history=$(python3 "$script_path" "$test_id" --include-success --prowjob-name "$most_failed_job" --start-days-ago 28 --exclude-output --format json)
   ```

   **Analyze the Run History**:

   The runs are returned in order from most recent to least recent. Iterate through them to find when failures started:

   ```bash
   # Check if fetch was successful
   if [ "$(echo "$job_history" | jq -r '.success')" = "true" ]; then
     runs=$(echo "$job_history" | jq -r '.runs')
     num_runs=$(echo "$runs" | jq 'length')

     echo "Analyzing $num_runs test runs for regression start date..."

     # AI ANALYSIS: Iterate through runs from newest to oldest
     # Look for the transition point where failures began
     #
     # The goal is to find the approximate date when failures started occurring
     # more frequently. Look for patterns like:
     # - A series of recent failures followed by older successes
     # - A clear transition point from passing to failing
     #
     # For each run, check the 'success' field (true/false) and 'timestamp' or 'start_time'
   fi
   ```

   **How to Determine Regression Start Date with AI**:

   1. **Scan from Newest to Oldest**: Walk through the runs array (index 0 = newest)
      - Track the pattern of success/failure as you go back in time

   2. **Look for Transition Point**: Find where the test changed from mostly passing to mostly failing
      - Example: If runs are [F, F, F, F, F, S, S, S, S, S, S, S], the regression likely started around the 5th run from newest

   3. **Identify the First Failure in a Failure Streak**:
      - Find the oldest failure that's part of the current regression
      - The run just before that (if it was a success) marks the approximate start

   4. **Handle Edge Cases**:
      - If test has always been failing in available history → cannot determine start date
      - If test is flaky (mixed S/F throughout) → cannot determine clear start date
      - If pattern is unclear → do not include this in the report

   5. **Report the Findings** (only if a clear start date can be determined):
      - Report the job URL of the first failure in the regression
      - Report the timestamp/date when that run occurred
      - Example: "Regression appears to have started on 2026-01-15 with job run: https://prow.ci.openshift.org/view/gs/..."

   **Output Format** (only include if start date can be determined):

   ```
   Regression Start Analysis:
   - Job Analyzed: periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn
   - Approximate Start Date: 2026-01-15
   - First Failing Run: https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...
   - Pattern: 18 consecutive failures followed by 12 successes
   ```

   **Note**: If the API is unavailable or no clear start date can be determined, skip this section entirely. Do not include inconclusive results.

9. **Identify Suspect PRs in Payload**: Use `fetch-prowjob-json` and `fetch-new-prs-in-payload` skills

   **Only perform this step if step 8 successfully identified a clear regression start point** (i.e., a first failing run URL exists). If step 8 was skipped or inconclusive, skip this step entirely.

   This step identifies pull requests that may have caused the regression by examining what was new in the payload where failures began.

   **Step 9a: Get the payload tag from the first failing run**

   Use the `fetch-prowjob-json` skill to fetch the prowjob.json for the first failing run identified in step 8.

   ```bash
   # The first_failing_run_url comes from step 8
   # Use the fetch-prowjob-json skill to convert to gcsweb URL and fetch
   # See plugins/ci/skills/fetch-prowjob-json/SKILL.md for URL conversion details
   #
   # Extract these annotations:
   payload_tag=$( ... )       # metadata.annotations["release.openshift.io/tag"]
   from_tag=$( ... )          # metadata.annotations["release.openshift.io/from-tag"] (may not exist)
   ```

   - `payload_tag`: The payload the cluster was tested against (or upgraded to for upgrade jobs)
   - `from_tag`: The original version before upgrade (only present on upgrade jobs). If present, note this in the report as it helps distinguish whether a regression is in the upgrade path itself vs the target version.

   If the prowjob.json cannot be fetched or the `release.openshift.io/tag` annotation is missing (e.g., manually triggered jobs), skip the rest of this step.

   **Step 9b: Fetch new PRs in the payload**

   ```bash
   script_path="plugins/ci/skills/fetch-new-prs-in-payload/fetch_new_prs_in_payload.py"
   pr_data=$(python3 "$script_path" "$payload_tag" --format json)
   ```

   See `plugins/ci/skills/fetch-new-prs-in-payload/SKILL.md` for complete implementation details.

   **Step 9c: Identify potentially related PRs**

   From the list of new PRs, identify candidates that might be related to the regression. Filter based on:

   1. **Component match**: PR component name matches or overlaps with the regression's `component` or `capability`
   2. **Repository match**: PR is from a repo related to the failing test (e.g., a test in `[sig-network]` and a PR from `openshift/ovn-kubernetes`)
   3. **Title keywords**: PR description contains keywords related to the test name, error messages from step 7, or the affected subsystem
   4. **Bug association**: PR has a `bug_url` referencing a fix for something in the same area

   Select a maximum of **5** candidate PRs to investigate (to avoid excessive API calls). Prioritize PRs whose component or repo most closely matches the regression.

   If no PRs look related based on filtering, note that in the report and skip step 9d.

   **Step 9d: Check PR details with GitHub CLI**

   For each candidate PR (up to 5), use the `gh` CLI to fetch the PR description and diff summary:

   ```bash
   # Check if gh CLI is available
   if command -v gh &>/dev/null; then
     # Extract org/repo and PR number from the PR URL
     # e.g., https://github.com/openshift/machine-config-operator/pull/5509
     # → owner=openshift, repo=machine-config-operator, pr_number=5509

     # Fetch PR details (title, body, changed files)
     gh pr view "$pr_number" --repo "$owner/$repo" --json title,body,files,labels

     # Fetch the diff summary (file names and change counts)
     gh pr diff "$pr_number" --repo "$owner/$repo" --stat
   else
     echo "Note: gh CLI not available. Showing PR URLs only - install gh for deeper analysis."
   fi
   ```

   **Analyze each PR for relevance**:

   - Read the PR description and diff to determine if the changes could plausibly affect the failing test
   - Look for changes to files, packages, or APIs referenced in the test error messages (from step 7)
   - Note if the PR modifies test infrastructure, API schemas, or operator behavior relevant to the regression
   - Classify each PR as:
     - **Likely related**: Changes directly affect the area where the test is failing
     - **Possibly related**: Changes are in a related subsystem but not directly in the failure path
     - **Unlikely related**: Changes appear unrelated to the test failure

   **Output Format**:

   ```
   Suspect PRs in Payload (payload: 4.22.0-0.ci-2026-02-06-195709):
   Upgrade From: 4.22.0-0.ci-2026-02-05-195709

   Investigated 3 of 17 new PRs in this payload:

   1. [LIKELY] openshift/machine-config-operator#5509
      "Set NodeDegraded MCN condition when node state annotation is set to Degraded"
      Bug: OCPBUGS-67229
      Relevance: Changes MCN condition logic which is tested by the failing test
      Files changed: pkg/controller/node/status.go (+45/-12)

   2. [POSSIBLY] openshift/hypershift#7470
      "use InfraStatus.APIPort for custom DNS kubeconfig"
      Bug: OCPBUGS-72258
      Relevance: Modifies API port handling, test involves API connectivity

   3. [UNLIKELY] openshift/router#707
      "Updating openshift-enterprise-haproxy-router-container image"
      Relevance: Router image update, unrelated to test failure area
   ```

10. **Identify Related Regressions**: Use the `list-regressions` skill to find similar failing tests

   Use the `list-regressions` skill with test name filtering to find related regressions that may share the same root cause. Run two queries: one for the exact same test (different variants) and one for similar tests (same namespace/sig).

   **Implementation**:

   ```bash
   # Extract test name and release from regression data
   test_name=$(echo "$regression_data" | jq -r '.test_name')
   release=$(echo "$regression_data" | jq -r '.release')
   script_path="plugins/teams/skills/list-regressions/list_regressions.py"

   # Query 1: Find regressions for the exact same test across all variants
   same_test_regressions=$(python3 "$script_path" --release "$release" --test-name "$test_name")

   # Query 2: Find regressions for similar tests (e.g., same namespace)
   # Extract the namespace from the test name (e.g., "openshift-machine-config-operator")
   # and search for other tests mentioning it
   # Choose a distinctive substring from the test name that identifies related tests
   similar_test_regressions=$(python3 "$script_path" --release "$release" --test-name-contains "<distinctive_substring>")
   ```

   **Note**: `--test-name` and `--test-name-contains` cannot be combined with `--components` or `--team` — they search across all components automatically.

   **Analyze Related Regressions**:

   From the filtered results, identify regressions related to the current one:

   - **Same test, different variants**: From the `--test-name` query — other regressions for the same test but with different variant combinations (e.g., same test failing on both `aws` and `metal` platforms)
   - **Similar test names**: From the `--test-name-contains` query — regressions with test names that share a common prefix or test suite (e.g., same `[sig-api-machinery]` tests)

   For each related regression found, note:
   - Regression ID
   - Test name (if different from the current one)
   - Variants where it is failing
   - Whether it is triaged (has entries in `triages` array) and to which JIRA bug
   - Whether it is open or closed

   For each related regression that will be included in a bug report or triage, fetch its details to get the `test_details_url`:

   ```bash
   # Fetch details for a related regression to get its test_details_url
   related_data=$(python3 "plugins/ci/skills/fetch-regression-details/fetch_regression_details.py" <related_regression_id> --format json)
   related_test_details_url=$(echo "$related_data" | jq -r '.test_details_url')
   # Convert to UI URL
   related_test_details_ui_url=$(echo "$related_test_details_url" | sed 's|https://sippy.dptools.openshift.org/api/component_readiness/test_details|https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/test_details|')
   ```

   **Summarize variant patterns**:
   - Identify if the test is failing across all jobs of one Platform variant (e.g., all `metal` jobs)
   - Identify if failures cluster around a specific Upgrade, Network, or Topology variant
   - Note any variant combinations that are NOT failing (helps narrow root cause)

11. **Find Related Triages and Untriaged Regressions**: Use the `fetch-related-triages` skill

   Query the Sippy API to find existing triage records and untriaged regressions related to this regression:

   ```bash
   script_path="plugins/ci/skills/fetch-related-triages/fetch_related_triages.py"
   related=$(python3 "$script_path" <regression_id> --format json)
   ```

   See `plugins/ci/skills/fetch-related-triages/SKILL.md` for complete implementation details.

   The API returns matches based on similarly named tests and shared last failure times, each with a confidence level (1-10):
   - **10**: High confidence — same or very closely related tests
   - **5**: Medium confidence — similarly named tests matched by edit distance
   - **2**: Low confidence — regressions sharing the same last failure timestamp (same job runs)

   **Analyze the results**:

   - **`triaged_matches`**: Existing triage records that look related. For each match:
     - Note the `triage_id`, `jira_key`, `jira_status`, and `confidence_level`
     - High confidence matches (>=5) with open JIRA bugs are strong candidates for adding this regression to
     - Low confidence matches or closed JIRA bugs are informational
     - Present these in the report as potential triage targets

   - **`untriaged_regressions`**: Open regressions not yet triaged that appear related. These are candidates to be triaged together with the current regression under one bug. For each:
     - Note the `match_reason` (`similarly_named_test` or `same_last_failure`)
     - `similarly_named_test` with low `edit_distance` (0-2) are likely the same or very similar tests in different variants
     - `same_last_failure` regressions may share the same root cause (same failing job runs) but could be from different components

   **Combine with step 10 results**: Merge these findings with the related regressions found via `--test-name` in step 10. The two sources are complementary:
   - Step 10 finds regressions for the exact same test name (different variants)
   - This step finds regressions with similar test names AND existing triages that may already cover the issue

12. **Prepare Bug Filing Recommendations or Existing Bug Status**: Generate actionable information

   **Important**: Component Readiness regressions are treated as release blockers. Any bug filed for a regression should be conveyed to the user as a release blocker. See the [release blocker definition](https://github.com/openshift/enhancements/blob/master/dev-guide/release-blocker-definition.md) for details on the criteria and process.

   **If regression is NOT triaged** (no existing JIRA):
   - Component assignment (from test mappings)
   - If step 4's test report found `open_bugs > 0`, note these existing bugs — one may be suitable for triaging this regression without filing a duplicate
   - Bug summary suggestion based on failure pattern (informed by step 6 pattern analysis)
   - Bug description template including:
     - Test name and release
     - Test ID (`test_id` — the BigQuery/Component Readiness ID, e.g., `openshift-tests:abc123`)
     - Regression ID(s) — the Component Readiness regression ID(s) being triaged
     - Regression opened date
     - Affected variants
     - Failure patterns identified (permafail/flaky/resolved/recent)
     - Pass sequence analysis from step 6
     - **Global test report from step 4**: overall pass rate, per-variant breakdown, open bugs
     - **Failure output consistency analysis from step 7** (if available):
       - Common error message
       - Consistency percentage
       - Key debugging information (file references, resources, stack traces)
     - **Sippy Test Details report links** - this is critical for debugging:
       - Link for the current regression (converted `test_details_ui_url`)
       - Links for each related regression found in step 10 (each regression has its own `test_details_url` from the list-regressions data - convert each to UI URL)
     - Regression start date (if determined in step 8)
     - Suspect PRs from payload analysis (if determined in step 9) — include PR URLs and relevance classification for LIKELY and POSSIBLY related PRs
     - Related regressions (if any) with their regression IDs and test names
   - Triage type recommendation:
     - `product`: actual product issues (default)
     - `test`: clear issues in the test itself (especially for flaky patterns)
     - `ci-infra`: CI outages
     - `product-infra`: customer-facing outages (e.g., quay)

   **If regression IS triaged** (existing JIRA):
   - Note: "A bug already exists for this regression - do not file a duplicate"
   - Display JIRA key(s) with links
   - Show JIRA progress analysis from step 5:
     - 🟢 **ACTIVE**: Bug is being worked on, no action needed
     - 🟡 **STALLED**: Bug may need attention, consider commenting or reassigning
     - 🔴 **NEEDS ATTENTION**: Bug appears abandoned, consider taking ownership or escalating
   - **If analysis_status == -1000** (failed fix):
     - Recommend: Re-open the existing bug OR file a new bug if the failure mode is different
     - Provide new bug template if failure analysis suggests a different root cause

13. **Display Comprehensive Report**: Present findings in clear format

   **Section 1: Regression Summary**
   - Test name
   - Component
   - Regression opened/closed dates
   - Affected variants
   - Analysis status and explanations
   - Current triage status (none for untriaged regressions)
   - Global test report (from step 4): overall pass rate, trend, open bugs count
   - If open bugs exist, note them as potential triage targets

   **Section 2: Global Test Health** (from `fetch-test-report` skill with `--no-collapse`)
   - Overall pass rate across all variants for this release
   - Per-variant breakdown highlighting variants with low pass rates
   - Open bugs count — if > 0, list them as potential triage targets
   - Trend direction (improving/regressing/unchanged)

   **Section 3: Failure Pattern Analysis**
   - Jobs ranked by number of failures (most to least impacted)
   - For each job:
     - Job name
     - Total failed runs
     - Pass sequence visualization
     - Pattern classification:
       - **Permafail**: All or most recent runs failing
       - **Resolved**: Recent runs succeeding after a block of failures
       - **Flaky**: Sporadic failures interspersed with successes
       - **Recent Regression**: Recently started failing after consistent successes
     - Priority level (High/Medium/Low)
     - Recommended action
   - Overall assessment of regression severity

   **Section 4: Failure Output Analysis** (from `fetch-test-runs` skill)
   - Number of test outputs analyzed
   - Consistency classification (Highly Consistent / Moderately Consistent / Inconsistent)
   - Most common error message with occurrence count
   - Key debugging information:
     - File/line references
     - Resource or API paths
     - Error messages
   - Sample job URLs for manual inspection
   - **Note**: If the test outputs API is not available, this section will note: "Test output analysis not available"

   **Section 5: Regression Start Analysis** (only if determinable)
   - Job analyzed (the job with most failures)
   - Approximate start date of the regression
   - URL of the first failing job run
   - Pattern description (e.g., "18 consecutive failures followed by 12 successes")
   - **Note**: This section is omitted if no clear start date can be determined

   **Section 6: Suspect PRs in Payload** (only if regression start was determined)
   - Payload tag and upgrade-from tag (if applicable)
   - Total number of new PRs in the payload
   - Number of PRs investigated (up to 5)
   - For each investigated PR:
     - Relevance classification: LIKELY, POSSIBLY, or UNLIKELY
     - PR URL, title, and associated bug (if any)
     - Brief explanation of why it may or may not be related
     - Key files changed (from `gh pr diff --stat`)
   - **Note**: This section is omitted if step 8 did not determine a clear regression start, if the prowjob.json lacks release annotations, or if no PRs looked potentially related. It is also omitted if `gh` CLI is not available, though PR URLs are still listed.

   **Section 7: Related Regressions and Existing Triages** (from `fetch-related-triages` skill and `list-regressions --test-name`)
   - Existing triages that may cover this regression, ranked by confidence level (10 = high, 5 = medium, 2 = low)
   - For each existing triage: JIRA key, status, summary, triage type, confidence level, triage UI link
   - Untriaged regressions that appear related (same/similar tests, shared failure times)
   - Regressions for the exact same test in different variants (from step 10)
   - Recommendation: whether to add to an existing triage or file a new bug

14. **Offer to Triage**: After presenting the report, offer to triage the regression

   Based on the analysis, determine the appropriate triage action and ask the user if they want to proceed.

   **Generating the triage description**: Every triage record must include a `--description`. Generate a single concise sentence summarizing the failure, similar in style to a JIRA bug summary. Example: `"InsightsDataGather CRD not found - all InsightsRuntimeExtractor tests failing across platforms since Feb 6"`

   **Scenario A: Related triage record found on another regression** (from step 11)

   If step 11 found that a related regression already has a triage record (i.e., another regression for the same or similar test is already triaged to a JIRA bug), offer to add this regression to that existing triage. Also include any other untriaged related regressions found in steps 10 and 11.

   ```
   A related triage already exists:
   - Triage ID: 789
   - JIRA: https://issues.redhat.com/browse/OCPBUGS-12345
   - Type: product

   The following untriaged regressions could be added to this triage:
   - Regression <current_regression_id> (this regression)
   - Regression <related_id_1> (related, same test, different variant)
   - Regression <related_id_2> (related, same test, different variant)

   Would you like to add these regressions to the existing triage?
   ```

   If the user confirms, use the `triage-regression` skill to update the existing triage:

   ```bash
   # Obtain auth token from DPCR cluster (oc-auth skill)
   TOKEN=$(oc whoami -t --context="$DPCR_CONTEXT")

   # Only pass the new regression IDs to add - the script automatically
   # fetches existing regressions and merges them (safe additive behavior)
   new_regression_ids="<current_id>,<related_id_1>,<related_id_2>"

   # Generate a concise description from the analysis (see note below)
   description="<generated_description>"

   script_path="plugins/ci/skills/triage-regression/triage_regression.py"
   triage_result=$(python3 "$script_path" "$new_regression_ids" \
     --token "$TOKEN" \
     --triage-id <existing_triage_id> \
     --url "<existing_jira_url>" \
     --type "<existing_triage_type>" \
     --description "$description" \
     --format json)
   ```

   After triaging, extract the triage ID from the response and display both the JIRA URL and the triage UI link:

   ```bash
   triage_id=$(echo "$triage_result" | jq -r '.triage.id')
   ```

   Display to the user:
   ```
   Triage updated:
   - JIRA: <existing_jira_url>
   - Triage: https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/triages/<triage_id>
   ```

   **Note**: The triage-regression script automatically fetches the existing triage and merges its regressions with the new ones, so you only need to pass the regression IDs you want to add.

   **Scenario B: JIRA bug found but not triaged to any regression** (from step 5 or step 11)

   If step 5 found a linked JIRA bug on this regression's triage, or step 11 found a JIRA bug that looks related, or step 4's test report found `open_bugs > 0` (e.g., same component, similar error pattern) but no triage record exists yet, offer to create a new triage linking this regression and all related untriaged regressions to that bug.

   ```
   A related JIRA bug was found:
   - JIRA: https://issues.redhat.com/browse/OCPBUGS-67890
   - Summary: [bug summary from JIRA]

   The following regressions could be triaged to this bug:
   - Regression <current_regression_id> (this regression)
   - Regression <related_id_1> (related, same test, different variant)
   - Regression <related_id_2> (related, same test, different variant)

   Recommended triage type: product

   Would you like to create a triage record linking these regressions to this bug?
   ```

   If the user confirms, use the `triage-regression` skill to create a new triage:

   ```bash
   # Obtain auth token from DPCR cluster (oc-auth skill)
   TOKEN=$(oc whoami -t --context="$DPCR_CONTEXT")

   all_regression_ids="<current_id>,<related_id_1>,<related_id_2>"

   # Generate a concise description from the analysis (see note below)
   description="<generated_description>"

   script_path="plugins/ci/skills/triage-regression/triage_regression.py"
   triage_result=$(python3 "$script_path" "$all_regression_ids" \
     --token "$TOKEN" \
     --url "https://issues.redhat.com/browse/OCPBUGS-67890" \
     --type product \
     --description "$description" \
     --format json)
   ```

   After triaging, extract the triage ID from the response and display both the JIRA URL and the triage UI link:

   ```bash
   triage_id=$(echo "$triage_result" | jq -r '.triage.id')
   ```

   Display to the user:
   ```
   Triage created:
   - JIRA: https://issues.redhat.com/browse/OCPBUGS-67890
   - Triage: https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/triages/<triage_id>
   ```

   **Scenario C: No related triage or bug found**

   If no related triage record or JIRA bug was found, and the regression is untriaged, offer to create a new JIRA bug and triage all related regressions to it.

   ```
   No existing triage or related JIRA bug was found for this regression.

   Would you like me to create a JIRA bug and triage the following regressions to it?
   - Regression <current_regression_id> (this regression)
   - Regression <related_id_1> (related, same test, different variant)
   - Regression <related_id_2> (related, same test, different variant)

   Proposed bug details:
   - Project: OCPBUGS
   - Component: <component from regression data>
   - Summary: <suggested summary from step 12>
   - Triage type: <recommended type>
   ```

   If the user confirms, create the bug using the `/jira:create-bug` skill with the bug template from step 12. Apply the label `component-regression` to the bug (this label identifies bugs found through Component Readiness). The bug description must include:
   - Test name(s) — the full name of each affected test
   - Test ID(s) (`test_id` — the BigQuery/Component Readiness ID, e.g., `openshift-tests:abc123`)
   - Regression ID(s) — the Component Readiness regression ID(s) being triaged
   - Release
   - Regression opened date
   - Affected variants
   - Failure pattern analysis summary
   - Common error message (if available from step 7)
   - **Sippy Test Details report links** for each regression being triaged (convert each `test_details_url` from API to UI URL)
   - Related regression IDs and test names

   After the bug is created, mark it as a release blocker using the `set-release-blocker` skill (component readiness regressions are release blockers):

   ```bash
   script_path="plugins/ci/skills/set-release-blocker/set_release_blocker.py"
   python3 "$script_path" "<new_bug_key>" --format json
   ```

   See `plugins/ci/skills/set-release-blocker/SKILL.md` for details.

   Then use the `triage-regression` skill to triage all regressions to the new bug:

   ```bash
   # Obtain auth token from DPCR cluster (oc-auth skill)
   TOKEN=$(oc whoami -t --context="$DPCR_CONTEXT")

   all_regression_ids="<current_id>,<related_id_1>,<related_id_2>"

   # Generate a concise description from the analysis (see note below)
   description="<generated_description>"

   script_path="plugins/ci/skills/triage-regression/triage_regression.py"
   triage_result=$(python3 "$script_path" "$all_regression_ids" \
     --token "$TOKEN" \
     --url "https://issues.redhat.com/browse/<new_bug_key>" \
     --type <recommended_type> \
     --description "$description" \
     --format json)
   ```

   After triaging, extract the triage ID from the response and display both the JIRA URL and the triage UI link:

   ```bash
   triage_id=$(echo "$triage_result" | jq -r '.triage.id')
   ```

   Display to the user:
   ```
   Bug filed and triaged:
   - JIRA: https://issues.redhat.com/browse/<new_bug_key>
   - Release Blocker: Approved
   - Triage: https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/triages/<triage_id>
   ```

   **Scenario D: Regression is already triaged**

   If this regression already has a triage record (from step 5), do not offer to triage again. The report already shows the JIRA progress analysis.

   See `plugins/ci/skills/triage-regression/SKILL.md` for complete implementation details.

## Return Value

The command outputs a **Comprehensive Regression Analysis Report** for all regressions, with additional JIRA progress analysis for triaged regressions:

#### Regression Summary

- **Test Name**: Full test name
- **Analysis Status**: Integer status code (negative indicates problems)
  - **-1000**: Failed fix - test continues to fail after triage was resolved
  - **Other negative values**: Severity of the regression (lower = more severe)
- **Analysis Explanations**: Human-readable descriptions of the regression status
- **Component**: Auto-detected component from test mappings
- **Release**: OpenShift release version
- **Regression Status**: Open/Closed with dates
- **Affected Variants**: List of platform/topology variants where test is failing
- **Current Triage**: Existing JIRA tickets (if any)
- **Test Details URL**: Direct link to Sippy Test Details report (converted from API URL to UI URL)

#### Failure Pattern Analysis

- **Jobs Ranked by Impact**: List of jobs sorted by number of failures (descending)
- **For Each Job**:
  - Job name and variant details
  - Total number of failed runs
  - Pass sequence string (e.g., "FFFFFFFFFF" or "SFSFSFSF")
  - **Pattern Classification** (remember: LEFT = newest runs, RIGHT = oldest runs):
    - **Permafail**: "FFFFFFFFFF..." - F's at the LEFT (newest runs are failing). Test is currently broken.
    - **Resolved**: "SSSSSSFFFF..." - S's at the LEFT (newest runs passing), F's at the RIGHT (older runs failed). Issue has been fixed.
    - **Flaky**: "SFSFSFSFSF..." - Mixed S's and F's throughout. Test is unstable/flaky.
    - **Recent Regression**: "FFFFFSSSSSS..." - F's at the LEFT (newest runs failing), S's at the RIGHT (older runs passed). Test recently started failing.
  - **Priority Level**: High (permafail/recent regression), Medium (flaky with many failures), Low (resolved/occasional flakes)
  - **Recommended Action**: Next steps based on pattern (e.g., "Investigate recent code changes", "Stabilize flaky test", "Verify issue is resolved")
- **Overall Assessment**: Summary of regression severity across all jobs

#### Global Test Health

Generated using the `fetch-test-report` skill with `--no-collapse`:

- **Overall Pass Rate**: Aggregate pass rate across all variants for this release
- **Per-Variant Breakdown**: Pass rates for each variant combination, highlighting variants with low pass rates
- **Open Bugs**: Count of Jira bugs mentioning this test by name. If > 0, these bugs may be usable for triaging the regression without filing a duplicate.
- **Trend**: Whether the test is improving, regressing, or unchanged compared to the previous period

#### Failure Output Analysis

Generated using the `fetch-test-runs` skill (see `plugins/ci/skills/fetch-test-runs/SKILL.md`):

- **Number of Outputs Analyzed**: Total test outputs examined
- **Consistency Classification**:
  - **Highly Consistent** (>90% same): All or nearly all failures show identical error messages
  - **Moderately Consistent** (50-90% same): Most failures share common patterns
  - **Inconsistent** (<50% same): Failures show different error messages
- **Common Error Message**: Most frequent error message with occurrence count (e.g., "17/18 failures")
- **Key Debugging Information**:
  - File and line references where failure occurred
  - Resource or API endpoints being accessed
  - Extracted error messages
- **Sample URLs**: Links to representative failed job runs for manual inspection
- **Assessment**: Interpretation of consistency (e.g., "Single root cause - API endpoint not available")
- **Note**: If the test outputs API is not available, this section will note that the analysis could not be performed

#### Regression Start Analysis (only if determinable)

Generated using the `fetch-test-runs` skill with `--include-success` and `--prowjob-name`:

- **Job Analyzed**: The job with the most failures (from step 6)
- **Approximate Start Date**: When the test began failing more frequently
- **First Failing Run URL**: Link to the job run where the regression appears to have started
- **Pattern Description**: Summary of the pass/fail pattern (e.g., "18 consecutive failures followed by 12 successes")
- **Note**: This section is only included when a clear regression start date can be determined. It is omitted for:
  - Flaky tests with scattered failures
  - Tests that have been failing throughout the available history
  - When the API is unavailable
  - When the pattern is inconclusive

#### Suspect PRs in Payload (only if regression start was determined)

Generated using the `fetch-prowjob-json` and `fetch-new-prs-in-payload` skills:

- **Payload Tag**: The payload where the regression first appeared
- **Upgrade From Tag**: The pre-upgrade payload (for upgrade jobs only)
- **Total New PRs**: Number of PRs new in this payload
- **Investigated PRs**: Up to 5 PRs examined in detail via `gh` CLI
- **For Each Investigated PR**:
  - Relevance classification (LIKELY / POSSIBLY / UNLIKELY)
  - PR URL, title, and associated bug URL
  - Explanation of relevance to the regression
  - Summary of changed files
- **Note**: This section is only included when step 8 determined a clear regression start and the first failing run's prowjob.json has a `release.openshift.io/tag` annotation. Omitted if `gh` CLI is not available (PR URLs still listed without deep analysis).

#### Root Cause Analysis

- **Failure Patterns**: Common patterns identified across multiple job failures
- **Suspected Component**: Component/area likely responsible for the failure
- **Classification**: Whether the issue is infrastructure-related or a product bug

#### Related Regressions

- **Similar Failing Tests**: List of other regressions that appear similar
- **Common Patterns**: Shared error messages, stack traces, or failure modes
- **Variant Analysis**: Summary of which job variants are affected (e.g., all AWS jobs, all upgrade jobs). Cross-reference with the per-variant breakdown from the Global Test Health section.
- **Triaging Recommendation**: Whether these regressions should be grouped under a single JIRA ticket

#### Existing Triages and JIRA Progress

- **Triage Status**: Whether this regression has been triaged to a JIRA bug
- **Open Bugs from Test Report**: If step 4 found open bugs mentioning this test, list them here as potential triage targets
- **For Triaged Regressions**:
  - **JIRA Key(s)**: Links to existing bug(s)
  - **JIRA Status**: Current status (NEW, ASSIGNED, IN PROGRESS, etc.)
  - **Assignee**: Who is responsible for the fix
  - **Last Activity**: When the issue was last updated
  - **Recent Comments Summary**: Key points from recent comments
  - **Progress Classification**:
    - 🟢 **ACTIVE**: Assigned, recent activity, PR in progress - no action needed
    - 🟡 **STALLED**: Assigned but no activity in 14+ days - may need attention
    - 🔴 **NEEDS ATTENTION**: NEW/unassigned, no comments - needs someone to pick it up
  - **Recommendation**: Based on progress status (monitor, follow up, or take action)
- **For Untriaged Regressions**:
  - Note: "No bug filed yet"
  - Related JIRA tickets from similar regressions
  - Bug filing template with all relevant details

#### Bug Filing / Next Steps

- **For Untriaged Regressions**: Complete bug template ready to file. If open bugs were found via the test report, suggest triaging to one of those instead of filing a duplicate.
- **For Triaged Regressions with Active Progress**: Note existing bug and progress status
- **For Triaged Regressions Needing Attention**: Suggested actions (comment, reassign, escalate)
- **For Failed Fixes (analysis_status -1000)**: Recommendation to re-open or file new bug

#### Triage Offering

After the report, the command offers to triage based on findings:

- **Related triage found**: Offers to add this regression (and untriaged related regressions) to the existing triage record
- **Related JIRA bug found**: Offers to create a new triage linking this regression (and untriaged related regressions) to the bug
- **No bug found**: Offers to create a new JIRA bug (with test details report link) and triage all related regressions to it
- **Already triaged**: No triage action offered (JIRA progress shown instead)

Uses the `triage-regression` skill with authentication via the `oc-auth` skill (DPCR cluster).

## Arguments

- `$1` (required): Regression ID
  - Format: Integer ID of the regression to analyze
  - Example: 34446
  - The regression ID can be found in the Component Readiness UI regressed tests table by hovering over the regressed since column, click to copy.

## Prerequisites

1. **Python 3**: Required to run the regression data fetching scripts

   - Check: `which python3`
   - Version: 3.6 or later

2. **Network Access**: Must be able to reach Component Readiness API and Sippy

   - Component Readiness API
   - Check firewall and VPN settings if needed

3. **JIRA_TOKEN** (optional): Required for JIRA progress analysis on triaged regressions

   - Set environment variable: `export JIRA_TOKEN="your-jira-api-token"`
   - Obtain from: https://issues.redhat.com (Profile → Personal Access Tokens)
   - If not set, JIRA progress analysis will be skipped but other analysis continues

## Notes

- **Always performs full analysis** regardless of triage status
- **For triaged regressions**: Fetches JIRA issue details and analyzes whether the bug is being actively worked on or needs attention
- **JIRA Progress Classification**:
  - 🟢 **ACTIVE**: Status is ASSIGNED/IN PROGRESS with recent activity (comments, PR links within 7 days)
  - 🟡 **STALLED**: Status is ASSIGNED but no activity in 14+ days
  - 🔴 **NEEDS ATTENTION**: Status is NEW/OPEN with no assignee or no recent comments
- **Analysis Status Codes**:
  - `-1000`: Failed fix - test continues to fail after triage was resolved (requires different investigation approach)
  - Other negative values: Severity of regression (lower = more severe)
  - Negative values indicate problems detected by the regression analysis
- **Skills Used**:
  - `fetch-regression-details`: Fetches regression data and analyzes pass/fail patterns
  - `fetch-test-report`: Fetches global test health report with per-variant breakdown and open bug counts
  - `fetch-releases`: Determines the latest OCP release (used by fetch-test-report)
  - `fetch-test-runs`: Fetches actual test outputs and analyzes error message consistency
  - `fetch-prowjob-json`: Fetches prowjob.json to get payload tag and upgrade-from tag for a Prow job
  - `fetch-new-prs-in-payload`: Fetches new PRs in a payload compared to its predecessor
  - `list-regressions` (teams plugin): Lists all regressions for a release/component to find related regressions
  - `fetch-related-triages`: Finds existing triages and untriaged regressions related to a regression
  - `fetch-jira-issue`: Fetches JIRA issue details and classifies progress
  - `triage-regression`: Creates or updates triage records linking regressions to JIRA bugs
  - `set-release-blocker`: Sets the Release Blocker field to "Approved" on filed JIRA bugs
  - `oc-auth`: Provides authentication tokens for sippy-auth API
- The regression details skill groups failed jobs by job name and provides pass sequences for pattern analysis
- The test failure outputs skill compares error messages to determine if failures have a single root cause
- Follows the guidance: "many regressions can be caused by one bug"
- Helps teams consistently follow the documented triage procedure
- Pattern analysis (permafail/resolved/flaky/recent) helps prioritize investigation efforts
- For high-level component health analysis, use `/component-health:analyze-regressions` instead
- For listing all regressions, use `/component-health:list-regressions`
- For questions, ask in #forum-ocp-release-oversight

## See Also

- Related Skill: `fetch-regression-details` - Fetches regression data with pass sequences (`plugins/ci/skills/fetch-regression-details/SKILL.md`)
- Related Skill: `fetch-test-report` - Fetches global test health report with per-variant breakdown and open bugs (`plugins/ci/skills/fetch-test-report/SKILL.md`)
- Related Skill: `fetch-releases` - Determines the latest OCP release (`plugins/ci/skills/fetch-releases/SKILL.md`)
- Related Skill: `fetch-test-runs` - Fetches and analyzes test failure outputs (`plugins/ci/skills/fetch-test-runs/SKILL.md`)
- Related Skill: `fetch-prowjob-json` - Fetches prowjob.json for payload tag and metadata (`plugins/ci/skills/fetch-prowjob-json/SKILL.md`)
- Related Skill: `fetch-new-prs-in-payload` - Fetches new PRs in a payload (`plugins/ci/skills/fetch-new-prs-in-payload/SKILL.md`)
- Related Skill: `list-regressions` (teams plugin) - Lists all regressions for a release/component (`plugins/teams/skills/list-regressions/SKILL.md`)
- Related Skill: `fetch-related-triages` - Finds existing triages and untriaged regressions related to a regression (`plugins/ci/skills/fetch-related-triages/SKILL.md`)
- Related Skill: `fetch-jira-issue` - Fetches JIRA issue details and classifies progress (`plugins/ci/skills/fetch-jira-issue/SKILL.md`)
- Related Skill: `triage-regression` - Creates or updates triage records (`plugins/ci/skills/triage-regression/SKILL.md`)
- Related Skill: `set-release-blocker` - Sets Release Blocker field on JIRA bugs (`plugins/ci/skills/set-release-blocker/SKILL.md`)
- Related Skill: `oc-auth` - Authentication tokens for sippy-auth (`plugins/ci/skills/oc-auth/SKILL.md`)
- Related Command: `/component-health:list-regressions` (for bulk regression data)
- Related Command: `/component-health:analyze-regressions` (for overall component health)
- Component Readiness: https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/main
- TRT Documentation: https://docs.ci.openshift.org/docs/release-oversight/troubleshooting-failures/
