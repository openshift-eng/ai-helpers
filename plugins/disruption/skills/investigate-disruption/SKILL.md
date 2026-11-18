---
name: investigate-disruption
description: Use when investigating OpenShift CI disruption end to end — a DisruptionRegression alert, a Grafana disruption dashboard URL, Prow job runs, "when did disruption start", "what made disruption worse", or "what changed between these payloads". Picks the workflow, runs the disruption skills in order with a checkpoint between them, and assembles the final report with a verdict.
---

# Investigate Disruption

The entry point for disruption questions. It does no analysis itself: it chooses a workflow, runs the building-block skills of the `disruption` plugin in order, stops at their checkpoints so the user can steer, and writes the final report.

| Skill | Answers |
|---|---|
| `disruption-trend` | When did disruption start or change? |
| `disruption-find-runs` | Which runs should we look at? |
| `disruption-analyze-run` | Why was each run disrupted? |
| `disruption-compare-cohorts` | What differs between before and after? |
| `disruption-change-suspects` | What changed that could explain it? |
| `disruption-known-issues` | Is it already tracked? |

## Step 1: Choose the workflow

Read `references/workflows.md`. Classify the request into W1–W6 with its table. If it is ambiguous, ask the user which question they mean (when it started, what made it worse, or why these runs are disrupted) before running anything. A `DisruptionRegression*` alert or a dashboard URL with "investigate this" is W3.

Keep the input exactly as given: the full alert text including every label, the dashboard URL unchanged, and exact backend names. Create the investigation directory first (Step 2 names it; `mkdir -p` it), then write a pasted alert unchanged to `alert.txt` in it with your file-writing tool, and give skills that file, never the text on a command line. Do not open the Grafana URL; it is behind SSO.

## Step 2: Start the investigation state

Create `.work/disruption-analysis/<YYYY-MM-DD>-<short-slug>/investigation.json` (for example `2026-11-11-kube-api-aws-micro`) by passing that path as `--state-file` to the first skill that takes one. Pass the same path to every later skill. Reuse an existing state file when the user continues an investigation. In W1, W5, and W6 no script writes the state file before `disruption-known-issues` records its result, so `series.backends` is never set there: pass the exact backends and the selected runs to each skill inline.

## Step 3: Run the workflow

Run each step of the workflow as its skill. In Claude Code, invoke the skill (for example `disruption:disruption-trend`) with the input and the state file. Where skills cannot invoke other skills (Codex), read that skill's `SKILL.md` and follow it. Do not paraphrase a skill from memory, and do not run its scripts without it.

Every skill ends its turn with a `disruption-checkpoint` block:

- At a ⏸ checkpoint, relay the skill's answer and its `next` options, and **wait for the user's choice**. Then run the step the choice names, which may switch workflows (`references/workflows.md`, "Moving between workflows").
- When the request said to run without pausing (`--auto`, or "just run it"), take each skill's default and say which one it took. Filing or editing Jira still waits for the user.
- Pass forward what the next skill needs: the state file always, plus the user's choice (a transition, edited cohorts, a component).

## Step 4: Verdict and report

Read `references/report-guide.md` and follow it. Assemble the report from the investigation files (`analysis.md` per run, `comparison.md`, `suspects.md`, `known-issues.md`) and the state file; do not redo their analysis. Save it as `{investigation_dir}/{backend_names}-analysis.md`.

- **W3 and W4** end with exactly one verdict from `references/workflows.md`: regression explained, partially explained, or regression cause unresolved. Lead the answer with it. When the evidence explains the disrupted runs but not the increase, the verdict is unresolved; say so plainly and list the open hypotheses.
- **W5** explains the current disrupted runs. Say it is not a regression analysis, and offer W3 if the user wants to know what made it worse. When W5 was reached from W3 (no transition in the window), the request was still a regression: keep the verdict, normally "regression cause unresolved, no transition in the window" (`references/workflows.md`).
- **W2** answers when; offer W3 to find out why.

Never present a related Jira card, a symptom both cohorts share, or the alert's platform as the explanation. A platform-specific cause needs a platform control (`disruption-trend --control`, W3 only); report the controls that were run. In W4 a platform-specific candidate stays open.

## Error handling

- **A skill reports a missing library** (`disruption_common`): the plugin was installed partially. Report the message and stop; every skill needs the whole `disruption` plugin.
- **Missing release or backend** for an alert or dashboard: ask the user for it.
- **Sippy rate limits or lost runs**: the skill says so (`DEGRADED`). Lead with it, and offer to rerun later rather than looping.
- **Jira unavailable**: finish the workflow and say the Jira search was skipped.
