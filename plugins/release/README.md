# Release Plugin

A plugin to manage OpenShift release workflows, including periodic job configuration migration and analysis.

## Commands

### `/release:find-main-periodic-tests`

Find test definitions with periodic scheduling (`interval:` or `cron:`) in main/master branch configuration files. This helps identify tests that may need to be moved to dedicated `__periodics.yaml` files.

**Usage:**
```
/release:find-main-periodic-tests [path]
```

**Examples:**
```bash
# Find all periodic tests in main/master configs
/release:find-main-periodic-tests

# Check specific organization
/release:find-main-periodic-tests ci-operator/config/openshift

# Check specific repository
/release:find-main-periodic-tests ci-operator/config/openshift/origin
```

**Output:** Lists main/master configuration files containing tests with `interval:` or `cron:` fields, helping identify tests that should potentially be in dedicated periodic files.

### `/release:find-missing-periodics`

Find [periodic](https://docs.ci.openshift.org/docs/how-tos/naming-your-ci-jobs/#configuration-for-periodic-jobs) job configurations that exist for one release version but are missing for another. This is useful for discovering which periodic jobs need to be migrated when preparing a new release.

**Usage:**
```
/release:find-missing-periodics <from-release> <to-release> [path]
```

**Examples:**
```bash
# Find all missing 4.18 periodics that exist in 4.17
/release:find-missing-periodics 4.17 4.18

# Check specific repository
/release:find-missing-periodics 4.18 4.19 ci-operator/config/openshift/etcd

# Check entire organization
/release:find-missing-periodics 4.19 4.20 ci-operator/config/openshift
```

**Output:** Lists periodic configurations that need to be migrated, with statistics and suggested next steps.

### `/release:move-periodics-to-dedicated-file`

Move test definitions with periodic scheduling from main/master branch configuration files to dedicated `__periodics.yaml` files for a specific release. This helps properly organize periodic tests that are currently defined in the wrong location.

**Usage:**
```
/release:move-periodics-to-dedicated-file <target-release> [path] [--confirm-each-test]
```

**Examples:**
```bash
# Move all periodic tests to 4.21 release files (batch mode)
/release:move-periodics-to-dedicated-file 4.21

# Move periodic tests for specific organization
/release:move-periodics-to-dedicated-file 4.21 ci-operator/config/openshift

# Move periodic tests for specific repository
/release:move-periodics-to-dedicated-file 4.20 ci-operator/config/openshift/cluster-etcd-operator

# Confirm each test individually before moving (interactive mode)
/release:move-periodics-to-dedicated-file 4.21 --confirm-each-test

# Interactive mode with custom path
/release:move-periodics-to-dedicated-file 4.21 ci-operator/config/openshift --confirm-each-test
```

**Features:**
- Git branch verification and user confirmation before modifications
- Automatic detection of tests with `interval:` or `cron:` scheduling
- Creates or updates release-specific `__periodics.yaml` files
- Version string transformation to match target release
- Randomized cron schedule regeneration to avoid thundering herd
- Automatic removal of moved tests from source files in both modes
- Two operation modes:
  - **Batch mode (default)**: Display summary, single confirmation, then move and auto-cleanup all tests
  - **Interactive mode (--confirm-each-test)**: Confirm each test individually, auto-cleanup confirmed tests
- Handles duplicate test names when merging with existing files

### `/release:migrate-periodics`

Migrate [periodic](https://docs.ci.openshift.org/docs/how-tos/naming-your-ci-jobs/#configuration-for-periodic-jobs) job definitions from one OpenShift release to another. Automatically transforms version references, regenerates randomized cron schedules, and creates new configuration files.

**Usage:**
```
/release:migrate-periodics <from-release> <to-release> [path] [--skip-existing]
```

**Examples:**
```bash
# Migrate all periodic jobs from 4.17 to 4.18
/release:migrate-periodics 4.17 4.18

# Migrate specific repository
/release:migrate-periodics 4.18 4.19 ci-operator/config/openshift/cloud-credential-operator

# Migrate entire organization
/release:migrate-periodics 4.19 4.20 ci-operator/config/openshift

# Migrate with automatic skip of existing files (no prompts)
/release:migrate-periodics 4.17 4.18 --skip-existing

# Migrate specific path and skip existing files
/release:migrate-periodics 4.18 4.19 ci-operator/config/openshift --skip-existing
```

**Features:**
- Git branch verification and user confirmation before modifications
- Version string transformation (base images, builder images, registry paths, release names)
- Randomized cron schedule regeneration to avoid thundering herd
- Conflict detection and resolution for existing files
- Optional `--skip-existing` flag to automatically skip existing files without prompting
- Comprehensive error handling and reporting

## Typical Workflows

### Workflow 1: Organizing Existing Periodic Tests

When you need to move periodic tests from main/master configs to dedicated periodic files:

1. **Find periodic tests in main/master configs:**
   ```
   /release:find-main-periodic-tests ci-operator/config/openshift
   ```

2. **Review the findings** to determine which tests should be moved

3. **Move tests to dedicated periodic files:**
   ```
   /release:move-periodics-to-dedicated-file 4.21 ci-operator/config/openshift
   ```

4. **Verify the changes** and create a pull request

### Workflow 2: Migrating Periodic Jobs to New Release

When preparing periodic jobs for a new OpenShift release:

1. **Discover what needs migration:**
   ```
   /release:find-missing-periodics 4.17 4.18
   ```

2. **Review the missing configurations** to determine which should actually be migrated

3. **Perform the migration:**
   ```
   /release:migrate-periodics 4.17 4.18
   ```

4. **Verify the changes** and create a pull request

## Installation

```bash
/plugin install release@ai-helpers
```

## See Also

- [OpenShift CI Periodic Jobs Documentation](https://docs.ci.openshift.org/docs/how-tos/naming-your-ci-jobs/#configuration-for-periodic-jobs)
- [openshift/release Repository](https://github.com/openshift/release)
