---
description: Stage reverts for high-confidence payload suspects identified by analyze-payload
argument-hint: "<payload-tag>"
---

## Name

ci:payload-revert

## Synopsis

```
/ci:payload-revert <payload-tag>
```

## Description

The `ci:payload-revert` command reads the suspects YAML produced by `/ci:analyze-payload` and stages reverts for all high-confidence suspects (confidence score >= 85) that have not already been reverted.

For each qualifying suspect, it creates a TRT JIRA bug, opens a revert PR, and triggers payload validation jobs using the `stage-payload-reverts` skill.

This command is one of three composable stages in the payload triage pipeline:
1. `/ci:analyze-payload` — produces the suspects YAML
2. `/ci:payload-revert` — stages reverts for HIGH confidence suspects (this command)
3. `/ci:payload-experiment` — opens draft revert PRs for MEDIUM confidence suspects

### Job Triggering Limits

- **Non-aggregated jobs**: Up to 5 total across all suspects
- **Aggregated jobs**: Up to 1 total

When the number of failing jobs across all suspects exceeds these limits, prioritize jobs from higher-confidence suspects first.

## Implementation

1. **Parse the payload tag** from the argument. Extract `version`, `stream`, and `architecture` from the tag (see `analyze-payload` Step 1 for parsing rules).

2. **Read the suspects YAML**: Look for `payload-analysis-{tag}-suspects.yaml` in the current working directory. If not found, print an error and exit:
   ```
   Error: Suspects YAML not found for {payload_tag}.
   Run `/ci:analyze-payload {payload_tag}` first to generate it.
   ```

3. **Filter suspects**: Select suspects with `confidence_score >= 85`. Exclude any with `existing_revert_status` of `"merged"` or `"open"`.

4. **Fail-fast validation**: For each suspect's `failing_jobs`, if any entry has `is_aggregated: true` but `underlying_job_name` is empty, skip that job and record an error: "Cannot trigger payload test: aggregated job missing underlying_job_name from analysis".

5. **Dispatch to `stage-payload-reverts` skill**: Pass all qualifying suspects with their context (payload tag, version, stream, architecture, release controller URL, and failing jobs).

6. **Report results**: Print a summary of actions taken (JIRA tickets created, revert PRs opened, payload jobs triggered).

## Return Value

- Summary of staged reverts with JIRA keys, revert PR URLs, and triggered payload job URLs
- Any errors encountered during staging

## Examples

1. **Stage reverts after analysis**:
   ```
   /ci:analyze-payload 4.22.0-0.nightly-2026-02-25-152806
   /ci:payload-revert 4.22.0-0.nightly-2026-02-25-152806
   ```

## Arguments

- $1: A full payload tag (e.g., `4.22.0-0.nightly-2026-02-25-152806`). Must match the tag used with `/ci:analyze-payload`. (required)

## Skills Used

- `stage-payload-reverts`: Creates TRT JIRA bugs, opens revert PRs, triggers payload jobs
- `trigger-payload-job`: Triggers payload jobs and collects URLs
- `revert-pr`: Git revert workflow for creating revert PRs
