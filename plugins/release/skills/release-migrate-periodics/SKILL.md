---
name: Release Migrate Periodics
description: Migrate OpenShift periodic CI job definitions from one release version to another by copying and transforming YAML configuration files
---

# Release Migrate Periodics

This skill automates the migration of OpenShift periodic CI job definitions from one release version to another. Periodic jobs are CI tests that run on a schedule (via cron) rather than on pull requests.

## When to Use This Skill

Use this skill when the user wants to:
- Migrate periodic job definitions to a new OpenShift release version
- Copy and update periodic configurations from one version to another (e.g., 4.17 → 4.18)
- Prepare periodic jobs for a newly branched OpenShift release
- Bulk update version-specific references in periodic job configurations

## Prerequisites

Before starting, verify these prerequisites:

1. **Working in openshift/release repository**
   - The user should have the openshift/release repository available
   - Check current working directory or ask user for repository path
   - Periodic files are located under `ci-operator/config/`

2. **Understanding of file naming pattern**
   - Periodic files follow pattern: `{org}-{repo}-{branch}__periodics.yaml`
   - Branch format: `release-{major}.{minor}` or `main`
   - Example: `openshift-cloud-credential-operator-release-4.17__periodics.yaml`

## Input Format

The user will provide:

1. **from-release** (required) - Source release version
   - Format: `{major}.{minor}` (e.g., `4.17`)
   - Alternative formats accepted: `release-4.17`, `4.17.0`
   - Normalize to `{major}.{minor}` for processing

2. **to-release** (required) - Target release version
   - Format: `{major}.{minor}` (e.g., `4.18`)
   - Alternative formats accepted: `release-4.18`, `4.18.0`
   - Normalize to `{major}.{minor}` for processing

3. **path** (optional) - Specific directory to process
   - Default: `ci-operator/config/`
   - Can specify subdirectory: `ci-operator/config/openshift/etcd`
   - Must be relative to repository root

4. **--skip-existing** (optional) - Flag to automatically skip existing files
   - Can appear as either the 3rd or 4th argument
   - If present, automatically skip all existing target files without prompting
   - If not present, prompt user for each existing file
   - Examples:
     - `4.17 4.18 --skip-existing` (default path, skip existing)
     - `4.17 4.18 ci-operator/config/openshift --skip-existing` (custom path, skip existing)

## Implementation Steps

### Step 1: Verify Git Branch and Get User Confirmation

**CRITICAL:** Before making any modifications, check the current git branch and confirm with user.

1. **Check current git branch**
   - Use `git rev-parse --abbrev-ref HEAD` to get current branch name
   - If command fails, warn user that this doesn't appear to be a git repository
   - If not in a git repository, ask if they want to continue anyway

2. **Display branch information**
   - Show the user: "You are currently on branch: `{branch_name}`"
   - If on `main` or `master`, add a warning:
     - "⚠️  WARNING: You are on the main branch. Changes will be made directly to main."
   - If on another branch, show:
     - "Changes will be made to this branch."

3. **Ask for user confirmation**
   - Use AskUserQuestion tool with:
     - Question: "Do you want to proceed with migrating periodic files on branch `{branch_name}`?"
     - Options:
       - "Yes, proceed" - Continue with migration
       - "No, cancel" - Abort the migration
   - If user selects "No, cancel":
     - Display: "Migration cancelled. No files were modified."
     - Exit skill immediately
   - If user selects "Yes, proceed":
     - Display: "Proceeding with migration on branch `{branch_name}`"
     - Continue to next step

4. **Handle git errors gracefully**
   - If not in a git repository:
     - Ask user: "This doesn't appear to be a git repository. Do you want to continue anyway?"
     - Options: "Yes, continue" or "No, cancel"
   - If git command fails for other reasons:
     - Log the error
     - Ask user if they want to proceed without branch verification

### Step 2: Parse Arguments and Normalize Version Numbers

1. **Parse all arguments**
   - Argument 1: `from_version` (required)
   - Argument 2: `to_version` (required)
   - Arguments 3 and/or 4: Check for `path` and/or `--skip-existing` flag
   - Parse logic:
     - If argument contains `--skip-existing`: set `skip_existing = True`
     - If argument looks like a path (contains `/` or starts with `ci-operator`): set as `path`
     - If argument 3 is `--skip-existing`: use default path, enable skip mode
     - If argument 3 is a path and argument 4 is `--skip-existing`: use custom path, enable skip mode
   - Store parsed values: `from_version`, `to_version`, `path`, `skip_existing` (boolean)

2. **Normalize from-release**
   - Extract major.minor from input (strip `release-` prefix if present)
   - Remove patch version if provided (e.g., `4.17.0` → `4.17`)
   - Validate format: must be `{digit(s)}.{digit(s)}`
   - Store as: `from_version` (e.g., `4.17`)

3. **Normalize to-release**
   - Extract major.minor from input (strip `release-` prefix if present)
   - Remove patch version if provided
   - Validate format: must be `{digit(s)}.{digit(s)}`
   - Store as: `to_version` (e.g., `4.18`)

4. **Validate version relationship**
   - Ensure `from_version != to_version`
   - Optionally warn if `to_version` is older than `from_version`

5. **Determine search path**
   - If path provided: use as-is (relative to repo root)
   - If not provided: default to `ci-operator/config/`
   - Verify path exists in repository

6. **Log parsed configuration**
   - Display to user:
     - "Migrating from release {from_version} to {to_version}"
     - "Search path: {path}"
     - "Skip existing files: {Yes/No}" (based on skip_existing flag)

### Step 3: Find Source Periodic Files

1. **Construct search pattern**
   - Pattern: `{search_path}/**/*-release-{from_version}__periodics.yaml`
   - Example: `ci-operator/config/**/*-release-4.17__periodics.yaml`
   - Use Glob tool to find matching files

2. **Validate search results**
   - If no files found, inform user:
     - "No periodic files found for release {from_version} in {search_path}"
     - Suggest checking if the version number is correct
     - Suggest checking if the path is correct
   - If files found, inform user of count:
     - "Found {count} periodic file(s) for release {from_version}"

3. **Display found files**
   - List all files that will be migrated
   - Show abbreviated paths for readability
   - Ask user for confirmation before proceeding

### Step 4: Check for Existing Target Files

For each source file found:

1. **Construct target filename**
   - Replace `-release-{from_version}__periodics.yaml` with `-release-{to_version}__periodics.yaml`
   - Example:
     - Source: `openshift-etcd-operator-release-4.17__periodics.yaml`
     - Target: `openshift-etcd-operator-release-4.18__periodics.yaml`

2. **Check if target exists**
   - Use Glob or Read to check if target file already exists
   - If target exists:
     - **If skip_existing flag is True:**
       - Automatically mark action as "skip"
       - Log: "Skipping {target_path} (already exists)"
       - Do NOT prompt user
     - **If skip_existing flag is False (default):**
       - Use AskUserQuestion to ask if they want to overwrite
       - Options: "Overwrite", "Skip this file", "Cancel entire migration"
       - Track user's decision for this file
       - If user selects "Cancel entire migration": exit immediately
   - If target does NOT exist:
     - Mark action as "create"

3. **Build migration plan**
   - Create list of files to migrate
   - Include: source path, target path, action (create/overwrite/skip)
   - Count actions:
     - Files to create (new migrations)
     - Files to overwrite (re-migrations)
     - Files to skip (existing, not changing)
   - Display summary:
     - "Migration plan: {create_count} to create, {overwrite_count} to overwrite, {skip_count} to skip"

### Step 5: Perform File Migration

For each file in the migration plan (if action is create or overwrite):

1. **Read source file**
   - Use Read tool to read entire source file
   - Handle any read errors (file permissions, etc.)

2. **Transform file content**
   - Replace all version references following these patterns:

   **Base images section:**
   - `ocp_{from_version_underscore}_` → `ocp_{to_version_underscore}_`
   - Example: `ocp_4_17_base-rhel9` → `ocp_4_18_base-rhel9`

   **Builder images:**
   - `openshift-{from_version}` → `openshift-{to_version}`
   - Example: `rhel-8-golang-1.22-openshift-4.17` → `rhel-8-golang-1.22-openshift-4.18`

   **Registry paths:**
   - `ocp/{from_version}:` → `ocp/{to_version}:`
   - Example: `registry.ci.openshift.org/ocp/4.17:` → `registry.ci.openshift.org/ocp/4.18:`

   **Release name:**
   - `name: "{from_version}"` → `name: "{to_version}"`
   - Example: `name: "4.17"` → `name: "4.18"`

   **Branch metadata:**
   - `branch: release-{from_version}` → `branch: release-{to_version}`
   - Example: `branch: release-4.17` → `branch: release-4.18`

3. **Regenerate cron schedules (CRITICAL)**
   - Periodic jobs use cron schedules that should be randomized to avoid thundering herd
   - For each test with a `cron:` field:
     - Generate a new randomized cron schedule
     - Keep the same frequency/pattern as original if possible
     - Use format: `minute hour day-of-month month day-of-week`
     - Randomize minute and hour values
     - Example: `11 4 14 8 *` → `37 15 14 8 *` (same day/month, different time)

   **Cron generation strategy:**
   - Parse existing cron to understand frequency
   - If monthly (specific day-of-month): keep day, randomize time
   - If weekly: keep day-of-week, randomize time
   - If daily: randomize time
   - Ensure generated times are distributed throughout the day
   - Avoid midnight to reduce peak load (prefer 1-23 hours)

4. **Handle special cases**
   - **Golang version updates:**
     - May need to update golang versions for newer releases
     - Check if golang version needs updating (e.g., 1.22 → 1.23)
     - Only update if user confirms or if documented requirement exists

   - **RHEL version updates:**
     - Generally RHEL versions stay the same during minor version migrations
     - Only update if specifically required

   - **Cluster profiles:**
     - Some profiles may change between versions (e.g., `aws` → `aws-3`)
     - These changes are environment-specific
     - Preserve existing profiles unless user specifies changes

   - **Feature flags:**
     - Preserve feature set configurations (e.g., `TechPreviewNoUpgrade`)
     - These are test-specific, not version-specific

5. **Validate transformed content**
   - Ensure YAML is still valid after transformations
   - Check that no unintended replacements occurred
   - Verify all version references were updated consistently

### Step 6: Write Target Files

For each transformed file:

1. **Write new file**
   - Use Write tool to create target file
   - Path: constructed target path from Step 3
   - Content: transformed YAML from Step 4

2. **Track success/failure**
   - Log successful migrations
   - Capture any write errors
   - Track which files were created/updated

3. **Handle errors**
   - If write fails, log error and continue with next file
   - Don't abort entire migration on single file failure
   - Report all failures at end

### Step 7: Report Results

1. **Generate migration summary**
   - Total files processed
   - Successfully migrated: count and list
   - Skipped: count and list (if any)
   - Failed: count and list with error messages (if any)

2. **Display file-level details**
   - For each migrated file, show:
     - Source path
     - Target path
     - Key changes made (version numbers, cron schedules)

3. **Provide next steps**
   - Suggest running CI operator config generator if available
   - Suggest testing the new configurations
   - Suggest creating a pull request if appropriate

## Cron Schedule Generation Algorithm

To avoid thundering herd problems, generate randomized cron schedules:

```python
import random

def generate_cron_schedule(frequency='monthly'):
    """Generate randomized cron schedule"""
    minute = random.randint(0, 59)
    hour = random.randint(1, 23)  # Avoid midnight

    if frequency == 'monthly':
        day_of_month = random.randint(1, 28)  # Safe for all months
        month = '*'
        day_of_week = '*'
    elif frequency == 'weekly':
        day_of_month = '*'
        month = '*'
        day_of_week = random.randint(0, 6)
    elif frequency == 'daily':
        day_of_month = '*'
        month = '*'
        day_of_week = '*'
    else:  # custom
        day_of_month = random.randint(1, 28)
        month = random.randint(1, 12)
        day_of_week = '*'

    return f"{minute} {hour} {day_of_month} {month} {day_of_week}"
```

**Usage Notes:**
- You can implement this in Python, Bash, or inline in your code
- Preserve the general frequency of the original schedule
- If original runs monthly, new schedule should also run monthly
- Document that cron schedules were randomized in the summary

## Version String Transformation Reference

Here's a quick reference for version string transformations:

| Context | Pattern | Example Transformation |
|---------|---------|----------------------|
| Base image key | `ocp_{version_underscore}_*` | `ocp_4_17_base-rhel9` → `ocp_4_18_base-rhel9` |
| Builder tag | `openshift-{version}` | `openshift-4.17` → `openshift-4.18` |
| Registry path | `ocp/{version}:` | `ocp/4.17:base-rhel9` → `ocp/4.18:base-rhel9` |
| Release name | `name: "{version}"` | `name: "4.17"` → `name: "4.18"` |
| Branch | `branch: release-{version}` | `branch: release-4.17` → `branch: release-4.18` |
| Filename | `-release-{version}__` | `-release-4.17__periodics.yaml` → `-release-4.18__periodics.yaml` |

**Important:** Version in underscored contexts uses `_` instead of `.`
- Normal: `4.17`
- Underscored: `4_17`

## Error Handling

### Common Errors and Solutions

1. **No files found**
   - Verify version number is correct
   - Check if release uses different naming (e.g., `main` instead of `release-*`)
   - Verify path is correct relative to repository root

2. **File already exists**
   - Ask user if they want to overwrite
   - Offer to show diff between existing and new
   - Provide option to skip

3. **YAML parsing errors**
   - Report line number if possible
   - Show the problematic content
   - Ask user how to proceed

4. **Version format mismatch**
   - If file contains unexpected version formats
   - Log warning but continue
   - Report in final summary

5. **Permission errors**
   - Check file permissions
   - Report to user
   - Continue with next file

## Testing Validation

After migration, suggest these validation steps to the user:

1. **YAML syntax validation**
   ```bash
   # Validate YAML syntax
   for file in ci-operator/config/**/*-release-{to_version}__periodics.yaml; do
     yaml-lint "$file" || echo "Invalid: $file"
   done
   ```

2. **Diff against source**
   ```bash
   # Show what changed (expect version and cron changes)
   diff -u \
     ci-operator/config/openshift/etcd/openshift-etcd-release-4.17__periodics.yaml \
     ci-operator/config/openshift/etcd/openshift-etcd-release-4.18__periodics.yaml
   ```

3. **Regenerate CI configs (if applicable)**
   ```bash
   # Regenerate Prowjob configs from ci-operator configs
   make jobs
   ```

## Example Migration

**Input:**
- from-release: `4.17`
- to-release: `4.18`
- path: `ci-operator/config/openshift/cloud-credential-operator`

**Process:**
1. Find: `openshift-cloud-credential-operator-release-4.17__periodics.yaml`
2. Create: `openshift-cloud-credential-operator-release-4.18__periodics.yaml`
3. Transform:
   - `ocp_4_17_base-rhel9` → `ocp_4_18_base-rhel9`
   - `openshift-4.17` → `openshift-4.18`
   - `ocp/4.17:` → `ocp/4.18:`
   - `name: "4.17"` → `name: "4.18"`
   - `branch: release-4.17` → `branch: release-4.18`
   - `cron: 11 4 14 8 *` → `cron: 37 15 14 8 *` (randomized)
4. Write new file
5. Report success

## Additional Notes

- **Preserving comments:** YAML comments may be lost during programmatic editing. If possible, use text-based find/replace to preserve formatting and comments.

- **Batch processing:** When migrating multiple files, process them sequentially but report results in batch.

- **Golang version handling:** Some releases require golang version bumps. This is NOT automatic - only change if user confirms or if documented requirement exists.

- **Testing frequency:** Some periodic tests run very infrequently (monthly, quarterly). Ensure cron schedules reflect appropriate frequency.

- **Documentation:** After migration, suggest documenting the migration in commit message or PR description.
