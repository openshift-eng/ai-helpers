# Evidence-Only Job Investigation

Investigate every failed blocking job in parallel. This phase determines what
happened; it does not identify which recent PR to blame.

## Investigator prompt

Use this prompt for each job, substituting its values:

> Analyze `<prow_url>` using `ci:prow-job-analysis`.
>
> The job has `<retry_count>` retries. Previous attempts:
> `<previous_attempt_urls>`.
>
> For an aggregated job, retries rerun only aggregation over the same children;
> inspect the final aggregation and then investigate the failed child runs. For
> a non-aggregated job, inspect the final attempt first and compare earlier
> attempts. Repetition establishes persistence, not whether the cause is
> product, infrastructure, or test.
>
> This is an evidence-only investigation. Do not inspect, enumerate, or rank
> payload PRs. Determine the failure mechanism from job artifacts before any
> change attribution occurs.
>
> Start with the build log, JUnit, events, intervals, and targeted pod or
> controller logs. Download must-gather or other large bundles only when these
> smaller artifacts do not establish the earliest abnormal event or a material
> causal link.
>
> Split independent failure modes. For each, order the earliest abnormal event,
> propagation or recovery behavior, detector, and terminal symptom. A test that
> reports a real product or infrastructure failure is a detector, not its
> cause. Use unresolved when artifacts do not distinguish credible causes.
>
> Record short exact excerpts and artifact paths. For aggregated jobs, extract
> the underlying job name from child-run artifacts rather than deriving it from
> the aggregator name.
>
> Return the structured block below and do not ask questions.

```yaml
ANALYSIS_RESULT:
  job_name: ""
  failed_phase: setup|install|test|upgrade|teardown|unknown
  cause_category: product|infrastructure|test|indeterminate
  failure_type: test|install|upgrade|infra
  root_cause_summary: ""
  underlying_job_name: ""
  retries_consistent: yes|no|no_retries|only_final_examined
  retry_summary: ""
  rhcos_version: rhcos9|rhcos10|rhcos9_10|rhcos9-default|rhcos10-default
  rhcos_rpm_correlation: none|possible|likely
  rhcos_rpm_suspect_packages: []
  failure_modes:
    - signature: ""
      earliest_abnormal_event:
        role: trigger|propagation|amplifier|recovery|detector|terminal|unknown
        observation: ""
        artifact: ""
      causal_chain:
        - role: trigger|propagation|amplifier|recovery|detector|terminal|unknown
          observation: ""
          artifact: ""
      competing_explanations:
        - explanation: ""
          evidence_for: ""
          evidence_against: ""
      missing_evidence: []
```

`failed_phase` says where the job surfaced the failure. `cause_category` says
what produced it. A test assertion that detects a cloud, network, storage, or
provisioning failure does not make the cause a test.

Set the output-schema `failure_type` to `infra` for an infrastructure cause,
even when it surfaced during tests. Use `test` when a product regression or a
test/framework defect failed during the test phase, and `install` or `upgrade`
for product failures in those phases. For an indeterminate cause, use the
observed phase and `root_cause_summary: unresolved`.

## Collect results

Wait for every investigator. A running or incomplete investigator is not a
result. Re-run only jobs whose structured block is missing or materially
incomplete.

Copy returned failure modes into `analysis-state.yaml`. Preserve artifact
references and disagreements; do not reconcile them against candidate changes
in this phase.
