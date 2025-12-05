---
description: Automatically add 'approve' label to PR when all conditions are met
argument-hint: [pr-number]
---

## Name
git:auto-approve

## Synopsis
```
/git:auto-approve [pr-number]
```

## Description

The `/git:auto-approve` command automates adding the 'approve' label to a pull request when all required conditions are satisfied. This is particularly useful for repositories using the Prow/Tide merge automation system where the 'approve' label is required for automatic merging.

The command performs comprehensive checks before adding the approve label:
1. Verifies the PR author is listed as an approver in OWNERS files
2. Confirms the PR has the 'lgtm' label
3. Validates all CI tests have passed
4. Ensures no 'do-not-merge' related labels are present

If any condition fails, the command reports which conditions are not met without making any changes.

## Implementation

### Prerequisites

**GitHub CLI (gh) Installation**
- Check if installed: `which gh`
- If not installed, provide installation instructions:
  - macOS: `brew install gh`
  - Linux: Follow instructions at https://github.com/cli/cli/linux
- Verify authentication: `gh auth status`
- If not authenticated: `gh auth login`

### Step 1: Determine the PR number

**If PR number not provided:**
```bash
# Get current branch
current_branch=$(git branch --show-current)

# Find PR for current branch
pr_number=$(gh pr list --head "$current_branch" --json number --jq '.[0].number')

# If no PR found, fail with message:
# "Error: No PR found for branch '$current_branch'. Please specify PR number or create a PR first."
```

**If PR number provided:**
- Use the provided PR number directly
- Validate it exists:
```bash
gh pr view $pr_number --json number &> /dev/null
# If exit code is not 0, fail with message:
# "Error: PR #$pr_number not found"
```

### Step 2: Fetch PR details

Use GitHub CLI to get comprehensive PR information:
```bash
gh pr view $pr_number --json \
  number,title,author,state,labels,statusCheckRollup,files \
  > /tmp/pr-details.json
```

Extract key information from JSON:
- `author.login`: PR author username
- `state`: PR state (must be OPEN)
- `labels[].name`: All label names on the PR
- `statusCheckRollup[].status`: CI check statuses
- `files[].path`: List of changed files

**Validation:**
- If PR state is not "OPEN", fail with message:
  ```
  Error: PR #$pr_number is not open (state: $state)
  ```

### Step 3: Check Condition 1 - Author is an approver

**Find OWNERS files for changed files:**

For each file changed in the PR:
1. Search for OWNERS files in the file's directory and parent directories up to repository root
2. Parse each OWNERS file (YAML format):
   ```yaml
   approvers:
     - username1
     - username2
   ```

**Collect all approvers:**
- Aggregate all `approvers` from all OWNERS files found
- Deduplicate the list
- Check if `author.login` is in the approvers list

**Implementation:**
```bash
# For each changed file, find OWNERS files
changed_files=$(jq -r '.files[].path' /tmp/pr-details.json)

for file in $changed_files; do
  dir=$(dirname "$file")

  # Search up the directory tree for OWNERS files
  while [ "$dir" != "." ]; do
    if [ -f "$dir/OWNERS" ]; then
      # Parse OWNERS file and extract approvers
      # Add to aggregated list
    fi
    dir=$(dirname "$dir")
  done

  # Check root OWNERS file
  if [ -f "OWNERS" ]; then
    # Parse and add approvers
  fi
done
```

**Result:**
- Set `is_approver=true` if author is found in any approvers list
- Set `is_approver=false` otherwise

### Step 4: Check Condition 2 - PR has 'lgtm' label

Extract labels from PR details:
```bash
labels=$(jq -r '.labels[].name' /tmp/pr-details.json)
```

Check for 'lgtm' label:
```bash
if echo "$labels" | grep -q '^lgtm$'; then
  has_lgtm=true
else
  has_lgtm=false
fi
```

**Result:**
- Set `has_lgtm=true` if 'lgtm' label is present
- Set `has_lgtm=false` otherwise

### Step 5: Check Condition 3 - All CI tests passed

Extract CI check statuses:
```bash
# Get all check statuses
check_statuses=$(jq -r '.statusCheckRollup[]? | "\(.name):\(.status):\(.conclusion)"' /tmp/pr-details.json)
```

Analyze check statuses:
- **Status values**: QUEUED, IN_PROGRESS, COMPLETED
- **Conclusion values**: SUCCESS, FAILURE, NEUTRAL, CANCELLED, SKIPPED, TIMED_OUT, ACTION_REQUIRED

**Pass conditions:**
- All checks must have status "COMPLETED"
- All completed checks must have conclusion "SUCCESS" or "NEUTRAL" or "SKIPPED"
- No checks with conclusion "FAILURE", "CANCELLED", or "TIMED_OUT"

**Special cases:**
- If no checks are defined, consider as passing (set `all_tests_passed=true`)
- If checks are still running (status != COMPLETED), consider as not passed

**Implementation:**
```bash
all_tests_passed=true
failed_checks=""

while IFS=':' read -r name status conclusion; do
  if [ "$status" != "COMPLETED" ]; then
    all_tests_passed=false
    failed_checks="$failed_checks\n  - $name: $status"
  elif [ "$conclusion" != "SUCCESS" ] && [ "$conclusion" != "NEUTRAL" ] && [ "$conclusion" != "SKIPPED" ]; then
    all_tests_passed=false
    failed_checks="$failed_checks\n  - $name: $conclusion"
  fi
done <<< "$check_statuses"
```

**Result:**
- Set `all_tests_passed=true` if all checks passed
- Set `all_tests_passed=false` otherwise
- Capture `failed_checks` for reporting

### Step 6: Check Condition 4 - No 'do-not-merge' labels

Check for any labels containing 'do-not-merge':
```bash
do_not_merge_labels=$(echo "$labels" | grep -i 'do-not-merge' || true)

if [ -z "$do_not_merge_labels" ]; then
  no_dnm_labels=true
else
  no_dnm_labels=false
fi
```

Common 'do-not-merge' label patterns to check:
- `do-not-merge`
- `do-not-merge/hold`
- `do-not-merge/work-in-progress`
- `do-not-merge/invalid-owners-file`
- Any label containing "do-not-merge"

**Result:**
- Set `no_dnm_labels=true` if no do-not-merge labels found
- Set `no_dnm_labels=false` otherwise
- Capture `do_not_merge_labels` for reporting

### Step 7: Evaluate all conditions and take action

**Check all conditions:**
```bash
if [ "$is_approver" = true ] && \
   [ "$has_lgtm" = true ] && \
   [ "$all_tests_passed" = true ] && \
   [ "$no_dnm_labels" = true ]; then
  # All conditions met - add approve label
  can_approve=true
else
  # Conditions not met - report status
  can_approve=false
fi
```

**If can_approve=true:**
1. Check if 'approve' label already exists:
   ```bash
   if echo "$labels" | grep -q '^approve$'; then
     # Already approved
   else
     # Add approve label
     gh pr edit $pr_number --add-label approve
   fi
   ```

2. Report success

**If can_approve=false:**
- Report which conditions are not met
- Do not add the approve label

### Step 8: Generate report

Create a detailed status report showing:
- PR number and title
- All condition statuses (✓ or ✗)
- Specific details for failed conditions
- Final action taken

## Return Value

**Success (all conditions met, approve label added):**
```
✓ Auto-approve check for PR #1234: "Add new feature"

Conditions:
  ✓ Author is an approver (found in OWNERS files)
  ✓ PR has 'lgtm' label
  ✓ All CI tests passed (15/15 checks)
  ✓ No 'do-not-merge' labels

Action: Added 'approve' label to PR #1234
```

**Success (already approved):**
```
✓ Auto-approve check for PR #1234: "Add new feature"

Conditions:
  ✓ Author is an approver (found in OWNERS files)
  ✓ PR has 'lgtm' label
  ✓ All CI tests passed (15/15 checks)
  ✓ No 'do-not-merge' labels

Action: PR #1234 already has 'approve' label
```

**Failure (conditions not met):**
```
✗ Auto-approve check for PR #1234: "Add new feature"

Conditions:
  ✗ Author is NOT an approver
    - Author: user123
    - Approvers found in OWNERS: alice, bob, charlie
  ✓ PR has 'lgtm' label
  ✗ CI tests not all passed
    - api-tests: FAILURE
    - integration-tests: IN_PROGRESS
    - unit-tests: SUCCESS
  ✓ No 'do-not-merge' labels

Action: Cannot add 'approve' label - conditions not met
```

## Examples

1. **Auto-approve current branch PR** (all conditions met):
   ```
   /git:auto-approve
   ```
   Output:
   ```
   ✓ Auto-approve check for PR #1234: "Fix authentication bug"

   Conditions:
     ✓ Author (alice) is an approver (found in OWNERS, pkg/auth/OWNERS)
     ✓ PR has 'lgtm' label
     ✓ All CI tests passed (8/8 checks)
     ✓ No 'do-not-merge' labels

   Action: Added 'approve' label to PR #1234
   ```

2. **Specify PR number** (conditions not met):
   ```
   /git:auto-approve 5678
   ```
   Output:
   ```
   ✗ Auto-approve check for PR #5678: "Add experimental feature"

   Conditions:
     ✓ Author (bob) is an approver (found in OWNERS)
     ✓ PR has 'lgtm' label
     ✓ All CI tests passed (12/12 checks)
     ✗ Has 'do-not-merge' labels:
       - do-not-merge/work-in-progress

   Action: Cannot add 'approve' label - remove do-not-merge labels first
   ```

3. **CI tests still running**:
   ```
   /git:auto-approve
   ```
   Output:
   ```
   ✗ Auto-approve check for PR #9012: "Update dependencies"

   Conditions:
     ✓ Author (charlie) is an approver (found in OWNERS, vendor/OWNERS)
     ✓ PR has 'lgtm' label
     ✗ CI tests not all passed:
       - unit-tests: SUCCESS
       - integration-tests: IN_PROGRESS
       - e2e-tests: QUEUED
     ✓ No 'do-not-merge' labels

   Action: Cannot add 'approve' label - wait for CI tests to complete
   ```

4. **Author not an approver**:
   ```
   /git:auto-approve
   ```
   Output:
   ```
   ✗ Auto-approve check for PR #3456: "Documentation update"

   Conditions:
     ✗ Author (contributor123) is NOT an approver
       - Approvers found in OWNERS: alice, bob, charlie, diana
     ✓ PR has 'lgtm' label
     ✓ All CI tests passed (5/5 checks)
     ✓ No 'do-not-merge' labels

   Action: Cannot add 'approve' label - author needs approval from: alice, bob, charlie, or diana
   ```

5. **Missing lgtm label**:
   ```
   /git:auto-approve
   ```
   Output:
   ```
   ✗ Auto-approve check for PR #7890: "Refactor API handlers"

   Conditions:
     ✓ Author (diana) is an approver (found in pkg/api/OWNERS)
     ✗ PR does NOT have 'lgtm' label
       - Current labels: size/L, kind/cleanup
     ✓ All CI tests passed (10/10 checks)
     ✓ No 'do-not-merge' labels

   Action: Cannot add 'approve' label - needs code review and 'lgtm' label first
   ```

6. **No PR found for current branch**:
   ```
   /git:auto-approve
   ```
   Output:
   ```
   Error: No PR found for branch 'feature/new-api'

   Please either:
   - Create a PR first with: gh pr create
   - Specify a PR number: /git:auto-approve <pr-number>
   - Switch to a branch with an existing PR
   ```

7. **All conditions met, but already approved**:
   ```
   /git:auto-approve 4321
   ```
   Output:
   ```
   ✓ Auto-approve check for PR #4321: "Performance improvements"

   Conditions:
     ✓ Author (eve) is an approver (found in pkg/performance/OWNERS)
     ✓ PR has 'lgtm' label
     ✓ All CI tests passed (20/20 checks)
     ✓ No 'do-not-merge' labels

   Current labels: lgtm, approve, size/XL, kind/performance

   Action: PR #4321 already has 'approve' label - no action needed
   ```

## Arguments

- **pr-number** (optional): The pull request number to check and potentially approve. If not provided, the command will find the PR associated with the current git branch.

## Notes

- This command requires the GitHub CLI (`gh`) to be installed and authenticated
- The command only adds the 'approve' label; it does not trigger merges (that's handled by Prow/Tide)
- OWNERS files must be in YAML format with an `approvers` field
- The author check looks for the PR author's GitHub username in any OWNERS file related to changed files
- CI checks include all GitHub Actions, status checks, and required checks
- The command is safe to run multiple times; it won't duplicate labels
- Consider setting up a git alias for quick access: `git config alias.auto-approve '!gh pr list --author @me --json number -q ".[0].number" | xargs -I {} /git:auto-approve {}'`
