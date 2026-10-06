# Run Discovery (Step 1.5)

Skip this step if the input is Prow job URL(s). This step resolves a Grafana disruption
dashboard URL, or a disruption regression alert, into specific Prow job runs for analysis.

**IMPORTANT: Do NOT fetch or open the Grafana URL.** The dashboard is behind Red Hat SSO
and will redirect to a login page. Do NOT manually query Sippy API endpoints — the script
below handles all URL parsing, Sippy querying, and disruption filtering in one call.

## 1.5.1: Run the Disruption Run Finder

Run `find_disruption_runs.py` with `--auto-select 5` to get a recommended default selection.
For a dashboard URL, pass it unchanged. For an alert, pass the pasted text unchanged,
including a `link:` annotation when the alert has one. The script maps series labels to
Sippy variant filters, queries Sippy for matching runs, keeps runs whose
`master_nodes_updated` matches, and auto-selects a diverse sample.

```bash
python3 "${CLAUDE_SKILL_DIR}/find_disruption_runs.py" \
  --grafana-url "{grafana_url}" \
  --auto-select 5 \
  --format table
```

```bash
python3 "${CLAUDE_SKILL_DIR}/find_disruption_runs.py" \
  --alert-text "{alert_text}" \
  --auto-select 5 \
  --format table
```

Series labels, and what the finder does with each:

- Sippy job variants, applied when the URL or alert sets them: `platform`, `architecture` (`var-architectures`), `topology` (`var-topologies`), `network` (`var-networks`), `upgrade_type`, `feature_set` (`var-featureset` or `var-feature_set`), `os` (`var-os`), `ipmode` (`var-ipmode`, dashboard only)
- `release` (`var-releases`) selects the Sippy release. `backend` (`var-backend`) is scored as an exact name
- `master_nodes_updated` is not a job variant. The same job is `Y` on some runs and `N` on others. The disruption API returns it per run. `Y` or `N` drops the other runs, including a clean comparison run. `All` / `$__all` / absent does not filter. If the API response has no such field, the finder keeps nothing and says so
- `lookback` is the window in calendar days. An alert with no `link:` uses 3 days, the window `DisruptionRegression*` measures. A link's `var-lookback` wins
- `delta` / `var-percentile` names which tail moved (P50, P75, P95). Runs are still ranked by per-run seconds
- `compare_release` is the previous GA the delta was computed against. It is report context, not a filter on the current release's runs
- `releaseStatus`, `var-min_disruption_regression`, `var-min_disruption_job_list`, `var-min_relevance`, and `orgId` are not run filters
- FIPS, serial, installer, ipsec, and realtime are not series labels. Do not add Sippy filters for them. Those jobs belong in the series when they share the labels above

An alert `link:` is the base URL. Labels the link omits, including `feature_set` and `os`, are still applied. Do not drop those labels because the annotation forgot them. A value already on the link wins over the label.

Pass the Grafana URL through unchanged, including every `var-backend` value. Do not
collapse a multi-backend URL to a single API backend, and do not strip names to a
base such as `kube-api` or `openshift-api`. The script scores **exact** backend names
from the URL. Derived probes are not those backends and must not be used to rank
runs. Names it does not treat as a selected backend unless that exact string is in
the URL include:

- `*-localhost-*`
- `*-http1-*` and `*-http2-*`
- `*-service-network-*` and `*-internal-lb-*`
- `cache-*` (unless the URL selected that cache backend)

`Disruption (s)` is the max seconds among the exact selected names for that run, from
BigQuery. The summary line names the dashboard percentile (`var-percentile` or alert
`delta`, such as P75) so those seconds are not read as that percentile. It also prints
the applied series filters: platform, architecture, topology, network, upgrade, feature
set, OS, master nodes updated, lookback, and compare release, when each one is set.
The `Backend` column is the selected name that produced that max. The table lists runs with seconds > 0 on those
names, sorted by that max, after scanning the dashboard window — not the newest 50
runs. `var-lookback`
is that window, in calendar days from UTC midnight. `All` / `$__all` variant values
(including `var-featureset=All`) are not Sippy filters. Recommended runs are marked
with `*` in the `Rec` column. When available, a clean comparison run (0s on the
selected backends, from the same job as a disrupted run) is included and marked with `C`.
The output looks like:

```text
Dashboard: disruption-for-5-0-os-agnostic
Filters: Platform=gcp | Architecture=amd64 | Topology=ha | Network=ovn | Upgrade=micro
Release: 5.0 | Percentile: P95 | Backend: kube-api-new-connections, pod-to-host-new-connections
Window start: 2026-09-28 00:00
Scanned 1200 runs.

Showing 8 runs with disruption > 0s on kube-api-new-connections, pod-to-host-new-connections (per-run seconds, not P95):

| # | Rec | Job | Build ID | Result | Disruption (s) | Backend | Disruption Failures | Timestamp |
|---|-----|-----|----------|--------|----------------|---------|---------------------|-----------|
| 1 | *   | ...e2e-aws-ovn-serial-ipsec | 2105807354116182016 | S | 476 | pod-to-host-new-connections | — | 2026-10-01 23:49 |
| 2 |     | ...e2e-gcp-ovn-upgrade | 2084186427159334912 | S | 31 | kube-api-new-connections | — | 2026-08-02 12:00 |
| 3 | *   | ...e2e-gcp-runc-upgrade | 2084097565123456789 | S | 12 | kube-api-new-connections | — | 2026-08-01 06:00 |
| 4 | C   | ...e2e-aws-ovn-serial-ipsec | 2084097565987654321 | S | 0 | — | — | 2026-07-31 18:00 |

Auto-selected 5 runs (* = disrupted, C = clean comparison from same job) for diverse coverage.
```

The auto-selection algorithm:
1. Deduplicates same-job runs within 60s and cross-job runs within 5s
2. Categorizes remaining runs into high/moderate/low disruption tiers
3. Round-robins across different jobs within each tier for diversity
4. Reserves one slot for a clean comparison (0s disruption from the same job as a selected
   disrupted run) — used in Step 6.3 for same-job A/B comparison to filter out red herrings

The `Disruption (s)` column shows the max disruption seconds among the exact
`var-backend` names from BigQuery. A `—` means BigQuery data is not yet available
for that run (data is refreshed every 4 hours). Do not re-rank these runs by
localhost, HTTP, service-network, or internal-lb probe totals.

To get machine-readable output for downstream processing, use `--format json` with the same `--grafana-url` or `--alert-text` as the table run:

```bash
python3 "${CLAUDE_SKILL_DIR}/find_disruption_runs.py" \
  --grafana-url "{grafana_url}" \
  --auto-select 5 \
  --format json
```

Each JSON row includes `build_id` (Prow build ID), `job` (job name),
`disruption_seconds` (max seconds among the exact selected backends),
`disruption_backend` (the selected name that produced that max),
`disruption_backends` (only those exact names, with their disruption seconds),
`disruption_failures` (test failures), `url` (Prow URL), `recommended` (boolean),
and `role` (`"clean-comparison"` for the 0s same-job A/B run, absent otherwise).

Use `--disruption-only` to omit the clean-comparison run and keep only disruption > 0
on the exact selected backends. This uses actual BigQuery data, not test failures.

Additional flags:
- `--since-hours N` — rolling hour window; overrides `var-lookback`. When omitted and the URL has no lookback, the window is 720 hours (30 days). An alert with no link already sets lookback to 3 days; do not pass `--since-hours` unless the user asks for a different window
- `--limit N` — cap how many runs are scanned. When omitted, the script pages through the whole window (up to 5000 runs)
- `--auto-select N` — change number of auto-selected runs (default when used: 5)
- Individual flags (`--release`, `--platform`, `--backend`, etc.) can override URL params. `--backend` may be comma-separated and is matched exactly, the same way as repeated `var-backend` values

The script pages Sippy across the whole window (`var-lookback` calendar days, 3 days for an alert with no link, or 30 days),
then ranks by exact-backend disruption. Do not pass `--limit 50` to "sample recent runs" —
that drops the runs the dashboard is showing. Narrow `--since-hours` only when the user
asks for a different window than the URL or alert.

Recommended runs (the `*` rows, plus a `C` clean comparison when one was kept) are the
runs to analyze. When an alert returns more than one run, show the table and ask before
analyzing. When it returns one run, skip the table and the question: say it is the only
match, give that run's details, and continue. The candidate set is already limited to
the alert or dashboard series.

## 1.5.2: Present Candidates and Collect Selection

Run the finder with `--format table` and leave its stdout on the terminal.

**One run from an alert.** If the input was an alert and the table has a single run row,
do not paste the table and do not ask which runs to analyze. Say that this is the only
matching run, then give the filter summary from the finder header and that run's job
name, build ID, result, disruption seconds, backend, and timestamp. Continue to Step
1.5.3 with that run.

**More than one run.** The finder stdout is the candidate list. Paste it into the reply
inside a `text` fence, complete and unchanged, then ask which runs to analyze.

Do not redirect that command into `.work`, and do not save a JSON, txt, or canvas copy
of the candidates for the user to open. Do not write a script that rebuilds the table.
The finder already prints it. `.work/disruption-analysis/` is only for timeline
downloads and the final analysis report, after the runs to analyze are known. For a
single alert match, that is the one run. Otherwise it is after the user has picked runs.

`--format json` is a second run, used only after the runs are chosen, to read `url`.
Do not turn that JSON into a table yourself.

When the table is shown, do not filter, reformat, or omit rows. Recommended runs are
marked with `*` in the `Rec` column — auto-selected for diverse coverage across jobs,
disruption severity, and timestamps. The algorithm deduplicates runs that likely share
the same infrastructure event and then selects a mix of high, moderate, and low
disruption for comparison.

After showing the full table (more than one run), ask:

```text
Recommended runs are marked with * (auto-selected for diverse coverage).
Proceed with recommended runs, or specify different numbers? (e.g., "1,3,5" or "all" or "yes" for recommended)
```

If the user confirms the recommendation (or says "yes"), use the recommended runs.
If the user provides specific numbers, use those instead. Skip this question when the
alert returned a single run; that run is the selection.

If no runs have disruption test failures for the target backend, note this and offer to
analyze the most recent failed runs anyway (disruption may be within threshold but elevated).

## 1.5.3: Convert Selections to Prow URLs

Re-run `find_disruption_runs.py` with `--format json` and the same `--grafana-url` or `--alert-text` to get machine-readable output with `url`
fields. Use the `url` field from the JSON output to get Prow URLs for the selected runs. Set:
- `--backends` to the exact comma-separated backend list from the Grafana URL or the alert (unless the user overrides it). Do not shorten those names
- The resolved Prow URLs proceed to Step 1, item 3 (Parse each Prow URL) and then Step 2
