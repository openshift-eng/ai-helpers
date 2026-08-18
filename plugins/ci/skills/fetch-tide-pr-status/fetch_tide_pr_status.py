#!/usr/bin/env python3
"""See SKILL.md for details."""

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import urlopen, Request

import yaml


def clean_description(desc):
    return re.sub(r'[\u2000-\u200f\u2028-\u202f]+', ' ', desc).strip()


def fetch_url(url):
    req = Request(url, headers={"User-Agent": "fetch-tide-pr-status/1.0"})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode()


def gh_api(path):
    result = subprocess.run(
        ["gh", "api", path],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh api {path} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def gh_api_paginated(path):
    """Fetch all pages and flatten into a single list."""
    result = subprocess.run(
        ["gh", "api", "--paginate", "--slurp", path],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh api {path} failed: {result.stderr.strip()}")
    pages = json.loads(result.stdout)
    items = []
    for page in pages:
        if isinstance(page, list):
            items.extend(page)
        else:
            items.append(page)
    return items


def fetch_pr_data(repo, pr_num):
    """Two GitHub API calls per PR: pulls/{n} + commits/{sha}/status."""
    pr_meta = gh_api(f"repos/{repo}/pulls/{pr_num}")
    sha = pr_meta["head"]["sha"]
    status_data = gh_api(f"repos/{repo}/commits/{sha}/status?per_page=100")
    return pr_num, pr_meta, status_data


def fetch_presubmit_config(repo, branch):
    """Fetch presubmit config from openshift/release (main branch).

    Returns dict mapping context name → {always_run, optional}, or None on failure.
    """
    org, repo_name = repo.split("/")
    filename = f"{org}-{repo_name}-{branch}-presubmits.yaml"
    url = f"https://raw.githubusercontent.com/openshift/release/master/ci-operator/jobs/{org}/{repo_name}/{filename}"
    try:
        raw = fetch_url(url)
    except Exception:
        return None
    data = yaml.safe_load(raw)
    if not data:
        return None
    config = {}
    for j in data.get("presubmits", {}).get(repo, []):
        ctx = j.get("context", j.get("name", ""))
        if ctx:
            config[ctx] = {
                "always_run": j.get("always_run", False),
                "optional": j.get("optional", False),
            }
    return config




def match_tide_queries(tide_queries, repo, branch, pr_labels_set):
    """Port of closestMatchingQueries (pr.ts:1062).

    Returns list of processed queries sorted by descending score.
    Score 1.0 = all label requirements met.
    """
    owner = repo.split("/")[0]
    results = []
    for tq in tide_queries:
        repos = tq.get("repos", [])
        orgs = tq.get("orgs", [])
        excluded_repos = tq.get("excludedRepos", [])

        if repo not in repos and not (owner in orgs and repo not in excluded_repos):
            continue

        inc = tq.get("includedBranches", [])
        exc = tq.get("excludedBranches", [])
        if branch in exc:
            continue
        if inc and branch not in inc:
            continue

        required = sorted(tq.get("labels", []), key=len)
        forbidden = sorted(tq.get("missingLabels", []), key=len)

        labels = [{"name": label, "have": label in pr_labels_set} for label in required]
        missing_labels = [{"name": label, "have": label in pr_labels_set} for label in forbidden]

        total = len(labels) + len(missing_labels)
        if total > 0:
            hits = sum(1 for label in labels if label["have"]) + sum(1 for label in missing_labels if not label["have"])
            score = hits / total
        else:
            score = 1.0

        results.append({"labels": labels, "missingLabels": missing_labels, "score": score})

    results.sort(key=lambda q: -q["score"])
    return results


def build_job_entry(name, state, description, url):
    """Build a job entry with a normalized state."""
    if state == "pending":
        if "Waiting for pipeline" in (description or ""):
            state = "awaiting_pipeline"
        else:
            state = "running"

    entry = {"name": name, "state": state}
    if state == "failure" and url:
        entry["url"] = url
    if state in ("running", "error") and description:
        entry["description"] = description
    return entry


def build_pr_result(pr_num, pr_meta, status_data, tide_queries, presubmit_configs):
    repo = pr_meta["base"]["repo"]["full_name"]
    branch = pr_meta["base"]["ref"]

    tide_status = None
    jobs = []
    for s in status_data.get("statuses", []):
        if s["context"] == "tide":
            tide_status = clean_description(s.get("description", ""))
        else:
            jobs.append(build_job_entry(
                s["context"], s["state"],
                clean_description(s.get("description", "")),
                s.get("target_url") or None,
            ))

    pr_labels_set = {label["name"] for label in pr_meta.get("labels", [])}
    queries = match_tide_queries(tide_queries, repo, branch, pr_labels_set)
    best = queries[0] if queries else None

    # Labels
    if best:
        labels_section = {
            "met": abs(best["score"] - 1.0) < 1e-9,
            "required": {
                "have": [label["name"] for label in best["labels"] if label["have"]],
                "missing": [label["name"] for label in best["labels"] if not label["have"]],
            },
            "forbidden": {
                "have": [label["name"] for label in best["missingLabels"] if label["have"]],
                "clear": [label["name"] for label in best["missingLabels"] if not label["have"]],
            },
        }
    else:
        labels_section = None

    # Classify jobs
    job_config = presubmit_configs.get(branch)
    if job_config:
        required_jobs = [
            j for j in jobs
            if j["name"] in job_config and not job_config[j["name"]]["optional"]
        ]
    else:
        required_jobs = [{"error": f"could not fetch presubmit config from openshift/release for {repo} branch {branch} — job classification unavailable"}]

    blockers = []
    if best:
        blockers += [f"missing required label: {label['name']}" for label in best["labels"] if not label["have"]]
        blockers += [f"has forbidden label: {label['name']}" for label in best["missingLabels"] if label["have"]]
    else:
        blockers.append("no Tide query matches this branch")

    for j in required_jobs:
        if "error" not in j and j["state"] != "success":
            blockers.append(f"job not passing: {j['name']} ({j['state']})")

    if pr_meta.get("mergeable") is False:
        blockers.append("merge conflict (needs rebase)")

    return {
        "number": pr_num,
        "title": pr_meta["title"],
        "author": pr_meta["user"]["login"],
        "url": pr_meta["html_url"],
        "branch": branch,
        "state": pr_meta["state"],
        "mergeable": pr_meta.get("mergeable"),
        "tide": tide_status,
        "blockers": blockers,
        "labels": labels_section,
        "required_jobs": required_jobs,
    }


def list_open_prs(repo, author):
    """List open PR numbers for an author in a repo."""
    data = gh_api_paginated(f"repos/{repo}/pulls?state=open&per_page=100")
    return [pr["number"] for pr in data if pr["user"]["login"] == author]


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <owner/repo> <author | pr1,pr2,...>", file=sys.stderr)
        sys.exit(1)

    repo = sys.argv[1]
    if "/" not in repo:
        print(f"Error: repo must be owner/name, got '{repo}'", file=sys.stderr)
        sys.exit(1)

    arg = sys.argv[2]
    if arg.isdigit() or "," in arg:
        pr_numbers = [int(x) for x in arg.split(",")]
    else:
        pr_numbers = list_open_prs(repo, arg)
        if not pr_numbers:
            print(json.dumps([]))
            return

    # Phase 1: fetch tide.js + PR data in parallel
    with ThreadPoolExecutor(max_workers=16) as pool:
        future_tide = pool.submit(fetch_url, "https://prow.ci.openshift.org/tide.js")
        pr_futures = {
            pool.submit(fetch_pr_data, repo, pr_num): pr_num
            for pr_num in pr_numbers
        }
        tide = json.loads(future_tide.result())
        tide_queries = tide.get("TideQueries", [])

        pr_data = {}
        for future in as_completed(pr_futures):
            pr_num, pr_meta, status_data = future.result()
            pr_data[pr_num] = (pr_meta, status_data)

    # Phase 2: fetch presubmit configs for unique branches
    branches = {pr_data[n][0]["base"]["ref"] for n in pr_numbers}
    presubmit_configs = {}
    with ThreadPoolExecutor(max_workers=16) as pool:
        branch_futures = {
            pool.submit(fetch_presubmit_config, repo, b): b for b in branches
        }
        for future in as_completed(branch_futures):
            b = branch_futures[future]
            try:
                cfg = future.result()
                if cfg is not None:
                    presubmit_configs[b] = cfg
            except Exception:
                pass

    results = [
        build_pr_result(n, pr_data[n][0], pr_data[n][1], tide_queries, presubmit_configs)
        for n in pr_numbers
        if pr_data[n][0]["state"] == "open" and not pr_data[n][0].get("draft")
    ]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
