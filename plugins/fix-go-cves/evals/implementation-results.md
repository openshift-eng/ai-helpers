# Simplification implementation and verification

The skill remains **unaccepted**. Script correctness, stock grades and independent
whole-reply acceptance are separate. The [plan](../plans/e2e-simplification.md)
defines remaining work; the [historical matrix](live/README.md#branch-policy-matrix)
retains earlier failures unchanged. Different source groups below are never pooled.

## Current implementation, 2026-10-23

The implementation from `8c88928b` is still being verified. These measurements
supersede component claims only; all actor grades below remain historical.

| Changed boundary | Measured evidence |
| --- | --- |
| Frozen execution and independent authority | 80 eval tests passed; model-free stock 005/007/002 preparation/replay passed |
| Shared process lifecycle and exit aggregation | 302 focused harness tests plus three actual result-field/aggregation tests passed; reproducible patch checked in |
| Physical Go metadata binding | Seven actual local-proxy transaction controls passed on Go 1.26 and Go 1.24 |
| Generated output ownership and scan consumer | 16 real-Git/actual-scan controls passed; reverting the consumer reproduces failure |
| Checkout cleanup and archive failure | Six actual cleanup controls passed |
| Report-only preservation | Seven actual-producer controls passed; reverting the producer reproduces dirty-input/restore-diagnostic failures |
| Dispatch capture | 90 assertions across 14 controlled producer/logger cases passed |
| Full runtime integration | Fresh combined run exposed fixture migrations for conservative ownership/policy handling; final combined run pending |

Production simplification removes the separate reporting reference and publication
profile, replaces duplicate policy readers with the existing semantic loader, and
uses one final test phase. Metadata uses explicit native physical-file binding,
not an additional effective-path query system. The identified harness patch is
applied to the pinned checkout; no supervisor or new harness service was added.

Replay oracle development retained 126 judge calls and all failures. The current
fixed controls use the V2 publication pair, V4 case-007 citation pair and V5 three
case-005 controls: 14/14 expected criterion majorities, 41/42 matching individual
samples, zero sample errors. Restoring whole-reply accuracy in the authoritative
criterion fixed a scope regression; adding typed result fields did not fix it and
was removed. These inspected controls are development/regression evidence, not
unseen holdouts or a reliability estimate. Judge costs are not fully priced.

The first replay pilot, `e2e-simplified-replay005-20261023-01`, completed all stock
stages ($0.69 reported actor cost; six judge calls unpriced). Contract passed;
outcome passed TTT despite independent failure; action_owner failed FFF. Independent
review rejects unsupported causal exoneration, missing native uncertainty and a
repair confined to the generated branch before a promised clean rerun. Actual
Claude session evidence confirms complete current skill intake; this is a behavior
failure, not a staging omission. The all-pass source campaign stopped after this
one actor; all original stock stages and raw results are preserved. No later actor
may be pooled into it. Live source/settings still require their final freeze.

The live oracle controls separately matched 8/8 expected criterion majorities and
24/24 samples without errors. Existing actual/corrected landing advice and bounded
causal-experiment pairs were copied unchanged; scoped diagnostic units earn no
full-runtime credit. All 24 calls are unpriced. A new nine-control replay regression
check is running after explicit causal-support/native-disclosure clarification;
no later actor has started.

The fresh combined Python snapshot passed 66/66 metadata, artifact, policy,
cleanup, report and publication controls. Subsequent shell-fixture-only migration
adds a preserved legacy publication case; the final shell snapshot remains pending.


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
mechanism and a narrow external candidate are being verified separately.

Current changes move existing remote/image prerequisites beside the reporting
table and put attribution uncertainty before repair discovery. Immutable-ref
reads use captured command/base/retained commits; a refreshed origin ref is not
the executed base. Every failure or unresolved decision gets a row, including a
failed-then-passed attempt; unknown repairs get an investigation instruction.
Already quoted script scope gets no duplicate interpretation. Runtime/helper bytes
remain those verified above. The invoking skill was frozen as `8788312f` for the
separate pilot group below.

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
contract, skip the package or silently inject a local patch. A reviewed upstream
fixture repair and a declared fresh official pin are prerequisites to closing that
successful-repair cell. Native engine coverage is demonstrated under earlier
reporting variants; current invoking-agent/native acceptance remains distinct.


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
