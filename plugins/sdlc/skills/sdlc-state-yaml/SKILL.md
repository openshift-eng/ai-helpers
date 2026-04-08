---
name: SDLC State YAML
description: State management for SDLC orchestrator — you must use this skill whenever reading or writing the SDLC state YAML file
---

# SDLC State YAML

This skill defines the schema for the `sdlc-state.yaml` file and provides the operations for reading and writing it. The orchestrator and all phase skills must use this skill when interacting with the state file.

## When to Use This Skill

Use this skill whenever you need to:
- **Create** a new state file (during orchestrator initialization)
- **Read** the state (at the start of each phase)
- **Update** phase status and outputs (during and after each phase)
- **Resume** from a saved state (when `--resume` flag is used)

## File Location

The file is always written to and read from:

```
.work/sdlc/{jira-key}/sdlc-state.yaml
```

Where `{jira-key}` is the Jira issue key (e.g., `OCPSTRAT-1612`).

## Schema

```yaml
schema_version: "1.0"

metadata:
  jira_key: "OCPSTRAT-1612"
  jira_url: "https://redhat.atlassian.net/browse/OCPSTRAT-1612"
  feature_summary: "Configure and Modify Internal OVN IPV4 Subnets"
  orchestrator_version: "0.1.0"
  initiated_at: "2026-04-02T10:30:00Z"
  initiated_by: "user@redhat.com"
  mode: "interactive"  # or "automation"
  remote: "origin"

current_phase:
  name: "implementation"  # enhancement|design|implementation|testing|pr_review|merge|completion
  status: "in_progress"   # pending|in_progress|completed|failed|blocked
  started_at: "2026-04-02T11:00:00Z"
  last_updated: "2026-04-02T11:15:00Z"

phases:
  enhancement:
    status: "completed"
    started_at: "2026-04-02T10:30:00Z"
    completed_at: "2026-04-02T10:45:00Z"
    outputs:
      enhancement_doc_path: ".work/sdlc/OCPSTRAT-1612/enhancement-proposal.md"
      jira_key: "OCPSTRAT-1612"
      feature_summary: "Configure and Modify Internal OVN IPV4 Subnets"
    verification_gates:
      - gate: "document_exists"
        status: "passed"
        timestamp: "2026-04-02T10:45:00Z"
      - gate: "document_valid_markdown"
        status: "passed"
        timestamp: "2026-04-02T10:45:00Z"

  design:
    status: "completed"
    started_at: "2026-04-02T10:45:00Z"
    completed_at: "2026-04-02T11:00:00Z"
    outputs:
      spec_path: ".work/sdlc/OCPSTRAT-1612/implementation-spec.md"
      estimated_complexity: "medium"
      files_to_modify: ["pkg/operator/controller.go", "api/v1beta1/types.go"]
    verification_gates:
      - gate: "spec_exists"
        status: "passed"
        timestamp: "2026-04-02T11:00:00Z"
      - gate: "user_approval"
        status: "passed"
        timestamp: "2026-04-02T11:00:00Z"

  implementation:
    status: "in_progress"
    started_at: "2026-04-02T11:00:00Z"
    outputs:
      branch_name: "fix-OCPSTRAT-1612"
      remote: "origin"
      commits: []
      files_changed: 0
      test_files_added: 0
      verification_results:
        make_lint_fix: "pending"
        make_verify: "pending"
        make_test: "pending"
        make_build: "pending"
    verification_gates:
      - gate: "make_lint_fix"
        status: "pending"
      - gate: "make_verify"
        status: "pending"
      - gate: "make_test"
        status: "pending"

  testing:
    status: "pending"

  pr_review:
    status: "pending"

  merge:
    status: "pending"

  completion:
    status: "pending"

resumability:
  can_resume: true
  resume_from_phase: "implementation"
  blocking_issues: []
  manual_intervention_required: false

errors:
  - phase: "implementation"
    timestamp: "2026-04-02T11:08:00Z"
    error_type: "lint_failure"
    message: "goimports found unsorted imports"
    resolved: true
    resolution: "Applied make lint-fix"
    resolution_timestamp: "2026-04-02T11:09:00Z"
```

### `metadata`

Written once during orchestrator initialization. Never modified by phase skills.

| Field | Type | Description |
|-------|------|-------------|
| `jira_key` | string | Jira issue key (e.g., `"OCPSTRAT-1612"`) |
| `jira_url` | string | Full Jira issue URL |
| `feature_summary` | string | Brief summary from Jira |
| `orchestrator_version` | string | SDLC plugin version (e.g., `"0.1.0"`) |
| `initiated_at` | string | ISO 8601 timestamp of when orchestration started |
| `initiated_by` | string | Username or email of user who started orchestration |
| `mode` | string | `"interactive"` or `"automation"` (based on `--ci` flag) |
| `remote` | string | Git remote name (e.g., `"origin"`) |

### `current_phase`

Updated by the orchestrator when transitioning between phases.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Current phase name |
| `status` | string | Current phase status (see status values below) |
| `started_at` | string | ISO 8601 timestamp when current phase started |
| `last_updated` | string | ISO 8601 timestamp of last state update |

**Status values:**

| Status | Meaning |
|--------|---------|
| `"pending"` | Phase has not started yet |
| `"in_progress"` | Phase is currently executing |
| `"completed"` | Phase finished successfully |
| `"failed"` | Phase encountered a failure |
| `"blocked"` | Phase is blocked waiting for external action |

### `phases.{phase_name}`

Each phase has its own section with status, timestamps, outputs, and verification gates.

**Common fields for all phases:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Phase status (pending, in_progress, completed, failed, blocked) |
| `started_at` | string | ISO 8601 timestamp when phase started |
| `completed_at` | string | ISO 8601 timestamp when phase completed |
| `outputs` | object | Phase-specific outputs (see below) |
| `verification_gates` | array | Verification gates with status and timestamps |

### `phases.enhancement.outputs`

| Field | Type | Description |
|-------|------|-------------|
| `enhancement_doc_path` | string | Path to generated enhancement document |
| `jira_key` | string | Jira issue key |
| `feature_summary` | string | Feature summary from Jira |

### `phases.design.outputs`

| Field | Type | Description |
|-------|------|-------------|
| `spec_path` | string | Path to implementation specification |
| `estimated_complexity` | string | Complexity estimate (low, medium, high) |
| `files_to_modify` | array of strings | List of files identified for modification |

### `phases.implementation.outputs`

| Field | Type | Description |
|-------|------|-------------|
| `branch_name` | string | Git feature branch name |
| `remote` | string | Git remote name |
| `commits` | array | List of commits (see below) |
| `files_changed` | int | Number of files modified |
| `test_files_added` | int | Number of test files added |
| `verification_results` | object | Results of make commands |

**`commits[]` structure:**

```yaml
commits:
  - sha: "abc123def456"
    message: "feat(api): Add subnet configuration fields"
    timestamp: "2026-04-02T11:10:00Z"
```

### `phases.testing.outputs`

| Field | Type | Description |
|-------|------|-------------|
| `test_results` | string | Overall test result (passed, failed) |
| `tests_run` | int | Total number of tests run |
| `tests_passed` | int | Number of tests passed |
| `coverage_percentage` | float | Test coverage percentage |
| `new_failures` | array | List of new test failures |
| `preexisting_failures` | array | List of pre-existing test failures |

### `phases.pr_review.outputs`

| Field | Type | Description |
|-------|------|-------------|
| `pr_url` | string | GitHub PR URL |
| `pr_number` | int | PR number |
| `pr_state` | string | PR state (open, draft, closed) |
| `ci_status` | string | CI status (passing, failing, pending) |
| `created_at` | string | ISO 8601 timestamp of PR creation |

### `phases.merge.outputs`

| Field | Type | Description |
|-------|------|-------------|
| `merge_sha` | string | Merge commit SHA |
| `merge_timestamp` | string | ISO 8601 timestamp of merge |
| `merged_by` | string | Username who merged the PR |
| `first_payload` | string | First payload containing the merge commit |
| `payload_status` | string | Payload status (accepted, rejected, pending) |

### `phases.completion.outputs`

| Field | Type | Description |
|-------|------|-------------|
| `jira_updated` | bool | Whether Jira was successfully updated |
| `completion_timestamp` | string | ISO 8601 timestamp of completion |
| `final_status` | string | Final status (success, partial, failed) |
| `completion_report_path` | string | Path to completion report |

### `resumability`

Tracks whether orchestration can be resumed.

| Field | Type | Description |
|-------|------|-------------|
| `can_resume` | bool | Whether resumption is possible |
| `resume_from_phase` | string | Phase to resume from |
| `blocking_issues` | array of strings | Issues preventing resumption |
| `manual_intervention_required` | bool | Whether manual action is needed |

### `errors[]`

Record of errors encountered during orchestration.

| Field | Type | Description |
|-------|------|-------------|
| `phase` | string | Phase where error occurred |
| `timestamp` | string | ISO 8601 timestamp of error |
| `error_type` | string | Type of error |
| `message` | string | Error message |
| `resolved` | bool | Whether error was resolved |
| `resolution` | string | How error was resolved (if resolved) |
| `resolution_timestamp` | string | When error was resolved (if resolved) |

## Operations

### Create (used by orchestrator initialization)

Create a new state file when starting orchestration:

1. Create directory: `.work/sdlc/{jira-key}/`
2. Write `sdlc-state.yaml` with:
   - `metadata` populated from orchestrator arguments and Jira data
   - All `phases` set to `status: "pending"` with empty `outputs`
   - `current_phase` set to `enhancement` with `status: "pending"`
   - `resumability.can_resume: true`
   - `errors: []`

### Read (used at start of each phase)

Load the state file to determine context:

1. Read `.work/sdlc/{jira-key}/sdlc-state.yaml`
2. Validate `schema_version` is compatible (currently `"1.0"`)
3. Return state object for access to:
   - `metadata` (jira_key, jira_url, mode, remote)
   - `current_phase` (name, status)
   - Previous phase `outputs` (for dependencies)
   - `resumability` (can_resume, blocking_issues)

### Update Phase Start (used when starting a phase)

Update state when beginning a phase:

1. Read existing state
2. Update `current_phase`:
   - `name`: Set to phase name
   - `status`: Set to `"in_progress"`
   - `started_at`: Set to current timestamp
   - `last_updated`: Set to current timestamp
3. Update `phases.{phase_name}`:
   - `status`: Set to `"in_progress"`
   - `started_at`: Set to current timestamp
4. Write state file

### Update Phase Progress (used during phase execution)

Update state during phase execution:

1. Read existing state
2. Update `current_phase.last_updated` to current timestamp
3. Update `phases.{phase_name}.outputs` with new data
4. Update `phases.{phase_name}.verification_gates` with gate status
5. Append to `errors` array if errors occurred
6. Write state file

### Update Phase Complete (used when finishing a phase)

Update state when completing a phase:

1. Read existing state
2. Update `phases.{phase_name}`:
   - `status`: Set to `"completed"`
   - `completed_at`: Set to current timestamp
3. Update `resumability`:
   - `resume_from_phase`: Set to next phase name
4. Write state file

### Update Phase Failed (used when phase fails)

Update state when a phase fails:

1. Read existing state
2. Update `phases.{phase_name}.status` to `"failed"`
3. Update `current_phase.status` to `"failed"`
4. Append error to `errors` array with full details
5. Update `resumability`:
   - `can_resume`: Set based on whether failure is recoverable
   - `blocking_issues`: Add description of failure
   - `manual_intervention_required`: Set to `true` if user action needed
6. Write state file

### Resume Detection (used by orchestrator with `--resume`)

Determine where to resume orchestration:

1. Read state file
2. Check `resumability.can_resume`:
   - If `false`: Exit with error explaining blocking issues
   - If `true`: Continue
3. Find the first phase where `status` is `"in_progress"` or `"failed"`
4. If no such phase found (all completed): Check if `completion.status == "completed"`
   - If yes: Orchestration already complete
   - If no: Resume from `completion` phase
5. Return phase name to resume from

### Validate State (used when loading state)

Validate state file integrity:

1. Check file exists
2. Parse YAML
3. Validate required fields:
   - `schema_version` exists and is `"1.0"`
   - `metadata` contains all required fields
   - `current_phase` exists
   - All 7 phases exist in `phases`
4. Return validation result (valid/invalid with errors)

## Usage Examples

### Example: Initialize State

```yaml
# Orchestrator creates new state at start
schema_version: "1.0"
metadata:
  jira_key: "OCPSTRAT-1612"
  jira_url: "https://redhat.atlassian.net/browse/OCPSTRAT-1612"
  feature_summary: "Configure OVN Subnets"
  orchestrator_version: "0.1.0"
  initiated_at: "2026-04-02T10:30:00Z"
  initiated_by: "developer@redhat.com"
  mode: "interactive"
  remote: "origin"
current_phase:
  name: "enhancement"
  status: "pending"
  started_at: ""
  last_updated: "2026-04-02T10:30:00Z"
phases:
  enhancement: {status: "pending"}
  design: {status: "pending"}
  implementation: {status: "pending"}
  testing: {status: "pending"}
  pr_review: {status: "pending"}
  merge: {status: "pending"}
  completion: {status: "pending"}
resumability:
  can_resume: true
  resume_from_phase: "enhancement"
  blocking_issues: []
  manual_intervention_required: false
errors: []
```

### Example: Update During Implementation Phase

```yaml
# Implementation phase updates outputs and verification gates
phases:
  implementation:
    status: "in_progress"
    started_at: "2026-04-02T11:00:00Z"
    outputs:
      branch_name: "fix-OCPSTRAT-1612"
      remote: "origin"
      commits:
        - sha: "abc123"
          message: "feat(api): Add subnet configuration"
          timestamp: "2026-04-02T11:10:00Z"
      files_changed: 5
      test_files_added: 2
      verification_results:
        make_lint_fix: "passed"
        make_verify: "in_progress"
        make_test: "pending"
    verification_gates:
      - gate: "make_lint_fix"
        status: "passed"
        timestamp: "2026-04-02T11:08:00Z"
      - gate: "make_verify"
        status: "in_progress"
```

## See Also

- Related Command: `/sdlc:orchestrate` — main orchestrator command
- Related Skills: All `phase-*` skills use this state schema
