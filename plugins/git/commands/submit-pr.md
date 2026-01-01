---
description: Creates a pull request with analyzed change description
argument-hint: "[--title PR_TITLE] [--fixes PR_ISSUE] [--related RELATED_PR] [--draft true|false] [--base BRANCH]"
---

## Name

git:submit-pr

## Synopsis
```
/git:submit-pr [--title PR_TITLE] [--fixes PR_ISSUE] [--related RELATED_PR] [--draft true|false] [--base BRANCH]
```

## Description

The `git:submit-pr` command analyzes current git changes and automatically creates a pull request with an intelligently generated description based on commit subject, message, and changed files.

The command executes automatically through Claude Code's slash command system, combining the explanatory workflow below with actual git and GitHub CLI operations. It performs systematic analysis of the current branch and repository state to create or update pull requests intelligently, automatically detecting fork workflows and handling existing PR updates gracefully.

## Implementation

### 1. Argument handling

Parse arguments from the invocation:

- `--title <PR_TITLE>`: Optional PR title
- `--fixes <ISSUE_NUMBER>`: Optional issue number, adds `Fixes #<number>` to PR description
- `--related <ISSUE_NUMBER>`: Optional related issue, adds `Related #<number>` to PR description
- `--draft <true|false>`: Optional draft mode (default: false)
- `--base <BRANCH>`: Optional base branch (default: main)

### 2. Workflow Detection and Repository Analysis

The command begins by analyzing the repository structure to determine the workflow type (fork vs direct) and validate the current state for PR creation.

**Repository Type Detection:**
Detects fork workflows by checking for an upstream remote, which determines PR targeting strategy.

```bash
# Detect repository workflow
git remote show upstream
```

**Branch Validation:**
Validates the current branch contains commits ahead of the base branch.

```bash
# Validate branch state
git rev-list --count HEAD ^<base-branch>
```

**Prerequisites Verification:**
Confirms GitHub CLI availability and authentication status.

```bash
# Verify GitHub CLI setup
gh auth status
```

### 3. Intelligent Content Analysis

The command analyzes commit messages and changed files to automatically categorize the PR and generate appropriate descriptions.

**Commit Analysis:**
Examines commit subjects, bodies, and full history since base branch for primary change description and multi-commit summaries.

**File Pattern Recognition:**
Detects modification types from changed file patterns:
- API changes (`api/` directory)
- Controller modifications (`controllers/` directory)
- Test additions (`tests/` or `_test.go`)
- Documentation updates (`.md`, `.adoc`)

**Type Classification:**
Automatically classifies PRs using commit keywords and file patterns:
- **Enhancement / New Feature**: Default classification for new features and improvements
- **Bug Fix**: Detects keywords like "fix", "bug", "error" in commit messages
- **Refactor**: Identifies code restructuring with keywords like "refactor", "cleanup", "restructure"
- **Optimization**: Detects performance improvements with keywords like "optimize", "performance", "faster"
- **Test**: Identifies test-only changes with no production code modifications
- **Documentation**: Recognizes documentation-only updates

**Edge Case Handling:**
- **Multiple Types**: When multiple types detected, prioritizes in order: Bug Fix > Enhancement > Refactor > Optimization > Test > Documentation
- **Conflicting Signals**: File patterns override commit message keywords when they conflict
- **No Clear Indicators**: Defaults to "Enhancement / New Feature" classification

```bash
# Analyze commit content
git log -1 --format='%s %b' HEAD
git diff --name-only <base-branch>...HEAD
```

### 4. Existing PR Detection and Conflict Resolution

Searches for existing open PRs on current branch to prevent duplicates and enable updates.

**PR Discovery:**
Queries for existing open PRs using consistent head reference format for both fork and direct repository workflows.

```bash
# Check for existing PRs
gh pr list --head <current-branch> --state open
```

**Fork-Aware Queries:**
Targets upstream repository for fork workflows while maintaining head reference format for automatic fork context resolution.

**Update Decision Process:**
When existing PR found, displays:
- Existing PR details (title, number, URL)
- 20-second countdown timer with abort instructions
- Clear message: "Press Ctrl+C to abort, or wait to proceed with update"
- Automatic proceed after timeout with confirmation message

### 5. PR Description Generation

Generates comprehensive PR descriptions using structured template with type classification, content analysis, and issue linking.

**Template Structure:**
- **Type Classification**: Auto-selected checkbox list based on analysis
- **Description Content**: Commit body content or subject fallback
- **Multi-commit Context**: Summary for PRs with multiple commits
- **Issue References**: Integration with `fixes` and `related` arguments

**Content Prioritization:**
Prioritizes commit body content for main description, falls back to subjects for minimal messages. For multi-commit PRs, provides commit summary list using only commit titles (not bodies).

**Multi-Commit Description Logic:**
- **Primary Description**: Uses first commit's body content as main description
- **Fallback Order**: First commit body → first commit subject → "Multiple changes" generic message
- **Commit List**: Appends chronological list of all commit titles since base branch
- **Duplicate Detection**: Removes duplicate commit titles from summary list

### 6. PR Creation and Update Execution

Executes appropriate action based on analysis results, handling both creation and update scenarios.

**Branch Synchronization:**
Ensures remote branch reflects current local state using appropriate push strategies.

**Fork Workflow Handling:**
Requires specific targeting with head specifications and upstream repository targeting for PR creation.

```bash
# Create PR with fork awareness
gh pr create --repo <upstream-repo> --head <fork-owner>:<branch> --base <base-branch>
```

**Update Operations:**
Updates both remote branch content and PR metadata (title/description) to reflect current state.

```bash
# Update existing PR
git push --force-with-lease origin <current-branch>
gh pr edit <pr-number> --title "<title>" --body-file <description-file>
```

**File Cleanup:**
Automatically removes temporary description file after successful PR creation or update to prevent system accumulation of temp files.

**Error Handling:**
Provides clear feedback for failure scenarios and debugging guidance for manual resolution.

## Features

- **Intelligent Workflow Detection**: Automatically identifies fork vs direct repository workflows
- **Smart Content Analysis**: Categorizes PRs based on commit messages and file patterns
- **Existing PR Management**: Detects and updates existing PRs with user confirmation
- **Comprehensive Descriptions**: Auto-generates structured PR descriptions with type classification
- **Issue Integration**: Links PRs to issues using `fixes` and `related` arguments
- **Fork-Aware Operations**: Handles cross-repository PR creation seamlessly

## Usage Examples

```bash
# Basic PR creation with automatic analysis
/git:submit-pr

# PR with issue linking
/git:submit-pr --fixes 123

# Custom title and related issue
/git:submit-pr --title "Add authentication feature" --related 456

# Draft PR against different base
/git:submit-pr --draft true --base develop
```

## Error Scenarios

**GitHub CLI Authentication:**
If GitHub CLI isn't authenticated, the command will fail with clear instructions to run `gh auth login`.

**No Commits Available:**
When the current branch has no commits ahead of the base branch, the command exits with guidance to make commits first.

**Branch Validation:**
Attempting to create PRs from the base branch (e.g., `main`) results in an error with instructions to switch to a feature branch.

**Empty Commits:**
Commits without meaningful changes are detected and command exits with guidance to make substantial changes.

**Merge Conflicts:**
Push failures due to conflicts are detected with instructions to resolve conflicts locally first.

**GitHub API Limits:**
Rate limit errors provide wait time estimates and retry guidance.

**Invalid Branch Names:**
Branch names with special characters or reserved names are validated with correction suggestions.

**Network Issues:**
Remote fetch failures are handled gracefully with fallback behavior where possible, and clear error messages for manual resolution when required.
