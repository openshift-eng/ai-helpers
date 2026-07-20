#!/usr/bin/env python3
"""Fetch test results for a pull request from the Sippy API.

Returns test results from presubmit job runs for a specific PR, including
test name, status, output, job info, and SHA.
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

SIPPY_API_BASE = "http://localhost:8080/api"


def fetch_pr_test_results(org, repo, pr_number, sha=None,
                          include_successes=None, latest_sha_only=False):
    """Fetch test results for a PR from the Sippy API."""
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=14)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    params = {
        "org": org,
        "repo": repo,
        "pr_number": str(pr_number),
        "start_date": start_date,
        "end_date": end_date,
    }

    if sha:
        params["sha"] = sha
    if latest_sha_only:
        params["latest_sha_only"] = "true"

    query_parts = list(urllib.parse.urlencode(params).split("&"))
    if include_successes:
        for pattern in include_successes:
            query_parts.append(
                urllib.parse.urlencode({"include_successes": pattern})
            )
    query_string = "&".join(query_parts)

    url = f"{SIPPY_API_BASE}/pull_requests/test_results?{query_string}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
            err_data = json.loads(body)
            body = err_data.get("message", body)
        except Exception:
            pass
        return {
            "success": False,
            "error": f"HTTP {e.code}: {body or e.reason}",
            "api_url": url,
        }
    except urllib.error.URLError as e:
        return {
            "success": False,
            "error": f"Failed to connect to Sippy API: {e.reason}",
            "api_url": url,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "api_url": url,
        }

    if isinstance(data, dict) and "code" in data:
        return {
            "success": False,
            "error": data.get("message", "Unknown API error"),
            "api_url": url,
        }

    return {
        "success": True,
        "org": org,
        "repo": repo,
        "pr_number": pr_number,
        "sha": sha,
        "total_results": len(data),
        "results": data,
        "api_url": url,
    }


def format_summary(result):
    """Format results as a human-readable summary."""
    if not result["success"]:
        lines = [
            "PR Test Results - FETCH FAILED",
            "=" * 60,
            "",
            f"Error: {result['error']}",
        ]
        return "\n".join(lines)

    lines = [
        "PR Test Results",
        "=" * 60,
        "",
        f"PR: {result['org']}/{result['repo']}#{result['pr_number']}",
    ]
    if result.get("sha"):
        lines.append(f"SHA: {result['sha']}")
    lines.append(f"Total Results: {result['total_results']}")
    lines.append("")

    results = result["results"]
    if not results:
        lines.append("No test results found.")
        return "\n".join(lines)

    by_job = {}
    for r in results:
        job_key = (r["prow_job_run_id"], r["prow_job_name"])
        by_job.setdefault(job_key, []).append(r)

    shas = sorted(set(r.get("pr_sha", "") for r in results if r.get("pr_sha")))
    if shas:
        lines.append(f"SHAs: {', '.join(shas)}")
        lines.append("")

    status_counts = {}
    for r in results:
        s = r.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1
    lines.append("Status Breakdown:")
    for s, c in sorted(status_counts.items()):
        lines.append(f"  {s}: {c}")
    lines.append("")

    lines.append(f"Job Runs: {len(by_job)}")
    lines.append("")

    for i, ((_run_id, job_name), tests) in enumerate(
        sorted(by_job.items(), key=lambda x: x[1][0].get("prow_job_start", ""),
               reverse=True)
    ):
        if i >= 10:
            lines.append(f"... and {len(by_job) - 10} more job runs")
            break
        failures = [t for t in tests if t.get("status") == "failure"]
        lines.append(f"  {job_name}")
        lines.append(f"    URL: {tests[0].get('prow_job_url', 'N/A')}")
        lines.append(f"    SHA: {tests[0].get('pr_sha', 'N/A')}")
        lines.append(f"    Started: {tests[0].get('prow_job_start', 'N/A')}")
        lines.append(f"    Tests: {len(tests)} ({len(failures)} failures)")
        if failures:
            for f in failures[:5]:
                lines.append(f"      FAIL: {f['test_name']}")
            if len(failures) > 5:
                lines.append(f"      ... and {len(failures) - 5} more failures")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch test results for a pull request from the Sippy API.",
    )
    parser.add_argument(
        "pr_url_or_number",
        help="GitHub PR URL (e.g. https://github.com/openshift/kubernetes/pull/2653) "
             "or just the PR number (requires --org and --repo)",
    )
    parser.add_argument(
        "--org",
        default=None,
        help="GitHub org (default: openshift). Extracted from URL if PR URL is provided.",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="GitHub repo. Extracted from URL if PR URL is provided.",
    )
    parser.add_argument(
        "--sha",
        default=None,
        help="Filter to a specific commit SHA",
    )
    parser.add_argument(
        "--latest-sha",
        action="store_true",
        default=False,
        help="Only return results for the most recent PR SHA",
    )
    parser.add_argument(
        "--include-successes",
        action="append",
        default=None,
        help="Include successes/flakes for tests matching this substring "
             "(repeatable). By default only failures are returned.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write output to a file instead of stdout",
    )

    args = parser.parse_args()

    pr_input = args.pr_url_or_number
    org = args.org
    repo = args.repo
    pr_number = None

    if pr_input.startswith("http"):
        parts = pr_input.rstrip("/").split("/")
        try:
            idx = parts.index("pull")
            org = parts[idx - 2]
            repo = parts[idx - 1]
            pr_number = int(parts[idx + 1])
        except (ValueError, IndexError):
            print(f"Error: Could not parse PR URL: {pr_input}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            pr_number = int(pr_input)
        except ValueError:
            print(f"Error: Invalid PR number: {pr_input}", file=sys.stderr)
            sys.exit(1)

    if org is None:
        org = "openshift"
    if repo is None:
        print("Error: --repo is required when passing a PR number instead of a URL",
              file=sys.stderr)
        sys.exit(1)

    result = fetch_pr_test_results(
        org=org,
        repo=repo,
        pr_number=pr_number,
        sha=args.sha,
        include_successes=args.include_successes,
        latest_sha_only=args.latest_sha,
    )

    if args.format == "json":
        output_text = json.dumps(result, indent=2)
    else:
        output_text = format_summary(result)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output_text)
        print(f"Output written to {args.output} "
              f"({result.get('total_results', 0)} results)",
              file=sys.stderr)
    else:
        print(output_text)

    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
