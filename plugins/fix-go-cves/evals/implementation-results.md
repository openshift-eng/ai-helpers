# Simplification implementation and verification

Full-cohort acceptance remains **open**. C16 passed live 001, then stopped after
publication 002 failed original and independent action/owner review for forecasting
a full fix after an unexecuted rerun. Facts, exact relay and operations passed.
The skill now gives verification steps without predicting outcomes. Prospective
C17 starts with publication 002; no freeze or actor has occurred.
The [plan](../plans/e2e-simplification.md) defines remaining work; the
[historical matrix](live/README.md#branch-policy-matrix) retains earlier failures.
Source groups, original false-positive grades and independent review stay separate.

## Current implementation, 2026-10-23

Earlier implementation from `8c88928b` passed component integration. Current v5
verification incorporates the license ownership and LF-reader fixes below; v4
passes remain historical evidence. Historical actor grades are unchanged.

| Changed boundary | Measured evidence |
| --- | --- |
| Frozen execution and authority | 85 eval tests pass in 49.587 seconds; current model-free 005/007/002 prepare/replay passes with expected historical results |
| Shared lifecycle and aggregation | 362 lifecycle/configuration checks and 186 scoring/sample-retention checks passed on selected harness paths |
| Physical Go metadata | Seven actual local-proxy transaction controls passed on Go 1.24 and 1.26 |
| Artifact ownership and scan consumer | 19 focused tests pass in 4.699 seconds, including actual license producer and native Unicode consumer controls; original counterexamples preserved |
| Cleanup / report preservation | Six / seven actual-producer controls; old report producer reproduces failures |
| Policy / publication | 15 semantic reader controls; 16 real-Git recipe controls; 182 workflow checks |
| Dispatch / final evidence | 90 assertions across 14 capture cases; 473 final-evidence workflow checks |
| Earlier combined integration | 3,207/3,207 frozen shell checks with all 28 runtime/subagent/test files matching that snapshot. Frozen Python suite: 66/66 before one additional publication control, separately verified. V4: 3,207 shell and 69 Python tests passed; later Unicode counterexamples prevent treating v4 as current closure. |
| Current v5 integration | 3,207/3,207 frozen shell checks pass (exit 0); all 28 runtime/subagent/test files match current bytes/modes. Python: 70/70 in 23.062 seconds. Receipt: `combined-runtime-v5-verification.json`. |
| Action calibration evidence | V6: 20/20 expected majorities, 60/60 samples, zero errors. All 18 V5 inputs/labels remain unchanged; two added controls isolate the whole-commit alternative. Prior failures and limits: [calibration record](live/calibration.md). |

Simplification removes the separate reporting reference/publication profile,
replaces duplicate policy readers with the existing semantic loader, and uses one
final canonical test phase. Native Go file binding replaces the proposed effective-
path query system. Publication uses an explicit confirmed Git route. No supervisor,
transaction service, generic flag/shell parser or new policy serializer was added.

A fresh critical review reproduced a surviving owned CLI when group signaling
raises an OS error. The small direct-child fallback passes the new stalled-leader
control; removing it reproduces failure. Partial output/settings cleanup and an
unrelated sentinel remain checked. Descendant termination when group signaling
fails is not guaranteed.

| New pilot | Original stock result | Independent result |
| --- | --- | --- |
| `e2e-simplified-replay005-20261023-01` | C true, O TTT false positive, A FFF; actor $0.69 | O/A false: unsupported independence, missing native uncertainty, fix-branch-only repair and promised clean rerun |
| `e2e-inference-replay005-20261023-01` | C true, O FFF, A TTT; actor $0.83 | O false solely missing native uncertainty; A true. All other factual claims independently verified. |
| `e2e-scope-replay005-20261023-01` | C true, O FFF, A TTT; actor $0.87 | O false: 16 other passing packages claimed versus 17 recorded, plus wrong tidy attribution. Separate rerun-owner ambiguity retained. |
| `e2e-handoff-replay005-20261023-01` | C/O/A true, O/A TTT; actor $0.75 | O false: directive upgrade attributed to tidy despite the producer observing it before tidy. A true. |
| `e2e-actionable-replay005-20261023-01` | C true, O FFF, A TTT; actor $0.81 | O false: wrong tidy attribution and missing compiled-binary coverage limitation. A true. |
| `e2e-concrete-replay005-20261023-01` | C/O/A true, O/A TTT; actor $0.82 | A true; O not fully certified because added no-scan/no-compilation claims exceed the receipts. No opposite unknown facts invented. |
| `e2e-relay-replay005-20261023-01` | C false (literal Summary), O/A TTT; actor $0.74 | Exact Summary was blockquoted; separate unsupported vet/transitive-dependency explanation prevents acceptance. A true. |
| `e2e-final-relay-replay005-20261023-01` | C true, O/A TTT, zero sample errors; actor $0.67 | C8 first accepted 005: O/A true after primary-evidence adjudication; original null review and stock grades retained |
| `e2e-final-relay-replay007-20261023-01` | C false (missing `8234df0`), O/A FFF, zero sample errors; actor $0.77 | O/A false: unsupported independence, wrong Go 1.25 explanation, missing existing repair commit and promised clean rerun/recipe; C8 stopped |
| `e2e-compact-relay-replay007-20261023-01` | C true, O FFF, A TTT, zero sample errors; actor $0.72 | C9 stopped: operational/A true, O false for unsupported syncer independence and reporter-predates claims; existing repair commit and all attempt outcomes correct |
| `e2e-observed-actions-replay007-20261023-01` | C true, O true (2/3), A TTT, zero sample errors; actor $0.75 | C10 individual pass: independent O/A and operations true; original dissent retained |
| `e2e-observed-actions-replay005-20261023-01` | C true, O true (2/3), A TTT, zero sample errors; actor $0.50 | C10 individual pass: independent O/A and operations true; original dissent retained |
| `e2e-observed-actions-publication002-20261023-01` | C false, O FFF, A TTT, zero sample errors; actor $0.70 | C10 stopped: independent O false, A/operations true; exact Summary followed by a duplicate rewritten recipe, missing native uncertainty and unsupported coverage |
| `e2e-scope-recipe-publication002-20261023-01` | C false, O FFF, A TTT, zero sample errors; actor $0.79 | C11 stopped after one actor: independent O false, A/operations true; exact Summary/native uncertainty and 34 test measurements verify, but a second equivalent-argv rewritten recipe fails strict relay |
| `e2e-stage-read-publication002-20261023-01` | C true, O/A TTT, zero sample errors; actor $0.74 | C12 replay pass; exact recipe once, native uncertainty, measured facts and image-publication prerequisite verify. Effective guard forwarding remains unverified, without inferring false guards. |
| `e2e-stage-read-replay007-20261023-01` | C true, O/A TTT, zero sample errors; actor $0.78 | C12 replay pass; independent O/A true, both attempts and origin repair prerequisite retained |
| `e2e-stage-read-replay005-20261023-01` | C true, O/A TTT, zero sample errors; actor $0.61 | C12 replay pass; independent O/A true, single attempt and origin repair prerequisite retained |
| `e2e-stage-read-live001-20261023-01` | C true, O TTT, A FFT, zero sample errors; actor $0.62 | C12 stopped: runtime/O true, independent A false for fixable-finding ignore advice and promised compilation; original A majority rejects on an unsupported reporter-backport requirement |
| `e2e-policy-boundary-live001-20261023-01` | C true, O FFF, A TTT, zero sample errors; actor $1.43 | C13 stopped: independent runtime 29/29 and A true, O false; quoted certificate 1.052s/57.5% contradicts actual 20.059s/89.1% |
| `e2e-summary-tests-live001-20261023-01` | C true, O TTT, A FTF, zero sample errors; actor $1.44 | C14 stopped: independent runtime 27/27 and O true, A false for a tentative compilation forecast from version; same-result caveat genuine, dissent retained |
| `e2e-prerequisite-only-live001-20261023-01` | C true, O/A TTT, zero sample errors; actor $0.71 | C15 stopped: independent runtime 27/27 and O true, A false; full candidate adds a Kubernetes-minor migration without approval, while the standalone Go option is valid |
| `e2e-commit-scope-live001-20261023-01` | C true, O/A TTT, zero sample errors; driver 0 | C16 individual pass: independent runtime 29/29, 52 evidence hashes and whole-reply O/A pass |
| `e2e-commit-scope-publication002-20261023-01` | C true, O TTT, A FFF, zero sample errors; driver 1 | C16 stopped after two actors: independent O/operations true, A false for an unobserved full-fix forecast; exact Summary/recipe and native uncertainty pass |

Complete actual skill intake was confirmed for the prior pilots, all three C10
actors, C11 publication 002 and C12–C16. Earlier campaigns remain separate; no failed actor is pooled
into a revised source. Current guidance quotes runtime
observations and failed/later-attempt outcomes, then allows only supported future
actions, owners and verification prerequisites. Default-branch repair-commit
search and direct target-origin policy reads remain required. The
bounded archived-producer witness now exposes the known tidy error to judges;
original recordings, prompts, thresholds and old grades remain unchanged. V7/V8 preserved false positives despite the producer witness and a named-command
criterion. A request-boundary audit verified complete serialized input, expected
model and absence of local cache/truncation. V9 replaces holistic assessment with
a factual-error audit of complete claim/evidence relationships: 18/18 expected
majorities across 54 calls, zero execution errors, one citation dissent. Original
failed grades remain unchanged. The current actor source clarifies compiled Go
binary coverage and defaults to reporting observed state without guessing an
uncaptured producing command.

C8's first 005 initially retained a null independent outcome for the phrase
"pulled in Go 1.26 toolchain." Separate primary verification supports the minimum
Go requirement reading: x/net v0.60.0 requires Go 1.26, the captured update raises
the directive, and Go 1.26's interface-method printf inference is gated on that
directive. This matches the failing `Basic.Failure` call even with the same
installed builder. Actual compiler installation/selection history stays unknown;
the reply does not claim a download or switch. Primary verification and the
resolution addendum accept O/A without new judging or changed criteria. The
original null review and stock sample rationales, including their unsupported
tidy attribution, remain unchanged. Receipts are
`final-relay005-pilot01-{independent-review,c8-primary-adjudication,adjudication-addendum,stock-completion}.json`
under `.work/fix-go-cves-e2e-20261023/`. This accepts one replay cell, not the full
cohort or general reliability.

A valid Markdown quote envelope exposed a separate checker defect. A shared
CommonMark extractor now decodes quote/list/indented code containers for Summary
and recipe checks while preserving literal content, including `>` operators.
Counts, exits, recipe values and duplicate/invented commands still reject. The
earlier 83-test suite passed; parser version 4.2.0 remains explicit in setup and
preflight. A three-line correction now aligns source indices with CommonMark
CR/LF normalization instead of Python Unicode `splitlines`, using the same parser.
Before correction, all three LF/CRLF/CR positive controls failed; afterward all
accept and reject an appended invented push. One 12-line regression covers both
boundaries; that 84-test snapshot passed in 49.570 seconds. Snapshot helper SHA-256:
`c41e6916cc7cdb076ca634408be0c59b21b7a80fe65e50f8320817337519c001`.
The earlier model-free 005/007/002 smoke exited 0, exercised driver preflight and
retained `aa5a4fc`/`aaaeea3`/`2716c2ff`, each with historical runtime exit 2.
Original artifacts and grades remain immutable; that smoke supplied no actor credit.

C10 publication 002 omitted native uncertainty and asserted unsupported coverage.
C11 corrected that distinction, preserved the full Summary through `exit=2`, and
accurately quoted all 34 passing package measurements and nine advisory rows.
Both added a second rewritten recipe with equivalent argv and target. The strict
literal guard intentionally rejects that relay/instruction/bloat failure; no unsafe
command, changed target or invented argument difference is asserted. Supported
Shipyard ownership, published Go 1.26.9 image prerequisite and rerun with unverified
outcome keep A true. Both original drivers exited 1 after all stages and six samples
completed without errors. Original independent/stock receipts remain under
`.work/fix-go-cves-e2e-20261023/{observed-actions,scope-recipe}-publication002-pilot01-*.json`;
the independent receipts retain their narrower process-exit observation boundaries.

C12's three replays passed under frozen source `52863d9d`. Actual loaded-section
rereads were observed with later read-only inspections; neither a last-tool gate
nor reread efficacy is established. Publication's effective guard environment
remains unverified: retained snapshot directories were empty, and omitted launch
assignments do not prove false guards. Live 001 separately authenticated both
guards true.

The live 001 engine completed in 139 seconds with exit 2: five actionable findings
remained blocked, one canonical `make unit` and all four audits passed, no build or
license was configured, no commits remained, and original `devel` was restored.
Archived runtime/evidence identities and quoted outcomes verify. Independent A
rejects advice to ignore findings with published fixes and the promise that the
proposed update "will compile" based only on builder version. The manual branch
workflow does discuss compatibility ignores, but the invoked skill permits only
no-fix ignores. No ignore was executed. Original A labels FFT are preserved: the
two rejecting rationales wrongly demand a reporter backport despite passing tests;
the passing sample misses the selected ignore policy and unsupported prediction.
Receipts remain under `.work/fix-go-cves-e2e-20261023/stage-read*-{independent-review,stock-completion}.json`.

The C13 skill and action criteria preserve
no-fix-only ignores and treat compiler compatibility as a prerequisite, with
proposed build/test/rerun outcomes unverified. Policy V2 and method V3 calibration
both falsely accept isolated prediction control 104 with TTT; neither starts its
conditional replay arm. Their original failures remain in the
[calibration record](live/calibration.md). Prediction V4 passed live controls but
rejected replay positives 102/103 with FFF: rationales turned supported syncer
investigation with a named owner into a required blocker from its table placement,
without an actual verification prerequisite. No control was relabeled or retried
unchanged. V5 shortens the method and distinguishes supported advice from an
asserted prerequisite; all 54 samples match their 18 fixed labels, including the
new paired blocker negative. Component checks above remain evidence only for
unchanged bytes; no actor or historical rescoring credit follows from calibration.
C13 then stopped after its first live 001 at frozen `975e0661`. Its engine took
155 seconds, exited 2 with five policy-blocked findings, passed canonical tests
and all audits, and restored the original checkout without commits. Independent
runtime checks pass, including both guards; advice keeps policy approval separate
from future verification without promising its outcome. But the reply quotes certificate
`1.052s`/`57.5%` instead of the actual `20.059s`/`89.1%`. The wrong values do not
appear in any authenticated captured log; their origin remains unknown. This is
a response accuracy failure, not a failed engineering gate. Original stages,
samples and the independent review remain under `c13-live001*` in the scratch root.

C14 at frozen `2a3c1b27` omitted redundant successful-package measurements;
its factual reporting passed in this cell. The actor took 268 seconds; the engine
completed a 143-second blocked exit 2 with canonical tests/audits passing, both
guards enabled and no commits. Original contract/outcome pass, A samples are FTF,
and the driver exits 1. Independent runtime and outcome
pass, A fails for "Go 1.26.9, so compilation is expected to succeed." A genuine
caveat leaves the same build/test/scan outcome uncertain; it does not establish
support for the version-to-compilation forecast. This was not a guarantee,
executed-success claim or uncaveated prediction. The rejecting majority applies
that exact boundary; the dissent waives the forecast because of the caveat.
Original artifacts and reviews remain under `c14-live001*` in the scratch root.

C15's original driver exited 0 after all stages and samples completed without
errors. The actor took 261.8 seconds; its 147-second engine run remained blocked
at exit 2, passed canonical tests/audits, retained no commits, and canceled its
wakeup. Independent runtime and outcome pass; action/owner fails the alternative
"cherry-picking `2d9f5fb` or a standalone go directive bump." The complete candidate
raises Kubernetes dependencies from 0.35.5 to 0.36.2 against release 0.35.8; only
Go approval was discussed. The standalone option is valid, but does not excuse
the bundled migration's missing decision. Nothing was migrated and no API failure
is asserted. The third passing A sample notices possible broader Kubernetes scope
then excuses it because the standalone option is also offered. Preserve that
false positive and all original rationales under `c15-live001*` in the scratch root.

C16 at `b538f2f9` stopped after two actors. Live 001 passed original thresholds and
independent runtime/whole-reply review: its 145-second runtime remained blocked at
exit 2, passed canonical tests/audits and retained no commits. The actor took
282.5 seconds/$0.737293; its driver exited 0. Publication 002 took 137 seconds/
$0.70137175; its driver exited 1 after all stages. The exact Summary and recipe,
native uncertainty, Shipyard owner and published-image prerequisite verify.
“Should clear” is tentative, not itself a guarantee; “the partial PR becomes a
full fix” asserts an unobserved rerun outcome. Original samples and independent
receipts remain under `c16-{live001,publication002}*` in the scratch root.

Prospective C17 changes only the skill's final phrase from “without predicting
build or test success” to “without predicting verification outcomes.” Both judges,
V6 calibration and computational components remain unchanged; do not repeat the
60 calibration calls or credit C16 actors to changed skill bytes. Whole-candidate
scope and approval checks remain; live-001 candidate facts require no particular
repair. After source freeze, start publication 002, then live 001, 007/005,
live 002/003/004 and four eligible replay repeats under the same 11-actor/$115
maximum, models and pins. C17 is not frozen; no actor has run.

A sandbox actual-license-block counterexample deleted a pre-existing ignored,
non-executable caller file when a generated executable's name contained a newline;
tracked files stayed clean. Ordinary-name control preserved the caller file.
The reviewed fix replaces pathname deletion with the existing artifact helper,
using a separate license prefix and no previous-run claims. Make/logger exits
remain separate from ownership failure, which blocks publication. Actual producer,
logger and trap controls preserve native baselines, caller files, links and nested
checkouts. Partial helper I/O failure coverage is not claimed.

A subsequent actual-license-producer counterexample exposed Unicode separators
being split in the helper's serialized baseline. Two LF-only baseline reads now
preserve all 16 pre-existing-path controls (eight separators × two modes) that the
old producer could delete. A third runtime reader fix preserves the same path
identity in native scan consumption: actual Unicode-fresh/ASCII-in-place scan
controls fail with the old consumer and pass with the correction. One eval JSONL
reader likewise now splits only LF; its raw-Unicode event regression previously
raised `JSONDecodeError` and now passes. These retain existing formats and parsers;
no human-log rewrite or new framework was added. Thirty-three retained machine
files containing 2,462 rows parse unchanged, recorded in
`jsonl-parser-compatible-recordings.json`.

Current model-free `e2e-owned-unicode-dry-20261023-01` completes 005/007/002
prepare/replay with exit 0, retaining `aa5a4fc`/`aaaeea3`/`2716c2ff` and each
historical runtime exit 2. Original counterexamples and verification receipts,
including `license-cleanup-{counterexample,fix-verification.json}` and
`final-boundary-unicode-artifact/{receipt,actual-producer-receipt}.json`, remain
under `.work/fix-go-cves-e2e-20261023/`. V5 source identity is recorded in
`combined-snapshot-v5-source.json`. Runtime, outcome criteria, models and thresholds
remain unchanged. V9 outcome controls retain their scope; the changed action
prompt and live-001 action annotation require the separate calibration above.
This supplies no actor credit, scoring recovery or live acceptance of changed
runtime. Component verification remains applicable to unchanged bytes;
future actor acceptance remains separate.

A separate model-free actual-engine diagnostic,
`e2e-engine-readiness002-20261023-01`, repaired all five x/net findings on official
Admiral `af20d0b` in 240.08 seconds (exit 0). Its single canonical `make unit`,
including race detection, passed on exact retained commit `6e660e1`; all four
audits passed and final scan matches were zero. License/native build were not
configured. The checkout was clean, all 22 frozen runtime files unchanged, and
no owned containers remained. Standard frozen capture passed; its actual repair
scenario passed 18/18 predicates and 10/10 capture/provenance checks. The full
contract correctly rejected the missing actor reply. This verifies producer/
consumer compatibility and one engineering outcome, not live actor acceptance,
general reliability, or a causal explanation for earlier race failures. Cost is
unknown. No engine/actor rerun, target patch or pin change was used.

A separate native Subctl diagnostic at official `50243ac` completed once in
295.57 seconds, exit 2 confirmed partial. Tests, four audits and license passed
on retained `c9932ef`; initial/final unpacked native artifacts had exact clean VCS,
positive catalog locations and matching retained hashes. One stdlib finding,
GO-2026-6809, remains in the custom Go 1.26.9 compiler; a vendor-supported patched
image must be published before consumers rerun. Frozen capture passed and the
actual binary scenario accepted 24/24 predicates plus 10/10 integrity checks.
No owned containers remained. The full checker rejected absent actor output;
this supplies no actor/cohort credit or claim of stdlib remediation.

The live oracle's existing landing/causal controls matched 8/8 labels and 24/24
samples. Oracle controls are inspected development evidence, not unseen holdouts
or reliability estimates. All judge costs remain unpriced. Judge rationale is not
independent evidence; overreaching incidental reasoning remains documented.

Sample aggregation now retains each raw value, rationale, error and supplied
usage/response ID in the existing result file (+12 production lines). It preserves
requests and verdicts: 84 mocked serialized requests are byte-identical; the first
real run retained six complete rationales and six distinct response IDs. Older
samples retain their representative-rationale limitation. Upstream physical retry
usage overwritten before aggregation remains outside this metadata fix.

## Earlier implemented changes and checks

Detection owns default commands; the skill preserves target policy, launches once
and investigates read-only. Runtime fixes preserve command/logger status and
reviewer detail, report phase-specific scope and enforce explicit Go/Kubernetes
minor restrictions. Reporting uncertainty does not trigger the blocking opaque-
binary marker. Native contracts require initial/final proof outside clean fast
paths; Subctl release now declares `binary` coverage.

Positive recording 002 uses an applicable publication/builder scoring profile
sharing replay execution/contract configuration. Its [calibration](cases/case-002/calibration.md)
retains the failed initial oracle and corrected independent Summary witness:
V4: 10/10 expected majorities, 30/30 expected samples, zero sample errors.
V5 adds two actual/corrected scope/environment controls: 2/2 majorities and 6/6
samples match. Preserve the actual actor false positive and unsound extra rationale
criticisms. These bounded controls do not prove general factual reliability.

| Local check | Result |
| --- | --- |
| Immutable runtime shell suite | 3,102/3,102; runtime/test bytes and modes matched |
| Eval helper suite | 73/73, including complete skill staging and corrected cleanup-head provenance |
| Focused evidence / Go guards / reviewer checks | 349 / 34 / 14 passed |
| Model-free 005/007/positive-002 replay | Expected retained commits and exit 2 reproduced |
| Strict site build / clean-snapshot lint | Passed before this documentation update |

Native outcome [controls](live/calibration.md) now reject the two known native
reply errors by majority (4/4 expected majorities, 11/12 expected samples), retaining
one wrong-builder false-positive sample. The initial calibration accepted both
known negatives; all original grades remain preserved.

Earlier shell runs were invalidated by concurrent edits or an obsolete physical-
line assertion. A behavioral build test replaced that assertion; the immutable
suite above is the final runtime result. Model-free worker checks exercised real
Dapper ownership, timeout, caller cancellation and container cleanup. Runs used
the disposable rootless daemon and inherited `make unit`; no target publication
was executed. Missing native/build coverage remains explicit.

## Actor results by frozen source

Run IDs below live under `.work/fix-go-cves-evals/runs/fix-go-cves:fix-go-cves/`.
`C`, `O`, `A`, `B` mean contract, outcome, action_owner and backport. Pass/fail
refers to preserved stock results; the last column is independent whole-reply
review. A passing majority does not erase a factual error.

| Source / run ID | Preserved stock result | Whole-reply result or coverage |
| --- | --- | --- |
| Original: `simplify-replay-20261022-01` | 005: C/B pass, A fail; 007: B pass, C/A fail | Both reject causal claims; 007 misses actual retries and attempts denied `git stash` |
| Original: `simplify-publication-20261022-01` | C/O pass, A fail | Reject invented prerequisite, guaranteed clean rerun and missing native uncertainty |
| Operator error: `simplify-publication-20261022-02` | Incomplete; actor terminated | Wrong-directory edit failed while launch continued with unchanged source; no revised-candidate evidence |
| Relay clarification: `simplify-publication-20261022-03` | A pass, C/O fail | Reject duplicate rewritten publication recipe; preserve qualified future wording separately |
| Original live: `simplify-live001-20261022-01` | C fail, O/A pass; separate corrected-oracle recheck passes runtime conditions | Real exit 2: both guards enabled, five findings blocked, `make unit` passed, no commits, original ref restored. Reply rejects: unsupported low-risk assessment and guaranteed five-CVE repair |
| Facts: `simplify-facts-replay-20261022-01` | 005: C/B/A fail; 007: C/B pass, A fail | 005 attempts denied source Edit and misses matching backport; 007 retains unsupported causality |
| Facts: `simplify-facts-publication-20261022-01` | C/O pass, A fail | Exact recipe, but reject claim repaired image will produce a clean result |
| Facts live: `simplify-facts-live002-20261022-01` | C/O pass, A fail | Real x/net repair `c426d81`, exit 0, unit/four audits/final scan pass. Build unconfigured/native unverified; reject claimed build pass and invented publication steps |
| Reporting reference: `simplify-reference-replay005-20261022-01` | C/B/A pass after scoring-only recovery | Reject unsupported upgraded-Go cause and invented original ref. Reference read before launch, not near composition |
| Reporting reference: `simplify-reference-publication-20261022-01` | C/O/A pass after scoring-only recovery | Reference read immediately before reply; exact recipe/scope/owner retained. Reject false “only unit” claim: four audits and license actually passed |
| Final reference pilot: `simplify-final-replay005-20261022-01` | C/B pass, A fail | Reject unsupported attribution and binary-only scope label |
| Final reference pilot: `simplify-final-publication-20261022-01` | C/O/A pass | Accept literal recipe, supported image owner/prerequisite and native uncertainty |
| Handoff: `simplify-handoff-replay005-20261022-01` / `02` / `03` | C/B/A pass in all three | 01/02 accept; 03 miscounts 17 passing packages as 16, despite correct backport/prerequisite |
| Handoff: `simplify-handoff-replay007-20261022-01` | C/B pass, A fail | Reject unsupported syncer cause and missing investigation owner/action despite accurate attempt outcomes |
| Handoff native: `simplify-handoff-live003-20261022-01` | C/O/A pass | Runtime proof/gates pass; reject blanket native-unverified claim contradicting quoted positive scope |
| Handoff native: `simplify-handoff-live004-20261022-01` | C/O/A pass | runtime proof/gates pass; reject wrong builder/owner imported from nested reviewer narrative |
| Observed evidence: `simplify-observed-replay-pilots-20261022-01` | 005 C/B/A pass; 007 C/B pass, A fail | 005 accepts; 007 rejects unsupported pre-existing/flaky label and rerun prediction despite correct attempts |
| Observed positive: `simplify-observed-publication-20261022-01` | C/O/A pass | Reject inferred native proof and categorical toolchain setting; literal recipe, owner/prerequisite and read-only behavior pass |

Live 001 exposed an oracle defect: the final scan ran at the executed release
HEAD, then empty-branch cleanup restored the original devel HEAD. The old helper
compared the receipt with that restored HEAD. The corrected helper checks executed
scan provenance; its model-free recheck preserves all original grades/artifacts.
It does not accept the actor's reply.

Reference pilots initially failed the scoring integrity fence because the helper
changed concurrently. Initial artifacts were preserved; restoring the exact frozen
helper allowed **scoring/report/verification only**, with byte-identical actor
artifacts and no actor retry. Both recovered stock passes above are false positives
against whole-reply requirements. Retain the integrity failure alongside recovery.

## Current treatment and remaining acceptance

The literal source group at `472270e9` was measured from an unchanged detached
worktree. All three pilots passed stock thresholds and independent review. The
second replay pair then exposed a denied `git stash` and omitted upstream-landing
prerequisite in 007. Preserve the correct contract failure and the factual judge's
false positive; final clean refs do not excuse an attempted forbidden operation.

| Literal measurement | Stock result | Independent result |
| --- | --- | --- |
| `simplify-literal-replay-20261022-01` | 005/007 C/B/A pass | Both pass; minor format/reference-order deviations retained |
| `simplify-literal-publication-20261022-01` | C/O/A pass | Pass; exact recipe and supported image prerequisite |
| `simplify-literal-replay-20261022-02` | 005 C/B/A pass; 007 C fail, B/A pass | 005 passes; 007 denied stash and missing origin landing |
| `simplify-literal-live001-20261022-01` | C/O/A pass | Runtime 21/21; whole reply passes; guarded exit 2, five findings, no commits, original ref restored |
| `simplify-literal-live002-20261022-01` | C fail, O/A pass | x/net repair clears five findings, but both unit attempts fail on the same workqueue race; whole advice omits origin landing |

Live002 retains `ed36476d` with only go.mod/go.sum changes. Four audits and final
scan pass; passing scans cannot override failed tests. Both race attempts retain
paired logs/receipts. The failed successful-repair scenario remains failed; no
extra retry or local patch is applied to its eval case. A separately declared
single baseline `make unit` at `af20d0bf` passed. That control does not establish
absence of the race or attribute the update's role. The test-fixture lifetime
mechanism and narrow external candidate were investigated separately; the final
diagnostics below retain the inconclusive result.

The historical `8788312f` source placed remote/image prerequisites beside its
reporting table and attribution uncertainty before repair discovery. Immutable-ref
reads use captured command/base/retained commits; a refreshed origin ref is not
the executed base. That source required a row for each failure or unresolved
decision, including a failed-then-passed attempt, and an investigation instruction
for unknown repairs. Current compact guidance retains relevant attempts and
actionable unresolved work without requiring that table or a task for a recovered
retry. The separate pilot group below preserves the historical source and results.

The live action criterion now explicitly requires upstream repair landing before
reruns and published images before consumer reruns. Its two controls match all
6/6 samples and 2/2 majorities, preserving the prior false-positive grades. Full
oracle details belong to the [native/live calibration record](live/calibration.md)
and [publication calibration record](cases/case-002/calibration.md).

Scratch evidence remains under `.work/fix-go-cves-implementation-20261022/`.
Each `*-candidate-protocol.json` freezes its source group; run directories retain
inputs, replies, traces, samples, HTML and completion/regression results. Independent
`*-whole-reply-review.json` and `*-runtime-review.json` receipts keep disagreements
separate. `literal-operation-state-audit.json` records the denied stash; the
`workqueue-baseline-control/` protocol/log/exit preserves the single passing control.
Prior scoring-only integrity recovery and failed calibrations remain unchanged.

No complete current-source cohort or replay reliability is accepted. Do not rerun
unchanged live002 merely to obtain a favorable race seed, weaken its repair
contract, skip the package or silently inject a local patch. That historical
successful-repair cell remains failed. The separate official-pin readiness
diagnostic above demonstrates feasibility without proving a race repair or
requiring a new pin. Native engine coverage under earlier reporting variants
remains distinct from current invoking-agent/native acceptance.


## Prerequisite pilot and final diagnostics

The `8788312f` campaign contains only the three declared pilots:
`simplify-prerequisite-replay-20261022-01` (005/007) and
`simplify-prerequisite-publication-20261022-01` (002). It stops without expansion.
Replay 005 has sound facts/backport prerequisites; 007 reports both attempts and
remote landing but adds an unsupported flaky label and misidentifies a package
failure's log line. Neither attempts a denied operation. Publication has sound
facts, exact recipe and a published-image prerequisite, but attempts denied
read-only `git stash list`. That differs from the earlier attempted mutating
stash; the existing blanket permission/trace contract still rejects it. Preserve
literal-evidence and reference-order deviations separately from factual invention.
Publication's recovered contract fails; O/A both pass all three samples. All six
judge calls complete without sample errors (168.40 seconds; all unpriced).
Independent factual/advice review passes while operational whole acceptance fails.
Recovered replay scoring passes both contracts, B=TTT and A=TTT for each case
(12 judge calls, zero regressions). Those 007 factual labels are false positives
against the independent citation/neutral-label review; retain both results.
The compact oracle still omits finding IDs; full raw rows independently validate
the accurate IDs rather than treating absence from that compact oracle as proof.

Both original pipelines execute their declared actors, then collection fails 127:
the old Homebrew Python 3.13 interpreter target disappears mid-campaign. Replay
007's prepare hook falls back to system Python 3.14.8; do not claim one interpreter
identity across these cases. Original failures and raw actor artifacts are retained.
An isolated Python 3.12.15 environment reconstructs all 45 exact package versions;
73 helper and 275 focused harness tests pass. Recovery executes only collection,
previously unexecuted judging, reporting and verification against unchanged actor
artifacts. This is scoring recovery, not an untouched successful E2E run.

The external workqueue investigation also stops. All 20 focused diagnostic
executions pass, including unpatched arms. A separately declared final canonical
comparison runs each retained tree once: original exit 0 (81.424 seconds), patched
exit 0 (80.237 seconds), all 19 packages with race detection and coverage. Neither
comparison demonstrates patch efficacy; the original focused gate stays unmet and
live002 stays failed. Independent receipts verify source/input/image hashes,
clean trees, host ownership and empty worker containers. The
[fixture-owned cleanup design](../plans/workqueue-race.md) is preferred for separate
upstream review; it is not implemented or tested by the diagnostic candidate.

Evidence is under `prerequisite-*-protocol.json`, `prerequisite-*-review.json`,
`recovery-*.json` and `workqueue-full-context-comparison/` in the existing scratch
root. Preserve the original 127 exits, interpreter differences, operation denials
and all recovered grades. No current-source cohort or replay reliability is accepted.
