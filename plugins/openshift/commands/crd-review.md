---
description: Review Kubernetes CRDs against Kubernetes and OpenShift API conventions
argument-hint: [repository-path]
---

## Name
openshift:crd-review

## Synopsis
```
/openshift:crd-review [repository-path]
```

## Description

The `openshift:crd-review` command analyzes Go Kubernetes Custom Resource Definitions (CRDs) in a repository against both:
- **Kubernetes API Conventions** as defined in the [Kubernetes community guidelines](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md)
- **OpenShift API Conventions** as defined in the [OpenShift development guide](https://github.com/openshift/enhancements/blob/master/dev-guide/api-conventions.md)

This command helps ensure CRDs follow best practices for:
- API naming conventions and patterns
- Resource structure and field organization
- Status field design and patterns
- Field types and validation
- Documentation standards
- OpenShift-specific requirements

The review covers Go API type definitions, providing actionable feedback to improve API design.

## Key Convention Checks

### Kubernetes API Conventions

#### Naming Conventions
- **Resource Names**: Must follow DNS label format (lowercase, alphanumeric, hyphens)
- **Field Names**: PascalCase for Go, camelCase for JSON
- **Avoid**: Abbreviations, underscores, ambiguous names
- **Include**: Units/types in field names when needed (e.g., `timeoutSeconds`)

#### API Structure
- **Required Fields**: Every API object must embed a `k8s.io/apimachinery/pkg/apis/meta/v1` `TypeMeta` struct
- **Metadata**: Every API object must include a `k8s.io/apimachinery/pkg/apis/meta/v1` `ObjectMeta` struct called `metadata`
- **Spec/Status Separation**: Clear separation between desired state (spec) and observed state (status)

#### Status Field Design
- **Conditions**: Must include conditions array with:
  - `type`: Clear, human-readable condition type
  - `status`: `True`, `False`, or `Unknown`
  - `reason`: Machine-readable reason code
  - `message`: Human-readable message
  - `lastTransitionTime`: RFC 3339 timestamp

#### Field Types
- **Integers**: Prefer `int32` over `int64`
- **Avoid**: Unsigned integers, floating-point values
- **Enums**: Use string constants, not numeric values
- **Optional Fields**: Use pointers in Go

#### Versioning
- **Group Names**: Use domain format (e.g., `myapp.example.com`)
- **Version Strings**: Must match DNS label format (e.g., `v1`, `v1beta1`)
- **Migration**: Provide clear paths between versions

### OpenShift API Conventions

#### Configuration vs Workload APIs
- **Configuration APIs**: Typically cluster-scoped, manage cluster behavior
- **Workload APIs**: Usually namespaced, user-facing resources

#### Field Design
- **Avoid Boolean Fields**: Use enumerations instead of binary true/false
  - ❌ Bad: `enabled: true`
  - ✅ Good: `state: "Enabled"` with enum values `["Enabled", "Disabled", "Auto"]`
- **Object References**: Use specific types, omit "Ref" suffix
- **Clear Semantics**: Each field should have one clear purpose

#### Documentation Requirements
- **Godoc Comments**: Comprehensive documentation for all exported types and fields
- **JSON Field Names**: Use JSON names in documentation (not Go names)
- **User-Facing**: Write for users, not just developers
- **Explain Interactions**: Document how fields interact with each other

#### Validation
- **Kubebuilder Tags**: Use validation markers (`+kubebuilder:validation:*`)
- **Enum Values**: Explicitly define allowed values
- **Field Constraints**: Define minimums, maximums, patterns
- **Meaningful Errors**: Validation messages should guide users

#### Union Types
- **Discriminated Unions**: Use a discriminator field to select variant
- **Optional Pointers**: All union members should be optional pointers
- **Validation**: Ensure exactly one union member is set

## Implementation

The command performs the following analysis workflow:

1. **Repository Discovery**
   - Find Go API types (typically in `api/`, `pkg/apis/` directories)
   - Identify CRD generation markers (`+kubebuilder` comments)

2. **Kubernetes Convention Validation**
   - **Naming validation**: Check resource names, field names, condition types
   - **Structure validation**: Verify required fields, metadata, spec/status separation
   - **Status validation**: Ensure conditions array, proper condition structure
   - **Field type validation**: Check integer types, avoid floats, validate enums
   - **Versioning validation**: Verify group names and version strings

3. **OpenShift Convention Validation**
   - **API classification**: Identify configuration vs workload APIs
   - **Field design**: Flag boolean fields, check enumerations
   - **Documentation**: Verify Godoc comments, user-facing descriptions
   - **Validation markers**: Check kubebuilder validation tags
   - **Union types**: Validate discriminated union patterns

4. **Report Generation**
   - List all findings with severity levels (Critical, Warning, Info)
   - Provide specific file and line references
   - Include remediation suggestions
   - Highlight whether a suggested change might lead to breaking API changes
   - Link to relevant convention documentation

## Output Format

The command generates a structured report with:
- **Summary**: Overview of findings by severity
- **Kubernetes Findings**: Issues related to upstream conventions
- **OpenShift Findings**: Issues related to OpenShift-specific patterns
- **Recommendations**: Actionable steps to improve API design

Each finding includes:
- Severity level (❌ Critical, ⚠️ Warning, 💡 Info)
- File location and line number
- Description of the issue
- Remediation suggestion
- Link to relevant documentation

## Examples

### Example 1: Review current repository
```
/crd-review
```
Analyzes CRDs in the current working directory.

### Example 2: Review specific repository
```
/crd-review /path/to/operator-project
```
Analyzes CRDs in the specified directory.

### Example 3: Review with detailed output
The command automatically provides detailed output including:
- All CRD files found
- Go API type definitions
- Compliance summary
- Specific violations with file references

## Common Findings

### Kubernetes Convention Issues

#### Boolean vs Enum Fields
**Issue**: Using boolean where enum is better
```go
// ❌ Bad
type MySpec struct {
    Enabled bool `json:"enabled"`
}

// ✅ Good
type MySpec struct {
    // State defines the operational state
    // Valid values are: "Enabled", "Disabled", "Auto"
    // +kubebuilder:validation:Enum=Enabled;Disabled;Auto
    State string `json:"state"`
}
```

#### Missing Status Conditions
**Issue**: Status without conditions array
```go
// ❌ Bad
type MyStatus struct {
    Ready bool `json:"ready"`
}

// ✅ Good
type MyStatus struct {
    // Conditions represent the latest available observations
    // +listType=map
    // +listMapKey=type
    Conditions []metav1.Condition `json:"conditions,omitempty"`
}
```

#### Improper Field Naming
**Issue**: Ambiguous or abbreviated names
```go
// ❌ Bad
type MySpec struct {
    Timeout int `json:"timeout"` // Ambiguous unit
    Cnt     int `json:"cnt"`     // Abbreviation
}

// ✅ Good
type MySpec struct {
    // TimeoutSeconds is the timeout in seconds
    // +kubebuilder:validation:Minimum=1
    TimeoutSeconds int32 `json:"timeoutSeconds"`

    // Count is the number of replicas
    // +kubebuilder:validation:Minimum=0
    Count int32 `json:"count"`
}
```

### OpenShift Convention Issues

#### Missing Documentation
**Issue**: Exported fields without Godoc
```go
// ❌ Bad
type MySpec struct {
    Field string `json:"field"`
}

// ✅ Good
type MySpec struct {
    // field specifies the configuration field for...
    // This value determines how the operator will...
    // Valid values include...
    Field string `json:"field"`
}
```

#### Missing Validation
**Issue**: Fields without kubebuilder validation
```go
// ❌ Bad
type MySpec struct {
    Mode string `json:"mode"`
}

// ✅ Good
type MySpec struct {
    // mode defines the operational mode
    // +kubebuilder:validation:Enum=Standard;Advanced;Debug
    // +kubebuilder:validation:Required
    Mode string `json:"mode"`
}
```

## Best Practices

1. **Start with Conventions**: Review conventions before writing APIs
2. **Use Code Generation**: Leverage controller-gen and kubebuilder markers
3. **Document Early**: Write Godoc comments as you define types
4. **Validate Everything**: Add validation markers for all fields
5. **Review Regularly**: Run this command during development and before PRs
6. **Follow Examples**: Study well-designed APIs in OpenShift core

## Arguments

- **repository-path** (optional): Path to repository containing CRDs. Defaults to current working directory.

## Exit Codes

- **0**: Analysis completed successfully
- **1**: Error during analysis (e.g., invalid path, no CRDs found)

## See Also

- [Kubernetes API Conventions](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md)
- [OpenShift API Conventions](https://github.com/openshift/enhancements/blob/master/dev-guide/api-conventions.md)
- [Kubebuilder Documentation](https://book.kubebuilder.io/)
- [Controller Runtime API](https://pkg.go.dev/sigs.k8s.io/controller-runtime)
