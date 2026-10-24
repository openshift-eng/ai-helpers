#!/usr/bin/env python3
"""Read-only Grype policy validation and selector projection for the audits."""

import json
import re
import subprocess
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
                self.merged_nodes.add(id(node))
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


def mapping(node):
    return {key.value: value for key, value in node.value} if isinstance(node, yaml.MappingNode) else {}


def normalize_location(value):
    if value.startswith("/src/"):
        value = value[5:]
    if value.startswith("/"):
        value = value[1:]
    return "/" + value if value else ""


def read_policy(path, text=None):
    try:
        if text is None:
            text = path.read_text(encoding="utf-8")
        loader = PolicyLoader(text)
        try:
            node = loader.get_single_node()
            # Construct the same node tree so merged selectors retain their marks.
            loader.merged_nodes = set()
            policy = loader.construct_document(node) if node is not None else None
            merged_nodes = loader.merged_nodes
        finally:
            loader.dispose()
    except (OSError, UnicodeError, yaml.YAMLError, TypeError, ValueError) as error:
        return [], [f"YAML_PARSE_ERROR: {path}: {error}"], False
    if policy is None:
        return [], [], True
    if not isinstance(policy, dict):
        return [], ["INVALID_IGNORE_STRUCTURE: Grype configuration must be a mapping"], False
    ignore_pair = next(((key, value) for key, value in node.value if key.value == "ignore"), None)
    lines = text.splitlines()
    mutable = id(node) not in merged_nodes and (ignore_pair is None or (not ignore_pair[0].style and ignore_pair[0].start_mark.column == 0 and bool(re.fullmatch(
        r"ignore:\s*(?:\[\s*\]\s*)?(?:#.*)?", lines[ignore_pair[0].start_mark.line]))))
    entries = policy.get("ignore")
    if entries is None:
        return [], [], mutable
    if not isinstance(entries, list):
        return [], ["INVALID_IGNORE_STRUCTURE: ignore must be a list"], False
    ignore_node = ignore_pair[1]
    mutable = mutable and (not entries or not ignore_node.flow_style)
    mutable = mutable and not any(isinstance(token, (yaml.AliasToken, yaml.AnchorToken)) and
        ignore_pair[0].start_mark.index <= token.start_mark.index < ignore_node.end_mark.index
        for token in yaml.scan(text, Loader=CSafeLoader))
    issues, projected = [], []
    for number, (entry, entry_node) in enumerate(zip(entries, ignore_node.value), 1):
        if not isinstance(entry, dict):
            issues.append(f"INVALID_IGNORE_STRUCTURE: ignore entry {number} must be a mapping")
            mutable = False
            continue
        vulnerability, package = entry.get("vulnerability"), entry.get("package")
        fields = mapping(entry_node)
        package_node = fields.get("package")
        start = entry_node.start_mark.line
        mutable = mutable and not entry_node.flow_style and id(entry_node) not in merged_nodes and bool(re.match(
            r"\s*-\s+(vulnerability|package):", lines[start]))
        mutable = mutable and (package_node is None or (isinstance(package_node, yaml.MappingNode) and not package_node.flow_style))
        mutable = mutable and id(package_node) not in merged_nodes
        if isinstance(package_node, yaml.MappingNode):
            mutable = mutable and all(not key.style for key, _ in package_node.value if key.value == "name")
        if not nonempty_string(vulnerability):
            issues.append(f"MISSING_VULNERABILITY_FIELD: ignore entry {number} needs a nonempty string vulnerability")
        if not isinstance(package, dict) or not nonempty_string(package.get("name")):
            issues.append(f"MISSING_PACKAGE_FIELD: ignore entry {number} needs a package mapping with a nonempty string name — broad ignores are forbidden")
        if not nonempty_string(vulnerability) or not isinstance(package, dict) or not nonempty_string(package.get("name")):
            continue
        state = entry.get("fix-state")
        if state is None:
            state = ""
        if not isinstance(state, str):
            issues.append(f"BAD_FIX_STATE: fix-state {state!r} must be a string")
            continue
        if any(package.get(field) is not None and not isinstance(package[field], str)
               for field in ("type", "location")):
            issues.append(f"INVALID_IGNORE_STRUCTURE: package type/location in entry {number} must be strings")
            continue
        start = entry_node.start_mark.line
        comments = []
        previous = start - 1
        while previous >= 0 and lines[previous].lstrip().startswith("#"):
            comments.insert(0, lines[previous].lstrip()[1:].strip())
            previous -= 1
        projected.append({"vulnerability": vulnerability, "package": package["name"],
                          "type": package.get("type") or "", "location": normalize_location(package.get("location") or ""),
                          "fix_state": state, "comment": " ".join(comments), "commented": previous < start - 1})
        mutable = mutable and bool(re.fullmatch(
            r"\s*-\s+vulnerability:\s*" + re.escape(vulnerability) + r"\s*", lines[start]))
        mutable = mutable and not fields["vulnerability"].style
    return projected, issues, mutable


def audit(path, base):
    """Apply this tool's added-rule policy without reinterpreting inherited rules."""
    entries, problems, _ = read_policy(path)
    diff = subprocess.run(["git", "diff", base, "--", str(path)], capture_output=True, text=True)
    if diff.returncode:
        problems.append("GIT_POLICY_DIFF_ERROR: cannot compare ignore policy with the branch base")
    if problems:
        return problems
    listed = subprocess.run(["git", "ls-tree", "--name-only", base, "--", str(path)], capture_output=True, text=True)
    if listed.returncode:
        return ["GIT_POLICY_BASE_ERROR: cannot inspect the branch base ignore policy"]
    original = []
    if listed.stdout:
        previous = subprocess.run(["git", "show", f"{base}:{path}"], capture_output=True, text=True)
        if previous.returncode:
            return ["GIT_POLICY_BASE_ERROR: cannot read the branch base ignore policy"]
        original, previous_problems, _ = read_policy(path, previous.stdout)
        if any(problem.startswith("YAML_PARSE_ERROR:") for problem in previous_problems):
            return previous_problems
    def identity(entry):
        return tuple(entry[field] for field in ("vulnerability", "package", "type", "location", "fix_state"))
    inherited = {identity(entry) for entry in original}
    for entry in entries:
        is_go = entry["type"] == "go-module" or (not entry["type"] and
            (entry["package"] == "stdlib" or re.match(r"^[^/]*[.][^/]*/", entry["package"])))
        if not is_go or identity(entry) in inherited:
            continue
        if not entry["vulnerability"].startswith(("CVE-", "GHSA-", "GO-")):
            problems.append(f"BAD_VULN_FORMAT: '{entry['vulnerability']}' does not match CVE-/GHSA-/GO- pattern")
        if entry["fix_state"] not in ("", "not-fixed", "unknown", "wont-fix"):
            problems.append(f"BAD_FIX_STATE: fix-state '{entry['fix_state']}' is not 'not-fixed', 'unknown', or 'wont-fix'")
        if not entry["commented"]:
            problems.append(f"MISSING_COMMENT: no comment line before entry for {entry['vulnerability']}")
    return problems


def check(path):
    return read_policy(path)[1]


if __name__ == "__main__":
    mode = "check"
    arguments = sys.argv[1:]
    if arguments and arguments[0] in ("--entries", "--writable", "--audit"):
        mode = arguments.pop(0)
    if len(arguments) != (2 if mode == "--audit" else 1):
        raise SystemExit("Usage: check-grype-ignores.py [--entries|--writable] FILE; --audit FILE BASE")
    if mode == "--audit":
        entries, problems, mutable = [], audit(Path(arguments[0]), arguments[1]), False
    else:
        entries, problems, mutable = read_policy(Path(arguments[0]))
    if mode == "--writable":
        # The bounded broad-selector remover intentionally repairs these two
        # structural defects, but only in its supported comment-preserving layout.
        problems = [item for item in problems if not item.startswith(("MISSING_VULNERABILITY_FIELD:", "MISSING_PACKAGE_FIELD:"))]
    if mode == "--writable" and not problems and not mutable:
        problems = ["UNSUPPORTED_IGNORE_LAYOUT: comment-preserving mutation needs a block list with vulnerability first and a block package mapping; review this policy manually"]
    for problem in problems:
        print(problem, file=sys.stderr if mode == "--entries" else sys.stdout)
    if not problems and mode == "--entries":
        print(json.dumps(entries))
    raise SystemExit(bool(problems))
