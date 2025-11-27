---
description: Find and retest failed e2e CI jobs and payload jobs on a PR
argument-hint: "[repo] <pr-number>"
---

## Name
ci:pr-retest

## Synopsis
```
/ci:pr-retest <pr-number>
/ci:pr-retest <repo> <pr-number>
/ci:pr-retest <org>/<repo> <pr-number>
```

## Description
Analyzes a pull request to find all failed e2e CI jobs and payload jobs, providing detailed failure statistics and interactive options to retest them. This command combines both e2e and payload job analysis into a single workflow:

1. **E2E Jobs Analysis**:
   - Identifies failed e2e jobs from PR status checks
   - Counts consecutive failures from prow history
   - Shows recent statistics (fail/pass/abort counts)
   - Provides interactive retest options

2. **Payload Jobs Analysis**:
   - Searches for all payload run URLs in PR comments
   - Analyzes all runs to track job history
   - Counts consecutive failures across multiple runs
   - Provides interactive retest options

The repository can be specified in multiple ways:
- **Omit repo argument**: Auto-detect from current directory's git remote
- **Repo name only**: Assumes `openshift/<repo>` (e.g., `ovn-kubernetes` → `openshift/ovn-kubernetes`)
- **Full org/repo**: Use any GitHub repository (e.g., `openshift/origin`, `kubernetes/kubernetes`)

**Note:** This command runs both `/ci:e2e-retest` and `/ci:payload-retest` sequentially. For faster, focused analysis, use those individual commands.

## Implementation

**CRITICAL INSTRUCTIONS - READ FIRST:**
1. DO NOT output any text to the user
2. DO NOT explain what you are doing
3. DO NOT say "I'll execute" or similar
4. IMMEDIATELY execute the bash block below with NO preamble

Execute the entire workflow in a single bash invocation:

```bash
# Use relative path from working directory
SCRIPT_DIR="plugins/ci/skills"

# Extract PR number from arguments for temp file naming
if [ $# -eq 1 ]; then
  PR_NUM="$1"
else
  PR_NUM="$2"
fi

# Start BOTH data fetches in background simultaneously
bash "${SCRIPT_DIR}/e2e-retest/fetch-e2e-data.sh" "$@" > /tmp/e2e_data_${PR_NUM}.json 2>&1 &
E2E_PID=$!
bash "${SCRIPT_DIR}/payload-retest/fetch-payload-data.sh" "$@" > /tmp/payload_data_${PR_NUM}.json 2>&1 &
PAYLOAD_PID=$!

# Wait for both to complete
wait $E2E_PID
wait $PAYLOAD_PID

# Read both results
E2E_DATA=$(cat /tmp/e2e_data_${PR_NUM}.json)
PAYLOAD_DATA=$(cat /tmp/payload_data_${PR_NUM}.json)
rm -f /tmp/e2e_data_${PR_NUM}.json /tmp/payload_data_${PR_NUM}.json

# Check if PR is open
ERROR=$(echo "$E2E_DATA" | jq -r '.error // empty')
if [ -n "$ERROR" ] && [ "$ERROR" = "PR is not open" ]; then
  REPO=$(echo "$E2E_DATA" | jq -r '.repo')
  PR_NUMBER=$(echo "$E2E_DATA" | jq -r '.pr_number')
  PR_STATE=$(echo "$E2E_DATA" | jq -r '.state')
  echo "Repository: $REPO"
  echo "PR #$PR_NUMBER is $PR_STATE (not open)"
  exit 0
fi

# Parse data
REPO=$(echo "$E2E_DATA" | jq -r '.repo')
PR_NUMBER=$(echo "$E2E_DATA" | jq -r '.pr_number')
E2E_FAILED=$(echo "$E2E_DATA" | jq '.failed_jobs | length')
E2E_RUNNING=$(echo "$E2E_DATA" | jq '.running_jobs | length')
PAYLOAD_RUNS=$(echo "$PAYLOAD_DATA" | jq -r '.payload_runs')
PAYLOAD_FAILED=$(echo "$PAYLOAD_DATA" | jq '.failed_jobs | length')
PAYLOAD_RUNNING=$(echo "$PAYLOAD_DATA" | jq '.running_jobs | length')

# Display E2E results
echo "========================================="
echo "E2E JOBS"
echo "========================================="
echo ""
echo "Repository: $REPO"
echo ""

if [ "$E2E_FAILED" -gt 0 ]; then
  echo "Failed e2e jobs:"
  echo "$E2E_DATA" | jq -r '.failed_jobs[] | "  ❌ \(.name)\n     Consecutive failures: \(.consecutive)\n     Recent history: \(.fail) fail / \(.pass) pass / \(.abort) abort"'
  echo ""
fi

if [ "$E2E_RUNNING" -gt 0 ]; then
  echo "⏳ Currently running ($E2E_RUNNING jobs):"
  echo "$E2E_DATA" | jq -r '.running_jobs[] | "  • \(.)"'
  echo ""
fi

# Display Payload results
echo "========================================="
echo "PAYLOAD JOBS"
echo "========================================="
echo ""

if [ "$PAYLOAD_RUNS" -eq 0 ]; then
  echo "No payload runs found for this PR"
else
  echo "Found $PAYLOAD_RUNS payload run(s)"
  echo ""

  if [ "$PAYLOAD_FAILED" -gt 0 ]; then
    echo "Failed payload jobs:"
    echo "$PAYLOAD_DATA" | jq -r '.failed_jobs[] | "  ❌ \(.name)\n     Consecutive failures: \(.consecutive)"'
    echo ""
  fi

  if [ "$PAYLOAD_RUNNING" -gt 0 ]; then
    echo "⏳ Currently running ($PAYLOAD_RUNNING jobs):"
    echo "$PAYLOAD_DATA" | jq -r '.running_jobs[] | "  • \(.)"'
    echo ""
  fi
fi

# Store data for later use
echo "$E2E_DATA" > /tmp/e2e_final_data_${PR_NUM}.json
echo "$PAYLOAD_DATA" > /tmp/payload_final_data_${PR_NUM}.json
```

**AFTER BASH EXECUTION:**
- If you see "E2E JOBS" and "PAYLOAD JOBS" sections in the output above, that means SUCCESS
- DO NOT say "there's an issue" - there is NO issue
- DO NOT debug or re-run anything
- IMMEDIATELY proceed to the next step below

Check if there are failed jobs:

```bash
# Extract PR number from arguments
if [ $# -eq 1 ]; then PR_NUM="$1"; else PR_NUM="$2"; fi

E2E_FAILED=$(cat /tmp/e2e_final_data_${PR_NUM}.json | jq '.failed_jobs | length')
PAYLOAD_FAILED=$(cat /tmp/payload_final_data_${PR_NUM}.json | jq '.failed_jobs | length')
```

**If E2E_FAILED > 0**: Use AskUserQuestion with these options for e2e jobs:
1. Retest selected jobs
2. Retest all failed
3. Use /retest
4. Just show list

Then execute the appropriate action using the data from `/tmp/e2e_final_data_${PR_NUM}.json`.

**If PAYLOAD_FAILED > 0**: Use AskUserQuestion with these options for payload jobs:
1. Retest selected jobs
2. Retest all failed
3. Just show list

Then execute the appropriate action using the data from `/tmp/payload_final_data_${PR_NUM}.json`.

**Always clean up** at the end:
```bash
# Extract PR number from arguments
if [ $# -eq 1 ]; then PR_NUM="$1"; else PR_NUM="$2"; fi
rm -f /tmp/e2e_final_data_${PR_NUM}.json /tmp/payload_final_data_${PR_NUM}.json
```

## Example Commands

### E2E Jobs

Fetch currently failing e2e jobs (excluding running ones):
```bash
# Get failed jobs (excluding PENDING)
gh pr view ${PR_NUMBER} --repo ${REPO} --json statusCheckRollup | \
  jq -r '.statusCheckRollup[] |
    select(.state == "FAILURE" or .state == "ERROR") |
    select(.context | test("ci/prow/.*e2e")) |
    .context | sub("ci/prow/"; "")'

# Get currently running jobs
gh pr view ${PR_NUMBER} --repo ${REPO} --json statusCheckRollup | \
  jq -r '.statusCheckRollup[] |
    select(.state == "PENDING") |
    select(.context | test("ci/prow/.*e2e")) |
    .context | sub("ci/prow/"; "")'
```

Parse prow history for consecutive failures:
```bash
curl -sL "https://prow.ci.openshift.org/pr-history?org=${ORG}&repo=${REPO_NAME}&pr=${PR_NUMBER}" | \
  grep -E 'job-history.*e2e|run-(success|failure|aborted)'
```

Post e2e retest comment:
```bash
gh pr comment ${PR_NUMBER} --repo ${REPO} --body "/test <job-name>"
```

### Payload Jobs

Extract payload run URLs from comments:
```bash
# Extract all payload URLs from PR comments
gh pr view ${PR_NUMBER} --repo ${REPO} --json comments | \
  jq -r '.comments[].body' | \
  grep -oE 'https://pr-payload-tests[^ )]+' | \
  sort -u
```

Find the most recent payload run by Created timestamp:
```bash
# For each URL, fetch its Created timestamp and find the most recent
for url in $(gh pr view ${PR_NUMBER} --repo ${REPO} --json comments | \
             jq -r '.comments[].body' | \
             grep -oE 'https://pr-payload-tests[^ )+' | \
             sort -u); do
  timestamp=$(curl -sL "$url" | grep -E 'Created:' | sed -E 's/.*Created: ([^<]+).*/\1/')
  echo "$timestamp|$url"
done | sort | tail -1 | cut -d'|' -f2
```

Parse payload run results (only completed jobs with success/danger classes):
```bash
# This grep filters for only text-success and text-danger, automatically excluding running jobs (plain text)
curl -sL '<payload-run-url>' | \
  grep -E 'text-(success|danger)' | \
  sed -E 's/.*<span class="text-(success|danger)">(.*)<\/span>.*/\2|\1/'
```

Post payload retest comment:
```bash
gh pr comment ${PR_NUMBER} --repo ${REPO} --body "/payload-job <full-job-name>"
```

## Return Value

The command displays:
- **E2E Jobs Section**:
  - Repository name
  - Failed e2e jobs with consecutive failure counts and recent history
  - Currently running jobs (if any)
  - Interactive menu for retest options
  - Confirmation of posted retest comments
- **Payload Jobs Section**:
  - Number of payload runs found
  - Failed payload jobs with consecutive failure counts
  - Currently running jobs (if any)
  - Interactive menu for retest options
  - Confirmation of posted retest comments

## Examples

1. **Auto-detect repo from current directory**:
   ```
   cd ~/repos/ovn-kubernetes
   /ci:pr-retest 2838
   ```
   Output: `ℹ️  Auto-detected repository: openshift/ovn-kubernetes`

2. **Specify repo name only (assumes openshift org)**:
   ```
   /ci:pr-retest ovn-kubernetes 2838
   ```
   Output: `ℹ️  Using repository: openshift/ovn-kubernetes`

3. **Specify full org/repo**:
   ```
   /ci:pr-retest openshift/origin 5432
   ```
   Output: `ℹ️  Using repository: openshift/origin`

4. **Non-OpenShift repository**:
   ```
   /ci:pr-retest kubernetes/kubernetes 12345
   ```
   Output: `ℹ️  Using repository: kubernetes/kubernetes`

## Arguments
- **$1**: Repository specification (optional) OR PR number (required if repo omitted)
  - Omit to auto-detect from current directory's git remote
  - Repo name only (e.g., `ovn-kubernetes`) assumes `openshift/` org
  - Full format (e.g., `openshift/origin` or `kubernetes/kubernetes`)
- **$2**: Pull request number (required, last argument)
  - Example: `2838`

## Notes

- **PR State Check**: Exits immediately if PR is not OPEN (merged, closed, etc.)
- **Two-Part Analysis**: Runs e2e analysis first, then payload analysis
- **E2E Jobs**: Always analyzed for all repositories
- **Payload Jobs**: Optional feature - gracefully skipped if not present
- **Running Jobs**: Automatically excluded from retest lists (shown separately for visibility)
- **Consecutive Failures**:
  - E2E: Counted from prow history (last 10 runs)
  - Payload: Counted across ALL payload run URLs found in PR comments
- **Comment Format**: Multiple `/test` or `/payload-job` commands in a single comment
- **Performance**: Minimal Claude overhead - data fetching in bash, interaction via AskUserQuestion
- **Individual Commands**: For faster analysis of just e2e or just payload, use `/ci:e2e-retest` or `/ci:payload-retest`
