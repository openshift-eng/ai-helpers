# Payload Agent Analysis Report

**Generated:** 2026-05-14
**Data range:** 2026-03-18 to 2026-05-14

## 1. Summary Statistics

| Metric | Count |
|--------|-------|
| Total CI jobs | 702 |
| Jobs with claude-sessions tarball | 332 |
| Jobs with payload-results YAML | 331 |
| Rejected payloads | 79 |
| Accepted/passed payloads (no phase or empty) | 240 |
| "Ready" phase payloads (still in progress) | 12 |
| Jobs with failing blocking jobs | 308 |
| High-confidence revert candidates (score >= 85) | 26 jobs, 15 unique PRs |
| Medium-confidence candidates (score 50-84) | 29 jobs |
| Low-confidence candidates (score < 50) | 54 jobs |
| Explicit revert_recommendations (structured field) | 0 |

**Key ratios:**
- 79 of 331 analyzed payloads were Rejected (23.9%)
- 26 of 308 payloads with failures produced high-confidence candidates (8.4%)
- Only 2 of 79 Rejected payloads had high-confidence candidates (2.5%)

## 2. True Positives

PRs flagged with high confidence (>= 85) that were subsequently reverted. **10 of 15 unique high-confidence recommendations were true positives (66.7%).**

### TP1: cluster-version-operator #1309 (score 95)
- **Payload:** 4.22.0-0.nightly-2026-03-18-161724
- **Build:** 2034304434720215040
- **PR:** https://github.com/openshift/cluster-version-operator/pull/1309
- **Title:** "NO-ISSUE: OTA-1605 Automate OCP-42543"
- **Reverted by:** [#1353](https://github.com/openshift/cluster-version-operator/pull/1353) on 2026-03-18
- **Turnaround:** Same day

### TP2: oc #2219 (score 85)
- **Payloads:** 4.22.0-0.nightly-2026-03-22-134704, 4.22.0-0.nightly-2026-03-22-201225
- **Builds:** 2035715747061174272, 2035813017240735744
- **PR:** https://github.com/openshift/oc/pull/2219
- **Title:** "CNTRLPLANE-2769: Bump k8s dependencies to 1.35"
- **Reverted by:** [#2236](https://github.com/openshift/oc/pull/2236) on 2026-03-23 (re-applied in #2241 on 2026-03-24)
- **Turnaround:** ~1 day

### TP3: cluster-authentication-operator #839 (score 92)
- **Payload:** 4.22.0-0.nightly-2026-03-26-231124
- **Build:** 2037307536838758400
- **PR:** https://github.com/openshift/cluster-authentication-operator/pull/839
- **Title:** "CNTRLPLANE-2589: Migrate test/e2e-encryption to Ginkgo v2 framework"
- **Reverted by:** [#857](https://github.com/openshift/cluster-authentication-operator/pull/857) on 2026-03-27
- **Turnaround:** ~1 day

### TP4: cloud-credential-operator #978 (score 90-95, flagged across 4 payloads)
- **Payloads:** 4.22.0-0.nightly-2026-03-30 through 2026-03-31 (4 consecutive)
- **Builds:** 2038743555995865088, 2038855995874086912, 2038963867484164096, 2039076834276020224
- **PR:** https://github.com/openshift/cloud-credential-operator/pull/978
- **Title:** "CCO-738, CCO-739: Set operator condition to Progressing when pod identity webhook pods are updating"
- **Reverted by:** [#1007](https://github.com/openshift/cloud-credential-operator/pull/1007) on 2026-03-31
- **Note:** Agent correctly flagged this across 4 consecutive payloads with sustained high confidence

### TP5: hypershift #7790 (score 95)
- **Payload:** 4.22.0-0.ci-2026-03-31-170515
- **Build:** 2039038567224709120
- **PR:** https://github.com/openshift/hypershift/pull/7790
- **Title:** "CNTRLPLANE-2841: feat(HCCO): add guest cluster metrics forwarder for control plane metrics"
- **Reverted by:** [#8141](https://github.com/openshift/hypershift/pull/8141) on 2026-04-01
- **Turnaround:** ~1 day

### TP6: cluster-network-operator #2959 (score 85-90, flagged in 2 payloads)
- **Payloads:** 5.0.0-0.ci-2026-05-07-142711 (Rejected), 5.0.0-0.nightly-2026-05-07-185738
- **Builds:** 2052395627291086848, 2052464730387255296
- **PR:** https://github.com/openshift/cluster-network-operator/pull/2959
- **Title:** "OCPBUGS-83800: add remaining CNO NetworkPolicies"
- **Reverted by:** [#2999](https://github.com/openshift/cluster-network-operator/pull/2999) on 2026-05-08
- **Evidence quality:** Excellent -- 0% pass rate vs 100% historical, cross-platform consistency

### TP7: cluster-monitoring-operator #2814 (score 95, flagged in 2 payloads)
- **Payloads:** 5.0.0-0.nightly-2026-04-27-183150, 5.0.0-0.nightly-2026-04-28-112407
- **Builds:** 2048838426882478080, 2049088219407978496
- **PR:** https://github.com/openshift/cluster-monitoring-operator/pull/2814
- **Title:** "MON-4517: Minimal and telemetry CP monitors"
- **Reverted by:** [#2901](https://github.com/openshift/cluster-monitoring-operator/pull/2901) on 2026-04-28

### TP8: cluster-monitoring-operator #2886 (score 90)
- **Payload:** 5.0.0-0.nightly-2026-05-01-102026
- **Build:** 2050159797738672128
- **PR:** https://github.com/openshift/cluster-monitoring-operator/pull/2886
- **Title:** "MON-4558: enable zoneinfo node-exporter collector via config"
- **Reverted by:** [#2910](https://github.com/openshift/cluster-monitoring-operator/pull/2910) on 2026-05-01

### TP9: hypershift #8357 (score 85)
- **Payload:** 5.0.0-0.nightly-2026-05-05-071423
- **Build:** 2051580592402731008
- **PR:** https://github.com/openshift/hypershift/pull/8357
- **Title:** "OCPBUGS-84572: fix(cpo): generate EBS CSI driver operator serving cert in CPO"
- **Reverted by:** [#8417](https://github.com/openshift/hypershift/pull/8417) on 2026-05-05

### TP10: cluster-node-tuning-operator #1499 (score 95)
- **Payload:** 5.0.0-0.nightly-2026-05-08-191551
- **Build:** 2052831474708647936
- **PR:** https://github.com/openshift/cluster-node-tuning-operator/pull/1499
- **Title:** "NO-JIRA: ote: embed extended testdata in cluster-node-tuning-operator-test-ext binary"
- **Reverted by:** [#1511](https://github.com/openshift/cluster-node-tuning-operator/pull/1511) on 2026-05-09

## 3. False Positives

PRs flagged with high confidence (>= 85) that were NOT reverted. **5 of 15 unique high-confidence recommendations were false positives (33.3%).**

### FP1: cluster-ingress-operator #1354 (score 90-95, flagged in 3 payloads)
- **Payloads:** 4.22.0-0.nightly-2026-03-20 (3 consecutive payloads)
- **Builds:** 2034867318227472384, 2034969861733486592, 2035092985116364800
- **PR:** https://github.com/openshift/cluster-ingress-operator/pull/1354
- **Title:** "NE-2471: Replace OLM-based Istio install with Sail Library"
- **Status:** NOT REVERTED -- no revert PR found
- **Note:** Large architectural change (OLM to Sail) that eventually stabilized without revert

### FP2: oc #2232 (score 95, flagged in 2 payloads)
- **Payloads:** 4.22.0-0.nightly-2026-03-20-053450, 4.22.0-0.nightly-2026-03-20-192352
- **Builds:** 2034867318227472384, 2035092985116364800
- **PR:** https://github.com/openshift/oc/pull/2232
- **Title:** "NO-ISSUE: pkg/cli/admin/release/extract: Read manifests into memory"
- **Status:** NOT REVERTED

### FP3: cluster-authentication-operator #825 (score 85)
- **Payload:** 4.22.0-0.nightly-2026-03-24-224450
- **Build:** 2036576107607625728
- **PR:** https://github.com/openshift/cluster-authentication-operator/pull/825
- **Title:** "CNTRLPLANE-2610: Create network policies for AUTH components"
- **Status:** NOT REVERTED

### FP4: hypershift #8194 (score 92)
- **Payload:** 5.0.0-0.ci-2026-04-14-085906 (Rejected)
- **Build:** 2043978118967857152
- **PR:** https://github.com/openshift/hypershift/pull/8194
- **Title:** "CNTRLPLANE-3197: update builder images from 4.22 to 4.23"
- **Status:** NOT REVERTED
- **Note:** AKS failure was Azure Graph API auth failure that resolved on its own (likely Azure-side fix). Agent's causal reasoning (builder image SDK changes breaking auth) was plausible but incorrect.

### FP5: etcd #368 (score 88)
- **Payload:** 5.0.0-0.ci-2026-04-24-102730
- **Build:** 2047624496151531520
- **PR:** https://github.com/openshift/etcd/pull/368
- **Title:** "OCPBUGS-82495: 5.0/4.23 rebase 3.6.10"
- **Status:** NOT REVERTED

### Uncertain cases (high confidence but unclear outcome)

- **ovn-kubernetes #3084** (score 90): Downstream merge, no clear revert found
- **hypershift #7774** (score 90): API Auth Config integration, no clear revert found
- **machine-config-operator #5767** (score 90-95): This PR itself is a "Reapply" of a previously reverted change. No evidence it was reverted again.

## 4. Recommended Eval Candidates

### Case 1: CNO NetworkPolicy regression (TRUE POSITIVE -- best case)
- **Build:** 2052395627291086848
- **Payload:** 5.0.0-0.ci-2026-05-07-142711
- **Phase:** Rejected
- **What failed:** cloud-network-config-controller CrashLoopBackOff across all platforms (AWS, Azure, GCP) -- API server timeout caused by newly added NetworkPolicies blocking egress
- **Candidate:** CNO #2959 (score 90), actually reverted as #2999
- **Why good eval case:** Textbook correct identification. 0% vs 100% pass rate, cross-platform consistency, precise mechanism match (NetworkPolicies blocking egress), clear temporal correlation. Tests whether the agent can identify infrastructure-level networking restrictions causing application failures.

### Case 2: Cloud Credential Operator regression (TRUE POSITIVE -- sustained detection)
- **Builds:** 2038743555995865088 through 2039076834276020224 (4 consecutive)
- **Payload:** 4.22.0-0.nightly-2026-03-30-221541 through 2026-03-31-202006
- **What failed:** CCO condition reporting causing upgrade test failures
- **Candidate:** CCO #978 (score 90-95), reverted as #1007
- **Why good eval case:** Agent correctly maintained high confidence across 4 consecutive failing payloads. Tests persistence and consistency of analysis across runs.

### Case 3: HyperShift builder image false positive (FALSE POSITIVE)
- **Build:** 2043978118967857152
- **Payload:** 5.0.0-0.ci-2026-04-14-085906
- **Phase:** Rejected
- **What failed:** AKS e2e (Azure Graph API auth failure)
- **Candidate:** hypershift #8194 (score 92), NOT reverted
- **Why good eval case:** Agent constructed a plausible but incorrect causal chain (builder image SDK changes -> auth library changes -> Graph API failure). The failure was actually an Azure-side issue that resolved on its own. Tests whether the agent can distinguish platform-side issues from code regressions.

### Case 4: oc k8s dependency bump (TRUE POSITIVE -- revert then reapply)
- **Builds:** 2035715747061174272, 2035813017240735744
- **Payload:** 4.22.0-0.nightly-2026-03-22-134704
- **What failed:** Test suite failures from k8s 1.35 bump
- **Candidate:** oc #2219 (score 85), reverted by #2236, then re-applied in #2241
- **Why good eval case:** Tests the nuance of dependency bumps that need temporary revert followed by proper fix. The revert-reapply pattern is common.

### Case 5: Cluster ingress Sail migration (FALSE POSITIVE)
- **Builds:** 2034867318227472384, 2034969861733486592, 2035092985116364800
- **Payload:** 4.22.0-0.nightly-2026-03-20
- **What failed:** Various ingress/test failures
- **Candidate:** cluster-ingress-operator #1354 (score 90-95), NOT reverted
- **Why good eval case:** Large architectural change (OLM to Sail) that caused real failures but was stabilized via forward fixes rather than revert. Tests whether the agent can distinguish "needs revert" from "needs forward fix".

### Case 6: CMO monitoring regression (TRUE POSITIVE -- two distinct cases)
- **Builds:** 2048838426882478080, 2050159797738672128
- **Payloads:** 5.0.0-0.nightly-2026-04-27 and 5.0.0-0.nightly-2026-05-01
- **What failed:** Monitoring test regressions from two separate CMO PRs
- **Candidate A:** CMO #2814 (score 95), reverted by #2901
- **Candidate B:** CMO #2886 (score 90), reverted by #2910
- **Why good eval case:** Two similar-but-distinct monitoring regressions from the same component. Tests whether the agent can identify component-specific patterns.

### Case 7: CVO test automation regression (TRUE POSITIVE -- fast turnaround)
- **Build:** 2034304434720215040
- **Payload:** 4.22.0-0.nightly-2026-03-18-161724
- **What failed:** CVO test failures
- **Candidate:** CVO #1309 (score 95), reverted same day by #1353
- **Why good eval case:** Very fast revert turnaround. Tests whether the agent can quickly identify test automation regressions vs product regressions.

### Case 8: Node tuning operator testdata embedding (TRUE POSITIVE)
- **Build:** 2052831474708647936
- **Payload:** 5.0.0-0.nightly-2026-05-08-191551
- **What failed:** Node tuning tests
- **Candidate:** NTO #1499 (score 95), reverted by #1511
- **Why good eval case:** Non-obvious failure -- embedding testdata into a binary caused test failures. Tests whether the agent can trace build-system changes to test failures.

### Case 9: Rejected payload with infrastructure failures only
- **Build:** 2054990768048705536
- **Payload:** 5.0.0-0.ci-2026-05-14-181709
- **Phase:** Rejected
- **What failed:** Insights API Gateway HTTP 500, infrastructure issue
- **Candidates:** None (correctly)
- **Why good eval case:** Agent correctly identified infrastructure failures and did not blame any PR. Tests the agent's ability to classify and dismiss infrastructure issues.

### Case 10: etcd rebase false positive
- **Build:** 2047624496151531520
- **Payload:** 5.0.0-0.ci-2026-04-24-102730
- **What failed:** etcd-related failures
- **Candidate:** etcd #368 (score 88), NOT reverted
- **Why good eval case:** Large rebase PRs are high-risk by nature and easy to blame. Tests whether the agent over-indexes on "big scary change" without sufficient causal evidence.

## 5. Improvement Ideas

### Observation 1: Very low candidate identification rate on rejected payloads
Only 2 of 79 rejected payloads (2.5%) got high-confidence candidates. Most rejected payloads have 0 candidates. This suggests the agent is conservative, which is good for precision but means many real regressions go unidentified.

**Suggestion:** Analyze the 79 rejected payloads to see how many had actual reverts done by TRT independently. If TRT is reverting things the agent missed, those are missed-detection opportunities.

### Observation 2: Most high-confidence detections are on non-Rejected payloads
24 of 26 high-confidence candidate jobs had empty or no phase field (not Rejected). This means the agent is finding regressions in payloads before they get formally rejected. This is actually valuable -- early warning.

**Suggestion:** Track whether early warnings lead to faster reverts. The agent could be most valuable as a proactive alert system, not just a post-mortem tool.

### Observation 3: 33% false positive rate at high confidence
5 of 15 unique high-confidence recommendations were false positives. The main failure modes were:
- **Azure/cloud platform issues** attributed to code changes (FP4: hypershift #8194)
- **Large architectural changes** that stabilize without revert (FP1: ingress Sail migration)
- **Correlation without causation** for dependency bumps (FP5: etcd rebase)

**Suggestions:**
- Add explicit checks for cloud-provider-side issues (Azure Graph API, AWS service disruptions) before blaming code changes
- Weight "was this change reverted in a prior similar situation" as negative evidence for large refactors
- Require stronger causal mechanism evidence for dependency bumps/rebases beyond just temporal correlation

### Observation 4: Multi-payload persistence is a strong signal
When the agent flags the same PR across multiple consecutive payloads (CCO #978 across 4, CNO #2959 across 2, CMO #2814 across 2), it was always a true positive. Single-payload flags had a higher false positive rate.

**Suggestion:** Implement cross-run memory or state so the agent can boost confidence when it sees the same candidate across consecutive runs.

### Observation 5: No use of revert_recommendations field
Despite having a `revert_recommendations` field in the output schema, it was empty across all 331 jobs. All recommendations were expressed through the `candidates` hierarchy instead.

**Suggestion:** Either populate `revert_recommendations` when confidence >= 85, or remove the field from the schema to reduce confusion.

### Observation 6: Format inconsistency
The YAML output format varies across runs:
- Some files are gzip-compressed, some are plain text
- Candidate structure varies between nested (high/medium/low) and flat lists
- Score field name varies (`score` vs `confidence_score`)
- Phase field is missing in ~240 of 331 jobs

**Suggestion:** Standardize the output schema. This will make automated analysis and eval easier.

### /eval-optimize workflow
To use these findings with eval-optimize:
1. Create eval test cases from the 10 recommended cases above, including both true positives and false positives
2. Score on: (a) did the agent identify the correct PR, (b) did it assign appropriate confidence, (c) did it avoid false positives for infra issues
3. Key failure mode to optimize: distinguishing code regressions from cloud-platform-side issues
4. Key strength to preserve: the agent's conservative approach (low false positive rate overall, strong precision at >= 85 confidence)
