---
name: git-pr-reader
description: "Unified interface for GitHub PRs and GitLab MRs: read PR/MR data with file filtering, list changed files, get review comments, post inline review comments, extract line numbers from diffs, validate comments, auto-detect PR/MR for current branch, and get unified diffs. Automatically detects GitHub vs GitLab from URL. Use this skill for analyzing code changes, posting review feedback, and documentation workflows."
author: Gabriel McGoldrick (gmcgoldr@redhat.com)
allowed-tools: Read, Bash, Grep, Glob
---

# Git PR Reader Skill

Unified interface for GitHub Pull Requests and GitLab Merge Requests — read, review, and post comments.

## Capabilities

- **Auto-detect Git platform**: Automatically identifies GitHub vs GitLab from URL
- **Read PR/MR data**: Fetch title, description, and file-level diffs with smart filtering
- **List changed files**: Get file paths, statuses, and line counts with optional glob filtering
- **Review comments**: Fetch existing review comments/discussions, filter bots, include/exclude resolved
- **Post review comments**: Post inline comments on specific diff lines with duplicate detection and fallback to PR-level comments
- **Extract line numbers**: Parse diffs to get added/modified line numbers for accurate comment placement
- **Validate comments**: Check comment line numbers against actual diff content
- **Auto-detect PR/MR**: Find the open PR/MR for the current git branch (GitHub via `gh` CLI, GitLab via API)
- **Smart file filtering**: Exclude irrelevant files using configurable YAML patterns:
  - Test files (test/, *_test.go, *.spec.ts, etc.)
  - Lock files (package-lock.json, *.lock, Pipfile.lock, etc.)
  - CI/CD configs (.gitlab-ci.yml, .github/workflows/, Dockerfile, etc.)
  - Build artifacts (dist/, build/, target/, *.class, etc.)
  - Generated code (*.pb.go, *.gen.go, etc.)
  - Vendor directories (node_modules/, vendor/, etc.)
  - Images and binaries (*.png, *.jpg, *.svg, etc.)

## Usage

### Subcommands

#### read — Read PR/MR data with diffs and file filtering

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py read --url "https://github.com/owner/repo/pull/123"
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py read --url "https://gitlab.com/group/project/-/merge_requests/456" --format markdown
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py read --url "https://github.com/owner/repo/pull/123" --no-filter
```

#### info — Get PR/MR information

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py info https://github.com/owner/repo/pull/123 --json
```

#### files — List changed files

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py files https://github.com/owner/repo/pull/123
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py files https://github.com/owner/repo/pull/123 --filter "*.adoc" --json
```

#### comments — List review comments

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py comments https://github.com/owner/repo/pull/123
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py comments https://github.com/owner/repo/pull/123 --include-resolved --json
```

#### diff — Get unified diff

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py diff https://github.com/owner/repo/pull/123
```

#### post — Post review comments

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py post https://github.com/owner/repo/pull/123 comments.json
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py post https://github.com/owner/repo/pull/123 comments.json --review-type technical
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py post https://github.com/owner/repo/pull/123 comments.json --review-type style --dry-run
```

#### extract — Extract line numbers from diff

```bash
# Find line number for a pattern
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py extract https://github.com/owner/repo/pull/123 path/to/file.adoc "pattern"

# Dump all added/modified lines
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py extract --dump https://github.com/owner/repo/pull/123 path/to/file.adoc

# Validate a comments JSON file against the diff
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py extract --validate https://github.com/owner/repo/pull/123 comments.json
```

#### metadata — Get combined PR/MR metadata

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py metadata https://github.com/owner/repo/pull/123
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py metadata https://gitlab.com/group/project/-/merge_requests/456
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py metadata https://github.com/owner/repo/pull/123 --diff-output /path/to/diff.patch
```

Returns combined metadata: platform, pr_number, title, description, state, author, base_branch, head_branch, labels, commits, changed_files, and url. With `--diff-output`, also saves the unified diff to the specified file.

#### detect — Auto-detect PR/MR for current branch

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py detect
python3 ${CLAUDE_SKILL_DIR}/scripts/git_pr_reader.py detect --json
```

### Authentication

Set in `~/.env` (global) or `.env` in the project root (local override). See docs-tools README for setup:

```bash
GITHUB_TOKEN=your-github-pat    # required scope: "repo" for private, "public_repo" for public
GITLAB_TOKEN=your-gitlab-pat    # required scope: "api"
```

The script loads `.env` files automatically — do **not** prepend `source ~/.env` to bash commands.

### Python Library Usage

```python
from git_pr_reader import GitReviewAPI

api = GitReviewAPI.from_url("https://github.com/owner/repo/pull/123")

# Read PR data with filtering
data = api.get_pr_data()

# Get PR info
info = api.get_pr_info()

# Get changed files
files = api.get_changed_files()

# Get combined metadata (author, labels, commits, files, state)
metadata = api.get_metadata()

# Get review comments
comments = api.get_review_comments()

# Post comments
api.post_comments([
    {"file": "path/to/file.adoc", "line": 42, "message": "Issue description"}
])

# Extract line numbers from diff
lines = api.extract_line_numbers("path/to/file.adoc")

# Validate comments against diff
results = api.validate_comments(comments_list)
```

## Comments JSON Format

```json
[
  {"file": "path/to/file.adoc", "line": 42, "message": "Issue: missing title", "severity": "suggestion"},
  {"file": "path/to/other.adoc", "line": 10, "message": "Typo in description", "severity": "suggestion"}
]
```

## Configuration

File filtering patterns are defined in `config/git_filters.yaml`. You can customize these patterns for your specific needs.

## Dependencies

Install required Python packages:

```bash
python3 -m pip install PyGithub python-gitlab pyyaml pip-system-certs
```

## Integration with Other Skills

This skill works well with:
- **jira-reader**: Combine JIRA issue context with Git code changes
- **jira-writer**: Generate release notes from JIRA + Git data, then push back to JIRA
- **docs-review-style**: Post style review findings as inline PR/MR comments
- **docs-review-technical**: Post technical review findings as inline PR/MR comments

## Limitations

- GitHub API rate limits: 60 requests/hour (unauthenticated), 5000/hour (authenticated)
- GitLab API rate limits: 10 requests/second
- Only fetches file-level diffs, not commit-level history
- Requires public PRs/MRs unless authentication tokens are provided
