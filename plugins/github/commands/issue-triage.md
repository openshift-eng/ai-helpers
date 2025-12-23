---
description: Automatically triage and label GitHub issues using AI analysis
argument-hint: "<owner/repo> [issue-number]"
---

## Name
github:issue-triage

## Synopsis
```
/github:issue-triage <owner/repo> [issue-number]
```

## Description
The `github:issue-triage` command automates the process of triaging and labeling GitHub issues using AI-powered content analysis. It analyzes issue titles, descriptions, and context to intelligently select and apply appropriate labels from the repository's existing label set.

When provided with a repository and optional issue number, the command:
- Fetches issue details and repository labels using GitHub CLI
- Analyzes issue content to understand the type, scope, and technical areas involved
- Selects relevant labels based on objective criteria
- Applies labels to the issue(s) automatically
- Provides a summary of changes made

This command is designed to reduce manual triage overhead and ensure consistent labeling across issues.

## Implementation

### Prerequisites
1. **GitHub CLI (gh) Installation**
   - Check if installed: `which gh`
   - If not installed, install from: https://cli.github.com/
   - Verify authentication: `gh auth status`
   - If not authenticated, run: `gh auth login`

2. **Repository Access**
   - User must have write access to the repository to apply labels
   - For organization repositories, ensure proper permissions are granted

### Workflow Steps

1. **Validate Arguments**
   - Ensure repository is provided in `owner/repo` format
   - Validate issue number format if provided (must be numeric)
   - Verify repository exists and is accessible

2. **Fetch Repository Labels**
   ```bash
   gh label list --repo $1 --json name,description --limit 1000
   ```
   - Retrieve all available labels from the repository
   - Store label names and descriptions for reference during analysis

3. **Determine Issues to Triage**
   - If issue number provided (`$2`): Triage only that specific issue
   - If no issue number: Fetch all open issues without any labels
   ```bash
   # Single issue
   gh issue view $2 --repo $1 --json number,title,body,labels

   # All unlabeled issues
   gh issue list --repo $1 --state open --limit 100 --json number,title,body,labels \
     | jq '.[] | select(.labels | length == 0)'
   ```

4. **Analyze Each Issue**
   For each issue to be triaged:

   a. **Content Analysis**
      - Examine issue title for keywords and intent
      - Parse issue body/description for technical details
      - Identify issue type (bug report, feature request, question, documentation, etc.)
      - Determine affected components or areas
      - Assess clarity and completeness of the issue

   b. **Label Selection Criteria**
      Apply labels based on:
      - **Type labels**: `bug`, `enhancement`, `question`, `documentation`, etc.
      - **Area/Component labels**: Specific to repository structure (e.g., `area/cli`, `component/api`)
      - **Status labels**: `needs-triage`, `needs-info`, `good-first-issue`, etc.
      - **Platform labels**: OS-specific or environment-specific labels if mentioned
      - **Special flags**: `duplicate` (if similar issues exist), `stale`, etc.

   c. **Label Selection Rules**
      - **ONLY use labels that exist in the repository's label list**
      - Be specific but comprehensive in label selection
      - **AVOID priority labels** (e.g., `p0`, `p1`, `p2`, `priority/critical`) unless explicitly part of triage criteria
      - Prefer 2-5 labels per issue for optimal categorization
      - If issue content is too vague or unclear, apply `needs-info` or `needs-triage` label
      - Do not apply labels if none are objectively appropriate

5. **Apply Labels**
   ```bash
   gh issue edit $issue_number --repo $1 --add-label "label1,label2,label3"
   ```
   - Apply all selected labels in a single command
   - Handle errors gracefully (e.g., label doesn't exist, permission denied)

6. **Report Results**
   - Provide a summary table showing:
     - Issue number and title
     - Labels applied
     - Reasoning for label selection
   - Include any errors or warnings encountered
   - Suggest manual review for ambiguous cases

### Error Handling

- **GitHub CLI not installed**: Provide installation instructions
- **Not authenticated**: Guide user to run `gh auth login`
- **Repository not found**: Verify repository name format
- **Permission denied**: Check if user has write access to repository
- **Issue not found**: Verify issue number exists
- **Label doesn't exist**: Skip invalid labels and warn user
- **API rate limiting**: Inform user and suggest retry timing

### Constraints

- **No commenting**: The command applies labels only; it does not post comments on issues
- **Objective labeling**: Labels are selected based on objective analysis, not subjective priority
- **Batch limits**: Process maximum 100 issues at once to avoid rate limiting
- **Timeout**: Set reasonable timeout for API calls (e.g., 30 seconds per issue)

## Return Value

- **Format**: Markdown table summarizing triage results

Example output:
```
Issue Triage Summary for owner/repo
====================================

✓ Successfully triaged 5 issues

| Issue | Title | Labels Applied | Reasoning |
|-------|-------|---------------|-----------|
| #123 | Login fails on Safari | bug, area/auth, browser/safari | Bug report affecting authentication in Safari browser |
| #124 | Add dark mode support | enhancement, area/ui | Feature request for UI enhancement |
| #125 | How to configure X? | question, area/config | Configuration question |
| #126 | Fix typo in README | documentation, good-first-issue | Simple documentation fix suitable for new contributors |
| #127 | API returns 500 error | bug, area/api, needs-info | Bug report lacking reproduction steps |

⚠ Issues needing manual review:
- #127: Insufficient information to fully categorize; applied 'needs-info'
```

## Examples

1. **Triage a specific issue**:
   ```
   /github:issue-triage openshift-eng/ai-helpers 184
   ```
   Analyzes issue #184 in the openshift-eng/ai-helpers repository and applies appropriate labels.

2. **Triage all unlabeled issues in a repository**:
   ```
   /github:issue-triage kubernetes/kubernetes
   ```
   Finds all open issues without labels in kubernetes/kubernetes and triages them in batch.

3. **Triage issues in a personal repository**:
   ```
   /github:issue-triage username/my-project 42
   ```
   Triages issue #42 in a personal repository.

## Arguments

- `$1` (required): Repository in `owner/repo` format (e.g., `openshift-eng/ai-helpers`)
- `$2` (optional): Specific issue number to triage (e.g., `184`). If omitted, triages all open unlabeled issues.

## Notes

- This command is inspired by automated issue triage workflows used in large open-source projects
- The AI analysis is designed to be conservative and objective to avoid misclassification
- For repositories with custom labeling schemes, the command adapts to available labels
- Regular use of this command helps maintain consistent issue categorization
- Consider running this command periodically (e.g., daily) for active repositories
