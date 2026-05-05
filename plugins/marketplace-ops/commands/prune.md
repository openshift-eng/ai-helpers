---
description: Analyze and prune stale plugins, commands, and skills from the marketplace
argument-hint: "[--dry-run]"
---

## Name
marketplace-ops:prune

## Synopsis
```
/marketplace-ops:prune [--dry-run]
```

## Description
Analyzes the plugin marketplace for stale or low-value plugins, commands, and skills using git history, structural signals, and LLM judgment. By default, creates a branch removing identified candidates, opens a PR with a removal manifest, and provides a `/save` workflow for stakeholders to protect items.

With `--dry-run`, prints the analysis report without creating a branch or PR.

## Arguments
- `--dry-run`: Report pruning candidates without taking any action. No branch, no removals, no PR.

## Implementation

### Step 1: Load Protection List

Read `.pruneprotect` from the repository root. If the file does not exist, treat the protection list as empty.

Parse rules:
- Lines starting with `#` are comments — skip them.
- Empty/whitespace-only lines — skip.
- All other lines are path prefixes (e.g., `plugins/hello-world/` or `plugins/ci/commands/foo.md`).

A plugin, command, or skill is protected if its path starts with any entry in the protection list.

### Step 2: Inventory All Plugins

For each directory under `plugins/`:
1. Read `.claude-plugin/plugin.json` — extract `name`, `version`, `description`.
2. List commands: `find plugins/{name}/commands -name "*.md" -maxdepth 1 2>/dev/null`.
3. List skills: `find plugins/{name}/skills -name "SKILL.md" 2>/dev/null`.
4. Check for hooks: test if `plugins/{name}/hooks/` exists.
5. Check for README: test if `plugins/{name}/README.md` exists and get its size.

Build a structured inventory of every plugin with its commands, skills, hooks, and metadata.

### Step 3: Gather Git Metadata

For each plugin directory, run:
```bash
# Last commit date (ISO format)
git log -1 --format="%aI" -- "plugins/{name}/"

# Number of unique contributors
git shortlog -sn --all -- "plugins/{name}/" | wc -l

# Contributors list (for reporting)
git shortlog -sn --all -- "plugins/{name}/"
```

For command-level and skill-level analysis, also gather per-file metadata:
```bash
git log -1 --format="%aI" -- "path/to/file.md"
git shortlog -sn --all -- "path/to/file.md" | wc -l
```

Calculate the age of the last commit in days from today's date.

**Batch-update detection:** If more than 5 plugins share the exact same last-commit date, that commit is likely a batch infrastructure update. In that case, look at the second-most-recent commit for those plugins to find the last *meaningful* update:
```bash
git log -2 --format="%aI" -- "plugins/{name}/"
```

### Step 4: Plugin-Level Scoring

Apply these heuristics to each non-protected plugin. A plugin is a pruning candidate if its total score is >= 3:

| Signal | Weight | How to detect |
|--------|--------|---------------|
| Last meaningful commit > 6 months ago | 2 | Git log date vs. today |
| Version stuck at 0.0.x | 1 | Parse `version` field from plugin.json |
| 1-2 commands and no skills | 1 | Count from inventory |
| No README or README < 100 bytes | 1 | File existence + size check |
| Single contributor + inactive > 3 months | 1 | Shortlog count + date |

**Important:** Hook-only plugins (no commands) are NOT penalized for having no commands. Hook-only plugins serve infrastructure purposes and should be evaluated on the same signals as any other plugin.

### Step 5: Command/Skill-Level Analysis (Higher Bar)

For plugins that are NOT being fully pruned, evaluate individual commands and skills. This requires a higher bar — use all of the following signals together:

1. **Read the command/skill `.md` content.**
2. **Check contributor count and activity:** single contributor + no commits in 6+ months.
3. **Apply LLM judgment on utility:**
   - Does the command require AI reasoning/analysis/decisions? Or could it be a shell alias or Makefile target? Commands that just wrap scripts violate the repo's "AI reasoning required" rule and are candidates.
   - Does the command duplicate or substantially overlap with another command in the marketplace?
   - Does the command reference tools, APIs, or services that no longer exist or are deprecated?
   - Would an engineering organization find this command useful?

Only flag a command/skill if both the quantitative signals (low contributors + inactive) AND the qualitative judgment (low utility) agree. When in doubt, keep the item.

### Step 6: Cross-Reference Scan

Before finalizing the removal list, check whether any item being removed is referenced by items NOT being removed:

```bash
# For each plugin being removed
grep -rl "/{plugin-name}:" plugins/ --include="*.md" | grep -v "plugins/{plugin-name}/"
grep -rl "plugins/{plugin-name}" plugins/ --include="*.md" | grep -v "plugins/{plugin-name}/"

# For each command being removed
grep -rl "{command-name}" plugins/ --include="*.md"
```

Record any cross-references as warnings to include in the report.

### Step 7: Generate Report

Build a removal manifest table:

```markdown
| Type | Path | Reason |
|------|------|--------|
| plugin | `plugins/foo/` | No commits in 7 months, v0.0.1, 1 contributor |
| command | `plugins/bar/commands/baz.md` | Single contributor, inactive 8 months, wraps shell script |
```

Also list any cross-reference warnings:
```markdown
## Cross-Reference Warnings
- `plugins/xyz/`: referenced by `plugins/abc/commands/def.md`
```

And list protected items that were skipped:
```markdown
## Protected (skipped)
- `plugins/hello-world/` — listed in .pruneprotect
```

### Step 8: Dry-Run Exit Point

**If `--dry-run` was specified:** Print the full report to the user and stop. Do not create a branch, remove files, or open a PR.

### Step 9: Create Branch and Remove Items

```bash
git checkout -b prune/$(date +%Y%m%d) main
```

For each item in the removal manifest:
```bash
# Full plugin removal
git rm -rf plugins/{plugin-name}/

# Individual command removal
git rm plugins/{plugin-name}/commands/{command}.md

# Individual skill removal
git rm -rf plugins/{plugin-name}/skills/{skill-name}/
```

### Step 10: Sync and Commit

Run `make update` to regenerate marketplace.json and documentation:
```bash
make update
git add -A
```

Commit:
```bash
git commit -m "$(cat <<'EOF'
chore: prune stale plugins, commands, and skills

See PR description for full removal manifest.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Step 11: Push and Open PR

Determine the correct remote for the user's fork:
```bash
git remote -v
```

Push to the user's fork:
```bash
git push -u {fork-remote} HEAD
```

Open the PR with `gh pr create`. The body must include the removal manifest, cross-reference warnings, save instructions, and protection note:

```bash
gh pr create --title "chore: prune stale marketplace content" --body "$(cat <<'EOF'
## Summary
Automated pruning of stale/inactive plugins, commands, and skills.

## Removal Manifest

{paste the table from Step 7}

## Cross-Reference Warnings
{paste warnings from Step 6, or "None" if clean}

## How to Save Items
Comment `/save <path>` on this PR to protect any item from removal. Examples:
```
/save plugins/foo/
/save plugins/bar/commands/baz.md
```

Then run `/marketplace-ops:prune-update` to process saves. Saved items are:
1. Restored in the PR branch
2. Added to `.pruneprotect` permanently (with a note of who requested it)

## Protected Items
Items listed in `.pruneprotect` were excluded from analysis.

{paste protected list from Step 7}
EOF
)"
```

### Step 12: Report Results

Print the PR URL and a summary: how many plugins, commands, and skills were proposed for removal.

## Return Value
- **With `--dry-run`:** A markdown report of pruning candidates with reasons, cross-references, and protected items.
- **Without `--dry-run`:** The URL of the created PR, plus a summary of removals.

## Examples

1. **Dry run to see candidates:**
   ```
   /marketplace-ops:prune --dry-run
   ```

2. **Full pruning with PR creation:**
   ```
   /marketplace-ops:prune
   ```
