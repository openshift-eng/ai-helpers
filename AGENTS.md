# AGENTS.md

Claude Code plugins repository. Plugins live under `plugins/`.

## Structure

```text
plugins/{plugin-name}/
├── .claude-plugin/
│   └── plugin.json               # Required: name, description, version, author
├── skills/                        # User-facing or reusable workflows
│   └── {skill-name}/
│       └── SKILL.md
└── README.md
```

Canonical example: `plugins/hello-world/`

## Development Commands

| Command | When |
|---------|------|
| `make lint` | Before every commit — validates structure, format, and marketplace registration |
| Bump `version` in `plugin.json` | Once per affected plugin per PR when modifying skills, hooks, or plugin.json (not README.md or OWNERS). Skip if that plugin is already higher than the base branch tip. |
| `make update` | After version bumps — syncs marketplace.json and regenerates docs |

## Contributing Rules

- **No plugin commands.** Do not add a `commands/` directory. Expose user-facing workflows as skills with `user-invocable: true` and `disable-model-invocation: true`.
- **AI reasoning required.** User-invocable skills must require AI analysis/decisions, not just wrap scripts. If it could be a shell alias or Makefile target, it should not be a user-invocable skill.
- **Never reference real people** by name, even stylistically. Describe desired qualities explicitly instead.
- **Check for overlaps** before contributing: run `/utils:review-ai-helpers-overlap --idea "description"`.
- **Follow existing patterns.** Read `[plugins/hello-world/skills/echo/SKILL.md](plugins/hello-world/skills/echo/SKILL.md)` for user-invocable skill format; the linter enforces structure.
- **Use kebab-case** for all plugin names and skill directories.
- **Use `.work/{feature-name}/`** for temporary files (gitignored).
- **Register all plugins** in [.claude-plugin/marketplace.json](.claude-plugin/marketplace.json).
- **Set author** to `"github.com/openshift-eng"` in `plugin.json`.
- **Add new skills** to an existing plugin when they fit its scope, or to `plugins/utils/` if no clear parent. Create a new plugin only for a distinct group of related skills.
