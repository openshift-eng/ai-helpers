# Escape Evidence and Result Schema

## Collector output

`escape-analysis.json` is a frozen merge-time evidence bundle:

- `schema_version`: evidence schema version.
- `collected_at`: collector timestamp.
- `cutoff`: normally the PR merge timestamp. Events after this are excluded.
- `data_complete`: false when a required GitHub or CI-configuration read failed.
- `collection_errors[]`: source and error for unavailable reads.
- `pr`: URL, repository, number, author, base branch/base SHA, merge head SHA,
  merge commit, merge timestamp, merge actor, labels, and merge mechanism.
- `chatops_actions[]`: normalized command, action, arguments, timestamp, actor,
  and `actor_kind` (`human`, `chai`, `automation`, or `unknown`).
- `ci_reported_failures[]`: normalized rows from Prow's PR test-report comments,
  including context, tested commit, Prow URL, required flag, rerun command,
  report timestamp, and report actor.
- `reviews[]`: review state, commit, timestamp, and normalized actor.
- `status_contexts[]`: one entry per commit-status context on the merge head.
  `events` contains all status updates chronologically; `terminal_attempts`
  contains only success/failure/error terminals and is the retry history.
- `check_runs[]`: checks-api runs on the merge head, for CI systems that use
  Checks rather than commit statuses.
- `ci_configuration`: frozen source revisions and snapshot-relative paths for:
  - `openshift_release.ci_operator_configs[]`
  - `openshift_release.prow_presubmits[]`
  - `repository.ci_operator[]`
  - `repository.workflows[]`

The openshift/release files are selected by PR repository and base branch at
the last openshift/release commit at or before merge. For a PR against
openshift/release itself, the PR's base SHA is used.

Prow terminal attempts are distinct terminal status events, normally with
distinct `target_url` build IDs. Pending events do not count as attempts.

`redhat-chai-bot` is normalized to `actor_kind: chai` even though the GitHub
account is represented as a user. Other bots remain `automation`; do not infer
additional Chai identities.

## Analysis result

Attach this object to the culprit candidate as `escape_analysis`:

```yaml
escape_analysis:
  outcome: mixed
  summary: "The relevant job was optional and its matching failure was replaced by a green retry."
  relevant_presubmits:
    - name: "ci/prow/e2e-aws"
      coverage: full
      required: false
      selection: always
      ran_on_merge_sha: true
      terminal_results: [failure, success]
      assessment: "Exercises the failing AWS upgrade path and reported the same error."
  factors:
    - type: optional_signal
      evidence: "e2e-aws has optional: true and failed on the merge SHA."
      actor_login: ""
      actor_kind: unknown
    - type: retry_masking
      evidence: "Build 123 failed with the regression signature; build 124 passed on the same SHA after /retest."
      actor_login: "contributor"
      actor_kind: human
  merge:
    merged_at: "2026-01-02T03:04:05Z"
    merged_by: "openshift-merge-bot[bot]"
    merged_by_kind: automation
  recommendations:
    - "Make e2e-aws required for changes to the affected path."
  limitations: []
```

Rules:

- `outcome`: `coverage_gap`, `signal_handling`, `false_negative`, `mixed`, or
  `unknown`.
- `coverage`: `full`, `partial`, `none`, or `unknown`.
- `required`: boolean or null when unavailable.
- `selection`: `always`, `conditional`, `manual`, or `unknown`.
- `terminal_results`: chronological terminal conclusions on the merge SHA.
- `factors[].type`: one of the factor names in the main skill.
- `actor_kind`: `human`, `chai`, `automation`, or `unknown`. Leave actor fields
  empty/unknown when the factor has no actor.
- `limitations` is required, even when empty.
