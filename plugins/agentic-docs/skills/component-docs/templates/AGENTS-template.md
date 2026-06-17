# Component Name - Agentic Documentation

**Component**: [Component Full Name]  
**Repository**: openshift/[repo-name]  

> **Generic Platform Patterns**: See Platform documentation (openshift/enhancements/ai-docs/) for operator patterns, testing practices, security guidelines, and cross-repo ADRs.

## What is [Component Name]?

[Brief 1-2 sentence description of what the component does]

**Key Principle**: [Core principle or design philosophy]

## Core Components

- **Component1**: Purpose | **Component2**: Purpose | **Component3**: Purpose

**Quick Start**: `oc describe clusteroperator/[name]` | `oc describe [primary-resource]`

## Documentation Structure

```text
ai-docs/
├── domain/                    # Component-specific CRDs
├── architecture/              # Component internals
├── decisions/                 # Component-specific ADRs
├── exec-plans/                # Feature planning
├── references/
│   └── ecosystem.md           # Links to Platform
├── [COMPONENT]_DEVELOPMENT.md # Component dev workflows
└── [COMPONENT]_TESTING.md     # Component test suites
```text

**Exec-Plans**: Use `active/` for new features. See [Platform Exec-Plans Guide](Platform documentation).

**Platform Patterns (Platform)**: [Operator](Platform documentation) | [Testing](Platform documentation) | [Security](Platform documentation)

## Knowledge Graph

```text
                         [AGENTS.md] ← Start here
                              │
              ┌───────────────┼───────────────┐
              │               │               │
         [domain/]      [architecture/]  [decisions/]
        CRD concepts    Component design  ADR history
              │               │               │
              └───────────────┼───────────────┘
                              │
                      [references/ecosystem]
                      Links to Platform
```text

**AI Agent Path**: domain/ → architecture/ → decisions/ → [COMPONENT]_DEVELOPMENT.md

## External References

- [Product Docs](https://docs.openshift.com/) | [Related Project](https://github.com/...)

---

**Platform Documentation**: openshift/enhancements/ai-docs/
