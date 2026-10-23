# E2E acceptance and simplification

Acceptance remains **open**. C14 at `2a3c1b27` stopped after one live 001 actor:
runtime and factual reporting passed, but advice forecast likely compilation from
version compatibility despite a genuine uncertainty caveat. C15 changes only that
compiler clause to prerequisites and verification steps; no freeze or actor exists.
Preserve source groups, grades and dissent; the
[results record](../evals/implementation-results.md) owns counts.

This plan owns current design choices and the remaining acceptance sequence. The
[testing strategy](testing.md) owns durable requirements and calibration/reuse
rules; the [results record](../evals/implementation-results.md) owns measurements
and source groups; the [workqueue investigation](workqueue-race.md) owns the
external diagnostic. Commands belong in the [eval README](../evals/README.md).

## Desired ownership

| Component | Owns |
| --- | --- |
| Detection | Effective target configuration, defaults and explicit compatibility restrictions |
| Runtime | Mutation/rollback, bounded tests, four audits, final scan/license gates, receipts and publication eligibility |
| Invoking skill | Target/policy selection, one launch, completion, read-only diagnosis and supported handoff |
| Eval helper | Independent operation/state/scenario checks, evidence identity and exact witnessed relay |
| Semantic grading | Past/present facts and future advice against independent evidence, with whole-reply review |

Policy selection, repair discovery and useful advice remain AI work. Bash retains
transaction orchestration; the existing Python structural-policy boundary owns
semantic policy reads. No orchestrator rewrite, transaction service, new result
schema, generic shell/flag parser or plugin sandbox is needed.

Runtime safety obligations remain release requirements even when this bounded
fix-only cohort cannot exercise them. It cannot establish report-only safety or
every YAML/publication path. Optional deletions do not block unrelated measurements.

## Implemented design

### Frozen execution and independent authority

Freeze the required plugin/helper files once, preserving the prepared
`fix-go-cves` basename, relative layout and invocation shim. Replay combines the
historical runtime with the complete current skill; live uses current runtime.
Identify generated shim, historical runtime and unwrapped live components
separately. Confirm actual actor intake rather than inferring it from preparation.
Tools, caches and answers stay outside scanned trees and actor input.
Keep source/provenance/control roots explicit: literal-path checks miss variable-
based answer reads and run-root environment exposure. This setup is not isolation;
shared infrastructure owns stronger isolation.

One absolute venv interpreter serves hooks, drivers, judges and stock stages;
its entrypoint, version, executable identity and packages are recorded. Required
child imports fail closed. The existing manifest identifies cases, configuration,
helper/skill/runtime, CLI/model/harness and tools, including file kind and relevant
execution mode. Unexpected source links are rejected; intentional tool/venv links
have separate identities. Record observed scanner/database/builder identity without
credentials, cache archives or unrelated filesystem metadata. Reject incompatible
track/profile/case combinations before checkout preparation.

Frozen inputs and annotations govern scenario, pins, guards, canonical commands,
scan-head selection and replay outcomes. Collected state cannot weaken them.
Required-repair cases prove an initial scan at the pinned base, an actionable
published fix threshold, a retained dependency repair and the required final gates.
The independent threshold specification distinguishes supported releases/pseudo-
versions from empty, malformed and prerelease-only values; published availability
is separate from compatibility permission. Dependency removal can remediate a
finding without satisfying that narrower repair exercise.

Reject duplicate canonical native paths before checking individual witnesses;
a later good record cannot replace failed evidence. Preserve actual blocked or
unreached phases and initial-only proof for a clean fast path. Entry kind, content
and execution mode are part of source/native identity.

The selected shared runner patch bounds termination, pipe draining and reaping,
preserves partial traces and raw exits, and fails aggregation for any nonzero case
status, including negative exits. Its effective code identity and dirty state are
recorded alongside the base revision. Direct-child fallback handles group-signaling
failure; it does not prove descendant termination in that failure mode. Process-
group control also does not own detached containers. Resource disposition remains
explicit shared-environment work.

### Owned mutation and exact final state

Generated-artifact deletion requires current content/type ownership, still-
untracked status and canonical containment through every parent. Preserve changed,
tracked, linked or otherwise unproven outputs and leave them scan-visible. Abort
cleanup checks the latest run-owned branch/HEAD before destructive operations;
unknown checkout/index context is preserved with recovery information. Sequential
controls do not establish general concurrent-edit or signal safety. Retention of
committed uncompleted repairs remains a separate rollback-policy decision.

Internal Go graph, get, tidy, vendor and edit operations bind to the owned physical
`go.mod` with native `-modfile` and clear overlays where supported. This replaces
the proposed effective-path query system: `go env GOMOD` or module `Dir` alone
cannot establish which bytes a command reads/writes. Keep native Go parsing and
caller build/test flags. Validate regular, tracked, single-link selectors,
canonical parents and nested-checkout boundaries before writes. Workspace identity
and use members are checked with a local-toolchain read-only view; synchronization
is confined to owned transaction members. Preserve owned nested modules and
read-only local replacements rather than snapshotting external projects.
Existing regular checksum files may be tracked, untracked or ignored: the existing
transaction captures/restores their pre-state and adds only previously absent
files. Actual minimum/current-Go transaction controls support this design; they
make no concurrent-configuration guarantee.

One final canonical test phase follows bounded verification and all dependency/
policy commits, with the existing bounded retry and per-attempt receipts. The
early test phase and policy-excluding conditional retest are removed. Bind final
expected HEAD to `TESTED_HEAD` before configured cleanup, capture cleanup failure,
and check retained HEAD/tracked state after cleanup and subsequent gates. Passing
tests cannot clear failed verification. Generated workspace cleanup preserves
existing caller files. Exact commit identity removes ancestry or policy-equivalence
exceptions.

Four independent audits require complete typed counters. Final rebuild/scan and
license gates preserve the tested state; the clean fast path checks unchanged
source before normalization. Command and logger exits stay separate throughout
capture pipelines. Required capture failure blocks downstream gates. Optional
archive-copy failure preserves the engineering exit, warning and available private
diagnostics/recovery paths; an eval missing required evidence still fails.
Report builds reject dirty input and retain checkout/restore failures as incomplete
results; reports without a build remain read-only. The fix-only actor cohort does
not establish report-only E2E safety.

### Policy and publication

Preflight and audit readers share the existing semantic `PolicyLoader`, including
aliases, merges, inline/package-first layouts, duplicate/schema checks and scoped
vulnerability/package/type/location/fix-state identity. The writer remains
conservative: unsupported comment-preserving mutation layouts stop for review
rather than generically serializing user policy. Keep actionable/ignored,
regression, multi-module and four-audit gate semantics distinct.

An optional publication recipe requires a configured `branch.<name>.pushRemote`
or `remote.pushDefault`, one effective GitHub push destination and an independently
confirmed base/head route. Same-base routes can be confirmed offline; user-fork
routes require optional bounded read-only network metadata. Ambiguity withholds
the recipe without changing completed engineering gates. Owner inequality,
basename equality, first-remote and first-push-URL inference are insufficient.
No remote registry, mandatory topology service, URL rewriting or credential output
is needed. Historical positive recipe relay is distinct from current generation
correctness; evals never push or create a PR.

### Compact handoff and factual grading

The skill carries the reporting contract directly: preserve target policy, launch
once and observe actual completion. The reply starts with the exact emitted
Summary through terminal exit, with its recipe exactly once. Only explicit
runtime scope lines establish coverage; if none establish compiled Go binary
coverage, add its uncertainty statement. Quote each failed attempt's diagnostics
and outcome plus later attempt outcomes; for all-success tests, the Summary
status suffices. Added prose gives only future actions, owners and verification
prerequisites. Inspect `origin/<branch>` directly for target policy and search
default-branch history for an existing repair commit. Stop once that handoff is
supported. Applicable source repairs must land on the starting origin;
builder repairs must be published before consumers rerun. Compiler version is a
prerequisite; give build/test verification steps without predicting success. A
recovered retry alone creates no maintainer task. Unknown coverage stays unknown; positive artifact/phase
proof stays positive. Nested-reviewer prose does not authenticate observations.

Exact timing/last-tool gates, table/imperative grammar, verbatim-only evidence
cells, universal no-count rules, mandatory causal/uncertainty paragraphs and
universal failed-attempt investigation are removed. The stage-local loaded-section
reread was observed in C12; it is no timing gate, last-tool rule or separate
reference, and its efficacy remains unproven.
Wrong refs, citations, counts, coverage,
builders, command attribution, unsupported causes, omitted attempts/blockers,
invented publication and missing required handoff still fail applicable criteria.
Other presentation choices do not fail; the strict recipe relay rule still
applies when argument values agree. Accurate derived facts remain allowed. A retry
called “flaky” does not alone assert pre-existing failure. Read-only denied
inspection is distinct from attempted mutation; unknown/mixed shell forms stay
conservative, and denied source edits or mutating stash still fail. Trace heuristics
are observation, not a shell sandbox.

Two semantic judges, three samples each, retain distinct responsibilities: outcome
owns past/present facts; action_owner owns supported future repair, owner and
prerequisites. A wrong historical citation does not automatically invalidate
separately supported advice. Independent archived witnesses and captured
observations ground the existing projection, including the bounded producer
witness needed to check command attribution. Neither the reply's Summary nor
nested review proves itself. Claims outside admitted evidence still need
independent whole-reply review. A source diff alone proves neither execution
history nor causal independence from other changes.

## One acceptance campaign, after local closure

C14 completed original stages and stopped at its first live 001 actor. Runtime
and outcome passed; action/owner failed for a version-based successful-compilation
forecast. The caveat addressed the same future build/test/scan result, so this was
neither an executed-success claim nor an unconditional guarantee. The unsupported
forecast still failed the frozen criterion. The
[results record](../evals/implementation-results.md) preserves the dissent and
prior C13 measurement error separately.

C15 changes only the final compiler clause: state prerequisites and verification
steps without predicting build/test success. Retain C14 failed/later-attempt
reporting and use the Summary for test status when all tests succeed. Runtime/helper, fixtures
and O/A oracles are unchanged; reuse V5 only with identical judge prompts/inputs,
without repeating its calls. Fresh actors remain required across the skill change.

C15 remains prospective. After source freeze, measure live 001 first, then
publication 002, replay 007/005, live 002/003/004 and eligible replay repeats.
Finish each cell's original stages, thresholds and independent review before
continuing. Preserve the eleven-actor/$115 maximum, models and pins. No C15 source
is frozen and no C15 actor has run.

License cleanup reuses the existing artifact ownership helper with a private
license prefix. Serialized path/event readers honor LF delimiters without splitting
embedded Unicode separators. Existing focused controls, frozen integration and
model-free replay remain applicable to unchanged components; partial helper I/O
failure coverage is not claimed.

Apply the [calibration rules](testing.md#measuring-relevant-changes): preserve
labels, witnesses, prompts, models, grades and dissent; require every sample
without error and strict-majority boolean results. Negative controls must fail
production thresholds. These are development controls, not unseen holdouts; do not
repeat unchanged judging to obtain agreement. Freeze all live components/settings
before the first live actor.

Declare reuse before launch under the [component reuse rules](testing.md#measuring-relevant-changes):
changed skill paths require affected actors; runtime/environment paths require
focused controls and real execution reaching them. Changed oracles/validators may
separately reinterpret sufficient immutable archived facts. Missing new fields
stay unknown. Preserve original manifests/helper-hash fences and grades. Restoring
the exact original frozen helper is scoring-only recovery; a corrected oracle is
a separate interpretation. Neither becomes an untouched original E2E pass. Use
existing records rather than a dependency resolver or new evidence ledger.

A separate authentic Admiral engine diagnostic demonstrates repair feasibility at
the existing official pin and producer/consumer compatibility; its missing actor
reply correctly prevents behavioral acceptance. It supplies no actor/cohort credit
or causal explanation of earlier race failures. The existing pin remains possible
under a declared changed question; another official pin needs concrete justification.
The external race investigation requires no specific local patch before measurement.
Never inject local repair, remove race checks, downgrade repair to observed-only
or rerun unchanged work for a favorable seed. Historical replay can validate guard
forwarding while its historical engine lacks newer enforcement; current enforcement
needs local/live evidence.

Retain eleven actors maximum: 005/007 three each, positive 002 once and four live
once. Run seven distinct scenarios first (live 001, positive 002, 007, 005, then
live 002/003/004), followed
by four remaining replay repeats if eligible. Pilots count within their declared
source campaign; failed campaigns remain separate. Existing actor caps total $115
(seven at $5, four at $20); nested/judge costs are separate. Do not adapt caps,
deadlines, source, model or seed within that campaign after a failure. A supported
fix requires a separately declared measurement; preserve the stopped campaign.

Finish each cell's original stock stages, required samples, scenario checks and
independent whole-reply review before launching the next actor. Multi-case actor
batching cannot enforce that stop rule; model-free batching remains useful. Full
fixed-cohort acceptance requires every stock threshold/stage and independent
scenario/review requirement in [testing](testing.md): live001 may block correctly,
002 must repair with canonical gates, and 003/004 must prove native phases/artifacts.
Complete evidence with a false verdict still fails its threshold; a stock pass
with a factual contradiction still fails independent review. Stop on safety/
integrity failure or any failed required gate, aggregate threshold or review.
Dissent alone does not fail a majority. A predeclared two-of-three comparison may
continue only for its narrower question, not all-pass acceptance. Never pool
behaviorally different source groups or erase failed samples. Three fixture
executions establish repetition, not general safety or reliability.

## Deferred and bounded questions

Reviewer removal remains conditional on complete NEEDS_REVIEW/publication semantics,
including successful primary repair with failed indirect repin and absent/malformed
reviewer transport. Distinguish real compatibility/security blockers from advice.
Only then remove nested invocation, pre-review build/scan, retries and parser
together; otherwise retain the independent decision with validated reasons and raw
output. No temporary framework is needed.

Optional deletions do not block this campaign:

- After acceptance, trim duplicate eval README passages at lines 26–33, 70–91,
  338–345, 350–353 and 567–576, linking existing testing, live-result and case-007
  calibration owners. Preserve unique historical grades/limits and artifact paths
  at 557–565; remove obsolete cohort-selection sentences at 387/400/470.
- Trace the pre-verification `FINAL_SCAN`, which is only printed before the first
  audit independently rebuilds/rescans. Remove it only after accounting for artifact
  and sentinel effects; retain audit inputs and the authoritative final rebuilt scan.
- Remove duplicate full frozen-source validation and the duplicate PATH Grype
  identity probe only after confirming their callers share the same boundary;
  retain actual per-scan scanner identity and the integrity fence.

HEAD alone is not a scan cache key. Pure tuple/location parsing deduplication
preserves distinct gate meanings.

Source-coverage probes have not reproduced a real Go-exclusion/full false-clean.
Before adding a source check, compare real healthy/suppressed/omitted Go, non-Go-only,
dependency-free and native-only inventories. Keep the npm-type diagnosis narrow;
this is no implicit campaign gate or mandatory optional-native-proof requirement.
Actual-function proofs, checker counterexamples and full engine runs remain
distinct: helper outside writes or predicate proofs do not establish an observed
full publication bypass.

Defer broad rewrites, shell policy engines, fleet/scheduled evals, new recordings,
automated campaigns, publication execution and generic caching. Retain unique
proofs/limits under `.work/fix-go-cves-{design-audit,critical-waves,second-audit,third-audit}-20261023/`
and case calibration records. Replace superseded prescriptions rather than
accumulating audit chronology; do not remove failed trials or weaken rollback,
compatibility, ignore-policy, native-coverage or publication gates.
