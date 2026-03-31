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
4. Creates a git commit
5. Pushes the commit to your fork (`origin` remote)
6. Creates a PR via `gh`

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
   - **For job config files** (`ci-operator/config/`): Set as the `TIMEOUT` env var (e.g., `TIMEOUT: +8 hours`) in the job's `env:` section
   - **For workflow files** (`ci-operator/step-registry/`): Set as `timeout:` (normalized to Go duration format, e.g., "8h" → "8h0m0s") and `best_effort: true` properties on the ref step

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

### Step 2: Validate Environment and Prepare Branch

**Silently validate and prepare** (no user prompts):

```bash
cd <repo-path>

# Check 1: Repository exists and is correct
git remote -v | grep "openshift/release" || exit 1

# Check 2: Determine the default branch name (main or master)
default_branch=$(git remote show upstream 2>/dev/null | grep "HEAD branch" | awk '{print $NF}')
if [ -z "$default_branch" ]; then
  # Fallback: check which branch exists locally
  for branch in main master; do
    if git rev-parse --verify "$branch" >/dev/null 2>&1; then
      default_branch="$branch"
      break
    fi
  done
fi

# Check 3: Checkout default branch and update from upstream
# Use --track -B to handle fresh clones where the local branch may not exist
git checkout --track -B "${default_branch}" "upstream/${default_branch}" 2>/dev/null \
  || git checkout "${default_branch}"
git pull --rebase upstream "${default_branch}"
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
Add a `test:` section with the wait step before the `post:` section. Since these are debug PRs (never merged), it is safe to add a test section even if the workflow didn't have one.

```yaml
    test:
      - ref: wait
    post:
      - chain: cucushift-installer-rehearse-aws-ipi-deprovision
```

Or with custom timeout:
```yaml
    test:
      - ref: wait
        timeout: 8h0m0s
        best_effort: true
    post:
      - chain: cucushift-installer-rehearse-aws-ipi-deprovision
```

→ Continue to **Step 5b: Modify Workflow File**

### Step 5a: Modify Job Config File

**Edit the job config file directly** - no confirmation needed:

```bash
# Add wait step before the last test step
# If timeout is provided, set it via the TIMEOUT env var in the job's env section
# See Step 6 for the YAML modification algorithm
```

**After editing, validate the file** by running the ref-step linter:
```bash
python3 <ai-helpers-repo>/plugins/ci/scripts/validate-ref-steps.py <job-config-file>
```
This catches invalid properties (e.g., `timeout:`, `best_effort:`) on `ref:` steps in job config files. If validation fails, fix the file before committing — use the `TIMEOUT` env var instead.

**Two scenarios**:

1. **Without custom timeout** (uses wait step's built-in default of 3h):
   ```yaml
   test:
   - ref: wait
   - chain: openshift-e2e-test-qe
   ```
   Note: No timeout or env change needed - the wait step will use its default TIMEOUT env var (3 hours)

2. **With custom timeout** (user-provided timeout parameter):
   Add `TIMEOUT` to the existing `env:` section within the job's `steps:` block, and add `- ref: wait` to the `test:` section:
   ```yaml
   env:
     BASE_DOMAIN: qe.devcluster.openshift.com
     TIMEOUT: +8 hours
   test:
   - ref: wait
   - chain: openshift-e2e-test-qe
   ```
   Note: The wait ref reads the `TIMEOUT` env var to determine how long to wait. Format: `+N hours` where N is the number of hours (e.g., `+1 hours`, `+8 hours`, `+24 hours`, `+72 hours`). Do NOT quote the value — the `determinize-ci-operator` tool strips quotes. If the job already has an `env:` section, add the `TIMEOUT` key to it. If not, create the `env:` section under `steps:`.

**Show brief confirmation**:
```text
✅ Modified: ${job_name} (OCP ${ocp_version})
   File: <job-config-file-path>
   Added: - ref: wait${timeout:+ (TIMEOUT: +${hours} hours)}
```

### Step 5b: Modify Workflow File

**Edit the workflow file directly** - no confirmation needed:

```bash
# Add wait step before the last test step
# If timeout is provided, add it as a step property
# See Step 6 for the YAML modification algorithm
```

**Two scenarios**:

1. **Without custom timeout** (uses wait step's built-in default of 3h):
   ```yaml
   test:
   - ref: wait
   - chain: baremetalds-ipi-test
   ```
   Note: No timeout or best_effort needed - the wait step will use its default TIMEOUT env var (3 hours)

2. **With custom timeout** (user-provided timeout parameter):
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
# Create branch from the updated default branch (already checked out and updated in Step 2)
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

**YAML Modification Algorithm**:

The modification process for both job configs and workflow files follows the same pattern:

1. **Locate the target**: Find the `test:` section
   - For job configs: Within the specific job definition (`- as: ${job_name}`)
   - For workflows: At the workflow level

2. **Find test steps**: Identify all steps (lines with `- ref:` or `- chain:`)

3. **Check for duplicates**: Ensure `- ref: wait` doesn't already exist

4. **Insert wait step**: Add before the **last** test step with matching indentation

5. **Handle timeout** (differs between job configs and workflow files):

   **For job config files** (`ci-operator/config/`):
   - Without timeout: Add simple `- ref: wait`
   - With timeout: Add simple `- ref: wait` AND add `TIMEOUT: +N hours` to the job's `env:` section

   **For workflow files** (`ci-operator/step-registry/`):
   - Without timeout: Add simple `- ref: wait`
   - With timeout: Add `- ref: wait` with `timeout:` and `best_effort:` properties (valid in workflow schema)

**Example transformation (job config):**

Before:
```yaml
env:
  BASE_DOMAIN: qe.devcluster.openshift.com
test:
- chain: openshift-e2e-test-qe
```

After (without timeout):
```yaml
env:
  BASE_DOMAIN: qe.devcluster.openshift.com
test:
- ref: wait
- chain: openshift-e2e-test-qe
```

After (with timeout=8h):
```yaml
env:
  BASE_DOMAIN: qe.devcluster.openshift.com
  TIMEOUT: +8 hours
test:
- ref: wait
- chain: openshift-e2e-test-qe
```

**Example transformation (workflow file):**

Before:
```yaml
test:
- chain: baremetalds-ipi-test
```

After (with timeout=8h):
```yaml
test:
- ref: wait
  timeout: 8h0m0s
  best_effort: true
- chain: baremetalds-ipi-test
```

6. **Validate**: Run `validate-ref-steps.py` on the modified file (see Step 5a). Fix any errors before committing.

**Critical constraints:**
- Preserve exact YAML indentation (typically 2 spaces per level)
- Insert BEFORE the last step, not after
- Normalize timeout format: for job configs use `+N hours`, for workflow files use Go duration (e.g., "8h" → "8h0m0s")

### Step 7: Push to Fork

**Push the branch to the user's fork** (`origin` remote):
```bash
git push origin "${branch_name}"
```

### Step 8: Create PR

**Create the PR using `gh`**:
```bash
gh pr create --repo openshift/release --title "[Debug] Add wait step to ${job_name} for OCP ${ocp_version}" --body "$(cat <<'EOF'
## Summary
- Adds a wait step to enable debugging of test failures in OCP ${ocp_version}
- Job: ${job_name}
- Timeout: ${timeout:-default (3h)}

The wait step pauses the workflow before tests run, allowing QE to:
- SSH into the test environment
- Inspect system state and logs
- Debug configuration issues
- Investigate test failures

⚠️ **DO NOT MERGE** — close this PR after debugging is complete.
EOF
)"
```

**Display the PR URL**:
```text
✅ PR created successfully!

PR: <pr_url>
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

- **Success**: Created PR URL and debugging instructions
- **Error**: Error message with suggestions for resolution
- **Format**: Text output with emoji indicators for status

## Examples

### Example 1: Without Timeout (Default 3h)

```bash
/ci:add-debug-wait aws-ipi-f7-longduration-workload
```

Prompts for: OCP version (4.21), repo path

Result:
```yaml
test:
- ref: wait
- chain: openshift-e2e-test-qe
```

Returns: PR URL

### Example 2: With Custom Timeout (Job Config)

```bash
/ci:add-debug-wait aws-ipi-f7-longduration-workload 8h
```

Prompts for: OCP version (4.21), repo path

Result (adds TIMEOUT env var + ref: wait):
```yaml
env:
  BASE_DOMAIN: qe.devcluster.openshift.com
  TIMEOUT: +8 hours
test:
- ref: wait
- chain: openshift-e2e-test-qe
```

Returns: PR URL

### Example 3: With Custom Timeout (Workflow File)

```bash
/ci:add-debug-wait baremetalds-two-node-arbiter-upgrade 24h
```

Behavior: Searches job config first, falls back to workflow if not found. Warns that workflow changes affect ALL jobs using it.

Result (timeout/best_effort on ref is valid in workflow files):
```yaml
test:
- ref: wait
  timeout: 24h0m0s
  best_effort: true
- chain: baremetalds-ipi-test
```

Returns: PR URL

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
