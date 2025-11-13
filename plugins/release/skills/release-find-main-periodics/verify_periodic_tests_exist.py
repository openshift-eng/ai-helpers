#!/usr/bin/env python3
"""
Verify that periodic tests have corresponding release job configurations.

This script reads a JSON file containing periodic tests and checks the local
ci-operator/jobs directory to verify that each test has a corresponding job
configuration for the target release.

Usage:
    python3 verify_periodic_tests_exist.py <json_file> <target_release>

Example:
    python3 verify_periodic_tests_exist.py periodic_tests_report.json 4.21
"""

import json
import sys
import os
import yaml
from pathlib import Path


def check_job_file_for_test(org, repo, test_name, release_version, release_repo_path):
    """
    Check if a test exists in the release-specific periodic job file.

    Args:
        org: Organization name (e.g., "openshift")
        repo: Repository name (e.g., "kubernetes")
        test_name: Name of the test to check
        release_version: Release version (e.g., "4.21")
        release_repo_path: Path to openshift/release repository

    Returns:
        tuple: (exists: bool, error: str or None, job_file: str or None)
    """
    # Construct path to job file
    # Pattern: ci-operator/jobs/{org}/{repo}/{org}-{repo}-release-{version}-periodics.yaml
    job_file_path = os.path.join(
        release_repo_path,
        'ci-operator/jobs',
        org,
        repo,
        f'{org}-{repo}-release-{release_version}-periodics.yaml'
    )

    # Check if file exists
    if not os.path.exists(job_file_path):
        return False, f"Job file does not exist", None

    try:
        # Read and parse YAML
        with open(job_file_path, 'r') as f:
            data = yaml.safe_load(f)

        if not data:
            return False, "Empty job file", job_file_path

        # Check for periodics section
        if 'periodics' not in data:
            return False, "No 'periodics' section in job file", job_file_path

        # Look for test in periodics
        for job in data['periodics']:
            # Job names typically follow pattern: periodic-ci-{org}-{repo}-release-{version}-{test_name}
            # or similar variations
            job_name = job.get('name', '')

            # Check if test name appears in job name
            if test_name in job_name and f'release-{release_version}' in job_name:
                return True, None, job_file_path

        return False, f"Test not found in periodics", job_file_path

    except yaml.YAMLError as e:
        return False, f"YAML parse error: {e}", job_file_path
    except Exception as e:
        return False, f"Error: {str(e)}", job_file_path


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 verify_periodic_tests_exist.py <json_file> <target_release>", file=sys.stderr)
        print("Example: python3 verify_periodic_tests_exist.py periodic_tests_report.json 4.21", file=sys.stderr)
        sys.exit(1)

    json_file = sys.argv[1]
    target_release = sys.argv[2]

    # Normalize release version (remove "release-" prefix if present)
    if target_release.startswith("release-"):
        target_release = target_release.replace("release-", "")

    # Determine path to openshift/release repository
    release_repo_path = '/home/fsb/github/neisw/openshift/release'
    if not os.path.exists(release_repo_path):
        print(f"Error: Release repository not found at {release_repo_path}", file=sys.stderr)
        sys.exit(1)

    # Load JSON file
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON file: {e}", file=sys.stderr)
        sys.exit(1)

    if 'repositories' not in data:
        print("Error: JSON file does not contain 'repositories' key", file=sys.stderr)
        sys.exit(1)

    # Track results
    total_tests = 0
    tests_with_release = 0
    missing_tests = []
    missing_job_files = set()

    print(f"Verifying periodic tests for release-{target_release}")
    print(f"Checking ci-operator/jobs in: {release_repo_path}")
    print("=" * 80)
    print()

    # Process each repository
    for repo_key, repo_data in data['repositories'].items():
        org = repo_data['organization']
        repo = repo_data['repository']

        print(f"Repository: {repo_key}")
        print("-" * 80)

        # Process each file
        for file_entry in repo_data.get('files', []):
            # Process each test
            for test in file_entry.get('tests', []):
                test_name = test['name']
                total_tests += 1

                print(f"  Checking: {test_name}...", end=" ", flush=True)

                # Check job file for this test
                exists, error, job_file = check_job_file_for_test(
                    org, repo, test_name, target_release, release_repo_path
                )

                if exists:
                    print(f"✓ FOUND in {os.path.basename(job_file)}")
                    tests_with_release += 1
                else:
                    print(f"✗ MISSING ({error})")
                    missing_tests.append({
                        'repository': repo_key,
                        'test': test_name,
                        'reason': error,
                        'expected_file': f'ci-operator/jobs/{org}/{repo}/{org}-{repo}-release-{target_release}-periodics.yaml'
                    })
                    if error == "Job file does not exist":
                        missing_job_files.add(f'{org}/{repo}')

        print()

    # Print summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total tests checked: {total_tests}")
    print(f"Tests with release-{target_release} jobs: {tests_with_release}")
    print(f"Missing tests: {len(missing_tests)}")
    print(f"Repositories missing job files: {len(missing_job_files)}")
    print()

    if missing_job_files:
        print("REPOSITORIES MISSING JOB FILES:")
        print("-" * 80)
        for repo in sorted(missing_job_files):
            print(f"  - {repo}")
            print(f"    Expected: ci-operator/jobs/{repo}/{repo.split('/')[1]}-release-{target_release}-periodics.yaml")
        print()

    if missing_tests:
        print("MISSING TESTS DETAILS:")
        print("-" * 80)
        for item in missing_tests:
            print(f"Repository: {item['repository']}")
            print(f"  Test: {item['test']}")
            print(f"  Reason: {item['reason']}")
            print(f"  Expected file: {item['expected_file']}")
            print()
    else:
        print(f"✓ All tests have corresponding release-{target_release} jobs!")

    # Exit with error code if there are missing tests
    sys.exit(1 if missing_tests else 0)


if __name__ == '__main__':
    main()
