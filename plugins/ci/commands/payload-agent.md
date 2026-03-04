---
description: Autonomous agent that analyzes a rejected payload, determines root causes, and takes action based on confidence scoring
argument-hint: "<payload-tag> [--lookback N] [--continue]"
---

## Name

ci:payload-agent

## Synopsis

```
/ci:payload-agent <payload-tag> [--lookback N] [--continue]
```

## Description

The `ci:payload-agent` command is an autonomous orchestrator that analyzes a rejected payload, identifies root causes, and takes action without human interaction. The human's only touchpoint is approving/merging revert PRs on GitHub.

It uses a deterministic confidence rubric to score suspect PRs and dispatches actions based on the score:

- **HIGH confidence (>= 85)**: Automatically creates a TRT JIRA bug, opens a revert PR, and triggers payload validation jobs
- **MEDIUM confidence (60-84)**: Opens draft revert PRs as bisect experiments, triggers payload jobs, and writes a tracking YAML for later result collection
- **LOW confidence (< 60)**: Reports findings only — no automated action

For medium-confidence suspects, the bisect workflow handles the hours-long CI gap via a YAML tracking file and `--continue` session resume. Phase 1 opens experiments and exits; Phase 2 (invoked with `--continue`) collects results after jobs complete, promotes confirmed causes to real revert PRs, and closes innocent drafts.

### Key Features

- **Autonomous operation**: No human interaction during execution
- **Confidence-based dispatch**: Deterministic rubric ensures consistent scoring
- **Bisect experiments**: Draft revert PRs test medium-confidence suspects experimentally
- **Session resume**: `--continue` collects bisect results after CI jobs complete
- **Comprehensive report**: HTML report includes staged reverts, bisect status, and full analysis

## Implementation

Load the `payload-agent` skill and follow its implementation steps. The skill orchestrates:

1. Analyzing the payload using the `analyze-payload` skill (Steps 1-6)
2. Scoring suspect PRs with the confidence rubric
3. Dispatching actions: staging reverts (HIGH), bisecting (MEDIUM), or reporting (LOW)
4. Generating an augmented HTML report with action results
5. Writing bisect tracking YAML when experiments are initiated

## Return Value

- **Format**: Self-contained HTML file + JSON data file saved to the current working directory
- **Filenames**:
  - `payload-analysis-{tag}-summary.html` — HTML report
  - `payload-analysis-{tag}-autodl.json` — JSON data for database ingestion
  - `{tag}-bisect.yaml` — Bisect tracking file (only when medium-confidence suspects are bisected)
- **Contents** (all `<a>` links must use `target="_blank"` to open in a new tab):
  - Everything from `analyze-payload` (executive summary, blocking jobs table, failure details, suspect PRs)
  - Staged Reverts table with JIRA tickets, revert PRs, and triggered payload jobs (when high-confidence reverts are staged)
  - Bisect In Progress section with draft PRs and payload test URLs (when bisect Phase 1 runs)
  - Bisect Results section with confirmed/innocent verdicts (when bisect Phase 2 completes)

## Examples

1. **Analyze and act on a nightly payload**:
   ```
   /ci:payload-agent 4.22.0-0.nightly-2026-02-25-152806
   ```

2. **Analyze with deeper lookback**:
   ```
   /ci:payload-agent 4.22.0-0.nightly-2026-02-25-152806 --lookback 20
   ```

3. **Resume bisect to collect results**:
   ```
   /ci:payload-agent 4.22.0-0.nightly-2026-02-25-152806 --continue
   ```

## Arguments

- $1: A full payload tag (e.g., `4.22.0-0.nightly-2026-02-25-152806`). Version, stream, and architecture are parsed from the tag automatically. (required)
- `--lookback N`: Maximum number of consecutive rejected payloads to examine (optional, default: 10)
- `--continue`: Resume bisect Phase 2 from a previous session. Reads the tracking YAML from the current working directory and collects payload job results. (optional)

## Skills Used

- `payload-agent`: Orchestrator with confidence scoring and decision dispatch
- `analyze-payload`: Core payload analysis (failure history, PR correlation, job investigation)
- `stage-payload-reverts`: Creates TRT JIRA bugs, opens revert PRs, triggers payload jobs for high-confidence candidates
- `bisect-payload-suspects`: Opens draft revert PRs and triggers payload jobs for medium-confidence candidates; collects results in Phase 2
- `fetch-payloads`: Fetches recent payloads from the release controller
- `fetch-new-prs-in-payload`: Identifies PRs new in a given payload vs its predecessor
- `prow-job-analyze-install-failure`: Analyzes install failures (used by subagents)
- `prow-job-analyze-test-failure`: Analyzes test failures (used by subagents)
- `revert-pr`: Git revert workflow for creating revert PRs
