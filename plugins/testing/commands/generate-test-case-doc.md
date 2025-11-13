---
description: Generate comprehensive test cases for a feature with priority filtering and multiple output formats
argument-hint: <feature_name> [--priority high|medium|low] [--component name] [--format markdown|docx]
---

## Name
testing:generate-test-case-doc

## Synopsis
```
/testing:generate-test-case-doc <feature_name> [--priority high|medium|low] [--component name] [--format markdown|docx]
```

## Description

The `testing:generate-test-case-doc` command generates comprehensive, detailed test cases for any new feature or functionality. It analyzes the feature requirements, generates multiple test scenarios covering different aspects (functional, regression, smoke, edge cases), and outputs a well-structured document that can be used by QA teams.

This command automates the creation of:
- Detailed test cases with clear steps and expected results
- Priority-based categorization (High/Medium/Low)
- Test type tagging (Regression, Smoke, Functional, Integration, etc.)
- Critical test case summary for quick validation
- Support for multiple output formats (Markdown, DOCX)

The command is designed for:
- QA engineers creating test plans for new features
- Developers documenting testing requirements
- Product teams validating feature completeness
- CI/CD integration for automated test documentation

## Implementation

### Process Flow

1. **Parse Arguments and Flags**:
   - **$1** (feature_name): Required - The name or description of the feature to test
     - Example: "User Authentication with OAuth2"
   - **--priority**: Optional filter to generate only test cases of specific priority
     - Values: `high`, `medium`, `low`, `all` (default: all)
     - Example: `--priority high` generates only high-priority test cases
   - **--component**: Optional component/module tag for organizing test cases
     - Example: `--component auth` tags all tests with the auth component
     - Multiple components: `--component auth,api,ui`
   - **--format**: Output format
     - Values: `markdown` (default), `docx`
     - Example: `--format docx` generates a Word document

   Parse these arguments using bash parameter parsing:
   ```bash
   FEATURE_NAME="$1"
   PRIORITY_FILTER="all"
   COMPONENT=""
   FORMAT="markdown"

   shift  # Remove feature_name from arguments

   while [[ $# -gt 0 ]]; do
     case "$1" in
       --priority)
         PRIORITY_FILTER="$2"
         shift 2
         ;;
       --component)
         COMPONENT="$2"
         shift 2
         ;;
       --format)
         FORMAT="$2"
         shift 2
         ;;
       *)
         echo "Unknown option: $1"
         exit 1
         ;;
     esac
   done
   ```

2. **Validate Inputs**:
   - Check if feature_name is provided:
     ```bash
     if [ -z "$FEATURE_NAME" ]; then
       echo "Error: Feature name is required"
       echo "Usage: /testing:generate-test-case-doc <feature_name> [options]"
       exit 1
     fi
     ```
   - Validate priority filter (if provided):
     - Must be one of: `high`, `medium`, `low`, `all`
     - If invalid, display error and exit
   - Validate format:
     - Must be one of: `markdown`, `docx`
     - If invalid, default to markdown with warning

3. **Analyze Feature Context and Codebase** (CRITICAL - DO NOT SKIP):

   **IMPORTANT**: This step is essential for generating relevant, accurate test cases. Spend time gathering context from the actual codebase.

   **A. Search for Feature Documentation**

   Display message: "🔍 Analyzing codebase for '{feature_name}'..."

   - Find documentation files mentioning the feature:
     ```bash
     # Search all markdown files
     grep -r -i "{feature_name}" --include="*.md" --include="*.txt" --include="*.rst"
     ```

   - Look for key documentation files:
     - README.md (installation, setup, usage)
     - CONTRIBUTING.md (development setup)
     - docs/ directory
     - Design documents, RFCs, proposals
     - CHANGELOG.md (feature additions)

   - Extract from documentation:
     - Installation/setup steps
     - Prerequisites (tools, versions, dependencies)
     - Configuration requirements
     - Usage examples
     - Known limitations

   **B. Find Existing Test Files** (Learn from existing patterns)

   Display message: "📋 Looking for existing test files..."

   - Search for test files in common locations:
     ```bash
     # Find test files
     find . -type f \( -name "*test*.go" -o -name "*test*.py" -o -name "*_test.js" -o -name "test_*.py" -o -name "*_spec.rb" \)

     # Search test files for feature mentions
     grep -r -i "{feature_name}" test/ tests/ spec/ --include="*test*" --include="*spec*"
     ```

   - Look for test files containing the feature name
   - Read relevant test files to understand:
     - Test structure and patterns used in this project
     - How tests are organized (by feature, by component, etc.)
     - Setup/teardown procedures
     - Assertion styles
     - Mock/stub patterns
     - Test data examples

   - **IMPORTANT**: If existing test files are found for this feature:
     - Read them completely
     - Learn the test case format used
     - Identify what scenarios are already tested
     - Use similar naming conventions
     - Follow the same structure

   **C. Search for Implementation Code**

   Display message: "💻 Searching implementation files..."

   - Find source code related to the feature:
     ```bash
     # Search source code
     grep -r -i "{feature_name}" --include="*.go" --include="*.py" --include="*.js" --include="*.java" --include="*.rb" --include="*.ts" | head -50
     ```

   - Identify key implementation files
   - Understand:
     - Main components involved
     - APIs or interfaces
     - Configuration options
     - Dependencies on external systems
     - Entry points (CLI commands, API endpoints, etc.)

   **D. Identify Setup and Configuration Requirements**

   Display message: "⚙️  Identifying setup requirements..."

   - Search for configuration files:
     ```bash
     # Find config files
     find . -type f \( -name "*.yaml" -o -name "*.yml" -o -name "*.json" -o -name "*.conf" -o -name "*.toml" -o -name "*.ini" \) | grep -v vendor | grep -v node_modules | head -20
     ```

   - Look for:
     - Deployment manifests (Kubernetes, Docker Compose)
     - Configuration examples
     - Environment variables
     - Command-line flags
     - Default settings

   - Check for installation/setup scripts:
     - Makefile targets
     - install.sh, setup.sh
     - Package managers (package.json, requirements.txt, go.mod)

   **E. Analyze Integration Points and Dependencies**

   Display message: "🔗 Analyzing integrations..."

   - Identify external dependencies:
     - Check README for prerequisites
     - Look for mentions of:
       - Container runtimes (Docker, containerd, CRI-O)
       - Kubernetes/OpenShift
       - Databases
       - Message queues
       - External APIs or services

   - Understand platform-specific requirements:
     - Operating system requirements
     - Kernel features needed
     - Network requirements
     - Storage requirements

   **F. Extract Commands and Tools Used**

   - Find command-line usage:
     - Search for CLI commands in docs
     - Look for kubectl, oc, docker commands
     - Identify custom tools or scripts

   - Extract from code/docs:
     - Actual commands users run
     - API endpoints
     - Configuration values
     - File paths

   **G. Summarize Context Gathered**

   Display message: "✓ Context analysis complete"

   Create a context summary with:
   - Repository type (Go project, Python project, K8s operator, etc.)
   - Feature location (which files implement it)
   - Existing test file(s) found (if any)
   - Setup/installation steps identified
   - Key tools/commands involved
   - Platform-specific requirements
   - Integration dependencies

   **IMPORTANT Decision Point**:
   - If existing test files found for this feature → Use them as primary reference
   - If similar test files found → Learn patterns and adapt
   - If no test files found → Generate from documentation and code analysis

   This context will be used to generate accurate, repository-specific test cases.

   **IMPORTANT**: Do NOT ask for user confirmation after gathering context. Proceed directly to Step 4 (Generate Comprehensive Test Cases) using the gathered context.

4. **Generate Comprehensive Test Cases**:

   **IMPORTANT**: Use the context gathered in Step 3 to create relevant, repository-specific test cases.

   **Context-Driven Test Generation**:

   - **If existing test files were found**:
     - Use their structure and format as the primary template
     - Follow their naming conventions (e.g., TC-001, Test-01, etc.)
     - Match their level of detail and specificity
     - Learn from scenarios already tested
     - Extend with additional scenarios not covered

   - **Use discovered setup/installation steps**:
     - In preconditions, reference actual installation steps from README
     - Include actual configuration files found (yaml, json, conf)
     - Reference specific tools/versions from prerequisites

   - **Use actual commands and tools found**:
     - In test steps, use real CLI commands discovered (kubectl, oc, docker, etc.)
     - Reference actual API endpoints from code
     - Use actual configuration values from examples
     - Include real file paths from the repository

   - **Reference platform-specific requirements**:
     - Include platform requirements discovered (K8s version, CRI-O config, etc.)
     - Reference container runtime specifics
     - Mention OS or kernel requirements found

   Create test cases covering these categories:

   **A. Functional Test Cases** (Core feature functionality):
   - Happy path scenarios (using actual commands from docs)
   - Alternative flows (based on code analysis)
   - User workflows (from README usage examples)
   - Data validation scenarios (based on implementation details)

   **B. Regression Test Cases** (Ensure existing functionality works):
   - Related feature interactions (from integration points found)
   - Backward compatibility checks (if version info found)
   - Integration with existing modules (from dependency analysis)

   **C. Smoke Test Cases** (Critical path validation):
   - Core functionality quick checks (based on critical paths in code)
   - Basic feature availability (from installation validation)
   - Critical user journeys (from documentation examples)

   **D. Edge Cases and Negative Test Cases**:
   - Boundary value testing (based on code constraints)
   - Invalid input handling (from error handling in code)
   - Error message validation (using actual error messages from code)
   - Timeout and failure scenarios (from configuration limits)

   **E. Security Test Cases** (if applicable):
   - Authentication/Authorization checks (if auth found in code)
   - Data privacy validations (based on security requirements)
   - Input sanitization tests (from injection points in code)

   **F. Performance Test Cases** (if applicable):
   - Load testing scenarios (based on resource limits in config)
   - Response time validations (from SLO/SLA docs if found)
   - Resource usage checks (from deployment manifests)

   For each test case, generate:
   ```
   TC-{NUMBER}: {Test Case Title}

   **Priority**: High | Medium | Low
   **Component**: {component_name}
   **Tags**: [Functional, Regression, Smoke, etc.]
   **Preconditions**:
   - List of setup requirements

   **Test Steps**:
   1. Step one with clear action
   2. Step two with clear action
   3. ...

   **Expected Result**:
   - Clear, measurable expected outcome
   - Verification criteria

   **Test Data** (if applicable):
   - Input data specifications
   - Test user accounts
   - Configuration values

   **Notes**:
   - Additional considerations
   - Related test cases
   ```

5. **Apply Filters**:
   - If `--priority` filter is specified:
     - Include only test cases matching the specified priority
     - Maintain all other metadata
   - If `--component` is specified:
     - Tag all test cases with the specified component
     - Can be comma-separated for multiple components

6. **Create Document Structure**:

   Generate document with the following sections:

   ```markdown
   # Test Cases: {Feature Name}

   **Generated**: {Current Date and Time}
   **Feature**: {Feature Name}
   **Component**: {Component Name(s)}
   **Priority Filter**: {Priority Filter Applied}
   **Total Test Cases**: {Count}

   ---

   ## Table of Contents
   1. Overview
   2. Setup and Installation
   3. Test Environment Requirements
   4. Test Cases
      - 4.1 Functional Tests
      - 4.2 Regression Tests
      - 4.3 Smoke Tests
      - 4.4 Edge Cases
      - 4.5 Security Tests (if applicable)
      - 4.6 Performance Tests (if applicable)
   5. Critical Test Cases Summary
   6. Test Execution Notes

   ---

   ## 1. Overview

   **Feature Description**: {Brief description of the feature based on docs/code analysis}

   **Scope**: {What is being tested - derived from feature context}

   **Out of Scope**: {What is not covered}

   **Project**: {Repository name if identifiable}

   ---

   ## 2. Setup and Installation

   **IMPORTANT**: Populate this section with actual setup steps discovered in Step 3.

   **Installation Steps**:
   {Extract from README.md, INSTALL.md, or installation scripts found}
   - Include actual commands with full paths
   - Reference specific versions if found
   - Include prerequisite installations

   **Configuration**:
   {Extract from configuration files and setup documentation}
   - Include actual configuration file snippets
   - Reference environment variables needed
   - Include platform-specific configuration (e.g., CRI-O setup)

   **Verification**:
   {Include verification steps from documentation}
   - Commands to verify installation success
   - Expected output examples
   - Health check procedures

   ---

   ## 3. Test Environment Requirements

   **Prerequisites**:
   {Populate with actual requirements discovered in Step 3}
   - Specific tools and versions (from README/package files)
   - Platform requirements (OS, kernel version from docs)
   - Access requirements (cluster admin, specific RBAC)
   - External dependencies (databases, message queues from code analysis)

   **Test Data**:
   {Reference actual test data from existing test files or examples}
   - Test configuration files (from test/ directory)
   - Sample input data (from examples/ or test fixtures)
   - Test accounts/credentials needed

   **Dependencies**:
   {List actual dependencies discovered}
   - Runtime dependencies (Kubernetes, OpenShift from manifests)
   - External services (from integration points in code)
   - Network requirements (from deployment configs)

   ---

   ## 4. Test Cases

   ### 4.1 Functional Tests

   {Generated functional test cases - use context from Step 3}

   ### 4.2 Regression Tests

   {Generated regression test cases - use context from Step 3}

   ### 4.3 Smoke Tests

   {Generated smoke test cases - use context from Step 3}

   ### 4.4 Edge Cases

   {Generated edge case test cases - use context from Step 3}

   ### 4.5 Security Tests

   {Generated security test cases if applicable - use context from Step 3}

   ### 4.6 Performance Tests

   {Generated performance test cases if applicable - use context from Step 3}

   ---

   ## 5. Critical Test Cases Summary

   This section lists all **High Priority** and **Smoke** test cases for quick validation:

   | TC ID | Title | Priority | Type | Expected Result |
   |-------|-------|----------|------|----------------|
   | TC-001 | ... | High | Smoke | ... |
   | TC-003 | ... | High | Functional | ... |
   | ... | ... | ... | ... | ... |

   **Quick Validation Steps**:
   1. Execute all Smoke tests (TC-XXX, TC-YYY)
   2. Execute all High Priority tests
   3. Verify critical user journeys

   ---

   ## 6. Test Execution Notes

   **Execution Order**:
   - Recommended order for test execution (based on test dependencies discovered)

   **Known Issues**:
   - Any known limitations or issues discovered in Step 3 analysis
   - Reference to existing issues in issue tracker if found

   **Reporting**:
   - How to report test results
   - Defect tracking information (reference actual project tools if found)

   ---

   ## Appendix

   **Test Case Statistics**:
   - Total: {total_count}
   - High Priority: {high_count}
   - Medium Priority: {medium_count}
   - Low Priority: {low_count}
   - Smoke Tests: {smoke_count}
   - Regression Tests: {regression_count}
   - Functional Tests: {functional_count}

   **Context Analysis**:
   - Existing test files found: {count or "None"}
   - Documentation files analyzed: {count}
   - Implementation files analyzed: {count}
   - Setup steps extracted: {Yes/No}

   **Generated by**: Claude Code `/testing:generate-test-case-doc` command
   **Timestamp**: {ISO 8601 timestamp}
   **Working Directory**: {pwd output - the repository/directory being analyzed}
   **Command**: `/testing:generate-test-case-doc "{feature_name}" {flags if any}`
   ```

7. **Generate Output File**:

   **A. For Markdown format (default)**:
   - Filename: `testcases-{sanitized_feature_name}.md`
     - Sanitize feature name: lowercase, replace spaces with hyphens
     - Example: "User Authentication" → `testcases-user-authentication.md`
   - Save to current working directory
   - Use Write tool to create the file

   **B. For DOCX format**:
   - Filename: `testcases-{sanitized_feature_name}.docx`
   - Use the helper script: `python3 plugins/testing/skills/testcase-doc-generator/generate_docx.py`
   - Script usage:
     ```bash
     python3 plugins/testing/skills/testcase-doc-generator/generate_docx.py \
       --input testcases-{sanitized_feature_name}.md \
       --output testcases-{sanitized_feature_name}.docx \
       --title "Test Cases: {Feature Name}"
     ```
   - The script converts markdown to properly formatted DOCX with:
     - Styled headings (Heading 1, 2, 3)
     - Tables for test case summaries
     - Proper spacing and formatting
     - Table of contents (if supported)

8. **Display Results to User**:
   ```
   ✓ Test cases generated successfully!

   Feature: {Feature Name}
   Total Test Cases: {count}
   Priority Filter: {filter if applied}
   Component: {component if specified}

   Breakdown:
   - High Priority: {count}
   - Medium Priority: {count}
   - Low Priority: {count}

   Test Types:
   - Functional: {count}
   - Regression: {count}
   - Smoke: {count}
   - Edge Cases: {count}
   - Security: {count}
   - Performance: {count}

   Output saved to: {file_path}
   Format: {markdown/docx}

   Critical test cases ({count}) are highlighted in Section 4 for quick validation.

   Next steps:
   - Review the generated test cases
   - Customize test data and preconditions
   - Execute smoke tests first
   - Report any issues found
   ```

9. **Post-Generation Options**:
   Ask the user if they would like to:
   - Generate additional test cases for specific scenarios
   - Export to a different format
   - Create a filtered version (e.g., only smoke tests)
   - Add custom test cases to the document

## Return Value

- **Success**:
  - File path of generated test cases document
  - Summary statistics of test cases created
  - Breakdown by priority and type

- **Error**:
  - Clear error message if feature name missing
  - Validation errors for invalid flags
  - File write errors with troubleshooting steps

- **Format**: Structured summary with:
  - Generated file location
  - Test case counts and categories
  - Critical test case highlights
  - Next steps for the user

## Examples

### Example 1: Basic usage (all test cases, markdown)
```
/testing:generate-test-case-doc "User Authentication with OAuth2"
```

**Output**:
- Generates `testcases-user-authentication-with-oauth2.md`
- Includes all priority levels (High, Medium, Low)
- All test types (Functional, Regression, Smoke, Edge Cases, Security)
- Critical test summary section

### Example 2: High priority test cases only
```
/testing:generate-test-case-doc "User Authentication with OAuth2" --priority high
```

**Output**:
- Generates only High priority test cases
- Useful for critical path testing
- Faster test execution planning

### Example 3: With component tagging
```
/testing:generate-test-case-doc "User Authentication with OAuth2" --component auth
```

**Output**:
- All test cases tagged with `Component: auth`
- Helps organize test cases by module

### Example 4: Multiple components
```
/testing:generate-test-case-doc "API Gateway Rate Limiting" --component api,gateway,security
```

**Output**:
- Test cases tagged with multiple components
- Useful for cross-functional features

### Example 5: DOCX format for sharing
```
/testing:generate-test-case-doc "User Authentication with OAuth2" --format docx
```

**Output**:
- Generates `testcases-user-authentication-with-oauth2.docx`
- Professional Word document with proper formatting
- Easy to share with non-technical stakeholders

### Example 6: Filtered high-priority DOCX for specific component
```
/testing:generate-test-case-doc "Payment Processing" --priority high --component payment,security --format docx
```

**Output**:
- High priority test cases only
- Tagged with payment and security components
- DOCX format for stakeholder review
- Focused on critical payment security scenarios

### Example 7: Medium priority test cases for regression suite
```
/testing:generate-test-case-doc "Shopping Cart Updates" --priority medium --component cart
```

**Output**:
- Medium priority test cases
- Suitable for extended regression testing
- Component-specific test organization

## Arguments

- **$1** (feature_name): The name or description of the feature to generate test cases for (required)
  - Example: "User Authentication with OAuth2"
  - Can be a brief description or full feature name
  - Spaces and special characters are supported

- **--priority** (filter): Filter test cases by priority level (optional)
  - Values: `high`, `medium`, `low`, `all`
  - Default: `all` (generates all priority levels)
  - Example: `--priority high` generates only critical test cases

- **--component** (name): Tag test cases with component/module name(s) (optional)
  - Can be single component: `--component auth`
  - Can be multiple components: `--component auth,api,ui`
  - Helps organize test cases by system module
  - Default: No component tag

- **--format** (type): Output file format (optional)
  - Values: `markdown`, `docx`
  - Default: `markdown`
  - `markdown`: Creates `.md` file (text-based, version control friendly)
  - `docx`: Creates Microsoft Word document (professional formatting, easy sharing)

## Notes

- **Test Case Quality**: Generated test cases are comprehensive but should be reviewed and customized based on specific requirements
- **Component Tagging**: Use consistent component names across projects for better organization
- **Priority Guidance**:
  - **High**: Critical functionality, blocking issues, smoke tests
  - **Medium**: Important features, common user scenarios, regression coverage
  - **Low**: Edge cases, optional features, nice-to-have validations
- **DOCX Generation**: Requires Python with `python-docx` library. The helper script will notify if dependencies are missing
- **File Location**: Test cases are saved in the current working directory. Use absolute paths if needed
- **Version Control**: Markdown format is recommended for version-controlled test cases
- **Customization**: Review and enhance generated test cases with:
  - Specific test data values
  - Environment-specific configurations
  - Team-specific testing conventions
- **Integration**: Generated test cases can be imported into test management tools (TestRail, Zephyr, etc.)

## Troubleshooting

- **Missing dependencies for DOCX**:
  ```bash
  pip install python-docx
  ```

- **Invalid priority filter**: Ensure value is one of: `high`, `medium`, `low`, `all`

- **File write errors**:
  - Check write permissions in current directory
  - Ensure disk space is available
  - Verify filename doesn't contain invalid characters

- **Empty test cases**:
  - Provide more context about the feature
  - Check if feature name is too vague
  - Manually add feature description in the prompt

## See Also

- `/utils:generate-test-plan` - Generate test plans from GitHub PRs
- `/jira:generate-test-plan` - Generate test plans from JIRA issues
