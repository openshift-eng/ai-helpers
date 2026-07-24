---
description: Retroactively re-run Sippy Symptom detection on completed Prow CI job runs
argument-hint: <prow-urls-or-build-ids...>
---

## Name

ci:reevaluate-job-runs

## Synopsis

```
/ci:reevaluate-job-runs <prow-urls-or-build-ids...>
```

## Description

The `ci:reevaluate-job-runs` command asks Sippy to re-scan completed Prow CI job runs against the current set of Symptoms — known-failure signatures that automatically apply human-readable Labels (like `InfraFailure`) when a run's artifacts match a pattern. Detection normally runs as artifacts arrive, so reevaluation is for runs that finished **before** a symptom was created or changed. Reevaluation is idempotent and preserves manually-applied labels.

## Implementation

1. **Load the skill**: Use the `reevaluate-job-runs` skill, which documents batching, retry behavior, and the auth workflow.

2. **Obtain the auth token**: Follow the `oc-auth` token-acquisition steps in the `reevaluate-job-runs` skill (requires `oc login` to the DPCR cluster, `https://api.cr.j7t7.p1.openshiftapps.com:6443`).

3. **Dry-run first**: Always suggest a `--dry-run` before applying — it reports what would match without writing anything. Pass numeric build IDs or full Prow job URLs in any count; the script deduplicates and batches automatically (default 10 per request to avoid gateway timeouts):
   ```bash
   python3 plugins/ci/skills/reevaluate-job-runs/reevaluate_job_runs.py \
     <run>... --token "$TOKEN" --dry-run --format summary
   ```

4. **Apply**: After the user reviews the dry-run results, rerun without `--dry-run` to actually write labels.

5. **Present the results**: For each run show status, symptoms evaluated/matched, and labels applied. If any batches failed (504 gateway timeouts after retries), tell the user which run IDs to rerun — retries are safe because reevaluation is idempotent. If the script reports an SSO login page, the token expired: refresh via `oc-auth` and rerun. For triage-wide reevaluation, collect `.job_runs[].prowjob_run_id` values from the `fetch-regression-details` skill for each regression and pass them all in.

## Return Value

- **Format**: Per-run summary plus a list of any failed batches
- **Key fields**: status (success | missing_error | eval_error | rewrite_error), symptoms_evaluated, symptoms_matched, labels_applied
- **failed_batches**: Run IDs that need rerunning after persistent gateway timeouts

## Examples

1. **Preview matches for a single run**:
   ```
   /ci:reevaluate-job-runs https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn/1856789012345678848
   ```

2. **Apply to several runs by build ID**:
   ```
   /ci:reevaluate-job-runs 1856789012345678848 1856789012345678849 1856789012345678850
   ```

## Arguments

- $1..$N: One or more Prow job URLs or numeric Prow build IDs (required) — any count; deduplicated and batched automatically

## Skills Used

- `reevaluate-job-runs`: Calls the sippy-auth reevaluate API with batching and retries
- `oc-auth`: Provides the Bearer token for the sippy-auth API
- `fetch-regression-details`: Source of `prowjob_run_id` values for triage-wide reevaluation
