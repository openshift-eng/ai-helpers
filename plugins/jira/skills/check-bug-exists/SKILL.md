---
name: check-bug-exists
description: Search for potential duplicate Jira bugs before creating new ones — matches by summary, description keywords, and component
command: /jira:check-bug-exists
---

# Check Bug Exists

This skill searches Jira for existing bugs that match a given description, helping avoid duplicate bug creation.

## When to Use This Skill

- Before creating a new bug, to check whether one already exists
- When triaging a reported issue and wanting to find related existing bugs
- Automatically invoked by `/jira:check-bug-exists`

## Prerequisites

- MCP Jira server configured and accessible
- User has permissions to search issues in the target project

## Implementation Steps

### Phase 1: Parse Input

Accept the user's input in one of these forms:

1. **Free-text description** — A summary or description of the bug (e.g., `"etcd pod OOMKilled after 24 hours"`)
2. **Existing issue key** — A Jira issue key (e.g., `OCPBUGS-12345`). Fetch the issue via `getJiraIssue` and extract its `summary`, `description`, and `components` to use as search terms.

Also accept optional filters:
- **Project** — Target project key (e.g., `OCPBUGS`). If not provided, infer from the issue key prefix or ask the user.
- **`--component`** — Filter by Jira component name
- **`--include-closed`** — Include Closed/Done issues in results (excluded by default)
- **`--link <issue-key>`** — After finding duplicates, link the specified issue as a duplicate of the best match
- **`--verbose`** — Include low-confidence matches in the report

### Phase 2: Extract Search Terms

From the input (free text or fetched issue), extract meaningful search terms:

1. Identify 3-5 significant keywords — prioritize:
   - Error messages and codes (e.g., `OOMKilled`, `SIGSEGV`, `500 error`)
   - Component or feature names (e.g., `etcd`, `kube-apiserver`, `ingress`)
   - Technical terms (e.g., `memory leak`, `crash loop`, `timeout`)
   - Version references (e.g., `4.21`, `upgrade`)
2. Strip common stop words (the, is, a, when, after, etc.)
3. Preserve quoted phrases as exact-match terms

If the input is too vague (fewer than 2 meaningful keywords), ask the user for more detail before proceeding.

### Phase 3: Build and Execute JQL Queries

Construct multiple JQL queries to maximize coverage. Run each via `searchJiraIssuesUsingJql` with `maxResults: 20`.

**Query 1 — Summary text match:**
```jql
project = {PROJECT} AND type = Bug AND summary ~ "{keyword1} {keyword2} {keyword3}"
ORDER BY updated DESC
```

**Query 2 — Full text match (broader):**
```jql
project = {PROJECT} AND type = Bug AND text ~ "{keyword1} {keyword2}"
ORDER BY updated DESC
```

**Query 3 — Component-scoped (if component known):**
```jql
project = {PROJECT} AND type = Bug AND component = "{component}" AND summary ~ "{keyword1}"
ORDER BY updated DESC
```

**Status filter:** Unless `--include-closed` is set, append:
```jql
AND status NOT IN (Closed, Done, "Won't Fix", "Won't Do", Obsolete)
```

**Fields to fetch:** `summary, status, priority, assignee, reporter, created, updated, description, components, labels, resolution`

**Deduplication:** Merge results from all queries, deduplicate by issue key. If the input was an issue key, exclude that issue from results.

### Phase 4: AI Similarity Analysis

For each candidate issue returned, compare it against the original input and assign a confidence level:

**High Confidence** — Likely the same bug:
- Summary describes the same problem with the same component
- Same error messages or failure mode mentioned
- Same component and similar symptoms

**Medium Confidence** — Possibly related:
- Similar component but different failure mode
- Same general area but different symptoms
- Partial keyword overlap with related context

**Low Confidence** — Weak match:
- Only superficial keyword overlap
- Different component, different problem
- Only shared because of common terms

For each match, write a one-sentence reasoning explaining why it matched (e.g., "Both describe OOMKilled on etcd pods during upgrade").

Discard Low confidence matches unless `--verbose` is set.

### Phase 5: Generate Report

Output a structured markdown report:

```markdown
## Bug Existence Check

**Search input**: "{original input or issue summary}"
**Project**: {PROJECT} | **Candidates found**: {total} | **Status filter**: {Open only / All}

### High Confidence ({count})

| Issue | Summary | Status | Components | Reasoning |
|-------|---------|--------|------------|-----------|
| [PROJ-123](link) | Summary text | Open | Component | Why this matches |

### Medium Confidence ({count})

| Issue | Summary | Status | Components | Reasoning |
|-------|---------|--------|------------|-----------|
| [PROJ-456](link) | Summary text | In Progress | Component | Why this matches |

### Verdict

{One of:}
- **Existing bug found** — {PROJ-123} appears to be the same issue. Consider adding your information as a comment on that bug instead of creating a new one.
- **Possibly related bugs found** — Review the medium-confidence matches above to determine if any are the same issue.
- **No matching bugs found** — No existing bugs match this description. Safe to create a new bug.
```

If no candidates were found at all, report:
```markdown
## Bug Existence Check

**Search input**: "{input}" | **Project**: {PROJECT}

### Verdict

**No matching bugs found** — No existing bugs match this description in {PROJECT}. Safe to create a new bug.
```

### Phase 6: Optional Duplicate Linking

Only execute if `--link <issue-key>` was provided AND at least one High confidence match was found.

1. Present the best match to the user and ask for confirmation:
   ```
   Link {issue-key} as a duplicate of {best-match-key} ("{best-match-summary}")?
   ```

2. If confirmed, create the link via `createIssueLink`:
   - `type`: `"Duplicate"`
   - `inwardIssue`: `{best-match-key}` (the original bug)
   - `outwardIssue`: `{issue-key}` (the duplicate being linked)

3. Report the link creation result.

## Error Handling

| Error | Handling |
|-------|----------|
| Issue key not found | "Could not find issue {key}. Verify the issue key is correct." |
| Project not specified and cannot be inferred | Ask the user: "Which Jira project should I search in?" |
| Input too vague | "Please provide more detail — include the component, error message, or specific symptoms." |
| MCP unavailable | "Jira MCP server required. Check plugin README for setup." |
| No search results from any query | Report "No matching bugs found" — this is a valid outcome, not an error |
| Link creation fails | Display error but still show the search results report |
| JQL syntax error | Retry with simplified query (fewer keywords, no special characters) |

## Examples

### Example 1: Free-text search

```bash
/jira:check-bug-exists "etcd pod OOMKilled after 24 hours" OCPBUGS
```

Extracts keywords: `etcd`, `OOMKilled`, `pod`.
Searches OCPBUGS for matching bugs. Reports any existing bugs about etcd OOM issues.

### Example 2: Search from existing issue

```bash
/jira:check-bug-exists OCPBUGS-54321
```

Fetches OCPBUGS-54321's summary and description, extracts keywords, searches for other bugs with similar content (excluding OCPBUGS-54321 itself).

### Example 3: Component-scoped search

```bash
/jira:check-bug-exists "API server returns 500 on namespace creation" OCPBUGS --component "kube-apiserver"
```

Searches within the kube-apiserver component for matching bugs.

### Example 4: Include closed bugs

```bash
/jira:check-bug-exists "memory leak in ingress controller" OCPBUGS --include-closed
```

Also searches Closed/Done bugs — useful to check if this was previously fixed and may have regressed.

### Example 5: Search and link

```bash
/jira:check-bug-exists OCPBUGS-99999 --link OCPBUGS-99999
```

Searches for duplicates of OCPBUGS-99999. If a high-confidence match is found, offers to link OCPBUGS-99999 as a duplicate.

## See Also

- `/jira:create bug` — Create a new bug report (use this skill first to check for duplicates)
- `/jira:grooming` — Grooming agenda that also detects related issues
- `create-bug` skill — Bug creation implementation guide
