## Phase 4: Validate

**Model note (optional):** Prefer a stronger model for this security-critical phase when the host allows model selection; otherwise continue with the current model.

Validate all parsed issue(s) before creation. Run all validation checks in parallel for each issue, then aggregate results. If any issue fails validation, BLOCK creation for that issue and report all failures.

### Security Validation (CRITICAL)

**Priority:** Run FIRST — credentials detected = immediate BLOCK, no creation.

Scan **all text fields** that will be sent to Jira (summary, description, acceptance criteria, steps to reproduce, expected behavior, actual behavior, user story, environment, technical notes, testing notes) for exposed credentials and secrets:

**Credential patterns to detect:**

- **AWS credentials:** Access keys (`AKIA[0-9A-Z]{16}`, `ASIA[0-9A-Z]{16}`), secret keys (base64url, ~40 chars, near `aws_secret`/`AWS_SECRET`), session tokens (`FwoGZXIvYXdzE`-prefixed)
- **API tokens:** Bearer tokens, OAuth tokens, JWT tokens (three base64url segments separated by `.`)
- **GCP service accounts:** JSON with `"private_key"`, `"client_email"`, `"type": "service_account"`
- **Azure secrets:** Storage account keys (base64, 88 chars), SAS tokens (`sig=`), client secrets
- **Private keys:** PEM header lines of the form `BEGIN <TYPE> PRIVATE KEY` (RSA, EC, OpenSSH, PKCS8, PGP variants)
- **Kubeconfigs:** YAML with `clusters:`, `users:`, `certificate-authority-data:`, client certificates
- **Database credentials:** Connection strings with embedded passwords (PostgreSQL, MySQL, MongoDB URIs)
- **Generic secrets:** High-entropy strings (>20 chars) near keywords `password`, `secret`, `token`, `key`
- **URLs with credentials:** `https://user:pass@host`, URLs with `token=` or `key=` query parameters

**Action on detection:**

```plaintext
BLOCKED: Credentials detected in issue content

Found: <credential-type> (e.g., "AWS access key", "kubeconfig", "API token")
Location: <field-name> (e.g., "description", "acceptance criteria")

DO NOT create this issue. Credentials must never be stored in Jira.

Next steps:
1. Remove or redact the credential from the markdown file
2. Use placeholders: YOUR_API_KEY, YOUR_AWS_ACCESS_KEY, <REDACTED>
3. Re-run /jira:create-jira-from-file after sanitizing content
```

**CRITICAL:** Do NOT echo the actual credential value in the error message. Only report the credential type and location.

### Summary Validation

Check each issue's summary for common anti-patterns:

**Anti-pattern 1: User story in summary**

If summary contains:
- Starts with "As a" / "As an"
- Contains "I want" or "so that"
- Longer than 100 characters

```plaintext
Summary looks like a full user story. Summaries should be concise titles (≤100 chars).

Current: "As a cluster admin, I want to configure autoscaling so that I can handle traffic spikes"

Suggested: "Enable autoscaling configuration for clusters"

Fix automatically? (yes/no/edit)
```

**Anti-pattern 2: Overly long summary**

If summary exceeds 100 characters but doesn't match user story pattern:

```plaintext
Summary is too long (125 chars). Consider shortening to ≤100 chars.

Current: "<summary-text>"

Options:
1. Auto-truncate to 100 chars
2. Manually edit summary
3. Proceed anyway (not recommended)
```

**Anti-pattern 3: Missing action verb (for tasks)**

If type is Task and summary lacks an action verb (Configure, Update, Implement, Refactor, Document, etc.):

```plaintext
Task summaries should start with an action verb.

Current: "API documentation"

Suggested: "Update API documentation"

Apply suggestion? (yes/no/edit)
```

**Action on detection:**

- Offer automatic fix (extract concise title from user story, truncate long summaries)
- Allow user to edit manually
- Allow proceeding anyway (for edge cases)
- Update the parsed issue object with corrected summary if user accepts

### Required Field Validation

Verify presence of mandatory fields for each issue:

**Required fields:**

- `project` — Project key (e.g., PLATFORM, OCPBUGS, CNTRLPLANE)
- `type` — Issue type (Story, Bug, Epic, Task, Feature, Initiative, Sub-task)

**Validation logic:**

```python
if not issue.project:
    error(f"Issue '{issue.summary}' missing required field: Project")
    prompt_user("Enter project key (e.g., PLATFORM, OCPBUGS): ")

if not issue.type:
    # Attempt auto-detection from summary/content patterns
    detected_type = auto_detect_type(issue)
    if detected_type:
        confirm(f"Auto-detected type: {detected_type}. Use this? (yes/no)")
    else:
        prompt_user("Enter issue type (Story/Bug/Epic/Task/Feature/Initiative/Sub-task): ")
```

**Auto-detection heuristics for type:**

- Contains "bug", "error", "crash", "broken" → Bug
- Contains "epic:", "theme:", or has child issues → Epic
- Contains "story:", "as a", acceptance criteria → Story
- Contains "task:", action verbs (configure, update, refactor) → Task
- Contains "feature:", strategic language → Feature
- Contains "initiative:", portfolio/strategic language → Initiative
- Contains "sub-task:" → Sub-task
- **Do NOT** treat `**Parent:**` alone as Sub-task — Stories, Tasks, and Epics can also have parents

**Action on missing fields:**

- Attempt auto-detection first
- If auto-detection fails or user rejects, prompt interactively
- If in batch mode, collect all missing fields across issues before prompting (single prompt session)

### Parent Hierarchy Validation (if parent specified)

**Only run if** `parent_key` field is present in the parsed issue.

Skip hierarchy fetch for in-batch parent references that are not yet real Jira keys (resolve those after the parent is created in Phase 5). For pre-existing keys, validate now.

**Step 1: Fetch parent issue**

Use `getJiraIssue` to retrieve parent metadata:

```json
{
  "issueKey": "<parent-key>"
}
```

**Step 2: Handle fetch errors**

| Error | Action |
|-------|--------|
| Parent not found (404) | Offer options: (1) Proceed without parent, (2) Specify different parent, (3) Cancel creation |
| Permission denied (403) | Warn user, suggest verifying parent key, offer same options as 404 |
| Network/API error (5xx) | Retry once, then offer to proceed without parent or cancel |

**Step 3: Validate hierarchy level**

If parent exists, check that its `hierarchyLevel` is exactly one level above the child:

| Creating (Child) | Required Parent Level | Parent Type Examples |
|------------------|-----------------------|----------------------|
| Story (level 0) | Level 1 | Epic |
| Task (level 0) | Level 1 | Epic |
| Bug (level 0) | Level 1 | Epic |
| Epic (level 1) | Level 2 | Feature, Initiative |
| Feature (level 2) | Level 3 | Outcome |
| Initiative (level 2) | Level 3 | Outcome |
| Sub-task (level -1) | Level 0 | Story, Task, Bug |

**Validation logic:**

```python
child_level = get_hierarchy_level(issue.type)  # From project metadata
parent_level = parent_issue.fields.issuetype.hierarchyLevel

if parent_level != child_level + 1:
    expected_types = get_types_at_level(child_level + 1, project)
    error(f"Invalid parent: {issue.type} (level {child_level}) cannot have parent {parent_issue.fields.issuetype.name} (level {parent_level})")
    error(f"Expected parent types: {', '.join(expected_types)}")
    prompt_user("Options: (1) Remove parent link, (2) Specify different parent, (3) Cancel")
```

**Step 4: Cross-project validation**

Ensure parent and child are in the same project:

```python
if parent_issue.fields.project.key != issue.project:
    error(f"Parent {issue.parent_key} is in project {parent_issue.fields.project.key}, but child will be created in {issue.project}")
    error("Parent and child must be in the same project")
    prompt_user("Options: (1) Remove parent, (2) Change child project to match parent, (3) Cancel")
```

### Component/Version Validation

**Optional fields** — validate if specified; report the error and offer alternatives if invalid, then continue without the field.

**Component validation:**

If `component` specified, verify it exists in the project:

```python
project_meta = getJiraProjectIssueTypesMetadata(issue.project)
valid_components = [c["name"] for c in project_meta.get("components", [])]

if issue.component not in valid_components:
    warning(f"Component '{issue.component}' not found in project {issue.project}")
    suggest_closest_match(issue.component, valid_components)  # Fuzzy match
    prompt_user("Options: (1) Use suggested component, (2) Remove component, (3) Manually specify")
```

**Version validation:**

If `version` specified, verify it exists:

```python
valid_versions = get_project_versions(issue.project)

if issue.version not in valid_versions:
    warning(f"Version '{issue.version}' not found in project {issue.project}")
    suggest_closest_match(issue.version, valid_versions)  # e.g., "4.21" → "openshift-4.21"
    prompt_user("Options: (1) Use suggested version, (2) Remove version, (3) List all versions")
```

**Action on validation failure:**

- Suggest closest match (Levenshtein distance, case-insensitive)
- Allow user to remove the field (proceed without component/version)
- Provide option to list all valid values and manually select

### Validation Result Aggregation

After running all validation checks:

**If all validations pass:**

```plaintext
✓ All validations passed (N issue(s))
  - Security: No credentials detected
  - Required fields: Present
  - Summary: Valid
  - Parent hierarchy: Valid (if applicable)
  - Component/version: Valid (if specified)

Proceeding to Phase 5 (Create Issues)...
```

**If any validation fails:**

```plaintext
✗ Validation failed for M of N issue(s):

Issue 1: "Enable autoscaling"
  ✗ Summary anti-pattern: User story in summary (auto-fix available)
  ✓ Required fields: Present
  ✓ Security: No credentials

Issue 2: "Fix API crash"
  ✗ BLOCKED: AWS access key detected in description
  ✓ Required fields: Present

Cannot proceed. Fix issues above and re-run.
```

**CRITICAL:** If any issue has a BLOCKED status (credentials detected), do NOT create ANY issues, even those that passed validation. Security failures block the entire batch.

**Partial success option (non-security failures):**

If failures are non-security (missing fields, invalid component, etc.), offer to create only the passing issues:

```plaintext
3 of 5 issues passed validation. Create the valid issues? (yes/no)

Valid issues:
  - "Enable autoscaling" (PLATFORM-TBD)
  - "Add user dashboard" (FRONTEND-TBD)
  - "Update API docs" (BACKEND-TBD)

Failed issues (skipped):
  - "Fix API crash" (missing Project field)
  - "Implement search" (invalid component "Serch")
```
