# AI SBOM Plugin

A plugin for generating AI Software Bill of Materials (SBOM) declarations for pull requests. Provides transparency into which AI tools, models, and skills contributed to code changes.

## Skills

### generate

Generate an `ai-assisted` code fence block for a PR description. Works in two modes:

- **Current session** — Generates the SBOM from skills used in the current conversation
- **Past session** — Parses Claude Code session transcripts to extract skill usage

The skill cross-references installed plugin metadata to include full provenance: skill versions, source repositories, and commit SHAs.

## Scripts

### extract_skills.py

Parses Claude Code JSONL session transcripts to extract skill invocations.

```bash
# Single session
python3 plugins/ai-sbom/scripts/extract_skills.py ~/.claude/projects/<project>/<session>.jsonl

# All sessions for a project
python3 plugins/ai-sbom/scripts/extract_skills.py ~/.claude/projects/<project>/
```

## Limitations

The format specification is tool-agnostic — any AI coding tool can produce an `ai-assisted` block. However, the generator skill and extraction script only support Claude Code session transcripts (JSONL format) today. Other tools (Gemini CLI, OpenCode, Cursor, etc.) would need their own extraction logic or manual entry.

## Format Specification

See [docs/AI_SBOM.md](docs/AI_SBOM.md) for the full format specification that repos can adopt.
