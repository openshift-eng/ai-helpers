---
description: Generate test steps for a JIRA issue
argument-hint: "[JIRA issue key] [GitHub PR URLs] [--generate-e2e] [--test-dir path] [--skeleton-only]"
---

## Name
jira:generate-test-plan

## Synopsis
/jira:generate-test-plan [JIRA issue key] [GitHub PR URLs] [--generate-e2e] [--test-dir path] [--skeleton-only]

## Description
The 'jira:generate-test-plan' command takes a JIRA issue key and optionally a list of PR URLs. It fetches the JIRA issue details, retrieves all related PRs (or uses the provided PR list), analyzes the changes, and generates:
1. A comprehensive manual testing guide (always generated)
2. Automated E2E test code (when `--generate-e2e` flag is used)

**JIRA Issue Test Guide Generator with Optional E2E Code Generation**

## Implementation

- The command uses curl to fetch JIRA data via REST API: https://issues.redhat.com/rest/api/2/issue/{$1}
- Uses WebFetch to extract PR links from JIRA issue if no PRs provided
- Uses `gh pr view` to fetch PR details for each PR
- Analyzes changes across all PRs to understand implementation
- Generates comprehensive manual test scenarios

## Process Flow:

1. **JIRA Analysis**: Fetch and parse JIRA issue details:
   - Use curl to fetch JIRA issue data: `curl -s "https://issues.redhat.com/rest/api/2/issue/{$1}"`
   - Parse JSON response to extract:
     - Issue summary and description
     - Context and acceptance criteria
     - Steps to reproduce (for bugs)
     - Expected vs actual behavior
   - Extract issue type (Story, Bug, Task, etc.)

2. **PR Discovery**: Get list of PRs to analyze:
   - **If no PRs provided in arguments** ($2, $3, etc. are empty):
     - Use WebFetch on https://issues.redhat.com/browse/{$1}
     - Extract all GitHub PR links from:
       - "Issue Links" section
       - "Development" section
       - PR links in comments
   - **If PRs provided in arguments**:
     - Use only the PRs provided in $2, $3, $4, etc.
     - Ignore any other PRs linked to the JIRA

3. **PR Analysis**: For each PR, fetch and analyze:
   - Use `gh pr view {PR_NUMBER} --repo <your repo> --json title,body,commits,files,labels`
   - Extract:
     - PR title and description
     - Changed files and their diffs
     - Commit messages
     - PR status (merged, open, closed)
   - Read changed files to understand implementation details
   - Use Grep and Glob tools to:
     - Find related test files
     - Locate configuration or documentation
     - Identify dependencies

4. **Change Analysis**: Understand what was changed across all PRs:
   - Identify the overall objective (bug fix, feature, refactor)
   - Determine affected components (API, CLI, operator, control-plane, etc.)
   - Find platform-specific changes (AWS, Azure, KubeVirt, etc.)
   - Map which PR addresses which aspect of the JIRA
   - Identify any dependencies between PRs

5. **Test Scenario Generation**: Create comprehensive test plan:
   - Map JIRA acceptance criteria to test scenarios
   - For bugs: Use reproduction steps as test cases
   - Generate test scenarios covering:
     - Happy path scenarios (based on acceptance criteria)
     - Edge cases and error handling
     - Platform-specific variations if applicable
     - Regression scenarios
   - For multiple PRs:
     - Create integrated test scenarios
     - Verify PRs work correctly together
     - Test each PR's contribution to the overall solution

6. **Test Guide Creation**: Generate detailed manual testing document:
   - **Filename**: Always use JIRA key format: `test-{JIRA_KEY}.md`
     - Convert JIRA key to lowercase
     - Examples: `test-cntrlplane-205.md`, `test-ocpbugs-12345.md`
   - **Structure**:
     - **JIRA Summary**: Include JIRA key, title, description, acceptance criteria
     - **PR Summary**: List all PRs with titles and how they relate to the JIRA
     - **Prerequisites**:
       - Required infrastructure and tools
       - Environment setup requirements
       - Access requirements
     - **Test Scenarios**:
       - Map each test to JIRA acceptance criteria
       - Numbered test cases with clear steps
       - Expected results with verification commands
       - Platform-specific test variations
     - **Regression Testing**:
       - Related features to verify
       - Areas that might be affected
     - **Success Criteria**:
       - Checklist mapping to JIRA acceptance criteria
     - **Troubleshooting**:
       - Common issues and debug steps
     - **Notes**:
       - Known limitations
       - Links to JIRA and all PRs
       - Critical test cases highlighted

7. **Exclusions**: Apply smart filtering:
   - **Skip PRs that don't require testing**:
     - PRs that only add documentation (.md files only)
     - PRs that only add CI/tooling (.github/, .claude/ directories)
     - PRs marked with labels like "skip-testing" or "docs-only"
   - **Note skipped PRs** in the test guide with reasoning
   - Focus test scenarios on PRs with actual code changes

8. **E2E Test Generation** (only if `--generate-e2e` flag is present):
   - **Determine Target Repository**:
     - **If PRs are provided**: Extract repository from the first PR URL (e.g., `https://github.com/openshift/hypershift/pull/123` -> `openshift/hypershift`)
     - **If no PRs found**: MUST ask user to confirm or specify the target repository
     - **NEVER default to current working directory without explicit user confirmation**

   - **Detect Test Directory**:
     - **If `--test-dir` provided**: Use the specified directory (absolute or relative to target repository)
     - **Otherwise, auto-detect** by searching for existing E2E test directories in the target repository:
       - Check for: `test/e2e/`, `tests/e2e/`, `e2e/`, `test/integration/`
       - If found, use the existing directory
       - If multiple found, prompt user to select
       - If none found, default to `test/e2e/` and ask for confirmation
     - **Always display the full path** where files will be generated and ask for user confirmation before writing files

   - **Analyze Existing Test Style**:
     - Find all `*_test.go` files in the detected test directory
     - Analyze the first 2-3 test files to extract code style patterns:
       - Test framework (Ginkgo, testify, standard testing)
       - Assertion library (Gomega, assert, require)
       - Naming conventions (function names, test descriptions)
       - Structure patterns (BeforeEach/AfterEach, setup/teardown)
       - Common imports and helper functions
       - Variable naming and declaration patterns
       - Context management patterns
       - Timeout and polling interval constants
       - Error handling style
     - Select the most similar existing test file as a template
     - If no existing tests found, use a default Ginkgo template

   - **Generate E2E Test Code**:
     - Create test file with name based on JIRA issue: `{feature}_test.go`
       - Extract feature name from JIRA summary (e.g., "imagetagmirrorset" from "Enable ImageTagMirrorSet configuration")
       - Convert to snake_case and append `_test.go`
     - Match the detected code style for all elements:
       - Use same test framework and assertion style
       - Follow same naming patterns for test descriptions
       - Use same variable declaration style (var blocks vs inline)
       - Match BeforeEach/AfterEach setup patterns
       - Replicate context management approach
       - Use same helper function patterns
       - Match timeout/interval constant usage
       - Follow same error handling patterns
     - Generate test cases based on JIRA acceptance criteria:
       - One test case per acceptance criterion
       - Use `By()` steps to break down test logic
       - Add TODO comments for implementation-specific details
       - Include verification steps with Eventually() for async operations
     - **Code Generation Strategy**:
       - If `--skeleton-only` flag: Generate only test structure with all TODO markers
       - If `--generate-e2e` without skeleton flag (default): Generate partial implementation:
         - Complete: imports, variable declarations, BeforeEach/AfterEach
         - Partial: test case structure with key assertions
         - TODO: Implementation-specific details that require PR analysis
     - Add appropriate imports based on detected patterns
     - Include inline comments explaining TODO items

   - **Create Test Directory Structure** (if needed):
     - If test directory doesn't exist, create it
     - If helpers directory is used in existing tests, create `helpers/` subdirectory
     - Maintain consistency with existing project structure

   - **Update Test Plan Document**:
     - Add "Automated E2E Tests" section to the generated test plan
     - Reference the generated test file location
     - Map each test case to corresponding acceptance criteria
     - Include instructions for running the tests
     - Add implementation notes with TODO list

9. **User Confirmation** (before writing E2E files):
   - **CRITICAL**: Before writing any E2E test files, MUST display to the user:
     - Target repository (from PR or current directory)
     - Full absolute path where test file will be created
     - Test directory detected or selected
   - **Ask for explicit confirmation**:
     - "Generate E2E test at `/path/to/repo/test/e2e/feature_test.go`? (y/n)"
     - If user says no, ask for alternative directory
     - If user provides alternative, validate and confirm again
   - **Only proceed with file generation after receiving explicit user approval**

10. **Output**: Display the testing guide and E2E code (if generated):
   - Show the file path where the manual test guide was saved
   - If E2E tests generated, show the test file path
   - Provide a summary of:
     - JIRA issue being tested
     - Number of PRs included
     - Number of manual test scenarios generated
     - Number of automated test cases generated (if applicable)
     - Target repository used (if applicable)
     - Test directory used (if applicable)
     - Code style matched (if applicable)
     - Number of TODO items requiring completion (if applicable)
     - Critical test cases to focus on
   - Highlight any PRs that were skipped and why
   - If E2E tests generated, provide next steps:
     - Review generated test code
     - Complete TODO items
     - Run tests to verify they work
   - Ask if the user would like any modifications to the test guide or generated code

## Examples:

### Manual Test Plan Only (Default Behavior)

1. **Generate test steps for JIRA with auto-discovered PRs**:
   ```bash
   /jira:generate-test-plan CNTRLPLANE-205
   ```

2. **Generate test steps for JIRA with specific PRs only**:
   ```bash
   /jira:generate-test-plan CNTRLPLANE-205 https://github.com/openshift/hypershift/pull/6888
   ```

3. **Generate test steps for multiple specific PRs**:
   ```bash
   /jira:generate-test-plan CNTRLPLANE-205 https://github.com/openshift/hypershift/pull/6888 https://github.com/openshift/hypershift/pull/6889
   ```

### E2E Test Generation

4. **Generate test plan + E2E test code (auto-detect test directory)**:
   ```bash
   /jira:generate-test-plan CNTRLPLANE-205 --generate-e2e
   ```
   Output:
   - `test-cntrlplane-205.md` - Manual test plan
   - `test/e2e/imagetagmirrorset_test.go` - E2E test code (auto-detected directory)

5. **Generate E2E tests with specific test directory**:
   ```bash
   /jira:generate-test-plan CNTRLPLANE-205 --generate-e2e --test-dir test/e2e/
   ```

6. **Generate only test skeleton (structure without implementation)**:
   ```bash
   /jira:generate-test-plan CNTRLPLANE-205 --generate-e2e --skeleton-only
   ```
   Generates test structure with all TODO markers for manual implementation.

7. **Generate E2E tests with specific PRs**:
   ```bash
   /jira:generate-test-plan CNTRLPLANE-205 https://github.com/openshift/hypershift/pull/6888 --generate-e2e
   ```

8. **Complete workflow example with confirmation**:
   ```bash
   # Generate test plan + E2E code (with PR provided)
   $ /jira:generate-test-plan OCPBUGS-12345 https://github.com/openshift/hypershift/pull/6888 --generate-e2e

   # Claude analyzes and prompts:
   # 🔍 Analyzing JIRA issue OCPBUGS-12345...
   # ✓ Found 1 PR: https://github.com/openshift/hypershift/pull/6888
   # ✓ Detected repository: openshift/hypershift
   # ✓ Detected test directory: test/e2e/
   # ✓ Code style: Ginkgo v2 + Gomega
   #
   # 📝 Ready to generate:
   #   - Manual test plan: /current/dir/test-ocpbugs-12345.md
   #   - E2E test code: /path/to/hypershift/test/e2e/bugfix_test.go
   #
   # Generate E2E test at /path/to/hypershift/test/e2e/bugfix_test.go? (y/n)

   # User responds: y

   # ✓ Generated test plan: test-ocpbugs-12345.md
   # ✓ Generated E2E test: /path/to/hypershift/test/e2e/bugfix_test.go
   #
   # Next steps:
   # 1. Review test-ocpbugs-12345.md
   # 2. Complete TODOs in test/e2e/bugfix_test.go (8 items)
   # 3. Run: make test-e2e FOCUS="bugfix"
   ```

9. **Workflow when no PR is found**:
   ```bash
   # Generate test plan + E2E code (no PR linked)
   $ /jira:generate-test-plan OCPCLOUD-3262 --generate-e2e

   # Claude analyzes and prompts:
   # 🔍 Analyzing JIRA issue OCPCLOUD-3262...
   # ⚠️  No PRs found linked to this JIRA issue
   #
   # Where should I generate the E2E test code?
   # Options:
   #   1. Current directory: go/src/github.com/openshift/cluster-capi-operator
   #   2. Specify a different repository path
   #   3. Skip E2E generation (manual test plan only)
   #
   # Please choose (1/2/3) or provide path:

   # User responds: 1

   # ✓ Detected test directory: e2e/
   # 📝 Ready to generate E2E test at: go/src/github.com/openshift/cluster-capi-operator/e2e/machineset_vap_test.go
   #
   # Confirm? (y/n)

   # User responds: y

   # ✓ Generated test plan: test-ocpcloud-3262.md
   # ✓ Generated E2E test: e2e/machineset_vap_test.go
   ```

## Arguments:

- **$1**: JIRA issue key (required) - e.g., CNTRLPLANE-205, OCPBUGS-12345
- **$2, $3, ..., $N**: Optional GitHub PR URLs
  - If provided: Only these PRs will be analyzed
  - If omitted: All PRs linked to the JIRA will be discovered and analyzed
- **--generate-e2e**: Generate automated E2E test code in addition to manual test plan
  - Analyzes existing test code style and generates matching test code
  - Creates test file in detected or specified test directory
  - Generates test cases based on JIRA acceptance criteria
  - Includes TODO markers for implementation-specific details
- **--test-dir <path>**: Specify the directory for E2E test generation
  - Only used when `--generate-e2e` is present
  - If omitted, auto-detects test directory from project structure
  - Examples: `test/e2e/`, `tests/integration/`, `e2e/`
- **--skeleton-only**: Generate only test structure without implementation
  - Only used when `--generate-e2e` is present
  - Creates test framework with all TODO markers
  - Useful when you want to write all implementation details manually

## Smart Features:

### Manual Test Plan Features

1. **Automatic PR Discovery**:
   - Scans JIRA issue for all related PRs
   - Identifies PRs in "Issue Links", "Development" section, and comments

2. **Selective PR Testing**:
   - Allows manual override to test specific PRs only
   - Useful when JIRA has many PRs but only some need testing

3. **Context-Aware Test Generation**:
   - Bug fixes: Focus on reproduction steps and verification
   - Features: Focus on acceptance criteria and user workflows
   - Refactors: Focus on regression and functional equivalence

4. **Multi-PR Integration**:
   - Understands how multiple PRs work together
   - Creates integration test scenarios
   - Identifies dependencies and testing order

5. **Build/Deploy Section Exclusion**:
   - Does NOT include build or deployment steps
   - Assumes environment is already set up
   - Focuses purely on testing procedures

6. **Cleanup Section Exclusion**:
   - Does NOT include cleanup steps
   - Focuses on test execution and verification

### E2E Code Generation Features (when --generate-e2e is used)

7. **Intelligent Test Directory Detection**:
   - Automatically finds existing E2E test directories
   - Supports common patterns: `test/e2e/`, `tests/e2e/`, `e2e/`, `test/integration/`
   - Prompts user for confirmation if multiple directories found
   - Creates directory structure if it doesn't exist

8. **Code Style Analysis and Matching**:
   - Analyzes existing test files to learn project conventions
   - Detects test framework (Ginkgo, testify, standard testing)
   - Matches naming conventions for functions and variables
   - Replicates setup/teardown patterns (BeforeEach/AfterEach)
   - Uses same assertion style (Gomega matchers, assert, require)
   - Follows same context management approach
   - Matches timeout and polling interval patterns
   - Preserves import organization and helper function usage

9. **Template-Based Generation**:
   - Finds the most similar existing test as a template
   - Extracts reusable patterns and structures
   - Adapts template to new test requirements
   - Maintains consistency with existing codebase

10. **Acceptance Criteria Mapping**:
    - Generates one test case per JIRA acceptance criterion
    - Maps test scenarios to specific requirements
    - Ensures complete coverage of acceptance criteria
    - Links generated tests back to manual test plan

11. **Partial Implementation with TODO Guidance**:
    - Generates complete test structure and framework
    - Includes partial implementation where possible
    - Adds clear TODO markers for manual completion
    - Provides inline comments explaining what needs to be done
    - Balances automation with flexibility

12. **Integration with Test Plan**:
    - Updates manual test plan with E2E test information
    - Cross-references automated and manual test scenarios
    - Provides instructions for running generated tests
    - Documents implementation status and TODO items

## Example Workflows:

### Workflow 1: Manual Test Plan Only

```bash
# Auto-discover all PRs from JIRA
/jira:generate-test-plan CNTRLPLANE-205

# Test only specific PRs
/jira:generate-test-plan CNTRLPLANE-205 https://github.com/openshift/hypershift/pull/6888

# Test multiple specific PRs
/jira:generate-test-plan OCPBUGS-12345 https://github.com/openshift/hypershift/pull/1234 https://github.com/openshift/hypershift/pull/1235
```

The command will provide a comprehensive manual testing guide that QE or developers can use to thoroughly test the JIRA issue implementation.

### Workflow 2: Manual Test Plan + E2E Test Generation

```bash
# Generate both manual test plan and E2E test code
$ /jira:generate-test-plan CNTRLPLANE-205 --generate-e2e

🔍 Analyzing JIRA issue CNTRLPLANE-205...
✓ Fetched issue: "Enable ImageTagMirrorSet configuration in HostedCluster CRs"
✓ Found 3 acceptance criteria

🔍 Discovering PRs...
✓ Found 1 linked PR: https://github.com/openshift/hypershift/pull/6888

📊 Analyzing PR changes...
✓ Detected changes in: API types, Controller logic
✓ Platforms affected: AWS, Azure, GCP

🔍 Detecting test directory...
✓ Found existing tests in: test/e2e/
✓ Analyzing code style...
✓ Detected: Ginkgo v2 + Gomega
✓ Found template: test/e2e/hostedcluster_test.go (90% similarity)

📝 Generating test plan...
✓ Created: test-cntrlplane-205.md

💻 Generating E2E test code...
✓ Created: test/e2e/imagetagmirrorset_test.go
✓ Generated 3 test cases (mapped to acceptance criteria)
✓ Added 8 TODO items for manual completion

Summary:
  Manual Test Plan: test-cntrlplane-205.md
    - 5 manual test scenarios
    - 2 regression test scenarios

  E2E Test Code: test/e2e/imagetagmirrorset_test.go
    - 3 automated test cases
    - 8 TODO items to complete
    - Framework: Ginkgo v2 + Gomega
    - Style matched to existing tests

Next steps:
1. Review test-cntrlplane-205.md for manual test scenarios
2. Complete TODO items in test/e2e/imagetagmirrorset_test.go:
   - TODO #1: Add ImageTagMirrorSet configuration (line 45)
   - TODO #2: Verify configuration is applied (line 52)
   - TODO #3-8: Implementation-specific validations
3. Run tests: make test-e2e FOCUS="ImageTagMirrorSet"
4. Update test plan with E2E test results
```

### Workflow 3: Skeleton-Only E2E Generation

```bash
# Generate test structure without implementation details
$ /jira:generate-test-plan OCPBUGS-12345 --generate-e2e --skeleton-only

✓ Generated test skeleton: test/e2e/bugfix_test.go
✓ All implementation marked with TODO comments
✓ Test structure ready for manual coding

# Useful when you want full control over implementation
```
