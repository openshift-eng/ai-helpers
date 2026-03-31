#!/usr/bin/env python3
"""
Fetch a Prow job run summary from Sippy API.
Returns job metadata and all failed tests (excluding flakes),
with error messages and pattern analysis for AI consumption.
"""

import sys
import json
import re
import urllib.request
import urllib.error
from collections import defaultdict
from typing import Dict, Any, List, Tuple


class JobRunSummaryFetcher:
    """Fetches job run summary from Sippy API."""

    BASE_URL = "https://sippy.dptools.openshift.org/api/job/run/summary"

    def __init__(self, prow_job_run_id: str):
        self.prow_job_run_id = prow_job_run_id

    def fetch(self) -> Dict[str, Any]:
        url = f"{self.BASE_URL}?prow_job_run_id={self.prow_job_run_id}"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}: {e.reason}", "url": url}
        except urllib.error.URLError as e:
            return {"error": f"URL error: {e.reason}", "url": url}

    @staticmethod
    def extract_error_pattern(error_msg: str) -> str:
        """Extract a short canonical error pattern from an error message."""
        if not error_msg:
            return "unknown"
        # Remove UUIDs, timestamps, and specific identifiers
        cleaned = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '<uuid>', error_msg)
        cleaned = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\s]*', '<timestamp>', cleaned)
        # Truncate to first meaningful line
        first_line = cleaned.split('\n')[0].strip()
        if len(first_line) > 150:
            first_line = first_line[:150] + "..."
        return first_line

    def format_text(self, data: Dict[str, Any]) -> str:
        """Format job run summary as AI-readable text."""
        if "error" in data:
            return f"Error fetching job run summary: {data['error']}\nURL: {data.get('url', 'N/A')}"

        lines = []

        # Job metadata
        lines.append("## Job Run Summary")
        lines.append("")
        lines.append(f"- **Job**: {data.get('name', 'N/A')}")
        lines.append(f"- **Run ID**: {data.get('id', 'N/A')}")
        lines.append(f"- **Release**: {data.get('release', 'N/A')}")
        lines.append(f"- **Start Time**: {data.get('startTime', 'N/A')}")
        duration_s = data.get('durationSeconds', 0)
        lines.append(f"- **Duration**: {duration_s // 3600}h {(duration_s % 3600) // 60}m {duration_s % 60}s")
        lines.append(f"- **Result**: {data.get('overallResult', 'N/A')} ({data.get('reason', 'N/A')})")
        lines.append(f"- **Cluster**: {data.get('cluster', 'N/A')}")
        lines.append(f"- **Infrastructure Failure**: {data.get('infrastructureFailure', False)}")
        lines.append(f"- **URL**: {data.get('url', 'N/A')}")
        variants = data.get('variants', [])
        if variants:
            lines.append(f"- **Variants**: {', '.join(variants)}")
        lines.append("")

        # Test statistics
        test_count = data.get('testCount', 0)
        failure_count = data.get('testFailureCount', 0)
        pass_rate = ((test_count - failure_count) / test_count * 100) if test_count > 0 else 0
        lines.append("## Test Statistics")
        lines.append("")
        lines.append(f"- **Total Tests**: {test_count}")
        lines.append(f"- **Failures**: {failure_count}")
        lines.append(f"- **Pass Rate**: {pass_rate:.1f}%")
        lines.append("")

        # Failed tests
        test_failures = data.get('testFailures', {})
        if not test_failures:
            lines.append("No test failures recorded.")
            return "\n".join(lines)

        # Detect common error patterns across all failures
        error_patterns: Dict[str, int] = defaultdict(int)
        for test_name, error_msg in test_failures.items():
            pattern = self.extract_error_pattern(error_msg)
            error_patterns[pattern] += 1

        # Show dominant patterns (appearing in >5% of failures)
        threshold = max(2, len(test_failures) * 0.05)
        dominant = [(p, c) for p, c in error_patterns.items() if c >= threshold]
        if dominant:
            dominant.sort(key=lambda x: -x[1])
            lines.append("## Dominant Error Patterns")
            lines.append("")
            for pattern, count in dominant[:10]:
                pct = count / len(test_failures) * 100
                lines.append(f"- **{count}/{len(test_failures)} ({pct:.0f}%)**: {pattern}")
            lines.append("")

        # All failed tests sorted alphabetically
        lines.append(f"## Failed Tests ({len(test_failures)} total)")
        lines.append("")
        for test_name, error_msg in sorted(test_failures.items()):
            lines.append(f"- **{test_name}**")
            if error_msg:
                short_err = error_msg[:300]
                if len(error_msg) > 300:
                    short_err += "..."
                lines.append(f"  Error: {short_err}")
        lines.append("")

        return "\n".join(lines)

    def format_json(self, data: Dict[str, Any]) -> str:
        """Format job run summary as structured JSON."""
        if "error" in data:
            return json.dumps({"success": False, **data}, indent=2)

        test_failures = data.get('testFailures', {})

        # Error patterns
        error_patterns: Dict[str, int] = defaultdict(int)
        for error_msg in test_failures.values():
            pattern = self.extract_error_pattern(error_msg)
            error_patterns[pattern] += 1
        threshold = max(2, len(test_failures) * 0.05)
        dominant = {p: c for p, c in error_patterns.items() if c >= threshold}

        test_count = data.get('testCount', 0)
        failure_count = data.get('testFailureCount', 0)

        result = {
            "success": True,
            "job_name": data.get("name"),
            "job_run_id": str(data.get("id")),
            "release": data.get("release"),
            "start_time": data.get("startTime"),
            "duration_seconds": data.get("durationSeconds"),
            "overall_result": data.get("overallResult"),
            "reason": data.get("reason"),
            "infrastructure_failure": data.get("infrastructureFailure", False),
            "cluster": data.get("cluster"),
            "url": data.get("url"),
            "variants": data.get("variants", []),
            "test_count": test_count,
            "failure_count": failure_count,
            "pass_rate": round((test_count - failure_count) / test_count * 100, 1) if test_count > 0 else 0,
            "failed_tests": [
                {"test_name": name, "error": error}
                for name, error in sorted(test_failures.items())
            ],
            "dominant_error_patterns": [
                {"pattern": p, "count": c, "percentage": round(c / len(test_failures) * 100, 1)}
                for p, c in sorted(dominant.items(), key=lambda x: -x[1])
            ] if dominant else []
        }
        return json.dumps(result, indent=2)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Fetch a Prow job run summary from Sippy API"
    )
    parser.add_argument(
        "prow_job_run_id",
        help="Prow job run ID (e.g., 2030845545290928128)"
    )
    parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Output format (default: text)"
    )
    args = parser.parse_args()

    fetcher = JobRunSummaryFetcher(args.prow_job_run_id)
    data = fetcher.fetch()

    if args.format == "json":
        print(fetcher.format_json(data))
    else:
        print(fetcher.format_text(data))


if __name__ == "__main__":
    main()
