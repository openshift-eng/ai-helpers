---
description: Analyze a rejected nightly payload with historical lookback to identify root causes of blocking job failures
argument-hint: "[version] [architecture] [--lookback N]"
---

## Name

ci:analyze-payload

## Synopsis

```
/ci:analyze-payload [version] [architecture] [--lookback N]
```

## Description

The `ci:analyze-payload` command finds the latest rejected nightly payload for a given OCP version, investigates every failed blocking job, and produces a self-contained HTML report summarizing what went wrong.

It performs **historical lookback** through consecutive rejected payloads to determine when each failure first appeared. For each originating payload (where a job first started failing), it fetches the new PRs introduced in that payload as likely culprits. This distinguishes new failures from persistent/permafailing jobs and helps identify the root cause commits.

When a suspect PR can be correlated with high confidence (>= 90%) to a blocking job failure — based on component match, error analysis, and timing — the report will **recommend it for revert** with a rationale. The `/ci:revert-pr` command can then be used to execute the revert.

Failed jobs are investigated **in parallel** using subagents with the appropriate analysis skill (install failure vs test failure).

### Key Features

- **Automatic payload discovery**: Finds the latest rejected nightly payload
- **Historical lookback**: Walks back through up to N consecutive rejected payloads (default 10) to find when each job first started failing
- **PR correlation**: Uses the `fetch-new-prs-in-payload` skill to identify PRs that landed in the originating payload for each failure
- **Parallel investigation**: Kicks off subagents for each failed blocking job using the appropriate CI analysis skill
- **Revert recommendations**: Proposes specific PRs to revert when the evidence strongly links them to a failure
- **HTML report**: Generates an attractive, self-contained HTML report with collapsible sections, color-coded severity, and executive summary

## Implementation

Load the "Analyze Payload" skill and follow its implementation steps. The skill orchestrates:

1. Fetching recent rejected payloads using the `fetch-payloads` skill
2. Walking back through consecutive rejected payloads to build failure history
3. Fetching new PRs in originating payloads using the `fetch-new-prs-in-payload` skill
4. Launching parallel subagents to investigate each failed job
5. Generating the final HTML report

## Return Value

- **Format**: Self-contained HTML file saved to the current working directory
- **Filename**: `payload-analysis-{tag}.html`
- **Contents**:
  - Executive summary with overall payload health
  - Summary table of all blocking jobs (pass/fail)
  - Per-job failure analysis with root cause, error messages, and logs
  - Failure streak length (how many consecutive payloads each job has failed)
  - Originating payload and suspect PRs for each persistent failure
  - Recommended reverts section with PR links, rationale, and `/ci:revert-pr` instructions
  - Color-coded severity and collapsible detail sections

## Examples

1. **Analyze latest rejected 4.22 nightly (defaults to amd64, lookback 10)**:
   ```
   /ci:analyze-payload 4.22
   ```

2. **Analyze with specific architecture**:
   ```
   /ci:analyze-payload 4.22 arm64
   ```

3. **Analyze with deeper lookback**:
   ```
   /ci:analyze-payload 4.22 amd64 --lookback 20
   ```

4. **Analyze latest version (auto-detected)**:
   ```
   /ci:analyze-payload
   ```

## Arguments

- $1: OCP version (optional, default: latest from Sippy) — e.g., 4.18, 4.22
- $2: CPU architecture (optional, default: amd64) — amd64, arm64, ppc64le, s390x, multi
- `--lookback N`: Maximum number of consecutive rejected payloads to examine (optional, default: 10)

## Skills Used

- `fetch-payloads`: Fetches recent payloads from the release controller
- `fetch-new-prs-in-payload`: Identifies PRs new in a given payload vs its predecessor
- `prow-job-analyze-install-failure`: Analyzes install failures (used by subagents)
- `prow-job-analyze-test-failure`: Analyzes test failures (used by subagents)
- `revert-pr`: Referenced in recommendations for executing reverts of identified culprit PRs
