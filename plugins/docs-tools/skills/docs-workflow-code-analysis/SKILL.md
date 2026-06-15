---
name: docs-workflow-code-analysis
description: "Run code-learner analysis on a source repository for the docs orchestrator workflow. Dispatches a subagent to run learn-code, keeping the heavy orchestration out of the main context. Produces ONBOARDING.md, module registry, per-module summaries, and cross-module relationship data."
argument-hint: --repo <path> --ticket <TICKET> --output-dir <path>
allowed-tools: Read, Write, Bash, Agent, Glob, Grep
---

# docs-workflow-code-analysis

Orchestrator step skill that wraps `learn-code` to analyze a source repository and produce structured code understanding for downstream documentation steps.

## Arguments

| Flag | Required | Description |
|---|---|---|
| `--repo` | Yes | Path to the cloned source repository |
| `--ticket` | Yes | JIRA ticket ID |
| `--output-dir` | Yes | Base output directory (`.agent_workspace/<ticket>/code-analysis/`) |

## Execution

### 1. Validate inputs

- Verify `--repo` directory exists and is a git repository
- Verify `--output-dir` parent exists; create output directory if needed

### 2. Check for cached analysis

Check if learn-code output already exists:

```bash
ls "${REPO}/.agent_workspace/"*/synthesis/ONBOARDING.md 2>/dev/null
```

If an `ONBOARDING.md` exists under any `.agent_workspace/<repo-name>/synthesis/` directory, the analysis was already completed. Locate the corresponding base directory (the parent of `synthesis/`) and copy cached results to `--output-dir`:

```bash
# Find the learn-code base directory containing the cached analysis
LEARN_CODE_BASE="$(dirname "$(dirname "$(ls "${REPO}/.agent_workspace/"*/synthesis/ONBOARDING.md 2>/dev/null | head -1)")")"

cp "${LEARN_CODE_BASE}/synthesis/ONBOARDING.md" "${OUTPUT_DIR}/"
cp "${LEARN_CODE_BASE}/detection/detection.json" "${OUTPUT_DIR}/detection.json" 2>/dev/null
cp "${LEARN_CODE_BASE}/module-registry/registry.json" "${OUTPUT_DIR}/registry.json" 2>/dev/null
mkdir -p "${OUTPUT_DIR}/summaries" "${OUTPUT_DIR}/relationships"
cp "${LEARN_CODE_BASE}/module-analysis/"*.json "${OUTPUT_DIR}/summaries/" 2>/dev/null
cp "${LEARN_CODE_BASE}/relationships/"*.json "${OUTPUT_DIR}/relationships/" 2>/dev/null
```

Skip to step 4.

### 3. Dispatch learn-code subagent

**You MUST use the Agent tool** to run learn-code in an isolated subagent. Do NOT invoke `Skill: learn-code` inline — that would load 850+ lines of skill text plus all intermediate orchestration into the main context.

```
Agent:
  description: "Run learn-code analysis on <REPO>"
  prompt: |
    Run the learn-code skill to analyze the source repository.

    Skill: learn-code, args: "<REPO>"

    After learn-code completes, report the location of the output files
    (ONBOARDING.md, registry.json, detection.json, summaries/, relationships/).
```

After the agent completes, locate the learn-code output. Learn-code stores results in `${REPO}/.agent_workspace/<repo-name>/`. Copy the analysis output to the step's output directory:

```bash
# Find the learn-code output directory
LEARN_CODE_BASE="$(dirname "$(dirname "$(ls "${REPO}/.agent_workspace/"*/synthesis/ONBOARDING.md 2>/dev/null | head -1)")")"

cp "${LEARN_CODE_BASE}/synthesis/ONBOARDING.md" "${OUTPUT_DIR}/"
cp "${LEARN_CODE_BASE}/detection/detection.json" "${OUTPUT_DIR}/detection.json" 2>/dev/null
cp "${LEARN_CODE_BASE}/module-registry/registry.json" "${OUTPUT_DIR}/registry.json" 2>/dev/null
mkdir -p "${OUTPUT_DIR}/summaries" "${OUTPUT_DIR}/relationships"
cp "${LEARN_CODE_BASE}/module-analysis/"*.json "${OUTPUT_DIR}/summaries/" 2>/dev/null
cp "${LEARN_CODE_BASE}/relationships/"*.json "${OUTPUT_DIR}/relationships/" 2>/dev/null
```

If `ONBOARDING.md` is not found after the agent completes, mark the step as `failed` and report the error.

### 4. Write step-result.json

Read the analysis data and write the sidecar:

```json
{
  "schema_version": 1,
  "step": "code-analysis",
  "ticket": "<TICKET>",
  "completed_at": "<ISO 8601>",
  "module_count": "<count from registry.json>",
  "relationship_count": "<count from relationships/>",
  "languages_detected": ["<from detection.json>"],
  "repo_path": "<absolute path to repo>"
}
```

### 5. Report completion

Print summary:
```
Code analysis complete:
- Modules: <N>
- Relationships: <N>
- Languages: <list>
- Output: <output-dir>
```
