# Artifact Download (Steps 2 and 4)

Follow **Timeline download** for every run. Follow **Deep-dive artifact download** only when Step 4 says the parser output is insufficient.

## Timeline download (Step 2)

Compute `{date}` as today's date in `YYYY-MM-DD` format (e.g., `2026-03-23`).

Check for existing artifacts first. If `.work/disruption-analysis/{date}/{build_id}/logs/` exists
with timeline files, ask the user whether to reuse or re-download.

Use `download_timelines.py` to download prowjob.json and timeline files for all runs in a single
invocation. The script handles creating directories, downloading prowjob.json, extracting the
`--target=` value, finding timeline files via `gcloud storage ls`, and downloading them — all in
parallel across runs:

```bash
python3 "${CLAUDE_SKILL_DIR}/download_timelines.py" \
  --runs "{job_name_1}:{build_id_1},{job_name_2}:{build_id_2}" \
  --output-dir .work/disruption-analysis/{date} \
  --format text
```

**Important GCS bucket note**: Prow URLs may contain `origin-ci-test` in the path (e.g.,
`/view/gs/origin-ci-test/logs/...`), but the actual GCS bucket is always `test-platform-results-public`.
The script handles this automatically.

The `--runs` flag takes comma-separated `job_name:build_id` pairs. Extract these from the Prow
URLs parsed in Step 1.

Output shows the target and downloaded timeline file paths per run:

```text
2084417286357127168: target=e2e-gcp-runc-upgrade
  .work/disruption-analysis/2026-08-04/2084417286357127168/logs/e2e-timelines_spyglass_20260804-000654.json
  .work/disruption-analysis/2026-08-04/2084417286357127168/logs/e2e-timelines_spyglass_20260804-012513.json

2084701838124257280: target=e2e-gcp-ovn-upgrade
  .work/disruption-analysis/2026-08-04/2084701838124257280/logs/e2e-timelines_spyglass_20260804-190035.json
```

Use `--format json` for machine-readable output with `build_id`, `job`, `target`,
`timeline_files`, and `error` per run. `error` is the gcloud diagnostic when a
download or listing failed. `no timeline files found` means the listing succeeded
and matched nothing. `failed to list timeline files: ...` means the listing
command itself failed (auth, network, timeout, or launch).

Exit status:

- **0** — every requested run downloaded its timeline files
- **2** — at least one timeline file downloaded, and at least one run or file failed. Keep the successful files and continue with those runs.
- **1** — no timeline file was downloaded. Report each run's `error` text. Do not treat that as an empty artifact directory.

**Timeline file locations vary by job type**:

- **Non-upgrade jobs**: Usually one timeline file
- **Upgrade jobs**: Usually two timeline files (one per phase — upgrade and conformance)

On exit 2, keep the downloaded files and continue with the runs that have timelines. On
exit 1, stop and report each run's error. The script already uses anonymous public-bucket
access; do not run `gcloud auth login` to retry it.

## Deep-dive artifact download (Step 4)

**Only perform this step if the parser output from Step 3 is insufficient for root cause
determination** — for example, when you need to see the full audit log request details or
etcd log context beyond what the timeline summaries provide.

### 4.1: Download Audit Logs (if needed)

```bash
CLOUDSDK_AUTH_DISABLE_CREDENTIALS=true gcloud storage cp -r \
  "gs://test-platform-results-public/{bucket-path}/artifacts/{target}/gather-extra/artifacts/audit_logs/" \
  .work/disruption-analysis/{date}/{build_id}/logs/audit_logs/ --no-user-output-enabled || true
```

Query for sampler requests during disruption windows to identify request gaps.

### 4.2: Download etcd Pod Logs (if needed)

```bash
CLOUDSDK_AUTH_DISABLE_CREDENTIALS=true gcloud storage cp -r \
  "gs://test-platform-results-public/{bucket-path}/artifacts/{target}/gather-extra/artifacts/pods/openshift-etcd/" \
  .work/disruption-analysis/{date}/{build_id}/logs/etcd-pods/ --no-user-output-enabled || true
```

Search for leader changes, write delays, member issues, and disk problems.

The same `CLOUDSDK_AUTH_DISABLE_CREDENTIALS=true` prefix applies to any other direct
`gcloud storage ls` or `cp` against this bucket, including journal logs. Do not hide
stderr: the gcloud message is the diagnostic. A missing optional directory is not an
auth failure.

### 4.3: PromQL Queries for Manual Investigation

If the analysis needs live cluster metrics (not available in artifacts), provide these queries:

```promql
-- Top CPU consumers across all nodes
topk(25, sum by (namespace) (rate(container_cpu_usage_seconds_total{container!="",pod!=""}[5m])))

-- CPU on a specific node
topk(25, sum by (namespace) (rate(container_cpu_usage_seconds_total{container!="",pod!="",node="<node-name>"}[5m])))

-- E2E test CPU on a specific node
topk(10, sum by (namespace) (rate(container_cpu_usage_seconds_total{container!="",pod!="",node="<node-name>",namespace=~"^e2e-.*"}[5m])))
```
