# Disruption Plugin

Skills for investigating disruption in OpenShift CI: when disruption on a series started or changed, which runs to look at, why they were disrupted, what differs before and after a change, which code change could explain it, and whether it is already tracked.

## Skills

Start with **`investigate-disruption`**. It picks a workflow for the question and runs the other skills in order, stopping between them so you can steer. Each skill also works on its own.

| Skill | Answers |
|---|---|
| [`investigate-disruption`](skills/investigate-disruption/SKILL.md) | Entry point: chooses the workflow, runs the skills with checkpoints, and writes the report with a verdict |
| [`disruption-trend`](skills/disruption-trend/SKILL.md) | When did disruption on a series start, get worse, or improve? |
| [`disruption-find-runs`](skills/disruption-find-runs/SKILL.md) | Which runs to analyze: current disrupted runs, before/after cohorts around a transition, or your own cohorts checked |
| [`disruption-analyze-run`](skills/disruption-analyze-run/SKILL.md) | Why was each run disrupted? Intervals, rollouts, and etcd, OVS, CPU, and cloud signals |
| [`disruption-compare-cohorts`](skills/disruption-compare-cohorts/SKILL.md) | What differs between before and after: new, pre-existing with more impact, or unchanged |
| [`disruption-change-suspects`](skills/disruption-change-suspects/SKILL.md) | Which PRs between two payloads fit the mechanism |
| [`disruption-known-issues`](skills/disruption-known-issues/SKILL.md) | Is it tracked? Demonstrated mechanism matches kept apart from related cards |

## Workflows

Defined once in [`investigate-disruption/references/workflows.md`](skills/investigate-disruption/references/workflows.md), and followed by both `investigate-disruption` and Chai:

| Workflow | Typical request |
|---|---|
| W1. Explain runs | "Why was this run disrupted?" with Prow URLs |
| W2. Find onset | "When did disruption start on kube-api-new-connections?" |
| W3. Investigate regression | A `DisruptionRegression*` alert or dashboard, or "what made it worse?" |
| W4. Compare cohorts | "Compare these good runs to these bad ones" |
| W5. Sample current disruption | "What is disrupting this series right now?" |
| W6. What changed | "What landed between payload A and B that could hit kube-api?" |

Regression investigations end with a verdict: explained, partially explained, or cause unresolved.

## Shared library

`scripts/disruption_common/` holds the code several skills use: series resolution from alerts and dashboards, Sippy access, payload pairs, anonymous GCS reads, interval loading, investigation state, and Jira query building. Its tests are in `tests/`. Install the whole plugin: Claude Code does, and Chai copies the plugin's `scripts/` tree into every skill it installs, so no extra persona configuration is needed. A skill installed without it exits with a message saying the library is missing.

## Prerequisites

- Python 3.7 or later.
- Network access to `sippy.dptools.openshift.org`, `storage.googleapis.com`, and `*.ocp.releases.ci.openshift.org`. All are public.
- The gcloud CLI for `disruption-analyze-run`, for `payload_diff.py` in `disruption-change-suspects` with `job:build_id` runs, and for the fix check in `disruption-known-issues` (anonymous reads from the public `test-platform-results-public` bucket).
- `oc`, only when `payload_diff.py` is given a release pullspec.
- `gh`, authenticated, for `disruption-change-suspects` to read PR descriptions and diffs.
- The Atlassian MCP tools for `disruption-known-issues`.
