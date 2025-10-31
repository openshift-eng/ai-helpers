---
description: Generate bug fix release notes from Jira tickets and linked GitHub PRs
argument-hint: <issue-key>
---

## Name
jira:create-release-note

## Synopsis
```
/jira:create-release-note <issue-key>
```

## Description

The `jira:create-release-note` command automatically generates bug fix release notes by analyzing Jira bug tickets and their linked GitHub pull requests, then updates the Jira ticket with the generated release note content.

This command is particularly useful for:
- Creating consistent, well-formatted release notes across all bugs
- Automatically extracting information from multiple sources (Jira + GitHub)
- Saving time by analyzing PR code changes, commits, and descriptions
- Ensuring complete release notes with Cause, Consequence, Fix, Result, and Workaround

The command follows the standard release note template format and populates both the Release Note Type and Release Note Text fields in Jira.

## Implementation

The `jira:create-release-note` command runs in multiple phases:

### 🎯 Phase 1: Fetch and Validate Jira Bug

1. **Fetch bug ticket** using `mcp__atlassian__jira_get_issue` MCP tool:
   - Request all fields to ensure we have complete data
   - Verify the issue is a Bug type
   - Extract issue description, links, and custom fields

2. **Validate issue type**:
   - If not a Bug, warn user and ask if they want to continue
   - Release notes are typically for bugs, but may apply to other types

3. **Parse bug description** to extract required sections:
   - **Cause**: The root cause of the problem
   - **Consequence**: The impact or effect of the problem

4. **Handle missing sections**:
   - If Cause or Consequence sections are missing, inform the user
   - Provide template format and ask user to update the bug description
   - Optionally, allow user to provide Cause/Consequence interactively

### 🔗 Phase 2: Extract Linked GitHub PRs

Extract all linked GitHub PR URLs from multiple sources:

1. **Remote links** (Primary source - web links in Jira):
   - Check the Jira issue response for web links/remote links
   - Common field names: `remotelinks`, `issuelinks` with `outwardIssue.fields.issuetype.name == "GitHub PR"`
   - Look for GitHub PR URLs in remote link objects
   - Pattern: `https://github.com/{org}/{repo}/pull/{number}`
   - Extract PR URLs and parse into `{org}/{repo}` and `{number}`

2. **Description text**: Scan bug description for GitHub PR URLs
   - Use regex pattern to find PR URLs: `https://github\.com/[\w-]+/[\w-]+/pull/\d+`
   - Extract and parse all matches
   - **IMPORTANT**: Do NOT use `gh issue view {JIRA-KEY}` - Jira keys are not GitHub issues

3. **Comments**: Scan bug comments for GitHub PR URLs
   - Iterate through comments
   - Extract PR URLs using same regex pattern
   - **IMPORTANT**: Only look for full GitHub PR URLs, not issue references

4. **Deduplicate**: Create unique set of PR URLs

5. **Search by bug number** (Fallback if no PR URLs found):
   - If no PRs found via links, search GitHub for PRs mentioning the bug
   - **For OCPBUGS**: Search common repos (openshift/hypershift, openshift/cluster-api-provider-*):
     ```bash
     # Try common OpenShift repos
     for repo in "openshift/hypershift" "openshift/cluster-api-provider-aws" "openshift/origin"; do
       gh pr list --repo $repo --search "{issue-key} in:title,body" --state all --limit 10 --json number,url,title
     done
     ```
   - Ask user to confirm which PRs are relevant
   - **IMPORTANT**: Never use `gh issue view {JIRA-KEY}` - this will fail because Jira keys are not GitHub issue numbers

6. **Validate**: Ensure at least one PR is found
   - If no PRs found after all attempts, show error: "No GitHub PRs found linked to {issue-key}. Please link at least one PR to generate release notes."
   - Provide instructions on how to link PRs in Jira

### 📊 Phase 3: Analyze Each GitHub PR

For each linked PR, analyze multiple sources to extract Fix, Result, and Workaround information:

1. **Extract repository and PR number** from URL:
   - Parse: `https://github.com/{org}/{repo}/pull/{number}`
   - Store: `{org}/{repo}` as `REPO`, `{number}` as `PR_NUMBER`

2. **Fetch PR details** using `gh` CLI:
   ```bash
   gh pr view {PR_NUMBER} --json body,title,commits,url,state --repo {REPO}
   ```
   - Extract: title, body/description, commits array, state
   - Handle errors: If PR is inaccessible, log warning and skip

3. **Fetch PR diff** using `gh` CLI:
   ```bash
   gh pr diff {PR_NUMBER} --repo {REPO}
   ```
   - Analyze code changes to understand what was fixed
   - Look for key changes in error handling, validation, etc.

4. **Fetch PR comments** using `gh` CLI:
   ```bash
   gh pr view {PR_NUMBER} --json comments --repo {REPO}
   ```
   - Extract reviewer comments and author responses
   - Look for clarifications about the fix or workarounds

5. **Analyze all sources**:
   - **PR Title**: Often summarizes the fix
   - **PR Body/Description**: Usually contains detailed explanation
   - **Commit Messages**: May provide step-by-step implementation details
   - **Code Changes**: Shows exactly what was modified
   - **PR Comments**: May contain clarifications or additional context

6. **Extract key information**:
   - **Fix**: What code/configuration changes were made to address the problem
   - **Result**: What behavior changed after the fix
   - **Workaround**: If mentioned, any temporary solutions before the fix

### 🤖 Phase 4: Synthesize Release Note Content

Combine information from all analyzed PRs into a cohesive release note:

1. **Combine Cause/Consequence** from Jira bug:
   - Use the extracted Cause and Consequence sections
   - Clean up formatting (remove Jira markup if needed)

2. **Synthesize Fix** from all PRs:
   - If single PR: Use the PR's fix description
   - If multiple PRs: Combine into coherent narrative
   - Focus on "what was changed" rather than "how it was coded"
   - Keep it concise but complete

3. **Synthesize Result** from all PRs:
   - Describe the outcome after the fix is applied
   - Focus on user-visible changes
   - Example: "The control plane operator no longer crashes when..."

4. **Extract Workaround** (if applicable):
   - Check if PRs mention temporary solutions
   - Only include if a workaround was documented
   - Omit this section if no workaround exists

5. **Format according to template**:
   ```
   Cause: <extracted from bug description>
   Consequence: <extracted from bug description>
   Fix: <synthesized from PR analysis>
   Result: <synthesized from PR analysis>
   Workaround: <synthesized from PR analysis if applicable>
   ```

### 🔒 Phase 5: Security Validation

Scan the generated release note text for sensitive data before submission:

1. **Prohibited content patterns**:
   - Credentials: Passwords, API tokens, access keys
   - Cloud keys: AWS access keys (AKIA...), GCP service accounts, Azure credentials
   - Kubeconfigs: Cluster credentials, service account tokens
   - SSH keys: Private keys, authorized_keys content
   - Certificates: PEM files, private key content
   - URLs with credentials: `https://user:pass@example.com`

2. **Scanning approach**:
   - Use regex patterns to detect common credential formats
   - Check for base64-encoded secrets
   - Look for common secret prefixes (sk_, ghp_, etc.)

3. **Action if detected**:
   - STOP release note creation immediately
   - Inform user what type of data was detected (without showing it)
   - Example: "Detected what appears to be an API token in the release note text."
   - Ask user to review PR content and redact sensitive information
   - Provide guidance on safe alternatives (use placeholders like `<redacted>`, `YOUR_API_KEY`, etc.)

### 📝 Phase 6: Select Release Note Type

Prompt user to select the appropriate Release Note Type:

1. **Available options** (from Jira dropdown):
   - Bug Fix (most common for OCPBUGS)
   - Release Note Not Required
   - Known Issue
   - Enhancement
   - Rebase
   - Technology Preview
   - Deprecated Functionality
   - CVE

2. **Auto-detection** (optional):
   - For OCPBUGS: Default to "Bug Fix"
   - Check PR titles/descriptions for keywords
   - Suggest type based on content analysis

3. **User confirmation**:
   - Show suggested type
   - Allow user to override
   - Use `AskUserQuestion` tool for interactive selection

### ✅ Phase 7: Update Jira Ticket

Update the Jira bug ticket with generated release note:

1. **Prepare fields** for update:
   ```
   {
     "customfield_12320850": {"value": "<Release Note Type>"},
     "customfield_12317313": "<Release Note Text>"
   }
   ```

2. **Update using MCP tool**:
   ```
   mcp__atlassian__jira_update_issue(
     issue_key=<issue-key>,
     fields={
       "customfield_12320850": {"value": "Bug Fix"},
       "customfield_12317313": "<formatted release note text>"
     }
   )
   ```

3. **Handle update errors**:
   - Permission denied: User may not have rights to update these fields
   - Invalid field value: Release Note Type value not in allowed list
   - Field not found: Custom field IDs may be different in different Jira instances

### 📤 Phase 8: Display Results

Show the user what was created:

1. **Display generated release note**:
   ```
   Release Note Created for {issue-key}

   Type: Bug Fix

   Text:
   ---
   Cause: ...
   Consequence: ...
   Fix: ...
   Result: ...
   Workaround: ...
   ---

   Updated: https://issues.redhat.com/browse/{issue-key}
   ```

2. **Provide next steps**:
   - Link to the updated Jira ticket
   - Suggest reviewing the release note in Jira
   - Mention that the release note can be edited manually if needed

## Arguments

- **$1 – issue-key** *(required)*
  Jira issue key for the bug (e.g., `OCPBUGS-12345`).
  Must be a valid bug ticket with linked GitHub PRs.

## Return Value

- **Issue Key**: The Jira issue that was updated
- **Release Note Type**: The selected release note type
- **Release Note Text**: The generated release note content
- **Issue URL**: Direct link to the updated Jira ticket

## Examples

### Basic Usage

Create release note for a bug with linked PRs:
```
/jira:create-release-note OCPBUGS-38358
```

The command will:
1. Fetch the bug from Jira
2. Extract Cause and Consequence from the description
3. Find and analyze all linked GitHub PRs
4. Generate the release note
5. Prompt for Release Note Type selection
6. Update the Jira ticket
7. Display the results

### Example Output

```
Analyzing OCPBUGS-38358...

Found bug: "hostedcontrolplane controller crashes when hcp.Spec.Platform.AWS.CloudProviderConfig.Subnet.ID is undefined"

Extracted from bug description:
  Cause: hostedcontrolplane controller crashes when hcp.Spec.Platform.AWS.CloudProviderConfig.Subnet.ID is undefined
  Consequence: control-plane-operator enters a crash loop

Found 1 linked GitHub PR:
  - https://github.com/openshift/hypershift/pull/4567

Analyzing PR #4567...
  Title: "Fix panic when CloudProviderConfig.Subnet is not specified"
  Commits: 2
  Files changed: 3

Synthesizing release note...

Select Release Note Type:
1. Bug Fix
2. Release Note Not Required
3. Known Issue
4. Enhancement
5. CVE

Selection: 1 (Bug Fix)

Updating Jira ticket...

✓ Release Note Created for OCPBUGS-38358

Type: Bug Fix

Text:
---
Cause: hostedcontrolplane controller crashes when hcp.Spec.Platform.AWS.CloudProviderConfig.Subnet.ID is undefined
Consequence: control-plane-operator enters a crash loop
Fix: Added nil check for CloudProviderConfig.Subnet before accessing Subnet.ID field
Result: The control-plane-operator no longer crashes when CloudProviderConfig.Subnet is not specified
---

Updated: https://issues.redhat.com/browse/OCPBUGS-38358
```

## Error Handling

### No GitHub PRs Linked

**Scenario**: Bug ticket has no linked GitHub PRs.

**Error Message**:
```
No GitHub PRs found linked to OCPBUGS-12345.

To generate a release note, please link at least one GitHub PR to this bug.

How to link PRs:
1. Edit the bug in Jira
2. Add a web link to the GitHub PR URL
3. Or mention the PR URL in a comment
4. Then run this command again
```

**Action**: Exit without updating the ticket.

### PR Not Accessible

**Scenario**: One or more linked PRs cannot be accessed.

**Warning Message**:
```
Warning: Unable to access PR https://github.com/org/repo/pull/123
Verify the PR exists and you have permissions.

Continuing with remaining PRs...
```

**Action**: Skip the inaccessible PR, continue with others. If all PRs are inaccessible, treat as "No PRs" error.

### Missing Cause or Consequence

**Scenario**: Bug description doesn't contain required Cause and/or Consequence sections.

**Error Message**:
```
Bug description is missing required sections:
  - Missing: Cause
  - Missing: Consequence

Please update the bug description to include these sections.

Template format:
---
Description of problem:
<problem description>

Cause:
<root cause of the problem>

Consequence:
<impact or effect of the problem>

Steps to Reproduce:
1. ...
---

Would you like to provide Cause and Consequence interactively? (yes/no)
```

**Action**:
- If user says yes: Prompt for Cause and Consequence
- If user says no: Exit and ask them to update the bug

### Security Validation Failure

**Scenario**: Generated release note contains potential credentials or secrets.

**Error Message**:
```
Security validation failed!

Detected what appears to be an API token in the release note text.

This may have come from:
- PR description
- Commit messages
- Code changes
- PR comments

Please review the source PRs and remove any credentials before proceeding.

Use placeholder values instead:
- YOUR_API_KEY
- <redacted>
- ********

Aborting release note creation.
```

**Action**: Stop immediately, do not update Jira ticket.

### Update Permission Denied

**Scenario**: User doesn't have permission to update Release Note fields.

**Error Message**:
```
Failed to update OCPBUGS-12345.

Error: You do not have permission to edit field 'Release Note Type'

This may require specific Jira permissions. Please contact your Jira administrator or use the Jira web UI to add the release note manually.

Generated release note (for manual entry):
---
Cause: ...
Consequence: ...
...
---
```

**Action**: Display the generated release note so user can manually copy it.

### Invalid Release Note Type

**Scenario**: Selected release note type is not valid for this Jira instance.

**Error Message**:
```
Failed to update Release Note Type field.

Error: Value "Bug Fix" is not valid for field customfield_12320850

This may indicate a Jira configuration issue. Please verify the allowed values for Release Note Type in your Jira instance.
```

**Action**: Ask user to select a different type or manually update in Jira.

### Multiple PRs with Conflicting Information

**Scenario**: Multiple PRs describe different fixes or contradictory information.

**Warning Message**:
```
Found 3 linked PRs with different fix descriptions:
- PR #123: Fix A
- PR #456: Fix B
- PR #789: Fix C

Combining all fixes into a single release note...
```

**Action**: Use AI to synthesize a coherent narrative combining all fixes. If truly contradictory, ask user for clarification.

## Best Practices

1. **Link PRs early**: Add GitHub PR links to bugs as soon as PRs are created
2. **Use structured bug descriptions**: Always include Cause and Consequence sections
3. **Review before submission**: Check the generated release note before confirming
4. **Sanitize PR content**: Don't include credentials in PR descriptions or commits
5. **One release note per bug**: Don't run this command multiple times for the same bug
6. **Update if needed**: Release notes can be manually edited in Jira after creation

## Prerequisites

### Required Tools

1. **MCP Jira Server**: Must be configured and accessible
   - See [Jira Plugin README](../README.md) for setup instructions
   - Requires read/write permissions for bugs

2. **GitHub CLI (`gh`)**: Must be installed and authenticated
   - Install: `brew install gh` (macOS) or see [GitHub CLI docs](https://cli.github.com/)
   - Authenticate: `gh auth login`
   - Verify: `gh auth status`

3. **Access to GitHub Repositories**: Must have read access to repos where PRs are located
   - PRs in private repos require appropriate GitHub permissions
   - Public repos should work without additional configuration

### Required Permissions

1. **Jira Permissions**:
   - Read access to bug tickets
   - Write access to Release Note Type field (customfield_12320850)
   - Write access to Release Note Text field (customfield_12317313)

2. **GitHub Permissions**:
   - Read access to pull requests
   - Read access to repository diffs and commits

## See Also

- `jira:solve` - Analyze and solve Jira issues
- `jira:create` - Create Jira issues with guided workflows
- `jira:generate-test-plan` - Generate test plans for PRs
- `jira:status-rollup` - Create status rollup reports

## Technical Notes

### Jira Custom Fields

The command uses these Jira custom field IDs:
- `customfield_12320850`: Release Note Type (dropdown)
- `customfield_12317313`: Release Note Text (text field)

These field IDs are specific to Red Hat's Jira instance. If using a different Jira instance, you may need to update the field IDs.

### GitHub CLI Rate Limits

The `gh` CLI is subject to GitHub API rate limits:
- Authenticated: 5,000 requests per hour
- This command typically uses 3-4 requests per PR (view, diff, comments)
- For bugs with many linked PRs, be aware of rate limits

### Release Note Template

The release note follows this structure:
- **Cause**: Root cause (from Jira)
- **Consequence**: Impact (from Jira)
- **Fix**: What was changed (from PRs)
- **Result**: Outcome after fix (from PRs)
- **Workaround**: Temporary solution (from PRs, optional)

This format is standard for Red Hat bug fix release notes.
