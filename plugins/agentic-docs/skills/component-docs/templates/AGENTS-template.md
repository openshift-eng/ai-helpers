# [Component Name]

**Repository**: openshift/[repo-name]

[1-2 sentence description of what the component does and its role in OpenShift.]

> **Platform Patterns**: See openshift/enhancements repo (`dev-guide/`, `guidelines/`, `CONVENTIONS.md`) for generic platform conventions.

## Critical Warnings

[3-5 most important "never do X" rules discovered from codebase exploration.
These should be the patterns that, if violated, produce subtly broken code.
Format as a numbered list with bold warnings. These must be unique to this
component — not generic advice.]


## Architecture at a Glance

[One small table or 2-3 sentences capturing the key architectural choice.
E.g., framework split, core reconciliation pattern, or resource management approach.
Just enough to orient — details are in ARCHITECTURE.md.]

## Documentation

See also: [REVIEW.md](REVIEW.md) for code review rules, [.coderabbit.yaml](.coderabbit.yaml) for CodeRabbit config.

```text
ai-docs/
├── ARCHITECTURE.md    # Internals, integrations, behavioral contracts, design refs
├── DEVELOPMENT.md     # Build, common tasks, mistakes
├── TESTING.md         # Test suites and patterns
└── ENHANCEMENTS.md    # Enhancement/KEP/design doc catalog (when present)
```

**AI Agent Path**: ARCHITECTURE.md → DEVELOPMENT.md → TESTING.md

[If prior agent docs contained a retrieval order, documentation map, or useful
deep links, preserve a compact route here. A larger map may live in ai-docs,
but link directly to it from this section; do not leave only a bare directory.]

## Key Files

| What | Where |
|------|-------|
| [What] | [Where] |

[List the top 5-8 most important files an agent needs to find quickly, such as
the entrypoint, controller directories, type definitions, feature gates, and error types.]

## External References

- [Product Docs](https://docs.openshift.com/) | [Upstream Project](https://github.com/...)

---

`CLAUDE.md` is a symlink to this file.
