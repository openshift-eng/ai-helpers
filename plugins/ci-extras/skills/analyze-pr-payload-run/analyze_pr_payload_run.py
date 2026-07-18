#!/usr/bin/env python3
"""
Analyze a PR payload validation run from pr-payload-tests.ci.openshift.org.

Fetches the run page, extracts PR metadata and prow job URLs, then fetches
each job's prowjob.json from GCS for status. For failed jobs, optionally
queries the Sippy API for test failure details.
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime


GCSWEB_BASE = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com"
SIPPY_BASE_URL = "https://sippy.dptools.openshift.org/api/job/run/summary"

PROW_URL_PATTERN = re.compile(
    r"https://prow\.ci\.openshift\.org/view/gs/test-platform-results/logs/[^\"'<>\s\)\]\},;]+(?<![.])"
)
PROW_PATH_PATTERN = re.compile(r'/view/gs/(test-platform-results/logs/([^/]+)/([^/?#]+))/?(?:[?#].*)?$')
PR_URL_PATTERN = re.compile(r'https://github\.com/([^/]+/[^/]+)/pull/(\d+)')
PAYLOAD_URL_PATTERN = re.compile(
    r'https://pr-payload-tests\.ci\.openshift\.org/runs/ci/([a-f0-9-]+)', re.IGNORECASE
)


def extract_error_pattern(error_msg):
    if not error_msg:
        return "unknown"
    error_msg = str(error_msg)
    cleaned = re.sub(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        '<uuid>', error_msg,
    )
    cleaned = re.sub(
        r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\s]*',
        '<timestamp>', cleaned,
    )
    first_line = cleaned.split('\n')[0].strip()
    if len(first_line) > 150:
        first_line = first_line[:150] + "..."
    return first_line


def fetch_url(url, timeout=30):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def fetch_prowjob_json(gcs_path):
    url = f"{GCSWEB_BASE}/gcs/{gcs_path}/prowjob.json"
    try:
        body = fetch_url(url)
        result = json.loads(body)
        if not isinstance(result, dict):
            return {"error": f"unexpected JSON type: {type(result).__name__}"}
        return result
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"URL error: {e.reason}"}
    except Exception as e:
        return {"error": str(e) or "unknown error"}


def fetch_sippy_summary(run_id):
    url = f"{SIPPY_BASE_URL}?prow_job_run_id={run_id}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict):
                return data
            return None
    except Exception:
        return None


def parse_page(html):
    prow_urls = list(dict.fromkeys(PROW_URL_PATTERN.findall(html)))

    seen = set()
    jobs = []
    for prow_url in prow_urls:
        m = PROW_PATH_PATTERN.search(prow_url)
        if m:
            key = (m.group(2), m.group(3))
            if key not in seen:
                seen.add(key)
                jobs.append({
                    "job_name": m.group(2),
                    "prow_url": prow_url,
                    "run_id": m.group(3),
                    "gcs_path": m.group(1),
                })

    pr_match = PR_URL_PATTERN.search(html)
    pr_metadata = {}
    if pr_match:
        pr_metadata["repo"] = pr_match.group(1)
        pr_metadata["pr_number"] = pr_match.group(2)

    return {
        "jobs": jobs,
        "pr_metadata": pr_metadata,
        "all_jobs_finished": bool(re.search(r'\bAllJobsFinished\b', html)),
    }


def fetch_job_status(job):
    prowjob = fetch_prowjob_json(job["gcs_path"])
    if "error" in prowjob:
        return {**job, "prowjob": prowjob}

    status = prowjob.get("status") or {}
    start = status.get("startTime", "")
    end = status.get("completionTime", "")
    duration_s = None
    if start and end:
        try:
            t0 = datetime.fromisoformat(start.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(end.replace("Z", "+00:00"))
            duration_s = int((t1 - t0).total_seconds())
        except Exception:
            pass

    return {
        **job,
        "prowjob": {
            "state": status.get("state", "unknown"),
            "description": status.get("description", ""),
            "start_time": start,
            "completion_time": end,
            "duration_seconds": duration_s,
        },
    }


def fetch_all_statuses(jobs, max_workers=5):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_job = {
            executor.submit(fetch_job_status, job): job
            for job in jobs
        }
        for future in as_completed(future_to_job):
            try:
                results.append(future.result())
            except Exception as e:
                job = future_to_job[future]
                results.append({**job, "prowjob": {"error": str(e)}})
    results.sort(key=lambda x: x["job_name"])
    return results


def enrich_failed_jobs(jobs, max_workers=5):
    failed = [j for j in jobs if j.get("prowjob", {}).get("state") == "failure"]
    if not failed:
        return

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_job = {
            executor.submit(fetch_sippy_summary, job["run_id"]): job
            for job in failed
        }
        for future in as_completed(future_to_job):
            job = future_to_job[future]
            try:
                sippy = future.result()
                if sippy:
                    job["sippy"] = sippy
            except Exception:
                pass


def analyze_test_failures(test_failures):
    if not isinstance(test_failures, dict):
        return {"failed_tests": [], "dominant_error_patterns": [], "total": 0}
    error_patterns = defaultdict(int)
    for error_msg in test_failures.values():
        pattern = extract_error_pattern(error_msg)
        error_patterns[pattern] += 1
    threshold = max(1, len(test_failures) * 0.05)
    dominant = sorted(
        [(p, c) for p, c in error_patterns.items() if c >= threshold],
        key=lambda x: -x[1],
    )
    return {
        "failed_tests": sorted(test_failures.keys()),
        "dominant_error_patterns": dominant,
        "total": len(test_failures),
    }


def classify_job(job):
    prowjob = job.get("prowjob", {})
    if "error" in prowjob:
        return "E"
    state = prowjob.get("state", "")
    if state == "success":
        return "S"
    if state == "failure":
        return "F"
    if state == "aborted":
        return "A"
    return "pending"


def format_duration(seconds):
    if seconds is None or seconds < 0:
        return "-"
    if seconds == 0:
        return "<1s"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"


def format_text(data):
    lines = []

    lines.append("## PR Payload Run Summary")
    lines.append("")
    lines.append(f"- **URL**: {data['url']}")
    pr = data.get("pr_metadata", {})
    if pr.get("repo"):
        lines.append(f"- **PR**: {pr['repo']}#{pr['pr_number']}")
    status = "All jobs finished" if data["all_jobs_finished"] else "Jobs still running"
    lines.append(f"- **Status**: {status}")
    lines.append("")

    jobs = data["jobs"]
    passed = sum(1 for j in jobs if j["_result"] == "S")
    failed = sum(1 for j in jobs if j["_result"] == "F")
    aborted = sum(1 for j in jobs if j["_result"] == "A")
    errors = sum(1 for j in jobs if j["_result"] == "E")
    pending = sum(1 for j in jobs if j["_result"] == "pending")

    parts = [f"{passed} passed", f"{failed} failed"]
    if aborted:
        parts.append(f"{aborted} aborted")
    if errors:
        parts.append(f"{errors} errors")
    if pending:
        parts.append(f"{pending} pending")
    lines.append(f"## Job Results ({len(jobs)} total: {', '.join(parts)})")
    lines.append("")
    lines.append("| Job | Result | Duration |")
    lines.append("|-----|--------|----------|")

    failed_jobs = []
    for job in jobs:
        result = job["_result"]
        prowjob = job.get("prowjob", {})
        duration = format_duration(prowjob.get("duration_seconds"))
        lines.append(f"| {job['job_name']} | {result} | {duration} |")
        if result == "F":
            failed_jobs.append(job)
    lines.append("")

    if failed_jobs:
        lines.append("## Failed Job Details")
        lines.append("")
        for job in failed_jobs:
            prowjob = job["prowjob"]
            lines.append(f"### {job['job_name']}")
            lines.append("")

            desc = prowjob.get("description", "")
            duration = format_duration(prowjob.get("duration_seconds"))

            lines.append(f"- **Description**: {desc}")
            lines.append(f"- **Duration**: {duration}")
            lines.append(f"- **Prow URL**: {job['prow_url']}")

            sippy = job.get("sippy", {})
            test_failures = sippy.get("testFailures", {})
            if test_failures:
                test_count = sippy.get("testCount", 0)
                failure_count = sippy.get("testFailureCount", 0)
                pass_rate = (
                    f"{(test_count - failure_count) / test_count * 100:.1f}%"
                    if test_count > 0 else "N/A"
                )
                lines.append(f"- **Tests**: {test_count} total, {failure_count} failures ({pass_rate} pass rate)")

                analysis = analyze_test_failures(test_failures)
                if analysis["dominant_error_patterns"]:
                    lines.append("- **Dominant Error Patterns**:")
                    for pattern, count in analysis["dominant_error_patterns"][:5]:
                        pct = count / analysis["total"] * 100
                        lines.append(f"  - {count}/{analysis['total']} ({pct:.0f}%): {pattern}")

                top_n = analysis["failed_tests"][:10]
                lines.append(f"- **Failed Tests** (showing {len(top_n)}/{analysis['total']}):")
                for test_name in top_n:
                    lines.append(f"  - {test_name}")
            lines.append("")

    error_jobs = [j for j in jobs if j["_result"] == "E"]
    if error_jobs:
        lines.append("## Errored Jobs")
        lines.append("")
        for job in error_jobs:
            err = job.get("prowjob", {}).get("error", "")
            lines.append(f"- {job['job_name']} ({err})")
            lines.append(f"  {job['prow_url']}")
        lines.append("")

    pending_jobs = [j for j in jobs if j["_result"] == "pending"]
    if pending_jobs:
        lines.append("## Pending Jobs")
        lines.append("")
        for job in pending_jobs:
            lines.append(f"- {job['job_name']}")
            lines.append(f"  {job['prow_url']}")
        lines.append("")

    if failed_jobs:
        lines.append("## Next Steps")
        lines.append("")
        lines.append("To analyze specific failures in detail, use the `prow-job-analysis` skill with the prow URL.")
        lines.append("")
        lines.append("Failed job URLs:")
        for job in failed_jobs:
            lines.append(f"- {job['prow_url']}")
        lines.append("")

    return "\n".join(lines)


def format_json(data):
    jobs = data["jobs"]
    passed = sum(1 for j in jobs if j["_result"] == "S")
    failed = sum(1 for j in jobs if j["_result"] == "F")
    aborted = sum(1 for j in jobs if j["_result"] == "A")
    errors = sum(1 for j in jobs if j["_result"] == "E")
    pending = sum(1 for j in jobs if j["_result"] == "pending")

    job_entries = []
    for job in jobs:
        result = job["_result"]
        prowjob = job.get("prowjob", {})
        entry = {
            "job_name": job["job_name"],
            "prow_url": job["prow_url"],
            "run_id": job["run_id"],
            "result": result,
            "state": prowjob.get("state", "unknown"),
            "description": prowjob.get("description", ""),
            "duration_seconds": prowjob.get("duration_seconds"),
        }
        if prowjob.get("error"):
            entry["error"] = prowjob["error"]

        sippy = job.get("sippy", {})
        test_failures = sippy.get("testFailures", {})
        if test_failures:
            test_count = sippy.get("testCount", 0)
            failure_count = sippy.get("testFailureCount", 0)
            entry["test_count"] = test_count
            entry["failure_count"] = failure_count
            entry["pass_rate"] = (
                round((test_count - failure_count) / test_count * 100, 1)
                if test_count > 0 else None
            )
            analysis = analyze_test_failures(test_failures)
            entry["failed_tests"] = analysis["failed_tests"]
            entry["dominant_error_patterns"] = [
                {"pattern": p, "count": c,
                 "percentage": round(c / analysis["total"] * 100, 1)}
                for p, c in analysis["dominant_error_patterns"]
            ] if analysis["dominant_error_patterns"] else []
        job_entries.append(entry)

    output = {
        "url": data["url"],
        "uuid": data["uuid"],
        "pr_metadata": data.get("pr_metadata", {}),
        "all_jobs_finished": data["all_jobs_finished"],
        "summary": {
            "total_jobs": len(jobs),
            "passed": passed,
            "failed": failed,
            "aborted": aborted,
            "errors": errors,
            "pending": pending,
        },
        "jobs": job_entries,
    }
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a PR payload validation run"
    )
    parser.add_argument(
        "url",
        help="PR payload test URL (https://pr-payload-tests.ci.openshift.org/runs/ci/<uuid>)",
    )
    parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    m = PAYLOAD_URL_PATTERN.match(args.url)
    if not m:
        print("Error: invalid PR payload test URL", file=sys.stderr)
        print("Expected: https://pr-payload-tests.ci.openshift.org/runs/ci/<uuid>", file=sys.stderr)
        sys.exit(1)
    uuid = m.group(1)

    try:
        html = fetch_url(args.url)
    except Exception as e:
        print(f"Error fetching page: {e}", file=sys.stderr)
        sys.exit(1)

    page_data = parse_page(html)

    if not page_data["jobs"]:
        print("No prow jobs found on the page. The run may not have been triggered yet.",
              file=sys.stderr)
        sys.exit(1)

    job_results = fetch_all_statuses(page_data["jobs"])
    enrich_failed_jobs(job_results)
    for job in job_results:
        job["_result"] = classify_job(job)

    data = {
        "url": args.url,
        "uuid": uuid,
        "pr_metadata": page_data["pr_metadata"],
        "all_jobs_finished": page_data["all_jobs_finished"],
        "jobs": job_results,
    }

    if args.format == "json":
        print(format_json(data))
    else:
        print(format_text(data))


if __name__ == "__main__":
    main()
