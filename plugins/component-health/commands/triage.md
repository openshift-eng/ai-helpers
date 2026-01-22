---
description: Analyze root cause of a specific regressed test case from Component Readiness
argument-hint: <test-name> <release> [--variant <variant>]
---

## Name

component-health:triage

## Synopsis

```
/component-health:triage <test-name> <release> [--variant <variant>]
```

## Description

The `component-health:triage` command automates the root cause analysis workflow for a specific regressed test case as documented in the Component Readiness User Guide. This command helps teams quickly diagnose test failures and prepare for bug filing and triaging.

This command implements the following workflow from the Component Readiness User Guide:
1. Fetches detailed regression data for the specific test
2. Retrieves test failure logs and job information
3. Analyzes failure patterns using Sippy AI
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

1. **Parse Arguments**: Extract test name, release version, and optional variant

   - Test name format: Full test name as shown in Component Readiness (e.g., "[sig-network] Feature:SCTP...")
   - Release format: "X.Y" (e.g., "4.21", "4.22")
   - Optional variant filter: specific platform/topology variant

2. **Fetch Regression Details**: Get regression data from Component Readiness API

   - Use the list_regressions.py script to fetch regression data
   - Filter for the specific test name provided
   - Extract regression metadata:
     - Component assignment
     - Variants where test is failing
     - Regression opened/closed dates
     - Existing triages (if any)
     - Test owner information

3. **Get Test Details URL**: Construct Test Details report URL

   - Format: `https://sippy-auth.dptools.openshift.org/sippy-ng/tests/<release>/analysis?test=<encoded-test-name>`
   - Display URL to user for direct access to Test Details page
   - This corresponds to clicking the red icon in the Regressed Tests modal

4. **Analyze Test Failures Using Sippy AI**: Query Sippy for root cause analysis

   - **IMPORTANT**: Invoke the `ci:oc-auth` skill BEFORE using ask-sippy
   - Construct targeted query for Sippy AI:
     - "Analyze the root cause of test failure: `<test-name>` in release `<release>`. What are the common failure patterns? What component is likely responsible?"
   - Use `/ci:ask-sippy` command to get AI analysis
   - Parse response for:
     - Failure patterns
     - Suspected component
     - Similar failures in other tests
     - Infrastructure vs product issues
     - Recent changes that might have caused the regression

5. **Identify Related Regressions**: Search for similar failing tests

   - Extract test suite/signature from test name (e.g., "[sig-network]")
   - Query regression data for other tests in same area
   - Look for tests failing in same job runs
   - Check for common error messages or stack traces
   - This implements the documented guidance: "many regressions can be caused by one bug"

6. **Prepare Bug Filing Recommendations**: Generate actionable information

   - Component assignment (from test mappings or AI analysis)
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

7. **Check Existing Triages**: Look for related triage records

   - Query regression data for triages with similar test names
   - Identify triages from same job runs
   - Present existing JIRA tickets that might already cover this regression
   - This implements: "scan for pre-existing triages that look related"

8. **Display Comprehensive Report**: Present findings in clear format

   **Section 1: Regression Summary**
   - Test name
   - Component
   - Regression opened/closed dates
   - Affected variants
   - Current triage status

   **Section 2: Root Cause Analysis**
   - Sippy AI analysis results
   - Failure patterns identified
   - Suspected component/area
   - Infrastructure vs product classification

   **Section 3: Related Regressions**
   - List of potentially related failing tests
   - Common patterns across failures
   - Recommendation: "These regressions may be caused by the same issue and could be triaged to one JIRA"

   **Section 4: Bug Filing Guidance**
   - Recommended component
   - Bug summary template
   - Bug description template
   - Triage type recommendation
   - Link to Test Details report
   - Link to file bug (if available from API)

   **Section 5: Existing Triages**
   - Related JIRA tickets already filed
   - Option to add this regression to existing triage
   - Warning if triaging separately: "Do not triage every regression to a separate jira"

9. **Offer Next Steps**: Guide user through workflow

   - Provide clear next actions:
     - Review Test Details report (link provided)
     - File new JIRA or add to existing triage
     - Use authenticated Sippy for triage: https://sippy-auth.dptools.openshift.org/sippy-ng/
   - Remind about team responsibilities from User Guide
   - Point to #forum-ocp-release-oversight for questions

10. **Error Handling**: Handle common error scenarios

    - Test name not found in regression data
    - No regression data available for release
    - Sippy AI query failures
    - API connectivity issues
    - Invalid release format

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

From Sippy AI analysis:
- **Failure Patterns**: Common error messages or failure modes
- **Suspected Component**: Component likely responsible
- **Issue Classification**: Infrastructure / Product / Test / Product-Infra
- **Recent Changes**: Potential commits or changes that introduced regression
- **Confidence Level**: AI confidence in analysis

### Related Regressions

Potentially related failing tests:
```
1. [sig-network] Feature:SCTP test case 2
   - Same failure pattern: "connection refused"
   - Failing since: 2025-01-15
   - Status: Untriaged

2. [sig-network] Basic networking test
   - Same job run failures
   - Failing since: 2025-01-14
   - Status: Triaged to OCPBUGS-12345
```

**Recommendation**: These regressions appear to be caused by the same underlying issue and could be triaged to a single JIRA.

### Bug Filing Guidance

**Recommended Component**: `Networking / ovn-kubernetes`

**Suggested Bug Summary**:
```
[sig-network] Feature:SCTP test failing in 4.22: connection refused
```

**Bug Description Template**:
```
Test: [sig-network] Feature:SCTP should create a Pod with SCTP HostPort
Release: 4.22
Regression Opened: 2025-01-15

The test is failing with "connection refused" errors across multiple variants:
- aws
- gcp
- metal

Test Details: https://sippy-auth.dptools.openshift.org/sippy-ng/tests/4.22/analysis?test=...

Root Cause Analysis:
[Sippy AI findings]

Related Regressions:
- Test X (OCPBUGS-12345)
- Test Y (untriaged)
```

**Recommended Triage Type**: `product`

**File Bug Link**: [If available from API]

### Existing Triages

Related JIRA tickets that may already cover this regression:

- **OCPBUGS-12345**: SCTP networking failures in 4.22
  - Filed: 2025-01-14
  - Status: NEW
  - Triaged regressions: 3
  - **Recommendation**: Consider adding this regression to this existing triage instead of filing a new bug

### Next Steps

1. **Review Test Details**: [Link to Test Details report]
2. **Choose Action**:
   - Add to existing JIRA OCPBUGS-12345 (recommended if same root cause)
   - File new JIRA using templates above
3. **Triage in Authenticated Sippy**: https://sippy-auth.dptools.openshift.org/sippy-ng/
4. **Coordinate**: Ask in #forum-ocp-release-oversight if unsure

**Remember**: Multiple regressions caused by the same bug should be triaged to one JIRA to avoid overwhelming bug counts.

## Examples

1. **Analyze a specific regressed test**:

   ```
   /component-health:triage "[sig-network] Feature:SCTP should create a Pod with SCTP HostPort" 4.22
   ```

   Analyzes the SCTP test regression in 4.22, provides root cause analysis, identifies related regressions, and gives bug filing guidance.

2. **Analyze with variant filter**:

   ```
   /component-health:triage "[sig-storage] CSI volumes should mount" 4.21 --variant aws
   ```

   Focuses analysis on AWS variant failures specifically.

3. **Analyze authentication test**:

   ```
   /component-health:triage "[sig-auth] ServiceAccounts should support OIDC discovery" 4.22
   ```

   Analyzes authentication regression, suggests correct component assignment, identifies if related to recent auth changes.

## Arguments

- `$1` (required): Test name
  - Format: Full test name as shown in Component Readiness
  - Must be enclosed in quotes if it contains spaces
  - Example: "[sig-network] Feature:SCTP should create a Pod with SCTP HostPort"
  - Example: "[sig-api-machinery] AdmissionWebhook should honor timeout"

- `$2` (required): Release version
  - Format: "X.Y" (e.g., "4.21", "4.22")
  - Must be a valid OpenShift release number
  - Should match the release shown in Component Readiness

- `$3+` (optional): Filter flags
  - `--variant <variant>`: Filter analysis to specific platform/topology
    - Examples: `aws`, `gcp`, `azure`, `metal`, `single-node`
    - Useful when test fails on specific platform only

## Prerequisites

1. **Python 3**: Required to run the regression data fetching scripts

   - Check: `which python3`
   - Version: 3.6 or later

2. **Network Access**: Must be able to reach Component Readiness API and Sippy

   - Component Readiness API
   - Sippy AI API (requires authentication)
   - Check firewall and VPN settings if needed

3. **Sippy Authentication**: Required for ask-sippy functionality

   - The `ci:oc-auth` skill must be available
   - DPCR cluster token for authenticated API access
   - See `/ci:ask-sippy` command for authentication setup

## Notes

- This command implements the workflow from the Component Readiness User Guide
- Follows the guidance: "many regressions can be caused by one bug"
- Integrates with existing `/ci:ask-sippy` for AI-powered root cause analysis
- Helps teams consistently follow the documented triage procedure
- Provides direct links to Sippy UI for manual verification
- Use authenticated Sippy (sippy-auth) for triage operations
- For high-level component health analysis, use `/component-health:analyze` instead
- For listing all regressions, use `/component-health:list-regressions`
- For questions, ask in #forum-ocp-release-oversight

## See Also

- Related Command: `/component-health:list-regressions` (for bulk regression data)
- Related Command: `/component-health:analyze` (for overall component health)
- Related Command: `/ci:ask-sippy` (for AI-powered Sippy queries)
- Component Readiness: https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/main
- TRT Documentation: https://docs.ci.openshift.org/docs/release-oversight/troubleshooting-failures/
