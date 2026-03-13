---
name: Payload Autodl JSON
description: Schema for the autodl JSON data file produced by analyze-payload for database ingestion — you must use this skill whenever generating the autodl JSON file
---

# Payload Autodl JSON

This skill defines the schema for the `payload-analysis-{tag}-autodl.json` file. The file is a flat denormalized table designed for database ingestion, with one row per (failed blocking job, candidate PR) pair.

## When to Use This Skill

Use this skill when you need to generate the autodl JSON file during `analyze-payload` (Step 8).

## File Location

The file is written to the current working directory:

```
payload-analysis-<sanitized_tag>-autodl.json
```

The filename **must** end with `-autodl.json`. Sanitize the tag for filename safety (replace colons and slashes with hyphens).

## Schema

```json
{
    "table_name": "payload_triage",
    "schema": {
        "payload_tag": "string",
        "version": "string",
        "stream": "string",
        "architecture": "string",
        "phase": "string",
        "release_controller_url": "string",
        "analyzed_at": "string",
        "rejection_streak": "int64",
        "total_blocking_jobs": "int64",
        "failed_blocking_jobs": "int64",
        "job_name": "string",
        "prow_url": "string",
        "failure_type": "string",
        "root_cause_summary": "string",
        "streak_length": "int64",
        "is_new_failure": "int64",
        "originating_payload_tag": "string",
        "candidate_pr_url": "string",
        "candidate_title": "string",
        "candidate_repo": "string",
        "candidate_confidence_score": "int64",
        "candidate_rationale": "string",
        "revert_pr_url": "string",
        "revert_pr_status": "string"
    },
    "schema_mapping": null,
    "rows": [
        {
            "payload_tag": "4.22.0-0.nightly-2026-02-25-152806",
            "version": "4.22",
            "stream": "nightly",
            "architecture": "amd64",
            "phase": "Rejected",
            "release_controller_url": "https://amd64.ocp.releases.ci.openshift.org/...",
            "analyzed_at": "2026-02-26T10:30:00Z",
            "rejection_streak": "5",
            "total_blocking_jobs": "42",
            "failed_blocking_jobs": "4",
            "job_name": "periodic-ci-openshift-release-main-ci-4.22-e2e-aws-ovn",
            "prow_url": "https://prow.ci.openshift.org/view/gs/...",
            "failure_type": "test",
            "root_cause_summary": "OVN gateway mode selection regression",
            "streak_length": "5",
            "is_new_failure": "0",
            "originating_payload_tag": "4.22.0-0.nightly-2026-02-20-150000",
            "candidate_pr_url": "https://github.com/openshift/cno/pull/2037",
            "candidate_title": "Fix OVN gateway mode selection",
            "candidate_repo": "openshift/cluster-network-operator",
            "candidate_confidence_score": "95",
            "candidate_rationale": "Error references code changed by this PR",
            "revert_pr_url": "https://github.com/openshift/cno/pull/2038",
            "revert_pr_status": "open"
        },
        {
            "payload_tag": "4.22.0-0.nightly-2026-02-25-152806",
            "version": "4.22",
            "stream": "nightly",
            "architecture": "amd64",
            "phase": "Rejected",
            "release_controller_url": "https://amd64.ocp.releases.ci.openshift.org/...",
            "analyzed_at": "2026-02-26T10:30:00Z",
            "rejection_streak": "5",
            "total_blocking_jobs": "42",
            "failed_blocking_jobs": "4",
            "job_name": "periodic-ci-openshift-release-main-ci-4.22-e2e-gcp-ovn",
            "prow_url": "https://prow.ci.openshift.org/view/gs/...",
            "failure_type": "install",
            "root_cause_summary": "Install timeout waiting for etcd quorum",
            "streak_length": "2",
            "is_new_failure": "0",
            "originating_payload_tag": "4.22.0-0.nightly-2026-02-23-080000",
            "candidate_pr_url": "",
            "candidate_title": "",
            "candidate_repo": "",
            "candidate_confidence_score": "0",
            "candidate_rationale": "",
            "revert_pr_url": "",
            "revert_pr_status": ""
        }
    ],
    "chunk_size": 0,
    "expiration_days": 0,
    "partition_column": ""
}
```

## Row Cardinality Rules

| Scenario | Rows for that job |
|----------|-------------------|
| Failed job, no candidate | 1 row — candidate fields are `""` / `"0"` |
| Failed job, 1 candidate | 1 row — candidate fields populated |
| Failed job, 2+ candidates | N rows — job fields identical, candidate fields differ per candidate |
| Passed job | 0 rows — not included |

## Field Rules

1. **All row values MUST be strings** — wrap every value in double quotes (e.g., `"5"` not `5`). The schema declares the downstream types.
2. **Empty/missing values** are empty strings (`""`). For int64 fields with no value, use `"0"`.
3. **`is_new_failure`**: `"1"` for true, `"0"` for false.
4. **`candidate_confidence_score`**: Integer 0-100, e.g. `"95"`. `"0"` when no candidate.
5. **`revert_pr_url`**: URL of the revert PR — either a pre-existing revert discovered during analysis, or one created by `stage-payload-reverts`. `""` if no revert exists.
6. **`revert_pr_status`**: `"open"`, `"merged"`, `"draft"`, `"closed"`, or `""` if no revert.
7. **`schema_mapping`** is always `null`.
8. **`chunk_size`**, **`expiration_days`**, and **`partition_column`** are always `0`, `0`, and `""`.

## Field Descriptions

### Payload-level fields (denormalized across all rows)

| Field | Type | Description |
|-------|------|-------------|
| `payload_tag` | string | Full payload tag |
| `version` | string | OCP version (e.g., `"4.22"`) |
| `stream` | string | `"nightly"` or `"ci"` |
| `architecture` | string | `"amd64"`, `"arm64"`, `"multi"`, etc. |
| `phase` | string | Payload phase: `"Rejected"`, `"Accepted"`, `"Ready"` |
| `release_controller_url` | string | URL to the payload on the release controller |
| `analyzed_at` | string | ISO 8601 timestamp of when the analysis was performed |
| `rejection_streak` | int64 | Number of consecutive rejected payloads leading up to the target |
| `total_blocking_jobs` | int64 | Total number of blocking jobs in the payload |
| `failed_blocking_jobs` | int64 | Number of failed blocking jobs |

### Job-level fields

| Field | Type | Description |
|-------|------|-------------|
| `job_name` | string | Full periodic job name |
| `prow_url` | string | Prow URL for the failing run |
| `failure_type` | string | `"test"`, `"install"`, `"upgrade"`, or `"infrastructure"` |
| `root_cause_summary` | string | Brief description of the failure mode |
| `streak_length` | int64 | Consecutive payloads this job has been failing |
| `is_new_failure` | int64 | `1` if the job first started failing in the target payload, `0` otherwise |
| `originating_payload_tag` | string | The payload where this job first started failing in the current streak |

### Candidate-level fields

| Field | Type | Description |
|-------|------|-------------|
| `candidate_pr_url` | string | GitHub PR URL, or `""` if no candidate |
| `candidate_title` | string | PR title, or `""` |
| `candidate_repo` | string | GitHub `org/repo`, or `""` |
| `candidate_confidence_score` | int64 | 0-100 confidence score, `0` when no candidate |
| `candidate_rationale` | string | Explanation of why this PR is a candidate, or `""` |
| `revert_pr_url` | string | URL of a revert PR if one exists, or `""` |
| `revert_pr_status` | string | `"open"`, `"merged"`, `"draft"`, `"closed"`, or `""` |

## Operations

### Create (used by `analyze-payload`)

Generate the full autodl JSON file with all rows populated from the analysis results. Each failed blocking job produces at least one row. Candidate fields are populated when a PR is correlated to the failure, otherwise they are empty strings / `"0"`.

### Update Revert Status (used by `stage-payload-reverts`)

After staging reverts, find rows matching `candidate_pr_url` and set:
- `revert_pr_url`: URL of the revert PR (created or pre-existing)
- `revert_pr_status`: `"open"` (or `"draft"` if draft)

### Update Experiment Status (used by `payload-experimental-reverts`)

**Phase 1 (dispatch):** After creating draft revert PRs, find rows matching `candidate_pr_url` and set:
- `revert_pr_url`: URL of the draft revert PR
- `revert_pr_status`: `"draft"`

**Phase 2 (collection):** After collecting experiment results, find rows matching `candidate_pr_url` and update:
- **PASS** (confirmed cause): `revert_pr_status`: `"open"`
- **FAIL** (innocent): `revert_pr_url`: `""`, `revert_pr_status`: `""` (draft was closed)

## See Also

- Related Skill: `analyze-payload` — creates this file in Step 8
- Related Skill: `stage-payload-reverts` — updates revert fields after staging reverts
- Related Skill: `payload-experimental-reverts` — updates revert fields after experiments
- Related Skill: `payload-results-yaml` — the YAML results file for downstream agentic actions
