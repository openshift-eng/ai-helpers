# Common Jira Issue Validation Logic

**Shared across:** `jira:create`, `jira:create-jira-from-file`, and other Jira creation skills

**Model note (optional):** Prefer a stronger model for this security-critical validation when the host allows model selection; otherwise continue with the current model.

Validate all parsed issue(s) before creation using a **two-pass approach** that separates non-interactive checks from interactive remediation:

1. **Pass 1 — Non-interactive checks (run first, no user prompts):**
   - Security credential scanning (BLOCKS immediately if credentials found)
   - Summary anti-pattern detection
   - Parent hierarchy validation (API fetch, no user input)
   - Component/version existence checks (API lookup, no user input)

2. **Pass 2 — Interactive remediation (single prompt session after all checks complete):**
   - Collect all issues requiring user input across all batch items
   - Present all required inputs together (missing type, missing project, summary fixes, etc.)
   - Do NOT interleave prompts with API calls

This separation ensures that API lookups can proceed without blocking on user input, and that all prompts are batched into one interaction phase. If security credentials are detected in Pass 1, stop immediately — do not proceed to Pass 2.

**Invoking skills must provide:** Issue objects with fields: `summary`, `description`, `project`, `type`, `parent_key` (optional), `component` (optional), `version` (optional), and any extracted content fields.

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
3. Re-run the creation command after sanitizing content
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

**Pass 1 — detect silently (no prompts yet):**

```python
missing = []
for issue in issues:
    if not issue.project:
        missing.append((issue, "project"))
    if not issue.type:
        detected_type = auto_detect_type(issue)
        if detected_type:
            issue.type = detected_type          # apply silently
            issue.type_auto_detected = True
        else:
            missing.append((issue, "type"))
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

**Pass 2 — prompt for everything missing in one session:**

```python
for issue, field in missing:
    if field == "project":
        issue.project = prompt_user(f"Issue '{issue.summary}': enter project key (e.g., PLATFORM, OCPBUGS): ")
    elif field == "type":
        issue.type = prompt_user(f"Issue '{issue.summary}': enter type (Story/Bug/Epic/Task/Feature/Initiative/Sub-task): ")

# Confirm auto-detected types together
auto_detected = [i for i in issues if getattr(i, "type_auto_detected", False)]
if auto_detected:
    show_user([(i.summary, i.type) for i in auto_detected])
    if not confirm("Use these auto-detected types? (yes/no/edit)"):
        # allow per-issue correction
```

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

**Step 2: Handle fetch errors (Pass 1 — record, do not prompt yet)**

| Error | Record as |
|-------|-----------|
| Parent not found (404) | `issue.parent_validation_error = "not_found"` |
| Permission denied (403) | `issue.parent_validation_error = "permission_denied"` |
| Network/API error (5xx) | Retry once; if still failing: `issue.parent_validation_error = "api_error"` |

**Step 3: Validate hierarchy level (Pass 1)**

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

```python
child_level = get_hierarchy_level(issue.type)
parent_level = parent_issue.fields.issuetype.hierarchyLevel

if parent_level != child_level + 1:
    # Record the mismatch — prompt user in Pass 2
    issue.parent_validation_error = "wrong_level"
    issue.parent_validation_detail = {
        "expected_types": get_types_at_level(child_level + 1, project),
        "actual_parent_type": parent_issue.fields.issuetype.name
    }
```

**Step 4: Cross-project validation (Pass 1)**

```python
if parent_issue.fields.project.key != issue.project:
    issue.parent_validation_error = "cross_project"
    issue.parent_validation_detail = {"parent_project": parent_issue.fields.project.key}
```

**Pass 2 — prompt for parent issues in batch:**

After all API checks complete, present all parent problems together and collect resolutions:
```
Parent validation issues found:
  Issue "Add user dashboard": parent PROJ-100 not found
    → (1) Proceed without parent  (2) Enter different parent key  (3) Skip this issue

  Issue "Update API docs": parent type mismatch (Bug cannot have Epic as parent; expected Feature or Initiative)
    → (1) Remove parent link  (2) Enter different parent key  (3) Skip this issue
```

### Component/Version Validation

**Optional fields** — validate if specified. Record failures in Pass 1; offer alternatives in Pass 2.

**Component validation (Pass 1):**

```python
project_meta = getJiraProjectIssueTypesMetadata(issue.project)
valid_components = [c["name"] for c in project_meta.get("components", [])]

if issue.component not in valid_components:
    issue.component_suggestion = find_closest_match(issue.component, valid_components)
    issue.component_validation_error = True
```

**Pass 2 — present all component/version issues together:**
```
Component/version issues found:
  Issue "Enable autoscaling": component 'Infra' not found in PLATFORM
    Closest match: 'Infrastructure'
    → (1) Use 'Infrastructure'  (2) Remove component  (3) Enter manually
```

**Version validation (Pass 1):**

```python
valid_versions = get_project_versions(issue.project)

if issue.version not in valid_versions:
    issue.version_suggestion = find_closest_match(issue.version, valid_versions)
    issue.version_validation_error = True
```

All version issues are presented together in Pass 2 alongside component issues (see above).

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
