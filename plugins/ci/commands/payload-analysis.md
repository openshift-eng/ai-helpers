---
description: Analyze a payload snapshot to identify root causes of blocking job failures and produce an HTML report with revert recommendations
argument-hint: "<payload-tag> [--snapshot-dir DIR]"
---

## Name

ci:payload-analysis

## Synopsis

```bash
/ci:payload-analysis <payload-tag> [--snapshot-dir DIR]
```

## Description

The `ci:payload-analysis` command analyzes a specific payload tag using a local snapshot (from the `payload-snapshot` skill), investigates every failed blocking job, and produces a self-contained HTML report summarizing what went wrong.

It supports **Rejected** payloads (full analysis), **Ready** payloads (early analysis of blocking jobs that have already failed), and **Accepted** payloads (which may have been force-accepted despite blocking failures).

The analysis reads from a pre-built snapshot that contains all release controller, GitHub, and CI data frozen at the time of snapshot creation. This means:

- **Reproducible**: Re-running the analysis on the same snapshot produces consistent results
- **Historical replay**: Analyze old payloads against their original data, even after the world has moved on
- **Model-friendly**: Less capable models can perform analysis without orchestrating complex multi-skill data gathering

If no snapshot exists for the requested payload, one is created automatically.

The analysis performs **historical lookback** through the snapshot's payload chain to determine when each failure first appeared. For each originating payload, it identifies the PRs introduced as likely culprits. When a candidate PR can be correlated with high confidence (>= 85 rubric score), the report recommends it for **immediate revert** per OCP policy.

An **adversarial review** subagent checks the analysis for weak correlations, misattributions, and logical gaps before finalizing the report.

The payload results YAML output (`payload-results-{tag}.yaml`) can be consumed by composable downstream commands: `/ci:payload-revert` stages reverts for high-confidence candidates, and `/ci:payload-experiment` opens draft revert PRs for medium-confidence candidates.

### Key Features

- **Snapshot-based**: All data pre-gathered locally — no live API orchestration during analysis
- **Historical lookback**: Uses the snapshot's chain data to identify when each job first started failing
- **PR correlation**: Reads local PR diffs from the snapshot to match error messages with code changes
- **Parallel investigation**: Kicks off subagents for each failed blocking job using the appropriate CI analysis skill
- **Adversarial review**: A dedicated reviewer subagent checks conclusions before finalizing
- **Revert recommendations**: Proposes specific PRs to revert when evidence strongly links them to a failure
- **HTML report**: Self-contained HTML report with collapsible sections, color-coded severity, and executive summary

## Implementation

Load the "payload-analysis" skill and follow its implementation steps. The skill orchestrates:

1. Locating or creating a payload snapshot
2. Reading failure data, streaks, and candidate PRs from the snapshot
3. Launching parallel subagents to investigate each failed job
4. Scoring candidates and identifying revert recommendations
5. Adversarial review of conclusions
6. Generating the final HTML report, YAML, and JSON outputs

## Return Value

- **Format**: Self-contained HTML file + payload results YAML + JSON data file saved to the current working directory
- **Filenames**:
  - `payload-analysis-{tag}-summary.html` — HTML report
  - `payload-analysis-{tag}-autodl.json` — JSON data for database ingestion
  - `payload-results-{tag}.yaml` — Scored candidates for downstream commands
- **Contents** (all `<a>` links must use `target="_blank"` to open in a new tab):
  - Executive summary with overall payload health
  - Summary table of all blocking jobs (pass/fail with streaks and failure patterns)
  - Per-job failure analysis with root cause, error messages, and logs
  - Originating payload and candidate PRs for each failure
  - Recommended reverts section with PR links, rationale, and copy-paste revert text
  - Adversarial review notes
  - Color-coded severity and collapsible detail sections

## Examples

1. **Analyze an amd64 nightly payload** (auto-creates snapshot if needed):
   ```text
   /ci:payload-analysis 4.22.0-0.nightly-2026-02-25-152806
   ```

2. **Analyze using an existing snapshot directory**:
   ```text
   /ci:payload-analysis 4.22.0-0.nightly-2026-02-25-152806 --snapshot-dir payload/4.22/nightly
   ```

3. **Analyze an arm64 payload** (architecture inferred from tag):
   ```text
   /ci:payload-analysis 4.22.0-0.nightly-arm64-2026-02-25-152806
   ```

## Arguments

- $1: A full payload tag (e.g., `4.22.0-0.nightly-2026-02-25-152806`). Version, stream, and architecture are parsed from the tag automatically. Tags without an architecture suffix are amd64. (required)
- `--snapshot-dir DIR`: Path to an existing snapshot directory containing `summary.json` (optional). If not provided, searches standard locations or creates a new snapshot.

## Skills Used

- `payload-snapshot`: Creates the local data snapshot (auto-invoked if needed)
- `payload-analysis`: Orchestrates the full analysis workflow
- `payload-results-yaml`: Schema for the results YAML output
- `payload-autodl-json`: Schema for the JSON data output
- `prow-job-analyze-install-failure`: Analyzes install failures (used by subagents)
- `prow-job-analyze-test-failure`: Analyzes test failures (used by subagents)
