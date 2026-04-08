---
name: Phase Merge
description: Monitor PR merge and track deployment to payloads (Phase 6 of SDLC orchestrator)
---

# Phase Merge

This skill implements Phase 6 of the SDLC orchestrator: Merge & Deployment Tracking. It monitors PR merge status and tracks commit inclusion in OpenShift payloads.

## Prerequisites

1. **Required Skill Loaded**: `sdlc-state-yaml` must be loaded
2. **Phase 5 Complete**: PR creation phase must be completed
3. **GitHub CLI**: `gh` command must be available
4. **CI Plugin**: `/ci:fetch-payloads` skill must be available for OpenShift payload tracking

## Inputs

Read from state file:
- `metadata.jira_key`: Jira issue key
- `metadata.mode`: Orchestration mode
- `phases.pr_review.outputs.pr_number`: PR number
- `phases.pr_review.outputs.pr_url`: PR URL
- `phases.implementation.outputs.branch_name`: Feature branch name

## Outputs

Written to state file:
- `phases.merge.outputs.merge_sha`: Merge commit SHA
- `phases.merge.outputs.merge_timestamp`: When PR was merged
- `phases.merge.outputs.merged_by`: Who merged the PR
- `phases.merge.outputs.first_payload`: First payload containing the commit
- `phases.merge.outputs.payload_status`: Payload status (accepted/rejected/pending)
- `phases.merge.verification_gates[]`: Verification gate statuses

## Implementation Steps

### Step 1: Update State - Phase Start

1. Read state file
2. Update state using "Update Phase Start" operation:
   - `current_phase.name`: `"merge"`
   - `current_phase.status`: `"in_progress"`
   - `phases.merge.status`: `"in_progress"`
   - `phases.merge.started_at`: Current timestamp
3. Write state file

### Step 2: Check PR Status

Check current PR status:

1. Get PR details:
   ```bash
   gh pr view {pr_number} --json state,merged,mergedAt,mergedBy,mergeCommit
   ```

2. Parse response:
   - `state`: "OPEN", "CLOSED", "MERGED"
   - `merged`: true/false
   - `mergedAt`: Timestamp (if merged)
   - `mergedBy.login`: Username who merged
   - `mergeCommit.oid`: Merge commit SHA

3. Handle different states:

   **If state == "MERGED"**:
   - PR is already merged
   - Extract merge details
   - Skip to Step 4 (Track Payload)

   **If state == "OPEN"**:
   - PR is still open, waiting for merge
   - Continue to Step 3 (Wait for Merge)

   **If state == "CLOSED" and not merged**:
   - PR was closed without merging
   - Append error to state
   - Update phase status to `"failed"`
   - Update `resumability.can_resume: false`
   - Exit with error: "PR was closed without merging"

### Step 3: Wait for PR Merge (if not merged)

If PR is still open:

**In interactive mode:**

1. Display status:
   ```
   ━━━ Phase 6/7: Merge & Deployment Tracking ━━━

   PR Status: Open
   PR URL: {pr_url}

   Waiting for PR to be merged...
   ```

2. Ask user for action:
   - **"wait"**: Poll PR status every minute until merged
   - **"pause"**: Save state and exit (can resume later with `--resume`)
   - **"skip"**: Mark phase as "blocked", proceed to completion without merge tracking
   - **"check"**: Check PR status now

3. If "wait" selected:
   - Poll PR status every 60 seconds:
     ```bash
     while true; do
       gh pr view {pr_number} --json merged
       if merged; then break; fi
       sleep 60
     done
     ```
   - Update state periodically (every 5 minutes) to show still waiting
   - When merged, proceed to Step 4

4. If "pause" selected:
   - Update `resumability.manual_intervention_required: true`
   - Update current_phase.status to `"blocked"`
   - Write state and exit

**In automation mode:**

1. Check PR status once
2. If not merged:
   - Update phase status to `"blocked"`
   - Update `resumability.manual_intervention_required: true`
   - Log: "PR is not yet merged. Resume orchestration with --resume after merge."
   - Write state and exit

### Step 4: Record Merge Details

Once PR is merged:

1. Get merge details:
   ```bash
   gh pr view {pr_number} --json mergedAt,mergedBy,mergeCommit
   ```

2. Extract:
   - `merge_sha`: Commit SHA of merge
   - `merge_timestamp`: When merged
   - `merged_by`: Username who merged

3. Update state with merge details:
   ```yaml
   outputs:
     merge_sha: "{merge_commit_sha}"
     merge_timestamp: "{merged_at}"
     merged_by: "{merged_by_login}"
   ```

4. Update verification gate:
   ```yaml
   - gate: "pr_merged"
     status: "passed"
     timestamp: "{timestamp}"
   ```

### Step 5: Track Payload Inclusion (OpenShift-specific)

Track when the merge commit appears in OpenShift payloads:

**Detect if repository is OpenShift-related:**

1. Check git remote URL:
   ```bash
   git remote get-url origin
   ```
2. If contains "github.com/openshift/":
   - Continue with payload tracking
3. If not OpenShift repository:
   - Skip payload tracking
   - Mark gate as "skipped"
   - Proceed to Step 6

**For OpenShift repositories:**

1. **Determine OCP version** from repository:
   - Check for `VERSION` file
   - Check for version in `Makefile` or CI config
   - Default to latest supported version (e.g., "4.22")

2. **Invoke `/ci:fetch-payloads` skill**:
   ```
   skill: "ci:fetch-payloads"
   args: "{architecture} {version} nightly --limit 20"
   ```
   - Use architecture: "amd64" (default)
   - Use detected version
   - Fetch recent nightly payloads

3. **Search for merge commit in payloads**:
   - Parse payload output
   - For each payload, check if it contains the merge SHA
   - Find first payload containing the commit

4. **If commit found in payload**:
   - Record payload tag
   - Check payload status (Accepted, Rejected, Ready)
   - Update state:
     ```yaml
     first_payload: "{payload_tag}"
     payload_status: "{status}"
     ```

5. **If commit not yet in any payload**:
   - Log: "Merge commit not yet in a payload"
   - In interactive mode:
     - Ask: "Wait for commit to appear in payload? (yes/no/pause)"
     - If yes: Poll every 5 minutes for up to 1 hour
     - If no: Mark as "pending", proceed
     - If pause: Save state and exit
   - In automation mode:
     - Mark payload_status as "pending"
     - Proceed (can be checked later)

6. **Monitor payload status** (if found):
   - If payload status is "Rejected":
     - Check if this PR was flagged as cause using `/ci:analyze-payload`
     - Log warning if PR is suspected cause
     - Note in state
   - If payload status is "Accepted":
     - Success! Deployment verified
   - If payload status is "Ready":
     - Payload is in progress
     - Mark as "pending"

### Step 6: Verify Merge Gates

Run verification gates:

**Gate 1: PR Merged**

```yaml
- gate: "pr_merged"
  status: "passed"
  timestamp: "{timestamp}"
```

**Gate 2: Merge Commit Identified**

```yaml
- gate: "merge_commit_identified"
  status: "passed"
  timestamp: "{timestamp}"
```

**Gate 3: Payload Tracking** (OpenShift repos only)

```yaml
- gate: "payload_tracking"
  status: "passed"  # or "skipped" for non-OpenShift repos
  timestamp: "{timestamp}"
```

**Gate 4: Deployment Verified** (if payload accepted)

```yaml
- gate: "deployment_verified"
  status: "passed"  # or "pending" if not yet accepted
  timestamp: "{timestamp}"
```

### Step 7: Update State - Phase Complete

1. Read current state
2. Update state with outputs:
   ```yaml
   phases:
     merge:
       status: "completed"
       completed_at: "{timestamp}"
       outputs:
         merge_sha: "{merge_commit_sha}"
         merge_timestamp: "{merged_at}"
         merged_by: "{username}"
         first_payload: "{payload_tag}"  # or "" if not tracked
         payload_status: "accepted"  # or "rejected"/"pending"/"not_tracked"
         payload_url: "{release_controller_url}"  # if tracked
       verification_gates: [{gates array}]
   ```
3. Update `resumability.resume_from_phase`: `"completion"`
4. Write state file

### Step 8: Display Summary

```
━━━ Phase 6/7: Merge & Deployment Tracking ━━━ COMPLETE

✓ PR merged successfully
✓ Merge SHA: {merge_sha}
✓ Merged by: @{merged_by}
✓ Merged at: {merge_timestamp}

{If OpenShift repo and payload tracked:}
✓ First payload: {first_payload}
✓ Payload status: {payload_status}
{If payload rejected:}
⚠ WARNING: Payload was rejected. Check if this PR was the cause.

Next phase: Completion & Verification
```

## Error Handling

### PR Closed Without Merge

If PR is closed but not merged:

1. Append error:
   ```yaml
   errors:
     - phase: "merge"
       error_type: "pr_closed_without_merge"
       message: "PR #{pr_number} was closed without merging"
       resolved: false
   ```
2. Update phase status to `"failed"`
3. Update `resumability.can_resume: false`
4. Exit with error

### Merge Commit Not Found

If unable to identify merge commit:

1. Try alternative methods:
   - Check branch history: `git log origin/main --grep="{pr_number}"`
   - Check PR description for merge SHA
2. If still not found:
   - Log warning
   - Proceed without merge SHA (mark as unknown)

### Payload Tracking Fails

If `/ci:fetch-payloads` skill fails:

1. Log warning
2. Skip payload tracking
3. Mark payload-related gates as "skipped"
4. Proceed to completion phase

### Payload Rejected with This PR as Cause

If payload is rejected and this PR is identified as cause:

1. Log high-priority warning
2. Add to state:
   ```yaml
   payload_rejection:
     suspected_cause: true
     payload_tag: "{payload_tag}"
     analysis_url: "{link_to_analysis}"
   ```
3. In interactive mode:
   - Alert user: "⚠️ Payload was rejected and this PR may be the cause!"
   - Ask: "Would you like to: (1) View analysis, (2) Open revert PR, (3) Continue"
4. In automation mode:
   - Log error
   - Note in state
   - Proceed (human review required)

### Timeout Waiting for Merge

If polling for merge times out (e.g., 24 hours):

1. Update phase status to `"blocked"`
2. Update `resumability.manual_intervention_required: true`
3. Log: "Timed out waiting for PR merge. Resume with --resume after PR is merged."
4. Write state and exit

## Success Criteria

Phase 6 is successful when:

- ✅ PR merged to target branch
- ✅ Merge commit identified
- ✅ Merge details recorded (SHA, timestamp, user)
- ✅ Payload tracking attempted (OpenShift repos)
- ✅ Payload status recorded (if tracked)
- ✅ State file updated with merge and deployment details

## See Also

- Related Skill: `/ci:fetch-payloads` — fetches OpenShift payloads
- Related Skill: `/ci:analyze-payload` — analyzes payload failures
- Related Skill: `sdlc-state-yaml` — state schema and operations
- Previous Phase: `phase-pr-review` — creates pull request
- Next Phase: `phase-completion` — updates Jira and generates report
