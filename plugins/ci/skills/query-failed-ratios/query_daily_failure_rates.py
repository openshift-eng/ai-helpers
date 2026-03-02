#!/usr/bin/env python3
"""
Query QE webapp for daily failure rates by subteam and threshold

Returns: For each test case, shows which days had failure rate >= threshold
"""

import re
import json
import sys
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
import ssl
from collections import defaultdict

def query_qe_webapp(subteam, failure_threshold, start_date, end_date):
    """Query the QE webapp for test cases and their daily failure rates"""

    # Create SSL context that doesn't verify certificates
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # Step 1: Get list of test cases that had failures in this period
    base_url = "https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com/"
    params = f"?subteam={subteam}&failed_percentage_greater_than=0&start_date={start_date}&end_date={end_date}"
    url = base_url + params

    print(f"Querying for test cases: {url}", file=sys.stderr)

    req = Request(url)
    with urlopen(req, context=ctx) as response:
        html = response.read().decode('utf-8')

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
            with urlopen(req, context=ctx) as response:
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
                    failed_data = eval(failed_data_str)

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
                            except:
                                pass

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
            f"#",
            f"# Note: high_failure_days and link are shown only on the first row for each test case",
            "",
            "subteam,test_case_id,high_failure_days,link,date,failure_rate_percent"
        ]

        base_url = "https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com"

        for case_id in sorted(results.keys()):
            high_failure_days = len(results[case_id])
            link = f"{base_url}/prow_test_cases/{case_id}"

            # Sort days by date
            sorted_days = sorted(results[case_id], key=lambda x: x['date'])

            # First row: include all columns
            first_day = sorted_days[0]
            lines.append(f'"{query["subteam"]}","{case_id}",{high_failure_days},"{link}",{first_day["date"]},{first_day["failure_rate"]}')

            # Subsequent rows: empty high_failure_days and link columns
            for day_data in sorted_days[1:]:
                lines.append(f'"{query["subteam"]}","{case_id}",,"",{day_data["date"]},{day_data["failure_rate"]}')

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
            f"- Total Test Cases with High Failure Days: {len(results)}",
            "",
            "## Test Cases with High Failure Rates",
            "",
            "| Test Case | Subteam | High-Failure Days | Date | Failure Rate | Link |",
            "|-----------|---------|-------------------|------|--------------|------|"
        ]

        base_url = "https://ocpqe-webapp-aos-qe-ci--runtime-int.apps.int.gpc.ocp-hub.prod.psi.redhat.com"

        for case_id in sorted(results.keys()):
            high_failure_days = len(results[case_id])
            link = f"{base_url}/prow_test_cases/{case_id}"

            for day_data in sorted(results[case_id], key=lambda x: x['date']):
                lines.append(f"| {case_id} | {query['subteam']} | {high_failure_days} | {day_data['date']} | {day_data['failure_rate']}% | [View]({link}) |")

        return "\n".join(lines)

    else:  # text format
        report = []
        report.append("=" * 80)
        report.append("Daily Failure Rates Report")
        report.append("=" * 80)
        report.append(f"Query Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
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
        print("Usage: query_daily_failure_rates.py <subteam> <failure_threshold> <start_date> <end_date> [output_format]")
        sys.exit(1)

    subteam = sys.argv[1]
    failure_threshold = sys.argv[2]
    start_date = sys.argv[3]
    end_date = sys.argv[4]
    output_format = sys.argv[5] if len(sys.argv) > 5 else 'text'

    # Query the webapp
    data = query_qe_webapp(subteam, failure_threshold, start_date, end_date)

    if not data:
        print("Failed to retrieve data")
        sys.exit(1)

    # Generate and print report
    report = generate_report(data, output_format)
    print(report)

if __name__ == '__main__':
    main()
