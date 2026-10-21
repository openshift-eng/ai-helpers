# Testing and evals

## What is established

Three layers answer different questions:

- **Scripts:** `test/test-lib.sh` passed 2,787 hermetic checks for mutations,
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
2. **Boundary fixtures pass.** The existing shell suite passed 2,787 checks,
   including different original/target refs, detached and absent refs,
   successful/blocked outcomes, clean fast paths and removed empty branches.
   The 53 eval checks cover witnessed publication, tampering, frozen inputs,
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

### Fix demonstrated engine gaps first

Implement the three [prioritized changes](README.md#next-changes) separately:
validated single-scan reports, scanner deadlines, then preservation of inherited
ignore policy with reliable read-only YAML parsing. Reproduce each defect in the
existing shell suite before fixing it. Include passing controls and check exit
status, retained HEAD/files and suppressed publication, not just diagnostic text.
Historical replay uses historical scripts and cannot validate these fixes.

Keep the source repair and final advice acceptance decisions separate. The latest
case-004 follow-up preserves the canonical command and exit-2 result: two lint
attempts failed with 43 issues across three linters; unit remained unrun because
of `&&`. The retained commits change only dependency/policy files. Both base and
result declare Go 1.26.0; Admiral's different Go-directive experiment does not
attribute this failure. Independent archived-evidence review verifies the native
scan and four audits; case 004's stock runtime check does not assert these.
The reply overstates causal independence and miscounts linters. Contract
passes, outcome is true 3/3 and action/owner is false/true/false. Neither a blocked
run nor a passing factual sample establishes correct advice. The
[live record](../evals/live/README.md#subctl-release-check) preserves both runs.

### Establish what the evaluator can distinguish

Recorded tool observations now expose the real history citation and its `--all`
query without agent prose or reasoning. All 13 stock-render checks pass. Keep this
accurate context: omitting it caused a judge to call a real commit fabricated.
The separate action/owner calibration still fails: the reviewed reference and
the untouched actual negative are both accepted 3/3. More context is not evidence
of reliable grading, and these are repeated judges on replies, not independent
skill executions. Original scores remain unchanged.

Two model-free controls are prepared from the reviewed reference: one changes
only causal qualification, the other only whether `--all` proves default-branch
membership. Local provenance is retained under
`.work/fix-go-cves-release024/quality-plan-audit/oracle-controls/manifest.json`;
these controls are not corrected actor results. The positive retains useful
diagnosis, all three diagnostic classes, both attempts, owners and remaining verification. Independent review approves the
causal false label under the existing criterion. Membership alone is outside its
explicit causal rule; keep that control manual/exploratory rather than silently
expanding the criterion or adding a judge.

If a calibration is selected, freeze the positive/causal-only pair and run three
samples each through the existing stock scorer, with unchanged criteria/model.
Require all six expected labels, no errors and evidence-supported rationales;
calling an observed commit fabricated is still a failure. Stop after that set,
without adaptive retuning or retries. Passing this deliberately clear pair would
show only that distinction. It would not resolve false acceptance of the actual
reply or validate general grading, actor improvement or the skill. Preserve that
actual negative as an acceptance check; independent whole-reply review remains
necessary. No scoring campaign or additional model trial is selected by this audit.

### Select a different behavioral mechanism before another live run

Literal Summary relay is implemented, followed by read-only diagnosis. The smaller
workflow remains unaccepted. The bounded-report treatment at `487d0759` failed
005/007 and a live successful-repair reporting check: unsupported claims moved
inside its fields, retry coverage was lost and publication was invented. It was
reverted. More warnings, prescribed fields or repetitions of that treatment have
no demonstrated benefit. [Detailed results](../evals/README.md#multi-failure-replay)
retain failed and incomplete trials, source revisions and costs.

A candidate experiment is diagnosis in a fresh context over completed, frozen
artifacts. Treat execution-context interference as a hypothesis, not an established
cause: shorter replay contexts also failed. Before selecting it, verify the
existing tool can evaluate this component. Predeclare the same diagnosis task,
complete runtime/investigation inputs and repository instructions for treatment
and comparator, and record added latency/cost and supported hosts. Preserve
useful source/history analysis and prerequisite advice. Silently
reducing the product to Summary-only reporting is not acceptance.

Use case 005's supported repair, case 007's distinct failures/retry, and the latest
Subctl case's unconfirmed attribution. Freeze witnesses and review the whole
reply manually; the current judge cannot be the sole oracle. A component pass
would justify a full invocation test, not acceptance by itself. Stop if the same
errors persist. Do not add a permanent reviewer loop, new user command or context
routing framework before showing a benefit. No production mechanism or new actor
run is selected yet. The optional operational Summary handoff in the main plan
has separate human value and does not solve unsupported causal prose.

Keep checked-in repository instructions, including Admiral's `CLAUDE.md` and
imported CVE workflow. They contain genuine competing procedure context, not
answer leakage to remove. `project_hooks: false` does not disable that context;
its presence does not prove causation. Resolve the Go-minor compatibility policy
separately in [decisions](README.md#decisions), without removing repository policy
or installing a natural-language policy parser.

### Close distinct E2E coverage after relevant changes

Use the existing stock runner and scenario-specific runtime assertions:

- Validate changed engine paths with hermetic regressions first, then a real case
  that actually reaches them. A clean scan does not exercise a repair or invalid
  inherited-policy rejection. Resolve the Go-minor policy before measuring that
  behavior. Do not hand-repair target repositories to obtain a passing result.
- Admit historical case 002 only for the distinct positive-publication relay and
  builder-owner decisions. Prepare the sanitized complete log, verified archive,
  corrected reference and negatives model-free. Calibrate before behavioral
  measurement using applicable stock criteria and thresholds, not Admiral-only
  backport requirements or a new judge.
- Close native case 003's missing invoking-agent completion after its recorded
  engine success only with a changed mechanism or concrete current-engine
  question. Likewise, exercise the missing-fork diagnostic on an actual success
  path; the blocked Subctl follow-up never reached it. Local-only remotes can
  legitimately withhold a PR recipe; do not invent a GitHub fork to force one.

Mutable database misses remain missing coverage. Preserve source revisions,
commands, evidence and costs; do not rerun a successful engine merely to seek
accepted prose. Revalidate worker ownership/cancellation when recreating it and
keep it stopped between selected runs. Do not expand to all repositories,
per-run baseline testing, automated campaigns or target draft updates until the
relevant result is independently correct and produced by the skill.

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

The test gate keeps command and logger statuses separate. Logging failure stops
retry and downstream gates after workspace cleanup. Observed command results are
retained before later diagnostics; an interrupted retry inherits neither the
previous result nor its output. Exit cleanup preserves successfully saved
receipts and records completed attempts whose earlier evidence write failed.

Tests now require clean tracked files and the same retained HEAD before and after
each attempt. A changed index, worktree or commit stops before retry or further
gates, retaining diagnostics and any actual child result. Existing exit cleanup
still rolls back tracked changes; this adds no automatic normalization or commit.
Cloud-prepare's canonical branch check adds checksum-only metadata, so its
release-context verification ran in a separate checkout of the same commit.
Those additions alone do not invalidate the unit/lint results or prove a changed
dependency graph. Local checks must carry their required CI environment.

Final checks also require the retained HEAD and clean tracked state captured
after verification. A change during the reviewer refresh, final rebuild/scan or
license check blocks publication through the existing policy gate, preserving
the actual check results. The separate snapshot accepts earlier policy-only
commits; checked index/worktree status catches changes hidden by an aggregate
diff. This adds no automatic normalization or new evidence schema. A zero-finding
initial scan also requires unchanged tracked source and HEAD, checked before
generated-file normalization can erase a change. Normal remediation retains its
existing generated-file handling.

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
runtime fix in the [prioritized changes](README.md#next-changes), rather
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
