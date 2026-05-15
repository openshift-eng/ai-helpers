---
description: Archive all artifacts needed to reproduce a payload analysis offline
argument-hint: "<payload-tag> [--output-dir DIR] [--limit N]"
allowed-tools: Bash, Read, Write
---

## Name

ci:archive-payload-result

## Synopsis

```
/ci:archive-payload-result <payload-tag> [--output-dir DIR] [--limit N]
```

## Description

The `ci:archive-payload-result` command downloads and archives all API responses, Prow job artifacts, and GCS artifact trees needed to reproduce a payload analysis offline. This is useful for creating evaluation datasets, debugging analysis logic without network access, or preserving a snapshot of CI state at a point in time.

**Only failed blocking job artifacts are downloaded** — successful jobs are excluded. For aggregated failed jobs, the underlying job artifacts are discovered by parsing JUnit XML and downloaded as well.

## Implementation

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
- `--limit N`: How many payloads to fetch from the release controller (default: `15`)

Set the archive directory to `{output-dir}/{tag}/`.

### Step 2: Locate Scripts

Locate the fetch scripts using the standard plugin lookup pattern:

```bash
FETCH_PAYLOADS="${CLAUDE_PLUGIN_ROOT}/skills/fetch-payloads/fetch_payloads.py"
if [ ! -f "$FETCH_PAYLOADS" ]; then
  FETCH_PAYLOADS=$(find ~/.claude/plugins -type f -path "*/ci/skills/fetch-payloads/fetch_payloads.py" 2>/dev/null | sort | head -1)
fi
if [ -z "$FETCH_PAYLOADS" ] || [ ! -f "$FETCH_PAYLOADS" ]; then echo "ERROR: fetch_payloads.py not found" >&2; exit 2; fi

FETCH_NEW_PRS="${CLAUDE_PLUGIN_ROOT}/skills/fetch-new-prs-in-payload/fetch_new_prs_in_payload.py"
if [ ! -f "$FETCH_NEW_PRS" ]; then
  FETCH_NEW_PRS=$(find ~/.claude/plugins -type f -path "*/ci/skills/fetch-new-prs-in-payload/fetch_new_prs_in_payload.py" 2>/dev/null | sort | head -1)
fi
if [ -z "$FETCH_NEW_PRS" ] || [ ! -f "$FETCH_NEW_PRS" ]; then echo "ERROR: fetch_new_prs_in_payload.py not found" >&2; exit 2; fi
```

### Step 3: Create Archive Directory Structure

```bash
ARCHIVE="{output-dir}/{tag}"
mkdir -p "$ARCHIVE/api-responses"
mkdir -p "$ARCHIVE/gh-cache"
mkdir -p "$ARCHIVE/test-platform-results/logs"
```

### Step 4: Fetch Payload Data

Run `fetch_payloads.py` and save the JSON response:

```bash
python3 "$FETCH_PAYLOADS" {architecture} {version} {stream} --limit {limit} > "$ARCHIVE/api-responses/fetch-payloads-{arch}-{version}-{stream}.json"
```

Read the saved JSON to extract all payload data for subsequent steps.

### Step 5: Fetch New PRs for Each Payload

For **each payload** in the response, run `fetch_new_prs_in_payload.py` and save the output:

```bash
python3 "$FETCH_NEW_PRS" {payload_tag} --format json > "$ARCHIVE/api-responses/fetch-new-prs-{payload_tag}.json"
```

Do this for every payload in the response, not just the target payload. Some fetches may fail (e.g., if the payload is too old for the API) — log the error but continue with the remaining payloads.

### Step 6: Extract Failed Blocking Job URLs

Parse the fetch-payloads JSON to extract Prow job URLs **only from failed blocking jobs**. The JSON structure is:

```json
[
  {
    "tag": "...",
    "phase": "...",
    "results": {
      "blockingJobs": {
        "job-short-name": {
          "state": "Failed",
          "url": "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/{job-name}/{build-id}",
          "retries": 1,
          "previousAttemptURLs": ["..."]
        }
      }
    }
  }
]
```

**Only include jobs where `state` is `"Failed"`**. Skip jobs with state `"Succeeded"`, `"Pending"`, or any other state.

For each failed job:
- Extract the GCS path from the URL: strip the `https://prow.ci.openshift.org/view/gs/` prefix to get `test-platform-results/logs/{job-name}/{build-id}`
- For **non-aggregated** jobs: include `previousAttemptURLs` too (each retry may show different failure modes)
- For **aggregated** jobs: only include the final attempt URL (retries re-run aggregation only, not underlying tests)

Collect all unique GCS paths.

### Step 7: Download Failed Job GCS Artifacts

For each unique GCS path from Step 6, download the full artifact tree:

```bash
gcloud storage cp -r "gs://{gcs_path}/" "$ARCHIVE/{gcs_path}/"
```

**Run downloads in parallel** (up to 10 concurrent) to maximize throughput:

```bash
MAX_PARALLEL=10
running=0

for gcs_path in "${all_gcs_paths[@]}"; do
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

### Step 8: Discover and Download Underlying Jobs for Aggregated Failures

For each **aggregated** failed job (job short name starts with `aggregated-`), discover the underlying job artifacts:

1. Find JUnit XML files in the downloaded artifacts:
   ```bash
   find "$ARCHIVE/{gcs_path}/artifacts/" -name 'junit*.xml' -path '*/aggregated*'
   ```

2. Parse each JUnit XML to extract underlying job URLs from `<system-out>` blocks. The `<system-out>` contains YAML with a `humanurl` field:
   ```
   humanurl: https://prow.ci.openshift.org/view/gs/test-platform-results/logs/{underlying-job-name}/{build-id}
   ```

3. Extract the GCS path from each `humanurl` and download the artifact tree (same pattern as Step 7).

4. Deduplicate: if the same underlying job/build-id is referenced by multiple aggregated jobs, download it only once.

Run these underlying job downloads in parallel as well.

**Important**: The underlying job name cannot be derived from the aggregated job name — it must be extracted from the JUnit artifacts. This is why we download aggregated job artifacts first, then parse them for underlying references.

### Step 9: Report Results

After all downloads complete, report:

1. **Archive path**: The full path to the archive directory
2. **Number of payloads**: How many payloads were included
3. **Number of PR fetch responses**: How many `fetch-new-prs-*.json` files were saved
4. **Number of failed jobs downloaded**: How many unique failed job artifact trees were downloaded (direct + aggregated)
5. **Number of underlying jobs discovered**: How many underlying job artifact trees were found and downloaded from aggregated jobs
6. **Number of failed downloads**: How many GCS downloads failed (if any)
7. **Total archive size**: Run `du -sh "$ARCHIVE"` and report the result

## Return Value

- **Success**: Archive directory populated with all API responses and GCS artifacts, summary printed
- **Error**: Script location failures, network errors, or GCS access issues (partial results are still preserved)

## Examples

1. **Archive a nightly payload with defaults**:
   ```
   /ci:archive-payload-result 4.22.0-0.nightly-2026-03-20-053450
   ```

2. **Archive to a custom directory**:
   ```
   /ci:archive-payload-result 4.22.0-0.nightly-2026-03-20-053450 --output-dir /tmp/payload-archives
   ```

3. **Archive with more payloads in lookback**:
   ```
   /ci:archive-payload-result 4.22.0-0.nightly-2026-03-20-053450 --limit 30
   ```

4. **Archive an arm64 payload** (architecture inferred from tag):
   ```
   /ci:archive-payload-result 4.22.0-0.nightly-arm64-2026-03-20-053450
   ```

## Arguments

- **$1** (payload-tag): A full payload tag (e.g., `4.22.0-0.nightly-2026-03-20-053450`). Version, stream, and architecture are parsed from the tag automatically. Tags without an architecture suffix are amd64. (required)
- `--output-dir DIR`: Base directory for the archive (optional, default: `eval/archives`)
- `--limit N`: Number of payloads to fetch from the release controller (optional, default: `15`)

## Notes

- **Failed jobs only**: Only artifacts from failed blocking jobs are archived. Successful job artifacts are not downloaded. If the analysis LLM tries to access a successful job's artifacts, it should get a "not found" error — which is the correct behavior (successful jobs should not be investigated).
- **Aggregated → underlying**: For aggregated failed jobs, the underlying job artifacts are automatically discovered and downloaded. The underlying job name is extracted from JUnit XML `<system-out>` `humanurl` fields, not inferred from the aggregated job name.
- **GCS access**: The `test-platform-results` bucket is publicly readable. No authentication is required for `gcloud storage cp`.
- **Disk space**: Full artifact trees for failed blocking jobs can be large (hundreds of MB to several GB per job). Ensure sufficient disk space before running.
- **Partial archives**: If some downloads fail, the archive is still usable — missing artifacts will simply be unavailable during offline analysis.
- **gh-cache directory**: Created empty for future use by offline analysis tools that may cache GitHub API responses.
- **Idempotency**: Running the command again with the same tag and output directory will overwrite existing files. Move or rename the existing archive first if you want to preserve it.

## Skills Used

- `fetch-payloads`: Fetches payload data from the release controller
- `fetch-new-prs-in-payload`: Fetches PRs new in each payload vs its predecessor
