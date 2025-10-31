#!/usr/bin/env python3
"""
Migrate periodic tests from main/master configs to dedicated release-specific periodic files.

This script reads a JSON file containing periodic tests and migrates them to dedicated
__periodics.yaml files for a specific release version.

Usage:
    python3 migrate_periodic_tests.py <json_file> <target_release> <release_repo_path>

Example:
    python3 migrate_periodic_tests.py migrate_4.21.json 4.21 /path/to/release/repo
"""

from ruamel.yaml import YAML
import json
import sys
import os
from pathlib import Path

# Initialize ruamel.yaml with formatting preservation
yaml = YAML()
yaml.preserve_quotes = True
yaml.default_flow_style = False
yaml.width = 4096  # Prevent line wrapping


def read_yaml_file(file_path):
    """Read and parse a YAML file while preserving formatting."""
    with open(file_path, 'r') as f:
        return yaml.load(f)


def write_yaml_file(file_path, data):
    """Write data to a YAML file while preserving formatting."""
    with open(file_path, 'w') as f:
        yaml.dump(data, f)


def extract_tests_from_source(source_data, test_names):
    """Extract specific tests from source YAML data."""
    if 'tests' not in source_data:
        return []

    extracted_tests = []
    for test in source_data['tests']:
        if test.get('as') in test_names:
            extracted_tests.append(test)

    return extracted_tests


def remove_tests_from_source(source_data, test_names):
    """Remove specific tests from source YAML data."""
    if 'tests' not in source_data:
        return source_data

    source_data['tests'] = [
        test for test in source_data['tests']
        if test.get('as') not in test_names
    ]

    return source_data


def create_periodic_file_structure(source_data, tests, target_release):
    """Create the structure for a periodic file based on source data."""
    periodic_data = {}

    # Copy base fields from source
    for field in ['base_images', 'build_root', 'operator', 'releases', 'resources']:
        if field in source_data:
            periodic_data[field] = source_data[field]

    # Add the tests
    periodic_data['tests'] = tests

    # Add metadata
    if 'zz_generated_metadata' in source_data:
        metadata = source_data['zz_generated_metadata'].copy()
        metadata['variant'] = 'periodics'
        # Update branch to release version
        metadata['branch'] = f'release-{target_release}'
        periodic_data['zz_generated_metadata'] = metadata

    return periodic_data


def merge_with_existing_periodic_file(existing_data, new_tests):
    """Merge new tests with existing periodic file."""
    if 'tests' not in existing_data:
        existing_data['tests'] = []

    # Get existing test names
    existing_test_names = {test.get('as') for test in existing_data['tests']}

    # Add new tests that don't already exist
    for test in new_tests:
        test_name = test.get('as')
        if test_name not in existing_test_names:
            existing_data['tests'].append(test)
        else:
            print(f"  Warning: Test '{test_name}' already exists in periodic file, skipping")

    return existing_data


def main():
    if len(sys.argv) < 4:
        print("Usage: python3 migrate_periodic_tests.py <json_file> <target_release> <release_repo_path>", file=sys.stderr)
        sys.exit(1)

    json_file = sys.argv[1]
    target_release = sys.argv[2]
    release_repo_path = sys.argv[3]

    # Normalize release version
    if target_release.startswith("release-"):
        target_release = target_release.replace("release-", "")

    # Load JSON file
    with open(json_file, 'r') as f:
        data = json.load(f)

    if 'repositories' not in data:
        print("Error: JSON file does not contain 'repositories' key", file=sys.stderr)
        sys.exit(1)

    # Track statistics
    total_repos = len(data['repositories'])
    total_tests = sum(
        len(file_entry.get('tests', []))
        for repo_data in data['repositories'].values()
        for file_entry in repo_data.get('files', [])
    )

    processed_repos = 0
    migrated_tests = 0
    created_files = 0
    updated_files = 0
    modified_sources = 0

    print(f"Periodic Tests Migration to Dedicated Files")
    print(f"=" * 80)
    print(f"Target Release: {target_release}")
    print(f"Repositories to process: {total_repos}")
    print(f"Tests to migrate: {total_tests}")
    print()

    # Process each repository
    for repo_key, repo_data in data['repositories'].items():
        org = repo_data['organization']
        repo = repo_data['repository']

        print(f"Processing: {repo_key}")
        print(f"-" * 80)

        # Process each file in the repository
        for file_entry in repo_data.get('files', []):
            source_file = file_entry['file']
            source_path = os.path.join(release_repo_path, source_file)

            # Get test names to migrate
            test_names = [test['name'] for test in file_entry.get('tests', [])]

            if not test_names:
                continue

            print(f"  Source: {source_file}")
            print(f"  Tests to migrate: {', '.join(test_names)}")

            # Read source file
            try:
                source_data = read_yaml_file(source_path)
            except Exception as e:
                print(f"  Error reading source file: {e}")
                continue

            # Extract tests from source
            extracted_tests = extract_tests_from_source(source_data, test_names)

            if not extracted_tests:
                print(f"  Warning: No tests found in source file")
                continue

            print(f"  Extracted {len(extracted_tests)} test(s)")

            # Determine target periodic file path
            # Extract branch from source filename (-main or -master)
            source_filename = os.path.basename(source_file)
            if '-main.yaml' in source_filename:
                branch_part = 'main'
            elif '-master.yaml' in source_filename:
                branch_part = 'master'
            else:
                print(f"  Error: Could not determine branch from filename")
                continue

            # Target file: {org}-{repo}-release-{version}__periodics.yaml
            target_filename = f"{org}-{repo}-release-{target_release}__periodics.yaml"
            target_path = os.path.join(os.path.dirname(source_path), target_filename)

            print(f"  Target: {target_filename}")

            # Create or update target periodic file
            if os.path.exists(target_path):
                print(f"  Periodic file exists, merging...")
                periodic_data = read_yaml_file(target_path)
                periodic_data = merge_with_existing_periodic_file(periodic_data, extracted_tests)
                updated_files += 1
            else:
                print(f"  Creating new periodic file...")
                periodic_data = create_periodic_file_structure(source_data, extracted_tests, target_release)
                created_files += 1

            # Write target periodic file
            try:
                write_yaml_file(target_path, periodic_data)
                print(f"  ✓ Wrote periodic file")
            except Exception as e:
                print(f"  Error writing periodic file: {e}")
                continue

            # Remove tests from source file
            updated_source = remove_tests_from_source(source_data, test_names)

            try:
                write_yaml_file(source_path, updated_source)
                print(f"  ✓ Removed {len(test_names)} test(s) from source file")
                modified_sources += 1
            except Exception as e:
                print(f"  Error updating source file: {e}")
                continue

            migrated_tests += len(extracted_tests)

        processed_repos += 1
        print()

    # Print summary
    print(f"=" * 80)
    print(f"Migration Summary")
    print(f"=" * 80)
    print(f"Repositories processed: {processed_repos}/{total_repos}")
    print(f"Tests migrated: {migrated_tests}/{total_tests}")
    print(f"Periodic files created: {created_files}")
    print(f"Periodic files updated: {updated_files}")
    print(f"Source files modified: {modified_sources}")
    print()
    print(f"Next steps:")
    print(f"1. Review changes: git status && git diff")
    print(f"2. Regenerate jobs: make jobs")
    print(f"3. Commit and create PR")


if __name__ == '__main__':
    main()
