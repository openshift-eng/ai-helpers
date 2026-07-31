# Evidence-Only Job Investigation

Determine what happened in every failed blocking job before considering
candidate changes.

## Run the investigations

For each failed blocking job:

1. Start an investigator with the job's Prow URL, retry URLs, aggregation
   status, RHCOS variant, and known artifact paths.
2. Require the investigator to use `ci:prow-job-analysis`.
3. Keep payload PR descriptions, diffs, and candidate rankings out of the
   investigator's context.
4. Run independent job investigations in parallel when capacity allows.
5. Wait for every result before establishing signatures.

Use this prompt, substituting the job values:

> Investigate `<prow_url>` using `ci:prow-job-analysis`.
>
> The job has `<retry_count>` retries. Previous attempts:
> `<previous_attempt_urls>`.
>
> If this is an aggregated job, inspect the aggregation result and its failed
> or incomplete child runs. If it is not aggregated, inspect the final attempt
> first and compare earlier attempts. Repetition proves persistence, not the
> cause category.
>
> Do not inspect, enumerate, or rank payload PRs. Determine the mechanism from
> job artifacts alone.
>
> Inspect the build log, JUnit, events, intervals, and targeted pod or
> controller logs first. Download larger artifacts only when a material causal
> link remains unresolved.
>
> Split independent failure modes. For each one, identify the earliest abnormal
> event and order the causal chain through propagation, recovery, detection,
> and the terminal symptom. A test that reports a real product or
> infrastructure failure is a detector, not the cause.
>
> Record short excerpts and artifact paths. Use `unresolved` when the artifacts
> do not distinguish credible causes. For aggregated jobs, read the underlying
> job name from child-run artifacts rather than deriving it from the aggregator
> name.
>
> Return the following block:

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

## Classify the result

Use `failed_phase` for where the failure surfaced. Use `cause_category` for what
produced it. A test assertion that detects a cloud, network, storage, or
provisioning failure does not make the cause a test.

Set the output-schema `failure_type` to `infra` for an infrastructure cause,
even when it surfaced during tests. Use `test` when a product regression or a
test/framework defect failed during the test phase, and `install` or `upgrade`
for product failures in those phases. For an indeterminate cause, use the
observed phase and `root_cause_summary: unresolved`.

## Accept the result

Accept an `ANALYSIS_RESULT` only when it:

- covers the correct job and relevant retries or child runs;
- identifies independent failure modes and the earliest abnormal event;
- provides artifact references for material causal links;
- lists credible competing explanations and missing evidence;
- distinguishes the failed phase from the cause category.

Repeat materially incomplete investigations. Copy accepted results into
`analysis-state.yaml` without reconciling them against candidate changes.
