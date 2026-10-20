# Testing and evals

## What is established

Three layers answer different questions:

- **Scripts:** `test/test-lib.sh` passed 2,506 hermetic checks for mutations,
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
2. **Boundary fixtures pass.** The existing shell suite passed 2,506 checks,
   including different original/target refs, detached and absent refs,
   successful/blocked outcomes, clean fast paths and removed empty branches.
   The 52 eval checks cover witnessed publication, tampering, frozen inputs,
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

## Next steps

The bounded-report candidate at `487d0759` failed its first completed 005/007
pair and the separately selected live successful-repair check. Revert its entire
skill treatment, including the extra workflow-ownership sentence: unsupported
claims moved inside the prescribed fields, retry coverage was lost, and the live
reply still invented publication. Keep the prior smaller workflow as the chosen
baseline, without claiming acceptance or comparative improvement. The declared
three-execution comparison remains incomplete; no further wording trials are
selected. [Detailed results](../evals/README.md#multi-failure-replay) preserve raw
samples, native reviews, source revisions and costs.

The unresolved boundary is reliable generation of final advice. Script results,
retained state and literal Summary are independently checkable; neither reducing
the attribution task nor prescribing final report fields made generated advice
reliable. A passing engine and a completed parent do not establish a passing
skill. Existing factual criteria still apply throughout the reply. Further work
needs evidence for a different mechanism, rather than another warning, format,
reviewer loop or repeated trial. No new enforcement framework is selected.

Keep Admiral's checked-in `CLAUDE.md` and imported CVE workflow intact. The legacy
workflow requests manual mutation/verification and a generated publication
recipe. This is genuine competing procedure context, not answer leakage to
remove. `project_hooks: false` does not disable that context; its presence does
not prove it caused the failures. Repository constraints remain distinct from
workflow routing; the Go-minor conflict stays in [decisions](README.md#decisions).

The one live case-002 check now establishes actual source repair and invoking-
agent completion under candidate `487d0759`: all 14 runtime conditions pass,
but the response fails for invented publication. Its scores do not validate the
reverted skill. Runtime script hashes are unchanged, so the engine evidence
remains applicable. Do not rerun this scenario merely to seek acceptance. See
[the live record](../evals/live/README.md#successful-repair-reporting-check).

A future positive-publication relay case would add a distinct decision. Historical
Submariner case 002 still needs a complete sanitized log, verified bundle/archive,
corrected command reference and negatives. Its builder decision needs applicable
outcome/action-owner criteria and matching thresholds through stock configuration,
not the Admiral-only backport criterion or a new judge. Prepare model-free and
calibrate before any measurement; it is not automatically selected.

Native case 003 has separate parent-completion coverage missing after its
43-minute engine success. A source-only repair cannot close it. Any later live
run needs a changed mechanism or concrete current-engine question. Preserve
mutable database misses and different outcomes as missing coverage. Revalidate
ownership/cancellation when recreating the worker, retain supervised lifecycle
management, and keep it stopped between selected runs.

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

Real release-0.24 use exposed a check-selection gap: Admiral's required Go lint
job is separate from the inferred `make unit` command. The skill now instructs
the agent to select relevant local checks before launch through the existing
`CVE_FIX_TEST_CMD`, preserving explicit commands. This changes guidance, not runtime gate
machinery or defaults; unrun CI remains unverified.

Cloud-prepare's real run also exposed test-generated workspace leakage: lint
created root `go.work` and `go.work.sum`, and the retry could no longer resolve
the tools module's mock generator. Each test attempt now removes only those
paths that were absent and untracked before it and remain untracked afterward.
Cleanup precedes evidence recording; cleanup failure stops further verification
while retaining the actual child result. Hermetic orchestration regressions cover
retry isolation, real timeout, existing-file preservation and cleanup/evidence
failures. This addresses workspace lifetime, not the separate lint findings.

Tests now require clean tracked files and the same retained HEAD before and after
each attempt. A changed index, worktree or commit stops before retry or further
gates, retaining diagnostics and any actual child result. Existing exit cleanup
still rolls back tracked changes; this adds no automatic normalization or commit.
Cloud-prepare's canonical branch check adds checksum-only metadata, so its
release-context verification ran in a separate checkout of the same commit.
Those additions alone do not invalidate the unit/lint results or prove a changed
dependency graph. Local checks must carry their required CI environment.

The existing live contract accepts runtime exit 0 or 2 with a completed Summary
or clean-fast-path message. It checks execution, retained state and allowed operations;
fact judges check diagnosis and action/owner. A faithful report of an engine
bug can pass these checks. Scenario-specific runtime assertions additionally
check actual engine evidence rather than the agent's final prose.

Runtime verification now requires all four audit scripts and fresh, complete
counter records. Incomplete evidence stops before repair dispatch; complete
positive counts retain the bounded repair/recheck loop. Existing shell fixtures
cover this boundary, including missing sources, stale output, malformed counters
and publication suppression. The preserved real Admiral audit archive passes the
new validator. These checks establish runtime acceptance behavior, not improved
invoking-agent reporting. Verification now uses those audits directly, without
model calls; the main AI review and shared scanner helpers remain. Visible
poison-provider fixtures check that verification never invokes either CLI, and
persistent findings exhaust the existing repair bound without passing. The
subsequent frozen `87ca7ece` live repair passes all 14 runtime checks and all
51 evidence hashes. Its invoking-agent action/owner samples remain mixed and
the reply supplies replacement publication guidance; see the
[results and judge caveat](../evals/README.md#live-evidence-and-coverage).

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
case when it exercises the changed path. Audit completeness and model-verification
removal use the existing fixtures and eval runner. The existing successful-repair
live case now verifies the changed audit path. This single run establishes neither
invoking-agent acceptance nor native-binary or verification-time repair coverage.

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
