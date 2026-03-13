---
description: Open draft revert PRs for medium-confidence payload candidates and trigger payload jobs to experimentally determine which PR is causing failures
argument-hint: "<payload-tag>"
---

## Name

ci:payload-experiment

## Synopsis

```
/ci:payload-experiment <payload-tag>
```

## Description

The `ci:payload-experiment` command opens draft revert PRs for medium-confidence payload candidates (confidence score 60-84) and triggers payload jobs to experimentally determine which PR is causing failures. It operates in two phases separated by a CI wait period.

**Phase 1**: Reads the payload results YAML, filters medium-confidence candidates, opens draft revert PRs, triggers payload jobs, and appends action entries (`type: "experiment"`, `status: "pending"`) to each candidate's `actions` array.

**Phase 2**: Detects candidates with a `status: "pending"` action entry in the results YAML, checks job results, promotes confirmed causes to real revert PRs (with TRT JIRA bugs), and closes innocent draft PRs.

All state is tracked in the payload results YAML via the `payload-results-yaml` skill — no separate tracking file is created.

This command is one of three composable stages in the payload triage pipeline:
1. `/ci:analyze-payload` — produces the payload results YAML
2. `/ci:payload-revert` — stages reverts for HIGH confidence candidates
3. `/ci:payload-experiment` — experimentally tests MEDIUM confidence candidates (this command)

### Job Triggering Limits

- **Non-aggregated jobs**: Up to 5 total across all candidates
- **Aggregated jobs**: Up to 1 total

## Implementation

1. **Parse the payload tag** from the argument. Extract `version`, `stream`, and `architecture` from the tag (see `analyze-payload` Step 1 for parsing rules).

2. **Read the payload results YAML** using the `payload-results-yaml` skill: Look for `payload-results-{tag}.yaml` in the current working directory. If not found, print an error and exit:
   ```
   Error: Payload results YAML not found for {payload_tag}.
   Run `/ci:analyze-payload {payload_tag}` first to generate it.
   ```

3. **Detect Phase 2 resume**: If the results YAML contains any action entry with `type: "experiment"` and `status: "pending"`, jump to Phase 2 (step 5). Phase 2 processes only pending experiments — candidates with other statuses are left unchanged.

4. **Phase 1 — Set up experiments**: Filter candidates with `60 <= confidence_score < 85`. Exclude any that already have an action with `status` of `"open"` or `"merged"` (pre-existing revert). Dispatch to the `payload-experimental-reverts` skill Phase 1, which updates the results YAML in place.

5. **Phase 2 — Collect results**: Dispatch to the `payload-experimental-reverts` skill Phase 2 to check job results, promote confirmed causes, close innocent drafts, and update the results YAML.

6. **Report results**: Print a summary of actions taken.

## Return Value

- **Phase 1**: Confirmation that experiments are running, with resume instructions
- **Phase 2**: Summary of experiment verdicts (confirmed/innocent) and actions taken. If some experiments are still running, they remain `pending` and the command can be re-invoked to check again.

## Examples

1. **Start experiments after analysis**:
   ```
   /ci:analyze-payload 4.22.0-0.nightly-2026-02-25-152806
   /ci:payload-experiment 4.22.0-0.nightly-2026-02-25-152806
   ```

2. **Resume to collect results** (run from the same directory after jobs complete):
   ```
   /ci:payload-experiment 4.22.0-0.nightly-2026-02-25-152806
   ```

## Arguments

- $1: A full payload tag (e.g., `4.22.0-0.nightly-2026-02-25-152806`). Must match the tag used with `/ci:analyze-payload`. (required)

## Skills Used

- `payload-results-yaml`: Reads and updates the payload results YAML
- `payload-experimental-reverts`: Opens draft revert PRs and triggers payload jobs (Phase 1); collects results and acts (Phase 2)
- `trigger-payload-job`: Triggers payload jobs and collects URLs
- `revert-pr`: Git revert workflow for creating revert PRs
