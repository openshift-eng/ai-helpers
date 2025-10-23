---
description: Analyze technical debt indicators in the repository
argument-hint:
---

## Name
git:debt-scan

## Synopsis
```
/git:debt-scan
```

## Description
The `git:debt-scan` command provides a comprehensive analysis of technical debt indicators in the current Git repository. It scans for common code health signals including TODO/FIXME comments, stale branches, large files, uncommitted changes, and recent development activity patterns. This command is designed to give developers quick insights into areas that may need attention without making any modifications to the repository.

It provides essential information for developers including:
- Count and locations of TODO, FIXME, HACK, and XXX comments
- Stale branches tracking openshift org remotes that may need cleanup (excludes main, master, develop, release-*, gh-pages, local-only branches, and personal forks)
- Large git-tracked files that might benefit from refactoring
- Uncommitted or unstaged changes
- Recent commit activity trends

The spec sections is inspired by https://man7.org/linux/man-pages/man7/man-pages.7.html#top_of_page

## Implementation
- Executes multiple analysis commands to gather technical debt indicators
- Searches codebase for technical debt comments (TODO, FIXME, HACK, XXX)
- Identifies stale branches tracking openshift org GitHub remotes (excludes main, master, develop, release-*, gh-pages, local-only branches, and personal forks)
- Verifies branches still exist on upstream remote to avoid false positives
- Finds large git-tracked files that may need refactoring
- Shows uncommitted changes
- Analyzes recent commit patterns
- Formats output for clear readability
- All operations are read-only with no side effects

Implementation logic:
```bash
# Search for technical debt comments
echo "=== Technical Debt Comments ==="
FILE_PATTERNS="*.{js,ts,go,py,java,rb,c,cpp,h,hpp,cs,php,swift,kt}" && for marker in TODO FIXME HACK XXX; do echo "$marker comments: $(grep -r "$marker" --include="$FILE_PATTERNS" . 2>/dev/null | grep -v '.git/' | wc -l | xargs)"; done

# Show top 10 files with most debt comments
echo -e "\n=== Files with Most Debt Comments ==="
grep -r 'TODO\|FIXME\|HACK\|XXX' --include="*.{js,ts,go,py,java,rb,c,cpp,h,hpp,cs,php,swift,kt}" . 2>/dev/null | grep -v '.git/' | cut -d: -f1 | sort | uniq -c | sort -rn | head -10

# Check for stale branches on openshift remotes (excluding main, master, release branches)
echo -e "\n=== Stale Branches (not updated in 30+ days) ===" && bash -c 'OPENSHIFT_REMOTES=$(git remote -v | grep -E "github\.com[:/]openshift/" | grep fetch | awk "{print \$1}" | sort -u); if [ -z "$OPENSHIFT_REMOTES" ]; then echo "(No openshift GitHub remotes found)"; else for remote in $OPENSHIFT_REMOTES; do git ls-remote --heads "$remote" | awk "{print \$2}" | sed "s|refs/heads/||" | grep -vE "^(main|master|develop|release-.*|gh-pages)$" | while read branch; do commit_info=$(git log -1 --format="%cr|%an" "$remote/$branch" 2>/dev/null || echo ""); if [ -n "$commit_info" ]; then date=$(echo "$commit_info" | cut -d"|" -f1); author=$(echo "$commit_info" | cut -d"|" -f2); echo "$date" | grep -qE "years? ago|months? ago|[4-9] weeks ago|[0-9]{2,} weeks ago" && echo "$branch - Last commit: $date by $author"; fi; done | head -10; done; fi'

# Find large files (only git-tracked files)
echo -e "\n=== Large Files (>1MB, tracked by git) ==="
git ls-files | xargs ls -lh 2>/dev/null | awk '$5 ~ /M$/ && $5+0 > 1 {print $9 " - " $5}' | head -10

# Check uncommitted changes
echo -e "\n=== Uncommitted Changes ==="
git status --porcelain | head -20

# Recent commit activity
echo -e "\n=== Commit Activity ===" && echo "Commits in last week: $(git log --since='1 week ago' --oneline 2>/dev/null | wc -l | xargs)" && echo "Commits in last month: $(git log --since='1 month ago' --oneline 2>/dev/null | wc -l | xargs)" && bash -c 'count=$(git log --since="30 days ago" --oneline 2>/dev/null | wc -l | xargs); if command -v bc >/dev/null 2>&1; then avg=$(echo "scale=1; $count / 30" | bc 2>/dev/null); echo "Average commits per day (last 30 days): ${avg:-0}"; else echo "Average commits per day (last 30 days): ~$((count / 30))"; fi'
```

## Return Value
- **Claude agent text**: Formatted analysis including:
  - Count of technical debt comments by type (TODO, FIXME, HACK, XXX)
  - List of files with the most debt comments
  - List of stale branches (30+ days old)
  - List of large files (>1MB) tracked by git that may need refactoring
  - Summary of uncommitted/unstaged changes
  - Recent commit activity statistics

## Examples

1. **Clean repository with minimal debt**:
   ```
   /git:debt-scan
   ```
   Output:
   ```
   === Technical Debt Comments ===
   TODO comments: 5
   FIXME comments: 1
   HACK comments: 0
   XXX comments: 0

   === Files with Most Debt Comments ===
      3 ./src/api/users.ts
      2 ./src/utils/helpers.js
      1 ./tests/integration.test.ts

   === Stale Branches (not updated in 30+ days) ===
   feature/old-experiment - Last commit: 3 months ago by Alice
   bugfix/minor-issue - Last commit: 2 months ago by Bob

   === Large Files (>1MB, tracked by git) ===
   data/seed.json - 2.1M

   === Uncommitted Changes ===
   

   === Commit Activity ===
   Commits in last week: 12
   Commits in last month: 48
   Average commits per day (last 30 days): 1.6
   ```

2. **Repository with technical debt to address**:
   ```
   /git:debt-scan
   ```
   Output:
   ```
   === Technical Debt Comments ===
   TODO comments: 47
   FIXME comments: 23
   HACK comments: 8
   XXX comments: 5

   === Files with Most Debt Comments ===
     12 ./src/legacy/payment-processor.js
      9 ./src/controllers/auth.ts
      7 ./src/services/notifications.py
      5 ./src/utils/data-transformer.go
      4 ./tests/e2e/checkout.test.js

   === Stale Branches (not updated in 30+ days) ===
   feature/refactor-database - Last commit: 5 months ago by Carol
   feature/new-ui - Last commit: 4 months ago by Dave
   bugfix/memory-leak - Last commit: 6 weeks ago by Eve

   === Large Files (>1MB, tracked by git) ===
   src/legacy/monolith.js - 5.3M
   dist/bundle.min.js - 3.2M
   data/migrations.sql - 2.8M

   === Uncommitted Changes ===
    M src/api/routes.ts
   ?? temp/debug-logs.txt
   ?? scripts/experimental.sh

   === Commit Activity ===
   Commits in last week: 3
   Commits in last month: 15
   Average commits per day (last 30 days): 0.5
   ```

3. **Active development repository**:
   ```
   /git:debt-scan
   ```
   Output:
   ```
   === Technical Debt Comments ===
   TODO comments: 18
   FIXME comments: 4
   HACK comments: 2
   XXX comments: 0

   === Files with Most Debt Comments ===
      6 ./src/features/new-feature.ts
      4 ./src/api/v2/endpoints.go
      3 ./tests/unit/service.test.js

   === Stale Branches (not updated in 30+ days) ===
   (no stale branches found)

   === Large Files (>1MB, tracked by git) ===
   docs/api-reference.pdf - 1.2M

   === Uncommitted Changes ===
    M src/features/new-feature.ts
    M tests/unit/service.test.js

   === Commit Activity ===
   Commits in last week: 28
   Commits in last month: 89
   Average commits per day (last 30 days): 3.0
   ```

## Interpretation Guide

**Technical Debt Comments:**
- 0-10: Excellent - minimal documented debt
- 11-30: Good - manageable debt levels
- 31-100: Moderate - consider dedicating time to address
- 100+: High - prioritize technical debt reduction

**Stale Branches:**
- Branches inactive for 30+ days may be abandoned
- Consider cleaning up or merging forgotten branches
- Review with team before deletion

**Large Files:**
- Git-tracked files over 1MB may benefit from:
  - Code splitting or modularization
  - Moving data to separate files or Git LFS
  - Compression or optimization
  - Being added to .gitignore if they're generated/built files

**Commit Activity:**
- Low activity may indicate stagnant project
- Very high activity may indicate need for better planning
- Consistent activity suggests healthy development pace

## Arguments:
- None

