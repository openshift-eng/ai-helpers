#!/usr/bin/env python3
"""
Query QE webapp for daily failure rates by subteam and threshold

Returns: For each test case, shows which days had failure rate >= threshold
"""

import re
import json
import sys
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen, Request
import ssl
from urllib.error import URLError
from collections import defaultdict

def secure_urlopen(request, timeout=30, warn_on_insecure=True):
    """
    Attempt to open URL with certificate verification enabled (secure by default).
    If that fails due to certificate issues, fall back to skipping verification.

    Args:
        request: urllib.request.Request object
        timeout: Timeout in seconds for the request (default: 30)
        warn_on_insecure: Print warning when falling back to insecure mode

    Returns:
        Response object from urlopen
    """
    # Try secure connection first (with certificate verification)
    try:
        secure_ctx = ssl.create_default_context()
        return urlopen(request, context=secure_ctx, timeout=timeout)
    except URLError as secure_err:
        # Only fall back when failure is specifically certificate-validation related.
        reason = getattr(secure_err, "reason", None)
        is_cert_failure = isinstance(reason, ssl.SSLCertVerificationError)
        if not is_cert_failure:
            raise

        # If secure connection fails due to certificates, try without verification
        if warn_on_insecure:
            print(f"Warning: Secure connection failed ({type(secure_err).__name__}), falling back to insecure mode", file=sys.stderr)
            print(f"  This weakens transport security and allows tampered responses", file=sys.stderr)

        insecure_ctx = ssl.create_default_context()
        insecure_ctx.check_hostname = False
        insecure_ctx.verify_mode = ssl.CERT_NONE
        return urlopen(request, context=insecure_ctx, timeout=timeout)
    except ssl.SSLError:
        # Non-verification SSL errors should be surfaced directly.
        raise

def query_qe_webapp(subteam, failure_threshold, start_date, end_date):
    """Query the QE webapp for test cases and their daily failure rates"""

    # Step 1: Get list of test cases that had failures in this period
    base_url = "https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/"
    params = f"?subteam={subteam}&failed_percentage_greater_than=0&start_date={start_date}&end_date={end_date}"
    url = base_url + params

    print(f"Querying for test cases: {url}", file=sys.stderr)

    req = Request(url)
    try:
        with secure_urlopen(req) as response:
            html = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error querying test-case index page: {e}", file=sys.stderr)
        return None

    # Parse HTML to find the subteam section
    subteam_pattern = f'<div class="tab-pane fade" id="{subteam}">(.*?)(?:<div class="tab-pane fade" id=|</div>\s*</div>\s*</div>\s*</body>)'
    subteam_section = re.search(subteam_pattern, html, re.DOTALL)

    if not subteam_section:
        print(f"No data found for subteam: {subteam}", file=sys.stderr)
        return None

    section_html = subteam_section.group(1)

    # Extract test case IDs from the table
    test_case_ids = set()
    table_match = re.search(r'<tbody>(.*?)</tbody>', section_html, re.DOTALL)
    if table_match:
        table_html = table_match.group(1)
        case_ids = re.findall(r'href="/prow_test_cases/(OCP-\d+)"', table_html)
        test_case_ids.update(case_ids)

    print(f"Found {len(test_case_ids)} unique test cases", file=sys.stderr)

    # Step 2: For each test case, get its daily failure rates
    test_results = {}

    for i, case_id in enumerate(sorted(test_case_ids), 1):
        print(f"Querying test case {i}/{len(test_case_ids)}: {case_id}...", file=sys.stderr)

        case_url = f"{base_url}prow_test_cases/{case_id}"
        req = Request(case_url)

        try:
            # Don't warn on each test case to avoid spam (already warned on first request)
            with secure_urlopen(req, warn_on_insecure=False) as response:
                case_html = response.read().decode('utf-8')

            # Parse the chart data for this test case
            # Look for: [{"name":"Passed","data":[["2026-01-05",97],...]},{"name":"Failed","data":[["2026-01-05",2],...]}]
            chart_match = re.search(r'Chartkick\["LineChart"\]\("chart-\d+",\s*(\[.*?\]),\s*\{', case_html, re.DOTALL)

            if chart_match:
                chart_data_str = chart_match.group(1)
                # This is a complex nested structure, need to parse it carefully

                # Extract Failed data series
                failed_match = re.search(r'\{"name":"Failed","data":(\[\[.*?\]\])\}', chart_data_str, re.DOTALL)
                if failed_match:
                    failed_data_str = failed_match.group(1)
                    try:
                        failed_data = json.loads(failed_data_str)
                    except json.JSONDecodeError as e:
                        print(f"  Error parsing failed series for {case_id}: {e}", file=sys.stderr)
                        continue
                    # Filter to only dates in our range and failure rate >= threshold
                    high_failure_days = []
                    for date_str, failure_rate in failed_data:
                        if failure_rate >= float(failure_threshold):
                            # Check if date is in our range
                            try:
                                test_date = datetime.strptime(date_str, '%Y-%m-%d')
                                start = datetime.strptime(start_date, '%Y-%m-%d')
                                end = datetime.strptime(end_date, '%Y-%m-%d')

                                if start <= test_date <= end:
                                    high_failure_days.append({
                                        'date': date_str,
                                        'failure_rate': failure_rate
                                    })
                            except Exception as e:
                                print(f"  Warning: Skipping invalid date '{date_str}' for {case_id}: {e}", file=sys.stderr)

                    if high_failure_days:
                        test_results[case_id] = high_failure_days

        except Exception as e:
            print(f"  Error querying {case_id}: {e}", file=sys.stderr)
            continue

    return {
        'subteam': subteam,
        'query': {
            'subteam': subteam,
            'failure_threshold': float(failure_threshold),
            'start_date': start_date,
            'end_date': end_date,
        },
        'results': test_results
    }

def generate_report(data, output_format='text'):
    """Generate report from queried data"""

    if not data or not data.get('results'):
        return "No test cases found with failure rate >= threshold in the specified date range"

    query = data['query']
    results = data['results']

    if output_format == 'json':
        return json.dumps(data, indent=2)

    elif output_format == 'csv':
        lines = [
            f"# Daily Failure Rates Report",
            f"# Subteam: {query['subteam']}",
            f"# Failure Threshold: >= {query['failure_threshold']}%",
            f"# Date Range: {query['start_date']} to {query['end_date']}",
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "subteam,test_case_id,failure_rate_percent,date,high_failure_days"
        ]

        base_url = "https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com"

        for case_id in sorted(results.keys()):
            high_failure_days = len(results[case_id])
            link = f"{base_url}/prow_test_cases/{case_id}"
            # Excel/Google Sheets HYPERLINK formula: =HYPERLINK("url", "display_text")
            # In CSV, double quotes inside quoted fields must be escaped by doubling them
            hyperlink_formula = f'=HYPERLINK("{link}", "{case_id}")'
            # Escape quotes for CSV: " becomes ""
            hyperlink_formula_escaped = hyperlink_formula.replace('"', '""')

            # Sort days by date
            sorted_days = sorted(results[case_id], key=lambda x: x['date'])

            # All rows: include all fields (no empty cells)
            for day_data in sorted_days:
                lines.append(f'"{query["subteam"]}","{hyperlink_formula_escaped}",{day_data["failure_rate"]},{day_data["date"]},{high_failure_days}')

        return "\n".join(lines)

    elif output_format == 'markdown':
        lines = [
            f"# Daily Failure Rates Report",
            "",
            f"**Query Parameters:**",
            f"- **Subteam:** {query['subteam']}",
            f"- **Failure Threshold:** >= {query['failure_threshold']}%",
            f"- **Date Range:** {query['start_date']} to {query['end_date']}",
            f"- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"**Summary:**",
            f"- Test Cases with High Failure Days: {len(results)}",
            "",
            "## Test Cases with High Failure Rates",
            "",
            "| Subteam | Test Case | Failure Rate | Date | High-Failure Days |",
            "|---------|-----------|--------------|------|-------------------|"
        ]

        base_url = "https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com"

        for case_id in sorted(results.keys()):
            high_failure_days = len(results[case_id])
            link = f"{base_url}/prow_test_cases/{case_id}"
            # Embed hyperlink in test case ID using markdown syntax
            test_case_link = f"[{case_id}]({link})"

            for day_data in sorted(results[case_id], key=lambda x: x['date']):
                lines.append(f"| {query['subteam']} | {test_case_link} | {day_data['failure_rate']}% | {day_data['date']} | {high_failure_days} |")

        return "\n".join(lines)

    else:  # text format
        report = []
        report.append("=" * 80)
        report.append("Daily Failure Rates Report")
        report.append("=" * 80)
        report.append(f"Query Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        report.append(f"Source: ocpqe-webapp-aos-qe-ci (runtime-int)")
        report.append("")
        report.append("Query Parameters:")
        report.append(f"  Subteam: {query['subteam']}")
        report.append(f"  Failure Threshold: >= {query['failure_threshold']}%")
        report.append(f"  Date Range: {query['start_date']} to {query['end_date']}")
        report.append("")
        report.append("Summary:")
        report.append(f"  Test Cases with High Failure Days: {len(results)}")
        report.append("")
        report.append("=" * 80)
        report.append("Test Cases with Daily Failure Rate >= Threshold:")
        report.append("=" * 80)
        report.append("")

        for case_id in sorted(results.keys()):
            days = sorted(results[case_id], key=lambda x: x['date'])
            report.append(f"Test Case: {case_id}")
            report.append(f"  High-Failure Days: {len(days)}")
            report.append(f"  Link: https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/prow_test_cases/{case_id}")
            report.append("")

            for day_data in days:
                report.append(f"    {day_data['date']}: {day_data['failure_rate']}% failure rate")

            report.append("")

        report.append("=" * 80)
        report.append("Note: Failure rates shown are daily percentages.")
        report.append("A failure rate of 100% means all test runs failed that day.")
        report.append("A failure rate of 0% means all test runs passed that day.")
        report.append("=" * 80)

        return "\n".join(report)

def main():
    if len(sys.argv) < 5:
        print("Usage: query_daily_failure_rates.py <subteam> <failure_threshold> <start_date> <end_date> [output_format]", file=sys.stderr)
        sys.exit(1)

    subteam = sys.argv[1]
    failure_threshold = sys.argv[2]
    start_date = sys.argv[3]
    end_date = sys.argv[4]
    output_format = sys.argv[5] if len(sys.argv) > 5 else 'text'

    # Define valid subteam names (extracted from QE webapp dropdown on 2026-03-02)
    # Source: https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/ratios
    # Note: Removed "Logging" (lowercase) - only "LOGGING" (uppercase) is valid
    # Note: Removed "pod" - not a standard subteam name
    valid_subteams = [
        'API_Server', 'Authentication', 'Cluster_Infrastructure', 'Cluster_Observability', 'Cluster_Operator',
        'Container_Engine_Tools', 'DR_Testing', 'ETCD', 'Hypershift', 'INSTALLER', 'Image_Registry',
        'LOGGING', 'MCO', 'MTO', 'NODE', 'Network_Edge', 'Network_Observability',
        'OAP', 'OLM', 'OTA', 'Operator_SDK', 'PSAP', 'PerfScale', 'SDN', 'STORAGE',
        'Security_and_Compliance', 'User_Interface_Cypress', 'Windows_Containers', 'Workloads'
    ]

    # Validate subteam name
    if subteam not in valid_subteams:
        print(f"Error: Invalid subteam name '{subteam}'", file=sys.stderr)
        print(f"\nValid subteam names (case-sensitive):", file=sys.stderr)
        # Print in organized columns
        for i in range(0, len(valid_subteams), 3):
            row = valid_subteams[i:i+3]
            print(f"  {', '.join(row)}", file=sys.stderr)

        # Check for case-insensitive matches and suggest
        subteam_lower = subteam.lower()
        suggestions = [s for s in valid_subteams if s.lower() == subteam_lower]
        if suggestions:
            print(f"\nDid you mean: {suggestions[0]}?", file=sys.stderr)
        sys.exit(1)

    # Validate threshold is numeric
    try:
        threshold_value = float(failure_threshold)
    except ValueError:
        print(f"Error: Failure threshold must be a number, got '{failure_threshold}'", file=sys.stderr)
        sys.exit(1)

    # Validate threshold range (0-100)
    if threshold_value < 0 or threshold_value > 100:
        print(f"Error: Failure threshold must be between 0 and 100, got {threshold_value}", file=sys.stderr)
        sys.exit(1)

    # Validate date formats (YYYY-MM-DD)
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    except ValueError:
        print(f"Error: Start date must be in YYYY-MM-DD format, got '{start_date}'", file=sys.stderr)
        sys.exit(1)

    try:
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        print(f"Error: End date must be in YYYY-MM-DD format, got '{end_date}'", file=sys.stderr)
        sys.exit(1)

    # Validate date range (start <= end)
    if start_dt > end_dt:
        print(f"Error: Start date ({start_date}) must be before or equal to end date ({end_date})", file=sys.stderr)
        sys.exit(1)

    # Validate output format
    valid_formats = ['text', 'csv', 'markdown', 'json']
    if output_format not in valid_formats:
        print(f"Warning: Unknown output format '{output_format}', using 'text' format", file=sys.stderr)
        output_format = 'text'

    # Query the webapp
    data = query_qe_webapp(subteam, failure_threshold, start_date, end_date)

    if not data:
        print("Failed to retrieve data", file=sys.stderr)
        sys.exit(1)

    # Generate and print report
    report = generate_report(data, output_format)
    print(report)

if __name__ == '__main__':
    main()
