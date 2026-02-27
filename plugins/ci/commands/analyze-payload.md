---
description: Analyze a rejected or in-progress payload with historical lookback to identify root causes of blocking job failures
argument-hint: "<payload-tag> [--lookback N] [--stage-revert]"
---

## Name

ci:analyze-payload

## Synopsis

```
/ci:analyze-payload <payload-tag> [--lookback N] [--stage-revert]
```

## Description

The `ci:analyze-payload` command analyzes a specific payload tag, investigates every failed blocking job, and produces a self-contained HTML report summarizing what went wrong.

It supports both **Rejected** payloads (full analysis) and **Ready** payloads (early analysis of blocking jobs that have already failed, to determine if the payload is on track for rejection).

It performs **historical lookback** through consecutive rejected payloads to determine when each failure first appeared. For each originating payload (where a job first started failing), it fetches the new PRs introduced in that payload as likely culprits. This distinguishes new failures from persistent/permafailing jobs and helps identify the root cause commits.

When a suspect PR can be correlated with high confidence (>= 90%) to a blocking job failure — based on component match, error analysis, and timing — the report will **recommend it for revert** with a rationale. The `/ci:revert-pr` command can then be used to execute the revert.

When `--stage-revert` is passed, the command automatically creates a TRT JIRA bug (with `trt-incident` label) for each revert candidate, opens a revert PR on GitHub, triggers `/payload-job` commands for the failing blocking jobs, and shows links to all created artifacts in the HTML report.

Failed jobs are investigated **in parallel** using subagents with the appropriate analysis skill (install failure vs test failure).

### Key Features

- **Historical lookback**: Walks back through up to N consecutive rejected payloads (default 10) to find when each job first started failing
- **PR correlation**: Uses the `fetch-new-prs-in-payload` skill to identify PRs that landed in the originating payload for each failure
- **Parallel investigation**: Kicks off subagents for each failed blocking job using the appropriate CI analysis skill
- **Revert recommendations**: Proposes specific PRs to revert when the evidence strongly links them to a failure
- **HTML report**: Generates an attractive, self-contained HTML report with collapsible sections, color-coded severity, and executive summary
- **Automated staged reverts**: With `--stage-revert`, automatically creates TRT tickets, opens revert PRs, and triggers payload jobs

## Implementation

Load the "Analyze Payload" skill and follow its implementation steps. The skill orchestrates:

1. Fetching recent rejected payloads using the `fetch-payloads` skill
2. Walking back through consecutive rejected payloads to build failure history
3. Fetching new PRs in originating payloads using the `fetch-new-prs-in-payload` skill
4. Launching parallel subagents to investigate each failed job
5. Generating the final HTML report

## Return Value

- **Format**: Self-contained HTML file saved to the current working directory
- **Filename**: `payload-analysis-{tag}-summary.html`
- **Contents** (all `<a>` links must use `target="_blank"` to open in a new tab):
  - Executive summary with overall payload health
  - Summary table of all blocking jobs (pass/fail)
  - Per-job failure analysis with root cause, error messages, and logs
  - Failure streak length (how many consecutive payloads each job has failed)
  - Originating payload and suspect PRs for each persistent failure
  - Recommended reverts section with PR links, rationale, and `/ci:revert-pr` instructions (default mode), or a "Staged Reverts" table with links to created TRT tickets, revert PRs, and triggered payload jobs (when `--stage-revert` is used)
  - Color-coded severity and collapsible detail sections

## Examples

1. **Analyze an amd64 nightly payload**:
   ```
   /ci:analyze-payload 4.22.0-0.nightly-2026-02-25-152806
   ```

2. **Analyze a CI stream payload**:
   ```
   /ci:analyze-payload 4.22.0-0.ci-2026-02-25-152806
   ```

3. **Analyze an arm64 nightly payload** (architecture is inferred from the tag):
   ```
   /ci:analyze-payload 4.22.0-0.nightly-arm64-2026-02-25-152806
   ```

4. **Analyze with deeper lookback**:
   ```
   /ci:analyze-payload 4.22.0-0.nightly-2026-02-25-152806 --lookback 20
   ```

5. **Analyze and automatically stage reverts for identified culprits**:
   ```
   /ci:analyze-payload 4.22.0-0.nightly-2026-02-25-152806 --stage-revert
   ```

## Arguments

- $1: A full payload tag (e.g., `4.22.0-0.nightly-2026-02-25-152806`). Version, stream, and architecture are parsed from the tag automatically. Tags without an architecture suffix (e.g., `4.22.0-0.nightly-...`) are amd64. Tags with an architecture suffix (e.g., `4.22.0-0.nightly-arm64-...`, `4.22.0-0.nightly-ppc64le-...`) use that architecture. (required)
- `--lookback N`: Maximum number of consecutive rejected payloads to examine (optional, default: 10)
- `--stage-revert`: Automatically create TRT JIRA bugs, open revert PRs, and trigger `/payload-job` commands for each revert candidate (optional, default: false)

## Skills Used

- `fetch-payloads`: Fetches recent payloads from the release controller
- `fetch-new-prs-in-payload`: Identifies PRs new in a given payload vs its predecessor
- `prow-job-analyze-install-failure`: Analyzes install failures (used by subagents)
- `prow-job-analyze-test-failure`: Analyzes test failures (used by subagents)
- `revert-pr`: Referenced in recommendations for executing reverts of identified culprit PRs
