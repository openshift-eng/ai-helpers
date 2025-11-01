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
7. **Assess Best Practices**: **MUST follow the standards defined in "Testing Guidelines and References" section below**
8. **Generate Recommendations**: Provide actionable improvement suggestions based on the guidelines

**CRITICAL**: All reviews MUST be evaluated against the specific standards, references, and best practices listed in the **"Testing Guidelines and References"** section below. Do not use generic testing advice - follow the OpenShift-specific guidelines provided.

## Testing Guidelines and References

The review follows established testing best practices from:

**For Ginkgo/E2E Tests:**
- OpenShift Origin Test Extended: https://github.com/openshift/origin/tree/master/test/extended
- Ginkgo Testing Framework: https://onsi.github.io/ginkgo/
- OpenShift Test Best Practices: https://github.com/openshift/origin/blob/master/test/extended/README.md

**For oc CLI Tests:**
- OpenShift CLI Documentation: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/developer-cli-commands.html
- Bash Best Practices: https://google.github.io/styleguide/shellguide.html

**Key Testing Standards:**
- Use descriptive, stable test names (no timestamps, random IDs)
- Proper resource cleanup (AfterEach, defer, trap)
- Meaningful assertions with clear failure messages
- Test isolation (each test creates own resources)
- Appropriate timeouts and waits
- No BeforeAll/AfterAll in Ginkgo tests
- Use framework helpers (e2epod, e2enode) when available

## Arguments

- **$1** (file-path-or-test-code-or-commands): One of:
  - **File path**: Path to test file (shell script or Go test file)
  - **oc commands**: Set of oc CLI commands to review
  - **Test code**: Pasted test code (Ginkgo or shell script)
