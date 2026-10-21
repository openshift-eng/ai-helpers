#!/usr/bin/env python3
"""Read-only structural check for selectors in a Grype ignore policy."""

import sys
from pathlib import Path

try:
    import yaml
    from yaml import CSafeLoader
except ImportError:
    raise SystemExit("YAML_PARSE_ERROR: PyYAML with libyaml (CSafeLoader) is required")


class PolicyLoader(CSafeLoader):
    """Reject ambiguous duplicate keys while retaining YAML aliases/merges."""

    def construct_mapping(self, node, deep=False):
        keys = set()
        for key_node, _ in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                continue
            key = self.construct_object(key_node, deep=deep)
            if key in keys:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate mapping key: {key!r}", key_node.start_mark
                )
            keys.add(key)
        return super().construct_mapping(node, deep=deep)


def nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def check(path):
    try:
        with path.open(encoding="utf-8") as policy_file:
            policy = yaml.load(policy_file, Loader=PolicyLoader)
    except (OSError, UnicodeError, yaml.YAMLError, TypeError, ValueError) as error:
        return [f"YAML_PARSE_ERROR: {path}: {error}"]
    if policy is None:
        return []
    if not isinstance(policy, dict):
        return ["INVALID_IGNORE_STRUCTURE: Grype configuration must be a mapping"]
    entries = policy.get("ignore")
    if entries is None:
        return []
    if not isinstance(entries, list):
        return ["INVALID_IGNORE_STRUCTURE: ignore must be a list"]
    issues = []
    for number, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            issues.append(f"INVALID_IGNORE_STRUCTURE: ignore entry {number} must be a mapping")
            continue
        vulnerability = entry.get("vulnerability")
        package = entry.get("package")
        if not nonempty_string(vulnerability):
            issues.append(
                f"MISSING_VULNERABILITY_FIELD: ignore entry {number} needs a nonempty string vulnerability"
            )
        if not isinstance(package, dict) or not nonempty_string(package.get("name")):
            issues.append(
                f"MISSING_PACKAGE_FIELD: ignore entry {number} needs a package mapping with a nonempty string name — broad ignores are forbidden"
            )
    return issues


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: check-grype-ignores.py FILE")
    problems = check(Path(sys.argv[1]))
    for problem in problems:
        print(problem)
    raise SystemExit(bool(problems))
