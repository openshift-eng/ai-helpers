---
name: docs-review-style
description: Multi-agent style guide and modular docs review with confidence scoring. Supports local branch review, PR/MR review with optional inline comment posting, interactive comment actioning, and fix mode. MUST BE USED when the user asks for style guide compliance review, modular docs structure review, content quality checks, or wants to review documentation for formatting and language issues.
argument-hint: "[--local | --pr <url> [--post-comments] | --action-comments [url]] [--fix] [--threshold <0-100>]"
allowed-tools: Read, Write, Glob, Grep, Edit, Bash, Skill, Agent, WebSearch, WebFetch, AskUserQuestion
---

# Style Guide and Modular Docs Review

Multi-agent style guide compliance and modular docs review with confidence-based scoring.

For technical accuracy and code-aware validation, use `docs-review-technical`.

## Modes

| Arguments | Mode | Description |
|-----------|------|-------------|
| `--local` | Local review | Review doc changes in current branch vs base branch |
| `--pr <url>` | PR/MR review | Review doc changes in a GitHub PR or GitLab MR |
| `--pr <url> --post-comments` | PR/MR + post | Review and post inline comments to PR/MR |
| `--action-comments [url]` | Action comments | Fetch and interactively action unresolved PR/MR review comments (auto-detects PR if URL omitted) |
| *(no arguments)* | Interactive | AskUserQuestion gathers mode and options |

## Global Options

| Option | Description |
|--------|-------------|
| `--threshold <0-100>` | Confidence threshold for reporting issues (default: 80) |
| `--fix` | Auto-fix high-confidence issues (>=65%), then interactively walk through remaining |

## Interactive mode — no arguments provided

**STOP. You MUST follow the steps below IN ORDER. Do not skip any step. Do not start the review pipeline until all required inputs are gathered.**

### Step 1: Mode selection — call AskUserQuestion

You MUST call the AskUserQuestion tool now. Do not skip this.

**What type of style review would you like to run?**

| Option | Description |
|--------|-------------|
| Review local branch changes | Review doc changes in current branch vs base branch |
| Review a PR/MR | Review doc changes in a GitHub PR or GitLab MR |
| Action unresolved review comments | Fetch and interactively action unresolved PR/MR review comments |

Wait for the answer before proceeding.

- If **"Review local branch changes"**: set mode to `--local`. Proceed to Step 3.
- If **"Review a PR/MR"**: proceed to Step 2A.
- If **"Action unresolved review comments"**: proceed to Step 2B.

### Step 2A: PR/MR details — call AskUserQuestion

Call AskUserQuestion with `textInput: true`:

> Enter the PR/MR URL (e.g., https://github.com/org/repo/pull/123):

Set mode to `--pr <url>`.

Then call AskUserQuestion:

**Post inline comments to the PR/MR?**

| Option | Description |
|--------|-------------|
| No (default) | Review only — results displayed locally |
| Yes | Post review findings as inline PR/MR comments |

If **"Yes"**: append `--post-comments` to mode.

Proceed to Step 3.

### Step 2B: Action comments — call AskUserQuestion

Call AskUserQuestion with `textInput: true`:

> Enter the PR/MR URL, or leave blank to auto-detect from current branch:

- If blank: set mode to `--action-comments`.
- If URL provided: set mode to `--action-comments <url>`.

Then call AskUserQuestion:

**Which comments should be included?**

| Option | Description |
|--------|-------------|
| Unresolved only (default) | Only show comments that have not been resolved |
| All comments | Include both resolved and unresolved comments |

- If **"All comments"**: set `INCLUDE_RESOLVED=true`.

Proceed to the **Mode: --action-comments** section (skip Step 3).

### Step 3: Fix mode — call AskUserQuestion

Call AskUserQuestion:

**Apply automatic fixes for high-confidence issues?**

| Option | Description |
|--------|-------------|
| No (default) | Report issues only |
| Yes | Auto-fix issues with confidence >=65%, then walk through the rest interactively |

If **"Yes"**: append `--fix` to mode.

Proceed to the review pipeline with the constructed arguments.

## Agent Assumptions

These apply to ALL agents and subagents:

- All tools are functional. Do not test tools or make exploratory calls.
- Only call a tool if required. Every tool call should have a clear purpose.
- The confidence threshold is 80 by default (adjustable with `--threshold`).

---

# Multi-Agent Review Pipeline

The `--local` and `--pr` modes share the same pipeline. The difference is how files are discovered and how results are delivered.

## Step 1: Pre-flight Checks

### For --pr mode

Launch a haiku agent to run pre-flight checks using `git-pr-reader`. Stop if any condition is true (still review Claude-generated PRs):

- **PR/MR is closed or draft**: Check the PR/MR state from the platform API.
- **No documentation files changed**: Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py files "${PR_URL}" --json` and check if any changed files end with `.adoc` or `.md`.
- **Claude already commented**: Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py comments "${PR_URL}" --include-resolved --json` and check if any comment `author` matches Claude's username.

### For --local mode

```bash
CURRENT_BRANCH=$(git branch --show-current)
# Detect base branch from remote default, fall back to local refs
BASE_BRANCH=$(git rev-parse --abbrev-ref origin/HEAD 2>/dev/null | sed 's|^origin/||')
if [ -z "$BASE_BRANCH" ]; then
    if git show-ref --verify --quiet refs/heads/main; then
        BASE_BRANCH="main"
    elif git show-ref --verify --quiet refs/heads/master; then
        BASE_BRANCH="master"
    else
        echo "ERROR: Cannot determine base branch"; exit 1
    fi
fi
if [ "$CURRENT_BRANCH" = "$BASE_BRANCH" ]; then
    echo "ERROR: Currently on $BASE_BRANCH. Switch to a feature branch first."; exit 1
fi
```

## Step 2: Discover Documentation Files

### For --local mode

```bash
git diff --name-only "$BASE_BRANCH"...HEAD | sort -u | grep -E '\.(adoc|md)$' > /tmp/docs-review-doc-files.txt || true
DOC_FILES=$(wc -l < /tmp/docs-review-doc-files.txt)
```

### For --pr mode

Use `git-pr-reader` to get changed files:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py files "${PR_URL}" --json | \
    python3 -c "import json,sys; files=[f['path'] for f in json.load(sys.stdin) if f['path'].endswith(('.adoc','.md'))]; print('\n'.join(files))" > /tmp/docs-review-doc-files.txt
```

### For both modes

If no documentation files found, report and exit.

## Step 2a: Extract Changed Line Ranges

Extract the exact changed line ranges so review agents only flag issues in changed content.

### For --local mode

```bash
git diff "$BASE_BRANCH"...HEAD -- $(cat /tmp/docs-review-doc-files.txt | tr '\n' ' ') | \
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/extract_changed_ranges.py \
    --context 3 -o /tmp/docs-review-changed-ranges.json
```

### For --pr mode

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py diff "${PR_URL}" | \
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/extract_changed_ranges.py \
    --context 3 -o /tmp/docs-review-changed-ranges.json
```

The output is a JSON file mapping each file to either `"new"` (entire file is in scope) or a list of `[start, end]` line ranges (inclusive, 1-based). Read and store this as `CHANGED_RANGES` for use in Steps 4 and 6.

## Step 3: Summarize Changes

Launch a sonnet agent to view changes and return a summary noting:
- Which files are new vs modified
- Whether files appear to be concepts, procedures, references, or assemblies
- Any structural patterns (modular docs, release notes)

For `--pr` mode: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py diff "${PR_URL}"`
For `--local` mode: `git diff "$BASE_BRANCH"...HEAD -- $(cat /tmp/docs-review-doc-files.txt)`

## Step 4: Multi-Agent Parallel Review

Launch agents in parallel. Each agent returns issues with: `file`, `line`, `description`, `reason`, `confidence` (0-100), `severity` (error/warning/suggestion).

For `--pr` mode, use `python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py extract` for deterministic line numbers.

**Important**: The agent files describe a JIRA-based drafts workflow for standalone use. In this context, ignore JIRA/drafts sections — review changed files from the diff and return issues in the format above.

**CRITICAL — Scope constraint**: Include the contents of `/tmp/docs-review-changed-ranges.json` in each agent's prompt. Instruct each agent:

> **You MUST only flag issues on lines that fall within the changed ranges below. For files marked `"new"`, all lines are in scope. For files with line ranges, ONLY lines within those ranges are in scope. Do NOT flag issues on lines outside these ranges — they are pre-existing content that is not part of this review.**
>
> Changed ranges: `{CHANGED_RANGES}`

### Agent 1: Style guide compliance (batch A)

- `subagent_type`: `docs-tools:docs-reviewer`

Focus on: `ibm-sg-language-and-grammar`, `ibm-sg-punctuation`, `ibm-sg-structure-and-format`, `ibm-sg-technical-elements`, `rh-ssg-grammar-and-language`, `rh-ssg-formatting`, `rh-ssg-structure`, `rh-ssg-technical-examples`

### Agent 2: Style guide compliance (batch B)

- `subagent_type`: `docs-tools:docs-reviewer`

Focus on: `ibm-sg-audience-and-medium`, `ibm-sg-numbers-and-measurement`, `ibm-sg-references`, `ibm-sg-legal-information`, `rh-ssg-gui-and-links`, `rh-ssg-legal-and-support`, `rh-ssg-accessibility`, `rh-ssg-release-notes`

### Agent 3: Modular docs structure and content quality

- `subagent_type`: `docs-tools:docs-reviewer`

Focus on: `docs-review-modular-docs`, `docs-review-content-quality`. Run Vale once per file if available.

### Signal quality filter

**Flag issues where:**
- Required modular docs structure is missing or incorrect
- Clear, unambiguous style guide violations with a citable rule
- Accessibility failures (missing alt text, inaccessible tables)

**Do NOT flag:**
- Minor stylistic preferences that don't affect clarity
- Potential issues depending on context outside changed files
- Subjective wording suggestions unless they violate a specific rule
- Pre-existing issues in unchanged content
- Something that appears to be a style violation but is an accepted project convention
- Pedantic nitpicks that a senior technical writer would not flag
- Issues that Vale will catch automatically (do not run Vale to verify unless the agent has Vale available)
- General quality concerns (e.g., "could be more concise") unless they violate a specific rule
- Style suggestions that conflict with existing content in the same document
- Terminology that matches the product's official naming even if it differs from the style guide

## Step 5: Validate Issues

For each issue from Step 4, launch parallel subagents to validate:
- Missing short description -> verify `[role="_abstract"]` is actually absent
- Style violation -> confirm the specific rule applies and text truly violates it
- Broken cross-reference -> verify the target doesn't exist
- Terminology error -> check it's not an acceptable variant

Use sonnet subagents for style violations.

## Step 6: Filter Issues

Remove issues that:
- Were not validated in Step 5
- Score below the confidence threshold (default: 80)
- **Fall outside the changed line ranges from Step 2a** — For each issue, check that its `line` number falls within the `CHANGED_RANGES` for its file. For files marked `"new"`, all lines pass. For files with `[[start, end], ...]` ranges, the issue's line must fall within at least one range. Drop any issue that fails this check, regardless of confidence or severity.

## Step 7: Generate Report and Present Results

Write report to `/tmp/docs-review-style-report.md` using the format below. Output summary to terminal:

```
## Style Review

**Source**: <branch vs base | PR/MR URL>
**Files reviewed**: X documentation files
**Issues found**: Y (Z above confidence threshold)

### Issues

1. **file.adoc:15** [confidence: 92] — Missing `:_mod-docs-content-type:` attribute (modular-docs)
2. **file.adoc:42** [confidence: 85] — Use "data center" not "datacenter" (RedHat.TermsErrors)

### Skipped (below threshold)

- **file.adoc:55** [confidence: 60] — Consider using active voice

Full report saved to: /tmp/docs-review-style-report.md
```

### For --local mode: Offer to Apply Changes

After the summary, offer to apply fixes for errors. Describe suggestions but let the user decide.

### For --pr mode without --post-comments

Stop here.

### For --pr mode with --post-comments

If NO issues found, post a summary comment via `git-pr-reader`:

```bash
cat <<'SUMMARY' > /tmp/docs-review-summary.json
[{"file": "", "line": 0, "message": "## Style review\n\nNo issues found. Checked for style guide compliance, modular docs structure, and content quality.", "severity": "suggestion"}]
SUMMARY
python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py post "${PR_URL}" /tmp/docs-review-summary.json --review-type style
```

If issues found, continue to Step 8.

## Step 8: Post Inline Comments (--post-comments only)

Get deterministic line numbers:
```bash
LINE=$(python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py extract "${PR_URL}" "path/to/file.adoc" "pattern from the issue")
```

Build comments JSON and post:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py post "${PR_URL}" /tmp/docs-review-comments.json --review-type style
```

For each comment: brief description with style guide rule, include corrected text for small fixes, describe larger fixes without inline code. **Only ONE comment per unique issue.**

## Step 8a: Fix Mode (--fix only)

**Phase A — Auto-fix**: For each issue with confidence >=65%, apply the fix using the Edit tool.

**Phase B — Interactive walkthrough**: For each issue with confidence <65%, present to user:

```
Issue 1 of 5: Missing content type attribute | Confidence: 60% | Severity: Warning
File: modules/con-overview.adoc

Current:   [id="con-overview_{context}"]
Suggested: Add :_mod-docs-content-type: CONCEPT after the module ID

Evidence: docs-review-modular-docs rule
```

Ask user via AskUserQuestion: **Apply** | **Modify** | **Skip** | **Delete section**

---

# Mode: --action-comments

Fetch unresolved review comments from GitHub PRs or GitLab MRs and interactively action them on local files.

## Step 1: Resolve PR/MR URL

If URL provided, use directly. If omitted, auto-detect:
```bash
PR_URL=$(python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py detect 2>/dev/null)
```

If detection fails, stop with:

> Could not detect a PR/MR for the current branch. Please provide a URL and try again.

## Step 2: Get PR info and check out the branch locally

Fetch PR metadata to determine the source branch:

```bash
HEAD_REF=$(python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py info "${PR_URL}" --field head_ref)
BASE_REF=$(python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py info "${PR_URL}" --field base_ref)
TITLE=$(python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py info "${PR_URL}" --field title)
```

Check whether the current branch matches `head_ref`:

```bash
CURRENT_BRANCH=$(git branch --show-current)
```

**If already on the correct branch**: proceed to Step 3.

**If on a different branch**:

1. Check for uncommitted changes:
   ```bash
   git status --porcelain
   ```
   If there are uncommitted changes, stop with:
   > You have uncommitted changes on `{CURRENT_BRANCH}`. Please commit or stash them before switching branches.

2. Fetch and check out the PR branch:
   ```bash
   git fetch origin "${HEAD_REF}"
   git checkout "${HEAD_REF}"
   ```

   If the branch does not exist locally, create a tracking branch:
   ```bash
   git checkout -b "${HEAD_REF}" "origin/${HEAD_REF}"
   ```

Report to the user:

> Checked out branch `{HEAD_REF}` for PR: {title}

## Step 3: Fetch review comments

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py comments "${PR_URL}" --json
```

Add `--include-resolved` if `INCLUDE_RESOLVED=true` (set during interactive mode).

The script automatically filters bot comments, resolved threads (unless `--include-resolved`), and returns top-level comments with: `id`, `path`, `line`, `body`, `author`, `resolved`.

If no comments are returned, report:

> No unresolved review comments found on this PR/MR.

And stop.

## Step 4: Categorize comments

Before presenting comments, categorize each one:

| Category | Criteria | Action |
|----------|----------|--------|
| **Required** | Style violations, technical errors, broken examples | Must fix |
| **Suggestion** | Wording improvements, reorganization | User discretion |
| **Question** | Requests for clarification, questions from reviewer | Present but do not auto-suggest a fix |
| **Outdated** | Already addressed by subsequent commits | Skip automatically |

For **Outdated** detection: read the file at the comment's `path` and `line`. If the content no longer matches what the comment references, mark as outdated. Extract the reviewer's quoted text from markdown blockquotes (`>` lines) in the `body` field. If no blockquotes are present, fall back to comparing against the line context.

## Step 5: Process each comment interactively

For each non-outdated comment, present:

```markdown
## Comment {N} of {total} from @{author} on `{path}:{line}` [{category}]

> {comment_body}

### Current content (local file)
{relevant lines from the local file around the comment's line}

### Suggested change
{your analysis and proposed edit}
```

Call AskUserQuestion with these options:

| Option | Description |
|--------|-------------|
| Apply | Apply the suggested change |
| Edit | Apply with modifications — ask for user's preferred text |
| Skip | Skip this comment |
| View context | Show more surrounding lines, then re-ask |

**When Apply is selected**: Read the target file, apply the edit using Edit tool, confirm the change was applied, move to next comment.

**When Edit is selected**: Call AskUserQuestion with `textInput: true`:

> Enter the text you'd like to use instead:

Apply the user's text using Edit tool, confirm, move to next.

**When View context is selected**: Read 20 lines before and after the comment's line from the local file, display them, then re-present the same options.

**When Skip is selected**: Move to next comment.

## Step 6: Summary

After all comments are processed, present:

```markdown
## Action Comments Summary

**PR/MR**: {PR_URL}
**Branch**: {HEAD_REF}

| Metric | Count |
|--------|-------|
| Total comments | X |
| Applied | Y |
| Edited | Z |
| Skipped | S |
| Outdated (auto-skipped) | O |
| Bot comments (filtered) | B |

### Changes applied

1. `{path}:{line}` — {brief description of change}
2. ...

### Comments skipped

1. `{path}:{line}` — @{author}: "{truncated comment}" — Reason: {user skipped / outdated}
```

If any changes were applied, remind the user:

> Changes have been applied to your local files on branch `{HEAD_REF}`. Review them with `git diff` and commit when ready.

---

# Report Format

```markdown
# Style Review Report

**Source**: [Branch: <branch> vs <base> | PR/MR URL]
**Date**: YYYY-MM-DD

## Summary

| Metric | Count |
|--------|-------|
| Files reviewed | X |
| Errors (must fix) | Y |
| Warnings (should fix) | Z |
| Suggestions (optional) | N |

## Files Reviewed

### 1. path/to/file.adoc

**Type**: CONCEPT | PROCEDURE | REFERENCE | ASSEMBLY

#### Vale Linting

| Line | Severity | Rule | Message |
|------|----------|------|---------|

#### Structure Review

| Line | Severity | Issue |
|------|----------|-------|

#### Language Review

| Line | Severity | Issue |
|------|----------|-------|

#### Elements Review

| Line | Severity | Issue |
|------|----------|-------|

---

## Required Changes

1. **file.adoc:15** — Description

## Suggestions

1. **file.adoc:55** — Description

---

*Generated with [Claude Code](https://claude.com/claude-code)*
```

**Sections**: Errors = must fix. Warnings = should fix. Suggestions = optional.

**Do NOT include**: positive findings, executive summaries, compliance percentages, references sections.

## Feedback Guidelines

- **In scope**: Content changed in the branch or PR/MR. **Out of scope**: Unchanged content, enhancement requests.
- **Required** (blocks merging): Typos, modular docs violations, style guide violations.
- **Optional** (does not block): Wording improvements, reorganization, stylistic preferences. Mark with **[SUGGESTION]**.
- Cite specific style guide rules. Use softening language for suggestions. For recurring issues: "[GLOBAL] This issue occurs elsewhere."

---

# Notes

- Always use `python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py` for all Git platform interactions (see `git-pr-reader` for full API reference)
- Always use `git_pr_reader.py extract` for deterministic line numbers — never estimate or guess
- Use Bash with heredoc/cat for writing /tmp files (not the Write tool)
- Cite the specific style guide rule or review skill for each issue
- Comments are posted under YOUR username using tokens from `.env` files
- For .adoc files, modular docs compliance uses `docs-review-modular-docs`
- Release notes skills only apply to .adoc files that appear to be release notes
- Vale linting requires Vale to be installed and configured
