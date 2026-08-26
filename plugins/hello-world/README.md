# Hello World Plugin

A reference implementation plugin demonstrating Claude Code plugin structure and conventions.

## User-Invocable Skills

### `/hello-world:echo`

A simple echo skill that demonstrates the proper structure for explicit user invocation.

This plugin serves as a template for creating new plugins. See [skills/echo/SKILL.md](skills/echo/SKILL.md) for the complete user-invocable skill format defined in AGENTS.md.

## Installation

```bash
/plugin install hello-world@ai-helpers
```

## For Plugin Developers

This plugin is the canonical example of proper plugin structure:
- Correct frontmatter format
- Required sections (Name, Synopsis, Description, Implementation)
- Proper skill naming and invocation settings
- Complete documentation

Use this as a reference when creating new user-invocable skills and plugins.
