# E2E acceptance and simplification

Implementation plan audited by runtime, eval and simplification specialists on
2026-10-22 against `b0368cb8`. The finite treatment below is now implemented;
acceptance measurements are in progress, not accepted. The
[implementation results](../evals/implementation-results.md) retain measured
outcomes; the [testing strategy](testing.md) owns durable requirements and environment
rules; the [latest matrix](../evals/live/README.md#branch-policy-matrix) owns
historical results. Preserve original artifacts and grades.

## Findings and finish line

The stock pipeline completes execution, collection, extraction, judging,
reporting and regression. Remaining failures concern behavior, evidence and
scenario coverage. The finite treatment map is:

| Boundary | Failure and implemented treatment | Verification |
| --- | --- | --- |
| Command selection | Admiral release replaced inherited `make unit`; let `detect.sh` own defaults and preserve explicit settings unless higher-priority policy overrides them | Existing precedence tests and actual canonical-command receipts |
| Result relay | Admiral release rewrote a Summary line; relay the witnessed terminal result literally | Existing Summary/terminal-exit contract |
| Publication | Successful live replies invented procedures; preserve withheld publication and relay only the complete emitted recipe | Existing command contract, whole-reply negatives and a real positive relay measurement |
| Diagnosis | Correct repairs coexist with unsupported causes; separate observations, available repairs and demonstrated causes | Replays 005/007, reviewed references and causal negatives |
| Scan scope | Subctl replies omitted scope; expose concise phase-specific facts, leaving unsupported native coverage unverified | Evidence-enabled/disabled, clean and blocked paths plus native contract |
| Grading | Some factual majorities accept known errors; check the relevant controls before trusting new labels | Unchanged requirements, calibrated changed grader inputs and whole-reply review |

Track three explicit milestones. **Existing-cohort acceptance** requires both
Admiral replays and all four live cases to complete the stock pipeline, pass
configured thresholds and corrected scenario contracts, and pass whole-reply
review. Live 001 may correctly report a blocked run; live 002 must demonstrate a
successful repair; live 003/004 must demonstrate their declared native coverage.
**Replay reliability** requires the existing three-execution comparison for
005/007. **Publication coverage** requires the admitted real positive-recipe
replay to complete the stock pipeline, pass configured thresholds and pass
whole-reply review. Existing-cohort acceptance alone does not establish
complete skill acceptance while reliability, publication or applicable policy
boundaries remain unresolved. Pure cleanup is a separate deliverable.

## Implemented design

| Owner | Responsibility |
| --- | --- |
| `detect.sh` | Resolve environment, target configuration and default commands |
| Remediation scripts | Mutate/roll back, run gates, retain results and decide publication eligibility |
| Invoking skill | Apply user/branch policy, launch once, observe completion, relay results and investigate remaining work read-only |
| Eval helper | Independently check execution, retained state and declared scenario evidence |
| Factual judges | Assess diagnosis and advice against captured facts throughout the reply |

The skill now uses one ordered procedure. Detection implements
inherited environment → target configuration → defaults (`detect.sh:235–295`).
Retain explicit settings unless higher-priority user/branch policy requires an
override, and retain genuine maintained additional checks. Do not reconstruct a
default in the actor or treat CI/Make target presence alone as a new requirement.
This does not remove the existing deterministic license gate.

Use the unchanged Summary followed by diagnosis only for actual unresolved
outcomes. Preserve the observation, supported repair/investigation, owner and next
verification prerequisite. An available backport does not prove cause; it must
reach the remote target before a requested rerun. A passing retry does not erase
the first failure. Keep diagnosis useful without inventing attribution.

Existing output now includes concise scan-scope statements using available evidence,
including initial/final phases and terminal paths without a Summary. Normal runs
do not retain the eval's full catalog proof: a build, readable binary or absent
warning is insufficient proof of native catalog coverage. Report that coverage
as unverified when positive proof is unavailable; do not build a production copy
of the eval proof system merely to describe this limit. Basic output must work
without the optional evidence directory.

Reporting uncertainty must remain separate from the existing `.coverage-unknown`
sentinel: that marker denotes opaque/unreadable binaries and blocks clean results
and publication (`scan.sh:79–92`, `fix-all.sh:257–260,894–897`). Missing optional
proof must not acquire the same gate semantics. Preserve rollback ownership before
and after the detector's state handoff, partial results, interrupt disposition and
post-Summary empty-branch removal.

## Concrete runtime prerequisites

These narrow audit findings are addressed in the candidate, separately from
instruction simplification. They were not observed causes of the latest actor
failures; focused checks and live coverage remain distinct.

| Audited gap | Implemented treatment |
| --- | --- |
| Build/license pipelines lost logger status | Preserve command exits separately, stop scanning after build capture failure and mark license `capture_failed` while blocking publication |
| Parent dropped admitted `stdlib` reviewer detail | Accept exact requested keys and append valid reviewer detail while retaining deterministic reasons; no historical false-clean/publication bypass was established |
| Builder permission could mask repository restrictions | Carry Go-minor policy through configuration/state, proposed-update/post-tidy checks and reviewer input; effective caller guards override conflicting inherited settings. Unknown-builder diagnostics retain the guard reason |

Do not repair unrelated runtime behavior opportunistically. The existing hermetic
suite is the first check for these changes; a real run must reach a changed path
before claiming live coverage.

## Ordered work and execution budget

1. **Admission completed.** Recording 002 is packaged with its real log, pins,
   bundle, reference and negatives. `eval-publication.yaml` supplies applicable
   builder-image/recipe criteria without Admiral backport requirements; replay
   profiles share `replay-base.yaml`. Calibration passed all eight control
   majorities, with 23/24 expected sample labels and one criterion-bleed error.
   Preserve that disagreement. Local-only live remotes cannot replace positive
   recipe relay measurement.
2. **Finite treatment implemented.** The skill now leaves defaults to detection,
   instructs literal result relay and supported diagnosis, and exposes scope without
   adding production proof machinery. Logger/reviewer fixes and effective policy
   guards accompany the native-phase contract and live-004 expectation changes.
   Pure normalization/fixture/reviewer cleanup remains separate.
3. **Local checks and oracle review.** The helper suite passed 70 checks and
   focused Go-guard checks passed 34/34. Final shell/evidence verification is
   pending; preserve its actual outcome in the implementation results. Existing
   reviewed controls remain the oracle; recalibrate changed prompts, models or
   evidence inputs before scoring. Stock majority reduction stays unchanged:
   three judge samples are not three actor trials.
4. **Freeze one candidate and declare the executions.** Specify question, cases,
   criteria, source, CLI/model identities, caps and which executions count toward
   each milestone. Designate the integration execution in advance; do not select
   the best replay after scoring. An unchanged-source pilot/integration execution
   can count toward the three declared replay executions when its inputs and
   identities match. Compare current skill hashes across applicable cases and
   current runtime hashes across live cases; validate historical runtime archives
   against their own pins. `prepare()` copies current files per case
   (`eval.py:263–270`), so a Git revision and frozen YAML alone do not bind all bytes.
5. **Run the declared stock path and review every cell.** Revalidate shared-worker
   authentication, ownership mapping and cancellation first. Use 001 for inherited
   command/blocked diagnosis, 002 for repair/withheld publication and Subctl for
   native reporting/gates. Retain all samples, HTML reporting, completion checks
   and regression. Whole-reply review cannot replace a failed configured threshold.
   Keep blocked outcomes, missing findings from database drift and failed trials;
   investigate a specific failure before changing the next candidate. Repeat only
   affected measurements after changes; documentation-only edits need no new actors.

Combining both historical cases three times, one positive replay and four live
cells means **eleven actor executions**, before any additional pilots or calibration.
Current $5 replay/$20 live caps total $115 in actor caps for that set; nested review
and judge costs are additional or unknown. Do not automatically run a pilot,
separate targeted live cohort, full rerun and extra replay cohort. Use declared
repetitions, not undeclared retries or extended deadlines to obtain a pass.

## Exact framework scope

- **Native phases:** non-fast-path native remediation requires initial proof bound
  to the base and final proof bound to retained HEAD. Clean fast paths require
  initial proof only and do not count as repair. The candidate now enforces both
  phases for non-fast-path binary runs, with missing/invalid-initial-proof
  regressions; judges retain their independent evidence projection. Live 004
  now declares `binary`. Preserve original observed-contract grades and retain
  observed blocked-outcome coverage in live 001.
- **Coverage versus repair:** `binary` may establish coverage on an exit-2 run
  with remaining findings; it must not imply successful repair. Keep exit 0,
  cleared fixable findings, retained dependency changes and zero final actionable
  findings in the separate `repair` scenario owned by live 002. Do not silently
  redefine `binary` as `repair` or count clean scans as remediation.
- **Evidence and publication:** keep relevant history/tool observations, attempts
  and query scope. Filter verbose traces only if reviewed controls show decisive
  facts survive. Keep literal command checks deterministic and prose procedures
  under semantic review. No arbitrary regex classifier, general capability
  schema, new orchestration layer or actual target publication is required.

## Bloat audit: remove duplication, preserve distinctions

Cleanup can proceed independently where equivalence is demonstrated; it is not a
prerequisite for diagnosing the current actor failures. Finish behavior-affecting
cleanup before freezing a candidate, or remeasure only affected boundaries later.

| Candidate | Bounded task |
| --- | --- |
| Repeated `normloc`/tuple code | Share pure identity/normalization, retaining distinct actionable, ignored and regression coverage rules plus multi-module regressions |
| Source probes and repeated test fixtures | Remove a probe only when behavior proves the same boundary; extract setup that reduces maintenance, not merely file length |
| Nested policy review | Inspect retained independent decisions and existing provider controls. `fix-all.sh:800` triggers another build/scan before the final gate, while `review-prompt.md:25–49` duplicates fix/regression/ignore checks without fix diffs. Consider restricting it to independent policy triage and reusing the authoritative scan only if read-only/retained-tree and gate-order invariants remain valid |
| Repeated docs and stale “subagent” terms | Keep setup in eval README, requirements in testing plan, historical results in live record and implementation tasks here; correct comments when touching code |

Preserve rollback, receipt completeness, native coverage, scoped-ignore, no-fix-credit
and child-exit regressions. Avoid broad parser rewrites, directory renames, a new
reviewer campaign, event system, sandbox or fleet/scheduled eval expansion.

## Current evidence and remaining acceptance

The original audit baseline at `038d0a33` passed 3,046 shell checks, 68 helper
checks and model-free replays 005/007. Preserve those historical results;
implemented policy guards do not establish live enforcement or skill acceptance.
The former release lint override remains incorrect.

The declared candidate protocol is
`.work/fix-go-cves-implementation-20261022/candidate-protocol.json`; it freezes
source hashes, cases and caps. Replay 005/007 integration execution
`simplify-replay-20261022-01` counts as execution 1/3 for each case. Positive replay
`simplify-publication-20261022-01` and live 001
`simplify-live001-20261022-01` are also launched. Their measurements are in progress;
completion, thresholds, whole-reply review and remaining live/repetition coverage
are not yet established. Keep the changing outcome table in the
[implementation results](../evals/implementation-results.md).
