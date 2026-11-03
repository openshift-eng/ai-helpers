# OCP Memory Requests Plugin

Keep OpenShift **control-plane operator memory requests** accurate automatically,
replacing one-off manual fixes (like OCPBUGS-131892) with a recurring,
data-driven check.

## Overview

Single-replica ("singleton") control-plane operator pods carry a configured
memory **request**. Over time these requests drift from what the operators
actually use. This plugin measures observed post-upgrade usage from CI, compares
it to the configured request, and when they have drifted apart it files an
**agent-ready OCPBUGS** that CHAI solves via PR for the team to review.

It is built to run **headless in CHAI on a monthly cadence** with no human
approvals — humans review the resulting PR, not the run.

## How it works

1. **Measure** — query the `ci_data_autodl` `control_plane_singleton_pods` table
   (via the `bigquery-ci-data` plugin) for each operator's pre-suite (`Start`)
   memory use, across all CI runs on the current release over the last 30 days,
   using each run's latest (post-upgrade) snapshot.
2. **Compare** — take the **90th percentile across job runs** of pre-suite
   (at-rest) usage and add **~10% headroom** per the `openshift/enhancements`
   convention. This at-rest basis is deliberate and differs from the convention's
   during-suite percentile, so numbers can differ.
3. **Flag** — when the recommended request deviates from the configured request by
   more than the threshold (default 30%), in **either direction**. CI test-harness
   pods (non-product namespaces like `openshift-e2e-*`) are excluded.
4. **File** — open one OCPBUGS per operator with findings + agent-ready fix
   instructions, labeled `issue-for-agent` (CHAI auto-solves) and
   `ocp-memory-requests`. Idempotent: reconciles with existing open bugs (updates
   or leaves them) instead of duplicating, and ignores closed/verified ones.

## Data model (why these tables and columns)

Source: `openshift-ci-data-analysis.ci_data_autodl`, the `control_plane_singleton_pods`
table described in the `autodl` skill:

- **`control_plane_singleton_pods`** — one row per singleton pod per snapshot. The **per-pod memory** source, and the only table with `Namespace`/`Deployment` — so it is what identifies the operator to file a bug against. Group by `Deployment` (stable across runs, unlike `PodName`).

Key choices, all deliberate:

- **Use the `StartMemoryUsageMB` column.** `Start` is the memory use at the **start of the snapshot window — before the e2e suites run**. That is the at-rest baseline a request should cover, not the load the suites generate (`End`/`Peak`).
- **Floor from all CI runs on the release.** The baseline covers every run on the release (upgrade and non-upgrade alike), matching how the first batch of bugs was scoped. A run can emit more than one snapshot (upgrade runs emit two: post-install then post-upgrade), each identified by the timestamp in `Source` (`..._YYYYMMDD-HHMMSS-autodl.json`). **Use the latest snapshot per run** — the post-upgrade one for upgrade runs, the single snapshot for others — so each run contributes exactly one observation.
- **Exclude defective upgrade runs.** An **upgrade** run is expected to emit *two* snapshots; one that emitted only one (its post-upgrade snapshot is missing) is defective — its latest snapshot is the pre-upgrade `post-install` state, which would understate the floor. Drop such runs from the aggregate (the query does this) and note how many were dropped in the report. A non-upgrade run with a single snapshot is **not** defective.
- **90th percentile across job runs, not within a run.** Collapse each run to its one latest-snapshot observation per deployment, then take `APPROX_QUANTILES(..., 100)[OFFSET(90)]` **across runs**. This resists per-run outliers while still covering the busy end of the fleet. The percentile is computed **inside BigQuery** by `queries/singleton-usage.sql`.
- **Current release only, last `window_days`.** Release comes from the `Release` variant; join `autodl.JobRunName` → `jobs.prowjob_build_id` → `job_variants`.
- **Shipped operators only.** The singleton tables also capture CI test-harness pods (e.g. the loki `event-exporter` in `openshift-e2e-loki`) that are not product control-plane operators and have no repo to fix. These are excluded by namespace denylist in the query — never file bugs for them.

All memory values in these tables are in **MB** (10⁶ bytes), not MiB.

## Convention: how to turn observed usage into a request

Per `openshift/enhancements` `CONVENTIONS.md`, a memory **request** should carry
**~10% headroom over observed usage**. We apply that +10% rule, but note a
**deliberate difference in measurement basis**: the convention uses the p90 of
consumption *during* an e2e suite, whereas this workflow uses the **pre-suite
(`Start`) at-rest usage, p90 across runs**. The two can differ; we intentionally
target the at-rest floor:

```
recommended_request = p90_observed_start_usage * 1.10
```

Drift is the gap between that recommendation and what is configured today:

```
drift_pct = (recommended_request - current_request) / current_request * 100
```

Flag the deployment when `abs(drift_pct) > threshold_pct` (and `current_request > 0`).
Positive drift → **raise** the request; negative drift → **lower** it.

## Prerequisites

- `bigquery-ci-data` plugin (BigQuery `bq` CLI, authenticated; read access to
  `openshift-gce-devel` and `openshift-ci-data-analysis`).
- A way to search and file Red Hat Jira (OCPBUGS) bugs — CHAI provides its own; no
  specific tool assumed.

## Usage

This plugin is a **skill**, not a slash command — CHAI (or any agent with the
plugin loaded) invokes `check-memory-drift` directly. It accepts optional
parameters:

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `release` | current devel (resolved at runtime) | OCP release to analyze |
| `window_days` | `30` | Lookback window |
| `threshold_pct` | `30` | Drift threshold (`10`–`15` tightest, `30` less churn) |
| `min_runs` | `100` | Minimum job runs before trusting a percentile |
| `dry_run` | off | Report drift without filing bugs |

## Layout

```text
skills/check-memory-drift/
├── SKILL.md
├── queries/
│   ├── singleton-usage.sql         @release, @window_days -> per-deployment usage
│   └── defective-upgrade-runs.sql  -> excluded-run count for the report
└── scripts/
    ├── select-candidates.py        usage JSON -> candidates JSON
    ├── render-bug.py               candidate -> {summary, labels, key, description}
    └── test_*.py                   unit tests
```

## Skills

| Skill | Purpose |
|-------|---------|
| `check-memory-drift` | The full detect-and-file workflow: BigQuery query, drift math, reconcile, and OCPBUGS creation |

## Caution

Drastic increases are risky for **single-node** topologies, where every singleton
stacks on one node. Filed bugs flag large increases explicitly; the judgment call
stays with the PR reviewer.

## Design decisions

- **Threshold default 30%.** The ticket suggested 10% (15–20% to limit churn); we default to 30% to keep monthly bug volume manageable. Tune with `threshold_pct`.
- **Mixed runs, not upgrade-only.** The baseline includes upgrade and non-upgrade runs, matching how the first batch of bugs was scoped. Upgrade-only would change recommendations and churn existing bugs.
- **No volume cap.** Every candidate above threshold is acted on each run; reconciliation keeps later runs idempotent.
- **Step 4 (does it still ship) is a model judgment.** Finding a Deployment in real release manifests needs judgment; the skill documents the expectation rather than prescribing a fixed lookup, so CHAI can use whatever it has.
- **Mi rounding is deterministic.** `select-candidates.py` converts the MB recommendation to Mi (`MB × 0.9537`) and rounds **up to the next 16 Mi**; the bug shows both MB and Mi.
- **SQL fetches, scripts decide, the model judges.** `queries/*.sql` return raw usage; `select-candidates.py` applies the +10%/threshold/direction policy; `render-bug.py` renders the bug; the model does release resolution, the manifest check, reconciliation, and the report. Evals stub the edges (bq, Jira) and assert on the decisions.

## Future work

- Backlog management of open `ocp-memory-requests` bugs: close bugs whose drift has
  since resolved, and nudge stale ones. (Powered by the same label + JQL.)
