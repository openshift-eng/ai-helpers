---
name: disruption-trend
description: Use when asked when disruption started, got worse, improved, or changed for a disruption backend or series — from a DisruptionRegression alert, a Grafana disruption dashboard URL, or a release plus backend. Builds the per-run disruption time series and locates transitions and onset with stated uncertainty. Usually the first step of a disruption regression investigation.
---

# Disruption Trend

This skill answers **when**: when disruption on a series started, or when it changed. It does not explain why. It builds a time series of per-run disruption seconds for one series, then finds step changes (transitions) and the onset, and states every data limitation.

A series is one release, one or more exact backend names, the Sippy job variants (platform, architecture, topology, network, upgrade type, feature set, OS), and optionally `master_nodes_updated`.

## Prerequisites

1. **Python 3.7+** and network access to `sippy.dptools.openshift.org` and `storage.googleapis.com`. Both are public, so no credentials are needed.
2. **The `disruption_common` library.** It comes with the whole `ci` plugin (Claude Code). A Chai persona must list `supporting_dirs: [lib/disruption_common]` on its `ci` plugin entry. If the library is missing, the script exits and says exactly that. Report the message; do not work around it.

## Inputs

Take one of these, unchanged:

- **A `DisruptionRegression*` alert:** pass the full text, including every label and any `link:` annotation.
- **A Grafana disruption dashboard URL** (`grafana-loki.ci.openshift.org/d/...`): pass it unchanged. Do not open or fetch it, because it is behind SSO.
- **Explicit fields:** `--release` and `--backend` are required. Add `--platform`, `--upgrade-type`, `--architecture`, `--topology`, and `--network` when the user gives them.

Optional inputs:

- **Window:** `--days N`. The default is 30, or the dashboard lookback if that is longer. The maximum is 90, because the public Sippy API only keeps about 90 days of runs. A longer request is capped at 90 and a caveat says so.
- **State file:** `--state-file <path>`, the investigation state shared with the other disruption skills. When none is given, create one at `.work/disruption-analysis/<YYYY-MM-DD>-<short-slug>/investigation.json`.
- **`--auto`:** a workflow asked you not to pause at the checkpoint (see Step 4). This is an instruction to you, not a script flag.

If the release or backend is missing, ask for it. If only a release and backend were given with no platform or upgrade type, say that the series pools every job for that release and backend, because a change in the job mix can look like a regression. Then either ask for the missing fields or continue and keep that caveat in the answer.

Backend names are exact. Do not shorten `kube-api-new-connections` to `kube-api`, and do not substitute derived probes (`*-localhost-*`, `*-http1-*`, `*-http2-*`, `*-service-network-*`, `*-internal-lb-*`) or `cache-*` backends unless the user named them.

## Step 1: Run the series script

The script is `disruption_series.py` in this skill's directory. In Claude Code that is `${CLAUDE_SKILL_DIR}`; elsewhere, it is the directory containing this `SKILL.md`. Run it once, from the working directory where `.work/` should live:

```bash
python3 "<skill-dir>/disruption_series.py" \
  --alert-text "<alert text>" \
  --state-file ".work/disruption-analysis/<id>/investigation.json"
```

Use `--grafana-url "<url>"` instead of `--alert-text` for a dashboard. For explicit fields, use `--release 5.0 --backend kube-api-new-connections --platform gcp --upgrade-type micro`. Add `--days N` when the user asked for a different window.

Run it with a 10-minute command timeout (for example `timeout: 600000` on the Bash tool). A 30-day window usually takes 15–60 seconds, but the Sippy disruption API allows only 25 requests per rolling hour, shared by every user, so the script may wait up to 5 minutes (`--rate-limit-wait`, default 300 seconds) for the limit to free up. Each request covers 500 runs. Progress and rate-limit waits go to stderr. Disruption data is cached under `.work/disruption-analysis/cache/` after every request, so a rerun only fetches runs that are not cached yet. Run the script once; do not loop on it.

After the analysis, the script reads `prowjob.json` from the public GCS bucket for the 20 runs nearest each transition on each side (about 40 small files per transition, 4 at a time, cached) to get each run's initial and target payload. Add `--no-payloads` only if GCS is unreachable.

The table on stdout has the per-bucket run count, nonzero rate, P50/P75/P95, max, job count, and payload range. Then, for each transition: a summary line, a per-job table, the payload findings, and suggested before/after run pairs. The onset and caveats come last. A `DEGRADED:` line under the header means runs were lost to API failures (see Error handling). The full result, including every number referenced below, is in the state file under `trend`, and the per-run records (with `initial_payload` and `target_payload` for the sampled runs) are in `trend.runs_file`.

The values are **per-run peak seconds on the exact selected backends**. They are not the dashboard's percentile line. Say so if you compare them with the alert's numbers.

## Step 2: Judge the transitions

The script finds candidate change points with a Mann-Whitney test, using binary segmentation over the per-run values. `strong` means |z| ≥ 5 and `moderate` means |z| ≥ 4. Under no change, noise stays below about 4. These are candidates, not conclusions. Judge each one:

- **Is it practical?** `practical: false` means the shift is statistically detectable but too small to matter. Mention it at most in passing.
- **Is it consistent across jobs?** Read the per-job table (`per_job.jobs`). It lists every job with at least one run after the step: runs before and after, the job's own before P50/P95, and its after P50 and max. A job whose after P50 is above its own before P95 moved clearly. Jobs marked `small n` have fewer than `per_job.min_runs` runs on a side: use them as supporting evidence, not proof, and say how many runs they rest on. A job with 0 runs before is new after the step and says nothing about a change. A real product change usually moves most jobs of the affected kind (for example every upgrade job) while unrelated jobs stay flat; name which jobs moved and which did not. `per_job.jobs_compared`, `jobs_increased`, and `jobs_decreased` count only jobs with enough runs on both sides.
- **Did the job mix change?** A `job_mix_shift` of 0.3 or more means the set of jobs running changed at that point. The step may come from which jobs ran, not from a product change. Check `per_job` and the bucket table's job counts before calling it a regression.
- **Do the buckets show it?** Look at the bucket rows on both sides of `at`. A real step shows up as a sustained change in nonzero rate or P95 across several buckets, not as one noisy bucket.
- **Which direction?** For a "what made it worse" question, increases matter. A decrease is context, such as a fix landing. Report it, but do not treat it as the regression.

Place the change between `last_run_before` and `first_run_after`. The candidate change window is `between`. Runs are ordered by start time, not by payload.

**Payloads.** `payload_before` → `payload_after` come from Sippy's `release_tag`, which is often empty or from a different stream, so prefer `transitions[].payloads` when it is present. It is read from each sampled run's `prowjob.json` (`RELEASE_IMAGE_INITIAL` and `RELEASE_IMAGE_LATEST`):

- **By target payload:** `newest_target_before` and `oldest_target_after`. With `target_separates: true`, every after-step run tested a newer payload than every before-step run, so report the change as landing between those two payloads. With `false`, `after_on_old_target` after-step runs tested a payload that before-step runs also tested. The step then is not explained by the payload upgraded to alone; check the next point.
- **Upgrade jobs, by initial payload** (`after_upgrades_by_initial`): after-step upgrades are split by whether they started from a payload older than the estimated step payload (`pre_step`) or from it or later (`post_step`), with n, P50, and max. If `pre_step` is high and `post_step` is near the old level, the step depends on the payload upgraded *from*: upgrades that cross the change are disrupted, and upgrades that start after it recover. Say so; it means same-minor upgrade jobs will recover by themselves while jobs that upgrade from an older minor (`5.0 → 5.1`) will not. `version_pairs` gives the same comparison by initial and target minor version, before and after the step.
- Payloads are a sample (the 20 runs nearest the step on each side). `fetch_failed` and `no_payload` count runs whose `prowjob.json` could not be read or names no payload (jobs not started by the release controller). If none of the sampled runs had a payload, fall back to the Sippy payload range and say it is unverified.

Never claim that a run did or did not include a change without its payload pair.

The script's `shape` (`none`, `step`, `multiple`, or `gradual`) is a heuristic. Confirm it against the buckets:

- **step:** one credible transition.
- **multiple:** two or more credible transitions. Report each one. The latest increase is usually what a current alert is about, but say if an earlier one explains more.
- **gradual:** a sustained drift (`trend_rho` of 0.3 or more) with no clean step. Say there is no single transition to compare around.
- **none:** no credible transition in the window. If an alert fired anyway, the likely reasons are:
  - the regression is relative to the previous GA (`compare_release`) and happened before this window, or
  - it is too gradual or too small to locate.

  Say which the data supports, and offer a longer window if the current one is under 90 days.

## Step 3: Judge the onset (for "when did it start?")

Read `trend.onset.status`:

- **`in_window`:** disruption rose from a near-zero baseline (nonzero rate ≤ 10%) at `at`. Give the date, the payload range, and the before and after nonzero rates.
- **`before_window`:** disruption was already present in the earliest runs. **Never report the window's first day as the onset.** Say it started before the window, and offer a longer `--days` if the window is under 90 days. At 90 days, or if a caveat says Sippy returned nothing earlier, say the public data does not reach back far enough.
- **`sporadic`:** occasional disruption throughout, with no sustained start. Say there is no onset to point at.
- **`none`:** no disruption on these backends in the window.
- **`unknown`:** no run had usable disruption data, so the window says nothing about onset. Do not report this as "no disruption". Give the caveats that explain why: disruption data missing, the disruption API unreachable, or every run excluded for liveness disruption.

## Step 4: Report and checkpoint

Write a short answer to the user's question first: when, how confident, and what limits it. Then include:

1. The series line and filters from the table header.
2. The bucket table as the script printed it. For windows longer than about 40 buckets, keep the rows around each transition and summarize the rest.
3. Each credible transition: the change window, payloads (from `payloads` when present), before → after nonzero rate, P50, and P95, and its strength. Link `last_run_before.url` and `first_run_after.url` inline.
4. The per-job table for each credible transition, as printed, and which jobs moved. For upgrade jobs, the payload-pair finding (by target, and by initial payload).
5. The onset, if the question was about when it started.
6. Every caveat from `trend.caveats`, in plain words. Do not drop any. If `trend.degraded` is true, say so in the first paragraph of the answer, not only in the caveats.

Do not guess at causes. This skill establishes when. Explaining why is the job of the `analyze-disruption` skill, which analyzes the runs themselves.

End the turn with a checkpoint block, so a person or an orchestrating persona can choose the next step:

````text
```disruption-checkpoint
stage: trend
state_file: <path to investigation.json>
summary: <one line: shape, the transition or onset with its change window, confidence>
next:
  - analyze the suggested pairs around <at> (analyze-disruption with transitions[].handoff.prow_urls)
  - pick a different transition or date
  - widen the window (--days <N>, at most 90)
  - rerun later to fill runs lost to the disruption API (only when trend.degraded)
  - no credible transition: analyze the currently disrupted runs (analyze-disruption with the same alert or dashboard URL)
```
````

What each `next` option means:

- **Analyze the suggested pairs:** give `analyze-disruption` the Prow URLs in `transitions[].handoff.prow_urls`, unchanged. They are up to three before/after pairs (`handoff.pairs`), each from one job, nearest the step, with at most one run per launch batch, and with runs that show the change preferred (`representative: true`). `handoff.download_runs` is the same runs as `job:build_id` pairs for `download_timelines.py --runs`. Do not filter the runs file by hand. If a pair is marked not representative, or there are no pairs (no job ran on both sides), say so and pick runs from `trend.runs_file` for the jobs that moved in the per-job table.
- **Analyze the currently disrupted runs:** give `analyze-disruption` the same alert text or dashboard URL. Its run finder auto-selects representative disrupted runs from the dashboard window.
- **Rerun later:** the cache keeps every run already fetched, so a rerun after the rate limit frees up (up to an hour) only asks for the lost runs.

List only the `next` options that fit the result. Then **stop and wait** for the user's choice, unless the request said to run without pausing (`--auto`, or "just run it"). In that case, record the default you chose and why: the suggested pairs of the strongest practical increase, or for `none` the option to analyze the currently disrupted runs. Then continue.

## Error handling

- **Missing release or backend:** the script exits with code 1 and names the missing field. Ask the user for it.
- **No runs found:** the filters or window match nothing. Report the filters that were tried and suggest widening `--days` or dropping a filter.
- **`master_nodes_updated` matched nothing:** report the warning. Do not rerun without the filter unless the user agrees.
- **Sippy runs API fails** (connection error, HTTP error, timeout, or malformed reply): the script exits with code 1 and prints the error. If several platforms or other variant values were queried, the message lists every combination that failed. Report it; without runs there is no fallback for this skill.
- **Sippy disruption API fails for some runs** (HTTP 429 rate limit, which allows 25 requests per rolling hour shared by every user, or another error): the script retries 429s with backoff for up to `--rate-limit-wait` seconds in total, then gives up on the remaining runs and continues. Those runs are counted in `trend.runs.fetch_failed` and in their own caveat with the run count, date range, and affected buckets. They are not in the "no disruption data" caveat. `trend.data_loss` has the details. When more than 3% of the window's runs, or of either side of a transition, are lost, `trend.degraded` (and `transitions[].degraded`) is true and the table prints a `DEGRADED:` line. Then:
  - Lead the answer with the loss: how many runs, which dates, and which transitions are degraded. Do not present the result as clean.
  - Offer the "rerun later" option. The cache keeps everything already fetched, so the rerun only requests the lost runs. Do not rerun right away in a loop; the limit frees up over the next hour.
  - If no run has usable data, the onset is `unknown`.
- **`prowjob.json` cannot be fetched for some runs:** a caveat gives the count for each transition. The payload findings use the remaining runs. If no sampled run had a payload, a caveat says the transition cannot be placed by payload; use the Sippy payload range and call it unverified.
- **Library not found:** report the script's message, which names the `supporting_dirs` fix.
