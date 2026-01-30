#!/usr/bin/env python3
"""
Fetch test failure outputs from Sippy API.
Returns raw outputs for AI-based interpretation and similarity analysis.
"""

import sys
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any


class TestOutputFetcher:
    """Fetches test failure outputs from Sippy API."""

    # TEMPORARY: Using localhost endpoint for development
    # TODO: Switch to production endpoint once code merges
    # BASE_URL = "https://sippy.dptools.openshift.org/api/tests/v2/outputs"
    BASE_URL = "http://127.0.0.1:8080/api/tests/v2/outputs"

    def __init__(self, test_id: str, job_run_ids: List[str]):
        """
        Initialize fetcher with test ID and job run IDs.

        Args:
            test_id: Test identifier (e.g., "openshift-tests:71c053c318c11cfc47717b9cf711c326")
            job_run_ids: List of Prow job run IDs to fetch outputs for
        """
        self.test_id = test_id
        self.job_run_ids = job_run_ids
        self.api_url = f"{self.BASE_URL}?test_id={test_id}&prow_job_run_ids={','.join(job_run_ids)}"

    def fetch_outputs(self) -> Dict[str, Any]:
        """
        Fetch test outputs from API.

        Returns:
            dict: Response object with success status and outputs or error

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
                        'requested_job_runs': len(self.job_run_ids),
                    }

                # Return successful response with outputs
                return {
                    'success': True,
                    'test_id': self.test_id,
                    'requested_job_runs': len(self.job_run_ids),
                    'outputs': data,
                }

        except urllib.error.HTTPError as e:
            return {
                'success': False,
                'error': f"HTTP error {e.code}: {e.reason}",
                'test_id': self.test_id,
                'requested_job_runs': len(self.job_run_ids),
            }
        except urllib.error.URLError as e:
            return {
                'success': False,
                'error': f"Failed to connect to test outputs API: {e.reason}. Ensure localhost:8080 is running or production endpoint is available.",
                'test_id': self.test_id,
                'requested_job_runs': len(self.job_run_ids),
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'test_id': self.test_id,
                'requested_job_runs': len(self.job_run_ids),
            }


def format_summary(results: Dict[str, Any]) -> str:
    """
    Format results as a human-readable summary.

    Args:
        results: Results from fetch_outputs()

    Returns:
        str: Formatted summary text
    """
    lines = []

    if not results.get('success'):
        lines.append("Test Failure Outputs - FETCH FAILED")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Error: {results.get('error', 'Unknown error')}")
        lines.append("")
        lines.append("The test output API may not be available.")
        lines.append("TEMPORARY: Ensure localhost:8080 endpoint is running.")
        return "\n".join(lines)

    lines.append("Test Failure Outputs")
    lines.append("=" * 60)
    lines.append("")

    outputs = results.get('outputs', [])
    lines.append(f"Test ID: {results.get('test_id', 'N/A')}")
    lines.append(f"Requested Job Runs: {results.get('requested_job_runs', 0)}")
    lines.append(f"Outputs Fetched: {len(outputs)}")
    lines.append("")

    if not outputs:
        lines.append("No test outputs returned from API.")
        return "\n".join(lines)

    # Show first few outputs
    lines.append("Sample Outputs:")
    for i, output in enumerate(outputs[:3], 1):
        lines.append(f"\n{i}. Job URL: {output.get('url', 'N/A')}")
        output_text = output.get('output', '')
        preview = output_text[:200]
        if len(output_text) > 200:
            preview += "..."
        lines.append(f"   Output: {preview}")

    if len(outputs) > 3:
        lines.append(f"\n... and {len(outputs) - 3} more outputs")

    return "\n".join(lines)


def main():
    """Fetch test failure outputs from command line."""
    if len(sys.argv) < 3:
        print("Usage: fetch_test_failure_outputs.py <test_id> <job_run_id1,job_run_id2,...> [--format json|summary]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  fetch_test_failure_outputs.py 'openshift-tests:abc123' '12345,67890'", file=sys.stderr)
        print("  fetch_test_failure_outputs.py 'openshift-tests:abc123' '12345,67890' --format json", file=sys.stderr)
        print("  fetch_test_failure_outputs.py 'openshift-tests:abc123' '12345,67890' --format summary", file=sys.stderr)
        sys.exit(1)

    # Parse arguments
    test_id = sys.argv[1]
    job_run_ids = sys.argv[2].split(',')

    # Parse optional arguments
    output_format = 'json'

    # Check for --format flag
    for i, arg in enumerate(sys.argv):
        if arg == '--format' and i + 1 < len(sys.argv):
            output_format = sys.argv[i + 1]
            if output_format not in ('json', 'summary'):
                print(f"Error: Invalid format '{output_format}'. Use 'json' or 'summary'", file=sys.stderr)
                sys.exit(1)
            break

    # Fetch outputs
    try:
        fetcher = TestOutputFetcher(test_id, job_run_ids)
        results = fetcher.fetch_outputs()

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
