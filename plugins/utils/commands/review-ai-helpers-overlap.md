---
description: Review potential overlaps with existing ai-helpers (Claude Code Plugins, Commands, Skills, Sub-agents, or Hooks) and open PRs
argument-hint: "[--idea TEXT] [--pr NUMBER] [--verbose]"
---

## Name
utils:review-ai-helpers-overlap

## Synopsis
```
/utils:review-ai-helpers-overlap [--idea "description"] [--pr NUMBER] [--verbose]
```

## Description
Review potential overlaps between your planned or implemented work and existing **Claude Code Plugins, Commands, Skills, Sub-agents, or Hooks** in the `openshift-eng/ai-helpers` repository to avoid duplicating effort and find collaboration opportunity.

This command is specifically designed for contributors and reviewers to the `openshift-eng/ai-helpers` repository. It checks for overlaps in:
- Plugin commands (`plugins/*/commands/*.md`)
- Skills (`plugins/*/skills/*/SKILL.md` and helper scripts)
- Sub-agents (`agents/*.md`)
- Hooks (`.claude/hooks/*.sh` and `.claude/hooks/*.py`)

**Modes**:
- **Idea check** (`--idea "TEXT"`): Check if your idea already exists before writing code
- **Local check** (default): Compare your local changes against main branch and open PRs
- **PR review mode** (`--pr NUMBER`): Check if a specific PR overlaps with others

This command helps contributors avoid duplicate work and helps reviewers identify related PRs that should be consolidated.

## Implementation

Phased duplicate detection with token-efficient early returns:
- Checks local git changes, open PRs, and main branch commands
- Uses semantic matching ("analyze" ≈ "inspect") via Claude's LLM
- Progressive disclosure: summary → findings → verbose details

### Step 0: Determine Mode

Parse `$ARGUMENTS`:
1. **Idea Mode**: If `--idea "TEXT"` provided - extract idea description
2. **PR Review Mode**: If `--pr <NUMBER>` provided - extract PR number
3. **Contributor Mode** (default): Check local git diff

Store flags: `verbose`

### Step 1: Set Repository Context

This command only works with the `openshift-eng/ai-helpers` repository.

Validate repository:
```bash
# Check if we're in the ai-helpers repository
REPO_URL=$(git remote get-url upstream 2>/dev/null || git remote get-url origin)
if ! echo "$REPO_URL" | grep -q "openshift-eng/ai-helpers"; then
  echo "Error: This command only works in the openshift-eng/ai-helpers repository"
  exit 1
fi

# Hardcode repository for all gh commands
REPO="openshift-eng/ai-helpers"
```

### Step 2: Gather Context

**Idea Mode**: Extract keywords from idea description using Claude's semantic understanding

**Contributor Mode**:
- Get changed files from ai-helpers structure:
  ```bash
  # Get all ai-helpers changes in one pass (commands, skills, agents, hooks)
  CHANGED_FILES=$(git diff --name-only main...HEAD | grep -E '(^plugins/.*/commands/.*\.md$|^plugins/.*/skills/.*/SKILL\.md$|^plugins/.*/skills/.*\.py$|^agents/.*\.md$|^\.claude/hooks/.*\.(sh|py)$)')
  ```
- If no ai-helpers-specific files changed: Show message "No ai-helpers changes detected (commands, skills, agents, or hooks). This tool is designed for ai-helpers repository contributions." and exit
- For each file, use Read to extract: plugin name, command/skill/agent name, description (first 500 chars)

**PR Review Mode**:
- Get PR files: `gh pr view <NUMBER> --repo "$REPO" --json files --jq '.files[].path'`
- Get content: `gh pr diff <NUMBER> --repo "$REPO" -- <file_path>`
- Parse diff for added lines and extract metadata

### Step 3: Check PR Titles (Lightweight)

Fetch open PRs (metadata only): `gh pr list --repo "$REPO" --state open --json number,title,body,author,createdAt --limit 100`

Match keywords semantically:
- **Idea Mode**: Check PR titles/bodies for idea keywords
- **Contributor/PR Review Mode**: Check for plugin name, command name, similar keywords

If potential overlap found, prompt user: "Continue with deep comparison? (y/n)"
- If "no": Exit with recommendation to review the PR
- If "yes" or no overlap: Continue to Step 4

### Step 4: Deep Semantic Comparison

Run if Step 3 flagged overlaps (user confirmed) OR `--verbose` flag OR no obvious overlaps in Step 3.

For flagged PRs:
1. Fetch content based on file type:
   - Commands: `gh pr diff <PR_NUMBER> --repo "$REPO" -- plugins/<plugin>/commands/<command>.md`
   - Skills: `gh pr diff <PR_NUMBER> --repo "$REPO" -- plugins/<plugin>/skills/<skill>/SKILL.md`
   - Agents: `gh pr diff <PR_NUMBER> --repo "$REPO" -- agents/<agent>.md`
   - Hooks: `gh pr diff <PR_NUMBER> --repo "$REPO" -- .claude/hooks/<hook>.(sh|py)`
2. Parse diff to extract Description and Implementation sections
3. Claude compares purposes, workflows, functionality and assesses overlap:
   - **HIGH (85-100%)**: Near-identical → Strong warning to collaborate
   - **MODERATE (60-85%)**: Similar goal, different approach → Soft warning to differentiate
   - **LOW (<60%)**: Different purposes → OK to proceed

### Step 5: Check Main Branch

**Idea Mode**: Scan all ai-helpers files:
- Commands: `find plugins/*/commands/*.md`
- Skills: `find plugins/*/skills/*/SKILL.md`
- Agents: `find agents/*.md`
- Hooks: `find .claude/hooks/*.{sh,py}`

Use Read for frontmatter descriptions, flag if 3+ keyword overlap or semantic similarity

**Contributor/PR Review Mode**: List existing files in changed areas:
- Commands: `ls plugins/<plugin>/commands/*.md`
- Skills: `ls plugins/<plugin>/skills/*/SKILL.md`
- Agents: `ls agents/*.md`
- Hooks: `ls .claude/hooks/*.{sh,py}`

Check for duplicate names and description similarity

### Step 6: Present Findings

Use progressive disclosure (3 layers):
- **Layer 1 (always)**: Summary of checks performed and files analyzed
- **Layer 2 (if overlaps)**: Detailed findings with severity ([HIGH/MODERATE/LOW OVERLAP]), PR links, and recommendations for joint effort
- **Layer 3 (`--verbose`)**: Side-by-side comparison with differentiation suggestions

### Step 7: Save Report (Optional)

If overlaps found, save detailed report to `.work/review-ai-helpers-overlap/report-{timestamp}.md` with summary, PRs compared, findings, and recommendations. Display file path to user.

## Examples

1. **Idea validation (before coding)**:
   ```
   /utils:review-ai-helpers-overlap --idea "command to analyze Jira issues and create PRs"

   /utils:review-ai-helpers-overlap --idea "command to analyze test coverage"
   ```
   Checks if a similar command already exists in ai-helpers plugins or there are opened PR(s) for similar purpose

2. **Check local changes before raising a PR** (ai-helpers contributor workflow):
   ```
   /utils:review-ai-helpers-overlap
   ```
   Checks your local command/skill/agent/hook changes against main branch and open PRs.

3. **PR review (check if PR overlaps with others)**:
   ```
   /utils:review-ai-helpers-overlap --pr 123
   ```
   Check if PR #123 overlaps with other open PRs

## Return Value

Structured overlap analysis with progressive disclosure:
- **Summary**: Checks performed and files analyzed
- **Findings** (if overlaps): Severity ratings (HIGH/MODERATE/LOW), PR links, recommendations
- **Verbose details** (`--verbose`): Side-by-side comparisons with differentiation suggestions

Optionally saves report to `.work/review-ai-helpers-overlap/report-{timestamp}.md` when overlaps found.

## Notes

- **Repository Scope**: This command only works in the `openshift-eng/ai-helpers` repository
- **Requirements**: GitHub CLI (`gh`) and git
- **Best Practice**: Contributors run `/utils:review-ai-helpers-overlap --idea` during planning, run `/utils:review-ai-helpers-overlap` during developing; reviewers use `--pr <NUMBER>` during reviewing
- Uses semantic matching ("analyze" ≈ "inspect") and phased checks (PR titles → full diffs) for token efficiency

## Arguments

- `--idea "TEXT"`: Check if your idea exists before coding (activates idea validation mode)
- `--pr <NUMBER>`: Check if specific PR overlaps with others (reviewer mode)
- `--verbose`: Show detailed side-by-side comparisons (Layer 3 output)
