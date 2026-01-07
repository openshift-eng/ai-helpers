# List QE Jobs Skill

This skill provides a Python script to extract and list upgrade-related jobs from OpenShift QE CI configurations.

## Overview

The `parse_upgrade_jobs.py` script parses YAML configuration files from the `openshift/release` repository to identify upgrade-related test jobs in the `openshift-tests-private` CI configurations.

## Usage

```bash
python3 parse_upgrade_jobs.py <config-directory> [filter-pattern]
```

### Arguments

- `<config-directory>`: Path to the directory containing CI configuration YAML files
  - Typically: `.work/prow-qe-jobs/release/ci-operator/config/openshift/openshift-tests-private/`
- `[filter-pattern]`: Optional filter pattern to match against configuration filenames and job names

### Examples

```bash
# List all upgrade jobs
python3 parse_upgrade_jobs.py .work/prow-qe-jobs/release/ci-operator/config/openshift/openshift-tests-private/

# Filter by platform
python3 parse_upgrade_jobs.py .work/prow-qe-jobs/release/ci-operator/config/openshift/openshift-tests-private/ gcp

# Filter by version
python3 parse_upgrade_jobs.py .work/prow-qe-jobs/release/ci-operator/config/openshift/openshift-tests-private/ 4.15

# Filter by job type
python3 parse_upgrade_jobs.py .work/prow-qe-jobs/release/ci-operator/config/openshift/openshift-tests-private/ rosa
```

## Prerequisites

- Python 3.x
- PyYAML library: `pip3 install PyYAML`
- Access to the openshift/release repository (cloned locally)

## Output Format

The script outputs:
1. **Configuration files**: Groups jobs by their source configuration file
2. **Job listings**: Lists each upgrade job with platform information
3. **Summary statistics**: Total count and platform breakdown

Example:
```
Upgrade Jobs from openshift-tests-private:

Configuration: openshift-openshift-tests-private-release-4.15__amd64-nightly.yaml
  1. aws-ipi-sdn-live-migration-ovn-f60
  2. gcp-ipi-sdn-live-migration-ovn-f60
  3. vsphere-ipi-sdn-migration-ovn-f60

Total upgrade jobs found: 3

Breakdown by platform:
  - aws: 1
  - gcp: 1
  - vsphere: 1
```

## Implementation Details

### Job Detection

The script identifies upgrade-related jobs by checking:

1. **Job name keywords**:
   - "upgrade"
   - "update"
   - "migration"

2. **Workflow references**:
   - Checks the `workflow` field for upgrade-related keywords

3. **Step references**:
   - Inspects `pre`, `test`, and `post` steps for upgrade-related content

### Platform Detection

Platforms are extracted from job names by matching against known platforms:
- aws
- azure
- gcp
- vsphere
- openstack
- metal (for baremetal)
- alibaba
- nutanix
- powervs
- ibmcloud

### Filtering

The filter pattern (if provided) is matched against:
- Configuration filenames (case-insensitive)
- Individual job names (case-insensitive)

Jobs are included if the pattern matches either the configuration filename OR the job name.

## Error Handling

The script handles errors gracefully:
- YAML parsing errors are logged to stderr
- Files without test definitions are skipped
- Processing continues even if individual files fail
- Missing dependencies (PyYAML) are reported clearly
