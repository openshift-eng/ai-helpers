---
description: Expand basic test ideas or existing oc commands into comprehensive test scenarios with edge cases in oc CLI or Ginkgo format
argument-hint: [test-idea-or-file-or-commands] [format]
---

## Name
openshift:expand-test-case

## Synopsis
```
/openshift:expand-test-case [test-idea-or-file-or-commands] [format]
```

## Description

The `expand-test-case` command transforms basic test ideas or existing oc commands into comprehensive test scenarios. It accepts three types of input:

1. **Test idea**: Simple description of what to test (e.g., "verify pod deployment")
2. **File path**: Path to existing test file to expand (e.g., `/path/to/test.sh` or `/path/to/test.go`)
3. **oc commands**: Direct oc CLI commands to analyze and expand (e.g., `oc create pod nginx`)

The command expands the input to cover positive flows, negative scenarios, edge cases, and boundary conditions, helping QE engineers ensure thorough test coverage.

Supports two output formats:
- **oc CLI**: Shell scripts with oc commands for manual or automated execution
- **Ginkgo**: Go test code using Ginkgo/Gomega framework for E2E tests

## Implementation

The command analyzes the input and generates comprehensive scenarios:

1. **Parse Input**: Determine if input is a test idea, file path, or oc commands
   - If file path: Read and analyze existing test code
   - If oc commands: Parse commands to understand what's being tested
   - If test idea: Understand the core feature or behavior
2. **Identify Test Dimensions**: Determine coverage aspects (functionality, security, performance, edge cases)
3. **Generate Positive Tests**: Happy path scenarios where everything works
4. **Generate Negative Tests**: Error handling, invalid inputs, permission issues
5. **Add Edge Cases**: Boundary values, race conditions, resource limits
6. **Define Validation**: Clear success criteria and assertions
7. **Format Output**: Generate in requested format (oc CLI or Ginkgo) - **MUST follow the standards in "Test Coverage Guidelines" section below**

**CRITICAL**: All generated test scenarios MUST adhere to the coverage dimensions, best practices, and standards defined in the **"Test Coverage Guidelines"** section below. Use the referenced examples and patterns from OpenShift origin repository.

## Test Coverage Guidelines

The command generates comprehensive test scenarios following industry best practices:

**Test Coverage Dimensions:**
- **Positive Tests**: Valid inputs and expected workflows
- **Negative Tests**: Invalid inputs, permission errors, missing dependencies
- **Edge Cases**: Boundary values (0, max values, empty inputs, special characters)
- **Security Tests**: RBAC validation, security context enforcement, privilege escalation
- **Resource Tests**: Low memory, disk pressure, network issues, rate limiting
- **Concurrency**: Multiple operations happening simultaneously
- **Failure Recovery**: Restart behavior, cleanup on failure

**References:**
- OpenShift Test Examples: https://github.com/openshift/origin/tree/master/test/extended
- Ginkgo BDD Framework: https://onsi.github.io/ginkgo/
- Test Pattern Catalog: https://github.com/openshift/origin/blob/master/test/extended/README.md
- oc CLI Reference: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/developer-cli-commands.html

**Best Practices Applied:**
- Use stable, descriptive test names (no dynamic IDs or timestamps)
- Ensure proper resource cleanup (prevent resource leaks)
- Include meaningful assertions with clear failure messages
- Isolate tests (each test creates its own resources)
- Add appropriate timeouts to prevent hanging tests
- Follow Ginkgo patterns: Describe/Context/It hierarchy
- Use framework helpers: e2epod, e2enode, e2enamespace

## Arguments

- **$1** (test-idea-or-file-or-commands): One of:
  - **Test idea**: Description of what to test
  - **File path**: Path to existing test file
  - **oc commands**: Set of oc CLI commands to analyze and expand
- **$2** (format): Output format - "oc CLI" or "Ginkgo" (optional, will prompt if not provided)
