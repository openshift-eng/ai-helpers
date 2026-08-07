# AGENTS.md

Claude Code plugins repository. Plugins live under `plugins/`.

## Structure

```text
plugins/{plugin-name}/
├── .claude-plugin/
│   └── plugin.json               # Required: name, description, version, author
├── plugin.json                   # Required: Agent Plugins v1 manifest
├── commands/
│   └── {command-name}.md         # Optional: Claude-specific commands
├── skills/                        # Optional: portable skills
│   └── {skill-name}/
│       └── SKILL.md
├── mcp.json                      # Optional: Agent Plugins MCP configuration
└── README.md
```

Canonical example: `plugins/hello-world/`

Every plugin must provide at least one command or skill. Portable Agent
Plugins expose the directly packaged skills and MCP servers; commands remain
Claude-specific.

## Development Commands

| Command | When |
|---------|------|
| `make lint` | Before every commit — validates structure, format, and marketplace registration |
| `make sync-agent-plugins` | Creates missing portable manifests and translates tracked Claude MCP configs |
| Bump `version` in `.claude-plugin/plugin.json` | When modifying plugin commands, skills, hooks, or MCP configuration (not README-only or generated root-manifest changes) |
| `make update` | After version bumps — syncs marketplace.json and regenerates docs |

## Contributing Rules

- **AI reasoning required.** Commands must require AI analysis/decisions, not just wrap scripts. If it could be a shell alias or Makefile target, it should not be a plugin command.
- **Never reference real people** by name, even stylistically. Describe desired qualities explicitly instead.
- **Check for overlaps** before contributing: run `/utils:review-ai-helpers-overlap --idea "description"`.
- **Follow existing patterns.** Read `[plugins/hello-world/commands/echo.md](plugins/hello-world/commands/echo.md)` for command format; the linter enforces structure.
- **Use kebab-case** for all plugin names, command files, and skill directories.
- **Use `.work/{feature-name}/`** for temporary files (gitignored).
- **Register all plugins** in [.claude-plugin/marketplace.json](.claude-plugin/marketplace.json).
- **Set author** to `"github.com/openshift-eng"` in `plugin.json`.
- **Maintain both manifests**: `.claude-plugin/plugin.json` is the Claude Code manifest and the root `plugin.json` is the Agent Plugins v1 manifest. Keep their shared metadata synchronized with `make sync-agent-plugins`.
- **Limit portable content to the current Agent Plugins v1 surface**: skills under `skills/` and MCP servers under `mcp.json`. Commands, agents, hooks, and Claude plugin dependencies remain Claude-specific.
- **Treat meta-plugins as Claude-specific bundles**: a portable manifest may describe their directly packaged skills, but Agent Plugins v1 does not encode their dependency bundle.
- **Add new commands** to an existing plugin when they fit its scope, or to `plugins/utils/` if no clear parent. Create a new plugin only for a distinct group of related commands.
