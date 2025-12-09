---
description: Bootstrap OpenShift Manager (OM) integration for OpenShift operators with automated resource discovery
argument-hint: ""
---

## Name

openshift:bootstrap-om

## Synopsis

```bash
/openshift:bootstrap-om
```

## Description

The `openshift:bootstrap-om` command automates the complete integration of OpenShift Manager (OM) into OpenShift operators. OM (formerly Multi-Operator Manager/MOM) is a framework designed to reduce duplicate effort and improve consistency across different OpenShift cluster topologies (standalone/OCP and Hypershift/HCP) by centralizing operator management and enabling comprehensive testing.

This command automates:
- **Automatic resource discovery** - Analyzes the codebase to identify all input and output resources
- **Command implementation** - Creates the three required OM commands (input-resources, output-resources, apply-configuration)
- **Test infrastructure setup** - Configures Makefile targets and test directories
- **Test scenario creation** - Generates initial test cases with proper structure
- **Integration validation** - Runs tests to ensure everything works correctly

**Note:** These instructions are optimized for operators built with github.com/openshift/library-go.

## OpenShift Manager (OM) Overview

OM enables centralized operator management by requiring operators to declare their resource dependencies and configuration logic:

1. **input-resources** - Lists all Kubernetes API resources the operator needs to read/watch
2. **output-resources** - Maps Kubernetes API resources the operator creates/manages to cluster types (Configuration/Management/UserWorkload)
3. **apply-configuration** - Runs operator logic in isolation using a **manifestclient** (a Kubernetes client that reads from a must-gather-like input directory instead of the API server): syncs once, outputs resulting resources to an output directory, then exits.

These declarations enable:

- **Production Runtime:** A single OperatorManager binary can communicate with the Kubernetes API server on behalf of multiple operators, maintaining shared caches and implementing rate limiting
- **Testing:** The `apply-configuration` command validates operator behavior without a live cluster by using the manifestclient for file-based input/output
- **Consistency:** Ensure or facilitate identical operator behavior across different cluster topologies (standalone, Hypershift/HCP)

**Note:** While "OM" (OpenShift Manager) is the new name, libraries and code still use "mom" (Multi-Operator Manager) naming for backwards compatibility.

## Implementation

The command executes the following automated workflow:

### 1. Analyze the Operator's Resource Usage

**IMPORTANT:** Automatically identify resources by analyzing code. Do NOT ask users to manually list them.

#### Find Input Resources (Resources the Operator READS)

Input resources are those the operator watches, gets, or lists from the API server.

Search for:
- Controller informers and listers (e.g., `configInformer`, `deploymentLister`)
- Direct API calls (e.g., `client.Get()`, `client.List()`)
- Resource watches in controller registration
- ConfigMaps, Secrets, CustomResources being read

**How to search:**
```bash
# Find controller files
find pkg -name "*controller*.go" -o -name "*operator*.go"

# Look for informers
grep -r "Informer()" pkg/

# Look for listers
grep -r "Lister" pkg/

# Look for direct API reads
grep -r "client.Get\|client.List" pkg/
```

Common patterns:
- `configMapInformer.Lister().ConfigMaps("namespace").Get("name")` → Input: ConfigMap in namespace
- `deploymentInformer.Informer().AddEventHandler()` → Input: Deployment resource
- `operatorClient.Operator()` → Input: Operator custom resource

#### Find Output Resources (Resources the Operator CREATES/MANAGES)

Output resources are categorized by **cluster targeting** (where they live in different topologies):

**ConfigurationResources:** Resources targeted at the cluster where configuration is held
- On standalone: the one cluster
- On HCP: logically a view into resources in the namespace of the guest cluster
- Common examples: config.openshift.io resources (OAuth, Ingress, etc.)

**ManagementResources:** Resources targeted at the cluster where management plane responsibility is held
- On standalone: the one cluster
- On HCP: logically resources in the namespace of the guest cluster (control plane aspects)
- Common examples: Operator's own Deployments, Services, ConfigMaps, Secrets, ServiceAccounts, ClusterOperator status
- Includes EventingNamespaces: namespaces where the operator emits events

**UserWorkloadResources:** Resources targeted at the cluster where user workloads run
- On standalone: the one cluster
- On HCP: the guest cluster
- Common examples: ClusterRoles, ClusterRoleBindings, CRDs, resources that run alongside user workloads

**How to search:**
```bash
# Find manifests and bindata
find bindata/ manifests/ -type f 2>/dev/null

# Look for resource creation/apply
grep -r "Apply\|Create\|Update" pkg/ | grep -i "deployment\|service\|configmap"

# Look for manifest files
grep -r "apiVersion:" bindata/ manifests/ 2>/dev/null
```

Common patterns:
- Files in `bindata/` or `manifests/` → Output resources
- `resourceapply.ApplyDeployment()` → Output: Deployment
- `resourceapply.ApplyConfigMap()` → Output: ConfigMap
- ClusterOperator status updates → Output: ClusterOperator

### 2. Prepare Dependencies

Before creating command stubs, manually add the dependency to go.mod:

```go
// In the require section of go.mod, add:
github.com/openshift/multi-operator-manager v0.0.0-20250930141021-05cb0b9abdb4
```

**Note:** Don't run `go mod tidy` yet - it will remove the dependency since no code imports it yet. After creating the stub files that import the library, you'll run `go mod tidy && go mod vendor`, and the dependency will be committed together with the stubs in the first commit

### 3. Implement the Three OM Commands (Incrementally)

**IMPORTANT:** Create command stubs first, then fill them in with actual resource declarations. This creates a clean, logical git history with ~6-8 focused commits:

1. Create command stub → integrate into CLI → commit
2. Fill in the stub with discovered resources → commit
3. Repeat for each command
4. Set up test infrastructure → commit
5. (Optional) Add test scenario if apply-configuration works → commit

#### Common Patterns

**Directory structure:**
```bash
mkdir -p pkg/cmd/mom
```
Note: We keep the `mom` directory name for consistency with library imports.

**Helper functions** for declaring resources (use in both input-resources and output-resources):

Common resources:
- `ExactConfigMap(namespace, name)`, `ExactSecret(namespace, name)`, `ExactDeployment(namespace, name)`
- `ExactService(namespace, name)`, `ExactServiceAccount(namespace, name)`, `ExactNamespace(name)`
- `ExactRole(namespace, name)`, `ExactRoleBinding(namespace, name)`

OpenShift-specific:
- `ExactConfigResource(name)` - For config.openshift.io resources (e.g., "oauths", "ingresses")
- `ExactLowLevelOperator(name)` - For operator.openshift.io resources
- `ExactClusterOperator(name)` - For ClusterOperators

Cluster-scoped RBAC:
- `ExactClusterRole(name)`, `ExactClusterRoleBinding(name)`

Other:
- `ExactPDB(namespace, name)`, `ExactOAuthClient(name)`, `GeneratedCSR(prefix)`
- `ExactResource(group, version, resource, namespace, name)` - For any other resource

**CLI integration pattern** (add to `cmd/*/main.go`):
```go
import (
        "github.com/openshift/YOUR-OPERATOR/pkg/cmd/mom"
)

// In your main command function:
cmd.AddCommand(mom.NewInputResourcesCommand(ioStreams))
cmd.AddCommand(mom.NewOutputResourcesCommand(ioStreams))
cmd.AddCommand(mom.NewApplyConfigurationCommand(ioStreams))
```

**Build/test pattern:**
```bash
make build
./your-operator-binary <command-name>  # Test the command
git add <files>
git commit -m "<title>

<optional description>

Generated with Claude Code"
```

#### 3.1 Create and Commit input-resources Command Stub

Create `pkg/cmd/mom/input_resources_command.go`:

```go
package mom

import (
        "context"

        "github.com/openshift/multi-operator-manager/pkg/library/libraryinputresources"
        "github.com/spf13/cobra"
        "k8s.io/cli-runtime/pkg/genericiooptions"
)

func NewInputResourcesCommand(streams genericiooptions.IOStreams) *cobra.Command {
        return libraryinputresources.NewInputResourcesCommand(runInputResources, runOutputResources, streams)
}

func runInputResources(ctx context.Context) (*libraryinputresources.InputResources, error) {
        return &libraryinputresources.InputResources{
                ApplyConfigurationResources: libraryinputresources.ResourceList{
                        ExactResources: []libraryinputresources.ExactResourceID{
                                // TODO: Fill in discovered resources
                        },
                },
        }, nil
}
```

Integrate into CLI (see Common Patterns), build, test, and commit with title: "Add OM input-resources command stub"

#### 3.2 Fill in input-resources and Commit

Analyze the codebase to discover all input resources (see Section 1 for search patterns).

Update `runInputResources` function with discovered resources:

```go
func runInputResources(ctx context.Context) (*libraryinputresources.InputResources, error) {
        return &libraryinputresources.InputResources{
                ApplyConfigurationResources: libraryinputresources.ResourceList{
                        ExactResources: []libraryinputresources.ExactResourceID{
                                // Example discovered resources (see Helper Functions):
                                libraryinputresources.ExactLowLevelOperator("youroperators"),
                                libraryinputresources.ExactConfigResource("infrastructures"),
                                libraryinputresources.ExactNamespace("your-operator-namespace"),
                                libraryinputresources.ExactConfigMap("namespace", "config-name"),
                                // ... all discovered input resources
                        },
                },
        }, nil
}
```

Build, test, and commit with title: "Populate OM input-resources with discovered resources"

#### 3.3 Create and Commit output-resources Command Stub

Create `pkg/cmd/mom/output_resources_command.go`:

```go
package mom

import (
        "context"

        "github.com/openshift/multi-operator-manager/pkg/library/libraryoutputresources"
        "github.com/spf13/cobra"
        "k8s.io/cli-runtime/pkg/genericiooptions"
)

func NewOutputResourcesCommand(streams genericiooptions.IOStreams) *cobra.Command {
        return libraryoutputresources.NewOutputResourcesCommand(runOutputResources, streams)
}

func runOutputResources(ctx context.Context) (*libraryoutputresources.OutputResources, error) {
        return &libraryoutputresources.OutputResources{
                ConfigurationResources: libraryoutputresources.ResourceList{
                        ExactResources: []libraryoutputresources.ExactResourceID{},
                },
                ManagementResources: libraryoutputresources.ResourceList{
                        ExactResources: []libraryoutputresources.ExactResourceID{},
                        EventingNamespaces: []string{},
                },
                UserWorkloadResources: libraryoutputresources.ResourceList{
                        ExactResources: []libraryoutputresources.ExactResourceID{},
                },
        }, nil
}
```

Integrate into CLI, build, test, and commit with title: "Add OM output-resources command stub"

#### 3.4 Fill in output-resources and Commit

Analyze the codebase to discover all output resources (see Section 1 for search patterns and category descriptions).

Update `runOutputResources` function with discovered resources:

```go
func runOutputResources(ctx context.Context) (*libraryoutputresources.OutputResources, error) {
        return &libraryoutputresources.OutputResources{
                ConfigurationResources: libraryoutputresources.ResourceList{
                        ExactResources: []libraryoutputresources.ExactResourceID{
                                libraryoutputresources.ExactConfigResource("ingresses"),
                        },
                },
                ManagementResources: libraryoutputresources.ResourceList{
                        ExactResources: []libraryoutputresources.ExactResourceID{
                                libraryoutputresources.ExactClusterOperator("operatorname"),
                                libraryoutputresources.ExactNamespace("namespace"),
                                libraryoutputresources.ExactDeployment("namespace", "name"),
                                // ... all discovered management resources
                        },
                        EventingNamespaces: []string{
                                "operator-namespace",
                        },
                },
                UserWorkloadResources: libraryoutputresources.ResourceList{
                        ExactResources: []libraryoutputresources.ExactResourceID{
                                libraryoutputresources.ExactClusterRole("name"),
                                libraryoutputresources.ExactClusterRoleBinding("name"),
                        },
                },
        }, nil
}
```

Build, test, and commit with title: "Populate OM output-resources with discovered resources"

#### 3.5 Create apply-configuration Command Stub and Commit

**This is the most complex command.** It requires running your operator's reconciliation logic once using the manifestclient.

Create `pkg/cmd/mom/apply_configuration_command.go`:

```go
package mom

import (
        "context"
        "fmt"

        "github.com/openshift/multi-operator-manager/pkg/library/libraryapplyconfiguration"
        "github.com/spf13/cobra"
        "k8s.io/cli-runtime/pkg/genericiooptions"
)

func NewApplyConfigurationCommand(streams genericiooptions.IOStreams) *cobra.Command {
        return libraryapplyconfiguration.NewApplyConfigurationCommand(RunApplyConfiguration, runOutputResources, streams)
}

func RunApplyConfiguration(ctx context.Context, input libraryapplyconfiguration.ApplyConfigurationInput) (*libraryapplyconfiguration.ApplyConfigurationRunResult, libraryapplyconfiguration.AllDesiredMutationsGetter, error) {
        // TODO: Implement operator reconciliation logic
        //
        // The manifestclient (input.ManagementClient) is a drop-in replacement for standard k8s clients.
        // Pass it to your operator and run sync logic ONCE (not in a loop).
        //
        // Example: op := operator.NewOperator(input.ManagementClient, input.ManagementEventRecorder)
        //          if err := op.Sync(ctx); err != nil { return nil, nil, err }
        //          return &libraryapplyconfiguration.ApplyConfigurationRunResult{}, nil, nil
        //
        // See: github.com/openshift/cluster-authentication-operator/pkg/cmd/mom/apply_configuration_command.go

        return nil, nil, fmt.Errorf("not yet implemented - see TODO above")
}
```

Integrate into CLI, build (verify it compiles), and commit with title: "Add OM apply-configuration command stub"

**Note:** If you cannot implement apply-configuration fully, that's acceptable! The stub provides instructions for manual implementation later.

### 4. Set Up Test Infrastructure and Commit

**IMPORTANT:** Check if the project uses `build-machinery-go` before proceeding:

```bash
ls vendor/github.com/openshift/build-machinery-go/make/targets/openshift/operator/mom.mk
```

**If build-machinery-go is NOT present:**
- Inform the user that test infrastructure requires `build-machinery-go`
- Explain they need to vendor `github.com/openshift/build-machinery-go` first
- Skip test infrastructure setup (OM commands are still usable without it)

**If build-machinery-go IS present:**

#### 4.1 Update Makefile

Add to your `Makefile`:

```makefile
include $(addprefix ./vendor/github.com/openshift/build-machinery-go/make/, \
        targets/openshift/operator/mom.mk \
)
```

This provides:
- `make test-operator-integration` - Runs OM tests and validates output
- `make update-test-operator-integration` - Updates expected test output

#### 4.2 Create Test Scenarios (Optional - only if apply-configuration is implemented)

Create test directory structure:

```bash
mkdir -p test-data/apply-configuration/overall/minimal-cluster/input-dir
```

Each test scenario needs:
- **`test.yaml`** - Test metadata (binaryName, testName, description, testType, now)
- **`input-dir/`** - Input resources in must-gather format organized by `cluster-scoped-resources/<group>/<kind>.yaml` or `namespaces/<namespace>/<group>/<kind>/<name>.yaml`

Run initial test:
```bash
make build
make test-operator-integration
make update-test-operator-integration  # Update expected output
make test-operator-integration  # Should now pass
```

Commit Makefile (and test-data/ if created) with title: "Add OM test infrastructure"

### 5. Verify and Iterate

1. Run `make test-operator-integration` - Should pass after updating expected output
2. Create additional test scenarios for different configurations
3. Verify input-resources and output-resources are complete by checking test output

## Reference Implementation

**Study these files in `cluster-authentication-operator`:**
- `pkg/cmd/mom/input_resources_command.go` - Complete input resource declarations
- `pkg/cmd/mom/output_resources_command.go` - Complete output resource declarations
- `pkg/cmd/mom/apply_configuration_command.go` - Integration with operator core logic
- `cmd/*/main.go` - CLI integration pattern
- `Makefile` - OM makefile inclusion
- `test-data/apply-configuration/overall/` - Multiple test scenario examples

**Documentation:**
- [Multi-Operator Manager Development Guide](https://github.com/openshift/enhancements/blob/master/dev-guide/multi-operator-manager.md)
- [multi-operator-manager Repository](https://github.com/openshift/multi-operator-manager)
- [cluster-authentication-operator](https://github.com/openshift/cluster-authentication-operator)

**Key Concept - manifestclient:**
Implements standard Kubernetes client interfaces (`client.Client`, `kubernetes.Interface`, `dynamic.Interface`). It's a drop-in replacement that reads from files instead of the API server - no refactoring needed!

## Validation Checklist

Before considering OM integration complete:

- [ ] `pkg/cmd/mom/input_resources_command.go` exists and lists all input resources
- [ ] `pkg/cmd/mom/output_resources_command.go` exists and lists all output resources
- [ ] `pkg/cmd/mom/apply_configuration_command.go` exists (stub or implementation)
- [ ] Commands integrated into main CLI
- [ ] `Makefile` includes `mom.mk` (if build-machinery-go available)
- [ ] At least one test scenario in `test-data/apply-configuration/overall/` (if apply-configuration implemented)
- [ ] `make test-operator-integration` passes (if tests created)

## Usage Guidelines

1. **Separate Dependency Commits** - ALWAYS commit dependency changes separately. Any changes to `go.mod`, `go.sum`, or `vendor/` must go in their own commits. NEVER mix vendor changes with code implementation.

2. **Automatic Analysis** - Analyze codebase automatically. Do NOT ask users to list resources.

3. **apply-configuration Can Be a Stub** - If you cannot implement it fully, create a comprehensive stub with TODO comments. This is acceptable!

4. **Validate Early** - Build and test after each command stub/fill-in to catch issues immediately.

The command should autonomously complete all steps from resource discovery through test infrastructure setup (if build-machinery-go is available), creating focused, logical commits that are easy to review.
