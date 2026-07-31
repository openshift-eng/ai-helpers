# Snapshot and Failure Data

## Parse Arguments

**Anchor the output directory before anything else.** Capture the current working directory up front so all output files land in one stable, predictable location even if a later step changes directories:

```bash
OUTPUT_DIR="$(pwd)"
```

All three output files — the payload results YAML, HTML report, and autodl JSON — MUST be written under `$OUTPUT_DIR`, never into a snapshot subdirectory or a path a later `cd` may have changed. The final self-check verifies them at `$OUTPUT_DIR`.

The first argument is a **full payload tag** (e.g., `4.22.0-0.nightly-2026-02-25-152806`). Parse from it:
- `tag`: The specific payload tag to analyze
- `version`: Extract from the tag (e.g., `4.22` from `4.22.0-0.nightly-...`)
- `stream`: Extract from the tag (e.g., `nightly` from `4.22.0-0.nightly-...`)
- `architecture`: Inferred from the tag. The tag format is `<version>-0.<stream>[-<arch>]-<timestamp>`. If no architecture is present between the stream and timestamp, it is `amd64`. Otherwise, the architecture is the segment between the stream and timestamp. Examples:
  - `4.22.0-0.nightly-2026-02-25-152806` → `amd64`
  - `4.22.0-0.nightly-arm64-2026-02-25-152806` → `arm64`
  - `4.22.0-0.nightly-ppc64le-2026-02-25-152806` → `ppc64le`

## Locate or Create Snapshot

The analysis requires a local snapshot produced by the `payload-snapshot` skill. Search for an existing snapshot in this order:

1. **Explicit `--snapshot-dir DIR`**: If provided, look for `DIR/summary.json`. If not found, exit with an error.
2. **Current directory**: Check if `./summary.json` exists and its `payload_tag` field matches the requested tag.
3. **Standard relative path**: Check if `payload/<version>/<stream>/summary.json` exists and matches the tag.

If no matching snapshot is found, create one:

```bash
SNAPSHOT_SCRIPT="${CLAUDE_PLUGIN_ROOT}/skills/payload-snapshot/scripts/payload_snapshot.py"
if [ ! -f "$SNAPSHOT_SCRIPT" ]; then
  SNAPSHOT_SCRIPT=$(find ~/.claude/plugins -type f -path "*/ci/skills/payload-snapshot/scripts/payload_snapshot.py" 2>/dev/null | sort | head -1)
fi
if [ -z "$SNAPSHOT_SCRIPT" ] || [ ! -f "$SNAPSHOT_SCRIPT" ]; then echo "ERROR: payload_snapshot.py not found" >&2; exit 2; fi
python3 "$SNAPSHOT_SCRIPT" <payload_tag>
```

After locating `summary.json`, set `SNAPSHOT_DIR` to the directory containing it. All relative paths in `summary.json` (e.g., `job_json`, `junit_results`, `build_log`, PR paths) resolve from this directory.


## Extract Failure Data from Snapshot

Read `summary.json` to extract all data needed for analysis. The snapshot has already done the work of fetching payloads, building the chain, tracking streaks, and collecting PR data.

### Payload Metadata

From `summary.json` top-level fields:
- `payload_tag`, `phase`, `release_url`, `source`, `architecture`, `stream`, `version`
- `chain_length`, `baseline_tag`, `hours_since_baseline`


**Record `phase` verbatim** from the `summary.json` metadata (`Accepted`, `Rejected`, or `Ready`). Never infer the phase from the job results or from whether failures exist — a payload can be `Accepted` *with* blocking failures (force-accepted) or `Ready` while jobs are still running. For a Ready payload, analyze the blocking jobs that have completed and failed so far; do not wait for jobs that are still running. The stored phase drives the force-accept decision and the executive summary, so an inferred phase silently corrupts both.

### If the Snapshot Is Incomplete, Collect the Data Yourself

Check `summary.json` → `data_complete`. An absent `test_failure_count` means
*unknown*, not zero — never conclude a job had no test failures, and therefore
failed for some other reason, from missing data.

When data is missing, collect it yourself from the job's `gcs_url` artifacts
rather than analyzing around the gap. Do the same for any payload in the chain
whose per-test data is missing. Report a gap as a limitation only when the
artifacts themselves are unreachable.

An aggregated job with no per-test results at all is **unclassified**, not part
of a regression streak — aggregation also fails when too few child runs
completed or infrastructure killed them. Check the child runs: one that died
before the test phase cannot have failed a test.

### Failed Blocking Jobs

From `summary.json` → `blocking_jobs.failed_jobs[]`, each entry contains:
- `name`, `state`, `prow_url`, `gcs_url`, `is_aggregated`, `retries`
- `rhcos_version`: the RHCOS variant for this job (`rhcos9`, `rhcos10`, `rhcos9_10`, `rhcos9-default`, or `rhcos10-default`)
- `streak`: `streak_length`, `originating_payload`, `is_new_failure`, `failure_pattern`
- `build_log_errors`, `test_failure_count`
- Paths: `job_json`, `junit_results`, `build_log`

For each failed job, read its `job.json` (at `SNAPSHOT_DIR/<job_json>` path) to get `previousAttemptURLs`.

### Candidate PRs

For each failed job's `streak.originating_payload`, find the matching entry in `summary.json` → `payloads[]`. Its `prs[]` array contains the PRs introduced in that payload:
- `url`, `component`, `number`, `description`
- Paths to local artifacts: `diff`, `comments`, `jobs`

Treat this as a **preliminary** list only. The job-level streak merges unrelated failure modes, so its originating payload is frequently earlier than the regression being investigated — and candidates gathered from it can omit the causal PR entirely. `test_failures.blocking[].first_failed_in` is also preliminary: it tracks the test name, not the current minimal causal signature. Before scoring, re-derive the originating payload per atomic signature from raw artifacts and collect candidates from that payload.


### Test Failure Details

Only `test_failures.blocking[]` contains failures that can reject the payload. **`test_failures.informing[]` and `test_failures.flakes[]` cannot fail a job or reject a payload** — never score them as candidate causes, never use them to derive a failure mode's originating payload, and never propose a revert for them.

**"Informing job" ≠ "informing test."** These are two completely different
concepts that share a name:

- **Informing job** (`informing_jobs.failed_jobs[]`): a CI *job* that runs
  for visibility but does not gate the payload. Its pass/fail status is
  job-level. An informing job can still contain blocking tests.
- **Informing test** (`test_failures.informing[]`): an individual *test case*
  with `lifecycle="informing"`. It can appear inside any job — blocking or
  informing. Its results never count toward `test_failure_count`.

Never combine informing-job counts with informing-test lists. When
reporting informing/flake tests, list individual test names from
`test_failures.informing[]` / `test_failures.flakes[]` — do NOT report
informing *job* failure counts in the same section.

Report informing and flake tests in their own section of the report, under a heading that says so, with this caveat:

> These tests do not by themselves cause job failures or payload rejections. The only potential impact is if the test itself affects cluster health — for example if it breaks an operator or does something otherwise catastrophic.

Keep them visible: informing tests are new tests being stabilized, and a badly-behaved test can occasionally damage the cluster it runs on. Investigate one only when there is evidence of that, and say plainly that it is not a rejection cause.

From `summary.json` → `test_failures.blocking[]`:
- `test_name`, `jobs`, `first_failed_in`, `payloads_failing`
- `failure_message`, `failure_text` (full, not truncated)

### Build Log Errors

For deeper context, read `build_log.json` (at the `build_log` path) for any failed job. It contains `error_warning_lines[]` with `line_number` and `text`, plus `tail_lines[]` (last 20% of the log).

### RHCOS RPM Changes

For each failed job's `streak.originating_payload`, find the matching entry in `summary.json` → `payloads[]` and check for `rhcos_changes[]`. This array (when present) contains per-RHCOS-variant RPM diffs showing which packages changed in the underlying RHCOS image for that payload:

- `name`: Human-readable version (e.g., "Red Hat Enterprise Linux CoreOS 10.2")
- `tag`: Image stream tag — maps to job RHCOS variants:
  - `rhel-coreos` → applies to jobs with `rhcos_version` of `rhcos9` or `rhcos9-default`
  - `rhel-coreos-10` → applies to jobs with `rhcos_version` of `rhcos10` or `rhcos10-default`
  - Both apply to `rhcos9_10` (heterogeneous) jobs
- `changed`: `{package_name: {"old": old_version, "new": new_version}}`
- `added`: newly added packages (when present)
- `removed`: removed packages (when present)

For each failed job, identify the matching RHCOS variant's RPM changes (if any) based on the job's `rhcos_version` field and the RHCOS tag mapping above. Pass these changes into the job investigation and consider them as potential suspects during attribution.
