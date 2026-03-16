---
name: Payload Results YAML
description: State management for agentic payload triage actions — you must use this skill whenever reading or writing the payload results YAML file
---

# Payload Results YAML

This skill defines the schema for the `payload-results-{tag}.yaml` file and provides the operations for reading and writing it. All skills in the payload triage pipeline must use this skill when interacting with the results file.

## When to Use This Skill

Use this skill whenever you need to:
- **Create** a new results file (during `analyze-payload`)
- **Read** candidates or their actions (during `payload-revert`, `payload-experiment`)
- **Append an action** to a candidate (during `stage-payload-reverts`, `payload-experimental-reverts`)
- **Update an action's status** (during `payload-experimental-reverts` Phase 2)

## File Location

The file is always written to and read from the current working directory:

```
payload-results-{tag}.yaml
```

Where `{tag}` is the full payload tag with colons and slashes replaced by hyphens (e.g., `payload-results-4.22.0-0.nightly-2026-02-25-152806.yaml`).

## Schema

```yaml
metadata:
  payload_tag: "4.22.0-0.nightly-2026-02-25-152806"
  version: "4.22"
  stream: "nightly"
  architecture: "amd64"
  release_controller_url: "https://amd64.ocp.releases.ci.openshift.org/..."
  analyzed_at: "2026-02-26T10:30:00Z"

failing_jobs:
  - job_name: "periodic-ci-...-e2e-aws-ovn"
    prow_url: "https://prow.ci.openshift.org/..."
    is_aggregated: false
    underlying_job_name: ""
    failure_type: "test"
    root_cause_summary: "OVN gateway mode selection regression"
    streak_length: 5
    originating_payload_tag: "4.22.0-0.nightly-2026-02-20-150000"
    failure_pattern: "F F F F F S S"
  - job_name: "periodic-ci-...-e2e-gcp-ovn-techpreview"
    prow_url: "https://prow.ci.openshift.org/..."
    is_aggregated: false
    underlying_job_name: ""
    failure_type: "infra"
    root_cause_summary: "Pods deleted unexpectedly on build04 cluster"
    streak_length: 1
    originating_payload_tag: "4.22.0-0.nightly-2026-02-25-152806"
    failure_pattern: "F"

candidates:
  - pr_url: "https://github.com/openshift/cno/pull/2037"
    pr_number: 2037
    component: "cluster-network-operator"
    title: "Fix OVN gateway mode selection"
    confidence_score: 95
    rationale: "temporal match + component match + error references code changed"
    failing_jobs:
      - "periodic-ci-...-e2e-aws-ovn"
    actions:
      - type: "revert"
        status: "staged"
        revert_pr_url: "https://github.com/openshift/cno/pull/2038"
        revert_pr_state: "open"
        result_summary: "Revert PR opened and payload jobs triggered"
        jira_key: "TRT-1234"
        jira_url: "https://redhat.atlassian.net/browse/TRT-1234"
        payload_jobs:
          - command: "/payload-job periodic-ci-...-e2e-aws-ovn"
            test_url: "https://pr-payload-tests.ci.openshift.org/runs/ci/..."
            test_prow_url: "https://prow.ci.openshift.org/view/gs/..."
```

### `metadata`

Written once by `analyze-payload`. Never modified by downstream skills.

| Field | Type | Description |
|-------|------|-------------|
| `payload_tag` | string | Full payload tag being analyzed |
| `version` | string | OCP version (e.g., `"4.22"`) |
| `stream` | string | `"nightly"` or `"ci"` |
| `architecture` | string | `"amd64"`, `"arm64"`, `"multi"`, etc. |
| `release_controller_url` | string | URL to the payload on the release controller |
| `analyzed_at` | string | ISO 8601 timestamp of when the analysis was performed |

### `failing_jobs[]`

All failed blocking jobs in the payload. Written once by `analyze-payload`. Never modified by downstream skills. This is the authoritative list of failures — every failed blocking job appears here regardless of whether a candidate PR has been identified.

| Field | Type | Description |
|-------|------|-------------|
| `job_name` | string | Full periodic job name |
| `prow_url` | string | Prow URL for the failing run |
| `is_aggregated` | bool | Whether this is an aggregated job |
| `underlying_job_name` | string | For aggregated jobs, the underlying periodic job name; `""` otherwise |
| `failure_type` | string | `"test"`, `"install"`, `"upgrade"`, or `"infra"` |
| `root_cause_summary` | string | Brief description of the failure mode |
| `streak_length` | int | Consecutive payloads this job has been failing |
| `originating_payload_tag` | string | The payload where this job first started failing in the current streak |
| `failure_pattern` | string | Pass/fail history across the lookback window, most recent first (e.g., `"F F F S F F"`) |

### `candidates[]`

Each entry represents a PR identified as a candidate cause of payload failures. Top-level candidate fields are written once by `analyze-payload` and are read-only to downstream skills. The `actions` sub-array is mutable (see below).

Candidates reference failing jobs by `job_name` via the `failing_jobs` string array, linking back to the top-level `failing_jobs[]` entries.

| Field | Type | Description |
|-------|------|-------------|
| `pr_url` | string | GitHub PR URL |
| `pr_number` | int | PR number |
| `component` | string | OCP component name |
| `title` | string | PR title |
| `confidence_score` | int | 0-100 confidence that this PR caused the failures |
| `rationale` | string | Explanation of why this PR is a candidate |
| `failing_jobs` | array of strings | Job names from the top-level `failing_jobs[]` that this candidate is blamed for |
| `actions` | array | Actions taken on this candidate (see below) |

### `candidates[].actions[]`

Actions taken on a candidate. New entries are **appended** by downstream skills. Existing entries may be **updated in place** (e.g., `status`, `result_summary`, `payload_jobs`) by the Update Action Status operation. An empty array means no action has been taken.

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"revert"` or `"experiment"` |
| `status` | string | See status values below |
| `revert_pr_url` | string | URL of the revert PR (draft or real) |
| `revert_pr_state` | string | `"draft"`, `"open"`, `"merged"`, `"closed"` |
| `result_summary` | string | Brief description of the outcome |
| `jira_key` | string | TRT JIRA key (e.g., `"TRT-1234"`), or `""` |
| `jira_url` | string | TRT JIRA URL, or `""` |
| `payload_jobs` | array | Payload validation jobs triggered (see below) |

**Status values:**

| Status | Meaning |
|--------|---------|
| `"open"` | Pre-existing revert PR found open during analysis |
| `"merged"` | Pre-existing revert PR already merged |
| `"staged"` | Revert PR and JIRA created, payload jobs triggered (used by `type: "revert"`) |
| `"pending"` | Experiment dispatched, payload jobs running, results not yet collected |
| `"passed"` | Payload jobs passed with the revert — candidate confirmed as cause |
| `"failed"` | Payload jobs still fail with the revert — candidate is innocent |
| `"inconclusive"` | Mixed or unfinished results |
| `"skipped_conflict"` | Revert has merge conflicts, skipped |
| `"deferred"` | Jobs skipped due to triggering limits, or candidate exceeded max experiment count |

### `candidates[].actions[].payload_jobs[]`

Payload validation jobs triggered against the revert PR.

| Field | Type | Description |
|-------|------|-------------|
| `command` | string | The payload command posted on the PR (e.g., `/payload-job periodic-ci-...-e2e-aws-ovn`) |
| `test_url` | string | pr-payload-tests URL for the run |
| `test_prow_url` | string | Prow URL for the resulting test run |

## Operations

### Create (used by `analyze-payload`)

Write a new `payload-results-{tag}.yaml` with `metadata`, `failing_jobs`, and `candidates` populated. All failed blocking jobs are recorded in `failing_jobs`. Candidates with no pre-existing revert start with `actions: []`. If a pre-existing revert PR is discovered during analysis, append an action with `type: "revert"` and `status: "open"` or `"merged"`.

### Read Candidates (used by `payload-revert`, `payload-experiment`)

Read the file. Filter candidates by `confidence_score` range. Exclude candidates that already have an action with `status` of `"open"` or `"merged"` (pre-existing revert). Return matching candidates. Use the top-level `failing_jobs[]` to look up full job details for each candidate's `failing_jobs` references.

### Append Action (used by `stage-payload-reverts`, `payload-experimental-reverts`)

For a given candidate (matched by `pr_url`), append a new entry to its `actions` array. Do not modify existing action entries.

### Update Action Status (used by `payload-experimental-reverts` Phase 2)

For a given candidate's action entry (matched by `pr_url` and `type`), update its `status`, `result_summary`, `revert_pr_state`, `jira_key`, `jira_url`, and `payload_jobs` fields in place.

### Resume Detection (used by `payload-experiment`)

Scan all candidates. If any candidate has an action with `type: "experiment"` and `status: "pending"`, the file has in-progress experiments awaiting Phase 2 collection. Phase 2 processes only pending experiments — candidates with other statuses are left unchanged.

## See Also

- Related Skill: `analyze-payload` — creates the results file
- Related Skill: `stage-payload-reverts` — appends `type: "revert"` actions
- Related Skill: `payload-experimental-reverts` — appends `type: "experiment"` actions, updates status in Phase 2
- Related Command: `/ci:payload-revert` — stages reverts for high-confidence candidates
- Related Command: `/ci:payload-experiment` — experimentally tests medium-confidence candidates
