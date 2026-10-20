# Testing and evals

## What is established

Three layers answer different questions:

- **Scripts:** `test/test-lib.sh` passed 2,320 hermetic checks for mutations,
  rollback and gates. Runtime changes need regressions here. `make test` requires
  Go 1.24 or later and fails rather than skips when `CI` is set.
- **Historical replay:** packaged Admiral case 005 runs today's skill over real
  pinned history and recorded scripts/output. Its references and negatives are
  calibrated. All three frozen three-execution cohorts failed. The latest
  recorded contract 2/3 and factual conjunction 2/3; manual publication
  compliance was 1/3 because an indented fence bypassed the guard. Replay
  cannot validate today's remediation engine.
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

## Next implementation slices

Preparation needs no paid calls. The next behavioral change remains unimplemented;
the implemented provenance check protects measurement, not skill reliability.

1. **Define a small reporting treatment against the observed failures.**
   Consolidate `SKILL.md` around observed terminal results followed by qualified,
   read-only diagnosis, preserving retained commit citations and action/owner
   requirements. Omit return advice when the original ref was not observed.
   If retaining that advice, `scripts/fix-all.sh` can print its existing
   `ORIGINAL_REF` beside the Summary's branch; detection stores a branch or
   detached commit hash. This line addresses return advice only. Neither it nor
   literal relay enforces read-only work or proves behavioral improvement.
   Keep the change within existing output and instructions.
2. **Test the changed boundary at the cheapest useful layer.** For a runtime
   output change, extend the existing `detect.sh --setup-branch` and
   orchestrator/PR fixtures in `test/test-lib.sh`: original ref differs from
   target, detached start, absent evidence, and successful/blocked outcomes.
   Assert the reported ref agrees with the start state and that exit codes,
   counts, retained commits and publication prerequisites stay correct. The
   clean fast path has no Summary; a no-commit Summary can name a subsequently
   removed branch. Skipped or unconfigured gates are not passing gates. Keep
   existing publication/mutation regressions. Derived checks of old traces test
   detection, not compliance by a revised skill.
3. **Run a fresh experiment only for an unanswered behavioral question.**
   Freeze the reviewed change, current cases/criteria and tested harness pin;
   stop editing helper/runtime until it finishes. Use case-005 replay for
   interpretation; its historical scripts/log cannot validate a new runtime
   line. Inspect failures before deciding whether live case-001 adds evidence;
   do not automatically progress to live after the same publication or mutation
   failure. Claim blocked-path coverage only if that run actually reaches its
   test blocker. Preserve a different truthful outcome and record missing
   coverage rather than alter findings. Source/native reruns need a relevant
   runtime, completion or environment question. No paid trials are needed for
   this preparation, and adding a return-ref line alone warrants none.
4. **Cover positive publication relay without a new fixture framework.** The
   current check forbids push/PR recipes in backtick fences even when faithfully
   copied; current cases expect none. When implementing positive relay, first
   use the actual command block from historical Submariner case 002 in a focused
   helper fixture. Preserve the complete block, including flags and escaping;
   live reduced evidence currently truncates it, although the full log remains.
   Compare witnessed commands as data, with copied/altered/absent-block checks;
   keep actual publication tool calls forbidden. Admit the full historical case
   only when its additional judgment coverage justifies packaging it. This is
   separate from the no-command treatment; do not invent remotes, a shell parser
   or another reporting schema.

Frozen scoring uses copied inputs/configuration and exact selected cases,
judges and complete samples. Extraction validates that provenance and its
helper hash before changing state/reply files or scheduling factual judges.
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
cancellation probes after recreating the now-stopped worker. One cancellation
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
changes. The first case-005 baseline at source `5079407` completed with contract
3/3 and factual conjunction 1/3: it failed. Its reports are preserved under
`.work/fix-go-cves-next-slice/replay-baseline-20261019/`.
The `9ba32eda` follow-up also failed (contract 2/3, factual conjunction 3/3 by
majority), preserved in `replay-followup-20261019/` beside that directory.
The compact-report cohort at `b8265808` failed too: recorded contract 2/3,
factual conjunction 2/3, but manual publication compliance 1/3. Its reports and
guard probe remain in `replay-report-20261019/`; no failed trial was replaced.
No fourth cohort is planned merely to seek acceptance.

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

Six source recordings remain under `.work/fix-go-cves-evals/source/`; only 005
is packaged. Admit another only when it adds a concrete decision or regression.

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
