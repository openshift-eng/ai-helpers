# Hello World Plugin

A reference implementation plugin demonstrating Claude Code plugin structure and conventions.

## Commands

### `/hello-world:echo`

A simple echo command that demonstrates the proper structure for command definitions.

This plugin serves as a template for creating new plugins. See [commands/echo.md](commands/echo.md) for the complete command format that follows the conventions defined in AGENTS.md.

## Installation

```bash
/plugin install hello-world@ai-helpers
```

## For Plugin Developers

This plugin is the canonical example of proper plugin structure:
- Correct frontmatter format
- Required sections (Name, Synopsis, Description, Implementation)
- Proper command naming conventions
- Complete documentation

Use this as a reference when creating new commands and plugins.

