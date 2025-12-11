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

1. **Fetch CI Configuration Files**: Access the openshift/release repository
   - Clone or fetch the latest from `https://github.com/openshift/release`
   - Navigate to `ci-operator/config/openshift/openshift-tests-private/`
   - Identify all YAML configuration files

2. **Parse Configuration Files**: Read and parse each YAML file
   - Use a YAML parser to read configuration files
   - Look for job definitions in the `tests` section
   - Identify upgrade-related jobs by checking:
     - Job names containing "upgrade"
     - Test configurations with upgrade-related commands
     - Workflow references related to upgrades (e.g., `openshift-upgrade-*`)

3. **Filter Jobs** (if filter pattern provided): Apply optional filtering
   - Filter job names by the provided pattern (substring or regex)
   - Examples: "gcp", "aws", "4.15", "ovn", etc.

4. **Display Results**: Present the upgrade jobs in a clear format
   - List job names
   - Show relevant metadata (platform, version, workflow type)
   - Group by configuration file or platform if helpful
   - Include counts and summary statistics

5. **Error Handling**: Handle repository access and parsing errors
   - Check if repository is accessible
   - Handle YAML parsing errors gracefully
   - Report files that cannot be processed
   - Continue processing remaining files

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
