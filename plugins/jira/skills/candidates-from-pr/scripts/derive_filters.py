#!/usr/bin/env python3
"""Derive component(s) and target release for a PR.

Reads PR JSON (fetch_pr.py output) on stdin and writes a JSON object with
derived filters. Pure local logic — no API calls. When the base ref is
`main`/`master` the target_release is left null with source="needs_lookup",
signalling the skill caller to query Jira project versions.

Usage:
    fetch_pr.py ... | derive_filters.py \
        [--component "Networking / ovn-kubernetes" ...] \
        [--target-release X.Y]

Output:
    {
      "components": ["..."],
      "component_source": "auto" | "override" | "path-heuristic" | "none",
      "target_release": "4.18" | null,
      "target_release_source": "override" | "base_ref" | "needs_lookup" | "unknown",
      "warnings": ["..."]
    }
"""

from __future__ import annotations

import argparse
import json
import re
import sys

# Repo (org/name) -> default component(s).
REPO_COMPONENTS: dict[str, list[str]] = {
    "openshift/ovn-kubernetes": ["Networking / ovn-kubernetes"],
    "openshift/cluster-network-operator": ["Networking / cluster-network-operator"],
    "openshift/sdn": ["Networking / openshift-sdn"],
    "openshift/cluster-ingress-operator": ["Networking / router"],
    "openshift/hypershift": ["HyperShift"],
    "openshift/cluster-version-operator": ["Cluster Version Operator"],
}

# Path-prefix heuristics applied if no repo mapping exists.
PATH_HEURISTICS: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"^pkg/network/"), ["Networking"]),
    (re.compile(r"^pkg/operator/"), ["Operator"]),
]

RELEASE_BRANCH_RE = re.compile(r"^release[-/](\d+\.\d+)$")
DEV_BRANCHES = {"main", "master"}


def derive_components(
    org: str,
    repo: str,
    files: list[dict],
    overrides: list[str],
) -> tuple[list[str], str, list[str]]:
    warnings: list[str] = []
    if overrides:
        return overrides, "override", warnings

    slug = f"{org}/{repo}"
    if slug in REPO_COMPONENTS:
        return REPO_COMPONENTS[slug], "auto", warnings

    paths = [f.get("path", "") for f in files]
    matched: list[str] = []
    for pattern, comps in PATH_HEURISTICS:
        if any(pattern.search(p) for p in paths):
            for c in comps:
                if c not in matched:
                    matched.append(c)
    if matched:
        warnings.append(
            f"no repo mapping for {slug}; derived components from file paths"
        )
        return matched, "path-heuristic", warnings

    warnings.append(
        f"no component mapping known for {slug}; JQL will omit component filter"
    )
    return [], "none", warnings


def derive_target_release(
    base_ref: str, override: str | None
) -> tuple[str | None, str, list[str]]:
    if override:
        return override, "override", []
    m = RELEASE_BRANCH_RE.match(base_ref or "")
    if m:
        return m.group(1), "base_ref", []
    if base_ref in DEV_BRANCHES:
        return None, "needs_lookup", []
    return (
        None,
        "unknown",
        [
            f"could not derive target release from base ref '{base_ref}'; "
            "skill caller should pass --target-release or skip version filter"
        ],
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--component", action="append", default=[])
    p.add_argument("--target-release", default=None)
    args = p.parse_args()

    pr = json.load(sys.stdin)

    components, csrc, cwarn = derive_components(
        pr.get("org", ""), pr.get("repo", ""), pr.get("files") or [], args.component
    )
    release, rsrc, rwarn = derive_target_release(
        pr.get("base_ref", ""), args.target_release
    )

    json.dump(
        {
            "components": components,
            "component_source": csrc,
            "target_release": release,
            "target_release_source": rsrc,
            "warnings": cwarn + rwarn,
        },
        sys.stdout,
    )
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
