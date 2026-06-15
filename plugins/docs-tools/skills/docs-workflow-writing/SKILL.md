---
name: docs-workflow-writing
description: Write documentation from a documentation plan. Dispatches the docs-writer agent. Supports AsciiDoc (default) and MkDocs formats. Default placement is UPDATE-IN-PLACE; use --draft for staging area. Also supports fix mode for applying technical review corrections.
argument-hint: <ticket> --base-path <path> --format <adoc|mkdocs> [--draft] [--repo <path>]... [--repo-path <path>] [--fix-from <review_path>]
allowed-tools: Read, Write, Glob, Grep, Edit, Bash, Skill, Agent
---

# Documentation Writing Step

Step skill for the docs-orchestrator pipeline. Follows the step skill contract: **run script → dispatch agent → verify output**.

## Execution

### 1. Run the script

Run the build script to parse arguments, validate inputs, determine mode, and create output directories:

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/build_writing_args.sh <args>
```

Pass through the full args string. The script emits JSON on stdout:

```json
{
  "mode":                "update-in-place | draft | fix",
  "ticket":              "PROJ-123",
  "format":              "adoc | mkdocs",
  "input_file":          "<base-path>/planning/plan.md",
  "code_analysis_dir":   "<base-path>/code-analysis/ | null",
  "has_code_analysis":   true | false,
  "pr_analysis_dir":     "<base-path>/pr-analysis/ | null",
  "has_pr_analysis":     true | false,
  "output_dir":          "<base-path>/writing",
  "output_file":         "<base-path>/writing/_index.md",
  "docs_repo_path":      "<path> | null",
  "source_repo_path":    "<path> | null",
  "additional_repo_paths": ["<path>", ...],
  "additional_code_analysis_dirs": ["<path>", ...],
  "fix_from":            "<path> | null",
  "verify_output":       true | false
}
```

If the script exits non-zero, stop and report the error from stderr.

### 2. Dispatch the docs-writer agent

**You MUST use the Agent tool** to invoke the `docs-writer` subagent. Do NOT read the agent's markdown file or attempt to perform the agent's work yourself — the agent has a specialized system prompt and must run as an isolated subagent.

Select the prompt based on `mode` and `format` from the JSON output. In every prompt below, substitute the `<TICKET>`, `<INPUT_FILE>`, `<OUTPUT_FILE>`, `<OUTPUT_DIR>`, `<DOCS_REPO_PATH>`, `<FIX_FROM>`, `<CODE_ANALYSIS_DIR>`, `<PR_ANALYSIS_DIR>`, `<SOURCE_REPO>`, `<ADDITIONAL_REPO_PATHS>`, and `<ADDITIONAL_CODE_ANALYSIS_DIRS>` placeholders with the corresponding values from the script's JSON.

**Agent tool parameters for all modes:**
- `subagent_type`: `docs-tools:docs-writer`
- `description`: use the value described under each mode below

---

#### Mode: `update-in-place`, format: `adoc`

**Description:** `Write adoc documentation for <TICKET>`

**Prompt:**

> Write complete AsciiDoc documentation based on the documentation plan for ticket `<TICKET>`.
>
> Read the plan from: `<INPUT_FILE>`
>
> **[Include only if HAS_CODE_ANALYSIS=true]** Code-learner analysis is available at `<CODE_ANALYSIS_DIR>`. Read `ONBOARDING.md` for architecture overview and module relationships. Read relevant module summaries from `summaries/` for accurate function signatures (`public_api`), dependencies, and data flow patterns. Prefer analysis over assumptions — if the analysis contradicts the plan, follow the analysis.
>
> Use the module registry (`registry.json`) to understand module priority:
> - **read-first** modules: write with full technical detail using the module's summary data
> - **read-second** modules: write concise coverage, focusing on key APIs and purpose
> - **skip** modules: do not write standalone content — mention only if relevant to a documented module
>
> **[Include only if HAS_PR_ANALYSIS=true]** PR analysis is available at `<PR_ANALYSIS_DIR>`. Read `PR-*-ANALYSIS.md` for change-specific context — what code was modified, why, and what impact it has. Use this to ensure documentation accurately reflects the current state of the code after the PR changes.
>
> **[Include only if SOURCE_REPO is not null]** Source code repository is available at `<SOURCE_REPO>`. You may read specific source files for additional detail when the analysis data does not contain sufficient information for a section. Use this to verify function signatures, check parameter types, or find code examples — do not browse the entire repo.
>
> **[Include only if ADDITIONAL_REPO_PATHS is non-empty]** Additional source code repositories are available at: <list each path from ADDITIONAL_REPO_PATHS>. For each additional repo with a code-learner analysis directory in `<ADDITIONAL_CODE_ANALYSIS_DIRS>`, read its `ONBOARDING.md` for architecture overview. Use these for cross-repo context when features span multiple repositories.
>
> **IMPORTANT**: Write COMPLETE .adoc files, not summaries or outlines.
>
> **Placement mode: UPDATE-IN-PLACE**
>
> [If `docs_repo_path` is not null: "The target repository is at `<DOCS_REPO_PATH>`. Explore **that directory** for framework detection and write files there."]
>
> Place files directly in the repository following existing conventions. Before writing any files:
> 1. Detect the repository's documentation build framework (Antora, ccutil, Sphinx, etc.)
> 2. Analyze existing file naming conventions, directory layout, include patterns, and nav/TOC structure
> 3. Determine the correct target path for each module based on the detected framework and conventions
>
> Write modules and assemblies directly to their correct repo locations. Update navigation/TOC files as needed, following existing patterns.
>
> Create a manifest at `<OUTPUT_FILE>` listing **all files written and modified** with **absolute paths**. The manifest must include every intentional change — both new files created and existing files modified (e.g., nav/TOC updates).
>
> [If `docs_repo_path` is not null: "Record `Target repo: <DOCS_REPO_PATH>` in the manifest header."]

---

#### Mode: `update-in-place`, format: `mkdocs`

**Description:** `Write mkdocs documentation for <TICKET>`

**Prompt:**

> Write complete Material for MkDocs Markdown documentation based on the documentation plan for ticket `<TICKET>`.
>
> Read the plan from: `<INPUT_FILE>`
>
> **[Include only if HAS_CODE_ANALYSIS=true]** Code-learner analysis is available at `<CODE_ANALYSIS_DIR>`. Read `ONBOARDING.md` for architecture overview and module relationships. Read relevant module summaries from `summaries/` for accurate function signatures (`public_api`), dependencies, and data flow patterns. Prefer analysis over assumptions — if the analysis contradicts the plan, follow the analysis.
>
> Use the module registry (`registry.json`) to understand module priority:
> - **read-first** modules: write with full technical detail using the module's summary data
> - **read-second** modules: write concise coverage, focusing on key APIs and purpose
> - **skip** modules: do not write standalone content — mention only if relevant to a documented module
>
> **[Include only if HAS_PR_ANALYSIS=true]** PR analysis is available at `<PR_ANALYSIS_DIR>`. Read `PR-*-ANALYSIS.md` for change-specific context — what code was modified, why, and what impact it has. Use this to ensure documentation accurately reflects the current state of the code after the PR changes.
>
> **[Include only if SOURCE_REPO is not null]** Source code repository is available at `<SOURCE_REPO>`. You may read specific source files for additional detail when the analysis data does not contain sufficient information for a section. Use this to verify function signatures, check parameter types, or find code examples — do not browse the entire repo.
>
> **[Include only if ADDITIONAL_REPO_PATHS is non-empty]** Additional source code repositories are available at: <list each path from ADDITIONAL_REPO_PATHS>. For each additional repo with a code-learner analysis directory in `<ADDITIONAL_CODE_ANALYSIS_DIRS>`, read its `ONBOARDING.md` for architecture overview. Use these for cross-repo context when features span multiple repositories.
>
> **IMPORTANT**: Write COMPLETE .md files with YAML frontmatter (title, description). Use Material for MkDocs conventions: admonitions, content tabs, code blocks with titles, heading hierarchy starting at `# h1`.
>
> **Placement mode: UPDATE-IN-PLACE**
>
> [If `docs_repo_path` is not null: "The target repository is at `<DOCS_REPO_PATH>`. Explore **that directory** for framework detection and write files there."]
>
> Place files directly in the repository following existing conventions. Before writing any files:
> 1. Detect the repository's documentation build framework (MkDocs, Docusaurus, Hugo, etc.)
> 2. Analyze existing file naming conventions, directory layout, and nav structure
> 3. Determine the correct target path for each page based on the detected framework and conventions
>
> Write pages directly to their correct repo locations. Update `mkdocs.yml` nav section or equivalent as needed, following existing patterns.
>
> Create a manifest at `<OUTPUT_FILE>` listing **all files written and modified** with **absolute paths**. The manifest must include every intentional change — both new files created and existing files modified (e.g., `mkdocs.yml` nav updates).
>
> [If `docs_repo_path` is not null: "Record `Target repo: <DOCS_REPO_PATH>` in the manifest header."]

---

#### Mode: `draft`, format: `adoc`

**Description:** `Write adoc documentation for <TICKET>`

**Prompt:**

> Write complete AsciiDoc documentation based on the documentation plan for ticket `<TICKET>`.
>
> Read the plan from: `<INPUT_FILE>`
>
> **[Include only if HAS_CODE_ANALYSIS=true]** Code-learner analysis is available at `<CODE_ANALYSIS_DIR>`. Read `ONBOARDING.md` for architecture overview and module relationships. Read relevant module summaries from `summaries/` for accurate function signatures (`public_api`), dependencies, and data flow patterns. Prefer analysis over assumptions — if the analysis contradicts the plan, follow the analysis.
>
> Use the module registry (`registry.json`) to understand module priority:
> - **read-first** modules: write with full technical detail using the module's summary data
> - **read-second** modules: write concise coverage, focusing on key APIs and purpose
> - **skip** modules: do not write standalone content — mention only if relevant to a documented module
>
> **[Include only if HAS_PR_ANALYSIS=true]** PR analysis is available at `<PR_ANALYSIS_DIR>`. Read `PR-*-ANALYSIS.md` for change-specific context — what code was modified, why, and what impact it has. Use this to ensure documentation accurately reflects the current state of the code after the PR changes.
>
> **[Include only if SOURCE_REPO is not null]** Source code repository is available at `<SOURCE_REPO>`. You may read specific source files for additional detail when the analysis data does not contain sufficient information for a section. Use this to verify function signatures, check parameter types, or find code examples — do not browse the entire repo.
>
> **[Include only if ADDITIONAL_REPO_PATHS is non-empty]** Additional source code repositories are available at: <list each path from ADDITIONAL_REPO_PATHS>. For each additional repo with a code-learner analysis directory in `<ADDITIONAL_CODE_ANALYSIS_DIRS>`, read its `ONBOARDING.md` for architecture overview. Use these for cross-repo context when features span multiple repositories.
>
> **IMPORTANT**: Write COMPLETE .adoc files, not summaries or outlines.
>
> **Placement mode: DRAFT (staging area)**
>
> Save files to the staging area. Do not modify any existing repository files.
>
> Output folder structure:
> ```
> <OUTPUT_DIR>/
> ├── _index.md                     # Index of all modules
> ├── assembly_<name>.adoc          # Assembly files at root
> └── modules/                      # All module files
>     ├── <concept-name>.adoc
>     ├── <procedure-name>.adoc
>     └── <reference-name>.adoc
> ```
>
> Save modules to: `<OUTPUT_DIR>/modules/`
> Save assemblies to: `<OUTPUT_DIR>/`
> Create index at: `<OUTPUT_FILE>`

---

#### Mode: `draft`, format: `mkdocs`

**Description:** `Write mkdocs documentation for <TICKET>`

**Prompt:**

> Write complete Material for MkDocs Markdown documentation based on the documentation plan for ticket `<TICKET>`.
>
> Read the plan from: `<INPUT_FILE>`
>
> **[Include only if HAS_CODE_ANALYSIS=true]** Code-learner analysis is available at `<CODE_ANALYSIS_DIR>`. Read `ONBOARDING.md` for architecture overview and module relationships. Read relevant module summaries from `summaries/` for accurate function signatures (`public_api`), dependencies, and data flow patterns. Prefer analysis over assumptions — if the analysis contradicts the plan, follow the analysis.
>
> Use the module registry (`registry.json`) to understand module priority:
> - **read-first** modules: write with full technical detail using the module's summary data
> - **read-second** modules: write concise coverage, focusing on key APIs and purpose
> - **skip** modules: do not write standalone content — mention only if relevant to a documented module
>
> **[Include only if HAS_PR_ANALYSIS=true]** PR analysis is available at `<PR_ANALYSIS_DIR>`. Read `PR-*-ANALYSIS.md` for change-specific context — what code was modified, why, and what impact it has. Use this to ensure documentation accurately reflects the current state of the code after the PR changes.
>
> **[Include only if SOURCE_REPO is not null]** Source code repository is available at `<SOURCE_REPO>`. You may read specific source files for additional detail when the analysis data does not contain sufficient information for a section. Use this to verify function signatures, check parameter types, or find code examples — do not browse the entire repo.
>
> **[Include only if ADDITIONAL_REPO_PATHS is non-empty]** Additional source code repositories are available at: <list each path from ADDITIONAL_REPO_PATHS>. For each additional repo with a code-learner analysis directory in `<ADDITIONAL_CODE_ANALYSIS_DIRS>`, read its `ONBOARDING.md` for architecture overview. Use these for cross-repo context when features span multiple repositories.
>
> **IMPORTANT**: Write COMPLETE .md files with YAML frontmatter (title, description). Use Material for MkDocs conventions: admonitions, content tabs, code blocks with titles, heading hierarchy starting at `# h1`.
>
> **Placement mode: DRAFT (staging area)**
>
> Save files to the staging area. Do not modify any existing repository files.
>
> Output folder structure:
> ```
> <OUTPUT_DIR>/
> ├── _index.md                     # Index of all pages
> ├── mkdocs-nav.yml                # Suggested nav tree fragment
> └── docs/                         # All page files
>     ├── <concept-name>.md
>     ├── <procedure-name>.md
>     └── <reference-name>.md
> ```
>
> Save pages to: `<OUTPUT_DIR>/docs/`
> Create nav fragment at: `<OUTPUT_DIR>/mkdocs-nav.yml`
> Create index at: `<OUTPUT_FILE>`

---

#### Mode: `fix`

**Description:** `Fix documentation for <TICKET>`

**Prompt:**

> Apply fixes to documentation drafts based on technical review feedback for ticket `<TICKET>`.
>
> Read the review report from: `<FIX_FROM>`
>
> **[Include only if `<BASE_PATH>/technical-review/issues.json` exists]** Structured issue list is available at: `<BASE_PATH>/technical-review/issues.json`. This file provides the canonical issue IDs and severity classifications for tracking in the manifest below. The review report (`<FIX_FROM>`) provides the full context, descriptions, and suggestions for applying each fix. When details differ between the two sources, prefer the review report for fix content and use `issues.json` only for issue IDs and severity.
>
> Drafts location: `<OUTPUT_DIR>/`
>
> For each issue flagged in the review:
> 1. If the fix is clear and unambiguous, apply it directly
> 2. If the issue requires broader context or judgment, skip it
> 3. Do NOT rewrite content that was not flagged
>
> Edit files in place. Do NOT create copies or new files (except the fix manifest below).
>
> **[Include only if SOURCE_REPO is not null]** Source code repository is available at `<SOURCE_REPO>`. You may read specific source files to verify fixes and resolve ambiguous review findings.
>
> **[Include only if ADDITIONAL_REPO_PATHS is non-empty]** Additional source code repositories are available at: <list each path from ADDITIONAL_REPO_PATHS>. Use these for cross-repo verification of review findings.
>
> After applying all fixes, write a fix manifest to: `<OUTPUT_DIR>/fix-manifest.json`
>
> The manifest must contain one entry per issue. Use issue IDs from `issues.json` if available; otherwise create synthetic IDs from the review sections (`review-critical-1`, `review-significant-1`, etc.).
>
> ```json
> {
>   "schema_version": 1,
>   "ticket": "<TICKET>",
>   "fixed_at": "<ISO 8601>",
>   "fixes": [
>     {
>       "issue_id": "issue-1",
>       "action": "fixed",
>       "description": "Added -n <namespace> flag to the oc apply command on line 42",
>       "file": "proc-installing-operator.adoc",
>       "lines_changed": "42"
>     },
>     {
>       "issue_id": "issue-3",
>       "action": "skipped",
>       "description": "Requires SME input to confirm the default timeout value",
>       "file": null,
>       "lines_changed": null
>     }
>   ],
>   "summary": {
>     "fixed": 4,
>     "skipped": 2,
>     "partial": 0,
>     "total": 6
>   }
> }
> ```
>
> Valid `action` values: `"fixed"` (change applied), `"skipped"` (requires judgment or SME input), `"partial"` (partially addressed, needs verification).

In fix mode, the skill does not create new modules or restructure content.

---

### 3. Verify output

If `verify_output` is `true` in the script's JSON output, check that `output_file` exists.

If `verify_output` is `false` (fix mode), no verification is needed — files are edited in place.

### 4. Write step-result.json

If `mode` is `"fix"`, skip writing `step-result.json` (fixes edit files in place — no new manifest to parse). However, verify that `fix-manifest.json` was written to `<OUTPUT_DIR>/fix-manifest.json`. If it was not written, log a warning: `"Fix agent did not produce fix-manifest.json — the orchestrator will treat all issues as unverified."` Then skip the rest of this step.

Read the manifest at `<OUTPUT_FILE>` (`_index.md`). Extract every absolute file path from the table rows. These become the `files` array.

Write the sidecar to `<OUTPUT_DIR>/step-result.json` using the `mode` and `format` values from the script's JSON output:

```json
{
  "schema_version": 1,
  "step": "writing",
  "ticket": "<TICKET>",
  "completed_at": "<current ISO 8601 timestamp>",
  "files": [
    "/absolute/path/to/file1.adoc",
    "/absolute/path/to/file2.adoc"
  ],
  "mode": "<mode from script JSON>",
  "format": "<format from script JSON>"
}
```
