---
description: Query daily failure rates from QE webapp by subteam and threshold
argument-hint: <subteam> <failure-threshold> <start-date> <end-date> [output-format]
---

## Name
ci:query-failed-ratios

## Synopsis
```
/ci:query-failed-ratios <subteam> <failure-threshold> <start-date> <end-date> [output-format]
```

## Description
The `ci:query-failed-ratios` command queries **daily failure rates** from the OpenShift QE webapp at `ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com`. It shows which test cases had daily failure rates above a specified threshold on which specific days within a given date range.

**What you get:** For each test case, see exactly which days had failure rate >= threshold, with the actual percentage for each day.

This command is useful for:
- Identifying consistently failing tests (vs. occasional failures)
- Seeing when test failures started or stopped
- Prioritizing fixes based on failure severity and frequency
- Tracking test health trends over time
- Generating daily failure rate reports for QE team review

## Arguments
- `$1` (subteam): Subteam name to filter tests. **Valid values** (case-sensitive):
  - `API_Server`, `Authentication`, `Cluster_Infrastructure`, `Cluster_Observability`, `Cluster_Operator`
  - `Container_Engine_Tools`, `DR_Testing`, `ETCD`, `Hypershift`, `INSTALLER`, `Image_Registry`
  - `LOGGING`, `MCO`, `MTO`, `NODE`, `Network_Edge`, `Network_Observability`
  - `OAP`, `OLM`, `OTA`, `Operator_SDK`, `PSAP`, `PerfScale`, `SDN`, `STORAGE`
  - `Security_and_Compliance`, `User_Interface_Cypress`, `Windows_Containers`, `Workloads`
- `$2` (failure-threshold): Minimum **daily** failure percentage to include (e.g., "10" means show days where >= 10% of test runs failed)
- `$3` (start-date): Start date in YYYY-MM-DD format (e.g., "2026-01-01")
- `$4` (end-date): End date in YYYY-MM-DD format (e.g., "2026-01-31")
- `$5` (output-format) [optional]: Output format - "json", "csv", "markdown", or "text" (default: "text")

## Implementation

**Implementation script:** Use the Python helper script at:
```
ai-helpers/plugins/ci/skills/query-failed-ratios/query_daily_failure_rates.py
```

### Steps:

1. **Parse and Validate Arguments**
   - Extract subteam from `$1` (must match exact case from valid values list)
   - Extract failure threshold from `$2` (validate it's a number between 0-100)
   - Extract start date from `$3` (validate YYYY-MM-DD format)
   - Extract end date from `$4` (validate YYYY-MM-DD format)
   - Extract output format from `$5` if provided, default to "text"
   - Validate that start_date <= end_date

2. **Run the Query Script**
   ```bash
   mkdir -p .work/failed-ratios/${subteam}/

   # Determine file extension based on format
   case "${output_format}" in
     json) ext="json" ;;
     csv) ext="csv" ;;
     markdown) ext="md" ;;
     *) ext="txt" ;;
   esac

   # Capture stdout (report) and stderr (diagnostics) separately
   # - stdout → report file (clean structured data)
   # - stderr → .log file (progress messages, errors, diagnostics)
   python3 ai-helpers/plugins/ci/skills/query-failed-ratios/query_daily_failure_rates.py \
     ${subteam} ${failure_threshold} ${start_date} ${end_date} ${output_format} \
     > .work/failed-ratios/${subteam}/daily-failure-rates-${start_date}-to-${end_date}-${failure_threshold}pct.${ext} \
     2> .work/failed-ratios/${subteam}/daily-failure-rates-${start_date}-to-${end_date}-${failure_threshold}pct.log
   ```

3. **What the Script Does**

   The script performs these steps automatically:

   a. **Query for test cases**: Hits the main QE webapp page to get list of test cases with failures
      - URL: `https://ocpqe-webapp.../?subteam=${subteam}&failed_percentage_greater_than=0&start_date=${start_date}&end_date=${end_date}`
      - Parses HTML to extract test case IDs from the subteam's section

   b. **For each test case**: Query its detail page to get daily failure rates
      - URL: `https://ocpqe-webapp.../prow_test_cases/OCP-{id}`
      - Extracts chart data containing daily pass/fail percentages
      - Chart format: `{"name":"Failed","data":[["2026-01-01",100],["2026-01-12",33],...]}`

   c. **Filter by threshold**: Keep only days where `failure_rate >= threshold`
      - Only includes days within the specified date range
      - Filters out days below the threshold

   d. **Generate report**: Format results according to requested output format
      - **stdout**: Clean structured report (CSV/JSON/Markdown/Text)
      - **stderr**: Progress messages, diagnostics, errors, security warnings (plain text, not formatted as comments)

   **Security:**
   - Script attempts secure HTTPS connection first (with certificate validation)
   - If certificate validation fails, falls back to insecure mode with warning
   - Security warning appears in stderr/log: "Warning: Secure connection failed, falling back to insecure mode"


4. **Save Reports in Multiple Formats** (Optional but recommended)
   ```bash
   # IMPORTANT: Always separate stdout (report) from stderr (diagnostics)
   # Pattern: > report_file 2> log_file

   # Text report + diagnostics
   python3 ... text \
     > .work/failed-ratios/${subteam}/daily-failure-rates-...-${threshold}pct.txt \
     2> .work/failed-ratios/${subteam}/daily-failure-rates-...-${threshold}pct.log

   # CSV report + diagnostics
   python3 ... csv \
     > .work/failed-ratios/${subteam}/daily-failure-rates-...-${threshold}pct.csv \
     2> .work/failed-ratios/${subteam}/daily-failure-rates-...-${threshold}pct.log

   # Markdown report + diagnostics
   python3 ... markdown \
     > .work/failed-ratios/${subteam}/daily-failure-rates-...-${threshold}pct.md \
     2> .work/failed-ratios/${subteam}/daily-failure-rates-...-${threshold}pct.log

   # JSON report + diagnostics
   python3 ... json \
     > .work/failed-ratios/${subteam}/daily-failure-rates-...-${threshold}pct.json \
     2> .work/failed-ratios/${subteam}/daily-failure-rates-...-${threshold}pct.log
   ```

5. **Display Summary to User**

   Show key findings from the report:
   - **Total test cases** with high-failure days (focus on COUNT of test cases, not total days)
   - **Severity categorization**: Group tests by failure patterns
     - CRITICAL: Tests with mostly 100% failure rates (completely broken)
     - HIGH: Tests with frequent high failure rates
     - FLAKY: Tests with mostly 0% or low % (intermittent failures)
   - **Top 3 most problematic tests**: Listed by number of days with failures >= threshold
   - **Links to generated files**:
     - Report file: `.work/failed-ratios/${subteam}/daily-failure-rates-...-${threshold}pct.${ext}`
     - Diagnostics log: `.work/failed-ratios/${subteam}/daily-failure-rates-...-${threshold}pct.log`

   **IMPORTANT**: Avoid summing up total days across all test cases as this is confusing.
   Example: If 9 tests each fail 20 days, don't say "180 failure days" - instead say "9 test cases with failures, top test failed 20 days".

### Performance Notes

- **Query time**: ~1-2 seconds per test case (queries individual test case pages)
- **Total time**: For 20 test cases, expect 30-60 seconds
- **Progress tracking**: Script outputs progress to stderr (saved to `.log` file when using separate redirection)
  - Example progress messages: "Querying for test cases: ...", "Found 21 unique test cases", "Querying test case 5/21: OCP-55887..."
  - These are plain text (not formatted as comments), so they must be captured separately from report output

### Error Handling

- **Certificate verification**: Script tries secure connection first, falls back to insecure only if needed
  - Secure by default: Validates SSL certificates to prevent MITM attacks
  - Fallback: If certificate validation fails (self-signed certs), warns user and disables verification
  - Warning appears once in diagnostics log when falling back to insecure mode
- **Authentication errors**: Inform user to check VPN connection and Kerberos ticket (`klist`)
- **No data**: If no test cases found, verify subteam name (case-sensitive!) and date range
- **Timeout**: Script continues with next test case if one fails

## Return Value

**Format**: Report showing daily failure rates for each test case

**Query Parameters Section:**
- Subteam
- Failure threshold (%)
- Date range (start - end)
- Query timestamp

**Summary Section:**
- Test Cases with High Failure Days: Count of test cases that had days with failure rate >= threshold

**Test Case Details:**
For each test case with days >= threshold:
- Test case ID
- Number of high-failure days
- Link to test case detail page
- List of dates with failure rates:
  - Date (YYYY-MM-DD)
  - Failure rate percentage

**Output Files:**
- **Report**: `.work/failed-ratios/{subteam}/daily-failure-rates-{start_date}-to-{end_date}-{threshold}pct.{ext}`
  - Contains structured data (CSV/JSON/Markdown/Text)
  - Clean output suitable for parsing, import, or analysis
- **Diagnostics log**: `.work/failed-ratios/{subteam}/daily-failure-rates-{start_date}-to-{end_date}-{threshold}pct.log`
  - Contains progress messages, errors, warnings
  - Useful for debugging query issues or understanding what was fetched

## Examples

1. **Query SDN tests with daily failure rate >= 10% in January**:
   ```
   /ci:query-failed-ratios SDN 10 2026-01-01 2026-01-31
   ```

2. **High-severity storage failures (>= 50%) in last week**:
   ```
   /ci:query-failed-ratios STORAGE 50 2026-02-21 2026-02-28
   ```

3. **Generate CSV report for authentication tests**:
   ```
   /ci:query-failed-ratios Authentication 10 2026-01-01 2026-01-31 csv
   ```

4. **Export to Markdown for JIRA ticket**:
   ```
   /ci:query-failed-ratios Network_Edge 20 2026-01-01 2026-01-31 markdown
   ```

5. **Find all failing days (>= 0%) for NODE team**:
   ```
   /ci:query-failed-ratios NODE 0 2026-01-01 2026-01-31
   ```

## Output Example

```
================================================================================
Daily Failure Rates Report
================================================================================
Query Time: 2026-02-28 02:09:09 UTC
Source: ocpqe-webapp-aos-qe-ci (runtime-int)

Query Parameters:
  Subteam: SDN
  Failure Threshold: >= 10.0%
  Date Range: 2026-01-01 to 2026-01-31

Summary:
  Test Cases with High Failure Days: 17

================================================================================
Test Cases with Daily Failure Rate >= Threshold:
================================================================================

Test Case: OCP-83672
  High-Failure Days: 31
  Link: https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-83672

    2026-01-01: 100% failure rate
    2026-01-02: 100% failure rate
    2026-01-03: 100% failure rate
    ...
    2026-01-31: 100% failure rate

Test Case: OCP-79910
  High-Failure Days: 30
  Link: https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-79910

    2026-01-01: 100% failure rate
    2026-01-02: 100% failure rate
    ...
    2026-01-31: 100% failure rate

Test Case: OCP-55887
  High-Failure Days: 24
  Link: https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-55887

    2026-01-01: 100% failure rate
    2026-01-02: 100% failure rate
    ...
    2026-01-12: 33% failure rate
    ...
    2026-01-31: 100% failure rate

[... additional test cases ...]

================================================================================
Note: Failure rates shown are daily percentages.
A failure rate of 100% means all test runs failed that day.
A failure rate of 0% means all test runs passed that day.
================================================================================

Files saved to:
  Report: .work/failed-ratios/SDN/daily-failure-rates-2026-01-01-to-2026-01-31-10pct.txt
  Diagnostics: .work/failed-ratios/SDN/daily-failure-rates-2026-01-01-to-2026-01-31-10pct.log
```

## CSV Output Example

```csv
# Daily Failure Rates Report
# Subteam: SDN
# Failure Threshold: >= 10.0%
# Date Range: 2026-01-01 to 2026-01-31
# Generated: 2026-02-28 03:21:20

subteam,test_case_id,failure_rate_percent,date,high_failure_days
"SDN","=HYPERLINK(""https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-83672"", ""OCP-83672"")",100,2026-01-01,31
"SDN","=HYPERLINK(""https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-83672"", ""OCP-83672"")",100,2026-01-02,31
"SDN","=HYPERLINK(""https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-83672"", ""OCP-83672"")",100,2026-01-03,31
"SDN","=HYPERLINK(""https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-79910"", ""OCP-79910"")",100,2026-01-01,30
"SDN","=HYPERLINK(""https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-79910"", ""OCP-79910"")",100,2026-01-02,30
"SDN","=HYPERLINK(""https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-55887"", ""OCP-55887"")",100,2026-01-01,24
"SDN","=HYPERLINK(""https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-55887"", ""OCP-55887"")",33,2026-01-12,24
"SDN","=HYPERLINK(""https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-55887"", ""OCP-55887"")",100,2026-01-31,24
```

**CSV Columns:**
- **subteam**: Subteam name (e.g., SDN)
- **test_case_id**: Clickable hyperlink to test case detail page (uses Excel/Google Sheets HYPERLINK formula)
- **failure_rate_percent**: Failure rate percentage for that date
- **date**: Specific date (YYYY-MM-DD)
- **high_failure_days**: Total number of days this test had failures >= threshold


## Markdown Output Example

```markdown
# Daily Failure Rates Report

**Query Parameters:**
- **Subteam:** SDN
- **Failure Threshold:** >= 10%
- **Date Range:** 2026-01-01 to 2026-01-31
- **Generated:** 2026-02-28 03:11:49

**Summary:**
- Test Cases with High Failure Days: 17

## Test Cases with High Failure Rates

| Subteam | Test Case | Failure Rate | Date | High-Failure Days |
|---------|-----------|--------------|------|-------------------|
| SDN | [OCP-83672](https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-83672) | 100% | 2026-01-01 | 31 |
| SDN | [OCP-83672](https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-83672) | 100% | 2026-01-02 | 31 |
| SDN | [OCP-83672](https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-83672) | 100% | 2026-01-03 | 31 |
| SDN | [OCP-79910](https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-79910) | 100% | 2026-01-01 | 30 |
| SDN | [OCP-55887](https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-55887) | 100% | 2026-01-01 | 24 |
| SDN | [OCP-55887](https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-55887) | 33% | 2026-01-12 | 24 |
```

## Understanding the Results

### What is "Daily Failure Rate"?

Daily failure rate = (Failed test runs / Total test runs) × 100% **for that specific day**

Examples:
- **100%** = All test runs failed that day (e.g., 3/3 failed)
- **66%** = Two-thirds failed (e.g., 2/3 failed)
- **33%** = One-third failed (e.g., 1/3 failed)
- **0%** = All test runs passed (not shown if below threshold)

### Interpreting Severity

**CRITICAL** - Tests failing every day at 100%:
- Completely broken test
- Highest priority to fix
- Example: OCP-83672 (31 consecutive days at 100%)

**HIGH** - Tests failing most days at high rates:
- Very unstable test
- High priority
- Example: OCP-55887 (24 days, mostly 100%, some 33%)

**MEDIUM** - Tests with sporadic high failure days:
- Flaky or environment-dependent
- Medium priority
- Example: OCP-66884 (7 specific days at 66-100%)

**LOW** - Tests at threshold boundary:
- Occasional failures
- Monitor for trends
- Example: OCP-47088 (1 day at 33%)

## Notes

- **Data Source**: QE webapp provides daily pass/fail/skip percentages
- **Failure Rate**: This is a **daily** percentage, showing how many runs failed each day
- **Threshold**: Applied to **each day individually** - days below threshold are not shown
- **Security**: Script uses secure HTTPS by default; only disables certificate verification if connection fails
  - Secure by default: Validates SSL certificates to prevent man-in-the-middle attacks
  - Automatic fallback: If webapp uses self-signed certificates, script warns and proceeds insecurely
  - Check diagnostics log for security warnings
- **Authentication**: May require Red Hat network access, VPN, or Kerberos authentication
- **Network Access**: Ensure you can reach internal Red Hat network URLs
- **Date Format**: Dates must be in YYYY-MM-DD format (ISO 8601)
- **Failure Threshold**: Value should be between 0 and 100 (percentage)
- **Subteam Names**: **CRITICAL - Case-sensitive and must use underscores**. Use exact values from the Arguments section (e.g., `SDN`, `Network_Edge`, `API_Server` - NOT `sdn`, `network-edge`, or `api-server`)
- **Output Directory**: `.work/failed-ratios/` is in .gitignore for temporary analysis files
- **Query Performance**: Queries each test case individually (~1-2 sec each), so expect 30-60 seconds for ~20 test cases

## Prerequisites

Before using this command, verify:

1. **Network Access**
   - You can reach internal Red Hat network URLs
   - VPN is connected if required
   - Test with: `curl -k "https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/ratios"`

2. **Authentication**
   - Kerberos ticket is valid (if required): `klist`
   - SSO credentials are configured

3. **Required Tools**
   - Python 3.6+ (no additional packages needed - uses standard library only)

## Troubleshooting

**Problem**: "SSL certificate verification failed"
- **Solution**: Script automatically falls back to insecure mode if secure connection fails
- Check the diagnostics log for warning: "Warning: Secure connection failed, falling back to insecure mode"
- If you see this warning, it means the webapp is using self-signed or invalid certificates
- **Security note**: Fallback mode disables certificate verification, which allows potential MITM attacks

**Problem**: "401 Unauthorized" or "403 Forbidden"
- **Solution**: Check VPN connection, verify Kerberos ticket with `klist`, or authenticate via browser first

**Problem**: "No data returned" or "No test cases found with failure rate >= threshold"
- **Solution**:
  - Verify subteam name matches exact case from valid values list (e.g., `SDN` not `sdn`)
  - Ensure underscores are used (e.g., `Network_Edge` not `Network-Edge`)
  - Check date range is valid and not in the future
  - Try lowering threshold to 0 to see all results
  - Date range may have no test runs (try a different time period)

**Problem**: "Connection timeout" or script hangs
- **Solution**:
  - Verify network connectivity to Red Hat internal network, check VPN status
  - Script will continue with next test case if one times out
  - Wait or press Ctrl+C and retry

**Problem**: Script is slow
- **Expected**: Queries ~1-2 seconds per test case (queries individual pages for daily data)
- Progress shown on stderr (check `.log` file): "Querying test case 5/21: OCP-55887..."
- If using separate redirection, tail the log file to monitor progress: `tail -f .work/failed-ratios/*/...log`

## See Also

- `/ci:query-test-result` - Query specific test details from Sippy
- `/ci:list-unstable-tests` - List unstable tests with pass rate below 95%
- QE Webapp: https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/ratios
- Individual test case pages: https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-{id}
