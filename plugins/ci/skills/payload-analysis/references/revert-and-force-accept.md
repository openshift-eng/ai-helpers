# Revert and Force-Accept Decisions

## Purpose

Convert the causal analysis into safe revert and force-accept decisions.
Confidence ranks hypotheses; the action gates authorize reverts.

## Inputs

- scored candidates and their causal evidence;
- competing explanations and missing links;
- payload phase, failed blocking-job count, and `hours_since_baseline`;
- existing revert records.

## Result

Write every candidate's gate results and revert eligibility, verified existing
actions, and the payload's force-accept decision to `analysis-state.yaml`.

## Actions

### Apply the revert gates

Record all five gates for every candidate:

| Gate | Pass requirement |
|---|---|
| `changed_path_executed` | Failing-run evidence connects observed behavior to the changed path |
| `full_causal_chain` | The change explains the earliest trigger through the gating symptom, not only recovery, detection, cleanup, or a terminal error |
| `exact_signature_timing` | A comparable prior execution verifies the minimal signature was absent |
| `alternatives_excluded` | Credible product, infrastructure, test-framework, and external-dependency alternatives have affirmative evidence against them |
| `experiment_isolates_change` | A relied-upon experiment reliably isolates the change |

Use `pass`, `fail`, or `unknown`. For `experiment_isolates_change`, use
`not_applicable` when no experiment informed the conclusion.

Assign each status from its evidence:

- unavailable diff or unobserved changed behavior makes
  `changed_path_executed` unknown;
- a candidate matching only a downstream symptom makes `full_causal_chain`
  fail;
- job/test-name timing or an unobservable predecessor makes
  `exact_signature_timing` unknown;
- an earlier infrastructure or test trigger makes `alternatives_excluded`
  fail; unexamined credible alternatives make it unknown;
- an unpaired passing retry is not an isolating experiment.

Set `revert_eligible: true` exactly when:

1. final confidence is at least 85;
2. the first four gates pass;
3. `experiment_isolates_change` is `pass` or `not_applicable`.

Only eligible candidates appear under Recommended Reverts. PRs that are merely
recent, component-exclusive, or adjacent to an error are not eligible.

### Verify existing reverts

For every eligible PR:

1. Search for open, closed, and merged revert PRs.
2. Verify that the revert diff removes the candidate change.
3. Record a verified open or merged revert as an existing action.
4. Do not recommend creating a duplicate revert.

### Exclude non-revert cases

Do not recommend a revert for:

- infrastructure failures not introduced by a repository change;
- flaky tests that also fail on accepted payloads;
- unresolved causes;
- RHCOS package changes through the normal PR workflow;
- a Kubernetes rebase solely because the kubelet rebuild has not yet reached
  RHCOS.

For Kubernetes rebase version skew, record a test failure caused by transient
build lag and recommend waiting for the rebuilt kubelet/RHCOS. Do not
force-accept or revert the rebase solely for that lag.

### Decide force-accept eligibility

If the payload phase is already Accepted, set
`force_accept_recommended: false`.

Otherwise recommend force-accept only when:

1. every blocking failure has `cause_category: infrastructure` and is
   temporary;
2. no more than two blocking jobs failed;
3. `hours_since_baseline` is at least 18 or unavailable.

Temporary means likely to self-resolve without human action: lease acquisition,
quota recovery, transient cloud throttling, a one-off endpoint timeout, or a CI
control-plane blip. Broken CI configuration, credentials, registry URLs,
persistent misconfiguration, tests, and product defects require human action
and are not force-accept eligible.

### Record the result

Write every gate and its evidence, revert eligibility, verified existing
actions, and the force-accept decision to `analysis-state.yaml`. Complete this
step only when every candidate and the payload have explicit action decisions.
