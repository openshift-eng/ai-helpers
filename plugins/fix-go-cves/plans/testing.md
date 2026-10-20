# Testing and evals

## What is established

Three layers answer different questions:

- **Scripts:** `test/test-lib.sh` passed 2,343 hermetic checks for mutations,
  rollback and gates. Runtime changes need regressions here. `make test` requires
  Go 1.24 or later and fails rather than skips when `CI` is set.
- **Historical replay:** packaged Admiral case 005 runs today's skill over real
  pinned history and recorded scripts/output. Its references and negatives are
  calibrated. The first three frozen comparisons failed. The first literal-report
  comparison was incomplete after an SDK-event parsing error. The revised
  comparison passes contract and factual conjunction in all three executions;
  manual wording caveats remain separate from those scores. Case 007 is
  admitted and calibrated, but both comparisons fail: the first has contract
  2/3 and factual conjunction 0/3; the follow-up has contract 3/3 and factual
  conjunction 1/3. Replay cannot validate today's remediation engine.
- **Live evaluation:** real Grype and canonical commands establish Admiral
  source repair (14 runtime assertions) and Subctl native repair (19), both
  with engine exit 0. Skill execution remains unaccepted: Admiral invented
  publication; Subctl exhausted its parent budget without a completed reply.
  A refreshed blocked Admiral run retained valid exit-2 evidence, but performed
  temporary cherry-pick/cleanup mutations. Its original contract missed these
  writes; action/owner failed unanimously. Separate derived checks correct
  guard gaps without replacing original scores.

[Eval setup and replay results](../evals/README.md) and the
[live results](../evals/live/README.md) retain the detailed evidence and costs.
The same-builder reporter experiment established that raising only the Go
directive activates the current vet failure. The source defect pre-existed;
that does not establish that the failure was unrelated to the update. It does
not attribute the historical run or replace a full baseline test suite.

## Reporting and E2E status

1. **Reporting is implemented.** `SKILL.md` quotes the completed terminal
   result, then gives evidence-qualified, read-only diagnosis. Return advice
   needs observed original-ref evidence; `fix-all.sh` exposes its existing
   branch or detached ref in the Summary. Recommendations focus on the next
   unmet prerequisite and verification still needed. This is a behavioral
   treatment, not enforcement or proof of general reliability.
2. **Boundary fixtures pass.** The existing shell suite passed 2,343 checks,
   including different original/target refs, detached and absent refs,
   successful/blocked outcomes, clean fast paths and removed empty branches.
   The 47 eval checks cover witnessed publication, tampering, frozen inputs,
   native event shapes and preserved failures. Skipped/unconfigured gates are
   not passing gates; old-trace rechecks prove detection, not revised behavior.
3. **Selected replay behavior is measured.** At `07515259`, case-005 passes its
   deterministic contract and both factual judges in all three executions,
   with agreeing samples and no errors. It retains actual outcomes without
   mutation, publication recipes or guessed return advice. Manual review still
   found overconfident future-result wording. A subsequent affirmative
   prerequisite-to-verification clarification is source-reviewed, not measured
   by those replays. The fresh live case-001 at `a6c8e5a0` verifies reporter,
   original-ref and completion evidence on today's engine: contract passes and
   outcome is true 3/3. Action/owner is false 3/3 for unsupported causality about
   a first-only syncer failure; no judge errors. Read-only behavior is preserved.
   The distinct-failure clarification is now measured by case 007 and still
   yields unsupported causal synthesis; see the comparison below.
4. **Positive publication detection is covered.** A small real historical
   Submariner command fragment exercises exact recipe/Summary relay and
   altered/extra/absent witnesses. Replay uses frozen logs; live logs are hashed
   at completion. Actual publication tools remain forbidden. This does not
   establish positive relay by the invoking agent; full case-002 admission
   remains conditional on useful additional judgment coverage.

Keep the first literal-report comparison incomplete: two scored passes and a
third extraction failure. A separate frozen, model-free recheck handles that
native event correctly and retains the strict-policy denial as a false contract;
it does not replace missing original scores. All original records and manual
caveats are retained in the [eval results](../evals/README.md#current-reporting-implementation).

## Next prepared experiment

The next question is whether the skill diagnoses **each distinct failure** from
the same real run without treating a passing retry as causal evidence. Case 005
lacks the first-only syncer failure; another execution of it cannot answer that
question. Fresh live case-001 may not reproduce that intermittent failure.

1. **Case 007 is admitted.** It preserves the full two-attempt log, recorded
   plugin and `aaaeea3` bundle from `cve-live-admiral-reporting-20261020`, whose
   sole parent is the pinned base. Independent review verified ancestry, facts,
   reference/negative, sanitization and absence of answer leakage. The unchanged
   helper completed model-free replay with expected exit 2 and clean retained
   state. Original evidence and case 005 remain unchanged.
2. **Reference calibration passed.** The stock factual judges received the
   actual rendered annotations and reply, including recorded Go/x/tools facts.
   All 12 samples agreed without errors: `backport` passes both replies;
   `action_owner` passes the uncertainty reference and rejects the retry-causality
   negative. The reference's directive explanation passed without requiring a
   compiler replacement or new baseline run. Prompts/model/criteria were not
   weakened. See [fixture provenance](../evals/cases/case-007/calibration.md).
   This calibrates the oracle, not skill behavior. Preserve raw results and the
   original live failure; change a rubric only if calibration demonstrates a defect.
3. **Both frozen comparisons failed.** At `0fdccbb0`, contract passes 2/3 and
   factual conjunction 0/3. At `d9261b68`, contract passes 3/3 and factual
   conjunction 1/3. Preserve all raw samples and original failures; the one
   follow-up pass is not overridden by manual precision caveats. Manual review
   finds two follow-up replies omit the distinct syncer failure, one truncates
   the literal Summary and one asserts changed tooling without comparing the
   actual base. Revert the two-line remaining-work treatment; this bounded
   comparison does not establish a general causal treatment effect or acceptance
   of the earlier wording. See [results](../evals/README.md#multi-failure-replay).
4. **Retrieval measured; this experiment branch is stopped.** At `f3b12fd3`,
   the selected 005/007 three-run comparison stopped after one completed pair.
   Case 007 retrieves both failures and retry outcomes, but its overview still
   makes unsupported global causal/repair claims. Preserve the raw majority
   factual pass and manual failure separately. Case 005's original contract
   false is a checker defect: a historical capture-status line was wrongly
   required inside its otherwise complete engine Summary. Correct the shared
   recording/authorization boundary and verify it model-free; do not rewrite
   prior scores or rerun actors merely to fill the declared count. See
   [results](../evals/README.md#multi-failure-replay).
5. **Validate the known oracle gap.** The existing action/owner criterion
   already rejects unsupported causal claims, but its judge accepted a global
   overclaim despite later uncertainty. Add one focused contradictory-overview
   negative and clarify whole-reply scope in that existing prompt. The single
   calibration at `eb44d2f1` passes all 21 samples without errors: both references
   accepted and five negatives rejected, three samples each. Raw samples and
   earlier mixed verdicts remain preserved; no tuning/retry loop was needed.
   This calibrates seven oracle examples, not skill acceptance or a revised
   factual score for the natural retained reply. Further skill work needs a design
   that prevents unsupported synthesis after evidence has been retrieved; another
   search, warning or
   prompt heading does not address the demonstrated mechanism. Keep literal
   Summary, each attempt, actual base-to-result evidence and whole-reply causality
   in manual review. Current-engine repair and native completion remain separate.

Positive publication relay is the next distinct candidate, not a prerequisite for
this experiment. Historical Submariner case 002 needs a complete sanitized log,
verified bundle/archive, corrected literal command reference and negatives. Its
builder decision cannot use the current Admiral-specific backport judge: choose
applicable outcome/action-owner criteria and matching thresholds through stock
configuration support, rather than inventing a backport requirement or another
judge. Verify
model-free preparation and calibrate before measuring it.

Further live work needs a concrete current-engine, successful-repair or long-run
completion question. Existing live case-002 can measure completed successful-repair
reporting without invented publication; local remotes still cannot prove positive
PR-command relay. Case-003 can measure native invoking-agent completion after the
wait-cadence change, preserving the earlier budget failure and established runtime
evidence. Do not automatically run both. Neither a clean run nor another mutable
blocked run is a substitute for the prepared multi-failure regression. Claim blocked coverage only
when reached, and preserve database drift or different outcomes as missing
coverage. Keep the worker stopped during preparation. Revalidate the existing
ownership/cancellation probes if it is recreated; retain supervised lifecycle
management for selected live runs.

Frozen scoring uses copied inputs/configuration and exact selected cases,
judges and complete samples. Extraction checks all collected case directories
against the frozen selection, then validates outputs before factual scoring.
Provenance, helper identity and case membership are checked before rewriting
state/reply files; missing or extra cases stop the scoring hook.
A changed helper requires a separately frozen derived record; preserve original
outputs and scores. The tightened action/owner criterion passed seven
three-sample checks (21 calls); the unchanged backport criterion passed six
earlier reference/negative samples. All matched expected labels without errors;
failed earlier calibrations remain evidence. Recalibrate if criteria or judge models
change, rather than adding judges for the observed reporting failures.

## Runtime and behavioral acceptance

The existing live contract accepts runtime exit 0 or 2 with a completed Summary
or clean-fast-path message. It checks execution, retained state and allowed operations;
fact judges check diagnosis and action/owner. A faithful report of an engine
bug can pass these checks. Scenario-specific runtime assertions additionally
check actual engine evidence rather than the agent's final prose.

| Scenario | Required runtime evidence |
| --- | --- |
| Existing blocked Admiral case | Real execution and retained result; actual test blocker and scan outcome, with accurate advice and no follow-up mutation |
| Successful repair | An initial actionable finding, a retained dependency repair, canonical tests and audits passing, valid authoritative final scan with zero actionable findings, runtime exit 0 |
| Native binary | Fresh build from the tested tree, binary hash and `go version -m` metadata, positive catalog/coverage evidence even with zero findings, canonical gates after remediation, and rebuild/rescan after applicable changes |

Report measurement completion, behavioral verdicts and runtime scenario coverage
separately. A no-findings fast path can be valid behavior but does not exercise a
repair. A source-only scan, stale or opaque binary does not establish native
binary coverage. Native coverage does not prove stdlib remediation unless a
stdlib finding is actually repaired. Database drift may remove the candidate's
actionable finding; record the missing coverage and choose a suitable new pin
deliberately. Do not fake findings, stub tools, skip canonical gates or add broad
ignores to qualify.

The local origin/fork remotes prevent publication. They also mean that even a
successful runtime may correctly emit no GitHub PR command. Keep that limitation
explicit; do not invent fork URLs to force one. Existing hermetic PR rendering
coverage and eventual skill relay coverage are separate from proving repair.
No eval should push changes or create a PR.

## Environment, evidence and deadlines

Use the tested shared harness revision
[`1a980e707909a23f8c143ce333d97f5203db34ab`](https://github.com/opendatahub-io/agent-eval-harness/tree/1a980e707909a23f8c143ce333d97f5203db34ab)
for the next implementation checks; revalidate integration before changing it.
Record actual runtime/helper contents as well as staged wrapper hashes, case
pins, CLI/model/harness settings, scanner path/version/hash or container digest,
Grype database identity/status, and actual builder image/compiler identity.
The observed live scanner was v0.121.0 while the runtime fallback is v0.112.0;
record what executed. Cache reuse does not freeze the database or builder. Keep
identity metadata, not a vendored database or image archive.

Package-bearing runtime tools, caches, logs and evidence must remain outside
the scanned tree; a real Grype probe demonstrated that `.git` does not exclude
them. The source-only staged plugin and driver retain the stock runner layout.
Fresh HOME, local remotes and permission/trace checks are not host isolation. Before an
unattended or broader campaign, use disposable build resources through the
shared harness/worker environment. A container with the host Docker socket
still lets canonical repository cleanup affect host resources. Verify that
Dapper, scanner/database access, network and model credentials work in the
chosen environment; do not implement a plugin-specific sandbox.

The successful supervised worker also entered its dedicated rootless daemon's
user and mount namespaces: UID 0 there mapped to the host task owner, preserving
ownership through Dapper. Merely exporting `DOCKER_HOST` had left subuid-owned
files and broken Git. Reuse the actual Dapper ownership and partial-evidence
cancellation probes after recreating the worker. One cancellation
left a container requiring targeted operator cleanup; unattended teardown is
still unproven. Keep worker lifecycle in the shared environment and retain
operator-owned cleanup, without another plugin preflight layer.

Exercise timeout/cancellation and retention of partial evidence in that
disposable environment before unattended runs. Parent time/budget limits do
not account for all nested reviewers and judges. `CVE_FIX_SCAN_TIMEOUT` is not
currently enforced uniformly across scanner and database calls; keep that
runtime fix in the existing [operations plan](README.md#operations), rather
than claim the configured value bounds every scan. Record environment failures,
operator stops, elapsed time and available costs separately from model behavior;
observed violations remain evidence even when a trial is stopped.

## Acceptance rounds and expansion

Freeze case membership, criteria and configuration before comparing skill
changes. Original comparison scores, revisions and retained report locations
belong in the [eval results](../evals/README.md#current-reporting-implementation).
Keep failed trials and separately label corrected-guard rechecks. A fresh
comparison needs a changed behavioral question, not another attempt to get a pass.

For a declared replay comparison, the existing rule requires its deterministic
contract in all three independent skill executions and all factual criteria
together in at least two. An individual failed execution still exits nonzero;
the three-execution rule is a separate comparison, not a per-run threshold. Inspect each case, not pooled rates. Three judge samples on one reply
are not three skill executions. This is not statistical confidence or a new
campaign command. Preserve every trial and original score; corrected guard
re-verification needs a separate provenance record and no paid skill rerun.

Do not mechanically run three expensive live trials against changing external
state. Establish actual successful-repair and binary evidence after the relevant
changes; rerun to resolve an identified failure or environment change. Recalibrate
judges when their prompts, models or fixtures change. Missing cases, samples or
verdicts are errors, never passing evidence. Avoid an automatic extra-six-run
rule for borderline scores or repeated attempts merely to obtain a pass.

Live failures feed the faster layers: engine bugs get hermetic regressions and
interpretation errors get replay cases. Existing no-fix marker, major-version
and Kubernetes-identity fixes remain independent work in the
[main plan](README.md#next-changes). Validate each with the shell suite and a real
case when it exercises the changed path. Harden audit completeness before
removing model verification; that removal does not need its own eval framework.

## Historical follow-ups

Of the six original recordings under `.work/fix-go-cves-evals/source/`, only 005
is packaged. Case 007 comes from the later live capture. Admit another only when
it adds a concrete decision or regression.

| Case | Recording | Admission work |
| --- | --- | --- |
| 001 | Lighthouse license | Correct cdc3003 backport advice to repair the remote target before rerunning |
| 002 | Submariner partial | Preserve PR relay and the owner of the builder-image decision |
| 003 | Cloud-prepare clean | Check that flagged lines need no action; heavier live success alternative |
| 004 | Subctl `bin/lichen` | Correct the reference and resolve the empty binary contradicting the log |
| 005 | Admiral govet | Packaged and calibrated; preserve the failed baseline and compare the focused skill revision |
| 006 | Lighthouse x/crypto | Correct no-fix and license-backport advice |

Case 004 must cover all three blocked bumps: x/net, grpc and otel/sdk. Case 006
has no remaining x/crypto finding after the no-fix ignore of GO-2026-5932;
inventing further x/crypto action, a Go raise or a team decision must fail. Its
license failure also needs 001's remote-target backport advice. Keep Go-raise
policy scoring neutral until the conflicting repository/plugin policy is
resolved ([decisions](README.md#decisions)).

Package needed logs, references, negatives, inputs, annotations, bundle commits
and historical scripts. Sanitize home paths and omit raw recording transcripts
with unrelated connector or memory metadata. Add binary/report evidence only
when the case requires it. These recordings helped tune the skill and measure
regression, not generalization. Defer fleet coverage, scheduled canaries, CI
campaign automation and direct reviewer evals until a concrete gap warrants them.
