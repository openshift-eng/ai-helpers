# Investigation budgets and continuation

Separate output and exploration limits, consistent with `investigate-ci-reliability`:

- `--max-recommendations 10`: distinct independently validated repair mechanisms
  plus validated retirement candidates produced in this invocation. Proposed or
  unreviewed actions do not count. A shared mechanism counts once across jobs.
- `--max-candidates 100`: distinct cohort investigations started in this invocation,
  including investigations that yield shared failures, insufficient evidence,
  already-fixed results, or no supported repair.
- `--time-budget-minutes 120`: collection, investigation, review, and export combined.

These are ceilings, not required finding counts. Continue to other candidates when
early investigations produce no actionable recommendation. Stop discovery when a
ceiling is reached or no feasible queued work remains. Reserve enough time to
finish reviews and export; do not relax evidence requirements to fill the output.

## Queue and history

After ranking, run:

```bash
python3 scripts/investigation_queue.py plan --workspace WORK
```

The helper writes `WORK/investigation-queue.json` and defaults shared history to
`WORK/../investigation-history.json`. Default timestamped workspaces therefore
share `~/tmp/analyze-payload-informing-jobs/investigation-history.json`. Use
`--history-file FILE` for a user-selected location. Keep a shared history file under
one writer at a time. It is scheduling state, not a review attestation.

On first initialization, discover up to 50 sibling workspaces' manifests/rankings
and import completed findings of the exact release/architecture/stream. Discovery
is bounded and gaps are recorded; it does not scan artifact trees. Use repeatable
`--prior-workspace PATH` for older or differently located workspaces. Imported
findings need a recognized disposition, completed investigation status, summary,
and next action. Partial or interrupted findings are not treated as completed.

History keys combine exact scope with the stable cohort ID, preserving underlying
job, upgrade-route, and population distinctions. Store the observation fingerprint,
finding digest/path, source analysis, completion time, disposition, summary,
next action, and optional `revisit_condition`. Re-importing an old finding after
re-ranking does not replace the originally investigated observations.

Queue ordering is separate from raw rankings:

1. Pending cohorts without a completed investigation, in current then predecessor
   ranking order. Resume their retained partial work instead of restarting it.
2. Prior cohorts needing a recheck because run observations or supplied
   `investigation_inputs` changed, retained findings disappeared/changed, or a
   supported revisit decision exists.
3. Unchanged completed investigations are deferred until their revisit condition
   becomes feasible. Unknown cause alone does not justify repeating the same work.

New run IDs warrant an applicability recheck, not automatic repetition ahead of
pending cohorts. AI review should inspect current source/configuration, signatures,
artifact availability, repair adoption, and recorded follow-ups. If that review
finds a substantive change or a feasible next step, supply `--revisit-decisions FILE`:

```json
{"revisits": [{"cohort_id": "COHORT", "reason": "Previously missing artifact is available",
               "evidence": ["Artifact URL and retrieval result"]}]}
```

The helper retains these decisions until completion. Optional cohort
`investigation_inputs` can record reviewed source/configuration/signature inputs
for fingerprint comparison. Neither new runs nor a scheduling decision proves the
old diagnosis still applies. Verify retained evidence hashes and applicability
before reusing evidence; changes require renewed findings and reviews.

## Begin, complete, and resume

Before starting the next cohort, pass the actual count from independent review:

```bash
python3 scripts/investigation_queue.py begin --workspace WORK \
  --cohort-id COHORT --validated-recommendations 0
```

The helper refuses new discovery after the recommendation, candidate, or time
limit. The supplied validated count must be nonnegative and cannot decrease within
a session. It accounts for review outcomes; it cannot establish validation itself.
For a justified priority change, add `--reason TEXT`, including why a recheck must
precede pending work. Candidate limits count started cohorts, so unsuccessful or
interrupted attempts still consume exploration budget.

After completing a bounded investigation, save its finding under `WORK/findings/`
with `investigation_status: COMPLETE_BOUNDED` or `COMPLETED_WITH_LIMITATIONS` and run:

```bash
python3 scripts/investigation_queue.py record --workspace WORK \
  --finding WORK/findings/COHORT.json
```

Completion means the bounded investigation was carried out, not that it found a
fix. Record limitations, remaining questions, next action, and a concrete
`revisit_condition`, such as a new failure signature, configuration change, repair
adoption, available missing artifact, or owner-provided catalogue evidence. A
blocked/partial attempt remains pending for continuation. Recording requires a
begun investigation with matching observations; changing inputs requires beginning
again. Do not mark untouched or budget-interrupted jobs completed to advance the queue.

Replanning an active invocation preserves its deadline, limits, attempted cohorts,
and progress. It never silently resets an exhausted budget. On a later user-requested
invocation that continues the same frozen population, collect with `--resume`, then:

```bash
python3 scripts/investigation_queue.py plan --workspace WORK --new-session \
  --max-recommendations 10 --max-candidates 100 --time-budget-minutes 120
```

This starts a fresh invocation budget and preserves completed history. A new time
window uses a new analysis/workspace with the same history file. Keep previous
metrics separate, reassess applicability, and never carry old reviews into new findings.

Before export, replan with `--validated-recommendations N` from actual review
results to update the queue and final stop reason. If discovery stops early to
reserve review/export time or because remaining work cannot proceed, also supply
`--stop-reason REVIEW_EXPORT_RESERVE` or `--stop-reason NO_FEASIBLE_WORK` and explain
the constraint in the handoff. This closes discovery for the session; replanning
cannot silently reopen it. The report retains the queue and states
limits, attempts, completions, stop reason, next cohort, history gaps, and counts of
pending/recheck/deferred cohorts. Historical summaries are labeled as previous
investigations; they do not manufacture current findings, validated fixes, or cleared
jobs. Zero validated recommendations remains an honest outcome after exploration.
