---
name: kubelet-version-check
description: Determine the kubelet version and job status for a list of /payload job runs from their gcsweb artifact URLs
---

# Kubelet Version Check

This skill inspects a list of `/payload` job runs and reports, for each one, its result status and the kubelet version that was running on the cluster nodes. It reads a text file of gcsweb artifact URLs (one per line) — the same format produced by the `payload-blocking-runs` skill — and prints a table of job name, build ID, status, and kubelet version.

For each run it:

- fetches `finished.json` to determine the job result (e.g. `SUCCESS`, `FAILURE`)
- locates the e2e step's `gather-extra/artifacts/oc_cmds/nodes` artifact and extracts the kubelet version column

Work is parallelized across 24 worker threads, so large lists complete quickly.

## When to Use This Skill

Use this skill when you need to:

- Confirm which kubelet (node) version was actually running across a set of payload runs
- Detect runs where the kubelet version was unexpected or the nodes artifact is missing
- Correlate kubelet version with job pass/fail status when investigating a version-sensitive regression
- Verify that a version bump (e.g. a Kubernetes rebase) landed consistently across blocking jobs

It pairs naturally with the `payload-blocking-runs` skill, which produces the input URL list.

## Prerequisites

1. **Python 3**: Python 3.9 or later — standard library only, no external dependencies.
   - Check: `python3 --version`

2. **A file of gcsweb artifact URLs**, one per line, e.g.:
   ```text
   https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/<job-name>/<build-id>/
   ```
   Generate one with the `payload-blocking-runs` skill (`-o payload-runs.txt`).

3. **Network access** to `storage.googleapis.com` (the public `test-platform-results` bucket).

4. **Optional authentication**: Set `GOOGLE_APPLICATION_CREDENTIALS` to a GCS service-account JSON key for authenticated access. Unauthenticated access works for the public bucket, so this is usually unnecessary.

## Implementation Steps

### Step 1: Locate and Run the Script

```bash
# Locate the Python script
KUBELET_CHECK="${CLAUDE_PLUGIN_ROOT}/skills/kubelet-version-check/get_kubestat.py"
if [ ! -f "$KUBELET_CHECK" ]; then
  KUBELET_CHECK=$(find ~/.claude/plugins -type f -path "*/ci/skills/kubelet-version-check/get_kubestat.py" 2>/dev/null | sort | head -1)
fi
if [ -z "$KUBELET_CHECK" ] || [ ! -f "$KUBELET_CHECK" ]; then echo "ERROR: get_kubestat.py not found" >&2; exit 2; fi

# Run against a file of gcsweb URLs
python3 "$KUBELET_CHECK" payload-runs.txt
```

Progress messages are written to stderr; the results table is written to stdout. Capture just the table with:

```bash
python3 "$KUBELET_CHECK" payload-runs.txt > kubelet-versions.txt
```

### Step 2: Read the Table

The output is a fixed-width table:

```text
JOB                                 BUILD_ID             STATUS   KUBELET_VERSION
----------------------------------  -------------------  -------  ---------------
periodic-...-e2e-aws-ovn-serial     1234567890123456789  SUCCESS  v1.35.0
periodic-...-e2e-gcp-ovn-upgrade    1234567890123456790  FAILURE  v1.35.0
```

Column meanings:

- **JOB**: the prowjob name parsed from the URL
- **BUILD_ID**: the run's build ID
- **STATUS**: the `result` field from `finished.json` (`unknown` if unavailable)
- **KUBELET_VERSION**: the kubelet version from the nodes artifact, or a note such as `no e2e step`, `no nodes file`, or `unexpected: <value>`

### Step 3: (Optional) Authenticate

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
python3 "$KUBELET_CHECK" payload-runs.txt
```

## Input / Output

- **Input**: a text file path (first positional argument). Each non-empty line must be a gcsweb URL of the form `.../gcs/<bucket>/logs/<job>/<build>/`.
- **Output**: a table of `JOB`, `BUILD_ID`, `STATUS`, `KUBELET_VERSION`, sorted by job then build, on stdout.
- **Concurrency**: up to 24 runs are processed in parallel.

## Error Handling

The script handles each run independently rather than aborting the whole batch; per-run problems are reported inline in that run's row:

- **Unparseable URL**: raises a `ValueError` for that line (fix or remove the offending URL).
- **Missing `finished.json`**: status is reported as `unknown`.
- **No e2e step directory**: kubelet version is `no e2e step`.
- **No nodes artifact**: kubelet version is `no nodes file`.
- **Version doesn't match the expected `v1.3x` pattern**: reported as `unexpected: <value>` so anomalies stand out.

**Exit Codes:**
- `0`: Success (table printed)
- `1`: No input file argument provided

## Examples

### Example 1: Check kubelet versions for a payload run list

```bash
python3 "$KUBELET_CHECK" payload-runs.txt
```

### Example 2: Chain with the payload-blocking-runs skill

```bash
# 1. Produce the URL list for a PR's blocking payload runs
python3 "$PAYLOAD_BLOCKING" --repo machine-config-operator --pr 5509 \
  --start 2026-01-01 --streams 4.20.0-0.nightly -o payload-runs.txt

# 2. Report kubelet version + status for each run
python3 "$KUBELET_CHECK" payload-runs.txt
```

### Example 3: Authenticated access

```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json \
  python3 "$KUBELET_CHECK" payload-runs.txt
```

## Notes

- Uses only the Python standard library; no `pip install` step is required for the default (unauthenticated) path.
- The kubelet version is read from the second line, fifth column of the `nodes` artifact (`oc get nodes` output) under the first e2e step that has one.
- Status comes from the `result` field of `finished.json`.
- The public `test-platform-results` GCS bucket does not require credentials; set `GOOGLE_APPLICATION_CREDENTIALS` only if you need authenticated access.

## See Also

- Related Skill: `payload-blocking-runs` (produces the input URL list)
- Related Command: `/ci:check-kubelet-versions` (wraps this skill and adds cross-run analysis)
