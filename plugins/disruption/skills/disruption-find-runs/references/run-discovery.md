# Sampling Disrupted Runs

This resolves a Grafana disruption dashboard URL, or a disruption regression alert, into the
currently disrupted Prow job runs worth analyzing (`sample-disrupted`).

**IMPORTANT: Do NOT fetch or open the Grafana URL.** The dashboard is behind Red Hat SSO
and will redirect to a login page. Do NOT manually query Sippy API endpoints — the script
below handles all URL parsing, Sippy querying, and disruption filtering in one call.

## 1. Run the Disruption Run Finder

Run `find_disruption_runs.py` with `--auto-select 5` to get a recommended default selection.
For a dashboard URL, pass it unchanged in single quotes. For an alert, write the pasted
text unchanged, including a `link:` annotation when the alert has one, to
`{investigation_dir}/alert.txt` with your file-writing tool (not `echo` or an unquoted heredoc),
and pass that file. Never put alert text on the command line: backticks and `$(...)` in it
would run. The script maps series labels to
Sippy variant filters, queries Sippy for matching runs, keeps runs whose
`master_nodes_updated` matches, and auto-selects a representative sample.

```bash
python3 "${CLAUDE_SKILL_DIR}/find_disruption_runs.py" \
  --grafana-url '{grafana_url}' \
  --auto-select 5 \
  --format table
```

```bash
python3 "${CLAUDE_SKILL_DIR}/find_disruption_runs.py" \
  --alert-file {investigation_dir}/alert.txt \
  --auto-select 5 \
  --format table
```

Series labels, and what the finder does with each:

- Sippy job variants, applied when the URL or alert sets them: `platform`, `architecture` (`var-architectures`), `topology` (`var-topologies`), `network` (`var-networks`), `upgrade_type`, `feature_set` (`var-featureset` or `var-feature_set`), `os` (`var-os`), `ipmode` (`var-ipmode`, dashboard only)
- `release` (`var-releases`) selects the Sippy release. `backend` (`var-backend`) is scored as an exact name
- `master_nodes_updated` is not a job variant. The same job is `Y` on some runs and `N` on others. The disruption API returns it per run. `Y` or `N` drops the other runs, including a clean comparison run. `All` / `$__all` / absent does not filter, and neither does `Y` and `N` together (`var-master_nodes_updated=Y&var-master_nodes_updated=N`), which means All and is not warned about. If the API response has no such field, the finder keeps nothing and says so
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

The Jira search (`disruption-known-issues`) is different: `known_issue_queries.py` deliberately searches the
whole API family, because a bug is often filed against a sibling probe. That does not
change how runs are found or ranked here.

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

The table output is compact. Before the run rows it prints:

- **Selected backends**: for each exact selected name, the runs where it was > 0, the
  runs where it was the max (the name in the `Backend` column), and its median seconds
  when > 0. Names stay exact; nothing is collapsed to a base or family for ranking.
- **Correlation** (more than one selected name): the number of disrupted runs where
  every selected name with data for that run was within 15% of that run's max. A high
  count means the names move together, which usually points to one event per run.
- **A probe-family note** when the selection mixes probe families (`*-localhost-*`,
  `*-service-network-*`, `*-internal-lb-*`, `cache-*`, or main backends) and one probe
  family was the max in more than half of the disrupted runs. Ask the user which family
  they mean before choosing runs (see section 2).
- **Per-job disruption**: for each job with disruption, its runs, disrupted runs, total
  and median seconds on the selected names, and its share of the total, sorted by total.

The run rows are the top `--top` rows (default 20) plus any recommended row below
them, numbered by their rank in the full table. Each summary also shows at most
`--top` lines. When rows are cut, the full report (every row, backend, and job) is
written to a file, and the last lines say where. The output looks like this (run with
`--top 3` to keep it short):

```text
Dashboard: disruption-for-5-0-os-agnostic
Filters: Platform=gcp | Architecture=amd64 | Topology=ha | Network=ovn | Upgrade=micro
Release: 5.0 | Percentile: P95 | Backend: kube-api-new-connections, pod-to-host-new-connections
Window start: 2026-09-28 00:00
Scanned 1200 runs.

Selected backends (runs > 0, runs where it was the max, median seconds when > 0):

| Backend | Runs > 0 | Max in | Median (s) |
|---------|----------|--------|------------|
| kube-api-new-connections | 40 | 31 | 4 |
| pod-to-host-new-connections | 12 | 9 | 2 |

Selected backends correlated (every selected backend in the run within 15% of that run's max) in 3 of 40 disrupted runs.

Per-job disruption (sorted by total seconds on the selected backends):

| Job | Runs | Disrupted | Total (s) | Share | Median (s) |
|-----|------|-----------|-----------|-------|------------|
| periodic-ci-openshift-release-main-nightly-5.0-e2e-aws-ovn-serial-ipsec | 30 | 6 | 520 | 61% | 8 |
| periodic-ci-openshift-release-main-ci-5.0-e2e-gcp-ovn-upgrade | 80 | 25 | 250 | 29% | 6 |

Showing 40 runs with disruption > 0s on kube-api-new-connections, pod-to-host-new-connections (per-run seconds, not P95):

| # | Rec | Job | Build ID | Result | Disruption (s) | Backend | Disruption Failures | Timestamp |
|---|-----|-----|----------|--------|----------------|---------|---------------------|-----------|
| 1 | *   | ...e2e-aws-ovn-serial-ipsec | 2105807354116182016 | S | 476 | pod-to-host-new-connections | — | 2026-10-01 23:49 |
| 2 |     | ...e2e-gcp-ovn-upgrade | 2084186427159334912 | S | 31 | kube-api-new-connections | — | 2026-08-02 12:00 |
| 3 | *   | ...e2e-gcp-runc-upgrade | 2084097565123456789 | S | 12 | kube-api-new-connections | — | 2026-08-01 06:00 |
| 31 | C  | ...e2e-aws-ovn-serial-ipsec | 2084097565987654321 | S | 0 | — | — | 2026-07-31 18:00 |

Showing rows 1-3 plus 1 recommended row(s) below them of 41.
Full table (41 rows, all backends and jobs): .work/disruption-analysis/2026-10-05/find-runs-142233.md
Total: 41 (40 disrupted, 1 clean comparison)
Auto-selected 3 runs (* = disrupted, C = clean comparison from same job).
```

Warnings go to stderr. A selected backend name that contains whitespace (usually a
URL-encoding slip such as `host-to-host-new-connec%20%20tions`), or that never appears in
the disruption data for any scanned run, gets a warning with the closest name seen in
the data. The name is still used exactly as given. Tell the user about the warning and
ask whether they meant the suggested name; do not substitute it yourself.

The auto-selection rules, in order:
1. The top run (most seconds, newest on a tie) is always selected.
2. Each event gives at most one pick. Runs of the same job that start within 5 minutes of
   the batch's first run share a launch, and usually a payload; only the worst of them can be
   picked. Runs of any job that start within 5 seconds of each other are one event, and so
   are sister shards (`-1of2`, `-2of2`) that start within 5 minutes of each other. Runs in
   the top run's event add no weight to their jobs. The table's `Same event` line lists
   runs left out this way.
3. Runs split into two tiers at the dashboard percentile (`var-percentile` or the alert's
   `delta`, P95 when absent), taken over every run in the series, 0s runs included.
   Outliers are runs above twice that value. The tail is the rest, the runs that set
   the percentile. Picks alternate between the tiers, so a sample shows both the large
   outages and what moves the plotted line. When the percentile is 0s, every disrupted run
   is an outlier and there is one tier. The table's `Tiers` line gives the numbers.
4. Within a tier, a job's weight is its disrupted events times their median seconds, so
   a job with one large run does not get extra picks for its small ones, and a job that is
   disrupted in most runs gets a pick ahead of a one-off. Each next pick in the tier goes to
   the job with the most weight per pick it already has there.
5. In an upgrade series (the Upgrade filter names any value other than `none`, such as
   `micro` or `micro,minor,none`), a job without `upgrade` in its name counts at half
   weight, so upgrade jobs are preferred when weights are close.
6. A job's first pick in a tier is its worst batch, its second its most typical batch
   (closest to the median seconds), and later picks go down by seconds.
7. With 3 or more picks, one slot is a clean comparison: a 0s run from the
   highest-priority selected job. It takes a free slot, or replaces the last pick. It never
   replaces the top run or the only disrupted pick from its own job. The cohort comparison uses it for
   same-job A/B comparison to filter out red herrings.

If the question is narrower than the series (only the large outages, or only why the
percentile moved), pick runs from the matching tier by hand instead.

The `Disruption (s)` column shows the max disruption seconds among the exact
`var-backend` names from BigQuery. A `—` means BigQuery data is not yet available
for that run (data is refreshed every 4 hours). Do not re-rank these runs by
localhost, HTTP, service-network, or internal-lb probe totals.

To get machine-readable output for downstream processing, use `--format json` with the same `--grafana-url` or `--alert-file` as the table run:

```bash
python3 "${CLAUDE_SKILL_DIR}/find_disruption_runs.py" \
  --grafana-url '{grafana_url}' \
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
- `--top N` — table format only: how many top rows, and summary lines, to print (default 20). `--top 0` prints everything and writes no file
- `--full-table-out PATH` — table format only: where to write the full report. When omitted and rows are cut, it goes to `.work/disruption-analysis/<UTC date>/find-runs-<HHMMSS>.md` under the current directory. JSON output is always complete and ignores both flags
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

## 2. Present Candidates and Collect Selection

Run the finder with `--format table` and leave its stdout on the terminal.

**One run from an alert.** If the input was an alert and the table has a single run row,
do not paste the table and do not ask which runs to analyze. Say that this is the only
matching run, then give the filter summary from the finder header and that run's job
name, build ID, result, disruption seconds, backend, and timestamp. Continue to section 3 with that run.

**More than one run.** The finder stdout is the candidate list. Paste it into the reply
inside a `text` fence, complete and unchanged, then ask which runs to analyze. Give the
path of the full table file from the last lines so the user can open it, and do not
paste that file. The user may pick any row number from the full table, not only the
rows shown.

If the output has a probe-family note (for example, `*-localhost-*` backends were the max
in most disrupted runs), ask which backend family the user means before asking which runs
to analyze. Rerun the finder with `--backend` set to that family's exact names from the
URL. Do the same when a backend-name warning suggests a different name. Keep that
`--backend` override for every later finder call, including the `--format json` rerun.

Do not write a script that rebuilds or reformats the table. The finder already prints
the compact table and writes the full one. Apart from that file, `.work/disruption-analysis/`
is only for the investigation state, timeline downloads, and reports, after the runs to
analyze are known. For a single alert match, that is the one run. Otherwise it is after the user
has picked runs.

`--format json` is a second run, used only after the runs are chosen, to read `url`.
Do not turn that JSON into a table yourself.

When the table is shown, do not filter, reformat, or omit rows. Recommended runs are
marked with `*` in the `Rec` column. They follow the jobs that contribute the most
seconds, count each launch batch once, and always include the top run (rules above).

After showing the table (more than one run), ask:

```text
Recommended runs are marked with * (auto-selected across the outlier and tail tiers; see the rules above).
Proceed with recommended runs, or specify different numbers from the table or the full table file? (e.g., "1,3,5" or "all" or "yes" for recommended)
```

If the user confirms the recommendation (or says "yes"), use the recommended runs.
If the user provides specific numbers, use those instead. Skip this question when the
alert returned a single run; that run is the selection.

If the finder lists no runs, check its warnings first. When it warns that the Sippy
disruption API failed for some runs, their disruption is unknown, not zero: say that the
result is incomplete and suggest rerunning later. Only without that warning does an empty
table mean no run in the window had disruption > 0 on these backends. Either way, do not
pick runs from other backends instead.

## 3. Convert Selections to Prow URLs

Re-run `find_disruption_runs.py` with `--format json`, the same `--grafana-url` or `--alert-file`, and the same
`--backend` override as the last table run, to get machine-readable output with `url` fields. The rerun can
order rows differently (the window moves and Sippy refreshes), so match each selected run by its build ID
(`prow_id`), never by row number, and take that row's `url`. If a selected run is not in the JSON output,
say so; do not substitute another row. For
`disruption-analyze-run`, set:
- its `--backends` to the exact comma-separated backend list from the Grafana URL or the alert (unless the user overrides it). Do not shorten those names
- The resolved Prow URLs, and the exact backends, are what `disruption-analyze-run` takes
