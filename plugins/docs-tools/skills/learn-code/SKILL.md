---
name: learn-code
description: Analyze a codebase for engineer onboarding. Detects language, maps modules, analyzes each module in parallel, discovers cross-module relationships, and produces an ONBOARDING.md guide.
argument-hint: <repo-path-or-url> [--exclude <glob>...]
allowed-tools: Read, Write, Bash, Glob, Grep, Agent
---

# Learn-Code — Codebase Analysis for Onboarding

Single-skill pipeline that detects language, maps modules, analyzes each module in parallel via fan-out agents, discovers cross-module relationships, and produces a structured onboarding guide.

## Usage

```
/code-learner:learn-code /path/to/repo
/code-learner:learn-code https://github.com/user/repo
/code-learner:learn-code git@github.com:user/repo.git
/code-learner:learn-code /path/to/repo --exclude "test/*" "vendor/*"
```

## Arguments

- `$1` — Path or URL of the repository to analyze (required). Accepts a local filesystem path or a git remote URL (`https://`, `git@`, `git://`). Git URLs are cloned to `.agent_workspace/<repo-name>/_clone/`.
- `--exclude <glob>...` — Glob patterns to exclude from analysis

## Pre-flight

### 1. Parse and validate arguments

Extract the repo path from the first positional argument. Extract any `--exclude` patterns.

### 2. Resolve repo path

**If the argument is a git URL** (matches `https://`, `http://`, `git@`, or `git://`):

1. Derive `REPO_NAME` from the URL: strip any trailing `.git`, then take the last path segment (e.g., `https://github.com/user/my-project.git` → `my-project`, `git@github.com:user/my-project` → `my-project`).
2. Set the clone destination:

```bash
GIT_ROOT="$(cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" && pwd)"
CLONE_DIR="${GIT_ROOT}/.agent_workspace/${REPO_NAME}/_clone"
```

3. If `${CLONE_DIR}` already exists and is a git repo, ask the user: `"Existing clone found at ${CLONE_DIR}. Pull latest or use as-is?"`. If pull: run `git -C "${CLONE_DIR}" pull`. If as-is: continue.
4. If `${CLONE_DIR}` does not exist, clone:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/git-pr-reader/scripts/git_pr_reader.py clone "<URL>" --output-dir "${CLONE_DIR}"
```

If the clone fails (status "error" in JSON output), STOP and report the error.

5. Set `REPO_PATH="${CLONE_DIR}"`.

**If the argument is a local path:**

Validate:
- The path exists and is a directory
- The path is not empty (has files)

If the repo path is relative, resolve it to an absolute path.

If the path does not exist, STOP and report: `"Repository path not found: <path>"`.

Derive `REPO_NAME` from the basename of the repo path (e.g., `/home/user/my-project` → `my-project`).

Set `REPO_PATH` to the resolved absolute path.

### 3. Set base path

```bash
GIT_ROOT="$(cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" && pwd)"
BASE_PATH="${GIT_ROOT}/.agent_workspace/${REPO_NAME}"
mkdir -p "${BASE_PATH}"
```

### 4. Check for existing progress (resume)

Look for an existing progress file:

```
${BASE_PATH}/workflow/learn-code_${REPO_NAME}.json
```

**If found and status is `in_progress`**:
- Read the progress file
- Log: `"Resuming workflow from last checkpoint"`
- Skip steps whose status is `completed`
- Start from the first step whose status is `pending` or `in_progress`

**If found and status is `completed`**:
- Ask the user: `"Previous analysis found. Re-run from scratch?"`
- If yes: reset all steps to `pending`, update `updated_at`
- If no: show the completion summary and exit

**If not found**: create a new progress file (see below).

### 5. Create progress file

```json
{
  "workflow_type": "learn-code",
  "target": "<REPO_NAME>",
  "repo_path": "<absolute REPO_PATH>",
  "base_path": "<absolute BASE_PATH>",
  "status": "in_progress",
  "created_at": "<current ISO 8601 UTC>",
  "updated_at": "<current ISO 8601 UTC>",
  "options": {
    "exclude_patterns": ["<patterns>"]
  },
  "step_order": ["detection", "module-registry", "module-analysis", "relationships", "synthesis"],
  "steps": {
    "detection": { "status": "pending", "output": null, "result": null },
    "module-registry": { "status": "pending", "output": null, "result": null },
    "module-analysis": { "status": "pending", "output": null, "result": null },
    "relationships": { "status": "pending", "output": null, "result": null },
    "synthesis": { "status": "pending", "output": null, "result": null }
  }
}
```

Write to `${BASE_PATH}/workflow/learn-code_${REPO_NAME}.json`.

### 6. Show analysis plan

Log:

```
Learn-Code: Analyzing <REPO_NAME>
  Repository: <absolute-path>
  Steps:      detection → module-registry → module-analysis → relationships → synthesis
  Excludes:   <patterns or "none">
```

---

## Step 1 — Detection

Detect the primary language, walk the file tree to build a module map, and read config files.

### 1.1 Set output path

```bash
OUTPUT_DIR="${BASE_PATH}/detection"
mkdir -p "$OUTPUT_DIR"
```

### 1.2 Detect language

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/detect_language.py --repo <REPO_PATH>
```

Capture the JSON output. If it contains an `error` field, STOP and report the error.

Extract `primary_language` from the result.

### 1.3 Build module map

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/build_module_map.py --repo <REPO_PATH> --lang <PRIMARY_LANGUAGE> [--exclude <PATTERNS>...]
```

Capture the JSON output. If it contains an `error` field, STOP and report the error.

### 1.4 Read config files

From the module map result, read each file listed in `config_files`. Read the actual file content from the repo (e.g., `<REPO_PATH>/pyproject.toml`). Truncate each config file to 5000 characters.

### 1.5 Write detection.json

Combine all results:

```json
{
  "primary_language": "<from detect_language>",
  "language_counts": "<from detect_language>",
  "total_files": "<from detect_language>",
  "total_source_files": "<from detect_language>",
  "modules": "<from build_module_map>",
  "module_count": "<from build_module_map>",
  "config_files": "<list of config file names>",
  "config_contents": { "<filename>": "<truncated file content>" },
  "repo_root": "<absolute repo path>",
  "excluded_patterns": "<from build_module_map>"
}
```

Write to `${OUTPUT_DIR}/detection.json`.

### 1.6 Write step-result.json

```json
{
  "schema_version": 1,
  "step": "detection",
  "target": "<repo-name>",
  "completed_at": "<current ISO 8601 UTC>",
  "primary_language": "<detected language>",
  "languages_detected": "<language_counts>",
  "module_count": "<number of modules>",
  "total_source_files": "<count>",
  "config_files_found": ["<list of config files>"]
}
```

Write to `${OUTPUT_DIR}/step-result.json`.

### 1.7 Update progress

Update the progress file: set `steps.detection.status` to `completed`, set `steps.detection.output` to `${OUTPUT_DIR}/`, set `steps.detection.result` to the step-result data. Update `updated_at`.

Log: `"Detection complete: <primary_language>, <module_count> modules, <total_source_files> source files"`.

---

## Step 2 — Module Registry

Dispatch the repo-mapper agent to produce a per-module registry with tailored analysis questions.

### 2.1 Set paths

```bash
INPUT_FILE="${BASE_PATH}/detection/detection.json"
OUTPUT_DIR="${BASE_PATH}/module-registry"
mkdir -p "$OUTPUT_DIR"
```

### 2.2 Read detection data

Read `${INPUT_FILE}`. If it does not exist, STOP and report that the detection step must complete first.

Extract `primary_language`, `modules`, `config_contents`, `module_count`.

If `module_count` is 0, write an empty registry and step-result, then skip to Step 3.

### 2.3 Dispatch repo-mapper agent

```
Agent:
  subagent_type: code-learner:repo-mapper
  description: "Map modules for <REPO_NAME>"
  prompt: |
    Analyze this <PRIMARY_LANGUAGE> repository and produce a module registry.

    DETECTION_DATA:
    <JSON of detection data — include modules, module_count, config_files>

    CONFIG_CONTENTS:
    <Text of each config file, prefixed with filename headers>

    REPO_PATH: <repo-path>

    Produce a JSON array of module entries, one per module in the detection data.
    Print ONLY the JSON array to stdout.
```

### 2.4 Parse agent response

The agent should return a JSON array. Parse it into `registry.json`.

If the agent response is not valid JSON:
1. Try to extract a JSON array from the response (look for `[` ... `]`)
2. If that fails, create a fallback registry with minimal entries for each module

### 2.5 Write registry.json

Write the parsed JSON array to `${OUTPUT_DIR}/registry.json`.

### 2.6 Write registry.md

Generate a human-readable markdown table:

```markdown
# Module Registry — <repo-name>

| Module | Purpose | Complexity | Likely Imports | Analysis Question |
|--------|---------|------------|----------------|-------------------|
| <module> | <purpose> | <complexity> | <imports> | <question truncated to 80 chars> |
```

Write to `${OUTPUT_DIR}/registry.md`.

### 2.7 Write step-result.json

```json
{
  "schema_version": 1,
  "step": "module-registry",
  "target": "<repo-name>",
  "completed_at": "<current ISO 8601 UTC>",
  "module_count": "<number of modules in registry>",
  "complexity_distribution": { "low": "<count>", "medium": "<count>", "high": "<count>" }
}
```

Write to `${OUTPUT_DIR}/step-result.json`.

### 2.8 Update progress

Update progress file for `module-registry` step. Log: `"Registry complete: <module_count> modules (low: N, medium: N, high: N)"`.

---

## Step 3 — Module Analysis

Fan-out module-analyzer agents with size-aware tiering and batched dispatch.

### 3.1 Set paths

```bash
REGISTRY_FILE="${BASE_PATH}/module-registry/registry.json"
DETECTION_FILE="${BASE_PATH}/detection/detection.json"
OUTPUT_DIR="${BASE_PATH}/module-analysis"
mkdir -p "$OUTPUT_DIR"
```

### 3.2 Read upstream data

Read `${REGISTRY_FILE}` and `${DETECTION_FILE}`.

Extract `primary_language`, module file lists from `detection.modules`, and registry entries.

### 3.3 Classify modules into tiers

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/classify_modules.py \
  --detection "${DETECTION_FILE}" \
  --registry "${REGISTRY_FILE}"
```

Capture the JSON output. This produces three tiers:

| Tier | Criteria | Agent strategy |
|------|----------|----------------|
| `full` | ≤3000 lines, non-low complexity | Full source in prompt |
| `api-guided` | 3001–8000 lines, or low-complexity multi-file | API + truncated source (first 2000 lines). Agent reads more from disk if needed |
| `api-only` | >8000 lines, or auto-generated code, or single low-complexity file | No agent dispatch — generate entry from API + registry |

Log: `"Module tiers: <full_count> full, <api_guided_count> api-guided, <api_only_count> api-only"`.

### 3.4 Pre-extract public API (AST-aware)

For each module, run the appropriate AST extraction script based on language:

**Python:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/extract_public_api.py \
  --files <file1.py> <file2.py> ... \
  --lang python \
  --module <module-name>
```

**Go, JavaScript, TypeScript:**
```bash
node ${CLAUDE_SKILL_DIR}/scripts/extract_public_api_treesitter.mjs \
  --files <file1> <file2> ... \
  --lang <go|javascript|typescript> \
  --module <module-name>
```

Capture the JSON output for each module. If a script fails for a module, log a warning and continue without pre-extracted API data for that module.

### 3.5 Generate api-only entries (no agent dispatch)

For each module in the `api-only` tier, generate a summary entry directly from the pre-extracted API and registry data:

```json
{
  "module": "<module-name>",
  "language": "<primary_language>",
  "purpose": "<purpose from registry>",
  "public_api": "<from pre-extracted API, or empty>",
  "dependencies": "<likely_imports from registry>",
  "external_libs": [],
  "data_flow": "See source for details",
  "implicit_contracts": [],
  "gotchas": [],
  "onboarding_priority": "skim",
  "question_answer": "API-only analysis — not deeply analyzed",
  "analysis_depth": "api-only"
}
```

Write each to `${OUTPUT_DIR}/<safe-module-name>.json`.

### 3.6 Load source for agent-analyzed modules

For each module in the `full` and `api-guided` tiers, concatenate source files with file headers:

```
### FILE: <relative-path>
<file contents>
```

Use absolute paths when reading files. Files are listed in `detection.modules.<module-name>.files`.

**Important**: Keep all import statements — they are the relationship signal consumed by the relationships step.

For `api-guided` modules: truncate the concatenated source to the **first 2000 lines**. Append a note: `### [TRUNCATED — agent may Read additional files from REPO_PATH]`.

### 3.7 Batch dispatch module-analyzer agents

Group `full` and `api-guided` modules into batches of **max 10 agents per batch**. Dispatch each batch as a single message for parallel execution. Wait for the batch to complete before dispatching the next.

Each agent gets:

```
Agent:
  subagent_type: code-learner:module-analyzer
  description: "Analyze module: <module-name>"
  prompt: |
    Analyze the following <LANGUAGE> module for engineer onboarding.

    MODULE: <module-name>
    LANGUAGE: <primary_language>
    QUESTION: <question from registry>

    PUBLIC_API (pre-extracted via AST):
    <JSON output from extract_public_api script, or "Not available" if extraction failed>

    SOURCE:
    <concatenated source with ### FILE: headers>

    Write your JSON result to: <OUTPUT_DIR>/<module-name>.json
```

For `api-guided` modules, add to the prompt:

```
    REPO_PATH: <absolute path to repository>
    NOTE: Source is truncated. Read additional files from REPO_PATH if needed to answer the question.
```

**Critical**: All Agent tool calls within a single batch MUST be in a single message so they execute in parallel. Do NOT dispatch agents one at a time within a batch.

### 3.8 Collect and merge results

After all batches complete, read each `<OUTPUT_DIR>/<module-name>.json` file.

For modules where the agent failed or produced invalid JSON, create a fallback entry:

```json
{
  "module": "<module-name>",
  "language": "<primary_language>",
  "purpose": "Analysis failed — manual review needed",
  "public_api": [],
  "dependencies": [],
  "external_libs": [],
  "data_flow": "Unknown",
  "implicit_contracts": [],
  "gotchas": ["Automated analysis failed for this module"],
  "onboarding_priority": "read-second",
  "question_answer": "Analysis failed"
}
```

### 3.9 Write summary.json

Combine all module results (api-only, agent-analyzed, and fallback) into a single JSON array. Write to `${OUTPUT_DIR}/summary.json`.

### 3.10 Write summary.md

Generate a human-readable summary:

```markdown
# Module Analysis Summary — <repo-name>

## Overview

- **Language**: <primary_language>
- **Modules analyzed**: <count>
- **Full analysis**: <count>
- **API-guided**: <count>
- **API-only**: <count>
- **Failed**: <count>

## Modules

### <module-name>

**Purpose**: <purpose>
**Priority**: <onboarding_priority>
**Analysis depth**: <full | api-guided | api-only>
**Public API**: <comma-separated list>
**Dependencies**: <comma-separated list>
**Key gotcha**: <first gotcha or "None">

---
```

Write to `${OUTPUT_DIR}/summary.md`.

### 3.11 Write step-result.json

```json
{
  "schema_version": 1,
  "step": "module-analysis",
  "target": "<repo-name>",
  "completed_at": "<current ISO 8601 UTC>",
  "modules_analyzed": "<successful count>",
  "modules_failed": "<failed count>",
  "tiers": { "full": "<count>", "api_guided": "<count>", "api_only": "<count>" },
  "total_public_api_entries": "<sum of public_api array lengths>",
  "languages": ["<primary_language>"]
}
```

Write to `${OUTPUT_DIR}/step-result.json`.

### 3.12 Update progress

Update progress file for `module-analysis` step. Log: `"Module analysis complete: <analyzed> modules (full: N, api-guided: N, api-only: N, failed: N)"`.

---

## Step 4 — Relationships

Cross-module dependency analysis with prioritized pair selection and batched dispatch.

### 4.1 Set paths

```bash
SUMMARY_FILE="${BASE_PATH}/module-analysis/summary.json"
DETECTION_FILE="${BASE_PATH}/detection/detection.json"
REGISTRY_FILE="${BASE_PATH}/module-registry/registry.json"
OUTPUT_DIR="${BASE_PATH}/relationships"
mkdir -p "$OUTPUT_DIR"
```

### 4.2 Read upstream data

Read `${SUMMARY_FILE}`, `${DETECTION_FILE}`, and `${REGISTRY_FILE}`.

### 4.3 Build dependency pairs

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/build_dep_pairs.py \
  --summaries "${SUMMARY_FILE}" \
  --registry "${REGISTRY_FILE}"
```

Capture JSON output. If `total_pairs` is 0, write empty results and step-result, then skip to Step 5.

### 4.4 Prioritize pairs

Classify each dependency pair as **priority** or **lightweight**:

**Priority pairs** (max 20): At least one module in the pair has:
- `complexity` of "high" in the registry, OR
- `onboarding_priority` of "read-first" in the module analysis summary

AND both modules have `analysis_depth` that is NOT "api-only" in the module analysis summary.

Sort priority pairs by: pairs where both modules are "high" complexity first, then pairs with one "high" module.

**Lightweight pairs**: All remaining pairs. Generate entries directly without agent dispatch:

```json
{
  "pair": ["<module_a>", "<module_b>"],
  "coupling_type": "interface-contract",
  "description": "<module_a> depends on <module_b> (lightweight analysis)",
  "shared_types": [],
  "implicit_assumptions": [],
  "risk": "See detailed analysis for core modules",
  "strength": "loose",
  "analysis_depth": "lightweight"
}
```

Log: `"Relationship pairs: <priority_count> priority, <lightweight_count> lightweight (of <total> total)"`.

### 4.5 Prepare source data for priority pairs

For each priority pair `(module_a, module_b)`:

**Module A source**: If module A has `total_lines` ≤ 3000, concatenate all source files with `### FILE:` headers. Otherwise, use the pre-extracted API surface and instruct the agent to read from disk.

**Module B — API surface only**: Run the appropriate AST extraction script:

**Python:**
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/extract_public_api.py \
  --files <b_files...> --lang python --module <module_b>
```

**Go, JavaScript, TypeScript:**
```bash
node ${CLAUDE_SKILL_DIR}/scripts/extract_public_api_treesitter.mjs \
  --files <b_files...> --lang <go|javascript|typescript> --module <module_b>
```

### 4.6 Read language guidance

Read language-specific relationship analysis guidance from `${CLAUDE_PLUGIN_ROOT}/reference/language-configs.md`.

### 4.7 Batch dispatch relationship-analyzer agents

Group priority pairs into batches of **max 10 agents per batch**. Dispatch each batch as a single message for parallel execution. Wait for the batch to complete before dispatching the next.

```
Agent:
  subagent_type: code-learner:relationship-analyzer
  description: "Analyze relationship: <mod_a> <-> <mod_b>"
  prompt: |
    Analyze the relationship between these two <LANGUAGE> modules.

    MODULE_A: <mod_a>
    MODULE_B: <mod_b>
    LANGUAGE: <primary_language>

    SOURCE_A (full source or API surface):
    <concatenated source of module A, or API JSON + REPO_PATH for large modules>

    API_B (public API surface only):
    <JSON output from extract_public_api for module B>

    LANGUAGE_GUIDANCE:
    <relevant section from language-configs.md>

    REPO_PATH: <absolute path to repository>

    Write your JSON result to: <OUTPUT_DIR>/<mod_a>--<mod_b>.json
```

For large module A (>3000 lines), add to the prompt:

```
    NOTE: Module A source is provided as API surface only. Read files from REPO_PATH/<module_a_path>/ as needed.
```

**Critical**: All Agent tool calls within a single batch MUST be in a single message for parallel execution.

### 4.8 Collect and merge results

After all batches complete, read each `<OUTPUT_DIR>/<mod_a>--<mod_b>.json` file. For failed agents or missing files, create a fallback:

```json
{
  "pair": ["<module_a>", "<module_b>"],
  "coupling_type": "unknown",
  "description": "Analysis failed — manual review needed",
  "shared_types": [],
  "implicit_assumptions": [],
  "risk": "Unknown",
  "strength": "unknown"
}
```

Combine agent results with the lightweight entries from step 4.4.

### 4.9 Write relationships.json

Write the array of all relationship results (priority + lightweight) to `${OUTPUT_DIR}/relationships.json`.

### 4.10 Write dependency-graph.json

Build a graph structure from the summaries and relationships:

```json
{
  "nodes": [
    {"id": "<module>", "purpose": "<purpose>", "priority": "<onboarding_priority>"}
  ],
  "edges": [
    {"from": "<module_a>", "to": "<module_b>", "strength": "<tight|loose|none>", "coupling_type": "<type>"}
  ]
}
```

Write to `${OUTPUT_DIR}/dependency-graph.json`.

### 4.11 Write relationships.md

Generate a human-readable summary:

```markdown
# Cross-Module Relationships — <repo-name>

## Summary

- **Pairs analyzed (agent)**: <priority_count>
- **Pairs (lightweight)**: <lightweight_count>
- **Tight couplings**: <count>
- **Loose couplings**: <count>

## Tight Couplings

### <module_a> ↔ <module_b>

- **Type**: <coupling_type>
- **Description**: <description>
- **Shared types**: <list>
- **Risk**: <risk>

## Loose Couplings

| Pair | Type | Strength |
|------|------|----------|
| <a> ↔ <b> | <type> | loose |
```

Write to `${OUTPUT_DIR}/relationships.md`.

### 4.12 Write step-result.json

```json
{
  "schema_version": 1,
  "step": "relationships",
  "target": "<repo-name>",
  "completed_at": "<current ISO 8601 UTC>",
  "pairs_analyzed": "<priority count>",
  "pairs_lightweight": "<lightweight count>",
  "pairs_failed": "<failed count>",
  "coupling_distribution": { "tight": "<count>", "loose": "<count>", "none": "<count>" }
}
```

Write to `${OUTPUT_DIR}/step-result.json`.

### 4.13 Update progress

Update progress file for `relationships` step. Log: `"Relationship analysis complete: <priority_count> priority + <lightweight_count> lightweight pairs (tight: N, loose: N, none: N)"`.

---

## Step 5 — Synthesis

Combine all module summaries and relationship data to produce the final ONBOARDING.md.

### 5.1 Set output path

```bash
OUTPUT_DIR="${BASE_PATH}/synthesis"
mkdir -p "$OUTPUT_DIR"
```

### 5.2 Build synthesis context

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/build_synthesis_context.py \
  --base-path "${BASE_PATH}" \
  --max-size 80000 > "${OUTPUT_DIR}/context.json"
```

If the output contains an `error` field, STOP and report the error.

The `--max-size 80000` flag ensures the context stays within agent context limits by progressively compacting summaries and relationships.

Log: `"Synthesis context: <context_size_bytes> bytes (truncated: <truncated or 'no'>)"`.

### 5.3 Dispatch synthesis-writer agent

The context is always written to a file. The synthesis agent reads it from disk rather than receiving it inline.

```
Agent:
  subagent_type: code-learner:synthesis-writer
  description: "Write onboarding guide for <REPO_NAME>"
  prompt: |
    Write an engineer onboarding guide for this codebase.

    Read the full context from: ${OUTPUT_DIR}/context.json

    OUTPUT_DIR: <OUTPUT_DIR>

    Write ONBOARDING.md to the output directory.
    Also write dependency-graph.json if relationship data exists (relationship_count > 0).

    Follow the template from ${CLAUDE_PLUGIN_ROOT}/reference/onboarding-template.md.
```

### 5.4 Verify output

Confirm `${OUTPUT_DIR}/ONBOARDING.md` exists. If it does not, STOP and report the synthesis agent failed.

### 5.5 Write step-result.json

Scan ONBOARDING.md for level-2 headings (`## `) to determine sections:

```json
{
  "schema_version": 1,
  "step": "synthesis",
  "target": "<repo-name>",
  "completed_at": "<current ISO 8601 UTC>",
  "output_file": "ONBOARDING.md",
  "sections": ["<list of section names from ## headings>"],
  "context_size_bytes": "<from context builder>"
}
```

Write to `${OUTPUT_DIR}/step-result.json`.

### 5.6 Update progress

Update progress file for `synthesis` step. Log: `"Synthesis complete: ONBOARDING.md written to ${OUTPUT_DIR}"`.

---

## Failure Handling

If any step skill fails (throws an error or does not produce output):
- Set `steps.<step-name>.status` to `failed` in the progress file
- Log the error
- Ask the user: `"Step <step-name> failed. Retry or skip?"`
- If retry: reset to `pending` and re-run the step
- If skip: mark as `failed` and continue (downstream steps with this as input may also fail)

---

## Completion

After all steps complete:

### Update workflow status

Set `status` to `completed`. Update `updated_at`. Write progress file.

### Print completion summary

```
Learn-Code Analysis Complete
================================
Repository:    <REPO_NAME>
Language:      <primary_language>
Modules:       <module_count>
Relationships: <pairs_analyzed>

Output files:
  Detection:     <BASE_PATH>/detection/
  Registry:      <BASE_PATH>/module-registry/
  Analysis:      <BASE_PATH>/module-analysis/
  Relationships: <BASE_PATH>/relationships/
  Onboarding:    <BASE_PATH>/synthesis/ONBOARDING.md

Workflow:      <BASE_PATH>/workflow/learn-code_<REPO_NAME>.json
```

### Suggest next steps

- Read the onboarding guide: `cat <BASE_PATH>/synthesis/ONBOARDING.md`
- View the dependency graph: `cat <BASE_PATH>/relationships/dependency-graph.json`
- Query the codebase: `/code-learner:query-code "your question" --repo <REPO_PATH>`
