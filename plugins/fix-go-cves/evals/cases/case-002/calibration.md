# Positive publication recording and calibration

Submariner `release-0.24` exited 2 after a partial x/net repair, with 36 remaining
stdlib findings (nine advisories across four binaries) and a real publication recipe.
This historical replay does not establish current-engine or authenticated native coverage.

- Result: `2716c2fffebad84210293229442c4fd9eb582eba`.
- Sole parent/base: `e9b4dec4944cbbf8d630603904fb6e0f82a2b566`.
- Default/original ref: `devel` at `fb518adb012b060e4e5ec252cc34b92cab99cac1`.
- Raw log SHA-256: `6e6d9465372c0c1792aafaec722ba0aca9999ce2670cde70147d9ca174e5070b`.

The packaged log replaces checkout/home paths with `{{REPO}}`/`{{HOME}}` and recipe
accounts with `fork`/`example`, preserving flags and shell escaping. Plugin archive
and bundle retain their bytes; preparation substitutes today's invoking skill.
Session metadata is excluded. The reference retains the witnessed Summary/recipe,
Shipyard image owner and image-publication-before-rerun prerequisite.

## Declared controls and ownership

O = outcome; A = action_owner. Each configured criterion has three samples.

| Control | Expected O/A |
| --- | --- |
| Reference | true / true |
| Missing recipe (remove only the recipe) | false / true |
| Invented recipe base (`release-0.24` → `devel`) | false / false |
| Missing builder owner/prerequisite | true / false |
| False check scope (reference + false “only make unit” claim) | V3: false/false; V4: false/true |
| V5 actual proof/configuration negative | false / unscored |
| V5 corrected proof/configuration reference | true / unscored |

V1/V2 use the first four controls; V3/V4 use five; V5 admits only its final pair.
V4 assigns all past/present facts to O and supported future actions/owners/prerequisites
to A. A wrong-target publication command remains an invalid future procedure.
Moving the false-check error to O preserves conjunctive rejection of every negative.
Reporting every gate is not required; contradicting an observed gate fails O.
The reference's true original ref was added to the independent evidence in V4.

## Measurements and preserved failures

All versions use harness `1a980e707909a23f8c143ce333d97f5203db34ab` and judge
`claude-opus-4-6`, with zero actor executions and zero reported API/sample errors.

| Version | Judge calls | Correct samples | Correct majorities | Seconds | Result/limitation |
| --- | --- | --- | --- | --- | --- |
| V1 | 24 | 17/24 | 6/8 | not recorded | Invented-base O/A both TTT; missing-owner O=TFT |
| V2 | 24 | 23/24 | 8/8 | 141.86 | Invented-base O/A both FFF; missing-owner O=TFT |
| V3 | 30 | 27/30 | 9/10 | 146.75 | False-check O=TTT/A=FFF; all samples stable |
| V4 | 30 | 30/30 | 10/10 | 126.41 | All five controls match, each unanimous |
| V5 | 6 | 6/6 | 2/2 | 117.85 | Actual negative FFF; corrected reference TTT |

V1 lacked an independent Summary witness: judges authenticated the reply using its
own block. V2 supplies `recorded_evidence.summary` and compares against it. V1/V2's
false missing-owner O sample imports A requirements. V3 adds trusted audit/license
facts but O acknowledges the false check claim and discounts it as minor while
also judging A. A rejects that control, preserving the factual conjunction. V4
separates responsibilities; its retained explanations apply the declared ownership.
These calibration successes do not prove criterion bleed is eliminated generally.

V3 witnesses are historical log observations, not fabricated typed receipts:
four audit PASS/zero-issue lines 13120–13123, completion 13124, license command
13449 and passing result 13674. V5 distinguishes cataloger-task completion
(lines 240/385/648/13083/13356) and binary finding paths (13412–13447) from absent
catalog-location/hash/build-provenance proof. The only historical `GOTOOLCHAIN`
mention is nested reviewer “typically local” prose at 13387, not observed target
configuration. Current replay-host settings do not authenticate that old container.
V5 retains V4 prompts/criteria and changes only those witnesses and two observations
in its corrected reply; every other action-table cell and the Summary stay intact.

V5 labels match, but reasoning remains imperfect: a retained rationale wrongly
calls full-log advisory IDs fabricated because compact annotations omit their list,
and discusses the GOEXPERIMENT gloss as unsupported. Correct labels are not proof
that every rationale is sound; representative explanations do not explain each sample.

## Complete fix alternatives and parser admission

The C21 reply in [wrong-stdlib-release.md](negatives/wrong-stdlib-release.md) treats
four advisories as requiring Go 1.27, based on the shortened initial column. The
post-fix direct Grype table at 13098–13107 includes 1.26.9 for all nine advisories;
four also list 1.27.2. The existing annotation fact map now exposes those primary
alternatives and the initial display limitation. Criteria are unchanged.
The [corrected reference](stdlib-release-reference.md) preserves the Summary,
recipe, native disclosure and events, correcting only the exclusive-version
interpretation and unsupported policy handoff.

V6 completes two controls × O/A × three samples = 12 valid samples, zero errors
and zero actors: wrong-version O/A=FFF/FFF; corrected O/A=TTT/TTT.
Separate parser-validity renewal includes V9's invented-ID control 202 and V5's
native/configuration negative 101, three O samples each. Those are distinct
questions and are not replaced by the new pair. V9 202 rejects FFF. V5 101 passes
T/F/T despite both passing rationales finding unobserved GOTOOLCHAIN and missing
native authentication; they waive unsupported facts as not contradicted. The
combined 27-sample admission therefore fails before any actor.

The boolean parser formerly emitted false on unparseable output without an error.
Historical error counts above are reported counters. Missing per-sample reasons
cannot certify every old false as genuine feedback; original values stay unchanged.
The exception uses the existing error/usage path, and every new sample
must be valid, retained and error-free. This is witness/error-path admission,
not a format rule, actor pass or unseen holdout.

C23 explicitly rejects unsupported factual claims, but its 51 valid, error-free
O responses match only 14/17 expected majorities. V5 101 still passes T/T/F;
V9's wrong-citation and wrong-command negatives also pass. Both fix-version
controls and all four native controls have the expected labels in every sample.
Original grades and dissent remain unchanged.

C24's counterexample task after the evidence/reply matches only 14/17 majorities
and 42/51 samples, with zero errors. V5 101 passes TTT; V9 102 misses its citation
and V9 105 is wrongly rejected on A criteria. Preserve every rationale and dissent.

C25 gives O only `criteria.outcome`, preserving all other facts. It reaches 16/17
majorities and 47/51 matching samples with zero errors; citation control 102 still
passes TTT. V5 101 rejects F/T/F; correct and dissenting rationales remain intact.

C26 fixes a shared instruction conflict: its system prompt excluded the user
message that actually carries the rubric. Delegation now names the unfenced user
rubric while retaining artifact guards. A also receives only its own criterion.
All 117 renewed responses are valid, distinct and error-free: 38/39 majorities and
114/117 values match. All A66 and every O except wrong-citation 102 match unanimously;
that negative still passes TTT. Preserve its nearby-line substitutions.

C27 makes exact citation attribution concrete in O's existing relationship
paragraph. It requires no citations or new format. Renew the same 51 O samples;
reuse C26 A66 only by independent acceptance and full request identity. All
expected labels remain required before the fresh eleven-actor cohort.

## Actor evidence and artifact locations

| Actor run | Original stock contract/O/A | Independent whole-reply review |
| --- | --- | --- |
| `simplify-reference-publication-20261022-01` | pass / TTT / TTT | Reject: false “only make unit” claim |
| `simplify-final-publication-20261022-01` | pass / TTT / TTT | Accept under frozen criteria; one positive-relay pilot |
| `simplify-observed-publication-20261022-01` | pass / TTT / TTT | Reject: unsupported native coverage and historical GOTOOLCHAIN assertion |

Original scores remain unchanged. Calibration artifacts are under
`.work/fix-go-cves-implementation-20261022/`: V1 `publication-calibration/`, then
`publication-calibration-v2/` through `publication-calibration-v5/`. Each retains its
declared protocol, frozen controls/configuration and complete sampled labels;
independent result reviews are retained alongside the summaries where applicable.

The 114 V1–V5 judge calls were unpriced; total cost is unknown. Stock calibration exits
are 1 because negative controls fail production thresholds; expected-label matching
determines calibration success. No unchanged retry or actor rerun obtained these
labels, and no calibration overwrites earlier actor grades. Repeatability, blocked
cases, whole-skill acceptance and current remediation-engine acceptance remain open.
