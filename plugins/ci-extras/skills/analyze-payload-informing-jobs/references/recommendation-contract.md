# Recommendation and report contract

All machine-readable records use `schema_version: 1`. Times are explicit UTC,
hashes are lowercase SHA256, missing observations are `null`, and substantive
claims reference evidence records with source URL, retrieval time, retained path,
hash, exact excerpt location, and evidence role.

## Finding

A finding identifies one stable cohort, selected payload/run IDs, current and
previous-release metrics, sampled runs and controls, intended purpose, causal
phase, mechanism/signature, current source/configuration state, contrary
evidence, limitations, investigation status, and disposition. `PROPOSE_FIX` needs
a supported mechanism, exact change scope, owner, acceptance criteria, and
current applicability. The sibling reliability package remains authoritative for
validated repair candidate/review schemas and `PROVEN_FIX` export.
Test exclusions follow the shared
[test-selection scope guidance](../../investigate-ci-reliability/references/proof-review.md#topology-and-platform-test-selection).
The proposed change must explain why its scope covers affected jobs while
preserving execution in compatible environments. A per-job workaround needs a
reason the shared condition cannot be used and, if temporary, a removal condition.
Record an explicit `revisit_condition` for unresolved or proposed actions so later
invocations can distinguish a feasible follow-up from repeating unchanged work.
Use the [investigation progress contract](investigation-progress.md) for shared
history, queue ordering, exploration ceilings, and continuation.

## Readable job handoff

Every finding must supply nonempty strings `title`, `summary`, and `next_action`.
The AI writes a descriptive title and a two- or three-sentence summary covering
observed performance, failure phase/mechanism or explicit unknown, recommended
action, and uncertainty. Do not attribute the whole ranked failure population
to a mechanism observed only in the investigation sample.

Use the sibling `investigate-ci-reliability` issue README structure:

| Section | Finding data and interpretation |
| --- | --- |
| Summary | `summary` and `next_action`; action must be readable without opening JSON. |
| Impact and affected runs | Ranked identity, population/window, success metrics and denominators, sample sufficiency, recent behavior, configuration/upgrade route; `sampled_runs` and `execution` describe the separate investigation sample. |
| Root cause / demonstrated mechanism | `mechanism`; retain uncertainty and separate shared causes from local defects. |
| Current source and fix status | `current_source_state`, including revisions, existing repair checks, and adoption/applicability. |
| Suggested action and owner | `next_action`, `owner`, `proposed_change` or `proposed_followup`; explicit unknown owner if unresolved. Changes remain unapplied, and partial repairs disclose residual failures. |
| Validation and acceptance | `acceptance_criteria`; retirement proposals also expose `restoration_condition`. |
| Limits and unresolved cofailures | `limitations`, `contrary_evidence`, and passing controls; disclose missing evidence and uncovered mechanisms. |
| Independent review | Actual analysis/retirement review status and scope; unavailable or stale review remains explicit and does not establish repair proof. |
| Evidence | Relative retained-file links, source URLs, retrieval times, hashes, and excerpt locations below the readable explanation. |

`sampled_runs` is a list with string `run_id` (or `prow_run_id`), `url` (or
`prow_url`), `payload_id`, result, and per-run execution observations. Keep full
ranked metrics authoritative in `job-rankings.json`; never replace the terminal-run
denominator with the investigation sample size. Structured mechanism/source/action
fields may be prose, lists, or objects; the renderer preserves their content.

Optional `WORK/analysis-review.json` follows the existing analysis report format:
top-level `reviewer_context_identity`, `reviewed_at`, `scope`,
`selection_version_checked`, and a `findings` list. Each entry identifies
`cohort_id`, `finding_sha256`, `verdict`, `reasoning`, and `evidence_checked`, with
counterargument and outstanding concerns where applicable. The finding digest
is SHA256 of canonical JSON excluding its top-level `review` (sorted keys,
compact separators, UTF-8, `ensure_ascii=False`). A review is displayed as current
only when its digest and selection version match, its reviewer differs from the
finding's `investigator_context_identity`, and those review fields are present.
Otherwise the handoff reports stale/incomplete review. This displays an analysis
attestation; proven repairs still require the unchanged sibling proof gate.

Pending cohorts receive shorter generated summaries of identity, scope, metrics,
recent behavior, sample sufficiency, and pending reason, with no invented cause
or repair. An optional ranking `pending_reason` explains budget or evidence gaps;
otherwise the exporter states that no completed investigation is recorded.
Sparse observations do not establish chronic failure, and pending status does
not clear a job. Keep historical summaries and their windows separate.

## Retirement candidate

A retirement record is separate from a repair. It requires:

- current cohort identity and chronic-performance evidence meeting configured
  distinct-run and payload minimums;
- release-specific counts and mapping evidence when predecessor history helps;
- current persistence, including recent-three behavior and recovery checks;
- localization with supporting and contrary peer results;
- sampled execution evidence, investigated hypotheses, source checks, and the
  reason no supported repair was found within the bounded investigation;
- exact release-controller alias/entry, actual Prow job, pinned source revision,
  periodic definition, current schedule, valid proposed yearly schedule, and an
  unapplied patch or before/after excerpt;
- every other stream/release/architecture consumer, coverage/replacement analysis,
  residual risk, owner, validation steps, and restoration condition.

For an informing job unable to execute its intended real tests, when no supported
repair is found and yearly operation is recommended, require one combined proposal:

- Set `disabled: true` on the exact informing verification entry in the selected
  payload configuration, retaining its alias, job mapping, and other fields.
  Record its path, alias, underlying Prow job, and pinned source revision.
- Set the associated periodic to a valid yearly schedule, retaining its definition
  and manual diagnostic use. If it is already yearly, explicitly retain that
  schedule and still disable the payload entry; no redundant schedule edit is needed.

The periodic schedule does not prevent payload-triggered runs. For
`5.1 --architecture amd64 --stream nightly`, the payload target is
[`core-services/release-controller/_releases/release-ocp-5.1.json`](https://github.com/openshift/release/blob/main/core-services/release-controller/_releases/release-ocp-5.1.json):
propose setting `verify["<selected-alias>"].disabled` to `true`, as in the
[4.21 release configuration](https://github.com/openshift/release/blob/main/core-services/release-controller/_releases/release-ocp-4.21.json#L91).
Resolve the appropriate configuration for other scopes instead of reusing this
example path.
Keep unrelated verification entries intact and check other consumers before
proposing a shared periodic change.

`configuration.unapplied_change` must contain a reviewable patch or before/after
excerpt setting `disabled: true` on the retained payload entry. Include the
periodic schedule change in the same proposal; if it is already yearly, include
evidence that the yearly schedule will be retained instead. The finding's
`summary` and `next_action` must name both disabling payload verification and
yearly operation.
Validation checks the proposed payload JSON, retention of the selected entry
with boolean `disabled: true`, preservation of its job mapping and other entries,
and retained periodic/manual capability with the yearly schedule.
Restoration criteria cover clearing or setting `disabled` to `false` and
restoring normal periodic frequency when the job can provide reliable coverage.

This rule does not waive any retirement gate. Zero test counts alone, missing
artifacts, or an unknown cause are insufficient, and useful intentionally testless
jobs do not qualify merely because they have no real test cases.

Do not combine `interval` and `cron`. Validate scheduler syntax and timezone.
When a periodic is shared, disclose affected consumers and present scoped
alternatives. Keep the job definition and manual diagnostic use unless a later
request explicitly changes that scope.

## Review

Canonicalize the recommendation JSON without its review, hash it, and bind the
review to that digest. A review records a distinct reviewer context identity,
time, evidence checked, counterarguments, verdict, and outstanding concerns.
Editing the recommendation invalidates the review.

Retirement review verdicts are `VALIDATED_CANDIDATE`, `REJECTED`, or
`INSUFFICIENT_EVIDENCE`. They validate persistence, localization, investigation,
configuration, impact, and scope; they do not claim an unknown defect has a
proven repair. An unavailable independent review leaves the candidate
`UNREVIEWED`.

For the qualifying no-tests outcome, reviewers must check both `disabled: true`
on the retained payload entry and the proposed or retained yearly schedule.
Reject a schedule-only proposal that leaves the selected payload verification entry active, including
when the periodic is already yearly.

## Export behavior

Export to a fresh directory and verify every retained evidence hash and relative
link. Include:

- `README.md` with complete current/historical ranked tables linking every
  cohort summary; `manifest.json`, `payloads.json`, and `job-rankings.json`;
- `findings/<cohort-id>/README.md` generated on every export; investigated cohorts
  also include `finding.json` and evidence/control links, while pending cohorts
  have no manufactured finding record;
- optional `analysis-review.json` retaining the analysis attestation and scope;
- `investigation-queue.json` when queue state exists, preserving stopping reason,
  pending/recheck/deferred work, and prior investigation context without importing
  prior findings as current diagnoses or renewing their reviews;
- `fixes/` containing only sibling-exported `PROVEN_FIX` repair handoffs;
- `retirement-candidates/` containing recommendation plus matching review;
- `unresolved.json` containing pending, sparse, shared, fixed, rejected,
  unreviewed, and insufficient records, including zero-validated-fix runs.

The manifest states inspected/selected counts, both windows, population roles,
fallback trigger/result, selection version, budgets, limits hit, provenance,
artifact inventory, missing evidence, and investigation coverage. Reaching a
limit changes coverage; it never changes the evidence threshold.

The exporter generates summaries from validated records instead of copying
manually authored README files. The visible disposition uses actual finding and
review status; unvalidated proposals do not inherit the sibling handoff's
“independently validated current defect” label. Retirement recommendations and
their available reviews are linked within the corresponding cohort summary,
including unreviewed or rejected proposals; only validated candidacies enter
`retirement-candidates/`. Proven repair handoffs are reused unchanged in `fixes/`.
