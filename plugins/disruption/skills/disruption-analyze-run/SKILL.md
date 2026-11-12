---
name: disruption-analyze-run
description: Use when explaining why specific Prow CI job runs were disrupted — downloads their interval/timeline data and analyzes disruption episodes, waves, revision rollouts, and concurrent etcd, OVS, CPU, and cloud signals per run, with audit and etcd logs when needed. Takes Prow URLs or job:build_id pairs. Usually one step of a disruption investigation (see investigate-disruption).
---

# Disruption Analyze Run

This skill answers **why these runs were disrupted**: the mechanism in each run. It does not decide whether disruption got worse, compare cohorts, or search Jira; other disruption skills do that.

## Prerequisites

1. **gcloud CLI** (`which gcloud`). The `test-platform-results-public` bucket is public. Do not run `gcloud auth login`, and do not change the user's gcloud config. `download_timelines.py` sets `CLOUDSDK_AUTH_DISABLE_CREDENTIALS=true` on each gcloud subprocess, and any direct `gcloud storage` command here uses the same variable. Anonymous access still needs network execution when the command runs in a sandbox.
2. **Python 3.7+.**
3. **The `disruption_common` library**: the `disruption` plugin's `scripts/disruption_common`, installed with the plugin. If it is missing, the scripts exit and say so. Report the message; do not work around it.

The scripts are in this skill's directory: `${CLAUDE_SKILL_DIR}` in Claude Code, or the directory containing this `SKILL.md` elsewhere.

## Rules shared by the disruption skills

- **Backend names are exact.** Pass them as `--backends` unchanged. Do not shorten `kube-api-new-connections` to `kube-api`, and do not substitute derived probes (`*-localhost-*`, `*-http1-*`, `*-http2-*`, `*-service-network-*`, `*-internal-lb-*`) or `cache-*` backends unless the user named them.
- **Liveness.** A run where `ci-cluster-network-liveness` is disrupted has unreliable disruption data. Keep it, say so, and do not rest a conclusion on its disruption counts alone.
- **Platform.** The platform in the alert or job name is where disruption was measured, not evidence of the cause. Name a platform-specific cause only when the run evidence shows a platform mechanism (a cloud metric, a cloud API error, a platform-only component).
- **State.** With a state file (`investigation.json`), `{investigation_dir}` is its directory; otherwise create `.work/disruption-analysis/<YYYY-MM-DD>-<short-slug>/`. Runs go under `{runs_dir}` = `{investigation_dir}/runs`.
- **One block.** Do not run another disruption skill yourself. End with the checkpoint below.

## Step 1: Inputs

- **Prow URLs** (`prow.ci.openshift.org` or `gcsweb-ci`), one or more. Or `job:build_id` pairs, such as `cohorts.handoff.download_runs` from `disruption-find-runs` in the state file.
- **Backends** (`--backends`): the exact names. Take them from the request, or from the state file's `series.backends`. Without either, analyze every backend that shows disruption and say so.
- When the runs are cohorts (before/after), keep each run's cohort; the analysis of each run is the same, but the checkpoint says which cohort each run is in.

From each Prow URL take the job name and build ID: the last two path segments after `/logs/`. The job name is letters, digits, `.`, `_`, and `-`, and the build ID is all digits; skip and report anything else rather than putting it in a shell command. Presubmit runs (`/pr-logs/pull/...`) are not supported: the download reads only `/logs/` artifacts, so say so and skip them. Prow URLs may say `origin-ci-test`; the bucket is always `test-platform-results-public`.

## Step 2: Download timelines

Read `references/artifacts.md` and follow **Timeline download**: one `download_timelines.py` call for every run, with `--output-dir {runs_dir}`. When the runs are before/after cohorts, add `--gather`: `disruption-compare-cohorts` compares component versions from each run's `releaseinfo.json`, and the revision-trigger check needs the events and configmaps. On exit 2, continue with the runs that downloaded; on exit 1, stop and report each run's error.

Keep each run's payload pair (initial → target) from the output. For upgrade jobs, make no claim that depends on which payload a run started from or upgraded to without that run's pair; if it is unknown, say so.

## Step 3: Analyze the timelines

For every run, save the parser's full JSON (the cohort comparison reads it) and print its one-line summary, in one loop:

```bash
for run in '{job_1}:{build_id_1}' '{job_2}:{build_id_2}'; do
  job="${run%%:*}"; build_id="${run##*:}"; dir="{runs_dir}/${build_id}"
  if python3 "${CLAUDE_SKILL_DIR}/parse_disruption.py" "${dir}"/logs/e2e-timelines_spyglass_*.json \
      --job-name "${job}" --build-id "${build_id}" --backends '{exact_backends}' --format json > "${dir}/parsed.json.tmp"; then
    mv "${dir}/parsed.json.tmp" "${dir}/parsed.json"
    python3 "${CLAUDE_SKILL_DIR}/parse_disruption.py" "${dir}"/logs/e2e-timelines_spyglass_*.json \
      --job-name "${job}" --build-id "${build_id}" --backends '{exact_backends}' --format summary
  else
    rm -f "${dir}/parsed.json.tmp"; echo "${build_id}: the parser failed; no parsed.json written" >&2
  fi
done
```

A run without timelines gets no `parsed.json`, so the cohort comparison reports it as missing instead of reading an empty file.

Then read `references/timeline-analysis.md` and follow 3.2 through 3.4 (blast radius, deep-dive of the runs that need it, and how to read each signal).

Compare runs by the parser's episodes and waves (for example "3 episodes in 1 wave" against "6 episodes in 2 waves (3+3)"), not by the disruption count. Check which static-pod revision rollout (`rollouts:`) each wave falls inside. If some runs have an extra rollout that others do not, Step 4 is needed: follow **4.3 Revision Trigger**.

## Step 4: Deep dive (only when Step 3 is not enough)

Only if the parser output does not establish the mechanism, read the **Deep-dive artifact download** section of `references/artifacts.md` and follow it: audit logs, etcd logs, the revision trigger (`revision_triggers.py`), and PromQL for live clusters. Prefix any direct `gcloud storage` command with `CLOUDSDK_AUTH_DISABLE_CREDENTIALS=true`.

When a wave sits inside a revision rollout that comparison runs do not have, run `revision_triggers.py` on a run with the rollout and one without it to find the write that started the revision. Use the script rather than reading events.json or configmaps.json by hand. The commits behind that write are the `disruption-change-suspects` skill's job: record the component and both runs for it (4.4).

## Step 5: Additional checks

`references/timeline-analysis.md` section 5 has the node-shutdown and endpoint-slice checks. Do them when disruption coincides with node events.

## Output

Write one short analysis per run to `{runs_dir}/{build_id}/analysis.md`:

- the job, build ID (linked to Prow), cohort if any, payload pair, and liveness status;
- the episodes and waves on the selected backends, and the phase;
- the **mechanism**: what the evidence shows caused each wave, with the evidence linked inline (link shapes and payload rules: `references/evidence-links.md`). Say "not determined" when it is not, and what was checked;
- the other disrupted backends (blast radius), briefly.

Then answer with a compact table (one row per run: build ID, cohort, episodes/waves, mechanism, liveness) and the mechanisms in a few sentences. When there are several runs, say which mechanisms repeat across runs and which appear once. Do not compare before and after cohorts here; that is `disruption-compare-cohorts`.

End the turn with:

````text
```disruption-checkpoint
stage: run-analysis
state_file: <path to investigation.json>
summary: <one line: runs analyzed, the recurring mechanism, anything undetermined>
next:
  - compare the cohorts (disruption-compare-cohorts)
  - look for the change behind <component> between <run without> and <run with> (disruption-change-suspects)
  - search Jira for this mechanism (disruption-known-issues)
  - deep-dive run <build_id>
```
````

List only the options that fit: comparing cohorts only when the runs are cohorts, the change search only when a component is implicated. Then **stop and wait** for the user's choice, unless the request said to run without pausing (`--auto`, or "just run it"); then record the default (compare the cohorts when there are cohorts, otherwise search Jira) and continue.

## Error handling

1. **No disruption found**: report that the run is clean on these backends. This is a valid result.
2. **Interval files not found**: a critical error for that run. Report it and continue with the others.
3. **Audit or etcd logs missing**: note it and continue with the available data.
4. **gcloud errors**: report the run's `error` text (credential-like values are removed). A sandbox that blocks the network is separate from an auth failure; request network execution and run the downloader again. Do not run `gcloud auth login`.

## Performance

- One downloader call for every run; it works in parallel.
- Use `--format summary` to triage many runs before deep-diving, so large JSON stays in files.
- Filter audit logs by time range rather than scanning whole files.
