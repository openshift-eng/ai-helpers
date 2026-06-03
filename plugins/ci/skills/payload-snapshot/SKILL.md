---
name: payload-snapshot
description: Snapshot OpenShift payload data (release controller, PR diffs, comments, CI jobs, JUnit results, regression tracking) to a local directory for offline analysis
---

# Payload Snapshot

This skill downloads all data needed to analyze an OpenShift payload into a local directory tree. The resulting snapshot can be navigated entirely via file reads — no live API calls required during analysis.

## When to Use This Skill

Use this skill when you need to:

- Analyze a rejected payload and want all data available locally before starting
- Create a reproducible snapshot of payload state at a point in time
- Track test failure regressions across multiple payloads
- Work offline or reduce API calls during payload analysis

## Prerequisites

1. **Python 3** (3.10 or later)
   - Uses only standard library (no external dependencies)

2. **GitHub CLI (`gh`)** — for PR diff, comment, and job data
   - Install: `brew install gh` (macOS) or see https://cli.github.com
   - Authenticate: `gh auth login`
   - Without `gh`, release controller data is still fetched; PR data is skipped

3. **Google Cloud SDK (`gcloud`)** — for JUnit test result download
   - Install: `brew install google-cloud-sdk` (macOS) or see https://cloud.google.com/sdk
   - Authenticate: `gcloud auth login`
   - Without `gcloud`, JUnit data is skipped; job directories still created

4. **Network access** to:
   - `*.ocp.releases.ci.openshift.org` (release controller)
   - `api.github.com` (via `gh` CLI)
   - `storage.googleapis.com` (via `gcloud` CLI)

## Implementation Steps

### Step 1: Run the Snapshot Script

```bash
script_path="plugins/ci/skills/payload-snapshot/scripts/payload_snapshot.py"

# Snapshot a specific payload
python3 "$script_path" 4.22.0-0.nightly-2026-02-25-152806

# Custom output directory
python3 "$script_path" 4.22.0-0.nightly-2026-02-25-152806 --output-dir .work/snapshot

# Limit chain depth
python3 "$script_path" 4.22.0-0.nightly-2026-02-25-152806 --max-chain 5

# Skip JUnit download (faster, still generates job structure and summary)
python3 "$script_path" 4.22.0-0.nightly-2026-02-25-152806 --no-junit
```

The script will:
1. Parse the payload tag to determine version, stream, and architecture
2. Probe all available streams for the version (nightly, ci, across architectures)
3. Chain backwards through previous payloads until finding one where all blocking jobs passed
4. For each payload in the chain, download release controller data and the changelog (PR diff)
5. Split jobs into blocking/informing directories with metadata and GCS browser links
6. For each failed blocking job, download and parse JUnit XML test results
7. For each failed blocking job, download build-log.txt from GCS and extract error/warning lines + log tail
8. Track test failure regressions — when did each failure first appear?
9. Track per-job failure streaks — consecutive failures, originating payload, failure pattern
10. For each unique PR across all changelogs, fetch the git diff, comments, and CI jobs via `gh`
11. Generate summary.json with comprehensive triage data, plus AGENTS.md/CLAUDE.md for agent orientation

### Step 2: Navigate the Snapshot

The output directory is structured for easy navigation:

```text
payload/
  <version>/
    <stream>/
      summary.json                         # START HERE — full triage data
      CLAUDE.md                            # Imports AGENTS.md for Claude Code
      AGENTS.md                            # Dynamic snapshot orientation doc
      streams.json                         # All streams for this version
      <tag>/                               # Each payload in the chain
        payload.json                       # Release controller API response
        changelog.json                     # PRs that changed vs. previous payload
        regressions.json                   # Test failure regression tracking
        jobs/
          blocking/
            <job-name>/
              job.json                     # Job metadata (state, URLs, GCS link, retries)
              build_log.json               # Error/warning lines + log tail (failed only)
              junit/                       # Only for failed jobs
                junit_operator.xml         # CI phase results
                junit-aggregated.xml       # Aggregated jobs only
                results.json               # Parsed test failures (full output)
          informing/
            <job-name>/
              job.json                     # Job metadata only (no JUnit/build log)
        <component>/                       # e.g., machine-config-operator
          prs/
            <pr_number>/
              code.diff                    # Git diff of the PR
              comments.json                # PR comments and reviews
              jobs.json                    # CI check runs
```

### Step 3: Use the Data

**Find failed blocking jobs (with streaks):**
```bash
jq '.blocking_jobs.failed_jobs[] | {name, state, streak: .streak.streak_length, pattern: .streak.failure_pattern}' payload/<version>/<stream>/summary.json
```

**Check test failures and when they started:**
```bash
jq '.[] | {test: .test_name, first_failed: .first_failed_in, payloads: .payloads_failing, jobs: .jobs}' payload/<version>/<stream>/<tag>/regressions.json
```

**List PRs in a payload:**
```bash
jq '.changeLogJson.updatedImages[].commits[] | {component: .name, pr: .pullURL, subject: .subject}' payload/<version>/<stream>/<tag>/changelog.json
```

**Read a specific PR's diff:**
```bash
cat payload/<version>/<stream>/<tag>/<component>/prs/<number>/code.diff
```

**Check JUnit failures for a specific job:**
```bash
jq '.[].name' payload/<version>/<stream>/<tag>/jobs/blocking/<job-name>/junit/results.json
```

## CLI Reference

```text
python3 payload_snapshot.py <payload_tag> [OPTIONS]

Positional:
  payload_tag          Payload tag (e.g., 4.22.0-0.nightly-2026-02-25-152806)

Options:
  --output-dir DIR     Base output directory (default: payload)
  --max-chain N        Maximum backward chain depth (default: 20)
  --workers N          Parallel workers for API calls (default: 8)
  --no-junit           Skip JUnit download and regression tracking
```

## Output Files

### `streams.json`

Lists all available streams for the payload's version.

### `summary.json`

Comprehensive stream-level triage data — start here. Contains:
- Payload metadata: `payload_tag`, `phase`, `release_url`, `architecture`, `stream`, `version`
- Chain data: `chain_length`, `baseline_tag`, `hours_since_baseline`
- `blocking_jobs.failed_jobs[]` — detailed objects with `name`, `state`, `prow_url`, `gcs_url`, `streak` (streak_length, originating_payload, is_new_failure, failure_pattern), `build_log_errors`, `test_failure_count`, and relative paths to `job_json`, `junit_results`, `build_log`
- `informing_jobs.failed_jobs[]` — job name strings
- `test_failures.blocking[]` — `test_name`, `jobs`, `first_failed_in`, `payloads_failing`, `failure_message`, `failure_text` (full, not truncated)
- `payloads[]` — per-payload entries with `tag`, `phase`, relative file paths, and `prs[]` with component/diff/comments paths

### `AGENTS.md` / `CLAUDE.md`

Dynamic orientation document generated at snapshot time. Contains the specific payload tag, chain, failed jobs, file layout, key concepts, and summary.json schema. `CLAUDE.md` imports `AGENTS.md` via `@AGENTS.md`.

### `payload.json`

Full release controller response including `blockingJobs`, `informingJobs`, and `asyncJobs` with their states, Prow URLs, and retry attempt URLs.

### `changelog.json`

Release controller diff response with `changeLogJson.updatedImages` listing every PR that changed between this payload and its predecessor.

### `regressions.json`

Per-payload regression tracking data. For each failing test in the target payload:
- `test_name`: the failing test
- `jobs`: which jobs it fails in
- `first_failed_in`: the earliest payload in the chain where it was failing
- `payloads_failing`: how many consecutive payloads it has been failing
- `failure_message`: the error message
- `failure_text`: full failure output

### `job.json`

Per-job metadata including name, state, lifecycle (blocking/informing), Prow URL, GCS browser URL (`gcs_url`), retry count, whether it's an aggregated job, and GCS bucket path.

### `build_log.json` (failed blocking jobs only)

Extracted from `build-log.txt` in GCS (handles gzip decompression). Contains:
- `total_lines`: total line count of the build log
- `error_warning_count`: number of lines matching error/warning patterns
- `error_warning_lines[]`: each with `line_number` and `text`
- `tail_start_line`, `tail_lines[]`: last 20% of the log for context

### `results.json` (in junit/ subdirectory)

Parsed JUnit test failures for a specific job. Only includes failed/error tests. For aggregated jobs, includes per-run pass/fail/skip data with Prow URLs for each run.

### `code.diff`, `comments.json`, `jobs.json`

PR artifacts from GitHub (unchanged from previous version).

## Chain Logic

The script chains backwards from the target payload until it finds a payload where **all blocking jobs succeeded**. This is stricter than the `Accepted` phase — a payload can be force-accepted with failed blocking jobs, which does not count as a stop point.

For terminal payloads (Accepted/Rejected), jobs showing `Pending` on the release controller are cross-checked against the actual Prow `prowjob.json` artifact to get their real state.

## Aggregated Jobs

Aggregated jobs run the same underlying test multiple times with statistical analysis. The script:
- Detects aggregated jobs by the `aggregated-` name prefix
- Downloads `junit-aggregated.xml` which contains per-run pass/fail/skip data
- Parses the YAML in `<system-out>` to extract individual run URLs

## Error Handling

- **Tag not found**: Exits with code 2 and a descriptive error
- **Release controller unreachable**: Exits with code 1
- **`gh` not authenticated**: Prints a warning and continues without PR data
- **`gcloud` not available**: Prints a warning and skips JUnit download
- **Individual job/PR fetch failure**: Logs a warning and continues
- **Idempotent**: Re-running skips files that already exist

## Notes

- The script uses only Python standard library — no pip dependencies
- PR data is deduplicated across payloads — each PR is fetched once
- JUnit and build-log download are scoped to failed blocking jobs only (informing jobs get `job.json` but no JUnit or build log)
- The `--workers` flag controls parallelism for all subprocess calls (default 8)
- Summary is always regenerated on re-run (not skipped like other files)
- Progress is printed to stderr; the script produces no stdout output

## See Also

- Related Skill: `fetch-payloads` (fetches recent payloads from the release controller)
- Related Skill: `fetch-new-prs-in-payload` (fetches PRs new in a specific payload)
- Related Skill: `payload-analysis` (analyzes a payload snapshot for revert candidates)

