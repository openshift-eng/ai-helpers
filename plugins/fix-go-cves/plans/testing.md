# Testing and evals

## Layers and current status

Separate reproducible fixed-input contracts from remaining model decisions and
changing live inputs. Finite actor samples cannot prove all-time success.

| Layer | Question and economical verification |
| --- | --- |
| Hermetic scripts | Mutations, rollback, gates, policy and evidence: focused behavioral regressions for changed runtime paths. `make test` requires Go 1.24 or later and fails rather than skips with `CI` set. |
| Native transport | Does the actual interface deliver authentic output/status? Local synthetic transport can test dispatch without providers; it cannot establish model quality, interactive behavior from print mode, or CVE repair. |
| Historical replay | Admiral 005/007 cover failures/retries; Submariner 002 covers publication and complete stdlib alternatives. Changed AI duties need affected actors; recorded engine output cannot validate today's engine. |
| Live execution | Four packaged scenarios exercise canonical commands/scans. Reuse unchanged direct engine proof by component identity; engine acceptance and invoking-reply acceptance remain separate. Database, builder and target-test variation stay explicit. |

Current-source checks and independent review pass; the
[results record](../evals/implementation-results.md#current-design-closure-2026-11-04)
owns counts, source identities and qualifications. The
[production plan](e2e-simplification.md) owns scope and remaining review.
Historical actor grades stay tied to their frozen sources; a script pass,
stock majority or old-trace recheck cannot validate revised actor behavior.
Setup belongs in the [eval README](../evals/README.md); unique historical outcomes
remain in the results and [live record](../evals/live/README.md).

## Runtime and behavioral acceptance

A live contract checks the invocation, retained state, observed terminal result
and allowed operations. Independent whole-reply review assesses facts and report scope;
scenario-specific assertions check actual engine evidence independently of prose.
A faithful report of an engine defect can pass behavioral checks while failing
runtime acceptance. Missing receipts cannot be replaced by a matching `run.json`.
Live completion accepts only runtime exits 0 or 2, with the emitted Summary, clean
fast-path message or authenticated terminal abort evidence as applicable. Setup
exit 1 and interrupted exits 130/143 remain failed measurements even when receipts
are retained.

| Scenario | Required runtime evidence |
| --- | --- |
| Blocked or partial run | Real execution and authenticated terminal result; reached scans and gates retain their actual exits, attempted tests retain paired logs/receipts, and the reply accurately reports blockers without follow-up mutation |
| Successful repair | Completed initial scan/receipt at the pinned base with an actionable finding, retained dependency repair, canonical tests and four typed audits passing, valid authoritative final scan with zero actionable findings, runtime exit 0 |
| Native binary | Unique canonical artifact witnesses: initial proof bound to the pinned base and final proof bound to retained HEAD after remediation: fresh build, binary SHA/clean embedded VCS and positive catalog location/file hash; retained bytes match and canonical gates pass. A clean fast path needs only initial proof and does not count as repair |

Native coverage can accompany a valid partial exit-2 result; it does not establish
successful repair. The current binary contract requires initial and final
native proof outside clean fast paths, independently of prose review.
Preserve historical grades under their original contracts; the
[production plan](e2e-simplification.md#next-design-and-reliability-work) records remaining work.

Frozen input/annotations govern scenario, pins, guards, commands and replay
outcomes. Collected paths/state cannot downgrade that authority. Required scan
phase/HEAD checks are unconditional for required scenarios, while genuinely
unreached phases remain valid for observed blocked runs. Reject duplicate canonical
native paths rather than allowing later records to overwrite failed evidence.
Track the entry kind, content and relevant executable mode actually promised by
unchanged-source/native-output claims; do not freeze unrelated UID/timestamp data.
For the published-fix exercise, nonempty `fix.versions` alone is insufficient:
require a usable supported threshold, an actual retained dependency repair and
clearance of the finding. Specify and independently test release/pseudo-version,
empty, prerelease, malformed and mixed cases, preserving module versus stdlib
version rules. Removal can legitimately remediate a vulnerability without meeting
that narrower exercise criterion; database drift alone cannot supply coverage.
Focused contradiction controls cover these contracts; complete E2E acceptance remains separate.

Replay capture binds staged driver and metadata bytes/modes to trusted prepared
inputs, including missing or linked files. Trace checks inspect direct commands;
nested shell programs, aliases and other indirection still require whole-trace review.
Native delivery uses single-line log paths. A newline in `TMPDIR` retains the
log/status but falls outside the collector's path grammar; only a controlled
helper-level failure was demonstrated, without native CLI failure or data loss.

Keep these runtime boundaries covered:

- Command and logger results remain separate. Required gate-capture failure blocks
  downstream gates; interrupted retries inherit neither a prior exit nor output.
  Preserve completed attempts and partial evidence, including cleanup failures.
  Optional archive-copy failure instead retains the engineering exit, warns and
  preserves available private diagnostics/recovery paths; an eval needing missing
  evidence fails. Do not turn optional native proof into a production gate.
- Run one canonical test phase after bounded deterministic
  verification finishes dependency/policy changes, retaining its existing bounded
  retry, without an early suite or conditional policy-excluding retest. Tests
  witness the exact retained HEAD, including policy-only commits; passing tests
  cannot clear failed verification. Unreached phases remain unreached.
  Each attempt preserves its HEAD, logs/receipts and clean tracked state. Remove
  only root `go.work` and `go.work.sum` generated by tests when absent before
  and still untracked afterward; preserve existing files. Cleanup failure
  stops verification. Keep configured post-test cleanup with this phase; capture
  its exit and block confirmation on failure even if tracked state is clean. Bind
  final expected HEAD to `TESTED_HEAD` before cleanup; cleanup cannot commit a new
  tree and silently redefine verified source. Preserve historical attempts under
  their original ordering.
- Verification requires all four audit scripts and fresh, complete, unique
  nonnegative integer counters.
  Missing/malformed evidence blocks; positive findings enter the bounded repair
  loop. Poison-provider controls verify that deterministic verification invokes
  neither model CLI.
- Artifact deletion requires current content/type ownership and canonical
  containment through every path component. A pathname from a previous run is
  insufficient. Preserve changed, linked, tracked or otherwise unowned outputs.
  Abort cleanup must preserve an unexpectedly moved checkout/index rather than
  reset another branch. Committed-abort rollback policy is a separate decision.
- Internal Go graph/get/tidy/vendor/edit commands bind to the exact canonical
  owned `go.mod` using native `-modfile`, clearing overlays where supported.
  A path-only `go env GOMOD` or module `Dir` check cannot establish effective
  read/write bytes. Keep native Go parsing and caller build/test flags; fixing
  only a writer leaves policy reads inconsistent. Validate regular, tracked,
  single-link selectors, canonical parents, derived sums and nested-checkout
  boundaries. Existing regular checksum files may be tracked, untracked or ignored:
  capture/restore their pre-state and add only previously absent files. Preserve
  outside module/sum bytes and cover absolute, relative, stored and quoted flags,
  aliases, overlays, hardlinks and workspace transactions with actual minimum/
  current-Go get/tidy/vendor/build/rollback controls.
- Built-in workspace synchronization must stay within the canonical owned,
  tracked transaction module set. Validate workspace identity/use ownership with
  a nonmutating local-toolchain read before graph/update writes; reject unowned/
  outside effective members while preserving internal modules and replacements.
  Existing snapshots, policy/staging and rollback must cover every mutable member.
- Final rebuild/scan and license checks preserve the post-verification retained
  HEAD and clean tracked state. The zero-finding fast path checks unchanged source
  before normalization can conceal a change. Add no automatic repair or commit to
  make these checks pass.

Real execution of a changed path remains separate from hermetic verification.
Reporting-only unknown native scope must not set the blocking opaque-binary
coverage marker. Required capture failures stay distinct from optional reporting
proof; publication cannot rely on missing required evidence.

The delivered record must retain the actual Summary, exits, attempts, fixed/ignored/remaining
findings, observed original ref when available, coverage and publication
availability. When no Summary is emitted, relay the terminal clean/error message; absent completion
evidence remains unconfirmed. Skipped or unconfigured checks remain unverified.
Unknown native coverage is not proof of a source-only scan; positive native
coverage is not stdlib remediation unless a stdlib finding was actually repaired.
A no-findings fast path does not exercise repair. The positive historical
publication fragment tests detection and exact witness relay. Packaged case 002
now permits measuring actual invoking-agent relay; its calibration is not actor
acceptance. Local-only or ambiguous remotes can correctly
withhold a PR recipe; generation must bind base/head and all push destinations.
A renamed fork or same-named repository cannot be authenticated by basename.
Exact historical recipe relay is distinct from current generation correctness; do not invent a fork or publication steps. No eval pushes
changes or creates a PR.

The current candidate delivers the complete LOG and original engine exit through
native hook output, preserving Summary/recipe, scope, complete unresolved stdlib
alternatives and paired test outcomes without model copying. Earlier assistant
text remains subject to whole-visible factual review: an unsolicited cause or
future promise still fails. Codex retains direct execution, bounded progress reads
and an evidence-based outcome summary with its log pointer. Check that partial
and report-only exits keep their meaning, absent/unconfigured checks stay
unverified, and no intermediate line is mistaken for completion. Native hook
tests establish no Codex model-compliance guarantee. Requested
diagnosis and old backport/owner controls remain outside this default acceptance.
Old literal-reply contracts, false grades and source identities remain preserved.

Use user and maintainer policy to select branch-maintained checks; CI/Make target
presence alone does not establish a required gate. The user clarified that
Submariner release `golangci-lint` is not maintained for these repairs. Preserve
historical lint runs as evidence of our incorrect override, rather than requiring API repairs
or relaxed rules. Explicit live `make unit` settings measure forwarding/execution;
conflicting inherited-command selection has separate forward-review coverage.
Keep builder capability separate from repository compatibility
[restrictions](e2e-simplification.md#desired-ownership); the candidate's explicit guards carry those
restrictions without inferring approval. Keep genuine repository
instructions, including competing manual procedure, in the fixture.

## Environment, evidence and limits

The baseline shared harness revision is
[`1a980e707909a23f8c143ce333d97f5203db34ab`](https://github.com/opendatahub-io/agent-eval-harness/tree/1a980e707909a23f8c143ce333d97f5203db34ab);
the identified [patch](../evals/harness.patch) repairs its inherited-pipe/status
boundaries. Record base revision plus effective code identity and revalidate
changed paths. Preserve the prepared plugin basename and prove that actual skill
intake and invocation shim refer to that prepared copy. Follow the existing
[setup instructions](../evals/README.md#setup), including fresh-HOME authentication.
Use one absolute venv interpreter for hooks, drivers, judges and stock stages,
with PyYAML `CSafeLoader` and required child imports verified. Preserve its venv
entrypoint and identify actual executable/version/packages; dependencies must not
rely on shell activation or silent fallback Python.

Record actual runtime/helper and staged-wrapper hashes, case pins, CLI/model and
harness identities, scanner path/version/hash or image digest, database status and
builder/compiler identity. Resolve the CLI through the launch PATH, pin the
version-specific executable and compare the native init version with that frozen
identity.
Cache reuse does not freeze the database or builder. Keep identity metadata,
not vendored database/image archives. Test fixtures must bound Git discovery
without hiding genuine nested repositories; checks need their required CI
metadata/environment, not an inferred dependency-graph change.

Keep package-bearing tools, caches, logs and evidence outside the scanned tree;
`.git` does not exclude them from Grype. The source-only staged plugin and driver
retain stock layout. Fresh HOME, local remotes and trace/permission checks are
not host isolation. Literal-path trace checks do not prove answers inaccessible
through shell variables; minimize answer-root exposure without claiming a sandbox.
Use disposable build resources through the shared environment
before unattended work; a container with the host Docker socket can still affect
host resources through repository cleanup. Do not add a plugin-specific sandbox.

Revalidate Dapper ownership mapping and partial-evidence cancellation when
recreating the rootless worker. Merely setting `DOCKER_HOST` did not preserve file
ownership; the supervised worker entered its dedicated daemon's user/mount
namespaces. Preserve targeted operator cleanup: unattended teardown remains
unproven. Keep worker lifecycle in the shared environment, with ownership checks
and explicit disposition rather than another plugin preflight layer.

`CVE_FIX_SCAN_TIMEOUT` bounds shared scanner/database operations; bounded
termination, cleanup and fallback add time. It is not a whole-pipeline deadline
and excludes installer downloads/generic daemon probes. Healthy scans do not
prove termination of stalls; controlled timeout/cancellation fixtures do. Record
environment failures, operator stops and partial evidence separately from actor
behavior, retaining observed violations even on interrupted trials.

The selected shared runner must return after deadline/cancellation within its
declared bounded termination/drain reserve, even when descendants hold stdout or
stderr and the leader exits. Preserve partial traces and raw per-case status;
aggregate any nonzero status as failure. Process-group proof does not establish
container/daemon cleanup. A changed or patched harness needs its effective source
identity and local integration controls, not just an unchanged revision string.

Use declared budgets/deadlines from the existing configurations: live actor $20
and 3,600 seconds, replay settings unchanged. Parent caps do not cover all nested
model/judge costs. Record known actor costs and unknown judge/total costs; never
extend or retry a cell adaptively after a budget or timeout failure.

## Measuring relevant changes

For an actual delivery change, check the real supported output with known false
generated text and authentic archived records before another paid actor. The
artifact must be accessible and correctly identified; missing/swapped evidence,
partial exits and interrupted completion retain their meaning. Keep whole-reply
review blocking while generated prose remains visible. Never score just an
artifact to conceal the old delivered falsehood. Existing integrity, receipt,
recipe, scope and timeout controls need no duplicate prose-matching suite.

The existing invocation record captures only raw `CVE_FIX_TEST_CMD`,
`CVE_FIX_GO_MINOR_GUARD` and `CVE_FIX_K8S_VERSION_GUARD` overrides, preserving
unset/empty/false distinctions. These are not fully effective settings because
configuration/defaults may apply; old records without them remain unknown.
Compare with adjudicated fixture expectations without a model grader. Prefer
existing versioned configuration for routine policy, preserving current environment
precedence; changing conflict handling requires separate behavior review.

Validate a changed engine path with meaningful hermetic regressions. Require a
real case reaching it when claiming live/E2E coverage of that path; isolated
predicate/preservation fixes do not each require another paid actor. The declared
fix-only cohort does not validate report-only, every YAML layout or publication
generation on a positive remote. A clean scan does not exercise repair, inherited-policy
rejection or stalled-scanner termination. Feed engine defects into script tests
and interpretation defects into relevant existing replays. Do not hand-repair
targets, fake findings, stub native tools, skip canonical gates or add broad
ignores to obtain coverage. Database drift can remove a finding: record missing
coverage and deliberately select another suitable pin only when justified.

Before a comparison, freeze its question, membership, source, criteria and
configuration. Keep actor executions distinct from repeated judge samples and
inspect every cell rather than pooled rates. Complete each normal actor run's
stages, grading and whole-reply review before launching the next; model-free
multi-case controls do not incur that restriction. Each prospective frozen
protocol owns its ordering and caps. Stop when any required gate, aggregate threshold or review disqualifies
all-pass; preserve disagreements without tuning or adaptive reruns.

Default profiles perform deterministic scoring only. Release acceptance also
requires the independent review declared in the production plan. Check that
procedure against applicable fixed positive/negative controls before actors;
a role-positive control does not establish whole-reply acceptance. Reviewers get
complete evidence and applicable criteria without expected labels or prior
rationales. Retain failed controls, dissent and actual source identities. These
inspected regression controls are not unseen holdouts or reliability estimates.

Historical sampled profiles retain their original three-sample strict-majority
rules, errors, raw values and costs. Do not reclassify stopped experiments or
contract-only runs as passes under those protocols. A custom sampled profile
still requires every configured error-free result; malformed responses are errors.

Evidence reuse follows the changed component. Documentation needs no executions.
A changed oracle needs affected calibration and separate scoring of sufficient
immutable archived replies; a validator needs local contradiction controls and
separate rechecks where existing facts suffice. Skill/instruction changes need
affected actors; runtime/staging/environment changes need focused controls and
fresh real execution reaching affected paths for a live coverage claim. Missing
new fields remain unknown. Keep the original manifest/helper-hash fence: never
rewrite it to let a changed helper masquerade as original scoring. A corrected
interpretation records new oracle and exact archived input identities separately,
without a new recheck service/schema or an untouched E2E-pass claim.

The historical **fixed-fixture replay comparison** protocol requires the deterministic
contract in all three independent actor executions, with all factual criteria
together in at least two. An individual failed execution still exits nonzero;
this is not a per-run threshold, statistical confidence or a live repetition
rule. The historical eleven-actor all-pass milestone was a separate, stricter question.
Historical coverage inventories supply no retrospective pass or actor credit.
Do not mechanically run three expensive live trials or another six-cell
cohort for borderline scores. A further measurement needs a concrete changed
question or environment condition, not another attempt to obtain accepted prose.
Declare which unchanged-source executions satisfy both integration and repetition
before launch; do not run separate cohorts for the same evidence. Never pool
repetitions across behaviorally different source groups; a documentation-only
commit does not change identical execution components. Scoring-only recovery restores the exact original frozen helper and verifies
unchanged actor artifacts; retain the initial failure and interpreter/source
identities. Completed failed samples cannot be overwritten as recovery. Keep
skipped, partial and newly executed judging distinguishable, including the
executed-scan versus cleanup-restored HEAD.
Compare current skill hashes across applicable cases and runtime hashes across live cases;
validate historical runtime archives against their own pins. Preparation copies
current files per case rather than freezing their bytes with the YAML alone.

## Recording admission

Original recordings 002/005 under `.work/fix-go-cves-evals/source/` are now
packaged; 007 is a later live capture. Case 002's applicable publication/builder
[calibrated controls](../evals/cases/case-002/calibration.md) preserve both corrected
witness boundaries and earlier false positives/criterion-bleed errors. Admission
and calibration do not establish actor acceptance.
Admit another only for a concrete new decision/regression. Prepare its complete
artifacts model-free and calibrate applicable criteria before measurement.

| Recording | Unique admission scope |
| --- | --- |
| 001 — Lighthouse license | Correct `cdc3003` backport advice: repair must reach the remote target before rerunning |
| 002 — Submariner partial | Packaged/calibrated; positive PR relay and complete stdlib alternatives |
| 003 — Cloud-prepare clean | Flagged lines needing no action; heavier live-success alternative |
| 004 — Subctl binary | Correct reference and empty binary contradicting the log; cover x/net, grpc and otel/sdk blocked bumps |
| 005 — Admiral govet | Already packaged/calibrated; preserve its failed baseline |
| 006 — Lighthouse x/crypto | No remaining x/crypto finding after GO-2026-5932 no-fix ignore; license repair needs remote-target backport advice |

Do not invent additional x/crypto action, a Go raise or team decision for 006.
Keep historical Go-raise scoring neutral where that recording did not resolve policy.
Sanitize home paths and exclude unrelated connector/memory metadata; add binary
or report evidence only where required. These recordings supported tuning and
regression, not generalization. Defer fleet coverage, scheduled canaries,
automated campaigns and direct reviewer evals until a concrete gap warrants them.
Do not expand to actual target draft-PR updates until the relevant output is
independently correct and produced by the skill; no custom hand repair.
