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

**Script invocation rules**: Run Python skill scripts directly and analyze their JSON output with your own reasoning (pass `--format json` where the script offers the flag; scripts without it, such as `list_regressions.py`, emit JSON by default). Do not pipe script output through inline Python one-liners. Do not suppress stderr: if a script exits non-zero or returns invalid/empty JSON, stop and surface the error — an authentication or API failure must never be mistaken for an empty inventory ("nothing to triage").

**Authentication**: Read steps (listing, fetching details, test runs, GCS artifacts) require no auth — Phases 1–3 and a read-only report must work without any credentials. Write credentials are validated **only when writes are going to happen**: with `--auto-triage`, validate both up front (so an expired token surfaces before hours of analysis); otherwise validate at the start of Phase 4, before the first write. Sippy writes (creating/updating triage records) require a Bearer token from the DPCR cluster (`api.cr.j7t7.p1.openshiftapps.com:6443`) — see the `oc-auth` skill and the token-extraction snippet in `/ci:analyze-regression`; check with an authenticated GET against `https://sippy-auth.dptools.openshift.org/api/component_readiness/triages` (200 vs 401/403).

JIRA writes (filing bugs, `set-release-blocker`, `add-jira-triage-link`) additionally require the `JIRA_USERNAME` and `JIRA_API_TOKEN` environment variables (API token from https://id.atlassian.com/manage-profile/security/api-tokens); verify with an authenticated GET against `https://redhat.atlassian.net/rest/api/3/myself` (Basic auth, 200 vs 401/403). If a required write credential is missing or invalid, pause before Phase 4 and ask the user to fix it — the analysis and report so far remain valid and must still be presented.

### Phase 1: Collect the full batch

1. **Load CI context**: Read the files in `plugins/ci/references/` (`jobs.md`, `tests.md`, `sippy-apis.md`) for conventions on tests, jobs, and Sippy APIs.

2. **Parse arguments**:
   - `view`: required, e.g. `5.0-main`
   - `--components`: component filter list, e.g. `Installer Unknown`. Matching is case-insensitive and hierarchy-aware: a filter matches the full component name or any ` / `-separated segment of it, so `Installer` also covers `Installer / openshift-installer`, and `Networking` covers `Networking / ovn-kubernetes`, `Networking / router`, and every other `Networking / *` component. If omitted, ask the user which components the duty covers.
   - `--auto-triage`: if present, triage buckets without per-bucket confirmation when confidence is high (see Phase 4). Default is to present findings and confirm before writing.

3. **List regressions** with the `list-regressions` skill:

   ```bash
   python3 plugins/teams/skills/list-regressions/list_regressions.py \
     --view <view> --components <components...>
   ```

   Keep only **open, untriaged** regressions (empty `triages` array), but note recently-triaged ones — they are prime candidates for absorbing untriaged siblings.

   **Closed regressions are out of scope — even when untriaged.** A regression whose `closed` field is set has already resolved itself; do not inventory it, cluster it, deep-dive it, or recommend retroactive triage for it. The duty batch consists solely of open untriaged regressions. Closed regressions may be *consulted* as evidence (e.g., a closed sibling that shares a root cause with an open bucket, or a closed sibling whose existing triage/JIRA an open bucket should reuse — see Pitfalls), but they must never appear as bucket members, action items, or "leftovers" in the report. The only exception is the explicit closed-set audit mode (`--audit-closed`, see below), which the user must request by name — it is never part of a normal duty run.

4. **Build a batch inventory table**: For every **open** untriaged regression record: regression ID, test name, component/capability, variants (Platform/Arch/Network/Topology/FeatureSet/Upgrade), opened date, failure/run counts. Present this table to the user up front so the scope of the duty run is visible. Do not include closed regressions in the inventory.

5. **Stale-triage sweep (mandatory) — a 100% triaged board can still hide live defects.** For every **open, already-triaged** regression, compare its `last_failure` against the state of its triage's JIRA: a regression whose bug is Closed/Verified/resolved but which has failed *after* the resolution date is an alarm, not a statistic. Its fresh failure window is either a failed fix or — more often — a **different cause hiding behind the old triage record**. For each such regression, verify the recent runs' signature (armed Sippy symptoms are a cheap first oracle: dry-run `reevaluate` the newest runs — label hits map windows to known causes instantly; unlabeled recent runs mean a new, uninvestigated cause) and add the correct triage(s) for the new window rather than trusting the stale one. A real sweep found three "triaged" metal regressions pointing at a Closed toolchain bug while actively failing daily from two entirely new causes (a build-cluster capacity outage and a same-day console regression) — invisible in every untriaged-count metric.

6. **Long-lived wrapper regressions are cause *timelines*, not single buckets.** An install-wrapper regression that stays open for weeks accumulates causes: one real record carried four (toolchain era → operator-flap window → CRI-O node bug → console startup fatal), each window separately verified and separately triaged. When a previously-analyzed regression shows new `last_failure` dates, re-verify the new window from scratch — never assume the existing triage covers it.

### Phase 2: Cluster into candidate buckets (cheap signals first)

Before any deep log analysis, group regressions using signals already in hand:

- **Same test, different variants** — almost always one bucket.
- **Same variant fingerprint, different tests** — e.g., `install should succeed: overall` + `: cluster creation` + `verify the cluster readiness and stability` all failing on `azure/amd64/techpreview` starting the same day is one bucket. Wrapper tests fail together.
- **Same opened date** — regressions opened the same day across components often share one payload-level cause.
- **Shared job runs** — fetch details for each regression (`fetch-regression-details` skill) and compare `job_runs` `prowjob_run_id`s. Regressions observed in the same failed runs are strong candidates for one bucket — but this is a clustering signal, not proof: the same run can contain independent defects or be a mass failure, so Phase 3 validation is still required. Also run the `fetch-related-triages` skill per regression; `same_last_failure` and `similarly_named_test` matches feed the clustering, and `triaged_matches` with confidence ≥5 immediately suggest an existing triage/bug for the whole bucket.
- **Symptom labels** — `fetch-regression-details` returns `label_summary` (per job) and `job_labels` (per run). A label shared by most failed runs of several regressions is a strong bucket signal, and labels are precise (human-written matchers over artifacts). An empty label list means nothing was *detected* — not that nothing is wrong.
- **Mass-failure marker**: high `test_failures` counts in `job_runs` mean the regression is likely collateral of a bigger event, not an independent issue.

Output of this phase: a **draft bucket list**, each bucket with member regression IDs, the shared fingerprint (test/variant/date/job-run overlap), and any candidate existing triage or JIRA bug.

Treat buckets as hypotheses — Phase 3 must confirm or split them. Do not merge buckets merely because both are "install failures"; installs fail at different stages for unrelated reasons.

### Phase 3: Deep-dive each bucket (confirm root cause and real owner)

For each bucket, pick 2–5 representative failed job runs (spread across jobs/variants; include the newest) and analyze. 2–5 runs are sufficient **only when they yield a consistent result** (same error signature / failure stage across all of them). If the sample is mixed or unclear — different errors, different stages, or an inconclusive owner — **extend the sample to 10–20 runs** before concluding; a small ambiguous sample must never be the basis for splitting/merging a bucket or attributing an owner.

**Deep-dive at least one CI sample per bucket — always, even at high confidence.** A Sippy `triaged_matches` confidence of 10 or a same-day triaged sibling is a *hypothesis*, not a verdict: Sippy matches on test names and shared job runs, which produces conf=10 for the same test name across unrelated platforms and root causes (see Pitfalls). Before accepting any disposition — including "extend existing triage" — read the actual failure evidence for at least one representative run of the bucket (failure output at minimum; installer logs / artifacts for install wrappers) and confirm it matches the target triage's root cause. You have deeper analysis capabilities than Sippy's heuristics — use your own judgement on the raw evidence, and if it contradicts the Sippy categorization, trust the evidence and re-bucket.

1. **Failure outputs**: `fetch-test-runs` skill with the bucket's test IDs and job run IDs — check whether error messages are consistent within the bucket. >90% same error is **strong evidence of** a single cause, not confirmation: wrapper tests and mass failures print identical error text for unrelated defects (e.g., "nodes not ready" covers disk, memory, and network deaths alike). Confirm with items 2–3 below before treating the bucket as one cause; inconsistent errors ⇒ split the bucket.

2. **Job run context**: `fetch-job-run-summary` skill per representative run — is the regressed test isolated, part of a consistent co-failure set, or one of hundreds of random failures? For `Unknown`-component and mass-failure regressions this is where the *real* component reveals itself: read the names of the co-failing tests.

3. **Install/bootstrap failures — mandatory artifact dig**: For any bucket whose tests include `install should succeed` (any stage) or bootstrap/cluster-readiness wrappers, invoke the `prow-job-analysis` skill per representative run. Do not stop at Sippy's generic "install failed" wrapper. From the GCS artifacts determine:
   - **Failure stage**: infrastructure provisioning / bootstrap / cluster creation (operators rolling out) / stability window.
   - **The blocking condition**: for cluster-creation failures, read `clusteroperators.json` (or the installer log's "Cluster operator X is not available" lines) and the failing operator's pod logs from the log bundle. For bootstrap failures, read the bootstrap log bundle (etcd, bootkube, release-image pulls).
   - **Bootstrap-era logs are full of normal transients — validate every causal theory against the gathered end-state.** During any bootstrap, operator logs contain scary-looking messages that resolve on their own ("the server could not find the requested resource (post routes.route.openshift.io)" before openshift-apiserver is up, static pods "0 nodes at revision 0" early on). Quoting one of these as the root cause is only valid if the *final* cluster state agrees. **The end-state oracle for bootstrap-stage failures is `clusteroperators.json`, not pod existence**: check etcd's `StaticPodsAvailable`/revision status and openshift-apiserver's `APIServicesAvailable` directly — a bootstrap-timed-out run whose gather still shows `etcd Available=False: 0 nodes are active; 3 nodes are at revision 0` was blocked by etcd no matter what else looks broken. Do **not** infer "etcd/apiserver were fine" from workload pods running: during bootstrap the bootstrap-node etcd/apiserver serve the control plane, so pods schedule and run happily while cluster etcd never deploys (this exact inference mis-refuted a correct etcd attribution in a real duty run). A crash-looping container's `*_previous.log` is primary evidence for *that container's* failure — but before assigning ownership, check whether its error names a missing upstream dependency (e.g., router looping on `failed to list *v1.Route: the server could not find the requested resource` is a **victim** of the Route API being unregistered, not a router bug).
   - **"Operators were not stable" — count condition transitions before classifying.** "Healthy at gather time" does NOT imply a harmless transient. Grep the install log for the operator's condition lines and look at `LastTransitionTime`/`DurationSinceTransition`: hundreds of transitions with `DurationSinceTransition=1s` across the stability window means the operator is **flapping continuously** (a sync-loop product bug that will never pass the stability check — permafail), whereas a single long `Progressing=True` window that eventually clears is a slow rollout (flaky race against the timeout). These two have opposite classifications and dispositions; a real duty run mislabeled a ~1 Hz flap (1600+ transitions in 30 minutes) as a "self-resolved slow rollout" by only looking at the gather-time state and one FailedMount event.
   - **The real owner**: the component whose operator/pods are actually failing. Examples from past duty: "cluster creation failed" ⇒ monitoring operator degraded ⇒ **Monitoring** bug; "bootstrap failed" ⇒ `etcdserver: request timed out` on Azure ⇒ **etcd** bug; nodes degraded during install ⇒ **MCO** bug; quota/DNS/cloud-API errors ⇒ **ci-infra**, not a product bug at all.
   - **Stability-window failures — "operator X not available" is a symptom, not a root cause.** For cluster-readiness/stability wrappers that fail on a ClusterVersion or ClusterOperator condition, two extra steps are mandatory before assigning an owner:
     1. **Recover the underlying condition message when the junit output is vague.** Outputs like `clusterversion not available: False` (empty reason) carry no cause. Run this literal check against the e2e step's `build-log.txt` (and, if present, the monitor-intervals JSON under the step's `artifacts/junit/`):

        ```bash
        curl -s <gcs-url-of-e2e-step>/build-log.txt | grep -oE '(Failing|Available|Degraded)=(True|False)[:,][^"\\]{0,160}' | sort | uniq -c | sort -rn | head
        ```

        The condition *messages* recovered this way (e.g., a controller error string) name the real culprit. This step is complete only when the report quotes the recovered message for every vague-output run. Never attribute such a run from its co-failing tests: co-failures on techpreview jobs are usually unrelated background noise, and correlation with them has produced wrong owners in past duty runs.
     2. **Ask *why* the operator went unavailable, not just *which* operator.** If everything is healthy at gather time, the wrapper caught a transient flap: read the operator's own pod log around the transition timestamps and find the trigger. Distinguish (a) the operator genuinely failing (⇒ product bug for that operator) from (b) a routine reconciliation/rollout triggered by a cluster mutation (config/secret change, node roll). A rollout of a single-replica deployment (e.g., image-registry on vSphere RWO storage) flaps Available by design. **A rollout-flap disposition must name the mutator, not stop at "the operator detected a configuration change":** quote the operator-log line identifying *which object changed* (grep the operator pod log for `object changed` / secret and config names and read the surrounding lines), then identify *who wrote it* — audit logs (verb `update`/`patch` on that object: user + userAgent) or the job's test-harness step logs (search them for the object name or the value being set). If a test step caused the mutation mid-run, the bucket is `test` owned by that suite, not a product bug against the flapping operator; filing "spurious rollouts" against the operator without naming the mutator is an incomplete deep-dive.

4. **Test-interference buckets — read the offending test's source before describing its scope.** When the root cause is another test's or tool's behavior (a test creates pods/namespaces that break an invariant check, leaks resources, reboots nodes, etc.), do not infer *why* the failure is confined to certain variants from the regression's variant labels — correlation with a variant (techpreview, platform, upgrade mode) is not evidence of how the offending code is gated. Instead:
   - Locate the offending code (`gh search code` in `openshift/origin` or the relevant repo for the test name, namespace prefix, or error string) and **read its skip/gate conditions** (`skipIf...`, `e2eskipper.Skipf`, feature-gate checks, platform checks, suite membership).
   - State the *actual* gating in the report (e.g., "gated on baremetal platform via `skipIfNotBaremetal`"), and if that gating is broader than the regressed variants, say so — the regression's variant slice then reflects job-scheduling or sample-size effects, not the blast radius, and other variants are also at risk.
   - Check the file's merge history (`gh api repos/<org>/<repo>/commits?path=...`) — a merge date matching the regression onset both confirms the attribution and identifies the owning team.
   - Never write "X-only" (techpreview-only, platform-only, arch-only) about a test or tool in the report or a bug unless the source code gating has been read and confirms it.

5. **Onset and suspect PRs** (when the bucket has a crisp start date): follow the "Determine Regression Start Date" and "Identify Suspect PRs in Payload" procedures from `/ci:analyze-regression` (first failing run → payload tag via `fetch-prowjob-json` → `fetch-new-prs-in-payload` → up to 5 candidate PRs vetted with `gh`). A LIKELY PR both strengthens the bucket and tells you the owning component/repo.

6. **Cross-check globally**: `fetch-test-report` skill (with `--no-collapse`) for the bucket's main test — confirms whether the issue is variant-specific or global, and surfaces `open_bugs` that may already cover the bucket.

7. **Check Slack context (optional — only when Slack access is available)**: The TRT/release-oversight team discusses ongoing payload and CI issues in **#forum-ocp-release-oversight** (https://redhat.enterprise.slack.com/archives/C01CQA76KMX). Search/read the **last 14 days** of messages there for the bucket's signature (test name, error message, operator, platform, payload tag) — known payload-wide events, infra outages, and in-flight fixes are usually discussed there before triages/bugs exist, and a thread often names the owning team or an existing OCPBUGS ticket. If the agent has no Slack access (no Slack tooling/credentials), **omit this step entirely** — do not block or ask for access.

After deep-dive, finalize buckets. **Depth is mandatory, not optional: no bucket may be finalized at LOW or MEDIUM confidence, and the duty run must not end with open "action items" like "needs artifact deep-dive" or "spot-check installer logs first".** When one regression's failed runs split into multiple distinct failure signatures, every signature must be root-caused independently — each may get its own triage record (a regression can carry several), and no run may be left labeled "ambiguous"/"unclear" in a bucket claimed at HIGH confidence: an unexplained run either gets dug into until it joins a signature, or the bucket's confidence is honestly downgraded and the digging continues. **Never bundle an unexplained sub-pattern into another pattern's triage "pragmatically" or "since the regression is open anyway"** — triage covers only the runs whose root cause it actually explains; attaching unexplained runs to it hides them from the next duty shift and mis-scopes the bug. If a sub-pattern remains unexplained, the whole bucket is not finalizable — keep digging. If confidence is not HIGH after the steps above, keep digging until it is — escalate through the evidence ladder yourself: raw failure outputs → job-run summaries → GCS artifacts (`prow-job-artifact-search`, install/test-failure analysis skills) → **audit logs** (grep for the failing object/namespace to identify the creating user and userAgent — this reliably resolves "who created this pod/namespace" questions) → junit timing correlation (what else ran in the same window) → suspect-PR vetting. Triage taking longer is acceptable; leaving an unexplained bucket is not. The only permitted low-confidence outcome is when the evidence is genuinely exhausted (artifacts expired, logs missing), and then the report must say exactly what was checked and what was missing.

Additional finalization rules (each has caused a wrong disposition in a real duty run):

- **"Resolved"/"stopped"/"no recurrence" claims require the full run list, not a sample.** Before classifying a signature as resolved or transient, enumerate *all* of the regression's `job_runs` by date and confirm the newest runs' signature. A signature absent from a 3–4 run sample of a 20-run regression is not evidence it stopped. And when a sub-test starts "passing" recently, verify recent runs actually **reach that stage**: a bootstrap failure cannot "self-resolve" while newer runs of the same job die earlier at infrastructure provisioning — the earlier failure masks the later stage, it does not fix it.
- **"Leave untriaged" is not a permitted disposition for a bucket with an identified root cause and owner.** If the deep-dive named the mechanism and the responsible component/suite, the bucket gets a triage (to an existing or new issue) — "collateral of noisy runs" is only a valid leftover justification when the failure has *no independent mechanism* (pure co-occurrence). A failure that is deterministically produced by another test's behavior has an independent mechanism and must be triaged as `test`.
- **Extend, don't duplicate.** When an existing triage record already covers the bucket's bug, extend that triage with the new regression IDs (`--triage-id`); do not create a second triage record pointing at the same JIRA.
- **Subagent outputs must be verified, not trusted.** If bucket deep-dives are delegated (subagents, parallel tasks), the orchestrator must check each returned bucket against this section's requirements before accepting it — in particular that the mandatory quotes are present (recovered condition messages for vague wrappers, mutator identification for rollout flaps, transition counts for stability failures, `*_previous.log` reads for crash-looping containers). A missing mandatory quote means the sub-analysis is incomplete and must be redone, regardless of how confident its prose sounds. Batch size is never a reason to skip mandatory steps.
- **Never end your turn to "wait" for dispatched subagents — the session ends the moment you stop.** There is no background execution across turns: an assistant message that ends with a status narration ("waiting for X analysis to complete") and no tool call terminates the run, and in CI the harness will tear the process down at that point. A real duty run burned 15 minutes and $12 of analysis and produced **no report** because the orchestrator ended its turn "waiting" for AWS/GCP subagents. Collect every subagent's result *within* the turn that needs it, and treat the duty report as a hard checkpoint: if the run were killed right after your current message, the report file must already exist on disk — write intermediate versions early and update them, rather than deferring all writing to a final step that may never come.

Each bucket must have:
- Member regression IDs (re-check the untriaged list — new siblings may have opened during analysis)
- Root cause summary (one paragraph) and failure classification (permafail / flaky / resolved / recent)
- **Owning component** (may differ from the Sippy component — state both)
- Triage type: `product` / `test` / `ci-infra` / `product-infra`
- Disposition: existing triage to extend / existing JIRA to create a triage for / new JIRA needed / no action (resolved or pure infra noise — say so explicitly and leave untriaged only with justification)

### Phase 4: Search for existing bugs, then triage each bucket

For each bucket, before filing anything new:

1. Check `triaged_matches` from `fetch-related-triages` (confidence ≥5 with an open JIRA is the default target) — but never act on a match, even conf=10, without the Phase 3 per-bucket CI-sample verification confirming the root cause actually matches.
2. Check `open_bugs` from the test report.
3. Search Jira for the root-cause signature (error message, operator name, `component-regression` label) in OCPBUGS against the **owning component** — the right bug may exist under Monitoring/etcd/MCO even though the regression sits under Installer.
4. **Component-scoped JIRA listing (mandatory — keyword search is not enough).** Owning teams describe defects in *developer* vocabulary that shares no keywords with the CI-side symptom (real duplicate: the CI symptom was "baremetal CO flaps Progressing / Applying metal3 resources", the existing bug was titled "Do not require metal3-static-ip-manager to progress in vmedia"). After determining the owning component, list its recent bugs regardless of keywords and *read the summaries*:

   ```
   project = OCPBUGS AND component = "<owning component>" AND created >= -21d ORDER BY created DESC
   ```

   A bug whose creation date falls inside the bucket's failure window, on the owning component, is a duplicate candidate even with zero keyword overlap — open it and compare mechanisms.
5. **Owning-repo merge-history check (mandatory when onset or cessation is dated).** Query the owning repo for PRs merged around the bucket's onset *and* cessation dates:

   ```bash
   gh pr list --repo <org>/<repo> --state merged --search "merged:<window>" --json number,title,mergedAt
   ```

   A merge at the **cessation** boundary is likely the fix — its `OCPBUGS-*` title prefix names the existing bug: triage to that bug instead of filing a new one. A merge at the **onset** boundary is a suspect trigger. The phrase "resolved by unidentified payload change" is banned from reports and bugs unless this check was run and came back empty — a real duplicate bug was filed because a signature that stopped on 07-21 was written off as "unidentified", while the owning repo had merged `OCPBUGS-xxxxx:`-titled fix at exactly that boundary. For **currently-live** breakage, also scan the owning repo's *newest* merges for revert PRs: a fresh `Revert "..."` title citing a TRT/OCPBUGS key hands you the trigger PR, the tracking ticket, and the expected recovery time in one query (a real console startup fatal was trigger-identified and triage-targeted entirely from its same-day revert's title).

Then act (this is where `--auto-triage` applies; without it, confirm each bucket with the user):

- **Extend existing triage**: `triage-regression` skill with `--triage-id` (additive merge is automatic; pass only the new IDs).
- **New triage to existing bug**: `triage-regression` skill with `--url`, `--type`, and a one-sentence `--description` (<120 chars).
- **New bug**: file with `/jira:create bug` (the `create` skill from the jira plugin) against the **owning component**, label `component-regression`, description per the bug-filing template in `/ci:analyze-regression` ("Prepare Bug Filing Recommendations" section: full test names in `{code}` blocks, test IDs, regression IDs, variants, error signature, Sippy test-details **UI** links for every member regression, suspect PRs). **Every JIRA issue or comment created by this workflow must end with an AI-attribution footer as a separate, visually marked block** — not a sentence buried in the text: place it after a divider, as its own paragraph or note panel, e.g. a `rule` followed by a `panel` (type `note`) in ADF containing "**AI-generated content:** This bug was filed by AI as part of Component Readiness triage duty. Please verify before acting on it." **Release blocker is conditional on the triage type and impact, not automatic**: mark the bug a release blocker (`set-release-blocker` skill) only for `product` bugs whose failures block or materially degrade blocking/informing payload jobs; `test` bugs (races, invariant-scan interference) and `ci-infra` issues (cloud capacity, registry outages) are **not** release blockers — state the blocker decision and its one-line justification in the report. Then create the triage record.
- Always finish a triage by running the `add-jira-triage-link` skill to put the triage URL into the JIRA description. The skill *appends* to the description — if the description ends with the AI-attribution footer, the appended link would land after it. After running the skill, verify the footer is still the final block; if not, move the footer back to the end of the description (or insert the triage link before the footer in the same update).
- While triaging each bucket, note whether its signature is symptom-worthy (crisp grep-able line in a durable artifact) — the Phase 5 report must carry a symptom proposal for every bucket where it is (see "Label the bucket's signature in Sippy").

With `--auto-triage`, only act autonomously when confidence is high: consistent error signature across the bucket, and either a confidence ≥5 triaged match or an unambiguous existing open bug. Buckets requiring a *new* bug, or with mixed signals, are always presented for confirmation.

### Phase 5: Duty report

Present a final report:

1. **Inventory**: N untriaged regressions found → M buckets.
2. **Per bucket**: member regression IDs, root cause, owning component (vs. Sippy component), classification, evidence highlights (error signature, stage, representative run links), action taken (triage ID + JIRA link) or recommendation awaiting confirmation.
3. **Leftovers**: regressions deliberately left untriaged (resolved / one-off flake / inconclusive) with justification and what evidence would change the call.
4. **Proposed Sippy symptoms** (mandatory section, even if empty): for every bucket whose root cause has a crisp, grep-able single-line signature in a durable artifact, include a concrete symptom proposal per the "Label the bucket's signature in Sippy" section below — label name, matcher, file pattern, validation pair, retro-apply run set. Proposing costs nothing (creation still requires explicit user confirmation); a duty shift that root-caused a bucket and did not propose a symptom for an obviously grep-able signature has left cheap future-triage value on the table. If no bucket qualifies, say so and why (e.g., signature only visible via timing correlation, artifact expires, no unique string).
5. **Cross-cutting observations**: payload-wide events, infra instability windows, techpreview-only patterns — useful context for the next duty shift.
6. **Session usage** (when available): if the run is orchestrated by a harness that captures usage telemetry (e.g. the CI job appends a "Session usage" section with model, turns, token counts, and cost after the session ends), do not fabricate these numbers yourself — the model cannot observe its own final token totals mid-session. In interactive runs simply omit the section.

### Label the bucket's signature in Sippy (propose always, create on confirmation)

When a bucket has a crisp, grep-able artifact signature (an error string or log line unique to the root cause), define a Sippy **symptom** so future runs are labeled automatically and the signature can be applied retroactively. Symptoms have repeatedly paid for themselves in real duty runs: a validated symptom **adjudicated a disputed root-cause attribution** (two competing theories for the same runs — the matcher proved which one was present), and retro-applying two symptoms to one regression's 20 runs **machine-verified a 19-vs-1 bucket split**. Good candidates: recurring infra events that spawn regressions across many job families, single-occurrence product signatures worth a tripwire (n=1 bugs), and any signature that a "known recurring family" keeps regenerating. These are writes: **always present the proposed label/symptom definitions and the target run list to the user and get explicit confirmation first** — `--auto-triage` does *not* authorize them.

1. Create a label and symptom via the authenticated API (DPCR Bearer token, same as triage writes): `POST https://sippy-auth.dptools.openshift.org/api/jobs/labels` (`{"label_title": ..., "explanation": ...}` — the title becomes the ID), then `POST .../api/jobs/symptoms` (`{"summary": "<Name> - <JIRA key>", "matcher_type": "string|regex|file", "file_pattern": "<glob under the job-run GCS root>", "match_string": ..., "label_ids": [...]}`). The symptom ID is derived from the summary; gzipped artifacts are decompressed transparently. To change a symptom, DELETE and re-POST (PUT does not reliably update). Reference the JIRA key in both the label explanation and the symptom summary.
2. **Beware single-occurrence false positives.** Before finalizing a matcher, grep the target file in a *healthy* run: many error lines appear once benignly during normal startup (e.g., a router logs one probe failure while warming up — identical text to the pathological loop). String/regex matchers cannot count occurrences, so if the line can appear benignly, re-anchor to an artifact that only exists in the failure mode — e.g., a container's `*_previous.log` (only present after a crash/restart) instead of its current log, or an events.json string that healthy runs never emit.
3. **Validate with a dry run** against one known-positive and one known-negative run — the best negative is a *near miss*: a failed run of the same job family with a different root cause (it catches over-broad matchers that a green run would not). `POST .../api/jobs/runs/reevaluate` with `{"prow_job_build_ids": [...], "dry_run": true}`. Proceed only if **both** outcomes are correct; otherwise refine the matcher and re-validate. Note: reevaluation runs *all* symptoms, so unrelated pre-existing labels may legitimately appear on your negative — check only that *your* symptom's matching is correct.
4. Then apply with `"dry_run": false` to the bucket's `prowjob_run_id`s. The API caps requests at 50 IDs, but reevaluation scans GCS artifacts server-side and large batches time out at the gateway (504) — use **batches of 5–10** with a retry, check each result's `status`, and stop and report on the first failed batch or any non-`success` result rather than continuing.
5. Match the **underlying error**, not a transient side effect: a matcher keyed on a crash/panic goes silently false-negative the moment a partial fix removes the crash while the defect persists. If the primary evidence lives in pod logs that sometimes fail to gather (dying clusters), add a fallback symptom against an artifact that survives (e.g., `pods.json` state/reason strings) mapped to the same label. When the same signature can surface under different step names (e.g., devscripts-driven vs plain IPI installs), create one symptom per file pattern, all mapped to the same label.

## Closed-set audit mode (`--audit-closed`) — justify why every closed regression closed

```
bulk-triage-regressions <view> --components ... --audit-closed
```

An explicitly-requested, **read-only** mode that answers a different question than triage duty: not "who owns this failure?" but **"why did this regression close, and can we prove it?"** Every closed untriaged regression must end the audit in exactly one of these justification classes:

| Class | Meaning | Proof required |
|---|---|---|
| `fixed` | A fix merged; closure follows it | Fix PR/bug with merge/resolution date at or before the close boundary |
| `event-ended` | An infra/payload event ended | Event window bracketing the failures (bad payload, repo outage, cloud capacity, credentials) |
| `intermittent-cause-open` | Pass rate recovered but the defect is still open | Signature matched to an open bug; state explicitly that closure ≠ resolution |
| `collateral` | Closed with the window of a tracked sibling event | Signature or run overlap with the tracked event |
| `evidence-expired` | Run history and artifacts are gone | List exactly what was checked (regression details, GCS) and the statistical argument (age, sibling consistency) — flagged, never silently absorbed |

No regression may be left as "unknown". `evidence-expired` is the only permitted terminal state without a mechanism, and it must be flagged in its own report section.

### Scale technique (a closed set is 5–30x a duty batch — per-regression deep-dives do not scale)

1. **Inventory and cluster first**: fetch details for all members (parallel, ~8 workers is safe for the details endpoint), then cluster by (test-family, platform, featureset, close-window). Expect heavy super-clusters — in a real audit, **one bad nightly payload explained 21% of the entire closed set** (installer stamped version "0.0" panicking on every platform for one day). Always look for same-day open/close waves across platforms before analyzing anything individually.
2. **Bypass the Sippy runs API for bulk signature extraction — it rate-limits (HTTP 429) far below audit volume, and backoff does not help at this scale.** Go to GCS directly (unthrottled, parallel-safe):
   - *Install-family tests*: classify from the installer log (`artifacts/*/ipi-install-install*/build-log.txt`, devscripts equivalent on metal) with an ordered signature catalog (most-specific first). Seed the catalog from the view's known events and extend it with whatever the duty history has verified (ign-push 403s, cipherSuites/rev-0, toolchain download, quay pulls, registry.ci 5xx, quota, capacity, provisioning, per-operator stabilization). Guard against substring traps — a real run mis-binned 31 regressions because `lease` matched inside `release`.
   - *Everything else*: parse the junit XML under the e2e step (`artifacts/*/<e2e-step>/artifacts/junit/junit_e2e*.xml`) with a real XML parser (regex over XML mis-matched ~95% of testcases in practice) and take the `<failure>` of the exact testcase.
   - Sample the 2 newest failed runs per regression; extend only where signatures disagree.
3. **Match against the full triage catalog**: fetch all existing triage records once (`/api/component_readiness/triages`) and index their regressions by test name — a closed untriaged record is very often the untriaged sibling of a triaged one, which supplies the bug and the closure mechanism for free.
4. **Date-anchor every closure claim**: `fixed` requires the fix date ≤ close boundary (JIRA `resolutiondate`, `gh pr list --search "merged:<window>"` on the owning repo); `event-ended` requires the last failing run to fall inside the event window. The Phase 4 component-scoped JIRA listing and merge-history checks apply here unchanged.
5. **Checkpoint long-running collection to disk and run it detached** (nohup + periodic JSON dumps): bulk GCS extraction takes tens of minutes, harness timeouts will kill foreground loops, and two concurrent writers on one results file destroy each other — one writer, atomic-ish checkpoints, verify counts after every stage.

### Audit report structure

1. Executive summary: category table (name, member count, one-line verdict).
2. Method: exactly which artifact paths / APIs were used and why.
3. Per-category narrative: mechanism, proof, closure explanation, and for `intermittent-cause-open` the explicit warning that siblings will reopen.
4. **Per-regression appendix — one row per member, no exceptions** (ID, test, platform/featureset, opened→closed, category, evidence sample).
5. Honest-limitations section listing every `evidence-expired` member.

### Audit-specific pitfalls

- **Sippy retention creates a hard evidence horizon**: regressions from the view's first tracking week may have no run history at all, and GCS artifacts expire (~3 months). Do not let the horizon silently shrink the audit — count and flag such members.
- **The view-baseline start date masquerades as a mass event**: many unrelated regressions "open" on the view's first tracking day. Check whether a suspicious same-day open wave is simply the earliest date in the dataset before hunting for a common cause.
- **"Closed" is not a verdict**: a closed regression whose signature maps to a still-open bug (`intermittent-cause-open`) is a prediction of future regressions — surface these in the summary so the next duty shift expects them.

## Pitfalls (learned from real duty runs)

- **Left = newest** in `pass_sequence` strings. Misreading direction inverts "regressed" vs "resolved".
- **Do not file bugs against Installer by default.** In practice a majority of `install should succeed` regressions in duty batches were owned by other components or were infra noise. The installer is the messenger.
- **`Unknown` component regressions** (e.g., `verify the cluster readiness and stability`, `verify all machines should be in Running state`) are wrappers; the co-failing tests and operator states identify the owner.
- **One bucket can span components**: Monitoring + Test Framework + Unknown + Installer regressions have all belonged to a single MCO bug. Don't let the component column fragment a bucket.
- **Techpreview variants** often fail for techpreview-only reasons (new feature gates); check whether the same job without techpreview passes before assuming a general regression.
- **A regression's variant slice is not the offending code's gating.** Real example: a QoS-invariant regression appeared only under `metal/techpreview`, and the report claimed the interfering SecurityPenetration tests were "techpreview-gated" — reading `penetration.go` showed they are gated on **baremetal platform**, so every metal job (any featureset) was exposed. Claims like "techpreview-only" or "platform-only" about a test/tool must come from its source-code skip/gate conditions (Phase 3 item 4), never from the variants Sippy happened to flag.
- **API vs UI URLs**: convert `test_details_url` to the `sippy-ng` UI form before putting it in bugs or reports, by replacing the base `https://sippy.dptools.openshift.org/api/component_readiness/test_details` with `https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/test_details` (query parameters are identical).
- **Re-list before writing**: new regressions open continuously; refresh the untriaged list right before creating/updating triages so siblings opened mid-analysis are included.
- **Check closed/dropped siblings too.** A regression that looks novel is often a *new open instance* of a root cause whose earlier sibling was already triaged and has since dropped out of the active view (its regression closed). `fetch-related-triages` and a `--test-name` query without an open-only filter find these; reuse the existing triage/JIRA instead of filing a new bug.
- **Identical `prowjob_run_id` sets are the strongest clustering signal — but still not proof.** When two regressions were opened from literally the same job runs, treat them as one draft bucket, then confirm in Phase 3 that the failure outputs actually point at one cause: a single run can carry independent defects (two unrelated tests failing for unrelated reasons), and in mass-failure runs co-occurrence is largely coincidental. Only merge into one triage after the error signatures/artifacts agree.
- **The failing monitor/test is often just the messenger.** Example: pod-to-service and host-to-service connectivity tests (attributed to Networking) failed because the *test preparation* poller pods could not be created due to `etcdserver: request timed out` — an etcd-on-Azure product issue, not a networking bug. Always read the actual error text, including setup/preparation errors, before trusting the test's subject area.
- **"Operator not available" during a stability window is not automatically that operator's bug.** Real example: `verify the cluster readiness and stability` failed with "Cluster operator image-registry is not available" on vSphere; the draft disposition was a product bug against Image Registry. The operator log showed the trigger: the job's test harness replaced the cluster pull secret mid-run, the operator re-synced `installation-pull-secrets` and rolled its single-replica deployment — a by-design flap. Correct disposition: `test` bug against the harness. Before filing against a flapping operator, find the mutation that triggered the reconcile.
- **A vague wrapper message hides a specific controller error — extract it, don't guess.** Real example: runs failing with bare `clusterversion not available: False` were drafted as "UDN CRD breakage" because UDN tests co-failed in the same jobs. The monitor intervals actually showed `Failing=True: failed to list agentic runs: no matches for kind "AgenticRun"` — a CVO controller bug with a merged fix, unrelated to UDN. When the junit output has an empty reason, grep the build log/monitor intervals for the condition-change events and their messages before attributing.
- **Bootstrap-transient theories that contradict the end-state.** Real example: an Azure bootstrap timeout was attributed to an etcd-operator "cipherSuites not found" race, and a GCP one to "monitoring can't create Routes (Route API not registered)" — the initial refutation used `pods.json` ("workloads running ⇒ etcd fine") and pinned it on crash-looping routers instead. `clusteroperators.json` later proved the refutation wrong: etcd was at `0 nodes active / revision 0` in every run — the etcd theory was **correct**, the router loop was a victim (it looped on `failed to list *v1.Route`, i.e., the Route API was never registered), and the bug got mis-attributed to the router change for weeks. Two lessons: pods running proves nothing about cluster etcd during bootstrap, and a crash-looping component whose error names a missing upstream dependency is a victim, not an owner.
- **A validated Sippy symptom detects a signature, not a cause.** The router probe-loop symptom fired on 30/33 runs of the etcd bucket above — correctly, because the loop really happens — yet triaging by that label alone attributed victim runs to the router bug. When a symptom's signature can be produced downstream of a different defect, its label text must say so, and a second symptom keyed on the *upstream* discriminator (here: the etcd cipherSuites/revision-0 evidence) should exist to adjudicate.
- **Flapping ≠ slow rollout, and a small sample ≠ cessation.** Real example: `not stable: [baremetal]` was classified "slow rollout, self-resolved" from 3 sampled runs that looked healthy at gather — the install log actually showed the operator re-transitioning `Progressing` every ~1 second (1600+ times in 30 minutes), a permafail sync-loop bug present in 19 of 20 runs including the newest. Count condition transitions and enumerate all run dates before choosing between flaky-transient and permafail.
- **Identifying a root cause and then leaving the regression untriaged is a contradiction.** Real example: a QoS-invariant failure was correctly root-caused to debug pods created by SecurityPenetration tests, then dispositioned "leave untriaged — mass-failure collateral". Deterministic test interference is an independent mechanism: it gets a `test` triage and a bug, regardless of how noisy the surrounding runs are.
- **No triage record ≠ no bug, and keyword search ≠ component search.** Real example: a CBO Progressing-flap bucket had no related triage and no keyword hits, so a new bug was filed — duplicating a 8-day-old bug on the owning component whose summary used only developer vocabulary ("static-ip-manager should be optional"), with the fix already merged at exactly the bucket's cessation date. The component-scoped JIRA listing and the owning-repo merge-history check (Phase 4 items 4–5) exist because both would have caught it; run them before every new-bug disposition, and treat an unexplained cessation as a strong hint that a fix already landed somewhere.
- **Known recurring families**: some failure signatures come back shift after shift and usually already have a triage — e.g., etcd slowness / slow fdatasync on Azure masters, quay.io 502s / `ImagePullNeverCompletes` on metal jobs (ci-infra), transient cloud quota or DNS provisioning errors. Search existing triages for the signature before opening anything.
- **Similar symptom ≠ same bucket.** Two image-pull triages can coexist for different causes (e.g., a quay ci-infra outage vs. an MCO bootimage product bug). Match on the full signature — error text, platform, job family, timing — not just the headline symptom, and pick the triage whose root cause matches, not the first one found.
- **Triage type follows the root cause, not the component**: a flaky test with an external dependency is `test` even if it looks like a product failure; an etcd timeout that also hits customers is `product`; a registry outage is `ci-infra` even when it kills installs.
- **A closed/MODIFIED bug can still be the right triage target** when the failures predate the fix landing; check the fix-merge date against the newest failed run before dismissing it — but if failures continue after the fix, that's a failed fix (analysis_status -1000) and needs the bug reopened or a new one.
- **Sample runs only from the regression's own `job_runs` list.** Broad Sippy job-filter URLs ("all jobs failing test X") sweep in unrelated jobs and post-fix eras; analyzing "3 random jobs" from such a list has produced three confidently wrong root causes in one shift. Every run you cite must be a member of the regression (and predate any candidate fix).
- **A CI step pod that never started is a build-cluster problem, not a product one.** If the prow build log shows `Deleting pod <step> that failed to start` or `pod pending for more than 1h: pod has not been scheduled` (with `0/N nodes are available: ... untolerated taints / unschedulable`), the OpenShift installer never ran — no product artifact exists to analyze. Classify as `ci-infra`, and name the build cluster from `prowjob.json` (`.spec.cluster`, e.g. build10) so the infra team knows where the capacity problem is. Trivial setup steps (rbac, hosted-loki) failing this way across a job family for days is a capacity outage worth its own tracking ticket.
- **`Unknown` conditions are not resource pressure.** When a kubelet stops posting status, *all* node conditions flip to `Unknown`, and the MCO controller logs `Reporting unready: ... OutOfDisk=Unknown` — this is a stale-status marker, not disk exhaustion. Only `DiskPressure/MemoryPressure=True` (or eviction/OOM events, df output, sosreport sar) is evidence of actual resource pressure.
- **Superficially different per-run mechanisms can share one upstream cause — and two defects can chain.** In one incident, runs died variously of maxPods saturation, memory livelock, and an OVS flow storm; all were downstream of a single namespace-deletion blockage, which also amplified an otherwise-transient network defect into node death. When run-level root causes look "completely different", look one level up (what leaked, what was stuck, what accumulated) before declaring them unrelated; and when a symptom vanishes without its component's fix merging, suspect an interacting defect that got fixed instead.

## Arguments

- `<view>`: Component Readiness view name (e.g., `5.0-main`). Required.
- `--components`: Space-separated component name filters, case-insensitive and hierarchy-aware (e.g., `Installer` also matches `Installer / openshift-installer`; `Networking` matches `Networking / ovn-kubernetes`, `Networking / router`, ...). Required in practice for duty scoping.
- `--auto-triage`: Allow high-confidence buckets to be triaged without per-bucket confirmation. New bug filing always requires confirmation.
- `--audit-closed`: Read-only closed-set audit mode (see "Closed-set audit mode") — justifies why every closed untriaged regression closed. Mutually exclusive with normal duty triage and with `--auto-triage`; performs no writes.

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
