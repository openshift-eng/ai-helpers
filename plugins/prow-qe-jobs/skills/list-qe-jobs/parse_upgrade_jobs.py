#!/usr/bin/env python3
"""
Parse OpenShift CI configuration files to extract upgrade-related jobs.
"""

import yaml
import sys
import os
from pathlib import Path
from collections import defaultdict

def is_upgrade_job(job_name, job_config):
    """Check if a job is upgrade-related."""
    # Check job name for upgrade keywords
    upgrade_keywords = ['upgrade', 'update', 'migration']
    job_name_lower = job_name.lower()

    if any(keyword in job_name_lower for keyword in upgrade_keywords):
        return True

    # Check workflow and steps for upgrade-related content
    if isinstance(job_config, dict):
        workflow = job_config.get('workflow', '')
        if workflow and 'upgrade' in workflow.lower():
            return True

        # Check in steps
        steps = job_config.get('steps', {})
        if isinstance(steps, dict):
            for step_type in ['test', 'pre', 'post']:
                step_list = steps.get(step_type, [])
                if isinstance(step_list, list):
                    for step in step_list:
                        if isinstance(step, dict):
                            ref = step.get('ref', '')
                            if ref and 'upgrade' in ref.lower():
                                return True

    return False

def extract_metadata(job_name, job_config):
    """Extract relevant metadata from job configuration."""
    metadata = {
        'name': job_name,
        'workflow': job_config.get('workflow', '') if isinstance(job_config, dict) else '',
        'cluster_profile': job_config.get('cluster_profile', '') if isinstance(job_config, dict) else '',
    }

    # Try to extract platform from job name
    platforms = ['aws', 'azure', 'gcp', 'vsphere', 'openstack', 'metal', 'alibaba', 'nutanix', 'powervs', 'ibmcloud']
    for platform in platforms:
        if platform in job_name.lower():
            metadata['platform'] = platform
            break
    else:
        metadata['platform'] = 'unknown'

    return metadata

def parse_config_file(file_path):
    """Parse a single CI configuration file."""
    try:
        with open(file_path, 'r') as f:
            config = yaml.safe_load(f)

        if not config or 'tests' not in config:
            return []

        upgrade_jobs = []
        tests = config.get('tests', [])

        for test in tests:
            if isinstance(test, dict):
                # Test name is usually the 'as' field
                job_name = test.get('as', '')
                if job_name and is_upgrade_job(job_name, test):
                    metadata = extract_metadata(job_name, test)
                    upgrade_jobs.append(metadata)

        return upgrade_jobs

    except Exception as e:
        print(f"Error parsing {file_path}: {e}", file=sys.stderr)
        return []

def main():
    config_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
    filter_pattern = sys.argv[2].lower() if len(sys.argv) > 2 else None

    # Find all YAML files
    yaml_files = sorted(config_dir.glob('*.yaml'))

    # Group jobs by configuration file
    jobs_by_config = defaultdict(list)
    all_jobs = []

    for yaml_file in yaml_files:
        # Skip __images.yaml files as they don't contain test definitions
        if '__images.yaml' in yaml_file.name:
            continue

        # Apply filter at file level if provided
        if filter_pattern and filter_pattern not in yaml_file.name.lower():
            jobs = parse_config_file(yaml_file)
            # Also filter individual job names
            if jobs:
                jobs = [j for j in jobs if filter_pattern in j['name'].lower()]
        else:
            jobs = parse_config_file(yaml_file)
            # If we matched the filename, include all jobs from this file
            # Otherwise filter job names
            if filter_pattern and jobs:
                jobs = [j for j in jobs if filter_pattern in yaml_file.name.lower() or filter_pattern in j['name'].lower()]

        if jobs:
            jobs_by_config[yaml_file.name] = jobs
            all_jobs.extend(jobs)

    # Display results
    if not all_jobs:
        if filter_pattern:
            print(f"No upgrade jobs found matching filter: '{filter_pattern}'")
        else:
            print("No upgrade jobs found in configuration files.")
        return

    print("Upgrade Jobs from openshift-tests-private:\n")

    for config_file, jobs in sorted(jobs_by_config.items()):
        print(f"Configuration: {config_file}")

        # Group by platform for better readability
        jobs_by_platform = defaultdict(list)
        for job in jobs:
            jobs_by_platform[job['platform']].append(job)

        job_num = 1
        for platform in sorted(jobs_by_platform.keys()):
            for job in sorted(jobs_by_platform[platform], key=lambda x: x['name']):
                workflow_info = f" (workflow: {job['workflow']})" if job['workflow'] else ""
                print(f"  {job_num}. {job['name']}{workflow_info}")
                job_num += 1

        print()

    # Summary statistics
    print(f"Total upgrade jobs found: {len(all_jobs)}")

    # Platform breakdown
    platform_counts = defaultdict(int)
    for job in all_jobs:
        platform_counts[job['platform']] += 1

    if len(platform_counts) > 1:
        print("\nBreakdown by platform:")
        for platform in sorted(platform_counts.keys()):
            print(f"  - {platform}: {platform_counts[platform]}")

if __name__ == '__main__':
    main()
