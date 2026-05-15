---
name: Archive Payload Result
description: Build a hermetic eval archive from an original Claude payload agent session — extracts all tool call responses, downloads GCS artifacts, and saves reference outputs
---

# Archive Payload Result

This skill builds a complete hermetic eval archive by extracting everything from the original Claude payload agent session that analyzed a payload. The session tarball contains all tool call responses (fetch_payloads, fetch_new_prs, curl, gh) — this skill extracts them, downloads the GCS artifacts for failed jobs, saves reference outputs, and compresses the result.

The archive enables fully offline, reproducible eval runs via the eval shims.

## When to Use This Skill

Use this skill when you need to:

- Create a reproducible eval archive for a payload analysis case
- Snapshot CI state before GCS artifacts are garbage-collected (30-90 day window)
- Build a complete hermetic archive from a previous Claude payload agent run

## Implementation Steps

### Step 1: Parse Arguments

The first argument is a **full payload tag** (e.g., `4.22.0-0.nightly-2026-03-20-053450`). Parse from it:

- `tag`: The specific payload tag
- `version`: Extract from the tag (e.g., `4.22` from `4.22.0-0.nightly-...`)
- `stream`: Extract from the tag (e.g., `nightly` from `4.22.0-0.nightly-...`)
- `architecture`: Inferred from the tag. The tag format is `<version>-0.<stream>[-<arch>]-<timestamp>`. If no architecture is present between the stream and timestamp, it is `amd64`. Otherwise, the architecture is the segment between the stream and timestamp. Examples:
  - `4.22.0-0.nightly-2026-02-25-152806` → `amd64`
  - `4.22.0-0.nightly-arm64-2026-02-25-152806` → `arm64`
  - `4.22.0-0.nightly-ppc64le-2026-02-25-152806` → `ppc64le`
  - `4.22.0-0.nightly-s390x-2026-02-25-152806` → `s390x`
  - `4.22.0-0.nightly-multi-2026-02-25-152806` → `multi`

Optional flags:

- `--output-dir DIR`: Base directory for the archive (default: `eval/archives`)

Set the archive directory to `{output-dir}/{tag}/`.

### Step 2: Find and Download Claude Session Tarball

This is the critical step — everything else derives from the session. Locate the original Claude payload agent session that analyzed this payload.

Search two GCS job variants:
- `periodic-ci-openshift-release-main-claude-payload-agent`
- `periodic-ci-openshift-release-main-claude-payload-agent-no-slack`

For each job variant:

1. List recent build IDs from gcsweb:
   ```bash
   curl -sL "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/$JOB/" | grep -oP '\d{19}' | sort -nu
   ```

2. For each build, check if this payload's output exists in the artifacts:
   ```bash
   curl -sL "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/$JOB/$BUILD_ID/artifacts/claude-payload-agent/openshift-claude-payload-agent/artifacts/" | grep -oP "payload-results-${TAG//./\\.}"
   ```

3. When found, download the session tarball and note the build ID:
   ```bash
   SESSION_FILE=$(curl -sL "...$BUILD_ID/artifacts/.../artifacts/" | grep -oP 'claude-sessions-[^"]+\.tar' | head -1)
   gcloud storage cp "gs://test-platform-results/logs/$JOB/$BUILD_ID/artifacts/claude-payload-agent/openshift-claude-payload-agent/artifacts/$SESSION_FILE" "/tmp/$SESSION_FILE"
   ```

**Optimization**: Use the payload tag's date to narrow the search. The build that analyzed a payload from date D typically ran on date D or D+1. Convert the date to an approximate build ID range using the calibration that build IDs increase by ~347 billion per day from a known reference point.

If no session tarball is found in either job variant, **stop and report an error**. The archive cannot be used for hermetic eval runs without the cached tool call responses from the session.

### Step 3: Extract Tool Call Responses from Session

Run the extraction script on the downloaded session tarball:

```bash
python3 scripts/extract_session_data.py "$SESSION_TARBALL" "$ARCHIVE" "$TAG"
```

This parses the Claude session JSONL files and extracts all tool call responses into the archive cache structure:

- `api-responses/fetch-payloads-{arch}-{version}-{stream}.json` — original fetch_payloads response
- `api-responses/fetch-new-prs-{tag}.json` — original fetch_new_prs responses (one per payload)
- `api-responses/curl-rc-*.json` — Release controller API responses from curl calls
- `api-responses/curl-sippy-*.json` — Sippy API responses from curl calls
- `gh-cache/{org}/{repo}/{pr_number}.json` — `gh pr view` responses
- `gh-cache/{repo}/pr-list-{search}.json` — `gh pr list` responses
- `gh-cache/api/{endpoint}.json` — `gh api` endpoint responses
- `gh-cache/raw/{path}` — `raw.githubusercontent.com` file content
- `failed-direct-jobs.txt` — GCS paths of directly failed blocking jobs
- `failed-aggregated-jobs.txt` — GCS paths of aggregated failed blocking jobs

### Step 4: Download Failed Job GCS Artifacts

Using the `failed-direct-jobs.txt` and `failed-aggregated-jobs.txt` produced by Step 3, download the full artifact tree for each failed job:

```bash
gcloud storage cp -r "gs://{gcs_path}/" "$ARCHIVE/{gcs_path}/"
```

**Run downloads in parallel** (up to 10 concurrent) to maximize throughput:

```bash
MAX_PARALLEL=10
running=0

for gcs_path in $(cat "$ARCHIVE/failed-direct-jobs.txt" "$ARCHIVE/failed-aggregated-jobs.txt" 2>/dev/null | sort -u); do
  mkdir -p "$ARCHIVE/$(dirname "$gcs_path")"
  gcloud storage cp -r "gs://$gcs_path/" "$ARCHIVE/$gcs_path/" 2>&1 &

  running=$((running + 1))
  if [ "$running" -ge "$MAX_PARALLEL" ]; then
    wait -n
    running=$((running - 1))
  fi
done
wait
```

Some downloads may fail (e.g., if the GCS artifacts have been garbage-collected). Log failures but continue.

### Step 5: Discover and Download Underlying Jobs for Aggregated Failures

For each **aggregated** failed job (from `failed-aggregated-jobs.txt`), discover the underlying job artifacts:

1. Find JUnit XML files in the downloaded artifacts:
   ```bash
   find "$ARCHIVE/{gcs_path}/artifacts/" -name 'junit*.xml' -path '*/aggregated*'
   ```

2. Parse each JUnit XML to extract underlying job URLs from `<system-out>` blocks. The `<system-out>` contains YAML with a `humanurl` field:
   ```
   humanurl: https://prow.ci.openshift.org/view/gs/test-platform-results/logs/{underlying-job-name}/{build-id}
   ```

3. Extract the GCS path from each `humanurl` and download the artifact tree (same pattern as Step 4).

4. Deduplicate: if the same underlying job/build-id is referenced by multiple aggregated jobs, download it only once.

Run these underlying job downloads in parallel as well.

**Important**: The underlying job name cannot be derived from the aggregated job name — it must be extracted from the JUnit artifacts.

### Step 6: Save Reference Outputs

Download the original analysis output files from the same GCS build (found in Step 2) into `$ARCHIVE/reference/`. These serve as gold-standard references for evaluating the skill's output quality.

```bash
mkdir -p "$ARCHIVE/reference"
ARTIFACTS_PATH="gs://test-platform-results/logs/$JOB/$BUILD_ID/artifacts/claude-payload-agent/openshift-claude-payload-agent/artifacts"
gcloud storage cp "$ARTIFACTS_PATH/payload-results-*.yaml" "$ARCHIVE/reference/" 2>/dev/null
gcloud storage cp "$ARTIFACTS_PATH/payload-analysis-*-summary.html" "$ARCHIVE/reference/" 2>/dev/null
gcloud storage cp "$ARTIFACTS_PATH/payload-analysis-*-autodl.json" "$ARCHIVE/reference/" 2>/dev/null
```

### Step 7: Compress Archive

Create a compressed tarball of the complete archive:

```bash
tar czf "${ARCHIVE}.tar.gz" -C "$(dirname "$ARCHIVE")" "$(basename "$ARCHIVE")"
```

The eval shims can transparently extract compressed archives on demand, so the uncompressed directory can optionally be removed after compression.

### Step 8: Report Results

After all downloads complete, report:

1. **Archive path**: The full path to the archive directory
2. **Session tarball**: Which job/build ID, number of cached tool responses extracted
3. **API responses extracted**: fetch_payloads, fetch_new_prs count, curl API count, gh count
4. **Number of failed jobs**: Direct + aggregated from the session data
5. **Number of underlying jobs discovered**: From aggregated job JUnit XML
6. **Number of failed GCS downloads**: If any
7. **Reference outputs**: Number of reference files saved (expected: 3 — YAML, HTML, JSON)
8. **Compressed tarball size**: Size of the `.tar.gz` file
9. **Total archive size** (uncompressed): Run `du -sh "$ARCHIVE"` and report

## Notes

- **Session-first**: Everything is derived from the original Claude session tarball. No live API calls to fetch_payloads or fetch_new_prs — those responses are extracted from the session.
- **Session required**: The skill will not proceed without a session tarball. Without cached tool call responses, the eval shims cannot serve data and the archive is useless.
- **Failed jobs only**: Only artifacts from failed blocking jobs are archived (extracted from the session's fetch_payloads response).
- **Aggregated → underlying**: For aggregated failed jobs, the underlying job artifacts are discovered from JUnit XML `<system-out>` `humanurl` fields.
- **GCS access**: The `test-platform-results` bucket is publicly readable.
- **Disk space**: Full artifact trees can be large (hundreds of MB to several GB per job).
- **Session tarball search**: Two GCS job variants are searched (`claude-payload-agent` and `claude-payload-agent-no-slack`). Build ID calibration (~347 billion/day increase) narrows the search window.
