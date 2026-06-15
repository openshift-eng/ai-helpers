---
name: docs-workflow-start
description: Interactive guided setup for the docs workflow. Only invoke this skill when the user explicitly requests docs-workflow-start (e.g., /docs-workflow-start). Do NOT invoke this skill when the user requests docs-orchestrator — that skill runs directly. When invoked with no CLI switches, uses AskUserQuestion to gather configuration. Supports full workflow, individual steps with auto-resolved prerequisites, and resuming previous runs. When switches are provided, passes through directly to docs-orchestrator.
argument-hint: "[<ticket>] [--workflow <name>] [--pr <url>...] [--source-code-repo <url-or-path>...] [--no-source-repo] [--auto-discover-repos] [--max-secondary-repos <N>] [--mkdocs] [--draft] [--docs-repo-path <path>] [--create-jira <PROJECT>]"
allowed-tools: Read, Write, Glob, Grep, Bash, Skill, AskUserQuestion
---

# Docs Workflow Start

Interactive entry point for the documentation workflow.

## Parse arguments

Same argument set as docs-orchestrator:

- `$1` — JIRA ticket ID (optional at this stage)
- `--workflow <name>` — Use `.agent_workspace/docs-<name>.yaml` instead of `docs-workflow.yaml`. Allows running alternative pipelines (e.g., writing-only, review-only). If the project-level file does not exist, fall back to the matching plugin default at `skills/docs-orchestrator/defaults/docs-<name>.yaml`
- `--pr <url>...` — PR/MR URLs (space-delimited, one or more). Accepts GitHub PRs (`gh` CLI) and GitLab MRs (`glab` CLI). Used both as requirements input (agent reads diffs/descriptions) and for source repo resolution (repo URL and branch derived from the first PR/MR). When multiple PRs from different repos are provided, all repos are resolved and treated equally as source material
- `--mkdocs` — Use Material for MkDocs format instead of AsciiDoc. Propagates to the writing step (generates `.md` with MkDocs front matter) and style-review step (applies Markdown-appropriate rules). Sets `options.format` to `"mkdocs"` in the progress file
- `--draft` — Write documentation to the staging area (`.agent_workspace/<ticket>/writing/`) instead of directly into the repo. Uses DRAFT placement mode: no framework detection, no file placement into the target repo. Without this flag, UPDATE-IN-PLACE is the default
- `--docs-repo-path <path>` — Target documentation repository for UPDATE-IN-PLACE mode. The docs-writer explores this directory for framework detection (Antora, MkDocs, Docusaurus, etc.) and writes files there instead of the current working directory. Propagates to `writing` and `create-merge-request` steps (mapped to their internal `--repo-path` flag). **Precedence**: if both `--docs-repo-path` and `--draft` are passed, `--docs-repo-path` wins — log a warning and ignore `--draft`
- `--source-code-repo <url-or-path>...` — Source code repository/repositories for code analysis and requirements enrichment (space-delimited, one or more). Accepts remote URLs (https://, git@, ssh:// — each shallow-cloned to `.agent_workspace/<ticket>/code-repo/<repo_name>/`) or local paths (used directly). The first repo is treated as primary; additional repos are returned as `additional_repos` in the result. Passed to requirements, code-analysis, and writing steps (mapped to their internal `--repo` flag). Without `--pr`, the entire repo is the subject matter; with `--pr`, the PR branch is checked out on the primary repo so code-analysis reflects the PR's state. Takes highest priority in source resolution, overriding `source.yaml` and PR-derived URLs
- `--create-merge-request` — Create a branch, commit, push, and open a merge request or pull request after reviews complete. Activates the `create-merge-request` workflow step (guarded by `when: create_merge_request`). Off by default
- `--no-source-repo` — Skip source repo resolution and all source-dependent steps (scope-req-audit). The workflow runs without source grounding. Use for tickets with no associated source code repository, or pass on resume after the workflow stops due to no repo being found
- `--auto-discover-repos` — Skip the confirmation prompt when secondary repos are discovered by scope-req-audit. Useful for CI/automation
- `--max-secondary-repos <N>` — Maximum number of secondary repos to clone after scope-req-audit (default: 3)

## Determine mode

**Pass-through mode**: If ANY `--` switches are present in the args string, invoke docs-orchestrator directly with all original arguments. Do NOT use AskUserQuestion.

```
Skill: docs-orchestrator, args: "<all original args>"
```

**Interactive mode**: If no `--` switches are present (bare invocation or just a ticket ID), go to the **Interactive mode — required steps** section below.

## Interactive mode — required steps

**STOP. You MUST follow steps 1–5 below IN ORDER. Do not skip any step. Do not invoke the orchestrator or any step skill until you reach step 5. Do not assume defaults — ask every question.**

### Step 1: Get ticket ID

If no ticket ID was provided in args, ask the user conversationally:

> What is the JIRA ticket ID? (e.g., PROJ-123)

The ticket ID is required. After obtaining it, proceed to step 2.

### Step 2: Action selection — call AskUserQuestion

You MUST call the AskUserQuestion tool now with 1 question. Do not skip this.

**What would you like to do?**

| Option | Description |
|--------|-------------|
| Run full workflow (Recommended) | Run the complete docs pipeline from requirements through to MR creation |
| Run specific step(s) | Run one or more individual workflow steps with prerequisites included automatically |
| Resume existing workflow | Continue a previously started workflow for this ticket |

Wait for the user's answer before proceeding.

- If **"Resume existing workflow"**: skip steps 3–4 and go directly to step 5 (resume path).
- If **"Run full workflow"**: proceed to step 3A.
- If **"Run specific step(s)"**: proceed to step 3B.

### Step 3A: Full workflow configuration — call AskUserQuestion

You MUST call the AskUserQuestion tool now with ALL 4 questions at once. Do not skip this.

**Q1: What output format should the documentation use?**

| Option | Description |
|--------|-------------|
| AsciiDoc (Recommended) | Standard Red Hat documentation format |
| Material for MkDocs | Markdown-based documentation format |

**Q2: Do you have source code related to this ticket?**

| Option | Description |
|--------|-------------|
| Yes — I have a PR URL | A pull request or merge request URL |
| Yes — I have a repo URL or path | A repository URL or local directory path |
| No source code | Proceed without code analysis |

**Q3: Where should the documentation be written?**

| Option | Description |
|--------|-------------|
| Current repo — update in place (Recommended) | Detect framework and write directly to the current repository |
| A different repo | Write to a specified repository path |
| Draft — staging area only | Write to staging area without modifying any repository |

**Q4: Create a linked JIRA ticket in another project?**

| Option | Description |
|--------|-------------|
| No (Recommended) | Skip JIRA ticket creation |
| Yes | Create a linked ticket in another JIRA project |

Wait for all answers before proceeding to step 4.

### Step 3B: Specific steps selection — call AskUserQuestion

You MUST call the AskUserQuestion tool now with 1 question. Set `multiSelect: true` on this question so the user can select multiple steps. Do not skip this.

**Which step(s) do you want to run?** (`multiSelect: true`)

| Option | Description |
|--------|-------------|
| requirements | Analyze JIRA ticket and extract documentation requirements |
| code-analysis | Analyze source repository with code-learner |
| writing | Write documentation from an existing plan |
| technical-review | Review existing documentation for technical accuracy |

For steps not listed (planning, style-review, create-merge-request), the user can type the step name via the "Other" option.

**Invalid step names**: If the user enters a step name via "Other" that is not recognized, the dependency resolver will report the error with a list of valid step names. Surface this error to the user and ask them to correct their selection.

After receiving the answer, determine which configuration questions are relevant:

- **Format?** — include if any of these steps are selected: writing, style-review
- **Source code?** — include if code-analysis is selected
- **Placement?** — include if any of these steps are selected: writing, create-merge-request
- **Create MR/PR?** — include if create-merge-request is selected

If any questions are relevant, call AskUserQuestion with those questions (same text and options as step 3A). If no questions are relevant, proceed to step 4.

### Step 4: Free-text follow-ups

Based on answers from step 3, collect any needed free-text inputs. Use AskUserQuestion with `textInput: true` for each value, so the user has a clear input prompt. Only ask questions that apply:

**If "Yes — I have a PR URL" was selected**:

Ask via AskUserQuestion (textInput): "Enter the first PR/MR URL:"

Then ask: "Enter another PR/MR URL, or select Done:"

| Option | Description |
|--------|-------------|
| Done | No more PR URLs |

Repeat until the user selects Done. Each URL becomes a `--pr <url>` flag.

**If "Yes — I have a repo URL or path" was selected**:

Ask via AskUserQuestion (textInput): "Enter the source repo URL or local path:"

Then ask via AskUserQuestion:

**Do you also have PR URL(s) for this repo?**

| Option | Description |
|--------|-------------|
| No (Recommended) | Proceed without PR URLs |
| Yes | Enter PR URL(s) |

`--source-code-repo` and `--pr` can coexist — the PR branch gets checked out within the repo. If the user selects Yes, collect PR URLs using the same loop as above.

**If "A different repo" was selected for placement**:

Ask via AskUserQuestion (textInput): "Enter the target docs repository path:"

Maps to `--docs-repo-path <path>`.

**If "Yes" was selected for Create JIRA**:

Ask via AskUserQuestion (textInput): "Enter the target JIRA project key (e.g., DOCS):"

Maps to `--create-jira <PROJECT>`.

If no follow-ups are needed, proceed directly to step 5.

### Step 5: Build CLI flags and execute

Build the args string from collected answers:

| Answer | CLI flag |
|--------|----------|
| Material for MkDocs | `--mkdocs` |
| PR URL(s) | `--pr <url>` (repeat for each URL) |
| Repo URL or path | `--source-code-repo <url-or-path>` |
| No source code | `--no-source-repo` |
| Auto-discover from JIRA | _(no flag — default behavior)_ |
| Draft — staging area only | `--draft` |
| Target docs repo path | `--docs-repo-path <path>` |
| Create JIRA = Yes | `--create-jira <PROJECT>` |
| `--workflow` was provided in args | `--workflow <name>` (pass through) |

AsciiDoc format and current repo placement are defaults — no flags needed.

**Precedence**: If both `--docs-repo-path` and `--draft` would be set, `--docs-repo-path` wins — log a warning and omit `--draft` (matches orchestrator behavior).

**NOW invoke the orchestrator** (or run specific steps — see below).

#### Full workflow execution

Invoke the orchestrator with the ticket ID and all constructed flags:

```
Skill: docs-orchestrator, args: "<ticket> <constructed flags>"
```

Example:

```
Skill: docs-orchestrator, args: "PROJ-123 --mkdocs --pr https://github.com/org/repo/pull/42 --draft"
```

#### Resume execution

For the resume path (user selected "Resume existing workflow" in step 2):

```
Skill: docs-orchestrator, args: "<ticket>"
```

The orchestrator detects the existing progress file and resumes automatically.

#### Specific steps execution

When running individual steps, dependencies are resolved automatically and each step skill is invoked directly.

### 1. Resolve base path

```bash
TICKET_LOWER=$(echo "<ticket>" | tr '[:upper:]' '[:lower:]')
BASE_PATH="$(cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" && pwd)/.agent_workspace/${TICKET_LOWER}"
mkdir -p "$BASE_PATH"
```

### 2. Resolve the YAML path

Determine which workflow YAML to use. If `--workflow <name>` was provided (from the parsed args), use the named variant; otherwise use the default:

```bash
if [[ -n "$WORKFLOW_NAME" && -f ".agent_workspace/docs-${WORKFLOW_NAME}.yaml" ]]; then
  YAML_PATH=".agent_workspace/docs-${WORKFLOW_NAME}.yaml"
elif [[ -f ".agent_workspace/docs-workflow.yaml" ]]; then
  YAML_PATH=".agent_workspace/docs-workflow.yaml"
else
  YAML_PATH="${CLAUDE_PLUGIN_ROOT}/skills/docs-orchestrator/defaults/docs-workflow.yaml"
fi
```

### 3. Compute execution plan

Run the dependency resolver:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/resolve_steps.py \
  --yaml "$YAML_PATH" \
  --steps <selected-step-names...> \
  --base-path "$BASE_PATH"
```

If the script exits with code 1, the user entered an invalid step name. Read the `error` field and `valid_steps` list from the JSON output and tell the user:

> Step name "\<name\>" is not recognized. Valid steps are: \<valid_steps list\>. Please try again.

Then re-ask the step selection question via AskUserQuestion.

### 4. Validate `requires` conditions

Check the `requires` field in the resolver's JSON output. If the workflow declares `requires: [has_source_repo]` and no source repo or PR URL was collected in step 3B/4, **STOP** immediately with:

> This workflow requires a source code repository. Pass `--source-code-repo <url-or-path>` or `--pr <url>`, or select a source code option when prompted.

This catches the problem before any steps run — the same early guard the orchestrator applies for full workflow mode.

### 5. Handle existing artifacts (smart hybrid confirmation)

Read the JSON output. If `steps_with_artifacts` is **non-empty**, use AskUserQuestion:

**Some prerequisite steps already have output from a previous run. Re-use existing artifacts or re-run?**

| Option | Description |
|--------|-------------|
| Re-use existing artifacts (Recommended) | Skip completed prerequisites and only run what's missing |
| Re-run all steps | Discard existing output and re-run everything from scratch |

If `steps_with_artifacts` is **empty**, skip this question and run all steps.

### 6. Evaluate `when` conditions

For each step in the execution plan with a `when` field:

- `when: has_source_repo` — skip this step if no source repo or PR URL was provided. Log: "Skipping \<step\>: no source repository configured."
- `when: create_merge_request` — skip this step if create-merge-request was not selected. Log: "Skipping \<step\>: merge request creation not requested."

### 7. Run steps sequentially

For each step in `execution_plan` order:

1. If `has_artifacts: true` AND user chose "Re-use existing artifacts" → skip with message: "Skipping \<step\>: using existing artifacts at \<base-path\>/\<step\>/"
2. If `when` condition is not met → skip with message (see above)
3. Otherwise, construct the args and invoke:

```
Skill: <step.skill>, args: "<ticket> --base-path <BASE_PATH> <step-specific-flags>"
```

**Step-specific flags** — each step gets `<ticket> --base-path <BASE_PATH>` plus:

| Step | Additional flags from collected config |
|------|---------------------------------------|
| requirements | `[--pr <url>]... [--repo <repo_path>]` |
| planning | _(none)_ |
| code-analysis | `--repo <repo_path>` |
| writing | `--format <adoc\|mkdocs> [--draft] [--repo <repo_path>] [--repo-path <path>]` |
| style-review | `--format <adoc\|mkdocs>` |
| technical-review | _(none)_ |
| create-merge-request | `[--draft] [--repo-path <path>]` |

The format flag defaults to `adoc` unless the user selected Material for MkDocs.

### 8. Verify and report

After each step completes:

1. Check the step's output directory exists at `<BASE_PATH>/<step-name>/`
2. If missing, report the failure: "Step \<step\> failed — expected output at \<path\> not found." **STOP** — do not continue to subsequent steps.
3. If present, report success: "Step \<step\> completed. Output: \<path\>"

After all steps complete, display a summary:

> **Completed steps:**
> - requirements: .agent_workspace/proj-123/requirements/
> - planning: .agent_workspace/proj-123/planning/
> - writing: .agent_workspace/proj-123/writing/
>
> **Skipped steps:**
> - code-analysis: no source repository configured
