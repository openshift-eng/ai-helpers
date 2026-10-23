# E2E acceptance and simplification

This is the next implementation plan, audited in four critical waves (twelve
specialist passes) on 2026-10-23 against `a41c98a6`.
It proposes changes; it does not accept the current skill or replace historical
results. The [results record](../evals/implementation-results.md) owns measurements,
[testing strategy](testing.md) owns durable requirements, and
[workqueue investigation](workqueue-race.md) owns that external diagnostic.

## What is actually preventing closure

The stock stages already execute. Current gaps are measurement authority,
execution identity and handoff semantics, plus independent runtime safety defects:

| Boundary | Evidence |
| --- | --- |
| Frozen source/interpreter | Preparation still copies current files; bare-Python hooks drifted during the recorded exit-127 incident |
| Frozen grading authority | A copied failed repair archive passes after only collected expectation downgrade; controlled phase/native contradictions also pass |
| Artifact identity/preservation | Modes/links escape snapshot identity; actual helpers delete changed ignored output and an outside target through a parent link |
| Checkout/publication ownership | An explicitly switched checkout is reset; recipe construction uses owner/first-URL inference |
| Grading/handoff | Replay lacks a grounded outcome role; reporting rituals and nested speculative text add avoidable failure surfaces |
| Other runtime findings | Accepted YAML layouts disagree in audits; report preservation/logger gaps are separate from the current fix-only cohort |

Controlled checker counterexamples are not observed actor exploits or malformed
producer output. Function proofs are not full remediation executions. The linked
results and scratch receipts retain those distinctions and original grades.

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

## Scope and order

Distinguish three kinds of work below. **Measurement prerequisites** must be ready
before interpreting a new actor run. **Runtime safety obligations** must be fixed
or explicitly left open before claiming general release readiness; the existing
fix-only cohort does not exercise every one. **Optional deletions** need their own
proof but must not hold all E2E progress hostage. These are labels on work, not a
new campaign framework.

Choose the implementation being measured, finish its relevant local controls,
then freeze it. Do not require report-only repair, parser cleanup and reviewer
elimination merely to test a corrected replay oracle. If runtime fixes are included,
remeasure affected live paths; if deferred, keep the narrower cohort claim and
release obligations visible. One all-pass cohort is not universal runtime safety.

The preferred architecture remains Bash transaction orchestration, existing
receipts and four independent audits, with the existing Python policy-loader
boundary for semantic YAML. A wholesale Python orchestrator, new result schema,
transaction service or plugin sandbox has no demonstrated advantage here.

## Ordered implementation

### 1. Settle the measurement contract before changing the actor

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

Keep the broad preventive CLI deny if useful, but prospectively classify the
actual proven read-only denied inventory form separately from mutation attempts.
Keep the denial visible. Start narrowly rather than building a list/show option
parser: mixed mutations, file-output redirects (`git stash list >go.mod`),
substitutions and external-diff/textconv options must not inherit a benign verdict.
Unknown forms remain conservative. An attempted source edit or mutating stash
still fails even when denied or final state is clean. Cover the actual inventory,
ordinary status/history, `git -C`, multiline/mixed commands and mutate-then-restore
in existing operation tests. Do not turn trace heuristics into a shell sandbox.

### 2. Close measurement provenance and validator gaps

In `evals/run.sh`, `snapshot`/`freeze_run`, `prepare` and YAML hooks:

- Freeze required current plugin files and helper once into run provenance;
  stage from that snapshot. Rewrite both lifecycle-hook paths and embedded
  deterministic-judge helper paths to it. Retain the `fix-go-cves` plugin basename
  and normal relative layout: the shared harness reuses its prepared plugin by
  basename, including the invocation shim. A generic `provenance/plugin` basename
  can stage another plugin and bypass that shim. Replay combines the historical engine archive with
  the complete frozen current skill; live uses the frozen current runtime. Keep
  generated tools/caches outside the scanned checkout and answers outside actor
  inputs. Do not copy the whole repository or require manual detached wrappers.
  A model-free control must exercise the shared staging function, resolved CLI
  plugin argument and intended shim, checking the same prepared plugin/skill bytes.
  Confirm actual model skill intake in the existing pilot trace, without adding
  an actor just to prove staging. Preserve existing distinct baselines for
  intentionally generated shims, historical-engine/current-skill replay and the
  unwrapped live runtime; do not compare every prepared byte to raw source.
- Resolve one absolute virtual-environment interpreter; use it for hooks, staged
  drivers, deterministic judges and stock stages. Preserve the venv entrypoint so
  packages resolve; record its resolved executable/hash, version and package
  identity. Validate child imports, including `CSafeLoader`, before actors.
  Do not silently fall back to another interpreter. Environment ownership belongs
  in the shared runner setup, without vendoring a Python distribution.
- Retain case/helper/skill/runtime/config/CLI/model/harness/tool identities in the
  existing manifest, including source file kind and relevant execution mode.
  Reject unexpected source links rather than silently omitting them; intended
  venv/tool links remain separately identified. Migrate baseline, completion,
  capture and native-retained-SHA consumers together when snapshots gain kind/mode;
  do not leave the current string-SHA lookup assuming the old shape. Do not freeze
  UID/GID, timestamps, inodes or cache contents. Detect drift before the next stage.
  Keep credentials out of snapshots. Stable bytes do not freeze live vulnerability
  databases or builder tags; retain their observed identities separately.
- Reject incompatible track/profile/case selection before preparing a real
  checkout. Keep CLI options simple; do not infer live mode from a late failure.
- Reconcile the 3,600-second actor deadline with serial 1,800-second builds/tests,
  retries and scans. Reserve time for bounded cleanup/collection; do not merely
  raise the cap. Verify owned child/container cancellation through the shared
  harness/worker, since killing the CLI alone is not proof of descendant cleanup.

Use frozen input/annotations as grading authority. `state.expected` currently can
change `repair` to `observed` on a copied failed live002 archive and turn its full
contract true without changing evidence or frozen input. Delete duplicated grading
expectations from collected state where practical, or compare the complete relevant
subset, including defaults and absent fields: scenario, pins, guards, canonical
commands and replay result/branch/exit. Use one bound reader for arguments,
scenario checks, scan-head selection and judge-evidence projection; fixing only
the Boolean verdict leaves a second mutable advisory authority. Capture paths are operational data, not permission to change the declared scenario.

For required repair, require the initial phase to be completed and bind its receipt
to the pinned base unconditionally. Current controlled fixtures pass with that
phase unreached and a wrong initial HEAD. For native proof, reject duplicate
canonical binary paths before building per-path checks; an invalid record followed
by a valid duplicate currently overwrites the failure. Test both orders and `./`
aliases. Preserve observed blocked-phase and initial-only binary fast-path rules.
These are small checks in existing predicates, not a general evidence schema.

Preserve original grades; corrected archive rechecks are separate records. Intact
hashes cannot authorize contradictory evidence or a changed scenario.

Keep answer/control files outside the staged execution tree, but do not claim
that an unrestricted shell cannot read them. Literal-path trace heuristics miss
variable-based reads; the shared runner exposes the run root in its environment.
Remove unnecessary exposure where possible and keep the observational limitation
explicit. Moving the frozen helper must not change protected roots accidentally:
record source/provenance/control roots rather than infer them from `EVAL_ROOT`'s
old directory depth. Do not add more shell regexes as an isolation guarantee;
strong isolation belongs to shared infrastructure if it becomes required.

Use model-free 005/007/002 plus the contradiction controls above. Mutate original
source after freezing, change/remove the selected interpreter, vary child Python,
backend imports and profile/track, and stall an owned child/container. Verify
snapshot reuse, early failures and partial-evidence cleanup. Scoring-only recovery
preserves the original failure and actor hashes; it is not an untouched E2E pass.
No campaign/resume service, plugin sandbox or generic preflight layer is needed.

### 3. Fix runtime safety independently of optional cleanup

These are release obligations, not claims that each caused the current cohort's
failures. Use focused actual-function/workflow controls; no new actor is needed
for each predicate. The existing live cases still validate any changed runtime
that is selected for the final cohort.

**Owned artifacts and checkout cleanup.** `artifact_manifest_prepare` deletes a
user-replaced ignored executable if its path appears in the prior manifest. The
sequential real-Git probe has clean status and uses the actual helpers; no race or
scanner behavior is needed. Extend the existing manifest with content/type identity;
delete only unchanged, still-untracked owned files within the canonical checkout, including parent components. A second clean-input
probe replaces an ignored output directory with a link; the helper deletes the
outside target. A leaf hash/type check alone does not establish containment.
Preserve changed files, tracked promotion, links, scope escapes and old/malformed
unproven claims, and leave preserved contents visible to scanning. Apply the rule
to current-run rebuild cleanup too. No artifact registry or database is needed.

Abort cleanup also resets the current tracked tree without checking that it still
owns the checkout. An explicit switch to another branch followed by a user edit
is overwritten by the actual cleanup function. Guard the latest run-owned branch/HEAD before
destructive cleanup, record actual state, and preserve unexpected context for
manual recovery. If ownership cannot be established, preserve rather than add
a transaction state machine. Do not promise general concurrent-edit safety or add a lock/lease service to solve
a demonstrated branch-ownership check. Keep controls for owned empty abort, completed
partial run and unexpected checkout/index preservation.

Deleting committed-but-uncompleted repairs on abort is currently documented
transaction rollback, not proven irreversible data loss. Decide separately whether
to retain a named unverified branch for inspection. Do not silently redefine that
product contract or describe reflog-recoverable objects as erased. The branch-switch
probe is a deterministic interleaving, not a tested signal/process-tree lifecycle.

**Publication generation.** Exact relay can faithfully repeat an unsafe recipe.
The renderer chooses by owner inequality/first remote and reads only the first
push URL, while `git push <remote>` can send to multiple destinations. Bind both
PR base repository and intended push destination; withhold ambiguous/unconfirmed
recipes. A renamed fork can have a different basename, and an unrelated repository
can share the same name: URL name equality is not fork authentication. Use an
existing explicit/trusted destination where available; do not invent a new remote
registry or mandatory online topology/authentication dependency. Do not rewrite
remote URLs or print credentials to make a recipe possible.

Controls: unique confirmed target, unrelated backup first, ambiguous candidates,
renamed fork under the chosen explicit policy, split fetch/push URLs, multiple
push destinations, supported SSH and unavailable identity. Assert generated base,
head and destination without executing push/PR. Historical positive replay proves
relay of its archived recipe, not correctness of today's generation.

**Policy interpretation and command status.**

Use one structural read-only Grype policy decoder, preferably extending the
existing `PolicyLoader`, for preflight and audit entry identity. Equivalent valid
YAML layouts must yield equivalent vulnerability/package/type/location/fix-state
semantics. Alias, merge, inline and package-first policies must not silently
produce zero audited entries. Retain duplicate-key/schema checks. For mutation
layouts that the comment-preserving writer cannot safely change, stop with a
specific review outcome; do not rewrite user policy with a generic serializer.
Eight actual checker/audit fixtures accept equivalent policies but report one
canonical issue versus zero for package-first/inline/alias forms. This proves an
audit reader gap, not a full publication bypass; see `.work/fix-go-cves-design-audit-20261023/yaml-counterexample/receipt.json`.

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

Replace obsolete source/layout assertions with behavioral controls when equivalent;
assertion count is not a coverage target. Deduplicate fixture setup without hiding
different scoped-policy or rollback cases.

**Unconfirmed follow-up: source catalog coverage.** The package-count function
accepts nonzero/non-Go context or missing count wording without inspecting Go
inventory; an extracted schema guard also mislabels an npm-only finding. No real
Grype exclusion or full false-clean was reproduced. Test the actual scanner on
healthy/suppressed/omitted Go modules, non-Go-only findings, dependency-free and
native-only inventories before choosing a small machine-readable source check.
Keep the narrow npm-type diagnosis separate. This investigation is not an implicit
campaign prerequisite or a reason to require optional native proof for source scans.

**Optional deletions.** Repeated build/scan work is a later measured deletion, not a cache project. Trace
which source/binary/ignore state each scan observes; remove the post-test presentation scan if the immediately following verifier
already supplies its only needed result, and remove the pre-review scan with its
owner. Preserve the authoritative final rebuilt scan after
all mutating phases. Do not memoize by HEAD alone or remove gates to save time.

### 4. Select a simpler handoff; keep larger deletions conditional

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

Reviewer removal is optional for measurement closure, not a prerequisite to
correcting the caller/oracle. Prefer removing it after making its publication
semantics explicit.
It is not currently just advisory: `fix-package.sh` can emit a successful indirect-
repin caveat without setting a deterministic blocker; reviewer `UNRESOLVED` alone
can then veto publication. Inventory every `NEEDS_REVIEW` origin. Preserve real
compatibility/security decisions as deterministic typed blockers; decide explicitly
whether a successful repair's repin caveat is advisory. Provider absence/failure
currently permits continuation while malformed available output can block: do not
migrate every incidental transport/parser veto into permanent policy. Existing audits must not
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

No new actors are selected by this planning change. Replay can demonstrate
policy intake/guard forwarding while its archived engine violates a newer guard;
that does not prove today's enforcement fails or require retrospective repair of
the historical result. Keep current enforcement checks local/live. No replay or
cohort pass substitutes for the separate release obligations above. Complete local semantic,
operation, staging/interpreter, validator and selected handoff/oracle controls,
then freeze the chosen implementation and criteria. Complete included runtime
changes' relevant controls; keep deferred safety obligations and optional deletions
explicit rather than making every improvement an implicit pre-freeze gate. Select and record an official upstream pin
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
all-pass milestone. A predeclared two-of-three semantic comparison may continue only while its
narrower question remains open; it cannot establish all-cells acceptance. Three
executions are a fixed-fixture repeat check, not general reliability. Preserve every failed source group and original grade. No automatic
next prompt variant, favorable-seed rerun or adaptive cap increase follows failure.

## Documentation and deferred work

Keep setup/commands in eval README, requirements in testing, decisions/next work
here, outcomes in the results record and unique historical grades where recorded.
Trim duplicate status/history without deleting unique failure evidence or creating
another parallel plan. Scratch expert audits and the model-free snapshot
inspection are under `.work/fix-go-cves-design-audit-20261023/`. Successive-wave
reports and bounded counterexample receipts are under
`.work/fix-go-cves-critical-waves-20261023/`; distinguish actual-function proofs,
controlled contract predicates and untested producer reachability in conclusions.

Defer a broad Bash/Python rewrite, directory/test-suite churn, general shell
policy engine, fleet/scheduled evals, additional recordings, automated campaigns,
publication execution and generic caching. Preserve rollback, scoped ignores,
no-fix credit, compatibility policy, native identity and fail-closed evidence.
