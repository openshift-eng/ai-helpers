# Adversarial Review and Self-Check

Challenge action-relevant conclusions, correct material defects, and validate
the outputs.

## Decide whether to run a reviewer

Launch one adversarial reviewer when:

- any candidate scores at least 60; or
- an unresolved conflict could change a revert or force-accept decision.

If neither condition applies, record why no reviewer was required.

## Prepare the review

Provide the reviewer only:

- each minimal signature and ordered chain with artifact references;
- each candidate diff reference, score breakdown, evidence cap, and gates;
- unresolved links and competing product, infrastructure, and test causes.

Do not send the complete snapshot or full logs.

Use this prompt:

> Falsify each candidate from the supplied decision records. Check whether it
> explains the earliest abnormal event rather than a downstream recovery error,
> detector, cleanup failure, or terminal symptom. Reject timing/component
> attribution without a usable diff. Check for earlier infrastructure or test
> triggers, incorrect signature boundaries, overstated evidence caps, and
> unsupported revert gates. A deterministic code path may close an unlogged
> internal link when observed inputs and outputs make that path necessary.
> Report only material defects, affected jobs, and the evidence needed to
> resolve them.

## Apply the review

For every material finding:

1. Identify which workflow step produced the defective conclusion.
2. Revisit the referenced artifact or diff.
3. Correct `analysis-state.yaml`.
4. Recompute dependent scores, gates, and decisions.
5. Regenerate all affected outputs.

Do not patch report prose around a stale conclusion.

## Run the final checks

Confirm:

1. Every failed-job investigator completed.
2. The required reviewer, if any, completed.
3. All three exact output files exist directly under `OUTPUT_DIR`.
4. HTML, YAML, and JSON agree on phase, failures, root causes, scores, and
   actions.
5. Every failed blocking job appears, even without a candidate.
6. Every candidate has five gates with non-empty evidence.
7. `revert_eligible` is true exactly when confidence is at least 85, the four
   core gates pass, and the experiment gate is `pass` or `not_applicable`.
8. The HTML recommends only eligible candidates.
9. Informing and flake tests are not presented as independent rejection causes.
10. No unresolved causal chain is presented as a proven root cause.

Fix every failed check and rerun the schema validators. Complete the analysis
only when every check passes, then present the three output paths and a concise
decision summary.
