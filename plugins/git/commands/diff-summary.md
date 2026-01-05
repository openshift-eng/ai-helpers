---
description: Generate a human-readable summary of changes between branches or commits
argument-hint: "[base] [compare]"
---

## Name
git:diff-summary

## Synopsis
```
/git:diff-summary                    # Compare current branch with main/master
/git:diff-summary [base]             # Compare current branch with [base] branch
/git:diff-summary [base] [compare]   # Compare [base] with [compare] branch/commit
```

## Description
AI-powered command that analyzes git differences and generates a comprehensive, human-readable summary of changes between branches or commits.

**Modes:**
- **Mode 1 (no arguments)** – Compare current branch with `main` or `master`
- **Mode 2 (with base)** – Compare current branch with specified base branch
- **Mode 3 (with base and compare)** – Compare two specific branches or commits

**Use cases:**
- Quickly understand changes before creating a pull request
- Generate PR descriptions with detailed change summaries
- Review what changed between releases or branches
- Understand the scope of work on a feature branch

**Output includes:**
- High-level overview of changes
- Categorized file changes (features, tests, configuration, dependencies, etc.)
- Line count statistics
- Impact assessment
- Key commits included

## Implementation

The command follows these steps:

### 1. Determine Branches to Compare

**Mode 1 (no arguments):**
1. Get current branch: `git branch --show-current`
2. Detect default branch:
   - Check if `main` exists: `git rev-parse --verify main`
   - Fallback to `master`: `git rev-parse --verify master`
   - Error if neither exists
3. Set base=default branch, compare=current branch

**Mode 2 (with base):**
1. Get current branch: `git branch --show-current`
2. Validate base branch exists: `git rev-parse --verify [base]`
3. Set base=[provided], compare=current branch

**Mode 3 (with base and compare):**
1. Validate both references exist:
   - `git rev-parse --verify [base]`
   - `git rev-parse --verify [compare]`
2. Set base=[provided], compare=[provided]

### 2. Collect Git Data

Gather comprehensive information about the differences:

```bash
# Get commit count difference
git rev-list --count [base]..[compare]

# Get commit list
git log [base]..[compare] --oneline

# Get file statistics
git diff [base]...[compare] --stat

# Get numerical stats for analysis
git diff [base]...[compare] --numstat

# Get current status (for Mode 1 only)
git status --short
```

### 3. Analyze Changes

Categorize and analyze the collected data:

1. **Parse file changes** from `--numstat` output:
   - Extract additions/deletions per file
   - Calculate total line changes
   - Identify file types (source code, tests, config, docs, etc.)

2. **Categorize changes** by analyzing file paths and content:
   - **Features** – New functionality in source files
   - **Bug Fixes** – Fixes identified from commit messages
   - **Tests** – Changes in test directories
   - **Documentation** – README, .md files, comments
   - **Configuration** – Build files, CI/CD, manifests
   - **Dependencies** – go.mod/sum, package.json, requirements.txt, vendor/
   - **Refactoring** – Code reorganization without feature changes
   - **Build/CI** – Dockerfile, Makefile, .github/, .tekton/

3. **Assess impact** based on:
   - Number of files changed
   - Total lines added/deleted
   - Critical files modified (APIs, core modules, configs)
   - Test coverage changes

4. **Identify key commits**:
   - Parse commit messages for types (feat, fix, docs, etc.)
   - Group related commits
   - Highlight breaking changes or major features

### 4. Generate Summary Report

Create a structured markdown summary with:

**Header Section:**
```markdown
## Diff Summary: `[compare]` vs `[base]`

**Branch Status:** [X] commits ahead of [base]
```

**Overview Section:**
```markdown
**Overview:**
[2-3 sentence high-level summary of what changed]
```

**Key Changes Section:**
```markdown
### Key Changes

**[Category Name]:**
- `file/path` - **+X/-Y** - Description of change
```

Group by categories identified in step 3. For each significant file:
- Show file path
- Show additions/deletions
- Provide brief description of what changed

**Files Modified Section:**
```markdown
### Files Modified ([total] files, +[added]/-[deleted] lines)

**[Category]** ([count] files):
- `path/to/file1` - **+X/-Y**
- `path/to/file2` - **+X/-Y**
```

**Impact Assessment:**
```markdown
**Impact:** [Low|Medium|High] risk - [explanation]
```

Risk levels:
- **Low**: <5 files, <100 lines, only tests/docs
- **Medium**: 5-20 files, 100-500 lines, some source changes
- **High**: >20 files, >500 lines, core/API changes

**Commit History (optional):**
```markdown
### Commits Included ([count] commits)

- `[hash]` [commit message]
- `[hash]` [commit message]
```

Limit to 10 most recent commits if more than 10.

### 5. Display and Copy Options

1. Display the formatted summary to the user
2. Optionally copy to clipboard or save to file if requested
3. Suggest using the summary for PR description

## Examples

```bash
# Compare current branch with main
/git:diff-summary

# Compare current branch with release-1.0
/git:diff-summary release-1.0

# Compare two specific branches
/git:diff-summary main feature/new-api

# Compare commits
/git:diff-summary abc123 def456
```

## Return Value

**Format:** Markdown-formatted summary report

**Structure:**
```markdown
## Diff Summary: `[compare]` vs `[base]`

**Branch Status:** X commits ahead of [base]

**Overview:**
[High-level summary]

### Key Changes

**[Category]:**
- Change descriptions

### Files Modified (X files, +Y/-Z lines)

**[Category]** (count):
- File listings

**Impact:** [Assessment]

### Commits Included ([count])
- Commit list (if ≤10 commits)
```

## Arguments

- **[base]** (optional): Base branch or commit to compare against
  - If omitted: Defaults to `main` or `master`
  - Examples: `main`, `release-1.0`, `abc123def`

- **[compare]** (optional): Branch or commit to compare
  - If omitted: Uses current branch
  - Examples: `feature/new-api`, `def456abc`

