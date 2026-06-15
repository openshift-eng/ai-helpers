---
name: docs-workflow-pr-analysis
description: "Run PR/MR analysis for the docs orchestrator workflow. Dispatches a subagent to run understand-pull-request, keeping the heavy orchestration out of the main context. Produces a structured PR-ANALYSIS.md. Conditional on has_pr — skipped when no PR URL is available."
argument-hint: --pr <url> --repo <path> --ticket <TICKET> --output-dir <path>
allowed-tools: Read, Write, Bash, Agent, Glob, Grep
---

# docs-workflow-pr-analysis

Orchestrator step skill that wraps `understand-pull-request` to analyze a specific PR/MR and produce change-specific documentation context.

## Arguments

| Flag | Required | Description |
|---|---|---|
| `--pr` | Yes | PR/MR URL (GitHub or GitLab) |
| `--repo` | Yes | Path to the cloned source repository |
| `--ticket` | Yes | JIRA ticket ID |
| `--output-dir` | Yes | Base output directory (`.agent_workspace/<ticket>/pr-analysis/`) |

## Execution

### 1. Validate inputs

- Verify `--pr` is a valid GitHub or GitLab PR/MR URL
- Verify `--repo` directory exists
- Create `--output-dir` if needed

### 2. Dispatch understand-pull-request subagent

**You MUST use the Agent tool** to run understand-pull-request in an isolated subagent. Do NOT invoke `Skill: understand-pull-request` inline — that would load 570+ lines of skill text plus all intermediate orchestration into the main context.

Check if learn-code output exists from a prior code-analysis step:

```bash
CODE_ANALYSIS_DIR="$(dirname "${OUTPUT_DIR}")/code-analysis"
ls "${CODE_ANALYSIS_DIR}/ONBOARDING.md" 2>/dev/null
```

Build the agent prompt with or without learn-code context:

```
Agent:
  description: "Analyze PR: <PR_URL>"
  prompt: |
    Run the understand-pull-request skill to analyze this PR/MR.

    Skill: understand-pull-request, args: "<PR_URL> --repo <REPO>"

    [If learn-code analysis exists at CODE_ANALYSIS_DIR:]
    Learn-code analysis is available at <CODE_ANALYSIS_DIR>. The skill
    will use it for richer module-level context.

    After the skill completes, report the location of the output files
    (PR-*-ANALYSIS.md and any pr-context.json).
```

After the agent completes, copy the PR analysis output to the step's output directory:

```bash
# Find the understand-pull-request output — it writes to .work/ or the repo's .agent_workspace/
# Look for PR-*-ANALYSIS.md in the agent's output locations
find "${REPO}" -name "PR-*-ANALYSIS.md" -newer "${OUTPUT_DIR}" 2>/dev/null | head -1
```

Copy the found files:
- `PR-<N>-ANALYSIS.md` — Structured change analysis document
- `pr-context.json` — PR metadata and per-module change data (if produced)

If `PR-*-ANALYSIS.md` is not found after the agent completes, mark the step as `failed` and report the error.

### 3. Write step-result.json

```json
{
  "schema_version": 1,
  "step": "pr-analysis",
  "ticket": "<TICKET>",
  "completed_at": "<ISO 8601>",
  "pr_number": "<N>",
  "pr_url": "<PR URL>",
  "modules_affected": "<count>",
  "platform": "github|gitlab"
}
```

### 4. Report completion

Print summary:
```
PR analysis complete:
- PR: <url>
- Modules affected: <N>
- Platform: <github|gitlab>
- Output: <output-dir>
```
