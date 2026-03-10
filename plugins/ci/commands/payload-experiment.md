---
description: Open draft revert PRs for medium-confidence payload suspects and trigger payload jobs to experimentally determine which PR is causing failures
argument-hint: "<payload-tag>"
---

## Name

ci:payload-experiment

## Synopsis

```
/ci:payload-experiment <payload-tag>
```

## Description

The `ci:payload-experiment` command opens draft revert PRs for medium-confidence payload suspects (confidence score 60-84) and triggers payload jobs to experimentally determine which PR is causing failures. It operates in two phases separated by a CI wait period.

**Phase 1**: Reads the suspects YAML, filters medium-confidence suspects, opens draft revert PRs, and triggers payload jobs. Writes a tracking YAML (`<tag>-experiments.yaml`) and exits.

**Phase 2**: Detects an existing `<tag>-experiments.yaml` with pending experiments, checks job results, promotes confirmed causes to real revert PRs (with TRT JIRA bugs), and closes innocent draft PRs.

This command is one of three composable stages in the payload triage pipeline:
1. `/ci:analyze-payload` — produces the suspects YAML
2. `/ci:payload-revert` — stages reverts for HIGH confidence suspects
3. `/ci:payload-experiment` — experimentally tests MEDIUM confidence suspects (this command)

### Job Triggering Limits

- **Non-aggregated jobs**: Up to 5 total across all suspects
- **Aggregated jobs**: Up to 1 total

## Implementation

1. **Parse the payload tag** from the argument. Extract `version`, `stream`, and `architecture` from the tag (see `analyze-payload` Step 1 for parsing rules).

2. **Detect Phase 2 resume**: Check for `<payload-tag>-experiments.yaml` in the current working directory. If it exists and contains experiments with `status: pending`, jump to Phase 2 (step 5).

3. **Read the suspects YAML**: Look for `payload-analysis-{tag}-suspects.yaml` in the current working directory. If not found, print an error and exit:
   ```
   Error: Suspects YAML not found for {payload_tag}.
   Run `/ci:analyze-payload {payload_tag}` first to generate it.
   ```

4. **Phase 1 — Set up experiments**: Filter suspects with `60 <= confidence_score < 85`. Exclude any with `existing_revert_status` of `"merged"` or `"open"`. Dispatch to the `payload-experimental-reverts` skill Phase 1.

5. **Phase 2 — Collect results**: Read the `<payload-tag>-experiments.yaml` tracking file. Dispatch to the `payload-experimental-reverts` skill Phase 2 to check job results, promote confirmed causes, and close innocent drafts.

6. **Report results**: Print a summary of actions taken.

## Return Value

- **Phase 1**: Path to the experiments tracking YAML and resume instructions
- **Phase 2**: Summary of experiment verdicts (confirmed/innocent/inconclusive) and actions taken

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

- `payload-experimental-reverts`: Opens draft revert PRs and triggers payload jobs (Phase 1); collects results and acts (Phase 2)
- `trigger-payload-job`: Triggers payload jobs and collects URLs
- `revert-pr`: Git revert workflow for creating revert PRs
