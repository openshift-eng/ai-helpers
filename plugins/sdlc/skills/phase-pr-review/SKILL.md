---
name: Phase PR Review
description: Create pull request with comprehensive description and track review status (Phase 5 of SDLC orchestrator)
---

# Phase PR Review

This skill implements Phase 5 of the SDLC orchestrator: PR Creation & Review. It creates a comprehensive pull request following `/jira:solve` patterns, linking to enhancement proposal and specification.

## Prerequisites

1. **Required Skill Loaded**: `sdlc-state-yaml` must be loaded
2. **Phase 4 Complete**: Testing phase must be completed
3. **GitHub CLI**: `gh` command must be available
4. **Git Remote**: Remote must be configured and accessible
5. **Feature Branch**: Implementation branch must exist with commits

## Inputs

Read from state file:
- `metadata.jira_key`: Jira issue key
- `metadata.jira_url`: Jira issue URL
- `metadata.remote`: Git remote name
- `metadata.mode`: Orchestration mode
- `phases.enhancement.outputs.enhancement_doc_path`: Enhancement proposal path
- `phases.design.outputs.spec_path`: Implementation spec path
- `phases.implementation.outputs.branch_name`: Feature branch name
- `phases.implementation.outputs.commits`: Array of commits
- `phases.testing.outputs`: Test results and coverage

## Outputs

Written to state file:
- `phases.pr_review.outputs.pr_url`: GitHub PR URL
- `phases.pr_review.outputs.pr_number`: PR number
- `phases.pr_review.outputs.pr_state`: PR state (draft/open)
- `phases.pr_review.outputs.ci_status`: CI status
- `phases.pr_review.outputs.created_at`: PR creation timestamp
- `phases.pr_review.verification_gates[]`: Verification gate statuses

## Implementation Steps

### Step 1: Update State - Phase Start

1. Read state file
2. Update state using "Update Phase Start" operation:
   - `current_phase.name`: `"pr_review"`
   - `current_phase.status`: `"in_progress"`
   - `phases.pr_review.status`: `"in_progress"`
   - `phases.pr_review.started_at`: Current timestamp
3. Write state file

### Step 2: Ensure on Feature Branch

Verify we're on the correct branch:

1. Run `git branch --show-current`
2. Compare with `phases.implementation.outputs.branch_name`
3. If mismatch, checkout correct branch

### Step 3: Push Branch to Remote

Push the feature branch to remote:

1. Get remote name from `metadata.remote`
2. Get branch name from `phases.implementation.outputs.branch_name`
3. Push branch:
   ```bash
   git push -u {remote} {branch_name}
   ```
4. If push fails:
   - Check if remote exists: `git remote -v`
   - Check if authentication is configured
   - In interactive mode: Ask user to fix remote/auth issues
   - In automation mode: Fail with detailed error

### Step 4: Generate PR Title

Create PR title following convention:

**Format**: `{JIRA-KEY}: {Summary}`

**Example**: `OCPSTRAT-1612: Configure and Modify Internal OVN IPV4 Subnets`

1. Extract summary from `phases.enhancement.outputs.feature_summary`
2. Truncate if too long (GitHub limit is ~256 characters)
3. Ensure title is clear and descriptive

### Step 5: Generate PR Description

Create comprehensive PR description:

**Check for PR template:**
1. Look for `.github/PULL_REQUEST_TEMPLATE.md`
2. If exists, read template and use as base structure
3. If not exists, use standard structure below

**PR Description Template:**

```markdown
## Summary

{Brief description of what this PR does - from enhancement summary}

## Jira Issue

{jira_url}

## Enhancement Proposal

{Link to enhancement document if it's in repo, or mention it's in .work/}

## Implementation Specification

{Link to spec document in .work/}

## Changes

{Auto-generated summary of commits and files changed}

- Modified {files_changed} files
- Added {test_files_added} test files
- Commits: {commit_count}

### Commits

{List of commit messages}

## Test Coverage

- Tests run: {tests_run}
- Tests passed: {tests_passed}
- Coverage: {coverage_percentage}%

{If preexisting_failures exist:}
### Pre-existing Test Failures

The following test failures existed before this PR:
{List of preexisting failures}

## Verification

All verification gates passed:
- ✓ make lint-fix
- ✓ make verify
- ✓ make test
- ✓ make build

{If any warnings or pre-existing failures:}
### Notes

{Details about warnings or known issues}

## Manual Testing

{If test plan was generated, include link or summary}

## SDLC Orchestration

This PR was created via SDLC orchestration:
- Enhancement phase: ✓ Complete
- Design phase: ✓ Complete
- Implementation phase: ✓ Complete
- Testing phase: ✓ Complete
- State file: `.work/sdlc/{jira-key}/sdlc-state.yaml`

🤖 Generated with [Claude Code](https://claude.com/claude-code) via `/sdlc:orchestrate {jira-key}`

## Additional Context

{Any additional notes or context from enhancement or spec}
```

**Generate the description:**
1. Read enhancement proposal
2. Read implementation spec
3. Get commit list from state
4. Get test results from state
5. Populate template with actual data
6. Save to `.work/sdlc/{jira-key}/pr-description.md` for reference

### Step 6: Create Pull Request

Create PR using GitHub CLI:

1. **Check if PR already exists** for this branch:
   ```bash
   gh pr list --head {branch_name} --json number,url,state
   ```
2. If PR exists:
   - Log: "PR already exists: {pr_url}"
   - Extract PR number and URL
   - Skip to Step 8 (Update PR if needed)
3. If PR doesn't exist:
   - Continue to create new PR

4. **Create draft PR**:
   ```bash
   gh pr create \
     --title "{pr_title}" \
     --body "$(cat <<'EOF'
{pr_description}
EOF
)" \
     --draft \
     --base main
   ```

5. **Parse PR creation output** to extract:
   - PR URL
   - PR number

6. **If PR creation fails**:
   - Check error message
   - Common issues:
     - No changes between branches
     - Branch not pushed
     - GitHub authentication failed
   - In interactive mode: Show error, ask user to fix
   - In automation mode: Fail with detailed error

### Step 7: Verify PR Creation

Run verification gates:

**Gate 1: PR Created Successfully**

```yaml
- gate: "pr_created"
  status: "passed"
  timestamp: "{timestamp}"
```

**Gate 2: PR Linked to Jira**

Verify PR description contains Jira URL:
```yaml
- gate: "jira_linked"
  status: "passed"
  timestamp: "{timestamp}"
```

**Gate 3: CI Checks Triggered**

Wait briefly for CI to start, then check:
```bash
gh pr checks {pr_number}
```

Parse output to determine CI status:
- "pending": CI is running
- "passing": All checks passed
- "failing": Some checks failed

```yaml
- gate: "ci_triggered"
  status: "passed"
  timestamp: "{timestamp}"
```

### Step 8: PR Description Review (Interactive Mode)

If `metadata.mode == "interactive"`:

1. Display PR summary:
   ```
   ━━━ Phase 5/7: PR Creation & Review ━━━

   ✓ Branch pushed to {remote}
   ✓ Draft PR created: {pr_url}
   ✓ PR linked to Jira issue
   ✓ CI checks triggered

   PR Title: {pr_title}
   PR Number: #{pr_number}
   ```

2. Ask user: "Would you like to review or update the PR description? (yes/no)"
3. If yes:
   - Show current PR description
   - Ask: "What changes would you like to make?"
   - Get user feedback
   - Update PR description:
     ```bash
     gh pr edit {pr_number} --body "{updated_description}"
     ```
   - Repeat review loop until user is satisfied

4. Ask user: "Ready to mark PR as ready for review? (yes/no/wait)"
   - **yes**: Convert from draft to ready:
     ```bash
     gh pr ready {pr_number}
     ```
     - Update state: `pr_state: "open"`
   - **no/wait**: Keep as draft
     - Update state: `pr_state: "draft"`
     - User can manually mark ready later

If `metadata.mode == "automation"`:
- Skip review step
- Keep PR as draft
- User can review and mark ready manually later

### Step 9: Track Initial CI Status

Monitor CI status briefly:

1. Wait for CI checks to start (up to 2 minutes)
2. Get CI status:
   ```bash
   gh pr checks {pr_number} --json name,conclusion,status
   ```
3. Parse results:
   - Count total checks
   - Count passing checks
   - Count failing checks
   - Identify check names and statuses
4. Update state with CI status:
   ```yaml
   ci_checks:
     total: {count}
     passing: {count}
     failing: {count}
     pending: {count}
   ```

**If CI checks fail immediately:**
- In interactive mode:
  - Show failing checks
  - Ask: "CI checks failed. Would you like to: (1) View logs, (2) Continue anyway, (3) Fix issues"
- In automation mode:
  - Log warning
  - Proceed (failures will be visible in PR, can be fixed in follow-up)

### Step 10: Add PR Comment with SDLC Context

Add a comment to the PR with SDLC orchestration details:

```bash
gh pr comment {pr_number} --body "$(cat <<'EOF'
## SDLC Orchestration Summary

This PR was created through the SDLC orchestrator. All phases completed successfully:

### Phase Completion Status
- ✅ **Enhancement Generation**: Enhancement proposal created
- ✅ **Design & Planning**: Implementation specification approved
- ✅ **Implementation**: Code changes implemented and verified
- ✅ **Testing & Validation**: Tests passed with {coverage}% coverage
- ✅ **PR Creation**: This PR created

### Artifacts
- Enhancement Proposal: `.work/sdlc/{jira-key}/enhancement-proposal.md`
- Implementation Spec: `.work/sdlc/{jira-key}/implementation-spec.md`
- Test Output: `.work/sdlc/{jira-key}/test-output.txt`
- State File: `.work/sdlc/{jira-key}/sdlc-state.yaml`

### Next Steps
1. Review code changes
2. Verify CI passes
3. Approve and merge
4. Orchestrator will track deployment in Phase 6

🤖 SDLC Orchestrator v{orchestrator_version}
EOF
)"
```

### Step 11: Update State - Phase Complete

1. Read current state
2. Update state with outputs:
   ```yaml
   phases:
     pr_review:
       status: "completed"
       completed_at: "{timestamp}"
       outputs:
         pr_url: "{pr_url}"
         pr_number: {pr_number}
         pr_state: "draft"  # or "open"
         pr_title: "{pr_title}"
         ci_status: "pending"  # or "passing"/"failing"
         created_at: "{timestamp}"
         ci_checks:
           total: {count}
           passing: {count}
           failing: {count}
       verification_gates: [{gates array}]
   ```
3. Update `resumability.resume_from_phase`: `"merge"`
4. Write state file

### Step 12: Display Summary

```
━━━ Phase 5/7: PR Creation & Review ━━━ COMPLETE

✓ Pull request created successfully
✓ PR URL: {pr_url}
✓ PR Number: #{pr_number}
✓ PR State: {draft|open}
✓ CI Status: {ci_status}
✓ All verification gates passed

The PR is ready for review. Next steps:
1. Code review by team members
2. Address any feedback
3. Merge when approved

Next phase: Merge & Deployment Tracking
(Will wait for PR to be merged before proceeding)
```

## Error Handling

### Branch Push Fails

If `git push` fails:
1. Check error message:
   - Authentication: Guide user to configure GitHub token
   - Force push needed: Warn user, don't force push automatically
   - Remote not found: Check remote configuration
2. Append error to state
3. In interactive mode: Ask user to fix issue, retry
4. In automation mode: Fail with detailed error

### PR Already Exists

If PR already exists for this branch:
1. Not an error - reuse existing PR
2. Log: "PR already exists, updating if needed"
3. Optionally update PR description if content changed
4. Proceed to next step

### GitHub CLI Not Available

If `gh` command not found:
1. Append error:
   ```yaml
   error_type: "missing_tool"
   message: "GitHub CLI (gh) not found. Install from https://cli.github.com/"
   ```
2. In interactive mode: Provide manual PR creation instructions
3. In automation mode: Fail

### CI Checks Not Starting

If CI doesn't trigger after 2 minutes:
1. Log warning
2. Mark CI status as "unknown"
3. Proceed (CI might start later, or repo might not have CI)

## Success Criteria

Phase 5 is successful when:

- ✅ Feature branch pushed to remote
- ✅ Pull request created on GitHub
- ✅ PR linked to Jira issue
- ✅ PR description comprehensive (enhancement, spec, tests, verification)
- ✅ CI checks triggered (or skipped if no CI)
- ✅ PR reviewed by user (interactive mode) or created as draft (automation mode)
- ✅ State file updated with PR details

## See Also

- Related Command: `/jira:solve` — PR creation patterns
- Related Skill: `sdlc-state-yaml` — state schema and operations
- Previous Phase: `phase-testing` — runs test suite
- Next Phase: `phase-merge` — tracks merge and deployment
