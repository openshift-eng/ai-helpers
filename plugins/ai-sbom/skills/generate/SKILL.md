---
name: AI SBOM Generate
description: "Generate an AI SBOM declaration for a PR description. Use this skill when the user asks to generate an AI SBOM, create an ai-assisted block, fill out their AI assistance section, or prepare a PR description with AI provenance. Also use when the user says 'what skills did I use' or 'summarize my AI usage'."
---

# Generate AI SBOM Declaration

Generate a formatted `ai-assisted` code fence block for a PR description that declares which AI tools, models, and skills contributed to the work.

## Modes

### Current Session

When the user asks to generate an AI SBOM during an active session, you already know which skills were invoked. Collect the list from your own tool usage history in this conversation. Get the tool version by running `claude --version`.

### Past Session

When the user wants an SBOM for a previous session or across multiple sessions:

1. Identify the project directory: `~/.claude/projects/<project-path-with-dashes>/`
2. Run the extraction script:
   ```bash
   python3 <ai-sbom-plugin-path>/scripts/extract_skills.py <path-to-session-or-project-dir>
   ```
3. The script outputs a JSON object with `skills`, `models`, and `tool_version`. The tool version is extracted from the session transcript when available; if not found, it falls back to the currently installed version via `claude --version`.

## Resolving Provenance

For each skill identified, resolve its version and source:

1. Read `~/.claude/plugins/installed_plugins.json` to find the plugin entry
   - The key format is `plugin-name@marketplace-name` (e.g., `superpowers@claude-plugins-official`)
   - Extract `version` and `gitCommitSha` from the entry

2. Read `~/.claude/plugins/known_marketplaces.json` to find the source repo
   - Match the marketplace name to get the `source.repo` (e.g., `anthropics/claude-plugins-official`)

3. For repo-local skills (`.claude/skills/`), use the `repo:` prefix with no version
4. For user-level skills (`~/.claude/skills/`), use the `user:` prefix with no version

## Output Format

Read the format specification at `plugins/ai-sbom/docs/AI_SBOM.md` for the exact block structure, field definitions, skill entry format, and examples. Generate the `ai-assisted` code fence block following that spec.

## Writing to a PR

When the user asks to write the SBOM to a PR:

1. Find the PR for the current branch: `gh pr view --json number,body`
2. Generate the SBOM block with the `## AI Assistance` header
3. Check if the PR body already contains a `## AI Assistance` section
   - If yes, replace everything from `## AI Assistance` through the closing `` ``` `` of the `ai-assisted` fence
   - If no, append the section to the end of the PR body
4. Update the PR: `gh pr edit <number> --body "<updated body>"`
5. Confirm to the user what was written

## Steps

1. Determine mode (current session or past session)
2. Get the tool version by running `claude --version`
3. Collect the list of skills used (from self-knowledge or extraction script)
4. Read `~/.claude/plugins/installed_plugins.json`
5. Read `~/.claude/plugins/known_marketplaces.json`
6. For each skill, resolve: marketplace, version, source repo, commit SHA
7. Check `.claude/skills/` and `~/.claude/skills/` for repo-local and user-level skills
8. Format the `## AI Assistance` section with the `ai-assisted` code fence block
9. If the user wants it written to a PR, update the PR body using `gh pr edit`
10. Otherwise, present it to the user for manual inclusion
