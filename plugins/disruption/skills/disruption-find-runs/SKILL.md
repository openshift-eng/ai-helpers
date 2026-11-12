---
name: disruption-find-runs
description: Use when choosing which Prow job runs to analyze for a disruption question — sampling the currently disrupted runs of a series, proposing before/after cohorts around a disruption-trend transition, or checking cohorts the user supplied. To investigate a DisruptionRegression alert or dashboard, start with investigate-disruption; this skill is usually one of its steps.
---

# Disruption Find Runs

This skill answers **which runs** to look at. It does not analyze them. It has three purposes; the request or the workflow names one:

| Purpose | Use when | Script |
|---|---|---|
| `sample-disrupted` | "What is disrupting this series right now?" An alert or dashboard URL, no regression comparison | `find_disruption_runs.py` |
| `cohorts-around` | A regression: before/after cohorts around a transition from `disruption-trend` | `cohorts.py around` |
| `validate` | The user gave their own before and after runs | `cohorts.py validate` |

If the purpose is not clear, ask: "Do you want the currently disrupted runs, or runs from before and after a change?"

## Prerequisites

1. **Python 3.7+** and network access to `sippy.dptools.openshift.org` and `storage.googleapis.com`. Both are public.
2. **The `disruption_common` library**: the `disruption` plugin's `scripts/disruption_common`, installed with the plugin. If it is missing, the scripts exit and say so. Report the message; do not work around it.

The scripts are in this skill's directory: `${CLAUDE_SKILL_DIR}` in Claude Code, or the directory containing this `SKILL.md` elsewhere. Do not query Sippy or fetch the Grafana URL yourself; the scripts do all of it in one call each.

## Rules shared by the disruption skills

- **Backend names are exact.** Do not shorten `kube-api-new-connections` to `kube-api`, and do not substitute derived probes (`*-localhost-*`, `*-http1-*`, `*-http2-*`, `*-service-network-*`, `*-internal-lb-*`) or `cache-*` backends unless the user named them.
- **Liveness.** A run where `ci-cluster-network-liveness` is disrupted has unreliable disruption data. Say so wherever it appears; do not rest a conclusion on its disruption counts alone.
- **State.** With a state file (`investigation.json`), `{investigation_dir}` is its directory. Without one, create `.work/disruption-analysis/<YYYY-MM-DD>-<short-slug>/investigation.json`.
- **One block.** Do not run another disruption skill yourself. End with the checkpoint below; chaining is the caller's job.

## Purpose: sample-disrupted

Read `references/run-discovery.md` and follow it. It runs `find_disruption_runs.py` once with the alert text or dashboard URL unchanged, presents the candidate table, and collects the user's selection. It picks runs across the outlier and percentile-tail tiers so the sample explains what drives the dashboard line.

These runs explain current disruption. They are not a before/after comparison, so they cannot by themselves say why disruption got worse. Say that when the request was about a regression, and offer `cohorts-around` instead.

## Purpose: cohorts-around

Run `disruption-trend` first; this purpose reads its per-run records from the state file and makes no Sippy request.

```bash
python3 "${CLAUDE_SKILL_DIR}/cohorts.py" around \
  --state-file "{investigation_dir}/investigation.json" \
  [--transition N | --at 2026-11-04T10:00:00Z] [--per-side 5] [--window-days 7]
```

- Without `--transition` or `--at`, it uses the strongest practical increase from the trend. Use `--transition N` (an index into `trend.transitions`) or `--at` when the user picked a different point.
- Each cohort comes from jobs that ran on both sides, nearest the step, at most one run per launch batch, so the two cohorts differ in time, not in job mix. Runs with liveness disruption or missing data are left out and counted.
- The cohorts are not chosen for high or low disruption. A before run with some disruption is expected: the baseline does not have to be 0s. The script prints each cohort's median and max next to its whole side's median and P95.
- It reads each chosen run's `prowjob.json` for its payload pair. Add `--no-payloads` only if GCS is unreachable.

Then judge the proposal and say what you see:

- Every comparability note the script printed, in plain words. Jobs only on one side are not in the cohorts; name them, because a new job can be the change.
- Whether the after cohort shows the change. If its median is not above the before cohort's, the cohorts may not capture the regression; offer a larger `--per-side`, a different transition, or `--window-days`.
- For upgrade jobs, the payload pairs: after runs that tested a payload no newer than a before run mean a payload change does not separate the cohorts.

## Purpose: validate

Keep the user's cohorts exactly as given. Do not add, drop, or swap runs; only report what makes them hard to compare.

```bash
python3 "${CLAUDE_SKILL_DIR}/cohorts.py" validate \
  --before "<url>,<url>" --after "<url>,<url>" \
  [--backends <exact names> | --state-file "{investigation_dir}/investigation.json"]
```

The backends come from `--backends` or the state file's series. If neither is available, ask which backends the comparison is about. The script reads each run's `prowjob.json` (job, start time, payload pair) and its disruption seconds from Sippy, then notes: jobs in only one cohort, mixed releases, cohorts that overlap in time, payloads that do not separate them, liveness, missing data, and an after cohort that is not more disrupted. Report every note and let the user decide whether to continue.

## Output and checkpoint

`cohorts.py` records the cohorts under `cohorts` in the state file, including `handoff.download_runs` (the `job:build_id` list for `disruption-analyze-run`) and `handoff.prow_urls`. For `sample-disrupted`, give the selected Prow URLs and the exact backends.

Show the cohorts (or the selected runs) as the script printed them, then end the turn with:

````text
```disruption-checkpoint
stage: cohorts | runs
state_file: <path to investigation.json>
summary: <one line: purpose, how many runs per cohort, the main comparability concern>
next:
  - analyze these runs (disruption-analyze-run with the runs above)
  - edit the cohorts (swap or add runs)
  - change the size or window (--per-side, --window-days)
  - pick a different transition or date
```
````

List only the options that fit. Then **stop and wait** for the user's choice, unless the request said to run without pausing (`--auto`, or "just run it"); then record the default (analyze these runs) and continue.

## Error handling

- **No runs file** (`cohorts-around`): run `disruption-trend` with the same state file first.
- **No usable runs on one side**: widen `--window-days` or pick another transition. Report the window that was tried.
- **No practical increase**: the trend found no step to compare around. Offer `sample-disrupted` or ask for a date (`--at`).
- **Sippy or GCS failures** (`validate`): the notes say which runs have unknown seconds or payloads. Unknown is not zero; say so.
- For `sample-disrupted`, the error cases (missing release or backend, no Sippy results, `master_nodes_updated` with no field) are in `references/run-discovery.md`.
