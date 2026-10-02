#!/usr/bin/env python3
"""Shared utilities for release Go version inventory scripts."""

import base64
from concurrent.futures import ThreadPoolExecutor
import json
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

SOURCE = "io.openshift.build.source-location"
BRANCH = "io.openshift.build.commit.ref"
COMMIT = "io.openshift.build.commit.id"
GITHUB_URL = re.compile(
    r"^(?:https://github\.com/|git@github\.com:)([^/]+)/([^/#?]+?)(?:\.git)?/?$"
)
GO_VERSION = re.compile(
    r"(?:^|[/_.:-])(?:go|golang)(?:[-_.]builder)?[-_:]?v?(\d+\.\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_USE_GH = False


class LookupErrorWithContext(Exception):
    """A component lookup failed without invalidating the whole release."""


def oc_json(*args):
    command = ["oc", *args]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return json.loads(result.stdout)
    except FileNotFoundError as exc:
        raise LookupErrorWithContext("oc is not installed") from exc
    except subprocess.CalledProcessError as exc:
        raise LookupErrorWithContext(
            f"{' '.join(command[:4])} failed: {exc.stderr.strip() or exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise LookupErrorWithContext("oc returned invalid JSON") from exc


def _github_json_via_gh(path):
    for attempt in range(4):
        try:
            result = subprocess.run(
                ["gh", "api", path.lstrip("/")],
                check=True, capture_output=True, text=True, timeout=30,
            )
        except FileNotFoundError as exc:
            raise LookupErrorWithContext("gh is not installed") from exc
        except subprocess.TimeoutExpired as exc:
            raise LookupErrorWithContext("gh api timed out") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() or str(exc)
            if re.search(r"HTTP (?:500|502|503|504)\b", detail) and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise LookupErrorWithContext(f"gh api failed: {detail}") from exc
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise LookupErrorWithContext("gh api returned invalid JSON") from exc


def github_json(path):
    global _USE_GH
    url = "https://api.github.com" + path
    if _USE_GH:
        return _github_json_via_gh(path)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "release-go-versions",
    }
    request = urllib.request.Request(url, headers=headers)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                try:
                    data = _github_json_via_gh(path)
                except LookupErrorWithContext as gh_exc:
                    raise LookupErrorWithContext(
                        f"GitHub API HTTP {exc.code}: {url}; {gh_exc}"
                    ) from gh_exc
                _USE_GH = True
                return data
            if exc.code in (500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise LookupErrorWithContext(
                f"GitHub API HTTP {exc.code}: {url}"
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise LookupErrorWithContext(
                f"GitHub API request failed: {url}: {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise LookupErrorWithContext(
                f"GitHub API returned invalid JSON: {url}"
            ) from exc


def github_repo(url):
    match = GITHUB_URL.fullmatch(url)
    if not match:
        raise LookupErrorWithContext(
            f"unsupported source repository: {url or '(missing)'}"
        )
    return f"{match[1]}/{match[2]}"


def image_labels(image):
    data = oc_json("image", "info", image, "-o", "json")
    config = data.get("config") or {}
    labels = {}
    for key in ("container_config", "config"):
        values = config.get(key) or {}
        labels.update(values.get("Labels") or values.get("labels") or {})
    return labels


def source_for_tag(tag, branch_from_image=False):
    annotations = tag.get("annotations") or {}
    source = annotations.get(SOURCE) or annotations.get("vcs-url")
    branch = annotations.get(BRANCH)
    commit = annotations.get(COMMIT)
    need_image = branch_from_image or not source or not branch or not commit
    image = (tag.get("from") or {}).get("name") if need_image else None
    if branch_from_image and not image:
        raise LookupErrorWithContext(
            "component image reference missing from release metadata"
        )
    if image:
        try:
            labels = image_labels(image)
        except LookupErrorWithContext:
            if not source or not (commit or branch):
                raise
        else:
            if branch_from_image:
                branch = labels.get(BRANCH) or branch
                source = labels.get(SOURCE) or labels.get("vcs-url") or source
                commit = labels.get(COMMIT) or commit
            else:
                source = source or labels.get(SOURCE) or labels.get("vcs-url")
                branch = branch or labels.get(BRANCH)
                commit = commit or labels.get(COMMIT)
    if not source:
        raise LookupErrorWithContext(
            "source repository missing from release and image metadata"
        )
    if not commit and not branch:
        raise LookupErrorWithContext(
            "source commit and branch missing from release and image metadata"
        )
    return github_repo(source), branch or "(unknown)", commit or branch


def repository_files(repo, ref):
    """List every blob, splitting a truncated recursive tree into subtrees."""
    def tree_for(treeish, recursive):
        encoded = urllib.parse.quote(treeish, safe="")
        suffix = "?recursive=1" if recursive else ""
        data = github_json(f"/repos/{repo}/git/trees/{encoded}{suffix}")
        if not isinstance(data.get("tree"), list):
            raise LookupErrorWithContext("GitHub tree response has no file list")
        return data

    def scan(item):
        prefix, treeish = item
        data = tree_for(treeish, True)
        if not data.get("truncated"):
            return (
                {prefix + entry["path"] for entry in data["tree"]
                 if entry.get("type") == "blob"},
                [],
            )
        data = tree_for(treeish, False)
        if data.get("truncated"):
            raise LookupErrorWithContext(
                f"GitHub tree is truncated even without recursion at {prefix or '/'}"
            )
        files = {prefix + entry["path"] for entry in data["tree"]
                 if entry.get("type") == "blob"}
        children = [
            (prefix + entry["path"] + "/", entry["sha"])
            for entry in data["tree"] if entry.get("type") == "tree"
        ]
        return files, children

    files = set()
    pending = [("", ref)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        while pending:
            current, pending = pending, []
            for found, children in pool.map(scan, current):
                files.update(found)
                pending.extend(children)
    return files


def file_content(repo, ref, path):
    """Fetch a single file from a GitHub repository at a given ref."""
    encoded_path = urllib.parse.quote(path, safe="/")
    encoded_ref = urllib.parse.quote(ref, safe="")
    data = github_json(f"/repos/{repo}/contents/{encoded_path}?ref={encoded_ref}")
    if data.get("encoding") != "base64" or "content" not in data:
        raise LookupErrorWithContext(f"cannot decode {path} at {ref}")
    try:
        return base64.b64decode(data["content"], validate=False).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise LookupErrorWithContext(f"cannot decode {path} at {ref}") from exc
