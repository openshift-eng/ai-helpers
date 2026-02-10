---
description: Find and retest failed e2e CI jobs on a PR
argument-hint: "[repo] <pr-number>"
---

## Name
ci:e2e-retest

## Synopsis
```
/ci:e2e-retest <pr-number>
/ci:e2e-retest <repo> <pr-number>
/ci:e2e-retest <org>/<repo> <pr-number>
```

## Description
Analyzes a pull request to find all failed e2e CI jobs from Prow status checks, showing consecutive failure counts and providing interactive options to retest them.

The repository can be specified in multiple ways:
- **Omit repo argument**: Auto-detect from current directory's git remote
- **Repo name only**: Assumes `openshift/<repo>` (e.g., `ovn-kubernetes` → `openshift/ovn-kubernetes`)
- **Full org/repo**: Use any GitHub repository (e.g., `openshift/origin`, `kubernetes/kubernetes`)

## Implementation

**CRITICAL INSTRUCTIONS - READ FIRST:**
1. DO NOT output any text to the user
2. DO NOT explain what you are doing
3. DO NOT say "I'll execute" or similar
4. IMMEDIATELY execute the bash block below with NO preamble

Execute the entire workflow in a single bash invocation:

```bash
# Use relative path from working directory
SCRIPT_DIR="plugins/ci/skills/e2e-retest"

# Extract PR number from arguments for temp file naming
if [ $# -eq 1 ]; then
  PR_NUM="$1"
else
  PR_NUM="$2"
fi

# Start data fetch in background
bash "${SCRIPT_DIR}/fetch-e2e-data.sh" "$@" > /tmp/e2e_data_${PR_NUM}.json 2>&1 &
DATA_PID=$!

# Wait for completion
wait $DATA_PID
DATA=$(cat /tmp/e2e_data_${PR_NUM}.json)
rm -f /tmp/e2e_data_${PR_NUM}.json

# Parse and display
REPO=$(echo "$DATA" | jq -r '.repo')
PR_NUMBER=$(echo "$DATA" | jq -r '.pr_number')
ERROR=$(echo "$DATA" | jq -r '.error // empty')

# Check if PR is not open
if [ -n "$ERROR" ] && [ "$ERROR" = "PR is not open" ]; then
  PR_STATE=$(echo "$DATA" | jq -r '.state')
  echo "Repository: $REPO"
  echo "PR #$PR_NUMBER is $PR_STATE (not open)"
  exit 0
fi

FAILED_COUNT=$(echo "$DATA" | jq '.failed_jobs | length')
RUNNING_COUNT=$(echo "$DATA" | jq '.running_jobs | length')

echo "Repository: $REPO"
echo ""

if [ "$FAILED_COUNT" -gt 0 ]; then
  echo "Failed e2e jobs:"
  echo "$DATA" | jq -r '.failed_jobs[] | "  ❌ \(.name)\n     Consecutive failures: \(.consecutive)\n     Recent history: \(.fail) fail / \(.pass) pass / \(.abort) abort"'
  echo ""
fi

if [ "$RUNNING_COUNT" -gt 0 ]; then
  echo "⏳ Currently running ($RUNNING_COUNT jobs):"
  echo "$DATA" | jq -r '.running_jobs[] | "  • \(.)"'
  echo ""
fi

# Store data for later use
echo "$DATA" > /tmp/e2e_final_data_${PR_NUM}.json
```

**AFTER BASH EXECUTION:**
- If you see "Repository:" and job lists in the output above, that means SUCCESS
- DO NOT say "there's an issue" - there is NO issue
- DO NOT debug or re-run anything
- IMMEDIATELY proceed to the next step below

Check if there are failed jobs:

```bash
# Extract PR number from arguments
if [ $# -eq 1 ]; then PR_NUM="$1"; else PR_NUM="$2"; fi
FAILED_COUNT=$(cat /tmp/e2e_final_data_${PR_NUM}.json | jq '.failed_jobs | length')
```

If `FAILED_COUNT > 0`, use AskUserQuestion to present these options:
1. Retest selected
2. Retest all failed
3. Use /retest
4. Just show list

Then based on the user's choice:

**Option 1 - Retest selected**: Ask user for job numbers, then:
```bash
# Extract PR number from arguments
if [ $# -eq 1 ]; then PR_NUM="$1"; else PR_NUM="$2"; fi
DATA=$(cat /tmp/e2e_final_data_${PR_NUM}.json)
REPO=$(echo "$DATA" | jq -r '.repo')
PR_NUMBER=$(echo "$DATA" | jq -r '.pr_number')

# User provides job numbers like "1 3 5"
# Build comment with selected jobs
COMMENT=""
for num in $USER_SELECTION; do
  JOB=$(echo "$DATA" | jq -r ".failed_jobs[$((num-1))].name")
  if [ -n "$JOB" ] && [ "$JOB" != "null" ]; then
    COMMENT="${COMMENT}/test ${JOB}"$'\n'
  fi
done

gh pr comment ${PR_NUMBER} --repo ${REPO} --body "$COMMENT"
rm -f /tmp/e2e_final_data_${PR_NUM}.json
```

**Option 2 - Retest all failed**:
```bash
# Extract PR number from arguments
if [ $# -eq 1 ]; then PR_NUM="$1"; else PR_NUM="$2"; fi
DATA=$(cat /tmp/e2e_final_data_${PR_NUM}.json)
REPO=$(echo "$DATA" | jq -r '.repo')
PR_NUMBER=$(echo "$DATA" | jq -r '.pr_number')

COMMENT=$(echo "$DATA" | jq -r '.failed_jobs[] | "/test \(.name)"' | paste -sd '\n')
gh pr comment ${PR_NUMBER} --repo ${REPO} --body "$COMMENT"
rm -f /tmp/e2e_final_data_${PR_NUM}.json
```

**Option 3 - Use /retest**:
```bash
# Extract PR number from arguments
if [ $# -eq 1 ]; then PR_NUM="$1"; else PR_NUM="$2"; fi
DATA=$(cat /tmp/e2e_final_data_${PR_NUM}.json)
REPO=$(echo "$DATA" | jq -r '.repo')
PR_NUMBER=$(echo "$DATA" | jq -r '.pr_number')

gh pr comment ${PR_NUMBER} --repo ${REPO} --body "/retest"
rm -f /tmp/e2e_final_data_${PR_NUM}.json
```

**Option 4 - Just show list**:
```bash
# Extract PR number from arguments
if [ $# -eq 1 ]; then PR_NUM="$1"; else PR_NUM="$2"; fi
rm -f /tmp/e2e_final_data_${PR_NUM}.json
```

## Example Commands

### Parsing Failed Jobs

```bash
# Get failed e2e jobs from PR status
gh pr view ${PR_NUMBER} --repo ${REPO} --json statusCheckRollup | \
  jq -r '.statusCheckRollup[] |
    select(.state == "FAILURE" or .state == "ERROR") |
    select(.context | test("ci/prow/.*e2e")) |
    .context | sub("ci/prow/"; "")'
```

### Counting Consecutive Failures

```bash
# For a specific job, extract its run history from prow HTML
JOB_NAME="pull-ci-openshift-ovn-kubernetes-master-e2e-aws-ovn"
grep -A 10 ">${JOB_NAME}<" /tmp/prow_history.html | \
  grep -oE 'run-(success|failure|aborted)' | \
  head -10
```

### Posting Retest Comment

```bash
# Post single comment with multiple /test commands
gh pr comment ${PR_NUMBER} --repo ${REPO} --body "/test e2e-aws-ovn
/test e2e-gcp-ovn"
```

## Return Value

The command displays:
- Repository name
- Summary of failed e2e jobs with consecutive failure counts and recent history statistics
- List of currently running jobs (if any)
- Interactive options to retest selected or all jobs
- Confirmation of posted retest comments

## Examples

1. **Auto-detect repo from current directory**:
   ```
   cd ~/repos/ovn-kubernetes
   /ci:e2e-retest 2782
   ```
   Output: `Repository: openshift/ovn-kubernetes`

2. **Specify repo name only (assumes openshift org)**:
   ```
   /ci:e2e-retest ovn-kubernetes 2782
   ```

3. **Specify full org/repo**:
   ```
   /ci:e2e-retest openshift/origin 5432
   ```

4. **Non-OpenShift repository**:
   ```
   /ci:e2e-retest kubernetes/kubernetes 12345
   ```

## Arguments
- **$1**: Repository specification (optional) OR PR number (required if repo omitted)
  - Omit to auto-detect from current directory's git remote
  - Repo name only (e.g., `ovn-kubernetes`) assumes `openshift/` org
  - Full format (e.g., `openshift/origin` or `kubernetes/kubernetes`)
- **$2**: Pull request number (required, last argument)
  - Example: `2782`

## Notes

- **PR State Check**: Exits immediately if PR is not OPEN (merged, closed, etc.)
- **Running Jobs**: Automatically excluded from retest lists (shown separately for visibility)
- **Consecutive Failures**: Counted by parsing prow history table (newest runs first)
- **Comment Format**: Multiple `/test` commands in a single comment
- **Fast Execution**: Parallel fetching of PR status and prow history
- **Accurate Parsing**: Robust HTML table parsing for failure statistics
