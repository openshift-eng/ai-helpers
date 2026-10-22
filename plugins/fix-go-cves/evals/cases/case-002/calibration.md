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

Both versions use harness `1a980e707909a23f8c143ce333d97f5203db34ab`, judge
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
