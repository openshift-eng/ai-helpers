---
name: search-issues
description: Search GitHub issues across configured repositories. Supports searching issue titles, bodies, and comments. Use for finding bugs, errors, or discussions.
allowed-tools:
  - Bash(gh search:*)
  - Bash(gh issue:*)
  - Bash(gh api:*)
  - Bash(cat ~/.claude/skills/search-issues/repos.txt)
  - Read
  - Edit
---

# GitHub Issue Search Command

## Configuration
Default repositories are stored in: `~/.claude/skills/search-issues/repos.txt`

## Command Usage

### Search issues
```
/search-issues <query>
```
Searches all configured repositories for issues matching the query.

### Search with options
```
/search-issues <query> --state=open|closed|all --repo=owner/repo
```
- `--state=open` - only open issues (default: all)
- `--state=closed` - only closed issues
- `--state=all` - both open and closed
- `--repo=owner/repo` - search only this repo (overrides defaults)

### Show configured repositories
```
/search-issues --list-repos
```
Displays all repositories currently configured for searching.

### Add a repository
```
/search-issues --add-repo owner/repo
```
Adds a new repository to the default search list.

### Remove a repository
```
/search-issues --remove-repo owner/repo
```
Removes a repository from the default search list.

## Execution Instructions

### For --list-repos
1. Read `~/.claude/skills/search-issues/repos.txt`
2. Display the repositories in a formatted list

### For --add-repo
1. Read current repos.txt
2. Append the new repository
3. Confirm the addition

### For --remove-repo
1. Read current repos.txt
2. Remove the specified repository line
3. Confirm the removal

### For search queries
1. First, read `~/.claude/skills/search-issues/repos.txt` to get default repos
2. Build repo flags: `--repo=REPO1 --repo=REPO2 ...` (skip commented lines)
3. Run the search:
```bash
gh search issues "QUERY" --repo=REPO1 --repo=REPO2 --state=STATE --limit=30 --json number,title,state,repository,updatedAt,url
```
4. If user wants to search comments too, also run:
```bash
gh api search/issues -X GET -f q="QUERY repo:REPO in:comments" --jq '.items[] | {number, title, state, html_url}'
```
5. Present results as a table:
   - Issue number (with URL)
   - Status (open/closed)
   - Repository
   - Title

### For viewing issue details
```bash
gh issue view NUMBER --repo=OWNER/REPO --comments
```

## Examples
- `/search-issues reconciler error` - search all default repos, all states
- `/search-issues memory leak --state=open` - only open issues
- `/search-issues --list-repos` - show configured repos
- `/search-issues --add-repo kubernetes/kubernetes` - add new repo