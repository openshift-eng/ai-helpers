---
name: payload-analysis
description: Use when analyzing a Rejected, Ready, or force-accepted OpenShift payload to identify root causes of blocking job failures, score candidate changes, and produce HTML, YAML, and JSON results with revert and force-accept recommendations.
argument-hint: "<payload-tag> [--snapshot-dir DIR]"
---

# Payload Analysis

This skill analyzes a payload using a local snapshot (produced by `ci:payload-snapshot`) to identify root causes of blocking job failures and produce a comprehensive HTML report. The snapshot provides the payload, GitHub, and CI evidence needed to begin the investigation; use the recorded artifact locations and targeted source-history searches when deeper evidence is required.

It supports **Rejected** payloads (full analysis of all failed blocking jobs), **Ready** payloads (early analysis of blocking jobs that have already failed), and **Accepted** payloads (which may have been force-accepted despite blocking failures).

## When to Use This Skill

Use this skill when you need to:

- Understand why a payload was rejected
- Investigate failures in a force-accepted payload
- Assess whether an in-progress ("Ready") payload is likely to be rejected
- Determine whether failures are new or persistent
- Identify which PRs likely caused new failures
- Get a comprehensive overview of payload health with actionable root cause analysis
- Re-analyze a historical payload against its original snapshot data

## Inputs and Outputs

The required input is a full payload tag. An optional `--snapshot-dir DIR`
points to the matching snapshot; otherwise locate or create it as described
below.

Write these three files to the directory where the analysis was invoked:

```text
payload-analysis-<sanitized-tag>-summary.html
payload-results-<sanitized-tag>.yaml
payload-analysis-<sanitized-tag>-autodl.json
```

The HTML is the human-readable report. The YAML records candidates, revert
gates, and decisions for downstream payload workflows. The JSON contains the
denormalized ingestion records.

## Examples

1. **Analyze an amd64 nightly payload** (auto-creates snapshot if needed):
   ```
   /ci:payload-analysis 4.22.0-0.nightly-2026-02-25-152806
   ```

2. **Analyze using an existing snapshot directory**:
   ```
   /ci:payload-analysis 4.22.0-0.nightly-2026-02-25-152806 --snapshot-dir payload/4.22/nightly
   ```

3. **Analyze an arm64 payload** (architecture inferred from tag):
   ```
   /ci:payload-analysis 4.22.0-0.nightly-arm64-2026-02-25-152806
   ```

## Required Skills

Before starting, you **MUST** load the following skills because they define the output schemas:

1. **`ci:payload-results-yaml`** — schema for the payload results YAML file
2. **`ci:payload-autodl-json`** — schema for the autodl JSON data file

## Prerequisites

1. **Python 3** (3.10 or later) — for running the snapshot script if needed
2. **gcloud CLI** — for subagent artifact download (must-gather, pod logs)
3. **GitHub CLI (`gh`)** — for step-registry change detection and checking existing revert PRs

## Workflow

Complete every section below. Read a reference when beginning that part of the
work, not all at startup, so its detailed instructions are fresh when needed.

### Prepare the snapshot and failure data

Read
[references/snapshot-and-failure-data.md](references/snapshot-and-failure-data.md)
and complete every action in it. This establishes the output directory, locates
the snapshot, and extracts the failed blocking jobs and preliminary change data.

### Investigate jobs and validate failure signatures

Read
[references/job-investigation-and-signatures.md](references/job-investigation-and-signatures.md)
and complete every action in it. Investigate every failed blocking job,
validate each minimal causal signature and its true boundary, adjudicate
conflicting causes, and build the executed causal chains.

Do not score changes until the failure signatures and their boundaries have
been established.

### Attribute changes and decide actions

Read
[references/attribution-and-actions.md](references/attribution-and-actions.md)
and complete every action in it. Check payload PRs, CI changes, and RHCOS
changes; score causally supported candidates; apply the revert gates; verify
existing reverts; decide force-accept eligibility; and write the results YAML.

### Generate and review the final outputs

Read
[references/report-and-review.md](references/report-and-review.md)
and complete every action in it. Generate the HTML and JSON, perform the
adversarial completeness review, run the final consistency checks, and present
the three output paths.

## See Also

- Related Skill: `ci:payload-snapshot` — creates the snapshot data this skill consumes
- Related Skill: `ci:payload-results-yaml` — schema for the results YAML
- Related Skill: `ci:payload-autodl-json` — schema for the autodl JSON data file
- Related Skill: `ci:prow-job-analysis` — deep test/install failure investigation
- Related Command: `/ci:payload-revert` — stages reverts for eligible candidates
- Related Command: `/ci:payload-experiment` — tests medium-confidence candidates experimentally
