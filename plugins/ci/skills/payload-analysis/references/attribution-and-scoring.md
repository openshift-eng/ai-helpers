# Attribution and Scoring

Map frozen causal signatures to changed behavior. A recent PR is a hypothesis,
not evidence.

## Enumerate candidate changes

For each signature, use its established onset payload:

- inspect `payloads[].prs[]` and each local `code.diff`;
- inspect matching RHCOS changes for the job's variant;
- inspect recent `openshift/release` step-registry changes when the failing
  operation is CI setup, provisioning, test execution, or teardown.

Do not use the longer job or test-name streak to select PRs. For Sippy-backed
payloads, use the archived PR list and diffs while treating unavailable
release-controller-only fields as unknown.

Search CI changes by the exact failing step and its upstream dependencies.
Generic commit messages are weak filters; filenames and patches are decisive.
A causal CI change is a scored candidate even when the job is classified as
infrastructure.

## Trace from trigger to diff

For each `(signature, candidate)` pair:

1. Start with the frozen earliest abnormal event.
2. Identify the smallest changed behavior capable of producing it.
3. Determine whether that behavior necessarily executed in the failing run.
4. Follow propagation to the gating symptom.
5. Challenge the chain with the recorded competing explanations.

A PR matching only a downstream recovery error, detector, cleanup failure, or
terminal symptom does not explain an earlier trigger.

If the diff is unavailable, do not claim that its path executed. Component and
timing correlation alone is capped at 60 and cannot authorize a revert.

When one code-level link is missing but the candidate is otherwise strong,
exhaust available source before declaring it unknown: search changed symbols,
callers, initialization side effects, output streams, and the error-producing
path. Deterministic code flow plus observed inputs and outputs can establish a
mechanism without standing up a new cluster.

## Score hypotheses

Apply the rubric once per atomic signature:

| Signal | Points | Requirement |
|---|---:|---|
| New failure mode | 30 | Verified signature boundary and changed code plausibly produces the signature |
| Component exclusivity | 10-30 | 10 for 4+ modifiers, 20 for 2-3, 30 for the sole modifier |
| Error/path match | 10-40 | 10 same subsystem, 20-30 same executed path, 40 exact changed identifier/string or demonstrated mechanism |
| Multi-job correlation | 10 | Independent clusters or executions show the same ordered signature |
| Presubmit coverage gap | 10 | The failing configuration was not exercised before merge |

Cap the raw sum at 100. Record one evidence line per awarded signal. Do not
award new-failure or exclusivity points to an unrelated PR merely because the
real cause was infrastructure.

Then cap the score by causal evidence:

| Evidence tier | Cap | Requirement |
|---|---:|---|
| Executed mechanism | 100 | Failing-run evidence plus the diff explain the earliest event and full chain; credible alternatives are contradicted |
| Incomplete mechanism | 80 | Changed behavior fits the earliest event, but a material link or credible alternative remains |
| Contextual correlation | 60 | Timing, component, subsystem proximity, coverage, or non-independent multi-job evidence only |
| Contradicted | 20 | A stronger earlier trigger exists, the path succeeded, or the same signature occurs without the change |

The final confidence is the lower of raw score and evidence cap. Record raw
sum, evidence tier, cap, final score, and any missing link.

## Interpret retries and experiments

Consistent retries establish reproducibility, not category. Product,
infrastructure, and test defects can all repeat.

The same signature persisting after a candidate is removed is strong evidence
against it. One passing retry after removal is weak evidence unless paired or
repeated runs isolate the change.

## Record non-PR causes

RHCOS package changes are suspects, not normal PR revert candidates. Record
package, variant, old/new versions, affected jobs, and causal rationale.

For each failed job with no causally linked candidate, state why and whether
the same signature appears elsewhere. An empty candidate list must represent a
conclusion, not an omitted investigation.

Write all scored candidates and RHCOS suspects to `analysis-state.yaml`.
