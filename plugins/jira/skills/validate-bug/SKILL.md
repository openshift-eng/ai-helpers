---
name: validate-bug
description: Diagnose and fix jira/invalid-bug on PRs by running the same 7 checks as the jira-lifecycle-plugin
command: /jira:validate-bug
---

# JIRA Bug Validator — Implementation Guide

**IMPORTANT FOR AI**: This is a procedural skill. Execute each phase in order. Do not skip steps. Do not invent field IDs — use only the documented custom field IDs below.

This skill replicates the validation logic of the [jira-lifecycle-plugin](https://github.com/openshift-eng/jira-lifecycle-plugin) (Prow external plugin) that applies the `jira/invalid-bug` label to PRs in OpenShift repositories.

## Custom Field Reference

| Field | Custom Field ID | JQL Name |
|-------|-----------------|----------|
| Target Version | `customfield_10855` | `"Target Version"` |
| Release Note Text | `customfield_10783` | — |
| Release Note Type | `customfield_10785` | — |
| Severity | `customfield_10840` | — |

## The 7 Validation Checks

The jira-lifecycle-plugin runs these checks in order. A bug must pass ALL checks to get `jira/valid-bug`.

| # | Check | What it validates |
|---|-------|-------------------|
| 1 | Bug is open | Status is not "Closed" |
| 2 | Target version matches branch | Bug's Target Version matches the expected version for the PR's base branch |
| 3 | Bug in valid state | Status is one of: NEW, ASSIGNED, POST |
| 4 | Release notes set | Release note text is non-empty and doesn't match the default template, OR release note type is "Release Note Not Required" |
| 5 | Dependent bug states | Each dependent (linked via "Blocks") is in an allowed state |
| 6 | Dependent bug target versions | Each dependent targets an allowed version |
| 7 | Dependents exist | At least one "Blocks" link exists to a bug in the same project |

Checks 5-7 only apply to release branches (`release-4.X`), not `main`/`master`.

## Branch-to-Version Mapping

The plugin config follows a mechanical pattern:

**Target version** (what the bug on the PR's branch must target):
- `release-4.X` → `4.X.z` (prefix match — `4.X.0` also accepted)
- `main` / `master` → `5.0.0` (prefix match — `5.0` also accepted)

**Dependent target version** (what the "Blocks" linked bug must target):
- `release-4.X` → `4.(X+1).0` or `4.(X+1).z`

**Valid states for the bug itself** (all branches):
- `NEW`, `ASSIGNED`, `POST`

**Valid states for dependent bugs** (varies by branch):
- `release-4.22` and newer: `MODIFIED`, `ON_QA`, `VERIFIED`
- `release-4.6` through `release-4.21`: `VERIFIED`, `RELEASE PENDING`, `CLOSED (ERRATA)`, `CLOSED (CURRENT RELEASE)`, `CLOSED (DONE)`, `CLOSED (DONE-ERRATA)`

**Dependent bug checks** (checks 5-7):
- Required for `release-4.X` branches
- NOT required for `main` / `master` (config sets `exclude_defaults: true`)

**Release notes**:
- Required by default (`require_release_notes: true`)
- Default template text (must NOT match this): `"Cause: What actions or circumstances cause this bug to present.\r\nConsequence: What happens when the bug presents.\r\nFix: What was done to fix the bug.\r\nResult: Bug doesn't present anymore."`

## Prerequisites

- `gh` CLI authenticated with GitHub
- Jira MCP server configured (Atlassian Rovo MCP)
- `cloudId`: use `redhat.atlassian.net`

## Detailed Implementation Steps

### Phase 1: Resolve Input

**Parse the argument to determine input type:**

1. **PR URL** — matches `https://github.com/{org}/{repo}/pull/{number}`
   - Extract org, repo, and PR number from the URL
   - Run: `gh pr view {number} --repo {org}/{repo} --json title,baseRefName,state`
   - Extract JIRA key from PR title using regex: first match of `[A-Z]+-[0-9]+` (e.g., `OCPBUGS-85778`)
   - Extract base branch from `baseRefName` (e.g., `release-4.20`, `main`)

2. **PR number** — plain integer
   - Determine repo from current git remote: `gh repo view --json nameWithOwner -q .nameWithOwner`
   - Then same as PR URL flow above

3. **JIRA key** — matches `[A-Z]+-[0-9]+`
   - Require `--branch` argument (no PR context to infer branch)
   - If `--branch` not provided, error: "JIRA key input requires --branch (e.g., --branch release-4.20)"

**Validate the JIRA key project:**
- Must be a bug project: `OCPBUGS`, `DFBUGS`, or `PROJQUAY`
- If not, warn: "Project {PROJECT} is not a bug project. The jira-lifecycle-plugin only validates bugs in OCPBUGS, DFBUGS, and PROJQUAY."

**Compute expected values from branch:**
- Parse branch name to extract version number
- Compute `expected_target_version`, `expected_dependent_versions`, `valid_states`, `dependent_valid_states`, `dependents_required` using the mapping above

### Phase 2: Gather Data

**Fetch the primary bug:**

Use `mcp__atlassian__getJiraIssue`:
- `cloudId`: `redhat.atlassian.net`
- `issueIdOrKey`: the JIRA key
- `fields`: `["summary", "status", "issuetype", "fixVersions", "issuelinks", "customfield_10855", "customfield_10783", "customfield_10785", "customfield_10840", "labels", "components"]`
- `responseContentFormat`: `markdown`

**Extract key data from response:**
- `status.name` — bug status (e.g., "New", "Verified")
- `customfield_10855` — Target Version array (each entry has `.name`)
- `customfield_10783` — Release Note Text (string or ADF doc)
- `customfield_10785` — Release Note Type (object with `.value`)
- `issuelinks` — array of issue links

**Find dependent bugs:**

Filter `issuelinks` for links where:
- Link type name is `"Blocks"` AND direction is `outwardIssue` (this bug blocks the dependent)
- The linked issue's key shares the same project prefix as the original bug (e.g., both are `OCPBUGS-*`)

For each dependent found:
- Record the dependent's key, status, and priority from the link data
- If the link data doesn't include Target Version, fetch the dependent with `getJiraIssue`:
  - `fields`: `["summary", "status", "customfield_10855", "fixVersions"]`

### Phase 3: Validate

Run each check and record the result:

```text
results = []
```

**Check 1: Bug is open**
- PASS if `status.name` is NOT "Closed"
- FAIL if `status.name` is "Closed"
- Pass message: `"bug is open, matching expected state (open)"`
- Fail message: `"bug is closed, expected it to be open"`

**Check 2: Target version matches branch**
- Get target versions from `customfield_10855` (array)
- FAIL if no target version is set: `"expected the bug to target the '{expected}' version, but no target version was set"`
- FAIL if multiple target versions are set (only one allowed)
- PASS if exactly one target version and its `.name` starts with the expected prefix (e.g., `"4.20"` for `release-4.20`)
- FAIL otherwise: `"expected the bug to target either version '{expected}' or 'openshift-{expected}', but it targets '{actual}' instead"`

**Check 3: Bug in valid state**
- PASS if `status.name` (uppercased) is in `["NEW", "ASSIGNED", "POST"]`
- FAIL otherwise: `"bug is in state {actual}, which is not one of the valid states (NEW, ASSIGNED, POST)"`

**Check 4: Release notes**
- Get release note text from `customfield_10783`
  - If it's an ADF document, extract the plain text content
  - If it's a string, use directly
- Get release note type from `customfield_10785`
- PASS if release note type `.value` equals `"Release Note Not Required"`
- PASS if release note text is non-empty AND does NOT start with `"Cause: What actions or circumstances"`
- FAIL otherwise: `"release note text must be set and not match the template OR release note type must be set to 'Release Note Not Required'"`

**Check 5: Dependent bug states** (skip if `dependents_required` is false)
- For each dependent bug found via "Blocks" links:
  - PASS if dependent's `status.name` (uppercased) is in the allowed `dependent_valid_states` list
  - FAIL otherwise: `"expected dependent Jira Issue {key} to be in one of the following states: {allowed}, but it is {actual} instead"`
- If no dependents exist, this check is implicitly skipped (check 7 handles that)

**Check 6: Dependent bug target versions** (skip if `dependents_required` is false)
- For each dependent bug:
  - Get its Target Version from `customfield_10855`
  - PASS if target version starts with one of the `expected_dependent_versions` prefixes
  - FAIL otherwise: `"expected dependent Jira Issue {key} to target a version in {allowed}, but it targets '{actual}' instead"`

**Check 7: Dependents exist** (skip if `dependents_required` is false)
- PASS if at least one "Blocks" link exists to a bug in the same project
- FAIL otherwise: `"expected Jira Issue to depend on a bug targeting a version in {allowed} and in one of the following states: {allowed_states}, but no dependents were found"`

### Phase 4: Report

Render results as a markdown table:

```markdown
## Validating {JIRA_KEY} against branch {BRANCH}

**Bug**: {summary}
**Status**: {status} | **Target Version**: {target_version} | **Project**: {project}

| # | Check                          | Expected                | Actual             | Result |
|---|--------------------------------|-------------------------|--------------------| -------|
| 1 | Bug is open                    | Open                    | {status}           | {P/F}  |
| 2 | Target version                 | {expected_tv}           | {actual_tv}        | {P/F}  |
| 3 | Valid state                    | NEW/ASSIGNED/POST       | {status}           | {P/F}  |
| 4 | Release notes                  | Set (not template)      | {actual_rn}        | {P/F}  |
| 5 | Dependent bug states           | {allowed_states}        | {actual_dep_state} | {P/F}  |
| 6 | Dependent bug target version   | {allowed_dep_tv}        | {actual_dep_tv}    | {P/F}  |
| 7 | Dependents exist               | At least one            | {count} found      | {P/F}  |

Result: {N} of 7 checks passed
```

For checks that were skipped (main branch, no dependents required), show `SKIP` in the Result column.

**For each failure**, list the specific fix instruction:

```markdown
### Fixes needed

1. **Target version**: Set Target Version to `{expected}` (currently `{actual}`)
2. **Status**: Transition to NEW, ASSIGNED, or POST (currently `{actual}`)
3. **Release notes**: Set release note text or set Release Note Type to "Release Note Not Required"
4. **Dependents**: Create or link a bug in {PROJECT} targeting `{expected_dep_version}`
```

**If all checks pass:**

```markdown
All 7 checks passed. If the PR still shows `jira/invalid-bug`, comment `/jira refresh` on the PR.
```

### Phase 5: Offer Fixes

After reporting, offer to fix each failing check. List the fixes and ask for confirmation before proceeding.

**Fix: Target version** (checks 2, 6)
1. Resolve the version ID from Jira field metadata: use `mcp__atlassian__getJiraIssueTypeMetaWithFields` with `projectIdOrKey: {PROJECT}`, `issueTypeId` from the bug's `issuetype.id`, and `requiredFieldsOnly: false`
2. Find `customfield_10855` in the response fields — its `allowedValues` array contains all available versions. Match the entry whose `.name` equals the expected version string (e.g., `4.20.z`) and extract its `.id`
3. Update: `mcp__atlassian__editJiraIssue` with `fields: {"customfield_10855": [{"id": "{version_id}"}]}`

**Fix: Status** (checks 1, 3)
1. Get available transitions: `mcp__atlassian__getTransitionsForJiraIssue`
2. Find transition to a valid state (prefer "New" or "POST")
3. Transition: `mcp__atlassian__transitionJiraIssue` with the transition ID

**Fix: Release notes** (check 4)
1. Ask the user for release note text. Suggest format:
   ```
   Cause: {what causes the bug}
   Consequence: {what happens}
   Fix: {what was done}
   Result: {the fix resolves it}
   ```
2. Update: `mcp__atlassian__editJiraIssue` with `fields: {"customfield_10783": "{text}"}`
3. Alternative: if user wants to skip release notes, set release note type:
   `fields: {"customfield_10785": {"value": "Release Note Not Required"}}`

**Fix: Missing dependents** (check 7)
1. Check if a "Blocks" linked dependent already exists in `issuelinks`
2. If no dependent exists, offer to create one:
   - Create a new bug in the same project with:
     - Same summary (prefixed with branch info if needed)
     - Target Version set to the expected dependent version
   - Link with a "Blocks" relationship: `mcp__atlassian__createIssueLink` with `type: "Blocks"`, `inwardIssue: {new_bug}`, `outwardIssue: {original_bug}`
   - Use `mcp__atlassian__createJiraIssue` then `mcp__atlassian__createIssueLink`
3. If a dependent exists but targets wrong version or is in wrong state, offer to fix it

**Fix: Dependent bug state** (check 5)
1. For each dependent in wrong state:
   - Get transitions: `mcp__atlassian__getTransitionsForJiraIssue` for the dependent
   - Find transition to an allowed state
   - Transition: `mcp__atlassian__transitionJiraIssue`

**After all fixes applied:**
1. Re-run all 7 checks to confirm everything passes
2. Display updated results table
3. Remind user: "Comment `/jira refresh` on the PR to have the bot re-validate."

## Error Handling

| Error | Handling |
|-------|----------|
| PR not found | Display error with PR URL, suggest checking the URL |
| No JIRA key in PR title | Display the PR title, explain the expected format: `{JIRA-KEY}: description` |
| JIRA issue not found | Check if key is correct, check project access |
| MCP tool unavailable | Fall back to `gh` CLI for GitHub data; for JIRA, display manual fix instructions |
| Branch not recognized | Warn that branch `{name}` doesn't match expected patterns, ask for `--branch` override |
| Version ID not found | Display the expected version string, instruct user to set it manually in JIRA |
| Transition not available | List available transitions, explain which one is needed and why it might be blocked |

## Notes

- The jira-lifecycle-plugin config lives at `openshift/release/core-services/jira-lifecycle-plugin/config.yaml`. If validation rules change, update the mapping in this skill.
- If a human manually adds `jira/valid-bug`, the bot will not remove it.
- For cherry-pick PRs, the plugin may auto-clone the parent JIRA bug. Check for existing "Blocks" links before creating new dependents.
- The `main` branch uses `exclude_defaults: true`, which disables dependent bug checks (5-7).
