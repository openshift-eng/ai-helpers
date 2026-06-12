---
description: Check if a bug already exists in Jira before creating a new one
argument-hint: "<description-or-issue-key> [project] [--component name] [--include-closed] [--link issue-key] [--verbose]"
---

## Name
jira:check-bug-exists

## Synopsis
```
/jira:check-bug-exists <description-or-issue-key> [project] [--component name] [--include-closed] [--link issue-key] [--verbose]
```

## Description
The `jira:check-bug-exists` command searches Jira for existing bugs that match a given description or issue, helping avoid duplicate bug creation. It extracts keywords from the input, runs multiple JQL queries for broad coverage, and uses AI analysis to rank matches by confidence.

This command is useful for:
- Checking whether a bug already exists before filing a new one
- Finding related bugs when triaging a reported issue
- Linking duplicate bugs together

## Implementation

Delegates to the `check-bug-exists` skill. See [skills/check-bug-exists/SKILL.md](../skills/check-bug-exists/SKILL.md) for the full implementation guide.

## Usage Examples

1. **Free-text search**:
   ```
   /jira:check-bug-exists "etcd pod OOMKilled after 24 hours" OCPBUGS
   ```

2. **Search from existing issue**:
   ```
   /jira:check-bug-exists OCPBUGS-54321
   ```

3. **Filter by component**:
   ```
   /jira:check-bug-exists "API server 500 error" OCPBUGS --component "kube-apiserver"
   ```

4. **Include closed bugs (regression check)**:
   ```
   /jira:check-bug-exists "memory leak in ingress" OCPBUGS --include-closed
   ```

5. **Search and link as duplicate**:
   ```
   /jira:check-bug-exists OCPBUGS-99999 --link OCPBUGS-99999
   ```

## Arguments

- **$1 — description-or-issue-key** *(required)*
  Either a free-text description of the bug or an existing Jira issue key.
  - Free text: `"etcd pod OOMKilled after 24 hours"`
  - Issue key: `OCPBUGS-54321` (fetches its details to use as search terms)

- **$2 — project** *(optional)*
  Jira project key to search within (e.g., `OCPBUGS`). If omitted and an issue key is provided, the project is inferred from the key prefix.

- **--component** *(optional)*
  Filter results by Jira component name.
  Example: `--component "HyperShift"`

- **--include-closed** *(optional)*
  Include Closed/Done issues in search results. Useful for checking if a bug was previously fixed and may have regressed. Default: excluded.

- **--link** *(optional)*
  After finding duplicates, link the specified issue as a duplicate of the best high-confidence match. Requires user confirmation before linking.
  Example: `--link OCPBUGS-99999`

- **--verbose** *(optional)*
  Include low-confidence matches in the report output.

## Return Value
- **Markdown Report**: Ranked list of potential duplicate bugs with confidence levels and a verdict (existing bug found / no matches / review recommended)

## See Also
- `jira:create` — Create Jira issues (check for duplicates first with this command)
- `jira:grooming` — Grooming agenda with related issue detection
