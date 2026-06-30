#!/usr/bin/env python3
"""
Check if a GitHub user is authorized to trigger review agent responses.

Authorized authors are:
1. Approved bots (coderabbitai)
2. Users listed in OWNERS or OWNERS_ALIASES
3. Members of the repository's GitHub organization (fallback)

Usage:
    check_authorized.py <owner> <repo> <login>

Returns:
    Exit 0: Authorized
    Exit 1: Not authorized
    Exit 2: Error occurred

Output:
    JSON with authorization result and reason.
"""

import json
import subprocess
import sys
from typing import Any

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

GH_TIMEOUT = 30

APPROVED_BOTS = [
    "coderabbitai",
    "coderabbitai[bot]",
]

IGNORED_ACCOUNTS = [
    "openshift-ci-robot",
    "openshift-ci",
    "openshift-merge-robot",
    "openshift-bot",
]


def run_gh(args: list[str]) -> str:
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
        check=True,
        timeout=GH_TIMEOUT,
    )
    return result.stdout


def _parse_simple_yaml_list(content: str, key: str) -> list[str]:
    result = []
    in_key = False
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith(f"{key}:"):
            in_key = True
            continue
        if in_key:
            if stripped.startswith("- "):
                result.append(stripped[2:].strip())
            elif stripped and not stripped.startswith("#") and ":" in stripped:
                in_key = False
    return result


def _parse_simple_yaml_aliases(content: str) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    current_alias = None
    in_aliases = False

    for line in content.split("\n"):
        stripped = line.rstrip()
        if stripped.startswith("aliases:"):
            in_aliases = True
            continue
        if not in_aliases:
            continue
        if stripped and not stripped.startswith(" ") and not stripped.startswith("\t"):
            break

        stripped = stripped.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.endswith(":") and not stripped.startswith("- "):
            current_alias = stripped[:-1].strip()
            aliases[current_alias] = []
        elif stripped.startswith("- ") and current_alias:
            aliases[current_alias].append(stripped[2:].strip())

    return aliases


class OwnersLookupError(Exception):
    pass


def get_authorized_users(owner: str, repo: str) -> set[str]:
    authorized: set[str] = set(APPROVED_BOTS)
    aliases: dict[str, list[str]] = {}
    errors: list[str] = []

    try:
        content = run_gh([
            "api", "-H", "Accept: application/vnd.github.raw",
            f"repos/{owner}/{repo}/contents/OWNERS_ALIASES",
        ])
        if HAS_YAML:
            data = yaml.safe_load(content)
            if data and "aliases" in data:
                aliases = data["aliases"]
        else:
            aliases = _parse_simple_yaml_aliases(content)

        for members in aliases.values():
            authorized.update(members)
    except subprocess.CalledProcessError as e:
        if "404" in (e.stderr or ""):
            print(f"Info: No OWNERS_ALIASES file in {owner}/{repo}", file=sys.stderr)
        else:
            errors.append(f"OWNERS_ALIASES: {e}")
    except subprocess.TimeoutExpired:
        errors.append("OWNERS_ALIASES: gh timed out")
    except Exception as e:
        errors.append(f"OWNERS_ALIASES: {e}")

    try:
        content = run_gh([
            "api", "-H", "Accept: application/vnd.github.raw",
            f"repos/{owner}/{repo}/contents/OWNERS",
        ])
        if HAS_YAML:
            data = yaml.safe_load(content)
            if data:
                def add_entries(entries: list):
                    for entry in entries:
                        if entry not in aliases:
                            authorized.add(entry)

                add_entries(data.get("approvers", []))
                add_entries(data.get("reviewers", []))

                if "filters" in data:
                    for _, config in data["filters"].items():
                        if isinstance(config, dict):
                            add_entries(config.get("approvers", []))
                            add_entries(config.get("reviewers", []))
        else:
            for entry in _parse_simple_yaml_list(content, "approvers"):
                if entry not in aliases:
                    authorized.add(entry)
            for entry in _parse_simple_yaml_list(content, "reviewers"):
                if entry not in aliases:
                    authorized.add(entry)
    except subprocess.CalledProcessError as e:
        if "404" in (e.stderr or ""):
            print(f"Info: No OWNERS file in {owner}/{repo}", file=sys.stderr)
        else:
            errors.append(f"OWNERS: {e}")
    except subprocess.TimeoutExpired:
        errors.append("OWNERS: gh timed out")
    except Exception as e:
        errors.append(f"OWNERS: {e}")

    if errors:
        raise OwnersLookupError("; ".join(errors))

    return authorized


def is_org_member(owner: str, login: str) -> bool:
    try:
        result = subprocess.run(
            ["gh", "api", f"orgs/{owner}/members/{login}"],
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"Warning: Org membership check timed out for {login}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Warning: Failed to check org membership for {login}: {e}", file=sys.stderr)
        return False


def main():
    if len(sys.argv) < 4:
        print("Usage: check_authorized.py <owner> <repo> <login>", file=sys.stderr)
        sys.exit(2)

    owner = sys.argv[1]
    repo = sys.argv[2]
    login = sys.argv[3]

    if not login:
        print(json.dumps({"authorized": False, "login": login, "reason": "empty_login"}))
        sys.exit(1)

    if login in IGNORED_ACCOUNTS or (login.endswith("[bot]") and login not in APPROVED_BOTS):
        print(json.dumps({"authorized": False, "login": login, "reason": "ignored_bot"}))
        sys.exit(1)

    try:
        authorized_users = get_authorized_users(owner, repo)
    except OwnersLookupError as e:
        print(json.dumps({"authorized": False, "login": login, "reason": f"owners_lookup_error: {e}"}))
        sys.exit(2)

    if login.lower() in {u.lower() for u in authorized_users}:
        reason = "approved_bot" if login in APPROVED_BOTS else "owners"
        print(json.dumps({"authorized": True, "login": login, "reason": reason}))
        sys.exit(0)

    if is_org_member(owner, login):
        print(json.dumps({"authorized": True, "login": login, "reason": "org_member"}))
        sys.exit(0)

    print(json.dumps({"authorized": False, "login": login, "reason": "not_authorized"}))
    sys.exit(1)


if __name__ == "__main__":
    main()
