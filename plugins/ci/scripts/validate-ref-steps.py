#!/usr/bin/env python3
"""
Validate ci-operator config files don't have forbidden properties on ref steps.

In ci-operator job config files (ci-operator/config/), ref steps cannot have
sibling properties like timeout, best_effort, as, commands, from, from_image,
or resources. The ci-operator validator treats these as literal test step
definitions requiring all mandatory fields.

This validation does NOT apply to workflow files (ci-operator/step-registry/)
where timeout and best_effort on ref steps are valid.

Usage: validate-ref-steps.py <config-file> [config-file...]
"""

import os
import sys

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

FORBIDDEN_KEYS = {
    "timeout", "best_effort", "as", "commands", "from", "from_image", "resources"
}


def validate_steps(steps, test_name):
    """Check a list of steps for ref entries with forbidden sibling properties."""
    errors = []
    if not isinstance(steps, list):
        return errors
    for step in steps:
        if not isinstance(step, dict):
            continue
        if "ref" not in step:
            continue
        bad_keys = set(step.keys()) & FORBIDDEN_KEYS
        if bad_keys:
            errors.append(
                f"  Test '{test_name}', ref '{step['ref']}': "
                f"forbidden properties: {', '.join(sorted(bad_keys))}"
            )
    return errors


def validate_file(filepath):
    """Validate a single ci-operator config file."""
    # Skip workflow files - timeout/best_effort are valid there
    if "step-registry" in filepath:
        print(f"Skipped (workflow file): {filepath}")
        return True

    # Only validate ci-operator config files
    if "ci-operator/config" not in filepath:
        print(f"Skipped (not a ci-operator config): {filepath}")
        return True

    try:
        with open(filepath) as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        print(f"Error reading {filepath}: {e}")
        return False

    if not data or "tests" not in data:
        print(f"Passed (no tests section): {filepath}")
        return True

    errors = []
    tests = data.get("tests")
    if not isinstance(tests, list):
        print(f"Passed (tests is not a list): {filepath}")
        return True
    for test in tests:
        if not isinstance(test, dict):
            continue
        test_name = test.get("as", "<unnamed>")
        steps = test.get("steps", {})
        if not isinstance(steps, dict):
            continue
        for section in ("pre", "test", "post"):
            section_steps = steps.get(section)
            if section_steps:
                errors.extend(validate_steps(section_steps, test_name))

    if errors:
        print(f"FAILED: {filepath}")
        for e in errors:
            print(e)
        print()
        print("ci-operator config files cannot have extra properties on ref steps.")
        print(f"Forbidden keys: {', '.join(sorted(FORBIDDEN_KEYS))}")
        print("For custom timeouts, use the TIMEOUT env var in the job's env: section.")
        return False

    print(f"Passed: {filepath}")
    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    all_passed = True
    for filepath in sys.argv[1:]:
        if not os.path.isfile(filepath):
            print(f"Error: File not found: {filepath}")
            all_passed = False
            continue
        if not validate_file(filepath):
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
