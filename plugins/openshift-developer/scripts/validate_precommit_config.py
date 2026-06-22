#!/usr/bin/env python3
"""Validate .pre-commit-config.yaml against a trusted repo whitelist.

Exit codes:
    0 — all repos are trusted
    1 — untrusted repos found (printed to stderr)
    2 — parse error
"""

import sys
import yaml

TRUSTED_REPOS = {
    "https://github.com/pre-commit/pre-commit-hooks": [
        "check-merge-conflict",
        "check-yaml",
        "trailing-whitespace",
    ],
    "https://github.com/leaktk/gitleaks": None,  # all hooks allowed
}


def main():
    try:
        with open(".pre-commit-config.yaml") as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        print(f"ERROR: failed to parse .pre-commit-config.yaml: {e}", file=sys.stderr)
        return 2

    blocked_repos = []
    blocked_hooks = []
    for r in cfg.get("repos", []):
        repo = r.get("repo", "")
        if repo == "local":
            continue
        if repo not in TRUSTED_REPOS:
            blocked_repos.append(repo)
            continue
        allowed_hooks = TRUSTED_REPOS[repo]
        if allowed_hooks is None:
            continue
        for hook in r.get("hooks", []):
            hook_id = hook.get("id", "")
            if hook_id not in allowed_hooks:
                blocked_hooks.append(f"{repo} -> {hook_id}")

    if blocked_repos or blocked_hooks:
        print("ERROR: .pre-commit-config.yaml contains untrusted entries:", file=sys.stderr)
        for b in blocked_repos:
            print(f"  untrusted repo: {b}", file=sys.stderr)
        for b in blocked_hooks:
            print(f"  untrusted hook: {b}", file=sys.stderr)
        print("Local hooks (repo: local) are always allowed.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
