---
name: docs-workflow-style-review
description: Style guide compliance review of documentation drafts. Dispatches the docs-tools:docs-reviewer agent with Vale linting and 18+ style guide review skills.
argument-hint: <ticket> --base-path <path> --format <adoc|mkdocs>
allowed-tools: Read, Write, Glob, Grep, Edit, Bash, Skill, Agent, WebSearch, WebFetch
---

# Style Review Step

Step skill for the docs-orchestrator pipeline. Follows the step skill contract: **parse args → dispatch agent → write output**.

## Arguments

- `$1` — JIRA ticket ID (required)
- `--base-path <path>` — Base output path (e.g., `.agent_workspace/proj-123`)
- `--format <adoc|mkdocs>` — Documentation format (default: `adoc`)

## Input

```
<base-path>/writing/
```

## Output

```
<base-path>/style-review/review.md
```

## Execution

### 1. Parse arguments

Extract the ticket ID, `--base-path`, and `--format` from the args string.

Set the paths:

```bash
OUTPUT_DIR="${BASE_PATH}/style-review"
OUTPUT_FILE="${OUTPUT_DIR}/review.md"
mkdir -p "$OUTPUT_DIR"
```

### 2. Determine source files

Read the writing step's sidecar at `${BASE_PATH}/writing/step-result.json` to determine the writing mode and file list.

**If the sidecar exists and `mode` is `"update-in-place"` with a non-empty `files` array:**

Build a `<SOURCE_FILES_BLOCK>` listing the files explicitly:

```
**Source files** — review and edit each of these files:
- `/absolute/path/to/file1.adoc`
- `/absolute/path/to/file2.adoc`

**Edit files in place** at their current paths. Do NOT create copies or move files.
```

**Otherwise** (draft mode, missing sidecar, or empty files array):

Set `DRAFTS_DIR="${BASE_PATH}/writing"` and build the block as:

```
**Source files**: `<DRAFTS_DIR>/` — review and edit files at this location only.

**Edit files in place** at the source path above. Do NOT create copies or write to a drafts/ subfolder.
```

### 3. Dispatch agent

**You MUST use the Agent tool** to invoke the `docs-tools:docs-reviewer` subagent. Do NOT read the agent's markdown file or attempt to perform the agent's work yourself — the agent has a specialized system prompt and must run as an isolated subagent.

Select the prompt below based on the `--format` flag. Substitute `<SOURCE_FILES_BLOCK>` with the block built in step 2.

**Agent tool parameters:**
- `subagent_type`: `docs-tools:docs-reviewer`
- `description`: `Review documentation for <TICKET>`

**Prompt for AsciiDoc** (`--format adoc`):

> Review the AsciiDoc documentation drafts for ticket `<TICKET>`.
>
> <SOURCE_FILES_BLOCK>
>
> **Report output**: `<OUTPUT_FILE>` — you MUST save the review report to exactly this path. Do NOT write to any other location.
>
> For each file:
> 1. Run Vale linting once (use the `lint-with-vale` skill)
> 2. Fix obvious errors where the fix is clear and unambiguous
> 3. Run documentation review skills:
>    - Red Hat docs: docs-review-modular-docs, docs-review-content-quality
>    - IBM Style Guide: ibm-sg-audience-and-medium, ibm-sg-language-and-grammar, ibm-sg-punctuation, ibm-sg-numbers-and-measurement, ibm-sg-structure-and-format, ibm-sg-references, ibm-sg-technical-elements, ibm-sg-legal-information
>    - Red Hat SSG: rh-ssg-grammar-and-language, rh-ssg-formatting, rh-ssg-structure, rh-ssg-technical-examples, rh-ssg-gui-and-links, rh-ssg-legal-and-support, rh-ssg-accessibility, rh-ssg-release-notes (if applicable)
> 4. Skip ambiguous issues requiring broader context

**Prompt for MkDocs** (`--format mkdocs`):

> Review the Material for MkDocs Markdown documentation drafts for ticket `<TICKET>`.
>
> <SOURCE_FILES_BLOCK>
>
> **Report output**: `<OUTPUT_FILE>` — you MUST save the review report to exactly this path. Do NOT write to any other location.
>
> For each file:
> 1. Run Vale linting once (use the `lint-with-vale` skill)
> 2. Fix obvious errors where the fix is clear and unambiguous
> 3. Run documentation review skills:
>    - Content quality: docs-review-content-quality
>    - IBM Style Guide: ibm-sg-audience-and-medium, ibm-sg-language-and-grammar, ibm-sg-punctuation, ibm-sg-numbers-and-measurement, ibm-sg-structure-and-format, ibm-sg-references, ibm-sg-technical-elements, ibm-sg-legal-information
>    - Red Hat SSG: rh-ssg-grammar-and-language, rh-ssg-formatting, rh-ssg-structure, rh-ssg-technical-examples, rh-ssg-gui-and-links, rh-ssg-legal-and-support, rh-ssg-accessibility
> 4. Skip ambiguous issues requiring broader context

Note: MkDocs review omits `docs-review-modular-docs` (AsciiDoc-specific) and `rh-ssg-release-notes`.

### 4. Verify output

After the agent completes, verify the review report exists at `<OUTPUT_FILE>`.

### 5. Write step-result.json

Write the sidecar to `<OUTPUT_DIR>/step-result.json`:

```json
{
  "schema_version": 1,
  "step": "style-review",
  "ticket": "<TICKET>",
  "completed_at": "<current ISO 8601 timestamp>"
}
```
