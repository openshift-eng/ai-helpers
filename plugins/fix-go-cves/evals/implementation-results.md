# Simplification implementation and verification

The 2026-10-22 candidate implements the [audited plan](../plans/e2e-simplification.md).
Acceptance is still open. Historical failures remain in the existing results;
new runs below do not replace their grades.

The skill is shorter and ordered around policy, execution, literal relay and
read-only diagnosis. Runtime changes retain both pipeline exits, preserve
observed package reasons alongside reviewer detail, report phase-specific scan
scope and enforce explicitly selected repository Go-minor restrictions without
restricting toolchain-only fixes. Native evals now require initial proof for
non-fast-path runs; release Subctl declares native coverage explicitly.

The positive Submariner publication recording uses a separate compatible scoring
profile sharing replay execution/contract configuration. Existing Admiral
replay configuration remains semantically unchanged. Its [calibration](cases/case-002/calibration.md)
records both the failed initial oracle and corrected independent witness.

## Local verification

| Check | Result |
| --- | --- |
| Eval helper tests | 70 passed |
| Focused evidence/relay/runtime checks | 349 passed |
| Focused Go guard checks | 34 passed |
| Reviewer scope/fact preservation checks | 14 passed |
| Model-free replay 005/007 and publication 002 | Reproduced retained commits and exit 2 |
| Strict site build | Passed |
| Clean source snapshot `make lint` | Passed; zero errors/warnings |
| Final immutable full shell suite | 3,102/3,102 passed; runtime/test bytes and modes match |

An earlier preliminary shell run was invalidated by concurrent source edits;
a subsequent snapshot exposed an obsolete assertion matching one physical source
line after a harmless line split. That assertion was replaced with a check of
`MAKEFLAGS` received by an actual scan build. The final suite runs an immutable
copy, with production hashes compared at completion.

Model-free readiness passed real Dapper file ownership on release/devel builders,
operation timeout, caller cancellation and container cleanup. Real runs use the
owned disposable rootless daemon, cached official builder images and inherited
`make unit`. Release runs preserve explicit Go/Kubernetes minor restrictions.
No target publication is executed.

## Declared actor measurements

Question, source hashes, identities, caps and run membership were frozen in
`.work/fix-go-cves-implementation-20261022/candidate-protocol.json` before launch.
Actor and judge model: `claude-opus-4-6`; CLI: `2.1.307`; harness:
`1a980e707909a23f8c143ce333d97f5203db34ab`. Per-run snapshots retain actual inputs;
whole-reply review and observed identities supplement stock grades.

| Measurement | Run ID | Status |
| --- | --- | --- |
| Initial replay 005/007 integration | `simplify-replay-20261022-01` | Both factual failures; 007 deterministic violation |
| Positive publication 002 | `simplify-publication-20261022-01` | Contract/outcome pass; action_owner fails; whole-reply rejected |
| Positive publication 002, clarified relay | `simplify-publication-20261022-03` | Duplicate rewritten recipe; deterministic/whole-reply failure |
| Admiral release, explicit canonical checks/policy | `simplify-live001-20261022-01` | Running |
| Admiral devel repair | `simplify-live002-20261022-01` | Not launched |
| Subctl devel native | `simplify-live003-20261022-01` | Not launched |
| Subctl release native | `simplify-live004-20261022-01` | Not launched |

The two remaining declared replay repetitions depend on inspecting the integration
results. Three judge samples are separate from three actor executions. Native
success, truthful blocked outcomes and missing repair coverage remain distinct.

Raw artifacts are under `.work/fix-go-cves-evals/runs/fix-go-cves:fix-go-cves/`;
verification logs, calibration inputs/reviews, complete Git caches and worker
ownership receipts are under `.work/fix-go-cves-implementation-20261022/`.
Failed initial model-free preparation used incomplete promisor Git caches; its
artifacts are retained, and complete fresh public Git caches corrected setup
without changing user checkouts. These setup failures did not execute actors.

## Initial integration findings

Publication trial 01 relayed the Summary/recipe exactly and named the correct
Shipyard owner and image-before-rerun prerequisite. Stock contract/outcome passed;
action_owner failed all three samples. Independent review additionally found an
invented publication-prerequisite failure, a guaranteed clean rerun and missing
explicit native catalog uncertainty. These failures remain recorded. Trial 03
clarifies those existing instructions without changing runtime or scoring criteria;
its source and question are separately frozen in `publication-v2-protocol.json`.
Trial 02 was an operator launch error: an edit failed in the wrong working
directory while the shell continued launching unchanged source. The identified
actor was terminated; incomplete artifacts and `publication-02-launch-error.json`
are retained. It supplies no revised-candidate acceptance evidence.

The generic Codex skill validator rejects this repository's existing Claude
`argument-hint`/`user-invocable` metadata. That metadata is preserved; the repository
linter validates its supported format.

The initial replay pair found the correct backport and remote-target prerequisite,
but both made unsupported causal claims. Replay 007 also missed actual retry
outcomes and attempted a denied `git stash`. Its deterministic contract failed;
005's contract passed. Both action_owner judges failed all samples. No reliability
repetitions of that failed candidate were launched.

Clarified publication trial 03 explicitly reported missing native proof and kept
future outcomes qualified, but added a second rewritten publication block; exact
Summary relay alone is insufficient. Independent review records the distinct
failure without treating every qualified expectation as a categorical guarantee.

The next instruction candidate replaces narrative freedom with one witnessed
result, supported scope and an observed-attempt ledger before repair advice. It
retains read-only history discovery and explicit image/remote-branch prerequisites.
`facts-candidate-protocol.json` separately freezes this changed hypothesis and
source. Its integration pair `simplify-facts-replay-20261022-01` is repetition 1/3;
positive `simplify-facts-publication-20261022-01` is also running. Old source trials
are retained separately and are not pooled into the new reliability comparison.
