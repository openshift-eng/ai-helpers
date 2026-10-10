---
name: analyze-payload-informing-jobs
description: Use when ranking unreliable non-blocking verification jobs across healthy OpenShift payloads, investigating job-local failures, and exporting evidence-backed repair or retirement recommendations.
---

# Analyze payload informing jobs

Analyze informing jobs only after freezing a bounded population of relatively
healthy payloads. This workflow produces local recommendations; it does not edit
release configuration, change schedules, open issues or PRs, decide payloads, or
trigger jobs.

## Inputs and defaults

Require `release`, `--architecture`, and `--stream`. Accept natural-language
equivalents and record the effective values. Defaults are a 14-day window ending
at collection start, 10 healthy payloads, 50 inspected payloads, 3 healthy
payloads, 5 distinct runs across 3 payloads per chronic conclusion, 90% blocker
health, 50% poor-job success, `--max-recommendations 10`, `--max-candidates 100`,
and `--time-budget-minutes 120`. Recommendation limits count distinct validated
repair mechanisms and validated retirement candidates; candidate limits count
distinct cohorts started in this invocation. Neither is a quota. The
default `--history-release auto-previous` uses only the verified immediately
previous release when a newly started release lacks history. Use `none` to
disable fallback or a release value to select it explicitly.

Reject rates outside `[0,1]`, nonpositive budgets, ambiguous lookback plus
start/end inputs, and non-UTC or reversed boundaries. A deliberately smaller
sample remains provisional. Freeze the end time and never add newer payloads on
restart.

Workspace/output paths are user-selected when supplied. Otherwise the workspace
is `~/tmp/analyze-payload-informing-jobs/<UTC timestamp>` and report exports are
fresh timestamped directories inside it.

Resolve bundled paths relative to this `SKILL.md`, independent of the current
working directory. Python 3.10+ and public HTTPS access are required.

## Collect, select, and rank

Read [population and ranking](references/population-and-ranking.md), then run:

```bash
python3 scripts/collect_payload_jobs.py RELEASE \
  --architecture ARCH --stream STREAM --workspace WORK
python3 scripts/rank_jobs.py --workspace WORK
```

The collector uses Sippy's `/api/releases/tags` and
`/api/releases/job_runs` array API. It records raw responses, provenance,
limits, unknown values, large Prow IDs as strings, and every payload association.
It never treats a display page as an API page. Review collection completeness,
payload health, role normalization, and any fallback mapping before accepting the
frozen selection. Unknown roles are not informing. Forced acceptance never
overrides blocker results.

Shared-failure interpretation requires AI review. Compare signatures across
independent job families, adjacent payloads, versions, and successful peers. Add
reviewed decisions with `--shared-failure-decisions FILE` and rerun ranking;
selection revisions remain in the manifest. Kubernetes or OS version skew is a
hypothesis to investigate, not an automatic common cause.

Ranking is deterministic and complete. It keeps association and unique-run
denominators separate, keeps current and previous-release rates separate, and
labels sparse cohorts. A raw worst performer may differ from the highest-priority
job-local candidate.

## Investigate prioritized cohorts

Read [investigation progress](references/investigation-progress.md) and initialize
the persistent queue before choosing jobs:

```bash
python3 scripts/investigation_queue.py plan --workspace WORK
```

Investigate pending cohorts before unchanged prior investigations. Continue through
the queue even if the first five yield no fixes. Stop new discovery at the validated
recommendation ceiling, candidate ceiling, elapsed time budget, or exhaustion of
feasible queued work; reserve time for review and export. Report the stopping reason
and next cohort. Completed investigations with unresolved causes still count as
explored; partial or interrupted work remains eligible for continuation.

Use the helper's `begin` before each cohort and `record` after saving its completed
finding. It enforces candidate/time limits and the validated count supplied from
actual review results; that count is accounting, not proof. Record a concrete
`revisit_condition` for unresolved or proposed actions. Subsequent runs use shared
history, prioritize pending cohorts, and recheck changed observations or documented
source/configuration/signature changes and newly feasible follow-ups. Preserve the
raw performance ranking and explain any investigation priority override.

For each queued investigation, sample as many as three failing
runs on different eligible payloads, plus the newest run and a passing control
when available. Invoke the `ci:prow-job-analysis` skill for each sampled failed
Prow run. Use the existing bounded artifact helper in the sibling
`investigate-ci-reliability` skill for metadata, listings, JUnit, and aggregate
child discovery.

Classify causal execution phase as `NOT_STARTED`, `SETUP_FAILED`,
`WORKLOAD_FAILED_BEFORE_REAL_TESTS`, `REAL_TEST_FAILURE`, `POST_TEST_FAILURE`,
`INTENTIONAL_TESTLESS`, or `UNKNOWN`. Record real, failed-real, and synthetic
test counts as integers or `null`; a JUnit file or successful setup alone does
not prove intended tests ran. Keep phase distinct from recurring mechanism.

Use failures from multiple payloads, passing controls, and unaffected peers to
decide whether a mechanism is job-local, shared, fixed, or unresolved. Inspect
current source and configuration, existing repairs, purpose, coverage, image/OS
adoption when relevant, and the precise causal failure. Source-only proposals
are proposed repairs until a confirming run exists.

For tests incompatible with a topology, platform, or common cluster configuration,
prefer shared OTE / `openshift-tests` selection or setup skips when multiple jobs
can be affected and the test setup supports the condition. Inspect existing
selectors and current registered names before proposing per-job `TEST_SKIPS`.
Follow the shared [test-selection scope guidance](../investigate-ci-reliability/references/proof-review.md#topology-and-platform-test-selection)
for ownership, validation, and justified job-specific fallbacks.

## Decide, review, and export

Read [recommendation contract](references/recommendation-contract.md). Record
per-cohort finding JSON under `WORK/findings/`, retirement records under
`WORK/retirement-candidates/`, and unresolved records under `WORK/unresolved/`.
Each finding needs a descriptive `title`, a two- or three-sentence `summary`, and
a concrete `next_action`. Explain performance, the sampled mechanism or unknown
cause, action, and uncertainty. Keep the ranked denominator separate from the
deeply inspected sample, and identify partial repairs and their remaining failures.
Record the owner, source/fix status, acceptance criteria, and limitations using
the readable handoff contract; the exporter renders these fields without diagnosis.
Then run:

```bash
python3 scripts/export_report.py --workspace WORK --output WORK/report
```

Allowed dispositions are `PROPOSE_FIX`, `RETIREMENT_CANDIDATE`,
`SHARED_FAILURE`, `ALREADY_FIXED`, `INSUFFICIENT_EVIDENCE`, and `KEEP_MONITOR`.
Uninvestigated ranked cohorts remain pending. Missing artifacts, an exhausted
budget, or an unknown cause cannot by itself justify retirement.

Repairs use the sibling reliability skill's evidence and independent proof-review
contract unchanged; only its `PROVEN_FIX` findings enter `fixes/`. Retirement
candidates use a separate digest-bound review. They require adequate population,
recent persistence, localization, documented investigation, exact current
verification and periodic configuration, cross-stream impact, coverage risk,
owners, validation, and restoration criteria. Say “no supported repair found
within the documented investigation” when that is the evidence.

When an informing job cannot execute its intended real tests and no supported
repair is found, a yearly retirement proposal must also set `disabled: true` on
its verification entry in the selected payload configuration, retaining the entry
and its job mapping. If the periodic is already yearly, retain that schedule and
still propose disabling payload verification. Preserve the periodic definition
and manual diagnostic use. Include both actions in the
summary, `next_action`, and unapplied configuration proposal; independent review
must reject a schedule-only proposal for this case. Zero tests alone and useful
intentionally testless work do not satisfy the retirement gates. Follow the
retirement contract for exact configuration targets and restoration criteria.

The exporter refuses an existing destination. It generates a linked ranked table
and `findings/<cohort-id>/README.md` for every current and historical cohort.
Investigated handoffs follow the sibling reliability format; pending cohorts get
short metrics-and-status summaries with cause and action explicitly unassessed.
It also writes manifest, payloads, rankings, evidence-linked findings, fixes,
retirement candidates, and unresolved records. Report the actual collection and
investigation coverage even when no recommendation passes review.
