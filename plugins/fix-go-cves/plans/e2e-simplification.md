# E2E acceptance and simplification

Re-audited on 2026-10-23 against `42eff37a`, including the third four-wave review.
These are proposed changes, not acceptance or replacements for historical grades.
The [results record](../evals/implementation-results.md) owns measurements,
[testing strategy](testing.md) owns requirements, and
[workqueue investigation](workqueue-race.md) owns the external diagnostic.

## What is actually preventing closure

Stock stages execute, but measurement authority/provenance and handoff semantics
remain unreliable. Separate runtime findings also prevent general release claims.

| Boundary | Observed gap |
| --- | --- |
| Frozen execution | Preparation copies current files; bare-Python hooks drifted in the exit-127 incident |
| Shared lifecycle | Inherited child pipes exceed the pinned runner timeout; aggregation masks -1 beside 0 |
| Grading authority | Collected expectation downgrade and phase/native contradictions can pass |
| Runtime ownership | Actual helpers delete replaced artifacts/outside link targets, reset a switched checkout and write outside selected Go metadata |
| State composition | Late policy commits skip retesting but the checker requires exact tested/retained HEAD |
| Interpretation | YAML readers disagree; replay lacks grounded outcome grading; reporting/reviewer text adds unsupported claims |

Actual-function proofs, controlled checker counterexamples and full engine runs
are different evidence. Neither a predicate proof nor an outside-write helper
proves a full publication bypass or an observed actor exploit. Preserve those limits.

## Desired ownership

| Component | Owns |
| --- | --- |
| Detection | Effective target configuration, defaults and explicit compatibility restrictions |
| Runtime | Mutation/rollback, bounded tests, four audits, final scan/license gates, receipts and publication eligibility |
| Invoking skill | Target/policy selection, one launch, completion, read-only diagnosis and supported handoff |
| Eval helper | Independent operation/state/scenario checks, evidence identity and exact witnessed relay |
| Semantic grading | Past/present facts and future advice against independent evidence, with whole-reply review |

Keep policy selection, repair discovery and useful advice as AI work. Retain Bash
transaction orchestration and the existing Python structural-policy boundary.
No wholesale orchestrator rewrite, result schema, transaction service or sandbox.

## Scope and order

Fix measurement prerequisites before interpreting new actor results. Choose the
bounded implementation and claim, complete changed-boundary controls, then freeze.
Runtime obligations below remain release blockers if deferred; optional deletions
do not hold unrelated E2E measurements hostage. The fix-only cohort cannot establish
report-only safety or every YAML/publication path.

Use the [component reuse rules](testing.md#measuring-relevant-changes): changed
oracles/validators can reinterpret sufficient archived facts separately; changed
actor/runtime paths need affected execution. Missing new fields remain unknown.
Preserve original manifests, helper-hash fences and grades. Only restoring the
original frozen helper is scoring-only recovery; a corrected oracle is a separate
interpretation. Neither is an untouched original E2E pass. Declare reuse and
component identities in existing records, not a dependency resolver or new ledger.

## Ordered implementation

### 1. Settle the prospective contract

Keep the next outcome rubric strict about demonstrated factual contradictions,
including precise wrong citations, while distinguishing criterion scope: a wrong
line does not itself invalidate separately correct backport advice. Wrong refs,
coverage/builders/counts, omitted attempts/blockers, unsupported causality,
invented publication, missing required handoff and unsafe mutations fail their
applicable criteria. Preserve historical criteria and grades unchanged.

Presentation, reference-read timing, accurate derived totals and harmless denied
inspection are not intrinsic product failures. A failed/passing retry called
“flaky” does not alone assert pre-existing failure. Attribution needs evidence
when asserted; neither an attribution task nor an uncertainty paragraph is mandatory.

Keep the preventive deny if useful, but distinguish the proven read-only denied
inventory form from attempted mutation. Unknown forms stay conservative; redirects,
substitutions, external-diff/textconv and mixed mutations inherit no benign verdict.
Cover ordinary history/status, `git -C`, multiline commands and mutate/restore in
existing operation tests. Attempted source edits/mutating stash fail even if denied.
Trace heuristics are observation, not a shell sandbox or generic option parser.

### 2. Freeze execution and repair measurement authority

In `evals/run.sh`, snapshot/preparation, hooks and deterministic judges:

- Freeze required plugin/helper files once and stage from them. Rewrite lifecycle
  and embedded judge paths. Preserve the `fix-go-cves` basename/relative layout:
  harness basename reuse must select the prepared invocation shim. Replay uses
  historical runtime plus complete frozen current skill; live uses current runtime.
  Keep generated tools/caches outside scanned trees and answers outside actor input.
- Exercise shared staging, resolved CLI plugin argument and intended shim model-free;
  confirm actual skill intake in a declared pilot. Preserve distinct generated-shim,
  historical-runtime and unwrapped-live baselines rather than comparing every
  prepared byte to source. Do not copy the entire repository.
- Resolve one absolute venv interpreter for hooks, drivers, judges and stock stages.
  Preserve its venv entrypoint; identify executable/hash, version and packages.
  Check child imports including `CSafeLoader`; fail instead of falling back.
- Identify cases, helper/skill/runtime/config, CLI/model/harness and tools in the
  existing manifest. Add file kind/relevant execution mode; reject unexpected
  source links and identify intentional tool/venv links separately. Migrate baseline,
  completion/capture and native SHA consumers together. Exclude credentials,
  ownership/timestamps/inodes/cache bytes; record observed database/builder identity.
- Reject incompatible track/profile/case before preparing a checkout. Reconcile
  serial operation limits and actor deadline with bounded cleanup/collection.
- Fix inherited-pipe termination/draining/reaping in the shared runner, preserving
  partial traces/raw exits. Any nonzero case exit fails aggregation; `max(-1,0)`
  is wrong even though later per-case extraction rejects it. Completeness and
  thresholds remain separate. Process-group control does not own detached containers.
- Select a tested harness revision or identified local patch; record base/effective
  code identity and dirty state. Do not introduce a supervisor or runner fork.

Bind arguments, scenario checks, scan-head selection and semantic projection to
frozen input/annotations. A copied failed live002 archive passes when only
`state.expected` changes repair to observed. Remove duplicated collected expectations
or compare the complete relevant subset including defaults/absence: scenario,
pins, guards, canonical commands and replay result/branch/exit. Paths are operational.

Required repair must unconditionally prove completed initial scan at the pinned
base. Reject duplicate canonical native paths before per-path checks, both orders
and `./` aliases: a later good record must not overwrite a failed witness. Preserve
observed blocked phases and initial-only native clean fast paths.

Repair-exercise credit also needs a usable advertised fix threshold: nonempty
containers `['']` and prerelease-only lists currently pass. Independently apply a
small release/pseudo-version specification with empty/prerelease/release/pseudo
controls; dispatch's loose `validfix` is not complete version validation. Published
availability is separate from compatibility permission and generic remediation by
dependency removal. No resolver simulation or shared runtime/oracle implementation.

Keep source/provenance/control roots explicit when relocating helpers. Literal-path
checks miss variable-based answer reads and run-root environment exposure; reduce
exposure without claiming isolation. Shared infrastructure owns stronger isolation.

Use existing model-free 005/007/002 and contradiction controls. Vary frozen-source
drift, selected/child Python, imports and track/profile. Shared lifecycle controls
cover stdout/stderr/both, early leader exit, ignored TERM, cancellation and exit
matrices [-1,0], [-1,-1], [1,0], [0,0]; inspect termination, not eventual pipe closure.
Retain partial evidence and explicit container/resource disposition separately.

### 3. Close runtime ownership and state boundaries

**Artifacts and checkout.** Actual helpers delete a replaced ignored executable
and, through a replaced parent-directory link, an outside target. Require current
content/type ownership, still-untracked status and canonical containment through
all parents before deleting prior/current-run outputs. Preserve changed, tracked,
linked and unproven old/malformed claims; leave preserved output scan-visible.

Actual abort cleanup also resets a deliberately switched checkout with a user edit.
Check latest run-owned branch/HEAD before destructive cleanup; preserve unknown
checkout/index context and record recovery state. Cover owned empty abort, partial
completion and unexpected context. This is a sequential interleaving proof, not
general concurrent-edit/signal safety. Named retention of committed uncompleted
repairs is a separate rollback-policy choice; reflog-recoverable objects are not erased.

**Effective Go metadata.** Real workspace sync modifies `../outside` beyond
rollback. Validate effective workspace identity/use members before graph/update
writes using canonical paths and a local-toolchain read-only JSON view; bind sync
to that workspace. Mutable module files must be tracked/owned in the existing
transaction set. Reject outside/untracked members, parent links and independent
nested checkouts; preserve owned nested modules, internal sync, read-only local
replacements and sibling/vendor/API rollback. Do not snapshot external projects.

Workspace checks alone miss inherited `GOFLAGS=-modfile`: actual `fix-stdlib.sh`
updates sibling outside.mod, leaves target unchanged/clean and emits FIXED. This
proves an outside write and false helper result, not full fix-all publication.
Reject `go env GOMOD` as the guard: actual controls return owned go.mod while
`go mod edit` reads/writes outside.mod. `Dir` alone also misses the alternate file.
The tested candidate is `GOWORK=off GOTOOLCHAIN=local go -C "$moddir" list -m -mod=readonly -json`.
Require one main-module result with nonempty `GoMod`; resolve relative values
against queried moddir. Bind selected path/type to exact tracked owned go.mod and
its derived sum path to the transaction, recording existing or absent pre-state;
reject alias/link selectors even if realpath equals owned go.mod. Sums derive
lexically from the selected modfile; the alias query is confirmed, not an executed
outside-sum write. Bound the query; mismatch, ambiguity, failure or timeout
requires review before policy reads/writes.

Native overlay controls also return owned `GoMod` while `go list` reads replacement
module bytes; `mod edit` reads/writes physical owned bytes in the same context.
This is inconsistent metadata selection, not an outside repair-write exploit.
Explicit native `-overlay=` restores owned query bytes; keep all internal reads
and writes physical, applying that override where supported and validating each
command rather than blindly adding a flag. Preserve caller build/test flags,
effective GOFLAGS/GOENV and benign flags otherwise; no general flag parser or
broad stripping.
Current-host absolute/relative/stored/tag/query controls preserve input bytes.
Cover nested modules, supported minimum/newer Go, overlay/alias/sum identity and
query errors before adoption. Complete explicit file binding is an alternative
only across graph/get/tidy/vendor/sums, not `mod edit` alone. These sequential
controls establish no concurrent configuration guarantee.

**One final test phase.** Actual YAML repair commits only .grype.yaml after early
tests. Runtime skips retest while the checker requires exact tested/scan HEAD;
the actual helper plus controlled predicate prove reachable contract disagreement,
not an observed full-cohort failure. Move canonical `run_tests` and its subsequent
`CLEAN_CMD` after bounded verification/outcome folding; delete the early invocation
and policy-excluding conditional retest. Keep one final phase with existing bounded
retry, per-attempt receipts and workspace/state checks. Bind `VERIFIED_HEAD` to
`TESTED_HEAD` before cleanup; capture cleanup exit and block confirmation on failure,
then check retained HEAD/tracked state after cleanup and all later gates. Exact
commit tests remove ancestry/policy-equivalence exceptions.
Failed verification remains failed despite passing tests; retain final-state partial
diagnostics. This changes prospective ordering, not historical failures. Cover late
policy/dependency commits, retries, mutating cleanup and workspace cleanup; execute
the affected live path.

**Publication.** Owner inequality/first-remote inference and first push URL are
insufficient; a remote can push to multiple destinations. Bind confirmed PR base,
head and all intended push destinations; withhold ambiguity. Basename equality
does not authenticate forks, including renamed forks. Use existing trusted/explicit
identity; no remote registry, mandatory online topology service, URL rewriting or
credential output. Locally cover backup-first, ambiguous, renamed/same-name, split
fetch/push, multiple destinations, SSH and unavailable identity without publishing.
Historical positive recipe relay does not prove current generation correctness.

**Policy and evidence.** Extend the existing structural `PolicyLoader` for shared
read-only preflight/audit identity: vulnerability/package/type/location/fix-state,
including aliases/merges/inline/package-first and duplicate/schema checks. Actual
equivalent-layout controls report one canonical issue versus zero for alternatives;
that is an audit-reader gap, not a full bypass. Unsupported comment-preserving
mutation layouts stop for review; do not generically serialize user policy.
Cover actionable ignores, non-Go entries, sibling scope, mixed broad/scoped rules
and missing evidence; retain four independent audits. Deduplicate only equivalent
entry/location/tuple parsing after parity, not different gate semantics.

Preserve child and tee statuses in remaining fix-package build/fix-all dispatch
pipelines; cover command 0/tee 1 and command 2/tee 1 with existing local patterns.
Required capture failure blocks gates. Optional archive-copy failure instead keeps
engineering exit, warns and preserves private diagnostics/recovery paths; actual
cleanup currently deletes them after copy failure. No new archive store/exit gate.
An eval missing required evidence still fails.

Report-only builds accept dirty input and ignore restore failures. Reject dirty
input before mutating builds or choose an isolated build with defined output
policy; never auto-stash. Add dirty-preservation/cleanup-failure controls, not actors
to this fix-only cohort. Replace obsolete layout assertions with equivalent behavior
controls; assertion count and test-directory churn are not coverage goals.

**Unconfirmed source coverage.** Package-count/schema probes accept non-Go-only
context or missing count wording; no real Grype Go-exclusion/full false-clean was
reproduced. Test real healthy/suppressed/omitted Go, non-Go-only, dependency-free
and native-only inventories before choosing a small source check. Keep the npm-type
diagnosis narrow; no implicit campaign gate or mandatory optional native proof.

### 4. Simplify handoff and keep deletions conditional

Inline the compact reporting contract in `SKILL.md`, retaining target policy,
one invocation, completion and immutable-ref read-only discovery. Relay emitted
Summary/recipe/exit exactly; authenticate extra facts; give unresolved work a
supported repair/investigation, owner and prerequisite. Preserve relevant attempts,
but a recovered retry alone creates no maintainer task. Applicable remote repairs
must land on starting origin; builder updates must be published. Unknown coverage
stays unknown; positive artifact-specific evidence stays positive.

Remove final-read timing, exact table/imperative grammar, verbatim-only evidence
cells, universal no-count/causality-paragraph rules and universal failed-attempt
investigation. Delete reporting.md if no conditional detail remains. Replace
speculative retry warning with actual exits; investigate relevant failing packages.
Keep exact Summary/recipe checks and historical runtime logs unchanged.

Reviewer removal is optional. Inventory NEEDS_REVIEW/publication effects, especially
successful primary repair/failed indirect repin. Decide real compatibility/security
blockers versus advisory caveats; absence/failure/malformed transport must not
accidentally define policy. Use existing response fixtures and blocker/repin/sibling/
poison-provider controls. Once semantics are complete, delete nested invocation,
pre-review build/scan, retries and parser together. Otherwise retain only the
independent decision and validated reasons with raw output. No temporary framework.

Repeated scans are measured deletions: trace observed source/binary/policy state
before removing presentation/pre-review scans. Keep the authoritative final rebuilt
scan after mutation; do not cache by HEAD alone or remove needed audit inputs.

### 5. Ground and calibrate the semantic oracle

Replace replay backport with outcome; keep backport/remote landing under action_owner.
Still two judges, three samples each. O owns past/present facts; A owns supported
future repair/owner/prerequisites. Supply independent historical witnesses and
captured observations through existing projection; reply Summary and nested review
text do not authenticate themselves. Add trusted observed finding IDs rather than
unbounded transcripts. Unobserved new history claims require independent review.

Controls separate false past cause/valid action (O false/A true), missing owner
(O true/A false) and wrong future target (A false). Cover recipe targets, package
citations/retries, origin landing, builders/native scope, overview contradictions,
counts and presentation. In 007's citation pair change only the wrong citation,
keeping “flaky” constant. Model-free admission checks annotated Summary/literal
log witnesses against recordings with only admitted wrapper substitutions removed.

Use the [calibration rules](testing.md#measuring-relevant-changes): frozen expected
criterion labels, raw samples/errors, strict-majority aggregation and retained
disagreements. TTF is true with complete error-free samples; no unanimity gate.
Negative controls correctly fail production thresholds, so stock exit zero is not
calibration success. Name tuned controls development/regression controls, keeping
reviewed pairs fixed without calling inspected controls unseen holdouts. Add no
recordings/models/actors for terminology or unchanged judging retries for agreement.

## One acceptance campaign, after local closure

This plan launches no actors. Freeze selected changes/criteria after relevant
controls; select an official upstream pin with actual actionable dependency repair.
The existing Admiral pin remains possible under a changed question; a justified
new official pin is also possible. The race investigation requires no specific
patch before measurement. Never inject local repair, remove race checks, downgrade
repair to observed-only or retry a favorable seed. Replay guard forwarding can pass
while its historical engine violates a newer guard; current enforcement is local/live.

Retain eleven actors maximum: 005/007 three each, positive 002 once, four live once.
Order seven distinct scenarios first (005, 007, 002, then four live), followed by
four remaining replay repeats if eligible. Pilots count. Existing actor caps total
$115 (seven at $5, four at $20); nested/judge costs remain separate. Finish each
cell's original stages, required samples, scenario checks and whole-reply review
before launching the next. Multi-case actor batching cannot enforce this stop rule;
model-free batching remains useful. Declare applicable evidence reuse before launch.

Full fixed-cohort acceptance requires stock thresholds/stages and independent
scenario/review requirements in [testing](testing.md): live001 can block correctly,
002 must repair with canonical gates, 003/004 prove native phases/artifacts. A false
completed verdict is complete evidence but can fail thresholds. Preserve accuracy
details; presentation alone does not fail. Stop on safety/integrity or any failed
required gate, aggregate threshold or review. Dissent alone does not fail a majority.
A predeclared two-of-three comparison can continue only for its narrower question,
not all-pass acceptance. Preserve failures; no adaptive prompt/seed/cap changes.
Three fixture executions establish repetition, not general safety or reliability.

## Documentation and deferred work

Keep decisions here, requirements in testing, commands in eval README, measurements
in results and unique calibration history beside cases. Audit receipts under
`.work/fix-go-cves-{design-audit,critical-waves,second-audit,third-audit}-20261023/`
retain detailed proofs and limits; replace superseded prescriptions, not append
every audit's chronology. Defer broad rewrites, shell policy engines, fleet/scheduled
evals, new recordings, campaigns, publication execution and generic caching.
