---
name: release-find-main-periodic-tests
description: Find test definitions with periodic scheduling in main/master branch configuration files
---

# Find Main/Master Periodic Tests Skill

This skill identifies test definitions with periodic scheduling (`interval:` or `cron:` fields) in main/master branch configuration files. These tests may need to be moved to dedicated `__periodics.yaml` files.

## When to Use This Skill

Use this skill when you need to:
- Identify tests with periodic scheduling in main/master configs
- Find tests that should potentially be moved to dedicated periodic files
- Audit OpenShift CI configuration for proper test organization

## Prerequisites

- User should be in the `openshift/release` repository
- CI operator configuration files exist in `ci-operator/config/`

## Implementation Steps

### Step 1: Determine Search Path

**Input:** Optional path argument from user (e.g., `ci-operator/config/openshift`)

**Process:**
1. If path argument provided:
   - Use the provided path as-is
   - Path should be relative to the repository root
2. If no path argument:
   - Default to `ci-operator/config/`
3. Construct full path: `/home/fsb/github/neisw/openshift/release/{path}`
4. Verify the path exists

**Output:** `search_path` variable with full absolute path

### Step 2: Find Main/Master Configuration Files

**Process:**
1. Use Glob tool to find files matching these patterns within search_path:
   - `**/*-main.yaml`
   - `**/*-master.yaml`
2. **Filter out** any files ending with `__periodics.yaml`
   - Use pattern matching or post-filter the results
   - Dedicated periodic files should NOT be included
3. Store the list of file paths

**Output:** List of main/master configuration file paths (excluding `__periodics.yaml` files)

### Step 3: Parse Each Configuration File for Periodic Tests

Use the `find_periodic_tests.py` helper script to efficiently parse all configuration files.

**Process:**
1. Create a temporary file list:
   ```bash
   find <search_path> -name "*-main.yaml" -o -name "*-master.yaml" | grep -v "__periodics.yaml" > /tmp/main_master_files.txt
   ```

2. Run the helper script:
   ```bash
   python3 plugins/release/skills/release-find-main-periodic-tests/find_periodic_tests.py /tmp/main_master_files.txt
   ```

3. The script will output results in this format:
   - `STATS:<total_files>:<files_with_periodic>:<total_periodic_tests>`
   - `FILE:<filepath>` (relative to repository root)
   - `TEST:<test_name>:<schedule>` (for each periodic test in that file)

**How the script works:**
- Reads each YAML configuration file
- Looks for the `tests:` section
- Identifies tests with `as:` field AND (`interval:` OR `cron:` field)
- Outputs structured data for easy parsing

**A test is considered periodic if:**
- It has an `as:` field (test name)
- AND it has EITHER an `interval:` field OR a `cron:` field

**Output:** Structured text output from the helper script containing:
- Statistics (total files, files with periodic tests, total tests)
- List of files with their periodic tests and scheduling configuration

### Step 4: Parse Script Output

**Process:**
1. Parse the `STATS` line to extract:
   - Total files scanned
   - Files containing periodic tests
   - Total periodic tests found
2. Parse `FILE` and `TEST` lines to build a structured list of results
3. Organize results by file path

**Output:** Parsed data structure ready for display

### Step 5: Display Results

**Format the output as:**

```
Periodic Tests in Main/Master Configurations
============================================
Search Path: {search_path}

Results:
--------
Scanned {total_files} main/master configuration file(s)
Found {files_with_periodic_tests} file(s) containing periodic tests
Total periodic tests: {total_tests}

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

... (list all files)

Recommendations:
----------------
Review these periodic tests to determine if they should be:
1. Moved to dedicated __periodics.yaml files
2. Converted to presubmit or postsubmit tests
3. Kept in main/master configs if there's a valid reason

To create a periodic configuration file for a repository:
  - File naming: {org}-{repo}-{branch}__periodics.yaml
  - Example: openshift-origin-main__periodics.yaml

See: https://docs.ci.openshift.org/docs/how-tos/naming-your-ci-jobs/#configuration-for-periodic-jobs
```

**Important Display Notes:**
- Show file paths relative to repository root (strip `/home/fsb/github/neisw/openshift/release/` prefix)
- Number the files (1, 2, 3, ...)
- Indent test names under each file
- Show the scheduling configuration in parentheses

## Error Handling

1. **Path doesn't exist:**
   - Display error message
   - Suggest correct path format
   - Exit gracefully

2. **No main/master files found:**
   - Display message that no matching files were found
   - Verify the search path is correct

3. **YAML parsing errors:**
   - Log which file had parsing issues
   - Continue processing other files
   - Include note in final report about any skipped files

4. **No periodic tests found:**
   - Display message that no periodic tests were found
   - This is a valid result (means configs are properly organized)

## Examples

### Example 1: Search all configs
**Input:** No path argument
**Search Path:** `ci-operator/config/`
**Expected:** Scan all main/master files in entire config directory

### Example 2: Search specific organization
**Input:** `ci-operator/config/openshift`
**Search Path:** `ci-operator/config/openshift`
**Expected:** Scan only openshift organization files

### Example 3: Search specific repository
**Input:** `ci-operator/config/openshift/origin`
**Search Path:** `ci-operator/config/openshift/origin`
**Expected:** Scan only origin repository files

## Notes

- **Performance:** This command is read-only and doesn't modify any files
- **Scope:** Always excludes `__periodics.yaml` files (dedicated periodic files)
- **Detection:** A test MUST have both `as:` and (`interval:` OR `cron:`) to be considered periodic
- **Not all findings require action:** Some tests may legitimately use periodic scheduling in main/master configs

## Tools to Use

1. **Bash tool:**
   - Find all `*-main.yaml` and `*-master.yaml` files using `find` command
   - Filter out `__periodics.yaml` files using `grep -v`
   - Run the `find_periodic_tests.py` helper script

2. **Helper Script:**
   - `plugins/release/skills/release-find-main-periodic-tests/find_periodic_tests.py`
   - Handles all YAML parsing and test identification
   - Outputs structured data for easy display formatting
