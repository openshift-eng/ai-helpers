---
description: Find test definitions with periodic scheduling in main/master branch configurations
argument-hint: [path] [--verify-release=VERSION]
---

## Name
release:find-main-periodic-tests

## Synopsis
Identify test definitions with interval or cron scheduling in main/master branch configuration files:
```
/release:find-main-periodic-tests [path] [--verify-release=VERSION]
```

## Description
The `release:find-main-periodic-tests` command searches for CI operator configuration files for main/master branches (`-main.yaml` or `-master.yaml`) that contain test definitions with periodic scheduling (`interval:` or `cron:` fields). This is useful for identifying tests that should potentially be moved to dedicated periodic configuration files (`__periodics.yaml`).

In OpenShift CI, periodic tests are typically defined in separate `__periodics.yaml` files rather than in the main branch configuration files. This command helps identify tests that may be in the wrong location or that need to be reviewed for proper organization.

## Arguments

- `$1` (**path**): Optional directory path to search for configuration files
  - Default: `ci-operator/config/` (searches all subdirectories)
  - Can specify a subdirectory to limit scope
  - Examples: `ci-operator/config/openshift`, `ci-operator/config/openshift-priv`
  - Must be relative to the openshift/release repository root
  - Can also be `--verify-release=VERSION` if using default path

- `$2` (**--verify-release=VERSION**): Optional flag to filter tests by existing job definitions
  - Format: `--verify-release=4.21` or `--verify-release=release-4.21`
  - When specified, only tests that have corresponding job definitions in `ci-operator/jobs/{org}/{repo}/{org}-{repo}-release-{VERSION}-periodics.yaml` will be included in results
  - This helps identify tests that already have release-specific configurations
  - Can appear as either the 1st or 2nd argument
  - Examples:
    - `/release:find-main-periodic-tests --verify-release=4.21` (verify with default path)
    - `/release:find-main-periodic-tests ci-operator/config/openshift --verify-release=4.21` (verify with custom path)

## Implementation

Use the `release-find-main-periodic-tests` skill to identify and report tests with periodic scheduling in main/master branch configuration files.

The skill performs the following steps:

1. **Parse arguments**
   - Check if `--verify-release=VERSION` is provided in arguments
   - Extract release version if provided (normalize to `X.Y` format)
   - Determine search path (default or user-provided)
   - Verify path exists in repository

2. **Find main/master configuration files**
   - Search for `*-main.yaml` and `*-master.yaml` files
   - Exclude `__periodics.yaml` files (dedicated periodic files)
   - Create file list in `/tmp/main_master_files.txt`

3. **Run find_periodic_tests.py to parse files**
   - Execute: `python3 plugins/release/skills/release-find-main-periodic-tests/find_periodic_tests.py /tmp/main_master_files.txt`
   - Script identifies tests with `as:` field AND (`interval:` OR `cron:` field)
   - Outputs structured data with file paths and test details

4. **Optional: Verify release-specific jobs (if --verify-release provided)**
   - For each test found, check if corresponding job file exists:
     - Path: `ci-operator/jobs/{org}/{repo}/{org}-{repo}-release-{VERSION}-periodics.yaml`
   - Read the job file and verify test appears in `periodics` section
   - Filter out tests that don't have release-specific job definitions
   - Track statistics of filtered vs unfiltered tests

5. **Build and display report**
   - Show statistics:
     - Files scanned
     - Files with periodic tests
     - Total periodic tests found
     - If --verify-release: tests with release jobs vs tests without
   - List each file containing periodic tests
   - Show test names and their scheduling configuration
   - If --verify-release: indicate which tests have release jobs
   - Provide recommendations for next steps

The skill handles all YAML parsing, filtering, and report generation automatically.

## Return Value

- **Format**: Text report with file paths and test details

The command outputs:
- Summary statistics (files scanned, files with periodic tests, total tests)
- List of files containing periodic tests
- For each file: list of test names with their scheduling configuration
- Recommendations for next steps

## Examples

1. **Find all periodic tests in main/master configs**:
   ```
   /release:find-main-periodic-tests
   ```
   Searches all of `ci-operator/config/` for main/master files with periodic tests.

2. **Check specific organization**:
   ```
   /release:find-main-periodic-tests ci-operator/config/openshift
   ```
   Checks only files under the openshift organization.

3. **Find tests that already have release-4.21 job definitions**:
   ```
   /release:find-main-periodic-tests --verify-release=4.21
   ```
   Only shows tests that have corresponding job definitions in `ci-operator/jobs/.../release-4.21-periodics.yaml` files.

   **Use case:** Identify which tests are already configured for the target release and can be safely moved.

4. **Find tests with release jobs in specific organization**:
   ```
   /release:find-main-periodic-tests ci-operator/config/openshift --verify-release=4.21
   ```
   Combines path filtering with release verification - only shows openshift tests that have 4.21 jobs.

5. **Check specific repository**:
   ```
   /release:find-main-periodic-tests ci-operator/config/openshift/origin
   ```
   Checks only the origin repository configuration.

6. **Check private repositories**:
   ```
   /release:find-main-periodic-tests ci-operator/config/openshift-priv
   ```
   Checks configurations in the openshift-priv organization.

## Prerequisites

- User should be working in the `openshift/release` repository
- Configuration files should follow standard naming conventions

## Notes

- **Detection criteria**: A test is considered periodic if it has:
  - An `as:` field (test identifier/name)
  - AND either an `interval:` field OR a `cron:` field

- **File patterns matched**:
  - `*-main.yaml` (main branch configurations)
  - `*-master.yaml` (master branch configurations)
  - Excludes `*__periodics.yaml` (dedicated periodic files)

- **Common interval values**:
  - `24h` = daily
  - `168h` = weekly (7 days × 24 hours)
  - `720h` = monthly (30 days × 24 hours)

- **Cron format**: Standard cron syntax
  - `minute hour day-of-month month day-of-week`
  - Example: `0 0 * * *` = daily at midnight
  - Example: `0 0 * * 0` = weekly on Sunday at midnight

- **Why this matters**:
  - Periodic tests in main/master configs may run on every PR (unintended)
  - Dedicated `__periodics.yaml` files are the proper location for scheduled tests
  - Helps maintain clean separation between presubmit and periodic tests

- **Not all findings require action**: Some tests may legitimately use `interval:` or `cron:` in main branch configs for specific CI behaviors

## Output Format Example

```
Periodic Tests in Main/Master Configurations
============================================
Search Path: ci-operator/config/openshift

Results:
--------
Scanned 156 main/master configuration file(s)
Found 8 file(s) containing periodic tests
Total periodic tests: 14

Files with Periodic Tests:
---------------------------

1. ci-operator/config/openshift/origin/openshift-origin-main.yaml
   Tests:
   - e2e-aws-upgrade (interval: 24h)
   - e2e-gcp-upgrade (interval: 24h)
   - images (interval: 2h)

2. ci-operator/config/openshift/kubernetes/openshift-kubernetes-master.yaml
   Tests:
   - periodic-conformance (cron: 0 */6 * * *)
   - periodic-unit (interval: 12h)

3. ci-operator/config/openshift/installer/openshift-installer-main.yaml
   Tests:
   - e2e-metal-ipi (cron: 0 0 * * 0)

... (additional files)

Recommendations:
----------------
Review these periodic tests to determine if they should be:
1. Moved to dedicated __periodics.yaml files
2. Converted to presubmit or postsubmit tests
3. Kept in main/master configs if there's a specific reason

To create a periodic configuration file for a repository:
  - File naming: {org}-{repo}-{branch}__periodics.yaml
  - Example: openshift-origin-main__periodics.yaml

See: https://docs.ci.openshift.org/docs/how-tos/naming-your-ci-jobs/#configuration-for-periodic-jobs
```

## See Also

- `/release:find-missing-periodics` - Find missing periodic configurations between releases
- `/release:migrate-periodics` - Migrate periodic configurations from one release to another
- OpenShift CI Documentation: https://docs.ci.openshift.org/docs/how-tos/naming-your-ci-jobs/#configuration-for-periodic-jobs
- Periodic jobs overview in the OpenShift CI system
