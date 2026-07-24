# Reevaluate Job Runs

Retroactively re-run Sippy Symptom detection on completed Prow CI job runs.

## Overview

Sippy Symptoms are known-failure signatures for OpenShift CI. A symptom is a rule made of a file pattern (a glob over a CI job run's artifact files, e.g. `**/build-log.txt`) and a matcher (`string` = substring, `regex` = regular expression, `none` = file merely exists, `cel` = a compound CEL expression over other label names). When a symptom matches a job run's artifacts, Sippy applies one or more **Labels** — human-readable tags like `InfraFailure` — to that run. Labels appear in the Sippy UI and Spyglass and help everyone quickly recognize known failure modes without re-debugging them. You do not need any prior Sippy knowledge to use this skill.

Symptom detection runs automatically on new job runs; use this skill to apply a new or changed symptom to runs that completed before the change.

## Authentication

Writes go to `https://sippy-auth.dptools.openshift.org` and require a Bearer token. Log into the DPCR cluster (`https://api.cr.j7t7.p1.openshiftapps.com:6443`) with `oc login` and use the `oc-auth` skill to obtain the token.

## Usage

Always start with `--dry-run` to preview what would match without writing anything:

```bash
python3 plugins/ci/skills/reevaluate-job-runs/reevaluate_job_runs.py \
  https://prow.ci.openshift.org/view/gs/test-platform-results/logs/<job>/<build_id> \
  --token "$TOKEN" --dry-run --format summary
```

Accepts any number of build IDs or Prow URLs; runs are deduplicated and sent in batches of 10 (with automatic retries on gateway timeouts). Reevaluation is idempotent, so retrying failed batches is safe.

## See Also

- [SKILL.md](SKILL.md) - Complete implementation guide, including batching/timeout guidance and the triage-wide bulk workflow
- Related: `oc-auth` skill (authentication tokens)
- Related: `manage-symptoms` skill (create/update symptoms)
- Related: `diagnose-job-run-symptoms` skill (explain a run's labels)
