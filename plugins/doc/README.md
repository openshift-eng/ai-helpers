# Doc Plugin

Engineering documentation and note-taking utilities for Claude Code.

## Commands

### `/doc:note`

Create and manage engineering notes and documentation.

See [commands/note.md](commands/note.md) for full documentation.

### `/doc:controller-design`

Generate comprehensive design documentation for Kubernetes operators and controllers.

Analyzes controller implementations, watches, reconciliation logic, resource relationships, CRDs, RBAC, and generates Mermaid diagrams. Outputs to `DESIGN.md` (or `docs/DESIGN.md` if `docs/` exists).

See [commands/controller-design.md](commands/controller-design.md) for full documentation.

## Installation

```bash
/plugin install doc@ai-helpers
```

