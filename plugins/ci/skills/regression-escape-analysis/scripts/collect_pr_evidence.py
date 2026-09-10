#!/usr/bin/env python3
"""Collect frozen merge-time evidence for regression escape analysis."""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1
CHAI_LOGINS = {"redhat-chai-bot", "redhat-chai-bot[bot]"}
TERMINAL_STATES = {"success", "failure", "error"}
CHATOPS_RE = re.compile(
    r"^\s*/(override|skip|retest-required|retest|test|verified|lgtm|approve|hold|unhold)"
    r"(?:[ \t]+([^\r\n]*?))?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
PROW_REPORT_ROW_RE = re.compile(
    r"^\s*(ci/prow/[^|]+?)\s*\|\s*([0-9a-f]{7,40})\s*\|\s*"
    r"\[link\]\((https://prow\.ci\.openshift\.org/[^)]+)\)\s*\|\s*"
    r"(true|false)\s*\|\s*`?(/[^`\r\n]+)`?\s*$",
    re.IGNORECASE,
)


def parse_pr_url(url):
    match = re.fullmatch(
        r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)/?", url.strip()
    )
    if not match:
        raise ValueError(f"not a GitHub pull request URL: {url}")
    return match.group(1), match.group(2), int(match.group(3))


def run_gh_json(endpoint, paginate=False):
    args = ["gh", "api"]
    if paginate:
        args.extend(["--paginate", "--slurp"])
    args.append(endpoint)
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=180, check=False
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if result.returncode != 0:
        error = result.stderr.strip() or f"gh exited {result.returncode}"
        if "HTTP 404" in error or "Not Found" in error:
            return None, "not_found"
        return None, error[:500]
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    if not paginate:
        return data, None
    flattened = []
    for page in data:
        if isinstance(page, list):
            flattened.extend(page)
        else:
            flattened.append(page)
    return flattened, None


def actor(user):
    if not isinstance(user, dict):
        return {"login": "", "type": "", "kind": "unknown"}
    login = user.get("login") or ""
    user_type = user.get("type") or ""
    lowered = login.lower()
    if lowered in CHAI_LOGINS:
        kind = "chai"
    elif user_type.lower() == "bot" or lowered.endswith("[bot]"):
        kind = "automation"
    elif login:
        kind = "human"
    else:
        kind = "unknown"
    return {"login": login, "type": user_type, "kind": kind}


def at_or_before(timestamp, cutoff):
    return bool(timestamp) and (not cutoff or timestamp <= cutoff)


def extract_chatops_actions(comments, cutoff):
    actions = []
    for comment in comments or []:
        created_at = comment.get("created_at", "")
        if not at_or_before(created_at, cutoff):
            continue
        who = actor(comment.get("user"))
        for match in CHATOPS_RE.finditer(comment.get("body") or ""):
            action = match.group(1).lower()
            arguments = (match.group(2) or "").strip()
            command = f"/{action}" + (f" {arguments}" if arguments else "")
            actions.append({
                "action": action,
                "arguments": arguments,
                "command": command,
                "created_at": created_at,
                "actor": who,
                "url": comment.get("html_url", ""),
            })
    return sorted(actions, key=lambda item: item["created_at"])


def normalize_reviews(reviews, cutoff):
    normalized = []
    for review in reviews or []:
        submitted_at = review.get("submitted_at", "")
        if not at_or_before(submitted_at, cutoff):
            continue
        normalized.append({
            "state": (review.get("state") or "").lower(),
            "commit_id": review.get("commit_id") or "",
            "submitted_at": submitted_at,
            "actor": actor(review.get("user")),
            "url": review.get("html_url", ""),
        })
    return sorted(normalized, key=lambda item: item["submitted_at"])


def extract_ci_reported_failures(comments, cutoff):
    failures = []
    for comment in comments or []:
        created_at = comment.get("created_at", "")
        if not at_or_before(created_at, cutoff):
            continue
        for line in (comment.get("body") or "").splitlines():
            match = PROW_REPORT_ROW_RE.match(line)
            if not match:
                continue
            failures.append({
                "context": match.group(1).strip(),
                "commit_sha": match.group(2),
                "prow_url": match.group(3),
                "required": match.group(4).lower() == "true",
                "rerun_command": match.group(5).strip(),
                "reported_at": created_at,
                "report_actor": actor(comment.get("user")),
                "report_url": comment.get("html_url", ""),
            })
    return sorted(failures, key=lambda item: (item["reported_at"], item["context"]))


def normalize_status_contexts(statuses, cutoff):
    grouped = defaultdict(list)
    for status in statuses or []:
        created_at = status.get("created_at", "")
        if not at_or_before(created_at, cutoff):
            continue
        grouped[status.get("context") or "(unnamed)"].append({
            "state": (status.get("state") or "").lower(),
            "created_at": created_at,
            "updated_at": status.get("updated_at") or "",
            "target_url": status.get("target_url") or "",
            "description": status.get("description") or "",
            "actor": actor(status.get("creator")),
        })

    contexts = []
    for context, events in grouped.items():
        events.sort(key=lambda item: (item["created_at"], item["updated_at"]))
        terminals = [event for event in events if event["state"] in TERMINAL_STATES]
        contexts.append({
            "context": context,
            "events": events,
            "terminal_attempts": terminals,
            "retry_count": max(0, len(terminals) - 1),
        })
    return sorted(contexts, key=lambda item: item["context"])


def normalize_check_runs(pages, cutoff):
    runs = []
    for page in pages or []:
        candidates = page.get("check_runs", []) if isinstance(page, dict) else []
        for check in candidates:
            started_at = check.get("started_at") or check.get("created_at") or ""
            if not at_or_before(started_at, cutoff):
                continue
            completed_at = check.get("completed_at")
            completed_by_cutoff = at_or_before(completed_at, cutoff)
            runs.append({
                "name": check.get("name") or "",
                "status": check.get("status") if completed_by_cutoff else "in_progress",
                "conclusion": check.get("conclusion") if completed_by_cutoff else None,
                "started_at": started_at,
                "completed_at": completed_at if completed_by_cutoff else None,
                "details_url": check.get("details_url") or "",
                "app": (check.get("app") or {}).get("slug", ""),
            })
    return sorted(runs, key=lambda item: (item["name"], item["started_at"]))


def download_file(url, destination):
    request = urllib.request.Request(
        url, headers={"User-Agent": "regression-escape-analysis/1.0"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        content = response.read()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)


def branch_prefix(org, repo, branch):
    branch_slug = branch.replace("/", "-")
    return f"{org}-{repo}-{branch_slug}"


def snapshot_entries(entries, output_dir, subdir, predicate, errors):
    saved = []
    for entry in entries or []:
        if entry.get("type") != "file" or not predicate(entry.get("name", "")):
            continue
        destination = output_dir / "ci-config" / subdir / entry["name"]
        try:
            download_file(entry["download_url"], destination)
        except (OSError, urllib.error.URLError) as exc:
            errors.append({
                "source": entry.get("path", entry["name"]),
                "error": str(exc),
            })
            continue
        saved.append({
            "source_path": entry.get("path", ""),
            "source_sha": entry.get("sha", ""),
            "snapshot_path": str(destination.relative_to(output_dir)),
        })
    return saved


def fetch_directory(repo, path, ref, errors, required=False):
    endpoint = (
        f"repos/{repo}/contents/{path}?ref={urllib.parse.quote(ref, safe='')}"
    )
    data, error = run_gh_json(endpoint)
    if error == "not_found":
        return []
    if error:
        errors.append({"source": path, "error": error, "required": required})
        return []
    return data if isinstance(data, list) else []


def fetch_file_entry(repo, path, ref, errors):
    endpoint = (
        f"repos/{repo}/contents/{path}?ref={urllib.parse.quote(ref, safe='')}"
    )
    data, error = run_gh_json(endpoint)
    if error == "not_found":
        return []
    if error:
        errors.append({"source": path, "error": error, "required": False})
        return []
    return [data] if isinstance(data, dict) else []


def collect_ci_configuration(org, repo, pr_meta, output_dir, errors):
    base_ref = pr_meta.get("base", {}).get("ref") or ""
    base_sha = pr_meta.get("base", {}).get("sha") or ""
    merged_at = pr_meta.get("merged_at") or ""
    full_repo = f"{org}/{repo}"

    if full_repo == "openshift/release":
        release_ref = base_sha
    else:
        commits, error = run_gh_json(
            "repos/openshift/release/commits"
            f"?until={urllib.parse.quote(merged_at, safe=':-TZ')}&per_page=1"
        )
        if error or not commits:
            errors.append({
                "source": "openshift/release merge-time revision",
                "error": error or "no commit found",
                "required": True,
            })
            release_ref = ""
        else:
            release_ref = commits[0].get("sha", "")

    prefix = branch_prefix(org, repo, base_ref)
    release_config = []
    release_jobs = []
    if release_ref:
        config_path = f"ci-operator/config/{org}/{repo}"
        job_path = f"ci-operator/jobs/{org}/{repo}"
        config_entries = fetch_directory(
            "openshift/release", config_path, release_ref, errors, required=True
        )
        job_entries = fetch_directory(
            "openshift/release", job_path, release_ref, errors, required=True
        )
        release_config = snapshot_entries(
            config_entries,
            output_dir,
            "openshift-release",
            lambda name: name == f"{prefix}.yaml"
            or (name.startswith(f"{prefix}__") and name.endswith(".yaml")),
            errors,
        )
        release_jobs = snapshot_entries(
            job_entries,
            output_dir,
            "openshift-release",
            lambda name: name == f"{prefix}-presubmits.yaml",
            errors,
        )

    workflow_entries = fetch_directory(
        full_repo, ".github/workflows", base_sha, errors, required=False
    )
    workflows = snapshot_entries(
        workflow_entries,
        output_dir,
        "repository-workflows",
        lambda name: name.endswith((".yml", ".yaml")),
        errors,
    )
    local_ci_entries = fetch_file_entry(
        full_repo, ".ci-operator.yaml", base_sha, errors
    )
    local_ci = snapshot_entries(
        local_ci_entries,
        output_dir,
        "repository",
        lambda name: name == ".ci-operator.yaml",
        errors,
    )

    return {
        "openshift_release": {
            "repository": "openshift/release",
            "ref": release_ref,
            "selected_at": merged_at,
            "ci_operator_configs": release_config,
            "prow_presubmits": release_jobs,
        },
        "repository": {
            "repository": full_repo,
            "ref": base_sha,
            "ci_operator": local_ci,
            "workflows": workflows,
        },
    }


def collect(pr_url, output_dir):
    org, repo, number = parse_pr_url(pr_url)
    errors = []
    pr_meta, error = run_gh_json(f"repos/{org}/{repo}/pulls/{number}")
    if error or not pr_meta:
        raise RuntimeError(error or "pull request metadata unavailable")
    if not pr_meta.get("merged_at"):
        raise RuntimeError("pull request has not merged; no escape point exists")

    cutoff = pr_meta["merged_at"]
    head_sha = pr_meta.get("head", {}).get("sha") or ""
    sources = {}
    endpoints = {
        "comments": (f"repos/{org}/{repo}/issues/{number}/comments?per_page=100", True),
        "reviews": (f"repos/{org}/{repo}/pulls/{number}/reviews?per_page=100", True),
        "statuses": (f"repos/{org}/{repo}/commits/{head_sha}/statuses?per_page=100", True),
        "checks": (f"repos/{org}/{repo}/commits/{head_sha}/check-runs?filter=all&per_page=100", True),
    }
    for name, (endpoint, paginate) in endpoints.items():
        value, source_error = run_gh_json(endpoint, paginate=paginate)
        if source_error == "not_found" and name == "checks":
            value, source_error = [], None
        if source_error:
            errors.append({"source": name, "error": source_error, "required": name != "checks"})
            value = []
        sources[name] = value

    ci_configuration = collect_ci_configuration(
        org, repo, pr_meta, output_dir, errors
    )
    merged_by = actor(pr_meta.get("merged_by"))
    merge_mechanism = (
        "tide"
        if "openshift-merge-bot" in merged_by["login"].lower()
        else "direct_or_other"
    )
    labels = sorted(label.get("name", "") for label in pr_meta.get("labels", []))

    evidence = {
        "schema_version": SCHEMA_VERSION,
        "collected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "cutoff": cutoff,
        "data_complete": not any(error.get("required") for error in errors),
        "collection_errors": errors,
        "pr": {
            "url": pr_meta.get("html_url") or pr_url,
            "repository": f"{org}/{repo}",
            "number": number,
            "title": pr_meta.get("title") or "",
            "author": actor(pr_meta.get("user")),
            "base_ref": pr_meta.get("base", {}).get("ref") or "",
            "base_sha": pr_meta.get("base", {}).get("sha") or "",
            "head_sha": head_sha,
            "merge_commit_sha": pr_meta.get("merge_commit_sha") or "",
            "merged_at": cutoff,
            "merged_by": merged_by,
            "merge_mechanism": merge_mechanism,
            "labels_at_collection": labels,
        },
        "chatops_actions": extract_chatops_actions(sources["comments"], cutoff),
        "ci_reported_failures": extract_ci_reported_failures(
            sources["comments"], cutoff
        ),
        "reviews": normalize_reviews(sources["reviews"], cutoff),
        "status_contexts": normalize_status_contexts(sources["statuses"], cutoff),
        "check_runs": normalize_check_runs(sources["checks"], cutoff),
        "ci_configuration": ci_configuration,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "escape-analysis.json"
    destination.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return destination


def main():
    parser = argparse.ArgumentParser(
        description="Collect merge-time PR evidence for regression escape analysis."
    )
    parser.add_argument("pr_url")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    try:
        destination = collect(args.pr_url, Path(args.output_dir).resolve())
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
