---
name: query-code
description: Answer questions about a previously analyzed codebase. Reads learn-code output and dispatches an agent that can also Read/Grep the actual source code to provide file:line-grounded answers.
argument-hint: <question> [--repo <path|url>]
allowed-tools: Read, Write, Bash, Glob, Grep, Skill, Agent
---

# Query-Code — Ask Questions About an Analyzed Codebase

Takes a natural-language question about a codebase, loads the analysis data produced by `learn-code`, and dispatches an agent that answers the question with evidence grounded in actual source files and line numbers.

## Usage

```
/code-learner:query-code "How does authentication work?" --repo /path/to/repo
/code-learner:query-code "How does authentication work?" --repo https://github.com/user/repo
/code-learner:query-code "What modules depend on the database layer?"
/code-learner:query-code "Where is the HTTP routing configured?" --repo /path/to/my-api
```

## Arguments

- `$1` — The question to answer (required, can be a quoted string)
- `--repo <path|url>` — Path or URL of the repository (optional if only one analysis exists). Accepts a local filesystem path or a git remote URL (`https://`, `git@`, `git://`). Git URLs are cloned to `.agent_workspace/<repo-name>/_clone/`.

## Execution

### 1. Parse arguments

Extract the question (first positional argument or quoted string) and optional `--repo` path.

If the question is empty, STOP and report: `"Please provide a question about the codebase."`.

### 2. Resolve analysis data

**If `--repo` is provided:**

**If the value is a git URL** (matches `https://`, `http://`, `git@`, or `git://`):

1. Derive `REPO_NAME` from the URL: strip any trailing `.git`, then take the last path segment (e.g., `https://github.com/user/my-project.git` → `my-project`).
2. Set paths:

```bash
GIT_ROOT="$(cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" && pwd)"
BASE_PATH="${GIT_ROOT}/.agent_workspace/${REPO_NAME}"
CLONE_DIR="${BASE_PATH}/_clone"
```

3. If `${CLONE_DIR}` already exists and is a git repo, use it as the repo path.
4. If `${CLONE_DIR}` does not exist and an analysis already exists at `${BASE_PATH}`, proceed without a clone (the analysis data is sufficient for querying, though file:line inspection will be limited).
5. If neither the clone nor analysis exists, clone:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py clone "<URL>" --output-dir "${CLONE_DIR}"
```

Then offer to run `learn-code` (see step 3 below).

**If the value is a local path:**

Resolve to absolute path. Derive `REPO_NAME` from basename. Set:

```bash
GIT_ROOT="$(cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" && pwd)"
BASE_PATH="${GIT_ROOT}/.agent_workspace/${REPO_NAME}"
```

**If `--repo` is NOT provided:**

Scan `.agent_workspace/` for subdirectories containing `synthesis/ONBOARDING.md`.

- If exactly one exists: use it. Derive `REPO_NAME` and `BASE_PATH`.
- If multiple exist: list them and ask the user to specify `--repo`.
- If none exist: report that no analysis data is available.

### 3. Verify analysis exists

Check that `${BASE_PATH}/synthesis/ONBOARDING.md` exists.

**If it does not exist:**

Check if `${BASE_PATH}/workflow/` contains a progress file.

- If a progress file exists with `status: "in_progress"`: report that the analysis is incomplete and offer to resume it.
- If no progress file exists: ask the user if they want to run learn-code first.

If the user agrees to run learn-code:

```
Skill: code-learner:learn-code
args: <repo-path>
```

Wait for it to complete, then proceed to step 4.

### 4. Load analysis context

Read the following files from `${BASE_PATH}/`:

| File | Content |
|------|---------|
| `detection/detection.json` | Language, module map, config info |
| `module-registry/registry.json` | Module purposes and complexity |
| `module-analysis/summary.json` | Detailed per-module analysis |
| `relationships/relationships.json` | Cross-module coupling data |
| `synthesis/ONBOARDING.md` | Full onboarding guide |

If any file is missing (except relationships, which may not exist for older analyses), log a warning but continue with available data.

Assemble the context into a JSON object:

```json
{
  "repo_name": "<REPO_NAME>",
  "primary_language": "<from detection>",
  "detection": "<detection.json contents>",
  "registry": "<registry.json contents>",
  "summaries": "<summary.json contents>",
  "relationships": "<relationships.json contents or []>"
}
```

### 5. Determine repo path

The repo path is needed so the agent can inspect actual source files. Determine it from:

1. The `--repo` argument if provided
2. The `repo_path` field in the progress file at `${BASE_PATH}/workflow/learn-code_${REPO_NAME}.json`
3. The `repo_root` field in `detection.json`

If none of these yield a valid path, warn the user that file:line references may not be available.

### 6. Set output path

```bash
OUTPUT_DIR="${BASE_PATH}/queries"
mkdir -p "$OUTPUT_DIR"
```

Generate a filename slug from the question:
1. Lowercase the question
2. Replace spaces and non-alphanumeric characters (except hyphens) with hyphens
3. Collapse consecutive hyphens into one
4. Strip leading and trailing hyphens
5. Truncate to 60 characters
6. Append `_<YYYYMMDD-HHMMSS>.md` using the current UTC time

Example: `"How do the Tekton PipelineRuns get triggered?"` → `how-do-the-tekton-pipelineruns-get-triggered_20260524-180000.md`

Set `OUTPUT_FILE="${OUTPUT_DIR}/<slug>.md"`.

### 7. Dispatch code-questioner agent

```
Agent:
  subagent_type: code-learner:code-questioner
  description: "Answer: <question truncated to 60 chars>"
  prompt: |
    Answer this question about the <REPO_NAME> codebase:

    QUESTION: <user's full question>

    ANALYSIS_CONTEXT:
    <JSON context object from step 4>

    ONBOARDING_GUIDE:
    <full contents of ONBOARDING.md>

    REPO_PATH: <absolute path to the repository>
    OUTPUT_FILE: <OUTPUT_FILE>

    You may Read and Grep files in REPO_PATH to find specific code evidence.
    Always include file:line references when citing specific code.
    Write your answer as markdown (with YAML frontmatter) to OUTPUT_FILE.
```

### 8. Verify and present answer

After the agent completes:

1. Verify `${OUTPUT_FILE}` was written. If the agent failed to write it, write the agent's response yourself to `${OUTPUT_FILE}` with YAML frontmatter:

```markdown
---
question: "<original question>"
repo: "<REPO_NAME>"
date: "<current ISO 8601 UTC>"
---

<agent's response>
```

2. Display the answer to the user.
3. Log: `"Answer saved to <OUTPUT_FILE>"`.
