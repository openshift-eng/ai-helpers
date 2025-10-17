---
description: Show current branch, git status, and recent commits for quick context
argument-hint:
---

## Name
git:summary

## Synopsis
```
/git:summary
```

## Description
The `git:summary` command provides a comprehensive overview of the current Git repository state. It displays the current branch, tracking status, working tree status, and recent commit history in a single concise view. This command is designed to give developers quick context about their repository without running multiple Git commands manually.

It provides essential information for developers including:
- Current branch and remote tracking status (ahead/behind)
- Working tree status (modified, staged, and untracked files)
- Recent commit history with one-line summaries
- Uncommitted changes summary

The spec sections is inspired by https://man7.org/linux/man-pages/man7/man-pages.7.html#top_of_page

## Implementation
- Executes multiple git commands to gather repository state
- Retrieves current branch name and tracking information
- Shows git status for modified, staged, and untracked files
- Displays last 5 commits with one-line summaries
- Summarizes uncommitted changes
- Formats output for clear readability
- All information is read-only with no side effects

Implementation logic:
```bash
# Get current branch and tracking status
git branch -vv

# Show working tree status
git status --short

# Display recent commits
git log --oneline -5

# Summarize uncommitted changes
git diff --stat
```

## Return Value
- **Claude agent text**: Formatted summary including:
  - Current branch name and remote tracking status
  - List of modified, staged, and untracked files
  - Last 5 commit messages with hashes
  - Statistics of uncommitted changes

## Examples

1. **Basic usage**:
   ```
   /git:summary
   ```
   Output:
   ```
   Current branch: main
   Your branch is up to date with 'origin/main'.

   Modified files:
    M src/index.ts
   ?? temp/

   Recent commits:
   abc123 Fix authentication bug
   def456 Add user profile feature
   ghi789 Update dependencies
   jkl012 Refactor database layer
   mno345 Initial commit

   Uncommitted changes:
   1 file changed, 15 insertions(+), 3 deletions(-)
   ```

2. **Repository with no changes**:
   ```
   /git:summary
   ```
   Output:
   ```
   Current branch: develop
   Your branch is up to date with 'origin/develop'.

   Working tree clean

   Recent commits:
   pqr678 Merge pull request #42
   stu901 Add test coverage
   vwx234 Fix linting issues
   yza567 Update README
   bcd890 Release v2.0.0
   ```

## Arguments:
- None
