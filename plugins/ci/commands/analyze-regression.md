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

1. **Parse Arguments**: Extract regression ID

   - Regression ID format: Integer ID from Component Readiness
   - Example: 34446

2. **Fetch Regression Details**: Use the `fetch-regression-details` skill

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
   - `test_details_url`: Link to Sippy test details
   - `sample_failed_jobs`: Dictionary keyed by job name, each containing:
     - `pass_sequence`: Chronological S/F pattern (newest to oldest)
     - `failed_runs`: List of failed runs with job_url, job_run_id, start_time

   See `plugins/ci/skills/fetch-regression-details/SKILL.md` for complete implementation details.

3. **Check Triage Status and Fetch JIRA Progress**: Determine triage state and analyze bug progress

   Check if the regression has already been triaged and fetch JIRA details:

   ```bash
   # Check if regression has triages
   triage_count=$(echo "$regression_data" | jq '.triages | length')
   ```

   **If `triage_count > 0` (regression is triaged)**:

   This means a human has already attributed this regression to a specific bug. For each triage entry, fetch the JIRA issue to analyze progress.

   ```bash
   # For each triage, fetch JIRA details
   for jira_key in $(echo "$regression_data" | jq -r '.triages[].jira_key'); do
     # Use gh or curl to fetch JIRA issue details
     # Note: Requires JIRA API access - use the jira CLI or API
     jira_data=$(curl -s -H "Authorization: Bearer $JIRA_TOKEN" \
       "https://issues.redhat.com/rest/api/2/issue/$jira_key?fields=status,assignee,updated,comment")
   done
   ```

   **Analyze JIRA Progress**:

   For each linked JIRA issue, determine the work status:

   - **Active Progress** indicators:
     - Status is `ASSIGNED`, `IN PROGRESS`, `Code Review`, or similar active states
     - Recent comments (within last 7 days) showing investigation or fix progress
     - Assignee is set and has been active on the issue
     - PR links in comments indicating fix is in progress

   - **Needs Attention** indicators:
     - Status is `NEW`, `OPEN`, or `Untriaged`
     - No assignee set
     - No comments or last comment is older than 14 days
     - No recent activity on the issue

   - **Stalled** indicators:
     - Status is `ASSIGNED` but no activity in 14+ days
     - Comments indicate blocker or waiting on something
     - Issue has been open for extended period with no progress

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
   - Continue with full investigation (steps 4-9)
   - Bug filing recommendations will be provided in step 8

   **Always continue to step 4** regardless of triage status to provide full analysis.

4. **Interpret Regression Data**: Analyze failure patterns from `sample_failed_jobs`

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

5. **Analyze Failure Output Consistency**: Use the `fetch-test-failure-outputs` skill

   Use the `fetch-test-failure-outputs` skill to fetch and analyze actual test failure outputs from all failed job runs. This helps determine if all failures have the same root cause or if there are multiple issues.

   **Implementation**:

   ```bash
   # Extract test_id from regression data
   test_id=$(echo "$regression_data" | jq -r '.test_id')

   # Collect all job_run_ids from sample_failed_jobs
   # This creates a comma-separated list of all failed job run IDs across all jobs
   job_run_ids=$(echo "$regression_data" | jq -r '
     .sample_failed_jobs
     | to_entries[]
     | .value.failed_runs[]
     | .job_run_id
   ' | tr '\n' ',' | sed 's/,$//')

   # Use the fetch-test-failure-outputs skill
   script_path="plugins/ci/skills/fetch-test-failure-outputs/fetch_test_failure_outputs.py"
   output_analysis=$(python3 "$script_path" "$test_id" "$job_run_ids" --format json)
   ```

   The skill fetches raw test failure outputs from Sippy API.

   See `plugins/ci/skills/fetch-test-failure-outputs/SKILL.md` for complete implementation details.

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

6. **Identify Related Regressions**: Search for similar failing tests

   - List all regressions for the release
   - Identify other variant combinations where this test is failing
   - Summarize the commonalities and differences in job variants
     - For example is this test failing for all jobs of one Platform or Upgrade variant

7. **Check Existing Triages**: Look for related triage records

   - Query regression data for triages with similar test names
   - Identify triages from same job runs
   - Present existing JIRA tickets that might already cover this regression
   - This implements: "scan for pre-existing triages that look related"

8. **Prepare Bug Filing Recommendations or Existing Bug Status**: Generate actionable information

   **If regression is NOT triaged** (no existing JIRA):
   - Component assignment (from test mappings)
   - Bug summary suggestion based on failure pattern (informed by step 4 pattern analysis)
   - Bug description template including:
     - Test name and release
     - Regression opened date
     - Affected variants
     - Failure patterns identified (permafail/flaky/resolved/recent)
     - Pass sequence analysis from step 4
     - **Failure output consistency analysis from step 5** (if available):
       - Common error message
       - Consistency percentage
       - Key debugging information (file references, resources, stack traces)
     - Link to Test Details report
     - Related regressions (if any)
   - Triage type recommendation:
     - `product`: actual product issues (default)
     - `test`: clear issues in the test itself (especially for flaky patterns)
     - `ci-infra`: CI outages
     - `product-infra`: customer-facing outages (e.g., quay)

   **If regression IS triaged** (existing JIRA):
   - Note: "A bug already exists for this regression - do not file a duplicate"
   - Display JIRA key(s) with links
   - Show JIRA progress analysis from step 3:
     - 🟢 **ACTIVE**: Bug is being worked on, no action needed
     - 🟡 **STALLED**: Bug may need attention, consider commenting or reassigning
     - 🔴 **NEEDS ATTENTION**: Bug appears abandoned, consider taking ownership or escalating
   - **If analysis_status == -1000** (failed fix):
     - Recommend: Re-open the existing bug OR file a new bug if the failure mode is different
     - Provide new bug template if failure analysis suggests a different root cause

9. **Display Comprehensive Report**: Present findings in clear format

   **Section 1: Regression Summary**
   - Test name
   - Component
   - Regression opened/closed dates
   - Affected variants
   - Analysis status and explanations
   - Current triage status (none for untriaged regressions)

   **Section 2: Failure Pattern Analysis**
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

   **Section 3: Failure Output Analysis** (from `fetch-test-failure-outputs` skill)
   - Number of test outputs analyzed
   - Consistency classification (Highly Consistent / Moderately Consistent / Inconsistent)
   - Most common error message with occurrence count
   - Key debugging information:
     - File/line references
     - Resource or API paths
     - Error messages
   - Sample job URLs for manual inspection
   - **Note**: If the test outputs API is not available, this section will note: "Test output analysis not available"

   **Section 4: Related Regressions**
   - List of potentially related failing tests
   - Common patterns across failures
   - Recommendation: "These regressions may be caused by the same issue and could be triaged to one JIRA"

   **Section 5: Existing Triages**
   - Related JIRA tickets already filed (from other regressions)

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
- **Test Details URL**: Direct link to Sippy Test Details report

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

#### Failure Output Analysis

Generated using the `fetch-test-failure-outputs` skill (see `plugins/ci/skills/fetch-test-failure-outputs/SKILL.md`):

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

#### Root Cause Analysis

- **Failure Patterns**: Common patterns identified across multiple job failures
- **Suspected Component**: Component/area likely responsible for the failure
- **Classification**: Whether the issue is infrastructure-related or a product bug

#### Related Regressions

- **Similar Failing Tests**: List of other regressions that appear similar
- **Common Patterns**: Shared error messages, stack traces, or failure modes
- **Variant Analysis**: Summary of which job variants are affected (e.g., all AWS jobs, all upgrade jobs)
- **Triaging Recommendation**: Whether these regressions should be grouped under a single JIRA ticket

#### Existing Triages and JIRA Progress

- **Triage Status**: Whether this regression has been triaged to a JIRA bug
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

- **For Untriaged Regressions**: Complete bug template ready to file
- **For Triaged Regressions with Active Progress**: "Bug exists and is being worked - no action needed"
- **For Triaged Regressions Needing Attention**: Suggested actions (comment, reassign, escalate)
- **For Failed Fixes (analysis_status -1000)**: Recommendation to re-open or file new bug

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
  - `fetch-test-failure-outputs`: Fetches actual test outputs and analyzes error message consistency
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
- Related Skill: `fetch-test-failure-outputs` - Fetches and analyzes test failure outputs (`plugins/ci/skills/fetch-test-failure-outputs/SKILL.md`)
- Related Command: `/component-health:list-regressions` (for bulk regression data)
- Related Command: `/component-health:analyze-regressions` (for overall component health)
- Component Readiness: https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/main
- TRT Documentation: https://docs.ci.openshift.org/docs/release-oversight/troubleshooting-failures/
