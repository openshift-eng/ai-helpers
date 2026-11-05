# Production readiness and simplification

The earlier runtime, delivery and evaluator checks are preserved. Codex-only
native validation completed across seven release-0.24 repositories. Five
reproduced runtime defects are fixed, and all configured checks pass in each
latest recorded run. Six overall exits remain partial for dependency/policy review.
[Results](../evals/implementation-results.md#current-design-closure-2026-11-04)
owns measurements and source identities; [testing](testing.md) owns contracts and
reuse rules. Historical actor grades remain tied to their frozen sources.
Hosted CI still needs maintainer authorization.

## Desired ownership

| Owner | Responsibility |
| --- | --- |
| Scripts | Owned mutation/rollback, compatibility and ignore policy, builds/tests/audits, scan coverage, retained-state checks and publication eligibility |
| Native delivery adapter | Consume one prepared request, run existing engines serially, retain original output/status and expose their log paths without another model request |
| One invoking AI | Select target and maintained checks from policy; prepare once in Claude Code, or launch/observe and summarize recorded outcomes with the log pointer in Codex |
| Existing evals | Verify operations/state and scenario coverage; retain complete text for separate independent factual review and preserve failures |

The deliverable is the complete captured LOG and original engine exit. The LOG
retains Summary/recipe, scope, complete stdlib alternatives and paired test
outcomes. Claude Code's native hook output owns delivery; earlier assistant text
remains visible and subject to factual review. Preparation stores private data; a
successful foreground callback validates the actual invocation and atomically
consumes its request. Codex retains direct execution, reads bounded excerpts for
progress and summarizes the engine's final evidence. This uses the invoking AI,
without another model call or reporting adapter.
Diagnosis, statistical reliability and unattended lifecycle remain outside
this demonstrated acceptance.

## Implemented simplifications

- Removed redundant scans, typed-to-legacy report conversion, nested model
  review/provider machinery, default diagnosis and Claude log transcription.
  Transaction scans, fresh verification and the post-test rebuild remain.
- Removed the unused evaluator evidence projection. Keep the full archived log
  and hash; validate frozen inputs freshly once per check, retaining cross-stage
  and source/interpreter fences.
- Removed dead counters, ignored-package history reconstruction, duplicate
  normalization and eager Make probes. Existing outcomes, shared normalization
  and automatic-command selection own those decisions.
- Parse each audit once and expose dirty names only after the whole result is
  valid. Parse current/HEAD ignore policy once per immutable decision; mutation
  and transaction checks still reread actual policy. Add no persistent cache.
- Reuse process cleanup and checkout validation instead of parallel mechanisms.
  Read-only detection now accepts retained fix branches; mutating runs still
  require branch setup. Build-image overrides identify the actual compiler.
- Replaced copied selector formulas and duplicate poison-model executions with
  production-path version/dispatch controls. Keep independent transaction,
  ownership, semantic policy and actual Git/Go tests.

## Current review disposition

Local suites pass for the recorded sources; the latest native fixes await fresh
review. Earlier frozen Subctl
binary/build/unit/license integration and report-only preservation retain their
source identities: the engine kept an honest stdlib blocker with partial exit 2;
report exit 0 meant completed measurement and preserved that finding. Earlier
native delivery/Admiral and paid actor passes likewise retain their frozen
identities. Review fixes use no paid Claude inference or semantic judges.

The repair base is discovered once from configured Git preferences, then shared
by fetches, policy reads, audits and publication identity. Ambiguous selection
stops before mutation; the push route remains separate.

Ownership loss stops later repairs/tests. Required policy-commit failures stop
dispatch; rejected ignores restore prior policy. Initial builds cannot redefine
the tracked baseline. Preparation carries approved session settings outside
selected worktrees; replay checks bind frozen driver and observed invocation
settings/arguments to the consumed request.

Interrupted native delivery preserves partial evidence and remains unconfirmed.
The pinned interactive cancellation control stops the child and later batch,
but the UI suppresses the normal LOG record; debug output is not visible relay.
Owned disposable-worker teardown is verified separately from plugin behavior.

## Next design and reliability work

The first installed Codex run exposed a delivery defect: completion-only reading
produced repetitive waiting messages and hid a useful partial result behind an
exit code. Remove that Codex restriction, reuse existing phase/Summary output,
and report retained work, gate outcomes, scope and required decisions. Keep the
terminal-exit witness and all engine ownership rules. Check archived evidence and
the installed skill without rerunning a completed repair or adding paid actors;
a later real invocation is still needed to measure the changed model behavior.

Proceed with maintainer review and hosted CI authorization. Add a change only for
a reproduced defect or a concrete missing decision/contract. Validate runtime
changes with focused behavioral controls and real execution before claiming live
coverage. Changed AI decisions need an affected, prospectively frozen actor
protocol with source, criteria, ordering, budget, deadline and stop rule; existing
finite actor passes do not promise all future runs pass.

The 2026-11-04 direct Codex runs used real Shipyard builds and Grype, without
model subprocesses. Subctl repaired four packages, passed race-enabled unit tests,
license checks and its final Go scan; a second build/report retained no Go
findings. Its unrelated GitHub Actions findings remain visible in the report.
Admiral's unit tests passed, but its Go 1.25 policy correctly rejected x/net
v0.62.0, which requires Go 1.26. Submariner's tools module has the same constraint.
Do not weaken compatibility guards or add ignores to manufacture passing scans.

Submariner also exposed a runtime defect: a later verification build regenerated
only the protoc-gen-go version stamp, blocking the strict pre-test tree check.
The canonical build reproduced the diff. Later tree checks now reuse the existing
generated-file reconciliation in restore-only mode; substantive output remains
dirty and blocked, and no source is staged or committed. Keep the initial scan's
strict mutation witness. The full 2deebd03 rerun completed in 20 minutes: tests,
deterministic verification, final scanning and licensing all completed with exit
0. It retained the partial repair at 6aa2776d and returned exit 2 for nine x/net
findings blocked by the tools module's Go policy.

Real Git controls then exposed a follow-up regression in 2deebd03: caching
checkout ownership before collecting status missed a HEAD or branch change during
that command. Keep the ownership check before restoration and repeat it after
status collection, without caching its verdict. Cover both movement types with
and without generator normalization; unchanged checkouts must still pass.

Operator's first 2deebd03 run completed its tests, scan and license gates, but
returned exit 2 after an unscoped ignore repair hit an unused root-module graph
dependency. Grype reported x/crypto only in tools/go.mod; tidy discarded the
irrelevant root bump. A native offline Go control reproduces that selection.
Narrow the shared repair dispatcher only when every reported occurrence points
to one tracked go.mod. Keep the original ignore selector for cleanup and review
classification; explicit, multiple-module, binary and unknown scopes retain
their existing behavior. The complete c6649279 continuation reaches tools/go.mod
and passes tests, verification, final scanning and licensing. It correctly
returns exit 2: x/crypto's proposed fix introduces the standalone vulnerable
OpenPGP module through Operator SDK's Helm plugin, so the regression guard
reverts it. The first fixed Helm release, v3.21.4, requires Kubernetes v0.36.2
in tools. A guarded parent-upgrade probe rejects that minor change and restores
the clean checkout. Do not weaken the regression gate or hide the new finding.

Lighthouse also exercises a successful bounded gRPC retry: the updated scan
reports v1.83.2 after v1.83.1 leaves an advisory unresolved. Two later audit
defects are corrected with real Go/Git controls. Existing scoped review markers
cover freshly built binaries only through the existing proven module mapping;
new findings and unproven ownership remain actionable. Merging redundant ignores
must preserve scoped expiry when Grype reports a published fix or an unsupported
state, rather than writing `fix-state: fixed`. The failed native branch remains
preserved; the continuation starts before its unsafe policy commit so that a new
baseline cannot grandfather the generated rule. The combined candidate passes
3,188 shell checks, 141 runtime tests and 82 evaluator tests.

The full e4e5bd28 Lighthouse continuation completes in 2,109 seconds with all
scan, test, verification and license gates at exit 0. One safe policy commit
retains scoped expiry; only one rejected CoreDNS attempt occurs. Independent
inspection confirms all four final binaries' hashes, clean VCS revision and Go
version, and all 26 binary findings against Go metadata. Its 46 outstanding Go
findings, including the published Crypto finding, remain visible; overall exit 2
preserves the real dependency/policy blockers.

Cloud Prepare and Shipyard complete with scan, unit and audit gates at exit 0,
preserving three package repairs/five findings and one package repair/one finding,
respectively. Their source-only scans retain ten and 14 findings for Go 1.25
policy review; build/license commands are unconfigured. All seven retained heads
match their tested source and are clean. Independent checks confirm declared
Go/Kubernetes minor restrictions across all 13 tracked modules. Submariner Bot
has no matching release branch.

Proceed with fresh maintainer review and hosted CI. Preserve the documented
source-specific results and original counterexamples. Go-minor and Operator's
tools-only Kubernetes exceptions on disposable branches await explicit user
direction; an unanswered question does not authorize either. Lighthouse's
coordinated CoreDNS/go-jose upgrade remains a target dependency review case.
Keep these outcomes visible rather than adding ignores or retrying unchanged
constraints. Add runtime code only for another reproduced defect.

Preserve stopped reporting protocols, original failures and costs in
[Results](../evals/implementation-results.md). Do not reroll or add model graders
to obtain favorable prose. Completed acceptance protocols are historical records,
not the next-work queue.

## Deferred work

Prefer upstreaming the shared runner lifecycle fix before deleting its local patch.
Keep cross-stage integrity fences; consolidate readers only when semantics agree.
Private request-format churn and extra binary-metadata caches do not currently
justify their cost. Use the existing explicit build-image override when a feature
or fix ref differs from its compiler-image tag; add no Make evaluator or branch
inference framework. Workspace vendoring, custom-compiler automation, speculative
scan gates, new recordings, fleet/scheduled runs and unattended lifecycle remain
outside this release.
