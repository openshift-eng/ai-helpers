# E2E acceptance and simplification

Implementation plan audited by runtime, eval and simplification specialists on
2026-10-22 against `b0368cb8`. No revised runtime, actor or judge was executed.
The [testing strategy](testing.md) owns durable requirements and environment
rules; the [latest matrix](../evals/live/README.md#branch-policy-matrix) owns
historical results. Preserve original artifacts and grades.

## Findings and finish line

The stock pipeline completes execution, collection, extraction, judging,
reporting and regression. Remaining failures concern behavior, evidence and
scenario coverage. The finite treatment map is:

| Boundary | Evidence and planned treatment | Verification |
| --- | --- | --- |
| Command selection | Admiral release replaced inherited `make unit`; let `detect.sh` own defaults and preserve explicit settings unless higher-priority policy overrides them | Existing precedence tests and actual canonical-command receipts |
| Result relay | Admiral release rewrote a Summary line; relay the witnessed terminal result literally | Existing Summary/terminal-exit contract |
| Publication | Successful live replies invented procedures; preserve withheld publication and relay only the complete emitted recipe | Existing command contract, whole-reply negatives and a real positive relay measurement |
| Diagnosis | Correct repairs coexist with unsupported causes; separate observations, available repairs and demonstrated causes | Replays 005/007, reviewed references and causal negatives |
| Scan scope | Subctl replies omitted scope; expose concise phase-specific facts, leaving unsupported native coverage unverified | Evidence-enabled/disabled, clean and blocked paths plus native contract |
| Grading | Some factual majorities accept known errors; check the relevant controls before trusting new labels | Unchanged requirements, calibrated changed grader inputs and whole-reply review |

Track three explicit milestones. **Existing-cohort acceptance** requires both
packaged replays and all four live cases to complete the stock pipeline, pass
configured thresholds and corrected scenario contracts, and pass whole-reply
review. Live 001 may correctly report a blocked run; live 002 must demonstrate a
successful repair; live 003/004 must demonstrate their declared native coverage.
**Replay reliability** requires the existing three-execution comparison for
005/007. **Publication coverage** requires an independently admitted and measured
real positive-recipe replay. Existing-cohort acceptance alone does not establish
complete skill acceptance while reliability, publication or applicable policy
boundaries remain unresolved. Pure cleanup is a separate deliverable.

## Intended design

| Owner | Responsibility |
| --- | --- |
| `detect.sh` | Resolve environment, target configuration and default commands |
| Remediation scripts | Mutate/roll back, run gates, retain results and decide publication eligibility |
| Invoking skill | Apply user/branch policy, launch once, observe completion, relay results and investigate remaining work read-only |
| Eval helper | Independently check execution, retained state and declared scenario evidence |
| Factual judges | Assess diagnosis and advice against captured facts throughout the reply |

Shorten the skill into one ordered procedure. Detection already implements
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

Add a concise scan-scope statement to existing output using available evidence,
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

Address these narrow source findings with focused regressions, separately from
instruction simplification. They are code findings, not observed causes of the
latest actor failures.

| Finding | Required change/check |
| --- | --- |
| Build and license pipelines retain only `PIPESTATUS[0]` (`scan.sh:61,63`; `fix-all.sh:1000–1001`), unlike test-attempt handling | Inject successful commands plus failing `tee`; preserve actual command exit separately and block downstream acceptance when logging/evidence fails. Verify evidence-enabled/disabled paths without adding a general logging framework |
| `review.sh:129–159` accepts requested `stdlib` outcomes, but `fix-all.sh:829–831` drops unresolved keys without dot/slash | Test parent propagation of every admitted key, including `stdlib`; preserve deterministic reasons when attaching valid reviewer detail. Lost detail is proven; a false-clean/publication bypass is not established |
| `review-prompt.md:31–36` permits Go directives at/below builder without repository restrictions in its supplied input | Resolve any applicable compatibility restriction before the affected treatment; carry it consistently through proposed-update/post-tidy guards and reviewer advice. Builder capability cannot override policy |

Do not repair unrelated runtime behavior opportunistically. The existing hermetic
suite is the first check for these changes; a real run must reach a changed path
before claiming live coverage.

## Ordered work and execution budget

1. **Close admission and acceptance dependencies model-free.** Inspect original
   recording 002 for complete logs, a trustworthy literal recipe, compatible pins,
   retained tree/bundle and calibration controls. Record a concrete admission task
   or the specific missing evidence. Its builder-image/recipe criteria do not fit
   the global Admiral backport prompts in `eval-replay.yaml:89–118`: use a compatible
   stock scoring configuration or make shared prompts criterion-conditional and
   recalibrate affected 005/007 controls. Do not invent a backport requirement.
   Failure to admit it leaves publication coverage open, without preventing work
   on the existing cohort. Local-only live remotes cannot fill that positive gap.
2. **Implement the finite treatment map and prerequisites.** Record the competing
   instruction/evidence and exact edit for each boundary above. Map current rules
   to retained requirements, duplicates or justified removals. Simplify command
   ownership and result/diagnosis flow; add only the missing scope handoff.
   Implement the native-phase contract and live-004 expectation changes below.
   Resolve policy before executing an affected live treatment. Extra warning
   paragraphs or another reviewer are not an established remedy.
3. **Verify locally and check the oracle.** Run focused behavioral regressions,
   the shell suite for runtime edits, helper tests and model-free replays. Check
   existing reviewed positives/negatives for causality, publication and scope;
   add a fixture only for a missing distinction. Calibrate changed prompts,
   models or evidence inputs before actor scoring, preserving prior grades.
   Stock majority reduction stays unchanged; three judge samples are not three
   actor trials, and unstable labels remain visible.
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
  initial proof only and do not count as repair. The current contract enforces
  native proof only at its selected terminal phase (`eval.py:623`); initial proof
  is projected to judges (`eval.py:519–527`). Add missing/invalid-initial-proof
  regressions, including the existing terminal-only passing fixture in
  `test_eval.py:1170–1207`. Use the existing `binary` expectation for future live
  004 runs, preserve original observed-contract grades, and retain observed
  blocked-outcome coverage in live 001.
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

## Open boundary and current evidence

Go-minor compatibility policy remains unresolved. Preserve user/repository
restrictions and allowed patch/unrestricted behavior without a global ban or
inferred authorization. The former release lint override was incorrect.

Fresh checks at `038d0a33` passed: 3,046 shell checks, 68 helper tests and stock
model-free replays 005/007 with expected commits/engine exit 2. No fresh actor,
judge or live engine run accompanied the specialist audit. The worker remains
stopped. These facts establish preparation, not acceptance.
