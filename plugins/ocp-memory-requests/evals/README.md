# ocp-memory-requests Plugin Evals

Index of what each `case-NN` directory under `cases/check-memory-drift` tests.

## check-memory-drift (`cases/check-memory-drift`)

Evaluates `ocp-memory-requests:check-memory-drift` against a **mocked** BigQuery
output and a **mocked** OCPBUGS store — no live BigQuery or Jira. Each case
provides:

- `input.yaml` — `command_args`, `devel_release`, `manifests_present`,
  `preexisting_bugs`.
- `usage.json` — the mocked result of
  [`queries/singleton-usage.sql`](../skills/check-memory-drift/queries/singleton-usage.sql),
  served by the `bq` stub (never read directly).
- `defective-upgrade-runs.json` — the mocked result of
  [`queries/defective-upgrade-runs.sql`](../skills/check-memory-drift/queries/defective-upgrade-runs.sql),
  served by the `bq` stub.

The eval's `runner.system_prompt` only sets up the **mock** dependencies (a
`bq-mock.py` command for BigQuery; `devel_release` for the release lookup;
`manifests_present` for the manifest check; `preexisting_bugs` for the store; a
`jira-mock.py` command for Jira writes). It deliberately does **not** describe the
pipeline, name the scripts, or give the output schema — the agent must read the
skill's [SKILL.md](../skills/check-memory-drift/SKILL.md) to know what to do, so
deleting or breaking SKILL.md breaks this eval.

Both mocks are call-recording stubs: every invocation appends one JSON line to a
call log in the workspace —

- [`bq-mock.py`](stubs/bq-mock.py) → **`bq-calls.jsonl`** — `{action:
  dry_run|query, query, parameters: {release, window_days}}`. It identifies the
  query from the SQL on stdin and serves the matching fixture on stdout, so the
  skill's real query step (named parameters, dry-run first per `foundations`)
  runs end to end.
- [`jira-mock.py`](stubs/jira-mock.py) → **`jira-calls.jsonl`** — one line per
  `create`/`update`/`comment`.

The judges in [`eval-check-memory-drift.yaml`](eval-check-memory-drift.yaml)
score those call logs (the queries and writes the skill actually made) plus a
small `result.json` report, against the case `annotations.yaml`; every judge is
a no-op (pass) when its annotation field is absent, so one judge set serves all
cases.

The harness stages `input.yaml`, both fixtures, and both stubs into each case
workspace (`dataset.workspace.files`); `annotations.yaml` (the answer key) is held
back as evaluation material and is never visible to the agent.

**These cases test decisions, not arithmetic.** The +10% recommendation, drift,
threshold, direction, and Mi rounding are deterministic and covered by the script
unit tests (below), so they are not re-tested here. The eval checks what needs
judgment: release resolution and the parameters actually passed to the queries
(from `bq-calls.jsonl`), dry-run-before-query cost discipline, the manifest
"still ships" check, reconciliation with existing bugs, the defective-run count
in the report, and dry-run behavior.

Defaults pinned to the skill: `window_days=30`, `threshold_pct=30`, `min_runs=100`.

| Case | Tests |
|------|-------|
| case-01 | Default params: no `--release` → resolve devel 5.1 over 30 days; file one bug |
| case-02 | Raise: bug carries the `memory-drift-key` and the SNO/HyperShift warning |
| case-03 | Lower: over-provisioned operator → `lower` direction |
| case-04 | Set: no request configured → direction `set` |
| case-05 | Deployment absent from manifests → skipped "manifest not found", no bug |
| case-06 | Differing requests across variants → flagged `var`; bug says check every manifest |
| case-07 | Reconcile: open bug, same key, similar value → `leave` (no write) |
| case-08 | Reconcile: open bug, same key, materially different value → `update` + comment |
| case-09 | Reconcile: Closed bug, same key → new bug filed |
| case-10 | Reconcile: same deployment name, different namespace → new bug (keys differ) |
| case-11 | Reconcile: open bug for a different release → new bug for 5.1 |
| case-12 | `--dry-run`: candidate reported, zero bugs authored |
| case-13 | No drift: no candidate, no bug |
| case-14 | Empty result: clear report, no bug |

## Unit tests

The deterministic math lives in the scripts and is pinned by co-located unit
tests (run with `python3 -m pytest` from the `scripts/` directory):

- [`test_select_candidates.py`](../skills/check-memory-drift/scripts/test_select_candidates.py)
  — the +10% recommendation, half-up rounding, MB→Mi round-up, the
  strictly-greater threshold, the min-runs floor, the zero-request `set` rule, the
  `var` flag, candidate ordering, and string-input coercion.
- [`test_render_bug.py`](../skills/check-memory-drift/scripts/test_render_bug.py)
  — the fixed Jira fields, the `memory-drift-key`, raise/lower/set summaries, the
  increase-only warning, the variants note, and the PR rules.

## Scope notes

- bq and Jira actions are scored from **real call logs** (`bq-calls.jsonl`,
  `jira-calls.jsonl`) written by the `bq-mock.py` / `jira-mock.py` stubs when
  the skill invokes them — not from a self-report. A run that writes a
  correct-looking `result.json` without actually querying or filing passes
  nothing, because the judges read the logs.
- The manifest "still ships" check is a model judgment with no prescribed
  mechanism, so it is exercised via a `manifests_present` fixture rather than a
  stubbed lookup.
- Percentiles are computed in BigQuery (`APPROX_QUANTILES`) by
  `queries/singleton-usage.sql`; cases provide already-aggregated per-deployment
  `usage.json`, so snapshot selection and percentile math are not re-tested here.
