# Repository Name - Agent Navigation Index

**Version**: 1.0 | **Docs**: ./ai-docs/ | **Files**: XX | **Lines**: XXXX

---

## CRITICAL: Retrieval Strategy

**IMPORTANT**: Prefer retrieval-led reasoning over pre-training-led reasoning.

When working on OpenShift:
- ✅ **DO**: Read relevant docs from `./ai-docs/` first
- ✅ **DO**: Verify patterns match current APIs
- ❌ **DON'T**: Rely solely on training data
- ❌ **DON'T**: Guess at API structures

---

## Quick Start

**New to OpenShift?** → Read `./ai-docs/KNOWLEDGE_GRAPH.md`  
**Building operator?** → Path: DESIGN_PHILOSOPHY.md → controller-runtime.md → status-conditions.md  
**Adding feature?** → Read `./ai-docs/workflows/implementing-features.md`

---

## Compressed Documentation Index

```
[Repo Agentic Docs]|root:./ai-docs|XX files, XXXX lines
|
|CRITICAL_READS:{KNOWLEDGE_GRAPH.md,DESIGN_PHILOSOPHY.md}
|
|platform/operator-patterns:{controller-runtime.md,status-conditions.md,...}
|practices/testing:{pyramid.md,e2e-framework.md,...}
|domain/kubernetes:{pod.md,node.md,...}
|domain/openshift:{clusteroperator.md,machine.md,...}
|decisions:{adr-0001-*.md,...}
```

---

## Task → Docs Quick Map

| Task | Read These (in order) |
|------|----------------------|
| **Build operator** | DESIGN_PHILOSOPHY.md → controller-runtime.md → status-conditions.md |
| **Add feature** | enhancement-process.md → api-evolution.md → pyramid.md |
| **Debug issue** | observability.md → must-gather.md |

---

## Architecture Overview

Brief architecture diagram or summary relevant to this repository.

---

## Documentation Principles

- Progressive disclosure (read 4-5 docs per task, not all)
- Reference style (terse, not tutorial)
- AI-optimized structure
