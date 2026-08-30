# AGENTS.md

Claude Code plugins repository. Plugins live under `plugins/`.

## Structure

```text
plugins/{plugin-name}/
├── .claude-plugin/
│   └── plugin.json               # Required: name, description, version, author
├── commands/
│   └── {command-name}.md         # Required: at least one command
├── skills/                        # Optional
│   └── {skill-name}/
│       └── SKILL.md
└── README.md
```

Canonical example: `plugins/hello-world/`

## Development Commands

| Command | When |
|---------|------|
| `make lint` | Before every commit — validates structure, format, and marketplace registration |
| Bump `version` in `plugin.json` | Once per affected plugin per PR when modifying commands, skills, hooks, or plugin.json (not README.md or OWNERS). Skip if that plugin is already higher than the base branch tip. |
| `make update` | After version bumps — syncs marketplace.json and regenerates MkDocs content |
| `make site-build` | Before documentation changes — runs a strict local site build |
| `make site-serve` | Preview the generated site at `http://127.0.0.1:8000/ai-helpers/` |

## Contributing Rules

- **AI reasoning required.** Commands must require AI analysis/decisions, not just wrap scripts. If it could be a shell alias or Makefile target, it should not be a plugin command.
- **Never reference real people** by name, even stylistically. Describe desired qualities explicitly instead.
- **Check for overlaps** before contributing: run `/utils:review-ai-helpers-overlap --idea "description"`.
- **Follow existing patterns.** Read `[plugins/hello-world/commands/echo.md](plugins/hello-world/commands/echo.md)` for command format; the linter enforces structure.
- **Use kebab-case** for all plugin names, command files, and skill directories.
- **Use `.work/{feature-name}/`** for temporary files (gitignored).
- **Register all plugins** in [.claude-plugin/marketplace.json](.claude-plugin/marketplace.json).
- **Set author** to `"github.com/openshift-eng"` in `plugin.json`.
- **Add new commands** to an existing plugin when they fit its scope, or to `plugins/utils/` if no clear parent. Create a new plugin only for a distinct group of related commands.
