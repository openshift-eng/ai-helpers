---
description: Write and validate new OpenShift E2E tests using Ginkgo framework
argument-hint: [test-specification]
---

## Name
openshift:new-e2e-test

## Synopsis
```
/new-e2e-test [test-specification]
```

## Description

The `new-e2e-test` command assists in writing and validating
new tests for the OpenShift test suite. It follows best practices for
Ginkgo-based testing and ensures test reliability through automated
validation.

This command handles the complete lifecycle of test development:
- Writes tests following Ginkgo patterns and OpenShift conventions
- Validates tests for reliability through multiple test runs
- Ensures proper test naming and structure
- Handles both origin repository and extension tests appropriately

## Test Framework Guidelines

### Ginkgo Framework
- OpenShift-tests uses **Ginkgo** as its testing framework
- Tests are organized in a BDD (Behavior-Driven Development) style with Describe/Context/It blocks
- All tests should follow Ginkgo patterns and conventions except
    - You MUST NOT use BeforeAll, AfterAll hooks
    - MUST NOT use ginkgo.Serial, instead use the [Serial] annotation in the test name if non-parallel execution is required

### Repository-Specific Guidelines

#### Origin Repository Tests

If working in the "origin" code repository:
- All tests should go into the `test/extended` directory
- If creating a new package, import it into `test/extended/include.go`
- After writing your test, **MUST** rebuild the openshift-tests binary using `make openshift-tests`

#### Other repositories

Other repositories have have different conventions for locations of
tests and how they get imported. Examine the code base and follow the
conventions defined.

## Critical Test Requirements

### Test Names

**CRITICAL**: Test names must be stable and deterministic.

#### ❌ NEVER Include Dynamic Information:
- Pod names (e.g., "test-pod-abc123")
- Timestamps
- Random UUIDs or generated identifiers
- Node names
- Namespace names with random suffixes
- Limits that may change later

#### ✅ ALWAYS Use Descriptive, Static Names:
- **Good example**: "should create a pod with custom security context"
- **Bad example**: "should create pod test-pod-xyz123 with custom security context"

- **Good example**: "should create a pod within a reasonable timeframe"
- **Bad example**: "should create a pod within 15 seconds"

### Results

**CRITICAL**: Tests must always produce a pass, fail or skip result. Do
not create tests that only produce pass or only produce a fail result.

## Test Structure Guidelines

### Best Practices

- Tests should be focused and test one specific behavior
- Use proper setup and cleanup in BeforeEach/AfterEach blocks
- Include appropriate timeouts for operations
- Add meaningful assertions with clear failure messages
- Follow existing patterns in the codebase for consistency

## Implementation

The command performs the following steps:

1. **Analyze Specification**: Parse the test specification provided by the user
2. **Write Test**: Create a new test file following Ginkgo and OpenShift conventions
   - Determine correct location
   - Follow proper test structure
   - Use stable, descriptive naming
   - Implement proper setup/cleanup
3. **Build Binary**: Rebuild the appropriate test binary (openshift-tests or a test extension)

## Arguments

- **$1** (test-specification): Description of the test behavior to validate. Should clearly specify:
  - What feature/behavior to test
  - Expected outcomes
  - Any specific conditions or configurations
