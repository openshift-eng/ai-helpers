#!/usr/bin/env python3
"""Resolve and clone/verify a source code repository for a docs workflow.

Handles repo cloning, source.yaml management, PR branch checkout, and
progress file synchronization. JIRA-based repo discovery is handled
upstream by the requirements step (extract_discovered_repos.py writes
discovered_repos.json, which this script reads at Priority 4).

Resolution priority:
    1. Explicit --repo flag
    2. Per-ticket source.yaml
    3. PR-derived (--pr without --repo)
    4. discovered_repos.json (from requirements step)
    5. Scan requirements.md for PR URLs (--scan-requirements)

When --progress-file is passed, writes resolved source info into the
workflow progress JSON and flips deferred steps to pending (or skipped
if --skip-deferred-on-no-source and no source found).

Output: JSON to stdout with the resolved source info, or an error status.

Exit codes:
    0 — success (source resolved, JSON on stdout)
    1 — error (message on stderr)
    2 — no source found (not an error; JSON with status "no_source" on stdout)

Prerequisites:
    - gh CLI (for GitHub PR resolution)
    - glab CLI (for GitLab MR resolution)
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# PR/MR URL patterns
GITHUB_PR_RE = re.compile(r"https?://github\.com/([^/]+/[^/]+)/pull/(\d+)")
GITLAB_MR_RE = re.compile(r"https?://gitlab\.[^/]+/(.+?)/-/merge_requests/(\d+)")

# Repo URL extraction patterns (for git_links that aren't PRs)
GITHUB_REPO_RE = re.compile(r"https?://github\.com/([^/]+/[^/]+?)(?:\.git)?(?:/.*)?$")
GITLAB_REPO_RE = re.compile(r"(https?://gitlab\.[^/]+/.+?)(?:\.git)?(?:/-/.*)?$")


def _is_remote_url(value):
    """Check if a value is a remote git URL (not a local path)."""
    return value.startswith(("https://", "git@", "ssh://"))


def _git_pr_reader_path():
    """Locate git_pr_reader.py relative to this script."""
    return str(
        Path(__file__).resolve().parents[2] / "git-pr-reader" / "scripts" / "git_pr_reader.py"
    )


def _read_source_yaml(base_path):
    """Read source.yaml if it exists. Returns dict or None."""
    source_file = Path(base_path) / "source.yaml"
    if not source_file.exists():
        return None
    try:
        import yaml
    except ImportError:
        # Fall back to basic parsing for simple YAML
        return _parse_simple_yaml(source_file)
    with open(source_file) as f:
        return yaml.safe_load(f)


def _parse_simple_yaml(path):
    """Parse a simple key-value YAML without PyYAML dependency.

    Handles the source.yaml schema: top-level scalars (repo, ref) and a
    nested scope dict with include/exclude lists. Indentation determines
    nesting — indented keys belong to the most recent top-level mapping key.
    """
    result = {}
    # parent_key tracks the current top-level mapping key (e.g., "scope")
    parent_key = None
    current_list = None

    with open(path) as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            indent = len(line) - len(line.lstrip())

            # Handle list items under a nested key
            if stripped.startswith("- ") and current_list is not None:
                value = stripped[2:].strip().strip('"').strip("'")
                current_list.append(value)
                continue

            if ":" not in stripped:
                continue

            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            if indent == 0:
                # Top-level key
                if value:
                    result[key] = value.strip('"').strip("'")
                    parent_key = None
                    current_list = None
                else:
                    # Mapping parent (e.g., "scope:")
                    result[key] = {}
                    parent_key = key
                    current_list = None
            elif parent_key and indent > 0:
                # Nested key under parent (e.g., "include:" under "scope:")
                if value:
                    result[parent_key][key] = value.strip('"').strip("'")
                    current_list = None
                else:
                    # List parent (e.g., "include:" with no value)
                    result[parent_key][key] = []
                    current_list = result[parent_key][key]

    return result


def normalize_git_url(url):
    """Normalize a git URL for comparison (strip .git suffix and trailing slash)."""
    return url.rstrip("/").removesuffix(".git")


def repo_name_from_url(url):
    """Extract the repository name from a git URL."""
    return normalize_git_url(url).split("/")[-1]


def _resolve_pr_info(pr_url):
    """Extract repo URL and branch from a GitHub PR or GitLab MR URL.

    Delegates to git_pr_reader.py resolve, which uses PyGithub/python-gitlab.
    Returns (repo_url, branch) where branch is None for merged PRs.
    """
    result = subprocess.run(  # noqa: S603
        ["python3", _git_pr_reader_path(), "resolve", pr_url, "--json"],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            ["git_pr_reader.py", "resolve"],
            result.stdout,
            result.stderr,
        )
    data = json.loads(result.stdout)
    return data["repo_url"], data["branch"]


def _scan_requirements_for_prs(base_path):
    """Scan requirements.md for PR/MR URLs and group by repo."""
    req_file = Path(base_path) / "requirements" / "requirements.md"
    if not req_file.exists():
        return {}

    content = req_file.read_text()
    repos = {}

    for match in GITHUB_PR_RE.finditer(content):
        repo_slug = match.group(1)
        pr_num = match.group(2)
        url = match.group(0)
        repos.setdefault(repo_slug, []).append(
            {
                "url": url,
                "number": int(pr_num),
                "type": "github",
            }
        )

    for match in GITLAB_MR_RE.finditer(content):
        repo_slug = match.group(1)
        mr_num = match.group(2)
        url = match.group(0)
        repos.setdefault(repo_slug, []).append(
            {
                "url": url,
                "number": int(mr_num),
                "type": "gitlab",
            }
        )

    return repos


def _read_discovered_repos(base_path):
    """Read discovered_repos.json if it exists.

    Returns list of repo dicts [{"repo_url": ..., "pr_urls": [...]}] or empty list.
    """
    repos_file = Path(base_path) / "requirements" / "discovered_repos.json"
    if not repos_file.exists():
        return []
    try:
        with open(repos_file) as f:
            data = json.load(f)
        return data.get("repos", [])
    except (json.JSONDecodeError, KeyError):
        return []


def _resolve_discovered_repos(discovered, base_path, dry_run=False):
    """Clone all repos from discovered_repos.json.

    Clones each remote repo into code-repo/<repo_name>/. For repos with
    PR URLs, resolves the first PR's branch and checks it out.

    Returns a result dict (same contract as resolve()).
    """
    if not discovered:
        return {"status": "no_source"}

    resolved_repos = []
    errors = []

    for repo_entry in discovered:
        repo_url = repo_entry.get("repo_url")
        if not repo_url:
            continue

        pr_urls = repo_entry.get("pr_urls", [])
        ref = None

        if pr_urls:
            try:
                _, pr_branch = _resolve_pr_info(pr_urls[0])
                ref = pr_branch
            except (subprocess.CalledProcessError, Exception) as e:
                print(
                    f"WARNING: Could not resolve PR branch from {pr_urls[0]}: {e}",
                    file=sys.stderr,
                )

        repo_name = repo_name_from_url(repo_url)
        clone_dir = Path(base_path) / "code-repo" / repo_name

        if not dry_run:
            if clone_dir.exists():
                if not _verify_existing_clone(clone_dir, ref, expected_repo_url=repo_url):
                    errors.append(f"Existing clone at {clone_dir} is invalid.")
                    continue
            else:
                first_pr = pr_urls[0] if pr_urls else None
                if not _clone_repo(repo_url, clone_dir, ref, pr_url=first_pr):
                    errors.append(f"Could not clone {repo_url}.")
                    continue

        resolved_repos.append(
            {
                "repo_path": str(clone_dir),
                "repo_url": repo_url,
                "ref": ref,
            }
        )

    if not resolved_repos:
        return {
            "status": "error" if errors else "no_source",
            "message": (f"Could not clone any discovered repos. Errors: {'; '.join(errors)}")
            if errors
            else None,
        }

    primary = resolved_repos[0]
    _write_source_yaml(base_path, primary["repo_url"], primary["ref"], dry_run=dry_run)

    result = _success(
        primary["repo_path"],
        repo_url=primary["repo_url"],
        ref=primary["ref"],
    )
    if len(resolved_repos) > 1:
        result["additional_repos"] = resolved_repos[1:]
    if errors:
        result["warnings"] = errors
    return result


def extract_repo_url(link_url):
    """Extract a normalized repo URL from a GitHub/GitLab link.

    Handles PR URLs, commit URLs, file URLs, tree URLs, and plain repo URLs.
    Returns a normalized https repo URL (without .git), or None if unrecognized.
    """
    # GitHub PR
    match = GITHUB_PR_RE.match(link_url)
    if match:
        return f"https://github.com/{match.group(1)}"

    # GitLab MR
    match = GITLAB_MR_RE.match(link_url)
    if match:
        base = link_url.split("/-/merge_requests/")[0]
        return normalize_git_url(base)

    # GitLab other paths (commits, tree, blob, etc.)
    match = GITLAB_REPO_RE.match(link_url)
    if match:
        return normalize_git_url(match.group(1))

    # GitHub other paths (commits, tree, blob, actions, etc.)
    match = GITHUB_REPO_RE.match(link_url)
    if match:
        slug = match.group(1)
        # Exclude non-repo GitHub pages
        if slug.split("/")[0] in ("orgs", "settings", "marketplace", "topics"):
            return None
        return f"https://github.com/{slug}"

    return None


def _clone_repo(repo_url, clone_dir, ref=None, pr_url=None, dry_run=False):
    """Clone a repo to clone_dir. Returns True on success.

    Delegates to git_pr_reader.py clone which handles fork-aware PR ref
    fallback (refs/pull/N/head, refs/merge-requests/N/head).
    """
    cmd = [
        "python3",
        _git_pr_reader_path(),
        "clone",
        repo_url,
        "--output-dir",
        str(clone_dir),
    ]
    if ref:
        cmd += ["--ref", ref]
    if pr_url:
        cmd += ["--pr-url", pr_url]
    if dry_run:
        cmd += ["--dry-run"]

    result = subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return result.returncode == 0


def _verify_existing_clone(clone_dir, ref=None, expected_repo_url=None, dry_run=False):
    """Verify an existing clone is valid. Optionally checkout a different ref.

    Delegates to git_pr_reader.py clone --verify.
    """
    if dry_run:
        return True

    cmd = ["python3", _git_pr_reader_path(), "clone", "--verify", str(clone_dir)]
    if ref:
        cmd += ["--ref", ref]
    if expected_repo_url:
        cmd += ["--expected-url", expected_repo_url]

    result = subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.returncode == 0


def _write_source_yaml(base_path, repo, ref, dry_run=False):
    """Write source.yaml for workflow resume."""
    if dry_run:
        return
    source_file = Path(base_path) / "source.yaml"
    if source_file.exists():
        return  # Don't overwrite existing config
    lines = [f"repo: {repo}"]
    if ref:
        lines.append(f"ref: {ref}")
    source_file.write_text("\n".join(lines) + "\n")


def _resolve_multiple_prs(pr_urls, base_path, dry_run=False):
    """Resolve and clone repos from a list of PR/MR URLs.

    Groups PRs by repo, clones each into code-repo/<repo_name>/,
    and returns a success result with primary + additional repos.
    """
    # Group PRs by normalized repo URL
    repo_groups = {}
    for url in pr_urls:
        try:
            repo_url, branch = _resolve_pr_info(url)
        except subprocess.CalledProcessError:
            continue
        normalized = normalize_git_url(repo_url)
        if normalized not in repo_groups:
            repo_groups[normalized] = {"repo_url": repo_url, "ref": branch, "urls": []}
        repo_groups[normalized]["urls"].append(url)

    if not repo_groups:
        return {
            "status": "error",
            "message": "Cannot resolve repo from any of the provided PRs.",
        }

    resolved_repos = []
    errors = []
    for _normalized, info in repo_groups.items():
        repo_url = info["repo_url"]
        ref = info["ref"]

        repo_name = repo_name_from_url(repo_url)
        repo_clone_dir = base_path / "code-repo" / repo_name

        if not dry_run:
            if repo_clone_dir.exists():
                if not _verify_existing_clone(repo_clone_dir, ref, expected_repo_url=repo_url):
                    errors.append(f"Existing clone at {repo_clone_dir} is invalid.")
                    continue
            else:
                first_pr = info["urls"][0] if info["urls"] else None
                if not _clone_repo(repo_url, repo_clone_dir, ref, pr_url=first_pr):
                    errors.append(f"Could not clone {repo_url}.")
                    continue

        resolved_repos.append(
            {
                "repo_path": str(repo_clone_dir),
                "repo_url": repo_url,
                "ref": ref,
            }
        )

    if not resolved_repos:
        return {
            "status": "error",
            "message": f"Could not clone any repos. Errors: {'; '.join(errors)}",
        }

    primary = resolved_repos[0]
    _write_source_yaml(base_path, primary["repo_url"], primary["ref"], dry_run=dry_run)

    discovered = {
        normalize_git_url(info["repo_url"]): len(info["urls"]) for info in repo_groups.values()
    }

    result = _success(
        primary["repo_path"],
        repo_url=primary["repo_url"],
        ref=primary["ref"],
        discovered_repos=discovered if len(repo_groups) > 1 else None,
    )
    if len(resolved_repos) > 1:
        result["additional_repos"] = resolved_repos[1:]
    if errors:
        result["warnings"] = errors
    return result


def _success(repo_path, repo_url=None, ref=None, scope=None, discovered_repos=None):
    """Build a success result dict."""
    result = {
        "status": "resolved",
        "repo_path": str(repo_path),
        "repo_url": repo_url,
        "ref": ref,
        "scope": scope,
    }
    if discovered_repos:
        result["discovered_repos"] = discovered_repos
    return result


def _resolve_explicit_repos(repo_values, pr_urls, base_path, dry_run=False):
    """Resolve one or more explicit --repo values.

    Clones each remote repo into code-repo/<repo_name>/.
    For a single repo with PRs, the first PR's branch is checked out.
    Returns primary + additional repos when multiple are given.
    """
    resolved_repos = []
    errors = []

    for i, repo_value in enumerate(repo_values):
        ref = None

        if _is_remote_url(repo_value):
            clone_dir = base_path / "code-repo" / repo_name_from_url(repo_value)

            # First repo gets the PR branch (if any)
            if i == 0 and pr_urls:
                try:
                    _, pr_branch = _resolve_pr_info(pr_urls[0])
                    ref = pr_branch
                except subprocess.CalledProcessError as e:
                    print(
                        f"WARNING: Could not resolve PR branch from {pr_urls[0]}: {e.stderr}",
                        file=sys.stderr,
                    )

            if not dry_run:
                if clone_dir.exists():
                    if not _verify_existing_clone(clone_dir, ref, expected_repo_url=repo_value):
                        errors.append(
                            f"Existing clone at {clone_dir} is invalid"
                            " or points to a different repo."
                        )
                        continue
                else:
                    first_pr = pr_urls[0] if pr_urls else None
                    if not _clone_repo(repo_value, clone_dir, ref, pr_url=first_pr):
                        errors.append(
                            f"Cannot clone {repo_value}."
                            " For private repos, ensure gh"
                            " is authenticated."
                        )
                        continue

            resolved_repos.append(
                {
                    "repo_path": str(clone_dir),
                    "repo_url": repo_value,
                    "ref": ref,
                }
            )
        else:
            local = Path(repo_value)
            if not dry_run and (not local.exists() or not local.is_dir()):
                errors.append(f"Source repo path does not exist: {repo_value}")
                continue
            resolved_repos.append(
                {
                    "repo_path": str(local),
                    "repo_url": None,
                    "ref": None,
                }
            )

    if not resolved_repos:
        return {
            "status": "error",
            "message": f"Could not resolve any repos. Errors: {'; '.join(errors)}",
        }

    primary = resolved_repos[0]
    repo = primary.get("repo_url") or primary["repo_path"]
    _write_source_yaml(base_path, repo, primary["ref"], dry_run=dry_run)

    result = _success(
        primary["repo_path"],
        repo_url=primary.get("repo_url"),
        ref=primary["ref"],
    )
    if len(resolved_repos) > 1:
        result["additional_repos"] = resolved_repos[1:]
    if errors:
        result["warnings"] = errors
    return result


def resolve(args):
    """Main resolution logic. Returns a result dict."""
    dry_run = getattr(args, "dry_run", False)
    base_path = Path(args.base_path)

    # Collect PR URLs from args
    pr_urls = args.pr or []

    # --- Priority 1: Explicit --repo flag ---
    if args.repo:
        return _resolve_explicit_repos(args.repo, pr_urls, base_path, dry_run=dry_run)

    # --- Priority 2: source.yaml ---
    source_config = _read_source_yaml(base_path)
    if source_config and source_config.get("repo"):
        repo_value = source_config["repo"]
        ref = source_config.get("ref")
        scope = source_config.get("scope")

        # PR overrides ref only
        if pr_urls:
            try:
                _, pr_branch = _resolve_pr_info(pr_urls[0])
                ref = pr_branch
            except subprocess.CalledProcessError:
                pass

        if _is_remote_url(repo_value):
            clone_dir = base_path / "code-repo" / repo_name_from_url(repo_value)
            if not dry_run:
                if clone_dir.exists():
                    if not _verify_existing_clone(clone_dir, ref, expected_repo_url=repo_value):
                        return {
                            "status": "error",
                            "message": (
                                f"Existing clone at {clone_dir} is invalid "
                                "or points to a different repo."
                            ),
                        }
                else:
                    first_pr = pr_urls[0] if pr_urls else None
                    if not _clone_repo(repo_value, clone_dir, ref, pr_url=first_pr):
                        return {
                            "status": "error",
                            "message": f"Cannot clone {repo_value}.",
                        }
            return _success(clone_dir, repo_url=repo_value, ref=ref, scope=scope)
        else:
            local = Path(repo_value)
            if not dry_run and (not local.exists() or not local.is_dir()):
                return {
                    "status": "error",
                    "message": f"Source repo path does not exist: {repo_value}",
                }
            return _success(local, repo_url=repo_value, ref=ref, scope=scope)

    # --- Priority 3: PR-derived (--pr without --repo) ---
    if pr_urls:
        return _resolve_multiple_prs(pr_urls, base_path, dry_run=dry_run)

    # --- Priority 4: discovered_repos.json (from requirements step) ---
    discovered = _read_discovered_repos(base_path)
    if discovered:
        result = _resolve_discovered_repos(discovered, base_path, dry_run=dry_run)
        if result["status"] != "no_source":
            return result

    # --- Priority 5: Scan requirements.md for PRs ---
    if args.scan_requirements:
        repos = _scan_requirements_for_prs(base_path)

        if not repos:
            return {"status": "no_source"}

        sorted_repos = sorted(repos.values(), key=len, reverse=True)
        all_pr_urls = [prs[0]["url"] for prs in sorted_repos]
        return _resolve_multiple_prs(all_pr_urls, base_path, dry_run=dry_run)

    # --- Priority 6: No source ---
    return {"status": "no_source"}


def _sync_progress(result, progress_file, skip_deferred_on_no_source=False):
    """Write resolved source info into a workflow progress file.

    On success: records options.source and flips deferred steps to pending.
    On no_source with skip flag: flips deferred steps to skipped.
    Returns the result dict with an added progress_updated field.
    """
    from datetime import datetime, timezone

    with open(progress_file) as f:
        progress = json.load(f)

    options = progress.setdefault("options", {})
    progress_updated = False

    if result["status"] == "resolved":
        options["source"] = {
            "repo_path": result["repo_path"],
            "repo_url": result.get("repo_url"),
            "ref": result.get("ref"),
            "scope": result.get("scope"),
        }
        options["additional_sources"] = result.get("additional_repos", [])
        for step_data in progress.get("steps", {}).values():
            if step_data.get("status") == "deferred":
                step_data["status"] = "pending"
        progress_updated = True
    elif result["status"] == "no_source" and skip_deferred_on_no_source:
        for step_data in progress.get("steps", {}).values():
            if step_data.get("status") == "deferred":
                step_data["status"] = "skipped"
        progress_updated = True

    if progress_updated:
        progress["updated_at"] = (
            datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
        with open(progress_file, "w") as f:
            json.dump(progress, f, indent=2)
            f.write("\n")

    result["progress_updated"] = progress_updated
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Resolve and clone/verify a source code repository"
    )
    parser.add_argument(
        "--base-path",
        required=True,
        help="Base output path (e.g., .agent_workspace/proj-123)",
    )
    parser.add_argument(
        "--repo",
        nargs="+",
        help="Source repo URL(s) or local path(s), space-delimited",
    )
    parser.add_argument(
        "--pr",
        nargs="+",
        help="PR/MR URL(s), space-delimited",
    )
    parser.add_argument(
        "--scan-requirements",
        action="store_true",
        help="Scan requirements.md for PR URLs (post-requirements discovery)",
    )
    parser.add_argument(
        "--progress-file",
        help="Workflow progress JSON file to update with resolved source",
    )
    parser.add_argument(
        "--skip-deferred-on-no-source",
        action="store_true",
        help="Mark deferred steps skipped when no source is found",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check if a source repo can be resolved without cloning or writing files",
    )
    parser.add_argument(
        "--priority",
        choices=["primary", "secondary"],
        default="primary",
        help="Repo priority level (default: primary). Secondary repos skip source.yaml overwrite",
    )
    args = parser.parse_args()

    if args.progress_file:
        try:
            pr_urls = args.pr
            if not pr_urls:
                with open(args.progress_file) as f:
                    progress = json.load(f)
                pr_urls = progress.get("options", {}).get("pr_urls") or None
            resolve_args = argparse.Namespace(
                base_path=args.base_path,
                repo=args.repo,
                pr=pr_urls,
                scan_requirements=args.scan_requirements,
                dry_run=False,
            )
            result = resolve(resolve_args)
            result = _sync_progress(result, args.progress_file, args.skip_deferred_on_no_source)
        except (OSError, json.JSONDecodeError) as e:
            result = {"status": "error", "message": str(e)}
    else:
        result = resolve(args)
        if args.priority == "secondary":
            result["priority"] = "secondary"
        if args.dry_run:
            result["dry_run"] = "true"

    json.dump(result, sys.stdout, indent=2)
    print()

    if result["status"] in ("error", "clone_failed"):
        sys.exit(1)
    elif result["status"] == "no_source":
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
