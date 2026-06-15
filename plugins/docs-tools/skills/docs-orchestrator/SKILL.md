---
name: docs-orchestrator
description: Documentation workflow orchestrator. Reads the step list from .agent_workspace/docs-workflow.yaml (or the plugin default). Runs steps sequentially, manages progress state, handles iteration and confirmation gates. Claude is the orchestrator — the YAML is a step list, not a workflow engine.

argument-hint: <ticket> [--workflow <name>] [--pr <url>...] [--source-code-repo <url-or-path>...] [--no-source-repo] [--auto-discover-repos] [--max-secondary-repos <N>] [--mkdocs] [--draft] [--docs-repo-path <path>] [--create-jira <PROJECT>] [--create-merge-request]

allowed-tools: Read, Write, Glob, Grep, Edit, Bash, Skill, AskUserQuestion
---

# Docs Orchestrator

**When the user invokes `/docs-orchestrator` or `/docs-tools:docs-orchestrator`, run THIS skill directly. Do NOT redirect to `docs-workflow-start` or any other skill.**

Claude is the orchestrator. The YAML is a step list. The hook is a safety net.

This skill teaches you how to run a documentation workflow pipeline. You read the step list from YAML, run each step skill sequentially, manage progress state via a JSON file, and handle iteration loops and confirmation gates.

## Pre-flight

Install the workflow completion Stop hook (safe to re-run, skips if already installed):

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/setup-hooks.sh
```

**Do not** source `.env` files or check for tokens/CLIs here — Python scripts (`jira_reader.py`, `resolve_source.py`, etc.) load `.env` files and validate prerequisites themselves, producing clear errors on failure.

## Parse arguments

When displaying available options to the user (e.g., on skill load or when asking for flags), reproduce the descriptions below **verbatim** — do not summarize or paraphrase them.

- `$1` — JIRA ticket ID (required). If missing, STOP and ask the user.
- `--workflow <name>` — Use `.agent_workspace/docs-<name>.yaml` instead of `docs-workflow.yaml`. Allows running alternative pipelines (e.g., writing-only, review-only). If the project-level file does not exist, fall back to the matching plugin default at `skills/docs-orchestrator/defaults/docs-<name>.yaml`
- `--pr <url>...` — PR/MR URLs (space-delimited, one or more). Accepts GitHub PRs (`gh` CLI) and GitLab MRs (`glab` CLI). Used both as requirements input (agent reads diffs/descriptions) and for source repo resolution (repo URL and branch derived from the first PR/MR). When multiple PRs from different repos are provided, all repos are resolved and treated equally as source material
- `--mkdocs` — Use Material for MkDocs format instead of AsciiDoc. Propagates to the writing step (generates `.md` with MkDocs front matter) and style-review step (applies Markdown-appropriate rules). Sets `options.format` to `"mkdocs"` in the progress file
- `--draft` — Write documentation to the staging area (`.agent_workspace/<ticket>/writing/`) instead of directly into the repo. Uses DRAFT placement mode: no framework detection, no file placement into the target repo. Without this flag, UPDATE-IN-PLACE is the default
- `--docs-repo-path <path>` — Target documentation repository for UPDATE-IN-PLACE mode. The docs-writer explores this directory for framework detection (Antora, MkDocs, Docusaurus, etc.) and writes files there instead of the current working directory. Propagates to `writing` and `create-merge-request` steps (mapped to their internal `--repo-path` flag). **Precedence**: if both `--docs-repo-path` and `--draft` are passed, `--docs-repo-path` wins — log a warning and ignore `--draft`
- `--source-code-repo <url-or-path>...` — Source code repository/repositories for code analysis and requirements enrichment (space-delimited, one or more). Accepts remote URLs (https://, git@, ssh:// — each shallow-cloned to `.agent_workspace/<ticket>/code-repo/<repo_name>/`) or local paths (used directly). The first repo is treated as primary; additional repos are returned as `additional_repos` in the result. Passed to requirements, code-analysis, writing, and technical-review steps (mapped to their internal `--repo` flag). Without `--pr`, the entire repo is the subject matter; with `--pr`, the PR branch is checked out on the primary repo so code-analysis reflects the PR's state. Takes highest priority in source resolution, overriding `source.yaml` and PR-derived URLs
- `--create-jira <PROJECT>` — Create a linked JIRA ticket in the specified project after the planning step completes. Runs the standalone `docs-workflow-create-jira` workflow (use `--workflow workflow-create-jira`). Requires `JIRA_API_TOKEN` to be set
- `--create-merge-request` — Create a branch, commit, push, and open a merge request or pull request after reviews complete. Activates the `create-merge-request` workflow step (guarded by `when: create_merge_request`). Off by default
- `--no-source-repo` — Skip source repo resolution and all source-dependent steps (scope-req-audit). The workflow runs without source grounding. Use for tickets with no associated source code repository, or pass on resume after the workflow stops due to no repo being found
- `--auto-discover-repos` — Skip the confirmation prompt when secondary repos are discovered by scope-req-audit. Useful for CI/automation where interactive prompts are not available. Has no effect if no secondary repos are found
- `--max-secondary-repos <N>` — Maximum number of secondary repos to clone after scope-req-audit (default: 3). Repos are ranked by the number of associated requirements

### Examples

```bash
# Minimal — just a ticket
/docs-orchestrator PROJ-123

# PR-driven with MkDocs output
/docs-orchestrator PROJ-123 --pr https://github.com/org/repo/pull/42 --mkdocs

# Multiple PRs from different repos, written to a separate docs repo
/docs-orchestrator PROJ-123 \
  --pr https://github.com/org/backend/pull/10 https://gitlab.example.com/org/frontend/-/merge_requests/5 \
  --docs-repo-path /home/user/docs-repo

# Source repo without PRs, draft mode, with merge request creation
/docs-orchestrator PROJ-123 \
  --source-code-repo https://github.com/org/operator \
  --draft \
  --create-merge-request

# Local source repo + PR (checks out PR branch within repo)
/docs-orchestrator PROJ-123 \
  --source-code-repo /home/user/local-checkout \
  --pr https://github.com/org/repo/pull/99

# Custom workflow YAML
/docs-orchestrator PROJ-123 --workflow quick
```

## Resolve source repository

After parsing arguments and before running steps, resolve the source code repository if one is configured. This makes the repo available to all downstream steps that need it (requirements, code-analysis, writing).

All clone, verify, PR-resolution, and source.yaml logic is handled by the `resolve_source.py` script. The orchestrator calls the script and acts on the JSON result.

### Pre-flight resolution

Run the script with whatever source information is available from CLI args:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/resolve_source.py \
  --base-path <base_path> \
  [--repo <url-or-path>...] \
  [--pr <url>...]
```

The script checks sources in priority order:

1. **CLI `--source-code-repo` flag** — clone or verify the path
2. **Per-ticket `source.yaml`** — read and apply existing config
3. **PR-derived** — resolve repo URL and branch from `--pr` via `gh pr view` or `glab mr view`
4. **`discovered_repos.json`** — read repos discovered by the requirements step (from JIRA graph walk)
5. **No source** — exit code 2, defer resolution until after requirements

The script outputs JSON to stdout:

```json
{
  "status": "resolved",
  "repo_path": ".agent_workspace/proj-123/code-repo/operator",
  "repo_url": "https://github.com/org/operator",
  "ref": "pr-branch-name",
  "scope": null
}
```

### Handle the result

| Exit code | `status` | Action |
|---|---|---|
| 0 | `resolved` | Set `has_source_repo = true`. Record `options.source` in the progress file from the JSON fields (`repo_path`, `repo_url`, `ref`, `scope`) |
| 1 | `error` | **STOP** with the error `message` from the JSON |
| 2 | `no_source` | Mark steps with `when: has_source_repo` as `deferred`. Source resolution will be retried after requirements (see [Post-requirements source resolution](#post-requirements-source-resolution)) |

If `discovered_repos` is present in the result (multiple repos found), log all resolved repos. If `additional_repos` is present, record them in the progress file alongside the primary source. If `warnings` is present, log each warning.

### Per-ticket source config schema

Writers can create `<base-path>/source.yaml` before starting a workflow to pre-configure the source repo and scope. The script also writes this file after a successful clone so that resume picks it up automatically.

```yaml
# .agent_workspace/<ticket>/source.yaml
repo: https://github.com/org/operator   # URL or local path (required)
ref: main                                # branch, tag, or commit (default: HEAD)
scope:
  include:                               # glob patterns — what to index and search
    - "src/controllers/**"
    - "pkg/api/v1/**"
    - "README.md"
  exclude:                               # glob patterns — what to skip
    - "**/vendor/**"
    - "**/testdata/**"
    - "**/*_test.go"
```

All fields except `repo` are optional. If `scope` is omitted, the entire repository is in scope.

## Load the step list

### 1. Determine the YAML file

- If `--workflow <name>` was specified → `.agent_workspace/docs-<name>.yaml`
- If that project-level file doesn't exist → fall back to `skills/docs-orchestrator/defaults/docs-<name>.yaml`
- Otherwise → `.agent_workspace/docs-workflow.yaml`
- If that project-level file doesn't exist → fall back to `skills/docs-orchestrator/defaults/docs-workflow.yaml`

### 2. Read the YAML

Read the YAML file and extract the ordered step list. Each step has: `name`, `skill`, `description`, optional `when`, and optional `inputs`.

### 3. Evaluate `when` conditions

- `when: create_merge_request` → run this step only if `--create-merge-request` was passed
- `when: has_pr` → run this step only if a PR/MR URL is available (passed via `--pr` or discovered from JIRA by the requirements step). Evaluated after source resolution completes — if a PR URL was resolved from `options.source` or `options.pr_urls`, the condition is met
- `when: has_source_repo` → evaluation depends on timing:
  - If `--no-source-repo` was passed → mark as `skipped` immediately (source resolution was skipped entirely)
  - If a source repo was already resolved pre-flight (via `--source-code-repo`, `--pr`, or `source.yaml`) → step runs normally (`pending`)
  - If no source is resolved yet but post-requirements discovery is possible (case 4 above) → mark the step `deferred` (not `skipped`). The orchestrator re-evaluates after requirements completes
  - After post-requirements resolution: `deferred` steps become `pending` (source found) or the workflow stops (see [No source found](#3-no-source-found))
- Steps with no `when` always run
- Steps that don't meet their `when` condition and cannot be deferred are marked `skipped` in the progress file

### 4. Validate the step list

All of the following must be true. If any check fails, **STOP** with a clear error:

- All step names are unique
- All `skill` references resolve to a known skill (bare names like `docs-workflow-writing` are preferred; fully qualified `plugin:skill` format is also accepted)
- Input dependencies are satisfied — for each step with `inputs`, every referenced step name must be present in the step list (unless it has a `when` condition that would skip it)

### Input dependencies

Steps declare their inputs as a list of upstream step names in the YAML:

```yaml
- name: writing
  skill: docs-workflow-writing
  inputs: [planning]

- name: create-merge-request
  skill: docs-tools:docs-workflow-create-merge-request
  when: create_merge_request
  inputs: [writing, style-review, technical-review]
```

The orchestrator validates at load time that every step name in `inputs` exists in the step list. Step skills read their input data from the upstream step's output folder by convention (see below).

**Conditional input dependencies**: If an upstream step in `inputs` has a `when` condition and was `skipped`, that dependency is considered satisfied. The downstream step is responsible for checking whether the optional input data actually exists (e.g., the writing step checks for `code-analysis/ONBOARDING.md` and uses it if present, but proceeds without it). Only upstream steps that ran and `failed` block downstream execution.

**Custom workflow validation**: If a step's `inputs` references a step that does not exist in the current YAML step list, fail at load time with an error (e.g., "Step 'writing' requires 'planning', but 'planning' is not in the step list").

## Output conventions

Every step writes to a predictable folder based on the ticket ID and step name:

```
.agent_workspace/<ticket>/<step-name>/
```

The ticket ID is converted to **lowercase** for directory names (e.g., `PROJ-123` → `proj-123`).

### Resolve base path

Resolve the base path to an absolute path so agents (which may run in a different working directory) can locate files correctly:

```bash
BASE_PATH="$(cd "$(git rev-parse --show-toplevel)" && pwd)/.agent_workspace/${TICKET_LOWER}"
```

Use this absolute `BASE_PATH` for the progress file's `base_path` field and for all `--base-path` arguments passed to step skills.

### Folder structure

```
.agent_workspace/proj-123/
  source.yaml                        (per-ticket source config, if applicable)
  code-repo/
    <repo-name>/                     (each repo gets its own subdirectory)
  requirements/
    requirements.md
    step-result.json                 (sidecar: title)
  code-analysis/                       (if source repo is available)
    ONBOARDING.md
    registry.json
    detection.json
    summaries/
    relationships/
    step-result.json                 (sidecar: module_count, relationship_count, languages_detected, repo_path)
  code-analysis-<repo-name>/           (additional repos, if any — same structure as code-analysis/)
    ONBOARDING.md
    registry.json
    detection.json
    summaries/
    relationships/
    step-result.json
  pr-analysis/                         (if PR is available)
    PR-<number>-ANALYSIS.md
    step-result.json                 (sidecar: pr_number, pr_url, modules_affected, platform)
  planning/
    plan.md
    step-result.json                 (sidecar: module_count)
  writing/
    _index.md
    fix-manifest.json                (written by fix agent, maps issue IDs to actions)
    step-result.json                 (sidecar: files, mode, format)
    assembly_*.adoc (or docs/*.md for mkdocs)
    modules/
  technical-review/
    review.md
    issues.json                      (structured issues with IDs and fixability)
    step-result.json                 (sidecar: confidence, severity_counts, has_issues_json, fixable_count)
    verification/                    (created during adversarial fix verification)
      verify-issue-1.json
      verify-issue-2.json
      verification-summary.json
  style-review/
    review.md
    step-result.json                 (sidecar: common fields only)
  create-merge-request/
    step-result.json                 (sidecar: commit_sha, branch, pushed, url, action, platform, skipped)
  workflow/
    docs-workflow_proj-123.json
```

Each step skill knows its own output folder and writes there. Each step reads input from upstream step folders referenced in its `inputs` list. The orchestrator passes the base path `.agent_workspace/<ticket>/` — step skills derive everything else by convention.

### Step result sidecars

Every step that produces markdown output also writes a `step-result.json` sidecar with structured metadata. See [schema/step-result-schema.md](schema/step-result-schema.md) for the full schema. Downstream scripts and the orchestrator prefer sidecar data when present, falling back to parsing the markdown output for backward compatibility.

## Progress file

Claude writes the progress file directly using the Write tool. Create it after parsing arguments, before step 1. Update it after each step. Also write the active workflow marker at the same time (see [Active workflow marker](#active-workflow-marker)).

**Location**: `.agent_workspace/<ticket>/workflow/<workflow-type>_<ticket>.json`

The `workflow_type` field and filename prefix match the YAML's `workflow.name`. This allows multiple workflow types to run against the same ticket without conflict.

### Schema

```json
{
  "workflow_type": "<workflow.name from YAML>",
  "ticket": "<TICKET>",
  "base_path": "/absolute/path/to/.agent_workspace/<ticket>",
  "status": "in_progress",
  "created_at": "<ISO 8601>",
  "updated_at": "<ISO 8601>",
  "options": {
    "format": "adoc",
    "draft": false,
    "create_merge_request": false,
    "pr_urls": [],
    "source": null,
    "additional_sources": [],
    "no_source_repo": false,
    "auto_discover_repos": false,
    "max_secondary_repos": 3
  },
  "step_order": ["requirements", "code-analysis", "pr-analysis", "planning", "writing", ...],
  "steps": {
    "<step-name>": {
      "status": "pending",
      "output": null,
      "result": null
    }
  }
}
```

The `output` field records the step's output folder path (e.g., `.agent_workspace/proj-123/writing/`) once completed.

The `result` field stores selected sidecar data after each step completes. This lets the orchestrator make downstream decisions and display summaries without re-reading sidecar files from disk — especially important on resume. Set to `null` until the step completes; then populated from `step-result.json` (see [Step-specific post-processing](#step-specific-post-processing)).

### Status values

| Value | Meaning |
|---|---|
| `pending` | Not yet started |
| `in_progress` | Currently running |
| `completed` | Finished successfully |
| `failed` | Failed — needs retry |
| `skipped` | Conditional step not applicable |
| `deferred` | Waiting for upstream step to determine if condition is met |

### `step_order`

A top-level array listing steps in canonical order. This field exists so the Stop hook can determine step ordering without a hardcoded bash array. It **must** always be written by the orchestrator and kept in sync with the YAML step list.

## Active workflow marker

The active workflow marker tells the Stop hook which workflow (if any) is currently running in this session. Without the marker, the hook allows Claude to stop freely.

**Location**: `.agent_workspace/.active-workflow`

### When to write the marker

Write the marker file using the Write tool at the same time as creating or updating the progress file to `"in_progress"` — after parsing arguments, before step 1. If resuming an existing workflow, overwrite any existing marker.

### Schema

```json
{
  "ticket": "<TICKET>",
  "workflow_type": "<workflow.name from YAML>",
  "progress_file": ".agent_workspace/<ticket-lower>/workflow/<workflow-type>_<ticket-lower>.json"
}
```

The `progress_file` path must be relative to the project root (matching the path the hook uses to locate the file).

### When to delete the marker

Delete `.agent_workspace/.active-workflow` when:

1. The workflow completes — immediately after setting the progress file's `status` to `"completed"` in the [Completion](#completion) section
2. The workflow fails terminally — after setting `status` to `"failed"` (e.g., planning step produces 0 modules and user chooses to stop)

Do **not** delete the marker between steps. The marker must persist for the entire duration of the workflow so the Stop hook can block premature stops.

### Overwriting on resume or new workflow

If the user starts a new workflow (different ticket or different workflow type) or resumes an existing one, overwrite the marker with the new workflow's information. There is only ever one active workflow at a time. The previous marker is implicitly superseded.

### Edge cases

- **No marker exists**: The Stop hook allows Claude to stop. This is the correct default for sessions that don't involve a workflow.
- **Marker points to a missing progress file**: The Stop hook cleans up the stale marker and allows stop.
- **Marker exists but workflow status is `"completed"` or `"failed"`**: The Stop hook cleans up the marker and allows stop.

## Check for existing work

Before starting, check for a progress file at `.agent_workspace/<ticket>/workflow/<workflow-type>_<ticket>.json`.

**If a progress file exists:**

1. Read it and identify which steps have status `"completed"` or `"skipped"`
2. For each `"completed"` step, verify its output folder still exists on disk. If it has been deleted, reset that step to `"pending"` and reset all downstream dependent steps to `"pending"` as well
3. If `options.source` is `null`, rehydrate it from on-disk source state **before** choosing the resume step:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/resolve_source.py \
  --base-path <base_path> \
  --progress-file <progress_file> \
  [--scan-requirements --skip-deferred-on-no-source]
```

Use the bracketed flags only if the `requirements` step has already completed; this re-runs post-requirements source discovery against the persisted workflow artifacts (`discovered_repos.json`, `requirements.md`). Then re-read the progress file from disk before continuing. This ensures cached `source.yaml` and any already-cloned repo are reflected in `options.source` on resume.

4. Resume from the first step with status `"pending"` or `"failed"`
5. Before running the resume step, validate its input dependencies are satisfied
6. Tell the user: "Found existing work for `<ticket>`. Resuming from `<step>`."
7. If the user provided additional flags on resume (e.g., `--create-jira`), update the progress file options accordingly

**If no progress file exists**, start from step 1, create a new progress file, and write the active workflow marker.

In both cases (new or resume), write the [active workflow marker](#active-workflow-marker) with the current ticket and workflow type. This ensures the Stop hook tracks only this workflow.

## Running workflow steps

Run steps in the order defined by the YAML. For each step:

- If the step's status is `deferred`, skip it for now — it will be re-evaluated after post-requirements source resolution
- If the step's status is `skipped`, skip it permanently

### Before the step

1. Validate input dependencies — for each step name in the step's YAML `inputs`, check the upstream step's status:
   - `"completed"` — must also have a non-null `output` folder in the progress file
   - `"skipped"` (upstream step has a `when` condition) — treated as satisfied even though `output` is `null`. The downstream step is responsible for checking whether the optional input data actually exists
   - `"failed"` — **fail the current step immediately** with a clear error (e.g., "Step 'writing' requires 'planning', but planning has status 'failed'")
2. Update the step's status to `"in_progress"` in the progress file

### Construct arguments

Build the args string for the step skill. The orchestrator maps its user-facing flags to the internal flags that step skills expect: `--source-code-repo` → `--repo`, `--docs-repo-path` → `--repo-path`.

1. **Always**: `<ticket> --base-path <base_path>` — the ticket ID and the **absolute** base output path
2. **If source repo is resolved**: `--repo <repo_path>` — passed to steps that can use it
3. **From orchestrator context**: Step-specific args from parsed CLI flags:
   - `requirements`: `[--pr <url>]... [--repo <repo_path>]`
   - `code-analysis`: `--repo <repo_path>`
   - `pr-analysis`: `--repo <repo_path> [--pr <url>...]`
   - `writing`: `--format <adoc|mkdocs> [--draft] [--repo <repo_path>]... [--repo-path <path>]` — pass `--repo` for the primary source repo AND for each entry in `options.additional_sources` (in order)
   - `technical-review`: `[--repo <repo_path>]...` — pass `--repo` for the primary source repo AND for each entry in `options.additional_sources` (in order)
   - `style-review`: `--format <adoc|mkdocs>`
   - `create-merge-request`: `[--draft] [--repo-path <path>]`

Step skills derive their own output folder and input folders from `--base-path` and step name conventions. No per-input flag wiring needed.

### Invoke the step skill

```
Skill: <step.skill>, args: "<constructed args>"
```

### After the step

1. Verify the output folder exists (for steps that produce files). If the expected output folder is missing, mark the step as `failed` in the progress file and **STOP**
2. Read the step's `step-result.json` sidecar if it exists in the output folder. If present, store the step-specific fields in `steps.<step-name>.result` in the progress file (see [Step-specific post-processing](#step-specific-post-processing) for which fields to record per step). Log a warning if the sidecar is missing (the step still counts as completed — sidecars are expected but not required for backward compatibility)
3. Update the step's status to `"completed"` with the output folder path in the progress file
4. Update the progress file's `updated_at` timestamp
5. Do NOT read step output files (requirements.md, plan.md, review.md) into the orchestrator context. Read only step-result.json sidecars. Step skills and their dispatched agents read output files — the orchestrator reads metadata only
6. Run [step-specific post-processing](#step-specific-post-processing) for the just-completed step
7. **Post-step context refresh** — Re-read the progress file from disk before starting the next step. This ensures that if automatic context compaction has occurred (compressing earlier conversation turns), the orchestrator re-establishes workflow state from the authoritative source. The progress file, active workflow marker, and step output folders are the complete state — nothing essential is held only in conversation context

### Step-specific post-processing

After each step completes, apply the rules below. When rules reference sidecar fields, read from `steps.<step-name>.result` in the progress file (already recorded in the after-step logic above). If the sidecar was missing, fall back to parsing the step's primary output file where noted.

**requirements**
- Log the `title` field: `"Requirements extracted: <title>"`
- If `options.source` is `null` → run [Post-requirements source resolution](#post-requirements-source-resolution). This may change `deferred` steps to `pending` or `skipped`

**code-analysis**
- Log: `"Code analysis completed: N modules, N relationships, languages: <languages_detected>"`
- Record `repo_path` from the sidecar for downstream steps
- **Multi-repo code analysis**: If `options.additional_sources` is non-empty, run code-analysis for each additional repo sequentially. For each additional source entry:
  1. Derive the repo name: `basename(additional_source.repo_path)`
  2. Invoke the code-analysis step skill with a custom output dir:
     ```
     Skill: docs-workflow-code-analysis, args: "--repo <additional_source.repo_path> --ticket <ticket> --output-dir <base_path>/code-analysis-<repo-name>"
     ```
  3. Log: `"Additional code analysis completed for <repo-name>"`
  These additional analyses are sub-tasks of the primary code-analysis step — do not create separate progress file entries. If an additional repo analysis fails, log a warning and continue (do not fail the entire code-analysis step)

**pr-analysis**
- Log: `"PR analysis completed: PR #<pr_number> — N modules affected"`

**planning**
- Log: `"Planning completed: N modules"`
- If `module_count` is 0, **warn**: `"Planning produced 0 modules — the plan may be empty. Review plan.md before continuing."` Ask the user whether to proceed or stop. If the user chooses to stop: mark the planning step as `failed` in the progress file, set the workflow status to `"failed"`, delete the active workflow marker (`.agent_workspace/.active-workflow`), log `"Planning stopped by user after 0 modules — workflow cancelled."`, and halt without running subsequent steps

**writing**
- If `result.files` is empty or missing, **warn**: `"Writing step produced no files."` Mark the `create-merge-request` step as `skipped` with `skip_reason: "no_files"` and record `result.commit_sha: null`, `result.branch: null`, `result.pushed: false`, `result.url: null`, `result.action: "skipped"`, `result.platform: "unknown"`, `result.skipped: true`. Log: `"Skipping create-merge-request: no files to commit."`

**create-merge-request**
- Record `result.url`, `result.pushed`, and `result.branch`. If `result.pushed` is false and `result.skipped` is false, log warning: `"create-merge-request: branch was not pushed."` If `result.url` is present, record it for the [Completion](#completion) summary

**create-jira**
- Record `result.jira_url` and `result.jira_key` for the [Completion](#completion) summary

## Post-requirements source resolution

This section triggers **only** when the `requirements` step completes AND `options.source` is still `null` (i.e., no source was resolved pre-flight).

### 1. Run resolve_source.py with `--progress-file`

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/resolve_source.py \
  --base-path <base_path> \
  --progress-file <progress_file> \
  --scan-requirements \
  --skip-deferred-on-no-source
```

The script reads `discovered_repos.json` (produced by the requirements step from the JIRA graph), then scans `requirements.md` for GitHub/GitLab PR/MR URLs as a fallback. When a repo is found, it clones/verifies it, writes `source.yaml`, records `options.source` in the progress file, and promotes deferred steps to `pending`.

### 2. Handle the result

| Exit code | `status` | Action |
|---|---|---|
| 0 | `resolved` | The script has already recorded `options.source` in the progress file (primary repo + any `additional_repos`) and updated all `deferred` steps to `pending`. Log all resolved repos |
| 1 | `error` / `clone_failed` | Log a warning: "Could not clone `<repo_url>`. Code-evidence will be skipped. To retry, run with `--source-code-repo <url-or-local-path>`." Leave the progress file unchanged |
| 2 | `no_source` | Skip code-analysis (see below) |

### 3. No source found

When the script returns `no_source`, skip code-analysis without prompting.

With `--skip-deferred-on-no-source`, the script has already updated all `deferred` steps to `skipped`. Continue without code-analysis and log: "No source code repository or PR discovered. Skipping code-analysis. To enable it, re-run with `--source-code-repo <url-or-path>` or `--pr <url>`."

## Technical review iteration

The technical review uses an Identify-Fix-Verify loop. The full opus reviewer runs exactly once. Fixes are verified by lightweight parallel sonnet agents. Rejected fixes are re-attempted with the rejection reason as context. Final confidence is computed from fix outcomes, not re-derived from a full re-review.

### Phase 1: Full review (one pass)

1. Invoke `docs-workflow-tech-review` with the standard args
2. Read the review metadata. **Prefer the sidecar** (`<base_path>/technical-review/step-result.json`) when present — read `confidence`, `severity_counts`, `has_issues_json`, and `fixable_count` directly. **Fall back** to using `grep` to extract the `Overall technical confidence: (HIGH|MEDIUM|LOW)` and `Severity counts:` lines from `review.md` if no sidecar exists — do not read the full review.md into context
   - If neither the sidecar nor the confidence line is found, treat it as a step failure — mark the step `failed` and stop
   - Update `steps.technical-review.result` from the sidecar (confidence, severity_counts, iteration, has_issues_json, fixable_count)
3. If `HIGH` → mark completed, proceed to next step
4. If `MEDIUM` or `LOW`, check the severity counts:
   - If `MEDIUM` with both `critical=0` AND `significant=0` → treat as acceptable. Log: "MEDIUM confidence with zero critical/significant issues — proceeding (remaining items require SME review)." Mark completed and proceed to next step
   - Otherwise (`MEDIUM` with critical or significant issues, or `LOW`) → continue to Phase 2

### Phase 2: Fix

5. Check for fixable issues:
   - If `has_issues_json` is `true` in the sidecar, read `<base_path>/technical-review/issues.json`
   - If `fixable_count` is `0` (all issues are SME-only or non-fixable), skip to Phase 4
   - If `issues.json` does not exist (legacy behavior), proceed with the fix and skip to Phase 4 after it completes
6. Run the fix skill:
   ```
   Skill: docs-tools:docs-workflow-writing, args: "<ticket> --base-path <base_path> [--repo <repo_path>]... --fix-from <base_path>/technical-review/review.md"
   ```
   Pass `--repo` for the primary source repo and each additional source (same as the writing step's initial invocation) so the fix agent can verify review findings against source code.
7. After the fix skill completes, check for `<base_path>/writing/fix-manifest.json`:
   - If it exists, read it and collect all issues where `action` is `"fixed"` or `"partial"` — these are the candidates for verification
   - If it does not exist, log a warning: "Fix agent did not produce fix-manifest.json — skipping adversarial verification." Skip to Phase 4

### Phase 3: Adversarial verification

8. Create the verification output directory: `<base_path>/technical-review/verification/`

9. For each issue in `fix-manifest.json` where `action` is `"fixed"` or `"partial"`, look up the full issue details from `issues.json` (match by `issue_id`). Resolve the `file` field to an absolute path before passing it to the verification agent: if the fix-manifest `file` field is a bare filename (no directory separators), look up the absolute path from the writing step's `step-result.json` `files` array (match by basename); if no match is found, prepend the writing output directory (`<base_path>/writing/`). If the file path is already absolute, use it as-is.

   Log: `"Verifying N fixes..."` where N is the number of candidates with `action` `"fixed"` or `"partial"`.

   Dispatch **all** verification agents in a **single message** (parallel execution). For each fixed issue, dispatch an inline sonnet agent:

   ```
   Agent:
     description: "Verify fix for <issue_id> in <TICKET>"
     prompt: |
       You are a skeptical technical reviewer verifying a documentation fix.
       Your job is to find reasons the fix is WRONG, not to confirm it is correct.

       ORIGINAL ISSUE:
       - ID: <issue_id>
       - Severity: <severity>
       - Location: <location>
       - Issue: <issue_text>
       - Impact: <impact>
       - Suggested fix: <suggestion>

       FIX APPLIED:
       - Action: <action from fix-manifest>
       - Description: <description from fix-manifest>
       - File: <file from fix-manifest>
       - Lines changed: <lines_changed from fix-manifest>

       TASK:
       1. Read the file at the location described above
       2. Determine whether the fix FULLY resolves the original issue
          (not partially, not approximately — fully)
       3. Check that the fix did not introduce new technical inaccuracies,
          broken syntax, or inconsistencies with surrounding content
       4. Write your verdict to: <base_path>/technical-review/verification/verify-<issue_id>.json

       Verdict format:
       {
         "issue_id": "<issue_id>",
         "verdict": "accepted" | "rejected",
         "reason": "<1-2 sentences explaining your verdict>",
         "new_problems": []
       }

       Be SKEPTICAL. Default to "rejected" if uncertain.
       A fix that partially addresses the issue but leaves the core problem is "rejected".
       A fix that resolves the issue but introduces a new factual error is "rejected".

       After writing, print ONLY: Verified <issue_id>: <verdict>
   ```

10. After all verification agents complete, collect results. For any fixed issue whose `verify-<issue_id>.json` file is missing (agent failed or was skipped), create a fallback file with `verdict: "rejected"` and `reason: "Verification agent did not produce a result"`.

11. Count accepted and rejected verdicts. Log: `"Verification complete: N accepted, M rejected"` with the actual counts. If any accepted verdict has a non-empty `new_problems` array, log a warning listing each new problem — these do not change the verdict but are surfaced to the user in the final summary. If all fixed issues are accepted, skip to Phase 4.

### Phase 3b: Re-fix rejected issues (max 2 retries per issue)

12. Before the first re-fix cycle, create `<base_path>/technical-review/verification/retry-state.json` to track per-issue retry counts and preserve fix details across cycles:

    ```json
    {
      "retries_by_issue": {},
      "cycle_count": 0,
      "fix_history": []
    }
    ```

    On each entry to Phase 3b, read `retry-state.json`. For each rejected issue, increment its counter in `retries_by_issue` (initialize to 0 if absent). Increment `cycle_count`. Write the updated `retry-state.json` back to disk before proceeding.

13. If any issues have `verdict: "rejected"` and their `retries_by_issue` count is less than 2:
    a. Write a targeted review file at `<base_path>/technical-review/refix-review.md` containing ONLY the rejected issues. Include a heading: `## Re-fix attempt (retry N of 2)`. For each rejected issue, include:
       - The original issue description (from `issues.json`)
       - The fix that was attempted (from `retry-state.json` `fix_history` for the previous cycle — not from `fix-manifest.json`, which will be overwritten)
       - The rejection reason (from the verification verdict)
       - Explicit instruction: "The previous fix was rejected because: <rejection reason>. Apply a corrected fix that addresses the rejection reason."
    b. Run the fix skill with the targeted review:
       ```
       Skill: docs-tools:docs-workflow-writing, args: "<ticket> --base-path <base_path> [--repo <repo_path>]... --fix-from <base_path>/technical-review/refix-review.md"
       ```
    c. After the fix skill completes, read `fix-manifest.json` and append the relevant entries (only the re-fixed issues) to `retry-state.json` `fix_history` with the cycle number. Write the updated `retry-state.json` back to disk
    d. Re-run verification for ONLY the rejected issues (dispatch parallel sonnet agents as in step 9, but only for the re-fixed issues). Resolve file paths as described in step 9
    e. Update the verification results for those issues
    f. If all re-verified issues are now accepted, proceed to Phase 4
    g. If retries exhausted (count reaches 2 in `retries_by_issue`) for any issue, accept the current state and proceed to Phase 4

### Phase 4: Final confidence computation

14. Compute the final confidence from verification outcomes rather than re-running the full reviewer.

    Read the verification results (if Phase 3 ran). Also read `issues.json` for severity information. Apply this logic:

    **Count unresolved issues by severity:**
    - An issue is "unresolved" if it was: never attempted (`action: "skipped"` in fix-manifest), rejected after max retries, or not present in the fix-manifest
    - An issue is "resolved" if it was accepted by adversarial verification
    - SME issues (`severity: "sme"`) are always counted as unresolved but do not affect confidence

    **Final confidence rules:**
    - Zero unresolved critical AND zero unresolved significant → `HIGH`
    - Zero unresolved critical AND any unresolved significant → `MEDIUM`
    - Any unresolved critical → `LOW`
    - Special case: if `fixable_count` was `0` (all issues are SME-only or non-fixable) AND the original confidence was `LOW`, keep `LOW` and ask the user — the reviewer assigned LOW for reasons beyond the individual issues
    - If Phase 3 was not run (issues.json did not exist, fix-manifest was absent, or legacy path was taken), retain the original confidence from Phase 1 unchanged

15. Update `step-result.json` with the final state:
    - Set `confidence` to the computed final confidence
    - Set `iteration` to `1` plus the number of fix-verify cycles completed
    - Update `severity_counts` to reflect UNRESOLVED issues only (original counts minus accepted fixes)
    - Add `"verification_summary"` field with the path to `verification-summary.json`

16. Write `<base_path>/technical-review/verification/verification-summary.json`:

    ```json
    {
      "schema_version": 1,
      "ticket": "<TICKET>",
      "verified_at": "<ISO 8601>",
      "initial_confidence": "<original confidence from Phase 1>",
      "final_confidence": "<computed confidence>",
      "results": {
        "accepted": ["issue-1", "issue-4"],
        "rejected": ["issue-2"],
        "not_fixed": ["issue-3", "issue-5"]
      },
      "counts": {
        "accepted": 2,
        "rejected": 1,
        "not_fixed": 2,
        "total_fixable": 5,
        "retries_used": 1
      }
    }
    ```

17. Log the final outcome:
    - If confidence improved to `HIGH`: "Technical review passed: all critical and significant issues resolved."
    - If confidence improved to `MEDIUM`: "Technical review improved to MEDIUM after fixes. N issues remain for SME review."
    - If confidence stayed `MEDIUM`: "Technical review MEDIUM: remaining issues require SME review."
    - If `LOW` after fixes: "Technical review LOW after fix cycle. N critical issues remain unresolved." Then ask the user whether to proceed or stop

18. Mark the step completed and proceed to the next step.

### Fallback behavior

If any infrastructure failure occurs during Phases 2-3 (fix agent crashes, no verification files produced, issues.json is malformed), fall back gracefully: log a warning describing the failure and accept the current confidence level as the final result. Do not retry the full reviewer. Write `verification-summary.json` with `initial_confidence` and `final_confidence` both set to the Phase 1 confidence, empty `results` arrays (`accepted: [], rejected: [], not_fixed: []`), zero `counts`, and a `fallback_reason` field describing the failure. The orchestrator should never fail the entire workflow due to a verification infrastructure issue — the initial review result is always a valid fallback.

## Commit confirmation gate

Before running the `create-merge-request` step, **ask the user to confirm** before committing. Show:
  - The target branch name — derived from the ticket ID (lowercase). If the repo is already on a feature branch, show the current branch name (from `git branch --show-current`)
  - The repository being committed to (current directory or `--docs-repo-path`)
  - The number of files — from `steps.writing.result.files` array length in the progress file. If unavailable, count files in the writing output folder

If the user declines, mark the `create-merge-request` step as `skipped` (with `skip_reason: "user_declined"`). Record `result.commit_sha: null`, `result.branch: null`, `result.pushed: false`, `result.url: null`, `result.action: "skipped"`, `result.platform: "unknown"`, `result.skipped: true`.

## Completion

After all steps complete (or are skipped):

1. Update the progress file: `status → "completed"`
2. Delete the active workflow marker: remove `.agent_workspace/.active-workflow`
3. Display a summary:
   - List all output folders with paths
   - Note any warnings (tech review didn't reach `HIGH`, planning had 0 modules, code-analysis had 0 modules, etc.)
   - Show MR/PR URL from `steps.create-merge-request.result.url` if present
   - Show JIRA URL from `steps.create-jira.result.jira_url` (with key `result.jira_key`) if present
   - Show module count from `steps.planning.result.module_count` and file count from `steps.writing.result.files` length

## Resume behavior

### Same session

The progress file is already in context. Skip completed steps and continue from the first `pending` or `failed` step. The Stop hook ensures Claude doesn't stop prematurely.

### New session

User says: `"Resume docs workflow for PROJ-123"`

1. Invoke this skill with the ticket
2. Check for an existing progress file
3. Read it, skip completed steps, resume from first `pending` or `failed` step
4. Before running the resume step, **validate its input dependencies** — every required upstream step must have `status: "completed"` and a non-null `output` folder. If a dependency is `failed` or `pending`, re-run that dependency first
5. For each upstream dependency, verify the output folder still exists on disk. If an output folder was deleted, mark that step as `pending` and re-run it
6. The user can provide additional flags on resume (e.g., add `--create-jira`) — update the progress file options accordingly

### After failure

Same as new session. The progress file shows which steps completed and which failed. Walk back to the earliest incomplete dependency and resume from there.

### Context management

The orchestrator relies on two complementary mechanisms for context management:

1. **Automatic compaction** — Claude Code automatically compresses prior conversation turns when approaching context limits. Because the orchestrator invokes step skills via the Skill tool, there are natural tool-call boundaries between steps where compaction can occur. No manual intervention is needed.

2. **Progress file as authoritative state** — After compaction, prior conversation turns (argument parsing, early step logs, sidecar data) may no longer be in context. The orchestrator handles this by re-reading the progress file from disk after each step completes (see "Post-step context refresh" in the after-step checklist). The progress file records everything the orchestrator needs to continue: ticket, options (format, draft, source, PR URLs), step_order, per-step status, output paths, and sidecar result data. No workflow state is held exclusively in conversation memory.

This design means the orchestrator runs the entire pipeline in a single session without forced stops. The progress file remains the safety net for genuine session interruptions (user closes the terminal, network failure, crash).

## Follow-on work

### Requirements-analyst agent: repo-aware analysis

When `--repo` is passed to the requirements step, the `requirements-analyst` agent uses the repo to enrich its analysis: verifying features exist in code, identifying existing documentation, extracting project metadata, and noting code references for downstream steps. See `agents/requirements-analyst.md` step 2 (Source repo enrichment).

