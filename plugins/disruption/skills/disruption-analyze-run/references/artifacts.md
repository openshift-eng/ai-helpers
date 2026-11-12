# Artifact Download (Steps 2 and 4)

Follow **Timeline download** for every run. Follow **Deep-dive artifact download** only when Step 4 says the parser output is insufficient.

## Timeline download (Step 2)

Check for existing artifacts first. If `{runs_dir}/{build_id}/logs/` exists
with timeline files, ask the user whether to reuse or re-download.

Use `download_timelines.py` to download prowjob.json and timeline files for all runs in a single
invocation. The script handles creating directories, downloading prowjob.json, extracting the
`--target=` value, finding timeline files via `gcloud storage ls`, and downloading them — all in
parallel across runs:

```bash
python3 "${CLAUDE_SKILL_DIR}/download_timelines.py" \
  --runs "{job_name_1}:{build_id_1},{job_name_2}:{build_id_2}" \
  --output-dir {runs_dir} \
  --format text
```

**Important GCS bucket note**: Prow URLs may contain `origin-ci-test` in the path (e.g.,
`/view/gs/origin-ci-test/logs/...`), but the actual GCS bucket is always `test-platform-results-public`.
The script handles this automatically.

The `--runs` flag takes comma-separated `job_name:build_id` pairs. Extract these from the Prow
URLs parsed in Step 1.

Output shows the target, the downloaded timeline file paths, and the payload pair per run:

```text
2084417286357127168: target=e2e-gcp-runc-upgrade
  {runs_dir}/2084417286357127168/logs/e2e-timelines_spyglass_20260804-000654.json
  {runs_dir}/2084417286357127168/logs/e2e-timelines_spyglass_20260804-012513.json
  payloads: 5.1.0-0.ci-2026-08-03-232923 -> 5.1.0-0.ci-2026-08-04-112923 (from clusterversion-history)

2084701838124257280: target=e2e-gcp-ovn-upgrade
  .work/disruption-analysis/2026-08-04/2084701838124257280/logs/e2e-timelines_spyglass_20260804-190035.json
  payloads: 5.0.0-0.nightly-2026-08-03-184859 -> 5.1.0-0.nightly-2026-08-04-075706 (from prowjob-env)
```

Use `--format json` for machine-readable output with `build_id`, `job`, `target`,
`timeline_files`, `initial_payload`, `target_payload`, `payload_source`, and `error`
per run. `error` is the gcloud diagnostic when a download or listing failed.
`no timeline files found` means the listing succeeded and matched nothing.
`failed to list timeline files: ...` means the listing command itself failed (auth,
network, timeout, or launch).

**Payload pair.** `initial_payload` is the payload the cluster was installed with and
`target_payload` the one it upgraded to. They come from the prowjob's
`RELEASE_IMAGE_INITIAL` / `RELEASE_IMAGE_LATEST` env (`prowjob-env`), then its
`release.openshift.io/from-tag` / `tag` annotations (`prowjob-annotations`). Jobs that
build their own release (for example `e2e-gcp-runc-upgrade`) have neither, so the
script downloads gather-extra `clusterversion.json` into `{build_id}/gather/` and reads
its update history (`clusterversion-history`: oldest entry is the install, newest the
target). `payloads: unknown (...)` means none of these worked; the reason does not
change the exit status. The parser prints the same pair from the saved files. Record
the pair for every upgrade run in the runs table, and do not make a claim that depends
on which payload a run started from or upgraded to without it.

**`--gather`** also downloads gather-extra `events.json`, `configmaps.json`,
`releaseinfo.json`, and `clusterversion.json` into `{build_id}/gather/` for the
revision-trigger recipe below and for `disruption-change-suspects`. Add it when the parser shows more
static-pod revision rollouts in one run than in another, or when payloads will be
compared (`disruption-change-suspects`). The per-run `gather_files` and `gather_error` fields report what was saved;
a missing gather-extra file does not change the exit status.

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
etcd log context beyond what the timeline summaries provide, or when the parser shows a
static-pod revision rollout (often a second kube-apiserver rollout) that the upgrade
itself does not explain. For that case go straight to 4.3 and 4.4.

### 4.1: Download Audit Logs (if needed)

```bash
CLOUDSDK_AUTH_DISABLE_CREDENTIALS=true gcloud storage cp -r \
  "gs://test-platform-results-public/{bucket-path}/artifacts/{target}/gather-extra/artifacts/audit_logs/" \
  {runs_dir}/{build_id}/logs/audit_logs/
```

Query for sampler requests during disruption windows to identify request gaps.

### 4.2: Download etcd Pod Logs (if needed)

```bash
CLOUDSDK_AUTH_DISABLE_CREDENTIALS=true gcloud storage cp -r \
  "gs://test-platform-results-public/{bucket-path}/artifacts/{target}/gather-extra/artifacts/pods/openshift-etcd/" \
  {runs_dir}/{build_id}/logs/etcd-pods/
```

Search for leader changes, write delays, member issues, and disk problems.

Leave stderr visible and keep the command's exit status. The same
`CLOUDSDK_AUTH_DISABLE_CREDENTIALS=true` prefix applies to any other direct
`gcloud storage ls` or `cp` against this bucket, including journal logs.

- If gcloud says the URL matched no objects or files, that optional directory is absent. Note it in the report and continue. A missing directory is not an auth failure.
- Any other non-zero exit is an auth, network, timeout, or copy failure. Report the gcloud message and do not treat the download as successful.

### 4.3: Revision Trigger (when a run has an extra static-pod rollout)

Use this when the parser's `rollouts:` shows more kube-apiserver (or etcd, KCM,
scheduler) revision rollouts in some runs than in others, or a disruption wave sits
inside a rollout you cannot explain from the upgrade itself. It answers "what wrote
the input that started revision N?".

1. Get gather-extra `events.json` and `configmaps.json` for a run with the extra
   rollout and a run without it (same job, before and after the change). If you did
   not pass `--gather` in Step 2, rerun the downloader for those runs; it reuses the
   same layout:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/download_timelines.py" \
     --runs "{job_name}:{build_id_before},{job_name}:{build_id_after}" \
     --output-dir {runs_dir} --gather --format text
   ```

   The direct equivalent for one file is:

   ```bash
   CLOUDSDK_AUTH_DISABLE_CREDENTIALS=true gcloud storage cp \
     "gs://test-platform-results-public/logs/{job_name}/{build_id}/artifacts/{target}/gather-extra/artifacts/events.json" \
     {runs_dir}/{build_id}/gather/
   ```

2. List the triggers and compare the runs in one command:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/revision_triggers.py" \
     {runs_dir}/{build_id_before} \
     {runs_dir}/{build_id_after} \
     --operator kube-apiserver
   ```

   For each run it prints the `openshift-kube-apiserver/revision-status-N` configmaps
   (creation time and `reason`), each `StartingNewRevision` / `RevisionTriggered`
   event with the `SecretUpdated` / `ConfigMapUpdated` / `*Created` events from any
   namespace in the same second, and the operator's `OperatorVersionChanged` events.
   Install-time revisions are hidden (`--all` shows them). A revision tagged
   `[after operator upgrade]` started after the operator reported its new version and
   is not the upgrade's first revision: it is a rollout beyond the upgrade's own. The last block lists trigger reasons
   present in only some runs. Example from a real regression:

   ```text
   revision 10  started 2026-11-10T01:08:29Z  triggered 2026-11-10T01:08:56Z  optional secret/webhook-authenticator has changed [after operator upgrade]
     2026-11-10T01:08:29Z SecretUpdated openshift-authentication-operator (oauth-apiserver-webhook-authenticator-controller-...): Updated Secret/webhook-authentication-integrated-oauth -n openshift-config because it changed
     2026-11-10T01:08:29Z SecretUpdated openshift-kube-apiserver-operator (kube-apiserver-operator-resource-sync-controller-...): Updated Secret/webhook-authenticator -n openshift-kube-apiserver because it changed
   ```

   The first write in the chain names the component that caused the rollout (here the
   authentication operator's webhook-authenticator controller). Use `--operator etcd`,
   `kube-controller-manager`, or `kube-scheduler` for the other static-pod operators,
   and `--format json` for structured output.

3. Caveats the script repeats in its output: the cluster keeps events for about 3 hours
   and aggregates repeats, so early upgrade events can be missing; the revision
   controller prunes old `revision-status-N` configmaps. Report what is missing rather
   than concluding a revision had no trigger.

Then record the component for 4.4.

### 4.4: The Component Change

Once 4.3 or a timeline signal points at a component, record the component and the payload
pair of a run without the behavior and a run with it. Listing the commits between them is
the `disruption-change-suspects` skill's job (`payload_diff.py`); do not read release info
or GitHub compares by hand here. Name the component and both runs in the checkpoint's
`next` options.

### 4.5: PromQL Queries for Manual Investigation

If the analysis needs live cluster metrics (not available in artifacts), provide these queries:

```promql
-- Top CPU consumers across all nodes
topk(25, sum by (namespace) (rate(container_cpu_usage_seconds_total{container!="",pod!=""}[5m])))

-- CPU on a specific node
topk(25, sum by (namespace) (rate(container_cpu_usage_seconds_total{container!="",pod!="",node="<node-name>"}[5m])))

-- E2E test CPU on a specific node
topk(10, sum by (namespace) (rate(container_cpu_usage_seconds_total{container!="",pod!="",node="<node-name>",namespace=~"^e2e-.*"}[5m])))
```
