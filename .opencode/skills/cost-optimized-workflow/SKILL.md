---
name: cost-optimized-workflow
description: Applies cost-aware model selection, subagent delegation, concise handoffs, RTK output filtering, and deterministic verification. Use for OpenCode coding, planning, debugging, review, research, or model-routing tasks.
---

# Cost-Optimized OpenCode Workflow

Use the cheapest reliable path while keeping reasoning and final decisions with a capable primary model.

## Model Policy

Use the provider/model IDs available in the current installation. The following is a reference policy, not a requirement; verify availability with `opencode models`.

- Normal implementation and edits: a cost-efficient reasoning model such as GPT-5.6 Luna.
- Planning and architecture: a stronger balanced reasoning model such as GPT-5.6 Terra.
- Mechanical execution: Gemini Flash Lite or another reliable low-cost model.
- Synthesis after delegated evidence: Claude Sonnet or an equivalent balanced model.
- Difficult architecture, security, or unresolved debugging: GPT-5.6 Sol or the strongest approved model.
- Provider failure fallback: an approved secondary provider; do not assume a subscription model is unlimited.

## Delegation Rules

Classify each request before acting:

- Mechanical-only work such as tests, builds, searches, logs, diff summaries, and extraction should be delegated to a cheap read-only executor.
- First-pass reviews may use a cheap read-only reviewer, but the primary agent owns the final review decision.
- Mixed implementation requests should delegate fact gathering and verification, then keep interpretation, design, edits, and final verification in the primary session.
- Never delegate security decisions, architecture decisions, subtle debugging, or production-impacting edits as a first step.

Require every delegated agent to return only:

```text
RESULT: PASS, FAIL, or BLOCKED
EVIDENCE: filenames, line numbers, errors, and exit codes
RISKS: false positives, missing coverage, or environment limits
NEXT: one concrete action for the primary agent
```

Do not return raw logs or large command output to the primary context.

## Context and Caching

- Keep stable instructions and repository conventions at the beginning of prompts.
- Put dynamic requests and per-run metadata last.
- Use deterministic serialization for generated JSON and reports.
- Use a fresh session when changing to an unrelated task.
- Keep global instructions short; put specialized guidance in skills.

## RTK

Use RTK when it is installed and configured for OpenCode. It filters Bash/Shell output before the model receives it.

- Prefer normal commands when the RTK OpenCode plugin transparently rewrites them.
- Use `rtk read`, `rtk grep`, `rtk find`, `rtk git diff`, and `rtk test` explicitly when native tools or command output would be large.
- Treat RTK savings as command-output reduction, not an equivalent percentage reduction in total API cost.
- Preserve access to full output when a filtered failure is insufficient; use the tee path or rerun a focused command.

## Verification

- Run deterministic tests, linters, type checks, and formatters after edits.
- Filter routine output, but inspect full failure details when diagnosing a real issue.
- Do not treat model agreement as proof of correctness or security.
- Record model, task type, outcome, and rework when evaluating routing quality.

## Configuration Notes

OpenCode does not provide a universal deterministic model router in its standard configuration. Automatic behavior is normally coordinator-based: the primary model classifies the task and invokes configured subagents. A hard router requires a custom plugin or external launcher and should be evaluated for context, latency, and failure-mode costs.

Each teammate must configure their own provider credentials, model IDs, project paths, permissions, and RTK integration. Never copy API keys or personal absolute paths into shared configuration.
