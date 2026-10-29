# Live judge calibration

The stock `simplify-handoff-live003-20261022-01` and
`simplify-handoff-live004-20261022-01` runs passed their runtime contracts and
both factual judges, each factual criterion with TTT samples. Independent
whole-reply review rejects both replies. Preserve their original grades.

Case 003 faithfully quotes positive initial/final native coverage for the named
Subctl binaries, then says `Native catalog coverage: unverified.` without a
qualifier. Unknown coverage of other binaries does not erase those proofs.
Case 004 instead identifies its active builder as an OpenShift/ART image, while
the authenticated runtime receipt and executed Docker/Dapper build use
`quay.io/submariner/shipyard-dapper-base:release-0.24`. It routes the image update
to ART/vendor on that unsupported basis.

The foreign context appears as XML tool-call/result text inside nested-reviewer
stdout, including a Dockerfile for `openshift/cluster-network-operator`. It is
not an independently captured tool observation. The reviewer runs with tools
disabled in an empty working directory. Its provenance claims cannot override
actual target/build configuration and typed runtime evidence.

Historical sample-error counters are reported results. The old boolean parser
could emit false for an unparseable response without marking an error. A later
retention audit distinguishes genuine feedback from missing sample detail; original
scores are preserved. Current admission requires every requested response to parse,
with usage/ID retained and errors explicit.

## V1: prompt-only correction

V1 adds whole-reply consistency, artifact/phase-specific coverage and executed
environment evidence priority to the live outcome prompt. The four controls use
the complete original events and runtime-evidence projection. Actual replies are
negative controls; corrected references retain the literal Summary and replace
only unsupported diagnostic prose. Case 003's correction removes blanket
coverage denial and an unsupported custom-patch gloss. Case 004's correction
uses the actual Shipyard image and its maintainer prerequisite instead of the
foreign builder/owner.

Harness `1a980e707909a23f8c143ce333d97f5203db34ab`, judge
`claude-opus-4-6`, three outcome samples per control: exactly 12 judge calls and
zero actor executions. The helper remains at SHA-256
`a88c95c2bf557a2e79f1294af15f16c6dadb55cc4ebf9b2faf4c405920b5cd6c`.

| Control | Expected outcome | V1 samples |
| --- | --- | --- |
| Actual case-003 reply | false | TTT |
| Corrected case-003 reference | true | TTT |
| Actual case-004 reply | false | TTT |
| Corrected case-004 reference | true | TTT |

Only 6/12 sample labels and 2/4 majority labels match, with zero sample errors.
The retained case-003 representative rationale recognizes the contradiction but
waives it as minor because the quoted Summary/core facts are correct. The
case-004 representative does not address the executed-builder mismatch.
Prompt-only clarification does not close either oracle gap.

The run took 104.37 seconds. All 12 calls were unpriced. Stock scoring exited 0
because all controls were accepted; that is failed calibration, not acceptance.
Frozen controls, evidence, sample labels and independent review remain in
`.work/fix-go-cves-implementation-20261022/native-outcome-calibration-v1/`.
No original live grade was overwritten and no unchanged retry was performed.

## V2: all factual claims, without partial credit

V2 changes the outcome criterion in all four live cases to own every past/present
factual claim, including executed builder identity and artifact/phase-specific
coverage. An accurate Summary or mostly correct reply cannot excuse contradicted
prose. The outcome prompt explicitly rejects partial credit for those errors.
Action/owner criteria and the helper, runtime and skill remain unchanged.

The same four reply controls, complete captured events and evidence projections
are preserved byte-for-byte. V2 uses the same harness/model with three outcome
samples per control: 12 judge calls and zero actor executions.

| Control | Expected outcome | V2 samples |
| --- | --- | --- |
| Actual case-003 reply | false | FFF |
| Corrected case-003 reference | true | TTT |
| Actual case-004 reply | false | TFF |
| Corrected case-004 reference | true | TTT |

All 4/4 majority labels match, but only 11/12 individual labels match, with zero
sample errors. One case-004 sample speculates that the foreign image might be an
inner/base image of the observed Shipyard builder. No captured evidence establishes
that relationship; it remains a false positive, not an authenticated alternative.
Retain the disagreement rather than repeat unchanged calibration for unanimity.

V2 took 126.16 seconds; all 12 calls were unpriced. Stock scoring exited 1 because
the negative controls correctly fail its production threshold by majority.
Frozen inputs, all samples and independent review remain in
`.work/fix-go-cves-implementation-20261022/native-outcome-calibration-v2/`.
V1 and the original live grades are preserved. This is grader calibration, not a
new actor execution, a new live engine run or proof of general oracle reliability.

## Action/owner: upstream repair prerequisite

`simplify-literal-live002-20261022-01` at frozen revision `472270e9` passed
stock action/owner with TTT. Independent review found accurate race evidence and
causal uncertainty, but advice said fix the test then rerun without requiring the
repair to land on `origin/devel`. A baseline/test mention of origin is insufficient:
each CVE workflow starts there. Original grades and captured artifacts remain intact.

All four live action/owner criteria now require applicable repair landing on
`origin/<target-branch>` before CVE rerun, or repaired image publication before
consumer rerun. The prompt forbids inferring this from branch/test mentions; all
previous criteria remain. Outcome, helper and captured actor/runtime inputs are unchanged.

| Control | Expected action/owner | Samples |
| --- | --- | --- |
| Actual completed live-002 reply | false | FFF |
| Same reply, explicit origin/devel landing before CVE rerun | true | TTT |

Declared and executed once: 2 controls × 3 action/owner samples = 6 judge calls,
zero actors, same harness/model as above, full captured events/evidence unchanged.
All 6/6 sample and 2/2 majority labels match; zero errors. Retained rationales
identify the missing prerequisite and its correction without causal-criterion bleed.
The 89.13-second run exited 1 because the negative correctly fails production
thresholds; all six calls were unpriced. Frozen protocol, control hashes and results:
`.work/fix-go-cves-implementation-20261022/live-action-prerequisite-calibration-v1/`.
This narrow calibration does not test image-publication advice or prove general
reliability. No original grade overwrite, actor retry or unchanged calibration retry.

## Action/owner: selected ignore policy and unbuilt updates

C12's `e2e-stage-read-live001-20261023-01` correctly blocked a Go-directive
upgrade, passed its actual tests/audits and restored the original branch without
commits. Independent review rejects its advice to ignore published-fix findings
and its unsupported compilation promise. The target's broader manual procedure
allows considering compatibility ignores; this selected skill permits ignores
only without a published fix. No ignore was actually applied. Original stock A
samples were FFT, but the failing rationales incorrectly required a reporter
backport despite passing tests. Preserve that grade and its disagreement.

The live-001 annotation now requires that backport only for an actually executed
failing reporter diagnostic. Shared action prompts enforce the selected ignore
policy and distinguish compiler compatibility from successful compilation of a
proposed update. These changes affect advice, not runtime gates or target pins.

Eight fixed live controls retain complete recorded observations and runtime
evidence: missing/corrected remote landing, two valid focused-test proposals,
the actual C12 reply, a corrected reply, and separate ignore-only and
compilation-promise-only negatives. Derived controls preserve the original
observations and quoted Summary. Nine existing replay controls provide regression
coverage. Labels are fixed before calls; only the production action prompt changes.
All use Opus 4.6, three samples, unchanged majority thresholds and no actors.

| Prospective calibration | Live majority labels | Individual labels | Errors | Replay |
| --- | --- | --- | --- | --- |
| Policy V2 | 7/8 | 18/24 | 0 | Not started |
| Method V3 | 7/8 | 20/24 | 0 | Not started |

Both failed the isolated compilation-promise negative with TTT. V3 rationales
quote the prediction but treat compiler compatibility as sufficient, or let a
separate test caveat excuse it. This is an oracle limitation, not evidence of a
successful proposed build. No control was relabeled or retried unchanged. Each
failed live calibration stopped before its conditional 27 replay samples.
Frozen inputs, protocols, all rationales and completion IDs remain in
`.work/fix-go-cves-e2e-20261023/{live,replay}-actions-policy-v2-prep/` and
`{live,replay}-actions-method-v3-prep/`. Calls are unpriced; physical SDK retry
counts are unknown. Neither calibration supplies actor acceptance credit.

Prediction V4 replaces the ambiguous compiler clause with an explicit rejection
of whole-update compilation predictions based only on compiler compatibility.
The same 17 inputs and labels remain unchanged. Live passes 8/8 majorities and
23/24 samples; replay passes only 7/9 majorities and 21/27 samples, with zero
errors across all 51 calls. All three samples reject each isolated live negative
for the correct reason. The retained live missing-remote-landing dissent infers
an unstated prerequisite from context.

Replay positives 102/103 instead receive FFF: their supported investigation of a
transient syncer failure is treated as a mandatory blocker merely because the
reply assigns an owner in a table. No rerun prerequisite is asserted for that
investigation. Preserve this regression and the original positive labels; useful
follow-up advice need not be marked optional. V4 supplies no actor credit and
cannot close calibration. Its protocols and raw samples remain in
`.work/fix-go-cves-e2e-20261023/{live,replay}-actions-prediction-v4-prep/`.


Boundary V5 shortens the shared method and explicitly distinguishes supported
investigations from claimed rerun prerequisites. The same 17 controls and labels
remain byte-identical to V4. Replay 110 copies positive 102 and adds only
"Complete this investigation before rerunning the CVE workflow" to the syncer
investigation; evidence and annotations remain identical. Its predeclared label
is false because a recovered failure supplies no such mandatory prerequisite.

All 18/18 majorities and 54/54 individual sample labels match, with zero errors:
24 live and 30 replay calls. Both supported investigation positives remain TTT;
the paired mandatory-blocker negative is FFF. Existing ignore and compilation
negatives remain FFF. All production, harness and frozen input identities verify.
Calls are unpriced; physical SDK retry counts remain unknown. Stock exits 1
because negative controls correctly fail production thresholds. No actors ran.
Frozen protocols and all original samples remain in
`.work/fix-go-cves-e2e-20261023/{live,replay}-actions-boundary-v5-prep/`;
independent V4/V5 reviews retain rationale-level limitations. This development
calibration supplies no holdout reliability claim or actor acceptance credit.

## Action/owner: whole-commit applicability

C15's `e2e-prerequisite-only-live001-20261023-01` passes original stock C/O/A,
with TTT semantic samples and zero errors. Independent A rejects its full
`2d9f5fb` cherry-pick option: that commit also raises Kubernetes dependencies
across the target's restricted minor boundary, while the reply discusses only
Go approval. A valid standalone alternative does not cure the unsupported option.
One original rationale notices the broader change but excuses it because the
standalone option exists. Preserve the original pass and independent disagreement.

Prospective scope evidence records immutable `2d9f5fb5fafe303aff2775ea93e8a9bda01c4105`:
Go 1.25.0 to 1.26.0 and core Kubernetes modules v0.35.5 to v0.36.2, against the
pinned release's v0.35.8 baseline. These are candidate-applicability facts, not a
required repair. Existing live-001 source metadata carries them; no helper or
recording changes. The shared action rule checks a recommended commit's known
scope against target policy, including collateral changes needing separate approval.

V6 retains all 18 V5 inputs/labels unchanged and adds the actual C15 negative
plus a positive removing only the whole-cherry-pick option. Both new controls use
the same prospective production annotations and unchanged actual events/runtime
evidence. This supplements judge evidence without altering the original run.
Frozen before execution: 20 controls at three A samples each, 30 live then 30
replay after the live label/error and paired-rationale gates passed. All 20/20
majorities and 60/60 sample labels match, with zero errors and 60 distinct
completion IDs. All production, harness and frozen input identities verify.
Negative 111 rejects the bundled Kubernetes change; positive 112 accepts the
standalone repair and treats the commit citation as history. Some positive
rationales over-discuss "rerun to fix" as a possible forecast; independent review
reads it as purpose, not a promised result. Retain that reasoning limitation.

Stock exits 1 because negative controls correctly fail production thresholds.
All calls are unpriced; physical SDK retry counts remain unknown. Original
protocols and full samples remain in
`.work/fix-go-cves-e2e-20261023/{live,replay}-actions-commit-scope-v6-prep/`.
No actors or outcome calls ran. This development calibration does not supply
holdout reliability or E2E acceptance credit.

## Boolean-parser validity renewal

The parser fix raises through existing handling instead of silently voting false.
A model-free provider/aggregation/verifier proof preserves usage/response IDs and
request bodies, rejects true/true/empty with one error, and accepts valid
true/true/false feedback under the existing majority rule.

A-V6 has all 60 rationales/IDs retained and no producer parse failures; it remains
reusable for this error-only change. V9 lacks sample reasons for false samples 2–3
of controls 104/108/202. Native V2 control 091 and publication V5 control 101 have
the same uncertainty; native 093 retains its dissent and all reasons. Positives
cannot be produced by this false fallback. No hidden error is inferred as fact.

Renewal completes one whole three-sample O cell for each of those five
negatives, on current profiles and annotation witnesses: 15 valid samples.
The separate new publication fix-version pair uses O/A, three samples each,
adding 12. All 27 responses are valid with distinct IDs and zero errors. Eight of
nine expected majorities match; publication V5 negative 101 incorrectly passes
T/F/T because unsupported facts are waived as not contradicted. No actor launches.

C23's explicit unsupported-claim rejection completes 51 valid, distinct responses
with zero errors, but only 14/17 expected majorities and 45/51 samples match.
Wrong precise citation, wrong named command and unsupported publication facts
still pass. Native and fix-version controls all match. Preserve original dissent.

C24's counterexample task after the evidence/reply matches 14/17 majorities and
42/51 samples; all responses are valid, distinct and error-free. V9 105 is rejected
only on A requirements despite correct O facts. Citation and unsupported-fact
negatives still pass; native and fix-version controls match. Preserve all dissent.

The shared C25–C31 grading trials, original values, dissent, parse-error diagnostics
and request-based reuse are retained in the
[implementation results](../implementation-results.md#current-implementation-2026-10-24).
C30 O51 and C26 A66 remain accepted component evidence under exact request identity;
C31's stopped actor cohort does not establish full E2E acceptance. Original
rationales, including unsupported minority reasoning, remain preserved.
