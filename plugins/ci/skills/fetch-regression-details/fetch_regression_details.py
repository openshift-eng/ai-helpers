#!/usr/bin/env python3
"""
Fetch detailed regression information from the Sippy Component Readiness API.
Retrieves test name, affected variants, release information, triage status, and metadata.
"""

import sys
import json
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Any
from datetime import datetime


class RegressionFetcher:
    """Fetches and parses regression data from Sippy API."""

    BASE_URL = "https://sippy.dptools.openshift.org/api/component_readiness/regressions"

    def __init__(self, regression_id: int):
        """
        Initialize fetcher with regression ID.

        Args:
            regression_id: Integer ID of the regression to fetch
        """
        self.regression_id = regression_id
        self.api_url = f"{self.BASE_URL}/{regression_id}"

    def fetch_raw_data(self) -> Dict[str, Any]:
        """
        Fetch raw regression data from API.

        Returns:
            dict: Raw JSON response from API

        Raises:
            ValueError: If regression not found or API error occurs
            urllib.error.URLError: If network connection fails
        """
        try:
            with urllib.request.urlopen(self.api_url) as response:
                data = json.loads(response.read().decode('utf-8'))

                # Check for API error in response
                if 'error' in data:
                    raise ValueError(f"API error: {data['error']}")

                return data

        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ValueError(
                    f"Regression ID {self.regression_id} not found.\n"
                    f"Verify the regression ID exists in Component Readiness."
                )
            else:
                raise ValueError(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise ValueError(
                f"Failed to connect to Sippy API: {e.reason}\n"
                f"Check network connectivity and VPN settings."
            )

    def parse_regression(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse raw API response into structured regression data.

        Args:
            raw_data: Raw JSON response from API

        Returns:
            dict: Structured regression data with parsed fields
        """
        # Extract basic fields
        regression = {
            'regression_id': raw_data.get('id'),
            'test_name': raw_data.get('test_name', ''),
            'test_id': raw_data.get('test_id', ''),
            'release': raw_data.get('release', ''),
            'base_release': raw_data.get('base_release', ''),
            'component': raw_data.get('component', ''),
            'capability': raw_data.get('capability', ''),
            'view': raw_data.get('view', ''),
        }

        # Parse dates
        regression['opened'] = raw_data.get('opened', '')

        # Parse closed status
        closed_obj = raw_data.get('closed', {})
        if isinstance(closed_obj, dict) and closed_obj.get('Valid'):
            regression['closed'] = closed_obj.get('Time', '')
            regression['status'] = 'closed'
        else:
            regression['closed'] = None
            regression['status'] = 'open'

        # Parse last failure
        last_failure_obj = raw_data.get('last_failure', {})
        if isinstance(last_failure_obj, dict) and last_failure_obj.get('Valid'):
            regression['last_failure'] = last_failure_obj.get('Time', '')
        else:
            regression['last_failure'] = None

        # Parse variants
        regression['variants'] = sorted(raw_data.get('variants', []))

        # Parse max failures
        regression['max_failures'] = raw_data.get('max_failures', 0)

        # Parse triages
        regression['triages'] = self._parse_triages(raw_data.get('triages', []))

        # Parse job_runs (all job runs where the failure was observed throughout the regression's life)
        regression['job_runs'] = self._parse_job_runs(raw_data.get('job_runs', []))

        # Parse links
        links = raw_data.get('links', {})
        regression['test_details_url'] = links.get('test_details', '')
        regression['api_url'] = links.get('self', self.api_url)

        return regression

    def _parse_triages(self, triages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse triage entries from API response.

        Args:
            triages: List of triage objects from API

        Returns:
            list: Parsed triage entries with JIRA keys extracted
        """
        parsed_triages = []

        for triage in triages:
            url = triage.get('url', '')

            # Extract JIRA key from URL (e.g., OCPBUGS-74651)
            jira_key = ''
            if url and 'browse/' in url:
                jira_key = url.split('browse/')[-1]

            # Parse resolved status
            resolved_obj = triage.get('resolved', {})
            resolved = isinstance(resolved_obj, dict) and resolved_obj.get('Valid', False)

            parsed_triages.append({
                'id': triage.get('id'),
                'url': url,
                'jira_key': jira_key,
                'type': triage.get('type', ''),
                'description': triage.get('description', ''),
                'bug_id': triage.get('bug_id'),
                'resolved': resolved,
                'created_at': triage.get('created_at', ''),
                'updated_at': triage.get('updated_at', ''),
            })

        return parsed_triages

    def _parse_job_runs(self, job_runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse job_runs array from the regression API response.

        Each entry represents a job run where the test failure was observed
        throughout the entire life of the regression.

        Args:
            job_runs: List of job run objects from the API

        Returns:
            list: Parsed job run entries sorted by start_time (newest first)
        """
        parsed = []
        for run in job_runs:
            parsed.append({
                'id': run.get('id'),
                'regression_id': run.get('regression_id'),
                'prowjob_run_id': run.get('prowjob_run_id', ''),
                'prowjob_name': run.get('prowjob_name', ''),
                'prowjob_url': run.get('prowjob_url', ''),
                'start_time': run.get('start_time', ''),
                'test_failures': run.get('test_failures', 0),
            })
        parsed.sort(key=lambda x: x['start_time'], reverse=True)
        return parsed

    def fetch_test_details(self, test_details_url: str) -> Dict[str, Any]:
        """
        Fetch test details report from test_details_url.

        Args:
            test_details_url: URL to test details API endpoint

        Returns:
            dict: Raw JSON response from test details API

        Raises:
            ValueError: If fetch fails or API error occurs
        """
        try:
            with urllib.request.urlopen(test_details_url) as response:
                data = json.loads(response.read().decode('utf-8'))

                # Check for API error in response
                if 'error' in data:
                    raise ValueError(f"Test details API error: {data['error']}")

                return data

        except urllib.error.HTTPError as e:
            raise ValueError(f"HTTP error fetching test details: {e.code} {e.reason}")
        except urllib.error.URLError as e:
            raise ValueError(f"Failed to fetch test details: {e.reason}")

    def parse_analyses_metadata(self, test_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse analysis metadata from test details response.

        Extracts status and explanations from analyses[0].

        Args:
            test_details: Raw JSON response from test details API

        Returns:
            dict: Dictionary containing status and explanations (empty dict if not found)
        """
        analyses = test_details.get('analyses', [])
        if not analyses:
            return {}

        analysis = analyses[0]
        return {
            'status': analysis.get('status'),
            'explanations': analysis.get('explanations', [])
        }

    def parse_failed_jobs_by_job(self, test_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse sample job runs grouped by job name.

        Extracts all job runs from sample_job_run_stats and groups them by job name.
        For each job, includes the pass/fail sequence and list of failed runs.

        Args:
            test_details: Raw JSON response from test details API

        Returns:
            dict: Dictionary keyed by job name, each containing pass_sequence and failed_runs
        """
        jobs_by_name = {}

        # Navigate to analyses[0].job_stats
        analyses = test_details.get('analyses', [])
        if not analyses:
            return jobs_by_name

        job_stats = analyses[0].get('job_stats', [])

        for job_stat in job_stats:
            sample_job_name = job_stat.get('sample_job_name', '')
            sample_job_run_stats = job_stat.get('sample_job_run_stats', [])

            # Collect all runs for this job
            all_runs = []
            failed_runs = []

            for run_stat in sample_job_run_stats:
                test_stats = run_stat.get('test_stats', {})
                success_count = test_stats.get('success_count', 0)
                failure_count = test_stats.get('failure_count', 0)
                start_time = run_stat.get('start_time', '')

                # Track all runs for pass sequence
                all_runs.append({
                    'start_time': start_time,
                    'success_count': success_count,
                    'failure_count': failure_count,
                })

                # Track failed runs
                if failure_count > 0:
                    failed_runs.append({
                        'job_url': run_stat.get('job_url', ''),
                        'job_run_id': run_stat.get('job_run_id', ''),
                        'start_time': start_time,
                        'test_failures': run_stat.get('test_failures', 0),
                        'job_labels': run_stat.get('job_labels', []),
                    })

            # Sort runs by start_time (newest first)
            all_runs.sort(key=lambda x: x['start_time'], reverse=True)
            failed_runs.sort(key=lambda x: x['start_time'], reverse=True)

            # Build pass sequence for this job
            sequence = ""
            for run in all_runs:
                if run['success_count'] > 0:
                    sequence += "S"
                elif run['failure_count'] > 0:
                    sequence += "F"

            # Only include jobs that have at least one failed run
            if failed_runs:
                # Aggregate job_labels across failed runs: label -> count of runs with that label
                label_counts = {}
                for run in failed_runs:
                    for label in run.get('job_labels', []):
                        label_counts[label] = label_counts.get(label, 0) + 1

                jobs_by_name[sample_job_name] = {
                    'pass_sequence': sequence,
                    'failed_runs': failed_runs,
                    'label_summary': label_counts,
                }

        return jobs_by_name

    def fetch_and_parse(self) -> Dict[str, Any]:
        """
        Fetch and parse regression data in one call.

        Returns:
            dict: Structured regression data with sample failed jobs grouped by job name

        Raises:
            ValueError: If fetch or parse fails
        """
        raw_data = self.fetch_raw_data()
        regression = self.parse_regression(raw_data)

        # Fetch sample failed jobs and analysis metadata from test details
        test_details_url = regression.get('test_details_url', '')
        if test_details_url:
            try:
                test_details = self.fetch_test_details(test_details_url)
                regression['sample_failed_jobs'] = self.parse_failed_jobs_by_job(test_details)

                # Extract analysis metadata (status and explanations)
                analysis_metadata = self.parse_analyses_metadata(test_details)
                if analysis_metadata:
                    regression['analysis_status'] = analysis_metadata.get('status')
                    regression['analysis_explanations'] = analysis_metadata.get('explanations', [])
            except ValueError as e:
                # Don't fail entire request if test details fetch fails
                regression['sample_failed_jobs'] = {}
                regression['sample_failed_jobs_error'] = str(e)
        else:
            regression['sample_failed_jobs'] = {}

        return regression


def format_summary(regression: Dict[str, Any]) -> str:
    """
    Format regression data as a human-readable summary.

    Args:
        regression: Parsed regression data

    Returns:
        str: Formatted summary text
    """
    lines = []
    lines.append(f"Regression #{regression['regression_id']} Details:")
    lines.append("=" * 60)
    lines.append("")

    # Basic info
    lines.append(f"Test Name: {regression['test_name']}")
    lines.append(f"Release: {regression['release']} (baseline: {regression['base_release']})")
    lines.append(f"Component: {regression['component']}")
    if regression['capability']:
        lines.append(f"Capability: {regression['capability']}")
    lines.append("")

    # Status
    opened_date = regression['opened'].split('T')[0] if regression['opened'] else 'unknown'
    status_line = f"Status: {regression['status'].title()} (opened: {opened_date}"
    if regression['closed']:
        closed_date = regression['closed'].split('T')[0]
        status_line += f", closed: {closed_date}"
    status_line += ")"
    lines.append(status_line)

    if regression['last_failure']:
        last_failure_date = regression['last_failure'].split('T')[0]
        lines.append(f"Last Failure: {last_failure_date}")

    lines.append(f"Max Failures: {regression['max_failures']}")
    lines.append("")

    # Analysis metadata
    if 'analysis_status' in regression and regression['analysis_status'] is not None:
        lines.append(f"Analysis Status: {regression['analysis_status']}")
        if regression['analysis_status'] < 0:
            lines.append("  (Negative status indicates a problem - lower is more severe)")

    if 'analysis_explanations' in regression and regression['analysis_explanations']:
        lines.append("Analysis Explanations:")
        for explanation in regression['analysis_explanations']:
            lines.append(f"  - {explanation}")
        lines.append("")

    # Variants
    if regression['variants']:
        lines.append("Affected Variants:")
        for variant in regression['variants']:
            lines.append(f"  - {variant}")
        lines.append("")

    # Triages
    if regression['triages']:
        lines.append("Triages:")
        for triage in regression['triages']:
            status = "resolved" if triage['resolved'] else "active"
            jira_info = triage['jira_key'] if triage['jira_key'] else triage['url']
            desc = f": {triage['description']}" if triage['description'] else ""
            lines.append(f"  - {jira_info} ({triage['type']}, {status}){desc}")
        lines.append("")
    else:
        lines.append("Triages: None - needs investigation")
        lines.append("")

    # Sample Failed Jobs (grouped by job name)
    if 'sample_failed_jobs' in regression:
        if regression.get('sample_failed_jobs_error'):
            lines.append(f"Sample Failed Jobs: Error fetching - {regression['sample_failed_jobs_error']}")
            lines.append("")
        elif regression['sample_failed_jobs']:
            total_failed_runs = sum(len(job_data['failed_runs']) for job_data in regression['sample_failed_jobs'].values())
            lines.append(f"Sample Failed Jobs ({len(regression['sample_failed_jobs'])} jobs, {total_failed_runs} failed runs):")
            lines.append("")

            for job_name, job_data in regression['sample_failed_jobs'].items():
                job_name_short = job_name.split('/')[-1] if '/' in job_name else job_name
                lines.append(f"  {job_name_short}:")
                lines.append(f"    Pass Sequence (newest to oldest): {job_data['pass_sequence']}")

                # Show label summary if any labels are present
                label_summary = job_data.get('label_summary', {})
                if label_summary:
                    total_failed = len(job_data['failed_runs'])
                    label_parts = [f"{label} ({count}/{total_failed} runs)" for label, count in sorted(label_summary.items(), key=lambda x: -x[1])]
                    lines.append(f"    Symptom Labels: {', '.join(label_parts)}")

                lines.append(f"    Failed Runs ({len(job_data['failed_runs'])}):")
                for run in job_data['failed_runs']:
                    start_date = run['start_time'].split('T')[0] if 'T' in run['start_time'] else run['start_time']
                    test_failures = run.get('test_failures', 0)
                    mass_failure_note = f" [MASS FAILURE: {test_failures} total test failures]" if test_failures > 10 else ""
                    labels = run.get('job_labels', [])
                    label_note = f" [{', '.join(labels)}]" if labels else ""
                    lines.append(f"      - Run ID: {run['job_run_id']}, Started: {start_date}{mass_failure_note}{label_note}")
                    lines.append(f"        URL: {run['job_url']}")
                lines.append("")
        else:
            lines.append("Sample Failed Jobs: None found")
            lines.append("")

    # Job Runs (full history across regression lifetime)
    job_runs = regression.get('job_runs', [])
    if job_runs:
        lines.append(f"Job Runs ({len(job_runs)} total across regression lifetime):")
        high_failure_count = sum(1 for r in job_runs if r.get('test_failures', 0) > 10)
        if high_failure_count:
            lines.append(f"  Runs with mass failures (>10 test failures): {high_failure_count}/{len(job_runs)}")
        if job_runs:
            oldest = job_runs[-1]
            newest = job_runs[0]
            oldest_date = oldest['start_time'].split('T')[0] if 'T' in oldest['start_time'] else oldest['start_time']
            newest_date = newest['start_time'].split('T')[0] if 'T' in newest['start_time'] else newest['start_time']
            lines.append(f"  Date range: {oldest_date} to {newest_date}")
        lines.append("")

    # Links
    if regression['test_details_url']:
        lines.append(f"Test Details: {regression['test_details_url']}")
    if regression['api_url']:
        lines.append(f"API URL: {regression['api_url']}")

    return "\n".join(lines)


def main():
    """Fetch regression details from command line and output results."""
    if len(sys.argv) < 2:
        print("Usage: fetch_regression_details.py <regression_id> [--format json|summary]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  fetch_regression_details.py 34446", file=sys.stderr)
        print("  fetch_regression_details.py 34446 --format json", file=sys.stderr)
        print("  fetch_regression_details.py 34446 --format summary", file=sys.stderr)
        sys.exit(1)

    # Parse arguments
    try:
        regression_id = int(sys.argv[1])
    except ValueError:
        print(f"Error: Regression ID must be a positive integer, got '{sys.argv[1]}'", file=sys.stderr)
        sys.exit(1)

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

    # Fetch and parse regression
    try:
        fetcher = RegressionFetcher(regression_id)
        regression = fetcher.fetch_and_parse()

        # Output in requested format
        if output_format == 'json':
            print(json.dumps(regression, indent=2))
        else:
            print(format_summary(regression))

        return 0

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
