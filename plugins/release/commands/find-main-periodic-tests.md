---
description: Find test definitions with periodic scheduling in main/master branch configurations
argument-hint: [path]
---

## Name
release:find-main-periodic-tests

## Synopsis
Identify test definitions with interval or cron scheduling in main/master branch configuration files:
```
/release:find-main-periodic-tests [path]
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

## Implementation

Perform the following steps to identify tests with periodic scheduling:

1. **Determine search path**
   - If path argument provided: use as-is (relative to repo root)
   - If not provided: default to `ci-operator/config/`
   - Verify path exists in repository

2. **Find main/master configuration files**
   - Use Glob tool to search for patterns:
     - `{search_path}/**/*-main.yaml`
     - `{search_path}/**/*-master.yaml`
   - Exclude files that end with `__periodics.yaml`
   - Store list of found configuration files

3. **Parse each configuration file**
   - Read the YAML file
   - Look for `tests:` section
   - For each test definition:
     - Check if it has an `as:` field (test name)
     - Check if it has either:
       - `interval:` field (e.g., `interval: 24h`, `interval: 168h`)
       - `cron:` field (e.g., `cron: 0 0 * * *`)
     - If both `as:` and (`interval:` or `cron:`), record this test

4. **Build report**
   - Group findings by file
   - For each file with periodic tests:
     - List the file path
     - List each test name (`as:` value)
     - Show the scheduling configuration (`interval:` or `cron:` value)
   - Calculate statistics:
     - Total files scanned
     - Files with periodic tests
     - Total periodic tests found

5. **Display results**
   - Show summary statistics:
     ```
     Periodic Tests in Main/Master Configurations
     ============================================
     Search Path: {search_path}

     Scanned {total_files} main/master configuration file(s)
     Found {files_with_periodic_tests} file(s) containing periodic tests
     Total periodic tests: {total_tests}
     ```

   - List files and their periodic tests:
     ```
     Files with Periodic Tests:
     ---------------------------

     1. ci-operator/config/openshift/origin/openshift-origin-main.yaml
        - test-name-1 (cron: 0 0 * * *)
        - test-name-2 (interval: 24h)

     2. ci-operator/config/openshift/kubernetes/openshift-kubernetes-master.yaml
        - periodic-test (interval: 168h)
     ```

6. **Provide recommendations**
   - Suggest reviewing these tests to determine if they should be:
     - Moved to `__periodics.yaml` files
     - Converted to presubmit/postsubmit tests
     - Kept as-is if there's a valid reason

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

3. **Check specific repository**:
   ```
   /release:find-main-periodic-tests ci-operator/config/openshift/origin
   ```
   Checks only the origin repository configuration.

4. **Check private repositories**:
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
