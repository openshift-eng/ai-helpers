---
description: Rebase Kubernetes dependencies across a group of related repositories
argument-hint: <group-name> [--workspace-dir] [--create-pr] [--create-jira]
---

## Name
k8s-bumpup:batch-by-group

## Synopsis
```
/k8s-bumpup:batch-by-group <group-name> [options]
```

## Description
The `k8s-bumpup:batch-by-group` command automates Kubernetes dependency rebasing across multiple related repositories defined in a group. It clones the latest code from each repository, runs the rebase workflow, and generates a comprehensive summary across all repos.

This command **automatically fetches and uses the latest stable Kubernetes release** from GitHub. No version specification is needed.

This is ideal for coordinated upgrades across related components (e.g., all corenet repos, all storage repos). Optionally creates PRs for each repository and a single JIRA issue tracking the entire group upgrade.

## Arguments
- `$1` (group-name): Repository group name (e.g., `network`, `storage`, `operators`) - **Required**

## Options
- `--workspace-dir <path>`: Custom workspace directory for cloned repos. Defaults to `.work/k8s-rebase-group/${GROUP_NAME}/${TIMESTAMP}`
- `--create-pr`: Automatically fork repositories (if not already forked), push branches to your fork, and create pull requests
- `--create-jira`: Create a single JIRA issue tracking the entire group upgrade (includes links to all PRs)
- `--dry-run`: Perform audit and validation without making any changes or creating branches
- `--skip-tests`: Skip running tests (faster, but less safe)

## Implementation

### Step 1: Parse Arguments and Load Group Configuration
1. **Parse command arguments**:
   - Extract group name (required)
   - Determine workspace directory from --workspace-dir flag or use default

2. **Fetch and sync Kubernetes version with client library version**:
   ```bash
   echo "Fetching latest Kubernetes release..."

   # Fetch latest stable release from GitHub API
   LATEST_K8S_VERSION=$(curl -s https://api.github.com/repos/kubernetes/kubernetes/releases/latest | \
     jq -r '.tag_name')

   if [ -z "$LATEST_K8S_VERSION" ] || [ "$LATEST_K8S_VERSION" = "null" ]; then
     echo "Error: Failed to fetch latest Kubernetes release from GitHub API"
     exit 1
   fi

   echo "Latest Kubernetes release: $LATEST_K8S_VERSION"

   # Extract minor version (v1.34.3 -> 34)
   MINOR_VERSION=$(echo "$LATEST_K8S_VERSION" | sed 's/^v1\.\([0-9]*\)\..*/\1/')

   # Query available k8s.io/api versions and find latest stable v0.{minor}.x
   echo "Querying available k8s.io/api versions..."
   TARGET_VERSION=$(go list -m -versions -json k8s.io/api 2>/dev/null | \
     jq -r '.Versions[]' | \
     grep "^v0\.${MINOR_VERSION}\." | \
     grep -v -E '(alpha|beta|rc)' | \
     sort -V | \
     tail -1)

   if [ -z "$TARGET_VERSION" ]; then
     echo "Error: Could not find stable v0.${MINOR_VERSION}.x release for k8s.io/api"
     exit 1
   fi

   echo "Latest stable client library: $TARGET_VERSION"

   # Extract patch version from client library (v0.34.2 -> 2)
   CLIENT_PATCH=$(echo "$TARGET_VERSION" | sed 's/^v0\.[0-9]*\.\([0-9]*\)/\1/')

   # Construct matching Kubernetes version (v1.34.2 to match v0.34.2)
   MATCHED_K8S_VERSION="v1.${MINOR_VERSION}.${CLIENT_PATCH}"

   # Check if versions are in sync
   if [ "$LATEST_K8S_VERSION" != "$MATCHED_K8S_VERSION" ]; then
     echo ""
     echo "⚠ Version mismatch detected:"
     echo "  Latest Kubernetes: $LATEST_K8S_VERSION"
     echo "  Latest client lib: $TARGET_VERSION"
     echo ""
     echo "Syncing to matching pair: $MATCHED_K8S_VERSION ↔ $TARGET_VERSION"
     KUBERNETES_VERSION="$MATCHED_K8S_VERSION"
   else
     echo "✓ Versions in sync: $LATEST_K8S_VERSION ↔ $TARGET_VERSION"
     KUBERNETES_VERSION="$LATEST_K8S_VERSION"
   fi
   ```

3. **Load repository group configuration**:
   ```bash
   CONFIG_FILE="plugins/k8s-bumpup/.claude-plugin/repo-groups.json"
   ```
   - Read JSON configuration file
   - Extract repository list for specified group
   - Validate group exists

4. **Display group information**:
   ```
   Repository Group: corenet
   Description: Core networking OpenShift repositories
   Repositories (4):
   1. multus-cni (https://github.com/openshift/multus-cni.git)
   2. ovn-kubernetes (https://github.com/openshift/ovn-kubernetes.git)
   3. sdn (https://github.com/openshift/sdn.git)
   4. cluster-network-operator (https://github.com/openshift/cluster-network-operator.git)

   Target Versions (synced):
   - Kubernetes: v1.34.2
   - Client Libraries: v0.34.2

   Note: Latest K8s release is v1.34.3, but using v1.34.2 to match available client libraries
   ```

5. **Request user confirmation**:
   - Ask: "Proceed with group rebase? This will clone and rebase all repositories. [yes/no]"
   - If "no", exit gracefully
   - If "yes", continue

### Step 2: Setup Workspace
1. **Create workspace directory**:
   ```bash
   WORKSPACE_DIR=".work/k8s-batch-by-group/${GROUP_NAME}/$(date +%Y%m%d-%H%M%S)"
   mkdir -p "${WORKSPACE_DIR}"/{repos,logs,reports}
   ```

2. **Create tracking file**:
   ```bash
   cat > "${WORKSPACE_DIR}/rebase-status.json" <<EOF
   {
     "group": "${GROUP_NAME}",
     "target_version": "${TARGET_VERSION}",
     "started_at": "$(date -Iseconds)",
     "repos": []
   }
   EOF
   ```

3. **Log workspace location**:
   ```
   Workspace: .work/k8s-batch-by-group/corenet/20251126-080000
   ```

### Step 3: Clone Repositories
For each repository in the group:

1. **Auto-detect default branch**:
   ```bash
   REPO_NAME="multus-cni"
   REPO_URL="git@github.com:k8snetworkplumbingwg/multus-cni.git"
   REPO_DIR="${WORKSPACE_DIR}/repos/${REPO_NAME}"

   # Auto-detect default branch instead of hardcoding
   DEFAULT_BRANCH=$(git ls-remote --symref "${REPO_URL}" HEAD | \
     awk '/^ref:/ {sub("refs/heads/", "", $2); print $2}')

   echo "Detected default branch: ${DEFAULT_BRANCH}"
   ```

2. **Clone repository**:
   ```bash
   git clone --depth 1 --branch "${DEFAULT_BRANCH}" "${REPO_URL}" "${REPO_DIR}" \
     2>&1 | tee "${WORKSPACE_DIR}/logs/${REPO_NAME}-clone.log"
   ```

   **Fallback strategy**: If clone fails, try common branch names:
   - Try `main`
   - Try `master`
   - Mark as SKIPPED if all fail

3. **Verify repository structure**:
   - Check `go.mod` exists (may be in subdirectory like `go-controller/`)
   - Check if k8s.io dependencies exist
   - Extract current k8s version

4. **Handle special cases**:
   - **Already up-to-date**: If current version == target version, mark as SKIPPED (up-to-date)
   - **No go.mod**: Search subdirectories for go.mod (e.g., ovn-kubernetes/go-controller/)
   - **No k8s deps**: Mark repo as SKIPPED (no k8s dependencies)

5. **Track progress**:
   ```
   [1/8] ✓ Cloned multus-cni (default branch: master)
   [2/8] ✓ Cloned ovn-kubernetes (default branch: master, go.mod in: go-controller/)
   [3/8] ⚠ Skipped sdn (no k8s dependencies)
   [4/8] ℹ️ Skipped net-attach-def-admission-controller (already v0.34.2)
   [5/8] ✓ Cloned cluster-network-operator (default branch: master)
   ```

### Step 4: Run Audit Phase (Parallel)
For each successfully cloned repository:

1. **Run audit in parallel** (if resources allow):
   ```bash
   # For each repo, run audit analysis
   # - Scan for k8s.io API usage
   # - Fetch Kubernetes changelogs
   # - Identify breaking changes
   ```

2. **Save individual audit reports**:
   - Location: `${WORKSPACE_DIR}/reports/${REPO_NAME}-audit.md`

3. **Aggregate audit results**:
   - Combine risk assessments
   - Identify common breaking changes across repos
   - Calculate overall risk level (highest risk among all repos)

4. **Present aggregate audit summary**:
   ```
   # Group Audit Summary

   ## Repositories
   | Repository | Current | Target | Risk | Status |
   |------------|---------|--------|------|--------|
   | multus-cni | v0.34.1 | v0.34.2 | LOW | ✓ Ready |
   | ovn-kubernetes | v0.33.0 | v0.34.2 | HIGH | ⚠ Review needed |
   | cluster-network-operator | v0.34.0 | v0.34.2 | LOW | ✓ Ready |

   ## Common Breaking Changes
   - None identified (patch version upgrade for most repos)

   ## High-Risk Repositories
   1. ovn-kubernetes: Crossing minor version (v0.33.0 → v0.34.2)
      - Review breaking changes in v0.34.x
      - Test thoroughly after upgrade

   ## Recommendations
   - Proceed with caution for ovn-kubernetes
   - Other repos are low-risk patch upgrades
   ```

5. **Request confirmation to proceed**:
   - Ask: "Proceed with rebase? [yes/no/review]"
   - If "review", open detailed audit reports
   - If "no", exit (repos remain cloned for manual inspection)
   - If "yes", continue to Step 5

### Step 5: Execute Rebase (Sequential)
Process each repository sequentially:

1. **Create feature branch**:
   ```bash
   cd "${REPO_DIR}"
   BRANCH_NAME="rebase/k8s-${TARGET_VERSION}-$(date +%Y%m%d)"
   git checkout -b "${BRANCH_NAME}"
   ```

2. **Find all go.mod files** (some repos have multiple):
   ```bash
   # Find all go.mod files (excluding vendor)
   GO_MOD_FILES=$(find . -name "go.mod" -type f | grep -v vendor)

   # Examples:
   # - Most repos: ./go.mod
   # - ovn-kubernetes: ./go-controller/go.mod, ./test/e2e/go.mod, ./test/conformance/go.mod
   ```

3. **Update dependencies in ALL go.mod files**:
   ```bash
   for GO_MOD_DIR in $(dirname "$GO_MOD_FILES"); do
     cd "${REPO_DIR}/${GO_MOD_DIR}"

     echo "Updating ${GO_MOD_DIR}/go.mod..."

     # Update both v1.x and v0.x versioned dependencies
     go get k8s.io/kubernetes@${KUBERNETES_VERSION} \      # v1.34.3
           k8s.io/api@${TARGET_VERSION} \                  # v0.34.3
           k8s.io/apimachinery@${TARGET_VERSION} \
           k8s.io/client-go@${TARGET_VERSION} \
           k8s.io/component-helpers@${TARGET_VERSION} \
           k8s.io/pod-security-admission@${TARGET_VERSION}

     go mod tidy

     # Update vendor if needed
     if [ -d "vendor" ]; then
       go mod vendor
     fi
   done
   ```

   **Important version mapping**:
   - `k8s.io/kubernetes` uses `v1.x.y` versioning (e.g., v1.34.3)
   - `k8s.io/api`, `k8s.io/apimachinery`, `k8s.io/client-go` use `v0.x.y` (e.g., v0.34.3)

3. **Run build verification**:
   ```bash
   echo "Building..."
   go build ./... 2>&1 | tee "${WORKSPACE_DIR}/logs/${REPO_NAME}-build.log"
   ```

4. **Run tests with progress indicators**:
   ```bash
   echo "Running tests..."
   # For repos with long-running tests (>2 min), show progress
   go test ./... -v 2>&1 | tee "${WORKSPACE_DIR}/logs/${REPO_NAME}-test.log" | \
     grep -E "^(PASS|FAIL|ok|=== RUN)" | \
     while read line; do
       echo "[$(date +%H:%M:%S)] $line"
     done
   ```

   **Progress tracking for long tests**:
   - Display running test package name
   - Show elapsed time every 30 seconds for tests taking >1 minute
   - Example: `[09:40:15] Running: pkg/ovn (elapsed: 2m 30s)...`
   - Log slowest test packages for summary report

5. **Handle build/test failures**:
   - **Build failures**:
     - Mark repo as FAILED
     - Log error details
     - Ask: "Build failed for ${REPO_NAME}. [skip/fix manually/abort all]"
     - If "skip", continue to next repo
     - If "fix manually", pause and wait
     - If "abort all", stop workflow

   - **Test failures**:
     - Check if tests also fail on default branch (pre-existing)
     - Run: `git stash && git checkout ${DEFAULT_BRANCH} && go test ./...`
     - If pre-existing, mark as WARNING but continue
     - If new failures, ask user to review
     - Restore: `git checkout ${BRANCH_NAME} && git stash pop`

6. **Commit changes**:
   ```bash
   git add go.mod go.sum vendor/
   git commit -m "Bump Kubernetes dependencies to ${TARGET_VERSION}

   Updated modules:
   - k8s.io/api: ${OLD_VER} → ${TARGET_VERSION}
   - k8s.io/apimachinery: ${OLD_VER} → ${TARGET_VERSION}
   - k8s.io/client-go: ${OLD_VER} → ${TARGET_VERSION}

   Build: ✓ PASS
   Tests: ${TEST_STATUS}

   Part of ${GROUP_NAME} group rebase to ${TARGET_VERSION}

   🤖 Generated with [Claude Code](https://claude.com/claude-code)

   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
   "
   ```

7. **Track completion**:
   - Update rebase-status.json with results
   - Record test duration and slowest packages
   - Mark repo as SUCCESS, FAILED, or WARNING

8. **Display progress**:
   ```
   [1/7] ✓ multus-cni - SUCCESS (build: ✓, tests: ✓ in 15s)
   [2/7] ✓ multi-networkpolicy-iptables - SUCCESS (build: ✓, tests: ✓ in 8s)
   [3/7] ⚠ ovn-kubernetes - SUCCESS (build: ✓, tests: ✓ in 12m 30s)
         Slowest: pkg/ovn (552s), pkg/node (83s), pkg/factory (35s)
   [4/7] ✓ cluster-network-operator - SUCCESS (build: ✓, tests: ✓ in 2m)
   ```

### Step 6: Generate Group Summary Report
1. **Create comprehensive summary**:
   ```markdown
   # Kubernetes Group Rebase Summary

   **Group**: network
   **Target Version**: v0.34.2
   **Date**: 2025-11-26
   **Workspace**: .work/k8s-batch-by-group/corenet/20251126-080000

   ## Overall Status
   - ✓ **Success**: 2 repositories
   - ⚠ **Warning**: 1 repository
   - ❌ **Failed**: 0 repositories

   ## Repository Results
   | Repository | Previous | Current | Build | Tests | Branch | Status |
   |------------|----------|---------|-------|-------|--------|--------|
   | multus-cni | v0.34.1 | v0.34.2 | ✓ | ✓ (216 specs) | rebase/k8s-v0.34.2-20251126 | ✓ SUCCESS |
   | ovn-kubernetes | v0.33.0 | v0.34.2 | ✓ | ⚠ (3 failures) | rebase/k8s-v0.34.2-20251126 | ⚠ WARNING |
   | cluster-network-operator | v0.34.0 | v0.34.2 | ✓ | ✓ | rebase/k8s-v0.34.2-20251126 | ✓ SUCCESS |

   ## Test Failures
   ### ovn-kubernetes
   - TestOVNController (pre-existing)
   - TestIPv6Support (pre-existing)
   - TestNetworkPolicy (new - needs investigation)

   ## Commits Created
   - multus-cni: rebase/k8s-v0.34.2-20251126 (abc123d)
   - ovn-kubernetes: rebase/k8s-v0.34.2-20251126 (def456e)
   - cluster-network-operator: rebase/k8s-v0.34.2-20251126 (789abc0)

   ## Next Steps
   1. Review test failure in ovn-kubernetes (TestNetworkPolicy)
   2. Push all branches to remote
   3. Create pull requests for each repository
   4. Coordinate testing across networking stack

   ## Commands to Push Branches

   Push branches to your fork (when using `--create-pr`):
   ```bash
   cd .work/k8s-batch-by-group/corenet/20251126-080000/repos/multus-cni && git push <fork-remote> rebase/k8s-v0.34.2-20251126
   cd .work/k8s-batch-by-group/corenet/20251126-080000/repos/ovn-kubernetes && git push <fork-remote> rebase/k8s-v0.34.2-20251126
   cd .work/k8s-batch-by-group/corenet/20251126-080000/repos/cluster-network-operator && git push <fork-remote> rebase/k8s-v0.34.2-20251126
   ```
   Note: `<fork-remote>` is the discovered remote name for your fork (typically 'myfork' or similar).

   ## Detailed Logs
   - Clone logs: `.work/k8s-batch-by-group/corenet/20251126-080000/logs/*-clone.log`
   - Rebase logs: `.work/k8s-batch-by-group/corenet/20251126-080000/logs/*-rebase.log`
   - Audit reports: `.work/k8s-batch-by-group/corenet/20251126-080000/reports/*-audit.md`
   ```

2. **Save summary**:
   - File: `${WORKSPACE_DIR}/rebase-summary.md`
   - Also save JSON: `${WORKSPACE_DIR}/rebase-status.json` (updated with final results)

3. **Display summary to user**

### Step 7: Fork Repositories and Push Branches (if --create-pr specified)
1. **Get GitHub user**:
   ```bash
   # Verify gh CLI is installed and authenticated
   if ! command -v gh &> /dev/null; then
     echo "Error: gh CLI not found. Install from https://cli.github.com/"
     exit 1
   fi

   gh auth status || {
     echo "Error: Not authenticated with GitHub. Run: gh auth login"
     exit 1
   }
   ```

2. **Fork repositories if needed**:
   ```bash
   # Get current GitHub user
   GH_USER=$(gh api user -q .login)

   for repo in ${SUCCESS_REPOS}; do
     # Check if fork exists
     if ! gh repo view "${GH_USER}/${repo}" &>/dev/null; then
       echo "Forking ${UPSTREAM_ORG}/${repo}..."
       gh repo fork "${UPSTREAM_ORG}/${repo}" --clone=false
     fi

     # Discover or add fork remote
     cd "${WORKSPACE_DIR}/repos/${repo}"
     FORK_URL="git@github.com:${GH_USER}/${repo}.git"

     # Check if remote already exists for this URL
     FORK_REMOTE=$(git remote -v | grep "$FORK_URL" | awk '{print $1}' | head -1)

     if [ -z "$FORK_REMOTE" ]; then
       # No remote exists for fork URL, add one
       FORK_REMOTE="myfork"
       git remote add "$FORK_REMOTE" "$FORK_URL"
       echo "Added remote: $FORK_REMOTE -> $FORK_URL"
     else
       echo "Using existing remote: $FORK_REMOTE -> $FORK_URL"
     fi

     # Store remote name for later use
     echo "$FORK_REMOTE" > "${WORKSPACE_DIR}/.remote-${repo}"
   done
   ```

3. **Request confirmation before pushing**:
   - Display summary of repos ready to push
   - Ask: "Ready to push ${#SUCCESS_REPOS[@]} branches to your fork (${GH_USER})? [yes/no]"
   - If "no", skip pushing (PRs can be created manually later)
   - If "yes", continue to push

4. **Push branches to fork**:
   ```bash
   for repo in ${SUCCESS_REPOS}; do
     cd "${WORKSPACE_DIR}/repos/${repo}"

     # Retrieve the discovered remote name
     FORK_REMOTE=$(cat "${WORKSPACE_DIR}/.remote-${repo}")

     # Verify remote exists before pushing
     if ! git remote get-url "$FORK_REMOTE" &>/dev/null; then
       echo "✗ Remote $FORK_REMOTE not found for ${repo}, skipping push"
       continue
     fi

     # Push to fork
     git push "$FORK_REMOTE" ${BRANCH_NAME}
     echo "✓ Pushed to ${GH_USER}/${repo} (remote: $FORK_REMOTE)"
   done
   ```

5. **Track push results**:
   - Record which repos were successfully pushed
   - Log any push failures
   - Update `rebase-status.json` with push status and fork info

### Step 8: Create Pull Requests (if --create-pr specified)
1. **Check prerequisites**:
   ```bash
   # Verify gh CLI is installed and authenticated
   if ! command -v gh &> /dev/null; then
     echo "Error: gh CLI not found. Install from https://cli.github.com/"
     exit 1
   fi

   gh auth status || {
     echo "Error: Not authenticated with GitHub. Run: gh auth login"
     exit 1
   }

   # Get GitHub user for fork-based PRs
   if [ "${USE_FORK}" = "true" ]; then
     GH_USER=$(gh api user -q .login)
   fi
   ```

2. **Generate PR descriptions for each repo**:
   ```bash
   # For each successful repo, create PR body
   for repo in ${SUCCESS_REPOS}; do
     PR_BODY_FILE="${WORKSPACE_DIR}/reports/${repo}-pr-body.md"

     cat > "$PR_BODY_FILE" <<EOF
   ## Summary

   Bump Kubernetes dependencies to ${TARGET_VERSION} as part of coordinated ${GROUP_NAME} group upgrade.

   ## Changes

   - k8s.io/api: ${OLD_VERSION} → ${TARGET_VERSION}
   - k8s.io/apimachinery: ${OLD_VERSION} → ${TARGET_VERSION}
   - k8s.io/client-go: ${OLD_VERSION} → ${TARGET_VERSION}
   - [Additional k8s.io modules]

   ## Risk Assessment

   ${REPO_RISK_LEVEL}

   $(cat ${WORKSPACE_DIR}/reports/${repo}-audit.md)

   ## Test Results

   - Build: ${BUILD_STATUS}
   - Tests: ${TEST_STATUS}

   ## Related PRs

   This is part of a coordinated upgrade across the ${GROUP_NAME} group:
   ${OTHER_PR_LINKS}

   ## Tracking

   ${JIRA_ISSUE_LINK}

   ---

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   EOF
   done
   ```

3. **Create PRs for each repository**:
   ```bash
   PR_URLS=()

   for repo in ${SUCCESS_REPOS}; do
     cd "${WORKSPACE_DIR}/repos/${repo}"

     # Determine PR head (fork or upstream branch)
     if [ "${USE_FORK}" = "true" ]; then
       # Fork-based PR: from user:branch to upstream:main
       # Dynamically discover default branch from upstream repo
       UPSTREAM_URL="git@github.com:${UPSTREAM_ORG}/${repo}.git"
       DEFAULT_BRANCH=$(git ls-remote --symref "${UPSTREAM_URL}" HEAD | \
         awk '/^ref:/ {sub("refs/heads/", "", $2); print $2}')

       PR_URL=$(gh pr create \
         --repo "${UPSTREAM_ORG}/${repo}" \
         --title "Bump Kubernetes dependencies to ${TARGET_VERSION}" \
         --body-file "${WORKSPACE_DIR}/reports/${repo}-pr-body.md" \
         --head "${GH_USER}:${BRANCH_NAME}" \
         --base "${DEFAULT_BRANCH}" \
         --draft 2>&1)
     else
       # Direct PR: from branch to main in same repo
       PR_URL=$(gh pr create \
         --title "Bump Kubernetes dependencies to ${TARGET_VERSION}" \
         --body-file "${WORKSPACE_DIR}/reports/${repo}-pr-body.md" \
         --draft \
         --label "dependencies,kubernetes" 2>&1)
     fi

     if [[ "$PR_URL" =~ ^https://github.com ]]; then
       echo "✓ Created PR for ${repo}: ${PR_URL}"
       PR_URLS+=("${repo}|${PR_URL}")

       # Save PR URL to status file
       jq ".repos[] | select(.name == \"${repo}\") | .pr_url = \"${PR_URL}\"" \
         "${WORKSPACE_DIR}/rebase-status.json" > tmp.json
       mv tmp.json "${WORKSPACE_DIR}/rebase-status.json"
     else
       echo "✗ Failed to create PR for ${repo}: ${PR_URL}"
     fi
   done
   ```

4. **Update PR descriptions with cross-references**:
   ```bash
   # Now that all PRs are created, update each PR body to include links to related PRs
   for pr_entry in "${PR_URLS[@]}"; do
     repo="${pr_entry%%|*}"
     pr_url="${pr_entry##*|}"

     # Build list of related PRs
     related_prs=""
     for other_pr in "${PR_URLS[@]}"; do
       other_repo="${other_pr%%|*}"
       other_url="${other_pr##*|}"
       if [ "$other_repo" != "$repo" ]; then
         related_prs="${related_prs}- ${other_repo}: ${other_url}\n"
       fi
     done

     # Update PR description with related PRs
     cd "${WORKSPACE_DIR}/repos/${repo}"

     # Get current PR body and append related PRs section
     pr_number=$(echo "$pr_url" | grep -oP '\d+$')
     gh pr edit $pr_number --body "$(gh pr view $pr_number --json body -q .body | sed "s|\${OTHER_PR_LINKS}|${related_prs}|")"
   done
   ```

5. **Display PR summary**:
   ```
   ✓ Created 3 pull requests:

   - multus-cni: https://github.com/k8snetworkplumbingwg/multus-cni/pull/123
   - ovn-kubernetes: https://github.com/ovn-kubernetes/ovn-kubernetes/pull/456
   - cluster-network-operator: https://github.com/openshift/cluster-network-operator/pull/789
   ```

### Step 9: Create JIRA Issue (if --create-jira specified)
1. **Check prerequisites**:
   ```bash
   # Verify JIRA CLI tools or credentials
   if [ -z "$JIRA_API_TOKEN" ] || [ -z "$JIRA_URL" ] || [ -z "$JIRA_USER" ]; then
     echo "Error: JIRA credentials not configured"
     echo "Set JIRA_URL, JIRA_USER, and JIRA_API_TOKEN environment variables"
     exit 1
   fi
   ```

2. **Determine JIRA project and issue type**:
   - Ask user for project key (e.g., "OCPBUGS", "CNV", "STOR")
   - Default issue type: "Story" or "Task"
   - Ask user for component (optional)

3. **Generate JIRA issue description**:
   ```bash
   JIRA_DESC_FILE="${WORKSPACE_DIR}/jira-issue-description.md"

   cat > "$JIRA_DESC_FILE" <<EOF
   h2. Summary

   Bump Kubernetes dependencies to ${TARGET_VERSION} across ${GROUP_NAME} repositories.

   h2. Scope

   This issue tracks the coordinated upgrade of Kubernetes dependencies across ${#SUCCESS_REPOS[@]} repositories in the ${GROUP_NAME} group:

   $(for repo in ${SUCCESS_REPOS}; do echo "* ${repo}"; done)

   h2. Target Version

   * *From*: ${OLD_VERSION} (varies by repo)
   * *To*: ${TARGET_VERSION}

   h2. Risk Assessment

   * *Overall Risk*: ${OVERALL_RISK_LEVEL}
   * *High-risk repos*: ${HIGH_RISK_REPOS}

   $(cat ${WORKSPACE_DIR}/rebase-summary.md | grep -A 20 "Common Breaking Changes")

   h2. Pull Requests

   $(for pr_entry in "${PR_URLS[@]}"; do
     repo="${pr_entry%%|*}"
     url="${pr_entry##*|}"
     echo "* [${repo}|${url}]"
   done)

   h2. Test Results

   $(cat ${WORKSPACE_DIR}/rebase-summary.md | grep -A 30 "Repository Results")

   h2. Next Steps

   # Review and approve all PRs
   # Run integration tests across networking stack
   # Merge PRs in dependency order
   # Monitor for issues in CI

   h2. Artifacts

   * Workspace: {{${WORKSPACE_DIR}}}
   * Summary Report: [rebase-summary.md|attachment]

   ---

   🤖 Generated with [Claude Code|https://claude.com/claude-code]
   EOF
   ```

4. **Create JIRA issue via API**:
   ```bash
   # Create the issue
   JIRA_RESPONSE=$(curl -s -X POST \
     -H "Content-Type: application/json" \
     -u "${JIRA_USER}:${JIRA_API_TOKEN}" \
     "${JIRA_URL}/rest/api/2/issue" \
     -d "{
       \"fields\": {
         \"project\": {
           \"key\": \"${JIRA_PROJECT}\"
         },
         \"summary\": \"Bump Kubernetes dependencies to ${TARGET_VERSION} (${GROUP_NAME} group)\",
         \"description\": $(cat "$JIRA_DESC_FILE" | jq -Rs .),
         \"issuetype\": {
           \"name\": \"Story\"
         },
         \"components\": [{
           \"name\": \"${JIRA_COMPONENT}\"
         }],
         \"labels\": [\"kubernetes-upgrade\", \"dependencies\", \"${GROUP_NAME}-group\"]
       }
     }")

   JIRA_ISSUE_KEY=$(echo "$JIRA_RESPONSE" | jq -r '.key')
   JIRA_ISSUE_URL="${JIRA_URL}/browse/${JIRA_ISSUE_KEY}"
   ```

5. **Link JIRA to all PRs**:
   ```bash
   # Update each PR description to include JIRA link
   for pr_entry in "${PR_URLS[@]}"; do
     repo="${pr_entry%%|*}"
     pr_url="${pr_entry##*|}"

     cd "${WORKSPACE_DIR}/repos/${repo}"
     pr_number=$(echo "$pr_url" | grep -oP '\d+$')

     # Update PR body with JIRA link
     gh pr edit $pr_number --body "$(gh pr view $pr_number --json body -q .body | sed "s|\${JIRA_ISSUE_LINK}|Tracking: ${JIRA_ISSUE_URL}|")"
   done
   ```

6. **Add remote links in JIRA**:
   ```bash
   # Link each PR to the JIRA issue
   for pr_entry in "${PR_URLS[@]}"; do
     repo="${pr_entry%%|*}"
     pr_url="${pr_entry##*|}"

     curl -s -X POST \
       -H "Content-Type: application/json" \
       -u "${JIRA_USER}:${JIRA_API_TOKEN}" \
       "${JIRA_URL}/rest/api/2/issue/${JIRA_ISSUE_KEY}/remotelink" \
       -d "{
         \"object\": {
           \"url\": \"${pr_url}\",
           \"title\": \"PR: ${repo}\",
           \"icon\": {
             \"url16x16\": \"https://github.githubassets.com/favicon.ico\"
           }
         }
       }"
   done
   ```

7. **Display JIRA summary**:
   ```
   ✓ Created JIRA issue: ${JIRA_ISSUE_KEY}

   URL: ${JIRA_ISSUE_URL}

   Linked to ${#PR_URLS[@]} pull requests.
   ```

8. **Save JIRA details**:
   ```bash
   # Update rebase-status.json with JIRA info
   jq ".jira_issue = {\"key\": \"${JIRA_ISSUE_KEY}\", \"url\": \"${JIRA_ISSUE_URL}\"}" \
     "${WORKSPACE_DIR}/rebase-status.json" > tmp.json
   mv tmp.json "${WORKSPACE_DIR}/rebase-status.json"
   ```

### Step 10: Display Final Summary
1. **Show completion summary**:
   ```
   ========================================
   Batch Rebase Complete!
   ========================================

   Group: ${GROUP_NAME}
   Target Version: ${TARGET_VERSION}

   Repositories: ${#SUCCESS_REPOS[@]} successful, ${#FAILED_REPOS[@]} failed

   Pull Requests: ${#PR_URLS[@]} created
   JIRA Issue: ${JIRA_ISSUE_URL}

   Workspace: ${WORKSPACE_DIR}
   Summary: ${WORKSPACE_DIR}/rebase-summary.md

   Next steps:
   1. Review PRs and address any feedback
   2. Run integration tests
   3. Merge PRs in dependency order
   4. Update JIRA issue with results
   ========================================
   ```

## Return Value

- **Format**: Group-wide summary with:
  - Per-repository results table
  - Overall success/failure counts
  - Common issues across repos
  - PR URLs (if `--create-pr` was used)
  - JIRA issue URL (if `--create-jira` was used)
  - Next action recommendations
  - Workspace location for review

- **Output locations**:
  - Summary: `${WORKSPACE_DIR}/rebase-summary.md`
  - Individual audit reports: `${WORKSPACE_DIR}/reports/${REPO_NAME}-audit.md`
  - PR descriptions: `${WORKSPACE_DIR}/reports/${REPO_NAME}-pr-body.md`
  - JIRA description: `${WORKSPACE_DIR}/jira-issue-description.md`
  - Rebase logs: `${WORKSPACE_DIR}/logs/${REPO_NAME}-*.log`
  - Cloned repositories: `${WORKSPACE_DIR}/repos/${REPO_NAME}/`
  - Status tracking: `${WORKSPACE_DIR}/rebase-status.json` (includes PR URLs and JIRA issue details)

## Repository Group Configuration

Repository groups are defined in `plugins/k8s-bumpup/.claude-plugin/repo-groups.json`:

```json
{
  "groups": {
    "corenet": {
      "description": "Core networking OpenShift repositories",
      "repos": [
        {
          "name": "multus-cni",
          "url": "git@github.com:k8snetworkplumbingwg/multus-cni.git"
        },
        {
          "name": "ovn-kubernetes",
          "url": "git@github.com:ovn-kubernetes/ovn-kubernetes.git"
        }
      ]
    }
  }
}
```

**Note**:
- Uses **SSH URLs** (`git@github.com:org/repo.git`) for better authentication with SSH keys
- The `branch` field is optional - the command auto-detects the default branch from the remote repository
- This makes the configuration more maintainable as repositories migrate from `master` to `main`

To add a new group or modify existing ones, edit this configuration file.

## Error Handling

1. **Group not found**:
   - Error: "Group '${GROUP_NAME}' not found in configuration"
   - List available groups
   - Exit gracefully

2. **Clone failures**:
   - Log error and mark repo as SKIPPED
   - Continue with other repositories
   - Include skipped repos in final summary

3. **No k8s dependencies**:
   - Skip repository if no k8s.io modules found
   - Log as INFO, not error
   - Mark as SKIPPED in summary

4. **Build/test failures**:
   - Pause workflow at failed repo
   - Allow user to skip, fix manually, or abort
   - Do not rollback successful repos

5. **Partial success**:
   - Generate summary showing mixed results
   - Clearly indicate which repos succeeded/failed
   - Provide next steps for failed repos

6. **Fork handling** (if --create-pr specified):
   - **Fork already exists**: Detected and skipped automatically (expected behavior, not an error)
   - **Fork creation failures**: Logged and workflow continues with remaining repos
   - **Remote already exists**: Handled gracefully with `|| true` (no error, continues normally)
   - **Missing GitHub authentication**: Requires `gh auth login` before using `--create-pr`

7. **PR creation failures** (if --create-pr specified):
   - Log which PRs failed to create
   - Continue creating remaining PRs
   - Skip cross-referencing for failed PRs
   - Include failure details in final summary

8. **JIRA creation failures** (if --create-jira specified):
   - Log error details
   - Save issue description to file for manual creation
   - Continue workflow (non-blocking)
   - Provide manual JIRA creation instructions

9. **Missing credentials**:
   - **GitHub**: Check `gh auth status` before creating PRs
   - **JIRA**: Verify `JIRA_URL`, `JIRA_USER`, `JIRA_API_TOKEN` environment variables
   - Provide clear error messages with setup instructions

## Examples

1. **Complete workflow with PR and JIRA creation**:
   ```
   /k8s-bumpup:batch-by-group corenet --create-pr --create-jira
   ```
   Fetches the latest stable Kubernetes release and rebases all corenet repos.
   Creates PRs and a tracking JIRA issue.

2. **Basic rebase (local only, no PR/JIRA creation)**:
   ```
   /k8s-bumpup:batch-by-group corenet
   ```
   Fetches latest Kubernetes version and rebases all corenet repos. Branches are created locally but not pushed.

3. **Rebase with automatic PR creation**:
   ```
   /k8s-bumpup:batch-by-group operators --create-pr
   ```
   Fetches latest version and rebases all operator repos, then creates draft PRs with cross-references.

4. **Complete workflow for storage group**:
   ```
   /k8s-bumpup:batch-by-group storage --create-pr --create-jira
   ```
   Complete workflow:
   - Fetches latest Kubernetes version
   - Rebases all storage repos
   - Creates PRs for each repo
   - Creates one JIRA issue tracking all PRs
   - Links PRs to JIRA and vice versa

5. **JIRA only (after manual PR creation)**:
   ```
   /k8s-bumpup:batch-by-group operators --create-jira
   ```
   Rebases repos and creates JIRA issue without auto-creating PRs

6. **Custom workspace**:
   ```
   /k8s-bumpup:batch-by-group corenet --workspace-dir /tmp/rebase-work --create-pr
   ```
   Uses custom workspace directory and creates PRs

7. **Dry-run mode**:
   ```
   /k8s-bumpup:batch-by-group monitoring --dry-run
   ```
   Audits the latest version upgrade without making any changes

8. **List available groups**:
   ```
   /k8s-bumpup:batch-by-group --list
   ```
   Displays all available repository groups

## Notes

- **Always uses latest available version**: This command fetches and uses the latest versions, ensuring Kubernetes and client libraries are in sync
- **Smart version syncing**:
  - Fetches latest Kubernetes release (e.g., v1.34.3)
  - Queries available k8s.io/api versions to find latest stable v0.34.x (e.g., v0.34.2)
  - If client library lags behind (v0.34.2 vs v1.34.3), automatically uses matching K8s version (v1.34.2)
  - Ensures consistency: Both Kubernetes v1.34.2 ↔ client libraries v0.34.2
  - Prevents mismatches that could cause compatibility issues
- This command clones fresh copies of repositories
- Original repositories are not modified
- All work happens in isolated workspace
- Branches are automatically pushed to your fork when using `--create-pr`
- Without `--create-pr`, branches remain local only
- Safe to re-run - creates new workspace each time
- Workspace preserved for review/debugging
- Ideal for coordinated upgrades across related components
- Respects each repository's .gitignore for vendor/ directories

### Key Features

1. **Smart version syncing**: Automatically syncs Kubernetes and client library versions - if client libraries lag behind, uses matching older K8s release to ensure compatibility
2. **Multiple go.mod support**: Automatically finds and updates ALL go.mod files in a repository (e.g., ovn-kubernetes has 3: go-controller/, test/e2e/, test/conformance/)
3. **Dual versioning**: Correctly handles both k8s.io/kubernetes (v1.x) and k8s.io/api (v0.x) version schemes
4. **Auto-detect default branch**: No need to specify `master` vs `main` in config - automatically detected
5. **Automatic forking**: With `--create-pr`, automatically forks repos (if not already forked) and creates PRs from your fork
6. **Smart test handling**: Detects pre-existing test failures vs new failures introduced by the upgrade
7. **Progress tracking**: Shows elapsed time and progress for long-running tests (e.g., ovn-kubernetes pkg/ovn: 552s)
8. **Already up-to-date detection**: Skips repositories that are already at the target version
9. **Test performance metrics**: Logs slowest test packages in summary report
10. **Dry-run mode**: Use `--dry-run` to audit without making changes

### PR Creation
- Requires `gh` CLI installed and authenticated (`gh auth login`)
- Creates draft PRs by default
- PRs include cross-references to related PRs in the same group
- PRs are labeled with `dependencies` and `kubernetes`
- If `--create-jira` is also specified, PRs link to the JIRA issue
- Creates fork-based PRs: from `user:branch` to `upstream:main` (repositories are automatically forked if needed)

### JIRA Creation
- Requires environment variables: `JIRA_URL`, `JIRA_USER`, `JIRA_API_TOKEN`
- Creates a single Story/Task tracking all repositories
- Includes links to all PRs (if `--create-pr` was used)
- Includes risk assessment and test results
- Automatically adds remote links from JIRA to each PR
- Issue is labeled with `kubernetes-upgrade`, `dependencies`, and `${GROUP_NAME}-group`

## See Also
- `/k8s-bumpup:rebase-repo` - Rebase single repository or multiple repositories
