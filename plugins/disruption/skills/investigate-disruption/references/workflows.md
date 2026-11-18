# Disruption Workflows

The canonical definitions of the disruption workflows. The `investigate-disruption` skill runs them in Claude Code; an orchestrator such as Chai runs the same sequences one skill per turn. Each step is one skill, invoked natively, with the state file passed along. ⏸ marks a checkpoint: the skill ends its turn with a `disruption-checkpoint` block and the user chooses the next step.

## Choosing a workflow

| Request | Workflow |
|---|---|
| Prow URL(s), asking why they were disrupted | **W1. Explain runs** |
| When did disruption start, get worse, or improve on a series | **W2. Find onset** |
| A `DisruptionRegression*` alert or a Grafana disruption dashboard to investigate, or "what made it worse?" | **W3. Investigate regression** |
| Two groups of runs the user supplied ("compare these good runs to these bad ones") | **W4. Compare cohorts** |
| "What is disrupting this series right now?" or "just analyze the disrupted runs" | **W5. Sample current disruption** |
| "What landed between payload A and B that could affect this backend?" | **W6. What changed** |
| Ambiguous ("look at disruption for 4.22 aws") | Ask: **When did it start?** (W2) / **What made it worse?** (W3) / **Why are these runs disrupted?** (W1 or W5) |

A regression investigation starts with the trend because an alert compares against a baseline: the runs worth analyzing are the ones on each side of the change, not the worst recent runs.

## Sequences

| Workflow | Steps |
|---|---|
| **W1. Explain runs** | `disruption-analyze-run` ⏸ → `disruption-known-issues` ⏸ → report |
| **W2. Find onset** | `disruption-trend` ⏸ → offer W3 ("find out why") |
| **W3. Investigate regression** | `disruption-trend` ⏸ → `disruption-find-runs` (cohorts-around) ⏸ → `disruption-analyze-run` (both cohorts) ⏸ → `disruption-compare-cohorts` ⏸ → `disruption-change-suspects` ⏸ → `disruption-known-issues` ⏸ → verdict and report |
| **W4. Compare cohorts** | `disruption-find-runs` (validate, cohorts kept as given) ⏸ → `disruption-analyze-run` ⏸ → `disruption-compare-cohorts` ⏸ → `disruption-change-suspects` ⏸ → `disruption-known-issues` ⏸ → verdict and report |
| **W5. Sample current disruption** | `disruption-find-runs` (sample-disrupted) ⏸ → `disruption-analyze-run` ⏸ → `disruption-known-issues` ⏸ → report, labelled as explaining runs, **not** a regression |
| **W6. What changed** | `disruption-change-suspects` alone |

**Controls (W3).** A control reruns `disruption-trend` with one field changed and `--control <name>`, recorded under `controls` in the state file without touching the investigated trend:

- **Platform control** (`--platform <other>`): offered at the W3 `disruption-compare-cohorts` and `disruption-change-suspects` checkpoints when a candidate or suspect is platform-specific. It is the only evidence that can support a platform-specific cause. It compares the control with the investigated trend's transitions, so W4, which has no trend, does not offer it: a W4 verdict leaves any platform-specific candidate open and says so.
- **Release control** (`--release <compare_release>`): offered at the trend checkpoint when the onset is before the window or there is no transition, for alerts that compare against a previous release.

Controls are never run by `--auto`; they spend the shared Sippy budget, so each one answers a question someone asked.

The checkpoints that need the user's judgment most are the trend (is this the right transition?) and the cohorts (are these the right runs?). After `disruption-analyze-run`, `disruption-compare-cohorts`, and `disruption-change-suspects`, the checkpoint can be a one-line progress note with a **[Change]** option when the default next step is obvious.

## Moving between workflows

At any checkpoint the user can switch, and the state file carries over:

- W2 → W3 to ask why.
- W3 → W5 when the trend shows no credible transition (`shape: none`), or the user only wants the current disruption explained. The investigation is still a regression investigation: the report keeps a verdict (see Verdicts).
- W3 or W4 → W1 to deep-dive one run.
- W5 → W3 when the user wants to know what made it worse.
- Any → W6 when a suspect component or payload range comes up.

## Running without pauses

`--auto` (or "just run it") runs the whole workflow without stopping at checkpoints, for batch use and evals. Each skill records the default it chose and why. Defaults: the strongest practical increase for the trend; `cohorts-around` with 5 runs per side; compare the cohorts; search for changes behind the strongest new or more-impact candidate; search Jira. Filing or editing Jira always waits for the user.

## Verdicts (W3, W4)

Every regression investigation ends with exactly one of these, at the top of the report:

- **Regression explained:** a candidate changed at the transition (new, or pre-existing with more impact), its mechanism is demonstrated in the after cohort and absent or weaker in the before cohort, and a change suspect or tracked fix accounts for it.
- **Partially explained:** the mechanism is demonstrated but the triggering change is not identified, or a change is identified but its mechanism is not demonstrated in the runs.
- **Regression cause unresolved:** the evidence explains the disrupted runs but not the increase: every candidate is pre-existing and unchanged, or the cohorts do not show the change. Say exactly this, and list the hypotheses still open with what would test each.

An investigation that started as W3 and switched to W5 (no transition in the window) still ends with a verdict. It is normally **regression cause unresolved, no transition in the window**: the runs analyzed show what disrupts the series now, not what changed. Say whether the release control was run and what it showed (the gap to `compare_release` is current, or not visible now). Use explained or partially explained only when the evidence meets their definitions above.

Never upgrade a related Jira card, a shared symptom, or the alert's platform into an explanation.

## Onset results (W2)

The trend's onset is one of: a date with its change window, several candidate dates, a gradual drift, sporadic disruption with no start, no disruption, or **started before the window**, with an offer to widen it (up to 90 days). The window's first day is never the onset.

## State and files

One investigation directory holds everything: `.work/disruption-analysis/<YYYY-MM-DD>-<short-slug>/`.

| File | Written by |
|---|---|
| `investigation.json` (`series`, `trend`, `controls`, `cohorts`, `comparison`, `jira`) | the scripts of each skill |
| `control-<name>-runs.json` | `disruption-trend --control` |
| `trend-runs.json` | `disruption-trend` |
| `runs/<build_id>/` (timelines, `parsed.json`, `analysis.md`) | `disruption-analyze-run` |
| `comparison.md` | `disruption-compare-cohorts` |
| `suspects.md` | `disruption-change-suspects` |
| `known-issues.md` | `disruption-known-issues` |
| `<backends>-analysis.md` | the final report (`report-guide.md`) |

Every skill accepts its inputs inline too (alert text, Prow URLs, payload tags), so a lost session or workspace can resume from the last checkpoint's summary without the files.

## For orchestrators (Chai)

- Run one skill per turn, invoked natively by name. Pass the state file path and the user's latest choice in every request.
- Each turn ends with a fenced `disruption-checkpoint` block: `stage`, `state_file`, `summary`, and `next`. Relay the summary and offer `next` as choices; map the user's choice to the next skill.
- Keep the Jira boundary on every turn: search only; filing a card is the orchestrator's job, with the user.
- Relay verdicts as given. If a skill says the cause is unresolved, or the onset is before the window, say so.
