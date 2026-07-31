---
name: payload-analysis
description: Use when investigating a rejected, ready, or force-accepted OpenShift payload. Determine the causes of failed blocking jobs from snapshot evidence, attribute causal PR, CI, and RHCOS changes, and produce HTML, YAML, and JSON results with evidence-gated revert and force-accept recommendations.
argument-hint: "<payload-tag> [--snapshot-dir DIR]"
---

# Payload Analysis

## Goal

Analyze one OpenShift payload from a local snapshot produced by
`ci:payload-snapshot`. Identify the causes of every failed blocking job,
determine whether each failure is new or persistent, evaluate candidate PR,
CI, and RHCOS changes, and recommend safe next actions.

Support these payload states:

- **Rejected:** explain every failed blocking job and the rejection.
- **Ready:** analyze blocking jobs that have already failed.
- **Accepted:** analyze failures in a payload that may have been force-accepted.

## Inputs

Required:

- a full payload tag, such as
  `4.22.0-0.nightly-2026-02-25-152806`.

Optional:

- `--snapshot-dir DIR`, pointing to a directory that contains the matching
  `summary.json`.

The snapshot is the source for payload metadata, payload history, blocking
jobs, test results, artifact locations, PR data, and RHCOS changes. If no
matching snapshot exists, create one with `ci:payload-snapshot`.

## Outputs

Write these files to the directory where the skill was invoked:

```text
payload-analysis-<sanitized-tag>-summary.html
payload-results-<sanitized-tag>.yaml
payload-analysis-<sanitized-tag>-autodl.json
```

The HTML report explains the result for a person. The YAML records candidates,
action gates, and decisions for downstream payload workflows. The JSON contains
the denormalized ingestion records.

## Required skills

- Use `ci:prow-job-analysis` to investigate failed jobs.
- Load `ci:payload-results-yaml` before writing the YAML.
- Load `ci:payload-autodl-json` before writing the JSON.

## Working state

Capture the invocation directory as `OUTPUT_DIR`. Store working evidence at:

```text
.work/payload-analysis/<payload-tag>/analysis-state.yaml
```

Record short excerpts and artifact paths, not full logs. Write final outputs
directly under `OUTPUT_DIR`.

## Workflow

Complete these steps in order. Read each reference when its step begins; do not
preload all references. Update `analysis-state.yaml` after every step. Record
unknowns and missing evidence instead of guessing.

### 1. Establish the payload scope

Read [references/snapshot.md](references/snapshot.md).

- Locate or create the matching snapshot.
- Verify the payload tag, metadata, and data completeness.
- Enumerate every failed blocking job and relevant aggregated child run.
- Initialize working state with metadata, jobs, artifact paths, and data gaps.
- Do not inspect or record candidate changes.

Complete this step when every failed blocking job is queued for investigation.

### 2. Investigate every failed blocking job

Read [references/job-investigation.md](references/job-investigation.md).

- Run one evidence-only investigation per failed job using
  `ci:prow-job-analysis`.
- Provide the Prow URL, retries, aggregation context, and artifact paths.
- Identify the earliest abnormal event and split independent failure modes.
- Keep candidate PRs hidden from the investigation.
- Require a complete `ANALYSIS_RESULT` with evidence and unresolved links.

Complete this step when every failed job has a structured investigation result.

### 3. Establish signatures and causal chains

Read [references/signatures-and-chains.md](references/signatures-and-chains.md).

- Normalize each independent mechanism into a minimal signature.
- Find the signature boundary in comparable earlier executions.
- Build the ordered chain from trigger to gating symptom.
- Record competing explanations and missing links.
- Freeze the signatures, boundaries, and chains before inspecting changes.

Complete this step when each failure mode has a frozen evidence record.

### 4. Attribute changed behavior

Read
[references/attribution-and-scoring.md](references/attribution-and-scoring.md).

- Enumerate payload PRs, relevant CI changes, and RHCOS changes at each
  signature boundary.
- Trace changed behavior to the frozen earliest abnormal event.
- Reject candidates supported only by timing or component proximity.
- Score supported hypotheses and apply the causal-evidence cap.
- Record a no-candidate conclusion when no change explains the mechanism.

Complete this step when every signature has scored candidates or an explicit
no-candidate result.

### 5. Make action decisions

Read
[references/revert-and-force-accept.md](references/revert-and-force-accept.md).

- Apply all revert gates independently of confidence.
- Verify existing revert PRs and their actual diffs.
- Recommend only candidates that meet the full eligibility rule.
- Decide force-accept eligibility from the causes and payload state.

Complete this step when every candidate has gate results and the payload has an
explicit force-accept decision.

### 6. Generate the outputs

Load `ci:payload-results-yaml` and `ci:payload-autodl-json`, then read
[references/output-files.md](references/output-files.md).

- Generate all outputs from `analysis-state.yaml`.
- Put decisions and immediate actions first in the HTML.
- Include every failed blocking job, including unresolved jobs.
- Validate the YAML and compare all three outputs for consistency.

Complete this step when all three files are non-empty and mutually consistent.

### 7. Challenge and validate the result

Read [references/review-and-self-check.md](references/review-and-self-check.md)
and follow its reviewer trigger.

- Falsify every action-relevant conclusion.
- Return to the responsible workflow step when a material defect is found.
- Correct working state from source evidence and regenerate affected outputs.
- Run all mechanical and schema checks.
- Present the output paths and decision summary only after validation passes.

Complete this step when no material review finding remains unresolved.

## Decision rules

- A repeated failure proves persistence, not product causation.
- A test that detects a real infrastructure failure is not the infrastructure
  cause.
- A candidate must explain the earliest abnormal event, not merely a later
  recovery error, detector, cleanup failure, or terminal symptom.
- Timing, component ownership, and being the only nearby PR never authorize a
  revert without executed-path evidence.
- If evidence cannot distinguish credible explanations, report the cause as
  unresolved rather than guessing.
- Do not recommend standing up a specially configured cluster merely to close
  an analysis gap. Use existing artifacts, deterministic code flow, and paired
  or repeated experiments that isolate the proposed change.
