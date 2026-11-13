---
name: check-memory-drift
description: Use when auditing or correcting OpenShift control-plane operator memory requests — detects when a single-replica operator pod's configured memory request has drifted from its observed post-upgrade usage in CI, and files agent-ready OCPBUGS to fix it. Designed to run headless in CHAI on a monthly cadence. Triggers on "control-plane memory requests", "operator memory drift", "ocp-memory-requests", "right-size operator memory", or a recurring/monthly memory-request check.
---

# Control-Plane Operator Memory-Request Drift Check

Keep control-plane operator memory **requests** accurate automatically, on a
recurring (~monthly) cadence, instead of fixing them one bug at a time. This skill
measures what single-replica ("singleton") control-plane operator pods actually use
after a cluster is installed and upgraded once, compares that to their configured
request, and files an **agent-ready OCPBUGS** when they have drifted — raising,
lowering, or setting a missing request. See the **README** for the data model, the
+10% convention, and design decisions.

## Prerequisites

- `bigquery-ci-data` plugin (`foundations` + `autodl` skills, `bq` CLI auth). Follow
  `foundations` for cost safety, partition filters, and caching.
- A way to search and file Red Hat Jira (OCPBUGS). Use whatever mechanism the
  environment provides — CHAI supplies its own; do not assume a specific tool/MCP.
- `python3` for the two bundled scripts.

## Parameters

Read from the invocation arguments; fall back to defaults.

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `release` | current devel (resolved at runtime) | OCP release to analyze; do not hardcode |
| `window_days` | `30` | Lookback window (positive integer) |
| `threshold_pct` | `30` | Flag when recommended deviates from current by more than this |
| `min_runs` | `100` | Minimum job runs before trusting a deployment's percentile |
| `dry_run` | `false` | Compute and report, but create no bugs |

## Pipeline

Scripts are deterministic (JSON in, JSON out) and unit-tested — never recompute their
numbers by hand. Paths are relative to this skill's directory.

1. **Resolve the release** *(model)* — if no `release` is given, resolve the current
   development release at runtime (CHAI and the `ci` plugin know it); do not hardcode.

2. **Fetch usage** *(bq)* — run the query with named parameters; cache the JSON under
   `.work/ocp-memory-requests/`. Follow the `foundations` cost protocol (dry-run
   first); this table is small (usually a fraction of a cent). Headless: if the
   estimate is implausibly large, abort and report rather than prompt.

   ```sh
   bq query --use_legacy_sql=false --format=json \
     --parameter=release:STRING:<RELEASE> --parameter=window_days:INT64:<WINDOW_DAYS> \
     < queries/singleton-usage.sql > usage.json
   ```
   Also run `queries/defective-upgrade-runs.sql` the same way for the excluded-run
   count in the report.

3. **Select candidates** *(script)* —
   ```sh
   python3 scripts/select-candidates.py --threshold-pct <T> --min-runs <M> < usage.json
   ```
   Prints `[{deployment, namespace, direction (raise|lower|set), current_mb,
   recommended_mb, recommended_mi, drift_pct, var, job_runs, p50_start_mb,
   p90_start_mb, …}]`, most-urgent first.

4. **Confirm each still ships** *(model)* — resolve the owning operator/repo (the
   namespace prefix usually names it) and confirm the Deployment exists in the target
   release's manifests. If it cannot be found, **skip** it (reason `manifest not
   found`), record it in the report, and file no bug.

5. **Reconcile with existing bugs** *(model)* — search Jira **coarsely** (label +
   release + not closed/verified), then treat a bug as an open match **only when its
   `memory-drift-key:` line equals `<release>/<namespace>/<deployment>` exactly**; do
   not fuzzy-match names. Then, only when `dry_run` is false: no match → file (step 6);
   open match with a materially different recommendation → update the bug + comment;
   otherwise leave it.

6. **Render and file** *(script + model)* —
   ```sh
   echo '<candidate>' | python3 scripts/render-bug.py --release <RELEASE> --window-days <W>
   ```
   Prints `{project, issuetype, summary, labels, key, versions, target_version,
   security, description}`. Fill the description's **"What was found"** section with the
   owning repo + manifest path from step 4, then file via the environment's Jira
   mechanism. One bug per deployment.

7. **Report** *(model)* — parameters used; counts (evaluated / candidates / filed /
   updated / unchanged / skipped); a table (deployment · current → recommended ·
   drift% · direction · OCPBUGS key or dry-run/updated/unchanged); the skip list with
   reasons; and the defective-upgrade-run count. Under `dry_run`, report only.

## Guardrails

- **Headless** — never block on human input. If a required dependency is missing
  (BigQuery auth, or a way to file Jira), stop and report the blocker; do not partially file.
- **Idempotent** — always reconcile (step 5) before filing; update or skip existing bugs, never duplicate.
- **Cost-safe** — dry-run the query first per `foundations`.
- **Request, not limit** — only ever recommend changing `requests.memory`.
- **Both directions** — file for decreases ("lower to") and missing requests ("set to"), not just increases.
- **Trust floor** — never file from fewer than `min_runs` job runs.
- **Shipped-only** — never file for a Deployment with no release manifest (step 4).
- **Escalate** — on an error or ambiguous result it can't resolve, reach out to the OCP Quality Staff Engineers (and/or comment on the Jira) rather than failing silently.
