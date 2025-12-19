---
description: Review Ginkgo test code changes in current branch or PR for naming violations and best practices
argument-hint: [base-branch-or-pr-url]
---

## Name
ci:pr-test-analysis

## Synopsis
```
/ci:pr-test-analysis [base-branch-or-pr-url]
```

## Description

The `ci:pr-test-analysis` command analyzes test code changes in the current git branch or a GitHub pull request to identify potential issues with Ginkgo test naming and structure, and detects changes that could break CI in different OpenShift topologies. It performs four main types of validation:

1. **Topology-Specific Risk Detection**: Identifies changes that could break CI in different OpenShift topologies
   - Detects memory/resource changes that could impact Single Node OpenShift, MicroShift, etc.
   - Flags high-risk changes and recommends comprehensive `/payload` testing
   - Extensible framework for teams to add topology-specific edge case detection
2. **Component Mapping**: Ensures tests have proper component tags to map test failures to the correct team
   - **NEW tests**: Must use `[Jira:"component"]` tags (required)
   - **MODIFIED tests**: May use existing `[sig-*]` or `[bz-*]` tags, but migration to `[Jira:"component"]` is encouraged
3. **Test Name Stability**: Ensures test names are stable and deterministic by detecting potentially random or dynamic strings
4. **Parallel Safety**: Validates that tests requiring serial execution have the `[Serial]` tag, and that tests with `[Serial]` actually need it

This command is designed for reviewing test changes in OpenShift repositories (commonly openshift/origin) that use the Ginkgo testing framework, where test names are constructed using nested blocks of `Describe()`, `Context()`, `When()`, and `It()` functions.

## Implementation

The command performs the following steps:

1. **Load OpenShift Testing Guidelines**:
   - Fetch the latest guidelines for OpenShift test conventions from the enhancements repository
   - Use `curl --connect-timeout 5 --max-time 10` to download: `https://github.com/openshift/enhancements/blob/master/dev-guide/test-conventions.md`
   - Parse the document to extract:
     - Testing requirements for OpenShift features
     - Best practices for test organization
     - Test naming conventions
     - Quality criteria and standards
   - Keep this context available throughout the review to validate against official OpenShift standards
   - If fetch fails, continue with review but note that latest guidelines are unavailable

2. **Determine Source of Changes**:
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

3. **Identify Code Changes**:
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

4. **Detect New and Modified Tests**:
   - **If PR Mode**:
     - For each changed Go file, use `gh api` to get the diff:
       - `gh api repos/<owner>/<repo>/pulls/<pr-number>/files --jq '.[] | select(.filename == "<file>") | .patch'`
     - Parse the unified diff to find additions and modifications
   - **If Branch/Auto-detect Mode**:
     - For each changed Go file, run `git diff <base-branch>...HEAD -- <file>` to see the actual changes
   - Look for lines that are additions (start with `+`) containing Ginkgo test functions:
     - `Describe(`
     - `Context(`
     - `When(`
     - `It(`
   - **Determine if test is NEW or MODIFIED**:
     - Examine the diff context (lines starting with ` ` that don't have `+` or `-`)
     - **NEW test**: The test definition line (e.g., `It("test name"`) is on a `+` line AND there's no corresponding `-` line removing a similar test in the same hunk
     - **MODIFIED test**: The test definition exists in context lines (unchanged) OR there's a `-` line removing the old version and a `+` line adding the modified version in the same diff hunk
     - This works because:
       - A brand new test only appears as `+` lines in the diff
       - A modified test will show context with the test structure already existing, or show `-` and `+` pairs for the changes
   - **Note**: In OpenShift test projects (e.g., openshift/origin), Ginkgo tests often appear in `.go` files without the `_test.go` suffix, particularly in `test/extended/` and similar directories
   - Extract the full test name by combining all nested blocks (Describe/Context/When/It)

5. **Validate Component Mapping**:
   For each test detected, verify it has proper component tagging based on whether it's a new test or a modified test:

   **For NEW tests (test didn't exist in base branch):**
   - **REQUIRED: [Jira:"component"] tag**
     - Look for `[Jira:"component-name"]` tag in the test name
     - If Jira MCP plugin is enabled, validate the component exists:
       - Query OCPBUGS project components using the Jira MCP search
       - Verify the component name matches exactly (case-sensitive)
       - If component doesn't exist, flag as violation
     - Example: `It("should create pod [Jira:\"kube-apiserver\"]")`
   - **NOT ALLOWED: [sig-*] or [bz-*] tags**
     - If a new test uses `[sig-<name>]` or `[bz-<name>]` tags instead of `[Jira:"component"]`, flag as violation
     - New tests must use the modern `[Jira:"component"]` format
   - **Missing component tag**: Flag as violation if no `[Jira:"component"]` tag found

   **For MODIFIED tests (test existed in base branch but was changed):**
   - **PREFERRED: [Jira:"component"] tag**
     - Encourage migration to `[Jira:"component"]` format
     - If Jira MCP plugin is enabled and component exists, validate it
   - **ALLOWED: Existing [sig-*] or [bz-*] tags**
     - If the test already had `[sig-<name>]` or `[bz-<name>]` tags, they are acceptable
     - Verify the tag is used elsewhere in the repository:
       - **If PR Mode**: Check if we're in the target repository locally
         - Parse PR URL to extract org/repo (e.g., `openshift/origin`)
         - Check if current directory is that repository: `git remote -v | grep "github.com[:/]<org>/<repo>"`
         - If local repo matches PR target: Run `git grep -r "\[sig-<name>\]" test/` locally
         - If not in matching repo: Note that tag validation requires local checkout and skip validation
       - **If Branch Mode**: Run `git grep -r "\[sig-<name>\]" test/` or `git grep -r "\[bz-<name>\]" test/`
       - If tag exists in other tests, it's valid
       - If tag is unique to this test, flag as potential made-up tag
     - Examples: `[sig-network]`, `[bz-storage]`
     - Note in report: "Consider migrating to `[Jira:"component"]` format"
   - **Missing component tag**: Flag as violation if no component tag found

6. **Analyze Test Names for Dynamic Content and Deprecated Conventions**:
   For each detected test definition, check if the test name contains potentially random or dynamic strings, and validate against deprecated conventions:

   **❌ VIOLATIONS TO FLAG:**
   - **String formatting with variables**: `fmt.Sprintf()` with variables that could be dynamic/random
   - **Variable interpolation**: Variables used in test name strings (especially runtime-generated values)
   - **Generated identifiers**: UUIDs, random strings, timestamps
   - **Resource names**: Pod names, namespace names with dynamic suffixes
   - **Numeric values**: Specific limits, counts, durations that might change
   - **Deprecated: Author/Owner in name**: Test names containing "Author:" or "Owner:" (deprecated convention from openshift-tests-private)
   - **Deprecated: Untagged LEVEL**: Test names containing "LEVEL0" without proper tag format (should be `[Level0]`)

   **IMPORTANT**: `fmt.Sprintf()` is acceptable when ALL arguments are string literals (constants). This is commonly used for proper quoting in tags like `[Jira:%q]`.

   **IMPORTANT**: Git history tracks authorship - do not include author/owner information in test names.

   **IMPORTANT**: The `[Level0]` tag is valuable and should be preserved - it indicates a test was ported from openshift-tests-private and was considered important. Only the format needs correction (from untagged "LEVEL0" to tagged `[Level0]`).

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

   // BAD: Author/Owner in name (deprecated from openshift-tests-private)
   It("Author:jdoe-OCP-12345-should create pod successfully")
   It("Owner:teamname should verify deployment")

   // BAD: Untagged LEVEL0 (deprecated format from openshift-tests-private)
   It("LEVEL0 should create pod successfully")
   Describe("LEVEL0 networking tests")
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

   // GOOD: Properly tagged Level0 (preserve this tag when porting tests)
   It("should create pod successfully [Level0] [Jira:\"kube-apiserver\"]")
   Describe("[Level0] Networking isolation tests")

   // NOTE: [Level0] should be preserved - it indicates an important test ported from openshift-tests-private
   ```

7. **Validate Parallel Safety**:
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

8. **Detect Topology-Specific Risks and Edge Cases**:
   OpenShift runs in radically different topologies (HyperShift, MicroShift, Single Node OpenShift, standard clusters, etc.). Analyze the PR changes for common issues that break CI in these topologies:

   **Memory/Resource Changes (HIGH RISK):**
   - **Detection**: Look for changes that might affect memory or CPU available to control plane pods
   - **Patterns to detect**:
     - Changes to resource requests/limits in manifests or code
     - Memory-related constants or configuration values
     - Pod memory settings in operators or controllers
     - Buffer sizes, cache sizes, or data structures that grow with cluster size
     - CPU-intensive operations added to hot paths
   - **Risk**: OpenShift CI runs intense workloads that stress both CPU and memory across ALL topologies
     - Standard HA clusters can hit resource limits during heavy testing
     - Single Node OpenShift, MicroShift, and edge deployments are even more constrained
     - Resource increases that seem minor can cause cascading failures under CI load
   - **Recommendation**: Flag as HIGH RISK and recommend `/payload <release> nightly blocking` for comprehensive validation across dozens of different job configurations
   - **Example violation**: "Increased default cache size from 100MB to 500MB - this could exhaust memory under CI test load"

   **Other Topology Risks (will be expanded by teams over time):**
   - This section is designed to grow as teams identify common gotchas
   - Teams can add new edge case patterns specific to their components
   - Each pattern should include: detection logic, affected topologies, risk level, and recommended testing

9. **Generate Report**:
   - **Assemble Full Test Names**: For each new or modified test detected, construct the complete test name by combining all nested Ginkgo blocks (Describe/Context/When/It)
   - List all test files with changes
   - For each file, show:
     - New or modified test cases detected with their full assembled names
     - Component mapping status and any violations
     - Parallel safety status and any violations
     - Any naming violations found with specific line numbers and code snippets
     - Suggested fixes for each violation
     - **Topology-specific risks detected** (if any)
   - If no new tests found, report that clearly
   - If tests found but no violations, provide a summary of tests reviewed

10. **Provide Recommendations**:
   - Suggest adding `[Jira:"component"]` tags for tests missing component mapping
   - Suggest adding or removing `[Serial]` tags based on test behavior analysis
   - Suggest rewriting test names to be static and descriptive
   - Cross-reference findings with the OpenShift test conventions guidelines loaded in step 1
   - Provide context-aware recommendations based on official OpenShift testing standards
   - Reference the test naming guidelines from openshift/origin
   - Link to relevant documentation including the test conventions guide
   - **Include additional testing guidance**:
     - If reviewing a PR (not just a local branch), include information about running additional CI jobs
     - Reference the pull request testing documentation: https://docs.ci.openshift.org/docs/release-oversight/pull-request-testing/
     - Explain that users can trigger additional jobs beyond configured presubmits using `/payload` commands
     - Note: This is useful for high-risk changes that could destabilize CI (e.g., major Kubernetes rebases, core networking changes, scheduler modifications)
     - **Important**: `/payload <version> nightly blocking|informing` is expensive (runs ALL blocking or informing jobs - consumes significant CI resources) but very worth it for high-risk changes
     - Other commands like `/payload-job` (specific job) and `/payload-aggregate` (statistical runs) are not nearly as expensive
     - Explain the difference between `blocking` and `informing`:
       - `blocking` jobs must pass for the payload to be accepted - this is what most people want
       - `informing` jobs provide additional signal but don't block acceptance
       - Use `blocking` when you want comprehensive validation before merge

## Return Value

**Format**: Markdown report with the following sections:

1. **Summary**: Number of test files changed, new tests added, modified tests, violations found (component mapping, parallel safety, naming, and topology risks)
2. **Tests Detected**: Full list of all new or modified test names (complete paths assembled from nested Ginkgo blocks), clearly indicating which are new vs modified
3. **Commit Context**: List of commit messages in the branch
4. **Test Files Changed**: List of all test files modified
5. **Topology-Specific Risks** (if any):
   - Risk level (HIGH, MEDIUM, LOW)
   - File path and line number
   - Type of risk (e.g., "Memory/Resource Change")
   - Description of the change detected
   - Affected topologies (e.g., "Single Node OpenShift, MicroShift")
   - Recommended testing (e.g., "/payload 4.21 nightly blocking")
6. **Component Mapping Violations** (if any):
   - File path and line number
   - Test name and status (NEW or MODIFIED)
   - Issue: Missing tag, invalid component, use of sig-/bz- tags in new tests, or unverified legacy tag
   - Suggested fix
7. **Parallel Safety Violations** (if any):
   - File path and line number
   - Test name
   - Issue: Missing `[Serial]` tag when needed, or unnecessary `[Serial]` tag
   - Evidence from code analysis (cluster-wide operations detected)
   - Suggested fix
8. **Naming Violations** (if any):
   - File path and line number
   - Original test name code
   - Explanation of the violation
   - Suggested fix
9. **Clean Tests** (if any): List of new tests with no violations
10. **Recommendations**: Best practices and next steps
11. **Additional Testing** (if reviewing a PR): Information about triggering additional CI jobs using `/payload` commands

## Examples

1. **Review current branch with auto-detection**:
   ```
   /ci:pr-test-analysis
   ```

2. **Review current branch against specific base branch**:
   ```
   /ci:pr-test-analysis up/main
   ```

3. **Review against a different upstream remote**:
   ```
   /ci:pr-test-analysis upstream/master
   ```

4. **Review a GitHub pull request**:
   ```
   /ci:pr-test-analysis https://github.com/openshift/origin/pull/305390
   ```

5. **Review a PR from a different repository**:
   ```
   /ci:pr-test-analysis https://github.com/openshift/kubernetes/pull/12345
   ```

   Expected output when violations are found:
   ```markdown
   ## Test Review Report

   ### Summary
   - Source: PR #305390 (openshift/origin)
   - Comparing: base branch `master` vs head branch `my-feature`
   - OpenShift test conventions guidelines: Loaded from test-conventions.md
   - Test files changed: 3
   - New tests detected: 4
   - Modified tests detected: 2
   - **Topology-specific risks: 1 HIGH RISK** ⚠️
   - Component mapping violations: 3
   - Parallel safety violations: 2
   - Naming violations: 3 (1 dynamic content, 2 deprecated conventions)

   ### Tests Detected

   The following new or modified tests were found:

   **New Tests:**
   1. `[sig-node] Pods should create pod successfully` (test/extended/pods/creation_test.go:32) ⚠️
   2. `[sig-network] Networking should isolate traffic between namespaces [Jira:"network-edge"]` (test/extended/networking/isolation_test.go:78)
   3. `[sig-machineconfig] MachineConfig should apply custom MachineConfig and wait for rollout [Jira:"MachineConfig"]` (test/extended/machineconfig/rollout_test.go:56)
   4. `[sig-node] Pods should create and delete a simple pod [Serial] [Jira:"kube-apiserver"]` (test/extended/pods/simple_test.go:23)

   **Modified Tests:**
   5. `[sig-auth] RBAC Author:jdoe-OCP-54321 should verify RBAC permissions` (test/extended/auth/rbac_test.go:67) ⚠️
   6. `[sig-storage] LEVEL0 persistent volume provisioning` (test/extended/storage/volume_test.go:123) ⚠️

   ### Commit Context
   - abc123 Add new pod creation tests
   - def456 Fix namespace isolation test
   - ghi789 Add MachineConfig test

   ### Test Files Changed
   - test/extended/pods/creation_test.go
   - test/extended/pods/simple_test.go
   - test/extended/networking/isolation_test.go
   - test/extended/machineconfig/rollout_test.go
   - test/extended/auth/rbac_test.go
   - test/extended/storage/volume_test.go
   - pkg/apiserver/controller/config.go (non-test file with topology risks)

   ### Topology-Specific Risks

   #### pkg/apiserver/controller/config.go:145 (HIGH RISK) ⚠️

   **Risk Type**: Memory/Resource Change

   **Change Detected**:
   ```go
   -    DefaultCacheSize: 100 * 1024 * 1024,  // 100MB
   +    DefaultCacheSize: 500 * 1024 * 1024,  // 500MB
   ```

   **Issue**: This change increases the default cache size from 100MB to 500MB, which significantly increases memory requirements for the kube-apiserver control plane pod.

   **Affected Topologies**:
   - **ALL topologies** - OpenShift CI runs intense workloads that stress resources
   - Standard HA clusters can hit limits during heavy test execution
   - Single Node OpenShift (SNO) - very memory constrained
   - MicroShift - extremely memory constrained
   - HyperShift hosted control planes - shared resource pools
   - Resource-constrained edge deployments

   **Why This Matters**: OpenShift CI runs extremely intensive test workloads that push clusters hard. A 400MB increase in cache size could:
   - Cause OOMKills during CI test execution even on HA clusters
   - Exhaust memory on Single Node OpenShift preventing cluster functionality
   - Create cascading failures as pods compete for limited resources under load
   - Break dozens of different CI job configurations across different topologies

   **Recommended Testing**:
   ```
   /payload 4.21 nightly blocking
   ```
   This will run dozens of comprehensive tests across all topologies including standard HA, SNO, MicroShift, and HyperShift to ensure this change doesn't break CI under heavy test load.

   **Alternative**: If this is an optional/configurable cache size, ensure it has appropriate defaults for different topologies and can be tuned down for constrained environments.

   ### Component Mapping Violations

   #### test/extended/pods/creation_test.go:32 (NEW TEST)
   Test name: "should create pod successfully"

   **Issue**: New test is missing required `[Jira:"component"]` tag. All new tests must include a `[Jira:"component"]` tag to map failures to the appropriate team.

   **Suggested fix**:
   ```go
   It("should create pod successfully [Jira:\"kube-apiserver\"]")
   ```

   #### test/extended/networking/isolation_test.go:78 (NEW TEST)
   Test name: "should isolate traffic between namespaces [Jira:\"network-edge\"]"

   **Issue**: Component "network-edge" does not exist in OCPBUGS project. Valid components can be found using the Jira plugin.

   **Suggested fix**: Verify the correct component name (e.g., `[Jira:"Networking"]` or similar).

   #### test/extended/auth/rbac_test.go:67 (MODIFIED TEST)
   Test name: "[sig-auth] RBAC should verify RBAC permissions"

   **Issue**: Test uses legacy `[sig-auth]` tag. While this is acceptable for modified tests, consider migrating to the modern `[Jira:"component"]` format.

   **Suggested fix**:
   ```go
   It("should verify RBAC permissions [Jira:\"kube-apiserver\"]")
   ```

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

   #### test/extended/auth/rbac_test.go:67
   ```go
   It("Author:jdoe-OCP-54321 should verify RBAC permissions")
   ```

   **Issue**: Test name contains deprecated "Author:" prefix from openshift-tests-private. Git history tracks authorship - this information should not be in test names.

   **Suggested fix**:
   ```go
   It("should verify RBAC permissions [Jira:\"kube-apiserver\"]")
   ```

   #### test/extended/storage/volume_test.go:123
   ```go
   Describe("LEVEL0 persistent volume provisioning")
   ```

   **Issue**: Test name contains untagged "LEVEL0" (deprecated format from openshift-tests-private). The Level0 designation should use proper tag format `[Level0]`.

   **Note**: The `[Level0]` tag is valuable - it indicates this test was ported from openshift-tests-private and was considered important. Preserve this tag, just correct the format.

   **Suggested fix**:
   ```go
   Describe("[Level0] persistent volume provisioning")
   ```

   ### Clean Tests
   - test/extended/storage/pvc_test.go:34 - `It(fmt.Sprintf("should provision persistent volume claim [Jira:%q]", "Storage"))`
   - test/extended/networking/dns_test.go:56 - `It("should resolve cluster DNS [Jira:\"Networking\"]")`
   - test/extended/auth/rbac_test.go:89 - `Describe(fmt.Sprintf("[sig-%s] RBAC permissions", "auth"))`

   ### Recommendations
   - **NEW TESTS**: All new tests MUST use `[Jira:"component"]` tags for proper component mapping
     - Legacy `[sig-*]` and `[bz-*]` tags are not acceptable for new tests
     - Use `/component-health:list-components` to find valid component names
   - **MODIFIED TESTS**: Consider migrating legacy `[sig-*]` and `[bz-*]` tags to `[Jira:"component"]` format
     - Existing legacy tags are acceptable but migration is encouraged
   - Review parallel safety violations and add/remove `[Serial]` tags as needed:
     - Add `[Serial]` for tests that modify cluster-wide resources (MachineConfigs, nodes, cluster operators)
     - Remove `[Serial]` from tests that only operate within their namespace
   - Remove deprecated openshift-tests-private conventions:
     - Remove "Author:" and "Owner:" prefixes from test names (git history tracks authorship)
     - Convert untagged "LEVEL0" to proper tag format: `[Level0]` (preserve the tag - it indicates an important ported test)
   - Remove dynamic content from test names (variables, timestamps, specific values)
   - Use the Jira plugin to verify valid component names: `/component-health:list-components`
   - See official OpenShift test conventions: https://github.com/openshift/enhancements/blob/master/dev-guide/test-conventions.md
   - See test naming guidelines: https://github.com/openshift/origin/blob/master/test/extended/README.md

   ### Additional Testing
   - **Want to run more comprehensive testing on this PR?**
     - You can trigger additional CI jobs beyond the configured presubmits using `/payload` commands
     - Useful for high-risk changes that could destabilize CI
     - Examples of high-risk changes: Kubernetes rebases, core networking changes, scheduler modifications, API changes

     **Command Options:**
     - `/payload 4.21 nightly blocking` - Run ALL blocking jobs for 4.21 (recommended - jobs must pass)
       - **⚠️ Expensive**: Runs dozens of blocking jobs across different topologies - consumes significant CI resources
       - **Very worth it** for high-risk changes that need comprehensive validation
     - `/payload 4.21 nightly informing` - Run ALL informing jobs for 4.21 (provides signal but doesn't block)
       - **⚠️ Expensive**: Runs dozens of informing jobs across different topologies - consumes significant CI resources
     - `/payload-job periodic_ci_openshift_release_some_job` - Run a specific job (not expensive)
     - `/payload-aggregate periodic_job 5` - Run a job 5 times for statistical analysis (not expensive)
     - `/payload-abort` - Stop all running payload jobs for this PR

     **Blocking vs Informing:**
     - `blocking` - Jobs must pass for the payload to be accepted (use this for comprehensive validation)
     - `informing` - Jobs provide additional signal but don't block acceptance
     - Most people want `blocking` when running comprehensive tests

     See full documentation: https://docs.ci.openshift.org/docs/release-oversight/pull-request-testing/
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

- **Test name assembly**:
  - The report includes a "Tests Detected" section at the start listing all new or modified tests
  - Full test names are assembled by combining all nested Ginkgo blocks (Describe/Context/When/It)
  - For example: `Describe("[sig-node] Pods") + Context("basic operations") + It("should create pod")` → `[sig-node] Pods basic operations should create pod`
  - This makes it easy to see exactly which tests are being added or changed
- **OpenShift guidelines integration**:
  - Automatically fetches the latest test-conventions guide from openshift/enhancements at the start of execution
  - Uses these official guidelines to validate test quality and completeness
  - Provides context-aware recommendations based on OpenShift testing standards
  - If the guidelines cannot be fetched, the review continues but recommendations may be more generic
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
  - If you have multiple remotes or stale branches, explicitly specify the base branch (e.g., `/ci:pr-test-analysis up/main`)
- **Component validation**:
  - **NEW TESTS**: Must use `[Jira:"component"]` tags - legacy `[sig-*]` and `[bz-*]` tags will be flagged as violations
  - **MODIFIED TESTS**: May use existing `[sig-*]` and `[bz-*]` tags, but migration to `[Jira:"component"]` is encouraged
  - If the Jira MCP plugin is enabled, the command will validate `[Jira:"component"]` tags against actual OCPBUGS components
  - If Jira plugin is not available, the command will still check for the presence of component tags but cannot validate them
  - Legacy `[sig-*]` and `[bz-*]` tags (when allowed for modified tests) are verified by checking if they exist elsewhere in the repository:
    - **In PR mode**: If you're in the target repository locally (checked via `git remote -v`), the command will use local code to validate sig- tags
    - **In branch mode**: Always uses local repository for tag validation
    - If not in the matching repository during PR review, tag validation will be skipped with a note
- **Component tag format**: The `[Jira:"component"]` tag can appear anywhere in the test name (typically at the end)
- **New vs Modified detection**:
  - The command determines if a test is new or modified by analyzing the diff context
  - **NEW**: Test appears only on `+` (added) lines with no corresponding `-` (removed) lines in the same hunk
  - **MODIFIED**: Test definition appears in context lines (unchanged portions) OR shows as `-` and `+` pairs indicating changes
  - This approach is simple and accurate because it uses the diff structure that's already being parsed
  - This distinction is critical because new tests have stricter requirements for component tags
- **Parallel safety validation**:
  - Analyzes actual test code (not just the name) to detect cluster-wide operations
  - Flags tests missing `[Serial]` when they perform operations that could affect other tests
  - Flags tests with unnecessary `[Serial]` tags that only operate in their namespace
  - Searches for keywords: MachineConfig, node operations, cluster operators, etc.
- **Format strings**: `fmt.Sprintf()` is allowed when all arguments are string literals (e.g., `fmt.Sprintf("[Jira:%q]", "kube-apiserver")` is acceptable for proper quoting)
- **Dynamic content detection**: Only flags format strings that use variables or function calls, not static string literals
- **Deprecated convention detection**:
  - Flags "Author:" and "Owner:" prefixes in test names (deprecated from openshift-tests-private)
  - Git history is the proper way to track test authorship
  - Flags untagged "LEVEL0" - this should use proper tag format: `[Level0]`
  - **Important**: The `[Level0]` tag itself is valuable and should be preserved - it indicates a test was ported from openshift-tests-private and was considered important
  - These conventions are being cleaned up as tests are ported from openshift-tests-private to main repos
- **Test file detection**:
  - Analyzes all `.go` files in test-related directories (not just `*_test.go` files)
  - OpenShift test projects often organize Ginkgo tests in regular `.go` files within `test/extended/` and similar directories
  - Detects tests by looking for Ginkgo functions (`Describe`, `Context`, `When`, `It`) rather than relying on file naming conventions
- Does not execute tests, only performs static analysis of test code
- Focuses specifically on component mapping, parallel safety, and test naming violations; does not perform comprehensive code review
