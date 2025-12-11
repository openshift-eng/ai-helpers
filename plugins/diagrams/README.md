# Diagrams Plugin

Expert diagram creation skills for Mermaid and other formats.

## Overview

This plugin provides expert guidance for creating diagrams. When installed, Claude automatically uses the appropriate skill when creating diagrams in supported formats.

## Skills

### Mermaid Expert

Located at `skills/mermaid/SKILL.md`, this skill provides:

- **Diagram type selection** - Choosing the right diagram type for your content
- **Syntax reference** - Complete syntax for flowchart, sequence, state, class, block-beta, and gantt diagrams
- **Critical rules** - Avoiding common syntax errors with special characters, parentheses, and bidirectional arrows
- **ASCII conversion** - Step-by-step guide for converting ASCII art to Mermaid

**Automatic usage**: When you ask Claude to create a Mermaid diagram, it will automatically use this skill to ensure correct syntax and best practices.

## Supported Diagram Types

| Type              | Use Case                                                 |
| ----------------- | -------------------------------------------------------- |
| `flowchart`       | Process flows, architectures, decision trees             |
| `sequenceDiagram` | Protocol handshakes, API interactions, message exchanges |
| `stateDiagram-v2` | State machines, lifecycles, workflows                    |
| `classDiagram`    | Class/struct relationships, OOP design                   |
| `block-beta`      | Structured data layouts, packet/frame diagrams           |
| `gantt`           | Timelines, schedules, project planning                   |

## Installation

```bash
/plugin install diagrams@ai-helpers
```

## Usage

Once installed, simply ask Claude to create a diagram:

```
"Create a flowchart showing the CI/CD pipeline"
"Convert this ASCII diagram to Mermaid"
"Create a sequence diagram for the OAuth flow"
```

Claude will automatically apply the Mermaid expert skill to ensure correct syntax.

## Enabling Automatic Usage

To ensure Claude **always** uses the Mermaid expert skill when creating diagrams, add the following to your project's `CLAUDE.md` file:

```markdown
## Markdown Diagrams

**ALWAYS use Mermaid syntax** for diagrams in Markdown files instead of ASCII art.

**ALWAYS use the Mermaid skill** from the diagrams plugin when creating Mermaid diagrams.
The skill is located at: `plugins/diagrams/skills/mermaid/SKILL.md`

The skill contains:

- Syntax rules for each diagram type
- Diagram type selection guidelines
- Common error prevention
```

This instructs Claude to reference the skill whenever it needs to create a Mermaid diagram, ensuring correct syntax and best practices.

## See Also

- [Mermaid documentation](https://mermaid.js.org/)
- [Mermaid live editor](https://mermaid.live/)
