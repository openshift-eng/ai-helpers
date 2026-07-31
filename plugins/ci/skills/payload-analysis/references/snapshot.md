# Snapshot and Scope

Use the snapshot to define the payload and investigation queue. Do not inspect
candidate PRs in this step.

## Locate the snapshot

1. Capture `OUTPUT_DIR="$(pwd)"`.
2. Parse the payload tag into version, stream, and architecture. Use `amd64`
   when the tag has no architecture segment.
3. Look for `summary.json` in:
   - the explicit `--snapshot-dir`;
   - the current directory;
   - `payload/<version>/<stream>/`.
4. Verify that `summary.json.payload_tag` matches the requested tag.
5. If no matching snapshot exists, use `ci:payload-snapshot` to create one.
6. Set `SNAPSHOT_DIR` to the directory containing `summary.json`. Resolve all
   snapshot paths from this directory.

Use Sippy-backed payload and changelog entries when release-controller data has
been garbage collected. Record release-controller-only fields as unknown when
they are unavailable.

## Record the payload

Copy these fields into working state without inferring replacements:

- `payload_tag`, `phase`, `release_url`, and `source`;
- `version`, `stream`, and `architecture`;
- `chain_length`, `baseline_tag`, and `hours_since_baseline`.

Do not derive `phase` from job outcomes. Accepted payloads can contain blocking
failures, and Ready payloads can already contain failed jobs.

## Queue failed jobs

For every entry in `blocking_jobs.failed_jobs[]`, record:

- job name, Prow URL, GCS URL, aggregation status, and retries;
- `previousAttemptURLs` from the job metadata;
- RHCOS variant and job-level streak fields;
- paths to job metadata, JUnit, and build-log summaries;
- artifact and test-data completeness.

For aggregated jobs, identify failed or incomplete child runs. Do not classify
an aggregation failure as a test regression until enough child runs completed
and their results support that conclusion.

Keep these distinctions:

- failed blocking jobs require causal investigation;
- informing jobs provide context but do not block the payload;
- blocking tests can fail a blocking job;
- informing and flake tests do not independently reject a payload;
- a missing test count is unknown, not zero.

## Initialize working state

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

Populate `payload`, `snapshot_dir`, and `failed_jobs`. Leave candidate and
decision fields empty. Complete this step only when every failed blocking job
has enough location data to begin an artifact investigation or an explicit data
gap explaining why it cannot.
