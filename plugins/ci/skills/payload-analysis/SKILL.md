---
name: payload-analysis
description: Analyze an OpenShift payload snapshot, determine the causes of failed blocking jobs, score causal PRs, and produce HTML, YAML, and JSON results with evidence-gated revert recommendations. Use for rejected, ready, or force-accepted payload investigation.
argument-hint: "<payload-tag> [--snapshot-dir DIR]"
---

# Payload Analysis

Run an evidence-first payload investigation. Keep observation, attribution, and
action authorization as separate phases so a recent PR cannot reshape the
observed failure.

## Required skills

Load these schema skills before creating outputs:

1. `ci:payload-results-yaml`
2. `ci:payload-autodl-json`

Use `ci:prow-job-analysis` inside each failed-job investigation.

## Working state

Capture the invocation directory as `OUTPUT_DIR`; write all final files there.
Maintain compact intermediate state at:

```text
.work/payload-analysis/<payload-tag>/analysis-state.yaml
```

The state file is an evidence handoff, not a report. Record artifact paths and
short excerpts rather than copying logs. Do not record candidate PRs until the
observed failure signatures and causal chains are frozen.

## Reference routing

Read a reference when its subject becomes relevant. Do not preload every
reference.

### Snapshot and scope

Read [references/snapshot.md](references/snapshot.md) when locating or creating
the snapshot, enumerating failed blocking jobs, and initializing working state.

### Job investigation

Read [references/job-investigation.md](references/job-investigation.md) before
dispatching failed-job investigators. Investigate every failed blocking job and
freeze its observed failure modes without inspecting or ranking payload PRs.

Wait for every investigator to return a complete `ANALYSIS_RESULT` before
continuing.

### Signatures and causal chains

Read [references/signatures-and-chains.md](references/signatures-and-chains.md)
when splitting mixed streaks, establishing signature boundaries, or
adjudicating conflicting causes.

### Change attribution and scoring

Read [references/attribution-and-scoring.md](references/attribution-and-scoring.md)
only after causal records are frozen. Use it to enumerate changes, inspect
diffs, map behavior to the earliest event, and score hypotheses.

### Revert and force-accept decisions

Read [references/revert-and-force-accept.md](references/revert-and-force-accept.md)
when applying action gates, checking revert history, and deciding force-accept
eligibility.

### Output generation

Read [references/output-files.md](references/output-files.md) before generating:

```text
payload-analysis-<sanitized-tag>-summary.html
payload-results-<sanitized-tag>.yaml
payload-analysis-<sanitized-tag>-autodl.json
```

All three files must be non-empty and located directly under `OUTPUT_DIR`.

### Review and self-check

Read [references/review-and-self-check.md](references/review-and-self-check.md)
when falsifying actionable conclusions and validating the final outputs.

## Non-negotiable decisions

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
