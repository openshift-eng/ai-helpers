# Release Plugin

A plugin to manage OpenShift release workflows, including periodic job configuration migration and analysis.

## Commands

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

## Typical Workflow

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
