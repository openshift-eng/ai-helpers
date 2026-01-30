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

The command first checks if the regression has already been triaged (attributed to a JIRA bug). If triaged, the command reports the triage information and analysis status, then exits without further investigation. If not triaged, it performs a full analysis to help determine the root cause and suggest next steps.

This command is useful for:

- Checking if a regression has already been triaged and attributed to a bug
- Understanding regression patterns and failure modes for untriaged regressions
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

3. **Check Triage Status**: Determine if investigation is needed

   Before proceeding with full analysis, check if the regression has already been triaged:

   ```bash
   # Check if regression has triages
   triage_count=$(echo "$regression_data" | jq '.triages | length')
   ```

   **Decision Logic**:

   - **If `triage_count > 0` (regression is triaged)**:

     This means a human has already attributed this regression to a specific bug. Normally there is only one entry in the triages list, but in rare cases one test might be failing for multiple reasons.

     - Display triage information (JIRA keys, descriptions, resolved status)
     - Show analysis status and explanations
     - **If `analysis_status == -1000`**: Note that this is a failed fix scenario
       - This indicates the test is still failing in jobs AFTER the triage was resolved
       - Note: "⚠️ FAILED FIX: Test continues to fail after triage was resolved (analysis_status: -1000)"
       - Note: "Further investigation of failed fixes requires different analysis (future command/skill)"
     - **Else**: Note: "This regression has been triaged. No further investigation required."
     - Exit early - skip steps 4-8

   - **If `triage_count == 0` (regression is NOT triaged)**:
     - Proceed with full investigation (steps 4-8)
     - The regression needs analysis and bug filing

   **Example Check**:

   ```bash
   if [ "$triage_count" -gt 0 ]; then
     echo "Regression already triaged. No further investigation needed."
     # Display triages and analysis status
     echo "$regression_data" | jq '{triages, analysis_status, analysis_explanations}'

     # Check for failed fix
     analysis_status=$(echo "$regression_data" | jq -r '.analysis_status // "null"')
     if [ "$analysis_status" == "-1000" ]; then
       echo ""
       echo "⚠️ FAILED FIX: Test continues to fail after triage was resolved"
       echo "Further investigation of failed fixes requires different analysis (future command/skill)"
     fi

     exit 0
   else
     echo "Regression is not triaged. Proceeding with analysis..."
     # Continue to step 4
   fi
   ```

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

   - **Analyze Pass Sequence Patterns**: For each job, examine the `pass_sequence` string (newest to oldest):

     **Pattern 1: Permafailing Test**
     - `pass_sequence` shows all or most recent runs are "F" (e.g., `FFFFFFFFFF` or `FFFFFFFSS`)
     - Interpretation: The test may have begun to permafail in this job
     - Example: `FFFFFFFFFFFFFFFFFF` (18 consecutive failures) indicates a permafail
     - Action: High priority - test is completely broken for this job variant

     **Pattern 2: Resolved Issue**
     - `pass_sequence` shows failures in a solid block, but most recent runs have returned to "S" (e.g., `SSSSSFFFFF` or `SSSSSFFFFFSS`)
     - Interpretation: The problem may have resolved itself or been fixed
     - Example: `SSSSFFFFFFFFFFFF` shows recent successes after a block of failures
     - Action: Lower priority - verify if issue is truly resolved or if more monitoring is needed

     **Pattern 3: Flaky Test**
     - `pass_sequence` shows "F"s sporadically throughout, interspersed with "S" (e.g., `SFSFSFSFSF` or `FSSFFSSFF`)
     - Interpretation: Test appears flaky rather than consistently failing
     - Example: `SSFSSFSSFSSF` shows intermittent failures
     - Action: May require test stabilization or flake investigation rather than product bug

     **Pattern 4: Recent Regression**
     - `pass_sequence` shows recent "F"s after a long sequence of "S" (e.g., `FFSSSSSSSSS`)
     - Interpretation: Test recently started failing, likely due to a recent change
     - Example: `FFFFFPPPPPPPPPPPPP` shows 5 recent failures after many successes
     - Action: High priority - recent regression, investigate recent code changes

   - **Generate Pattern Summary**: Create a summary for each job:
     - Job name
     - Total failed runs
     - Pass sequence pattern classification (permafail / resolved / flaky / recent regression)
     - Recommended priority level
     - Suggested next steps

   **Note**: Only perform this step if the regression is not triaged (triage_count == 0).

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
     }
   }
   ```

   Pattern analysis output:
   - **Job 1** (18 failures): `FFFFFFFFFFFFFFFFFF`
     - Classification: **Permafail**
     - Priority: **High**
     - Action: "Test is completely broken for this metal+ovn+ipv4+rhcos10 variant. Investigate immediately."
   - **Job 2** (1 failure): `SSFSSSSSSSS`
     - Classification: **Flaky**
     - Priority: **Low**
     - Action: "Single recent failure in mostly passing job. Monitor for pattern or investigate if recurring."

5. **Identify Related Regressions**: Search for similar failing tests

   - List all regressions for the release
   - Identify other jobs where this test is failing
   - Check for common error messages or stack traces
   - Summarize the commonalities and differences in job variants
     - For example is this test failing for all jobs of one platform type or upgrade type

6. **Check Existing Triages**: Look for related triage records

   - Query regression data for triages with similar test names
   - Identify triages from same job runs
   - Present existing JIRA tickets that might already cover this regression
   - This implements: "scan for pre-existing triages that look related"

7. **Prepare Bug Filing Recommendations**: Generate actionable information

   - Component assignment (from test mappings)
   - Bug summary suggestion based on failure pattern (informed by step 3 pattern analysis)
   - Bug description template including:
     - Test name and release
     - Regression opened date
     - Affected variants
     - Failure patterns identified (permafail/flaky/resolved/recent)
     - Pass sequence analysis from step 3
     - Link to Test Details report
     - Related regressions (if any)
   - Triage type recommendation:
     - `product`: actual product issues (default)
     - `test`: clear issues in the test itself (especially for flaky patterns)
     - `ci-infra`: CI outages
     - `product-infra`: customer-facing outages (e.g., quay)

8. **Display Comprehensive Report**: Present findings in clear format

   **Note**: This step is only performed for untriaged regressions (no entries in triages list).

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

   **Section 3: Related Regressions**
   - List of potentially related failing tests
   - Common patterns across failures
   - Recommendation: "These regressions may be caused by the same issue and could be triaged to one JIRA"

   **Section 4: Existing Triages**
   - Related JIRA tickets already filed (from other regressions)

## Return Value

The command output varies based on triage status:

### For Already-Triaged Regressions

If the regression has already been triaged by a human, the command outputs a **Triage Status Report**:

- **Test Name**: Full test name
- **Component**: Component from regression data
- **Release**: OpenShift release version
- **Regression Status**: Open/Closed with dates
- **Analysis Status**: Integer status code with explanations
  - **-1000**: Failed fix - test continues to fail after triage was resolved
  - **Other negative values**: Severity of the regression (lower = more severe)
- **Existing Triages**: List of JIRA tickets this regression has been attributed to:
  - JIRA key (e.g., OCPBUGS-12345)
  - Triage type (product/test/ci-infra/product-infra)
  - Description
  - Resolved status
  - Created/Updated timestamps
- **Note**: "This regression has been triaged. No further investigation required."
- **If analysis_status == -1000**: Additional note: "⚠️ FAILED FIX: Test continues to fail after triage was resolved. Further investigation of failed fixes requires different analysis (future command/skill)"

### For Untriaged Regressions

For regressions that need investigation, the command outputs a **Comprehensive Regression Analysis Report**:

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
  - **Pattern Classification**:
    - **Permafail**: "FFFFFFFFFF..." - All or most recent runs failing. Indicates test is completely broken for this job.
    - **Resolved**: "SSSSSSFFFF..." - Recent successes after failures. Issue may have self-resolved.
    - **Flaky**: "SFSFSFSFSF..." - Sporadic failures. Test is unstable/flaky.
    - **Recent Regression**: "FFFFFSSSSSS..." - Recently started failing. Likely caused by recent code change.
  - **Priority Level**: High (permafail/recent regression), Medium (flaky with many failures), Low (resolved/occasional flakes)
  - **Recommended Action**: Next steps based on pattern (e.g., "Investigate recent code changes", "Stabilize flaky test", "Verify issue is resolved")
- **Overall Assessment**: Summary of regression severity across all jobs

#### Root Cause Analysis

- **Failure Patterns**: Common patterns identified across multiple job failures
- **Suspected Component**: Component/area likely responsible for the failure
- **Classification**: Whether the issue is infrastructure-related or a product bug

#### Related Regressions

- **Similar Failing Tests**: List of other regressions that appear similar
- **Common Patterns**: Shared error messages, stack traces, or failure modes
- **Variant Analysis**: Summary of which job variants are affected (e.g., all AWS jobs, all upgrade jobs)
- **Triaging Recommendation**: Whether these regressions should be grouped under a single JIRA ticket

#### Existing Triages

- **Related JIRA Tickets**: Previously filed tickets that may already cover this regression
- **Triage Details**: Test names, job runs, and components from existing triages
- **Recommendations**: Whether to use existing ticket or file new one

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

- **Automatically checks triage status** before performing full investigation:
  - If regression is triaged, reports triage info and analysis status, then exits
  - If regression is not triaged, performs full investigation
- **Analysis Status Codes**:
  - `-1000`: Failed fix - test continues to fail after triage was resolved (requires different investigation approach)
  - Other negative values: Severity of regression (lower = more severe)
  - Negative values indicate problems detected by the regression analysis
- Uses the `fetch-regression-details` skill to automatically fetch regression data and analyze pass/fail patterns
- The skill groups failed jobs by job name and provides pass sequences for pattern analysis
- Follows the guidance: "many regressions can be caused by one bug"
- Helps teams consistently follow the documented triage procedure
- Pattern analysis (permafail/resolved/flaky/recent) helps prioritize investigation efforts
- For high-level component health analysis, use `/component-health:analyze-regressions` instead
- For listing all regressions, use `/component-health:list-regressions`
- For questions, ask in #forum-ocp-release-oversight

## See Also

- Related Skill: `fetch-regression-details` - Fetches regression data with pass sequences (`plugins/ci/skills/fetch-regression-details/SKILL.md`)
- Related Command: `/component-health:list-regressions` (for bulk regression data)
- Related Command: `/component-health:analyze-regressions` (for overall component health)
- Component Readiness: https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/main
- TRT Documentation: https://docs.ci.openshift.org/docs/release-oversight/troubleshooting-failures/
