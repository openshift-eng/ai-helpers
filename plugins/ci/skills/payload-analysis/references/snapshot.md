# Snapshot and Scope

Establish the analysis inputs without interpreting candidate PRs.

## Parse the invocation

Capture `OUTPUT_DIR="$(pwd)"`. Parse the full payload tag into version, stream,
and architecture. A tag without an architecture segment is `amd64`.

Locate `summary.json` in this order:

1. the explicit `--snapshot-dir`;
2. the current directory;
3. `payload/<version>/<stream>/`.

Verify that its `payload_tag` matches. If no snapshot exists, run the
`payload-snapshot` script for the requested tag and use its output directory.
All paths in `summary.json` resolve relative to `SNAPSHOT_DIR`.

The snapshot may use release-controller or Sippy data. Use Sippy-backed payload
and changelog entries when release-controller data has been garbage collected.
Treat unavailable release-controller-only fields as unknown, not empty.

## Record payload metadata

Copy these values verbatim into working state:

- `payload_tag`, `phase`, `release_url`, `source`;
- `version`, `stream`, `architecture`;
- `chain_length`, `baseline_tag`, `hours_since_baseline`.

Do not infer `phase` from failures. Accepted payloads can contain blocking
failures, and Ready payloads can already have failed jobs.

## Enumerate work

From `blocking_jobs.failed_jobs[]`, record for every failed blocking job:

- name, Prow and GCS URLs, aggregation status, retries;
- `previousAttemptURLs` from its job metadata;
- RHCOS variant;
- job-level streak fields;
- paths to job metadata, JUnit, and build-log summaries;
- whether test data and artifacts are complete.

Only failed blocking jobs require causal investigation. Keep informing jobs
visible for context, but do not count them as payload blockers.

`test_failures.blocking[]` contains tests capable of failing blocking jobs.
`test_failures.informing[]` and `test_failures.flakes[]` do not independently
reject a payload. An informing test is not the same thing as an informing job.

Missing test counts mean unknown, not zero. For an aggregated job with no
per-test results, inspect child-run completion before classifying it; too few
completed children is not a test regression.

## Initialize analysis state

Create `analysis-state.yaml` with:

```yaml
payload: {}
snapshot_dir: ""
failed_jobs: []
failure_modes: []
candidates: []
rhcos_suspects: []
decisions: {}
```

Populate only `payload`, `snapshot_dir`, and `failed_jobs` in this phase. Do
not read PR descriptions or diffs yet.
