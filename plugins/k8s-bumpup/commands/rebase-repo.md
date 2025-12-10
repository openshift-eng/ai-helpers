---
description: Complete workflow to rebase Kubernetes dependencies across repositories
argument-hint: <target-version> <repository-path> [additional-repos...]
---

## Name
k8s-bumpup:rebase-repo

## Synopsis
```bash
/k8s-bumpup:rebase-repo <target-version> <repository-path> [additional-repos...]
```

## Description
The `k8s-bumpup:rebase-repo` command executes the complete Kubernetes dependency rebase workflow for one or more repositories. It orchestrates auditing, updating, testing, and committing changes with proper validation at each step.

This is the high-level workflow command that automates the complete rebase process including audit analysis, dependency updates, testing, and committing changes.

## Arguments
- `$1` (target-version): Target Kubernetes version (e.g., `v1.29.0`)
- `$2` (repository-path): Path to first repository to rebase
- `$3+` (additional-repos): Optional. Additional repository paths to rebase

## Implementation

### Step 1: Initialize and Validate
1. **Parse arguments**:
   - Extract target version
   - Collect all repository paths
   - Validate target version format

2. **Validate all repositories**:
   - Check each path exists and is a Git repository
   - Verify each has `go.mod` file
   - Confirm clean working directory (or ask user to proceed)
   - Extract current k8s version from each repo

3. **Check prerequisites**:
   - Verify Go toolchain: `go version`
   - Check Git configuration: `git config user.name && git config user.email`
   - Verify internet connectivity for downloading modules

4. **Create work directory**:
   ```bash
   WORK_DIR=".work/k8s-bumpup/$(date +%Y%m%d-%H%M%S)"
   mkdir -p "$WORK_DIR"/{logs,reports}
   ```

### Step 2: Pre-Rebase Audit (For Each Repository)
1. **Run audit analysis**:
   - Execute audit analysis for each repo
   - Generate individual audit reports
   - Save to `${WORK_DIR}/reports/${REPO_NAME}-audit.md`

2. **Aggregate audit results**:
   - Combine findings across all repositories
   - Identify common breaking changes
   - Calculate overall risk level

3. **Present audit summary**:
   ```text
   # Multi-Repository Audit Summary

   ## Repositories
   1. my-operator (v1.28.0 → v1.29.0) - MEDIUM risk
   2. my-controller (v1.28.0 → v1.29.0) - LOW risk

   ## Common Breaking Changes
   - batch/v1beta1 CronJob → batch/v1 (affects: my-operator)

   ## Recommendations
   - Update my-operator CronJob API before proceeding
   - my-controller safe to proceed directly
   ```

4. **Request user confirmation**:
   - Display full audit summary
   - Ask: "Proceed with rebase? [yes/no/review]"
   - If "review", open detailed reports
   - If "no", exit gracefully
   - If "yes", continue to Step 3

### Step 3: Execute Rebase (For Each Repository)
Process each repository sequentially:

1. **Create feature branch**:
   ```bash
   cd ${REPO_PATH}
   BRANCH_NAME="rebase/k8s-${TARGET_VERSION}-$(date +%Y%m%d)"
   git checkout -b "${BRANCH_NAME}"
   ```

2. **Update dependencies**:
   - Execute dependency update logic
   - Log all output to `${WORK_DIR}/logs/${REPO_NAME}-update.log`

3. **Build verification**:
   ```bash
   go build ./... 2>&1 | tee "${WORK_DIR}/logs/${REPO_NAME}-build.log"
   ```
   - If build fails:
     - Log error details
     - Ask user: "Build failed. [fix manually/skip/abort]"
     - If "fix manually", pause and wait for user
     - If "skip", mark repo as FAILED and continue
     - If "abort", stop entire workflow

4. **Run tests**:
   ```bash
   go test ./... -v 2>&1 | tee "${WORK_DIR}/logs/${REPO_NAME}-test.log"
   ```
   - Parse test results (pass/fail counts)
   - If tests fail:
     - Display failed test names
     - Ask: "Tests failed. [review/skip/abort]"

5. **Generate changelog for this repo**:
   - Extract updated modules from `git diff go.mod`
   - Format commit message:
     ```
     Rebase Kubernetes dependencies to ${TARGET_VERSION}

     Updated modules:
     - k8s.io/api: ${OLD_VER} → ${TARGET_VERSION}
     - k8s.io/apimachinery: ${OLD_VER} → ${TARGET_VERSION}
     - k8s.io/client-go: ${OLD_VER} → ${TARGET_VERSION}

     Build: ✓ PASS
     Tests: ✓ PASS (120 tests)
     ```

6. **Commit changes**:
   ```bash
   git add go.mod go.sum vendor/  # vendor/ only if exists
   git commit -F "${WORK_DIR}/commit-msg-${REPO_NAME}.txt"
   ```

7. **Tag completion**:
   - Mark repo as SUCCESS or FAILED
   - Record in summary

### Step 4: Post-Rebase Validation
1. **Cross-repository validation** (if multiple repos):
   - Check if repos depend on each other
   - Verify version consistency across repos
   - Warn if version mismatches detected

2. **Run integration tests** (if configured):
   - Look for integration test script: `scripts/integration-test.sh`
   - Execute if present
   - Log results

### Step 5: Generate Summary Report
1. **Create comprehensive summary**:
   ```markdown
   # Kubernetes Rebase Summary
   Date: ${DATE}
   Target Version: ${TARGET_VERSION}

   ## Results
   | Repository | Previous | Current | Build | Tests | Status |
   |------------|----------|---------|-------|-------|--------|
   | my-operator | v1.28.0 | v1.29.0 | ✓ | ✓ (98/100) | ⚠️ PARTIAL |
   | my-controller | v1.28.0 | v1.29.0 | ✓ | ✓ | ✓ SUCCESS |

   ## Failed Tests
   ### my-operator
   - TestCronJobController (batch API migration needed)
   - TestWebhookValidation (client-go signature change)

   ## Commits Created
   - my-operator: rebase/k8s-v1.29.0-20250126 (abc123)
   - my-controller: rebase/k8s-v1.29.0-20250126 (def456)

   ## Next Steps
   1. Review failed tests in my-operator
   2. Fix CronJob API usage (see audit report)
   3. Re-run tests
   4. Push branches and create PRs
   ```

2. **Save summary**:
   - File: `${WORK_DIR}/rebase-summary.md`
   - Display in console with formatting

### Step 6: Offer Next Actions
1. **Present options to user**:
   ```
   Rebase complete! What would you like to do next?

   1. Push branches to remote
   2. Create pull requests
   3. Review detailed logs
   4. Rollback changes (reset branches)
   5. Exit
   ```

2. **Execute selected action**:
   - **Push branches to fork**:
     ```bash
     # Get GitHub user
     GH_USER=$(gh api user -q .login)

     for repo in ${REPOS}; do
       cd ${repo}

       # Discover fork remote by matching URL pattern
       FORK_REMOTE=$(git remote -v | grep "github.com[:/]${GH_USER}/" | awk '{print $1}' | head -1)

       if [ -z "$FORK_REMOTE" ]; then
         echo "✗ No fork remote found for ${repo}, skipping push"
         echo "  Add your fork with: git remote add <name> git@github.com:${GH_USER}/$(basename ${repo}).git"
         continue
       fi

       # Verify remote exists and push
       if git remote get-url "$FORK_REMOTE" &>/dev/null; then
         git push "$FORK_REMOTE" ${BRANCH_NAME}
         echo "✓ Pushed to $FORK_REMOTE"
       else
         echo "✗ Remote $FORK_REMOTE not found, skipping push"
       fi
     done
     ```

   - **Create PRs** (if `gh` CLI available):
     ```bash
     gh pr create \
       --title "Rebase Kubernetes dependencies to ${TARGET_VERSION}" \
       --body-file "${WORK_DIR}/rebase-summary.md" \
       --draft
     ```

   - **Review logs**:
     - Open `${WORK_DIR}` in editor
     - Display file tree

   - **Rollback**:
     ```bash
     for repo in ${REPOS}; do
       cd ${repo}
       git checkout main  # or previous branch
       git branch -D ${BRANCH_NAME}
     done
     ```

## Return Value

- **Format**: Multi-repository summary with:
  - Per-repository results (success/failure)
  - Build and test status for each
  - Created branches and commits
  - Next action recommendations

- **Output locations**:
  - Summary: `${WORK_DIR}/rebase-summary.md`
  - Audit reports: `${WORK_DIR}/reports/`
  - Build/test logs: `${WORK_DIR}/logs/`

## Error Handling

1. **Repository validation failures**:
   - If any repo invalid, list all issues before aborting
   - Do not proceed if prerequisites not met

2. **Build failures**:
   - Pause workflow at failed repo
   - Allow user to fix and retry
   - Option to skip failed repo and continue

3. **Git operation failures**:
   - Branch already exists: Ask to reuse or create new name
   - Push failures: Display error and suggest manual push
   - Commit failures: Check for hooks and retry

4. **Partial success scenarios**:
   - Some repos succeed, others fail
   - Create summary showing mixed results
   - Do not rollback successful repos automatically

## Examples

1. **Single repository rebase**:
   ```
   /k8s-bumpup:rebase-repo v1.29.0 ./my-operator
   ```
   Complete rebase workflow for one repository

2. **Multiple repositories**:
   ```
   /k8s-bumpup:rebase-repo v1.29.0 ./operator ./controller ./webhook
   ```
   Rebase three related repositories to same version

3. **Absolute paths**:
   ```
   /k8s-bumpup:rebase-repo v1.30.0 /home/user/proj1 /home/user/proj2
   ```
   Works with absolute paths

## Notes

- This command modifies Git state (creates branches, commits)
- Always commits changes - manual review recommended before pushing
- Creates draft PRs by default (if creating PRs)
- All artifacts saved to `.work/k8s-bumpup/` for review
- Safe to re-run - creates new branches with timestamps
- For complex migrations, review the audit report carefully before proceeding
- Respects `.gitignore` - vendor/ only committed if already tracked
