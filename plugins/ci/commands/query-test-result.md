---
description: Query test results from Sippy by version and test keywords
argument-hint: <version> <keywords> [sippy-url]
---

## Name
ci:query-test-result

## Synopsis
```
/ci:query-test-result <version> <keywords> [sippy-url]
```

## Description
The `ci:query-test-result` command queries OpenShift CI test results from Sippy based on the OpenShift version and test name keywords. It retrieves test statistics including pass rate, number of runs, failures, and links to failed job runs.

By default, it queries the production Sippy instance at `sippy.dptools.openshift.org`. You can optionally specify a different Sippy instance URL to query alternative environments (e.g., QE component readiness).

This command is useful for:
- Checking the health of specific test cases
- Finding test failure patterns
- Getting links to failed Prow job runs for debugging
- Monitoring test regression trends
- Querying different Sippy instances (production, QE, etc.)

## Arguments
- `$1` (version): OpenShift version to query (e.g., "4.21", "4.20", "4.19")
- `$2` (keywords): Keywords to search in test names (e.g., "PolarionID:81664", "olmv1", "sig-storage")
- `$3` (sippy-url) [optional]: Sippy instance base URL. Defaults to "sippy.dptools.openshift.org" if not provided. Examples: "qe-component-readiness.dptools.openshift.org"

## Implementation

1. **Parse Arguments**
   - Extract version from `$1` (e.g., "4.21")
   - Extract keywords from `$2` (e.g., "81664" or "olmv1")
   - Extract Sippy URL from `$3` if provided, otherwise use default "sippy.dptools.openshift.org"
   - Normalize URL to extract base domain for API endpoint (strip "/sippy-ng/" suffix if present)
   - Add "https://" prefix if not already present

2. **Build Sippy API Request**
   - Construct filter JSON for the `/api/tests` endpoint:
     ```python
     filters = {
         "items": [
             {
                 "columnField": "name",
                 "not": False,
                 "operatorValue": "contains",
                 "value": keywords
             }
         ],
         "linkOperator": "and"
     }
     ```
   - Set query parameters:
     - `release`: The OpenShift version
     - `filter`: JSON-encoded filter object
     - `sort`: "asc"
     - `sortField`: "net_improvement"

3. **Query Test Statistics**
   - Construct API endpoint from provided URL: `https://{base_url}/api/tests`
     - Example: If input is "sippy.dptools.openshift.org", use `https://sippy.dptools.openshift.org/api/tests`
     - Example: If input is "qe-component-readiness.dptools.openshift.org", use `https://qe-component-readiness.dptools.openshift.org/api/tests`
   - Make GET request to the constructed endpoint
   - Parse response to extract:
     - Test name
     - Current pass percentage
     - Total runs, passes, failures
     - Net improvement (trend indicator)

4. **Query Failed Job Runs** (for each matching test)
   - Calculate timestamp for 7 days ago: `start_time = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)`
   - Build filter for failed runs:
     ```python
     filters = {
         "items": [
             {
                 "columnField": "failed_test_names",
                 "operatorValue": "contains",
                 "value": test_name
             },
             {
                 "columnField": "timestamp",
                 "operatorValue": ">",
                 "value": str(start_time)
             }
         ],
         "linkOperator": "and"
     }
     ```
   - Make GET request to `https://{base_url}/api/jobs/runs` with parameters:
     - `release`: version
     - `filter`: JSON-encoded filter
     - `limit`: "20"
     - `sortField`: "timestamp"
     - `sort`: "desc"
   - **Parse Response Structure**:
     - Response is a dict with structure: `{"rows": [...], "page": N, "page_size": N, "total_rows": N}`
     - Extract job runs from `response["rows"]`
     - Each run contains:
       - `timestamp`: Unix timestamp in milliseconds
       - `brief_name` or `job`: Job name
       - `test_grid_url`: Link to Prow job details

5. **Format and Display Results**
   - Show summary statistics for each matching test
   - List failed job runs with:
     - Timestamp of the failure
     - Job name
     - Clickable Prow URL for each failed run
   - **After listing individual runs, provide a summary section:**
     - Create a "Failed Prow URLs (for easy copying)" section
     - List all Prow URLs from the failed runs in plain text format (one per line)
     - This allows users to easily copy all URLs at once for further analysis
   - Format output in a clear, readable structure with proper spacing
   - Present URLs as markdown links for easy clicking

## Return Value

**Format**: Formatted text output with:
- Test name(s) matching the keywords
- Statistics section showing:
  - Pass Rate (percentage)
  - Total Runs
  - Passes
  - Failures
  - Net Improvement
- Failed Job Runs section listing (for last 7 days):
  - Sequential numbering (1, 2, 3...)
  - Timestamp (formatted as YYYY-MM-DD HH:MM:SS)
  - Job name (brief name)
  - Clickable Prow URL (as markdown link or plain URL)
- Failed Prow URLs summary section:
  - Plain text list of all Prow URLs (one per line)
  - Allows easy copying of all URLs for batch analysis

**Output Format Example:**
```
Failed Job Runs (Last 7 Days):
1. 2025-11-03 12:12:31 - periodic-ci-openshift-operator-framework-...
   https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...

2. 2025-11-02 12:12:29 - periodic-ci-openshift-operator-framework-...
   https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...
```

If no tests match the keywords, inform the user that no results were found.
If a test has no failed runs in the last 7 days, display a success message.

## Examples

1. **Query by Polarion ID (using default Sippy instance)**:
   ```
   /ci:query-test-result 4.21 81664
   ```

   Returns test results for tests containing "81664" in version 4.21 from the default production Sippy instance (sippy.dptools.openshift.org).

2. **Query by test signature (using default Sippy instance)**:
   ```
   /ci:query-test-result 4.20 olmv1
   ```

   Returns all OLMv1-related test results for version 4.20 from the default Sippy instance.

3. **Query from QE Sippy instance (custom URL)**:
   ```
   /ci:query-test-result 4.20 olmv1 qe-component-readiness.dptools.openshift.org
   ```

   Returns all OLMv1-related test results for version 4.20 from the QE component readiness Sippy instance.

4. **Query by component with custom Sippy URL**:
   ```
   /ci:query-test-result 4.19 sig-storage sippy.dptools.openshift.org
   ```

   Returns all storage-related test results for version 4.19 from the specified Sippy instance.

5. **Custom URL variations (all valid formats)**:
   ```
   /ci:query-test-result 4.21 olmv1 sippy.dptools.openshift.org
   /ci:query-test-result 4.21 olmv1 https://sippy.dptools.openshift.org
   ```

   Both URL formats are accepted and will query the same Sippy instance.

## Output Example

```
====================================================================================================
Test Results for PolarionID: 81664 (Version 4.21)
====================================================================================================

Test Name:
[sig-olmv1][Jira:OLM] clusterextension PolarionID:81664-[Skipped:Disconnected]preflight check

Statistics (Last 7 Days):
  • Pass Rate: 0.00%
  • Total Runs: 6
  • Passes: 0
  • Failures: 6
  • Net Improvement: -100.00

Failed Job Runs (Last 7 Days):
----------------------------------------------------------------------------------------------------

1. 2025-11-03 12:12:31
   Job: periodic-ci-openshift-operator-framework-operator-controller-release-4.21-periodics-e2e-aws-ovn-techpreview-extended-f1
   https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-operator-framework-operator-controller-release-4.21-periodics-e2e-aws-ovn-techpreview-extended-f1/1985198377557561344

2. 2025-11-02 12:12:29
   Job: periodic-ci-openshift-operator-framework-operator-controller-release-4.21-periodics-e2e-aws-ovn-techpreview-extended-f1
   https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-operator-framework-operator-controller-release-4.21-periodics-e2e-aws-ovn-techpreview-extended-f1/1984835985292136448

[... additional failures ...]

----------------------------------------------------------------------------------------------------
Failed Prow URLs (for easy copying):
----------------------------------------------------------------------------------------------------
https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-operator-framework-operator-controller-release-4.21-periodics-e2e-aws-ovn-techpreview-extended-f1/1985198377557561344
https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-operator-framework-operator-controller-release-4.21-periodics-e2e-aws-ovn-techpreview-extended-f1/1984835985292136448
[... additional URLs ...]

====================================================================================================
```

## Notes

- **Default Sippy URL**: If no Sippy URL is provided, the command uses `sippy.dptools.openshift.org` by default
- The command queries data from the last 7 days by default
- Ensure you can access the Sippy API endpoints
- Results are sorted by net improvement to show regressed tests first
- Failed job runs are limited to the most recent 20 occurrences
- **URLs are displayed as clickable links** for easy access to Prow job details
- If multiple tests match the keywords, results for all matches will be displayed
- URL normalization:
  - The command automatically strips common suffixes like "/sippy-ng/" from the URL
  - It adds "https://" prefix if not provided
  - Both domain-only and full path formats are supported

## See Also

- Sippy UI (Production): https://sippy.dptools.openshift.org/sippy-ng/
- Sippy UI (QE): https://qe-component-readiness.dptools.openshift.org
- Sippy API Documentation: https://github.com/openshift/sippy
