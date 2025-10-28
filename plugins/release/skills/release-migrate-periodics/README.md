# Release Migrate Periodics Skill

This skill automates the migration of OpenShift periodic CI job definitions from one release version to another by transforming version-specific references and regenerating randomized cron schedules.

## Overview

Periodic jobs are CI tests that run on a schedule (via cron) rather than on pull requests. They are defined in YAML configuration files following the pattern `*-release-{major.minor}__periodics.yaml` in the `ci-operator/config/` directory of the openshift/release repository.

When a new OpenShift release is branched, these periodic configurations need to be migrated to the new release version. This skill automates that process by:
- Finding all periodic files for the source release
- Transforming version-specific references
- Regenerating randomized cron schedules
- Creating new configuration files for the target release

## Components

### SKILL.md
Claude Code skill definition that provides detailed implementation instructions for the AI assistant, including:
- Input validation and normalization
- File discovery patterns
- Version string transformation rules
- Cron schedule regeneration algorithm
- Error handling strategies

## Migration Transformations

The skill performs the following transformations when migrating from version X.Y to version A.B:

### 1. Base Images
```yaml
# Before (4.17)
ocp_4_17_base-rhel9:
  name: "4.17"
  tag: base-rhel9

# After (4.18)
ocp_4_18_base-rhel9:
  name: "4.18"
  tag: base-rhel9
```

### 2. Builder Images
```yaml
# Before (4.17)
ocp_builder_rhel-8-golang-1.22-openshift-4.17:
  name: builder
  tag: rhel-8-golang-1.22-openshift-4.17

# After (4.18)
ocp_builder_rhel-8-golang-1.22-openshift-4.18:
  name: builder
  tag: rhel-8-golang-1.22-openshift-4.18
```

### 3. Registry Paths
```yaml
# Before (4.17)
- registry.ci.openshift.org/ocp/4.17:base-rhel9

# After (4.18)
- registry.ci.openshift.org/ocp/4.18:base-rhel9
```

### 4. Release Names
```yaml
# Before (4.17)
releases:
  latest:
    integration:
      name: "4.17"

# After (4.18)
releases:
  latest:
    integration:
      name: "4.18"
```

### 5. Branch Metadata
```yaml
# Before (4.17)
zz_generated_metadata:
  branch: release-4.17
  org: openshift
  repo: cloud-credential-operator

# After (4.18)
zz_generated_metadata:
  branch: release-4.18
  org: openshift
  repo: cloud-credential-operator
```

### 6. Cron Schedules
```yaml
# Before (randomized for 4.17)
cron: 11 4 14 8 *

# After (re-randomized for 4.18)
cron: 37 15 14 8 *
```

**Note:** Cron schedules are regenerated to avoid thundering herd problems. The new schedules maintain the same frequency (monthly, weekly, daily) but use different randomized times.

## Resource Specification Format

The skill accepts version numbers in several formats:

**Input formats:**
- `4.17` - Simple major.minor format (preferred)
- `release-4.17` - Full branch name format
- `4.17.0` - With patch version (will be normalized to 4.17)

**File pattern:**
- Source: `*-release-{from-version}__periodics.yaml`
- Target: `*-release-{to-version}__periodics.yaml`

**Path specification:**
- Default: `ci-operator/config/` (searches all subdirectories)
- Specific repo: `ci-operator/config/openshift/etcd`
- Organization: `ci-operator/config/openshift-priv`

## Workflow

1. **Branch Verification (Safety Check)**
   - Check current git branch
   - Display branch name to user
   - Warn if on main/master branch
   - Ask user to confirm proceeding with modifications
   - Exit if user declines

2. **Input Validation**
   - Normalize version numbers to `{major}.{minor}` format
   - Validate version format and relationship
   - Determine search path

3. **File Discovery**
   - Search for files matching pattern
   - Display list of files found
   - Get user confirmation

4. **Conflict Resolution**
   - Check if target files already exist
   - Ask user whether to overwrite
   - Build migration plan

5. **Transformation**
   - Read source file
   - Transform version references
   - Regenerate cron schedules
   - Validate YAML syntax

6. **File Creation**
   - Write new periodic files
   - Track success/failure
   - Handle errors gracefully

7. **Reporting**
   - Display migration summary
   - Report successes and failures
   - Suggest next steps

## Usage Examples

### Migrate all periodics from 4.17 to 4.18
```
/release:migrate-periodics 4.17 4.18
```
Searches all of `ci-operator/config/` for files matching `*-release-4.17__periodics.yaml`.

### Migrate periodics for a specific repository
```
/release:migrate-periodics 4.18 4.19 ci-operator/config/openshift/cloud-credential-operator
```
Limits search to the cloud-credential-operator directory.

### Migrate all openshift organization periodics
```
/release:migrate-periodics release-4.19 release-4.20 ci-operator/config/openshift
```
Processes all repositories under the openshift organization.

### Migrate openshift-priv periodics
```
/release:migrate-periodics 4.17 4.18 ci-operator/config/openshift-priv
```
Handles private repository periodic configurations.

## Prerequisites

1. **openshift/release repository**
   - Must be working in or have access to the openshift/release repository
   - Source periodic files must exist for the from-release version

2. **Write permissions**
   - Ability to create new files in the repository

3. **Claude Code**
   - Command must be invoked via Claude Code `/release:migrate-periodics`

## Output

### Console Output
The skill provides progress updates including:
- Number of files found
- List of files to be migrated
- Confirmation prompts
- Success/failure status for each file
- Final migration summary

### Generated Files
New periodic configuration files in the same directory structure:
```
ci-operator/config/openshift/cloud-credential-operator/
├── openshift-cloud-credential-operator-release-4.17__periodics.yaml  # Source
└── openshift-cloud-credential-operator-release-4.18__periodics.yaml  # Created
```

## Next Steps After Migration

1. **Validate YAML syntax**
   ```bash
   yamllint ci-operator/config/**/*-release-{to-version}__periodics.yaml
   ```

2. **Review changes**
   ```bash
   git diff ci-operator/config/
   ```

3. **Regenerate Prowjob configs**
   ```bash
   make jobs
   ```

4. **Test configurations**
   - Verify periodic jobs are properly configured
   - Check cron schedules are distributed appropriately
   - Confirm version references are correct

5. **Create pull request**
   ```bash
   git checkout -b periodic-migration-4.17-to-4.18
   git add ci-operator/config/
   git commit -m "Migrate periodic jobs from 4.17 to 4.18"
   git push origin periodic-migration-4.17-to-4.18
   ```

## Important Notes

### Cron Schedule Randomization
Cron schedules are regenerated with randomized values to avoid thundering herd problems where many jobs start at the same time. The new schedules:
- Maintain the same frequency (monthly, weekly, daily)
- Use different randomized times
- Avoid midnight (prefer hours 1-23)
- Distribute load throughout the day

### Version Consistency
All version references in each file are updated consistently:
- Base image references
- Builder image tags
- Registry paths
- Release names
- Branch metadata
- Filenames

### Preserved Elements
The following are NOT automatically changed unless user confirms:
- Golang versions (e.g., golang-1.22)
- RHEL versions (e.g., rhel-8, rhel-9)
- Cluster profiles
- Feature flags
- Test commands and workflows

### YAML Formatting
While the skill attempts to preserve formatting, some YAML comments or formatting may be lost during programmatic editing. Review the generated files to ensure they meet project standards.

## Using with Claude Code

When you use the `/release:migrate-periodics` command, Claude automatically invokes this skill. The skill provides detailed step-by-step instructions that guide Claude through:
- Validating inputs
- Finding source files
- Transforming configurations
- Creating target files
- Reporting results

You can simply ask:
```
/release:migrate-periodics 4.17 4.18
```

Claude will execute the complete workflow and provide a detailed summary of the migration.

## Troubleshooting

### No files found
- Verify version number is correct
- Check if release uses different naming (e.g., `main` instead of `release-*`)
- Verify path is correct relative to repository root
- Try searching without path restriction first

### File already exists
- Review existing file to see if migration already happened
- Use diff to compare with what would be generated
- Choose to overwrite if regeneration is needed
- Skip if file was manually customized

### Version mismatch in file
- Some files may have unexpected version formats
- Check if file has custom configuration
- Review file manually if automatic migration fails
- Report in migration summary for manual review

### Permission errors
- Verify write permissions in repository
- Check git status and file locks
- Ensure no other process is modifying files
- Continue with other files and report failures

## See Also

- [OpenShift CI Periodic Jobs Documentation](https://docs.ci.openshift.org/docs/how-tos/naming-your-ci-jobs/#configuration-for-periodic-jobs)
- [CI Operator Configuration](https://docs.ci.openshift.org/docs/architecture/ci-operator/)
- [openshift/release Repository](https://github.com/openshift/release)
