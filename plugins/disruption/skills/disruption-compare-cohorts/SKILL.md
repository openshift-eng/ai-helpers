---
name: disruption-compare-cohorts
description: Use when deciding what behavior differs between a before and an after cohort of disrupted Prow runs — builds a candidate x cohort matrix from the per-run analyses and classifies each candidate cause as pre-existing and unchanged, pre-existing with more impact, or new. Also compares any set of analyzed runs for shared patterns. Usually one step of a disruption regression investigation (see investigate-disruption).
---

# Disruption Compare Cohorts

This skill answers **what differs** between the runs before a change and the runs after it. A regression is explained by something that changed, not by stress every run shares. It does not find the change in code (`disruption-change-suspects`) or search Jira (`disruption-known-issues`).

## Prerequisites

1. **Python 3.7+.**
2. **The `disruption_common` library**: the `disruption` plugin's `scripts/disruption_common`, installed with the plugin. If it is missing, the script exits and says so. Report the message; do not work around it.
3. **Analyzed runs:** each run's parser output at `{runs_dir}/{build_id}/parsed.json` and its analysis at `{runs_dir}/{build_id}/analysis.md`, both written by `disruption-analyze-run`. Cohorts come from `disruption-find-runs` (`cohorts` in the state file).

The script is in this skill's directory: `${CLAUDE_SKILL_DIR}` in Claude Code, or the directory containing this `SKILL.md` elsewhere.

## Rules shared by the disruption skills

- **Liveness.** A run where `ci-cluster-network-liveness` is disrupted has unreliable disruption data. Do not rest a conclusion on its disruption counts alone; its other signals still count.
- **Platform.** The platform in the alert is where disruption was measured, not evidence of the cause. Every run in both cohorts usually shares it, so it cannot explain a difference between them. Name a platform-specific cause only with evidence: a cloud signal that is new or stronger in the after cohort, or the same jobs on another platform staying flat over the same period.
- **State.** `{investigation_dir}` is the state file's directory; `{runs_dir}` is `{investigation_dir}/runs`.
- **One block.** Do not run another disruption skill yourself. End with the checkpoint below.

## Step 1: Build the matrix

```bash
python3 "${CLAUDE_SKILL_DIR}/compare_cohorts.py" \
  --state-file "{investigation_dir}/investigation.json" --runs-dir "{runs_dir}"
```

Without a state file, pass the parser outputs directly: `--before a.json,b.json --after c.json,d.json`.

Each row is one signal, with how many runs in each cohort show it (`runs/of`) and its median size there:

- `disruption`: disruptions, episodes, waves, and the count per phase on the selected backends.
- `rollout`: static-pod revision rollouts per operator, and how many had disruption inside.
- `during`: context events near disruption windows (concurrent events).
- `run-wide`: the same context sources over the whole run (`run_context`). A clean run has no disruption windows, so only these rows can show that a before run had the same stress without the disruption.

The `suggested` label compares counts only. A run listed as missing `parsed.json` was not analyzed; analyze it or say the comparison is without it.

## Step 2: Classify each candidate

A candidate is a mechanism the run analyses named (for example "second kube-apiserver rollout", "etcd slow fdatasync on master-0", "OVS poll stalls on the source node"), with the matrix rows that measure it. Read `references/cross-run-comparison.md` for how to line up episodes, waves, rollouts, payload pairs, and same-job pairs.

Put every candidate in exactly one class:

| Class | Evidence |
|---|---|
| **Pre-existing, unchanged** | Present in the before cohort about as often and as strongly as in the after cohort. It explains disrupted runs, but not why disruption increased. |
| **Pre-existing, more impact** | Present before, but in more after runs, larger, or now inside disruption episodes where before it was not. Say which of those it is. |
| **New** | Absent from the before cohort and present in most of the after cohort. |
| **Not supported** | Named by a run analysis but the matrix does not show it consistently in the after cohort. |

Rules:

- Judge "present before" from the run-wide rows, not only the `during` rows: a before run with no disruption has no `during` rows at all.
- A symptom shared by both cohorts (CPU pressure, etcd slowness) is pre-existing unless its size or its link to episodes changed. Do not let a familiar symptom stand in for the change.
- With 5 runs per cohort, one run is 20%. Say how many runs each conclusion rests on, and call a difference of one run noise.
- Name what would settle an open candidate: more runs, a deep dive, or the change search.

## Output

Write `{investigation_dir}/comparison.md`: the matrix rows that matter (as printed), then each candidate with its class, the runs it rests on (build IDs linked to Prow), and why. Answer with the candidates by class, new and more-impact first, and the strongest explanation for the increase. If no candidate is new or more impactful, say plainly that the comparison explains the disrupted runs but not the increase.

End the turn with:

````text
```disruption-checkpoint
stage: comparison
state_file: <path to investigation.json>
summary: <one line: the new or more-impact candidates, or "no candidate changed between cohorts">
next:
  - find the change behind <candidate> (disruption-change-suspects)
  - search Jira for <mechanism> (disruption-known-issues)
  - analyze more runs (disruption-find-runs with a larger --per-side, then disruption-analyze-run)
  - deep-dive run <build_id> (disruption-analyze-run)
```
````

List only the options that fit. Then **stop and wait** for the user's choice, unless the request said to run without pausing (`--auto`, or "just run it"); then record the default (find the change behind the strongest new or more-impact candidate; search Jira when there is none) and continue.

## Error handling

- **No cohorts in the state file**: run `disruption-find-runs` first, or pass `--before` and `--after`.
- **A cohort has no parsed run**: analyze the cohort with `disruption-analyze-run` first.
- **Only one cohort analyzed, or runs without cohorts**: there is nothing to compare across. Use `references/cross-run-comparison.md` for patterns across the runs, and say no before/after conclusion is possible.
