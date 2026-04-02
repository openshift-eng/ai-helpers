---
name: Phase Testing
description: Run comprehensive test suite and validate coverage (Phase 4 of SDLC orchestrator)
---

# Phase Testing

This skill implements Phase 4 of the SDLC orchestrator: Testing & Validation. It runs comprehensive tests and validates coverage beyond the basic verification done in Phase 3.

## Prerequisites

1. **Required Skill Loaded**: `sdlc-state-yaml` must be loaded
2. **Phase 3 Complete**: Implementation phase must be completed with passing verification
3. **Test Tools**: Test frameworks and coverage tools must be available
4. **Feature Branch**: Implementation branch must exist with committed changes

## Inputs

Read from state file:
- `metadata.jira_key`: Jira issue key
- `metadata.mode`: Orchestration mode
- `phases.implementation.outputs.branch_name`: Feature branch name
- `phases.implementation.outputs.verification_results`: Previous verification results

## Outputs

Written to state file:
- `phases.testing.outputs.test_results`: Overall result (passed/failed)
- `phases.testing.outputs.tests_run`: Total tests executed
- `phases.testing.outputs.tests_passed`: Tests that passed
- `phases.testing.outputs.coverage_percentage`: Test coverage
- `phases.testing.outputs.new_failures[]`: New test failures
- `phases.testing.outputs.preexisting_failures[]`: Pre-existing failures
- `phases.testing.verification_gates[]`: Verification gate statuses

## Implementation Steps

### Step 1: Update State - Phase Start

1. Read state file
2. Update state using "Update Phase Start" operation:
   - `current_phase.name`: `"testing"`
   - `current_phase.status`: `"in_progress"`
   - `phases.testing.status`: `"in_progress"`
   - `phases.testing.started_at`: Current timestamp
3. Write state file

### Step 2: Ensure on Feature Branch

Verify we're on the correct branch:

1. Run `git branch --show-current`
2. Compare with `phases.implementation.outputs.branch_name`
3. If mismatch:
   - Checkout correct branch: `git checkout {branch_name}`
4. Verify working tree is clean:
   - Run `git status`
   - If dirty, ask user to commit or stash (interactive) or exit (automation)

### Step 3: Run Unit Tests

Execute unit test suite with detailed output:

**If Makefile exists:**

```bash
make test
```

**If no Makefile, detect language:**

- **Go**: `go test -v -cover ./... | tee test-output.txt`
- **Node.js**: `npm test -- --verbose --coverage`
- **Python**: `pytest -v --cov=. --cov-report=term`
- **Other**: Check CI configuration for test commands

**Parse test output to extract:**
1. Total number of tests run
2. Number of tests passed
3. Number of tests failed
4. Test failure details (test names, error messages)
5. Coverage percentage (if available)

**Save test output:**
- Write to `.work/sdlc/{jira-key}/test-output.txt` for reference

### Step 4: Identify New vs Pre-existing Failures

If tests failed, determine which are new:

1. **Stash current changes** (if any uncommitted work)
2. **Checkout main/master branch**: `git checkout main`
3. **Run same test command**
4. **Compare results**:
   - Tests that fail on both feature branch AND main: Pre-existing
   - Tests that pass on main but fail on feature branch: New failures
5. **Checkout feature branch**: `git checkout {branch_name}`
6. **Pop stash** (if stashed)

**Record results:**
```yaml
new_failures:
  - test_name: "TestSubnetConfiguration"
    error_message: "expected subnet range 10.128.0.0/14, got 10.132.0.0/14"
    file: "pkg/operator/controller_test.go"
    line: 156

preexisting_failures:
  - test_name: "TestOldFeature"
    error_message: "known flaky test"
    file: "pkg/legacy/feature_test.go"
```

### Step 5: Run Integration Tests (if applicable)

If the repository has integration tests:

**Common patterns:**
- `make test-integration`
- `make test-e2e`
- `npm run test:integration`
- `pytest tests/integration/`

**Execute integration tests:**
1. Check if integration test target/command exists
2. If exists:
   - Run integration tests
   - Parse output
   - Record results separately
3. If not exists:
   - Log: "No integration tests found, skipping"

**Integration tests may require:**
- Running services/databases
- Kubernetes cluster access
- Extended timeouts
- Special environment setup

**Handle integration test failures:**
- Same approach as unit tests (distinguish new vs pre-existing)
- Integration test failures are often environment-related
- In interactive mode: Ask user if they want to skip integration tests
- In automation mode: Mark as warning if integration tests fail but unit tests pass

### Step 6: Check Test Coverage

If coverage tools are available:

**Go coverage:**
```bash
go test -coverprofile=coverage.out ./...
go tool cover -func=coverage.out | tail -1
```

**Parse coverage percentage:**
- Extract percentage from output
- Compare to project standards (if defined in README, Makefile, or CI config)

**Coverage thresholds:**
- Check for coverage configuration:
  - `.coveragerc` (Python)
  - `jest.config.js` (JavaScript)
  - Makefile targets with coverage thresholds
- If threshold defined and not met:
  - Log warning
  - Note in state

**Save coverage report:**
- Write to `.work/sdlc/{jira-key}/coverage.html` (HTML format if available)
- Write to `.work/sdlc/{jira-key}/coverage.txt` (text summary)

### Step 7: Generate Test Plan (Optional)

If `metadata.mode == "interactive"` and user wants manual test scenarios:

1. Ask user: "Would you like to generate a manual test plan? (yes/no)"
2. If yes:
   - Check if `/jira:generate-test-plan` skill exists
   - If exists, invoke it with jira_key
   - Save output to `.work/sdlc/{jira-key}/test-plan.md`
   - Add to outputs:
     ```yaml
     test_plan_path: ".work/sdlc/{jira-key}/test-plan.md"
     ```

### Step 8: Verify Test Gates

Run verification gates:

**Gate 1: Unit Tests Executed**

```yaml
- gate: "unit_tests_executed"
  status: "passed"  # or "failed"
  timestamp: "{timestamp}"
```

**Gate 2: No New Test Failures**

```yaml
- gate: "no_new_failures"
  status: "passed"  # "passed" if new_failures is empty, "failed" otherwise
  timestamp: "{timestamp}"
```

If new failures exist:
- In interactive mode: Ask user: "(1) Fix failures, (2) Document as known issues (3) Abort"
- In automation mode: Fail the phase

**Gate 3: Coverage Adequate** (if coverage tools available)

```yaml
- gate: "coverage_adequate"
  status: "passed"  # or "warning" if below threshold but acceptable
  timestamp: "{timestamp}"
```

If coverage below project threshold:
- Mark as "warning" not "failed"
- Note in state for PR description

**Gate 4: Integration Tests Passed** (if integration tests exist)

```yaml
- gate: "integration_tests_passed"
  status: "passed"  # or "skipped" if no integration tests
  timestamp: "{timestamp}"
```

### Step 9: Handle Test Failures

If new test failures were found:

**In interactive mode:**

1. Show test failure summary
2. Ask user for action:
   - **"fix"**: Analyze failures, attempt to fix implementation/tests, re-run
   - **"review"**: Show full test output, let user decide next steps
   - **"document"**: Document as known issues to address in follow-up, proceed with PR
   - **"abort"**: Update phase status to "failed", exit

**In automation mode:**

1. Attempt automatic fix:
   - Analyze test failure messages
   - Identify likely causes
   - Make targeted fixes to implementation or tests
   - Re-run tests
2. If automatic fix succeeds:
   - Create new commit with test fixes
   - Update state with new commit
   - Proceed
3. If automatic fix fails:
   - Update phase status to "failed"
   - Append detailed error to state
   - Exit

### Step 10: Update State - Phase Complete

1. Read current state
2. Update state with outputs:
   ```yaml
   phases:
     testing:
       status: "completed"
       completed_at: "{timestamp}"
       outputs:
         test_results: "passed"  # or "passed_with_warnings"
         tests_run: 127
         tests_passed: 127
         coverage_percentage: 82.5
         new_failures: []
         preexisting_failures:
           - test_name: "TestOldFeature"
             error_message: "known flaky test"
         test_output_path: ".work/sdlc/{jira-key}/test-output.txt"
         coverage_report_path: ".work/sdlc/{jira-key}/coverage.html"
         test_plan_path: ".work/sdlc/{jira-key}/test-plan.md"  # if generated
       verification_gates: [{gates array}]
   ```
3. Update `resumability.resume_from_phase`: `"pr_review"`
4. Write state file

### Step 11: Display Summary

```
━━━ Phase 4/7: Testing & Validation ━━━ COMPLETE

✓ Unit tests: {tests_passed}/{tests_run} passed
✓ Coverage: {coverage_percentage}%
✓ New test failures: 0
⚠ Pre-existing failures: {count} (will be documented in PR)
✓ All verification gates passed

Test output saved to: .work/sdlc/{jira-key}/test-output.txt

Next phase: PR Creation & Review
```

## Error Handling

### Test Command Not Found

If test commands don't exist:
1. Log warning
2. Try to detect test files:
   - Use Glob to find `**/*_test.go`, `**/*.test.js`, etc.
3. If test files exist but no command:
   - In interactive mode: Ask user for correct test command
   - In automation mode: Skip testing phase with warning
4. If no test files:
   - Log: "No tests found in repository"
   - Mark gate as "skipped"
   - Proceed (some repos legitimately have no tests yet)

### All Tests Fail

If all or most tests fail:
1. Likely indicates broader issue (missing setup, broken build, etc.)
2. Append error with diagnostic info:
   - First few test failure messages
   - Suggestions (missing dependencies, environment issues)
3. In interactive mode:
   - Show diagnostic info
   - Ask user: "This appears to be a systematic issue. Would you like to: (1) Debug, (2) Review test output, (3) Abort"
4. In automation mode:
   - Update phase status to "failed"
   - Exit with diagnostic info

### Coverage Tools Missing

If coverage percentage cannot be determined:
1. Log info: "Coverage tools not available"
2. Mark coverage gate as "skipped"
3. Proceed (coverage is nice-to-have, not required)

### Integration Tests Timeout

If integration tests take too long or hang:
1. Set reasonable timeout (e.g., 10 minutes)
2. If timeout exceeded:
   - Kill test process
   - Log warning
   - In interactive mode: Ask if should retry or skip
   - In automation mode: Mark as "warning", proceed

## Success Criteria

Phase 4 is successful when:

- ✅ Unit tests executed successfully
- ✅ No new test failures (or failures fixed/documented)
- ✅ Test coverage measured (if tools available)
- ✅ Integration tests passed or skipped with reason
- ✅ Pre-existing failures identified and documented
- ✅ All verification gates passed (or warnings acceptable)
- ✅ State file updated with test results

## See Also

- Related Command: `/jira:generate-test-plan` — generates manual test scenarios
- Related Skill: `sdlc-state-yaml` — state schema and operations
- Previous Phase: `phase-implementation` — executes code changes
- Next Phase: `phase-pr-review` — creates pull request
