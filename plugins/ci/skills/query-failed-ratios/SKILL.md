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
```text
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
   ```text
   Querying for test cases: https://...
   Found 21 unique test cases
   ```

2. **For each test case** (stderr output):
   ```text
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

Display key findings focused on **test case counts** and **severity**, not total days:

```text
Summary:
- Test Cases with High Failure Days: 17

By Severity:
- CRITICAL (Mostly 100% failures): 12 test cases
  - Completely broken, highest priority
- HIGH (Frequent high failures): 3 test cases
  - Very unstable, high priority
- FLAKY (Mostly 0% or low %): 2 test cases
  - Intermittent failures, monitor for trends

Top 3 Most Problematic:
1. OCP-83672: Failed all 31 days at 100% (CRITICAL)
2. OCP-79910: Failed 30 days at 100% (CRITICAL)
3. OCP-55887: Failed 24 days (mix of 100% and 33%)

Reports saved to:
- .work/failed-ratios/SDN/daily-failure-rates-2026-01-01-to-2026-01-31-10pct.txt
- .work/failed-ratios/SDN/daily-failure-rates-2026-01-01-to-2026-01-31-10pct.csv
- .work/failed-ratios/SDN/daily-failure-rates-2026-01-01-to-2026-01-31-10pct.md
```

**IMPORTANT**: Do NOT sum up total days across all test cases (e.g., "Total High-Failure Days: 196").
This is confusing because it aggregates across multiple test cases. Focus on:
- COUNT of test cases (actionable - you fix test cases, not days)
- Severity categorization (helps prioritize)
- Top problematic tests (shows what needs immediate attention)

## Output Formats

### Text Format (Default)

```text
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
- `subteam`: Subteam name (e.g., SDN)
- `test_case_id`: Clickable hyperlink to test case detail page (uses Excel/Google Sheets HYPERLINK formula)
- `failure_rate_percent`: Failure rate percentage for that date
- `date`: Specific date (YYYY-MM-DD)
- `high_failure_days`: Total number of days this test had failures >= threshold


### Markdown Format

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

**Markdown Features:**
- Test case IDs are clickable links for easy access to test case details
- High-Failure Days column helps quickly identify most problematic tests
- Table format is ready to paste into JIRA tickets or GitHub issues

### JSON Format

```json
{
  "subteam": "SDN",
  "query": {
    "subteam": "SDN",
    "failure_threshold": 10.0,
    "start_date": "2026-01-01",
    "end_date": "2026-01-31"
  },
  "results": {
    "OCP-83672": [
      {
        "date": "2026-01-01",
        "failure_rate": 100
      },
      {
        "date": "2026-01-02",
        "failure_rate": 100
      },
      {
        "date": "2026-01-31",
        "failure_rate": 100
      }
    ],
    "OCP-79910": [
      {
        "date": "2026-01-01",
        "failure_rate": 100
      },
      {
        "date": "2026-01-02",
        "failure_rate": 100
      }
    ],
    "OCP-55887": [
      {
        "date": "2026-01-01",
        "failure_rate": 100
      },
      {
        "date": "2026-01-12",
        "failure_rate": 33
      },
      {
        "date": "2026-01-31",
        "failure_rate": 100
      }
    ]
  }
}
```

**JSON Features:**
- Machine-readable format for programmatic analysis
- Structured data with query parameters and results
- Easy to parse with `jq`, Python, or other tools
- Each test case maps to array of high-failure days with dates and rates


## Error Handling

### Authentication Errors

If the script encounters authentication issues:
```text
Error querying OCP-12345: HTTP Error 401: Unauthorized
```

**Solutions:**
1. Check VPN connection
2. Verify Kerberos ticket: `klist`
3. Authenticate via browser first

### No Data Returned

If no test cases are found:
```text
No test cases found with failure rate >= threshold in the specified date range
```

**Possible causes:**
1. Threshold too high - try lowering to 0
2. Wrong subteam name (case-sensitive!)
3. Date range has no test runs
4. All tests passed (good news!)

### Timeout Issues

If queries are timing out, the script will continue with other test cases:
```text
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
