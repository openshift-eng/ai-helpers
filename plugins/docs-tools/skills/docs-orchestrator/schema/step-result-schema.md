# Step Result Sidecar Schema

Workflow steps write a `step-result.json` file alongside their primary output. The orchestrator and downstream scripts use this sidecar to read structured metadata without parsing markdown.

## Common fields

All sidecars share these fields:

```json
{
  "schema_version": 1,
  "step": "<step-name>",
  "ticket": "<TICKET>",
  "completed_at": "<ISO 8601>"
}
```

| Field | Type | Description |
|---|---|---|
| `schema_version` | integer | Always `1`. Bump when the schema changes incompatibly |
| `step` | string | Step name matching the YAML step list (e.g., `"requirements"`) |
| `ticket` | string | JIRA ticket ID as provided by the user (preserves original case) |
| `completed_at` | string | ISO 8601 timestamp of when the step finished |

## Per-step extensions

### requirements

```json
{
  "schema_version": 1,
  "step": "requirements",
  "ticket": "PROJ-123",
  "completed_at": "2026-04-23T14:30:00Z",
  "title": "Add installation guide for the Operator"
}
```

| Field | Type | Description | Consumed by |
|---|---|---|---|
| `title` | string | First heading from requirements.md (max 80 chars, ticket prefix stripped) | `create_merge_request.sh` — PR/MR title |

### scope-req-audit

```json
{
  "schema_version": 1,
  "step": "scope-req-audit",
  "ticket": "PROJ-123",
  "completed_at": "2026-04-23T14:35:00Z",
  "recommendation": "proceed",
  "grounded": 8,
  "partial": 2,
  "absent": 1,
  "total": 11,
  "discovered_repos_count": 2,
  "secondary_repos_count": 1
}
```

| Field | Type | Description | Consumed by |
|---|---|---|---|
| `recommendation` | string | `"proceed"`, `"gather-more"`, or `"review-needed"` | Orchestrator — post-step logging |
| `grounded` | integer | Count of grounded requirements | Orchestrator — post-step logging |
| `partial` | integer | Count of partial requirements | Orchestrator — post-step logging |
| `absent` | integer | Count of absent requirements | Orchestrator — post-step logging |
| `total` | integer | Total requirements classified | Orchestrator — post-step logging |
| `discovered_repos_count` | integer | Count of repos found in README/docs | Orchestrator — post-step logging |
| `secondary_repos_count` | integer | Count of repos from gap classification actions | Orchestrator — post-step logging |

### planning

```json
{
  "schema_version": 1,
  "step": "planning",
  "ticket": "PROJ-123",
  "completed_at": "2026-04-23T14:45:00Z",
  "module_count": 5
}
```

| Field | Type | Description | Consumed by |
|---|---|---|---|
| `module_count` | integer | Number of documentation modules in the plan | Informational (orchestrator summary) |

### code-analysis

```json
{
  "schema_version": 1,
  "step": "code-analysis",
  "ticket": "PROJ-123",
  "completed_at": "2026-04-23T14:40:00Z",
  "module_count": 12,
  "relationship_count": 8,
  "languages_detected": ["go", "python"],
  "repo_path": "/home/user/docs-repo/.agent_workspace/proj-123/code-repo/my-project"
}
```

| Field | Type | Description | Consumed by |
|---|---|---|---|
| `module_count` | integer | Number of modules analyzed by learn-code | Informational (orchestrator summary) |
| `relationship_count` | integer | Number of cross-module relationships discovered | Informational (orchestrator summary) |
| `languages_detected` | string[] | Programming languages found in the repo | Informational |
| `repo_path` | string | Absolute path to the analyzed source repository | Informational |

### pr-analysis

```json
{
  "schema_version": 1,
  "step": "pr-analysis",
  "ticket": "PROJ-123",
  "completed_at": "2026-04-23T14:50:00Z",
  "pr_number": 42,
  "pr_url": "https://github.com/org/repo/pull/42",
  "modules_affected": 3,
  "platform": "github"
}
```

| Field | Type | Description | Consumed by |
|---|---|---|---|
| `pr_number` | integer | PR/MR number | Informational |
| `pr_url` | string | Full URL to the PR/MR | Informational |
| `modules_affected` | integer | Number of modules with changes in the PR | Informational (orchestrator summary) |
| `platform` | string | `"github"` or `"gitlab"` | Informational |

### writing

```json
{
  "schema_version": 1,
  "step": "writing",
  "ticket": "PROJ-123",
  "completed_at": "2026-04-23T15:10:00Z",
  "files": [
    "/home/user/docs-repo/modules/proc-installing-operator.adoc",
    "/home/user/docs-repo/modules/con-operator-overview.adoc",
    "/home/user/docs-repo/assemblies/assembly-operator-guide.adoc"
  ],
  "mode": "update-in-place",
  "format": "adoc"
}
```

| Field | Type | Description | Consumed by |
|---|---|---|---|
| `files` | string[] | Absolute paths of all files written or modified | `create_merge_request.sh` — file staging |
| `mode` | string | `"update-in-place"`, `"draft"`, or `"fix"` | Informational |
| `format` | string | `"adoc"` or `"mkdocs"` | Informational |

### technical-review

```json
{
  "schema_version": 1,
  "step": "technical-review",
  "ticket": "PROJ-123",
  "completed_at": "2026-04-23T15:30:00Z",
  "confidence": "HIGH",
  "severity_counts": {
    "critical": 0,
    "significant": 0,
    "minor": 1,
    "sme": 2
  },
  "iteration": 1,
  "code_grounded": true,
  "has_issues_json": true,
  "fixable_count": 3,
  "verification_summary": ".agent_workspace/proj-123/technical-review/verification/verification-summary.json"
}
```

| Field | Type | Description | Consumed by |
|---|---|---|---|
| `confidence` | string | `"HIGH"`, `"MEDIUM"`, or `"LOW"`. After the fix-verify cycle, this is the FINAL computed confidence — not re-derived from a full review | Orchestrator — iteration logic |
| `severity_counts` | object | Issue counts by severity level. After the fix-verify cycle, counts reflect UNRESOLVED issues only (original counts minus accepted fixes) | Orchestrator — iteration logic |
| `severity_counts.critical` | integer | Unresolved critical issues | Orchestrator |
| `severity_counts.significant` | integer | Unresolved significant issues | Orchestrator |
| `severity_counts.minor` | integer | Unresolved minor issues | Orchestrator |
| `severity_counts.sme` | integer | Issues requiring SME verification | Orchestrator |
| `iteration` | integer | Number of fix-verify cycles completed (1 = initial review only, 2 = one fix cycle, etc.) | Orchestrator |
| `code_grounded` | boolean | Whether code-learner analysis was available for claim validation (code-analysis step completed) | Informational |
| `has_issues_json` | boolean | Whether `issues.json` was produced alongside `review.md` | Orchestrator — iteration logic |
| `fixable_count` | integer | Count of issues where `fixable` is `true` in `issues.json` | Orchestrator — iteration logic |
| `verification_summary` | string or null | Path to `verification-summary.json`. Null if the fix-verify cycle was not run (e.g., initial confidence was HIGH) | Orchestrator — iteration logic |

### style-review

```json
{
  "schema_version": 1,
  "step": "style-review",
  "ticket": "PROJ-123",
  "completed_at": "2026-04-23T15:45:00Z"
}
```

No extra fields. Common schema only.

### create-merge-request

```json
{
  "schema_version": 1,
  "step": "create-merge-request",
  "ticket": "PROJ-123",
  "completed_at": "2026-04-23T16:05:00Z",
  "commit_sha": "abc1234",
  "branch": "proj-123",
  "pushed": true,
  "url": "https://github.com/org/repo/pull/42",
  "action": "created",
  "platform": "github",
  "skipped": false,
  "skip_reason": null
}
```

When skipped (draft mode, no changes, or user declined):

```json
{
  "schema_version": 1,
  "step": "create-merge-request",
  "ticket": "PROJ-123",
  "completed_at": "2026-04-23T16:05:00Z",
  "commit_sha": null,
  "branch": null,
  "pushed": false,
  "url": null,
  "action": "skipped",
  "platform": "unknown",
  "skipped": true,
  "skip_reason": "draft"
}
```

| Field | Type | Description | Consumed by |
|---|---|---|---|
| `commit_sha` | string\|null | Git commit SHA (null when skipped) | Informational |
| `branch` | string\|null | Branch name committed to (null when skipped) | Orchestrator |
| `pushed` | boolean | Whether the branch was pushed to the remote | Orchestrator |
| `url` | string\|null | MR/PR URL (null when skipped or not pushed) | Orchestrator (final summary) |
| `action` | string | `"created"`, `"found_existing"`, or `"skipped"` | Orchestrator |
| `platform` | string | `"github"`, `"gitlab"`, or `"unknown"` | Informational |
| `skipped` | boolean | Whether the step was skipped | Orchestrator |
| `skip_reason` | string\|null | `"draft"`, `"no_changes"`, `"no_files"`, `"user_declined"`, `"on_default_branch"`, `"push_failed"`, `"commit_failed"`, `"create_failed"`, or `"unknown_platform"` when skipped | Orchestrator |

### create-jira

```json
{
  "schema_version": 1,
  "step": "create-jira",
  "ticket": "PROJ-123",
  "completed_at": "2026-04-23T16:10:00Z",
  "jira_url": "https://redhat.atlassian.net/browse/DOCS-456",
  "jira_key": "DOCS-456",
  "action": "created",
  "skipped": false,
  "skip_reason": null
}
```

When an existing linked ticket is found:

```json
{
  "schema_version": 1,
  "step": "create-jira",
  "ticket": "PROJ-123",
  "completed_at": "2026-04-23T16:10:00Z",
  "jira_url": "https://redhat.atlassian.net/browse/DOCS-456",
  "jira_key": "DOCS-456",
  "action": "found_existing",
  "skipped": false,
  "skip_reason": null
}
```

| Field | Type | Description | Consumed by |
|---|---|---|---|
| `jira_url` | string\|null | URL of the created or found JIRA ticket (null on failure) | Orchestrator (final summary) |
| `jira_key` | string\|null | JIRA issue key (e.g., `DOCS-456`) | Orchestrator |
| `action` | string | `"created"`, `"found_existing"`, or `"skipped"` | Orchestrator |
| `skipped` | boolean | Whether JIRA creation was skipped | Orchestrator |
| `skip_reason` | string\|null | Reason when skipped (e.g., `"existing_link"`) | Orchestrator |

## Backward compatibility

Downstream consumers use a sidecar-first pattern: read from `step-result.json` when present, fall back to parsing the markdown output when absent. This ensures in-flight workflows from before sidecar adoption continue to work.
