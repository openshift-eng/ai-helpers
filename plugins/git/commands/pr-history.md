---
description: Show the essential history of a PR - merges, reverts, and re-applications with reasons
argument-hint: <pr-number> [repository]
---

## Name
git:pr-history

## Synopsis
```
/git:pr-history <pr-number> [repository]
```

## Description
The `git:pr-history` command traces the complete lifecycle of a pull request through the Git history, showing merges, reverts, and re-applications with their associated reasons. This command is essential for understanding the journey of a PR, especially in cases where changes were merged, reverted due to issues, and later re-applied with fixes.

This command provides critical information for developers including:
- Original merge commit and associated metadata
- Any revert commits with revert reasons
- Re-application attempts with justification
- Timeline of PR lifecycle events
- Impact analysis of each operation

The command is particularly useful for tracking controversial changes, debugging regressions, or understanding why certain features were temporarily removed and re-introduced.

The specification section is inspired by the [Linux man pages](https://man7.org/linux/man-pages/man7/man-pages.7.html#top_of_page).

## Implementation
- Search git history for commits related to the specified PR number
- Identify merge commits using PR patterns (e.g., "Merge pull request #123")
- Find revert commits that reference the original merge
- Locate re-application commits that restore reverted changes
- Extract commit messages and metadata for timeline reconstruction
- Parse commit messages for reasoning and context
- Present chronological timeline with clear categorization
- Validate repository parameter to prevent command injection
- Handle cases where PR number doesn't exist or has no history
- Provide clear error messages for invalid inputs

Implementation logic:
```bash
# Validate PR number is numeric to prevent injection
if ! [[ "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
    echo "Error: PR number must be numeric"
    exit 1
fi

# Discover available git remotes (when repository parameter is provided)
git remote -v

# Validate repository parameter if provided
if [ -n "$REPOSITORY" ]; then
    # Ensure repository name contains only safe characters
    if ! [[ "$REPOSITORY" =~ ^[a-zA-Z0-9/_.-]+$ ]]; then
        echo "Error: Invalid repository name format"
        exit 1
    fi
fi

# Find original merge commit for the PR
MERGE_COMMITS=$(git log --grep="Merge pull request #${PR_NUMBER}" --oneline --all)
if [ -z "$MERGE_COMMITS" ]; then
    echo "No merge commits found for PR #${PR_NUMBER}"
    exit 1
fi

# Search for reverts of the merge commit
git log --grep="Revert" --grep="#${PR_NUMBER}" --oneline --all

# Look for re-applications or follow-up commits
git log --grep="Re-apply\|Reapply\|Re-land\|Reland" --grep="#${PR_NUMBER}" --oneline --all

# Get detailed commit information including author, date, and full message
git show --pretty=format:"%H %an %ad %s" --no-patch <commit-hashes>

# Analyze file changes in each commit
git show --name-only <commit-hashes>
```

Advanced search patterns:
- PR merge patterns: "Merge pull request #N", "Merged PR N", "#N"
- Revert patterns: "Revert", "Reverts", "This reverts commit"
- Re-application patterns: "Re-apply", "Reapply", "Re-land", "Reland"

## Return Value
- **Claude agent text**: Chronological timeline including:
  - Original PR merge with commit hash, author, and date
  - Revert operations with reasons and impact analysis
  - Re-application attempts with fixes and justifications
  - Timeline visualization showing PR lifecycle stages
  - Summary of current status (merged, reverted, or re-applied)

## Examples

1. **Basic PR history lookup in OpenShift Origin**:
   ```bash
   /git:pr-history 12345
   ```
   Output:
   ```text
   PR #12345 History Timeline:

   📥 MERGED (2024-10-15 14:30)
   abc123f Merge pull request #12345 from feature/etcd-encryption
   Author: OpenShift Storage Team
   Message: Add etcd encryption at rest support for control plane
   Files: pkg/etcd/encryption.go, test/e2e/etcd_encryption_test.go

   ⏪ REVERTED (2024-10-16 09:15)
   def456a Revert "Merge pull request #12345"
   Author: Release Engineering
   Reason: Breaking cluster upgrades for existing installations
   Impact: Reverted encryption.go changes, removed etcd encryption dependency

   ✅ RE-APPLIED (2024-10-18 16:45)
   ghi789b Re-apply PR #12345 with upgrade compatibility fixes
   Author: OpenShift Storage Team
   Message: Restored etcd encryption with backward compatibility for upgrades
   Files: pkg/etcd/encryption.go, pkg/etcd/migration.go, test/e2e/etcd_encryption_test.go

   Current Status: ✅ Active (re-applied with fixes)
   ```

2. **PR with multiple revert/re-apply cycles in Kubernetes**:
   ```bash
   # First, discover your configured remotes
   git remote -v

   # Then use the appropriate remote name (e.g., origin, upstream, etc.)
   /git:pr-history 67890 origin/master
   ```
   Output:
   ```text
   PR #67890 History Timeline:

   📥 MERGED (2024-09-01 10:00)
   aaa111 Merge pull request #67890 from sig-network/ovn-kubernetes-optimization
   Author: OVN-Kubernetes Team
   Files: pkg/network/ovn/gateway.go, pkg/network/ovn/controller.go

   ⏪ REVERTED (2024-09-02 08:30)
   bbb222 Revert OVN-K optimization PR #67890
   Reason: Causing network connectivity issues in multi-node clusters

   ✅ RE-APPLIED (2024-09-05 14:20)
   ccc333 Re-apply PR #67890 with multi-node cluster fixes
   Files: pkg/network/ovn/gateway.go, pkg/network/ovn/controller.go, pkg/network/ovn/multinode.go

   ⏪ REVERTED (2024-09-06 11:15)
   ddd444 Revert re-applied PR #67890 changes
   Reason: CNI plugin crashes detected in OpenShift CI tests

   ✅ RE-APPLIED (2024-09-10 09:45)
   eee555 Final re-application of PR #67890 with CNI stability fixes
   Author: OVN-Kubernetes Team + OpenShift Networking
   Files: pkg/network/ovn/gateway.go, pkg/network/ovn/controller.go, pkg/network/ovn/cni.go

   Current Status: ✅ Active (final re-application)
   Lifecycle: 3 operations over 9 days
   ```

3. **PR that was permanently reverted in OpenShift API**:
   ```bash
   /git:pr-history 54321
   ```
   Output:
   ```text
   PR #54321 History Timeline:

   📥 MERGED (2024-08-20 16:00)
   fff666 Merge pull request #54321 from openshift/experimental-cri-o-v2
   Author: OpenShift Node Team
   Message: Upgrade to CRI-O v2.0 with new container runtime features
   Files: 23 files changed across pkg/node/, vendor/

   ⏪ REVERTED (2024-08-22 12:30)
   ggg777 Revert experimental CRI-O v2 upgrade PR #54321
   Author: OpenShift Release Manager
   Reason: Breaking pod startup in production clusters, incompatible with existing workloads
   Impact: Complete rollback of CRI-O v2 upgrade, restored v1.x compatibility

   Current Status: ❌ Reverted (no re-application)
   Note: No re-application attempts found - waiting for upstream CRI-O v2 stabilization
   ```

## Error Handling
- **Invalid PR number**: Returns error if PR number is not numeric or contains invalid characters
- **Repository not found**: Validates repository parameter and provides clear error message for invalid formats
- **No PR history**: Handles cases where PR number exists but has no merge/revert/re-apply history
- **Git repository access**: Ensures command only runs in valid git repositories
- **Permission issues**: Gracefully handles cases where git history is not accessible

## Arguments:
- $1: **pr-number** (required) - The pull request number to trace through git history
  - Must be a positive integer
  - Examples: 123, 4567, 89012
- $2: **repository** (optional) - Git remote or branch to search (defaults to current branch and all remotes)
  - Format: remote/branch or just remote name
  - Use `git remote -v` to discover available remotes
  - Examples: origin/main, upstream/master, origin