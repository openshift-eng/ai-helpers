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
Analyzes the plugin marketplace for stale content using a two-tier system:

1. **Plugin-level (mechanical):** A scoring script flags entire plugins for removal based on git history and structural signals. If a plugin meets the scoring threshold, it is removed — no LLM override. The script is the decision-maker.
2. **Item-level (LLM-assisted):** For plugins that survive the plugin-level cut, a second script flags individual commands and skills. The LLM then reviews flagged items and applies qualitative judgment (AI reasoning required, duplicates, dead references) to decide which to remove.

By default, creates a branch removing identified items and opens a PR with a removal manifest and `/save` workflow. With `--dry-run`, prints the analysis report without taking action.

## Arguments
- `--dry-run`: Report pruning candidates without taking any action. No branch, no removals, no PR.

## Implementation

### Step 1: Run the Plugin Scoring Script

Run the scoring script to get a structured JSON report of all plugins scored by staleness:

```bash
python3 plugins/marketplace-ops/scripts/score-plugins.py .
```

The script handles:
- Reading `.pruneprotect` and skipping protected plugins
- Inventorying all plugins (commands, skills, hooks, README, version)
- Gathering git metadata (last commit date, commit count, contributor count)
- Detecting batch-update dates (when 5+ plugins share the same last-commit date) and falling through to the second-most-recent commit
- Scoring each plugin against these heuristics (candidate threshold: score >= 3):

| Signal | Weight |
|--------|--------|
| Last meaningful commit > 90 days ago | 1 |
| Last meaningful commit > 120 days ago | 2 |
| Last meaningful commit > 150 days ago | 3 |
| Last meaningful commit > 180 days ago | 4 |
| Number of commits <= 3 | 2 |
| Number of commits > 3 and <= 5 | 1 |
| Single contributor + inactive > 2 months | 1 |
| Has OWNERS file | -2 |
| Small plugin footprint (few things inside) | 1 |
| Minimal README or docs | 1 |

Maturity signals (commit count, OWNERS, footprint, README) are skipped for plugins younger than 90 days.

The JSON output contains `candidates` (score >= threshold), `protected` (skipped), and `safe` (scored but below threshold) arrays.

### Step 2: Remove All Plugin Candidates

**Plugin-level pruning is mechanical.** Every plugin in the `candidates` array is removed — no LLM judgment, no second-guessing the score. If the scoring threshold is met, the plugin goes. The `/save` workflow on the PR is the rescue path for false positives.

Add all candidate plugin paths to the removal list.

### Step 3: Command/Skill-Level Analysis (Higher Bar — LLM Judgment Required)

For plugins that survived Step 2 (not in the candidates list and not protected), run the item-level scoring script:

```bash
python3 plugins/marketplace-ops/scripts/score-items.py .
```

The script automatically skips protected plugins. To analyze only specific plugins:
```bash
python3 plugins/marketplace-ops/scripts/score-items.py --plugins ci,git,jira .
```

The script scores each command (individual `.md` file) and skill (full skill directory) using:
- Graduated inactivity (>90d: +1, >120d: +2, >150d: +3, >180d: +4)
- Low commit count (<=2 commits: +1)
- Single contributor (+1)
- Very small size (<500 bytes: +1)

Items with score >= 3 appear in the `flagged` array. For each flagged item, read its content and apply LLM judgment:
- Does the command require AI reasoning/analysis/decisions? Or could it be a shell alias or Makefile target? Commands that just wrap scripts violate the repo's "AI reasoning required" rule and are candidates.
- Does the command duplicate or substantially overlap with another command in the marketplace?
- Does the command reference tools, APIs, or services that no longer exist or are deprecated?
- Would an engineering organization find this command useful?

Only remove a command/skill if both the quantitative signals (flagged by the script) AND the qualitative judgment (low utility) agree. When in doubt, keep the item.

### Step 4: Cross-Reference Scan

Before finalizing the removal list, check whether any item being removed is referenced by items NOT being removed:

```bash
# For each plugin being removed
grep -rl "/{plugin-name}:" plugins/ --include="*.md" | grep -v "plugins/{plugin-name}/"
grep -rl "plugins/{plugin-name}" plugins/ --include="*.md" | grep -v "plugins/{plugin-name}/"

# For each command being removed
grep -rl "{command-name}" plugins/ --include="*.md"
```

Record any cross-references as warnings to include in the report.

### Step 5: Generate Report

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

### Step 6: Dry-Run Exit Point

**If `--dry-run` was specified:** Print the full report to the user and stop. Do not create a branch, remove files, or open a PR.

### Step 7: Create Branch and Remove Items

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

### Step 8: Sync and Commit

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

### Step 9: Push and Open PR

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

### Step 10: Report Results

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
