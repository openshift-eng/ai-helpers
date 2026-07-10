---
name: payload-blocking-runs
description: List gcsweb artifact URLs for /payload test runs on a pull request, filtered to the current release blocking jobs
---

# Payload Blocking Runs

This skill lists the gcsweb artifact URLs for `/payload` test runs that were triggered on a specific GitHub pull request. It queries the CI analytics BigQuery table (`openshift-gce-devel.ci_analysis_us.jobs`) for payload jobs associated with the PR, and — unless `--all-jobs` is given — filters them down to the runs that correspond to the **blocking jobs** of one or more release streams. The blocking-job set is read live from the OpenShift release controller.

The output is a sorted list of gcsweb artifact base URLs (one per line), which can be fed directly into other tools such as the `kubelet-version-check` skill.

## When to Use This Skill

Use this skill when you need to:

- Enumerate the `/payload` runs a developer launched on a PR to validate it against the release's blocking jobs
- Determine which blocking jobs have (and have not) been exercised for a PR before merge
- Produce a list of artifact URLs to feed into downstream per-run analysis (e.g. kubelet version checks, disruption analysis)
- Audit payload-testing coverage for a change over a date range

## Prerequisites

1. **Python 3**: Python 3.9 or later
   - Check: `python3 --version`

2. **Python packages**: `google-cloud-bigquery` and `requests`
   - Check: `python3 -c "import google.cloud.bigquery, requests"`
   - Install: `pip install google-cloud-bigquery requests`

3. **BigQuery access via ADC**: The script authenticates to BigQuery using Application Default Credentials (ADC).
   - Set up once: `gcloud auth application-default login`
   - The account needs read access to `openshift-gce-devel.ci_analysis_us.jobs` and a billing/quota project.

4. **Network access** to the OpenShift release controller (needed for the blocking-job filter):
   - `curl -s https://amd64.ocp.releases.ci.openshift.org/api/v1/releasestream/4.20.0-0.nightly/latest`
   - Not required when using `--all-jobs`.

## Implementation Steps

### Step 1: Locate and Run the Script

```bash
# Locate the Python script
PAYLOAD_BLOCKING="${CLAUDE_PLUGIN_ROOT}/skills/payload-blocking-runs/payload_blocking_runs.py"
if [ ! -f "$PAYLOAD_BLOCKING" ]; then
  PAYLOAD_BLOCKING=$(find ~/.claude/plugins -type f -path "*/ci/skills/payload-blocking-runs/payload_blocking_runs.py" 2>/dev/null | sort | head -1)
fi
if [ -z "$PAYLOAD_BLOCKING" ] || [ ! -f "$PAYLOAD_BLOCKING" ]; then echo "ERROR: payload_blocking_runs.py not found" >&2; exit 2; fi

# List blocking-job payload runs for a PR since a start date
python3 "$PAYLOAD_BLOCKING" \
  --org openshift --repo machine-config-operator --pr 5509 \
  --start 2026-01-01 \
  --streams 4.20.0-0.nightly 4.20.0-0.ci
```

### Step 2: Choose the Filtering Mode

- **Blocking-jobs filter (default)**: Pass one or more `--streams`. The script reads each stream's blocking jobs from the release controller, derives a test suffix for each, and keeps only payload runs whose job name contains one of those suffixes.
- **All payload runs**: Pass `--all-jobs` to skip the blocking-job filter entirely (no `--streams` needed).

### Step 3: Consume the Output

The script prints one gcsweb artifact base URL per line, sorted:

```text
https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/<job-name>/<build-id>/
...
```

Write it to a file for downstream tools:

```bash
python3 "$PAYLOAD_BLOCKING" --repo machine-config-operator --pr 5509 \
  --start 2026-01-01 --streams 4.20.0-0.nightly -o payload-runs.txt
```

### Step 4: Inspect Diagnostics (optional)

- `-v` / `--verbose`: prints, to stderr, the extracted blocking suffixes, how many BigQuery rows matched, and the names of rows that matched no suffix.
- `--show-jobs`: prints, to stderr, the unique job names among the selected runs.

## Command-Line Reference

| Flag | Required | Description |
|------|----------|-------------|
| `--org` | no (default `openshift`) | GitHub org that owns the PR |
| `--repo` | yes | GitHub repo that owns the PR |
| `--pr` | yes | Pull request number (integer) |
| `--start` | yes | Earliest run start date (UTC, `YYYY-MM-DD`) |
| `--end` | no (default now) | Latest run start date (UTC, `YYYY-MM-DD`, inclusive of the day) |
| `--streams` | yes, unless `--all-jobs` | Release stream name(s), e.g. `4.20.0-0.nightly` |
| `--all-jobs` | no | Skip the blocking-job filter (return every payload run) |
| `--show-jobs` | no | Print unique matched job names to stderr |
| `-v`, `--verbose` | no | Print filter diagnostics to stderr |
| `-o`, `--output` | no (default stdout) | Write the URL list to a file |

## How the Blocking Filter Works

1. For each `--streams` value, the script fetches `https://amd64.ocp.releases.ci.openshift.org/api/v1/releasestream/<stream>/latest`.
2. From `results.blockingJobs`, each job's Prow URL is parsed to recover the periodic prowjob name.
3. The "test suffix" is the portion after the last `nightly-<x.y>-` / `ci-<x.y>-` prefix (e.g. `...nightly-4.20-e2e-aws-ovn-serial` → `e2e-aws-ovn-serial`).
4. Release-controller keys beginning with `aggregated-` are kept verbatim as suffix patterns.
5. A payload run is kept if its `prowjob_name` contains any extracted suffix.

## Error Handling

- **Missing `--streams` without `--all-jobs`**: the script exits with an argument error.
- **Missing dependencies**: exits with code `2` and an install hint.
- **BigQuery auth/setup failure**: exits with an error pointing to `gcloud auth application-default login`.
- **A release stream cannot be fetched**: prints a `WARNING` to stderr and continues with the remaining streams.
- **No blocking suffixes extracted**: prints a `WARNING` (nothing will match); re-run with `--all-jobs` or verify the stream names.

**Exit Codes:**
- `0`: Success
- `2`: Missing dependency or invalid arguments
- non-zero: BigQuery or date-parsing errors

## Examples

### Example 1: Blocking runs for a PR across two streams

```bash
python3 "$PAYLOAD_BLOCKING" \
  --repo machine-config-operator --pr 5509 \
  --start 2026-01-01 \
  --streams 4.20.0-0.nightly 4.20.0-0.ci
```

### Example 2: Every payload run (no blocking filter), written to a file

```bash
python3 "$PAYLOAD_BLOCKING" \
  --repo cluster-network-operator --pr 2450 \
  --start 2026-02-01 --end 2026-02-28 \
  --all-jobs -o payload-runs.txt
```

### Example 3: Verbose diagnostics with the matched job names

```bash
python3 "$PAYLOAD_BLOCKING" \
  --repo origin --pr 29000 \
  --start 2026-03-01 \
  --streams 4.20.0-0.nightly \
  --verbose --show-jobs
```

## Notes

- `prowjob_pull_number` is stored as a STRING in BigQuery; the script converts `--pr` accordingly.
- Only jobs whose `prowjob_name` contains `payload` are considered (this excludes ordinary `pull-ci-*` presubmits that are not payload runs).
- The blocking-job set is read from the *latest* payload of each stream, so it reflects the current blocking configuration.
- Dates are interpreted in UTC; `--end` is inclusive of the entire day.

## See Also

- Related Skill: `kubelet-version-check` (consumes the URL list this skill produces)
- Related Skill: `fetch-payloads` (lists recent payloads and their blocking job results)
- Related Command: `/ci:list-payload-blocking-runs` (wraps this skill and adds coverage analysis)
