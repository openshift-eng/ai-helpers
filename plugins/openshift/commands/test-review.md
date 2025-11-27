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

The `test-review` command analyzes test code changes in the current git branch to identify potential issues with Ginkgo test naming and structure. It specifically focuses on ensuring test names are stable and deterministic by detecting potentially random or dynamic strings in test names.

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

3. **Analyze Test Names for Dynamic Content**:
   For each detected test definition, check if the test name contains potentially random or dynamic strings:

   **❌ VIOLATIONS TO FLAG:**
   - **String formatting with variables**: `fmt.Sprintf()`, `%s`, `%d`, `%v` in test names
   - **Variable interpolation**: Variables used in test name strings
   - **Generated identifiers**: UUIDs, random strings, timestamps
   - **Resource names**: Pod names, namespace names with dynamic suffixes
   - **Numeric values**: Specific limits, counts, durations that might change

   **Examples of violations:**
   ```go
   // BAD: Contains fmt.Sprintf with variable
   It(fmt.Sprintf("should create pod %s successfully", podName))

   // BAD: Variable in string
   Describe("Testing namespace " + namespaceName)

   // BAD: Dynamic timestamp
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
   ```

4. **Generate Report**:
   - List all test files with changes
   - For each file, show:
     - New or modified test cases detected
     - Any naming violations found with specific line numbers and code snippets
     - Suggested fixes for each violation
   - If no new tests found, report that clearly
   - If tests found but no violations, provide a summary of tests reviewed

5. **Provide Recommendations**:
   - Suggest rewriting test names to be static and descriptive
   - Reference the test naming guidelines from openshift/origin
   - Link to relevant documentation if available

## Return Value

**Format**: Markdown report with the following sections:

1. **Summary**: Number of test files changed, new tests added, violations found
2. **Commit Context**: List of commit messages in the branch
3. **Test Files Changed**: List of all test files modified
4. **Violations** (if any):
   - File path and line number
   - Original test name code
   - Explanation of the violation
   - Suggested fix
5. **Clean Tests** (if any): List of new tests with no violations
6. **Recommendations**: Best practices and next steps

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
   - Naming violations: 2

   ### Commit Context
   - abc123 Add new pod creation tests
   - def456 Fix namespace isolation test

   ### Violations Found

   #### test/extended/pods/creation_test.go:45
   ```go
   It(fmt.Sprintf("should create pod %s successfully", podName))
   ```

   **Issue**: Test name contains string formatting with variable `podName`, which makes the test name dynamic and unstable.

   **Suggested fix**:
   ```go
   It("should create pod successfully")
   ```

   ### Clean Tests
   - test/extended/networking/isolation_test.go:78 - "should isolate traffic between namespaces"
   - test/extended/storage/pvc_test.go:34 - "should provision persistent volume claim"

   ### Recommendations
   - Review the violations above and update test names to be static and descriptive
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
- Only analyzes `.go` files in test-related paths
- Does not execute tests, only performs static analysis of test code
- Focuses specifically on test naming violations; does not perform comprehensive code review
