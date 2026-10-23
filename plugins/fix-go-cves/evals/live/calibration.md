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
