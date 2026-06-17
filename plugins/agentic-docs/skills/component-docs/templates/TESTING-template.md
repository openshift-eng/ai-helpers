# [Component Name] - Testing Guide

> **Generic Testing Practices**: See [Platform Testing Practices](Platform documentation) for test pyramid philosophy (60/30/10), E2E framework patterns, and mock vs real strategies.

This guide covers **[COMPONENT]-specific** test suites and testing practices.

## Test Organization

The component follows the standard testing pyramid:

```text
        E2E Tests (10%, slow, comprehensive)
              ▲
         Integration Tests (30%, medium)
              ▲
          Unit Tests (60%, fast, focused)
```text

## Unit Tests

### Location

Unit tests live alongside the code they test:
- `pkg/controller/*/` - Controller unit tests
- `pkg/[domain]/*/` - Domain logic unit tests

### Running Unit Tests

```bash
# All unit tests
make test-unit

# Specific package
go test -v ./pkg/[package]/...

# Disable caching
go test -count=1 ./pkg/...

# With coverage
go test -cover ./pkg/...

# Coverage report
go test -coverprofile=coverage.out ./pkg/...
go tool cover -html=coverage.out
```text

### Unit Test Patterns

#### Controller Tests

Test controller logic without real Kubernetes API:

```go
func TestReconcile(t *testing.T) {
    // Use fake clientset
    client := fake.NewSimpleClientset()
    
    // Create test objects
    obj := &v1.MyResource{...}
    
    // Create reconciler
    r := &Reconciler{Client: client}
    
    // Test reconcile logic
    result, err := r.Reconcile(ctx, req)
    require.NoError(t, err)
    assert.False(t, result.Requeue)
}
```text

**For generic controller patterns**, see [Platform Controller Runtime](Platform documentation)

#### Domain Logic Tests

Test business logic:

```go
func TestDomainFunction(t *testing.T) {
    input := createTestInput()
    
    result, err := processInput(input)
    require.NoError(t, err)
    assert.Equal(t, expectedOutput, result)
}
```text

### Component-Specific Unit Test Patterns

[Document component-specific unit test patterns here]

Example:
- How to mock component-specific interfaces
- How to test component-specific algorithms
- How to test component-specific validation logic

## Integration Tests

### Location

`test/integration/` or alongside unit tests with build tag:

```go
//go:build integration
// +build integration
```text

### Running Integration Tests

```bash
# Requires KUBECONFIG set to test cluster
make test-integration

# Or with build tag
go test -v -tags=integration ./test/integration/...
```text

### Integration Test Patterns

Test with real or envtest Kubernetes API:

```go
func TestControllerIntegration(t *testing.T) {
    // Use envtest or real cluster client
    client := setupTestCluster(t)
    
    // Create real objects
    obj := &v1.MyResource{...}
    err := client.Create(ctx, obj)
    require.NoError(t, err)
    
    // Wait for reconciliation
    eventually.Assert(t, func() bool {
        err := client.Get(ctx, key, obj)
        return err == nil && obj.Status.Phase == "Ready"
    }, 30*time.Second)
}
```text

### Component-Specific Integration Tests

[Document component-specific integration test scenarios]

Example:
- Test CRD validation webhooks
- Test multi-resource workflows
- Test component-to-component interactions

## E2E Tests

### Location

`test/e2e/`

### Running E2E Tests

```bash
# Requires real OpenShift cluster
export KUBECONFIG=/path/to/kubeconfig
make test-e2e

# Or specific test
go test -v ./test/e2e/ -run TestSpecificScenario -timeout 30m
```text

### E2E Test Organization

```text
test/e2e/
├── [feature-1]_test.go        # Feature 1 E2E tests
├── [feature-2]_test.go        # Feature 2 E2E tests
└── framework/                 # E2E test utilities
    ├── client.go              # K8s client helpers
    └── helpers.go             # Test helpers
```text

### E2E Test Patterns

Test end-user scenarios:

```go
func TestFeatureE2E(t *testing.T) {
    // Setup
    client := framework.NewClient(t)
    
    // Create resource
    resource := &v1.MyResource{
        Spec: v1.MyResourceSpec{...},
    }
    err := client.Create(ctx, resource)
    require.NoError(t, err)
    
    // Wait for expected state
    err = wait.PollImmediate(5*time.Second, 5*time.Minute, func() (bool, error) {
        err := client.Get(ctx, key, resource)
        if err != nil {
            return false, err
        }
        return resource.Status.Phase == "Ready", nil
    })
    require.NoError(t, err)
    
    // Verify side effects
    verify.SideEffects(t, client, resource)
    
    // Cleanup
    defer client.Delete(ctx, resource)
}
```text

**For generic E2E patterns**, see [Platform E2E Framework](Platform documentation)

### Component-Specific E2E Scenarios

[Document component-specific E2E test scenarios]

Example:
- Happy path scenarios
- Upgrade scenarios
- Failure recovery scenarios
- Multi-resource workflows

## Test Coverage

### Current Coverage

```bash
# Generate coverage report
make coverage

# Expected coverage targets:
# - Unit tests: 60-80%
# - Integration tests: Critical paths
# - E2E tests: User-facing scenarios
```text

### Coverage Gaps

[Document known coverage gaps and plans to address them]

## CI/CD Testing

### PR Testing

CI runs on every PR:
- Unit tests (always)
- Integration tests (if applicable)
- E2E tests (critical scenarios)

See `.ci-operator.yaml` for CI configuration.

### Periodic Testing

Periodic jobs run full E2E suite:
- Upgrade tests
- Stress tests
- Long-running tests

## Debugging Failing Tests

### Unit Test Failures

```bash
# Run with verbose output
go test -v ./pkg/[package]/... -run TestSpecific

# Run with race detector
go test -race ./pkg/...
```text

### E2E Test Failures

```bash
# Check must-gather
oc adm must-gather

# Check operator logs
oc logs -n [namespace] deployment/[component]

# Check resource status
oc get [resource] -o yaml
```text

## Component-Specific Test Notes

[Add component-specific testing notes]

Example:
- Special test setup requirements
- Known flaky tests
- Test environment requirements
- Common test failures and solutions

## See Also

- [Development Guide](./[COMPONENT]_DEVELOPMENT.md)
- [Architecture](./architecture/components.md)
- [Platform Testing Practices](Platform documentation)
