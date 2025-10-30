---
description: Review test cases for completeness, quality, and best practices - accepts file path or direct oc commands/test code
argument-hint: [file-path-or-test-code-or-commands]
---

## Name
openshift:review-test-cases

## Synopsis
```
/openshift:review-test-cases [file-path-or-test-code-or-commands]
```

## Description

The `review-test-cases` command provides comprehensive review of OpenShift test cases to ensure quality, completeness, and adherence to best practices. It accepts three types of input:

1. **File path**: Path to test file (e.g., `/path/to/test.sh` or `/path/to/test.go`)
2. **oc commands**: Direct oc CLI commands to review (e.g., paste a set of oc commands)
3. **Test code**: Pasted Ginkgo test code to analyze

The command analyzes test code in both oc CLI shell scripts and Ginkgo Go tests, helping QE engineers identify gaps in test coverage, improve test reliability, and ensure tests follow OpenShift testing standards.

## Implementation

The command analyzes test cases and provides structured feedback:

1. **Parse Test Input**: Determine if input is a file path, oc commands, or test code
   - If file path: Read and analyze the test file
   - If oc commands: Parse command sequence
   - If test code: Analyze pasted Ginkgo/test code
2. **Identify Test Format**: Detect if it's oc CLI shell script or Ginkgo Go code
3. **Analyze Test Structure**: Review organization, naming, and patterns
4. **Check Coverage**: Verify positive, negative, and edge case coverage
5. **Review Assertions**: Ensure proper validation and error checking
6. **Evaluate Cleanup**: Verify resource cleanup and namespace management
7. **Assess Best Practices**: Check against OpenShift testing guidelines
8. **Generate Recommendations**: Provide actionable improvement suggestions

## Arguments

- **$1** (file-path-or-test-code-or-commands): One of:
  - **File path**: Path to test file (shell script or Go test file)
  - **oc commands**: Set of oc CLI commands to review
  - **Test code**: Pasted test code (Ginkgo or shell script)
