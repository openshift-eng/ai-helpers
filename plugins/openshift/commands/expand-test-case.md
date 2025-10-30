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
7. **Format Output**: Generate in requested format (oc CLI or Ginkgo)

## Arguments

- **$1** (test-idea-or-file-or-commands): One of:
  - **Test idea**: Description of what to test
  - **File path**: Path to existing test file
  - **oc commands**: Set of oc CLI commands to analyze and expand
- **$2** (format): Output format - "oc CLI" or "Ginkgo" (optional, will prompt if not provided)
