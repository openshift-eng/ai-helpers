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

This command implements the following workflow:
1. Fetches detailed regression data 
2. Retrieves test failure logs and job information
3. Analyzes failure patterns using `/prow-job:analyze-test-failure`
4. Identifies potential root causes
5. Checks for related regressions
6. Provides actionable recommendations for bug filing and triaging

This command is useful for:

- **Quickly diagnosing individual test failures** from Component Readiness regressed tests modal
- **Understanding root causes** before filing bugs
- **Identifying related regressions** that might be caused by the same issue
- **Getting pre-filled bug information** for efficient JIRA filing
- **Following the documented triage procedure** consistently

## Implementation

1. **Parse Arguments**: Extract regression ID

   - Regression ID format: Integer ID from Component Readiness
   - Example: 34446

2. **Fetch Regression Details**: Use the `fetch-regression-details` skill

   - See `plugins/ci/skills/fetch-regression-details/SKILL.md` for implementation
   - The skill fetches regression data from: https://sippy.dptools.openshift.org/api/component_readiness/regressions/<regression_id>
   - Extract regression metadata:
     - Test Name
     - Release version
     - Variants where test is failing
     - Regression opened/closed dates
     - Existing triages (if any)
     - Test details URL

3. **Get Failed Jobs from the Test Details Sample Table**: Construct Test Details report URL

   - Curl the test details URL
   - Build a list of the failed sample jobs
   - Use `prow-job:analyze-test-failure` to analyze the root cause of the failure, for each failed sample
   - Compare the failed jobs for a pattern or common failure reason

4. **Identify Related Regressions**: Search for similar failing tests

   - List all regressions for the release
   - Identify other jobs where this test is failing
   - Check for common error messages or stack traces
   - Summarize the commonalities and differences in job variants
     - For example is this test failing for all jobs of one platform type or upgrade type

5. **Check Existing Triages**: Look for related triage records

   - Query regression data for triages with similar test names
   - Identify triages from same job runs
   - Present existing JIRA tickets that might already cover this regression
   - This implements: "scan for pre-existing triages that look related"

6. **Prepare Bug Filing Recommendations**: Generate actionable information

   - Component assignment (from test mappings)
   - Bug summary suggestion based on failure pattern
   - Bug description template including:
     - Test name and release
     - Regression opened date
     - Affected variants
     - Failure patterns identified
     - Link to Test Details report
     - Related regressions (if any)
   - Triage type recommendation:
     - `product`: actual product issues (default)
     - `test`: clear issues in the test itself
     - `ci-infra`: CI outages
     - `product-infra`: customer-facing outages (e.g., quay)

7. **Display Comprehensive Report**: Present findings in clear format

   **Section 1: Regression Summary**
   - Test name
   - Component
   - Regression opened/closed dates
   - Affected variants
   - Current triage status

   **Section 2: Root Cause Analysis**
   - Results from `/prow-job:analyze-test-failure`
   - Failure patterns identified
   - Suspected component/area
   - Infrastructure vs product classification

   **Section 3: Related Regressions**
   - List of potentially related failing tests
   - Common patterns across failures
   - Recommendation: "These regressions may be caused by the same issue and could be triaged to one JIRA"

   **Section 4: Existing Triages**
   - Related JIRA tickets already filed

## Return Value

The command outputs a **Comprehensive Regression Analysis Report**:

### Regression Summary

- **Test Name**: Full test name
- **Component**: Auto-detected component from test mappings
- **Release**: OpenShift release version
- **Regression Status**: Open/Closed with dates
- **Affected Variants**: List of platform/topology variants where test is failing
- **Current Triage**: Existing JIRA tickets (if any)
- **Test Details URL**: Direct link to Sippy Test Details report

### Root Cause Analysis

- **Analysis Results**: Output from `/prow-job:analyze-test-failure` for each failed sample
- **Failure Patterns**: Common patterns identified across multiple job failures
- **Suspected Component**: Component/area likely responsible for the failure
- **Classification**: Whether the issue is infrastructure-related or a product bug

### Related Regressions

- **Similar Failing Tests**: List of other regressions that may share the same root cause
- **Common Patterns**: Shared error messages, stack traces, or failure modes
- **Variant Analysis**: Summary of which job variants are affected (e.g., all AWS jobs, all upgrade jobs)
- **Triaging Recommendation**: Whether these regressions should be grouped under a single JIRA ticket

### Existing Triages

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

- Follows the guidance: "many regressions can be caused by one bug"
- Integrates with existing `/prow-job:analyze-test-failure` for root cause analysis
- Helps teams consistently follow the documented triage procedure
- For high-level component health analysis, use `/component-health:analyze-regressions` instead
- For listing all regressions, use `/component-health:list-regressions`
- For questions, ask in #forum-ocp-release-oversight

## See Also

- Related Command: `/component-health:list-regressions` (for bulk regression data)
- Related Command: `/component-health:analyze-regressions` (for overall component health)
- Related Command: `/prow-job:analyze-test-failure` (for test root cause analysis)
- Component Readiness: https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/main
- TRT Documentation: https://docs.ci.openshift.org/docs/release-oversight/troubleshooting-failures/
