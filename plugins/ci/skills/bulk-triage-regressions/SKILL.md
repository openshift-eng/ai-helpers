---
name: bulk-triage-regressions
description: Use this skill for Component Readiness triage duty - holistically analyze and triage all untriaged regressions for a set of components in a view, clustering them into root-cause buckets
---

# Bulk Triage Regressions

## Input

```
bulk-triage-regressions <view> [--components comp1 comp2 ...] [--auto-triage]
```

Example: `bulk-triage-regressions 5.0-main --components Installer Unknown`

## Description

This skill implements the **Component Readiness triage duty workflow**: it fetches *all* untriaged regressions for a set of components in a view (e.g., `5.0-main`, components `Installer` and `Unknown`), analyzes them **as a batch**, clusters them into **root-cause buckets**, and then triages each bucket to a single JIRA bug (existing or new).

This differs from `/ci:analyze-regression` (which analyzes a single regression in depth). Triage duty requires a **holistic view**, because:

1. **Many regressions, few root causes.** One product bug commonly opens 5–30 regressions across variants (different platforms, arches, featuresets, upgrade modes) and across "wrapper" tests (`install should succeed: overall`, `: cluster bootstrap`, `: cluster creation`, `verify the cluster readiness and stability`, mass-failure tests, etc.). Analyzing regressions one-by-one wastes effort and risks filing duplicate bugs. Cluster first, deep-dive once per cluster.

2. **Component attribution is often wrong.** Regressions in `Installer` and `Unknown` are catch-all attributions. A failed installation or bootstrap is frequently caused by a *specific* component — e.g., a monitoring operator failing to go available blocks cluster creation, an etcd slowness issue breaks bootstrap, an MCO bug degrades nodes during install. The Sippy component label tells you *which test failed*, not *whose bug it is*. The real owner must be determined from artifacts (cluster operator status, log bundle, operator logs), and the JIRA bug must be filed against the **actual owning component**, not Installer.

Use this skill when doing triage duty for a view, or whenever a user asks to "look at all untriaged regressions from <components>" rather than a single regression ID.

## Implementation

**Script invocation rules**: Run Python skill scripts directly (`python3 script.py args --format json 2>/dev/null`) and analyze the JSON output with your own reasoning. Do not pipe script output through inline Python one-liners.

**Authentication**: Read steps (listing, fetching details, test runs, GCS artifacts) require no auth. Write steps (creating/updating triage records) require a Bearer token from the DPCR cluster (`api.cr.j7t7.p1.openshiftapps.com:6443`) — see the `oc-auth` skill and the token-extraction snippet in `/ci:analyze-regression`. Check token validity early (a simple authenticated GET against `https://sippy-auth.dptools.openshift.org/api/component_readiness/triages` returning 200 vs 401/403), so an expired token is surfaced to the user *before* hours of analysis, not after.

JIRA write steps (filing bugs, `set-release-blocker`, `add-jira-triage-link`) additionally require the `JIRA_USERNAME` and `JIRA_API_TOKEN` environment variables (API token from https://id.atlassian.com/manage-profile/security/api-tokens). Validate these early too: check both variables are set and verify the credentials with an authenticated GET against `https://redhat.atlassian.net/rest/api/3/myself` (Basic auth, 200 vs 401/403). If either the Sippy or JIRA check fails, stop and ask the user to fix credentials before starting the analysis.

### Phase 1: Collect the full batch

1. **Load CI context**: Read the files in `plugins/ci/references/` (`jobs.md`, `tests.md`, `sippy-apis.md`) for conventions on tests, jobs, and Sippy APIs.

2. **Parse arguments**:
   - `view`: required, e.g. `5.0-main`
   - `--components`: component filter list (fuzzy matched), e.g. `Installer Unknown`. If omitted, ask the user which components the duty covers.
   - `--auto-triage`: if present, triage buckets without per-bucket confirmation when confidence is high (see Phase 4). Default is to present findings and confirm before writing.

3. **List regressions** with the `list-regressions` skill:

   ```bash
   python3 plugins/teams/skills/list-regressions/list_regressions.py \
     --view <view> --components <components...>
   ```

   Keep only **open, untriaged** regressions (empty `triages` array), but note recently-triaged ones — they are prime candidates for absorbing untriaged siblings.

4. **Build a batch inventory table**: For every untriaged regression record: regression ID, test name, component/capability, variants (Platform/Arch/Network/Topology/FeatureSet/Upgrade), opened date, failure/run counts. Present this table to the user up front so the scope of the duty run is visible.

### Phase 2: Cluster into candidate buckets (cheap signals first)

Before any deep log analysis, group regressions using signals already in hand:

- **Same test, different variants** — almost always one bucket.
- **Same variant fingerprint, different tests** — e.g., `install should succeed: overall` + `: cluster creation` + `verify the cluster readiness and stability` all failing on `azure/amd64/techpreview` starting the same day is one bucket. Wrapper tests fail together.
- **Same opened date** — regressions opened the same day across components often share one payload-level cause.
- **Shared job runs** — fetch details for each regression (`fetch-regression-details` skill) and compare `job_runs` `prowjob_run_id`s. Regressions observed in the same failed runs are strong candidates for one bucket — but this is a clustering signal, not proof: the same run can contain independent defects or be a mass failure, so Phase 3 validation is still required. Also run the `fetch-related-triages` skill per regression; `same_last_failure` and `similarly_named_test` matches feed the clustering, and `triaged_matches` with confidence ≥5 immediately suggest an existing triage/bug for the whole bucket.
- **Mass-failure marker**: high `test_failures` counts in `job_runs` mean the regression is likely collateral of a bigger event, not an independent issue.

Output of this phase: a **draft bucket list**, each bucket with member regression IDs, the shared fingerprint (test/variant/date/job-run overlap), and any candidate existing triage or JIRA bug.

Treat buckets as hypotheses — Phase 3 must confirm or split them. Do not merge buckets merely because both are "install failures"; installs fail at different stages for unrelated reasons.

### Phase 3: Deep-dive each bucket (confirm root cause and real owner)

For each bucket, pick 2–5 representative failed job runs (spread across jobs/variants; include the newest) and analyze. 2–5 runs are sufficient **only when they yield a consistent result** (same error signature / failure stage across all of them). If the sample is mixed or unclear — different errors, different stages, or an inconclusive owner — **extend the sample to 10–20 runs** before concluding; a small ambiguous sample must never be the basis for splitting/merging a bucket or attributing an owner.

1. **Failure outputs**: `fetch-test-runs` skill with the bucket's test IDs and job run IDs — check whether error messages are consistent within the bucket (>90% same error ⇒ single cause confirmed; inconsistent ⇒ split the bucket).

2. **Job run context**: `fetch-job-run-summary` skill per representative run — is the regressed test isolated, part of a consistent co-failure set, or one of hundreds of random failures? For `Unknown`-component and mass-failure regressions this is where the *real* component reveals itself: read the names of the co-failing tests.

3. **Install/bootstrap failures — mandatory artifact dig**: For any bucket whose tests include `install should succeed` (any stage) or bootstrap/cluster-readiness wrappers, invoke the `prow-job-analysis` skill per representative run. Do not stop at Sippy's generic "install failed" wrapper. From the GCS artifacts determine:
   - **Failure stage**: infrastructure provisioning / bootstrap / cluster creation (operators rolling out) / stability window.
   - **The blocking condition**: for cluster-creation failures, read `clusteroperators.json` (or the installer log's "Cluster operator X is not available" lines) and the failing operator's pod logs from the log bundle. For bootstrap failures, read the bootstrap log bundle (etcd, bootkube, release-image pulls).
   - **The real owner**: the component whose operator/pods are actually failing. Examples from past duty: "cluster creation failed" ⇒ monitoring operator degraded ⇒ **Monitoring** bug; "bootstrap failed" ⇒ `etcdserver: request timed out` on Azure ⇒ **etcd** bug; nodes degraded during install ⇒ **MCO** bug; quota/DNS/cloud-API errors ⇒ **ci-infra**, not a product bug at all.

4. **Onset and suspect PRs** (when the bucket has a crisp start date): follow the "Determine Regression Start Date" and "Identify Suspect PRs in Payload" procedures from `/ci:analyze-regression` (first failing run → payload tag via `fetch-prowjob-json` → `fetch-new-prs-in-payload` → up to 5 candidate PRs vetted with `gh`). A LIKELY PR both strengthens the bucket and tells you the owning component/repo.

5. **Cross-check globally**: `fetch-test-report` skill (with `--no-collapse`) for the bucket's main test — confirms whether the issue is variant-specific or global, and surfaces `open_bugs` that may already cover the bucket.

6. **Check Slack context (optional — only when Slack access is available)**: The TRT/release-oversight team discusses ongoing payload and CI issues in **#forum-ocp-release-oversight** (https://redhat.enterprise.slack.com/archives/C01CQA76KMX). Search/read the **last 14 days** of messages there for the bucket's signature (test name, error message, operator, platform, payload tag) — known payload-wide events, infra outages, and in-flight fixes are usually discussed there before triages/bugs exist, and a thread often names the owning team or an existing OCPBUGS ticket. If the agent has no Slack access (no Slack tooling/credentials), **omit this step entirely** — do not block or ask for access.

After deep-dive, finalize buckets. Each bucket must have:
- Member regression IDs (re-check the untriaged list — new siblings may have opened during analysis)
- Root cause summary (one paragraph) and failure classification (permafail / flaky / resolved / recent)
- **Owning component** (may differ from the Sippy component — state both)
- Triage type: `product` / `test` / `ci-infra` / `product-infra`
- Disposition: existing triage to extend / existing JIRA to create a triage for / new JIRA needed / no action (resolved or pure infra noise — say so explicitly and leave untriaged only with justification)

### Phase 4: Search for existing bugs, then triage each bucket

For each bucket, before filing anything new:

1. Check `triaged_matches` from `fetch-related-triages` (confidence ≥5 with an open JIRA is the default target).
2. Check `open_bugs` from the test report.
3. Search Jira for the root-cause signature (error message, operator name, `component-regression` label) in OCPBUGS against the **owning component** — the right bug may exist under Monitoring/etcd/MCO even though the regression sits under Installer.

Then act (this is where `--auto-triage` applies; without it, confirm each bucket with the user):

- **Extend existing triage**: `triage-regression` skill with `--triage-id` (additive merge is automatic; pass only the new IDs).
- **New triage to existing bug**: `triage-regression` skill with `--url`, `--type`, and a one-sentence `--description` (<120 chars).
- **New bug**: file with `/jira:create bug` (the `create` skill from the jira plugin) against the **owning component**, label `component-regression`, description per the bug-filing template in `/ci:analyze-regression` ("Prepare Bug Filing Recommendations" section: full test names in `{code}` blocks, test IDs, regression IDs, variants, error signature, Sippy test-details **UI** links for every member regression, suspect PRs). **Every JIRA issue or comment created by this workflow must end with an AI-attribution footer as a separate, visually marked block** — not a sentence buried in the text: place it after a divider, as its own paragraph or note panel, e.g. a `rule` followed by a `panel` (type `note`) in ADF containing "**AI-generated content:** This bug was filed by AI as part of Component Readiness triage duty. Please verify before acting on it." Mark it a release blocker (`set-release-blocker` skill), then create the triage record.
- Always finish a triage by running the `add-jira-triage-link` skill to put the triage URL into the JIRA description.

With `--auto-triage`, only act autonomously when confidence is high: consistent error signature across the bucket, and either a confidence ≥5 triaged match or an unambiguous existing open bug. Buckets requiring a *new* bug, or with mixed signals, are always presented for confirmation.

### Phase 5: Duty report

Present a final report:

1. **Inventory**: N untriaged regressions found → M buckets.
2. **Per bucket**: member regression IDs, root cause, owning component (vs. Sippy component), classification, evidence highlights (error signature, stage, representative run links), action taken (triage ID + JIRA link) or recommendation awaiting confirmation.
3. **Leftovers**: regressions deliberately left untriaged (resolved / one-off flake / inconclusive) with justification and what evidence would change the call.
4. **Cross-cutting observations**: payload-wide events, infra instability windows, techpreview-only patterns — useful context for the next duty shift.

## Pitfalls (learned from real duty runs)

- **Left = newest** in `pass_sequence` strings. Misreading direction inverts "regressed" vs "resolved".
- **Do not file bugs against Installer by default.** In practice a majority of `install should succeed` regressions in duty batches were owned by other components or were infra noise. The installer is the messenger.
- **`Unknown` component regressions** (e.g., `verify the cluster readiness and stability`, `verify all machines should be in Running state`) are wrappers; the co-failing tests and operator states identify the owner.
- **One bucket can span components**: Monitoring + Test Framework + Unknown + Installer regressions have all belonged to a single MCO bug. Don't let the component column fragment a bucket.
- **Techpreview variants** often fail for techpreview-only reasons (new feature gates); check whether the same job without techpreview passes before assuming a general regression.
- **API vs UI URLs**: convert `test_details_url` to the `sippy-ng` UI form before putting it in bugs or reports, by replacing the base `https://sippy.dptools.openshift.org/api/component_readiness/test_details` with `https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/test_details` (query parameters are identical).
- **Re-list before writing**: new regressions open continuously; refresh the untriaged list right before creating/updating triages so siblings opened mid-analysis are included.
- **Check closed/dropped siblings too.** A regression that looks novel is often a *new open instance* of a root cause whose earlier sibling was already triaged and has since dropped out of the active view (its regression closed). `fetch-related-triages` and a `--test-name` query without an open-only filter find these; reuse the existing triage/JIRA instead of filing a new bug.
- **Identical `prowjob_run_id` sets are the strongest clustering signal — but still not proof.** When two regressions were opened from literally the same job runs, treat them as one draft bucket, then confirm in Phase 3 that the failure outputs actually point at one cause: a single run can carry independent defects (two unrelated tests failing for unrelated reasons), and in mass-failure runs co-occurrence is largely coincidental. Only merge into one triage after the error signatures/artifacts agree.
- **The failing monitor/test is often just the messenger.** Example: pod-to-service and host-to-service connectivity tests (attributed to Networking) failed because the *test preparation* poller pods could not be created due to `etcdserver: request timed out` — an etcd-on-Azure product issue, not a networking bug. Always read the actual error text, including setup/preparation errors, before trusting the test's subject area.
- **Known recurring families**: some failure signatures come back shift after shift and usually already have a triage — e.g., etcd slowness / slow fdatasync on Azure masters, quay.io 502s / `ImagePullNeverCompletes` on metal jobs (ci-infra), transient cloud quota or DNS provisioning errors. Search existing triages for the signature before opening anything.
- **Similar symptom ≠ same bucket.** Two image-pull triages can coexist for different causes (e.g., a quay ci-infra outage vs. an MCO bootimage product bug). Match on the full signature — error text, platform, job family, timing — not just the headline symptom, and pick the triage whose root cause matches, not the first one found.
- **Triage type follows the root cause, not the component**: a flaky test with an external dependency is `test` even if it looks like a product failure; an etcd timeout that also hits customers is `product`; a registry outage is `ci-infra` even when it kills installs.
- **A closed/MODIFIED bug can still be the right triage target** when the failures predate the fix landing; check the fix-merge date against the newest failed run before dismissing it — but if failures continue after the fix, that's a failed fix (analysis_status -1000) and needs the bug reopened or a new one.

## Arguments

- `<view>`: Component Readiness view name (e.g., `5.0-main`). Required.
- `--components`: Space-separated component name filters, fuzzy-matched (e.g., `Installer Unknown`). Required in practice for duty scoping.
- `--auto-triage`: Allow high-confidence buckets to be triaged without per-bucket confirmation. New bug filing always requires confirmation.

## See Also

- Related Command: `/ci:analyze-regression` — single-regression deep dive; this skill orchestrates its techniques across a batch
- Related Skill: `create` (jira plugin) — file new JIRA bugs via `/jira:create bug` (`plugins/jira/skills/create/SKILL.md`)
- Related Skill: `list-regressions` (teams plugin) — batch listing (`plugins/teams/skills/list-regressions/SKILL.md`)
- Related Skill: `fetch-regression-details` (`plugins/ci/skills/fetch-regression-details/SKILL.md`)
- Related Skill: `fetch-related-triages` (`plugins/ci/skills/fetch-related-triages/SKILL.md`)
- Related Skill: `fetch-test-runs` (`plugins/ci/skills/fetch-test-runs/SKILL.md`)
- Related Skill: `fetch-job-run-summary` (`plugins/ci/skills/fetch-job-run-summary/SKILL.md`)
- Related Skill: `prow-job-analysis` — GCS artifact analysis for install/bootstrap failures (`plugins/ci/skills/prow-job-analysis/SKILL.md`)
- Related Skill: `fetch-test-report` (`plugins/ci/skills/fetch-test-report/SKILL.md`)
- Related Skill: `triage-regression` (`plugins/ci/skills/triage-regression/SKILL.md`)
- Related Skill: `add-jira-triage-link` (`plugins/ci/skills/add-jira-triage-link/SKILL.md`)
- Related Skill: `set-release-blocker` (`plugins/ci/skills/set-release-blocker/SKILL.md`)
- Related Skill: `oc-auth` (`plugins/ci/skills/oc-auth/SKILL.md`)
- TRT Documentation: https://docs.ci.openshift.org/docs/release-oversight/troubleshooting-failures/
