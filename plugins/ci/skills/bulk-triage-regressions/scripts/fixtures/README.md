# Backtest fixtures

Slim regression records (`id, release, duty_views, test_name, component, capability, variants, opened, closed,
last_failure, max_failures, triages (ids), job_runs[{prowjob_name, prowjob_run_id, start_time, test_failures}]`), gzip JSON.

| File | Source | Records | Size |
|---|---|---|---|
| `frozen-2026-10-07.json.gz` | `bulk-existing-triage-4.16-4.22-2026-10-07/inventory.json`, key `open_untriaged`, records with a `-main` duty view (non-`-main` names dropped) | 326 | 86,937 B |
| `replay-days.json.gz` | `chaibot-design/live-4.{16..22}-main.json` (`components[*].open + closed`), `opened` within ±36 h of 12:00 UTC on 2026-08-30, 09-20, 09-24, 09-25 | 661 | 81,987 B |

Regenerate (sources are local, outside the repo): `python3 make_fixtures.py`

`expected-backtest.json` records the asserted outcomes; `test_prepass.py` enforces them.

Notes:
- The 09-20 precursor (18 regressions opened 2026-09-19T04Z) is only inside a 24 h window ending before 09-20T04Z;
  the test uses `now = 2026-09-20T00:00:00Z`.
- Tripwire continuity matches a previous cluster by id, then by `(release, lane_family)`, because a rolling
  window's `test_family` (and so the id) changes between runs of the same event.
- Weekly supersedes: a baseline cluster is listed when at least half of *its* members land in the current cluster.
- Prototype cross-check (`chaibot-design/prepass_proto.py <inventory.json> --main`, frozen inventory): 326 regressions ->
  15 clusters, HIGH=2 / ELEVATED=4 / LOW=9. `prepass.py` on the same fixture gives 15 clusters with the same HIGH/ELEVATED/LOW
  members asserted in `test_backtest_frozen_inventory`; no drift observed.
