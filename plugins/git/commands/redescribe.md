---
description: Adapt and correct a PR description to match its code diffs and commit messages
argument-hint: "[pr-url]"
---

## Name
git:redescribe

## Synopsis
```
/git:redescribe              # Redescribe the PR for the current branch
/git:redescribe <pr-url>     # Redescribe a specific PR by URL
```

## Description
The `/git:redescribe` command analyzes a Pull Request's actual code changes (diffs) and commit messages to generate an accurate, up-to-date PR description. It compares the existing description with the reality of the code, proposes a corrected description, and offers to update the PR.

This is particularly useful when:
- A PR has evolved significantly since it was opened.
- The initial description was placeholder text.
- Commits have been squashed or rebased, changing the PR's scope.

The command ensures the description accurately reflects:
- The problem being solved (from commit messages/Jira context).
- The changes made (from code diffs).
- The implementation details.

## Implementation

### 1. Identify Target PR

Determine which PR to operate on:
- **If `<pr-url>` is provided**: Use that PR.
- **If no argument**:
  - **Context Discovery**: Run `git remote -v` to identify the repository (prefer `upstream`, then `origin`).
  - Run `gh pr view --repo <owner>/<repo> --json url` to find the PR associated with the current branch. This proactively avoids "No default remote" errors.
  - If no PR is found, error out and ask the user to provide a URL or push the branch/open a PR.

### 2. Gather Context

Collect necessary information using the GitHub CLI (`gh`) and git:

1.  **Fetch PR Details**:
    ```bash
    gh pr view <pr-url> --json title,body,baseRefName,headRefName,number
    ```
    - `title`: For context (often contains Jira ID).
    - `body`: The current description (to see what needs changing).
    - `headRefName`: The source branch.

2.  **Fetch Commits**:
    ```bash
    gh pr view <pr-url> --json commits
    # OR if local:
    git log <base>..<head>
    ```
    - Extract commit messages to understand the *intent* and history.

3.  **Fetch Code Diffs**:
    ```bash
    gh pr diff <pr-url>
    ```
    - Analyze the actual code changes.
    - **Note**: If the diff is very large, prioritize file names, structural changes, and distinct code blocks to avoid context window limits.

### 3. Generate New Description

Synthesize a new description based on the gathered context.

**Analysis Steps:**
1.  **intent vs. Reality**: Compare the commit messages (intent) with the `gh pr diff` output (reality).
2.  **Missing Info**: Identify features or fixes in the code that are NOT in the current `body`.
3.  **Obsolete Info**: Identify things in the `body` that are no longer in the code.

**Drafting the Description:**
Create a new Markdown description that includes:
- **Summary**: A high-level overview of the change.
- **Motivation**: Why is this change needed? (Infer from Jira ID in title or "Fixes" in commits).
- **Changes**: A bulleted list of technical changes (e.g., "Added `FooComponent`", "Refactored `bar` logic", "Updated dependencies").
- **Testing**: A section suggesting how the changes verify the fix (inferred from test files changed).

*Style Note*: Use standard OpenShift/Kubernetes PR style if typical for the repo (e.g., linking issues, clear headers).

### 4. Present and Apply

1.  **Show the Proposal**:
    Display the **New Proposed Description** clearly to the user.
    Optionally show a "Diff" between the old description and the new one if helpful.

2.  **Interactive Confirmation**:
    Ask the user:
    > "Do you want to update the PR description with these changes? (y/n)"
    
    - **If 'y'**:
        Run:
        ```bash
        gh pr edit <pr-url> --body "<new-description>"
        ```
        Output: "✅ PR Description updated successfully."
    
    - **If 'n'**:
        Output: "Action cancelled. Description not updated."

## Return Value
- **Success**: Confirmation message that PR was updated (or skipped by user choice).
- **Failure**: Error message if PR not found, `gh` CLI fails, or network error.

## Examples

### Example 1: Redescribe current branch's PR
```bash
/git:redescribe
```
Output:
> Found PR #123: "Fix logic error"
> ...
> **Proposed Description:**
> ...
> Update PR description? (y/n)

### Example 2: Redescribe specific PR
```bash
/git:redescribe https://github.com/openshift/console/pull/9999
```

## Arguments
- **[pr-url]** (optional): The full URL of the Pull Request to analyze. If omitted, attempts to use the PR for the current checked-out branch.
