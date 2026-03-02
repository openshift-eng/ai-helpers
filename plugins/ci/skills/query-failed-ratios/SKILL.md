---
name: Query Failed Ratios
description: Query QE webapp for daily failure rates by subteam
---

# Query Failed Ratios Implementation Guide

This skill provides detailed implementation guidance for the `/ci:query-failed-ratios` command, which queries the OpenShift QE webapp for **daily failure rates** of test cases.

## Overview

The QE webapp provides **daily failure rate percentages** for each test case. This command:
1. Identifies test cases that had failures for a given subteam and date range
2. Queries each test case's detail page to get daily pass/fail/skip percentages
3. Filters to show only days where `failure_rate >= threshold`
4. Generates a report showing which test cases failed on which specific days

## Key Concepts

### What is "Daily Failure Rate"?

The failure rate is calculated **per day** as:
```
failure_rate = (failed_runs / total_runs) × 100%
```

Examples:
- **100%** = All test runs failed that day (e.g., 3 out of 3 failed)
- **66%** = Two-thirds failed (e.g., 2 out of 3 failed)
- **33%** = One-third failed (e.g., 1 out of 3 failed)
- **0%** = All test runs passed (not shown if below threshold)

### Why Daily Rates Matter

Unlike aggregate failure counts, daily rates reveal:
- **Consistency**: Is a test failing every day or just occasionally?
- **Trends**: When did failures start? Are they getting worse?
- **Severity**: 100% failure rate is more critical than sporadic failures
- **Prioritization**: Tests with many consecutive 100% failure days need urgent attention

## Implementation Steps

### Step 1: Parse and Validate Arguments

```python
subteam = sys.argv[1]          # e.g., "SDN"
failure_threshold = sys.argv[2]  # e.g., "10" (means >= 10%)
start_date = sys.argv[3]         # e.g., "2026-01-01"
end_date = sys.argv[4]           # e.g., "2026-01-31"
output_format = sys.argv[5] if len(sys.argv) > 5 else 'text'
```

**Validations:**
- Subteam must match exact case from valid values list
- Failure threshold must be 0-100
- Dates must be YYYY-MM-DD format
- start_date <= end_date

### Step 2: Use the Python Script

The implementation is provided in the helper script:
```bash
python3 ai-helpers/plugins/ci/skills/query-failed-ratios/query_daily_failure_rates.py \
  <subteam> <failure_threshold> <start_date> <end_date> [output_format]
```

**Script location:**
- Absolute: `ai-helpers/plugins/ci/skills/query-failed-ratios/query_daily_failure_rates.py`
- Relative to home: `~/ai-helpers/plugins/ci/skills/query-failed-ratios/query_daily_failure_rates.py`

### Step 3: Script Workflow (What It Does)

The script performs these steps automatically:

1. **Query for test cases** (stderr output)
   ```
   Querying for test cases: https://...
   Found 21 unique test cases
   ```

2. **For each test case** (stderr output):
   ```
   Querying test case 1/21: OCP-55887...
   Querying test case 2/21: OCP-66884...
   ```

3. **Extract daily failure rates** from HTML chart data:
   - Parses LineChart data: `{"name":"Failed","data":[["2026-01-01",100],["2026-01-02",33],...]}`
   - Filters to date range and threshold

4. **Generate report** (stdout output)

### Step 4: Save and Display Report

```bash
# Create output directory
mkdir -p .work/failed-ratios/{subteam}/

# Save report
python3 ai-helpers/plugins/ci/skills/query-failed-ratios/query_daily_failure_rates.py \
  SDN 10 2026-01-01 2026-01-31 text > \
  .work/failed-ratios/SDN/daily-failure-rates-2026-01-01-to-2026-01-31-10pct.txt

# Also generate CSV and Markdown
python3 ... csv > .work/failed-ratios/SDN/daily-failure-rates-...-10pct.csv
python3 ... markdown > .work/failed-ratios/SDN/daily-failure-rates-...-10pct.md
```

### Step 5: Show Summary to User

Display key findings:
```
Summary:
- Test Cases with High Failure Days: 17
- Total High-Failure Days: 196

Top Issues:
- OCP-83672: Failed all 31 days at 100% (CRITICAL)
- OCP-79910: Failed 30 days at 100% (CRITICAL)
- OCP-55887: Failed 24 days (mix of 100% and 33%)

Reports saved to:
- .work/failed-ratios/SDN/daily-failure-rates-2026-01-01-to-2026-01-31-10pct.txt
- .work/failed-ratios/SDN/daily-failure-rates-2026-01-01-to-2026-01-31-10pct.csv
- .work/failed-ratios/SDN/daily-failure-rates-2026-01-01-to-2026-01-31-10pct.md
```

## Output Formats

### Text Format (Default)

```
================================================================================
Daily Failure Rates Report
================================================================================

Test Case: OCP-83672
  High-Failure Days: 31
  Link: https://ocpqe-webapp.../prow_test_cases/OCP-83672

    2026-01-01: 100% failure rate
    2026-01-02: 100% failure rate
    ...
    2026-01-31: 100% failure rate
```

### CSV Format

```csv
# Daily Failure Rates Report
# Subteam: SDN
# Failure Threshold: >= 10.0%
# Date Range: 2026-01-01 to 2026-01-31
# Generated: 2026-02-28 03:21:20
#
# Note: high_failure_days and link are shown only on the first row for each test case

subteam,test_case_id,high_failure_days,link,date,failure_rate_percent
"SDN","OCP-83672",31,"https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-83672",2026-01-01,100
"SDN","OCP-83672",,"",2026-01-02,100
"SDN","OCP-55887",24,"https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-55887",2026-01-01,100
"SDN","OCP-55887",,"",2026-01-12,33
```

**CSV Columns:**
- `subteam`: Subteam name (e.g., SDN) - **shown on every row**, useful when combining reports from multiple subteams
- `test_case_id`: Test case identifier (e.g., OCP-83672) - **shown on every row**
- `high_failure_days`: Total count of days this test had failures >= threshold - **shown only on first row for each test case** to avoid repetition
- `link`: Direct URL to the test case detail page - **shown only on first row for each test case** to avoid repetition
- `date`: Specific date (YYYY-MM-DD) - **shown on every row**
- `failure_rate_percent`: Failure rate percentage for that date (0-100) - **shown on every row**

**Format Notes:**
- Results are grouped by test case ID
- The `high_failure_days` and `link` columns are only populated on the first row for each test case
- Subsequent rows for the same test case have empty values (`""`) for these columns
- This makes the CSV cleaner, easier to read, and avoids unnecessary repetition

### Markdown Format

```markdown
# Daily Failure Rates Report

**Query Parameters:**
- **Subteam:** SDN
- **Failure Threshold:** >= 10%
- **Date Range:** 2026-01-01 to 2026-01-31

**Summary:**
- Total Test Cases with High Failure Days: 17

## Test Cases with High Failure Rates

| Test Case | Subteam | High-Failure Days | Date | Failure Rate | Link |
|-----------|---------|-------------------|------|--------------|------|
| OCP-83672 | SDN | 31 | 2026-01-01 | 100% | [View](https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-83672) |
| OCP-83672 | SDN | 31 | 2026-01-02 | 100% | [View](https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-83672) |
```

**Markdown Features:**
- Clickable links in the "Link" column for easy access to test case details
- High-Failure Days column helps quickly identify most problematic tests
- Table format is ready to paste into JIRA tickets or GitHub issues

## Error Handling

### Authentication Errors

If the script encounters authentication issues:
```
Error querying OCP-12345: HTTP Error 401: Unauthorized
```

**Solutions:**
1. Check VPN connection
2. Verify Kerberos ticket: `klist`
3. Authenticate via browser first
4. The script uses `ssl.CERT_NONE` to bypass certificate verification

### No Data Returned

If no test cases are found:
```
No test cases found with failure rate >= threshold in the specified date range
```

**Possible causes:**
1. Threshold too high - try lowering to 0
2. Wrong subteam name (case-sensitive!)
3. Date range has no test runs
4. All tests passed (good news!)

### Timeout Issues

If queries are timing out, the script will continue with other test cases:
```
Error querying OCP-12345: timeout
Querying test case 2/21: OCP-67890...
```

## Performance Notes

- **Query time**: ~1-2 seconds per test case
- **Total time**: For 21 test cases, expect ~30-60 seconds
- **Progress tracking**: Script outputs progress to stderr
- **Clean output**: Stdout only contains the report (for piping to files)

## Data Source Details

### Main Page Query
URL: `https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/`

Parameters:
- `subteam`: SDN
- `failed_percentage_greater_than`: 0 (to get all test cases)
- `start_date`: 2026-01-01
- `end_date`: 2026-01-31

Returns: HTML page with table of test case IDs

### Test Case Detail Pages
URL: `https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/OCP-55887`

Contains: LineChart with daily pass/fail/skip data:
```javascript
Chartkick["LineChart"]("chart-1", [
  {"name":"Passed","data":[["2026-01-01",0],["2026-01-12",66],...]},
  {"name":"Failed","data":[["2026-01-01",100],["2026-01-12",33],...]},
  {"name":"Skipped","data":[...]}
])
```

The script extracts the "Failed" data series and filters by threshold.

## Prerequisites

**Required:**
- Python 3.6+
- Network access to Red Hat internal networks
- VPN connection (if querying from outside network)

**No additional Python packages needed** - uses only standard library:
- `urllib.request` for HTTP requests
- `ssl` for certificate handling
- `re` for regex parsing
- `json` for JSON output
- `datetime` for date handling

## Example Usage

### Basic Query
```bash
python3 ai-helpers/plugins/ci/skills/query-failed-ratios/query_daily_failure_rates.py \
  SDN 10 2026-01-01 2026-01-31 text
```

### Generate All Formats
```bash
SUBTEAM="SDN"
THRESHOLD="10"
START="2026-01-01"
END="2026-01-31"

mkdir -p .work/failed-ratios/${SUBTEAM}/

python3 ai-helpers/plugins/ci/skills/query-failed-ratios/query_daily_failure_rates.py \
  ${SUBTEAM} ${THRESHOLD} ${START} ${END} text > \
  .work/failed-ratios/${SUBTEAM}/daily-failure-rates-${START}-to-${END}-${THRESHOLD}pct.txt

python3 ai-helpers/plugins/ci/skills/query-failed-ratios/query_daily_failure_rates.py \
  ${SUBTEAM} ${THRESHOLD} ${START} ${END} csv > \
  .work/failed-ratios/${SUBTEAM}/daily-failure-rates-${START}-to-${END}-${THRESHOLD}pct.csv

python3 ai-helpers/plugins/ci/skills/query-failed-ratios/query_daily_failure_rates.py \
  ${SUBTEAM} ${THRESHOLD} ${START} ${END} markdown > \
  .work/failed-ratios/${SUBTEAM}/daily-failure-rates-${START}-to-${END}-${THRESHOLD}pct.md
```

### High Severity Only (50% threshold)
```bash
python3 ai-helpers/plugins/ci/skills/query-failed-ratios/query_daily_failure_rates.py \
  SDN 50 2026-01-01 2026-01-31 text
```

## Interpreting Results

### Critical Issues
Tests failing **every day at 100%**:
- Completely broken
- Highest priority to fix
- Example: OCP-83672 (31 consecutive days at 100%)

### High Severity
Tests failing **most days at high rates**:
- Very unstable
- High priority
- Example: OCP-55887 (24 days, mix of 100% and 33%)

### Medium Severity
Tests with **sporadic high failure days**:
- Flaky or environment-dependent
- Medium priority
- Example: OCP-66884 (7 specific days at 66-100%)

### Low Severity
Tests at **threshold boundary**:
- Occasional failures
- Monitor for trends
- Example: OCP-47088 (1 day at 33%)

## Troubleshooting

### "No data found for subteam"
- Check subteam name is exact match (case-sensitive)
- Valid examples: `SDN`, `Network_Edge`, `API_Server`
- Invalid: `sdn`, `network-edge`, `api-server`

### Script hangs on specific test case
- Network timeout - wait or Ctrl+C and retry
- Script will continue with next test case

### Empty CSV/report
- All tests may have passed (check with threshold=0)
- Date range may have no test runs
- Verify dates are not in the future

## See Also

- QE Webapp: https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/ratios
- Individual test case pages: `.../prow_test_cases/OCP-{id}`
- `/ci:query-test-result` - Query specific test details from Sippy
- `/ci:list-unstable-tests` - List unstable tests with pass rate below 95%
