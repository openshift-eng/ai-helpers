# Native coverage and executed-builder controls

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
