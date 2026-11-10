#!/usr/bin/env python3
"""Show which component commits changed between two release payloads.

Each payload is given as one of:

- a releaseinfo.json file (gather-extra `releaseinfo.json`, or the output of
  `oc adm release info -o json <pullspec>`)
- a per-run build dir from download_timelines.py (reads gather/releaseinfo.json)
- job_name:build_id (downloads that run's gather-extra releaseinfo.json
  anonymously into {output-dir}/{build_id}/gather/)
- a release pullspec (runs `oc adm release info -o json`; without oc the
  exact command is printed)

gather-extra releaseinfo.json describes the payload the cluster ran at the end
of the job: the upgrade target for upgrade jobs. To compare a run's initial
payload, pass its RELEASE_IMAGE_INITIAL pullspec (download_timelines.py prints
it).

For each component (release image tag) the commit comes from
references.spec.tags[].annotations["io.openshift.build.commit.id"] and the
repo from "io.openshift.build.source-location".

Without --component, lists every repo whose commit differs, with the GitHub
compare URL. With --component (a tag name such as
cluster-authentication-operator, or a repo name), also lists the commits and
changed files between the two commits with
`gh api repos/{owner}/{repo}/compare/{old}...{new}`. When gh is missing or
fails, prints that exact command and the compare URL instead.

Usage:
    python3 payload_diff.py <before> <after> [--component NAME] \
        [--output-dir DIR] [--include-vendor] [--format text|json]

Exit status: 0 on success, 1 when a payload could not be read.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.append(_HERE)
from download_timelines import (  # noqa: E402
    GCS_BUCKET, download_file, extract_target, gather_gcs_path,
)

COMMIT_ANNOTATION = "io.openshift.build.commit.id"
SOURCE_ANNOTATION = "io.openshift.build.source-location"
GH_TIMEOUT_SECONDS = 120
OC_TIMEOUT_SECONDS = 300

_RUN_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*:\d{6,}$")
_GITHUB_RE = re.compile(r"github\.com[/:]([^/]+)/([^/.]+?)(?:\.git)?/?$")


class PayloadError(Exception):
    pass


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise PayloadError("cannot read %s: %s" % (path, exc))


def fetch_run_releaseinfo(job, build_id, output_dir):
    """Download a run's prowjob.json (for --target) and gather-extra releaseinfo.json."""
    logs_dir = os.path.join(output_dir, build_id, "logs")
    gather_dir = os.path.join(output_dir, build_id, "gather")
    os.makedirs(logs_dir, exist_ok=True)
    os.makedirs(gather_dir, exist_ok=True)
    prowjob = os.path.join(logs_dir, "prowjob.json")
    if not os.path.isfile(prowjob):
        ok, detail = download_file(
            "gs://%s/logs/%s/%s/prowjob.json" % (GCS_BUCKET, job, build_id), prowjob)
        if not ok:
            raise PayloadError("failed to download prowjob.json for %s: %s" % (build_id, detail))
    target = extract_target(prowjob)
    if not target:
        raise PayloadError("no --target in prowjob.json for %s" % build_id)
    local = os.path.join(gather_dir, "releaseinfo.json")
    ok, detail = download_file(gather_gcs_path(job, build_id, target, "releaseinfo.json"), local)
    if not ok:
        raise PayloadError("failed to download releaseinfo.json for %s: %s" % (build_id, detail))
    return local


def oc_release_info(pullspec):
    """Run `oc adm release info -o json`; raise PayloadError with the command on failure."""
    command = ["oc", "adm", "release", "info", "-o", "json", pullspec]
    printable = " ".join(command)
    if not shutil.which("oc"):
        raise PayloadError("oc not found; run `%s > releaseinfo.json` and pass the file" % printable)
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=OC_TIMEOUT_SECONDS)
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise PayloadError("`%s` failed: %s" % (printable, exc))
    if result.returncode != 0:
        raise PayloadError("`%s` exited %d: %s" % (
            printable, result.returncode, (result.stderr or "").strip()[:300]))
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise PayloadError("`%s` printed invalid JSON: %s" % (printable, exc))


def resolve_payload(ref, output_dir):
    """Return (label, releaseinfo dict) for a file, build dir, job:build_id, or pullspec."""
    if os.path.isfile(ref):
        return ref, load_json(ref)
    if os.path.isdir(ref):
        for candidate in (os.path.join(ref, "gather", "releaseinfo.json"),
                          os.path.join(ref, "releaseinfo.json")):
            if os.path.isfile(candidate):
                return os.path.basename(os.path.normpath(ref)), load_json(candidate)
        raise PayloadError("%s has no gather/releaseinfo.json; run download_timelines.py --gather" % ref)
    if _RUN_REF_RE.match(ref):
        job, build_id = ref.rsplit(":", 1)
        return build_id, load_json(fetch_run_releaseinfo(job, build_id, output_dir))
    if "/" in ref and (":" in ref or "@" in ref):
        return ref, oc_release_info(ref)
    raise PayloadError("%s is not a file, build dir, job:build_id, or pullspec" % ref)


def payload_version(info):
    return ((info.get("metadata") or {}).get("version")
            or (info.get("references", {}).get("metadata") or {}).get("name") or "")


def parse_repo(url):
    """(owner, repo) from a GitHub source-location URL, or None."""
    match = _GITHUB_RE.search(url or "")
    if not match:
        return None
    return match.group(1), match.group(2)


def component_commits(info):
    """tag name -> {commit, source, repo} from references.spec.tags."""
    result = {}
    for tag in (info.get("references", {}).get("spec", {}).get("tags") or []):
        annotations = tag.get("annotations") or {}
        commit = annotations.get(COMMIT_ANNOTATION)
        if not commit:
            continue
        source = annotations.get(SOURCE_ANNOTATION, "")
        repo = parse_repo(source)
        result[tag["name"]] = {
            "commit": commit,
            "source": source,
            "repo": "%s/%s" % repo if repo else None,
        }
    return result


def changed_repos(before, after):
    """Repos whose commit differs, grouped across tags. Sorted by repo."""
    by_repo = {}
    for name in sorted(set(before) | set(after)):
        old = before.get(name, {})
        new = after.get(name, {})
        if old.get("commit") == new.get("commit"):
            continue
        repo = new.get("repo") or old.get("repo") or name
        key = (repo, old.get("commit"), new.get("commit"))
        entry = by_repo.setdefault(key, {
            "repo": repo, "before": old.get("commit"), "after": new.get("commit"), "tags": []})
        entry["tags"].append(name)
    result = sorted(by_repo.values(), key=lambda e: (e["repo"], e["tags"]))
    for entry in result:
        entry["compare_url"] = compare_url(entry["repo"], entry["before"], entry["after"])
    return result


def compare_url(repo, before, after):
    if not repo or "/" not in repo or not before or not after:
        return None
    return "https://github.com/%s/compare/%s...%s" % (repo, before, after)


def select_component(component, before, after):
    """(tag name, before entry, after entry) for a tag name or a repo name."""
    if component in before or component in after:
        return component, before.get(component, {}), after.get(component, {})
    for name in sorted(set(before) | set(after)):
        repo = (after.get(name) or before.get(name) or {}).get("repo") or ""
        if repo.split("/")[-1] == component or repo == component:
            return name, before.get(name, {}), after.get(name, {})
    raise PayloadError("component %s is not a tag or repo in either payload" % component)


def gh_compare_command(repo, before, after):
    return ["gh", "api", "repos/%s/compare/%s...%s" % (repo, before, after)]


def gh_compare(repo, before, after):
    """Run gh api compare. Returns (data, error)."""
    command = gh_compare_command(repo, before, after)
    if not shutil.which("gh"):
        return None, "gh not found"
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=GH_TIMEOUT_SECONDS)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return None, str(exc)
    if result.returncode != 0:
        return None, "exited %d: %s" % (result.returncode, (result.stderr or "").strip()[:300])
    try:
        return json.loads(result.stdout), None
    except ValueError as exc:
        return None, "invalid JSON: %s" % exc


def summarize_compare(data, include_vendor=False):
    """Commits and changed files from a GitHub compare response."""
    commits = []
    for c in data.get("commits") or []:
        commit = c.get("commit") or {}
        commits.append({
            "sha": (c.get("sha") or "")[:10],
            "date": (commit.get("committer") or {}).get("date"),
            "title": (commit.get("message") or "").split("\n", 1)[0],
        })
    files = []
    vendor = 0
    for f in data.get("files") or []:
        name = f.get("filename", "")
        if not include_vendor and (name.startswith("vendor/") or "/vendor/" in name):
            vendor += 1
            continue
        files.append({"status": f.get("status"), "filename": name,
                      "additions": f.get("additions"), "deletions": f.get("deletions")})
    return {
        "status": data.get("status"),
        "ahead_by": data.get("ahead_by"),
        "behind_by": data.get("behind_by"),
        "total_commits": data.get("total_commits"),
        "commits": commits,
        "files": files,
        "vendor_files_hidden": vendor,
    }


def format_text(result):
    lines = ["before: %s (%s)" % (result["before"]["label"], result["before"]["version"] or "?"),
             "after:  %s (%s)" % (result["after"]["label"], result["after"]["version"] or "?"), ""]
    comp = result.get("component")
    if comp:
        lines.append("%s (%s)" % (comp["tag"], comp["repo"] or "repo unknown"))
        lines.append("  before %s" % (comp["before"] or "absent"))
        lines.append("  after  %s" % (comp["after"] or "absent"))
        if comp["before"] == comp["after"]:
            lines.append("  unchanged between the two payloads")
        elif comp.get("compare"):
            cmp = comp["compare"]
            lines.append("  %s commits (status %s, ahead %s, behind %s)%s" % (
                cmp["total_commits"], cmp["status"], cmp["ahead_by"], cmp["behind_by"],
                "; GitHub lists at most 250" if (cmp["total_commits"] or 0) > 250 else ""))
            for c in cmp["commits"]:
                lines.append("    %s %s %s" % (c["sha"], c["date"], c["title"]))
            lines.append("  files (%d%s):" % (
                len(cmp["files"]),
                ", %d vendor/ hidden" % cmp["vendor_files_hidden"] if cmp["vendor_files_hidden"] else ""))
            for f in cmp["files"]:
                lines.append("    %s %s +%s/-%s" % (f["status"], f["filename"], f["additions"], f["deletions"]))
        elif not comp.get("command"):
            lines.append("  cannot compare: a commit or the repo is missing")
        else:
            lines.append("  gh compare unavailable (%s). Run:" % comp.get("compare_error"))
            lines.append("    %s" % " ".join(comp["command"]))
            if comp.get("compare_url"):
                lines.append("  or open %s" % comp["compare_url"])
        return "\n".join(lines)

    changed = result["changed"]
    lines.append("%d repos changed:" % len(changed))
    for c in changed:
        lines.append("  %s %s...%s (%s)" % (
            c["repo"], (c["before"] or "absent")[:10], (c["after"] or "absent")[:10], ", ".join(c["tags"])))
        if c["compare_url"]:
            lines.append("    %s" % c["compare_url"])
    lines.append("")
    lines.append("Rerun with --component <tag or repo> for commits and files.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Component commits changed between two payloads")
    parser.add_argument("before", help="releaseinfo.json, build dir, job:build_id, or pullspec")
    parser.add_argument("after", help="releaseinfo.json, build dir, job:build_id, or pullspec")
    parser.add_argument("--component", help="Release tag or repo name to compare with gh")
    parser.add_argument("--output-dir", default=os.path.join(".work", "disruption-analysis",
                                                             date.today().isoformat()),
                        help="Where job:build_id downloads go (default: .work/disruption-analysis/{today})")
    parser.add_argument("--include-vendor", action="store_true", help="Also list vendor/ files")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    payloads = {}
    for side, ref in (("before", args.before), ("after", args.after)):
        try:
            label, info = resolve_payload(ref, args.output_dir)
        except PayloadError as exc:
            print("Error: %s payload: %s" % (side, exc), file=sys.stderr)
            return 1
        payloads[side] = {"label": label, "version": payload_version(info),
                          "components": component_commits(info)}
        if not payloads[side]["components"]:
            print("Error: %s payload %s has no tags with %s" % (side, label, COMMIT_ANNOTATION),
                  file=sys.stderr)
            return 1

    before, after = payloads["before"]["components"], payloads["after"]["components"]
    result = {
        "before": {"label": payloads["before"]["label"], "version": payloads["before"]["version"]},
        "after": {"label": payloads["after"]["label"], "version": payloads["after"]["version"]},
    }
    if args.component:
        try:
            tag, old, new = select_component(args.component, before, after)
        except PayloadError as exc:
            print("Error: %s" % exc, file=sys.stderr)
            return 1
        repo = new.get("repo") or old.get("repo")
        comp = {"tag": tag, "repo": repo, "before": old.get("commit"), "after": new.get("commit")}
        if comp["before"] and comp["after"] and comp["before"] != comp["after"] and repo:
            comp["command"] = gh_compare_command(repo, comp["before"], comp["after"])
            comp["compare_url"] = compare_url(repo, comp["before"], comp["after"])
            data, error = gh_compare(repo, comp["before"], comp["after"])
            if data is not None:
                comp["compare"] = summarize_compare(data, args.include_vendor)
            else:
                comp["compare_error"] = error
        result["component"] = comp
    else:
        result["changed"] = changed_repos(before, after)

    if args.format == "json":
        json.dump(result, sys.stdout, indent=2)
        print()
    else:
        print(format_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
