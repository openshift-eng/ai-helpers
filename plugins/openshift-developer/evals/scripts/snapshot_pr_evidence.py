#!/usr/bin/env python3
"""Freeze a pull request's risk-assessment evidence into an eval case input.

Writes the evidence an automated caller hands the pr-risk-assessment skill:
the PR's title and description, its base branch and commits, and its changed
files with their patches. Vendored and generated files are listed without a
patch, and the smallest remaining patches are kept first within a character
budget, so a large PR is shown as partly unreadable exactly as the chai-bot
`prepare_pr_risk_assessment` tool shows it.

Labels, comments, reviews, and the author are left out: they can reveal the
tier the case expects. Review the description for people's names before
committing the snapshot.

Usage:
    snapshot_pr_evidence.py https://github.com/<org>/<repo>/pull/<n> <case-dir>
"""

import argparse
import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_BUDGET = 300_000

DEPENDENCY_MANIFESTS = {
    "go.mod",
    "go.sum",
    "go.work",
    "go.work.sum",
    "package-lock.json",
    "yarn.lock",
    "Cargo.lock",
    "poetry.lock",
    "Pipfile.lock",
    "requirements.txt",
}


def gh_api(path, paginate=False):
    cmd = ["gh", "api", path]
    if paginate:
        cmd.insert(2, "--paginate")
        cmd += ["--jq", ".[]"]
        out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
        return [json.loads(line) for line in out.splitlines() if line.strip()]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def classify(path):
    """The kind of file a changed path is (same rules as chai-bot's evidence)."""
    name = posixpath.basename(path)
    directories = path.split("/")[:-1]
    lower = path.lower()
    if "vendor" in directories or (directories and directories[0] == "third_party"):
        return "vendored"
    if name.startswith("zz_generated") or name.endswith(
        (".pb.go", ".pb.gw.go", "_generated.go", "bindata.go")
    ):
        return "generated"
    if "generated" in directories:
        return "generated"
    if name in DEPENDENCY_MANIFESTS:
        return "dependencies"
    if lower.endswith((".yaml", ".yml", ".json")) and (
        "crd" in lower or "customresourcedefinition" in lower
    ):
        return "crd_manifest"
    is_go = name.endswith(".go") and not name.endswith("_test.go")
    if is_go and (
        name == "types.go"
        or name.startswith("types_")
        or name.endswith("_types.go")
        or {"api", "apis"} & set(directories)
    ):
        return "api_types"
    if name.endswith(("_test.go", "_test.py", ".spec.ts", ".test.ts", ".test.tsx")) or name.startswith(
        "test_"
    ):
        return "tests"
    if {"test", "tests", "e2e", "testdata"} & set(directories):
        return "tests"
    if name.endswith((".md", ".adoc", ".rst")) or name in {"LICENSE", "OWNERS", "OWNERS_ALIASES", "NOTICE"}:
        return "docs"
    if {"docs", "doc", "enhancements"} & set(directories):
        return "docs"
    if name in {"Makefile", ".ci-operator.yaml"} or name.startswith(("Dockerfile", "Containerfile")):
        return "build"
    if name.endswith(".mk") or path.startswith((".tekton/", ".github/")):
        return "build"
    return "code"


def evidence_files(files, budget):
    """Files with as many patches as fit ``budget``; vendored and generated never."""
    kept = ("filename", "previous_filename", "status", "additions", "deletions")
    evidence = [
        {k: f[k] for k in kept if k in f} | {"kind": classify(f["filename"])} for f in files
    ]
    readable = sorted(
        (i for i, item in enumerate(evidence) if item["kind"] not in {"vendored", "generated"}),
        key=lambda i: len(files[i].get("patch") or ""),
    )
    used, complete = 0, True
    for index in readable:
        patch = files[index].get("patch")
        if not isinstance(patch, str):
            # GitHub omits the patch of binary or very large files.
            evidence[index]["patch_omitted"] = "not provided by GitHub"
            complete = False
            continue
        if used + len(patch) > budget:
            evidence[index]["patch_omitted"] = "evidence budget"
            complete = False
            continue
        evidence[index]["patch"] = patch
        used += len(patch)
    return evidence, complete


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pr_url")
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="patch characters (default %(default)s)")
    args = parser.parse_args()

    match = re.fullmatch(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)/?", args.pr_url)
    if not match:
        sys.exit(f"not a GitHub pull request URL: {args.pr_url}")
    org, repo, number = match.groups()
    full = f"{org}/{repo}"

    pr = gh_api(f"repos/{full}/pulls/{number}")
    files = gh_api(f"repos/{full}/pulls/{number}/files?per_page=100", paginate=True)
    # The fork point of the head from the base branch as the PR last saw it.
    compare = gh_api(f"repos/{full}/compare/{pr['base']['sha']}...{pr['head']['sha']}")
    evidence, complete = evidence_files(files, args.budget)

    snapshot = {
        "pr_url": args.pr_url.rstrip("/"),
        "repo": full,
        "pr_number": int(number),
        "base_branch": pr["base"]["ref"],
        "base_sha": compare["merge_base_commit"]["sha"],
        "head_sha": pr["head"]["sha"],
        "title": pr["title"],
        "body": pr.get("body") or "",
        "draft": bool(pr.get("draft")),
        "files_listed": pr["changed_files"],
        "diff_complete": complete and pr["changed_files"] == len(files),
        "files": evidence,
    }
    args.case_dir.mkdir(parents=True, exist_ok=True)
    out = args.case_dir / "input.json"
    out.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    shown = sum(1 for f in evidence if "patch" in f)
    print(f"{out}: {len(evidence)} files ({shown} with patches), diff_complete={snapshot['diff_complete']}")


if __name__ == "__main__":
    main()
