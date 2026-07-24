---
description: Explain which Sippy Symptoms and failure Labels apply to a Prow CI job run
argument-hint: <prow-job-url>
---

## Name

ci:diagnose-job-symptoms

## Synopsis

```text
/ci:diagnose-job-symptoms <prow-job-url>
```

## Description

The `ci:diagnose-job-symptoms` command takes a Prow job run URL and explains, in plain language, which Sippy Symptoms — known-failure signatures that match patterns in a run's artifact files — applied which Labels (like `InfraFailure`) to that run, including the matched file and text. Use it before debugging a CI failure from scratch to check whether it is already a known failure mode. The default mode needs no authentication.

## Implementation

1. **Load the skill**: Use the `diagnose-job-run-symptoms` skill, which documents both modes and the artifact schema.

2. **Default mode** — read already-applied labels from the run's public GCS artifacts (no auth):
   ```bash
   python3 plugins/ci/skills/diagnose-job-run-symptoms/diagnose_job_run.py "<prow-job-url>"
   ```

3. **If no labels are found, offer `--deep`**: The run may simply never have been scanned. Deep mode asks Sippy to re-scan the run server-side with `dry_run: true` (writes nothing) and requires a Bearer token — follow the `oc-auth` token-acquisition steps referenced in the skill (DPCR cluster, `https://api.cr.j7t7.p1.openshiftapps.com:6443`):
   ```bash
   python3 plugins/ci/skills/diagnose-job-run-symptoms/diagnose_job_run.py "<prow-job-url>" --deep
   ```

4. **Present the diagnosis**: For each applied label, explain the label title and meaning, the symptom rule that matched (matcher type, file pattern, match string), and the matched file/text (default mode only). If a deep rescan also finds nothing and the user has identified the cause, suggest creating a new symptom via `/ci:create-symptom` and applying it retroactively with `/ci:reevaluate-job-runs`.

## Return Value

- **Format**: Human-readable diagnosis, one block per applied label
- **Key fields**: label id/title/explanation, matched symptom (id, summary, matcher_type, file_pattern, match_string), matched file and text (default mode)
- **No matches**: Not an error — the output includes guidance on next steps

## Examples

1. **Diagnose a failed job run**:
   ```text
   /ci:diagnose-job-symptoms https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.20-e2e-aws-ovn/1856789012345678848
   ```

## Arguments

- $1: Prow job run URL (required) — must contain `/view/gs/` and end in a numeric build ID

## Skills Used

- `diagnose-job-run-symptoms`: Reads applied labels from GCS (default) or performs a server-side dry-run rescan (`--deep`)
- `oc-auth`: Provides the Bearer token for deep mode
