---
name: docs-workflow-planning
description: Create a documentation plan from requirements analysis output. Dispatches the docs-planner agent. Invoked by the orchestrator.
argument-hint: <ticket> --base-path <path>
allowed-tools: Read, Write, Glob, Grep, Edit, Bash, Skill, Agent
---

# Documentation Planning Step

Step skill for the docs-orchestrator pipeline. Follows the step skill contract: **parse args → dispatch agent → write output**.

## Arguments

- `$1` — JIRA ticket ID (required)
- `--base-path <path>` — Base output path (e.g., `.agent_workspace/proj-123`)

## Input

```
<base-path>/requirements/requirements.md
```

## Output

```
<base-path>/planning/plan.md
```

## Execution

### 1. Parse arguments

Extract the ticket ID and `--base-path` from the args string.

Set the paths:

```bash
INPUT_FILE="${BASE_PATH}/requirements/requirements.md"
OUTPUT_DIR="${BASE_PATH}/planning"
OUTPUT_FILE="${OUTPUT_DIR}/plan.md"
mkdir -p "$OUTPUT_DIR"
```

### 2. Dispatch agent

**You MUST use the Agent tool** to invoke the `docs-planner` subagent. Do NOT read the agent's markdown file or attempt to perform the agent's work yourself — the agent has a specialized system prompt and must run as an isolated subagent.

**Agent tool parameters:**
- `subagent_type`: `docs-tools:docs-planner`
- `description`: `Create documentation plan for <TICKET>`

**Prompt** (pass this as the `prompt` parameter to the Agent tool):

> Create a comprehensive documentation plan based on the requirements analysis.
>
> Read the requirements from: `<INPUT_FILE>`
>
> The plan must include:
> 1. Gap analysis (existing vs needed documentation)
> 2. Module specifications (type, title, audience, content points, prerequisites, dependencies)
> 3. Implementation order based on dependencies
> 4. Assembly structure (how modules group together)
> 5. Content sources from JIRA and PR/MR analysis
>
> Save the complete plan to: `<OUTPUT_FILE>`

**[Include only if `<BASE_PATH>/code-analysis/ONBOARDING.md` exists]** Append the following paragraph to the prompt:

> ## MANDATORY: Scope gating by code analysis
>
> **You MUST read** `<BASE_PATH>/code-analysis/ONBOARDING.md` and `<BASE_PATH>/code-analysis/registry.json` before creating any module specifications. These files contain structured analysis of the source repository produced by code-learner.
>
> **This is not optional. The module registry must inform your planning.**
>
> Use the module registry's `onboarding_priority` field to scope documentation:
> - **read-first** modules: create full module specifications. These are the core modules that new developers must understand first
> - **read-second** modules: create summary module specifications. Include purpose and key APIs but less detail than read-first modules
> - **skip** modules: **Do NOT create module specifications.** These are utility, test, or generated modules that don't warrant standalone documentation. If relevant to a read-first module, mention them briefly in that module's context
>
> Use the `public_api`, `dependencies`, and `data_flow` fields from module summaries in `<BASE_PATH>/code-analysis/summaries/` to inform content points and prerequisites in each module specification.
>
> **Self-check before writing the plan:** Count your module specifications. Verify that no skip-priority module has a full module specification — if any does, remove it or downgrade to a brief mention within a related module.

**[Include only if `<BASE_PATH>/pr-analysis/` exists]** Also append:

> ## PR change context
>
> Read the PR analysis from `<BASE_PATH>/pr-analysis/PR-*-ANALYSIS.md`. Focus documentation on modules listed in the "Changes by Module" section — these are the modules directly affected by the code changes that triggered this documentation work. Prioritize these modules for full specifications regardless of their onboarding_priority.

### 3. Verify output

After the agent completes, verify the output file exists at `<OUTPUT_FILE>`.

If no output file is found, report an error.

**[If `<BASE_PATH>/code-analysis/registry.json` exists]** Cross-check the plan against the registry: read the module registry and verify that no skip-priority module has a full module specification in the plan. If any skip module was given a full spec, log a warning: "Plan includes full specs for skip-priority module(s): <list>. These are typically utility modules that don't warrant standalone documentation." This is a warning, not a blocker.

### 4. Write step-result.json

Read `<OUTPUT_FILE>` and count the number of module specifications. Count each occurrence of:

- Level-3 headings (`###`) whose text begins with `Module:`
- Numbered or bulleted list items within the "Module Specifications" section that start with `Module:`

Ignore headings or list items outside the "Module Specifications" section, and skip items inside code blocks or blockquotes. Treat duplicate module titles as separate modules (no deduplication). This count becomes the `module_count` field.


Write the sidecar to `<OUTPUT_DIR>/step-result.json`:

```json
{
  "schema_version": 1,
  "step": "planning",
  "ticket": "<TICKET>",
  "completed_at": "<current ISO 8601 timestamp>",
  "module_count": <number of modules in the plan>
}
```
