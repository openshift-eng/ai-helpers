# Evidence Links and Payload Claims

Use these in every run analysis. Links go where the evidence is discussed, not in a separate
section at the end.

## Deep links

Construct deep links for each job run — these go **inline throughout the analysis**
wherever the run or a specific artifact is referenced, not in a separate table:

**Run-level links** (use when first mentioning a run):
- **Prow job page**: `https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/{job_name}/{build_id}`
- **Sippy intervals**: `https://sippy.dptools.openshift.org/sippy-ng/job_runs/{build_id}/{job_name}/intervals`

**GCS artifact deep links** (use when citing specific evidence):
- Base: `https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results-public/logs/{job_name}/{build_id}/artifacts/`
- Timeline file: the gcsweb URL for the object listed by `gs://test-platform-results-public/logs/{job_name}/{build_id}/artifacts/**/e2e-timelines_spyglass_*.json`. Replace the `gs://` prefix with `https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/` and keep the rest of that object path. Do not rebuild the link under `artifacts/junit/`.
- Audit logs dir: `{gcs_base}{target}/gather-extra/artifacts/audit_logs/`
- etcd pod logs: `{gcs_base}{target}/gather-extra/artifacts/pods/openshift-etcd/`
- Journal logs: `{gcs_base}{target}/gather-extra/artifacts/nodes/` (per-node `journal`, gzip without a `.gz` extension)
- Must-gather: `{gcs_base}{target}/gather-must-gather/artifacts/` (`must-gather.tar.gz`)

Where `{target}` is the ci-operator target extracted from prowjob.json (e.g., `e2e-azure-ovn-upgrade`).

**Inline linking style**: When discussing evidence, link directly to the artifact.
For example: "Run 1 ([Prow][prow1] | [Intervals][int1]) showed 11 disruptions in
the [timeline data][timeline1]..." — where `[timeline1]` links to the specific
`e2e-timelines_spyglass_*.json` file on gcsweb.

## Inline Linking Rules

1. **First mention of a run** — include `([Prow]({prow_url}) | [Intervals]({sippy_url}))` after
   the build ID or run number
2. **Citing evidence from a specific artifact** — deep-link to the exact file on gcsweb, e.g.:
   - `[timeline data]({gcsweb_timeline_url})` when discussing disruption events
   - `[audit logs]({gcsweb_audit_url})` when discussing request gaps
   - `[etcd pod logs]({gcsweb_etcd_url})` when discussing etcd pressure
   - `[OVS vswitchd logs]({gcsweb_journal_url})` when discussing OVS stalls
3. **Tables listing runs** — include Prow and Intervals links in a column
4. **Do NOT create a separate "Artifacts" or "Links" table** — all links belong inline where
   the reader would want to click through to verify the evidence
5. **Do NOT truncate or abbreviate job names** — always use the full job name (e.g.,
   `periodic-ci-openshift-release-main-ci-4.22-e2e-azure-ovn-upgrade`, not `periodic-ci-...-e2e-azure-ovn-upgrade`)

## Payload Claims

For upgrade jobs, every run's initial and target payload goes in the analysis (the Payloads
column of the runs table, or the Job Information block for a single run). Take them from
`download_timelines.py` (`payloads:` line, or `initial_payload` / `target_payload`) or the
parser (`payload:` in the summary, `payloads` in JSON), and give the payload tag, not the
registry path.

Do not make a claim that depends on which payload a run started from or upgraded to, such
as "this run already started from a payload with the fix" or "only upgrades into X are
affected", unless that run's pair was checked. When the pair is unknown (`payloads:
unknown`), write "payloads not checked" for that run and leave payload-dependent
conclusions out. When the target alone does not explain a difference between runs, say
whether the initial payloads differ.
