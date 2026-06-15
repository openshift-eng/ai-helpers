---
name: docs-review-technical
description: Technical accuracy review and code-aware validation with confidence scoring. Supports local branch review, PR/MR review with optional inline comment posting, interactive comment actioning, and code-aware technical validation against source code repos. MUST BE USED when the user asks to validate documentation against code, check technical accuracy, verify commands/APIs/configs in docs match source code, or run a technical review. Also use when the user provides a --code URL or mentions code-aware review.
argument-hint: "[--local | --pr <url> [--post-comments] | --action-comments [url]] [--code <url>] [--fix] [--threshold <0-100>]"
allowed-tools: Read, Write, Glob, Grep, Edit, Bash, Skill, Agent, WebSearch, WebFetch, AskUserQuestion
---

# Technical Accuracy and Code-Aware Review

Multi-agent technical accuracy review with confidence-based scoring and optional code-aware validation against source repositories.

For style guide compliance and modular docs review, use `docs-review-style`.

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
| `--code <url>` | Code repository URL for technical validation (repeatable). Enables Agent 2. |
| `--fix` | Auto-fix high-confidence issues (>=65%), then interactively walk through remaining |
| `--jira <TICKET-123>` | Auto-discover code repos from JIRA ticket (uses `jira-reader`). Enables Agent 2. |
| `--ref <branch>` | Git ref to check out in `--code` repos (default: default branch). Applies to preceding `--code`. |

## Interactive mode — no arguments provided

**STOP. You MUST follow the steps below IN ORDER. Do not skip any step. Do not start the review pipeline until all required inputs are gathered.**

### Step 1: Mode selection — call AskUserQuestion

You MUST call the AskUserQuestion tool now. Do not skip this.

**What type of technical review would you like to run?**

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

### Step 2A-ii: Code-aware validation (optional) — call AskUserQuestion

Call AskUserQuestion with `textInput: true`:

> Do you have a source code repo URL for code-aware validation? (leave blank to skip):

If provided: append `--code <url>` to mode.

Call AskUserQuestion with `textInput: true`:

> Do you have a JIRA ticket for auto-discovering code repos? (leave blank to skip):

If provided: append `--jira <ticket>` to mode.

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

The output is a JSON file mapping each file to either `"new"` (entire file is in scope) or a list of `[start, end]` line ranges (inclusive, 1-based). Read and store this as `CHANGED_RANGES` for use in Steps 4 and 8.

## Step 3: Summarize Changes

Launch a sonnet agent to view changes and return a summary noting:
- Which files are new vs modified
- Whether files appear to be concepts, procedures, references, or assemblies
- Any structural patterns (modular docs, release notes)

For `--pr` mode: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py diff "${PR_URL}"`
For `--local` mode: `git diff "$BASE_BRANCH"...HEAD -- $(cat /tmp/docs-review-doc-files.txt)`

## Step 4: Agent 1 — Technical Accuracy and Consistency

- `subagent_type`: `docs-tools:technical-reviewer`
- `model`: `opus`

Follow the full technical review process: doc type detection, reviewer persona (developer/architect lens), 6 review dimensions, confidence scoring, and output format. Use `jira-reader`, `git-pr-reader`, and `article-extractor` skills to cross-check technical claims. Do not duplicate style or formatting checks.

Returns issues with: `file`, `line`, `description`, `reason`, `confidence` (0-100), `severity` (error/warning/suggestion).

For `--pr` mode, use `python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py extract` for deterministic line numbers.

**Important**: The agent file describes a JIRA-based drafts workflow for standalone use. In this context, ignore JIRA/drafts sections — review changed files from the diff and return issues in the format above.

**CRITICAL — Scope constraint**: Include the contents of `/tmp/docs-review-changed-ranges.json` in the agent's prompt. Instruct the agent:

> **You MUST only flag issues on lines that fall within the changed ranges below. For files marked `"new"`, all lines are in scope. For files with line ranges, ONLY lines within those ranges are in scope. Do NOT flag issues on lines outside these ranges — they are pre-existing content that is not part of this review.**
>
> Changed ranges: `{CHANGED_RANGES}`

## Step 5: Agent 2 — Code-Aware Technical Scan (conditional)

**Only runs when**: `--code <url>` is provided, or code repos can be auto-discovered from the PR URL, JIRA ticket context, or `:code-repo-url:` AsciiDoc attributes in the changed files.

**Dispatched as**: a general-purpose agent.

Workflow:

1. **Clone repos** to `/tmp/tech-review/<repo-name>/` using full history (needed for `git log` search):

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py clone <repo-url> \
     --output-dir /tmp/tech-review/<repo-name>/ --depth 0 [--ref <ref>]
   ```

   **Repository discovery priority**: `--code` (explicit) > PR URL linked repos > `--jira` ticket linked repos > `:code-repo-url:` AsciiDoc attributes.

   If `--jira` is provided, fetch the ticket using `jira-reader` and extract linked PR/MR URLs and repository references. Parse repo URLs from PR links and JIRA ticket fields.

2. **Extract references** from doc files:
   ```bash
   mapfile -t DOC_FILES < /tmp/docs-review-doc-files.txt
   python3 ${CLAUDE_SKILL_DIR}/scripts/extract_refs.py "${DOC_FILES[@]}" --output /tmp/tech-review-refs.json
   ```

3. **Validate claims against code** — For each cloned repo, check if learn-code analysis exists:
   ```bash
   ls /tmp/tech-review/repo-name/.code-learner/ONBOARDING.md 2>/dev/null
   ```

   **If learn-code analysis exists**, read the module summaries from `.code-learner/summaries/` to get `public_api`, `dependencies`, and `data_flow` for each module. Cross-reference documentation claims against these structured summaries.

   **If learn-code analysis does NOT exist**, use direct source file reading: read the extracted references from `/tmp/tech-review-refs.json` and use Grep/Read to verify each reference against the actual source files. This is slower but works without prior analysis.

   For each claim in the documentation (function names, parameter types, configuration options, API endpoints, class names), verify against the source using the best available method (analysis data or direct reading). Record findings as:
   - **verified**: claim matches source code
   - **inaccurate**: claim contradicts source code (include what the source actually says)
   - **stale**: referenced symbol exists but has changed (renamed, deprecated, different signature)
   - **unverifiable**: cannot determine from available sources

4. **Extract API surface** — For each cloned repo:

   **If learn-code analysis exists** (`.code-learner/summaries/`), read the `public_api` field from each module summary. This provides classes, functions, methods with their purposes and dependencies.

   **If no analysis**, use Grep and Read to identify public API symbols:
   ```bash
   # For Go repos: find exported symbols (uppercase)
   grep -rn "^func [A-Z]" /tmp/tech-review/repo-name/
   grep -rn "^type [A-Z]" /tmp/tech-review/repo-name/

   # For Python repos: find public functions/classes
   grep -rn "^def [a-z]" /tmp/tech-review/repo-name/ --include="*.py" | grep -v "^def _"
   grep -rn "^class [A-Z]" /tmp/tech-review/repo-name/ --include="*.py"
   ```

   Build an API reference list for comparison against documentation references.

5. **Triage results** — Review the claim validation findings and API reference list against the extracted references (`/tmp/tech-review-refs.json`). Apply the structured triage pipeline from Step 6 (below). Use Read and Grep on source files to verify ambiguous results.

6. Return issues in the standard format: `file`, `line`, `description`, `reason`, `confidence`, `severity`. Include the code evidence in `reason`.

## Step 6: Structured Triage (Evidence-Based Classification)

Process ALL claim validation findings and API reference data through a classification pipeline. Do NOT skip this step or use ad-hoc exploration.

**Pass 1: Scope filtering (commands only)** — For each command in the extracted references (`/tmp/tech-review-refs.json`), classify the binary as external or in-scope. External system commands (sudo, dnf, oc, kubectl, docker, git, curl, etc.) cannot be validated against the code repo — tag as `out-of-scope` and skip further analysis.

**Pass 2: Claim validation analysis** — For each validated claim:
- `inaccurate` claims → Flag as likely incorrect. Read source to understand the discrepancy. High confidence (>=80%) when source clearly contradicts the claim.
- `unverifiable` claims → Check if the claim references something that should be in the repo. Could be wrong repo, or reference lives elsewhere. Medium confidence (50-70%).
- `stale` claims → Medium-high confidence. Cross-reference the actual current implementation to determine what changed.
- `verified` claims → No issue. Skip.

**Pass 3: API surface comparison** — Compare the extracted references (`/tmp/tech-review-refs.json`) against the API reference list:
- For each API, class, or function referenced in the docs, check if it appears in the API reference. If absent, flag as potentially stale or renamed. Confidence: 60-80%.
- For each entity in the API reference not mentioned in the doc references, note as potentially undocumented. Severity: Low-Medium. Confidence: 60-80%.

**Pass 4: Read source files** — For items flagged in passes 2-3 with confidence >=50%, read the actual source file to confirm the issue. Do not report issues based solely on analysis output without verifying against the source.

**Pass 5: Cross-reference and deduplicate** — Merge findings from passes 2-4:
- If a claim flagged in Pass 2 also has a missing API in Pass 3, consolidate into a single issue with the stronger evidence.
- If an entity flagged as undocumented in Pass 3 is found via additional Grep searches in the source, downgrade or remove.
- Remove duplicate findings that flag the same underlying problem from different angles.

**Assigning severity**: `High` = users will hit errors (broken commands, missing APIs). `Medium` = misleading but not blocking (wrong names, stale options). `Low` = cosmetic or informational (undocumented features, formatting).

### Signal quality filter

**Flag issues where:**
- Documentation will actively mislead users (wrong commands, broken examples, incorrect terminology)
- Code examples contain wrong default values, renamed flags, or missing parameters
- API signatures, return types, or import paths don't match source code
- Configuration keys or values are stale or incorrect

**Do NOT flag:**
- "Not found in code" without concrete evidence of a problem
- Test fixtures, examples, or intentionally different deprecated paths
- External system commands (sudo, grep, git, etc.) that aren't project-specific
- Pre-existing issues in unchanged content
- Minor discrepancies that don't affect functionality

## Step 7: Validate All Issues

For each issue from Steps 4-6, launch parallel subagents to validate:
- Wrong command/flag -> verify the correct command exists in the code
- Stale API reference -> confirm the API was renamed or removed
- Broken code example -> verify the example doesn't compile/run as documented
- Incorrect config value -> confirm the actual default in source

Use opus subagents for structural/technical issues.

## Step 8: Filter Issues

Remove issues that:
- Were not validated in Step 7
- Score below the confidence threshold (default: 80)
- **Fall outside the changed line ranges from Step 2a** — For each issue, check that its `line` number falls within the `CHANGED_RANGES` for its file. For files marked `"new"`, all lines pass. For files with `[[start, end], ...]` ranges, the issue's line must fall within at least one range. Drop any issue that fails this check, regardless of confidence or severity.

## Step 9: Whole-Repo Anti-Pattern Scan (conditional)

**Only runs when Agent 2 ran.** Catches issues grounded review may miss.

**Scan scope**: `.adoc` and `.md` files in the parent directories of the files listed in `/tmp/docs-review-doc-files.txt`.

**9a: Anti-pattern scan** — For each confirmed issue from Agent 2, use Grep to search the broader doc tree for additional occurrences of the same error pattern (e.g., same wrong flag name, same stale config key, same renamed path).

**9b: Blast radius scan** — For each issue from Step 6, search the doc tree for additional occurrences. Record every file and line.

## Step 10: Generate Report and Present Results

Write report to `/tmp/docs-review-technical-report.md` using the format below. Output summary to terminal:

```
## Technical Review

**Source**: <branch vs base | PR/MR URL>
**Files reviewed**: X documentation files
**Issues found**: Y (Z above confidence threshold)

### Issues

1. **file.adoc:23** [confidence: 95] — Flag `--enable-feature` renamed to `--feature-enable` in v2.3 (code-scan)
2. **file.adoc:67** [confidence: 88] — Default `pool_size` is 5, not 10 (technical-review)

### Skipped (below threshold)

- **file.adoc:91** [confidence: 55] — Config key `max_retries` not found in source

Full report saved to: /tmp/docs-review-technical-report.md
```

### For --local mode: Offer to Apply Changes

After the summary, offer to apply fixes for errors. Describe suggestions but let the user decide.

### For --pr mode without --post-comments

Stop here.

### For --pr mode with --post-comments

If NO issues found, post a summary comment via `git-pr-reader`:

```bash
cat <<'SUMMARY' > /tmp/docs-review-summary.json
[{"file": "", "line": 0, "message": "## Technical review\n\nNo issues found. Checked for technical accuracy and code-aware validation.", "severity": "suggestion"}]
SUMMARY
python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py post "${PR_URL}" /tmp/docs-review-summary.json --review-type technical
```

If issues found, continue to Step 11.

## Step 11: Post Inline Comments (--post-comments only)

Get deterministic line numbers:
```bash
LINE=$(python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py extract "${PR_URL}" "path/to/file.adoc" "pattern from the issue")
```

Build comments JSON and post:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py post "${PR_URL}" /tmp/docs-review-comments.json --review-type technical
```

For each comment: brief description with evidence from source code, include corrected values for small fixes, describe larger fixes without inline code. **Only ONE comment per unique issue.**

## Step 11a: Fix Mode (--fix only)

**Phase A — Auto-fix**: For each issue with confidence >=65%, apply the fix using the Edit tool.

**Phase B — Interactive walkthrough**: For each issue with confidence <65%, present to user:

```
Issue 1 of 5: Command flag renamed | Confidence: 60% | Severity: High
File: modules/proc-install.adoc

Current:   $ my-tool --enable-feature
Suggested: $ my-tool --feature-enable

Evidence: Flag renamed in commit abc123
```

Ask user via AskUserQuestion: **Apply** | **Modify** | **Skip** | **Delete section**

**Fix-mode report** — When `--fix` is used, the report at `/tmp/docs-review-technical-report.md` includes additional sections:

### Issues Auto-Fixed

| ID | File:Line | Issue | Evidence | Before | After |
|----|-----------|-------|----------|--------|-------|
| AF-1 | file.adoc:23 | Flag renamed | cli_validation | `--enable-feature` | `--feature-enable` |

### Issues Interactively Resolved

| ID | File:Line | Issue | Action |
|----|-----------|-------|--------|
| IR-1 | file.adoc:45 | Stale config key | Applied suggested fix |
| IR-2 | file.adoc:67 | Wrong default | Modified by user |

### Issues Skipped

| ID | File:Line | Issue | Confidence |
|----|-----------|-------|------------|
| SK-1 | file.adoc:91 | Config key not found | 55% |

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
| **Required** | Technical errors, broken examples, incorrect commands | Must fix |
| **Suggestion** | Improvements, alternative approaches | User discretion |
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
# Technical Review Report

**Source**: [Branch: <branch> vs <base> | PR/MR URL]
**Date**: YYYY-MM-DD

## Grounded Review Summary

| Metric | Count |
|--------|-------|
| Claims extracted | X |
| Supported | A |
| Partially supported | B |
| Unsupported | C |
| No evidence found | D |

## API Surface Summary

| Metric | Count |
|--------|-------|
| Files processed | X |
| Total entities | Y |
| Entities in docs | Z |
| Potentially undocumented | N |

## Code Repositories

| Repo | Ref | Clone Path | Source |
|------|-----|------------|--------|
| repo-name | main | /tmp/tech-review/repo-name | --code |

## Triage Summary

| Pass | Description | Items Processed | Issues Flagged |
|------|-------------|-----------------|----------------|
| Pass 1 | Scope filtering | X | Y |
| Pass 2 | Claim verdict analysis | X | Y |
| Pass 3 | API surface comparison | X | Y |
| Pass 4 | Source file verification | X | Y |
| Pass 5 | Cross-reference and deduplicate | X | Y |

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

#### Technical Accuracy

| Line | Severity | Issue | Evidence |
|------|----------|-------|----------|

#### Code Validation (if Agent 2 ran)

| Line | Severity | Issue | Evidence | Verdict |
|------|----------|-------|----------|---------|

Show specific value mismatches (e.g., "Docs: pool_size=10, Code: pool_size=5"), unsupported claims, and import path errors. Only report items where grounded review returned `unsupported` or `no_evidence_found` with concrete evidence, or where the API surface shows a missing/renamed entity.

---

## Required Changes

1. **file.adoc:23** — Description (evidence) [verdict: unsupported]

## Suggestions

1. **file.adoc:91** — Description [verdict: no_evidence_found]

## Undocumented API Surface (if Agent 2 ran)

Entities found in API surface but not referenced in reviewed documentation:

| Type | Name | Source File | Signature |
|------|------|-------------|-----------|
| function | list_resources | src/app.py:12 | def list_resources() |
| class | ExampleClient | src/client.py:2 | class ExampleClient |

## Out-of-Scope References

| Tool | Count |
|------|-------|
| sudo | X |
| kubectl | Y |

---

*Generated with [Claude Code](https://claude.com/claude-code)*
```

**Sections**: Errors = must fix. Warnings = should fix. Suggestions = optional.

**Do NOT include**: positive findings, executive summaries, compliance percentages, references sections.

## Feedback Guidelines

- **In scope**: Content changed in the branch or PR/MR. **Out of scope**: Unchanged content, enhancement requests.
- **Required** (blocks merging): Incorrect commands, wrong API references, broken code examples, stale config values.
- **Optional** (does not block): Minor accuracy improvements, additional context. Mark with **[SUGGESTION]**.
- Include source code evidence for each issue. For recurring issues: "[GLOBAL] This issue occurs elsewhere."

---

# Notes

- Always use `python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py` for all Git platform interactions (see `git-pr-reader` for full API reference)
- Always use `git_pr_reader.py extract` for deterministic line numbers — never estimate or guess
- Use Bash with heredoc/cat for writing /tmp files (not the Write tool)
- Include source code evidence in each issue's `reason` field
- Comments are posted under YOUR username using tokens from `.env` files
- `scripts/extract_refs.py` extracts technical references from doc files (commands, APIs, configs, file paths)
- When reviewing repos with learn-code analysis (`.code-learner/` directory), read ONBOARDING.md and module summaries for structured code understanding. When no analysis exists, use Read/Grep directly on source files.
- Vale linting is NOT part of the technical review — use `docs-review-style` for that
