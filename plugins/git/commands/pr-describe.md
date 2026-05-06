---
description: Generate a PR description from the current branch's changes against the base branch
argument-hint: "[base-branch]"
---

## Name
git:pr-describe

## Synopsis
```text
/git:pr-describe            # Compare against main
/git:pr-describe develop    # Compare against a specific base branch
```

## Description
Generate a well-structured Pull Request description by analyzing the current branch's commits and diff against the base branch. Designed for use *before* opening a PR.

**Use cases:**
- Draft a PR description before running `gh pr create`
- Get a starting point for complex multi-commit PRs
- Ensure the description covers all changes made

**Difference from `/git:redescribe`** -- That command rewrites the description of an *existing* PR. This command generates a description *before* the PR exists, working purely from local branch state.

## Implementation

### 1. Determine base branch and validate

- Use the provided argument as base branch, or default to `main`. If `main` does not exist, try `master`.
- Run `git rev-parse --verify <base>` to confirm the base branch exists. If not, error out.
- Run `git rev-parse --abbrev-ref HEAD` to get the current branch name. If on the base branch itself, error out.

### 2. Gather context

Collect commit and diff information:

```bash
# List commits on this branch not in base
git log --oneline <base>..HEAD

# Full commit messages for intent analysis
git log --format="%B---" <base>..HEAD

# Diff stat for a structural overview
git diff --stat <base>..HEAD

# Full diff for detailed analysis
git diff <base>..HEAD
```

If the full diff is extremely large (thousands of lines), first exclude test file contents (e.g. `*_test.go`, `*_test.py`, `test/**`, `tests/**`) and generated artifacts from detailed analysis — summarize them by count and purpose instead. Then focus on the stat output, file names, and representative hunks of non-test code rather than reading every line.

### 3. Detect PR template

Check for an existing PR template in the repository, in order of priority:

```bash
# Common PR template locations
.github/pull_request_template.md
.github/PULL_REQUEST_TEMPLATE.md
.github/PULL_REQUEST_TEMPLATE/default.md
docs/pull_request_template.md
pull_request_template.md
```

If a template is found, use its structure as the basis for the generated description. Fill in each section of the template with content derived from the diff and commits. Preserve any headings, checklists, or placeholders the template defines — replace placeholder text but keep the overall format intact.

If no template is found, use the default structure described in step 5.

### 4. Analyze and detect context

- **Jira / issue references**: Look for patterns like `OCPBUGS-\d+`, `JIRA-\d+`, `#\d+`, or `Fixes:` / `Closes:` in commit messages.
- **Change categories**: Classify changes (new files, modified files, deleted files, test changes, config changes, dependency updates).
- **Scope**: Identify which packages, modules, or components are touched.

### 5. Generate the PR description

If a PR template was found in step 3, populate it accordingly. Otherwise, produce a Markdown description with these sections:

- **Title suggestion**: A concise one-line summary (50-72 chars) derived from the overall change.
- **Summary**: 2-3 sentences explaining what this PR does and why.
- **Changes**: A bulleted list of the key changes, grouped logically (not one bullet per file -- group related changes together).
- **Testing**: Infer testing approach from test files changed or added. If no test changes, note that and suggest what testing might be appropriate.
- **Issue references**: Include any Jira or GitHub issue references found in commits.

**Style guidelines:**
- Be factual and specific -- describe what the code does, not vague generalities.
- Use imperative mood ("Add feature" not "Added feature").
- Keep it concise. A good PR description is thorough but not verbose.
- Do not invent information not present in the diff or commits.

### 6. Present output and offer next steps

1. Display the generated description clearly, formatted in a copyable Markdown block.
2. Ask the user:
   > "Would you like to: (1) copy to clipboard, (2) open a PR with this description via `gh pr create`, or (3) just keep it as-is?"

   - **Option 1**: Copy to clipboard using the first available tool: `wl-copy` (Wayland), `xclip -selection clipboard` (X11), or `pbcopy` (macOS). If no clipboard tool is available, just display the description.
   - **Option 2**: Run `gh pr create --title "<title>" --body "<description>"` after confirming with the user.
   - **Option 3**: Do nothing further.

## Return Value
- **Success**: A formatted PR description in Markdown, with optional next-step actions.
- **Failure**: Error message if not in a git repo, on the base branch, or no commits found ahead of base.

## Examples

### Example 1: Basic usage
```text
/git:pr-describe
```
Output:
```markdown
## Suggested title
feat(auth): add OAuth2 token refresh middleware

## Summary
Add automatic OAuth2 token refresh for API requests. When a token
expires mid-session, the middleware transparently refreshes it
instead of returning a 401 to the caller.

## Changes
- Add `TokenRefreshMiddleware` in `pkg/auth/middleware.go`
- Implement token expiry detection with configurable buffer time
- Add retry logic for failed refresh attempts (max 3 retries)
- Add unit tests covering refresh, expiry, and error scenarios

## Testing
- Unit tests added in `pkg/auth/middleware_test.go`
- Covers: successful refresh, expired refresh token, network errors

## References
- OCPBUGS-1234
```

### Example 2: Custom base branch
```text
/git:pr-describe release-4.16
```

## Arguments
- **[base-branch]** (optional): The branch to compare against. Defaults to `main` (falls back to `master` if `main` does not exist).

## See Also
- **`/git:redescribe`** -- Update description of an existing PR
- **`/git:commit-suggest`** -- Generate commit messages for staged changes
