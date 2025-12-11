---
name: Kubernetes Dependency Analysis
description: Deep analysis of Kubernetes API usage and breaking changes between versions
---

# Kubernetes Dependency Analysis Skill

This skill provides detailed guidance for analyzing Kubernetes dependency changes and identifying breaking changes when rebasing to a new Kubernetes version.

## When to Use This Skill

Use this skill when:
- Running `/k8s-bumpup:rebase-repo` or `/k8s-bumpup:batch-by-group` and need to understand the audit analysis
- Investigating build or test failures after a Kubernetes version update
- Understanding the impact of deprecated API usage in a codebase
- Planning a multi-version Kubernetes upgrade strategy

## Prerequisites

1. **Required tools**:
   - `go` (version 1.20+): `go version`
   - `jq` (for JSON parsing): `which jq`
   - `curl` or `wget` (for fetching changelogs)
   - `git` (for repository operations)

2. **Repository requirements**:
   - Valid Go module with `go.mod`
   - Kubernetes dependencies (`k8s.io/*`)
   - Git repository (for diff analysis)

3. **Network access**:
   - GitHub API access (for fetching changelogs)
   - Go module proxy access (proxy.golang.org)

## Implementation Steps

### Step 1: Extract Current Kubernetes API Usage

#### 1.1 Find All Kubernetes Imports

```bash
# Create output directory
mkdir -p .work/k8s-bumpup-audit

# Find all k8s.io imports across codebase
find . -name "*.go" \
  -not -path "./vendor/*" \
  -not -path "./.work/*" \
  -not -path "./.*" \
  -exec grep -h "\"k8s.io/" {} \; | \
  sed 's/.*"k8s\.io/k8s.io/' | \
  sed 's/".*//' | \
  sort -u > .work/k8s-bumpup-audit/all-k8s-imports.txt
```

#### 1.2 Categorize Imports by Type

```bash
# API imports (k8s.io/api/...)
grep "^k8s.io/api/" .work/k8s-bumpup-audit/all-k8s-imports.txt > \
  .work/k8s-bumpup-audit/api-imports.txt

# Client-go imports
grep "^k8s.io/client-go" .work/k8s-bumpup-audit/all-k8s-imports.txt > \
  .work/k8s-bumpup-audit/client-go-imports.txt

# API machinery
grep "^k8s.io/apimachinery" .work/k8s-bumpup-audit/all-k8s-imports.txt > \
  .work/k8s-bumpup-audit/apimachinery-imports.txt
```

#### 1.3 Extract API Group Versions

```bash
# Extract API group/version combinations (e.g., apps/v1, batch/v1beta1)
grep "^k8s.io/api/" .work/k8s-bumpup-audit/api-imports.txt | \
  sed 's/k8s\.io\/api\///' | \
  sort -u > .work/k8s-bumpup-audit/api-group-versions.txt

# Example output:
# apps/v1
# batch/v1
# batch/v1beta1
# core/v1
# networking/v1
```

#### 1.4 Find Resource Type Usage

```bash
# Search for typed resources (e.g., appsv1.Deployment, corev1.Pod)
grep -rh "\(apps\|core\|batch\|networking\|policy\)v[0-9]" \
  --include="*.go" \
  --exclude-dir="vendor" \
  --exclude-dir=".work" . | \
  grep -o "\(apps\|core\|batch\|networking\|policy\)v[0-9][^.]*\.[A-Z][a-zA-Z]*" | \
  sort -u > .work/k8s-bumpup-audit/resource-types.txt

# Example output:
# appsv1.Deployment
# appsv1.StatefulSet
# batchv1.Job
# batchv1beta1.CronJob
# corev1.Pod
```

### Step 2: Fetch Kubernetes Release Notes

#### 2.1 Calculate Version Range

```bash
# Given: CURRENT_VERSION=v1.27.8, TARGET_VERSION=v1.29.0
CURRENT_MINOR=$(echo "$CURRENT_VERSION" | sed 's/v\([0-9]*\.[0-9]*\)\..*/\1/')
TARGET_MINOR=$(echo "$TARGET_VERSION" | sed 's/v\([0-9]*\.[0-9]*\)\..*/\1/')

# Extract major.minor numbers
CURRENT_MAJ=$(echo "$CURRENT_MINOR" | cut -d. -f1)
CURRENT_MIN=$(echo "$CURRENT_MINOR" | cut -d. -f2)
TARGET_MAJ=$(echo "$TARGET_MINOR" | cut -d. -f1)
TARGET_MIN=$(echo "$TARGET_MINOR" | cut -d. -f2)

# Generate version list
VERSIONS=()
for ((i=$CURRENT_MIN+1; i<=$TARGET_MIN; i++)); do
  VERSIONS+=("$CURRENT_MAJ.$i")
done

# Example: crossing v1.27 → v1.29 includes v1.28, v1.29
echo "${VERSIONS[@]}"  # Output: 1.28 1.29
```

#### 2.2 Fetch Changelogs from GitHub

```bash
# For each version, fetch the changelog
for VERSION in "${VERSIONS[@]}"; do
  echo "Fetching changelog for v${VERSION}..."

  # Try fetching from kubernetes/kubernetes repo
  CHANGELOG_URL="https://raw.githubusercontent.com/kubernetes/kubernetes/master/CHANGELOG/CHANGELOG-${VERSION}.md"

  curl -sL "$CHANGELOG_URL" -o ".work/k8s-bumpup-audit/CHANGELOG-${VERSION}.md"

  if [ $? -ne 0 ]; then
    echo "Warning: Could not fetch changelog for v${VERSION}"
  fi
done
```

#### 2.3 Alternative: Use GitHub Releases API

```bash
# Fetch releases via API (more reliable)
for VERSION in "${VERSIONS[@]}"; do
  echo "Fetching release notes for v${VERSION}.0 via API..."

  curl -sL "https://api.github.com/repos/kubernetes/kubernetes/releases/tags/v${VERSION}.0" | \
    jq -r '.body' > ".work/k8s-bumpup-audit/release-notes-${VERSION}.md"

  if [ ! -s ".work/k8s-bumpup-audit/release-notes-${VERSION}.md" ]; then
    echo "Warning: No release notes found for v${VERSION}.0"
  fi
done
```

### Step 3: Identify Breaking Changes

#### 3.1 Parse Changelogs for Key Sections

```bash
# Extract "API Changes" section from changelog
for VERSION in "${VERSIONS[@]}"; do
  CHANGELOG=".work/k8s-bumpup-audit/CHANGELOG-${VERSION}.md"

  if [ -f "$CHANGELOG" ]; then
    # Extract API Changes section
    sed -n '/## Changes by Kind/,/##/p' "$CHANGELOG" | \
      sed -n '/### API Change/,/###/p' > \
      ".work/k8s-bumpup-audit/api-changes-${VERSION}.txt"

    # Extract Deprecation section
    sed -n '/## Deprecation/,/##/p' "$CHANGELOG" > \
      ".work/k8s-bumpup-audit/deprecations-${VERSION}.txt"
  fi
done
```

#### 3.2 Search for Specific Breaking Changes

```bash
# Common breaking change patterns to search for
PATTERNS=(
  "removed"
  "deprecated"
  "breaking change"
  "no longer supported"
  "beta.*promoted.*GA"
  "v1beta.*v1"
)

for VERSION in "${VERSIONS[@]}"; do
  CHANGELOG=".work/k8s-bumpup-audit/CHANGELOG-${VERSION}.md"

  echo "=== Breaking changes in v${VERSION} ===" > \
    ".work/k8s-bumpup-audit/breaking-${VERSION}.txt"

  for PATTERN in "${PATTERNS[@]}"; do
    grep -i "$PATTERN" "$CHANGELOG" >> \
      ".work/k8s-bumpup-audit/breaking-${VERSION}.txt" 2>/dev/null || true
  done
done
```

#### 3.3 Map Breaking Changes to Codebase Usage

```bash
# Cross-reference: Check if deprecated APIs are used in codebase

# Example: Check for batch/v1beta1 CronJob usage (deprecated in v1.25, removed in v1.29)
if grep -q "batch/v1beta1" .work/k8s-bumpup-audit/api-group-versions.txt; then
  echo "⚠️  WARNING: batch/v1beta1 CronJob is used but deprecated"
  echo "   Migration required: batch/v1beta1 → batch/v1"

  # Find files using this API
  grep -r "batch/v1beta1" --include="*.go" --exclude-dir="vendor" . | \
    cut -d: -f1 | sort -u > .work/k8s-bumpup-audit/files-using-cronjob-beta.txt

  echo "   Affected files:"
  cat .work/k8s-bumpup-audit/files-using-cronjob-beta.txt | sed 's/^/     - /'
fi

# Similar checks for other known deprecations
# - policy/v1beta1 PodSecurityPolicy (removed v1.25)
# - networking.k8s.io/v1beta1 Ingress (removed v1.22)
# - rbac.authorization.k8s.io/v1beta1 (removed v1.22)
```

### Step 4: Analyze Go Module Dependencies

#### 4.1 Check Current Dependency Graph

```bash
# List all k8s.io dependencies with versions
go list -m -json all | \
  jq -r 'select(.Path | startswith("k8s.io/")) | "\(.Path) \(.Version)"' | \
  sort > .work/k8s-bumpup-audit/current-k8s-deps.txt

# Example output:
# k8s.io/api v0.28.4
# k8s.io/apimachinery v0.28.4
# k8s.io/client-go v0.28.4
```

#### 4.2 Simulate Dependency Update

```bash
# Check what would change with target version
TARGET_VERSION="v1.29.0"

# Create temporary module for testing
cp go.mod go.mod.backup
cp go.sum go.sum.backup

# Try updating
go get k8s.io/api@${TARGET_VERSION} \
      k8s.io/apimachinery@${TARGET_VERSION} \
      k8s.io/client-go@${TARGET_VERSION} 2>&1 | \
  tee .work/k8s-bumpup-audit/update-simulation.log

# Extract dependency changes
go list -m -json all | \
  jq -r 'select(.Path | startswith("k8s.io/")) | "\(.Path) \(.Version)"' | \
  sort > .work/k8s-bumpup-audit/new-k8s-deps.txt

# Diff the changes
diff .work/k8s-bumpup-audit/current-k8s-deps.txt \
     .work/k8s-bumpup-audit/new-k8s-deps.txt > \
     .work/k8s-bumpup-audit/dep-diff.txt || true

# Restore original
mv go.mod.backup go.mod
mv go.sum.backup go.sum
```

#### 4.3 Check for Transitive Dependency Issues

```bash
# Check if any other dependencies conflict with target k8s version
go mod graph | grep "k8s.io/" > .work/k8s-bumpup-audit/dep-graph.txt

# Look for version mismatches
awk '{print $2}' .work/k8s-bumpup-audit/dep-graph.txt | \
  grep "k8s.io/" | \
  sort | uniq -c | \
  awk '$1 > 1 {print}' > .work/k8s-bumpup-audit/potential-conflicts.txt

# If this file is non-empty, there may be version conflicts to resolve
```

### Step 5: Generate Detailed Audit Report

#### 5.1 Create Report Structure

```bash
cat > .work/k8s-bumpup-audit/audit-report.md << 'EOF'
# Kubernetes Dependency Audit Report

**Generated**: $(date)
**Current Version**: ${CURRENT_VERSION}
**Target Version**: ${TARGET_VERSION}
**Versions Crossed**: ${VERSIONS[@]}

---

## Executive Summary

[To be filled]

## API Usage Analysis

### Imported API Groups
[List from api-group-versions.txt]

### Resource Types in Use
[List from resource-types.txt]

## Breaking Changes Detected

### Critical Issues
[API removals that affect the codebase]

### Warnings
[Deprecations that should be addressed]

### Informational
[Other changes]

## Dependency Analysis

### Current Dependencies
[From current-k8s-deps.txt]

### Updated Dependencies
[From new-k8s-deps.txt]

### Changes
[From dep-diff.txt]

## Recommendations

1. **Immediate Actions Required**
   - [List critical changes]

2. **Suggested Before Update**
   - [List deprecation fixes]

3. **Post-Update Validation**
   - [Testing recommendations]

## Migration Guides

- [Links to relevant Kubernetes migration guides]

---

## Detailed Findings

[Append detailed analysis]
EOF
```

#### 5.2 Populate Report with Findings

```bash
# Add API usage section
echo "" >> .work/k8s-bumpup-audit/audit-report.md
echo "### API Groups Used" >> .work/k8s-bumpup-audit/audit-report.md
cat .work/k8s-bumpup-audit/api-group-versions.txt | \
  sed 's/^/- `/' | sed 's/$/`/' >> .work/k8s-bumpup-audit/audit-report.md

# Add breaking changes
for VERSION in "${VERSIONS[@]}"; do
  if [ -f ".work/k8s-bumpup-audit/breaking-${VERSION}.txt" ]; then
    echo "" >> .work/k8s-bumpup-audit/audit-report.md
    echo "### Breaking Changes in v${VERSION}" >> .work/k8s-bumpup-audit/audit-report.md
    cat ".work/k8s-bumpup-audit/breaking-${VERSION}.txt" >> \
      .work/k8s-bumpup-audit/audit-report.md
  fi
done
```

#### 5.3 Add Risk Assessment

```bash
# Calculate risk score based on:
# - Number of versions crossed
# - Number of beta APIs in use
# - Number of detected breaking changes

VERSIONS_CROSSED=${#VERSIONS[@]}
BETA_APIS=$(grep -c "beta" .work/k8s-bumpup-audit/api-group-versions.txt || echo 0)
BREAKING_CHANGES=$(cat .work/k8s-bumpup-audit/breaking-*.txt 2>/dev/null | wc -l || echo 0)

# Simple risk calculation
RISK_SCORE=$((VERSIONS_CROSSED * 10 + BETA_APIS * 5 + BREAKING_CHANGES * 20))

if [ $RISK_SCORE -lt 30 ]; then
  RISK_LEVEL="LOW"
elif [ $RISK_SCORE -lt 70 ]; then
  RISK_LEVEL="MEDIUM"
else
  RISK_LEVEL="HIGH"
fi

echo "**Risk Level**: ${RISK_LEVEL} (Score: ${RISK_SCORE})" >> \
  .work/k8s-bumpup-audit/audit-report.md
```

## Error Handling

### Cannot Fetch Changelogs

If changelog fetching fails:

```bash
echo "Warning: Unable to fetch changelogs from GitHub"
echo "Falling back to local analysis only..."
echo ""
echo "Suggestion: Manually review release notes at:"
for VERSION in "${VERSIONS[@]}"; do
  echo "  - https://github.com/kubernetes/kubernetes/blob/master/CHANGELOG/CHANGELOG-${VERSION}.md"
done
```

### No Kubernetes Dependencies Found

```bash
if [ ! -s .work/k8s-bumpup-audit/all-k8s-imports.txt ]; then
  echo "ERROR: No k8s.io imports found in codebase"
  echo "This may not be a Kubernetes-dependent project"
  exit 1
fi
```

### Version Parsing Failures

```bash
if ! echo "$VERSION" | grep -qE '^v?[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "ERROR: Invalid version format: $VERSION"
  echo "Expected format: vMAJOR.MINOR.PATCH (e.g., v1.29.0)"
  exit 1
fi
```

## Examples

### Example 1: Audit v1.28 → v1.29 Upgrade

```bash
CURRENT_VERSION="v1.28.4"
TARGET_VERSION="v1.29.0"

# Run full analysis
[Execute all steps above]

# Expected output in audit-report.md:
# - List of API changes in v1.29
# - Detection of any v1beta APIs in use
# - Dependency version changes
# - Risk assessment
```

### Example 2: Detect Specific API Deprecation

```bash
# Check specifically for CronJob v1beta1 usage
if grep -q "batchv1beta1.CronJob" .work/k8s-bumpup-audit/resource-types.txt; then
  echo "Found deprecated CronJob v1beta1 usage"

  # Find exact locations
  grep -rn "batchv1beta1.CronJob" --include="*.go" . | \
    grep -v vendor | \
    tee .work/k8s-bumpup-audit/cronjob-migration-needed.txt
fi
```

## Best Practices

1. **Always fetch changelogs**: Even if time-consuming, official changelogs are authoritative
2. **Check both API and client-go changes**: Breaking changes can occur in client libraries too
3. **Test simulation in isolation**: Use temporary go.mod copies to avoid corrupting workspace
4. **Document all findings**: Future maintainers will appreciate the detailed audit trail
5. **Link to migration guides**: Include URLs to Kubernetes deprecation guides
6. **Automate where possible**: Scripts should be idempotent and resumable

## Additional Resources

- Kubernetes Deprecation Policy: https://kubernetes.io/docs/reference/using-api/deprecation-policy/
- API Migration Guide: https://kubernetes.io/docs/reference/using-api/deprecation-guide/
- Client-go Compatibility Matrix: https://github.com/kubernetes/client-go#compatibility-matrix
- Go Module Documentation: https://go.dev/ref/mod
