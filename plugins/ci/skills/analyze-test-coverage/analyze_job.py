#!/usr/bin/env python3
"""
Analyze a CI job configuration to determine which test suite it uses.
"""

import sys
import json
import yaml
from pathlib import Path


def find_job_config(release_repo, job_name):
    """
    Find the job configuration file for a given job name.

    Args:
        release_repo: Path to openshift/release repository
        job_name: Name of the periodic job

    Returns:
        dict with 'file' and 'job' keys, or None if not found
    """
    # Jobs are typically in ci-operator/jobs/openshift/release/
    jobs_dir = release_repo / "ci-operator/jobs/openshift/release"

    if not jobs_dir.exists():
        return None

    # Search for job in periodics files
    for yaml_file in jobs_dir.glob("*-periodics.yaml"):
        try:
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)

            if not data or 'periodics' not in data:
                continue

            for job in data['periodics']:
                if job.get('name') == job_name:
                    return {'file': str(yaml_file), 'job': job}

        except Exception as e:
            print(f"Warning: Error parsing {yaml_file}: {e}", file=sys.stderr)
            continue

    return None


def extract_test_suite(job_config, release_repo):
    """
    Extract TEST_SUITE from job configuration.

    Looks in:
    1. Job spec.env directly
    2. Workflow steps (from step-registry)

    Args:
        job_config: Job configuration dict
        release_repo: Path to release repository

    Returns:
        dict with 'test_suite' and 'workflow' keys
    """
    test_suite = None
    workflow_name = None
    test_type = "suite"  # or "upgrade-conformance"

    # Check job env vars directly
    spec = job_config.get('spec', {})
    env_vars = spec.get('env', [])

    for env in env_vars:
        if env.get('name') == 'TEST_SUITE':
            test_suite = env.get('value')
            break

    # Check if it's an upgrade job
    job_name = job_config.get('name', '')
    if 'upgrade' in job_name.lower():
        test_type = "upgrade-conformance"

    # If not in job, check workflow
    if not test_suite:
        # Extract workflow name from job steps
        if 'steps' in spec:
            workflow_name = spec['steps'].get('workflow')

        if workflow_name:
            # Load workflow definition
            # Workflow path format: ci-operator/step-registry/{workflow-name-with-slashes}/{workflow-name}-workflow.yaml
            workflow_path = release_repo / f"ci-operator/step-registry/{workflow_name.replace('-', '/')}/{workflow_name}-workflow.yaml"

            if workflow_path.exists():
                try:
                    with open(workflow_path, 'r') as f:
                        workflow = yaml.safe_load(f)

                    # Check workflow env
                    env_vars = workflow.get('env', [])
                    for env in env_vars:
                        if env.get('name') == 'TEST_SUITE':
                            test_suite = env.get('value')
                            break

                    # Also check test steps
                    if not test_suite:
                        test_steps = workflow.get('test', [])
                        for step in test_steps:
                            if isinstance(step, dict) and 'ref' in step:
                                # Check if it's a conformance test step
                                ref_name = step['ref']
                                if 'conformance' in ref_name or 'suite' in ref_name:
                                    # Load step definition
                                    step_path = release_repo / f"ci-operator/step-registry/{ref_name.replace('-', '/')}/{ref_name}-ref.yaml"
                                    if step_path.exists():
                                        with open(step_path, 'r') as sf:
                                            step_def = yaml.safe_load(sf)
                                            step_env = step_def.get('env', [])
                                            for env in step_env:
                                                if env.get('name') == 'TEST_SUITE':
                                                    test_suite = env.get('value')
                                                    break

                except Exception as e:
                    print(f"Warning: Error loading workflow {workflow_name}: {e}", file=sys.stderr)

    # Default to "openshift/conformance/parallel" if not found in conformance jobs
    if not test_suite and test_type == "suite":
        # Check job name patterns
        if 'serial' in job_name.lower():
            test_suite = "openshift/conformance/serial"
        elif 'conformance' in job_name.lower() or 'e2e' in job_name.lower():
            test_suite = "openshift/conformance/parallel"

    return {
        'test_suite': test_suite,
        'workflow': workflow_name,
        'test_type': test_type
    }


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print("Usage: analyze_job.py <release-repo-path> <job-name>", file=sys.stderr)
        print("", file=sys.stderr)
        print("Analyzes a CI job to determine which test suite it uses.", file=sys.stderr)
        print("Outputs JSON with test_suite, workflow, and test_type.", file=sys.stderr)
        sys.exit(1)

    release_repo = Path(sys.argv[1])
    job_name = sys.argv[2]

    if not release_repo.exists():
        print(json.dumps({'error': f'Release repository not found: {release_repo}'}))
        sys.exit(1)

    # Find job configuration
    job_data = find_job_config(release_repo, job_name)

    if not job_data:
        print(json.dumps({'error': f'Job not found: {job_name}'}))
        sys.exit(1)

    # Extract test suite information
    suite_info = extract_test_suite(job_data['job'], release_repo)

    result = {
        'job_name': job_name,
        'config_file': job_data['file'],
        'test_suite': suite_info['test_suite'],
        'workflow': suite_info['workflow'],
        'test_type': suite_info['test_type']
    }

    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
