---
description: Run strict OpenShift API review workflow for PR changes or local changes
argument-hint: "<pr_url> [--api-dir <path>]"
---

## Name
openshift:api-review

## Synopsis
```text
/openshift:api-review <pr_url> [--api-dir <path>]
```

## Description

Run a comprehensive API review for OpenShift API changes. Works with any GitHub repository — provide a full PR URL and the command extracts the owner/repo automatically. Optionally specify `--api-dir` to scope the review to a specific directory (e.g., `api/` for HyperShift). If omitted, the command auto-detects API directories.

## Implementation

# Output Format Requirements
You MUST use this EXACT format for ALL review feedback:


+LineNumber: Brief description
**Current (problematic) code:**
```go
[exact code from the PR diff]
```

**Suggested change:**
```diff
- [old code line]
+ [new code line]
```

**Explanation:** [Why this change is needed]


## Step 1: Pre-flight checks and parse arguments

```bash
set -euo pipefail

# Save current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "📍 Current branch: $CURRENT_BRANCH"

# Ensure we always return to the original branch on exit
cleanup() {
    git checkout "$CURRENT_BRANCH" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Parse arguments: extract PR URL and optional --api-dir
API_DIR=""
PR_URL=""
prev_arg=""
for arg in $ARGUMENTS; do
    if [ "$prev_arg" = "--api-dir" ]; then
        API_DIR="$arg"
        prev_arg=""
        continue
    fi
    if [ "$arg" = "--api-dir" ]; then
        prev_arg="$arg"
        continue
    fi
    if [[ "$arg" =~ github\.com.*pull ]]; then
        PR_URL="$arg"
    fi
done

# A PR URL is required
if [ -z "$PR_URL" ]; then
    echo "❌ ERROR: A GitHub PR URL is required."
    echo "Usage: /openshift:api-review <pr_url> [--api-dir <path>]"
    echo "Example: /openshift:api-review https://github.com/openshift/api/pull/2145"
    exit 1
fi

# Extract owner, repo, and PR number from the URL
OWNER=$(echo "$PR_URL" | sed -nE 's#^.*github\.com/([^/]+)/([^/]+)/pull/([0-9]+).*$#\1#p')
REPO=$(echo "$PR_URL" | sed -nE 's#^.*github\.com/([^/]+)/([^/]+)/pull/([0-9]+).*$#\2#p')
PR_NUMBER=$(echo "$PR_URL" | sed -nE 's#^.*github\.com/([^/]+)/([^/]+)/pull/([0-9]+).*$#\3#p')

if [ -z "$OWNER" ] || [ -z "$REPO" ] || [ -z "$PR_NUMBER" ]; then
    echo "❌ ERROR: Could not parse owner/repo/PR number from: $PR_URL"
    exit 1
fi

echo "🔍 Reviewing PR #$PR_NUMBER in $OWNER/$REPO"
if [ -n "$API_DIR" ]; then
    echo "📂 API directory: $API_DIR"
fi

# Check for uncommitted changes
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "❌ ERROR: Uncommitted changes detected. Cannot proceed with PR review."
    echo "Please commit or stash your changes before running the API review."
    git status --porcelain
    exit 1
fi
echo "✅ No uncommitted changes detected. Safe to proceed."

# Find or add an upstream remote for the target repository
UPSTREAM_REMOTE=""
for remote in $(git remote); do
    remote_url=$(git remote get-url "$remote" 2>/dev/null || echo "")
    if [[ "$remote_url" =~ github\.com[/:]${OWNER}/${REPO}(\.git)?$ ]]; then
        UPSTREAM_REMOTE="$remote"
        echo "✅ Found remote: '$remote' -> $remote_url"
        break
    fi
done

if [ -z "$UPSTREAM_REMOTE" ]; then
    echo "⚠️  No remote pointing to $OWNER/$REPO found. Adding upstream-review remote..."
    git remote add upstream-review "https://github.com/${OWNER}/${REPO}.git"
    UPSTREAM_REMOTE="upstream-review"
fi

echo "🔄 Fetching latest changes from $UPSTREAM_REMOTE..."
git fetch "$UPSTREAM_REMOTE" master || git fetch "$UPSTREAM_REMOTE" main
```

## Step 2: Checkout the PR and identify API files

```bash
echo "🔄 Checking out PR #$PR_NUMBER..."
gh pr checkout "$PR_NUMBER" --repo "$OWNER/$REPO"

echo "📁 Analyzing changed files in PR..."
ALL_CHANGED_GO=$(gh pr view "$PR_NUMBER" --repo "$OWNER/$REPO" --json files --jq '.files[].path' | grep '\.go$' || true)

# Filter to API files using --api-dir if provided, otherwise auto-detect
if [ -n "$API_DIR" ]; then
    # User specified the API directory — scope to that
    CHANGED_FILES=$(echo "$ALL_CHANGED_GO" | grep "^${API_DIR}" || true)
    echo "📂 Scoped to --api-dir=$API_DIR"
else
    # Auto-detect: check for common API directory patterns in the changed files
    # Priority: api/, apis/, pkg/api/, pkg/apis/, or files matching API version patterns
    API_DIRS=""
    for pattern in "^api/" "^apis/" "^pkg/api/" "^pkg/apis/"; do
        if echo "$ALL_CHANGED_GO" | grep -q "$pattern"; then
            API_DIRS="$API_DIRS $pattern"
        fi
    done

    if [ -n "$API_DIRS" ]; then
        # Filter to files in detected API directories
        CHANGED_FILES=""
        for pattern in $API_DIRS; do
            matches=$(echo "$ALL_CHANGED_GO" | grep "$pattern" || true)
            CHANGED_FILES=$(echo -e "$CHANGED_FILES\n$matches" | sed '/^$/d' | sort -u)
        done
        echo "📂 Auto-detected API directories: $API_DIRS"
    else
        # Fallback: look for files with API version directory patterns or types.go
        CHANGED_FILES=$(echo "$ALL_CHANGED_GO" | grep -E '/(v1|v1alpha[0-9]*|v1beta[0-9]*|v2|v2alpha[0-9]*|v2beta[0-9]*)/' || true)
        if [ -z "$CHANGED_FILES" ]; then
            CHANGED_FILES=$(echo "$ALL_CHANGED_GO" | grep -E 'types\.go$' || true)
        fi
        if [ -z "$CHANGED_FILES" ]; then
            # No API files detected — review all changed Go files
            CHANGED_FILES="$ALL_CHANGED_GO"
            echo "⚠️  Could not auto-detect API directory. Reviewing all changed Go files."
            echo "    Tip: Use --api-dir <path> to scope the review (e.g., --api-dir api/)"
        fi
    fi
fi

echo "Changed API files:"
echo "$CHANGED_FILES"

if [ -z "$CHANGED_FILES" ]; then
    echo "ℹ️  No API files changed. Nothing to review."
    git checkout "$CURRENT_BRANCH"
    exit 0
fi
```

## Step 3: Run linting checks on changes (if available)

```bash
# Check if a lint target exists in the Makefile before running
if [ -f Makefile ] && grep -qE '^lint[[:space:]]*:' Makefile; then
    echo "⏳ Running linting checks on changes..."
    make lint

    if [ $? -ne 0 ]; then
        echo "❌ Linting checks failed. Please fix the issues before proceeding."
        echo "🔄 Switching back to original branch: $CURRENT_BRANCH"
        git checkout "$CURRENT_BRANCH"
        exit 1
    fi
    echo "✅ Linting checks passed."
else
    echo "⚠️  No 'lint' Makefile target found — skipping lint step."
fi
```

## Step 4: Documentation validation

For each changed API file, I'll validate:

1. **Field Documentation**: All struct fields must have documentation comments
2. **Optional Field Behavior**: Optional fields must explain what happens when they are omitted
3. **Validation Documentation**: Validation rules must be documented and match markers

Let me check each changed file for these requirements:

```thinking
I need to analyze the changed files to:
1. Find struct fields without documentation
2. Find optional fields without behavior documentation
3. Find validation annotations without corresponding documentation

For each Go file, I'll:
- Look for struct field definitions
- Check if they have preceding comment documentation
- For optional fields (those with `+kubebuilder:validation:Optional` or `+optional`), verify behavior is explained
- For fields with validation annotations, ensure the validation is documented
```

## Step 5: Generate comprehensive review report

I'll provide a comprehensive report showing:
- ✅ Files that pass all checks
- ❌ Files with documentation issues
- 📋 Specific lines that need attention
- 📚 Guidance on fixing any issues

The review will fail if any documentation requirements are not met for the changed files.

## Step 6: Switch back to original branch

After completing the review, switch back to the original branch:

```bash
echo "🔄 Switching back to original branch: $CURRENT_BRANCH"
git checkout "$CURRENT_BRANCH"
echo "✅ API review complete. Back on branch: $(git branch --show-current)"
```

**CRITICAL WORKFLOW REQUIREMENTS:**

1. MUST check for uncommitted changes before starting
2. MUST abort if uncommitted changes are detected
3. MUST save current branch name before switching
4. MUST checkout the PR before running lint or review steps
5. MUST switch back to original branch when complete
6. If any step fails, MUST attempt to switch back to original branch before exiting

## Examples

1. **Review an openshift/api PR**:
   ```text
   /openshift:api-review https://github.com/openshift/api/pull/2145
   ```
   Checks out the PR, runs lint and convention checks, then switches back to your branch.

2. **Review a HyperShift PR with explicit API directory**:
   ```text
   /openshift:api-review https://github.com/openshift/hypershift/pull/1234 --api-dir api/
   ```
   Scopes the review to files under `api/` in the HyperShift repo.

3. **Review a PR in any repository**:
   ```text
   /openshift:api-review https://github.com/openshift/cluster-version-operator/pull/567
   ```
   Auto-detects API directories or falls back to reviewing all changed Go files.

## Arguments

- **pr_url** (required): Full GitHub PR URL (e.g., `https://github.com/openshift/api/pull/2145`). Owner and repo are extracted from the URL.
- **--api-dir** (optional): Path to the API directory within the repository (e.g., `api/`, `pkg/api/`). If omitted, the command auto-detects API directories from common patterns.

## See Also

- `/openshift:crd-review` - Review CRD types in any repository against conventions
- [OpenShift API Conventions](https://github.com/openshift/enhancements/blob/master/dev-guide/api-conventions.md)
- [Kubernetes API Conventions](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md)
- [Source command](https://github.com/openshift/api/blob/master/.claude/commands/api-review.md) in the openshift/api repository
