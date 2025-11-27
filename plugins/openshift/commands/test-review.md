---
description: Review Ginkgo test code changes in current branch for naming violations and best practices
argument-hint: [base-branch]
---

## Name
openshift:test-review

## Synopsis
```
/openshift:test-review [base-branch]
```

## Description

The `test-review` command analyzes test code changes in the current git branch to identify potential issues with Ginkgo test naming and structure. It performs two main types of validation:

1. **Component Mapping**: Ensures new tests have proper component tags (preferably `[Jira:"component"]`) to map test failures to the correct team
2. **Test Name Stability**: Ensures test names are stable and deterministic by detecting potentially random or dynamic strings

This command is designed for reviewing test changes in OpenShift repositories (commonly openshift/origin) that use the Ginkgo testing framework, where test names are constructed using nested blocks of `Describe()`, `Context()`, `When()`, and `It()` functions.

## Implementation

The command performs the following steps:

1. **Determine Base Branch**:
   - If user provides `base-branch` argument, use it directly (e.g., `up/main`, `origin/master`)
   - Validate the provided branch exists: `git rev-parse --verify <base-branch> 2>/dev/null`
   - If no argument provided, auto-detect upstream branch:
     - Check for these remotes in order: `up`, `upstream`, `origin`
     - Check for these branch names in order: `master`, `main`
     - Use the first combination that exists (e.g., `up/master`, `up/main`, `upstream/master`, `origin/main`, etc.)
     - Command to check: `git rev-parse --verify <remote>/<branch> 2>/dev/null`
   - If auto-detection fails, error and ask user to specify base branch explicitly

2. **Identify Code Changes**:
   - Run `git diff <base-branch>...HEAD --name-only` to find all changed files
   - Filter for Go test files (files ending in `_test.go` or in `test/` directories)
   - Read commit messages from the current branch using `git log <base-branch>..HEAD --oneline`

3. **Detect New Tests**:
   - For each changed test file, run `git diff <base-branch>...HEAD -- <file>` to see the actual changes
   - Look for lines that are additions (start with `+`) containing Ginkgo test functions:
     - `Describe(`
     - `Context(`
     - `When(`
     - `It(`
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

6. **Generate Report**:
   - List all test files with changes
   - For each file, show:
     - New or modified test cases detected
     - Component mapping status and any violations
     - Any naming violations found with specific line numbers and code snippets
     - Suggested fixes for each violation
   - If no new tests found, report that clearly
   - If tests found but no violations, provide a summary of tests reviewed

7. **Provide Recommendations**:
   - Suggest adding `[Jira:"component"]` tags for tests missing component mapping
   - Suggest rewriting test names to be static and descriptive
   - Reference the test naming guidelines from openshift/origin
   - Link to relevant documentation if available

## Return Value

**Format**: Markdown report with the following sections:

1. **Summary**: Number of test files changed, new tests added, violations found (both component mapping and naming)
2. **Commit Context**: List of commit messages in the branch
3. **Test Files Changed**: List of all test files modified
4. **Component Mapping Violations** (if any):
   - File path and line number
   - Test name
   - Issue: Missing tag, invalid component, or unverified legacy tag
   - Suggested fix
5. **Naming Violations** (if any):
   - File path and line number
   - Original test name code
   - Explanation of the violation
   - Suggested fix
6. **Clean Tests** (if any): List of new tests with no violations
7. **Recommendations**: Best practices and next steps

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

   Expected output when violations are found:
   ```markdown
   ## Test Review Report

   ### Summary
   - Comparing against: up/master
   - Test files changed: 2
   - New tests detected: 5
   - Component mapping violations: 2
   - Naming violations: 1

   ### Commit Context
   - abc123 Add new pod creation tests
   - def456 Fix namespace isolation test

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
   - If using legacy `[sig-*]` or `[bz-*]` tags, ensure they exist elsewhere in the repository
   - Remove dynamic content from test names (variables, timestamps, specific values)
   - Use the Jira plugin to verify valid component names: `/component-health:list-components`
   - See https://github.com/openshift/origin/blob/master/test/extended/README.md for test naming guidelines
   ```

## Arguments

- **$1** (base-branch, optional): The base branch to compare against (e.g., `up/main`, `origin/master`, `upstream/main`). If not provided, the command will auto-detect the upstream branch by checking for remotes (`up`, `upstream`, `origin`) and branch names (`master`, `main`) in order.

## Prerequisites

- Must be run from within a git repository
- Must have a current branch that differs from the upstream branch
- Repository should contain Ginkgo-based Go tests

## Notes

- **Branch detection priority**:
  - If base branch is provided as argument, it takes priority and is validated
  - If not provided, auto-detects by checking remotes (`up`, `upstream`, `origin`) and branch names (`master`, `main`)
  - Uses the first valid combination found
  - Displays which branch comparison is being used in the report
- **Recommended usage**: If you have multiple remotes or stale branches, explicitly specify the base branch (e.g., `/openshift:test-review up/main`) to ensure accurate comparison
- **Component validation**:
  - If the Jira MCP plugin is enabled, the command will validate `[Jira:"component"]` tags against actual OCPBUGS components
  - If Jira plugin is not available, the command will still check for the presence of component tags but cannot validate them
  - Legacy `[sig-*]` and `[bz-*]` tags are verified by checking if they exist elsewhere in the repository
- **Component tag format**: The `[Jira:"component"]` tag can appear anywhere in the test name (typically at the end)
- **Format strings**: `fmt.Sprintf()` is allowed when all arguments are string literals (e.g., `fmt.Sprintf("[Jira:%q]", "kube-apiserver")` is acceptable for proper quoting)
- **Dynamic content detection**: Only flags format strings that use variables or function calls, not static string literals
- Only analyzes `.go` files in test-related paths
- Does not execute tests, only performs static analysis of test code
- Focuses specifically on component mapping and test naming violations; does not perform comprehensive code review
