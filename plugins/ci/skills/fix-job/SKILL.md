---
name: Fix Job
description: Investigate a failing CI job, file a Jira bug, and open a PR to fix it
---

# Fix Job

This skill investigates a failing CI job, searches Jira for existing bugs, files a new OCPBUGS issue if needed, and attempts to create a fix PR for High and Medium fixability issues.

## When to Use This Skill

Use this skill when you need to:

- Take action on a failing CI job (not just investigate it)
- File a Jira bug for a CI regression
- Attempt an automated fix for a CI job failure
- End-to-end: investigate, file bug, open PR

## Prerequisites

1. **Network Access**: Must be able to reach Sippy, Prow, Jira, and GitHub
2. **Jira MCP**: Configured for searching and creating OCPBUGS issues
3. **GitHub CLI (`gh`)**: Installed and authenticated with push access to forks
4. **gcloud CLI**: For downloading Prow job artifacts
5. **Python 3**: For API requests

## Implementation Steps

### Step 1: Run Investigation

Execute the `investigate-job` skill with the provided `job_name` and `release` arguments.

Capture the structured `INVESTIGATION_RESULT` block from the output:
- `job_name`, `root_cause`, `classification`, `fixability`, `proposed_fix`, `existing_bugs`

If the investigation determines the job is healthy (no failures), report that and exit.

### Step 2: Search Jira for Existing Bugs

Search OCPBUGS for existing bugs related to this job. Use the Jira MCP tools to search.

#### 2.1: Search by Job Name

Search for the job name (or a distinctive substring) in OCPBUGS:

```
JQL: project = OCPBUGS AND text ~ "{job_name_substring}" AND status not in (Closed, Verified) ORDER BY created DESC
```

Use a distinctive part of the job name for the search (e.g., `e2e-vsphere-ovn-techpreview` rather than the full `periodic-ci-openshift-release-main-nightly-4.22-e2e-vsphere-ovn-techpreview`).

#### 2.2: Search by Error Strings

If no results from the job name search, search for key error strings from the investigation:

```
JQL: project = OCPBUGS AND text ~ "{key_error_string}" AND status not in (Closed, Verified) ORDER BY created DESC
```

Use the most distinctive error message from the root cause analysis.

#### 2.3: Evaluate Results

For each found bug:
- Check if it describes the same failure (same root cause, same component)
- Check if it's still relevant (not stale -- last updated recently, or status is active)

If a matching bug is found:
- Report it to the user with a link
- Note whether the bug's description matches the current failure or needs updating
- **Do not file a duplicate** -- skip to Step 4

### Step 3: File OCPBUGS

If no existing bug matches, file a new OCPBUGS issue using the Jira MCP tools.

#### 3.1: Determine Jira Component

Map the affected component from the investigation to a Jira component. Common mappings:

- Installer-related failures -> `Installer`
- Networking failures -> `Networking`
- OLM failures -> `OLM`
- Authentication failures -> `Authentication`
- Storage failures -> `Storage`
- Node failures -> `Node`
- Machine API failures -> `Machine Config Operator` or `Cluster Infrastructure`
- Test framework issues -> `Test Infrastructure`

If uncertain about the component, use `Test Infrastructure` as a fallback and note it in the description.

#### 3.2: Create the Bug

Use the Jira MCP `jira_create_issue` tool with these fields:

- **Project**: OCPBUGS
- **Issue Type**: Bug
- **Summary**: `[CI] {job_short_name}: {brief_failure_description}`
  - Keep under 120 characters
  - Example: `[CI] e2e-vsphere-ovn-techpreview: OLMv1 catalogd fails to bind IPv6 address`
- **Description**: Use this template:

```
h2. Impact
* *Job*: [{job_name}|{test_grid_url}]
* *Current pass rate*: {current_pass_percentage}% (was {previous_pass_percentage}%)
* *Runs in period*: {current_runs}
* *Classification*: {classification}
* *Variants*: {variants}

h2. Root Cause
{root_cause_description}

h2. Error Details
{key_error_messages_from_analysis}

h2. Proposed Fix
{proposed_fix}

h2. Recent Failed Runs
{list_of_prow_urls_for_recent_failures}
```

- **Component**: `{jira_component}` (from Step 3.1)
- **Affects Version**: `{release}` (e.g., "4.22")
- **Target Version**: `{release}.0` (e.g., "4.22.0")
- **Labels**: `["CI"]`

Report the created bug key and URL to the user.

### Step 4: Attempt Fix

Only attempt a fix if:
- Fixability is **High** or **Medium**
- The proposed fix is clear enough to implement
- The fix is in a repository we can modify

#### 4.1: Identify Target Repository

Determine which repository needs the fix based on the investigation:

- **openshift/release fixes**: Config changes, test skips, step registry updates -- fix directly in the current repo
- **Component fixes**: Identify the component repo from:
  - The job configuration in `ci-operator/config/`
  - The error messages (which component is failing)
  - The test name or step registry reference

#### 4.2: For openshift/release Fixes

If the fix is in `openshift/release` (current repo):

1. Make the necessary changes (config edit, test skip, etc.)
2. Run `make update` to regenerate downstream files
3. Commit with a descriptive message
4. Push to user's fork and open a PR

#### 4.3: For Component Fixes

If the fix is in a component repository:

1. **Clone the repo**: Use `gh repo clone {org}/{repo}` into a temporary directory
2. **Create a branch**: `git checkout -b fix/{brief-description}`
3. **Make the fix**: Based on the investigation's proposed fix
4. **Run any generators**: If the change involves generated code, run the appropriate make target
5. **Commit**: With descriptive message including:
   - What was wrong
   - What the fix does
   - Link to the failing job
   - `Co-Authored-By: Claude`
6. **Push and create PR**:
   ```bash
   gh repo fork {org}/{repo} --clone=false  # Ensure fork exists
   git push -u origin fix/{brief-description}
   gh pr create --title "{title}" --body "{body}"
   ```
7. **Link PR in Jira bug**: If a bug was filed in Step 3, add a comment with the PR link

#### 4.4: Report Fix Status

Report one of:
- "PR opened: {url}" with link to the PR
- "Fix attempted but needs manual review: {reason}"
- "Manual fix needed: {guidance}" for Low fixability or unclear fixes

### Step 5: Summary

Output a summary of all actions taken:

```markdown
## Actions Taken

### Investigation
- **Root cause**: {root_cause}
- **Classification**: {classification}
- **Fixability**: {fixability}
- **Report**: {html_report_path}

### Jira
- {Found existing bug: OCPBUGS-XXXXX | Filed new bug: OCPBUGS-XXXXX | No bug action taken}

### Fix
- {PR opened: {url} | Manual fix needed: {guidance} | No fix attempted (Low fixability)}
```

## Error Handling

1. **Investigation failure**: If the investigation skill fails, report the error and exit. Cannot proceed without investigation.
2. **Jira search failure**: If Jira MCP is unavailable, skip bug search/filing and note it. Continue with fix attempt.
3. **Jira create failure**: If bug creation fails, note the error. Continue with fix attempt.
4. **Clone failure**: If the component repo can't be cloned, report and suggest manual fix.
5. **PR creation failure**: If PR creation fails (permissions, branch exists, etc.), report the error with the changes that were made locally.

## Notes

- The skill always investigates first, even if the user thinks they know the problem. Fresh investigation data ensures accurate bug filing.
- Bug filing uses the OCPBUGS project, which is the standard project for OpenShift component bugs.
- When the fix is in `openshift/release`, the skill works in the current repository. For component fixes, it clones into a temporary directory.
- The `Co-Authored-By: Claude` trailer is important for attribution.
- PRs are opened against the default branch (usually `main` or `master`) unless the fix targets a specific release branch.

## See Also

- Related Command: `/ci:fix-job` - The user-facing command
- Related Skill: `investigate-job` - Investigation (always run first)
- Related Skill: `find-regressing-jobs` - Find jobs to fix
- Related Skill: `hunt-problems` - Orchestrator that can invoke this skill
