---
description: Create lean component documentation for OpenShift component repositories
argument-hint: "[repository-path]"
---

## Name
agentic-docs:component

## Synopsis
```
/agentic-docs:component [repository-path]
```

## Description
The `agentic-docs:component` command creates lean component documentation for OpenShift component repositories following the two-tier architecture pattern where generic patterns live in the platform hub and only component-specific knowledge is documented locally.

This command implements the philosophy: "Component docs contain ONLY component-specific knowledge." Generic platform patterns (operator patterns, testing practices, security guidelines) live in the platform hub (openshift/enhancements/ai-docs/) and are referenced, not duplicated.

The command generates:
- `AGENTS.md` - Master entry point (80-100 lines)
- `ai-docs/domain/` - Component-specific CRDs only
- `ai-docs/architecture/components.md` - Component internals
- `ai-docs/decisions/` - Component-specific ADRs
- `ai-docs/exec-plans/` - Active feature implementation plans
- `ai-docs/references/ecosystem.md` - Links to platform docs
- `[COMPONENT]_DEVELOPMENT.md` - Component-specific development guidance
- `[COMPONENT]_TESTING.md` - Component-specific testing guidance

## Implementation
When this command is invoked, Claude will execute the `component-docs` skill, which:
1. Analyzes the repository structure and existing code
2. Identifies component-specific CRDs, architecture, and patterns
3. Generates lean documentation focused only on this component
4. Creates references to platform documentation for generic patterns
5. Follows the decision rule: "Would another repo need to duplicate this?"
   - YES → Reference platform docs
   - NO → Document in component

The skill creates a complete but lean documentation structure that avoids duplication with platform-level documentation.

## Return Value
- Complete component documentation structure in the repository
- AGENTS.md entry point
- ai-docs/ directory with component-specific content
- References to platform hub for generic patterns

## Examples

1. **Create component docs for current directory**:
   ```
   /agentic-docs:component
   ```
   Analyzes the current repository and generates component documentation.

2. **Create component docs for specific repository**:
   ```
   /agentic-docs:component /path/to/openshift/component-repo
   ```
   Analyzes the specified component repository and generates documentation.

## Arguments
- `repository-path` (optional): Path to the component repository. Defaults to current directory if not specified.
