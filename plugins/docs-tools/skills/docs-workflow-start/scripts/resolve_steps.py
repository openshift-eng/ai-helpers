#!/usr/bin/env python3
"""Resolve step dependencies for docs-workflow-start.

Given a workflow YAML and requested steps, compute transitive
dependencies and return an ordered execution plan as JSON.

No external dependencies — uses a minimal parser for the constrained
workflow YAML format (no PyYAML required).

Exit codes:
    0 — success (JSON execution plan on stdout)
    1 — error (JSON with error message and valid_steps list on stdout)
"""

import argparse
import json
import os
import re
import sys


def parse_args():
    p = argparse.ArgumentParser(description="Resolve workflow step dependencies")
    p.add_argument(
        "--yaml",
        required=True,
        help="Path to the workflow YAML file",
    )
    p.add_argument(
        "--steps",
        required=True,
        nargs="+",
        help="Step names to run",
    )
    p.add_argument(
        "--base-path",
        default=None,
        help="Base artifact path — used to check for existing step output",
    )
    return p.parse_args()


def parse_workflow_yaml(path):
    """Parse the constrained workflow YAML format without PyYAML.

    Handles top-level workflow fields:
      - requires: [condition1, condition2]

    And step list items (lines starting with '- name:'):
      - name: value
      - skill: value
      - description: value
      - when: value
      - inputs: [a, b, c]

    Returns (steps, requires) where requires is a list of condition strings.
    """
    with open(path) as f:
        lines = f.readlines()

    steps = []
    requires = []
    current = None
    in_requires_block = False

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- name:"):
            in_requires_block = False
            if current:
                steps.append(current)
            current = {
                "name": stripped.split(":", 1)[1].strip(),
                "skill": None,
                "description": "",
                "when": None,
                "inputs": [],
            }
            continue

        if current is None:
            if in_requires_block and stripped.startswith("- "):
                requires.append(stripped[2:].strip())
                continue

            if ":" in stripped:
                key, value = stripped.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key == "requires":
                    in_requires_block = True
                    match = re.match(r"\[(.*)\]", value)
                    if match:
                        requires = [s.strip() for s in match.group(1).split(",") if s.strip()]
                        in_requires_block = False
                else:
                    in_requires_block = False
            continue

        if ":" in stripped and not stripped.startswith("-"):
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()

            if key == "inputs":
                match = re.match(r"\[(.*)\]", value)
                if match:
                    current["inputs"] = [s.strip() for s in match.group(1).split(",") if s.strip()]
            elif key in ("skill", "description", "when"):
                current[key] = value
            elif key == "name" and current.get("name") is None:
                current["name"] = value

    if current:
        steps.append(current)

    return steps, requires


def validate_inputs(steps_list, step_map):
    """Check that all input references point to existing steps."""
    errors = []
    for step in steps_list:
        for dep in step["inputs"]:
            if dep not in step_map:
                errors.append(f"Step '{step['name']}' references unknown input '{dep}'")
    return errors


def resolve_transitive_deps(steps_list, requested):
    """Walk the inputs graph to compute all needed steps.

    Returns step names in canonical YAML order (not insertion order).
    """
    step_map = {s["name"]: s for s in steps_list}
    canonical_order = [s["name"] for s in steps_list]
    needed = set()

    def walk(name):
        if name in needed or name not in step_map:
            return
        needed.add(name)
        for dep in step_map[name]["inputs"]:
            walk(dep)

    for name in requested:
        walk(name)

    return [s for s in canonical_order if s in needed]


def check_existing_artifacts(step_names, base_path):
    """Check which steps have non-empty artifact directories."""
    result = {}
    if not base_path:
        return result
    for name in step_names:
        step_dir = os.path.join(base_path, name)
        try:
            result[name] = os.path.isdir(step_dir) and len(os.listdir(step_dir)) > 0
        except OSError:
            result[name] = False
    return result


def main():
    args = parse_args()

    steps_list, requires = parse_workflow_yaml(args.yaml)
    step_map = {s["name"]: s for s in steps_list}
    valid_names = sorted(s["name"] for s in steps_list)

    input_errors = validate_inputs(steps_list, step_map)
    if input_errors:
        json.dump(
            {
                "error": "Invalid input dependencies in workflow YAML",
                "details": input_errors,
                "valid_steps": valid_names,
            },
            sys.stdout,
            indent=2,
        )
        sys.exit(1)

    invalid = [s for s in args.steps if s not in step_map]
    if invalid:
        json.dump(
            {
                "error": f"Unknown step(s): {', '.join(invalid)}",
                "valid_steps": valid_names,
            },
            sys.stdout,
            indent=2,
        )
        sys.exit(1)

    ordered = resolve_transitive_deps(steps_list, args.steps)
    existing = check_existing_artifacts(ordered, args.base_path)

    plan = []
    for name in ordered:
        step = step_map[name]
        plan.append(
            {
                "name": name,
                "skill": step["skill"],
                "description": step["description"],
                "is_prereq": name not in args.steps,
                "has_artifacts": existing.get(name, False),
                "when": step["when"],
                "inputs": step["inputs"],
            }
        )

    json.dump(
        {
            "requested": args.steps,
            "execution_plan": plan,
            "prereq_steps": [p["name"] for p in plan if p["is_prereq"]],
            "steps_with_artifacts": [n for n, exists in existing.items() if exists],
            "requires": requires,
        },
        sys.stdout,
        indent=2,
    )


if __name__ == "__main__":
    main()
