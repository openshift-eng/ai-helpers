# Agentic Docs

AI-optimized OpenShift documentation with progressive disclosure, reference style (tables/checklists), and pointer-based navigation.

## Two-Tier Architecture

**Platform Docs** (`openshift/enhancements/ai-docs/`) - **Already exists**  
Generic patterns, testing, security, K8s/OpenShift fundamentals, cross-repo ADRs. ~34 files, 4.4k lines.

**Component Docs** (`{component}/ai-docs/`)  
Component CRDs, architecture, local ADRs, exec-plans. Links to platform docs. ~15 files, 2.5k lines (58% leaner).

## Skills

### `/update-platform-docs`
Incrementally update platform docs with automatic gap detection.

```bash
cd /path/to/openshift/enhancements
/update-platform-docs
```

Scans ai-docs/, reports missing files, lets you fill gaps or add custom content. Auto-updates indexes/navigation and validates conventions. Use for incremental changes to existing platform documentation.

### `/component-docs`
Creates lean component docs in component repositories.

```bash
cd /path/to/component-repository
/component-docs
```

Creates AGENTS.md + ai-docs/ with: component CRDs only, architecture, component ADRs, exec-plans, ecosystem links to platform docs, development/testing guides. Excludes generic patterns (lives in platform docs). Example: [machine-config-operator/ai-docs](https://github.com/openshift/machine-config-operator/tree/master/ai-docs).

## Development

Skills live under `skills/{update-platform-docs,component-docs}/` with SKILL.md, scripts, and templates.

**License:** Apache 2.0
