# ResourceName

**API Group**: `group.openshift.io/v1`  
**Kind**: `ResourceName`  
**Scope**: Cluster | Namespaced

## Purpose

[Brief description of what this resource does - component-specific behavior only]

**Key Principle**: [Core principle specific to this resource]

## Spec Structure

```go
type ResourceNameSpec struct {
    Field1 Type  // Description
    Field2 Type  // Description
    Field3 Type  // Description
}
```text

## Key Concepts

### Concept 1

[Component-specific behavior and semantics]

### Concept 2

[Component-specific patterns and usage]

## Lifecycle

1. **Creation**: [What happens when created]
2. **Update**: [How updates are handled]
3. **Deletion**: [Cleanup behavior]

## Example: Common Use Case

```yaml
apiVersion: group.openshift.io/v1
kind: ResourceName
metadata:
  name: example
spec:
  field1: value
  field2: value
```text

**Use case**: [When to use this pattern]

## Component-Specific Behavior

[Document ONLY component-specific behavior, not generic patterns]

**For generic patterns**, see:
- Controller patterns: [Platform](Platform documentation)
- Status conditions: [Platform](Platform documentation)

## Related Concepts

- [Other Resource](./other-resource.md) - Related component resource
