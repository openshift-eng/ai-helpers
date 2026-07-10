#!/usr/bin/env python3
"""
Search and retrieve artifacts from Prow CI job runs stored in GCS.

Provides list, search, and fetch operations against the test-platform-results
GCS bucket. The bucket is PUBLIC (no authentication required), so this script
works two ways:

  1. If the `gcloud` CLI is installed, it is used (fast, native globbing).
  2. Otherwise it falls back to the public GCS JSON/download API over plain
     HTTPS via the Python standard library (urllib) — no external tools or
     credentials needed. This keeps the skill usable in minimal containers
     (e.g. CI eval images) that do not ship the Cloud SDK.

Both backends produce identical JSON output, so callers do not need to know or
care which one ran. Set PROW_ARTIFACT_SEARCH_NO_GCLOUD=1 to force the HTTP
fallback even when gcloud is present.

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
import urllib.error
import urllib.parse
import urllib.request


BUCKET = "test-platform-results"
DEFAULT_MAX_BYTES = 512 * 1024  # 512KB

# Public GCS endpoints (no auth — the bucket is world-readable).
GCS_API_ROOT = "https://storage.googleapis.com/storage/v1/b"
GCS_DOWNLOAD_ROOT = "https://storage.googleapis.com"
HTTP_TIMEOUT = 60
HTTP_HEADERS = {"User-Agent": "prow-job-artifact-search/1.0"}
# Upper bound for a single fetch when the object size is not advertised via a
# Content-Length header (GCS uses decompressive transcoding for gzip-stored
# text and streams it without a length). 64 MiB is far larger than any text
# artifact this tool is used to read, while still bounding memory use.
FETCH_READ_CAP = 64 * 1024 * 1024
# Safety cap for paginated listings (1000 pages * 1000 objects = 1M objects).
# Real jobs have at most a few thousand objects, so this is effectively
# unreachable; it only guards against a runaway pagination loop.
MAX_LIST_PAGES = 1000

_GCLOUD_AVAILABLE = None


def gcloud_available():
    """Return True if the gcloud CLI is usable, caching the result.

    Honors PROW_ARTIFACT_SEARCH_NO_GCLOUD=1 to force the HTTP fallback.
    """
    global _GCLOUD_AVAILABLE
    if _GCLOUD_AVAILABLE is not None:
        return _GCLOUD_AVAILABLE

    if os.environ.get("PROW_ARTIFACT_SEARCH_NO_GCLOUD"):
        _GCLOUD_AVAILABLE = False
        return _GCLOUD_AVAILABLE

    try:
        result = subprocess.run(
            ["gcloud", "version"],
            capture_output=True,
            timeout=10,
        )
        _GCLOUD_AVAILABLE = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        _GCLOUD_AVAILABLE = False
    return _GCLOUD_AVAILABLE


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


def object_path(prefix, subpath=None):
    """Build a bucket-relative object path (no gs:// or bucket name)."""
    path = prefix.strip("/")
    if subpath:
        path = f"{path}/{subpath.strip('/')}"
    return path


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


# ---------------------------------------------------------------------------
# Public GCS HTTP backend (used when gcloud is unavailable)
# ---------------------------------------------------------------------------


def _http_get_json(url):
    """GET a URL and parse the JSON body."""
    req = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def gcs_api_list(obj_prefix, delimiter=None):
    """List objects under obj_prefix via the public GCS JSON API.

    Follows pagination. Returns (items, prefixes) where:
      - items    is a list of full object-name strings under obj_prefix
      - prefixes is a list of immediate sub-directory prefixes (only populated
        when delimiter="/" is passed)
    """
    items = []
    prefixes = []
    page_token = None
    pages = 0
    base = f"{GCS_API_ROOT}/{BUCKET}/o"
    while True:
        params = {"prefix": obj_prefix, "maxResults": "1000"}
        if delimiter:
            params["delimiter"] = delimiter
        if page_token:
            params["pageToken"] = page_token
        data = _http_get_json(f"{base}?{urllib.parse.urlencode(params)}")
        for item in data.get("items", []):
            name = item.get("name")
            if name is not None:
                items.append(name)
        prefixes.extend(data.get("prefixes", []))
        page_token = data.get("nextPageToken")
        pages += 1
        if not page_token or pages >= MAX_LIST_PAGES:
            break
    return items, prefixes


def glob_to_regex(pattern):
    """Translate a gcloud/gsutil-style glob into an anchored regex.

    Mirrors gsutil wildcard semantics:
      - ``*``   matches any run of characters within a single path segment
                (does not cross ``/``)
      - ``**``  matches across path segments (any depth)
      - ``**/`` matches zero or more complete path segments
      - ``?``   matches a single non-``/`` character
    """
    out = ["^"]
    i, n = 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                if i + 2 < n and pattern[i + 2] == "/":
                    out.append("(?:.*/)?")  # **/ -> zero or more segments
                    i += 3
                else:
                    out.append(".*")  # ** -> across segments
                    i += 2
            else:
                out.append("[^/]*")  # * -> within a segment
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    out.append("$")
    return "".join(out)


def _http_list_lines(prefix, subpath=None):
    """Return gcloud-ls-style ``gs://`` lines for a directory listing."""
    obj_prefix = object_path(prefix, subpath)
    if not obj_prefix.endswith("/"):
        obj_prefix += "/"

    items, prefixes = gcs_api_list(obj_prefix, delimiter="/")

    lines = []
    for pfx in prefixes:  # sub-directories already carry a trailing slash
        lines.append(f"gs://{BUCKET}/{pfx}")
    for name in items:
        if name == obj_prefix:
            continue  # skip the directory placeholder object, if any
        lines.append(f"gs://{BUCKET}/{name}")
    return sorted(set(lines))


def _http_search_lines(prefix, pattern, subpath=None):
    """Return gcloud-ls-style ``gs://`` lines for a recursive glob search.

    Matches leaf objects (files) whose path relative to the search root matches
    the glob, mirroring ``gcloud storage ls "<root>/<pattern>"``. Directory
    placeholder objects are skipped: gcloud's wildcard ``ls`` does not return
    bare directories for these patterns, and callers use ``list`` to browse
    directories.
    """
    search_root = object_path(prefix, subpath)
    if not search_root.endswith("/"):
        search_root += "/"

    items, _ = gcs_api_list(search_root, delimiter=None)
    regex = re.compile(glob_to_regex(pattern))

    lines = set()
    for name in items:
        if not name.startswith(search_root):
            continue
        rel = name[len(search_root):]
        if not rel or rel.endswith("/"):
            continue  # skip the search root itself and directory placeholders
        if regex.match(rel):
            lines.add(f"gs://{BUCKET}/{name}")
    return sorted(lines)


def _http_fetch(obj_path, max_bytes):
    """Download an object's content via the public download API.

    Returns (size_bytes, truncated, content). ``size_bytes`` is the object's
    full size (from Content-Length when available); ``content`` holds at most
    ``max_bytes`` decoded characters.
    """
    url = f"{GCS_DOWNLOAD_ROOT}/{BUCKET}/{urllib.parse.quote(obj_path)}"
    req = urllib.request.Request(url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        content_length = resp.headers.get("Content-Length")
        size_bytes = None
        if content_length is not None:
            try:
                size_bytes = int(content_length)
            except ValueError:
                size_bytes = None

        if size_bytes is not None:
            # Size is known up front — only pull what we need for the content.
            data = resp.read(max_bytes)
        else:
            # No Content-Length (e.g. gzip decompressive transcoding streams the
            # decoded body without a length). Read the full body — bounded by a
            # safety cap — so size_bytes and truncation are accurate. This mirrors
            # gcloud, which downloads the whole object before reading it.
            data = resp.read(FETCH_READ_CAP + 1)
            size_bytes = len(data)

    truncated = size_bytes > max_bytes
    content = data[:max_bytes].decode("utf-8", errors="replace")
    return size_bytes, truncated, content


# ---------------------------------------------------------------------------
# Commands (backend-agnostic: identical JSON output either way)
# ---------------------------------------------------------------------------


def cmd_list(prefix, subpath=None):
    """List contents of a GCS directory."""
    target = gcs_path(prefix, subpath)
    if not target.endswith("/"):
        target += "/"

    if gcloud_available():
        stdout, stderr, rc = run_gcloud(["storage", "ls", target], timeout=30)
        if rc != 0:
            return {
                "success": False,
                "error": f"gcloud storage ls failed: {stderr.strip()}",
                "path": target,
            }
        lines = [ln.strip() for ln in stdout.strip().splitlines() if ln.strip()]
    else:
        try:
            lines = _http_list_lines(prefix, subpath)
        except urllib.error.HTTPError as e:
            return {
                "success": False,
                "error": f"GCS API list failed: HTTP {e.code} {e.reason}",
                "path": target,
            }
        except (urllib.error.URLError, OSError, ValueError) as e:
            return {
                "success": False,
                "error": f"GCS API list failed: {e}",
                "path": target,
            }

    entries = []
    full_prefix = f"gs://{BUCKET}/{prefix}/"
    for line in lines:
        # Strip the gs://bucket/ prefix for readability
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

    if gcloud_available():
        stdout, stderr, rc = run_gcloud(["storage", "ls", search_pattern], timeout=120)
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
        lines = [ln.strip() for ln in stdout.strip().splitlines() if ln.strip()]
    else:
        try:
            lines = _http_search_lines(prefix, pattern, subpath)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {
                    "success": True,
                    "pattern": search_pattern,
                    "count": 0,
                    "matches": [],
                }
            return {
                "success": False,
                "error": f"GCS API search failed: HTTP {e.code} {e.reason}",
                "pattern": search_pattern,
            }
        except (urllib.error.URLError, OSError, ValueError) as e:
            return {
                "success": False,
                "error": f"GCS API search failed: {e}",
                "pattern": search_pattern,
            }

    matches = []
    full_prefix = f"gs://{BUCKET}/{prefix}/"
    for line in lines:
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

    if gcloud_available():
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
    else:
        try:
            size_bytes, truncated, content = _http_fetch(object_path(prefix, filepath), max_bytes)
        except urllib.error.HTTPError as e:
            return {
                "success": False,
                "error": f"GCS download failed: HTTP {e.code} {e.reason}",
                "path": target,
            }
        except (urllib.error.URLError, OSError, ValueError) as e:
            return {
                "success": False,
                "error": f"GCS download failed: {e}",
                "path": target,
            }

        return {
            "success": True,
            "path": target,
            "size_bytes": size_bytes,
            "truncated": truncated,
            "max_bytes": max_bytes,
            "content": content,
        }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Search and retrieve artifacts from Prow CI job runs in GCS. "
            "Uses the gcloud CLI when available, otherwise falls back to the "
            "public GCS HTTP API (no auth or extra tooling required)."
        ),
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
