# HTML Report Guide (Step 7)

The report is produced by filling `assets/report-template.html` — never by writing HTML structure or CSS from scratch. The template is the single source of truth for section order, markup, and styling; this guide defines how to derive the value for each slot.

## Template contract

- Replace every `{placeholder}` with a computed value. Any placeholder left in the final file is a defect (Step 10 check).
- Blocks bounded by `<!-- BEGIN: name -->` / `<!-- END: name -->` comments are conditional or repeatable; the comment states the rule. Duplicate repeatable blocks once per item, drop conditional blocks whose condition is false, and remove all marker comments from the final file.
- Keep the section order exactly as the template has it: hero → stat tiles → chain context → verdicts → blocking jobs table → failed job details → informing/flake tests → RHCOS changes → adversarial review → footer.
- All `<a>` links use `target="_blank"` (already present in the template).
- The file must remain fully self-contained: embedded CSS only, no external resources.

## Hero and stat tiles

- `{phase_class}` — `hero-rejected`, `hero-accepted`, or `hero-ready` from the payload phase; `{phase}` is the phase word rendered **verbatim** from Step 3.1 — never inferred.
- Stat tiles: `failed`/`total_blocking` (blocking jobs), `new_failures`, `persistent_failures`, `consecutive_rejection_count`, `hours_since_baseline`.
- `consecutive_rejection_count` — the number of consecutive non-`Accepted` payloads in the chain up to and including this one (the chain runs from the last accepted baseline forward — see `chain_length` and the `payloads[]` phases).

## Chain context card

- `baseline_tag` / `hours_since_baseline` — the last accepted payload and how long ago it was cut.
- `per_job_persistence` — for each failed job, "job_name: failing N consecutive payloads" from its `streak.streak_length`.

## Confidence meters

Every confidence score is rendered as the number plus a meter bar (never a bare bar): set the inline width to the score (`style="width:{score}%"`) and pick the meter class by tier — default (red) for >= 85, `meter-mid` for 50-84, `meter-low` for < 50.

## Verdict blocks

Placed after the stat tiles, before the per-job details:

- `revert-verdict` — include when revert candidates exist (score >= 85). One `revert-row` per candidate; the Confidence cell uses the meter pattern above, and the Rationale cell carries the itemized rubric breakdown from Step 6.1. Keep the `/ci:payload-revert {payload_tag}` copy block.
- `no-revert-verdict` — include when there are no revert candidates. Exactly one of these two blocks appears.
- `force-accept-verdict` — include only when Step 6.4 recommends force-accept.

## Blocking jobs table

One `job-row` per blocking job, passed and failed:

- **RHCOS badge**: from the snapshot's `rhcos_version` — `badge-rhcos9` (also for `rhcos9-default`), `badge-rhcos10` (also for `rhcos10-default`), `badge-rhcos-mixed` for `rhcos9_10`. When the job's failure is variant-isolated (Step 4 pattern recognition), add the `variant-isolated` class to the badge.
- **Status**: a `pill pill-fail` ("FAILED") or `pill pill-pass` ("PASSED") pill — the word is required; color is never the only encoding.
- **Streak**: consecutive failing payloads; "N/A" for passed jobs.
- **History**: the `failure_pattern` from the snapshot (e.g., "F F F S F F") rendered as history cells — one `<i>` per payload, newest first, class `f` (failed) or `s` (succeeded), each with `title="<payload_tag>"` when the tag is known.
- **First Failed In**: originating payload tag linked to the release controller; "N/A" for passed jobs.

## Failed job details

One `failed-job` collapsible block per failed blocking job:

- Summary line: job name, `badge-new` ("New Failure") or `badge-persistent` ("Failing for N payloads"), and the RHCOS badge.
- `variant-callout` — include only when the failure is variant-isolated; fill in which variant is affected.
- `analysis_from_subagent` — the subagent's failure analysis (Step 4), adjudicated where Step 5b applied.
- `known-symptoms` — include only when the subagent reported symptoms other than "none".
- Candidate PR table: one `candidate-row` per scored candidate for this job, Confidence cell using the meter pattern above.

## Informing and flake tests

Include the `informing-tests` block when `test_failures.informing[]` or `test_failures.flakes[]` is non-empty. List individual test names — never informing *job* counts (see Step 3.4). The caveat paragraph is part of the template; keep it verbatim.

## RHCOS changes

Include the `rhcos-changes` block when any payload in the chain has RHCOS RPM changes.

- `rhcos-candidates` — include when scored RHCOS RPM candidates exist (`type: "rhcos_rpm"`); one row per candidate with its itemized rationale, plus the `changelog-evidence` collapsible when any candidate has changelog evidence.
- **Cover every relevant hop, not just one.** Failure modes can have different `first_failed_in` origins, so a single origin's diff can omit evidence for another candidate hop. Keep one "Full RHCOS RPM Changelog Diffs" collapsible: render the baseline diff for each variant with changes (`rhcos-baseline-diff`), plus one `rhcos-hop-diff` subsection for each distinct (originating payload, variant) pair referenced by any scored candidate or failure mode that differs from the baseline. Do not create a separate collapsible per origin.

## Adversarial review

Fill `review_summary` from the Step 9 reviewer's response. Include the `review-issues` list only when the reviewer identified issues; each entry pairs the issue with the action taken.
