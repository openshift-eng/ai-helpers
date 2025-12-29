---
description: Generate E2E tests for VPA operator from description or PR
argument-hint: "<description or PR-URL> [--output-dir <path>]"
---

## Name
vpa-testgen:generate-vpa-tests

## Synopsis
```
/vpa-testgen:generate-vpa-tests <input> [--output-dir <path>]
```

## Description

The `vpa-testgen:generate-vpa-tests` command generates comprehensive Ginkgo-based E2E tests for the VPA (Vertical Pod Autoscaler) operator based on a text description, GitHub PR URL, or scenario.

**Key Features:**
- Accepts flexible input: text description, PR URL, or bug/feature scenario
- Generates Ginkgo E2E tests following OpenShift conventions
- Includes proper setup/teardown, assertions, and error handling
- Outputs test files ready for integration into the operator repository

## Implementation

### Phase 1: Input Analysis

1. **Determine Input Type**:
   - **GitHub PR URL**: Extract and analyze PR changes
   - **Text description**: Parse scenario/bug/feature description
   - **File path**: Read specification from file

2. **For GitHub PR URL** (e.g., `https://github.com/openshift/vertical-pod-autoscaler-operator/pull/123`):
   ```bash
   gh pr view {PR_NUMBER} --repo {REPO} --json title,body,files,commits
   ```
   - Extract PR title and description
   - Analyze changed files
   - Understand implementation context

3. **For Text Description**:
   - Parse the scenario description
   - Identify:
     - Type: bug fix, feature, edge case
     - Affected components (recommender, updater, admission-controller)
     - Expected behavior
     - Failure conditions (if bug)

4. **Extract Test Requirements**:
   - What should be tested
   - Expected outcomes
   - Edge cases to cover
   - VPA modes involved (Off, Initial, Recreate, Auto)

### Phase 2: Test Generation

1. **Determine Test Categories**:
   - **Positive tests**: Valid inputs, expected workflows
   - **Negative tests**: Invalid inputs, error handling
   - **Edge cases**: Boundary values, resource limits
   - **Regression tests**: Specific to bug fixes

2. **Generate Ginkgo Test Structure**:

   ```go
   var _ = Describe("[sig-autoscaling] VPA", func() {
       var (
           oc = exutil.NewCLI("vpa-e2e")
           ns string
       )

       BeforeEach(func() {
           ns = oc.Namespace()
           // Setup code
       })

       AfterEach(func() {
           // Cleanup code
       })

       Context("when [scenario from description]", func() {
           It("should [expected behavior]", func() {
               // Test implementation
           })
       })
   })
   ```

3. **Apply VPA-Specific Patterns**:
   - VPA resource creation and validation
   - Pod resource recommendation verification
   - Update mode testing (Off, Initial, Recreate, Auto)
   - Container resource policy validation
   - Integration with workload controllers (Deployment, StatefulSet, etc.)

### Phase 3: Test File Output

1. **Output Location** (in order of preference):
   - If `--output-dir` provided: Use specified directory
   - If in VPA operator repo: `test/e2e/` directory
   - Default: `.work/vpa-testgen/{sanitized-name}/`

2. **File Naming Convention**:
   - For PR: `pr-{number}_test.go`
   - For description: `{sanitized-description}_test.go`
   - Example: `pr-123_test.go` or `vpa-empty-deployment_test.go`

3. **Generated File Structure**:
   ```
   .work/vpa-testgen/{name}/
   ├── {name}_test.go           # Main test file
   ├── helpers.go               # Test helpers (if needed)
   └── README.md                # Test documentation
   ```

## Test Framework Guidelines

### Ginkgo Conventions (CRITICAL)
- Use `Describe/Context/It` blocks following BDD style
- **NEVER** use `BeforeAll` or `AfterAll` hooks
- **NEVER** use `ginkgo.Serial` - use `[Serial]` annotation in test name instead
- Use stable, descriptive test names (no dynamic IDs, timestamps, pod names)

### VPA-Specific Test Patterns

```go
// Example: VPA Recommendation Test
It("should provide resource recommendations for a deployment", func() {
    // 1. Create a deployment with known resource usage
    deployment := createTestDeployment(oc, ns, "test-app")
    
    // 2. Create VPA with Auto updateMode
    vpa := createVPA(oc, ns, "test-vpa", deployment.Name, "Auto")
    
    // 3. Wait for recommendations
    Eventually(func() bool {
        return hasValidRecommendations(oc, ns, vpa.Name)
    }, 5*time.Minute, 10*time.Second).Should(BeTrue())
    
    // 4. Verify recommendations are within expected range
    recommendations := getVPARecommendations(oc, ns, vpa.Name)
    Expect(recommendations.ContainerRecommendations).NotTo(BeEmpty())
})
```

### Required Imports

```go
import (
    "context"
    "time"

    g "github.com/onsi/ginkgo/v2"
    o "github.com/onsi/gomega"
    
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
    "k8s.io/client-go/kubernetes"
    
    exutil "github.com/openshift/origin/test/extended/util"
)
```

## Return Value

- **Generated Files**: Path to generated test files
- **Summary**: Number of test cases generated, coverage areas
- **Next Steps**: Instructions for integrating tests into the operator repo

## Examples

1. **Generate tests from text description**:
   ```
   /vpa-testgen:generate-vpa-tests VPA should handle pods with no resource requests gracefully
   ```
   
   Output:
   ```
   Generated E2E tests:
   - File: .work/vpa-testgen/vpa-no-resource-requests/vpa_no_resource_requests_test.go
   - Test cases: 3
     - should provide recommendations for pods without resource requests
     - should not crash when targeting pods with missing requests
     - should apply default recommendations when no baseline exists
   ```

2. **Generate tests from GitHub PR**:
   ```
   /vpa-testgen:generate-vpa-tests https://github.com/openshift/vertical-pod-autoscaler-operator/pull/456
   ```

3. **Generate tests for bug scenario**:
   ```
   /vpa-testgen:generate-vpa-tests Bug: VPA updater crashes when deployment has 0 replicas
   ```

4. **Generate tests for feature**:
   ```
   /vpa-testgen:generate-vpa-tests Feature: Support minAllowed and maxAllowed per container in VPA spec
   ```

5. **Generate tests with custom output directory**:
   ```
   /vpa-testgen:generate-vpa-tests "VPA recommendation accuracy test" --output-dir ./test/e2e/vpa
   ```

## Arguments

- **$1** (required): Test scenario input. Can be one of:
  - **Text description**: Free-form description of what to test
    - Example: `"VPA should scale memory for Java apps correctly"`
  - **Bug description**: Prefix with "Bug:" for regression tests
    - Example: `"Bug: VPA crashes with empty containerPolicies"`
  - **Feature description**: Prefix with "Feature:" for new functionality
    - Example: `"Feature: VPA supports CronJob workloads"`
  - **GitHub PR URL**: Full URL to a VPA-related PR
    - Example: `https://github.com/openshift/vertical-pod-autoscaler-operator/pull/123`
  
- **--output-dir** (optional): Custom output directory for generated tests
  - Default: `.work/vpa-testgen/{sanitized-name}/`

## VPA Components Reference

When generating tests, consider these VPA components:

| Component | Purpose | Test Focus |
|-----------|---------|------------|
| **Recommender** | Computes resource recommendations | Recommendation accuracy, resource usage analysis |
| **Updater** | Evicts pods for updates | Pod eviction, update timing, disruption handling |
| **Admission Controller** | Mutates pod resources | Resource injection, container matching |

## VPA Update Modes

| Mode | Behavior | Test Considerations |
|------|----------|---------------------|
| **Off** | Only provides recommendations, no updates | Verify recommendations exist but pods unchanged |
| **Initial** | Sets resources only at pod creation | Verify new pods get resources, existing unchanged |
| **Recreate** | Evicts pods to apply new resources | Verify eviction and new resource values |
| **Auto** | Currently same as Recreate | Full lifecycle testing |

## Error Handling

The command will:
- Parse description to understand test requirements
- If PR URL provided, fetch PR details via `gh` CLI
- Generate meaningful tests even from brief descriptions
- Ask clarifying questions if the scenario is ambiguous

## Post-Generation Steps

After generating tests:

1. **Review Generated Tests**: Verify test logic matches requirements
2. **Adjust Test Parameters**: Customize timeouts, resource values as needed
3. **Run Locally**: 
   ```bash
   go test -v ./test/e2e/... -run "TestNamePattern"
   ```
4. **Integrate**: Move tests to appropriate location in operator repo
5. **PR**: Create PR with new tests
