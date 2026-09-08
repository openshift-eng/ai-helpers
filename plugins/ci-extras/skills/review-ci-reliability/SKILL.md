---
name: review-ci-reliability
description: Independently challenge proposed CI reliability fixes against run artifacts and current source. Use when reviewing candidate reliability issues before publishing validated handoffs.
---

# Independent CI reliability proof review

Review candidates produced by the bundled [investigate-ci-reliability skill](../investigate-ci-reliability/SKILL.md).
Read its [evidence contract](../investigate-ci-reliability/references/evidence-contract.md) and the
raw cited files. This review is a separate reasoning context from the investigator;
changing the investigator's name does not make a self-review independent.

## Check the causal claim

For each candidate, establish all of the following before `PROVEN_FIX`:

1. **Actual failure:** metadata and JUnit/step evidence show a blocking failure in an
   affected run. Informing cases, skipped tests, success-on-retry results, and alarming
   log text in green jobs do not establish the job's cause.
2. **Mechanism:** trace the originating error through executed code/configuration.
   Identify the incorrect behavior, not just the visible timeout or missing resource.
   A deterministic reproduction can establish a source defect, but scope any claim
   about the exact production interleaving to the available evidence.
3. **Current applicability:** pin current source or preserve its retrieval provenance
   and hash; verify the proposed repair is not already merged/adopted. Distinguish
   historical failures in old payloads from an unfixed defect.
4. **Correct repair:** explain why the proposed change addresses the demonstrated defect,
   preserves genuine failures, and has meaningful acceptance criteria. Extending a timeout,
   suppressing cleanup errors, or increasing quotas needs a demonstrated rationale.
5. **Controls and alternatives:** inspect same-job green controls or a justified alternative
   control/reproducer. Challenge shared infrastructure, version/input differences, ordinary
   PR mistakes, cofailures, and previously fixed causes. Missing OS/provider evidence limits
   the conclusion; it is not exculpatory evidence.

## Decide the verdict

Choose `UNRESOLVED` when the failure is real but a safe, current corrective change is not
established; `ALREADY_FIXED` when only adoption verification remains; `REJECTED` for a
refuted or out-of-scope reliability claim. Diagnostics improvements must be labeled as such
and cannot masquerade as fixes that restore the job. Record why each alternative was accepted
or rejected. Counts remain exposures unless every causal blocker in a run is addressed.

## Record the review

Write `WORK/reviews/<candidate-id>.json` with your reviewer identity, candidate digest,
verdict, checked evidence IDs, reasoning, strongest counterargument, and narrow repair scope.
Compute the digest using the bundled script:

```bash
python3 ../investigate-ci-reliability/scripts/reliability.py candidate-digest WORK/candidates/CANDIDATE.json
```

Resolve the script relative to this skill. Review the exact candidate bytes semantically;
the digest is canonical JSON, so harmless whitespace does not invalidate a review.
A substantive candidate change requires re-review. Do not modify candidates to approve your
own rewrite; return requested changes to the investigator. Run the bundled validator after
writing reviews. It checks evidence integrity and review freshness, not causal truth.
