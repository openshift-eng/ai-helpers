# Agentic Docs

AI-optimized OpenShift documentation with progressive disclosure, reference style (tables/checklists), and pointer-based navigation.

## Two-Tier Architecture

**Tier 1: Platform Hub** (`openshift/enhancements/ai-docs/`)  
Generic patterns, testing, security, K8s/OpenShift fundamentals, cross-repo ADRs. ~34 files, 4.4k lines.

**Tier 2: Component Repos** (`{component}/agentic/`)  
Component CRDs, architecture, local ADRs, exec-plans. Links to Tier 1. ~15 files, 2.5k lines (58% leaner).

## Skills

### `/platform-docs`
Creates Tier 1 platform documentation in `openshift/enhancements/ai-docs/`.

```bash
cd /path/to/openshift/enhancements
/platform-docs
```

Creates AGENTS.md (navigation) + ai-docs/ with: platform patterns (controller-runtime, webhooks, finalizers, RBAC, must-gather), domain concepts (K8s/OpenShift APIs), practices (testing, security, reliability), cross-repo ADRs, workflows (exec-plans, enhancement process), and references (repo-index, glossary, API pointers).

### `/update-docs`
Incrementally update Tier 1 docs with automatic gap detection.

```bash
cd /path/to/openshift/enhancements
/update-docs
```

Scans ai-docs/, reports missing files, lets you fill gaps or add custom content. Auto-updates indexes/navigation and validates conventions. Use for incremental changes when ai-docs/ exists (otherwise use `/platform-docs`).

### `/component-docs`
Creates Tier 2 lean docs in component repositories.

```bash
cd /path/to/component-repository
/component-docs
```

Creates AGENTS.md + agentic/ with: component CRDs only, architecture, component ADRs, exec-plans, ecosystem links to Tier 1, development/testing guides. Excludes generic patterns (lives in Tier 1). Example: [machine-config-operator/agentic](https://github.com/openshift/machine-config-operator/tree/master/agentic).

## Development

Skills live under `skills/{platform,update-platform-docs,component}/` with SKILL.md, scripts, and templates.

**License:** Apache 2.0
