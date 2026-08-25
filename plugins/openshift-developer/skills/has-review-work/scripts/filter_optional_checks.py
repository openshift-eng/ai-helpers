#!/usr/bin/env python3
"""Filter gh pr checks JSON to actionable (non-optional, non-tide) failures.

Usage:
    filter_optional_checks.py [--annotate] < checks.json

Reads a JSON array of check objects from stdin (gh pr checks --json
name,state,bucket,link). Default: write failing, non-tide, non-optional
checks. `--annotate`: keep optional jobs and add `"optional": true|false`.

A Prow job is optional when its prowjob.json has spec.optional == true
or the label prow.k8s.io/is-optional=true (OpenShift's GCS artifact often
omits spec.optional and only sets the label). Do not use
`gh pr checks --required`: that is GitHub branch protection and omits
Tide-required run_if_changed jobs.

If prowjob.json cannot be fetched, keep the failing check (fail closed).
Non-Prow failures (GitHub Actions, CodeRabbit) are kept.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

FETCH_TIMEOUT = 30
USER_AGENT = "has-review-work/filter-optional-checks"
GCSWEB_PREFIX = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/"
STORAGE_PREFIX = "https://storage.googleapis.com/"
MAX_WORKERS = 8

FetchJson = Callable[[str], dict[str, Any] | None]


def fetch_json(url: str) -> dict[str, Any] | None:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return None


def gcs_path_from_link(link: str) -> str | None:
    """Extract bucket/path from a Prow or gcsweb job URL."""
    if not link:
        return None
    parsed = urlparse(link)
    path = parsed.path.rstrip("/")
    for marker in ("/view/gs/", "/view/gcs/", "/gcs/"):
        if marker in path:
            gcs_path = path.split(marker, 1)[1].strip("/")
            if gcs_path and ".." not in gcs_path.split("/"):
                return gcs_path
    return None


def prowjob_json_urls(link: str) -> list[str]:
    gcs_path = gcs_path_from_link(link)
    if not gcs_path:
        return []
    suffix = f"{gcs_path}/prowjob.json"
    return [GCSWEB_PREFIX + suffix, STORAGE_PREFIX + suffix]


OPTIONAL_LABEL = "prow.k8s.io/is-optional"


def is_optional_prowjob(prowjob: dict[str, Any]) -> bool:
    if prowjob.get("spec", {}).get("optional") is True:
        return True
    labels = prowjob.get("metadata", {}).get("labels") or {}
    return str(labels.get(OPTIONAL_LABEL, "")).lower() == "true"


def check_is_optional(link: str, fetch: FetchJson = fetch_json) -> bool | None:
    """True if optional, False if required Prow job, None if unknown."""
    for url in prowjob_json_urls(link):
        prowjob = fetch(url)
        if prowjob is not None:
            return is_optional_prowjob(prowjob)
    return None


def is_tide(name: str) -> bool:
    return name == "tide" or name.endswith("/tide")


def failing_non_tide(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for check in checks:
        if check.get("bucket") != "fail":
            continue
        name = check.get("name") or ""
        if is_tide(name):
            continue
        candidates.append(check)
    return candidates


def optional_by_link(
    checks: list[dict[str, Any]],
    fetch: FetchJson = fetch_json,
) -> dict[str, bool | None]:
    result: dict[str, bool | None] = {}
    links = {c.get("link") or "" for c in checks}
    links.discard("")
    if not links:
        return result
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(check_is_optional, link, fetch): link for link in links}
        for future in as_completed(futures):
            link = futures[future]
            try:
                result[link] = future.result()
            except Exception as err:
                print(f"WARNING: optional check failed for {link}: {err}", file=sys.stderr)
                result[link] = None
    return result


def check_entry(check: dict[str, Any], optional: bool | None) -> dict[str, Any]:
    entry = {key: check[key] for key in ("name", "state", "bucket", "link") if key in check}
    if optional is not None:
        entry["optional"] = optional is True
    return entry


def annotate_checks(
    checks: list[dict[str, Any]],
    fetch: FetchJson = fetch_json,
) -> list[dict[str, Any]]:
    """Keep failing non-tide checks and set optional from the ProwJob."""
    candidates = failing_non_tide(checks)
    optional_map = optional_by_link(candidates, fetch)
    annotated: list[dict[str, Any]] = []
    for check in candidates:
        link = check.get("link") or ""
        annotated.append(check_entry(check, optional_map.get(link)))
    return annotated


def filter_checks(
    checks: list[dict[str, Any]],
    fetch: FetchJson = fetch_json,
) -> list[dict[str, Any]]:
    """Keep failing, non-tide checks that are not optional Prow jobs."""
    return [
        {key: check[key] for key in ("name", "state", "bucket", "link") if key in check}
        for check in annotate_checks(checks, fetch)
        if not check.get("optional")
    ]


def main() -> int:
    annotate = False
    if len(sys.argv) == 2 and sys.argv[1] == "--annotate":
        annotate = True
    elif len(sys.argv) != 1:
        print(f"Usage: {sys.argv[0]} [--annotate] < checks.json", file=sys.stderr)
        return 2

    raw_stdin = sys.stdin.read()
    try:
        checks = json.loads(raw_stdin)
    except json.JSONDecodeError as err:
        print(f"Error: stdin is not valid JSON: {err}", file=sys.stderr)
        return 1
    if not isinstance(checks, list):
        print("Error: stdin must be a JSON array of checks", file=sys.stderr)
        return 1

    result = annotate_checks(checks) if annotate else filter_checks(checks)
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
