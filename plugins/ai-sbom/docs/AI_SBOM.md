# AI SBOM Format

## Code Fence Block

PR descriptions include a fenced code block tagged `ai-assisted`.

### AI-Assisted PRs

````markdown
## AI Assistance

```ai-assisted
Tool: <tool-name> <tool-version>
Model: <model-id>

Skills used:
- <skill>@<version> (<source-repo>@<commit-sha>) — <description>
```
````

### Non-AI PRs

````markdown
## AI Assistance

```ai-assisted
none
```
````

## Fields

| Field | Required | Description |
|---|---|---|
| Tool | Yes | AI tool name and version (e.g., `Claude Code 2.1.126`, `Gemini CLI 1.0.0`, `OpenCode 0.5.0`) |
| Model | Yes | Model identifier (e.g., `claude-opus-4-6`) |
| Skills used | Yes | List of skills with provenance |

## Skill Entry Format

```text
- <skill-identifier>@<version> (<source-repo>@<commit-sha>) — <brief description>
```

### Skill Sources

| Source | Format | Example |
|---|---|---|
| Plugin skills | `marketplace:skill@version (org/repo@sha)` | `superpowers:test-driven-development@5.0.7 (anthropics/claude-plugins-official@a01a135f)` |
| Repo-local skills | `repo:skill` | `repo:git-commit-format` |
| User-level skills | `user:skill` | `user:restructure-commits` |

### Provenance Lookup

- **Plugin versions and commit SHAs**: `~/.claude/plugins/installed_plugins.json`
- **Source repositories**: `~/.claude/plugins/known_marketplaces.json`
- **Repo-local skills**: `.claude/skills/` in the project repo
- **User-level skills**: `~/.claude/skills/`

## Examples

````markdown
## AI Assistance

```ai-assisted
Tool: Claude Code 2.1.126
Model: claude-opus-4-6

Skills used:
- superpowers:brainstorming@5.0.7 (anthropics/claude-plugins-official@a01a135f) — Collaborative design and spec creation
- example-skills:skill-creator@b0cbd3df1533 (anthropics/skills@b0cbd3df1533) — Guided skill creation process
```
````

````markdown
## AI Assistance

```ai-assisted
Tool: Claude Code 2.1.126
Model: claude-opus-4-6

Skills used:
- personal-claude-skills:behavior-driven-testing@0.1.0 (example-user/personal-claude-skills@abc12345) — Gherkin-style behavior-driven tests
- ai-helpers:utils:address-reviews@0.0.1 (openshift-eng/ai-helpers@c8e587eb) — Systematic PR review comment resolution
```
````

````markdown
## AI Assistance

```ai-assisted
Tool: Claude Code 2.1.126
Model: claude-opus-4-6

Skills used:
- superpowers:writing-plans@5.0.7 (anthropics/claude-plugins-official@a01a135f) — Implementation planning
- superpowers:executing-plans@5.0.7 (anthropics/claude-plugins-official@a01a135f) — Plan execution
- personal-claude-skills:grill-with-docs@0.1.0 (example-user/personal-claude-skills@cd96dea7) — Documentation-based knowledge drilling
```
````

````markdown
## AI Assistance

```ai-assisted
none
```
````
