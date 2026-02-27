---
description: Find and retest failed payload jobs on a PR
argument-hint: "[repo] <pr-number>"
---

## Name
ci:payload-retest

## Synopsis
```
/ci:payload-retest [repo] <pr-number>
```

Alternative forms:
```
/ci:payload-retest <pr-number>
/ci:payload-retest <repo> <pr-number>
/ci:payload-retest <org>/<repo> <pr-number>
```

## Description
Analyzes a pull request to find failed payload jobs from the most recent `/payload` run, showing job statistics and providing interactive options to retest them.

Payload jobs are OpenShift-specific CI jobs that test PRs against release payloads. This command:
1. Searches PR comments for payload run URLs
2. Identifies the most recent payload run by Created timestamp
3. Parses failed and running jobs from that run
4. Provides interactive retest options

The repository can be specified in multiple ways:
- **Omit repo argument**: Auto-detect from current directory's git remote
- **Repo name only**: Assumes `openshift/<repo>` (e.g., `ovn-kubernetes` → `openshift/ovn-kubernetes`)
- **Full org/repo**: Use any GitHub repository (e.g., `openshift/origin`)

**Note:** Payload jobs are optional and may not exist for all PRs. The command will gracefully exit if no payload runs are found.

## Implementation

**CRITICAL INSTRUCTIONS - READ FIRST:**
1. DO NOT output any text to the user
2. DO NOT explain what you are doing
3. DO NOT say "I'll execute" or similar
4. IMMEDIATELY execute the bash block below with NO preamble

Execute the entire workflow in a single bash invocation:

```bash
# Use relative path from working directory
SCRIPT_DIR="plugins/ci/skills/payload-retest"

# Extract PR number from arguments for temp file naming
if [ $# -eq 1 ]; then
  PR_NUM="$1"
else
  PR_NUM="$2"
fi

# Start data fetch in background
bash "${SCRIPT_DIR}/fetch-payload-data.sh" "$@" > /tmp/payload_data_${PR_NUM}.json 2>&1 &
DATA_PID=$!

# Wait for completion
wait $DATA_PID
DATA=$(cat /tmp/payload_data_${PR_NUM}.json)
rm -f /tmp/payload_data_${PR_NUM}.json

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

PAYLOAD_RUNS=$(echo "$DATA" | jq -r '.payload_runs')
FAILED_COUNT=$(echo "$DATA" | jq '.failed_jobs | length')
RUNNING_COUNT=$(echo "$DATA" | jq '.running_jobs | length')

# Exit if no payload runs
if [ "$PAYLOAD_RUNS" -eq 0 ]; then
  echo "No payload runs found for this PR"
  exit 0
fi

echo "Repository: $REPO"
echo "Found $PAYLOAD_RUNS payload run(s)"
echo ""

if [ "$FAILED_COUNT" -gt 0 ]; then
  echo "Failed payload jobs:"
  echo "$DATA" | jq -r '.failed_jobs[] | "  ❌ \(.name)\n     Consecutive failures: \(.consecutive)"'
  echo ""
fi

if [ "$RUNNING_COUNT" -gt 0 ]; then
  echo "⏳ Currently running ($RUNNING_COUNT jobs):"
  echo "$DATA" | jq -r '.running_jobs[] | "  • \(.)"'
  echo ""
fi

# Store data for later use
echo "$DATA" > /tmp/payload_final_data_${PR_NUM}.json
```

**AFTER BASH EXECUTION:**
- If you see "Repository:" and job lists (or "No payload runs") in the output above, that means SUCCESS
- DO NOT say "there's an issue" - there is NO issue
- DO NOT debug or re-run anything
- IMMEDIATELY proceed to the next step below

Check if there are failed jobs:

```bash
# Extract PR number from arguments
if [ $# -eq 1 ]; then PR_NUM="$1"; else PR_NUM="$2"; fi
FAILED_COUNT=$(cat /tmp/payload_final_data_${PR_NUM}.json | jq '.failed_jobs | length')
```

If `FAILED_COUNT > 0`, use AskUserQuestion to present these options:
1. Retest selected
2. Retest all failed
3. Just show list

Then based on the user's choice:

**Option 1 - Retest selected**: Ask user for job numbers, then:
```bash
# Extract PR number from arguments
if [ $# -eq 1 ]; then PR_NUM="$1"; else PR_NUM="$2"; fi
DATA=$(cat /tmp/payload_final_data_${PR_NUM}.json)
REPO=$(echo "$DATA" | jq -r '.repo')
PR_NUMBER=$(echo "$DATA" | jq -r '.pr_number')

# User provides job numbers like "1 3 5"
# Build comment with selected jobs
COMMENT=""
for num in $USER_SELECTION; do
  JOB=$(echo "$DATA" | jq -r ".failed_jobs[$((num-1))].name")
  if [ -n "$JOB" ] && [ "$JOB" != "null" ]; then
    COMMENT="${COMMENT}/payload-job ${JOB}"$'\n'
  fi
done

gh pr comment ${PR_NUMBER} --repo ${REPO} --body "$COMMENT"
rm -f /tmp/payload_final_data_${PR_NUM}.json
```

**Option 2 - Retest all failed**:
```bash
# Extract PR number from arguments
if [ $# -eq 1 ]; then PR_NUM="$1"; else PR_NUM="$2"; fi
DATA=$(cat /tmp/payload_final_data_${PR_NUM}.json)
REPO=$(echo "$DATA" | jq -r '.repo')
PR_NUMBER=$(echo "$DATA" | jq -r '.pr_number')

COMMENT=$(echo "$DATA" | jq -r '.failed_jobs[] | "/payload-job \(.name)"' | paste -sd '\n')
gh pr comment ${PR_NUMBER} --repo ${REPO} --body "$COMMENT"
rm -f /tmp/payload_final_data_${PR_NUM}.json
```

**Option 3 - Just show list**:
```bash
# Extract PR number from arguments
if [ $# -eq 1 ]; then PR_NUM="$1"; else PR_NUM="$2"; fi
rm -f /tmp/payload_final_data_${PR_NUM}.json
```

## Example Commands

### Finding Payload URLs

```bash
# Extract payload URLs from PR comments
gh pr view ${PR_NUMBER} --repo ${REPO} --json comments | \
  jq -r '.comments[].body' | \
  grep -oE 'https://pr-payload-tests[^ )]+' | \
  sort -u
```

### Finding Most Recent Run

```bash
# For each URL, extract Created timestamp and sort
for url in $(payload_urls); do
  timestamp=$(curl -sL "$url" | grep -E 'Created:' | sed -E 's/.*Created: ([^<]+).*/\1/')
  echo "$timestamp|$url"
done | sort | tail -1
```

### Parsing Job Results

```bash
# Failed jobs (text-danger class)
curl -sL '<payload-url>' | \
  grep -oE '<span class="text-danger">[^<]+</span>' | \
  sed -E 's/<span class="text-danger">([^<]+)<\/span>/\1/'

# Running jobs (empty class attribute)
curl -sL '<payload-url>' | \
  grep -oE '<span class="">[^<]+</span>' | \
  sed -E 's/<span class="">([^<]+)<\/span>/\1/'
```

### Posting Retest Comment

```bash
# Post /payload-job commands
gh pr comment ${PR_NUMBER} --repo ${REPO} --body "/payload-job <full-job-name>"
```

## Return Value

The command displays:
- Repository name
- Number of payload runs found
- Most recent payload run URL and timestamp
- Summary of failed payload jobs (if any)
- List of currently running jobs (if any)
- Interactive options to retest selected or all jobs
- Confirmation of posted retest comments

## Examples

1. **Auto-detect repo from current directory**:
   ```
   cd ~/repos/ovn-kubernetes
   /ci:payload-retest 2782
   ```
   Output: `Repository: openshift/ovn-kubernetes`

2. **Specify repo name only (assumes openshift org)**:
   ```
   /ci:payload-retest ovn-kubernetes 2782
   ```

3. **Specify full org/repo**:
   ```
   /ci:payload-retest openshift/origin 5432
   ```

## Arguments
- **$1**: Repository specification (optional) OR PR number (required if repo omitted)
  - Omit to auto-detect from current directory's git remote
  - Repo name only (e.g., `ovn-kubernetes`) assumes `openshift/` org
  - Full format (e.g., `openshift/origin`)
- **$2**: Pull request number (required, last argument)
  - Example: `2782`

## Notes

- **PR State Check**: Exits immediately if PR is not OPEN (merged, closed, etc.)
- **Payload Jobs**: Optional feature - gracefully exits if not present
- **All Runs Analyzed**: Analyzes ALL payload runs to track job history across runs
- **Running Jobs**: Shown separately, not offered for retest
- **Comment Format**: Multiple `/payload-job` commands in a single comment
- **Fast Execution**: Parallel fetching of all payload run pages
- **Minimal Claude Overhead**: Data fetching in bash, interaction via AskUserQuestion
