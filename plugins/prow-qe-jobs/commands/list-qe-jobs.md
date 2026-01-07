---
description: Lists upgrade jobs from openshift-tests-private CI configurations
argument-hint: "[filter-pattern]"
---

## Name
prow-qe-jobs:list-qe-jobs

## Synopsis
Extract and list upgrade jobs from OpenShift QE CI configurations:
```
/prow-qe-jobs:list-qe-jobs [filter-pattern]
```

## Description
The `prow-qe-jobs:list-qe-jobs` command extracts upgrade-related job configurations from the openshift-tests-private repository's CI operator configs. It scans configuration files in `https://github.com/openshift/release/tree/master/ci-operator/config/openshift/openshift-tests-private` and identifies jobs related to upgrade testing.

## Implementation

This command uses a Python helper script to extract upgrade jobs from OpenShift CI configurations.

1. **Ensure PyYAML is installed**:
   ```bash
   pip3 install PyYAML
   ```

2. **Clone or update the openshift/release repository**:
   ```bash
   mkdir -p .work/prow-qe-jobs
   cd .work/prow-qe-jobs
   if [ -d "release" ]; then
     cd release && git pull
   else
     git clone --depth 1 https://github.com/openshift/release.git
   fi
   ```

3. **Run the Python script to extract and display upgrade jobs**:
   ```bash
   python3 plugins/prow-qe-jobs/skills/list-qe-jobs/parse_upgrade_jobs.py \
     .work/prow-qe-jobs/release/ci-operator/config/openshift/openshift-tests-private/ \
     [filter-pattern]
   ```

The script performs the following:
- **Parses YAML files**: Reads all configuration files from the openshift-tests-private directory
- **Identifies upgrade jobs**: Detects jobs by checking:
  - Job names containing "upgrade", "update", or "migration"
  - Workflow references with upgrade-related keywords
  - Step references with upgrade-related content
- **Filters results**: If a filter pattern is provided, matches against both configuration filenames and job names
- **Displays results**: Groups jobs by configuration file, extracts platform information, and provides summary statistics

## Return Value

**Format**: A list of upgrade job names with relevant metadata

Example output:
```
Upgrade Jobs from openshift-tests-private:

Configuration: openshift-openshift-tests-private-release-4.15__amd64.yaml
1. aws-ipi-ovn-ipsec-to-4.15-ci
2. azure-ipi-disc-fullypriv-to-4.15-ci
3. gcp-ipi-ovn-upgrade-4.14-micro-to-4.15-ci

Configuration: openshift-openshift-tests-private-release-4.16__amd64.yaml
1. aws-ipi-ovn-ipsec-to-4.16-ci
2. gcp-ipi-ovn-upgrade-4.15-minor-to-4.16-ci

Total upgrade jobs found: 5
```

## Examples

1. **List all upgrade jobs**:
   ```
   /prow-qe-jobs:list-qe-jobs
   ```

2. **Filter by platform (e.g., GCP)**:
   ```
   /prow-qe-jobs:list-qe-jobs gcp
   ```

3. **Filter by version (e.g., 4.15)**:
   ```
   /prow-qe-jobs:list-qe-jobs 4.15
   ```

4. **Filter by upgrade type (e.g., micro)**:
   ```
   /prow-qe-jobs:list-qe-jobs micro
   ```

## Arguments

- `$1`: Optional filter pattern to match job names (substring match)

## Notes

- The command requires network access to fetch the latest configurations from GitHub
- If the openshift/release repository is already cloned locally, it can use the local copy
- Job definitions may vary between release branches; this command targets the master branch by default
