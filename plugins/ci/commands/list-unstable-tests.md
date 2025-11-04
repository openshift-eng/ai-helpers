---
description: List unstable tests with pass rate below 95%
argument-hint: <version> <keywords> [sippy-url]
---

## Name
ci:list-unstable-tests

## Synopsis
```
/ci:list-unstable-tests <version> <keywords> [sippy-url]
```

## Description
The `ci:list-unstable-tests` command queries OpenShift CI test results from Sippy and lists all tests matching the keywords that have a pass rate below 95%. This is useful for quickly identifying unstable tests that need attention.

By default, it queries the production Sippy instance at `sippy.dptools.openshift.org`. You can optionally specify a different Sippy instance URL to query alternative environments (e.g., QE component readiness).

This command is useful for:
- Identifying unstable tests with inconsistent pass rates
- Finding regression candidates for investigation
- Generating reports of unstable test cases
- Prioritizing test stabilization efforts
- Quality gate checks before releases

## Arguments
- `$1` (version): OpenShift version to query (e.g., "4.21", "4.20", "4.19")
- `$2` (keywords): Keywords to search in test names (e.g., "olmv1", "sig-storage", "operator")
- `$3` (sippy-url) [optional]: Sippy instance base URL. Defaults to "sippy.dptools.openshift.org" if not provided. Examples: "qe-component-readiness.dptools.openshift.org"

## Implementation

1. **Parse Arguments**
   - Extract version from `$1` (e.g., "4.20")
   - Extract keywords from `$2` (e.g., "olmv1")
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
     - `sortField`: "current_pass_percentage"

3. **Query Test Statistics**
   - Construct API endpoint from provided URL: `https://{base_url}/api/tests`
   - Make GET request to the constructed endpoint
   - Parse response to extract test data

4. **Filter Tests Below 95% Pass Rate**
   - Iterate through all returned tests
   - Filter tests where `current_pass_percentage < 95`
   - Sort filtered results by pass percentage (ascending, worst first)
   - Collect the following data for each unstable test:
     - Test name
     - Current pass percentage
     - Total runs
     - Passes
     - Failures
     - Net improvement (trend indicator)

5. **Format and Display Results**
   - Display summary header with:
     - Total number of tests matching keywords
     - Number of tests below 95% pass rate
     - Percentage of unstable tests
   - List each unstable test with:
     - Test name
     - Pass rate percentage
     - Run statistics (runs/passes/failures)
     - Trend indicator (net improvement)
   - Sort by pass percentage (worst tests first)
   - If no tests are below 95%, display success message indicating all tests are stable

## Return Value

**Format**: Formatted text output with:

**Summary Section:**
- Total tests matching keywords
- Tests below 95% pass rate (unstable tests)
- Overall stability percentage

**Unstable Tests List:**
For each test with pass rate < 95%:
- Test name
- Pass rate percentage
- Total runs
- Passes
- Failures
- Net improvement

If all tests pass at 95% or above, display a success message indicating all tests are stable.

## Examples

1. **List unstable OLMv1 tests from QE Sippy**:
   ```
   /ci:list-unstable-tests 4.20 olmv1 qe-component-readiness.dptools.openshift.org
   ```

   Lists all OLMv1-related tests in version 4.20 from QE Sippy that have a pass rate below 95%.

2. **List unstable storage tests (using default Sippy)**:
   ```
   /ci:list-unstable-tests 4.21 sig-storage
   ```

   Lists all storage-related tests in version 4.21 from production Sippy with pass rate below 95%.

3. **List unstable operator tests**:
   ```
   /ci:list-unstable-tests 4.19 operator
   ```

   Lists all operator-related tests in version 4.19 with pass rate below 95%.

4. **Check specific component stability**:
   ```
   /ci:list-unstable-tests 4.20 sig-network qe-component-readiness.dptools.openshift.org
   ```

   Lists all network-related unstable tests from QE Sippy.

## Notes

- **Pass Rate Threshold**: Fixed at 95% - tests with pass rate >= 95% are considered stable
- **Default Sippy URL**: If no Sippy URL is provided, the command uses `sippy.dptools.openshift.org` by default
- The command queries data from the last 7 days by default
- Ensure you can access the Sippy API endpoints
- Results are sorted by pass percentage (ascending) to show most unstable tests first
- The net improvement metric shows if the test is getting worse (negative) or better (positive)
- If no tests match the keywords, an appropriate message will be displayed
- If all matching tests have pass rate >= 95%, a success message will be shown indicating all tests are stable

## Output Example

```
================================================================================
Unstable Tests Report - 4.20 olmv1
================================================================================
Sippy Instance: qe-component-readiness.dptools.openshift.org
Pass Rate Threshold: < 95%

Summary:
  Total Tests Matching 'olmv1': 45
  Unstable Tests (< 95%): 8 (17.8%)
  Stable Tests (>= 95%): 37 (82.2%)

================================================================================
Tests Below 95% Pass Rate (sorted by worst first):
================================================================================

1. Test: [sig-olmv1] clusterextension install should fail validation
   Pass Rate: 23.5%
   Runs: 17 | Passes: 4 | Failures: 13
   Net Improvement: -45.2

2. Test: [sig-olmv1] clusterextension upgrade from v1 to v2
   Pass Rate: 67.8%
   Runs: 28 | Passes: 19 | Failures: 9
   Net Improvement: -12.3

[... additional tests ...]

================================================================================
```

## See Also

- `/ci:query-test-result` - Query detailed results for a specific test
- Sippy UI (Production): https://sippy.dptools.openshift.org/sippy-ng/
- Sippy UI (QE): https://qe-component-readiness.dptools.openshift.org
- Sippy API Documentation: https://github.com/openshift/sippy
