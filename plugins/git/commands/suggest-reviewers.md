---
description: Suggest appropriate reviewers for a PR based on git blame and OWNERS files
argument-hint: "[base-branch]"
---

## Name
git:suggest-reviewers

## Synopsis
```
/git:suggest-reviewers [base-branch]
```

## Description
The `git:suggest-reviewers` command analyzes changed files and suggests the most appropriate reviewers for a pull request. It works with both committed changes on feature branches and uncommitted changes (even on the main branch), making it useful before you've created a branch or made any commits. It prioritizes developers who have actually contributed to the code being modified, using git blame data as the primary signal and OWNERS files as supporting information.

The command performs the following analysis:
- Identifies all files changed (both committed and uncommitted changes)
- Runs git blame on changed lines to find recent and frequent contributors
- Searches for OWNERS files in the directories of changed files (and parent directories)
- Aggregates and ranks potential reviewers based on:
  - Frequency and recency of contributions to modified code (highest priority)
  - Presence in OWNERS files (secondary consideration)
- Outputs a prioritized list of suggested reviewers

This command is particularly useful for large codebases with distributed ownership where choosing the right reviewer can be challenging. You can use it at any stage of development - from uncommitted local changes to a complete feature branch ready for PR.

## Implementation

### Step 1: Determine the base branch
- If `base-branch` argument is provided, use it
- Otherwise, detect the main branch (usually `main` or `master`)
- Verify the base branch exists

```bash
# Detect main branch if not provided
git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'
```

### Step 2: Get changed files
- Determine the current branch name
- Detect if we're on the base branch (main/master) or a feature branch
- Detect if there are uncommitted changes (staged or unstaged)
- List all modified, added, or renamed files based on the scenario
- Exclude deleted files (no one to blame)

**Scenario detection:**
```bash
# Get current branch
current_branch=$(git branch --show-current)

# Check if on base branch
if [ "$current_branch" = "$base_branch" ]; then
  on_base_branch=true
else
  on_base_branch=false
fi

# Check for uncommitted changes
has_uncommitted=$(git status --short | grep -v '^??' | wc -l)
```

**Case 1: On base branch (main/master) with uncommitted changes**
```bash
# Get staged changes
git diff --name-only --diff-filter=d --cached

# Get unstaged changes
git diff --name-only --diff-filter=d

# Combine and deduplicate
```

**Case 2: On feature branch with only committed changes**
```bash
# Get all changes from base branch to HEAD
git diff --name-only --diff-filter=d ${base_branch}...HEAD
```

**Case 3: On feature branch with committed + uncommitted changes**
```bash
# Get committed changes
git diff --name-only --diff-filter=d ${base_branch}...HEAD

# Get uncommitted changes
git diff --name-only --diff-filter=d HEAD
git diff --name-only --diff-filter=d --cached

# Combine and deduplicate all files
```

**Case 4: On base branch with no changes**
- Display error: "No changes detected. Please make some changes or switch to a feature branch."

### Step 3: Analyze git blame for changed lines

**IMPORTANT: Use the helper script** `${CLAUDE_PLUGIN_ROOT}/skills/suggest-reviewers/analyze_blame.py` to perform this analysis. Do NOT implement this logic manually.

The script automatically handles:
- Parsing git diff to identify specific line ranges that were modified
- Running git blame on those line ranges (not entire files)
- Extracting and aggregating author information
- Filtering out bot accounts

**For uncommitted changes:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/suggest-reviewers/analyze_blame.py \
  --mode uncommitted \
  --file <file1> \
  --file <file2> \
  --output json
```

**For committed changes on feature branch:**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/suggest-reviewers/analyze_blame.py \
  --mode committed \
  --base-branch ${base_branch} \
  --file <file1> \
  --file <file2> \
  --output json
```

**Output format:**
```json
{
  "Author Name": {
    "line_count": 45,
    "most_recent_date": "2024-10-15T14:23:10",
    "files": ["file1.go", "file2.go"],
    "email": "author@example.com"
  }
}
```

### Step 4: Find OWNERS files
- For each changed file, search for OWNERS files in:
  - The same directory
  - Parent directories up to repository root
- Parse OWNERS files to extract:
  - `approvers`: People who can approve changes
  - `reviewers`: People who can review changes
- OWNERS file format (YAML):
  ```yaml
  approvers:
    - username1
    - username2
  reviewers:
    - username3
    - username4
  ```

### Step 5: Aggregate and rank reviewers
- Combine data from git blame and OWNERS files
- Rank potential reviewers based on weighted scoring:
  1. **Lines contributed** (weight: 10) - More lines modified = better knowledge
  2. **Recency** (weight: 5) - Recent contributions = current knowledge
  3. **OWNERS approver + contributor** (weight: 3 bonus) - Authority + knowledge
  4. **OWNERS reviewer + contributor** (weight: 2 bonus) - Review rights + knowledge
  5. **OWNERS only, no contributions** (weight: 1) - Authority but may lack specific knowledge
- Exclude the current PR author from suggestions
- Filter out bot accounts (e.g., "openshift-bot", "k8s-ci-robot", "*[bot]")
- Normalize scores and sort by total score

### Step 6: Output results
- Display reviewers in ranked order
- Show why each reviewer is suggested (contribution count, recency, OWNERS role)
- Group by priority tiers based on score ranges
- Include GitHub usernames if available
- Show files each reviewer has worked on

## Return Value
- **Claude agent text**: Formatted list of suggested reviewers including:
  - **Primary reviewers**: Major contributors to the modified code
  - **Secondary reviewers**: Moderate contributors or OWNERS with some contributions
  - **Additional reviewers**: OWNERS members or minor contributors
  - Explanation for each suggestion (e.g., "Modified 45 lines across 3 files, last contribution 5 days ago, OWNERS approver")
  - Summary of analysis (files analyzed, OWNERS files found, total lines changed)

## Examples

1. **Basic usage** (auto-detect base branch):
   ```
   /git:suggest-reviewers
   ```
   Output:
   ```
   Analyzed 8 files changed from main (245 lines modified)
   Found 3 OWNERS files

   PRIMARY REVIEWERS:
   - @alice (modified 89 lines across 4 files, last contribution 5 days ago, OWNERS approver)
   - @bob (modified 67 lines in pkg/controller/manager.go, last contribution 2 weeks ago)

   SECONDARY REVIEWERS:
   - @charlie (modified 45 lines across 2 files, last contribution 1 month ago, OWNERS reviewer)
   - @diana (modified 23 lines in pkg/api/handler.go, last contribution 3 weeks ago)

   ADDITIONAL REVIEWERS:
   - @eve (OWNERS approver in pkg/util/, no recent contributions to changed code)

   Recommendation: Add @alice and @bob as reviewers
   ```

2. **Specify base branch**:
   ```
   /git:suggest-reviewers release-4.15
   ```
   Output:
   ```
   Analyzed 3 files changed from release-4.15 (78 lines modified)
   Found 2 OWNERS files

   PRIMARY REVIEWERS:
   - @frank (modified 56 lines in vendor/kubernetes/client.go, last contribution 1 week ago, OWNERS approver)

   SECONDARY REVIEWERS:
   - @grace (modified 12 lines in vendor/kubernetes/types.go, last contribution 2 months ago)
   - @henry (OWNERS reviewer in vendor/kubernetes/, contributed to adjacent code 1 month ago)

   Recommendation: Add @frank as primary reviewer, @grace as optional
   ```

3. **No OWNERS files found**:
   ```
   /git:suggest-reviewers
   ```
   Output:
   ```
   Analyzed 5 files changed from main (156 lines modified)
   No OWNERS files found in modified paths

   SUGGESTED REVIEWERS (based on code contributions):
   - @isabel (modified 89 lines across 4 files, last contribution 5 days ago)
   - @jack (modified 34 lines in src/main.ts, last contribution 10 days ago)
   - @karen (modified 12 lines in src/utils.ts, last contribution 3 months ago)

   Note: No OWNERS files found. Consider consulting team leads for additional reviewers.
   ```

4. **Single file change**:
   ```
   /git:suggest-reviewers
   ```
   Output:
   ```
   Analyzed 1 file changed from main: src/auth/login.ts (34 lines modified)
   Found 1 OWNERS file

   PRIMARY REVIEWERS:
   - @lisa (modified 28 lines, last contribution 3 weeks ago, OWNERS approver)

   SECONDARY REVIEWERS:
   - @mike (modified 6 lines, last contribution 2 months ago, OWNERS reviewer)

   Recommendation: Add @lisa as reviewer
   ```

5. **OWNERS members with no contributions**:
   ```
   /git:suggest-reviewers
   ```
   Output:
   ```
   Analyzed 4 files changed from main (112 lines modified)
   Found 2 OWNERS files

   PRIMARY REVIEWERS:
   - @noah (modified 78 lines across 3 files, last contribution 1 week ago)

   SECONDARY REVIEWERS:
   - @olivia (modified 34 lines in pkg/config/parser.go, last contribution 5 weeks ago)

   ADDITIONAL REVIEWERS:
   - @paul (OWNERS approver in pkg/, no contributions to changed code)
   - @quinn (OWNERS reviewer in pkg/, no contributions to changed code)

   Recommendation: Add @noah as primary reviewer. OWNERS members @paul and @quinn
   may provide approval but consider @noah for technical review.
   ```

6. **Uncommitted changes on main branch**:
   ```
   /git:suggest-reviewers
   ```
   Output:
   ```
   Analyzing uncommitted changes on main branch
   Found 3 modified files (2 staged, 1 unstaged) - 87 lines modified
   Found 1 OWNERS file

   PRIMARY REVIEWERS:
   - @rachel (modified 45 lines across 2 files, last contribution 2 weeks ago, OWNERS approver)
   - @steve (modified 32 lines in src/api/handler.ts, last contribution 1 month ago)

   SECONDARY REVIEWERS:
   - @tina (modified 10 lines in src/utils/format.ts, last contribution 3 months ago)

   Recommendation: Add @rachel and @steve as reviewers

   Note: These are uncommitted changes. Consider creating a feature branch and committing before creating a PR.
   ```

7. **Uncommitted changes on feature branch**:
   ```
   /git:suggest-reviewers
   ```
   Output:
   ```
   Analyzing branch feature/add-logging (includes uncommitted changes)
   - Committed changes from main: 4 files, 156 lines
   - Uncommitted changes: 2 files, 34 lines
   Total: 5 unique files, 190 lines modified
   Found 2 OWNERS files

   PRIMARY REVIEWERS:
   - @uma (modified 98 lines across 3 files, last contribution 1 week ago, OWNERS reviewer)
   - @victor (modified 67 lines in pkg/logger/logger.go, last contribution 2 weeks ago)

   SECONDARY REVIEWERS:
   - @wendy (modified 25 lines in pkg/config/settings.go, last contribution 1 month ago, OWNERS approver)

   Recommendation: Add @uma and @victor as reviewers

   Note: You have uncommitted changes. Consider committing them before creating a PR.
   ```

8. **No changes detected**:
   ```
   /git:suggest-reviewers
   ```
   Output:
   ```
   Error: No changes detected.

   You are on branch 'main' with no uncommitted changes.

   To use this command:
   - Make some changes to files (staged or unstaged), or
   - Switch to a feature branch with committed changes, or
   - Create a new feature branch with: git checkout -b feature/your-feature-name
   ```

## Arguments
- `base-branch` (optional): The base branch to compare against (default: auto-detect main branch, usually `main` or `master`)

## Notes
- The command analyzes both committed and uncommitted changes
- Works on any branch, including main/master (analyzes uncommitted changes in this case)
- For uncommitted changes, git blame is run on HEAD; for committed changes, on the base branch
- OWNERS files must be in YAML format with `approvers` and/or `reviewers` fields
- The current user (detected from git config) is automatically excluded from suggestions
- Reviewers are ranked primarily by their contribution to the specific code being changed
- OWNERS membership provides a bonus but is not the primary ranking factor
- If no reviewers are found via git blame, OWNERS members will be suggested as fallback
- If you're on the base branch with no uncommitted changes, the command will display an error
