---
name: Suggest Reviewers Helper
description: Git blame analysis helper for the suggest-reviewers command
---

# Suggest Reviewers Helper

This skill provides a Python helper script that analyzes git blame data for the `/git:suggest-reviewers` command. The script handles the complex task of identifying which lines were changed and who authored the original code.

## When to Use This Skill

Use this skill when implementing the `/git:suggest-reviewers` command. The helper script should be invoked during Step 3 of the command implementation (analyzing git blame for changed lines).

**DO NOT implement git blame analysis manually** - always use the provided `analyze_blame.py` script.

## Prerequisites

- Python 3.6 or higher
- Git repository with commit history
- Git CLI available in PATH

## Helper Script: analyze_blame.py

The `analyze_blame.py` script automates the complex process of:
1. Parsing git diff output to identify specific line ranges that were modified
2. Running git blame on only the changed line ranges (not entire files)
3. Extracting and aggregating author information with statistics
4. Filtering out bot accounts automatically

### Usage

**For uncommitted changes:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/suggest-reviewers/analyze_blame.py \
  --mode uncommitted \
  --file path/to/file1.go \
  --file path/to/file2.py \
  --output json
```

**For committed changes on a feature branch:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/suggest-reviewers/analyze_blame.py \
  --mode committed \
  --base-branch main \
  --file path/to/file1.go \
  --file path/to/file2.py \
  --output json
```

### Parameters

- `--mode`: Required. Either `uncommitted` or `committed`
  - `uncommitted`: Analyzes unstaged/staged changes against HEAD
  - `committed`: Analyzes committed changes against a base branch

- `--base-branch`: Required when mode is `committed`. The base branch to compare against (e.g., `main`, `master`)

- `--file`: Can be specified multiple times. Each file to analyze for blame information. Only changed files should be passed.

- `--output`: Output format. Default is `json`. Options:
  - `json`: Machine-readable JSON output
  - `text`: Human-readable text output

### Output Format (JSON)

```json
{
  "Author Name": {
    "line_count": 45,
    "most_recent_date": "2024-10-15T14:23:10",
    "files": ["file1.go", "file2.go"],
    "email": "author@example.com"
  },
  "Another Author": {
    "line_count": 23,
    "most_recent_date": "2024-09-20T09:15:33",
    "files": ["file3.py"],
    "email": "another@example.com"
  }
}
```

### Output Fields

- `line_count`: Total number of modified lines authored by this person
- `most_recent_date`: ISO 8601 timestamp of their most recent contribution to the changed code
- `files`: Array of files where this author has contributions in the changed lines
- `email`: Author's email address from git commits

### Bot Filtering

The script automatically filters out common bot accounts:
- GitHub bots (e.g., `dependabot[bot]`, `renovate[bot]`)
- CI bots (e.g., `openshift-ci-robot`, `k8s-ci-robot`)
- Generic bot patterns (any name containing `[bot]` or ending in `-bot`)

## Implementation Steps

### Step 1: Collect changed files

Before invoking the script, collect the list of changed files based on the scenario:

**Uncommitted changes:**
```bash
# Get staged and unstaged files
files=$(git diff --name-only --diff-filter=d HEAD)
files+=" $(git diff --name-only --diff-filter=d --cached)"
```

**Committed changes:**
```bash
# Get files changed from base branch
files=$(git diff --name-only --diff-filter=d ${base_branch}...HEAD)
```

### Step 2: Invoke the script

Build the command with the appropriate mode and all changed files:

```bash
# Start building the command
cmd="python3 ${CLAUDE_PLUGIN_ROOT}/skills/suggest-reviewers/analyze_blame.py"

# Add mode
if [ "$has_uncommitted" = true ] || [ "$on_base_branch" = true ]; then
  cmd="$cmd --mode uncommitted"
else
  cmd="$cmd --mode committed --base-branch $base_branch"
fi

# Add each file
for file in $files; do
  cmd="$cmd --file $file"
done

# Add output format
cmd="$cmd --output json"

# Execute and capture JSON output
blame_data=$($cmd)
```

### Step 3: Parse the output

The JSON output can be parsed using Python, jq, or any JSON parser:

```bash
# Example using jq to get top contributor
echo "$blame_data" | jq -r 'to_entries | sort_by(-.value.line_count) | .[0].key'

# Example using Python
python3 << EOF
import json
import sys

data = json.loads('''$blame_data''')

# Sort by line count
sorted_authors = sorted(data.items(), key=lambda x: x[1]['line_count'], reverse=True)

for author, stats in sorted_authors:
    print(f"{author}: {stats['line_count']} lines, last modified {stats['most_recent_date']}")
EOF
```

### Step 4: Combine with OWNERS data

After getting blame data, merge it with OWNERS file information to produce the final ranked list of reviewers.

## Error Handling

### No changed files

If no files are passed to the script:
```
Error: No files specified. Use --file option at least once.
```

**Resolution:** Ensure you've detected changed files correctly before invoking the script.

### Invalid mode

If an invalid mode is specified:
```
Error: Invalid mode 'invalid'. Must be 'uncommitted' or 'committed'.
```

**Resolution:** Use either `--mode uncommitted` or `--mode committed`.

### Missing base branch in committed mode

If `--mode committed` is used without `--base-branch`:
```
Error: --base-branch is required when mode is 'committed'.
```

**Resolution:** Provide the base branch: `--base-branch main`

### File not in repository

If a specified file is not tracked by git:
```
Warning: File 'path/to/file' is not tracked by git, skipping.
```

**Resolution:** This is a warning and can be safely ignored. The script will skip untracked files.

### No blame data found

If git blame returns no data for any files:
```json
{}
```

**Resolution:** This can happen if:
- All changed files are newly created (no blame history)
- All changes are in binary files
- Git blame is unable to run

In this case, fall back to OWNERS-only suggestions.

## Examples

### Example 1: Analyze uncommitted changes

```bash
$ python3 analyze_blame.py --mode uncommitted --file src/main.go --file src/utils.go --output json
{
  "Alice Developer": {
    "line_count": 45,
    "most_recent_date": "2024-10-15T14:23:10",
    "files": ["src/main.go", "src/utils.go"],
    "email": "alice@example.com"
  },
  "Bob Engineer": {
    "line_count": 12,
    "most_recent_date": "2024-09-20T09:15:33",
    "files": ["src/main.go"],
    "email": "bob@example.com"
  }
}
```

### Example 2: Analyze committed changes on feature branch

```bash
$ python3 analyze_blame.py --mode committed --base-branch main --file pkg/controller/manager.go --output json
{
  "Charlie Contributor": {
    "line_count": 78,
    "most_recent_date": "2024-10-01T11:42:55",
    "files": ["pkg/controller/manager.go"],
    "email": "charlie@example.com"
  }
}
```

### Example 3: Text output format

```bash
$ python3 analyze_blame.py --mode uncommitted --file README.md --output text

Blame Analysis Results:
=======================

Alice Developer (alice@example.com)
  Lines: 23
  Most recent: 2024-10-15T14:23:10
  Files: README.md

Bob Engineer (bob@example.com)
  Lines: 5
  Most recent: 2024-08-12T16:30:21
  Files: README.md
```

### Example 4: Multiple files with mixed results

```bash
$ python3 analyze_blame.py --mode committed --base-branch release-4.15 \
    --file vendor/k8s.io/client-go/kubernetes/clientset.go \
    --file pkg/controller/node.go \
    --file docs/README.md \
    --output json
{
  "Diana Developer": {
    "line_count": 156,
    "most_recent_date": "2024-09-28T13:15:42",
    "files": ["vendor/k8s.io/client-go/kubernetes/clientset.go", "pkg/controller/node.go"],
    "email": "diana@example.com"
  },
  "Eve Technical Writer": {
    "line_count": 34,
    "most_recent_date": "2024-10-10T10:22:18",
    "files": ["docs/README.md"],
    "email": "eve@example.com"
  }
}
```

## Technical Details

### How the script works

1. **Determine diff range**: Based on mode, calculates what to compare:
   - `uncommitted`: Compares working directory against HEAD
   - `committed`: Compares HEAD against base branch

2. **Parse diff output**: Runs `git diff` with unified format to identify:
   - Which files changed
   - Which line ranges were added/modified
   - Ignores deleted lines (can't blame what doesn't exist)

3. **Run git blame**: For each file and line range:
   - Runs `git blame -L start,end --line-porcelain file`
   - Parses porcelain format to extract author, email, and timestamp
   - Aggregates data across all changed lines

4. **Filter and aggregate**:
   - Removes bot accounts
   - Groups by author name
   - Counts total lines per author
   - Tracks most recent contribution date
   - Lists all files each author contributed to

5. **Output results**: Formats as JSON or text based on `--output` parameter

### Performance considerations

- Only blames changed line ranges, not entire files (much faster for small changes to large files)
- Processes files in parallel when possible
- Caches git commands where appropriate
- Skips binary files automatically

## Limitations

- Does not handle file renames/moves (treats as delete + add)
- Bot filtering is based on common patterns; custom bots may not be filtered
- Requires git history; newly initialized repos may not have useful data
- Does not consider commit message content or PR review history

## See Also

- Main command: `/git:suggest-reviewers` in `plugins/git/commands/suggest-reviewers.md`
- Git blame documentation: https://git-scm.com/docs/git-blame
- Git diff documentation: https://git-scm.com/docs/git-diff
