---
name: regression-escape-analysis
description: Use when explaining how a known regression escaped through a culprit pull request by comparing the regression with merge-time CI coverage, execution history, retries, and overrides. Requires an already-identified regression and likely culprit PR.
---

# Regression Escape Analysis

Analyze why a known regression was allowed to merge. This skill does not find
the culprit: the caller must provide both the regression and a likely causal
PR. Its job is to distinguish missing coverage, a test that ran but missed the
problem, optional or skipped signal, retry masking, and an explicit override.

Prefer frozen evidence produced by the bundled collector. A payload snapshot
stores that evidence as the PR's `escape_analysis` artifact, so payload analysis
normally requires no live GitHub calls.

## Inputs

Require:

- A regression description containing the affected jobs or environments, the
  failing tests or operations, the failure mechanism, and key error patterns.
- The culprit PR URL.
- Preferably, an `escape-analysis.json` evidence path.

If the evidence path is absent, collect it before analysis:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/regression-escape-analysis/scripts/collect_pr_evidence.py" \
  <pr-url> --output-dir .work/regression-escape/<owner>-<repo>-<number>
```

Do not use present-day PR state as a substitute for merge-time evidence. The
collector cuts comments, reviews, statuses, and checks off at `pr.merged_at`
and snapshots CI configuration at the revision effective when the PR merged.

Read [references/evidence-schema.md](references/evidence-schema.md) when
interpreting the evidence or producing the structured result.

## Analysis

1. Establish the regression mechanism before looking at CI job names. Reduce it
   to the scenario, phase, component/code path, and failure signature that a
   useful presubmit would need to exercise.
2. Read every file listed under `ci_configuration`. Compare the mechanism with
   the configured presubmits and repository workflows. A differently named job
   may still cover the same scenario; a similarly named job may not.
3. Identify relevant presubmits and classify each as required, optional,
   conditional/manual, or unknown from its configuration. `optional: true`
   means Tide can ignore its result. `always_run: false` plus a trigger or
   `run_if_changed` means the job is conditional; determine whether this PR
   should have selected it.
4. Use only status/check history for `pr.head_sha`, the revision that merged.
   Failures on superseded commits are not evidence that failing signal was
   ignored. Count terminal attempts, not pending status updates. Use
   `ci_reported_failures[]` to cross-check the tested commit, required flag,
   rerun command, and Prow run URL from the bot's own test report.
5. Compare the relevant terminal attempts with chat-ops actions:
   - A failure followed by a pass on the same SHA is a retry pattern. Call it
     masking only when the failed attempt shows the regression's failure mode
     and the later pass did not establish that the first failure was unrelated
     infrastructure.
   - `/override` and `/skip` are explicit signal-handling actions. Attribute
     them to the normalized `actor_kind` in the evidence.
   - `/verified` is verification evidence, not automatically a CI override.
     Treat it as a bypass only when the evidence shows that it satisfied a
     merge requirement despite missing or failing relevant CI.
   - Do not infer that another bot is Chai. Only evidence normalized as
     `actor_kind: chai` has that attribution.
6. Determine the escape factors. More than one can apply:
   - `coverage_gap`: no configured presubmit exercises the regression scenario.
   - `conditional_not_selected`: relevant coverage existed but was not selected.
   - `optional_signal`: relevant CI failed but was non-required.
   - `did_not_run`: a relevant required job was configured but has no run on the
     merge SHA.
   - `retry_masking`: the matching failure was replaced by a passing retry on
     the same SHA without a code change.
   - `override`: matching failed CI was explicitly overridden or skipped.
   - `verification_bypass`: a verification action substituted for missing or
     failing matching CI.
   - `test_false_negative`: relevant required CI ran and passed, but its
     assertions or environment did not expose the regression.
   - `unknown`: evidence is too incomplete to decide.
7. State what should change: add or broaden coverage, make an existing job
   required, repair selection rules, limit retries, or tighten override policy.
   Tie every recommendation to a demonstrated factor.

## Guardrails

- Do not claim a coverage gap from job-name mismatch alone.
- Do not claim retry masking without a matching failed attempt on the merge SHA.
- Do not call a failed optional job an override; optionality itself explains why
  it did not gate.
- Do not treat a green job as proof of adequate coverage. If it exercised only
  an adjacent scenario, the factor is still a coverage gap; if it exercised the
  scenario but lacked the right assertion, it is a false negative.
- Preserve uncertainty. If `data_complete` is false or a required config/status
  source is missing, identify exactly which conclusion cannot be made.

Return the structured result defined in the evidence reference. Keep the
summary concise, but retain concrete job names, attempt results, actors, and
timestamps in the evidence lines.
