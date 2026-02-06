#!/usr/bin/env python3
"""
Fetch test runs from Sippy API.
Returns test run data including outputs for AI-based interpretation and similarity analysis.
Can optionally include successful runs in addition to failures.
"""

import sys
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


class TestRunsFetcher:
    """Fetches test runs from Sippy API."""

    # TODO: Change to production URL once API is live
    BASE_URL = "http://127.0.0.1:8080/api/tests/v2/runs"

    def __init__(self, test_id: str, job_run_ids: Optional[List[str]] = None,
                 include_success: bool = False, prowjob_name: Optional[str] = None,
                 start_days_ago: Optional[int] = None):
        """
        Initialize fetcher with test ID and optional parameters.

        Args:
            test_id: Test identifier (e.g., "openshift-tests:71c053c318c11cfc47717b9cf711c326")
            job_run_ids: Optional list of Prow job run IDs to filter by
            include_success: If True, include successful test runs (default: False)
            prowjob_name: Optional Prow job name to filter results to a specific job
            start_days_ago: Optional number of days to look back (default API is 7 days)
        """
        self.test_id = test_id
        self.job_run_ids = job_run_ids
        self.include_success = include_success
        self.prowjob_name = prowjob_name
        self.start_days_ago = start_days_ago
        # Calculate start_date from start_days_ago
        if start_days_ago is not None:
            self.start_date = (datetime.now() - timedelta(days=start_days_ago)).strftime('%Y-%m-%d')
        else:
            self.start_date = None
        self.api_url = self._build_url()

    def _build_url(self) -> str:
        """Build the API URL with query parameters."""
        url = f"{self.BASE_URL}?test_id={self.test_id}"

        if self.job_run_ids:
            url += f"&prow_job_run_ids={','.join(self.job_run_ids)}"

        if self.include_success:
            url += "&include_success=true"

        if self.prowjob_name:
            # URL encode the job name in case it contains special characters
            encoded_name = urllib.parse.quote(self.prowjob_name, safe='')
            url += f"&prowjob_name={encoded_name}"

        if self.start_date:
            url += f"&start_date={self.start_date}"

        return url

    def fetch_runs(self) -> Dict[str, Any]:
        """
        Fetch test runs from API.

        Returns:
            dict: Response object with success status and runs or error

        """
        try:
            with urllib.request.urlopen(self.api_url, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))

                # Check for API error in response
                if isinstance(data, dict) and 'error' in data:
                    return {
                        'success': False,
                        'error': f"API error: {data['error']}",
                        'test_id': self.test_id,
                        'requested_job_runs': len(self.job_run_ids) if self.job_run_ids else 0,
                        'include_success': self.include_success,
                        'prowjob_name': self.prowjob_name,
                        'start_days_ago': self.start_days_ago,
                        'start_date': self.start_date,
                    }

                # Return successful response with runs
                return {
                    'success': True,
                    'test_id': self.test_id,
                    'requested_job_runs': len(self.job_run_ids) if self.job_run_ids else 0,
                    'include_success': self.include_success,
                    'prowjob_name': self.prowjob_name,
                    'start_days_ago': self.start_days_ago,
                    'start_date': self.start_date,
                    'runs': data,
                    'api_url': self.api_url,
                }

        except urllib.error.HTTPError as e:
            return {
                'success': False,
                'error': f"HTTP error {e.code}: {e.reason}",
                'test_id': self.test_id,
                'requested_job_runs': len(self.job_run_ids) if self.job_run_ids else 0,
                'include_success': self.include_success,
                'prowjob_name': self.prowjob_name,
                'start_days_ago': self.start_days_ago,
                'start_date': self.start_date,
            }
        except urllib.error.URLError as e:
            return {
                'success': False,
                'error': f"Failed to connect to test runs API: {e.reason}. Ensure localhost:8080 is running or production endpoint is available.",
                'test_id': self.test_id,
                'requested_job_runs': len(self.job_run_ids) if self.job_run_ids else 0,
                'include_success': self.include_success,
                'prowjob_name': self.prowjob_name,
                'start_days_ago': self.start_days_ago,
                'start_date': self.start_date,
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'test_id': self.test_id,
                'requested_job_runs': len(self.job_run_ids) if self.job_run_ids else 0,
                'include_success': self.include_success,
                'prowjob_name': self.prowjob_name,
                'start_days_ago': self.start_days_ago,
                'start_date': self.start_date,
            }


def format_summary(results: Dict[str, Any]) -> str:
    """
    Format results as a human-readable summary.

    Args:
        results: Results from fetch_runs()

    Returns:
        str: Formatted summary text
    """
    lines = []

    if not results.get('success'):
        lines.append("Test Runs - FETCH FAILED")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Error: {results.get('error', 'Unknown error')}")
        lines.append("")
        lines.append("The test runs API may not be available.")
        return "\n".join(lines)

    lines.append("Test Runs")
    lines.append("=" * 60)
    lines.append("")

    runs = results.get('runs', [])
    lines.append(f"Test ID: {results.get('test_id', 'N/A')}")
    if results.get('prowjob_name'):
        lines.append(f"Prow Job: {results.get('prowjob_name')}")
    if results.get('requested_job_runs', 0) > 0:
        lines.append(f"Requested Job Runs: {results.get('requested_job_runs', 0)}")
    lines.append(f"Include Successes: {results.get('include_success', False)}")
    if results.get('start_days_ago'):
        lines.append(f"Start Days Ago: {results.get('start_days_ago')} (since {results.get('start_date')})")
    lines.append(f"Runs Fetched: {len(runs)}")
    lines.append("")

    if not runs:
        lines.append("No test runs returned from API.")
        return "\n".join(lines)

    # Count successes and failures
    success_count = sum(1 for r in runs if r.get('success', False))
    failure_count = len(runs) - success_count
    lines.append(f"Successes: {success_count}, Failures: {failure_count}")
    lines.append("")

    # Show first few runs
    lines.append("Sample Runs:")
    for i, run in enumerate(runs[:5], 1):
        status = "PASS" if run.get('success', False) else "FAIL"
        lines.append(f"\n{i}. [{status}] Job URL: {run.get('url', 'N/A')}")
        output_text = run.get('output', '')
        if output_text:
            preview = output_text[:200]
            if len(output_text) > 200:
                preview += "..."
            lines.append(f"   Output: {preview}")

    if len(runs) > 5:
        lines.append(f"\n... and {len(runs) - 5} more runs")

    return "\n".join(lines)


def main():
    """Fetch test runs from command line."""
    if len(sys.argv) < 2:
        print("Usage: fetch_test_runs.py <test_id> [job_run_ids] [options]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Arguments:", file=sys.stderr)
        print("  test_id       Test identifier (e.g., 'openshift-tests:abc123')", file=sys.stderr)
        print("  job_run_ids   Optional comma-separated list of Prow job run IDs", file=sys.stderr)
        print("", file=sys.stderr)
        print("Options:", file=sys.stderr)
        print("  --include-success          Include successful test runs (default: failures only)", file=sys.stderr)
        print("  --prowjob-name <name>      Filter to runs from a specific Prow job", file=sys.stderr)
        print("  --start-days-ago <days>    Number of days to look back (default API is 7 days)", file=sys.stderr)
        print("  --format json|summary      Output format (default: json)", file=sys.stderr)
        print("", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  # Fetch all test runs (failures only)", file=sys.stderr)
        print("  fetch_test_runs.py 'openshift-tests:abc123'", file=sys.stderr)
        print("", file=sys.stderr)
        print("  # Fetch all test runs including successes", file=sys.stderr)
        print("  fetch_test_runs.py 'openshift-tests:abc123' --include-success", file=sys.stderr)
        print("", file=sys.stderr)
        print("  # Fetch runs from a specific job including successes", file=sys.stderr)
        print("  fetch_test_runs.py 'openshift-tests:abc123' --include-success --prowjob-name 'periodic-ci-openshift-...'", file=sys.stderr)
        print("", file=sys.stderr)
        print("  # Fetch runs going back 28 days (for regression start analysis)", file=sys.stderr)
        print("  fetch_test_runs.py 'openshift-tests:abc123' --include-success --start-days-ago 28", file=sys.stderr)
        print("", file=sys.stderr)
        print("  # Fetch specific job runs (for backward compatibility with analyze-regression)", file=sys.stderr)
        print("  fetch_test_runs.py 'openshift-tests:abc123' '12345,67890'", file=sys.stderr)
        print("", file=sys.stderr)
        print("  # Fetch with summary format", file=sys.stderr)
        print("  fetch_test_runs.py 'openshift-tests:abc123' --format summary", file=sys.stderr)
        sys.exit(1)

    # Parse arguments
    test_id = sys.argv[1]
    job_run_ids = None
    include_success = False
    prowjob_name = None
    start_days_ago = None
    output_format = 'json'

    # Parse remaining arguments
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--include-success':
            include_success = True
            i += 1
        elif arg == '--prowjob-name' and i + 1 < len(sys.argv):
            prowjob_name = sys.argv[i + 1]
            i += 2
        elif arg == '--start-days-ago' and i + 1 < len(sys.argv):
            try:
                start_days_ago = int(sys.argv[i + 1])
            except ValueError:
                print(f"Error: --start-days-ago requires an integer value", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif arg == '--format' and i + 1 < len(sys.argv):
            output_format = sys.argv[i + 1]
            if output_format not in ('json', 'summary'):
                print(f"Error: Invalid format '{output_format}'. Use 'json' or 'summary'", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif not arg.startswith('--') and job_run_ids is None:
            # This is the job_run_ids argument
            job_run_ids = arg.split(',')
            i += 1
        else:
            i += 1

    # Fetch runs
    try:
        fetcher = TestRunsFetcher(test_id, job_run_ids, include_success, prowjob_name, start_days_ago)
        results = fetcher.fetch_runs()

        # Output in requested format
        if output_format == 'json':
            print(json.dumps(results, indent=2))
        else:
            print(format_summary(results))

        # Exit with appropriate code
        return 0 if results.get('success') else 1

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
