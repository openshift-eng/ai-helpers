---
description: Autonomous agent that analyzes a rejected payload, determines root causes, and takes action based on confidence scoring
argument-hint: "<payload-tag>"
---

## Name

ci:payload-agent

## Synopsis

```
/ci:payload-agent <payload-tag>
```

## Description

The `ci:payload-agent` command is an autonomous orchestrator that analyzes a rejected payload, identifies root causes, and takes action without human interaction. The human's only touchpoint is approving/merging revert PRs on GitHub.

It uses a deterministic confidence rubric to score suspect PRs and dispatches actions based on the score:

- **HIGH confidence (>= 85)**: Automatically creates a TRT JIRA bug, opens a revert PR, and triggers payload validation jobs
- **MEDIUM confidence (60-84)**: Opens draft revert PRs as experimental reverts, triggers payload jobs, and updates the suspects YAML with pending status for later result collection
- **LOW confidence (< 60)**: Reports findings only — no automated action

For medium-confidence suspects, the experimental revert workflow handles the hours-long CI gap via the suspects YAML. Phase 1 opens experiments and marks them `action_status: pending`; running the same command again from the same directory automatically detects pending experiments and runs Phase 2 to collect results, promote confirmed causes to real revert PRs, and close innocent drafts.

The orchestrator composes three stages that are also independently invocable:
1. `/ci:analyze-payload` — produces the suspects YAML
2. `/ci:payload-revert` — stages reverts for HIGH confidence suspects
3. `/ci:payload-experiment` — experimentally tests MEDIUM confidence suspects

### Key Features

- **Autonomous operation**: No human interaction during execution
- **Confidence-based dispatch**: Deterministic rubric ensures consistent scoring
- **Experimental reverts**: Draft revert PRs test medium-confidence suspects experimentally
- **Reentrant**: Automatically resumes experiment Phase 2 when suspects YAML has pending experiments
- **Comprehensive report**: HTML report includes staged reverts, experiment status, and full analysis

## Implementation

Load the `payload-agent` skill and follow its implementation steps. The skill orchestrates:

1. Reading the suspects YAML (if it exists) and detecting resume state (pending experiments)
2. Analyzing the payload using the `analyze-payload` skill (if needed)
3. Classifying suspects by confidence tier
4. Dispatching actions: staging reverts (HIGH), experimental reverts (MEDIUM), or reporting (LOW)
5. Generating an augmented HTML report with action results

## Return Value

- **Format**: Self-contained HTML file + JSON data file saved to the current working directory
- **Filenames**:
  - `payload-analysis-{tag}-summary.html` — HTML report
  - `payload-analysis-{tag}-autodl.json` — JSON data for database ingestion
  - `payload-analysis-{tag}-suspects.yaml` — Scored suspects with action tracking for all tiers
- **Contents** (all `<a>` links must use `target="_blank"` to open in a new tab):
  - Everything from `analyze-payload` (executive summary, blocking jobs table, failure details, suspect PRs)
  - Staged Reverts table with JIRA tickets, revert PRs, and triggered payload jobs (when high-confidence reverts are staged)
  - Experiments In Progress section with draft PRs and payload test URLs (when experiment Phase 1 runs)
  - Experiment Results section with confirmed/innocent verdicts (when experiment Phase 2 completes)

## Examples

1. **Analyze and act on a nightly payload**:
   ```
   /ci:payload-agent 4.22.0-0.nightly-2026-02-25-152806
   ```

2. **Resume experiments to collect results** (run the same command again from the same directory):
   ```
   /ci:payload-agent 4.22.0-0.nightly-2026-02-25-152806
   ```

## Arguments

- $1: A full payload tag (e.g., `4.22.0-0.nightly-2026-02-25-152806`). Version, stream, and architecture are parsed from the tag automatically. (required)

## Skills Used

- `payload-agent`: Orchestrator with confidence scoring and decision dispatch
- `analyze-payload`: Core payload analysis (failure history, PR correlation, job investigation)
- `stage-payload-reverts`: Creates TRT JIRA bugs, opens revert PRs, triggers payload jobs for high-confidence candidates
- `payload-experimental-reverts`: Opens draft revert PRs and triggers payload jobs for medium-confidence candidates; collects results in Phase 2
- `fetch-payloads`: Fetches recent payloads from the release controller
- `fetch-new-prs-in-payload`: Identifies PRs new in a given payload vs its predecessor
- `prow-job-analyze-install-failure`: Analyzes install failures (used by subagents)
- `prow-job-analyze-test-failure`: Analyzes test failures (used by subagents)
- `revert-pr`: Git revert workflow for creating revert PRs
