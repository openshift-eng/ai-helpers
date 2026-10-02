#!/usr/bin/env python3
"""Report declared Go module or Go language versions across a release payload."""

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


SOURCE = "io.openshift.build.source-location"
BRANCH = "io.openshift.build.commit.ref"
COMMIT = "io.openshift.build.commit.id"
GITHUB_URL = re.compile(r"^(?:https://github\.com/|git@github\.com:)([^/]+)/([^/#?]+?)(?:\.git)?/?$")
MODULE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._~+/-]*$")
GITHUB_USE_GH = False


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


def github_json_via_gh(path):
    """Reuse gh's existing GitHub access without reading or handling a token."""
    for attempt in range(4):
        try:
            result = subprocess.run(
                ["gh", "api", path.lstrip("/")], check=True, capture_output=True,
                text=True, timeout=30
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
    global GITHUB_USE_GH
    url = "https://api.github.com" + path
    if GITHUB_USE_GH:
        return github_json_via_gh(path)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "release-go-module-versions"}
    request = urllib.request.Request(url, headers=headers)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                try:
                    data = github_json_via_gh(path)
                except LookupErrorWithContext as gh_exc:
                    raise LookupErrorWithContext(
                        f"GitHub API HTTP {exc.code}: {url}; {gh_exc}"
                    ) from gh_exc
                GITHUB_USE_GH = True
                return data
            if exc.code in (500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise LookupErrorWithContext(f"GitHub API HTTP {exc.code}: {url}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise LookupErrorWithContext(f"GitHub API request failed: {url}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise LookupErrorWithContext(f"GitHub API returned invalid JSON: {url}") from exc


def github_repo(url):
    match = GITHUB_URL.fullmatch(url)
    if not match:
        raise LookupErrorWithContext(f"unsupported source repository: {url or '(missing)'}")
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
    if branch_from_image:
        image = (tag.get("from") or {}).get("name")
        if not image:
            raise LookupErrorWithContext("component image reference missing from release metadata")
        try:
            labels = image_labels(image)
        except LookupErrorWithContext:
            if not source or not (commit or branch):
                raise
        else:
            branch = labels.get(BRANCH) or branch
            source = labels.get(SOURCE) or labels.get("vcs-url") or source
            commit = labels.get(COMMIT) or commit
    elif not source or not branch or not commit:
        image = (tag.get("from") or {}).get("name")
        if image:
            try:
                labels = image_labels(image)
            except LookupErrorWithContext:
                if not source or not (branch or commit):
                    raise
            else:
                source = source or labels.get(SOURCE) or labels.get("vcs-url")
                branch = branch or labels.get(BRANCH)
                commit = commit or labels.get(COMMIT)
    if not source:
        raise LookupErrorWithContext("source repository missing from release and image metadata")
    if not commit and not branch:
        raise LookupErrorWithContext("source commit and branch missing from release and image metadata")
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
            return ({prefix + entry["path"] for entry in data["tree"]
                     if entry.get("type") == "blob"}, [])
        data = tree_for(treeish, False)
        if data.get("truncated"):
            raise LookupErrorWithContext(
                f"GitHub tree is truncated even without recursion at {prefix or '/'}"
            )
        files = {prefix + entry["path"] for entry in data["tree"]
                 if entry.get("type") == "blob"}
        children = [(prefix + entry["path"] + "/", entry["sha"])
                    for entry in data["tree"] if entry.get("type") == "tree"]
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


def module_files(repo, ref):
    return sorted(path for path in repository_files(repo, ref)
                  if path.split("/")[-1] == "go.mod")


def module_content(repo, ref, path):
    encoded_path = urllib.parse.quote(path, safe="/")
    encoded_ref = urllib.parse.quote(ref, safe="")
    data = github_json(f"/repos/{repo}/contents/{encoded_path}?ref={encoded_ref}")
    if data.get("encoding") != "base64" or "content" not in data:
        raise LookupErrorWithContext(f"cannot decode {path} at {ref}")
    try:
        return base64.b64decode(data["content"], validate=False).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise LookupErrorWithContext(f"cannot decode {path} at {ref}") from exc


def declared_version(content, module):
    """Find a required module's version, accounting for matching replacements."""
    required = None
    replacements = {}
    in_block = None
    for raw_line in content.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        parts = line.split()
        if len(parts) == 2 and parts[0] in ("require", "replace") and parts[1] == "(":
            in_block = parts[0]
            continue
        if in_block and parts == [")"]:
            in_block = None
            continue
        if in_block:
            kind = in_block
        else:
            if not parts or parts[0] not in ("require", "replace"):
                continue
            kind, parts = parts[0], parts[1:]
        if kind == "require" and len(parts) == 2 and parts[0] == module:
            required = parts[1]
        elif kind == "replace" and parts and parts[0] == module and "=>" in parts:
            arrow = parts.index("=>")
            source, target = parts[:arrow], parts[arrow + 1:]
            if len(source) in (1, 2) and len(target) in (1, 2):
                source_version = source[1] if len(source) == 2 else None
                replacements[source_version] = " ".join(target)
    if required is None:
        return None
    replacement = replacements.get(required, replacements.get(None))
    if replacement is None:
        return required
    target = replacement.split()
    if len(target) == 2 and target[0] == module:
        replacement = target[1]
    return f"{replacement} (replaced)"


def declared_go_version(content):
    """Find the go directive in a go.mod, ignoring comments and toolchain."""
    for raw_line in content.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        parts = line.split()
        if len(parts) == 2 and parts[0] == "go":
            return parts[1]
    return None


def inspect_release(release, module, go_version=False, on_result=None):
    tags = ((release.get("references") or {}).get("spec") or {}).get("tags") or []
    if not tags:
        raise LookupErrorWithContext("release contains no component images")
    cache = {}
    version_cache = {}
    results = []

    def record(row):
        results.append(row)
        if on_result:
            on_result(row)

    for tag in tags:
        name = tag.get("name") or "(unnamed)"
        image = (tag.get("from") or {}).get("name") or "(missing image)"
        repo = branch = ref = "(unknown)"
        try:
            if image == "(missing image)":
                raise LookupErrorWithContext("component image reference missing from release metadata")
            repo, branch, ref = source_for_tag(tag, branch_from_image=True)
            key = (repo, ref)
            if key not in cache:
                cache[key] = module_files(repo, ref)
            files = cache[key]
            if not files:
                record((name, image, repo, branch, ref, "(none)", "no go.mod files"))
                continue
            found = False
            file_errors = False
            for path in files:
                try:
                    version_key = (repo, ref, path)
                    if version_key not in version_cache:
                        content = module_content(repo, ref, path)
                        version_cache[version_key] = (
                            declared_go_version(content) if go_version else declared_version(content, module)
                        )
                    version = version_cache[version_key]
                except LookupErrorWithContext as exc:
                    file_errors = True
                    record((name, image, repo, branch, ref, path, f"error: {path}: {exc}"))
                    continue
                if go_version:
                    record((name, image, repo, branch, ref, path,
                            version or "go directive absent"))
                elif version:
                    found = True
                    record((name, image, repo, branch, ref, path, version))
            if not go_version and not found and not file_errors:
                record((name, image, repo, branch, ref, "(none)", "package absent from all go.mod files"))
        except LookupErrorWithContext as exc:
            record((name, image, repo, branch, ref, "(unavailable)", f"error: {exc}"))
    return results


def format_result(row):
    return "\t".join((row[0], row[2], row[6]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_image", help="OpenShift release image pullspec")
    parser.add_argument("module", nargs="?", help="exact Go module path, e.g. google.golang.org/protobuf")
    parser.add_argument("--go-version", action="store_true", help="report each go.mod's go directive instead of a module version")
    args = parser.parse_args(argv)
    if args.go_version and args.module:
        parser.error("provide either a module or --go-version, not both")
    if not args.go_version and not args.module:
        parser.error("provide a module or --go-version")
    if args.module and not MODULE.fullmatch(args.module):
        parser.error("module must be an exact Go module path")

    try:
        print("Reading release metadata...", file=sys.stderr, flush=True)
        release = oc_json("adm", "release", "info", args.release_image, "-o", "json")
        print("component\trepository\tgo version/status" if args.go_version
              else "component\trepository\tmodule version/status", flush=True)
        rows = inspect_release(
            release, args.module, go_version=args.go_version,
            on_result=lambda row: print(format_result(row), flush=True),
        )
    except LookupErrorWithContext as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1 if any(row[-1].startswith("error:") for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
