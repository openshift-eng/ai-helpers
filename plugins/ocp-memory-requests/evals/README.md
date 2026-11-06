# ocp-memory-requests Plugin Evals

Index of what each `case-NN` directory under `cases/check-memory-drift` tests.

## check-memory-drift (`cases/check-memory-drift`)

Evaluates `ocp-memory-requests:check-memory-drift` against a **mocked** BigQuery
output and a **mocked** OCPBUGS store — no live BigQuery or Jira. Each case
provides:

- `input.yaml` — `command_args`, `devel_release`, `manifests_present`,
  `preexisting_bugs`.
- `usage.json` — the mocked output of
  [`queries/singleton-usage.sql`](../skills/check-memory-drift/queries/singleton-usage.sql),
  used in place of running `bq`.

The agent runs the skill's real pipeline: feed `usage.json` to
[`select-candidates.py`](../skills/check-memory-drift/scripts/select-candidates.py),
confirm each candidate ships (against `manifests_present`), reconcile against
`preexisting_bugs` by exact `memory-drift-key`, render each bug with
[`render-bug.py`](../skills/check-memory-drift/scripts/render-bug.py), and record
what it would file/update/leave in `result.json`. The judges in
[`eval-check-memory-drift.yaml`](eval-check-memory-drift.yaml) score the result
against the case `annotations.yaml`; every judge is a no-op (pass) when its
annotation field is absent, so one judge set serves all cases.

**These cases test decisions, not arithmetic.** The +10% recommendation, drift,
threshold, direction, and Mi rounding are deterministic and covered by the script
unit tests (below), so they are not re-tested here. The eval checks what needs
judgment: release resolution, the manifest "still ships" check, reconciliation
with existing bugs, and dry-run behavior.

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

- Jira actions are **self-reported** in `result.json` (the eval does not yet assert
  on real tool calls). Asserting on a logged Jira stub (`jira-calls.jsonl`) is
  future work and would require the stub-MCP harness used by `eval-jira-refine`.
- The manifest "still ships" check (step 4) is a model judgment with no prescribed
  mechanism, so it is exercised via a `manifests_present` fixture rather than a
  stubbed lookup.
- Percentiles are computed in BigQuery (`APPROX_QUANTILES`) by
  `queries/singleton-usage.sql`; cases provide already-aggregated per-deployment
  `usage.json`, so snapshot selection and percentile math are not re-tested here.
