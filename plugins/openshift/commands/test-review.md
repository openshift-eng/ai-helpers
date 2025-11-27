---
description: Review Ginkgo test code changes in current branch or PR for naming violations and best practices
argument-hint: [base-branch-or-pr-url]
---

## Name
openshift:test-review

## Synopsis
```
/openshift:test-review [base-branch-or-pr-url]
```

## Description

The `test-review` command analyzes test code changes in the current git branch or a GitHub pull request to identify potential issues with Ginkgo test naming and structure. It performs three main types of validation:

1. **Component Mapping**: Ensures new tests have proper component tags (preferably `[Jira:"component"]`) to map test failures to the correct team
2. **Test Name Stability**: Ensures test names are stable and deterministic by detecting potentially random or dynamic strings
3. **Parallel Safety**: Validates that tests requiring serial execution have the `[Serial]` tag, and that tests with `[Serial]` actually need it

This command is designed for reviewing test changes in OpenShift repositories (commonly openshift/origin) that use the Ginkgo testing framework, where test names are constructed using nested blocks of `Describe()`, `Context()`, `When()`, and `It()` functions.

## Implementation

The command performs the following steps:

1. **Determine Source of Changes**:
   - Check if argument is provided
   - If argument looks like a URL (contains `github.com/` and `/pull/`):
     - **PR Mode**: Parse the PR URL to extract owner, repo, and PR number
     - Use GitHub CLI (`gh`) to fetch PR information:
       - `gh pr view <PR-number> --repo <owner>/<repo> --json files,baseRefName,headRefName,commits`
     - Get list of changed files from the PR
     - Get base branch and head branch from PR metadata
     - For each changed test file, fetch the file content from both base and head
   - Else if argument is a branch name (e.g., `up/main`, `origin/master`):
     - **Branch Mode**: Validate the branch exists: `git rev-parse --verify <base-branch> 2>/dev/null`
     - Use git diff to compare current branch against provided base branch
   - Else if no argument provided:
     - **Auto-detect Mode**: Auto-detect upstream branch:
       - Check for these remotes in order: `up`, `upstream`, `origin`
       - Check for these branch names in order: `master`, `main`
       - Use the first combination that exists
       - Command to check: `git rev-parse --verify <remote>/<branch> 2>/dev/null`
   - If all methods fail, error and ask user to specify base branch or PR URL explicitly

2. **Identify Code Changes**:
   - **If PR Mode**:
     - Changed files are already available from `gh pr view` JSON output
     - Filter for Go files that may contain tests:
       - Files ending in `.go` (including but not limited to `_test.go`)
       - Located in `test/` directories (common in openshift/origin)
       - Located in directories containing test code (e.g., `test/extended/`, `e2e/`)
     - Commit messages available from PR commits in JSON output
   - **If Branch/Auto-detect Mode**:
     - Run `git diff <base-branch>...HEAD --name-only` to find all changed files
     - Filter for Go files that may contain tests:
       - Files ending in `.go` (including but not limited to `_test.go`)
       - Located in `test/` directories
       - Located in directories containing test code
     - Read commit messages from the current branch using `git log <base-branch>..HEAD --oneline`

3. **Detect New Tests**:
   - **If PR Mode**:
     - For each changed Go file, use `gh api` to get the diff:
       - `gh api repos/<owner>/<repo>/pulls/<pr-number>/files --jq '.[] | select(.filename == "<file>") | .patch'`
     - Parse the unified diff to find additions
   - **If Branch/Auto-detect Mode**:
     - For each changed Go file, run `git diff <base-branch>...HEAD -- <file>` to see the actual changes
   - Look for lines that are additions (start with `+`) containing Ginkgo test functions:
     - `Describe(`
     - `Context(`
     - `When(`
     - `It(`
   - **Note**: In OpenShift test projects (e.g., openshift/origin), Ginkgo tests often appear in `.go` files without the `_test.go` suffix, particularly in `test/extended/` and similar directories
   - These indicate new or modified test cases
   - Extract the full test name by combining all nested blocks (Describe/Context/When/It)

4. **Validate Component Mapping**:
   For each new test detected, verify it has proper component tagging:

   **Preferred: [Jira:"component"] tag**
   - Look for `[Jira:"component-name"]` tag in the test name
   - If Jira MCP plugin is enabled, validate the component exists:
     - Query OCPBUGS project components using the Jira MCP search
     - Verify the component name matches exactly (case-sensitive)
     - If component doesn't exist, flag as violation
   - Example: `It("should create pod [Jira:\"kube-apiserver\"]")`

   **Alternative: [sig-*] or [bz-*] tags**
   - Look for `[sig-<name>]` or `[bz-<name>]` tags
   - Verify the tag is used elsewhere in the repository:
     - Run `git grep -r "\[sig-<name>\]" test/` or `git grep -r "\[bz-<name>\]" test/`
     - If tag exists in other tests, it's valid
     - If tag is unique to this test, flag as potential made-up tag
   - Examples: `[sig-network]`, `[bz-storage]`

   **Missing component tag**: Flag as violation if no component tag found

5. **Analyze Test Names for Dynamic Content**:
   For each detected test definition, check if the test name contains potentially random or dynamic strings:

   **❌ VIOLATIONS TO FLAG:**
   - **String formatting with variables**: `fmt.Sprintf()` with variables that could be dynamic/random
   - **Variable interpolation**: Variables used in test name strings (especially runtime-generated values)
   - **Generated identifiers**: UUIDs, random strings, timestamps
   - **Resource names**: Pod names, namespace names with dynamic suffixes
   - **Numeric values**: Specific limits, counts, durations that might change

   **IMPORTANT**: `fmt.Sprintf()` is acceptable when ALL arguments are string literals (constants). This is commonly used for proper quoting in tags like `[Jira:%q]`.

   **Examples of violations:**
   ```go
   // BAD: Contains fmt.Sprintf with variable
   It(fmt.Sprintf("should create pod %s successfully", podName))

   // BAD: Variable in string
   Describe("Testing namespace " + namespaceName)

   // BAD: Dynamic timestamp or function call
   When(fmt.Sprintf("at time %v", time.Now()))

   // BAD: Specific numeric limit that might change
   It("should create pod within 15 seconds")
   ```

   **✅ ACCEPTABLE patterns:**
   ```go
   // GOOD: Static, descriptive name
   It("should create pod successfully")

   // GOOD: Generic description
   Describe("Testing namespace isolation")

   // GOOD: Relative time description
   It("should create pod within a reasonable timeframe")

   // GOOD: fmt.Sprintf with only string literals (common for [Jira] tags)
   It(fmt.Sprintf("should create pod successfully [Jira:%q]", "kube-apiserver"))

   // GOOD: Format string with literal arguments for proper quoting
   Describe(fmt.Sprintf("[sig-%s] Pod creation", "network"))
   ```

6. **Validate Parallel Safety**:
   For each new test, analyze the test code to determine if it can safely run in parallel with other tests:

   **Indicators that a test NEEDS `[Serial]` tag:**
   - **MachineConfig operations**: Creating, updating, or deleting MachineConfig or MachineConfigPool resources
   - **Node modifications**: Rebooting nodes, draining nodes, cordoning/uncordoning, changing node labels that affect scheduling
   - **Cluster-wide configuration**: Modifying cluster operators, cluster-scoped resources, or global settings
   - **Resource quota/limits**: Setting cluster-wide quotas or limits that could affect other tests
   - **Network policies**: Cluster-wide network policies or CNI configuration changes
   - **API server configuration**: Changes to API server settings, admission plugins, or authentication
   - **Storage provisioner changes**: Modifying default storage classes or provisioner settings
   - **Cluster upgrade operations**: Any operations that trigger cluster version changes

   **Indicators that `[Serial]` is NOT needed (safe for parallel):**
   - Test operates only in its own namespace
   - Creates only namespaced resources (pods, services, deployments, etc.)
   - Does not modify nodes or cluster-wide settings
   - Uses isolated resources that don't interfere with other tests

   **Detection logic:**
   - Read the full test code (not just the name, but the actual implementation)
   - **If PR Mode**: Fetch complete file content from PR head branch using `gh api`
   - **If Branch Mode**: Read file from working directory or use `git show`
   - Search for keywords indicating cluster-wide operations:
     - `MachineConfig`, `MachineConfigPool`, `mc.machineconfiguration.openshift.io`
     - Node operations: `cordon`, `uncordon`, `drain`, `SchedulingDisabled`
     - Cluster operators: `clusteroperator`, `config.openshift.io`
     - Reboot: `reboot`, `systemctl reboot`
   - Check if test has `[Serial]` tag in name
   - Flag mismatches:
     - Test performs cluster-wide operations but lacks `[Serial]` tag
     - Test has `[Serial]` tag but only operates in its namespace

7. **Generate Report**:
   - List all test files with changes
   - For each file, show:
     - New or modified test cases detected
     - Component mapping status and any violations
     - Parallel safety status and any violations
     - Any naming violations found with specific line numbers and code snippets
     - Suggested fixes for each violation
   - If no new tests found, report that clearly
   - If tests found but no violations, provide a summary of tests reviewed

8. **Provide Recommendations**:
   - Suggest adding `[Jira:"component"]` tags for tests missing component mapping
   - Suggest adding or removing `[Serial]` tags based on test behavior analysis
   - Suggest rewriting test names to be static and descriptive
   - Reference the test naming guidelines from openshift/origin
   - Link to relevant documentation if available

## Return Value

**Format**: Markdown report with the following sections:

1. **Summary**: Number of test files changed, new tests added, violations found (component mapping, parallel safety, and naming)
2. **Commit Context**: List of commit messages in the branch
3. **Test Files Changed**: List of all test files modified
4. **Component Mapping Violations** (if any):
   - File path and line number
   - Test name
   - Issue: Missing tag, invalid component, or unverified legacy tag
   - Suggested fix
5. **Parallel Safety Violations** (if any):
   - File path and line number
   - Test name
   - Issue: Missing `[Serial]` tag when needed, or unnecessary `[Serial]` tag
   - Evidence from code analysis (cluster-wide operations detected)
   - Suggested fix
6. **Naming Violations** (if any):
   - File path and line number
   - Original test name code
   - Explanation of the violation
   - Suggested fix
7. **Clean Tests** (if any): List of new tests with no violations
8. **Recommendations**: Best practices and next steps

## Examples

1. **Review current branch with auto-detection**:
   ```
   /openshift:test-review
   ```

2. **Review current branch against specific base branch**:
   ```
   /openshift:test-review up/main
   ```

3. **Review against a different upstream remote**:
   ```
   /openshift:test-review upstream/master
   ```

4. **Review a GitHub pull request**:
   ```
   /openshift:test-review https://github.com/openshift/origin/pull/305390
   ```

5. **Review a PR from a different repository**:
   ```
   /openshift:test-review https://github.com/openshift/kubernetes/pull/12345
   ```

   Expected output when violations are found:
   ```markdown
   ## Test Review Report

   ### Summary
   - Source: PR #305390 (openshift/origin)
   - Comparing: base branch `master` vs head branch `my-feature`
   - Test files changed: 3
   - New tests detected: 6
   - Component mapping violations: 2
   - Parallel safety violations: 2
   - Naming violations: 1

   ### Commit Context
   - abc123 Add new pod creation tests
   - def456 Fix namespace isolation test
   - ghi789 Add MachineConfig test

   ### Component Mapping Violations

   #### test/extended/pods/creation_test.go:32
   Test name: "should create pod successfully"

   **Issue**: Test is missing a component mapping tag. Tests should include a `[Jira:"component"]` tag to map failures to the appropriate team.

   **Suggested fix**:
   ```go
   It("should create pod successfully [Jira:\"kube-apiserver\"]")
   ```

   #### test/extended/networking/isolation_test.go:78
   Test name: "should isolate traffic between namespaces [Jira:\"network-edge\"]"

   **Issue**: Component "network-edge" does not exist in OCPBUGS project. Valid components can be found using the Jira plugin.

   **Suggested fix**: Verify the correct component name (e.g., `[Jira:"Networking"]` or similar).

   ### Parallel Safety Violations

   #### test/extended/machineconfig/rollout_test.go:56
   Test name: "should apply custom MachineConfig and wait for rollout [Jira:\"MachineConfig\"]"

   **Issue**: Test performs cluster-wide operations that could affect other tests but is missing the `[Serial]` tag.

   **Evidence**: Test code contains:
   - `MachineConfig` resource creation
   - `MachineConfigPool` status check
   - Node reboot detection

   **Suggested fix**:
   ```go
   It("should apply custom MachineConfig and wait for rollout [Serial] [Jira:\"MachineConfig\"]")
   ```

   #### test/extended/pods/simple_test.go:23
   Test name: "should create and delete a simple pod [Serial] [Jira:\"kube-apiserver\"]"

   **Issue**: Test has `[Serial]` tag but only operates within its own namespace. This test can safely run in parallel.

   **Evidence**: Test code only:
   - Creates pod in test namespace
   - Waits for pod ready
   - Deletes pod
   - No cluster-wide operations detected

   **Suggested fix**:
   ```go
   It("should create and delete a simple pod [Jira:\"kube-apiserver\"]")
   ```

   ### Naming Violations

   #### test/extended/pods/creation_test.go:45
   ```go
   It(fmt.Sprintf("should create pod %s successfully", podName))
   ```

   **Issue**: Test name contains string formatting with variable `podName`, which makes the test name dynamic and unstable. Note: `fmt.Sprintf()` is acceptable when ALL arguments are string literals, but this uses a variable.

   **Suggested fix**:
   ```go
   It(fmt.Sprintf("should create pod successfully [Jira:%q]", "kube-apiserver"))
   ```

   ### Clean Tests
   - test/extended/storage/pvc_test.go:34 - `It(fmt.Sprintf("should provision persistent volume claim [Jira:%q]", "Storage"))`
   - test/extended/networking/dns_test.go:56 - `It("should resolve cluster DNS [Jira:\"Networking\"]")`
   - test/extended/auth/rbac_test.go:89 - `Describe(fmt.Sprintf("[sig-%s] RBAC permissions", "auth"))`

   ### Recommendations
   - Add `[Jira:"component"]` tags to all tests for proper component mapping (preferred)
   - Review parallel safety violations and add/remove `[Serial]` tags as needed:
     - Add `[Serial]` for tests that modify cluster-wide resources (MachineConfigs, nodes, cluster operators)
     - Remove `[Serial]` from tests that only operate within their namespace
   - If using legacy `[sig-*]` or `[bz-*]` tags, ensure they exist elsewhere in the repository
   - Remove dynamic content from test names (variables, timestamps, specific values)
   - Use the Jira plugin to verify valid component names: `/component-health:list-components`
   - See https://github.com/openshift/origin/blob/master/test/extended/README.md for test naming guidelines
   ```

## Arguments

- **$1** (base-branch-or-pr-url, optional): Either:
  - **GitHub PR URL**: Full URL to a pull request (e.g., `https://github.com/openshift/origin/pull/305390`). The command will fetch and analyze the PR changes using GitHub CLI.
  - **Base branch**: The base branch to compare against (e.g., `up/main`, `origin/master`, `upstream/main`). The command will compare the current branch against this base.
  - **Omit**: If not provided, the command will auto-detect the upstream branch by checking for remotes (`up`, `upstream`, `origin`) and branch names (`master`, `main`) in order.

## Prerequisites

- **For local branch analysis**:
  - Must be run from within a git repository
  - Must have a current branch that differs from the upstream branch
  - Repository should contain Ginkgo-based Go tests (typically in `test/` directories)
- **For PR analysis**:
  - GitHub CLI (`gh`) must be installed and authenticated
  - No local repository needed if reviewing a PR URL
- **General**:
  - Works with any Ginkgo test project structure (tests in `*_test.go` files or regular `.go` files)

## Notes

- **Mode detection**:
  - Automatically detects if argument is a PR URL (contains `github.com/` and `/pull/`)
  - PR mode uses GitHub CLI (`gh`) to fetch changes - no local clone needed
  - Branch mode requires local git repository
- **Branch detection priority** (for branch/auto-detect mode):
  - If base branch is provided as argument, it takes priority and is validated
  - If not provided, auto-detects by checking remotes (`up`, `upstream`, `origin`) and branch names (`master`, `main`)
  - Uses the first valid combination found
  - Displays which branch comparison is being used in the report
- **Recommended usage**:
  - Use PR URL when reviewing someone else's PR or when you don't have the code locally
  - Use base branch name when reviewing your local working branch
  - If you have multiple remotes or stale branches, explicitly specify the base branch (e.g., `/openshift:test-review up/main`)
- **Component validation**:
  - If the Jira MCP plugin is enabled, the command will validate `[Jira:"component"]` tags against actual OCPBUGS components
  - If Jira plugin is not available, the command will still check for the presence of component tags but cannot validate them
  - Legacy `[sig-*]` and `[bz-*]` tags are verified by checking if they exist elsewhere in the repository
- **Component tag format**: The `[Jira:"component"]` tag can appear anywhere in the test name (typically at the end)
- **Parallel safety validation**:
  - Analyzes actual test code (not just the name) to detect cluster-wide operations
  - Flags tests missing `[Serial]` when they perform operations that could affect other tests
  - Flags tests with unnecessary `[Serial]` tags that only operate in their namespace
  - Searches for keywords: MachineConfig, node operations, cluster operators, etc.
- **Format strings**: `fmt.Sprintf()` is allowed when all arguments are string literals (e.g., `fmt.Sprintf("[Jira:%q]", "kube-apiserver")` is acceptable for proper quoting)
- **Dynamic content detection**: Only flags format strings that use variables or function calls, not static string literals
- **Test file detection**:
  - Analyzes all `.go` files in test-related directories (not just `*_test.go` files)
  - OpenShift test projects often organize Ginkgo tests in regular `.go` files within `test/extended/` and similar directories
  - Detects tests by looking for Ginkgo functions (`Describe`, `Context`, `When`, `It`) rather than relying on file naming conventions
- Does not execute tests, only performs static analysis of test code
- Focuses specifically on component mapping, parallel safety, and test naming violations; does not perform comprehensive code review
