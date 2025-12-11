---
description: List all workflows/jobs configured to execute a specific test
argument-hint: <version> <test-keywords> [release-repo-path]
---

## Name
ci:list-workflows-for-test

## Synopsis
```
/ci:list-workflows-for-test <version> <test-keywords> [release-repo-path]
```

## Description
The `ci:list-workflows-for-test` command searches the OpenShift CI configuration repository (openshift/release) to find all workflows and jobs that are configured to execute tests matching specific keywords. Unlike Sippy-based queries that only show jobs with recent test executions, this command shows ALL jobs configured to run the test, regardless of whether they've run recently or had failures.

This command is useful for:
- Finding comprehensive test coverage across all configured CI jobs
- Understanding which platforms and job types are configured to run a specific test
- Identifying test coverage gaps before they become issues
- Planning test execution strategy across different configurations
- Debugging why a test might behave differently in different jobs
- Verifying that a test runs on expected platforms (AWS, GCP, Azure, Metal, etc.)

## Arguments
- `$1` (version): OpenShift version (e.g., "4.21", "4.20", "4.19")
- `$2` (test-keywords): Keywords to search in test names or test-related configuration (e.g., "SCTP", "sig-network", "PolarionID:81664")
- `$3` (release-repo-path) [optional]: Path to local openshift/release repository. If not provided, the command will clone it to a temporary location.

## Implementation

### Step 1: Setup openshift/release Repository

1. **Check for existing repository**:
   - If `$3` (release-repo-path) is provided, validate it:
     ```bash
     cd <release-repo-path>
     git remote -v | grep "openshift/release" || exit 1
     ```
   - If path is invalid, show error and exit

2. **Clone repository if needed**:
   - If no path provided, clone to temporary location:
     ```bash
     TEMP_DIR=$(mktemp -d)
     cd $TEMP_DIR
     git clone --depth 1 https://github.com/openshift/release.git
     REPO_PATH="$TEMP_DIR/release"
     ```
   - Show progress: "Cloning openshift/release repository (this may take a minute)..."

3. **Set repository path**:
   - Store the repository path for use in subsequent steps
   - Repository structure:
     - `ci-operator/config/` - Job configuration files
     - `ci-operator/step-registry/` - Workflow and step definitions

### Step 2: Search for Workflows Mentioning the Test

1. **Search workflow files for test mentions**:
   ```bash
   find ${REPO_PATH}/ci-operator/step-registry -type f -name "*-workflow.yaml" \
     | xargs grep -l "${test_keywords}"
   ```

2. **Parse workflow files**:
   - For each workflow file found:
     - Load YAML and extract workflow name (`workflow.as` field)
     - Check if test appears in `TEST_SKIPS` environment variable
     - Check if test appears in other test-related env vars (`TEST_SUITE`, `TEST_FILTER`, etc.)
     - Record workflow information:
       ```python
       workflows_with_test[workflow_name] = {
           "skips": True/False,  # Whether this workflow skips the test
           "file": path_to_workflow_file
       }
       ```

3. **Identify e2e test workflows**:
   - Find all workflows that run general e2e tests:
     ```bash
     find ${REPO_PATH}/ci-operator/step-registry -type f -name "*-workflow.yaml" \
       | xargs grep -l "openshift-e2e-test"
     ```
   - Parse these workflows to determine if they would run the test:
     - Workflows that reference `openshift-e2e-test` step run comprehensive test suites
     - Exclude workflows that explicitly skip the test keyword in `TEST_SKIPS`
     - Include workflows that don't mention the test at all (they run default suite)

### Step 3: Search for Jobs Using These Workflows

1. **Find job configuration files for the version**:
   ```bash
   find ${REPO_PATH}/ci-operator/config -type f -name "*${version}*.yaml"
   ```

2. **Parse job configurations**:
   - For each config file:
     - Load YAML and extract `tests` array
     - For each test job:
       - Get job name (`as` field)
       - Get workflow reference (`steps.workflow` field)
       - Get job-specific env overrides (`steps.env`)
       - Get config file path for reference

3. **Match jobs to workflows**:
   - Create mapping: `jobs_by_workflow[workflow_name] = [list of jobs]`
   - Store job metadata:
     ```python
     {
         "name": job_name,
         "workflow": workflow_name,
         "config_file": path_to_config_file,
         "skips_test": True/False  # Check job-level TEST_SKIPS
     }
     ```

### Step 4: Determine Which Jobs Run the Test

1. **Job runs the test if**:
   - Job uses a workflow that was found in Step 2, AND
   - Job doesn't explicitly skip the test in job-level `TEST_SKIPS`

2. **Special cases**:
   - **Workflow skips test but job overrides**: If workflow has `TEST_SKIPS` but job overrides it, check the job's env
   - **Workflow mentions test**: If workflow mentions test in skips, it normally runs the test (just being skipped for that specific workflow variant)
   - **General e2e workflows**: Workflows using `openshift-e2e-test` without test-specific filters run comprehensive suites

3. **Deduplicate and collect**:
   - Remove duplicate job names
   - For each unique job, collect:
     - Job name
     - Workflow used
     - Config file path
     - Platform (extracted from job name)
     - Note explaining why it runs the test

### Step 5: Categorize and Organize Results

1. **Extract platform from job name**:
   ```python
   def detect_platform(job_name):
       platforms = []
       job_lower = job_name.lower()
       if "aws" in job_lower: platforms.append("AWS")
       if "gcp" in job_lower: platforms.append("GCP")
       if "azure" in job_lower: platforms.append("Azure")
       if "metal" in job_lower: platforms.append("Metal")
       if "vsphere" in job_lower: platforms.append("vSphere")
       if "openstack" in job_lower: platforms.append("OpenStack")
       if "alibaba" in job_lower: platforms.append("Alibaba Cloud")
       if "ibmcloud" in job_lower: platforms.append("IBM Cloud")
       return ", ".join(platforms) if platforms else "Platform-agnostic"
   ```

2. **Categorize by job type**:
   - Based on config file naming patterns:
     - Files containing `__amd64-nightly`, `__arm64-nightly`, `__ppc64le-nightly` → **Nightly Jobs**
     - Files containing `__periodics` → **Periodic Jobs**
     - Files containing `__upgrade-from-stable` → **Upgrade Jobs**
     - Files in `ci-operator/config/openshift/release/` → **Release Jobs**
     - Others → **Component Jobs** (tied to specific repositories)

3. **Categorize by platform**:
   - Group jobs by detected platform
   - Within each platform, list job names alphabetically

### Step 6: Format and Display Results

1. **Summary Section**:
   ```
   ====================================================================================================
   Workflows and Jobs Configured to Execute Tests Matching: <test_keywords>
   ====================================================================================================
   OpenShift Version: <version>
   Repository: <repo_path>

   Summary:
     Total Unique Jobs: <count>
     Platforms Covered: AWS, GCP, Azure, Metal, vSphere, etc.
     Job Types: Nightly, Periodic, Upgrade, Release, Component
   ```

2. **Results by Platform**:
   ```
   ====================================================================================================
   AWS Jobs (<count>):
   ====================================================================================================

   1. e2e-aws-ovn
      Workflow: openshift-e2e-aws
      Config: ci-operator/config/openshift/origin/openshift-origin-release-4.20.yaml
      Type: Component test

   2. e2e-aws-ovn-serial
      Workflow: openshift-e2e-aws-serial
      Config: ci-operator/config/openshift/cluster-capi-operator/...
      Type: Component test

   [... more AWS jobs ...]

   ====================================================================================================
   GCP Jobs (<count>):
   ====================================================================================================

   [... GCP jobs ...]
   ```

3. **Platform Coverage Summary**:
   ```
   ====================================================================================================
   Platform Coverage Summary:
   ====================================================================================================
   ✓ AWS: <count> jobs
   ✓ GCP: <count> jobs
   ✓ Azure: <count> jobs
   ✓ Metal: <count> jobs
   ✓ vSphere: <count> jobs
   ✗ OpenStack: No jobs found
   ✗ IBM Cloud: No jobs found
   ```

4. **Workflow Summary** (optional, if helpful):
   - List unique workflows that run the test
   - Show how many jobs use each workflow

### Step 7: Cleanup (if temporary clone)

1. **Remove temporary directory** (if created):
   ```bash
   if [ -n "$TEMP_DIR" ]; then
       rm -rf "$TEMP_DIR"
   fi
   ```

### Step 8: Handle Edge Cases

1. **No tests found**:
   - Message: "No workflows or jobs found that execute tests matching '<test_keywords>' in version <version>"
   - Suggest: "Try broader search terms or check spelling"

2. **Repository clone fails**:
   - Message: "Failed to clone openshift/release repository"
   - Suggest: "Check internet connection or provide local repository path as third argument"

3. **Invalid repository path**:
   - Message: "Invalid openshift/release repository path: <path>"
   - Suggest: "Ensure the path points to a valid clone of github.com/openshift/release"

4. **No config files for version**:
   - Message: "No CI configuration files found for version <version>"
   - Suggest: "Check version format (should be like '4.20', '4.21') or try a different version"

## Return Value

**Format**: Formatted text output with:

**Summary Section:**
- Test keywords searched
- OpenShift version
- Repository location
- Total jobs found
- Platforms covered
- Job types present

**Jobs Grouped by Platform:**
Each platform section contains:
- Platform name and job count
- List of jobs with:
  - Job name
  - Workflow used
  - Config file path (relative to repo root)
  - Job type (nightly, periodic, upgrade, etc.)

**Platform Coverage Summary:**
- Checkmarks for platforms with jobs
- Warning for platforms without coverage

**Output Format Example:**
```
====================================================================================================
Workflows and Jobs Configured to Execute Tests Matching: SCTP
====================================================================================================
OpenShift Version: 4.20
Repository: /tmp/openshift-release-sample
Scanning CI configurations...

Summary:
  Total Unique Jobs: 376
  Platforms Covered: AWS (156), GCP (72), Azure (64), Metal (18), vSphere (24), Platform-agnostic (42)
  Job Types: Nightly, Periodic, Upgrade, Component tests

====================================================================================================
AWS Jobs (156):
====================================================================================================

1. e2e-aws-ovn
   Workflow: openshift-e2e-aws
   Config: ci-operator/config/openshift/origin/openshift-origin-release-4.20.yaml
   Type: Component test

2. e2e-aws-ovn-serial
   Workflow: openshift-e2e-aws-serial
   Config: ci-operator/config/openshift/cluster-capi-operator/...
   Type: Component test

3. e2e-aws-ovn-upgrade
   Workflow: openshift-upgrade-aws
   Config: ci-operator/config/openshift/aws-ebs-csi-driver/...
   Type: Upgrade test

[... 153 more AWS jobs ...]

====================================================================================================
GCP Jobs (72):
====================================================================================================

[... GCP jobs ...]

====================================================================================================
Platform Coverage Summary:
====================================================================================================
✓ AWS: 156 jobs
✓ GCP: 72 jobs
✓ Azure: 64 jobs
✓ Metal: 18 jobs
✓ vSphere: 24 jobs
✓ Platform-agnostic: 42 jobs
✗ OpenStack: No jobs found
✗ IBM Cloud: No jobs found

====================================================================================================
```

## Examples

1. **Find all jobs configured to run SCTP tests**:
   ```
   /ci:list-workflows-for-test 4.20 SCTP
   ```

   Searches the openshift/release repository for all jobs in version 4.20 that are configured to execute SCTP-related tests. Shows comprehensive coverage across all platforms.

2. **Find jobs for a specific test by Polarion ID**:
   ```
   /ci:list-workflows-for-test 4.21 "PolarionID:81664"
   ```

   Returns all jobs configured to run the test with Polarion ID 81664 in version 4.21.

3. **Use existing local repository**:
   ```
   /ci:list-workflows-for-test 4.20 "sig-storage CSI" ~/repos/openshift-release
   ```

   Uses the local clone at ~/repos/openshift-release instead of cloning a new copy.

4. **Find network test coverage**:
   ```
   /ci:list-workflows-for-test 4.19 "sig-network"
   ```

   Shows all jobs configured to run sig-network tests in version 4.19, organized by platform.

5. **Check upgrade test coverage**:
   ```
   /ci:list-workflows-for-test 4.20 "upgrade"
   ```

   Lists all upgrade-related jobs in version 4.20.

## Notes

- **Comprehensive Coverage**: Unlike Sippy queries, this shows ALL configured jobs, not just those with recent executions or failures
- **Repository Clone**: First run will clone ~500MB repository (takes 1-2 minutes). Subsequent runs can reuse local clone by providing path
- **Local Repository**: For faster execution, clone openshift/release once and provide path:
  ```bash
  git clone https://github.com/openshift/release.git ~/repos/openshift-release
  /ci:list-workflows-for-test 4.20 SCTP ~/repos/openshift-release
  ```
- **Version Format**: Version should match the pattern used in config file names (e.g., "4.20", "4.21", not "v4.20" or "4.20.0")
- **Test Keywords**: Can be partial matches - searching "SCTP" will find all SCTP-related tests
- **Workflow vs Job**:
  - Workflows are reusable test execution templates
  - Jobs are specific instances that use workflows
  - One workflow may be used by many jobs
- **Platform Detection**: Extracted from job names, may not be 100% accurate for jobs with non-standard naming
- **Performance**:
  - First run (with clone): ~2-3 minutes
  - Subsequent runs (with local repo): ~10-30 seconds depending on search complexity
- **Advantages over Sippy**:
  - Shows jobs that haven't run recently
  - Shows jobs where test always passes (invisible in Sippy failure queries)
  - Based on configuration, not historical execution
  - Shows what SHOULD run, not just what HAS run

## See Also

- `/ci:query-test-result` - Query historical test results from Sippy (complementary to this command)
- `/ci:list-unstable-tests` - List tests with low pass rates
- `/ci:add-debug-wait` - Add debug wait step to a workflow
- OpenShift CI Documentation: https://docs.ci.openshift.org/
- openshift/release Repository: https://github.com/openshift/release
