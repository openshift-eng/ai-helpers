---
name: Prow Job Artifact Search
description: Search, list, and fetch artifacts from Prow CI job runs stored in GCS using the gcloud CLI
---

# Prow Job Artifact Search

This skill provides a reusable Python script for browsing, searching, and fetching artifacts from Prow CI job runs stored in the `test-platform-results` GCS bucket. It wraps `gcloud storage` commands so callers do not need to construct GCS URIs or manage the CLI directly.

## When to Use This Skill

Use this skill when you need to:
- Browse the artifact directory tree of a Prow job run
- Search for specific files within a job's artifacts (e.g., interval files, node logs, journal logs)
- Fetch the contents of a specific artifact file for analysis
- Discover what artifacts are available before running a more targeted analysis skill

This skill is a building block used by other analysis workflows. Use it when you need ad-hoc artifact access that is not covered by a dedicated analysis skill.

## Prerequisites

1. **gcloud CLI Installation**
   - Check if installed: `which gcloud`
   - If not installed, provide instructions for the user's platform
   - Installation guide: https://cloud.google.com/sdk/docs/install

2. **gcloud Authentication (Optional)**
   - The `test-platform-results` bucket is publicly accessible
   - No authentication is required for read access

3. **Python 3** (3.6 or later)
   - Check: `which python3`

## Script Location

```
plugins/ci/skills/prow-job-artifact-search/prow_job_artifact_search.py
```

## Operations

### list — List directory contents

List files and subdirectories at a given path within the job's artifact tree.

```bash
python3 plugins/ci/skills/prow-job-artifact-search/prow_job_artifact_search.py \
  <prow-url> list [subpath]
```

**Arguments:**
- `prow-url` (required): The Prow job URL
- `subpath` (optional): Subdirectory path relative to the job root. If omitted, lists the job root.

**Examples:**

```bash
# List the job root
python3 .../prow_job_artifact_search.py "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-.../1234567890" list

# List e2e test artifacts
python3 .../prow_job_artifact_search.py <url> list artifacts/e2e-test/openshift-e2e-test

# List gather-extra oc_cmds
python3 .../prow_job_artifact_search.py <url> list artifacts/e2e-test/gather-extra/artifacts/oc_cmds
```

**Output:**

```json
{
  "success": true,
  "path": "gs://test-platform-results/logs/<job>/<id>/",
  "count": 5,
  "entries": [
    {
      "name": "artifacts/",
      "path": "artifacts",
      "type": "directory",
      "gcs_uri": "gs://test-platform-results/logs/<job>/<id>/artifacts/"
    },
    {
      "name": "build-log.txt",
      "path": "build-log.txt",
      "type": "file",
      "gcs_uri": "gs://test-platform-results/logs/<job>/<id>/build-log.txt"
    }
  ]
}
```

### search — Search for files matching a glob pattern

Recursively search for files matching a glob pattern under a given path.

```bash
python3 plugins/ci/skills/prow-job-artifact-search/prow_job_artifact_search.py \
  <prow-url> search <pattern> [subpath]
```

**Arguments:**
- `prow-url` (required): The Prow job URL
- `pattern` (required): Glob pattern to match. Supports `**` for recursive matching and `*` for wildcards.
- `subpath` (optional): Subdirectory to search within. If omitted, searches from the job root.

**Examples:**

```bash
# Find all interval JSON files
python3 .../prow_job_artifact_search.py <url> search "**/*intervals*.json"

# Find all e2e timeline files
python3 .../prow_job_artifact_search.py <url> search "**/e2e-timelines_spyglass_*.json"

# Find node-related oc_cmds output
python3 .../prow_job_artifact_search.py <url> search "**/nodes" artifacts

# Find journal logs for a specific node
python3 .../prow_job_artifact_search.py <url> search "**/*worker-c-7t6ng*" artifacts

# Find all junit files
python3 .../prow_job_artifact_search.py <url> search "**/junit*.xml"

# Find must-gather archives
python3 .../prow_job_artifact_search.py <url> search "**/must-gather*"
```

**Output:**

```json
{
  "success": true,
  "pattern": "gs://test-platform-results/logs/<job>/<id>/**/*intervals*.json",
  "count": 3,
  "matches": [
    {
      "name": "e2e-timelines_spyglass_20260209-043512.json",
      "path": "artifacts/e2e-test/openshift-e2e-test/e2e-timelines_spyglass_20260209-043512.json",
      "type": "file",
      "gcs_uri": "gs://test-platform-results/logs/<job>/<id>/artifacts/..."
    }
  ]
}
```

### fetch — Fetch a specific file's contents

Download and return the contents of a specific file from the job's artifacts.

```bash
python3 plugins/ci/skills/prow-job-artifact-search/prow_job_artifact_search.py \
  <prow-url> fetch <filepath> [--max-bytes N]
```

**Arguments:**
- `prow-url` (required): The Prow job URL
- `filepath` (required): Path to the file relative to the job root
- `--max-bytes` (optional): Maximum bytes to read (default: 524288 = 512KB). Files larger than this are truncated.

**Examples:**

```bash
# Fetch the build log
python3 .../prow_job_artifact_search.py <url> fetch build-log.txt

# Fetch a specific oc_cmds output
python3 .../prow_job_artifact_search.py <url> fetch artifacts/e2e-test/gather-extra/artifacts/oc_cmds/nodes

# Fetch a large file with higher limit
python3 .../prow_job_artifact_search.py <url> fetch artifacts/e2e-test/openshift-e2e-test/build-log.txt --max-bytes 2097152
```

**Output:**

```json
{
  "success": true,
  "path": "gs://test-platform-results/logs/<job>/<id>/build-log.txt",
  "size_bytes": 45230,
  "truncated": false,
  "max_bytes": 524288,
  "content": "... file contents ..."
}
```

## Common Artifact Paths

These are common artifact paths within a Prow job. The `{target}` is the CI workflow step name (e.g., `e2e-gcp-ovn-rt-rhcos10-techpreview`).

| Path | Description |
|------|-------------|
| `build-log.txt` | Top-level build log |
| `artifacts/{target}/` | All artifacts for the test step |
| `artifacts/{target}/openshift-e2e-test/` | E2E test output (build-log, junit, timelines) |
| `artifacts/{target}/openshift-e2e-test/build-log.txt` | E2E test console log |
| `artifacts/{target}/openshift-e2e-test/artifacts/e2e-timelines_spyglass_*.json` | Interval/timeline data |
| `artifacts/{target}/gather-extra/artifacts/oc_cmds/` | Cluster state snapshots (nodes, pods, events, etc.) |
| `artifacts/{target}/gather-extra/artifacts/pods/` | Pod logs from all namespaces |
| `artifacts/{target}/gather-extra/artifacts/audit_logs/` | API server audit logs |
| `artifacts/{target}/gather-extra/artifacts/journal_logs/` | Node journal logs (systemd) |
| `artifacts/{target}/gather-must-gather/artifacts/` | Must-gather archives |
| `prowjob.json` | Job metadata (payload tag, timing, etc.) |

## URL Formats

The script accepts both Prow UI URLs and gcsweb URLs:

- `https://prow.ci.openshift.org/view/gs/test-platform-results/logs/<job>/<build_id>`
- `https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/<job>/<build_id>`

## Error Handling

### No matches found

When a search returns no results, the script returns success with an empty matches array:

```json
{
  "success": true,
  "pattern": "...",
  "count": 0,
  "matches": []
}
```

### gcloud not installed

```json
{
  "success": false,
  "error": "gcloud CLI is not installed. Install from: https://cloud.google.com/sdk/docs/install"
}
```

### Invalid path or 404

```json
{
  "success": false,
  "error": "gcloud storage ls failed: ...",
  "path": "gs://..."
}
```

## Notes

- The `test-platform-results` bucket is publicly accessible. No authentication is required.
- The `--no-user-output-enabled` flag is used on `gcloud storage cp` to suppress progress bars.
- For large files, use `--max-bytes` to limit download size. The default is 512KB.
- The `search` command uses `gcloud storage ls` with glob patterns, which supports `**` for recursive matching.
- All output is JSON on stdout. Errors also produce a JSON object with `"success": false`.

## See Also

- Related Skill: `prow-job-analyze-test-failure` — Analyzes test failures using build logs and timelines
- Related Skill: `prow-job-analyze-install-failure` — Analyzes install failures using installer logs
- Related Skill: `prow-job-analyze-resource` — Analyzes resource lifecycles using audit logs
- Related Skill: `prow-job-extract-must-gather` — Extracts must-gather archives
- Related Skill: `fetch-prowjob-json` — Fetches prowjob.json metadata
