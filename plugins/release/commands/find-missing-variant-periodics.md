---
description: Find periodic configurations missing for a target release version
argument-hint: <from-release> <to-release> [path]
---

## Name
release:find-missing-variant-periodics

## Synopsis
Identify periodic job configurations that exist for one release but are missing for another:
```
/release:find-missing-variant-periodics <from-release> <to-release> [path]
```

## Description
The `release:find-missing-variant-periodics` command identifies OpenShift periodic CI job configurations that exist for a source release version but are missing for a target release version. This is useful for discovering which periodic jobs need to be migrated when preparing a new release.

The command searches for periodic configuration files matching the source release pattern, then checks if corresponding configurations exist for the target release. It reports any missing configurations that should potentially be created.

Periodic jobs are CI tests that run on a schedule (via cron) rather than on pull requests. These are defined in files following the pattern: `*-release-{major.minor}__periodics.yaml` in the `ci-operator/config/` directory.

## Arguments

- `$1` (**from-release**): Source release version to search for existing configurations
  - Format: `{major}.{minor}` (e.g., `4.17`)
  - Alternative formats accepted: `release-4.17`, `4.17.0`
  - Examples: `4.17`, `4.18`, `4.19`

- `$2` (**to-release**): Target release version to check for missing configurations
  - Format: `{major}.{minor}` (e.g., `4.18`)
  - Alternative formats accepted: `release-4.18`, `4.18.0`
  - Examples: `4.18`, `4.19`, `4.20`

- `$3` (**path**): Optional directory path to search for periodic files
  - Default: `ci-operator/config/` (searches all subdirectories)
  - Can specify a subdirectory to limit scope
  - Examples: `ci-operator/config/openshift/etcd`, `ci-operator/config/openshift-priv`
  - Must be relative to the openshift/release repository root

## Implementation

Perform the following steps to identify missing periodic configurations:

1. **Normalize version numbers**
   - Parse and normalize from-release to `{major}.{minor}` format
   - Parse and normalize to-release to `{major}.{minor}` format
   - Strip any `release-` prefix or patch version numbers
   - Validate both version formats

2. **Determine search path**
   - If path argument provided: use as-is (relative to repo root)
   - If not provided: default to `ci-operator/config/`
   - Verify path exists in repository

3. **Find source periodic files**
   - Use Glob tool to search for pattern: `{search_path}/**/*-release-{from_version}__periodics.yaml`
   - Example pattern: `ci-operator/config/**/*-release-4.17__periodics.yaml`
   - Store list of found source files
   - If no files found:
     - Inform user: "No periodic files found for release {from_version} in {search_path}"
     - Exit

4. **Check for corresponding target files**
   - For each source file found:
     - Construct expected target filename by replacing:
       - `-release-{from_version}__periodics.yaml` with `-release-{to_version}__periodics.yaml`
     - Check if target file exists using Glob or by attempting to Read
     - Track whether target exists or is missing

5. **Build missing configurations report**
   - Create two lists:
     - **Missing**: Source files without corresponding target files
     - **Exists**: Source files that already have target files
   - Calculate statistics:
     - Total source files found
     - Number missing target files
     - Number with existing target files
     - Percentage missing

6. **Display results**
   - Show summary statistics:
     ```
     Periodic Configuration Analysis
     Source Release: {from_version}
     Target Release: {to_version}
     Search Path: {search_path}

     Found {total} periodic configuration(s) for release {from_version}
     Missing {missing_count} configuration(s) for release {to_version} ({percentage}%)
     Existing {exists_count} configuration(s) for release {to_version} ({percentage}%)
     ```

   - List missing configurations:
     ```
     Missing Configurations (need migration):
     - ci-operator/config/openshift/etcd/openshift-etcd-release-{to_version}__periodics.yaml
     - ci-operator/config/openshift/kube-apiserver/openshift-kube-apiserver-release-{to_version}__periodics.yaml
     ...
     ```

   - Optionally list existing configurations (if user wants to see them):
     ```
     Existing Configurations (already migrated):
     - ci-operator/config/openshift/oauth-server/openshift-oauth-server-release-{to_version}__periodics.yaml
     ...
     ```

7. **Provide next steps**
   - If missing configurations found:
     - Suggest using `/release:migrate-variant-periodics {from_version} {to_version} [path]` to migrate them
     - Suggest reviewing if all missing configs should actually be migrated
   - If no missing configurations:
     - Inform user: "All periodic configurations for {from_version} have corresponding {to_version} configurations."

## Return Value

- **Format**: Text report with statistics and file lists

The command outputs:
- Summary statistics (total, missing, existing counts and percentages)
- List of missing target configuration files that need to be created
- Optional list of existing target configuration files
- Suggested next steps for migration

## Examples

1. **Find all missing periodics from 4.17 to 4.18**:
   ```
   /release:find-missing-variant-periodics 4.17 4.18
   ```
   Searches all of `ci-operator/config/` and reports which 4.17 periodic configs don't have corresponding 4.18 configs.

2. **Check specific repository for missing periodics**:
   ```
   /release:find-missing-variant-periodics 4.18 4.19 ci-operator/config/openshift/cloud-credential-operator
   ```
   Checks only the cloud-credential-operator directory.

3. **Find missing periodics for an organization**:
   ```
   /release:find-missing-variant-periodics release-4.19 release-4.20 ci-operator/config/openshift
   ```
   Checks all repositories under the openshift organization.

4. **Check openshift-priv repositories**:
   ```
   /release:find-missing-variant-periodics 4.17 4.18 ci-operator/config/openshift-priv
   ```
   Checks private repository periodic configurations.

## Prerequisites

- User should be working in the `openshift/release` repository
- Source periodic files for the from-release version should exist

## Notes

- **Discovery tool**: This is a read-only analysis command - it doesn't modify any files

- **Use before migration**: Run this command before `/release:migrate-variant-periodics` to understand the scope of work

- **Version relationship**: Works in both directions - you can check newer-to-older or older-to-newer

- **Not all configs need migration**: Some repositories may intentionally not have periodic configs for certain releases (EOL, not applicable, etc.). Review the missing list to determine which should actually be migrated.

- **Complementary to migrate**: After running this command and identifying missing configs, use `/release:migrate-variant-periodics` to perform the actual migration

## Output Format Example

```
Periodic Configuration Analysis
===============================
Source Release: 4.17
Target Release: 4.18
Search Path: ci-operator/config/openshift

Results:
--------
Found 45 periodic configuration(s) for release 4.17
Missing 12 configuration(s) for release 4.18 (26.7%)
Existing 33 configuration(s) for release 4.18 (73.3%)

Missing Configurations (need migration):
-----------------------------------------
1. ci-operator/config/openshift/cloud-credential-operator/openshift-cloud-credential-operator-release-4.18__periodics.yaml
2. ci-operator/config/openshift/cluster-etcd-operator/openshift-cluster-etcd-operator-release-4.18__periodics.yaml
3. ci-operator/config/openshift/cluster-storage-operator/openshift-cluster-storage-operator-release-4.18__periodics.yaml
...

Next Steps:
-----------
To migrate missing configurations, run:
  /release:migrate-variant-periodics 4.17 4.18 ci-operator/config/openshift

To migrate specific repositories, run:
  /release:migrate-variant-periodics 4.17 4.18 ci-operator/config/openshift/cloud-credential-operator
```

## See Also

- `/release:migrate-variant-periodics` - Migrate periodic configurations from one release to another
- OpenShift CI Documentation: https://docs.ci.openshift.org/docs/how-tos/naming-your-ci-jobs/#configuration-for-periodic-jobs
- Periodic jobs overview in the OpenShift CI system
