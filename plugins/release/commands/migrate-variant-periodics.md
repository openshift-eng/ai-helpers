---
description: Migrate OpenShift periodic CI job definitions from one release version to another
argument-hint: <from-release> <to-release> [path] [--skip-existing]
---

## Name
release:migrate-variant-periodics

## Synopsis
Migrate periodic job configuration files from one OpenShift release version to another:
```
/release:migrate-variant-periodics <from-release> <to-release> [path] [--skip-existing]
```

## Description
The `release:migrate-variant-periodics` command automates the migration of OpenShift periodic CI job definitions between release versions. It finds all periodic configuration files matching the source release version, transforms version-specific references, regenerates randomized cron schedules, and creates new configuration files for the target release.

Periodic jobs are CI tests that run on a schedule (via cron) rather than on pull requests. These are defined in files following the pattern: `*-release-{major.minor}__periodics.yaml` in the `ci-operator/config/` directory.

## Arguments

- `$1` (**from-release**): Source release version to migrate from
  - Format: `{major}.{minor}` (e.g., `4.17`)
  - Alternative formats accepted: `release-4.17`, `4.17.0`
  - Examples: `4.17`, `4.18`, `4.19`

- `$2` (**to-release**): Target release version to migrate to
  - Format: `{major}.{minor}` (e.g., `4.18`)
  - Alternative formats accepted: `release-4.18`, `4.18.0`
  - Examples: `4.18`, `4.19`, `4.20`

- `$3` (**path**): Optional directory path to search for periodic files
  - Default: `ci-operator/config/` (searches all subdirectories)
  - Can specify a subdirectory to limit scope
  - Examples: `ci-operator/config/openshift/etcd`, `ci-operator/config/openshift-priv`
  - Must be relative to the openshift/release repository root

- `$4` (**--skip-existing**): Optional flag to automatically skip existing files
  - If specified, the command will not prompt to overwrite existing target files
  - Existing files will be automatically skipped without user interaction
  - Only new files (where target doesn't exist) will be created
  - Can appear as either the 3rd or 4th argument for flexibility
  - Examples:
    - `/release:migrate-variant-periodics 4.17 4.18 --skip-existing` (skip existing, use default path)
    - `/release:migrate-variant-periodics 4.17 4.18 ci-operator/config/openshift --skip-existing` (skip existing with custom path)
  - Useful for automation and batch operations where you don't want to overwrite existing migrations

## Implementation

Pass the user's request to the `release-migrate-variant-periodics` skill, which will:

1. **Verify git branch and get user confirmation**
   - Check current git branch using `git rev-parse --abbrev-ref HEAD`
   - Display branch name to user
   - Warn if on main/master branch
   - Ask user to confirm they want to proceed with modifications on this branch
   - Exit immediately if user declines

2. **Parse arguments and normalize inputs**
   - Parse all arguments to extract: from-release, to-release, path, and --skip-existing flag
   - The --skip-existing flag can appear in position 3 or 4
   - If a non-path argument is --skip-existing, treat it as the flag
   - Normalize from-release and to-release versions to {major}.{minor} format
   - Validate version format and relationship
   - Determine search path (use provided path or default to ci-operator/config/)

3. **Find source periodic files**
   - Search for files matching pattern: `*-release-{from-release}__periodics.yaml`
   - Display list of found files
   - Ask user for confirmation before proceeding

4. **Check for existing target files**
   - For each source file, check if target already exists
   - If --skip-existing flag is set:
     - Automatically skip all existing files without prompting
     - Only include non-existing files in migration plan
   - If --skip-existing flag is NOT set:
     - Ask user whether to overwrite each existing file
     - Use AskUserQuestion tool for each conflict
   - Build migration plan with actions for each file (create/overwrite/skip)

5. **Perform file migration**
   - Read each source file
   - Transform version references:
     - Base images: `ocp_4_17_*` → `ocp_4_18_*`
     - Builder tags: `openshift-4.17` → `openshift-4.18`
     - Registry paths: `ocp/4.17:` → `ocp/4.18:`
     - Release names: `name: "4.17"` → `name: "4.18"`
     - Branch metadata: `branch: release-4.17` → `branch: release-4.18`
   - Regenerate randomized cron schedules to avoid thundering herd
   - Validate transformed YAML

6. **Write target files**
   - Create new periodic configuration files
   - Track success/failure for each file
   - Handle write errors gracefully

7. **Report results**
   - Generate migration summary
   - Display file-level details
   - Provide next steps for testing and validation

The skill handles all implementation details including file discovery, version string transformation, cron schedule regeneration, and error handling.

## Return Value

- **Format**: Text summary of migration results

The command outputs:
- Count of files found for migration
- List of files that will be migrated
- Confirmation prompts for user approval
- Progress updates during migration
- Final summary with counts of successful/skipped/failed migrations
- Suggestions for next steps (testing, PR creation)

## Examples

1. **Migrate all periodic jobs from 4.17 to 4.18**:
   ```
   /release:migrate-variant-periodics 4.17 4.18
   ```
   This searches all of `ci-operator/config/` for files matching `*-release-4.17__periodics.yaml` and creates corresponding `*-release-4.18__periodics.yaml` files.

2. **Migrate periodic jobs for a specific repository**:
   ```
   /release:migrate-variant-periodics 4.18 4.19 ci-operator/config/openshift/cloud-credential-operator
   ```
   This limits the search to the `cloud-credential-operator` directory.

3. **Migrate all openshift organization periodics**:
   ```
   /release:migrate-variant-periodics release-4.19 release-4.20 ci-operator/config/openshift
   ```
   This searches all repositories under the `openshift` organization directory.

4. **Migrate periodics for openshift-priv repositories**:
   ```
   /release:migrate-variant-periodics 4.17 4.18 ci-operator/config/openshift-priv
   ```
   This handles private repository periodic configurations.

5. **Migrate with automatic skip of existing files**:
   ```
   /release:migrate-variant-periodics 4.17 4.18 --skip-existing
   ```
   This migrates all periodic jobs but automatically skips any files that already exist for 4.18, without prompting for each one.

6. **Migrate specific path with skip-existing**:
   ```
   /release:migrate-variant-periodics 4.18 4.19 ci-operator/config/openshift --skip-existing
   ```
   This migrates periodic jobs for the openshift organization, skipping any existing 4.19 configurations without user interaction.

## Prerequisites

- User should be working in the `openshift/release` repository
- User should have write permissions to create new files
- Source periodic files for the from-release version should exist

## Notes

- **Cron schedules**: The command automatically regenerates randomized cron schedules to distribute load and avoid thundering herd problems. The new schedules maintain the same frequency (monthly, weekly, etc.) but use different times.

- **Version consistency**: All version references in the file are updated consistently, including base images, builder images, registry paths, release names, and metadata.

- **Golang versions**: The command preserves golang versions unless user explicitly confirms changes. Golang version updates are not automatic.

- **Cluster profiles**: Existing cluster profile configurations are preserved unless user specifies changes.

- **YAML formatting**: While the command attempts to preserve formatting, some YAML comments may be lost during programmatic editing.

- **Skip existing files**: Use the `--skip-existing` flag to automatically skip files that already exist for the target release. This is useful for:
  - Re-running migrations without overwriting already-migrated files
  - Batch operations where you want to avoid interactive prompts
  - Automation scripts that should not require user interaction
  - Incremental migrations where some files have already been manually created

## See Also

- OpenShift CI Documentation: https://docs.ci.openshift.org/docs/how-tos/naming-your-ci-jobs/#configuration-for-periodic-jobs
- Periodic jobs overview in the OpenShift CI system
- `make jobs` command for regenerating Prowjob configurations
