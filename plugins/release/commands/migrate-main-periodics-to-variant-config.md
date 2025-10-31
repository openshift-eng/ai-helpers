---
description: Move periodic test definitions from main/master branch configs to dedicated __periodics.yaml files
argument-hint: <target-release> [path|--filter=<json>] [--confirm-each-test]
---

## Name
release:migrate-main-periodics-to-variant-config

## Synopsis
Extract test definitions with periodic scheduling from main/master branch configuration files and move them to dedicated periodic configuration files:
```
/release:migrate-main-periodics-to-variant-config <target-release> [path|--filter=<json>] [--confirm-each-test]
```

## Description
The `release:migrate-main-periodics-to-variant-config` command identifies test definitions with periodic scheduling (`interval:` or `cron:` fields) in main/master branch configuration files and moves them to dedicated `__periodics.yaml` files for a specific release version.

In OpenShift CI, periodic tests should be defined in separate `__periodics.yaml` files rather than in the main/master branch configuration files. This command automates the process of:
1. Finding tests with periodic scheduling in main/master configs (or using a JSON filter)
2. Extracting those test definitions
3. Creating or updating the appropriate release-specific `__periodics.yaml` file
4. Removing the tests from the source main/master file

This helps maintain proper separation between presubmit tests (run on PRs) and periodic tests (run on schedules).

## Arguments

- `$1` (**target-release**): Target release version for the periodic configuration
  - Format: `{major}.{minor}` (e.g., `4.21`)
  - Alternative formats accepted: `release-4.21`, `4.21.0`
  - Examples: `4.18`, `4.19`, `4.20`, `4.21`
  - This will be used in the periodic file naming: `{org}-{repo}-release-{version}__periodics.yaml`

- `$2` (**path** or **--filter=<json>**): Optional directory path or JSON filter file
  - **Path mode** (default): `ci-operator/config/` (searches all subdirectories)
    - Can specify a subdirectory to limit scope
    - Examples: `ci-operator/config/openshift`, `ci-operator/config/openshift/origin`
    - Must be relative to the openshift/release repository root
  - **Filter mode**: `--filter=<json_file>`
    - Provide a JSON file (like output from `/release:find-main-periodic-tests --format=json`)
    - Only tests specified in the JSON file will be processed
    - Example: `--filter=periodic_tests_report.json`
  - Can also be `--confirm-each-test` if using default path

- `$3` (**--confirm-each-test**): Optional flag to confirm each test individually
  - If specified, the command will prompt for each test asking if it should be moved
  - When a test is confirmed for moving, it will be automatically removed from the source file (no additional prompt)
  - When a test is declined, it will be skipped and remain in the source file
  - Can appear as either the 2nd or 3rd argument for flexibility
  - Examples:
    - `/release:migrate-main-periodics-to-variant-config 4.21 --confirm-each-test` (confirm each, use default path)
    - `/release:migrate-main-periodics-to-variant-config 4.21 --filter=report.json --confirm-each-test` (confirm each with JSON filter)
    - `/release:migrate-main-periodics-to-variant-config 4.21 ci-operator/config/openshift --confirm-each-test` (confirm each with custom path)
  - If NOT specified (batch mode):
    - All matching periodic tests will be summarized and displayed
    - A single confirmation prompt asks: "Proceed with moving all tests?"
    - If user confirms, all tests are moved and automatically removed from source files (no further prompts)
    - If user declines, no changes are made

## Implementation

Perform the following steps to move periodic tests to dedicated files:

1. **Verify git branch and get user confirmation**
   - Check current git branch using `git rev-parse --abbrev-ref HEAD`
   - Display branch name to user
   - Warn if on main/master branch
   - Ask user to confirm they want to proceed with modifications on this branch
   - Exit immediately if user declines

2. **Parse and normalize arguments**
   - Parse all arguments to extract: target-release, path/filter, and --confirm-each-test flag
   - The --confirm-each-test flag can appear in position 2 or 3
   - Check if argument 2 starts with `--filter=`:
     - If yes, extract JSON file path and set filter mode
     - If no, treat as path (or --confirm-each-test flag)
   - Normalize target-release to `{major}.{minor}` format (e.g., `4.21`)
   - Validate version format
   - Determine search mode:
     - **Filter mode**: If `--filter=<json>` provided, use JSON filter
     - **Path mode**: Use provided path or default to `ci-operator/config/`
   - Verify path/file exists in repository
   - Store whether --confirm-each-test flag is set

3. **Find main/master configuration files with periodic tests**

   **If using filter mode (--filter=<json>):**
   - Create file list using find command:
     ```bash
     find /home/fsb/github/neisw/openshift/release/ci-operator/config -name "*-main.yaml" -o -name "*-master.yaml" | grep -v "__periodics.yaml" > /tmp/main_master_files.txt
     ```
   - Run find_periodic_tests.py with filter:
     ```bash
     python3 plugins/release/skills/release-find-main-periodic-tests/find_periodic_tests.py /tmp/main_master_files.txt --filter=<json_file>
     ```
   - Parse the output to get filtered list of files and tests

   **If using path mode (default):**
   - Create file list using find command for the specified path
   - Run find_periodic_tests.py without filter:
     ```bash
     python3 plugins/release/skills/release-find-main-periodic-tests/find_periodic_tests.py /tmp/main_master_files.txt
     ```
   - Parse the output to get all periodic tests in the path

   - For each file with periodic tests found, add to processing list

4. **Display findings and get confirmation based on mode**

   **If --confirm-each-test flag is NOT set (batch mode):**
   - Display comprehensive summary of all tests to be moved:
     - Show which files contain periodic tests
     - For each file, list:
       - File path
       - Test names that will be moved
       - Their scheduling configuration (interval/cron values)
     - Calculate and display statistics:
       - Total files with periodic tests
       - Total tests to be moved
   - Ask single confirmation: "Proceed with moving all these tests?"
   - If user confirms:
     - Proceed to process all tests
     - All moved tests will be automatically removed from source files (no additional prompts)
   - If user declines:
     - Exit immediately with no changes made

   **If --confirm-each-test flag IS set (interactive mode):**
   - Show user that individual test confirmation mode is active
   - Display total files and tests found
   - Explain that each test will be confirmed individually
   - Explain that confirmed tests will be automatically removed from source files

5. **Process each file with periodic tests**

   For each main/master configuration file:

   **a. Extract periodic tests (behavior depends on --confirm-each-test flag)**

   **If --confirm-each-test flag IS set:**
   - Parse the source YAML file
   - For each test definition that has `interval:` or `cron:` fields:
     - Display test details:
       - Test name (`as:` field)
       - Scheduling configuration (`interval:` or `cron:` value)
       - Source file path
     - Ask user: "Move this test to the periodic file?" (Yes/No)
     - If user says Yes:
       - Add test to list of tests to move
       - Mark test for automatic removal from source file
     - If user says No:
       - Skip this test (leave it in source file)
       - Continue to next test
   - After all tests in file are processed, proceed with only the confirmed tests

   **If --confirm-each-test flag is NOT set (batch mode):**
   - Parse the source YAML file
   - Extract all test definitions that have `interval:` or `cron:` fields
   - All tests will be moved (already confirmed in step 4)
   - Mark all tests for automatic removal from source file

   **b. Determine target periodic file path**
   - Extract org and repo from source file path
   - Parse branch from source file name (`-main` or `-master`)
   - Construct target periodic file name:
     - Pattern: `{org}-{repo}-release-{target-release}__periodics.yaml`
     - Example: `openshift-origin-release-4.21__periodics.yaml`
   - Full path: same directory as source file

   **c. Transform test definitions for target release**
   - Update version references in each test:
     - Base images: adjust version tags if needed
     - Release references: `name: "4.17"` → `name: "4.21"`
     - Registry paths: `ocp/4.17:` → `ocp/4.21:`
     - Cluster versions: update to target release
   - Regenerate randomized cron schedules (if `cron:` field exists)
     - Maintain same frequency (daily, weekly, etc.)
     - Use different random times to avoid thundering herd
     - Preserve `@weekly`, `@daily`, etc. special syntax
   - Preserve `interval:` fields as-is (unless user requests changes)

   **d. Create or update target periodic file**
   - Check if target periodic file already exists
   - If file exists:
     - Read existing content
     - Parse existing YAML
     - Merge new tests with existing tests
     - Avoid duplicate test names (warn user if duplicates found)
     - Ask user how to handle duplicates:
       - Skip the duplicate test
       - Replace existing test with new definition
       - Rename the new test
   - If file doesn't exist:
     - Create new YAML structure based on source file metadata
     - Copy relevant fields from source (build_root, base_images, releases, etc.)
     - Add the periodic tests to `tests:` section
     - Include proper zz_generated_metadata section
   - Write the file using Write tool

   **e. Remove periodic tests from source file (automatic in both modes)**

   **If --confirm-each-test flag IS set (interactive mode):**
   - Tests confirmed for moving are automatically removed from the source file (no prompt)
   - For each confirmed test:
     - Parse source YAML
     - Remove the specific test definition from `tests:` array
     - Preserve all other tests and configuration
   - Write updated source file
   - Tests that were declined remain in the source file unchanged

   **If --confirm-each-test flag is NOT set (batch mode):**
   - All moved tests are automatically removed from the source file (no prompt)
   - User already confirmed proceeding in step 4, which includes automatic cleanup
   - Parse source YAML
   - Remove all extracted test definitions from `tests:` array
   - Preserve all other tests and configuration
   - Write updated source file

6. **Validate transformed files**
   - For each created/modified file:
     - Verify YAML is valid
     - Check that all expected tests are present
     - Verify version transformations are correct

7. **Build and display report**
   - Summary statistics:
     - Files processed
     - Tests moved
     - New periodic files created
     - Existing periodic files updated
     - Source files modified (if user chose to remove tests)
   - Detailed file-level information:
     - List each target periodic file created/updated
     - List tests moved to each file
     - Note any warnings or issues encountered

8. **Provide next steps and recommendations**
   - Suggest running `make jobs` to regenerate Prowjob configurations
   - Recommend testing the new periodic configurations
   - Suggest creating a PR with the changes
   - Provide link to OpenShift CI documentation

## Return Value

- **Format**: Text report with migration details and statistics

The command outputs:
- List of source files containing periodic tests
- Confirmation prompts for user decisions
- Progress updates during processing
- Summary of files created/updated
- List of tests moved to each periodic file
- Warnings for any conflicts or issues
- Next steps for validation and PR creation

## Examples

1. **Workflow: Find, filter, and move periodic tests**:
   ```
   # Step 1: Find all periodic tests and save to JSON
   /release:find-main-periodic-tests ci-operator/config/openshift
   # (Then manually run): python3 ... --format=json > periodic_tests_report.json

   # Step 2: Review and edit the JSON file to keep only tests you want to move
   # (Edit periodic_tests_report.json to remove repositories/tests you don't want to move)

   # Step 3: Move the filtered tests to dedicated files
   /release:migrate-main-periodics-to-variant-config 4.21 --filter=periodic_tests_report.json
   ```

2. **Move specific tests using a filtered JSON file**:
   ```
   /release:migrate-main-periodics-to-variant-config 4.21 --filter=selected_tests.json
   ```
   Uses only the repositories and tests specified in the JSON file.

3. **Move all periodic tests to 4.21 release files (batch mode)**:
   ```
   /release:migrate-main-periodics-to-variant-config 4.21
   ```
   Searches all of `ci-operator/config/` for main/master files with periodic tests and creates/updates corresponding `*-release-4.21__periodics.yaml` files. All matching tests are moved, with a single prompt asking if they should be removed from source files.

2. **Move periodic tests for specific organization**:
   ```
   /release:migrate-main-periodics-to-variant-config 4.21 ci-operator/config/openshift
   ```
   Processes only files under the openshift organization.

3. **Move periodic tests for specific repository**:
   ```
   /release:migrate-main-periodics-to-variant-config 4.20 ci-operator/config/openshift/cluster-etcd-operator
   ```
   Processes only the cluster-etcd-operator repository configuration.

4. **Move periodic tests for private repositories**:
   ```
   /release:migrate-main-periodics-to-variant-config 4.19 ci-operator/config/openshift-priv
   ```
   Processes configurations in the openshift-priv organization.

5. **Confirm each test individually (interactive mode)**:
   ```
   /release:migrate-main-periodics-to-variant-config 4.21 --confirm-each-test
   ```
   Prompts for each periodic test found, asking if it should be moved. Tests confirmed for moving are automatically removed from the source file.

6. **Confirm each test with custom path**:
   ```
   /release:migrate-main-periodics-to-variant-config 4.21 ci-operator/config/openshift --confirm-each-test
   ```
   Processes only the openshift organization, with individual test confirmation.

## Prerequisites

- User should be working in the `openshift/release` repository
- User should have write permissions to create/modify files
- Main/master branch configuration files should exist
- User should be on a feature branch (command will warn if on main/master)

## Notes

- **File naming pattern**: Target periodic files follow the pattern:
  - `{org}-{repo}-release-{version}__periodics.yaml`
  - Example: `openshift-origin-release-4.21__periodics.yaml`

- **Periodic test detection**: A test is considered periodic if it has:
  - An `as:` field (test identifier/name)
  - AND either an `interval:` field OR a `cron:` field

- **Version transformation**: The command updates version references to match the target release:
  - Base image tags
  - Release names and versions
  - Registry paths
  - Cluster version references

- **Cron schedule regeneration**: Cron schedules are randomized to avoid thundering herd:
  - Maintains same frequency (daily, weekly, monthly)
  - Uses different random times
  - Distributes load across the day/week

- **Merging with existing files**: If a periodic file already exists:
  - New tests are merged with existing tests
  - Duplicate test names trigger user confirmation
  - Metadata sections are preserved from existing file

- **Source file modification behavior**:
  - **Both modes automatically remove tests from source files**
  - **With --confirm-each-test flag (interactive)**: Tests confirmed for moving are automatically removed from source files
  - **Without --confirm-each-test flag (batch)**: All moved tests are automatically removed from source files after single confirmation
  - No additional prompts for source file cleanup in either mode
  - This prevents duplication and ensures tests don't run as both presubmit and periodic jobs

- **Confirmation modes**:
  - **Batch mode (default)**: Display summary of all tests, single confirmation prompt, then move and auto-cleanup all tests
  - **Interactive mode (--confirm-each-test)**: Confirm each test individually, with automatic source file cleanup for confirmed tests

- **Not all findings require action**: Some tests may legitimately use `interval:` or `cron:` in main branch configs for specific CI behaviors. Use `--confirm-each-test` to review each case individually.

- **Validation**: After migration, run:
  - `make jobs` to regenerate Prowjob configurations
  - Validate YAML syntax
  - Test the periodic configurations in a PR

## Output Format Example

### Batch Mode (Default)

```
Periodic Tests Migration to Dedicated Files
============================================
Target Release: 4.21
Search Path: ci-operator/config/openshift
Mode: Batch (all tests)

Step 1: Finding main/master files with periodic tests...
--------------------------------------------------------
Found 8 file(s) containing periodic tests:

1. ci-operator/config/openshift/origin/openshift-origin-main.yaml
   Tests to move:
   - e2e-aws-upgrade (interval: 24h)
   - e2e-gcp-upgrade (interval: 24h)
   - images (interval: 2h)

2. ci-operator/config/openshift/kubernetes/openshift-kubernetes-master.yaml
   Tests to move:
   - periodic-conformance (cron: 0 */6 * * *)
   - periodic-unit (interval: 12h)

... (additional files)

Total: 8 files, 24 tests to migrate

Step 2: Confirmation
--------------------
All tests listed above will be:
1. Moved to their corresponding release-4.21__periodics.yaml files
2. Automatically removed from source files

Proceed with moving all these tests? (y/n): y

Step 3: Processing files...
----------------------------
Processing: openshift-origin-main.yaml
  Target: openshift-origin-release-4.21__periodics.yaml (new file)
  Moving 3 tests...
  Transforming tests...
  Regenerating cron schedules...
  ✓ Created openshift-origin-release-4.21__periodics.yaml
  ✓ Removed 3 tests from openshift-origin-main.yaml (auto-cleanup)

Processing: openshift-kubernetes-master.yaml
  Target: openshift-kubernetes-release-4.21__periodics.yaml (exists)
  Moving 2 tests...
  Merging with existing 5 tests...
  ✓ Updated openshift-kubernetes-release-4.21__periodics.yaml (now 7 tests)
  ✓ Removed 2 tests from openshift-kubernetes-master.yaml (auto-cleanup)

... (additional files)

Step 4: Migration Summary
--------------------------
✓ Successfully processed 8 files
✓ Moved 24 periodic tests
✓ Created 5 new periodic files
✓ Updated 3 existing periodic files
✓ Modified 8 source files (removed periodic tests)

Files created/updated:
1. ci-operator/config/openshift/origin/openshift-origin-release-4.21__periodics.yaml (3 tests)
2. ci-operator/config/openshift/kubernetes/openshift-kubernetes-release-4.21__periodics.yaml (7 tests)
... (additional files)

Next Steps:
-----------
1. Review the changes:
   git status
   git diff

2. Regenerate Prowjob configurations:
   make jobs

3. Validate YAML syntax and test the configurations

4. Create a pull request with your changes

5. Monitor the periodic jobs after merge

See: https://docs.ci.openshift.org/docs/how-tos/naming-your-ci-jobs/#configuration-for-periodic-jobs
```

### Interactive Mode (--confirm-each-test)

```
Periodic Tests Migration to Dedicated Files
============================================
Target Release: 4.21
Search Path: ci-operator/config/openshift
Mode: Interactive (confirm each test)

Step 1: Finding main/master files with periodic tests...
--------------------------------------------------------
Found 8 file(s) containing 24 periodic tests

Tests will be confirmed individually.
Confirmed tests will be automatically removed from source files.

Step 2: Confirming tests...
----------------------------
File: ci-operator/config/openshift/origin/openshift-origin-main.yaml

Test: e2e-aws-upgrade
  Scheduling: interval: 24h
  Move this test to periodic file? (y/n): y
  ✓ Will move e2e-aws-upgrade

Test: e2e-gcp-upgrade
  Scheduling: interval: 24h
  Move this test to periodic file? (y/n): y
  ✓ Will move e2e-gcp-upgrade

Test: images
  Scheduling: interval: 2h
  Move this test to periodic file? (y/n): n
  ⊘ Skipping images (will remain in source file)

File: ci-operator/config/openshift/kubernetes/openshift-kubernetes-master.yaml

Test: periodic-conformance
  Scheduling: cron: 0 */6 * * *
  Move this test to periodic file? (y/n): y
  ✓ Will move periodic-conformance

... (additional tests)

Step 3: Processing confirmed tests...
--------------------------------------
Processing: openshift-origin-main.yaml
  Target: openshift-origin-release-4.21__periodics.yaml (new file)
  Moving 2 tests: e2e-aws-upgrade, e2e-gcp-upgrade
  Transforming tests...
  Regenerating cron schedules...
  ✓ Created openshift-origin-release-4.21__periodics.yaml
  ✓ Removed 2 tests from openshift-origin-main.yaml (auto-cleanup)

Processing: openshift-kubernetes-master.yaml
  Target: openshift-kubernetes-release-4.21__periodics.yaml (exists)
  Moving 1 test: periodic-conformance
  Merging with existing 5 tests...
  ✓ Updated openshift-kubernetes-release-4.21__periodics.yaml (now 6 tests)
  ✓ Removed 1 test from openshift-kubernetes-master.yaml (auto-cleanup)

... (additional files)

Step 4: Migration Summary
--------------------------
✓ Successfully processed 8 files
✓ Moved 18 periodic tests (6 tests skipped)
✓ Created 4 new periodic files
✓ Updated 2 existing periodic files
✓ Modified 6 source files (removed confirmed tests)

Tests moved:
- 18 tests moved to periodic files
- 6 tests kept in source files (user declined)

Files created/updated:
1. ci-operator/config/openshift/origin/openshift-origin-release-4.21__periodics.yaml (2 tests)
2. ci-operator/config/openshift/kubernetes/openshift-kubernetes-release-4.21__periodics.yaml (6 tests)
... (additional files)

Next Steps:
-----------
1. Review the changes:
   git status
   git diff

2. Regenerate Prowjob configurations:
   make jobs

3. Validate YAML syntax and test the configurations

4. Create a pull request with your changes

5. Monitor the periodic jobs after merge

See: https://docs.ci.openshift.org/docs/how-tos/naming-your-ci-jobs/#configuration-for-periodic-jobs
```

## See Also

- `/release:find-main-periodic-tests` - Find test definitions with periodic scheduling in main/master configs
- `/release:migrate-periodics` - Migrate periodic configurations from one release to another
- `/release:find-missing-periodics` - Find missing periodic configurations between releases
- OpenShift CI Documentation: https://docs.ci.openshift.org/docs/how-tos/naming-your-ci-jobs/#configuration-for-periodic-jobs
- Periodic jobs overview in the OpenShift CI system
