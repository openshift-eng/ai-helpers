#!/usr/bin/env python3
"""
Search and retrieve artifacts from Prow CI job runs stored in GCS.

Provides list, search, and fetch operations against the test-platform-results
GCS bucket using the gcloud CLI.

Usage:
    prow_job_artifact_search.py <prow-url> list [subpath]
    prow_job_artifact_search.py <prow-url> search <pattern> [subpath]
    prow_job_artifact_search.py <prow-url> fetch <filepath> [--max-bytes N]

Examples:
    # List top-level artifacts
    prow_job_artifact_search.py <url> list

    # List a specific subdirectory
    prow_job_artifact_search.py <url> list artifacts/e2e-test/openshift-e2e-test

    # Search for files matching a glob pattern (recursive)
    prow_job_artifact_search.py <url> search "**/*intervals*.json"

    # Search within a subdirectory
    prow_job_artifact_search.py <url> search "**/nodes" artifacts/e2e-test/gather-extra

    # Fetch a specific file
    prow_job_artifact_search.py <url> fetch artifacts/e2e-test/build-log.txt

    # Fetch with size limit (default 512KB)
    prow_job_artifact_search.py <url> fetch artifacts/e2e-test/build-log.txt --max-bytes 1048576
"""

import argparse
import json
import os
import re
import subprocess
import sys


BUCKET = "test-platform-results"
DEFAULT_MAX_BYTES = 512 * 1024  # 512KB


def check_gcloud():
    """Verify gcloud CLI is available."""
    try:
        subprocess.run(
            ["gcloud", "version"],
            capture_output=True,
            timeout=10,
        )
    except FileNotFoundError:
        print(
            json.dumps({
                "success": False,
                "error": "gcloud CLI is not installed. Install from: https://cloud.google.com/sdk/docs/install",
            }),
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(
            json.dumps({
                "success": False,
                "error": "gcloud CLI timed out during version check",
            }),
        )
        sys.exit(1)


def parse_prow_url(url):
    """Extract the GCS path prefix from a Prow job URL.

    Accepts either:
      - https://prow.ci.openshift.org/view/gs/test-platform-results/logs/<job>/<build_id>
      - https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/<job>/<build_id>

    Returns the path after the bucket name, e.g.:
      logs/<job>/<build_id>
    """
    # Normalise to just the portion after the bucket name
    patterns = [
        r"prow\.ci\.openshift\.org/view/gs/test-platform-results/(.+?)/?$",
        r"gcsweb-ci\.apps\.ci\.l2s4\.p1\.openshiftapps\.com/gcs/test-platform-results/(.+?)/?$",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1).rstrip("/")

    # Fallback: look for the bucket name anywhere in the URL
    if "test-platform-results/" in url:
        return url.split("test-platform-results/", 1)[1].rstrip("/")

    raise ValueError(
        f"Cannot parse Prow URL: {url}\n"
        "Expected format: https://prow.ci.openshift.org/view/gs/test-platform-results/logs/<job>/<build_id>"
    )


def gcs_path(prefix, subpath=None):
    """Build a gs:// URI."""
    base = f"gs://{BUCKET}/{prefix}"
    if subpath:
        subpath = subpath.strip("/")
        base = f"{base}/{subpath}"
    return base


def run_gcloud(args, timeout=60):
    """Run a gcloud command and return (stdout, stderr, returncode)."""
    cmd = ["gcloud"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", f"Command timed out after {timeout}s", 1


def cmd_list(prefix, subpath=None):
    """List contents of a GCS directory."""
    target = gcs_path(prefix, subpath)
    if not target.endswith("/"):
        target += "/"

    stdout, stderr, rc = run_gcloud(
        ["storage", "ls", target],
        timeout=30,
    )

    if rc != 0:
        return {
            "success": False,
            "error": f"gcloud storage ls failed: {stderr.strip()}",
            "path": target,
        }

    entries = []
    for line in stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip the gs://bucket/ prefix for readability
        full_prefix = f"gs://{BUCKET}/{prefix}/"
        relative = line.replace(full_prefix, "") if line.startswith(full_prefix) else line
        is_dir = line.endswith("/")
        entries.append({
            "name": relative.rstrip("/").split("/")[-1] + ("/" if is_dir else ""),
            "path": relative.rstrip("/"),
            "type": "directory" if is_dir else "file",
            "gcs_uri": line.rstrip("/") + ("/" if is_dir else ""),
        })

    return {
        "success": True,
        "path": target,
        "count": len(entries),
        "entries": entries,
    }


def cmd_search(prefix, pattern, subpath=None):
    """Search for files matching a glob pattern under a GCS path."""
    target = gcs_path(prefix, subpath)
    if not target.endswith("/"):
        target += "/"

    search_pattern = f"{target}{pattern}"

    stdout, stderr, rc = run_gcloud(
        ["storage", "ls", search_pattern],
        timeout=120,
    )

    if rc != 0:
        # gcloud returns non-zero when no matches found
        if "CommandException" in stderr or "One or more URLs matched no objects" in stderr or "matched no objects" in stderr.lower():
            return {
                "success": True,
                "pattern": search_pattern,
                "count": 0,
                "matches": [],
            }
        return {
            "success": False,
            "error": f"gcloud storage ls failed: {stderr.strip()}",
            "pattern": search_pattern,
        }

    matches = []
    full_prefix = f"gs://{BUCKET}/{prefix}/"
    for line in stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        relative = line.replace(full_prefix, "") if line.startswith(full_prefix) else line
        is_dir = line.endswith("/")
        matches.append({
            "name": relative.rstrip("/").split("/")[-1] + ("/" if is_dir else ""),
            "path": relative.rstrip("/"),
            "type": "directory" if is_dir else "file",
            "gcs_uri": line,
        })

    return {
        "success": True,
        "pattern": search_pattern,
        "count": len(matches),
        "matches": matches,
    }


def cmd_fetch(prefix, filepath, max_bytes=DEFAULT_MAX_BYTES):
    """Fetch contents of a specific file from GCS."""
    target = gcs_path(prefix, filepath)

    # Download to a temp file, then read
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".artifact") as tmp:
        tmp_path = tmp.name

    try:
        _stdout, stderr, rc = run_gcloud(
            ["storage", "cp", target, tmp_path, "--no-user-output-enabled"],
            timeout=60,
        )

        if rc != 0:
            return {
                "success": False,
                "error": f"gcloud storage cp failed: {stderr.strip()}",
                "path": target,
            }

        file_size = os.path.getsize(tmp_path)
        truncated = file_size > max_bytes

        with open(tmp_path, "r", errors="replace") as f:
            content = f.read(max_bytes)

        return {
            "success": True,
            "path": target,
            "size_bytes": file_size,
            "truncated": truncated,
            "max_bytes": max_bytes,
            "content": content,
        }
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main():
    parser = argparse.ArgumentParser(
        description="Search and retrieve artifacts from Prow CI job runs in GCS.",
    )
    parser.add_argument(
        "prow_url",
        help="Prow job URL (https://prow.ci.openshift.org/view/gs/...)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    list_parser = subparsers.add_parser("list", help="List directory contents")
    list_parser.add_argument(
        "subpath",
        nargs="?",
        default=None,
        help="Subdirectory path relative to the job root (optional)",
    )

    # search
    search_parser = subparsers.add_parser("search", help="Search for files matching a glob pattern")
    search_parser.add_argument(
        "pattern",
        help='Glob pattern to match (e.g., "**/*intervals*.json", "**/nodes")',
    )
    search_parser.add_argument(
        "subpath",
        nargs="?",
        default=None,
        help="Subdirectory to search within (optional, searches from job root by default)",
    )

    # fetch
    fetch_parser = subparsers.add_parser("fetch", help="Fetch a specific file's contents")
    fetch_parser.add_argument(
        "filepath",
        help="Path to the file relative to the job root",
    )
    fetch_parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help=f"Maximum bytes to read (default: {DEFAULT_MAX_BYTES})",
    )

    args = parser.parse_args()

    check_gcloud()

    try:
        prefix = parse_prow_url(args.prow_url)
    except ValueError as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)

    if args.command == "list":
        result = cmd_list(prefix, args.subpath)
    elif args.command == "search":
        result = cmd_search(prefix, args.pattern, args.subpath)
    elif args.command == "fetch":
        result = cmd_fetch(prefix, args.filepath, args.max_bytes)
    else:
        print(json.dumps({"success": False, "error": f"Unknown command: {args.command}"}))
        sys.exit(1)

    print(json.dumps(result, indent=2))
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
