# E2E acceptance and simplification

This is the next implementation plan, audited on 2026-10-23 against `7ff963c4`.
It proposes changes; it does not accept the current skill or replace historical
results. The [results record](../evals/implementation-results.md) owns measurements,
[testing strategy](testing.md) owns durable requirements, and
[workqueue investigation](workqueue-race.md) owns that external diagnostic.

## What is actually preventing closure

The stock harness already executes, collects, extracts, judges, reports and checks
regressions. The latest failures expose mismatched responsibilities and incomplete
inputs, rather than a need for another orchestration framework.

| Finding and source | Consequence | Next decision |
| --- | --- | --- |
| `snapshot` freezes cases/config/helper identity, but `prepare` copies current files from `EVAL_ROOT`; YAML hooks resolve current helper paths (`evals/scripts/eval.py`, `evals/replay-base.yaml`, `evals/eval-live.yaml`) | One nominal source group can stage different source bytes; detached worktrees currently supply a manual guarantee | Freeze the minimal execution inputs once and use them throughout |
| `CVE_EVAL_PYTHON` selects the driver, while hooks use bare `python3` and `prepare` embeds its own `sys.executable` | The removed interpreter produced exit 127 and a different interpreter in replay 007 | Select one environment for all stages and fail before actors on mismatch |
| Both profiles deny `git stash*`; `trace_violations` treats all stash operations and all denials as forbidden | Read-only `git stash list` is rejected despite unchanged source and remotes | Correct semantic classification prospectively; keep mutation prevention |
| Replay `backport`/`action_owner` receive annotations and reply, with no outcome criterion or captured observations | A correct backport grade cannot authenticate an extra log citation, count or source claim | Give factual grading evidence and a defined scope without adding a third judge |
| Main skill plus reporting reference is 174 lines versus the original 180 | Mandatory final rereads, exact table grammar and no-derived-count rules create more failure surfaces | Replace these treatments with a short semantic handoff contract |
| `fix-all.sh:run_tests` prints “a test may be flaky”; `review.sh` echoes raw merged model output | The caller receives speculative diagnosis and nested transcripts alongside engine facts | Emit observed attempt outcomes; separate advisory review from observations |
| YAML structural validation accepts aliases/merges, while ignore readers recognize particular line layouts | Accepted policy may be interpreted differently by checks and mutation helpers | Establish semantic agreement before cosmetic parser deduplication |
| Live Admiral repair cleared findings but both test attempts raced; later unpatched controls passed | That cell failed, but a specific patch's efficacy and dependency causality remain unproved | Preserve the failure; use a declared official-source scenario, not favorable-seed retries |

The interpreter incident and source-path issue are separate: pinning packages
alone does not freeze an executable target, and recording a Git revision alone
does not freeze files that later hooks copy.

## Desired ownership

| Component | Owns |
| --- | --- |
| Detection | Effective target configuration, canonical defaults and explicit compatibility restrictions |
| Runtime | Every mutation/rollback, bounded test attempts, deterministic audits, authoritative final scan, license gate, actual receipts, scope and publication eligibility |
| Invoking skill | Target/policy selection, one launch, completion, read-only investigation, useful supported next steps and exact emitted result |
| Eval helper | Independent invocation/state/operation/scenario checks, immutable evidence identity and exact witnessed relay |
| Semantic grading | Factual observations and future advice against supplied evidence, with independent review of known limitations |

Keep the AI work: resolving target policy, identifying applicable repairs and
owners, and deciding useful follow-up. Scripts need not perform speculative root
cause analysis or ask a second model to repeat deterministic verification.

## Ordered implementation

### 1. Settle the contract before changing the actor

Define product failures before another measurement. Wrong retained ref, coverage,
builder, count, quoted error or repair; omitted persistent failure or failed retry;
unsupported causal certainty; missing applicable owner/prerequisite; invented
publication; and unsafe mutation are correctness failures. Keep precise citation
errors recorded; a wrong line number prevents a claim of flawless accuracy, but
does not automatically invalidate a separately scoped backport criterion.

A table versus prose, reference-read order, an accurate derived total, or a harmless
denied inspection is not intrinsically a product failure. “Flaky” after a failed
and passing attempt does not alone assert that a failure predates the update.
Attribution needs evidence when asserted; it need not be a task or mandatory
uncertainty paragraph. Preserve prior grades and their criteria. Record prospective
criterion changes and review corrections alongside them, never overwrite them.

For stash inspection, prefer keeping the broad preventive CLI deny and classifying
only proven read-only denied `stash list`/`show` as harmless in the product contract.
This avoids opening mutation-capable commands merely to reduce false failures.
If runner rules are instead narrowed, change both runner and classifier together
and prove equivalent mutation prevention. Bare/default stash, push/pop/apply/drop,
clear/branch, unknown forms and mutating flags such as `show --output=...`
must remain disallowed; a denied
mutation attempt still fails even when final state is clean. Mixed commands retain
any mutating component. Start with the actual tightly recognized inventory form;
reject output-file redirects, substitutions and external-diff/textconv options,
including `git stash list >go.mod`, rather than assuming every list/show command
is harmless. Do not turn this into a general shell security engine;
unrecognized forms remain reviewable rather than silently authorized.

Controls: actual denied read-only inventory; ordinary status/history; bare and
mutating stash; compound/multiline and `git -C` forms; denied push/cleanup; an
attempted source edit that leaves final state unchanged. Use the existing trace
and operation tests, preserving the historical mutating-stash regression.

### 2. Make the normal runner reproducible and bounded

In `evals/run.sh`, `snapshot`/`freeze_run`, `prepare` and YAML hooks:

- Freeze required current plugin files and helper once into run provenance;
  stage from that snapshot. Rewrite both lifecycle-hook paths and embedded
  deterministic-judge helper paths to it, retaining a minimal layout compatible
  with the helper's `EVAL_ROOT` lookups. Replay combines the historical engine archive with
  the complete frozen current skill; live uses the frozen current runtime. Keep
  generated tools/caches outside the scanned checkout and answers outside actor
  inputs. Do not copy the whole repository or require manual detached wrappers.
- Resolve one absolute virtual-environment interpreter; use it for hooks, staged
  drivers, deterministic judges and stock stages. Preserve the venv entrypoint so
  packages resolve; record its resolved executable/hash, version and package
  identity. Validate child imports, including `CSafeLoader`, before actors.
  Do not silently fall back to another interpreter. Environment ownership belongs
  in the shared runner setup, without vendoring a Python distribution.
- Retain case/helper/skill/runtime/config/CLI/model/harness/tool identities in the
  existing manifest. Detect changed or missing inputs before the next stage.
  Keep credentials out of snapshots. Stable bytes do not freeze live vulnerability
  databases or builder tags; retain their observed identities separately.
- Reject incompatible track/profile/case selection before preparing a real
  checkout. Keep CLI options simple; do not infer live mode from a late failure.
- Reconcile the 3,600-second actor deadline with serial 1,800-second builds/tests,
  retries and scans. Reserve time for bounded cleanup/collection; do not merely
  raise the cap. Verify owned child/container cancellation through the shared
  harness/worker, since killing the CLI alone is not proof of descendant cleanup.

Controls: mutate original skill after snapshot and show both cases still stage
the snapshot; remove/change interpreter and fail before another actor; child
Python mismatch; missing native YAML backend; invalid profile/track; model-free
005/007/002; stalled owned process/container cancellation with partial evidence.
No new campaign service, sandbox, generic plugin preflight or resume engine.
A scoring-only recovery keeps the original failure and unchanged actor hashes;
it does not become an untouched successful E2E run.

### 3. Close concrete runtime gaps before broad cleanup

Use one structural read-only Grype policy decoder, preferably extending the
existing `PolicyLoader`, for preflight and audit entry identity. Equivalent valid
YAML layouts must yield equivalent vulnerability/package/type/location/fix-state
semantics. Alias, merge, inline and package-first policies must not silently
produce zero audited entries. Retain duplicate-key/schema checks. For mutation
layouts that the comment-preserving writer cannot safely change, stop with a
specific review outcome; do not rewrite user policy with a generic serializer.
An eight-fixture model-free counterexample uses the actual structural checker
and audit scripts: all layouts validate, but canonical permanent-ignore evidence
reports one issue while its three equivalent layouts report zero; the same
unknown-fix-state comparison fails in both audit companions. It stubs only Go
version/graph reads against a fixed scan. This proves audit false-clean results,
not a newly executed full remediation/publication bypass. Receipt:
`.work/fix-go-cves-design-audit-20261023/yaml-counterexample/receipt.json`.
This is a demonstrated reader-contract gap, not approval for a broad YAML rewrite.

Cover canonical/equivalent layouts with actionable ignored findings, unrelated
non-Go entries, scoped sibling modules, mixed broad/scoped policy, missing scan
evidence and unsupported mutation layouts. Keep all four independent audit gates.
After semantic parity, remove duplicate entry and pure location/tuple parsing;
do not merge distinct actionable/ignored/regression or multi-module rules.

Finish local command/logger-status parity: `fix-package.sh` still records only
its build pipeline's command status, while several `fix-all.sh` dispatch pipelines
use an aggregate status. Preserve both child and tee exits with the existing local
capture pattern; failed logging must not imply successful evidence or replace the
child's exit classification. Cover command 0/tee 1 and command 2/tee 1. Do not add
a generic command execution framework or make optional native proof mandatory.

The advertised report-only mode also needs a separate preservation fix:
`report.sh` builds with dirty input but only attempts restore for initially clean
input, and ignores restore failures. Reject dirty input before a mutating build,
or use an isolated build checkout with an explicitly defined output policy.
Never auto-stash it. Add a dirty-input preservation and cleanup-failure regression;
this is not exercised by the current fix-only cohort. Add no unrelated report
actors to the eleven-cell measurement.

Replace source-text/layout assertions with meaningful behavior at touched
boundaries when that behavior covers the same requirement; raw assertion count
is not a coverage target. Remove duplicated fixture setup only when it reduces
maintenance without hiding different policy/rollback cases.

Repeated build/scan work is a later measured deletion, not a cache project. Trace
which source/binary/ignore state each scan observes; remove the post-test presentation scan if the immediately following verifier
already supplies its only needed result, and remove the pre-review scan with its
owner. Preserve the authoritative final rebuilt scan after
all mutating phases. Do not memoize by HEAD alone or remove gates to save time.

### 4. Simplify the handoff and runtime output together

Retain target policy, one invocation, terminal completion, immutable-ref discovery
and read-only follow-up. Put the short shared reporting contract in `SKILL.md`:
relay actual exit and complete emitted Summary/recipe unchanged; authenticate
additional facts; give each unresolved issue a supported repair or investigation,
owner and next prerequisite. Include all relevant attempts, including passed
retries. Remote repairs must reach the starting origin branch before rerun;
updated builder images must be published before consumer reruns. Missing gate or
native proof stays unknown; positive artifact-specific proof must not be negated.

Delete mandatory final-read timing, the exact three-part/table/imperative grammar,
verbatim-only evidence cells, universal no-count rule and mandatory causality
paragraph. Delete `references/reporting.md` if the compact contract fits inline;
retain a reference only for genuinely conditional detail. Favor accurate concise
prose, with a table when several issues benefit. Keep the deterministic exact
Summary/publication checks; do not build a new report renderer or schema.

Replace the engine's speculative retry warning with actual first/retry exits.
Investigate relevant failing packages, not a universal enumeration of all passing
packages. Preserve original historical logs: new runtime wording does not change
what recorded replay actors receive.

Prefer removing the nested reviewer after making its publication semantics explicit.
It is not currently just advisory: `fix-package.sh` can emit a successful indirect-
repin caveat without setting a deterministic blocker; reviewer `UNRESOLVED` alone
can then veto publication. Inventory every `NEEDS_REVIEW` origin. Preserve real
compatibility/security decisions as deterministic typed blockers; decide explicitly
whether a successful repair's repin caveat is advisory. Existing audits must not
be assumed to subsume every reviewer veto.

Use existing response fixtures to inventory the absent/resolved/unresolved/
contradictory/malformed branches; do not build new tests for a parser slated for
deletion. Retain post-removal behavioral regressions for deterministic blockers,
successful primary repair with failed indirect repin, ignored/advisory siblings
and a poison provider proving the removed model path is not called. Once deterministic
semantics are complete, delete the nested invocation, pre-review rebuild/scan,
provider retry machinery and outcome parser together. The outer agent owns advice.
If an independently necessary review decision remains, retain only that scope and
archive raw output separately; expose validated advisory reasons rather than
embedded tool transcripts. Do not implement a temporary review-output framework
as a mandatory step toward deleting the reviewer.

### 5. Repair the oracle's evidence boundary

Replace replay's overlapping `backport` judge with `outcome`, retaining backport
availability/remote landing under `action_owner`: still two semantic judges with
three samples each. Reuse the existing extract/evidence projection to supply
independent historical outcome witnesses and captured tool observations. Do not
use the reply's own Summary as authentication or supply hidden expected answers
to the actor. A raw nested-review transcript remains a claim, not a tool event.

Define each field's scope: outcome owns past/present facts throughout the reply;
action/owner owns supported future repair, ownership and prerequisites. Move
past-causality/attempt/source-accuracy requirements out of A's current catchall
annotations into O, while preserving usable backport semantics in A. Controls
must separate false past cause with valid action (O false/A true), missing owner
(O true/A false), and a wrong proposed repair target (A false). A judge
cannot validate a new source/history claim absent the relevant observation; mark
that limitation for independent review rather than assuming it true or false.
Start with decisive observations, full relevant package attempts and independently
captured target configuration. Publication's compact witness omits its finding
IDs; add the trusted observed ID list and an invented-ID negative rather than accepting an unsupported
extra claim as merely uncontradicted. Keep raw logs/traces available for review; do not
add another lossy evidence store or dump unlimited transcripts into every prompt.

Controls: exact recipe versus altered target; right/wrong package-result citation;
all retry outcomes; correct origin landing; correct/wrong builder owner; positive
native proof versus genuinely unknown scope; contradictory overview; accurately
supported counts; optional presentation changes. In the actual 007/corrected
pair, change only the wrong line citation and keep “flaky” constant; this tests
factual grounding without reinstating adjective/style rejection. Keep some reviewed controls untouched while changing
the rubric, and retain disagreements and sample errors. Selected controls cannot
establish general grader reliability. Do not add more judges or rejudge to obtain
a favorable majority. Model-free admission must also check duplicated annotated
Summary and literal log witnesses against the packaged recording, stripping only
the admitted wrapper marker/substitutions; frozen files can still contradict each
other. Whole-reply review remains necessary.

## One acceptance campaign, after local closure

No new actors are selected by this planning change. Complete local semantic,
operation, staging/interpreter, preservation and oracle controls first, then freeze
one implementation and its criteria. Select and record an official upstream pin
with a real actionable dependency repair before the campaign. The existing
Admiral pin may be retained under a concrete changed implementation/question, or
a new justified official pin may be admitted; neither outcome is guaranteed.
The [race evidence](workqueue-race.md) does not require one specific upstream patch
to land before any new measurement. Never inject the local patch, remove race
checks, change the scenario to observed-only, or retry for a favorable seed.

Use a single maximum eleven-actor campaign: 005 and 007 three executions each,
positive 002 once, and the four live cases once. Initial 005/007/002 pilots count
as the first three members, not an additional campaign. Existing caps total $115
(seven replay actors at $5, four live at $20); nested/judge costs remain separate.
Remove the old nine-actor campaign followed by a duplicate eleven-actor cohort.
Compare component identities, not Git revision alone: documentation-only commits
need no actors, while changed runtime/profile/case/environment invalidates its
affected evidence. Declare any reuse before launch and its exact scope.

For **full fixed-cohort E2E**, require original stock stages to complete, all
configured thresholds and independent scenario checks to pass, every required
sample to exist without errors, and whole-reply review to find no unsupported
substantive fact or missing required handoff. Live 001 can block correctly; 002
must actually repair with canonical gates; 003/004 must prove declared native
artifact/phase coverage. Preserve minor accuracy details explicitly; never call
a flawed reply flawless. Harmless presentation drift is not a disqualifier.

Stop on safety/integrity failure or a substantive failure that disqualifies that
all-pass milestone. A separate predeclared two-of-three semantic comparison may
continue after a first semantic failure only if that narrower question remains
open; do not claim it establishes all-cells acceptance. Call three executions a
fixed-fixture repeat check, not statistical reliability or unseen-repository
coverage. Preserve every failed source group and original grade. No automatic
next prompt variant, favorable-seed rerun or adaptive cap increase follows failure.

## Documentation and deferred work

Keep setup/commands in eval README, requirements in testing, decisions/next work
here, outcomes in the results record and unique historical grades where recorded.
Trim repeated status/history and counter lists; plans/README is an index plus
truly deferred issues. Do not delete unique failure evidence or create another
parallel planning document. Scratch expert audits and the model-free snapshot
inspection are under `.work/fix-go-cves-design-audit-20261023/`.

Defer a broad Bash/Python rewrite, directory/test-suite churn, general shell
policy engine, fleet/scheduled evals, additional recordings, automated campaigns,
publication execution and generic caching. Preserve rollback, scoped ignores,
no-fix credit, compatibility policy, native identity and fail-closed evidence.
