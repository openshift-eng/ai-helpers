#!/usr/bin/env python3
"""List every pull request that landed between two release payloads.

Asks the release controller for the changelog from one payload to another in
the same stream (one public request, no GitHub access needed):

    https://<arch>.ocp.releases.ci.openshift.org/api/v1/releasestream/<stream>/release/<to>?from=<from>

and prints each updated component with its commits: the PR title (subject),
PR URL, linked Jira issues, and the GitHub compare URL for the component. The
payloads need not be adjacent; every payload in between is covered.

The response is cached under --cache-dir, because the changelog between two
existing payloads never changes.

Usage:
    python3 payload_prs.py 5.0.0-0.nightly-2026-11-07-182718 5.0.0-0.nightly-2026-11-09-184859 \
        [--arch amd64] [--component kube-apiserver] [--format text|json]

Exit status: 0 on success, 1 when the payloads cannot be compared.
"""
import argparse
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

RELEASE_CONTROLLER = "https://%s.ocp.releases.ci.openshift.org/api/v1"
ARCH_HOSTS = {"amd64": "amd64", "arm64": "arm64", "aarch64": "arm64", "ppc64le": "ppc64le",
              "s390x": "s390x", "multi": "multi"}
FETCH_TIMEOUT = 120
_TAG = re.compile(r"^(?P<stream>.+)-(?P<time>\d{4}-\d{2}-\d{2}-\d{6})$")
# Architecture suffixes in a stream name, such as 5.0.0-0.nightly-arm64.
_STREAM_ARCH = re.compile(r"-(arm64|ppc64le|s390x|multi)$")


class ChangelogError(RuntimeError):
    """The changelog could not be fetched or the payloads cannot be compared."""


def parse_tag(tag):
    """(stream, build time) of a payload tag such as 5.0.0-0.nightly-2026-11-09-184859."""
    match = _TAG.match(tag or "")
    if not match:
        raise ChangelogError("%r is not a payload tag like 5.0.0-0.nightly-2026-11-09-184859" % tag)
    return match.group("stream"), match.group("time")


def changelog_url(from_tag, to_tag, arch=None):
    """Release controller changelog URL for from_tag..to_tag. Raises ChangelogError for a bad range."""
    stream_from, time_from = parse_tag(from_tag)
    stream_to, time_to = parse_tag(to_tag)
    if stream_from != stream_to:
        raise ChangelogError("the payloads are in different streams (%s, %s); the release controller only "
                             "compares payloads in one stream" % (stream_from, stream_to))
    if time_from >= time_to:
        raise ChangelogError("%s is not older than %s; pass the older payload first" % (from_tag, to_tag))
    stream_arch = _STREAM_ARCH.search(stream_to)
    host = ARCH_HOSTS.get(arch or (stream_arch.group(1) if stream_arch else "amd64"))
    if not host:
        raise ChangelogError("unknown architecture %r (known: %s)" % (arch, ", ".join(sorted(ARCH_HOSTS))))
    base = RELEASE_CONTROLLER % host
    return "%s/releasestream/%s/release/%s?from=%s" % (
        base, urllib.parse.quote(stream_to), urllib.parse.quote(to_tag), urllib.parse.quote(from_tag))


def fetch_json(url, timeout=FETCH_TIMEOUT):
    """Fetch and decode JSON from url. Raises ChangelogError on HTTP, network, or JSON errors."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise ChangelogError("HTTP %s from the release controller for %s" % (e.code, url))
    except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
        raise ChangelogError("cannot reach the release controller (%s): %s"
                             % (url, getattr(e, "reason", None) or str(e) or type(e).__name__))
    except ValueError as e:
        raise ChangelogError("the release controller returned invalid JSON for %s: %s" % (url, e))


def components(data, only=None):
    """Updated components with their PRs, from a release controller changelog response."""
    changelog = (data or {}).get("changeLogJson") or {}
    wanted = {c.lower() for c in only or []}
    result = []
    for image in changelog.get("updatedImages") or []:
        name = image.get("name", "")
        path = image.get("path", "")
        repo = re.sub(r"^https://github\.com/([^/]+/[^/]+).*$", r"\1", path) if path else ""
        if wanted and name.lower() not in wanted and repo.split("/")[-1].lower() not in wanted:
            continue
        prs = []
        for commit in image.get("commits") or []:
            prs.append({"title": commit.get("subject", ""), "url": commit.get("pullURL", ""),
                        "number": commit.get("pullID"), "issues": sorted((commit.get("issues") or {}).keys())})
        result.append({"component": name, "repo": repo, "compare_url": image.get("fullChangeLog", ""), "prs": prs})
    result.sort(key=lambda c: c["component"])
    return result


def _check_complete(data, from_tag, to_tag):
    """Raise when the changelog does not cover exactly from_tag..to_tag.

    The release controller answers 200 with an empty changeLogJson when generating the
    changelog outlasts its internal wait, which would otherwise read as zero PRs.
    """
    changelog = (data or {}).get("changeLogJson") or {}
    got = ((changelog.get("from") or {}).get("name"), (changelog.get("to") or {}).get("name"))
    if got != (from_tag, to_tag):
        raise ChangelogError("the release controller has not finished the changelog for %s..%s yet; "
                             "retry in a minute" % (from_tag, to_tag))


def load_changelog(from_tag, to_tag, arch=None, cache_dir=None, fetch=None):
    """(changelog, url) for the payload range, from the cache when it holds a finished one."""
    url = changelog_url(from_tag, to_tag, arch)
    fetch = fetch or fetch_json
    cache_path = None
    if cache_dir:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", "%s..%s-%s" % (from_tag, to_tag, arch or "auto"))
        cache_path = os.path.join(cache_dir, "changelog", safe + ".json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path) as f:
                    cached = json.load(f)
                _check_complete(cached, from_tag, to_tag)
                return cached, url
            except (OSError, ValueError, ChangelogError):
                pass
    data = fetch(url)
    _check_complete(data, from_tag, to_tag)
    if cache_path:
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w") as f:
                json.dump(data, f)
        except OSError as e:
            print("Warning: could not cache the changelog at %s: %s" % (cache_path, e), file=sys.stderr)
    return data, url


def print_text(from_tag, to_tag, comps, url, out=None):
    """The PRs per component as plain text."""
    out = out or sys.stdout
    total = sum(len(c["prs"]) for c in comps)
    out.write("PRs from %s to %s: %d in %d component(s)\n" % (from_tag, to_tag, total, len(comps)))
    out.write("Source: %s\n" % url)
    for comp in comps:
        out.write("\n%s (%s) %s\n" % (comp["component"], comp["repo"] or "?", comp["compare_url"]))
        if not comp["prs"]:
            out.write("  (image changed, no PRs listed)\n")
        for pr in comp["prs"]:
            issues = (" [%s]" % ", ".join(pr["issues"])) if pr["issues"] else ""
            out.write("  %s  %s%s\n" % (pr["url"] or "(no PR)", pr["title"], issues))


def main(argv=None):
    """Print the PRs between two payloads, as text or JSON."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("from_tag", help="older payload tag")
    parser.add_argument("to_tag", help="newer payload tag, in the same stream")
    parser.add_argument("--arch", help="architecture (default: from the stream name, else amd64)")
    parser.add_argument("--component", action="append", default=[],
                        help="only this component (release image name or repo name); repeatable")
    parser.add_argument("--cache-dir", default=".work/disruption-analysis/cache")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    try:
        data, url = load_changelog(args.from_tag, args.to_tag, args.arch, args.cache_dir or None)
    except ChangelogError as e:
        print("Error: %s" % e, file=sys.stderr)
        return 1
    comps = components(data, args.component)
    if args.format == "json":
        print(json.dumps({"from": args.from_tag, "to": args.to_tag, "source": url, "components": comps}, indent=2))
    else:
        print_text(args.from_tag, args.to_tag, comps, url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
