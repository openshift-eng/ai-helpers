---
name: Create Release Note
description: Detailed implementation guide for generating bug fix release notes from Jira and GitHub PRs
---

# Create Release Note

This skill provides detailed step-by-step implementation guidance for the `/jira:create-release-note` command, which automatically generates bug fix release notes by analyzing Jira bug tickets and their linked GitHub pull requests.

## When to Use This Skill

This skill is automatically invoked by the `/jira:create-release-note` command and should not be called directly by users.

## Prerequisites

- MCP Jira server configured and accessible
- GitHub CLI (`gh`) installed and authenticated
- User has read access to the Jira bug
- User has write access to Release Note fields in Jira
- User has read access to linked GitHub repositories

## Implementation Steps

### Step 1: Fetch and Validate Jira Bug

**Objective**: Retrieve the bug ticket and validate it's appropriate for release note generation.

**Actions**:

1. **Fetch the bug using MCP**:
   ```
   mcp__atlassian__jira_get_issue(
     issue_key=<issue-key>,
     fields="summary,description,issuetype,status,issuelinks,customfield_12320850,customfield_12317313,comment"
   )
   ```

2. **Parse the response**:
   - Extract `issuetype.name` - verify it's "Bug"
   - Extract `description` - full bug description text
   - Extract `issuelinks` - array of linked issues
   - Extract `customfield_12320850` - current Release Note Type (if already set)
   - Extract `customfield_12317313` - current Release Note Text (if already set)
   - Extract `comment.comments` - array of comment objects

3. **Validate issue type**:
   - If `issuetype.name != "Bug"`, show warning:
     ```
     Warning: {issue-key} is not a Bug (it's a {issuetype.name}).
     Release notes are typically for bugs. Continue anyway? (yes/no)
     ```
   - If user says no, exit gracefully

4. **Check if release note already exists**:
   - If `customfield_12317313` is not empty, show warning:
     ```
     This bug already has a release note:
     ---
     {existing release note}
     ---

     Do you want to regenerate it? (yes/no)
     ```
   - If user says no, exit gracefully

### Step 2: Parse Bug Description for Cause and Consequence

**Objective**: Extract the required Cause and Consequence sections from the bug description.

**Bug Description Format**:

Jira bug descriptions often follow this structure:
```
Description of problem:
{code:none}
<problem description>
{code}

Cause:
{code:none}
<root cause>
{code}

Consequence:
{code:none}
<impact>
{code}

Version-Release number of selected component (if applicable):
...

How reproducible:
...

Steps to Reproduce:
...

Actual results:
...

Expected results:
...
```

**Parsing Strategy**:

1. **Look for "Cause:" section**:
   - Search for the string "Cause:" (case-insensitive)
   - Extract text between "Cause:" and the next major section
   - Remove Jira markup: `{code:none}`, `{code}`, etc.
   - Trim whitespace

2. **Look for "Consequence:" section**:
   - Search for the string "Consequence:" (case-insensitive)
   - Extract text between "Consequence:" and the next major section
   - Remove Jira markup
   - Trim whitespace

3. **Alternative patterns**:
   - Some bugs may use "Root Cause:" instead of "Cause:"
   - Some bugs may use "Impact:" instead of "Consequence:"
   - Try variations if exact match not found

4. **Handle missing sections**:
   - If Cause is missing:
     ```
     Bug description is missing the "Cause" section.

     Would you like to:
     1. Provide the Cause interactively
     2. Update the bug description in Jira first
     3. Cancel
     ```
   - If Consequence is missing:
     ```
     Bug description is missing the "Consequence" section.

     Would you like to:
     1. Provide the Consequence interactively
     2. Update the bug description in Jira first
     3. Cancel
     ```

5. **Interactive input** (if user chooses option 1):
   - Prompt: "What is the root cause of this bug?"
   - Collect user input
   - Use as Cause value
   - Repeat for Consequence if needed

**Example Parsing**:

Input:
```
Description of problem:
{code:none}
The control plane operator crashes when CloudProviderConfig.Subnet is not specified
{code}

Cause:
{code:none}
hostedcontrolplane controller crashes when hcp.Spec.Platform.AWS.CloudProviderConfig.Subnet.ID is undefined
{code}

Consequence:
{code:none}
control-plane-operator enters a crash loop
{code}
```

Output:
```
Cause: "hostedcontrolplane controller crashes when hcp.Spec.Platform.AWS.CloudProviderConfig.Subnet.ID is undefined"
Consequence: "control-plane-operator enters a crash loop"
```

### Step 3: Extract Linked GitHub PRs

**Objective**: Find all GitHub PR URLs associated with this bug.

**Sources to check** (in priority order):

1. **Remote Links** (Primary source - web links in Jira):
   - Check the Jira issue response for web links
   - Field name varies: `remotelinks`, or `issuelinks` with outward GitHub PR links
   - Extract GitHub PR URLs matching pattern: `https://github\.com/[\w-]+/[\w-]+/pull/\d+`
   - **IMPORTANT**: Never use `gh issue view {JIRA-KEY}` - Jira keys are NOT GitHub issue numbers

2. **Bug Description**:
   - Scan the `description` field for GitHub PR URLs
   - Use regex: `https://github\.com/([\w-]+)/([\w-]+)/pull/(\d+)`
   - Extract and parse all matches
   - **IMPORTANT**: Only extract full PR URLs, not issue references

3. **Bug Comments**:
   - Iterate through `comment.comments` array
   - For each comment, scan `body` field for GitHub PR URLs
   - Use same regex pattern
   - Extract all matches

4. **Search by bug number** (Fallback if no PR URLs found):
   - If no PRs found via links, search GitHub for PRs mentioning the bug
   - **For OCPBUGS**: Try common OpenShift repos:
     ```bash
     for repo in "openshift/hypershift" "openshift/cluster-api-provider-aws" "openshift/origin"; do
       gh pr list --repo "$repo" --search "{issue-key} in:title,body" --state all --limit 10 --json number,url,title
     done
     ```
   - Display found PRs and ask user to confirm which are relevant:
     ```
     Found PRs mentioning {issue-key}:
     1. openshift/hypershift#4567 - Fix panic when CloudProviderConfig.Subnet is undefined
     2. openshift/hypershift#4568 - Add tests for Subnet validation

     Which PRs should be included in the release note? (enter numbers separated by commas, or 'all')
     ```
   - **IMPORTANT**: Never use `gh issue view {JIRA-KEY}` - this will fail

**URL Parsing**:

For each found URL `https://github.com/openshift/hypershift/pull/4567`:
- Extract `org`: "openshift"
- Extract `repo`: "hypershift"
- Extract `pr_number`: "4567"
- Store as: `{"url": "...", "repo": "openshift/hypershift", "number": "4567"}`

**Deduplication**:

- Keep only unique PR URLs
- If same PR is mentioned multiple times, include it only once

**Validation**:

- If no PRs found after all attempts:
  ```
  No GitHub PRs found linked to {issue-key}.

  Please link at least one PR to generate release notes.

  How to link PRs in Jira:
  1. Edit the bug in Jira
  2. Add a web link to the GitHub PR URL
  3. Or mention the PR URL in a comment
  4. Then run this command again
  ```
  Exit without updating the ticket.

**Example**:

Found PRs:
```
[
  {
    "url": "https://github.com/openshift/hypershift/pull/4567",
    "repo": "openshift/hypershift",
    "number": "4567"
  },
  {
    "url": "https://github.com/openshift/hypershift/pull/4568",
    "repo": "openshift/hypershift",
    "number": "4568"
  }
]
```

### Step 4: Analyze Each GitHub PR

**Objective**: Extract Fix, Result, and Workaround information from each linked PR.

**For each PR in the list**:

#### 4.1: Fetch PR Details

**Command**:
```bash
gh pr view {number} --json body,title,commits,url,state --repo {repo}
```

**Error handling**:
```bash
if ! gh pr view {number} --json body,title,commits,url,state --repo {repo} 2>/dev/null; then
  echo "Warning: Unable to access PR {url}"
  echo "Verify the PR exists and you have permissions."
  # Skip this PR, continue with next
fi
```

**Expected output** (JSON):
```json
{
  "body": "This PR fixes the panic when CloudProviderConfig.Subnet is not specified...",
  "title": "Fix panic when CloudProviderConfig.Subnet is not specified",
  "commits": [
    {
      "messageHeadline": "Add nil check for Subnet field",
      "messageBody": "This prevents the controller from crashing..."
    }
  ],
  "url": "https://github.com/openshift/hypershift/pull/4567",
  "state": "MERGED"
}
```

**Parse and store**:
- `title`: PR title (short summary)
- `body`: Full PR description
- `commits`: Array of commit objects with messages
- `state`: PR state (MERGED, OPEN, CLOSED)

#### 4.2: Fetch PR Diff

**Command**:
```bash
gh pr diff {number} --repo {repo}
```

**Purpose**: Understand what code was actually changed

**Analysis strategy**:
- Look for added lines (starting with `+`)
- Identify key changes:
  - New error handling (`if err != nil`)
  - New validation checks (`if x == nil`)
  - New return statements
  - New error messages
- Don't include the entire diff in the release note
- Summarize the nature of changes

**Example diff analysis**:
```diff
+if hcp.Spec.Platform.AWS.CloudProviderConfig.Subnet == nil {
+    return fmt.Errorf("Subnet configuration is required")
+}
```

**Summary**: "Added nil check for CloudProviderConfig.Subnet field"

#### 4.3: Fetch PR Comments

**Command**:
```bash
gh pr view {number} --json comments --repo {repo}
```

**Expected output** (JSON):
```json
{
  "comments": [
    {
      "author": {"login": "reviewer1"},
      "body": "This looks good. The nil check will prevent the crash."
    },
    {
      "author": {"login": "author"},
      "body": "Yes, and I also added a more descriptive error message."
    }
  ]
}
```

**Analysis strategy**:
- Look for mentions of:
  - "workaround"
  - "temporary fix"
  - "until this is merged"
  - "users can work around this by..."
- Extract workaround information if found
- Look for clarifications about the fix
- Ignore unrelated discussion

#### 4.4: Synthesize PR Analysis

**Combine all sources** (title, body, commits, diff, comments) to extract:

**Fix** (what was changed):
- Prefer: PR body description of the fix
- Fallback: PR title + commit message summaries
- Focus on: What code/configuration was modified
- Keep concise: 1-3 sentences
- Avoid: Implementation details (specific function names, line numbers)

**Example Fix**:
```
Added nil check for CloudProviderConfig.Subnet before accessing Subnet.ID field to prevent nil pointer dereference
```

**Result** (outcome after the fix):
- Prefer: PR body description of expected behavior
- Fallback: Inverse of the bug's "Actual results"
- Focus on: What changed for users
- Keep concise: 1-2 sentences

**Example Result**:
```
The control-plane-operator no longer crashes when CloudProviderConfig.Subnet is not specified
```

**Workaround** (temporary solution before fix):
- Only include if explicitly mentioned in PR or comments
- Look for keywords: "workaround", "temporary", "manually"
- If not found: Omit this section entirely

**Example Workaround** (if found):
```
Users can manually specify a Subnet value in the HostedCluster spec to avoid the crash
```

### Step 5: Combine Multiple PRs

**Objective**: If multiple PRs are linked, synthesize them into a single coherent release note.

**Scenarios**:

#### Scenario A: Multiple PRs with different fixes

Example:
- PR #123: Fixes nil pointer crash
- PR #456: Adds better error message
- PR #789: Adds validation tests

**Strategy**: Combine all fixes into a narrative
```
Fix: Added nil check for CloudProviderConfig.Subnet field (PR #123), improved error messaging for missing configuration (PR #456), and added validation tests to prevent regression (PR #789)
```

#### Scenario B: Multiple PRs for same fix (backports)

Example:
- PR #123: Fix for main branch
- PR #456: Backport to release-4.20
- PR #789: Backport to release-4.19

**Strategy**: Mention the fix once, note the backports
```
Fix: Added nil check for CloudProviderConfig.Subnet field (backported to 4.20 and 4.19)
```

#### Scenario C: Multiple PRs with conflicting descriptions

Example:
- PR #123 says: "Fixed by adding validation"
- PR #456 says: "Fixed by removing the field access"

**Strategy**: Analyze the code diffs to determine what actually happened, or ask user:
```
Found multiple PRs with different fix descriptions:
- PR #123: "Fixed by adding validation"
- PR #456: "Fixed by removing the field access"

Which description is more accurate, or should I combine them?
```

### Step 6: Format Release Note

**Objective**: Create the final release note text following the standard template.

**Template**:
```
Cause: {cause from Jira}
Consequence: {consequence from Jira}
Fix: {synthesized from PRs}
Result: {synthesized from PRs}
Workaround: {synthesized from PRs - optional}
```

**Formatting rules**:
- Each line starts with the field name followed by a colon and space
- No blank lines between fields
- Workaround field is optional - omit if no workaround exists
- Keep each field concise but complete
- Use proper capitalization and punctuation

**Example output**:
```
Cause: hostedcontrolplane controller crashes when hcp.Spec.Platform.AWS.CloudProviderConfig.Subnet.ID is undefined
Consequence: control-plane-operator enters a crash loop
Fix: Added nil check for CloudProviderConfig.Subnet before accessing Subnet.ID field
Result: The control-plane-operator no longer crashes when CloudProviderConfig.Subnet is not specified
```

### Step 7: Security Validation

**Objective**: Scan the release note text for sensitive data before submission.

**Patterns to detect**:

1. **API Tokens and Keys**:
   - Pattern: `(sk|pk)_[a-zA-Z0-9]{20,}`
   - Pattern: `ghp_[a-zA-Z0-9]{36}`
   - Pattern: `gho_[a-zA-Z0-9]{36}`
   - Pattern: `github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}`

2. **AWS Credentials**:
   - Pattern: `AKIA[0-9A-Z]{16}`
   - Pattern: `aws_access_key_id\s*=\s*[A-Z0-9]+`
   - Pattern: `aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]+`

3. **Passwords in URLs**:
   - Pattern: `https?://[^:]+:[^@]+@`
   - Example: `https://user:password@example.com`

4. **JWT Tokens**:
   - Pattern: `eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+`

5. **SSH Private Keys**:
   - Pattern: `-----BEGIN (RSA|OPENSSH|DSA|EC|PGP) PRIVATE KEY-----`

6. **Kubernetes Secrets**:
   - Pattern: `[a-zA-Z0-9+/]{40,}==?` (base64 encoded secrets)
   - Context: If appears after "token:", "secret:", "password:"

**Validation logic**:

```python
sensitive_patterns = {
    "API Token": r"(sk|pk)_[a-zA-Z0-9]{20,}",
    "GitHub Token": r"gh[po]_[a-zA-Z0-9]{36}",
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "URL with credentials": r"https?://[^:]+:[^@]+@",
    "JWT Token": r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+",
    "Private Key": r"-----BEGIN .* PRIVATE KEY-----"
}

for name, pattern in sensitive_patterns.items():
    if re.search(pattern, release_note_text):
        print(f"Security validation failed!")
        print(f"Detected what appears to be {name} in the release note text.")
        print(f"Please review the source PRs and remove any credentials.")
        exit(1)
```

**If validation fails**:
```
Security validation failed!

Detected what appears to be an API token in the release note text.

This may have come from:
- PR description
- Commit messages
- Code changes (diff)
- PR comments

Please review the source PRs and remove any credentials before proceeding.

Use placeholder values instead:
- YOUR_API_KEY
- <redacted>
- ********

Aborting release note creation.
```

### Step 8: Select Release Note Type

**Objective**: Determine the appropriate Release Note Type for this bug.

**Available types** (from Jira dropdown):
1. Bug Fix
2. Release Note Not Required
3. Known Issue
4. Enhancement
5. Rebase
6. Technology Preview
7. Deprecated Functionality
8. CVE

**Auto-detection strategy**:

1. **For OCPBUGS**: Default suggestion is "Bug Fix" (most common)

2. **Check for CVE references**:
   - If bug description or PRs mention "CVE-" → Suggest "CVE"

3. **Check for deprecation**:
   - If PRs mention "deprecated", "deprecating", "removing" → Suggest "Deprecated Functionality"

4. **Check for new features**:
   - If PRs add significant new functionality → Suggest "Enhancement"
   - Though typically bugs should be "Bug Fix"

5. **Check for known issues**:
   - If PRs don't actually fix the issue, just document it → Suggest "Known Issue"

**User interaction**:

Use the `AskUserQuestion` tool:

```
questions = [{
  "question": "What type of release note is this?",
  "header": "Type",
  "multiSelect": false,
  "options": [
    {
      "label": "Bug Fix",
      "description": "Fix for a defect (most common)"
    },
    {
      "label": "Known Issue",
      "description": "Documents a known problem without a fix"
    },
    {
      "label": "Enhancement",
      "description": "New feature or improvement"
    },
    {
      "label": "CVE",
      "description": "Security vulnerability fix"
    }
  ]
}]
```

**Store selection** for use in the next step.

### Step 9: Update Jira Ticket

**Objective**: Write the release note to the Jira ticket.

**MCP tool call**:
```
mcp__atlassian__jira_update_issue(
  issue_key=<issue-key>,
  fields={
    "customfield_12320850": {"value": "<selected_type>"},
    "customfield_12317313": "<formatted_release_note_text>"
  }
)
```

**Field details**:
- `customfield_12320850`: Release Note Type (must be exact match from dropdown)
- `customfield_12317313`: Release Note Text (plain text)

**Error handling**:

1. **Permission denied**:
   ```
   Failed to update {issue-key}.

   Error: You do not have permission to edit Release Note fields

   Please contact your Jira administrator or manually add the release note.

   Generated release note (for manual entry):
   ---
   {release_note_text}
   ---
   ```

2. **Invalid field value**:
   ```
   Failed to update Release Note Type field.

   Error: Value "{selected_type}" is not valid

   Please select a different type or manually update in Jira.
   ```

3. **Field not found**:
   ```
   Failed to update {issue-key}.

   Error: Field customfield_12320850 not found

   This may indicate a different Jira instance or configuration.
   Please manually add the release note.
   ```

**Success response**:
```
{
  "success": true,
  "issue": {
    "key": "OCPBUGS-38358",
    "fields": {
      "customfield_12320850": {"value": "Bug Fix"},
      "customfield_12317313": "Cause: ... Consequence: ... Fix: ... Result: ..."
    }
  }
}
```

### Step 10: Display Results

**Objective**: Show the user what was created and provide next steps.

**Output format**:
```
✓ Release Note Created for {issue-key}

Type: {Release Note Type}

Text:
---
{Release Note Text with proper formatting}
---

Updated: https://issues.redhat.com/browse/{issue-key}

Next steps:
- Review the release note in Jira
- Edit manually if any adjustments are needed
- The release note will be included in the next release
```

**Example**:
```
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

Next steps:
- Review the release note in Jira
- Edit manually if any adjustments are needed
- The release note will be included in the next release
```

## Error Recovery Strategies

### PR Analysis Failures

**Problem**: Some PRs can't be accessed or analyzed

**Recovery**:
1. Log warning for each failed PR
2. Continue with successfully analyzed PRs
3. If all PRs fail, treat as "No PRs linked" error
4. Show summary of what was analyzed:
   ```
   Analyzed 2 of 3 linked PRs:
   ✓ PR #123
   ✓ PR #456
   ✗ PR #789 (access denied)
   ```

### Incomplete Bug Description

**Problem**: Missing Cause or Consequence sections

**Recovery**:
1. Offer interactive input option
2. Provide template for user
3. Allow user to update bug and retry
4. Don't proceed without both fields

### Ambiguous PR Content

**Problem**: PRs don't clearly explain the fix

**Recovery**:
1. Use PR title as fallback
2. Analyze code diff more carefully
3. Ask user for clarification:
   ```
   The linked PR doesn't clearly describe the fix.

   Based on code analysis, it appears to:
   {best guess from diff}

   Is this correct? If not, please describe the fix:
   ```

### Conflicting Information

**Problem**: Multiple PRs describe different fixes

**Recovery**:
1. Present both descriptions to user
2. Ask which is correct or how to combine
3. Use AI to attempt intelligent synthesis
4. If synthesis fails, escalate to user

## Best Practices for Implementation

1. **Always validate inputs**: Check that issue exists, PRs are accessible, fields are present
2. **Fail gracefully**: Provide helpful error messages with recovery instructions
3. **Be defensive**: Handle missing data, API errors, permission issues
4. **Log progress**: Show user what's happening at each step
5. **Preserve data**: If update fails, show generated content so it's not lost
6. **Security first**: Always validate before updating Jira
7. **User in control**: Confirm selections, allow overrides

## Testing Checklist

- [ ] Bug with single linked PR
- [ ] Bug with multiple linked PRs
- [ ] Bug with no linked PRs (error case)
- [ ] Bug with inaccessible PR (warning case)
- [ ] Bug missing Cause section (error case)
- [ ] Bug missing Consequence section (error case)
- [ ] Bug with existing release note (warning case)
- [ ] Bug that's not a Bug type (warning case)
- [ ] Release note with detected credentials (security failure)
- [ ] Different Release Note Type selections
- [ ] Update permission denied (error case)
- [ ] MCP server not configured (error case)
- [ ] gh CLI not authenticated (error case)
