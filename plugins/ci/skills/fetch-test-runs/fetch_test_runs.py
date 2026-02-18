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

    BASE_URL = "https://sippy.dptools.openshift.org/api/tests/v2/runs"

    def __init__(self, test_id: str, job_run_ids: Optional[List[str]] = None,
                 include_success: bool = False, job_name_filters: Optional[List[str]] = None,
                 start_days_ago: Optional[int] = None, exclude_output: bool = False):
        """
        Initialize fetcher with test ID and optional parameters.

        Args:
            test_id: Test identifier (e.g., "openshift-tests:71c053c318c11cfc47717b9cf711c326")
            job_run_ids: Optional list of Prow job run IDs to filter by
            include_success: If True, include successful test runs (default: False)
            job_name_filters: Optional list of job name substrings. The API filters server-side
                using AND logic with case-insensitive substring matching. Each value must appear
                somewhere in the job name. Works with both full job names and partial substrings.
                E.g., ["gcp", "techpreview"] matches jobs containing both "gcp" and "techpreview".
            start_days_ago: Optional number of days to look back (default API is 7 days)
            exclude_output: If True, strip the 'output' field from each run to reduce response
                size. Useful when you only need pass/fail status (e.g., regression start analysis).
        """
        self.test_id = test_id
        self.job_run_ids = job_run_ids
        self.include_success = include_success
        self.job_name_filters = job_name_filters
        self.start_days_ago = start_days_ago
        self.exclude_output = exclude_output
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

        if self.job_name_filters:
            # Each filter is sent as a separate prowjob_name query parameter for
            # server-side substring filtering with AND logic
            for name in self.job_name_filters:
                encoded_name = urllib.parse.quote(name, safe='')
                url += f"&prowjob_name={encoded_name}"

        if self.start_date:
            url += f"&start_date={self.start_date}"

        return url

    def _error_response(self, error_msg: str) -> Dict[str, Any]:
        """Build a standard error response dict."""
        return {
            'success': False,
            'error': error_msg,
            'test_id': self.test_id,
            'requested_job_runs': len(self.job_run_ids) if self.job_run_ids else 0,
            'include_success': self.include_success,
            'job_name_filters': self.job_name_filters,
            'start_days_ago': self.start_days_ago,
            'start_date': self.start_date,
        }

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
                    return self._error_response(f"API error: {data['error']}")

                # Strip output field if requested to reduce response size
                runs = data
                if self.exclude_output and isinstance(runs, list):
                    runs = [
                        {k: v for k, v in run.items() if k != 'output'}
                        for run in runs
                    ]

                result = {
                    'success': True,
                    'test_id': self.test_id,
                    'requested_job_runs': len(self.job_run_ids) if self.job_run_ids else 0,
                    'include_success': self.include_success,
                    'job_name_filters': self.job_name_filters,
                    'start_days_ago': self.start_days_ago,
                    'start_date': self.start_date,
                    'runs': runs,
                    'api_url': self.api_url,
                }

                # Build pass sequence only when successes are included
                # (a sequence of all F's is not useful)
                if self.include_success:
                    sorted_runs = sorted(
                        runs,
                        key=lambda r: r.get('start_time', ''),
                        reverse=True,
                    )
                    result['pass_sequence'] = ''.join(
                        'S' if r.get('success') else 'F'
                        for r in sorted_runs
                    )

                return result

        except urllib.error.HTTPError as e:
            return self._error_response(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            return self._error_response(f"Failed to connect to test runs API: {e.reason}")
        except Exception as e:
            return self._error_response(f"Unexpected error: {str(e)}")


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
    if results.get('job_name_filters'):
        lines.append(f"Job Contains: {results.get('job_name_filters')}")
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

    # Pass sequence
    pass_sequence = results.get('pass_sequence', '')
    if pass_sequence:
        lines.append(f"Pass Sequence (newest->oldest): {pass_sequence}")
    lines.append("")

    # Count mass failure jobs (failed_tests > 10)
    mass_failure_count = sum(1 for r in runs if r.get('failed_tests', 0) > 10)
    if mass_failure_count > 0:
        lines.append(f"Mass Failure Runs (>10 test failures in job): {mass_failure_count} of {len(runs)}")
        lines.append("  ⚠ These runs had many other test failures — this test may be caught up in a larger issue.")
        lines.append("")

    # Show first few runs
    lines.append("Sample Runs:")
    for i, run in enumerate(runs[:5], 1):
        status = "PASS" if run.get('success', False) else "FAIL"
        failed_tests = run.get('failed_tests', 0)
        mass_flag = " [MASS FAILURE]" if failed_tests > 10 else ""
        lines.append(f"\n{i}. [{status}]{mass_flag} Job URL: {run.get('url', 'N/A')}")
        if failed_tests > 0:
            lines.append(f"   Failed Tests in Job: {failed_tests}")
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
        print("  --include-success              Include successful test runs (default: failures only)", file=sys.stderr)
        print("  --job-contains <substring>     Filter by job name substring (server-side, case-insensitive).", file=sys.stderr)
        print("                                 Repeat for AND logic: --job-contains gcp --job-contains techpreview", file=sys.stderr)
        print("                                 Also accepts full job names (substring of itself).", file=sys.stderr)
        print("  --start-days-ago <days>        Number of days to look back (default API is 7 days)", file=sys.stderr)
        print("  --exclude-output               Strip test output text from runs to reduce response size.", file=sys.stderr)
        print("                                 Useful when only pass/fail status is needed.", file=sys.stderr)
        print("  --output <path>                Write output to file instead of stdout.", file=sys.stderr)
        print("                                 Avoids stdout truncation for large result sets.", file=sys.stderr)
        print("  --format json|summary          Output format (default: json)", file=sys.stderr)
        print("", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  # Fetch all test runs (failures only)", file=sys.stderr)
        print("  fetch_test_runs.py 'openshift-tests:abc123'", file=sys.stderr)
        print("", file=sys.stderr)
        print("  # Fetch all test runs including successes", file=sys.stderr)
        print("  fetch_test_runs.py 'openshift-tests:abc123' --include-success", file=sys.stderr)
        print("", file=sys.stderr)
        print("  # Filter by exact job name (still works - it's a substring of itself)", file=sys.stderr)
        print("  fetch_test_runs.py 'openshift-tests:abc123' --job-contains 'periodic-ci-openshift-...'", file=sys.stderr)
        print("", file=sys.stderr)
        print("  # Filter by multiple substrings (AND logic, case-insensitive)", file=sys.stderr)
        print("  fetch_test_runs.py 'openshift-tests:abc123' --job-contains gcp --job-contains techpreview", file=sys.stderr)
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
    exclude_output = False
    job_name_filters = []
    start_days_ago = None
    output_format = 'json'
    output_path = None

    # Parse remaining arguments
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--include-success':
            include_success = True
            i += 1
        elif arg == '--exclude-output':
            exclude_output = True
            i += 1
        elif arg == '--job-contains' and i + 1 < len(sys.argv):
            job_name_filters.append(sys.argv[i + 1])
            i += 2
        elif arg == '--start-days-ago' and i + 1 < len(sys.argv):
            try:
                start_days_ago = int(sys.argv[i + 1])
            except ValueError:
                print("Error: --start-days-ago requires an integer value", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif arg == '--output' and i + 1 < len(sys.argv):
            output_path = sys.argv[i + 1]
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
        fetcher = TestRunsFetcher(test_id, job_run_ids, include_success,
                                  job_name_filters if job_name_filters else None,
                                  start_days_ago, exclude_output)
        results = fetcher.fetch_runs()

        # Format output
        if output_format == 'json':
            formatted = json.dumps(results, indent=2)
        else:
            formatted = format_summary(results)

        # Write to file or stdout
        if output_path:
            with open(output_path, 'w') as f:
                f.write(formatted)
                f.write('\n')
            run_count = len(results.get('runs', []))
            print(f"Wrote {run_count} runs to {output_path}", file=sys.stderr)
        else:
            print(formatted)

        # Exit with appropriate code
        return 0 if results.get('success') else 1

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
