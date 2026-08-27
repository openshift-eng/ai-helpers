# HTML Report Guide (Step 7)

The report is produced by filling `assets/report-template.html` — never by writing HTML structure or CSS from scratch. The template captures the canonical production Payload Agent report format; this guide defines how to derive the value for each slot.

## Template contract

- Replace every `{placeholder}` with a computed value. Any placeholder left in the final file is a defect (Step 10 check).
- Blocks bounded by `<!-- BEGIN: name -->` / `<!-- END: name -->` comments are conditional or repeatable; the comment states the rule. Duplicate repeatable blocks once per item, drop conditional blocks whose condition is false, and remove all marker comments (and the leading contract comment) from the final file.
- Keep the section order exactly as the template has it: header + metadata → executive summary → verdicts → blocking jobs summary → failed job details → RHCOS changes → informing tests → adversarial review → footer.
- All `<a>` links use `target="_blank"` (already present in the template).
- The file must remain fully self-contained: embedded CSS only, no external resources.

## Header, metadata, and executive summary

- `{phase}` is rendered **verbatim** from Step 3.1 — never inferred.
- `consecutive_rejection_count` — the number of consecutive non-`Accepted` payloads in the chain up to and including this one (the chain runs from the last accepted baseline forward — see `chain_length` and the `payloads[]` phases).
- `baseline_tag` / `hours_since_baseline` — the last accepted payload and how long ago it was cut.
- Per-job persistence: one `persistence-item` per failed job from its `streak.streak_length`.

## Scores

Every score uses the tier classes: `score-high` (>= 85), `score-medium` (50-84), `score-low` (< 50). The Recommended Reverts table always shows the score in its Score column with the itemized rubric breakdown (Step 6.1) in the Rationale column, one signal per line separated by `<br>`.

## Verdict blocks

Placed immediately after the executive summary, before the blocking-jobs summary:

- `revert-verdict` — include when revert candidates exist (score >= 85). One `revert-row` per candidate. Keep the `/ci:payload-revert {payload_tag}` copy block.
- `no-revert-verdict` — include when there are no revert candidates. Exactly one of these two blocks appears.
- `force-accept-verdict` — include only when Step 6.4 recommends force-accept.

## Blocking jobs summary

One `job-row` per blocking job, passed and failed:

- **RHCOS badge**: from the snapshot's `rhcos_version` — `badge-rhcos9` (also for `rhcos9-default`), `badge-rhcos10` (also for `rhcos10-default`), `badge-rhcos-mixed` for `rhcos9_10`. When the job's failure is variant-isolated (Step 4 pattern recognition), add the `variant-isolated` class to the badge.
- **Status**: `status-passed` ("Passed") / `status-failed` ("Failed").
- **Streak**: consecutive failing payloads; "N/A" for passed jobs.
- **History**: the `failure_pattern` from the snapshot rendered inside `class="pattern"` as one `<span>` per payload, newest first — `<span class="f">F</span>` / `<span class="s">S</span>`.
- **First Failed In**: originating payload tag linked to the release controller; "N/A" for passed jobs.

## Failed job details

One `failed-job` collapsible block per failed blocking job:

- Summary line: job name, `badge-new` ("New Failure") or `badge-persistent` ("Failing for N payloads"), and the RHCOS badge.
- Prow line: Prow and GCS Artifacts links; for aggregated jobs, append the underlying job name.
- `variant-callout` — include only when the failure is variant-isolated; fill in which variant is affected.
- `analysis_from_subagent` — the subagent's failure analysis (Step 4), adjudicated where Step 5b applied. Render its Step 4a validated causal chain in order (question, answer, exact hydrated excerpts, and proof notes), followed by the failure type and retry comparison. Do not substitute uncited prose for the hydrated excerpts.
- `known-symptoms` — include only when the subagent reported symptoms other than "none".
- Candidates: use `candidates-table` (one `candidate-row` per scored candidate with its tiered score class) when candidates exist; otherwise use `candidates-none`, whose prose must state **why** no candidate explains the failure (Step 6.1) — never leave it blank or generic.

## RHCOS changes

Include the `rhcos-changes` block when any payload in the chain has RHCOS RPM changes. `{one_sentence_rhcos_correlation_summary}` states whether the changes correlate with any failure.

- `rhcos-candidates` — include when scored RHCOS RPM candidates exist (`type: "rhcos_rpm"`); one row per candidate with its itemized rationale, plus the `changelog-evidence` collapsible when any candidate has changelog evidence.
- **Cover every relevant hop, not just one.** Failure modes can have different `first_failed_in` origins, so a single origin's diff can omit evidence for another candidate hop. Keep one "Full RHCOS RPM Changelog Diffs" collapsible: render the baseline diff for each variant with changes (`rhcos-baseline-diff`, with a one-line muted summary of the changelog theme), plus one `rhcos-hop-diff` subsection for each distinct (originating payload, variant) pair referenced by any scored candidate or failure mode that differs from the baseline. Do not create a separate collapsible per origin.

## Informing test failures

Include the `informing-tests` block when `test_failures.informing[]` or `test_failures.flakes[]` is non-empty. List individual test names — never informing *job* counts (see Step 3.4). The caveat inside `informing-note` is part of the template; keep it verbatim.

## Adversarial review

Fill `review_summary` from the Step 9 reviewer's response. Include the `review-issues` list only when the reviewer identified issues; each entry pairs the issue with the action taken.
