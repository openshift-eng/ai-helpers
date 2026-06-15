#!/usr/bin/env python3
"""Extract secondary repository references from scope-req-audit output.

Parses recommended_action fields in evidence-status.json for GitHub/GitLab
URLs and PR references. Groups requirements by target repo and optionally
fetches PR file paths to derive suggested search scopes.

Usage:
    python3 extract_secondary_repos.py --evidence-status path/to/evidence-status.json
    python3 extract_secondary_repos.py --evidence-status path/to/evidence-status.json \
        --primary-repo https://github.com/org/main-repo \
        --fetch-pr-paths \
        --max-repos 3

Output: JSON array of secondary repo objects to stdout.

Exit codes:
    0 — success (JSON array on stdout, may be empty)
    1 — error (message on stderr)
"""

import argparse
import json
import re
import subprocess  # noqa: S404
import sys

GITHUB_PR_RE = re.compile(r"https?://github\.com/([^/]+/[^/]+)/pull/(\d+)")
GITLAB_MR_RE = re.compile(r"https?://gitlab\.[^/]+/(.+?)/-/merge_requests/(\d+)")
GITHUB_REPO_RE = re.compile(r"https?://github\.com/([^/]+/[^/]+?)(?:\.git)?(?:/.*)?$")
GITLAB_REPO_RE = re.compile(r"(https?://gitlab\.[^/]+/.+?)(?:\.git)?(?:/-/.*)?$")

_URL_RE = re.compile(r"https?://(?:github\.com|gitlab\.[^\s/]+)/[^\s\[\]()|<>\"']+")
_PR_HASH_RE = re.compile(r"(?:PR|MR)\s*#(\d+)", re.IGNORECASE)


def _extract_repo_url(link_url):
    """Normalize a GitHub/GitLab link to a canonical repo URL."""
    m = GITHUB_PR_RE.match(link_url)
    if m:
        return f"https://github.com/{m.group(1)}"
    m = GITLAB_MR_RE.match(link_url)
    if m:
        return link_url.split("/-/")[0]
    m = GITHUB_REPO_RE.match(link_url)
    if m:
        return f"https://github.com/{m.group(1)}"
    m = GITLAB_REPO_RE.match(link_url)
    if m:
        return m.group(1)
    return None


def _clean_url(raw):
    """Strip trailing punctuation and formatting artifacts."""
    url = raw.strip("[]() \t")
    url = url.rstrip(".,;:!?>)")
    return url


def _extract_pr_refs(text, repo_url):
    """Extract PR/MR numbers from text, both as URLs and #NNN references."""
    refs = set()
    for m in GITHUB_PR_RE.finditer(text):
        pr_repo = f"https://github.com/{m.group(1)}"
        if pr_repo == repo_url:
            refs.add(f"#{m.group(2)}")
    for m in GITLAB_MR_RE.finditer(text):
        mr_repo = text[: m.start()].split("/-/")[0] if "/-/" in text else None
        if mr_repo and mr_repo == repo_url:
            refs.add(f"#{m.group(2)}")
    for m in _PR_HASH_RE.finditer(text):
        refs.add(f"#{m.group(1)}")
    return sorted(refs, key=lambda r: int(r.lstrip("#")))


def _fetch_pr_file_paths(repo_url, pr_number):
    """Fetch file paths changed in a PR via gh CLI. Returns list or None."""
    m = GITHUB_REPO_RE.match(repo_url)
    if not m:
        return None
    repo_slug = m.group(1)
    try:
        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--repo",
                repo_slug,
                "--json",
                "files",
                "-q",
                ".files[].path",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _derive_suggested_scope(file_paths):
    """Derive directory prefixes from a list of file paths."""
    if not file_paths:
        return None
    from pathlib import PurePosixPath

    dirs = set()
    for fp in file_paths:
        parts = PurePosixPath(fp).parts
        if len(parts) >= 2:
            dirs.add(f"{parts[0]}/{parts[1]}/")
        elif len(parts) == 1:
            dirs.add(f"{parts[0]}/")
    if not dirs:
        return None
    return sorted(dirs)


def extract_secondary_repos(
    evidence_status, primary_repo_url=None, fetch_pr_paths=False, max_repos=3
):
    """Extract secondary repo references from evidence-status requirements.

    Returns a list of secondary repo dicts sorted by requirement count (desc).
    """
    requirements = evidence_status.get("requirements", [])
    repo_map = {}

    for req in requirements:
        if req.get("status") not in ("partial", "absent"):
            continue
        action = req.get("recommended_action")
        if not action:
            continue

        urls_found = _URL_RE.findall(action)
        for raw_url in urls_found:
            cleaned = _clean_url(raw_url)
            repo_url = _extract_repo_url(cleaned)
            if not repo_url:
                continue
            if primary_repo_url and repo_url == primary_repo_url:
                continue

            if repo_url not in repo_map:
                repo_map[repo_url] = {
                    "url": repo_url,
                    "source": "gap_classification",
                    "requirements": [],
                    "pr_refs": set(),
                    "priority": "secondary",
                    "suggested_scope": None,
                }
            entry = repo_map[repo_url]
            req_id = req.get("id", "unknown")
            if req_id not in entry["requirements"]:
                entry["requirements"].append(req_id)
            pr_refs = _extract_pr_refs(action, repo_url)
            entry["pr_refs"].update(pr_refs)

    repos = sorted(
        repo_map.values(),
        key=lambda r: len(r["requirements"]),
        reverse=True,
    )[:max_repos]

    for entry in repos:
        entry["pr_refs"] = sorted(entry["pr_refs"], key=lambda r: int(r.lstrip("#")))

    if fetch_pr_paths:
        for entry in repos:
            all_paths = []
            for ref in entry["pr_refs"][:3]:
                pr_num = ref.lstrip("#")
                paths = _fetch_pr_file_paths(entry["url"], pr_num)
                if paths:
                    all_paths.extend(paths)
            if all_paths:
                entry["suggested_scope"] = _derive_suggested_scope(all_paths)

    return repos


def main():
    parser = argparse.ArgumentParser(
        description="Extract secondary repo references from evidence-status.json"
    )
    parser.add_argument(
        "--evidence-status",
        required=True,
        help="Path to evidence-status.json from scope-req-audit",
    )
    parser.add_argument(
        "--primary-repo",
        help="Primary repo URL to exclude from results",
    )
    parser.add_argument(
        "--fetch-pr-paths",
        action="store_true",
        help="Fetch PR file paths via gh CLI to derive suggested_scope",
    )
    parser.add_argument(
        "--max-repos",
        type=int,
        default=3,
        help="Maximum secondary repos to return (default: 3)",
    )
    args = parser.parse_args()

    try:
        with open(args.evidence_status) as f:
            evidence_status = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error reading evidence-status.json: {e}", file=sys.stderr)
        sys.exit(1)

    repos = extract_secondary_repos(
        evidence_status,
        primary_repo_url=args.primary_repo,
        fetch_pr_paths=args.fetch_pr_paths,
        max_repos=args.max_repos,
    )

    json.dump(repos, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
