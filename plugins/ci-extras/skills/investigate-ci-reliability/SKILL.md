---
name: investigate-ci-reliability
description: Find and independently validate actionable reliability defects across OpenShift release jobs and presubmits, then export portable issue handoffs. Use when asked to investigate reliability across a bounded CI run population and deliver proven fixes.
---

# CI reliability investigation

Investigate actual failed job runs, demonstrate the underlying defects, and deliver
an `issues/` directory containing only independently validated, currently applicable
fixes. This package contains its own collectors, review contract, and exporter.
Use the `prow-job-analysis` skill from the `ci` plugin for failed-job debugging;
no prior investigation repository is required.

## Inputs and defaults

- `release`: required OpenShift release, inferred from the request when stated.
- Window: **last 24 hours**, frozen at collection start; explicit UTC start/end supported.
- Scope: **all jobs in the release plus presubmits**. Presubmits are the separate
  Sippy `Presubmits` population, not implicitly restricted to merged PRs or that release.
- Optional scope: release-only, presubmit-only, or verified payload-blocking runs.
  Optional exact job, job substring, and variant filters narrow either population.
- `max-issues`: **10 distinct validated mechanisms**, a ceiling rather than a quota.
- `max-candidates`: **100**; `time-budget-minutes`: **120**; `max-agents`: **4**.
  These bound exploration, including review. Honor smaller user limits.
- Workspace/output: user-selected paths, otherwise `~/tmp/ci-reliability/<UTC timestamp>`
  and its `validated/` subdirectory. Scratch defaults to `~/tmp/ci-reliability`.
  Keep raw downloads bounded and separate from curated handoff evidence.

Invoke `/investigate-ci-reliability 5.1 --max-issues 10` directly. The skill accepts
these inputs in natural language or flags. Resolve bundled script paths relative to this `SKILL.md`, regardless of cwd.
The bundled scripts need Python 3.10+ and public HTTPS access. The investigation
also requires the `prow-job-analysis` skill from the `ci` plugin.

## Start and collect

Read [collection controls](references/collection.md) for exact collector flags,
verified blocking selection, pagination behavior, and completeness limits.

```bash
python3 scripts/reliability.py init --workspace WORK --max-issues 10
python3 scripts/collect_runs.py --release 5.1 --output WORK
```

Here `WORK` is the chosen workspace, not a literal required directory name. Run commands
using the resolved script paths. The default collector includes successful controls,
running jobs, and every failure code; preserve these distinctions in all rate calculations.
The manifest records the frozen interval and any truncation or missing evidence.

Group failures by job, phase, and recurring signature. Use the selected release and
presubmit populations as independent cohorts and deduplicate shared run IDs. Ordinary
unmerged PR defects are not automatically reliability issues: establish that a defect
in reusable infrastructure, product recovery, or test behavior causes the failures.
A selected PR SHA does not freeze base revision, batch membership, configuration, or images.

## Investigate bounded candidates

Invoke `$prow-job-analysis` for every failed Prow job being investigated, including
aggregate component jobs. Provide the exact run URL, frozen scope, and selected scratch
location. Follow that skill's metadata, artifact, OS-evidence, and domain-specific
investigation procedure. If it is unavailable, report the missing skill dependency;
do not substitute a second debugging workflow here.

Use the bundled [artifact helpers](references/artifact-helpers.md) for bounded acquisition,
caching, and retained evidence. Preserve the chosen scratch location and budgets when
invoking `prow-job-analysis`. The proof-review stage below determines whether the resulting
causal finding is ready for a validated handoff.

For aggregated jobs, retain the parent verdict and follow recorded component URLs.
Verify which children belong to the tested payload versus baseline/control cohorts.
Investigate causal component failures and sample/discovery shortfalls. Unavailable children
are explicit coverage gaps. Parent retries sharing children are not independent failures.

If delegation is available, assign disjoint candidates and reserve independent review capacity
within `max-agents`. Give each worker the frozen scope, shared budgets, scratch location,
the requirement to use `prow-job-analysis`, and the evidence contract. Otherwise investigate serially and
request a separate review context before promotion; self-review cannot satisfy the gate.
Do not change the agent installation's concurrency configuration.

Stop new discovery when the validated ceiling, candidate ceiling, or elapsed time budget
is reached. Finish review and export within the remaining budget; export fewer issues when
proof is incomplete. Do not lower the standard to fill `max-issues`.

## Record evidence and independent review

Write one candidate JSON per mechanism under `WORK/candidates/` using the
[evidence contract](references/evidence-contract.md). Curate text artifacts under
`WORK/evidence/` with source URLs, SHA256 hashes, and exact line ranges. Distinguish
observed cofailures from sole blockers; source defects can be demonstrated without
claiming every matching run would recover. A timeout, quota rejection, or hypothesis is
not yet a demonstrated incorrect behavior with a justified fix.

Perform the [independent proof-review stage](references/proof-review.md) in a separate
reviewer context. Give the reviewer the raw evidence, candidate, and contract. Require
counterarguments, current-fix verification, and the exact scope of the proposed repair.
A later candidate edit invalidates its review digest. Already-fixed incidents and unresolved
causes stay outside `issues/`, even when their historical impact is large.

## Export the deliverable

```bash
python3 scripts/reliability.py validate --workspace WORK
python3 scripts/reliability.py publish --workspace WORK --output WORK/validated
```

The exporter requires matching investigator and independent `PROVEN_FIX` verdicts,
valid evidence hashes/ranges, and distinct investigator/reviewer identities. It deduplicates
by mechanism, ranks by priority, and enforces `max-issues`. It checks the evidence contract,
not the truth of an agent's claim; substantive review remains essential.

Output is a fresh, portable snapshot:

- `issues/<slug>/README.md`: impact, root cause, owner, source state, proposed change,
  acceptance criteria, review reasoning, limits, and linked retained evidence.
- Each issue includes evidence files and machine-readable finding/review records.
- `index.html` and `README.md`: ranked validated handoffs.
- `manifest.json`: limits and published issue inventory.
- `unresolved.json`: rejected, unresolved, already-fixed, duplicate, unreviewed, and
  validated-over-limit records; excluded from the fix directory.

Publishing refuses an existing destination to protect hand edits and prevent stale approvals
from surviving a new run. Choose a new snapshot path to publish again. Report the actual
validated count and collection/proof gaps. Collection and export are local/read-only with
respect to CI: opening external issues, triggering jobs, or implementing fixes are separate
user requests.
