# Report Guide

Produce a structured Markdown report with **inline deep links** throughout. Links go where the
evidence is discussed, not in a separate section at the end. Use Markdown reference-style links
to keep the text readable.

## Links and payload claims

Each run's analysis (`{runs_dir}/{build_id}/analysis.md`, from `disruption-analyze-run`) already
carries its Prow, Intervals, and artifact links and its payload pair. Keep those links inline
where the evidence is discussed when you assemble the report. The link shapes and the payload
rules are in `disruption-analyze-run`'s `references/evidence-links.md`; the same rules apply
here: no separate Artifacts or Links table, no truncated job names, and no claim that depends on
a run's payload pair unless that pair was checked.

## Report Structure

Use the regression structure for W3 and W4, the single-run structure for one run, and the
multiple-run structure for W1 and W5 with several runs. When a W3 investigation switched to
W5 (no transition in the window), use the multiple-run structure with the **Verdict** section
from the regression structure at the top.

**For a regression investigation (W3, W4):**

```text
# Disruption Regression: {backend_names} ({release}, {platform})

## Verdict
{One of: Regression explained | Partially explained | Regression cause unresolved (see
`workflows.md`). Two or three sentences: what changed, when, the mechanism, and the evidence
it rests on. For unresolved, say exactly that the evidence explains the disrupted runs but not
the increase, and list the open hypotheses.}

## When It Changed
{From disruption-trend: the transition's change window, payloads, before → after nonzero rate,
P50, P95, strength, which jobs moved, and every caveat. Link the last run before and the first
run after.}

## Controls
{From `controls` in the state file, one line each: the control (platform or release), its
before → after numbers around the transition, and what it shows. "None run" when there were
none; then a platform-specific cause stays unsupported. Omit the section only when no candidate
was platform-specific and the onset was in the window.}

## Cohorts
{From disruption-find-runs: before and after runs (linked), how they were chosen or that the
user supplied them, and every comparability note.}

## What Differs Between the Cohorts
{From comparison.md: each candidate with its class (new, pre-existing with more impact,
pre-existing unchanged, not supported), the runs it rests on, and why.}

## Change Suspects
{From suspects.md: the range compared, ranked suspects with PR links and why each fits, and
what would confirm the top one. "Not run" when the workflow skipped it.}

## Known Disruption Issues
{From known-issues.md: demonstrated mechanism matches with fix status, then related cards with
why each is only related.}

## Limits
{Sample sizes, degraded data, unknown payloads, runs with unreliable liveness, and anything
the user chose to skip.}
```

Each run's details stay in its `analysis.md`; link to it rather than repeating it.

**For single run:**

```text
# Disruption Analysis

{If this is a W3 investigation that switched to W5, start with the Verdict section from the
regression structure: normally "Regression cause unresolved, no transition in the window".}

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
- **Payloads**: {initial_payload} → {target_payload} (upgrade jobs; "payloads not checked" when unknown)
- **Sippy Intervals**: [View intervals]({sippy_intervals_url})

## Disruption Summary
{Episodes and waves (e.g. "6 episodes in 2 waves (3+3), wave gap 12m"), the static-pod
rollouts each wave falls inside, disruption count, backend classification,
network-liveness assessment}

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
{From `known-issues.md`: demonstrated matches, then related cards, or "Jira search skipped"}
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
| # | Build ID | Job | Payloads (initial → target) | Episodes / Waves | Rollouts | Disrupted Backends | Network Liveness |
|---|----------|-----|-----------------------------|------------------|----------|-------------------|------------------|
| 1 | {build_id_1} ([Prow]({prow_url}) \| [Intervals]({sippy_url})) | {job} | {initial_payload} → {target_payload} | {e.g. 3 in 1 wave} | {e.g. KAS 6->7 (w1)} | {backends} | {status} |
| 2 | {build_id_2} ([Prow]({prow_url}) \| [Intervals]({sippy_url})) | {job} | {initial_payload} → {target_payload} | {e.g. 6 in 2 waves (3+3)} | {e.g. KAS 6->7 (w1), KAS 8->9 (w2)} | {backends} | {status} |

The Payloads column is required for upgrade jobs (see Payload Claims); use "—" for
non-upgrade jobs and "not checked" when the pair is unknown. Rollouts lists the
static-pod revision rollouts that contain disruption episodes.

## Disruption Events
### Run 1 ({build_id_1})
Phase: {upgrade|conformance} — Disruption details with [timeline]({gcsweb_timeline_url}) links

## Cluster Activity Correlation
Run 1 [timeline]({gcsweb_timeline_url_1}) shows OVS stalls at 21:50:24Z...
Run 2 [timeline]({gcsweb_timeline_url_2}) shows disk IOPS at 100% ([cloud metrics]({gcsweb_timeline_url_2}))...

## Cross-Run Comparison
{Pattern analysis referencing specific runs with inline links}

{If triggered from a disruption alert, include this section:}
## Do These Runs Represent the Regression?
{The alert compares its lookback window (often 3 days) with {compare_release}. The runs
analyzed come from that window, so they can miss the regression: it may have started
earlier, or a fix may have landed inside the window. State which of these holds:
- {compare_release} is at a similar level over the same window (the release control from
  `disruption-trend --control release-<compare_release>`, if it was run). Then the regression
  is not visible in the current data and has not been explained.
- A matching fix (the fix check in `disruption-known-issues`) landed before most of the analyzed runs. Then they show
  what is left after the fix, not the regression.
- Neither was checked. Say so, and offer a regression investigation (W3) to find out.}

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
{From `known-issues.md`: demonstrated matches, then related cards, or "Jira search skipped"}
```

## Output filename

Save the report using a filename that references the backends being analyzed:

- **Single run**: `{investigation_dir}/{backend_names}-analysis.md`
- **Multiple runs**: `{investigation_dir}/{backend_names}-analysis.md`

Where `{backend_names}` is a kebab-case join of the disrupted backend base names (e.g.,
`image-registry-new-connections-analysis.md` or `kube-api-oauth-api-analysis.md`).
If all backends are analyzed (no `--backends` filter), use the backends that actually showed
disruption. If the resulting filename would be excessively long (more than 5 backends),
truncate to the first 5 and append `-and-more` (e.g., `kube-api-oauth-api-openshift-api-cache-oauth-api-cache-openshift-api-and-more-analysis.md`).
