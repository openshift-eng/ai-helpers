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

candidates:
  - pr_url: "https://github.com/openshift/cno/pull/2037"
    pr_number: 2037
    component: "cluster-network-operator"
    title: "Fix OVN gateway mode selection"
    confidence_score: 95
    rationale: "temporal match + component match + error references code changed"
    originating_payload_tag: "4.22.0-0.nightly-2026-02-20-150000"
    existing_revert_status: ""   # "merged", "open", or ""
    existing_revert_pr_url: ""
    failing_jobs:
      - job_name: "periodic-ci-...-e2e-aws-ovn"
        prow_url: "https://prow.ci.openshift.org/..."
        is_aggregated: false
        underlying_job_name: ""
        failure_type: "test"
        root_cause_summary: "OVN gateway mode selection regression"
    actions:
      - type: "revert"
        status: "staged"
        revert_pr_url: "https://github.com/openshift/cno/pull/2038"
        revert_pr_state: "open"
        result_summary: "Revert PR opened and payload jobs triggered"
        jira_key: "TRT-1234"
        jira_url: "https://issues.redhat.com/browse/TRT-1234"
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

### `candidates[]`

Each entry represents a PR identified as a candidate cause of payload failures. Written by `analyze-payload`, read by downstream skills.

| Field | Type | Description |
|-------|------|-------------|
| `pr_url` | string | GitHub PR URL |
| `pr_number` | int | PR number |
| `component` | string | OCP component name |
| `title` | string | PR title |
| `confidence_score` | int | 0-100 confidence that this PR caused the failures |
| `rationale` | string | Explanation of why this PR is a candidate |
| `originating_payload_tag` | string | The payload where this PR first caused failures |
| `existing_revert_status` | string | `"merged"`, `"open"`, or `""` — pre-existing revert PR status |
| `existing_revert_pr_url` | string | URL of pre-existing revert PR, or `""` |
| `failing_jobs` | array | Jobs failing due to this candidate (see below) |
| `actions` | array | Actions taken on this candidate (see below) |

### `candidates[].failing_jobs[]`

Jobs from the payload that are failing and attributed to this candidate. Written by `analyze-payload`, read by downstream skills. Never modified after creation.

| Field | Type | Description |
|-------|------|-------------|
| `job_name` | string | Full periodic job name |
| `prow_url` | string | Prow URL for the original failing run |
| `is_aggregated` | bool | Whether this is an aggregated job |
| `underlying_job_name` | string | For aggregated jobs, the underlying periodic job name; `""` otherwise |
| `failure_type` | string | `"test"`, `"install"`, `"upgrade"`, or `"infra"` |
| `root_cause_summary` | string | Brief description of the failure mode |

### `candidates[].actions[]`

Actions taken on a candidate. Each entry is **appended** by a downstream skill — never overwritten. An empty array means no action has been taken.

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

Write a new `payload-results-{tag}.yaml` with `metadata` and `candidates` populated. All candidates start with `actions: []`.

### Read Candidates (used by `payload-revert`, `payload-experiment`)

Read the file. Filter candidates by `confidence_score` range and `existing_revert_status`. Return matching candidates.

### Append Action (used by `stage-payload-reverts`, `payload-experimental-reverts`)

For a given candidate (matched by `pr_url`), append a new entry to its `actions` array. Do not modify existing action entries.

### Update Action Status (used by `payload-experimental-reverts` Phase 2)

For a given candidate's action entry (matched by `pr_url` and `type`), update its `status`, `result_summary`, `revert_pr_state`, `jira_key`, `jira_url`, and `payload_jobs` fields in place.

### Resume Detection (used by `payload-experiment`)

Scan all candidates. If any candidate has an action with `status: "pending"`, the file has in-progress experiments awaiting Phase 2 collection.

## See Also

- Related Skill: `analyze-payload` — creates the results file
- Related Skill: `stage-payload-reverts` — appends `type: "revert"` actions
- Related Skill: `payload-experimental-reverts` — appends `type: "experiment"` actions, updates status in Phase 2
- Related Command: `/ci:payload-revert` — stages reverts for high-confidence candidates
- Related Command: `/ci:payload-experiment` — experimentally tests medium-confidence candidates
