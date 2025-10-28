---
description: Generate Conventional Commits style commit messages or summarize existing commits
argument-hint: [N]
---

## Name
git:commit-suggest

## Synopsis
```
/git:commit-suggest       # Analyze staged changes
/git:commit-suggest [N]     # Analyze last N commits (1-100)
```

## Description
AI-powered command that analyzes code changes and generates Conventional Commits–style messages.

**Modes:**
- **Mode 1 (no argument)** – Analyze staged changes (`git add` required)
- **Mode 2 (with N)** – Analyze last N commits to rewrite (N=1) or summarize for squash (N≥2)

**Use cases:**
- Create standardized commit messages
- Improve or rewrite existing commits
- Generate squash messages for PR merges

**Difference from `/git:summary`** – That command is read-only, while `git:commit-suggest` generates actionable commit message suggestions for user review and manual use.

## Implementation

The command operates in two modes based on input:

**Mode 1 (no argument):**
1. Collect staged changes via `git diff --cached`
2. Analyze file paths and code content to identify type (feat/fix/etc.) and scope
3. Generate 3 commit message suggestions (Recommended, Standard, Minimal)
4. Display formatted suggestions and prompt user for selection
   - Ask: "Which suggestion would you like to use? (1/2/3 or skip)"
   - Support responses: `1`, `use option 2`, `commit with option 3`, `skip`
   - Execute `git commit` with selected message if user requests

**Mode 2 (with N):**
1. Retrieve last N commits using `git log`
2. Parse commit messages to extract types, scopes, and descriptions
3. For **N=1**: Suggest improved rewrite
   For **N≥2**: Merge commits intelligently by type priority (`fix > feat > perf > refactor > docs > test > chore`)
4. Generate 3 commit message suggestions (Recommended, Standard, Minimal)
5. Display formatted suggestions and prompt user for selection
   - Ask: "Which suggestion would you like to use? (1/2/3 or skip)"
   - Support responses: `1`, `use option 2`, `amend with option 3`, `skip`
   - Execute `git commit --amend` (N=1) or squash operation (N≥2) if user requests

## Examples

```bash
# Generate message for staged files
git add src/auth.ts src/middleware.ts
/git:commit-suggest

# Rewrite last commit message
/git:commit-suggest 1

# Summarize last 5 commits for squash
/git:commit-suggest 5
```

## Return Value

Generates 3 commit message suggestions:
- **Suggestion #1 (Recommended)** – Detailed with full body and metadata
- **Suggestion #2 (Standard)** – Concise with main points
- **Suggestion #3 (Minimal)** – Title and short summary

Each suggestion includes:
- Conventional Commits message (`type(scope): description`)
- Blank line between title and body
- Optional body text explaining the changes
- Optional footer (issue refs, co-authors, breaking changes, etc.)

**Example:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Suggestion #1 (Recommended)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
feat(auth): add JWT authentication middleware

Implement token-based authentication for API endpoints.
The middleware verifies JWT tokens and extracts user information.

Fixes: #123

Which suggestion would you like to use? (1/2/3 or skip)
```

### Mode 2 Specifics

- **N=1** – Suggest improved rewrite for the last commit
- **N≥2** – Generate unified squash message with footer: `Squashed from N commits:` + original commit list

## Conventional Commits Reference

### Format
```
type(scope): description

[optional body]

[optional footer]
```

### Common Types
- `feat` – New feature
- `fix` – Bug fix
- `docs` – Documentation changes
- `refactor` – Code refactoring
- `perf` – Performance improvements
- `test` – Test additions or modifications
- `build` – Build system or dependency changes
- `ci` – CI configuration changes
- `chore` – Other changes that don't modify src or test files

### Scope & Footer Examples

**Scope**: `auth`, `api`, `ui`, `db`, `deps` (indicates affected module)

**Footer**:
- Issue refs: `Fixes: #123`, `Closes: #456`, `Related: #789`
- Breaking changes: `BREAKING CHANGE: description`
- Co-authors: `Co-authored-by: Name <email@example.com>`

## Arguments

- **[N]** (optional): Number of recent commits to analyze (1-100)
  - If omitted: Analyzes staged changes (Mode 1)
  - If N=1: Suggests improved rewrite for the last commit
  - If N≥2: Generates unified squash message for last N commits

## See Also
- **`/git:summary`** – Display repository status and recent commits (read-only)
- [Conventional Commits Specification](https://www.conventionalcommits.org/)
