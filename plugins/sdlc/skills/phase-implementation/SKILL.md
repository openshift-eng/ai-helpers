---
name: Phase Implementation
description: Execute code changes according to implementation specification (Phase 3 of SDLC orchestrator)
---

# Phase Implementation

This skill implements Phase 3 of the SDLC orchestrator: Implementation. It executes code changes according to the implementation specification created in Phase 2, following patterns from `/jira:solve`.

## Prerequisites

1. **Required Skill Loaded**: `sdlc-state-yaml` must be loaded
2. **Phase 2 Complete**: Design phase must be completed with valid specification
3. **Git Repository**: Must be in a git repository with clean working directory (or user-confirmed dirty state)
4. **Build Tools**: Repository build tools must be available (Makefile, go, npm, etc.)

## Inputs

Read from state file:
- `metadata.jira_key`: Jira issue key
- `metadata.mode`: Orchestration mode
- `metadata.remote`: Git remote name
- `phases.design.outputs.spec_path`: Path to implementation specification
- `phases.design.outputs.files_to_modify`: Files identified for modification

## Outputs

Written to state file:
- `phases.implementation.outputs.branch_name`: Git feature branch name
- `phases.implementation.outputs.commits[]`: Array of commits created
- `phases.implementation.outputs.files_changed`: Number of files modified
- `phases.implementation.outputs.test_files_added`: Number of test files created
- `phases.implementation.outputs.verification_results`: Results of make/build commands
- `phases.implementation.verification_gates[]`: Verification gate statuses

## Implementation Steps

### Step 1: Update State - Phase Start

1. Read state file
2. Update state using "Update Phase Start" operation:
   - `current_phase.name`: `"implementation"`
   - `current_phase.status`: `"in_progress"`
   - `phases.implementation.status`: `"in_progress"`
   - `phases.implementation.started_at`: Current timestamp
3. Write state file

### Step 2: Load Implementation Specification

1. Read spec file from `phases.design.outputs.spec_path`
2. Parse the implementation plan sections:
   - API Changes
   - Vendor Updates
   - Generated Code
   - Operator/Controller Logic
   - CLI Changes
   - Support/Utility Code
   - Tests
   - Documentation
3. Identify the implementation phases/steps to execute

### Step 3: Create Feature Branch

Create a git feature branch following `/jira:solve` patterns:

1. Check current git status:
   ```bash
   git status
   ```
2. If working directory is dirty:
   - In interactive mode: Ask user if they want to stash, commit, or abort
   - In automation mode: Exit with error
3. Create branch with naming convention:
   ```bash
   git checkout -b fix-{jira_key}
   ```
   Example: `fix-OCPSTRAT-1612`
4. Update state with branch name:
   ```yaml
   outputs:
     branch_name: "fix-{jira_key}"
     remote: "{metadata.remote}"
   ```

### Step 4: Implement Changes

Execute the implementation plan step by step:

**For each implementation phase in the spec:**

1. **Read relevant files** identified in that phase
2. **Understand existing code patterns**:
   - Coding conventions
   - Error handling patterns
   - Logging patterns
   - Test patterns
3. **Make code changes** using Edit/Write tools:
   - Follow existing code patterns
   - Add godoc comments for public functions
   - Use appropriate error handling
   - Follow repository conventions
4. **If dealing with API changes**:
   - Modify API types in `api/` directory
   - Follow Kubernetes API conventions
   - Add validation tags where appropriate
5. **If updating dependencies**:
   - Update `go.mod` or equivalent
   - Run `go mod tidy` or equivalent
6. **If regenerating code** (like CRDs, clients):
   - Run `make update-codegen` or equivalent commands specified in spec
   - Verify generated files are created/updated
7. **If implementing operator/controller logic**:
   - Follow controller-runtime patterns
   - Add proper reconciliation logic
   - Update status conditions appropriately
   - Add logging for important events
8. **If adding tests**:
   - Follow existing test file naming conventions (`*_test.go`, etc.)
   - Use same testing framework as existing tests
   - Create table-driven tests where appropriate
   - Test both success and error cases
   - Ensure tests are deterministic (no race conditions)
9. **If updating documentation**:
   - Update relevant docs in `docs/` directory
   - Update README if needed
   - Update examples

**Complexity Guidelines:**

- For **low complexity** implementations: Execute all phases in one go
- For **medium complexity**: Execute in logical groups, pausing to verify between groups
- For **high complexity**: Consider delegating to SME agents or breaking into sub-tasks

**Update state during implementation:**

After each major change or file modification:
1. Update `files_changed` counter
2. Update `test_files_added` counter if applicable
3. Update `last_updated` timestamp
4. Write state file (allows resumability mid-implementation)

### Step 5: Run Verification Commands

Following `/jira:solve` verification strategy, run build tools to verify implementation:

**Check for Makefile:**

1. Run `ls Makefile` to check if Makefile exists
2. If Makefile exists:
   - Run `make help` or `grep '^[^#]*:' Makefile | head -20` to see available targets

**Run Verification Targets (if Makefile exists):**

Execute verification commands in this order:

1. **make lint-fix** (if target exists):
   ```bash
   make lint-fix
   ```
   - Purpose: Auto-fix import sorting, formatting issues
   - Update state: `verification_results.make_lint_fix = "passed"` or `"failed"`
   - If fails: Review errors, fix issues, re-run
   - Record in verification gates

2. **make verify** (if target exists):
   ```bash
   make verify
   ```
   - Purpose: Verify generated code is up to date, no schema drift
   - Update state: `verification_results.make_verify = "passed"` or `"failed"`
   - If fails:
     - Determine if failure is pre-existing (run on main branch to compare)
     - If new failure: Fix the issue (often need to regenerate code)
     - If pre-existing: Note in state but proceed
   - Record in verification gates

3. **make test** (if target exists):
   ```bash
   make test
   ```
   - Purpose: Run full test suite
   - **CRITICAL**: Run full test suite, NOT just modified packages
   - Update state: `verification_results.make_test = "passed"` or `"failed"`
   - If fails:
     - Parse test output to identify failing tests
     - Determine if failures are pre-existing
     - If new failures: Fix tests or implementation
     - If pre-existing: Note in state but proceed (document in PR)
   - Record in verification gates

4. **make build** (if target exists):
   ```bash
   make build
   ```
   - Purpose: Ensure code compiles
   - Update state: `verification_results.make_build = "passed"` or `"failed"`
   - If fails: Fix compilation errors, re-run
   - Record in verification gates

**Alternative Verification (if no Makefile):**

If Makefile doesn't exist, detect language and run appropriate commands:

- **Go projects**:
  ```bash
  go fmt ./...
  go vet ./...
  go test ./...
  go build ./...
  ```
- **Node.js projects**:
  ```bash
  npm run lint
  npm test
  npm run build
  ```
- **Python projects**:
  ```bash
  pylint .
  black . --check
  pytest
  ```
- **Other**: Check CI config files (`.github/workflows/`, `.gitlab-ci.yml`) for verification commands

**IMPORTANT - Anti-patterns (explicitly forbidden):**

- ❌ Do NOT run `go test ./changed/package/` instead of `make test`
- ❌ Do NOT skip `make test` because `make lint-fix` failed
- ❌ Do NOT assume targeted package tests are sufficient
- ✅ DO run the full test suite to catch cross-package regressions
- ✅ DO distinguish pre-existing failures from new failures
- ✅ DO require all verification commands to pass (or failures confirmed pre-existing) before proceeding

**You MUST NOT proceed to Step 6 (Commit Creation) until:**
- All verification commands have been run
- All failures are either fixed OR confirmed pre-existing

### Step 6: Create Logical Commits

Following `/jira:solve` commit patterns, create logical commits:

1. **Review all changes**:
   ```bash
   git status
   git diff
   ```

2. **Break commits into logical components** based on the nature of changes:

   **Common logical groupings** (use as guidance, not rigid rules):

   - **API changes**: Changes in `api/` directory (types, CRDs)
     ```bash
     git add api/
     git commit -m "feat(api): Add subnet configuration fields

This adds new configuration fields to the HostedCluster API
to support customization of OVN internal subnet ranges.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
     ```

   - **Vendor changes**: Dependency updates in `vendor/` directory
     ```bash
     git add go.mod go.sum vendor/
     git commit -m "chore(vendor): Update dependencies for OVN subnet support

Update ovn-kubernetes to v0.3.0 to pick up subnet configuration API.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
     ```

   - **Generated code**: Auto-generated clients, informers, listers, CRDs
     ```bash
     git add {generated_files}
     git commit -m "chore(generated): Regenerate clients and CRDs

Regenerate after API changes to ensure client code is in sync.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
     ```

   - **Operator changes**: Controller logic in `operator/` or `controllers/`
     ```bash
     git add pkg/operator/ controllers/
     git commit -m "feat(operator): Implement subnet reconciliation logic

Add reconciliation logic to configure OVN subnet ranges based on
HostedCluster spec. Without this the controller won't react when
subnet configuration changes.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
     ```

   - **CLI changes**: User-facing command changes in `cmd/`
     ```bash
     git add cmd/
     git commit -m "feat(cli): Add --ovn-subnet flag to cluster create

This allows users to configure OVN subnet ranges at cluster
creation time.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
     ```

   - **Support/utilities**: Shared code in `support/` directory
     ```bash
     git add support/
     git commit -m "refactor(support): Extract subnet validation utility

Consolidate duplicated subnet validation logic from multiple
controllers into shared helper function.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
     ```

   - **Tests**: Test additions or modifications
     ```bash
     git add {test_files}
     git commit -m "test: Add tests for subnet configuration

Ensure the new subnet configuration behavior is covered by unit
tests to prevent regressions.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
     ```

   - **Documentation**: Changes in `docs/` directory
     ```bash
     git add docs/
     git commit -m "docs: Document subnet configuration feature

Help users understand how to configure and use OVN subnet
customization.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
     ```

3. **Commit message format**:
   - Follow https://www.conventionalcommits.org/en/v1.0.0/
   - Format: `<type>(<scope>): <subject>` + body explaining "why"
   - Types: `feat`, `fix`, `chore`, `test`, `docs`, `refactor`
   - Always include body articulating the "why"
   - Always include: `Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>`

4. **Use heredoc for commit messages** to ensure proper formatting:
   ```bash
   git commit -m "$(cat <<'EOF'
feat(api): Add subnet configuration fields

This adds new configuration fields to the HostedCluster API
to support customization of OVN internal subnet ranges.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
   ```

5. **Record each commit in state**:
   ```yaml
   commits:
     - sha: "{commit_sha}"
       message: "{commit_subject_line}"
       timestamp: "{commit_timestamp}"
   ```

6. **Verify all changes committed**:
   ```bash
   git status
   ```
   - Should show "nothing to commit, working tree clean"
   - If there are uncommitted changes, ask user if they should be committed or discarded

### Step 7: Update State - Phase Complete

1. Read current state
2. Update state with full outputs:
   ```yaml
   phases:
     implementation:
       status: "completed"
       completed_at: "{timestamp}"
       outputs:
         branch_name: "fix-{jira_key}"
         remote: "{metadata.remote}"
         commits:
           - sha: "{sha1}"
             message: "{message1}"
             timestamp: "{ts1}"
           - sha: "{sha2}"
             message: "{message2}"
             timestamp: "{ts2}"
         files_changed: {count}
         test_files_added: {count}
         verification_results:
           make_lint_fix: "passed"
           make_verify: "passed"
           make_test: "passed"
           make_build: "passed"
       verification_gates:
         - gate: "make_lint_fix"
           status: "passed"
           timestamp: "{timestamp}"
         - gate: "make_verify"
           status: "passed"
           timestamp: "{timestamp}"
         - gate: "make_test"
           status: "passed"
           timestamp: "{timestamp}"
         - gate: "commits_created"
           status: "passed"
           timestamp: "{timestamp}"
   ```
3. Update `resumability.resume_from_phase`: `"testing"`
4. Write state file

### Step 8: Display Summary

```
━━━ Phase 3/7: Implementation ━━━ COMPLETE

✓ Feature branch created: fix-{jira_key}
✓ Changes implemented according to specification
✓ Files modified: {count}
✓ Test files added: {count}
✓ All verification gates passed:
  ✓ make lint-fix
  ✓ make verify
  ✓ make test
  ✓ make build
✓ Commits created: {count}

Next phase: Testing & Validation
```

## Error Handling

### Specification Not Found

If `spec_path` doesn't exist:
1. Append error to state
2. Update phase status to `"failed"`
3. Exit with message: "Implementation specification not found. Phase 2 must complete first."

### Verification Command Failures

If verification commands fail:

1. **Distinguish pre-existing vs new failures**:
   - Stash current changes
   - Checkout main branch
   - Run same verification command
   - If fails on main: Pre-existing failure
   - If passes on main: New failure caused by implementation
   - Checkout feature branch and pop stash

2. **Handle new failures**:
   - Append error to state with details
   - In interactive mode: Ask user: "(1) Fix automatically, (2) Let me fix manually, (3) Skip verification (not recommended)"
   - In automation mode: Attempt automatic fix, exit if unable

3. **Handle pre-existing failures**:
   - Log warning
   - Note in state: `"preexisting_failure": true`
   - Proceed with implementation
   - Document in PR description

### Merge Conflicts During Implementation

If git operations fail due to conflicts:
1. Append error to state
2. In interactive mode: Ask user to resolve conflicts, then continue
3. In automation mode: Exit with error

### Build/Compilation Errors

If code doesn't compile:
1. Parse error output
2. Identify problematic files/lines
3. Attempt to fix automatically
4. If unable to fix:
   - In interactive mode: Show errors, ask user for guidance
   - In automation mode: Exit with detailed error

## Success Criteria

Phase 3 is successful when:

- ✅ Feature branch created with conventional name
- ✅ All changes from spec implemented
- ✅ Code follows repository conventions
- ✅ godoc comments added for public functions
- ✅ Tests created for new functionality
- ✅ All verification commands pass (or pre-existing failures documented)
- ✅ Logical commits created following conventional commits
- ✅ Working tree is clean (all changes committed)
- ✅ State file updated with commits and verification results

## See Also

- Related Command: `/jira:solve` — patterns for implementation and verification
- Related Skill: `sdlc-state-yaml` — state schema and operations
- Previous Phase: `phase-design` — creates implementation specification
- Next Phase: `phase-testing` — runs comprehensive test suite
