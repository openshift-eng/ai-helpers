# Backtest fixtures

Slim regression records (`id, release, duty_views, test_name, component, capability, variants, opened, regression_opened,
closed, last_failure, max_failures, triages (ids), job_runs[{prowjob_name, prowjob_run_id, start_time, test_failures}]`), gzip JSON.

| File | Source | Records | Size |
|---|---|---|---|
| `frozen-2026-10-07.json.gz` | `bulk-existing-triage-4.16-4.22-2026-10-07/inventory.json`, key `open_untriaged`, records with a `-main` duty view (non-`-main` names dropped) | 326 | 89,503 B |
| `replay-days.json.gz` | `chaibot-design/live-4.{16..22}-main.json` (`components[*].open + closed`), `opened` within ±36 h of 12:00 UTC on 2026-08-30, 09-20, 09-24, 09-25 | 661 | 86,068 B |

Regenerate (sources are local, outside the repo): `python3 make_fixtures.py` (`--no-live` skips the enrichment below).

`opened` in both sources is the view-level (re)activation date that `list_regressions.filter_by_view` substitutes for
Sippy's regression-level `opened`. `regression_opened` was enriched on 2026-10-12 from the live regressions API
(immutable per regression; 326/326 and 661/661 resolved). It feeds `shape.regression_days_open` only; the blast-radius
rules still read `days_open` from `opened`, so the asserted outcomes below did not move. With regression-level ages the
frozen inventory would give HIGH 2 / ELEVATED 6 / LOW 7 (two permafails surface) and the 08-30 replay burst would be HIGH
(a recurrence of a 08-14 event) — recorded here as input for the shadow-period threshold review, not applied.

`expected-backtest.json` records the asserted outcomes; `test_prepass.py` enforces them.

Notes:
- Evidence is as-of the observation time: job runs that started after `now` are dropped before clustering and
  shaping (the replay fixtures contain later runs; e.g. the 09-24 HIGH cluster has 8 distinct jobs as-of, 11 with
  later runs). Medians are over distinct runs.
- The 09-20 precursor (18 regressions opened 2026-09-19T04Z) is only inside a 24 h window ending before 09-20T04Z;
  the test uses `now = 2026-09-20T00:00:00Z`.
- Tripwire continuity matches a previous cluster by id, then by `(release, lane_family)`, because a rolling
  window's `test_family` (and so the id) changes between runs of the same event.
- Weekly supersedes: a baseline cluster is listed when at least half of *its* members land in the current cluster.
- Prototype cross-check (`chaibot-design/prepass_proto.py <inventory.json> --main`, frozen inventory): 326 regressions ->
  15 clusters, HIGH=2 / ELEVATED=4 / LOW=9. `prepass.py` on the same fixture gives 15 clusters with the same HIGH/ELEVATED/LOW
  members asserted in `test_backtest_frozen_inventory`; no drift observed.

## Example manifest

`triage-manifest.example.json` is a hand-written schema-1.0 `triage-manifest.json`; `test_manifest.py` validates it and
builds its fixtures from it.

- `c-7f3a9e` (HIGH, KNOWN-CAUSE) predates prior memory and has no `prior` key: the validator admits manifests
  without it, which keeps every historical manifest valid.
- `c-prior-example` (LOW, UNEXPLAINED in both weeks) shows a carried analysis. Its `prior` is the projection of the
  baseline run `2105...` (observed 2026-10-06): one immediate source (`history_only: false`, `unfinished: false`),
  the same member (`matched_member_ids: [90001]`, empty `member_delta`), the source's bounded analysis with its
  `basis` (the original deep-dive), its rejected bug candidate kept as opaque history, and no action. The current
  `disposition.analysis` has `depth: "carried-forward"` plus the `reverification` record the validator checks: the
  basis equals the source's, `own_run_ids` name this week's own failed run in the current `evidence`, a negative
  bug-search locator is listed, `checked_at` is not before this run's `observation.time`, and `outcome: "carried"`.
- Flat retention: when the latest attempt left a cluster `UNANALYSED`, the pre-pass keeps the finished snapshots that
  attempt had itself inherited as `history_only: true` sources (original run, time and basis), beside the unfinished
  immediate source. Nothing is nested and nothing accumulates across attempts; retained history is context, never
  coverage, and never a carry source (`test_manifest.py`, `MultiGenerationTest`).
