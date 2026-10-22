# Positive publication recording

This historical Submariner release-0.24 recording retains result
`2716c2fffebad84210293229442c4fd9eb582eba`, whose sole parent is the pinned
`e9b4dec4944cbbf8d630603904fb6e0f82a2b566` base. The original ref was `devel`,
pinned at `fb518adb012b060e4e5ec252cc34b92cab99cac1`. Runtime exit 2 records a
partial dependency repair with remaining standard-library findings and a real
positive publication recipe. It does not establish current-engine or independently
authenticated native catalog coverage.

The full raw log SHA-256 was
`6e6d9465372c0c1792aafaec722ba0aca9999ce2670cde70147d9ca174e5070b`.
The packaged log replaces the historical checkout path with `{{REPO}}` and home
prefix with `{{HOME}}`; publication account identifiers become `fork` and
`example`. Command flags and shell escaping remain intact. The plugin archive
and result bundle retain their original bytes. Preparation substitutes today's
skill using the existing replay mechanism; session metadata is not packaged.

The reference preserves the witnessed Summary and recipe, then assigns the build
image patch update to Shipyard maintainers and verification after image publication.
The publication negatives respectively remove the recipe and change only its
`--base release-0.24` argument to `--base devel`. The ownership negative preserves
the recipe but omits the responsible owner and required update-before-rerun advice.

## Judge calibration

V1 and V2 use harness `1a980e707909a23f8c143ce333d97f5203db34ab`, judge
`claude-opus-4-6`, four fixed controls and three samples per criterion: 24 judge
calls and zero actor executions per version. Existing Admiral backport criteria
do not apply to this recording. Expected labels are:

| Control | outcome | action_owner |
| --- | --- | --- |
| Reference | true | true |
| Missing recipe | false | true |
| Invented recipe base | false | false |
| Missing builder owner | true | false |

V1 lacked the authoritative Summary in judge annotations. It accepted the
invented recipe in all six relevant samples; judges treated the reply's own
quoted block as its witness. One outcome sample also imported ownership
requirements into the missing-owner control. Only 17/24 sample labels and 6/8
majority labels matched expectations. Preserve this failed calibration under
`.work/fix-go-cves-implementation-20261022/publication-calibration/`.

V2 supplies the witnessed Summary as `recorded_evidence.summary` and instructs both
judges to compare against it rather than authenticate a reply using its own block.
The four reply bytes and substantive criteria are unchanged. Results are:

| Control | outcome samples | action_owner samples |
| --- | --- | --- |
| Reference | TTT | TTT |
| Missing recipe | FFF | TTT |
| Invented recipe base | FFF | FFF |
| Missing builder owner | TFT | FFF |

All eight majority labels match expectations; 23/24 individual labels match, with
zero sample errors. The remaining false outcome sample explicitly applies the
separate ownership criterion despite the prompt's scope. This is a semantic
grader error, not a new requirement on the outcome criterion. Retain the
disagreement; no unchanged calibration was retried to seek unanimity.

V2 completed in 141.86 seconds. All 24 judge calls were unpriced, so total cost
is unknown. Stock scoring exited 1 because negative controls fail production
thresholds; calibration compares their labels with declared expectations.
Frozen inputs, complete sampled results and the independent label review remain
under `.work/fix-go-cves-implementation-20261022/publication-calibration-v2/`.
Deterministic witness checks and whole-reply review remain necessary. These
controls do not measure invoking-skill relay or accept the skill.

## Logged-check evidence and V3

The `simplify-reference-publication-20261022-01` actor reply falsely claimed that
no checks beyond `make unit` were configured or run. Its original contract and
both factual judges passed, each factual criterion with TTT samples. Independent
whole-reply review rejects that reply: the full historical log records four
verification audits and passing `make licensecheck`. Those facts were absent
from the original judge annotations. Preserve the original grades as evidence
of this oracle gap.

The later `simplify-final-publication-20261022-01` pilot preserves one exact
recipe, explicit native uncertainty and supported image ownership/prerequisites,
without that false check claim. Its original contract and both factual judges
pass with TTT samples, and independent whole-reply review accepts it under its
frozen criteria. This is one accepted positive-relay pilot; blocked-case behavior,
repeatability and current-engine acceptance remain separate requirements.

V3 enriches only `recorded_evidence` with exact historical log observations:
`existing-entries`, `fix-availability`, `scan-regression` and `yaml-integrity`
report PASS with zero issues at lines 13120–13123, followed by `All subagents
passed.` at 13124. The license command appears at 13449 and its passing result
at 13674. These are historical log witnesses, not newly fabricated typed receipts.
The criteria, judge prompts and first four control replies remain unchanged.
The fifth control appends one false sentence to the clean reference:

> No additional checks beyond `make unit` (which passed) were configured or run.

V3 uses the same harness/model and three samples per criterion: exactly 30 judge
calls and zero actor executions. Expected labels for the fifth control are false
for both criteria. Results are:

| Control | outcome samples | action_owner samples |
| --- | --- | --- |
| Reference | TTT | TTT |
| Missing recipe | FFF | TTT |
| Invented recipe base | FFF | FFF |
| Missing builder owner | TTT | FFF |
| False check scope | TTT | FFF |

The outcome criterion still falsely accepts the new contradiction in all three
samples. Its retained representative rationale recognizes the passing audits and
license check, then discounts the false claim as minor while also evaluating
the separate ownership criterion. Evidence enrichment closes the input gap but
does not establish correct outcome grading. The action/owner criterion rejects
that control, so the configured factual conjunction rejects the false reply.

Only 27/30 sample labels and 9/10 majority labels match expectations, with zero
sample errors. All labels are stable within this execution; stability does not
make the erroneous outcome labels correct. The missing-owner outcome control
passes TTT here, but the other scope error means earlier criterion bleed remains
a known limitation. Representative rationale text does not explain every sample
independently.

V3 completed in 146.75 seconds; all 30 calls were unpriced. Stock scoring exited 1
with intentionally failing negative controls. Frozen inputs, all sample labels
and independent review remain in
`.work/fix-go-cves-implementation-20261022/publication-calibration-v3/`.
V1/V2 are preserved. No unchanged calibration was retried and no actor was rerun
for this oracle correction. Further grader changes require a separately declared
calibration; do not describe this version as passing every control.

## V4: distinct factual and advice responsibilities

V4 changes the publication-specific criterion ownership rather than repeating the
V3 measurement. `outcome` owns the accuracy of every past/present factual claim
throughout the reply, including extra claims about checks, scan scope and the
literal Summary/recipe. `action_owner` owns supported future actions, owners,
prerequisites and publication procedures, without the former broad historical
factual-claim catchall. This does not require enumerating every observed check;
it rejects claims that contradict those observations.

The same five reply controls are preserved byte-for-byte. The false-check
control's expected `action_owner` label changes to true because its proposed
future actions are correct; `outcome` must reject its false historical claim.
The wrong-base command still fails both criteria: it misstates the witnessed
recipe and supplies a future publication procedure with the wrong target. Each
known negative therefore retains conjunctive rejection. The evidence also gains
the reference's true original ref, `devel`, matched to `input.yaml` and the
prepared initial checkout. Earlier criteria, labels and grades remain preserved.

V4 uses the same harness/model and three samples per criterion, with exactly
30 judge calls and zero actor executions. All declared labels match:

| Control | outcome samples | action_owner samples |
| --- | --- | --- |
| Reference | TTT | TTT |
| Missing recipe | FFF | TTT |
| Invented recipe base | FFF | FFF |
| Missing builder owner | TTT | FFF |
| False check scope | FFF | TTT |

All 30/30 sample labels and 10/10 majority labels match, with zero sample errors.
The retained representative explanations apply the intended ownership on the
false-check and missing-owner controls and reject the wrong-base procedure.
This is one successful control calibration, not proof that all possible errors
or future criterion bleed are detected.

The run completed in 126.41 seconds. All 30 calls were unpriced. Stock scoring
exited 1 because negative controls fail production thresholds; their declared
calibration labels are correct. Frozen inputs, all sample labels and independent
review are under
`.work/fix-go-cves-implementation-20261022/publication-calibration-v4/`.
No unchanged retry or actor execution accompanied this correction. Calibration
does not rescore earlier actor runs or establish whole-skill acceptance.
