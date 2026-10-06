# Report Guide (Step 7)

Produce a structured Markdown report with **inline deep links** throughout. Links go where the
evidence is discussed, not in a separate section at the end. Use Markdown reference-style links
to keep the text readable.

## Deep links

Construct deep links for each job run — these go **inline throughout the report**
wherever the run or a specific artifact is referenced, not in a separate table:

**Run-level links** (use when first mentioning a run):
- **Prow job page**: `https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/{job_name}/{build_id}`
- **Sippy intervals**: `https://sippy.dptools.openshift.org/sippy-ng/job_runs/{build_id}/{job_name}/intervals`

**GCS artifact deep links** (use when citing specific evidence):
- Base: `https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results-public/logs/{job_name}/{build_id}/artifacts/`
- Timeline file: the gcsweb URL for the object listed by `gs://test-platform-results-public/logs/{job_name}/{build_id}/artifacts/**/e2e-timelines_spyglass_*.json`. Replace the `gs://` prefix with `https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/` and keep the rest of that object path. Do not rebuild the link under `artifacts/junit/`.
- Audit logs dir: `{gcs_base}{target}/gather-extra/artifacts/audit_logs/`
- etcd pod logs: `{gcs_base}{target}/gather-extra/artifacts/pods/openshift-etcd/`
- Journal logs: `{gcs_base}{target}/gather-extra/artifacts/journal_logs/`
- Must-gather: `{gcs_base}{target}/gather-extra/artifacts/must-gather/`

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

## Report Structure

**For single run:**

```text
# Disruption Analysis

{If triggered from a Grafana URL or a disruption alert, include this section:}
## Dashboard Context
- **Source**: [{dashboard_name}]({grafana_url}) or the alert name when there is no link
- **Filters**: Platform={platform} | Upgrade={upgrade_type} | Topology={topology} | Network={network} | Architecture={architecture} | FeatureSet={feature_set} | OS={os} | MasterNodesUpdated={master_nodes_updated}
- **Backend**: {backend}
- **Percentile**: {percentile} | **Release**: {release} | **Lookback**: {lookback}d | **Compare release**: {compare_release}

## Job Information
- **Prow Job**: [{job-name}]({prow_url})
- **Build ID**: {build_id}
- **Target**: {target}
- **Sippy Intervals**: [View intervals]({sippy_intervals_url})

## Disruption Summary
{Disruption count, backend classification, network-liveness assessment}

## Disruption Timeline
- **{from} — {to}** ({duration}s): {message}
  - Concurrent activity from [timeline]({gcsweb_timeline_url}): {events}
  - [Audit logs]({gcsweb_audit_url}): {gap analysis}

## Cluster Activity Correlation
{Reference specific artifacts inline, e.g.:}
The [timeline data]({gcsweb_timeline_url}) shows OVS vswitchd poll intervals up to 9s...
[etcd pod logs]({gcsweb_etcd_url}) confirm apply-too-long warnings at 03:56:00Z...

## Root Cause Hypothesis
{Analysis with inline links to supporting evidence}

## Other Disrupted Backends
{When --backends filter was used, list other backends that were disrupted during the
same time window and due to the same root cause. This helps readers understand the full
blast radius — e.g., if openshift-api was requested but kube-api, oauth-api, and
metrics-api were also disrupted simultaneously, that confirms a control plane problem
rather than an openshift-api-specific issue. Only include backends whose disruption
overlaps the same window; exclude unrelated disruption at other times.}

## Known Disruption Issues
{Results from Step 8 Jira search, or "Jira search skipped (--skip-jira)"}
```

**For multiple runs — use the same inline linking pattern:**

```text
# Disruption Analysis: {backend_names}

{If triggered from a Grafana URL or a disruption alert, include this section:}
## Dashboard Context
- **Source**: [{dashboard_name}]({grafana_url}) or the alert name when there is no link
- **Filters**: Platform={platform} | Upgrade={upgrade_type} | Topology={topology} | Network={network} | Architecture={architecture} | FeatureSet={feature_set} | OS={os} | MasterNodesUpdated={master_nodes_updated}
- **Backend**: {backend}
- **Percentile**: {percentile} | **Release**: {release} | **Lookback**: {lookback}d | **Compare release**: {compare_release}

## Runs Analyzed
| # | Build ID | Job | Disrupted Backends | Network Liveness |
|---|----------|-----|-------------------|------------------|
| 1 | {build_id_1} ([Prow]({prow_url}) \| [Intervals]({sippy_url})) | {job} | {backends} | {status} |
| 2 | {build_id_2} ([Prow]({prow_url}) \| [Intervals]({sippy_url})) | {job} | {backends} | {status} |

## Disruption Events
### Run 1 ({build_id_1})
Phase: {upgrade|conformance} — Disruption details with [timeline]({gcsweb_timeline_url}) links

## Cluster Activity Correlation
Run 1 [timeline]({gcsweb_timeline_url_1}) shows OVS stalls at 21:50:24Z...
Run 2 [timeline]({gcsweb_timeline_url_2}) shows disk IOPS at 100% ([cloud metrics]({gcsweb_timeline_url_2}))...

## Cross-Run Comparison
{Pattern analysis referencing specific runs with inline links}

## Root Cause Hypothesis
{Synthesis with links to key evidence}

## Other Disrupted Backends
{When --backends filter was used, list other backends that were disrupted during the
same time window and due to the same root cause — not all disruption in the run, just
what overlaps the identified disruption event. Show a consolidated table with backend
name, type (cache/non-cache/cloud/canary), and how many runs (out of N) showed that
backend disrupted in the same window. Sort by runs-affected descending, then by count.
This reveals the full blast radius and helps confirm root cause — e.g., if every API
backend fails together, the problem is control-plane-wide, not backend-specific.}

## Known Disruption Issues
{Results from Step 8 Jira search, or "Jira search skipped (--skip-jira)"}
```

## Output filename

Save the report using a filename that references the backends being analyzed:

- **Single run**: `.work/disruption-analysis/{date}/{backend_names}-analysis.md`
- **Multiple runs**: `.work/disruption-analysis/{date}/{backend_names}-analysis.md`

Where `{backend_names}` is a kebab-case join of the disrupted backend base names (e.g.,
`image-registry-new-connections-analysis.md` or `kube-api-oauth-api-analysis.md`).
If all backends are analyzed (no `--backends` filter), use the backends that actually showed
disruption. If the resulting filename would be excessively long (more than 5 backends),
truncate to the first 5 and append `-and-more` (e.g., `kube-api-oauth-api-openshift-api-cache-oauth-api-cache-openshift-api-and-more-analysis.md`).
