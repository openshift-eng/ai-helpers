# Component Name - Agentic Documentation

**Component**: [Component Full Name]  
**Repository**: openshift/[repo-name]  
**Documentation Tier**: 2 (Component-specific)

> **Generic Platform Patterns**: See [Tier 1 Ecosystem Hub](https://github.com/openshift/enhancements/tree/master/ai-docs) for operator patterns, testing practices, security guidelines, and cross-repo ADRs.

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
│   └── ecosystem.md           # Links to Tier 1
├── [COMPONENT]_DEVELOPMENT.md # Component dev workflows
└── [COMPONENT]_TESTING.md     # Component test suites
```

**Exec-Plans**: Use `active/` for new features. See [Tier 1 Exec-Plans Guide](https://github.com/openshift/enhancements/tree/master/ai-docs/workflows/exec-plans).

**Platform Patterns (Tier 1)**: [Operator](https://github.com/openshift/enhancements/tree/master/ai-docs/platform/operator-patterns) | [Testing](https://github.com/openshift/enhancements/tree/master/ai-docs/practices/testing) | [Security](https://github.com/openshift/enhancements/tree/master/ai-docs/practices/security)

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
                      Links to Tier 1
```

**AI Agent Path**: domain/ → architecture/ → decisions/ → [COMPONENT]_DEVELOPMENT.md

## External References

- [Product Docs](https://docs.openshift.com/) | [Related Project](https://github.com/...)

---

**Tier 1 Hub**: https://github.com/openshift/enhancements/tree/master/ai-docs
