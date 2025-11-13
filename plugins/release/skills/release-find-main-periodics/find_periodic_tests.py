#!/usr/bin/env python3
"""
Parse OpenShift CI configuration files to find periodic tests in main/master configs.

This script reads a list of YAML configuration files and identifies tests that have
periodic scheduling (interval or cron fields) which may need to be moved to dedicated
__periodics.yaml files.

Usage:
    python3 find_periodic_tests.py <file_list_path> [OPTIONS]

Where file_list_path contains one file path per line.

Options:
  --format=text|json           Output format (default: text)
  --filter=<json_file>         Filter results to only include repos/tests in the JSON file
  --verify-release=<version>   Only include tests that have job definitions for this release

Output formats:
  - text (default): Line-based format for easy parsing
    STATS:<total_files>:<files_with_periodic>:<total_periodic_tests>
    FILE:<filepath>
    TEST:<test_name>:<schedule>
    ...

  - json: JSON format grouped by repository
    {
      "statistics": {...},
      "repositories": {...}
    }
"""

import yaml
import sys
import json
import os
from pathlib import Path


def load_filter(filter_file):
    """Load filter from JSON file and return set of (repo_key, test_name) tuples."""
    with open(filter_file, 'r') as f:
        data = json.load(f)

    filter_set = set()
    if 'repositories' in data:
        for repo_key, repo_data in data['repositories'].items():
            for file_entry in repo_data.get('files', []):
                for test in file_entry.get('tests', []):
                    filter_set.add((repo_key, test['name']))

    return filter_set


def check_test_has_release_job(org, repo, test_name, release_version):
    """
    Check if a test has a corresponding job definition for the release version.

    Returns:
        bool: True if test has release job, False otherwise
    """
    release_repo_path = '/home/fsb/github/neisw/openshift/release'

    # Construct path to job file
    job_file_path = os.path.join(
        release_repo_path,
        'ci-operator/jobs',
        org,
        repo,
        f'{org}-{repo}-release-{release_version}-periodics.yaml'
    )

    # Check if file exists
    if not os.path.exists(job_file_path):
        return False

    try:
        # Read and parse YAML
        with open(job_file_path, 'r') as f:
            data = yaml.safe_load(f)

        if not data or 'periodics' not in data:
            return False

        # Look for test in periodics
        for job in data['periodics']:
            job_name = job.get('name', '')
            # Check if test name appears in job name and release version is present
            if test_name in job_name and f'release-{release_version}' in job_name:
                return True

        return False

    except Exception:
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 find_periodic_tests.py <file_list_path> [OPTIONS]", file=sys.stderr)
        print("Options:", file=sys.stderr)
        print("  --format=text|json           Output format (default: text)", file=sys.stderr)
        print("  --filter=<json_file>         Filter results to repos/tests in JSON file", file=sys.stderr)
        print("  --verify-release=<version>   Only include tests with release job definitions", file=sys.stderr)
        sys.exit(1)

    file_list_path = sys.argv[1]
    output_format = "text"
    filter_file = None
    verify_release = None

    # Check for format, filter, and verify-release arguments
    if len(sys.argv) > 2:
        for arg in sys.argv[2:]:
            if arg.startswith("--format="):
                output_format = arg.split("=", 1)[1]
            elif arg.startswith("--filter="):
                filter_file = arg.split("=", 1)[1]
            elif arg.startswith("--verify-release="):
                verify_release = arg.split("=", 1)[1]
                # Normalize release version (remove "release-" prefix if present)
                if verify_release.startswith("release-"):
                    verify_release = verify_release.replace("release-", "")

    # Load filter if provided
    filter_set = None
    if filter_file:
        filter_set = load_filter(filter_file)

    results = {}
    total_files = 0
    files_with_periodic = 0
    total_periodic_tests = 0

    with open(file_list_path, 'r') as f:
        files = [line.strip() for line in f if line.strip()]

    for filepath in files:
        total_files += 1
        try:
            with open(filepath, 'r') as f:
                data = yaml.safe_load(f)

            if not data or 'tests' not in data:
                continue

            # Extract org/repo for filtering
            rel_path = filepath.replace('/home/fsb/github/neisw/openshift/release/', '')
            parts = rel_path.split('/')
            repo_key = None
            if len(parts) >= 4:
                org = parts[2]  # openshift
                repo = parts[3]  # origin
                repo_key = f"{org}/{repo}"

            periodic_tests = []
            for test in data['tests']:
                if not isinstance(test, dict):
                    continue

                test_name = test.get('as')
                has_interval = 'interval' in test
                has_cron = 'cron' in test

                if test_name and (has_interval or has_cron):
                    # Apply filter if provided
                    if filter_set is not None:
                        if repo_key is None or (repo_key, test_name) not in filter_set:
                            continue

                    # Apply release verification if provided
                    if verify_release is not None:
                        if repo_key is None:
                            continue
                        # Extract org and repo from repo_key (format: "org/repo")
                        parts_key = repo_key.split('/')
                        if len(parts_key) != 2:
                            continue
                        test_org, test_repo = parts_key[0], parts_key[1]

                        # Check if test has release job
                        if not check_test_has_release_job(test_org, test_repo, test_name, verify_release):
                            continue

                    schedule = ""
                    if has_interval:
                        schedule = f"interval: {test['interval']}"
                    elif has_cron:
                        schedule = f"cron: {test['cron']}"

                    periodic_tests.append({
                        'name': test_name,
                        'schedule': schedule
                    })

            if periodic_tests:
                results[rel_path] = periodic_tests
                files_with_periodic += 1
                total_periodic_tests += len(periodic_tests)

        except Exception as e:
            print(f"Error parsing {filepath}: {e}", file=sys.stderr)
            continue

    # Output results based on format
    if output_format == "json":
        # Group by repository
        repositories = {}
        for filepath, tests in results.items():
            # Extract org/repo from path like ci-operator/config/openshift/origin/...
            parts = filepath.split('/')
            if len(parts) >= 4:
                org = parts[2]  # openshift
                repo = parts[3]  # origin
                repo_key = f"{org}/{repo}"

                if repo_key not in repositories:
                    repositories[repo_key] = {
                        "organization": org,
                        "repository": repo,
                        "files": []
                    }

                repositories[repo_key]["files"].append({
                    "file": filepath,
                    "tests": tests
                })

        output = {
            "statistics": {
                "total_files_scanned": total_files,
                "files_with_periodic_tests": files_with_periodic,
                "total_periodic_tests": total_periodic_tests
            },
            "repositories": repositories
        }

        print(json.dumps(output, indent=2))
    else:
        # Text format (default)
        print(f"STATS:{total_files}:{files_with_periodic}:{total_periodic_tests}")
        for filepath, tests in sorted(results.items()):
            print(f"FILE:{filepath}")
            for test in tests:
                print(f"TEST:{test['name']}:{test['schedule']}")


if __name__ == '__main__':
    main()
