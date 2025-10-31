---
description: Add a wait step to a CI workflow for debugging test failures
argument-hint: <workflow-or-job-name>
---

## Name
ci:add-debug-wait

## Synopsis
```
/ci:add-debug-wait <workflow-or-job-name>
```

## Description

The `ci:add-debug-wait` command adds a `wait` step to a CI job/workflow for debugging test failures.

**What it does:**
1. Takes job name and OCP version as input
2. Finds and edits the job config or workflow file
3. Adds `- ref: wait` before the last test step
4. Commits and pushes the change
5. Gives you a GitHub link to create the PR

**That's it!** Simple, fast, and automated.

## Implementation

The command performs the following steps:

### Step 1: Gather Required Information

**Prompt user for** (in this order):

1. **Workflow/Job Name**: (from command argument or prompt)
   ```
   Workflow or job name: <user-input>
   Example: aws-c2s-ipi-disc-priv-fips-f7
   Example: baremetalds-two-node-arbiter-e2e-openshift-test-private-tests
   ```

2. **OCP Version**: (prompt - REQUIRED for searching job configs)
   ```
   OCP version for debugging (e.g., 4.18, 4.19, 4.20, 4.21, 4.22):
   ```
   This is used to:
   - Search the correct job config file (e.g., release-4.21)
   - Document which version needs debugging
   - Add context to the PR

3. **OpenShift Release Repo Path**: (prompt if not in current directory)
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
# Simply add '- ref: wait' before the last test step
# Using the Python implementation from Step 6 below
```

**Show brief confirmation**:
```
✅ Modified: ${job_name} (OCP ${ocp_version})
   File: <job-config-file-path>
   Added: - ref: wait (before last test step)
```

### Step 5b: Modify Workflow File

**Edit the workflow file directly** - no confirmation needed:

```bash
# Simply add '- ref: wait' before the last test step
# Using the Python implementation from Step 6 below
```

**Show brief confirmation**:
```
✅ Modified: ${workflow_name} workflow
   File: <workflow-file-path>
   Added: - ref: wait (before last test step)
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
def add_wait_step_to_job_config(file_path, job_name):
    """
    Add '- ref: wait' before the last step in the job's test: section
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

    for i in range(test_line_index + 1, len(lines)):
        line = lines[i]
        stripped = line.lstrip()

        if stripped.startswith('- ref:') or stripped.startswith('- chain:'):
            if indent_spaces is None:
                indent_spaces = len(line) - len(stripped)
            test_steps.append(i)

        # Stop if we hit another key at same or lower indentation as 'test:'
        if line.strip() and not line.startswith(' '):
            break
        if line.strip() and line.strip() != '' and not line.strip().startswith('#'):
            test_indent = len(lines[test_line_index]) - len(lines[test_line_index].lstrip())
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= test_indent and stripped not in ['', '#']:
                break

    if not test_steps:
        raise ValueError("No test steps found in test: section")

    # Check if wait already exists
    for i in range(test_line_index + 1, test_steps[-1] + 5):
        if i < len(lines) and 'ref: wait' in lines[i]:
            return False  # Wait already exists

    # Insert wait step before the last test step
    last_step_index = test_steps[-1]
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
def add_wait_step_to_workflow(file_path):
    """
    Add '- ref: wait' before the last step in the workflow's test: section
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

    for i in range(test_line_index + 1, len(lines)):
        line = lines[i]
        stripped = line.lstrip()

        if stripped.startswith('- ref:') or stripped.startswith('- chain:'):
            if indent_spaces is None:
                indent_spaces = len(line) - len(stripped)
            test_steps.append(i)

        # Stop if we hit another top-level key
        if line.strip() and not line.startswith(' '):
            break

    if not test_steps:
        raise ValueError("No test steps found in test: section")

    # Check if wait already exists in test section
    for i in range(test_line_index + 1, test_steps[-1] + 5):
        if i < len(lines) and 'ref: wait' in lines[i]:
            return False  # Wait already exists

    # Insert wait step before the last test step
    last_step_index = test_steps[-1]
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

## Return Value

- **Success**: PR URL and debugging instructions
- **Error**: Error message with suggestions for resolution
- **Format**: Text output with emoji indicators for status

## Examples

### Example 1: Job Config (Most Common)

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

### Example 2: Workflow File (Fallback)

```
User: /ci:add-debug-wait baremetalds-two-node-arbiter-upgrade

Claude: OCP version: 4.20
         Repo path: ~/repos/openshift-release

Claude: ℹ️  No job config found, searching workflow...
        ✅ Modified: baremetalds-two-node-arbiter-upgrade workflow
        ⚠️  Impact: Affects ALL jobs using this workflow
        ✅ Changes pushed successfully!

        Create PR here:
        https://github.com/openshift/release/compare/master...debug-baremetalds-two-node-arbiter-upgrade-4.20-20251031

        Branch: debug-baremetalds-two-node-arbiter-upgrade-4.20-20251031
        OCP: 4.20
```

## Arguments

- **$1** (workflow-or-job-name): The name of the CI workflow or job to add the wait step to (required)

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
