# Improvement Recommendations: Getting More Green Payloads

**Generated:** 2026-05-14
**Based on:** Analysis of 331 payload agent jobs (2026-03-18 to 2026-05-14) and eval run `2026-05-14-opus-4cases`

---

## 1. Why Are Payloads Struggling?

The 23.9% rejection rate (79 of 331 payloads) means roughly 1 in 4 payloads fails to accept. The data reveals three distinct categories of payload failure, each requiring different interventions.

### 1.1 Code Regressions That Should Have Been Caught Earlier

At least 10 confirmed true-positive regressions were identified across the analysis period — PRs that landed, broke payloads, and were eventually reverted:

| Repo | PR | Days to Revert | Payloads Broken |
|------|-----|----------------|-----------------|
| cluster-version-operator | #1309 | <1 | 1+ |
| oc | #2219 | ~1 | 2 |
| cluster-authentication-operator | #839 | ~1 | 1 |
| cloud-credential-operator | #978 | ~1 | 4+ |
| hypershift | #7790 | ~1 | 1 |
| cluster-network-operator | #2959 | ~1 | 2 |
| cluster-monitoring-operator | #2814 | ~1 | 2 |
| cluster-monitoring-operator | #2886 | <1 | 1 |
| hypershift | #8357 | <1 | 1 |
| cluster-node-tuning-operator | #1499 | ~1 | 1 |

These 10 regressions collectively broke at minimum 16 payloads (some broke multiple consecutive payloads, like CCO #978 which persisted across 4). That accounts for roughly 20% of all rejections. The pattern is clear: regressions that escape presubmit testing (upgrade, FIPS, SNO, techpreview, bare-metal scenarios) land and break payloads for 1+ days before human TRT engineers notice and revert.

Key repos by regression frequency: **hypershift** (2 regressions), **cluster-monitoring-operator** (2), with one each across 6 other operators.

### 1.2 Infrastructure Failures

The analysis found rejected payloads with pure infrastructure failures (e.g., case 009 with AWS lease exhaustion on the hypershift aggregated job, the 2026-05-14 payload with Insights API Gateway HTTP 500). The agent correctly produces no revert candidates for these, but the payloads still get rejected. These represent wasted CI compute and pipeline delays that no skill improvement can fix — they require infrastructure reliability improvements or force-accept automation.

The `force_accept_recommended` field exists in the schema but appears underutilized. When all failures are infrastructure-related and no payload has been accepted for 18+ hours, the agent should be recommending force-accepts more aggressively.

### 1.3 The "Dark Matter" — 77 Rejected Payloads With No High-Confidence Candidates

The most concerning finding: 77 of 79 rejected payloads (97.5%) got zero high-confidence revert candidates. Two possibilities:

1. **Many rejections are genuinely caused by infrastructure/flakes**, not code regressions. If true, the force-accept mechanism should be catching more of these.
2. **The agent is missing real regressions.** If TRT engineers are independently reverting PRs that the agent never flagged, those are detection gaps.

The data does not disambiguate these cases because we lack a systematic cross-reference between TRT revert activity and agent output. This is the single most important gap to close (see Recommendation P1 below).

---

## 2. Why Is the Agent So Conservative?

Only 2.5% of rejected payloads produce high-confidence candidates. The agent's conservatism stems from multiple compounding factors.

### 2.1 The Rubric Requires Strong Evidence That Is Often Unavailable

The scoring rubric requires 85+ points for a revert recommendation, with the highest-weight signal being "error message match" (+40). This demands that the subagent trace a failure to specific code changed by a PR — a capability that works well when errors reference function names or packages (e.g., CVO #1309: klog corrupting JSON stdout, directly traceable to the test automation PR), but fails when:

- **Failures are emergent**: CNO #2959 added NetworkPolicies that blocked egress. The error messages reference API server timeouts and CrashLoopBackOff, not NetworkPolicy resources — the connection requires understanding Kubernetes networking, not string matching.
- **Multiple PRs touch the same repo**: Case 008 demonstrates this perfectly. The hypershift repo had PRs #7790, #8087, #8138 all landing near the originating payload. The agent picked #8087 (wrong) over #7790 (correct) because it couldn't distinguish CPO router LB changes from HCCO metrics forwarder changes within the same monorepo.
- **The failure is in test infrastructure**: NTO #1499 embedded testdata into a binary, causing test failures. The error messages reference test execution, not the embedding change.

### 2.2 Subagent Analysis Is the Bottleneck

Each failed job gets its own subagent for investigation. The subagent must: download artifacts, parse JUnit, extract must-gather, read pod logs, and trace to root cause. This is the most expensive and time-consuming step (case 008 took 1086s and $8.56 vs ~500s/$5-6 for simpler cases). When the subagent analysis is shallow — restating symptoms rather than tracing causes — the correlation step in 6.1 has insufficient evidence to score candidates highly.

The agent processes the *entire* artifact tree for each job. A single Prow job's artifact directory can contain hundreds of files across dozens of directories. The skill must navigate this to find the relevant logs, but the sheer context volume means it may miss key files or spend tokens on irrelevant ones.

### 2.3 No Memory Across Runs

The agent treats each payload analysis as independent. But multi-payload persistence — the same PR flagged across consecutive runs — was always a true positive (CCO #978 across 4 payloads, CNO #2959 across 2, CMO #2814 across 2). The agent cannot currently boost confidence based on "I flagged this same PR last time and the failure persists." Each run starts cold.

### 2.4 Infrastructure vs. Code Regression Discrimination Is Weak

Three of 5 false positives (FP1: ingress Sail migration, FP4: hypershift builder image, FP5: etcd rebase) involved the agent attributing infrastructure or platform-side failures to code changes. The agent lacks explicit checks for:

- Cloud provider service incidents (Azure Graph API outages, AWS API throttling)
- Known CI infrastructure issues (build farm problems, quota exhaustion)
- Platform-side changes that resolve without code changes

---

## 3. Concrete Skill Improvements

### 3.1 Progressive Discovery for Artifact Navigation

**Problem:** The analyze-payload skill's Step 5 subagents process the full artifact tree for each Prow job, consuming large context windows.

**Solution:** Implement a two-phase artifact investigation:

1. **Phase 1 — Triage** (cheap): Read only JUnit XML + build-log.txt + a small set of key files (e.g., `gather-extra/events.json` headers, `pods/` directory listing). Classify the failure as install/test/upgrade/infra and identify the specific failing tests.
2. **Phase 2 — Deep dive** (expensive): Based on Phase 1 classification, read only the relevant subset of artifacts. For test failures, go straight to the must-gather for the failing operator. For install failures, read the bootstrap logs. Skip prometheus tarballs, audit logs, and unrelated operator logs entirely.

This reduces per-job cost and improves analysis quality by focusing context on relevant artifacts. The `trim-archives.sh` script in `eval/scripts/` already identifies the heaviest files the skill never reads — use this as a guide for what Phase 1 should skip.

### 3.2 Sub-Component Awareness for Multi-PR Repos

**Problem:** Case 008 is the persistent eval weak point. The skill treats "hypershift" as a single component, but hypershift contains distinct sub-components: CPO (Control Plane Operator), HCCO (HostedCluster Config Operator), KAS, test framework, etc. When multiple PRs touch different hypershift sub-components, the "component exclusivity" rubric signal (+10 to +30) is applied at the wrong granularity.

**Solution:** Modify the component exclusivity scoring in Step 6.1 to support sub-component resolution for large repos:

- For repos with >3 PRs in a payload, use the PR's changed file paths to determine sub-component (e.g., `control-plane-operator/` vs `hypershift-operator/` vs `test/`).
- Score exclusivity based on sub-component overlap, not repo-level overlap.
- Add a special signal: "PR introduces a new test that immediately fails" should be near-automatic +40 (error message match equivalent), since the failing test name often directly references the PR's feature.

For case 008 specifically: PR #7790 introduced the `EnsureMetricsForwarderWorking` test and the HCCO metrics forwarder feature. The test name directly references the feature the PR added. The skill should recognize this as a +40 error message match, not just a +10 component match.

### 3.3 Cross-Run State and Confidence Boosting

**Problem:** Multi-payload persistence was a 100% true-positive signal, but the agent cannot use it.

**Solution:** Add an optional `--previous-results` flag to analyze-payload that accepts a path to a prior run's `payload-results-{tag}.yaml`. When provided:

1. Load the previous candidates list.
2. For any candidate PR that appears in both the current and previous run's output, apply a persistence bonus: +15 confidence points (capped at 100).
3. Note in the rationale: "This PR was also flagged in the previous payload analysis with confidence N."

The CI job that runs the payload agent can be modified to pass the previous run's results file. This is a lightweight change that doesn't require a database — just file passing between consecutive runs.

### 3.4 Cloud Platform Issue Detection

**Problem:** The main false positive source is attributing cloud-platform-side issues to code changes (FP4: Azure Graph API auth failure attributed to hypershift #8194's builder image changes).

**Solution:** Add an explicit infrastructure triage step before PR correlation:

1. **Check for known cloud provider failure signatures**: Azure Graph API errors, AWS STS failures, GCP quota exhaustion. Maintain a list of error patterns that indicate provider-side issues.
2. **Check for transient resolution**: If the same test passed on the same platform in a very recent payload (within 2 payloads), and no relevant PR landed between the pass and the current failure, classify as likely transient.
3. **Require mechanism evidence for platform-specific failures**: When a failure only occurs on one cloud platform (e.g., only AKS), the causal chain from PR to platform-specific error must be explicit, not inferred. "This PR changed builder images, which might have changed SDK versions, which might have changed auth behavior" is speculation, not evidence.

Add a negative evidence signal to the rubric: **Platform-specific failure without mechanism**: -20 (failure occurs only on one cloud platform and the causal chain from PR to platform-specific behavior requires multiple speculative steps).

### 3.5 Format Standardization

**Problem:** Output format varies across runs (gzip vs plain, `score` vs `confidence_score`, nested vs flat candidate lists, missing `phase` field in ~240 of 331 jobs).

**Solution:**
- Enforce the `payload-results-yaml` schema strictly. The schema is well-defined in the skill but the agent's output drifts.
- Always populate the `phase` field in metadata (currently missing in 72% of outputs).
- Standardize on plain-text YAML (not gzip). If compression is needed for CI artifact storage, do it at the artifact upload layer, not in the skill output.
- Remove the `revert_recommendations` field from the schema — it has never been populated across 331 jobs. All recommendations flow through `candidates[].actions[]`.

### 3.6 Test-Introduction Signal

**Problem:** The skill doesn't recognize that a PR introducing a new test which immediately fails is extremely strong evidence (effectively 100% confidence) that the PR is the cause.

**Solution:** Add a rubric signal: **New test introduction** (+40): If the failing test name matches a test added by the candidate PR (detectable from the PR diff), this is near-certain causation. This directly addresses case 008 where #7790 introduced `EnsureMetricsForwarderWorking` and it immediately started failing.

---

## 4. Eval Improvements

### 4.1 New Eval Case Types

The current eval suite only tests `analyze-payload`. Additional eval types would catch more issues:

**Infrastructure-only failure cases (eval type: `analyze-payload-infra`)**
- Input: Payloads rejected due to pure infrastructure failures (cloud quota, API outages, CI platform issues)
- Expected: No revert candidates, `force_accept_recommended: true` when applicable
- Tests: False positive suppression, infrastructure classification accuracy
- Source data: Case 009's hypershift aggregated job (AWS lease exhaustion), the 2026-05-14 payload (Insights API Gateway HTTP 500)

**False positive detection cases (eval type: `analyze-payload-fp`)**
- Input: Payloads where the agent historically produced false positives
- Expected: Either no candidates or low-confidence candidates (below 85)
- Tests: Whether skill improvements reduce false positive rate without hurting true positive rate
- Source data: FP1 (ingress Sail migration), FP4 (hypershift builder image / Azure Graph API), FP5 (etcd rebase)

**Multi-payload persistence cases (eval type: `analyze-payload-streak`)**
- Input: Consecutive payloads in a rejection streak with the same root cause
- Expected: Same candidate PR flagged across all payloads with increasing or stable confidence
- Tests: Cross-run consistency and confidence stability
- Source data: CCO #978 (4 consecutive payloads), CNO #2959 (2 payloads)

**Individual job failure analysis (eval type: `prow-job-analyze`)**
- Input: Single Prow job URLs with known root causes
- Expected: Correct failure type classification, specific root cause identification
- Tests: Subagent analysis quality in isolation (decoupled from PR correlation)
- Source data: The install failure case (`case-install-001-metal-ipi-ipv6-ckao`) already started; expand to test failures

### 4.2 Regression Guard Cases

Every skill improvement risks degrading existing performance. The current 4-case eval suite should be expanded to at least 8-10 cases before running `/eval-optimize`:

| Case | Type | Key Test |
|------|------|----------|
| 006 | Rejected, 2 candidates (FP) | Both FP candidates correctly identified |
| 007 | CI, single revert (TP) | CCO #978 at 95 confidence |
| 008 | CI, multi-PR hypershift (TP) | #7790 as primary, not #8087 |
| 009 | Nightly, CVO revert (TP) | #1309 at 95, infra correctly classified |
| NEW-A | CNO NetworkPolicy (TP) | #2959 at 90, cross-platform consistency |
| NEW-B | CMO monitoring (TP pair) | Two distinct CMO PRs correctly distinguished |
| NEW-C | Hypershift builder image (FP) | #8194 NOT flagged as high-confidence |
| NEW-D | Ingress Sail migration (FP) | #1354 NOT flagged (or correctly low-confidence) |
| NEW-E | Infrastructure-only rejection | No candidates, force-accept recommended |
| NEW-F | etcd rebase (FP) | #368 NOT flagged as high-confidence |

Cases NEW-C, NEW-D, and NEW-F are critical — they test false positive suppression, which is currently untested. Without these, skill improvements that increase sensitivity will also increase false positives undetected.

### 4.3 Cost and Efficiency Tracking

The eval already tracks cost per case ($5-9 per case). Add a threshold:

- `max_cost_usd` per case: Flag cases that exceed $10. Case 008 at $8.56 is already the most expensive; progressive discovery (3.1) should reduce this.
- `max_duration_s` per case: Flag cases exceeding 900s. The payload agent runs as a CI job with wall-clock constraints.

### 4.4 Judge Improvements

The current `revert_scoring_accuracy` judge deducts points for not itemizing rubric components. This is a presentation issue, not an analytical one (cases 006 and 007 scored 4/5 for this reason alone). Either:

- Update the rubric to explicitly require itemized scoring in the YAML rationale field, or
- Update the judge to give 5/5 when all candidates and scores are correct regardless of itemization format.

---

## 5. Prioritized Action Plan

Ranked by expected impact on green payload rate, considering both implementation effort and reach.

### P1: Close the Detection Gap (High Impact, Medium Effort)

**Action:** Cross-reference TRT revert history against the 77 rejected payloads with no high-confidence candidates. For each revert that TRT performed independently, determine whether the agent could have detected it.

**Why first:** We don't know the actual miss rate. If the agent is missing 50% of reverts, that's a fundamentally different problem than if 90% of rejections are genuinely infrastructure. This determines whether we should invest in sensitivity (more detections) or specificity (fewer false positives) or infrastructure automation (force-accepts).

**Expected impact:** Informs all subsequent priorities. No direct payload impact, but prevents investing in the wrong improvements.

### P2: Sub-Component Awareness + Test-Introduction Signal (High Impact, Medium Effort)

**Action:** Implement recommendations 3.2 and 3.6. Modify the component exclusivity scoring to use sub-component resolution for large repos, and add the "new test introduction" signal (+40).

**Why:** Directly fixes the persistent case 008 weakness. The hypershift repo is one of the highest-regression-frequency repos (2 of 10 confirmed TPs), and multi-PR repos are where the current rubric fails most visibly. The test-introduction signal applies broadly — CVO #1309, hypershift #7790, NTO #1499 all introduced or modified tests that immediately failed.

**Expected impact:** Converts case 008 from 3/5 to 5/5 on analysis quality. Improves detection of regressions in monorepo-structured projects. Estimated 2-3 additional true detections per month.

### P3: Cross-Run State (High Impact, Low Effort)

**Action:** Implement recommendation 3.3. Add `--previous-results` flag and persistence confidence bonus.

**Why:** Multi-payload persistence was a 100% TP signal. CCO #978 persisted across 4 payloads before being reverted — if the agent had boosted confidence on run 2, the revert could have happened a day earlier, saving 2-3 payload rejections.

**Expected impact:** Reduces time-to-revert for persistent regressions by 1 payload cycle (~6-12 hours). Prevents 2-4 additional rejections per month from sustained regressions.

### P4: Cloud Platform Issue Detection (Medium Impact, Medium Effort)

**Action:** Implement recommendation 3.4. Add negative evidence scoring for platform-specific failures without mechanism evidence.

**Why:** 3 of 5 false positives (60%) involved platform-side issues. Reducing the false positive rate from 33% to ~15% significantly increases trust in revert recommendations, making humans more likely to act on them quickly.

**Expected impact:** Eliminates ~2 false positives per month. Indirect payload improvement through faster human response to true positive recommendations.

### P5: Progressive Discovery (Medium Impact, High Effort)

**Action:** Implement recommendation 3.1. Two-phase artifact investigation.

**Why:** Reduces cost per analysis from $6-9 to an estimated $3-5, and reduces wall-clock time from 500-1100s to an estimated 300-600s. Faster analysis means faster revert recommendations, which means fewer payloads rejected before the revert lands.

**Expected impact:** 30-50% cost reduction per run. 20-40% wall-clock reduction. Enables running the agent on more payloads or with more parallelism within CI budget constraints.

### P6: Expand Eval Suite with FP Cases (Medium Impact, Low Effort)

**Action:** Implement eval improvements from Section 4.2. Add cases NEW-C, NEW-D, NEW-F (false positive guards) before running `/eval-optimize`.

**Why:** Without false positive regression tests, any `/eval-optimize` run risks increasing sensitivity at the cost of more false positives — which would erode trust and slow human response to recommendations.

**Expected impact:** Prevents FP regression during optimization. No direct payload impact, but protects P4's gains.

### P7: Force-Accept Automation (Medium Impact, Low Effort)

**Action:** Review the `force_accept_recommended` logic. When all failures are infrastructure and no payload has been accepted for 18+ hours, the recommendation should trigger an automated or semi-automated workflow (e.g., post to Slack channel with force-accept recommendation and one-click approval).

**Why:** Infrastructure-only rejections waste CI cycles and delay the release stream. These are payloads the agent already correctly identifies as having no code regressions — the bottleneck is that the recommendation isn't acted upon fast enough.

**Expected impact:** Recovers 5-10% of rejected payloads that are purely infrastructure-related. Reduces "no accepted payload" drought periods.

### P8: Format Standardization (Low Impact, Low Effort)

**Action:** Implement recommendation 3.5. Enforce schema, remove unused fields, standardize output format.

**Why:** Prerequisite for all automated downstream consumption. The varying format makes automated analysis fragile and makes eval harder to write.

**Expected impact:** No direct payload impact. Enables better tooling and faster iteration on other improvements.

---

## Summary of Expected Cumulative Impact

If P1 confirms that the agent is missing a significant number of regressions (as suspected given the 2.5% detection rate on rejected payloads), and P2-P4 are implemented:

- **True positive detection rate**: From 2.5% to an estimated 10-15% of rejected payloads (4-6x improvement)
- **False positive rate**: From 33% to an estimated 15% (2x improvement)
- **Time-to-revert for detected regressions**: From ~1 day to ~0.5 day (saving 1-2 payload cycles)
- **Payload rejection rate**: From 23.9% to an estimated 18-20% (driven by faster reverts and force-accept automation)

The 18-20% estimate is conservative. The floor is set by genuinely flaky tests and infrastructure issues that no agent improvement can address — those require CI infrastructure investment. The agent's maximum achievable impact is preventing code regressions from persisting across multiple payloads, which the data suggests accounts for roughly 20-25% of all rejections.
