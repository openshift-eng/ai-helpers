---
description: Add a wait step to a CI workflow for debugging test failures
argument-hint: <workflow-or-job-name> [timeout]
---

## Name
ci:add-debug-wait

## Synopsis
```
/ci:add-debug-wait <workflow-or-job-name> [timeout]
```

## Description

The `ci:add-debug-wait` command adds a `wait` step to a CI job/workflow for debugging test failures.

**What it does:**
1. Takes job name, OCP version, and optional timeout as input
2. Finds and edits the job config or workflow file
3. Adds `- ref: wait` before the last test step (with optional timeout configuration)
4. Commits and pushes the change
5. Gives you a GitHub link to create the PR

**That's it!** Simple, fast, and automated.

## Implementation

The command performs the following steps:

### Step 1: Gather Required Information

**Prompt user for** (in this order):

1. **Workflow/Job Name**: (from command argument $1 or prompt)
   ```
   Workflow or job name: <user-input>
   Example: aws-c2s-ipi-disc-priv-fips-f7
   Example: baremetalds-two-node-arbiter-e2e-openshift-test-private-tests
   ```

2. **Timeout** (optional, from command argument $2):
   ```
   Wait timeout in hours (optional, default: 3h):
   Examples: "1h", "2h", "8h", "24h", "72h"
   Valid range: 1h to 72h
   ```
   - If not provided, uses the wait step's default behavior (3 hours)
   - Format: Integer followed by 'h' (e.g., "1h", "2h", "8h")
   - Valid range: 1h to 72h (maximum enforced by wait step's timeout setting)
   - Will be normalized to Go duration format (e.g., "8h" → "8h0m0s")
   - This will be set as the `timeout:` property on the wait step in the workflow/job YAML

3. **OCP Version**: (prompt - REQUIRED for searching job configs)
   ```
   OCP version for debugging (e.g., 4.18, 4.19, 4.20, 4.21, 4.22):
   ```
   This is used to:
   - Search the correct job config file (e.g., release-4.21)
   - Document which version needs debugging
   - Add context to the PR

4. **OpenShift Release Repo Path**: (prompt if not in current directory)
   ```
   Path to openshift/release repository:
   Default: ~/repos/openshift-release
   ```

### Step 2: Validate Environment

**Silently validate** (no user prompts):

```bash
cd <repo-path>

# Check 1: Repository exists and is correct
git remote -v | grep "openshift/release" || exit 1

# Skip repo update - work with current state
# User can manually update their repo if needed
```

### Step 3: Search for Job/Test Configuration

**Priority 1: Search job configs first** (more specific and targeted):

```bash
cd <repo-path>

# Search for job config files matching the OCP version
# The job name could be in various config files, so search broadly
grep -r "as: ${job_name}" ci-operator/config/ --include="*release-${ocp_version}*.yaml" -l
```

**Example searches**:
- For `aws-c2s-ipi-disc-priv-fips-f7` and OCP 4.21:
  ```bash
  grep -r "as: aws-c2s-ipi-disc-priv-fips-f7" ci-operator/config/ --include="*release-4.21*.yaml" -l
  ```

**Handle job config search results**:

- **1 file found**:
  ```
  ✅ Found job configuration:
  ${file_path}

  Type: Job configuration file

  Proceeding with job config modification...
  ```
  → Continue to **Step 4a: Analyze Job Configuration**

- **Multiple files found**:
  ```
  Found ${count} matching job config files:

  1. ci-operator/config/.../release-4.21__amd64-nightly.yaml
  2. ci-operator/config/.../release-4.21__arm64-nightly.yaml
  3. ci-operator/config/.../release-4.21__ppc64le-nightly.yaml

  Select file (1-${count}) or 'q' to quit:
  ```

  **Prompt user to select** which file to modify, then continue to **Step 4a: Analyze Job Configuration**

- **0 files found**:
  ```
  ℹ️  No job config found for: ${job_name} (OCP ${ocp_version})

  Searching for workflow files instead...
  ```
  → Continue to **Priority 2** below

**Priority 2: Search workflow files** (if job config not found):

```bash
cd <repo-path>

# Search for workflow files
find ci-operator/step-registry -type f -name "*${workflow_name}*workflow*.yaml"
```

**Handle workflow search results**:

- **0 files found**:
  ```
  ❌ No job config or workflow file found for: ${job_name}

  Suggestions:
  1. Check spelling of job/workflow name
  2. Verify OCP version (${ocp_version})
  3. Try with partial name
  4. Search manually:
     - Job configs: grep -r "as: ${job_name}" ci-operator/config/
     - Workflows: find ci-operator/step-registry -name "*workflow*.yaml" | grep <partial-name>
  ```

- **1 file found**:
  ```
  ✅ Found workflow file:
  ${file_path}

  Type: Workflow file

  Proceeding with workflow modification...
  ```
  → Continue to **Step 4b: Analyze Workflow File**

- **Multiple files found**:
  ```
  Found ${count} matching workflow files:

  1. ci-operator/step-registry/.../workflow1.yaml
  2. ci-operator/step-registry/.../workflow2.yaml
  3. ci-operator/step-registry/.../workflow3.yaml

  Select file (1-${count}) or 'q' to quit:
  ```

  **Prompt user to select** which file to modify, then continue to **Step 4b: Analyze Workflow File**

### Step 4a: Analyze Job Configuration

**Read and parse the job config YAML**:

```bash
# Find the specific test definition
grep -A 30 "as: ${job_name}" <job-config-file>
```

**Check for**:
1. ✅ Has `steps:` section
2. ✅ Has `test:` section inside steps
3. ❌ Does NOT already have `- ref: wait`

**Example current structure**:
```yaml
- as: aws-c2s-ipi-disc-priv-fips-f7
  cron: 36 16 3,12,19,26 * *
  steps:
    cluster_profile: aws-c2s-qe
    env:
      BASE_DOMAIN: qe.devcluster.openshift.com
      FIPS_ENABLED: "true"
    test:
    - chain: openshift-e2e-test-qe
    workflow: cucushift-installer-rehearse-aws-c2s-ipi-disconnected-private
```

**If wait already exists**:
```
ℹ️  Wait step already configured in job config

Current test section:
  test:
  - ref: wait
  - chain: openshift-e2e-test-qe

No changes needed. The job is already set up for debugging.
```

**If no test section found**:
```
ℹ️  Job config found but no test: section

This job uses only the workflow's test steps.
Searching for the workflow: ${workflow_name}
```
→ Fall back to searching for workflow (Priority 2 in Step 3)

→ Continue to **Step 5a: Show Diff for Job Config**

### Step 4b: Analyze Workflow File

**Read and parse the workflow YAML**:

```bash
cat <workflow-file>
```

**Check for**:
1. ✅ Has `workflow:` section
2. ✅ Has `test:` section
3. ❌ Does NOT already have `- ref: wait`

**Example current structure**:
```yaml
workflow:
  as: baremetalds-two-node-arbiter-upgrade
  steps:
    pre:
      - chain: baremetalds-ipi-pre
    test:
      - chain: baremetalds-ipi-test
    post:
      - chain: baremetalds-ipi-post
```

**If wait already exists**:
```
ℹ️  Wait step already configured in workflow

Current test section:
  test:
    - ref: wait
    - chain: baremetalds-ipi-test

No changes needed. The workflow is already set up for debugging.
```

**If no test section exists**:
```
ℹ️  Workflow has no test: section

This workflow is provision/deprovision only.
The test steps must be defined in the job config.

Please provide the full job name to modify the job config instead.
```
→ Exit or prompt for job name

→ Continue to **Step 5b: Show Diff for Workflow**

### Step 5a: Modify Job Config File

**Edit the job config file directly** - no confirmation needed:

```bash
# Add wait step before the last test step
# If timeout is provided, add it as a step property
# Using the Python implementation from Step 6 below
```

**Two scenarios**:

1. **Without custom timeout** (uses wait step's built-in default of 3h):
   ```yaml
   test:
   - ref: wait
   - chain: openshift-e2e-test-qe
   ```
   Note: No timeout or best_effort needed - the wait step will use its default TIMEOUT env var (3 hours)

2. **With custom timeout** (user provided timeout parameter):
   ```yaml
   test:
   - ref: wait
     timeout: 8h0m0s
     best_effort: true
   - chain: openshift-e2e-test-qe
   ```
   Note: `best_effort: true` is required when timeout is customized to prevent the wait step from failing the job if it times out

**Show brief confirmation**:
```
✅ Modified: ${job_name} (OCP ${ocp_version})
   File: <job-config-file-path>
   Added: - ref: wait${timeout:+ (timeout: ${timeout})}
```

### Step 5b: Modify Workflow File

**Edit the workflow file directly** - no confirmation needed:

```bash
# Add wait step before the last test step
# If timeout is provided, add it as a step property
# Using the Python implementation from Step 6 below
```

**Two scenarios**:

1. **Without custom timeout** (uses wait step's built-in default of 3h):
   ```yaml
   test:
   - ref: wait
   - chain: baremetalds-ipi-test
   ```
   Note: No timeout or best_effort needed - the wait step will use its default TIMEOUT env var (3 hours)

2. **With custom timeout** (user provided timeout parameter):
   ```yaml
   test:
   - ref: wait
     timeout: 8h0m0s
     best_effort: true
   - chain: baremetalds-ipi-test
   ```
   Note: `best_effort: true` is required when timeout is customized to prevent the wait step from failing the job if it times out

**Show brief confirmation**:
```
✅ Modified: ${workflow_name} workflow
   File: <workflow-file-path>
   Added: - ref: wait${timeout:+ (timeout: ${timeout})}
   ⚠️  Impact: Affects ALL jobs using this workflow
```

### Step 6: Create Branch and Commit

**Branch naming**:
```
debug-${workflow_name}-${ocp_version}-$(date +%Y%m%d)
```

Example: `debug-baremetalds-two-node-arbiter-4.21-20250131`

**Git operations**:
```bash
# Create branch
git checkout -b "${branch_name}"

# Modify the file (add wait step using the implementation below)
# Add '- ref: wait' as the first step in the test: section

# Stage change
git add <workflow-file>

# Commit
git commit -m "[Debug] Add wait step to ${workflow_name} for OCP ${ocp_version}

This adds a wait step to enable debugging of test failures in OCP ${ocp_version}.

The wait step pauses the workflow before tests run, allowing QE to:
- SSH into the test environment
- Inspect system state and logs
- Debug configuration issues
- Investigate test failures

OCP Version: ${ocp_version}
Workflow: ${workflow_name}"
```

**YAML Modification Methods** (safe text-based approach):

#### For Job Configuration Files

The wait step should be added before the last step in the job's test section:
1. Read the job config file line by line
2. Find the job definition (line with `- as: ${job_name}`)
3. Find the `test:` section within that job
4. Find all test steps (lines starting with `- ref:` or `- chain:`)
5. Check if `- ref: wait` already exists
6. If not, insert `- ref: wait` before the **last** test step with proper indentation
7. Write the file back

Example Python implementation:
```python
def add_wait_step_to_job_config(file_path, job_name, timeout=None):
    """
    Add '- ref: wait' before the last step in the job's test: section

    Args:
        file_path: Path to the job config YAML file
        job_name: Name of the job to modify
        timeout: Optional timeout in Go duration format (e.g., "8h0m0s", "1h30m")
                 If provided, also adds 'best_effort: true'
    """
    with open(file_path, 'r') as f:
        lines = f.readlines()

    # Find job definition (- as: job_name)
    job_line_index = None
    for i, line in enumerate(lines):
        if f'as: {job_name}' in line and line.strip().startswith('- as:'):
            job_line_index = i
            break

    if job_line_index is None:
        raise ValueError(f"Job '{job_name}' not found in config file")

    # Find 'test:' section within this job
    test_line_index = None
    for i in range(job_line_index + 1, len(lines)):
        line = lines[i]
        # Stop if we hit the next job (another '- as:' at same indentation level)
        if line.strip().startswith('- as:') and i != job_line_index:
            break
        if line.strip() == 'test:':
            test_line_index = i
            break

    if test_line_index is None:
        raise ValueError(f"No 'test:' section found in job '{job_name}'")

    # Find all test steps (lines with '- ref:' or '- chain:')
    test_steps = []
    indent_spaces = None
    test_section_indent = len(lines[test_line_index]) - len(lines[test_line_index].lstrip())

    for i in range(test_line_index + 1, len(lines)):
        line = lines[i]
        stripped = line.lstrip()
        current_indent = len(line) - len(stripped)

        # Stop if we hit another key at same or lower indent as 'test:'
        if stripped and current_indent <= test_section_indent and not stripped.startswith('-'):
            break

        if stripped.startswith('- ref:') or stripped.startswith('- chain:'):
            if indent_spaces is None:
                indent_spaces = current_indent
            test_steps.append(i)

    if not test_steps:
        raise ValueError("No test steps found in test: section")

    # Check if wait already exists
    for i in range(test_line_index + 1, test_steps[-1] + 5):
        if i < len(lines) and 'ref: wait' in lines[i]:
            return False  # Wait already exists

    # Insert wait step before the last test step
    last_step_index = test_steps[-1]

    if timeout:
        # With timeout: add ref, timeout, and best_effort properties
        wait_lines = [
            ' ' * indent_spaces + '- ref: wait\n',
            ' ' * (indent_spaces + 2) + f'timeout: {timeout}\n',
            ' ' * (indent_spaces + 2) + 'best_effort: true\n'
        ]
        for line in reversed(wait_lines):
            lines.insert(last_step_index, line)
    else:
        # Without timeout: simple ref only
        wait_line = ' ' * indent_spaces + '- ref: wait\n'
        lines.insert(last_step_index, wait_line)

    # Write back
    with open(file_path, 'w') as f:
        f.writelines(lines)

    return True
```

#### For Workflow Files

The wait step should be added before the last step in the workflow's test section:
1. Read the workflow file line by line
2. Find the `test:` section
3. Find all test steps (lines starting with `- ref:` or `- chain:`)
4. Check if `- ref: wait` already exists
5. If not, insert `- ref: wait` before the **last** test step with proper indentation
6. Write the file back

Example Python implementation:
```python
def add_wait_step_to_workflow(file_path, timeout=None):
    """
    Add '- ref: wait' before the last step in the workflow's test: section

    Args:
        file_path: Path to the workflow YAML file
        timeout: Optional timeout in Go duration format (e.g., "8h0m0s", "1h30m")
                 If provided, also adds 'best_effort: true'
    """
    with open(file_path, 'r') as f:
        lines = f.readlines()

    # Find 'test:' section
    test_line_index = None
    for i, line in enumerate(lines):
        if line.strip() == 'test:':
            test_line_index = i
            break

    if test_line_index is None:
        raise ValueError("No 'test:' section found in workflow")

    # Find all test steps (lines with '- ref:' or '- chain:')
    test_steps = []
    indent_spaces = None
    test_section_indent = len(lines[test_line_index]) - len(lines[test_line_index].lstrip())

    for i in range(test_line_index + 1, len(lines)):
        line = lines[i]
        stripped = line.lstrip()
        current_indent = len(line) - len(stripped)

        # Stop if we hit another section key at same indent level as 'test:'
        if stripped and current_indent == test_section_indent and not stripped.startswith('-'):
            break

        if stripped.startswith('- ref:') or stripped.startswith('- chain:'):
            if indent_spaces is None:
                indent_spaces = current_indent
            test_steps.append(i)

    if not test_steps:
        raise ValueError("No test steps found in test: section")

    # Check if wait already exists in test section
    for i in range(test_line_index + 1, test_steps[-1] + 5):
        if i < len(lines) and 'ref: wait' in lines[i]:
            return False  # Wait already exists

    # Insert wait step before the last test step
    last_step_index = test_steps[-1]

    if timeout:
        # With timeout: add ref, timeout, and best_effort properties
        wait_lines = [
            ' ' * indent_spaces + '- ref: wait\n',
            ' ' * (indent_spaces + 2) + f'timeout: {timeout}\n',
            ' ' * (indent_spaces + 2) + 'best_effort: true\n'
        ]
        for line in reversed(wait_lines):
            lines.insert(last_step_index, line)
    else:
        # Without timeout: simple ref only
        wait_line = ' ' * indent_spaces + '- ref: wait\n'
        lines.insert(last_step_index, wait_line)

    # Write back
    with open(file_path, 'w') as f:
        f.writelines(lines)

    return True
```

### Step 7: Push and Show GitHub Link

**Auto-push the branch**:
```bash
git push origin "${branch_name}"
```

**Display GitHub PR creation link**:
```
✅ Changes pushed successfully!

Create PR here:
https://github.com/openshift/release/compare/master...${branch_name}

Branch: ${branch_name}
Job: ${job_name}
OCP: ${ocp_version}

⚠️  Remember to close PR after debugging (DO NOT MERGE)
```

That's it! Simple and clean.

### Error Handling

**Error: Repository Not Found**
```
❌ Error: Repository not found at ${repo_path}

Please provide the correct path to openshift/release repository.

To clone:
git clone https://github.com/openshift/release.git
```

**Error: Not in openshift/release Repo**
```
❌ Error: This doesn't appear to be the openshift/release repository

Remote URL: ${current_remote}
Expected: github.com/openshift/release

Please navigate to the correct repository.
```

**Error: Workflow File Not Found**
```
❌ Error: Workflow file not found

Searched for: *${workflow_name}*workflow*.yaml
Location: ci-operator/step-registry/

Suggestions:
1. Verify the workflow name
2. Try a partial match
3. Search manually: find ci-operator/step-registry -name "*workflow*.yaml"
```

**Error: Wait Step Already Exists**
```
ℹ️  Wait step already configured in this workflow

No action needed - you can proceed with debugging using the existing wait step.
```

**Error: Invalid OCP Version**
```
❌ Invalid OCP version: ${version}

Valid versions: 4.18, 4.19, 4.20, 4.21, 4.22, master

Please provide a valid version.
```

### Error: Invalid Timeout Format
```
❌ Invalid timeout format: ${timeout}

Valid format: Integer followed by 'h' (e.g., "1h", "2h", "8h", "24h", "72h")
Valid range: 1h to 72h

Examples:
- "1h" (1 hour)
- "8h" (8 hours)
- "24h" (24 hours)
- "72h" (72 hours, maximum)

Please provide a valid timeout in hours.
```

### Note: Timeout Normalization

When a user provides a timeout like "8h", the implementation should normalize it to the standard Go duration format "8h0m0s" for consistency with existing configurations in the codebase.

## Return Value

- **Success**: PR URL and debugging instructions
- **Error**: Error message with suggestions for resolution
- **Format**: Text output with emoji indicators for status

## Examples

### Example 1: Job Config Without Custom Timeout

```
User: /ci:add-debug-wait aws-ipi-f7-longduration-workload

Claude: OCP version: 4.21
         Repo path: ~/automation/Openshift/release

Claude: ✅ Modified: aws-ipi-f7-longduration-workload (OCP 4.21)
        ✅ Changes pushed successfully!

        Create PR here:
        https://github.com/openshift/release/compare/master...debug-aws-ipi-f7-longduration-workload-4.21-20251031

        Branch: debug-aws-ipi-f7-longduration-workload-4.21-20251031
        Job: aws-ipi-f7-longduration-workload
        OCP: 4.21

        ⚠️  Remember to close PR after debugging (DO NOT MERGE)
```

**Done!** Just click the link and create the PR.

### Example 2: Job Config With Custom Timeout

```
User: /ci:add-debug-wait aws-ipi-f7-longduration-workload 8h

Claude: OCP version: 4.21
         Repo path: ~/automation/Openshift/release

Claude: ✅ Modified: aws-ipi-f7-longduration-workload (OCP 4.21)
        Added: - ref: wait (timeout: 8h0m0s)
        ✅ Changes pushed successfully!

        Create PR here:
        https://github.com/openshift/release/compare/master...debug-aws-ipi-f7-longduration-workload-4.21-20251031

        Branch: debug-aws-ipi-f7-longduration-workload-4.21-20251031
        Job: aws-ipi-f7-longduration-workload
        OCP: 4.21
        Timeout: 8h0m0s

        ⚠️  Remember to close PR after debugging (DO NOT MERGE)
```

**Result in YAML**:
```yaml
test:
- ref: wait
  timeout: 8h0m0s
  best_effort: true
- chain: openshift-e2e-test-qe
```

### Example 3: Workflow File With Timeout

```
User: /ci:add-debug-wait baremetalds-two-node-arbiter-upgrade 24h

Claude: OCP version: 4.20
         Repo path: ~/repos/openshift-release

Claude: ℹ️  No job config found, searching workflow...
        ✅ Modified: baremetalds-two-node-arbiter-upgrade workflow
        Added: - ref: wait (timeout: 24h0m0s)
        ⚠️  Impact: Affects ALL jobs using this workflow
        ✅ Changes pushed successfully!

        Create PR here:
        https://github.com/openshift/release/compare/master...debug-baremetalds-two-node-arbiter-upgrade-4.20-20251031

        Branch: debug-baremetalds-two-node-arbiter-upgrade-4.20-20251031
        OCP: 4.20
        Timeout: 24h0m0s
```

## Arguments

- **$1** (workflow-or-job-name): The name of the CI workflow or job to add the wait step to (required)
- **$2** (timeout): Optional timeout in hours (1h-72h). Examples: "1h", "8h", "24h", "72h". If not provided, uses wait step's default (3h)

## Notes

### Best Practices for QE

**Before Running Command**:
- ✅ Confirm test is actually failing
- ✅ Check existing debug PRs
- ✅ Know which OCP version is affected

**During Debugging**:
- 📝 Take detailed notes
- 💾 Save logs and screenshots
- 🔍 Document root cause
- 📊 Record all findings

**After Debugging**:
- ✅ Document findings
- ✅ Close the debug PR
- ✅ Delete the branch
- ✅ Share learnings with team
- ✅ Create fix PR if needed

### Future Enhancements

Consider adding companion commands:
- `/ci:close-debug-pr` - Lists open debug PRs, prompts for findings, closes PR
- `/ci:list-debug-prs` - Show all open debug PRs
- `/ci:revert-debug-pr` - Revert a debug PR that was merged by mistake
