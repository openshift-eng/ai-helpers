---
description: Compare rebase commits (commits with the same message) between current branch and master
argument-hint: <commit-message>
---

## Name
openshift:rb-compare

## Synopsis
```
/openshift:rb-compare <commit-message>
```

## Description

The `openshift:rb-compare` command compares the contents of the latest commit with a given message on the current branch against the latest commit with the same message on the master branch. This is useful for validating cherry-picked commits during a rebase to ensure they were applied consistently.

The command:

- Searches for commits by comparing the first line of commit messages
- Identifies whether the commits are identical
- If not identical, uses AI analysis to understand and compare what each commit achieves
- Determines logical equivalence by interpreting the intent and outcome of each commit, not just textual similarity

## Arguments

- **commit-message** (required): The commit message (or substring) to search for
  - Only the first line of each commit message is matched
  - Can be a substring (e.g., "UPSTREAM: <carry>: Add OpenShift files")

## Prerequisites

Before using this command, ensure:

1. **Git repository**: You must be in a valid Git repository
   - Verify with: `git status`

2. **Clean working directory** (recommended): Command works on committed changes only
   - Check with: `git status`

3. **Master branch exists**: The repository must have a master branch
   - If your repository uses `main` instead, the command will detect and use it

4. **Branches are up to date** (recommended): For accurate comparison
   - Update with: `git fetch origin`

## Implementation

### 1. Determine Main Branch Name

First, detect whether the repository uses `master` or `main`:

```bash
if git rev-parse --verify master >/dev/null 2>&1; then
    MAIN_BRANCH="master"
elif git rev-parse --verify main >/dev/null 2>&1; then
    MAIN_BRANCH="main"
else
    echo "Error: Neither 'master' nor 'main' branch exists"
    exit 1
fi
```

### 2. Get Current Branch Name

Determine the current branch:

```bash
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [ "$CURRENT_BRANCH" = "$MAIN_BRANCH" ]; then
    echo "Warning: You are currently on $MAIN_BRANCH branch"
    echo "This command compares commits between different branches"
    echo "Please checkout a feature branch first"
    exit 1
fi

echo "Comparing commits between '$CURRENT_BRANCH' and '$MAIN_BRANCH'"
```

### 3. Find Commits with Matching Message

Search for the latest commit with the given message on both branches:

```bash
COMMIT_MESSAGE="$1"

# Find latest commit on current branch (only match first line)
CURRENT_COMMIT=$(git log --oneline --grep="^$COMMIT_MESSAGE" --all-match --format="%H" -n 1 HEAD)

# Find latest commit on main branch (only match first line)
MAIN_COMMIT=$(git log --oneline --grep="^$COMMIT_MESSAGE" --all-match --format="%H" -n 1 "$MAIN_BRANCH")

if [ -z "$CURRENT_COMMIT" ]; then
    echo "Error: No commit found with message '$COMMIT_MESSAGE' on current branch ($CURRENT_BRANCH)"
    exit 1
fi

if [ -z "$MAIN_COMMIT" ]; then
    echo "Error: No commit found with message '$COMMIT_MESSAGE' on $MAIN_BRANCH branch"
    exit 1
fi
```

### 4. Display Commit Information

Show the commits being compared:

```bash
echo ""
echo "Current branch ($CURRENT_BRANCH):"
echo "  Commit: $CURRENT_COMMIT"
git log -1 --pretty=format:"  Author: %an <%ae>%n  Date:   %ad%n  Message: %s%n" "$CURRENT_COMMIT"

echo ""
echo "$MAIN_BRANCH branch:"
echo "  Commit: $MAIN_COMMIT"
git log -1 --pretty=format:"  Author: %an <%ae>%n  Date:   %ad%n  Message: %s%n" "$MAIN_COMMIT"
echo ""
```

### 5. Check if Commits are Identical

First, check if the commits are exactly the same:

```bash
if [ "$CURRENT_COMMIT" = "$MAIN_COMMIT" ]; then
    echo "✅ Result: The commits are identical (same commit SHA)"
    echo "   This means both branches point to the exact same commit."
    exit 0
fi
```

### 6. Compare Commit Contents

If commits are different, compare their contents:

```bash
echo "Comparing commit contents..."
echo ""

# Get the diff between the two commits
# We're interested in the changes introduced by each commit, not the commits themselves
# So we compare each commit with its parent

# Create temporary directory for comparison
WORK_DIR=".work/rb-compare"
mkdir -p "$WORK_DIR"

# Get the diff for current branch commit
git show "$CURRENT_COMMIT" > "$WORK_DIR/current.diff"

# Get the diff for main branch commit
git show "$MAIN_COMMIT" > "$WORK_DIR/main.diff"

# Compare the diffs
if diff -q "$WORK_DIR/current.diff" "$WORK_DIR/main.diff" > /dev/null 2>&1; then
    echo "✅ Result: The commits are EXACTLY THE SAME"
    echo "   Both commits introduce identical changes (byte-for-byte match)"
    rm -rf "$WORK_DIR"
    exit 0
fi
```

### 7. Analyze Differences

If the commits differ, analyze what's different:

```bash
echo "❌ Result: The commits are NOT byte-for-byte identical"
echo ""
echo "Analyzing differences..."
echo ""

# Show a summary of what files were changed in each commit
echo "Files changed in current branch commit ($CURRENT_BRANCH):"
git show --stat "$CURRENT_COMMIT" | tail -n +2

echo ""
echo "Files changed in $MAIN_BRANCH branch commit:"
git show --stat "$MAIN_COMMIT" | tail -n +2

# Create a diff showing the differences between the two commits
echo ""
echo "Detailed comparison:"
echo "===================="

# Compare the actual changes
diff -u "$WORK_DIR/main.diff" "$WORK_DIR/current.diff" > "$WORK_DIR/comparison.diff" || true

# Show the comparison
if [ -s "$WORK_DIR/comparison.diff" ]; then
    echo ""
    echo "Differences between the commits:"
    cat "$WORK_DIR/comparison.diff"
    echo ""
fi
```

### 8. AI-Based Logical Equivalence Assessment

Use AI to analyze and interpret whether the commits achieve the same thing:

At this point, you have:
- `$WORK_DIR/current.diff` - full diff of the commit on the current branch
- `$WORK_DIR/main.diff` - full diff of the commit on the main branch
- Knowledge that the diffs are not byte-for-byte identical

**Your task**: Analyze both commits using AI to determine if they are logically equivalent.

**Analysis approach**:

1. **Read both commit diffs** to understand what each commit does
   - Read `$WORK_DIR/current.diff` using the Read tool
   - Read `$WORK_DIR/main.diff` using the Read tool

2. **Interpret the commits**:
   - What is the purpose of each commit?
   - What files are being modified?
   - What specific changes are being made?
   - What is the intended outcome or effect of each commit?

3. **Compare the semantic meaning**:
   - Do both commits accomplish the same goal?
   - Are the code changes functionally equivalent?
   - If there are differences, are they:
     - Due to different base branch states (e.g., different line numbers, surrounding code)?
     - Due to different formatting or whitespace?
     - Due to different but equivalent implementations?
     - Actual functional differences that change behavior?

4. **Consider context-specific factors**:
    - UPSTREAM carries that adapt to different base versions
    - Vendor directory updates that may differ due to dependency resolution
    - Generated files that may vary by tool version
    - Configuration files that may have branch-specific values
    - Automated formatting differences
    - Branch-specific adaptations (e.g., API versions, import paths)
    - Context-dependent changes that achieve the same result

5. **Provide detailed assessment**:

Display:
```
Logical Equivalence Assessment (AI Analysis):
=============================================

[Your analysis here - include:]
- Summary of what each commit does
- Key differences identified
- Whether differences are semantic or superficial
- Final verdict: LOGICALLY EQUIVALENT or NOT LOGICALLY EQUIVALENT
- Detailed reasoning for your conclusion
```

**Assessment criteria**:

- ✅ **LOGICALLY EQUIVALENT** if:
  - Both commits achieve the exact same functional outcome
  - Differences are only due to formatting, whitespace, or base branch state
  - Any code differences are semantically identical (e.g., `if (x)` vs `if x:` in different languages)
  - Changes adapt to branch-specific context but accomplish the same goal

- ❌ **NOT LOGICALLY EQUIVALENT** if:
  - Commits modify fundamentally different sets of files
  - Functional changes differ in behavior or effect
  - One commit includes changes not present in the other
  - The intended outcome or purpose differs

**Example output format**:

```
Logical Equivalence Assessment (AI Analysis):
=============================================

Commit on current branch (release-4.21):
  - Modifies Dockerfile to update base image from ubi8:8.8 to ubi8:8.9
  - Updates OWNERS to add new approver "user@example.com"
  - Updates go.mod to use golang 1.21

Commit on master branch:
  - Modifies Dockerfile to update base image from ubi8:8.7 to ubi8:8.9
  - Updates OWNERS to add new approver "user@example.com"
  - Updates go.mod to use golang 1.21

Key differences:
  - Dockerfile: Different starting base image version (8.8 vs 8.7) due to different branch states
  - Both arrive at the same final state: ubi8:8.9

Assessment: ✅ LOGICALLY EQUIVALENT

Reasoning: Both commits accomplish the same goal - updating the base image to ubi8:8.9,
adding the same approver, and updating to golang 1.21. The difference in the starting
base image version is due to the different branch states (release-4.21 already had 8.8
while master had 8.7). The functional outcome is identical: both branches now use ubi8:8.9.
```

After providing the analysis, clean up:
```bash
rm -rf "$WORK_DIR"
```

## Examples

### Example 1: Compare robot backport commits

```bash
/openshift:rb-compare "UPSTREAM: <carry>: Add OpenShift files"
```

Output:
```
Comparing commits between 'release-4.21' and 'master'

Current branch (release-4.21):
  Commit: a1b2c3d4e5f6
  Author: Robot <robot@example.com>
  Date:   Mon Oct 30 10:00:00 2025
  Message: UPSTREAM: <carry>: Add OpenShift files

master branch:
  Commit: f6e5d4c3b2a1
  Author: Robot <robot@example.com>
  Date:   Mon Oct 30 09:00:00 2025
  Message: UPSTREAM: <carry>: Add OpenShift files

Comparing commit contents...

❌ Result: The commits are NOT exactly the same

Analyzing differences...

Files changed in current branch commit (release-4.21):
 Dockerfile | 2 +-
 OWNERS     | 1 +
 2 files changed, 2 insertions(+), 1 deletion(-)

Files changed in master branch commit:
 Dockerfile | 2 +-
 OWNERS     | 1 +
 2 files changed, 2 insertions(+), 1 deletion(-)

Logical Equivalence Assessment (AI Analysis):
=============================================

Commit on current branch (release-4.21):
  - Modifies Dockerfile to update base image reference
  - Adds new approver to OWNERS file

Commit on master branch:
  - Modifies Dockerfile to update base image reference
  - Adds new approver to OWNERS file

Key differences:
  - Dockerfile has different line numbers for the base image change (line 5 vs line 4)
  - This is due to release-4.21 having an additional comment line not present in master

Assessment: ✅ LOGICALLY EQUIVALENT

Reasoning: Both commits achieve identical functional outcomes. The Dockerfile changes
update the same base image to the same version, just at different line numbers due to
branch-specific differences in surrounding code. The OWNERS file receives the same
approver addition in both commits. The commits accomplish exactly the same goal despite
minor contextual differences in their base branches.
```

### Example 2: Comparing with a substring match

```bash
/openshift:rb-compare "vendor: bump"
```

This will find the latest commit whose first line contains "vendor: bump".

### Example 3: Commits are identical

```bash
/openshift:rb-compare "Fix authentication bug"
```

Output:
```
Comparing commits between 'feature-branch' and 'master'

Current branch (feature-branch):
  Commit: abc123
  Author: Developer <dev@example.com>
  Date:   Tue Oct 31 14:00:00 2025
  Message: Fix authentication bug

master branch:
  Commit: abc123
  Author: Developer <dev@example.com>
  Date:   Tue Oct 31 14:00:00 2025
  Message: Fix authentication bug

✅ Result: The commits are identical (same commit SHA)
   This means both branches point to the exact same commit.
```

## Return Value

The command exits with different codes based on findings:

- **Exit 0**: Comparison completed successfully (whether commits are identical or not)
- **Exit 1**: Error occurred (commit not found, not in a git repo, on main branch, etc.)

**Output Format**:
- Commit metadata (SHA, author, date, message)
- Comparison results with visual indicators (✅ ❌ ⚠️)
- Logical equivalence assessment
- Detailed file-by-file comparison when commits differ

## Common Use Cases

### Robot Backport Validation

When robot automation creates backport commits across multiple branches:

```bash
git checkout release-4.21
/openshift:rb-compare "UPSTREAM: <carry>: Add OpenShift files"
```

This validates that the backport was applied correctly.

### Dependency Update Verification

After running dependency updates on multiple branches:

```bash
/openshift:rb-compare "vendor: bump dependencies"
```

Ensures the same dependencies were updated across branches.

### Cherry-pick Validation

After cherry-picking a commit to another branch:

```bash
/openshift:rb-compare "Fix CVE-2024-1234"
```

Confirms the fix was applied identically.

## Notes

- The command compares commit **contents**, not commit metadata (author, date, etc.)
- Only the first line of commit messages is used for matching
- Grep patterns are used, so regex special characters in the message should be escaped
- **AI-powered analysis**: The command uses AI to interpret and understand what each commit achieves, not just textual comparison
- Commits with the same SHA are always considered identical
- For commits with different SHAs, AI analyzes the semantic meaning and functional outcome of each commit
- The AI assessment considers context such as different base branch states, formatting variations, and OpenShift-specific patterns
- Logical equivalence is determined by whether commits achieve the same functional outcome, not whether they are textually similar
