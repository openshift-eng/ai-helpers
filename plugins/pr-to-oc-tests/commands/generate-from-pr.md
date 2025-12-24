---
description: Generate test cases with oc commands from any GitHub PR
argument-hint: "<pr-url> [--output <path>]"
---

## Name
generate-from-pr

## Synopsis
```
/generate-from-pr <pr-url> [--output <path>]
```

## Description

Analyzes any GitHub Pull Request and generates test cases with executable `oc` commands based on the actual changes in the PR.

## Implementation

### Step 1: Open PR and Analyze Changes

**IMPORTANT: Use browser tools to analyze the PR. Do NOT use `gh` CLI.**

1. **Use browser_navigate** to open the PR URL provided by user
2. **Use browser_snapshot** to read the PR description and conversation
3. **Navigate to "Files changed" tab** (append `/files` to PR URL) to see all modified files
4. **Use browser_snapshot** again to read the file changes
5. **Identify change categories**:

   | File Pattern | Category | Test Focus |
   |--------------|----------|------------|
   | `api/*_types.go`, `*_types.go` | API Types | New fields, validation |
   | `config/crd/*.yaml` | CRD Changes | Schema updates |
   | `*controller*.go`, `*reconcile*.go` | Controller | Reconciliation logic |
   | `pkg/`, `internal/` | Business Logic | Function behavior |
   | `cmd/` | CLI | Command behavior |
   | `test/e2e/` | E2E Tests | Test patterns to follow |

4. **Read PR description** for:
   - JIRA ticket references
   - Feature description
   - Bug reproduction steps
   - Acceptance criteria

### Step 2: Extract Test Information from PR

For each changed file, extract:

1. **For API type changes** (`*_types.go`):
   - New struct fields added
   - Field types and validation tags
   - API version and Kind
   - Required vs optional fields

2. **For CRD changes** (`*.yaml` in config/crd):
   - New properties in spec
   - Validation rules (enum, pattern, minimum, maximum)
   - Required fields list

3. **For controller changes**:
   - Resources being reconciled
   - Child resources created
   - Status conditions set
   - Events emitted

4. **From PR description**:
   - Example YAML snippets
   - Expected behavior
   - Bug scenario (if bug fix)

### Step 3: Generate Test Cases

Based on analyzed changes, generate `oc` command test cases:

#### Template: API/CRD Field Addition

```markdown
# Test: New Field in <Kind> CR

## Setup
oc create namespace test-<pr-number>

## Test Steps

# 1. Create CR with new field
cat <<EOF | oc apply -f -
apiVersion: <apiVersion>
kind: <Kind>
metadata:
  name: test-instance
  namespace: test-<pr-number>
spec:
  <newField>: <testValue>
EOF

# 2. Verify field is accepted
oc get <resource> test-instance -n test-<pr-number> -o jsonpath='{.spec.<newField>}'

# 3. Verify operator processes it (if applicable)
oc wait --for=condition=Ready <resource>/test-instance -n test-<pr-number> --timeout=120s

# 4. Test field update
oc patch <resource> test-instance -n test-<pr-number> --type=merge \
  -p '{"spec":{"<newField>":"<updatedValue>"}}'

oc get <resource> test-instance -n test-<pr-number> -o jsonpath='{.spec.<newField>}'

## Cleanup
oc delete namespace test-<pr-number>
```

#### Template: Controller/Operator Change

```markdown
# Test: Controller Reconciliation for <Kind>

## Setup
oc create namespace test-<pr-number>

## Test Steps

# 1. Check operator is running
oc get pods -n <operator-namespace> -l <operator-label>

# 2. Create CR to trigger reconciliation
cat <<EOF | oc apply -f -
apiVersion: <apiVersion>
kind: <Kind>
metadata:
  name: test-instance
  namespace: test-<pr-number>
spec:
  <spec-from-pr>
EOF

# 3. Wait for reconciliation
oc wait --for=condition=Available <resource>/test-instance -n test-<pr-number> --timeout=300s

# 4. Verify created child resources
oc get all -n test-<pr-number>
oc get configmaps -n test-<pr-number>
oc get secrets -n test-<pr-number>

# 5. Check operator logs
oc logs -n <operator-namespace> deployment/<operator> --tail=50

# 6. Verify status
oc get <resource> test-instance -n test-<pr-number> -o jsonpath='{.status.conditions}'

## Cleanup
oc delete namespace test-<pr-number>
```

#### Template: Bug Fix

```markdown
# Test: Bug Fix Verification

## Setup
oc create namespace test-<pr-number>

## Test Steps

# 1. Create scenario from bug report
cat <<EOF | oc apply -f -
<yaml-from-bug-report>
EOF

# 2. Verify issue is fixed
oc wait --for=condition=Ready <resource>/<name> -n test-<pr-number> --timeout=60s

# 3. Check no error events
oc get events -n test-<pr-number> --field-selector type=Warning

# 4. Check logs
oc logs -n <operator-namespace> deployment/<operator> --tail=100 | grep -i error || echo "No errors"

## Cleanup
oc delete namespace test-<pr-number>
```

#### Template: Validation Test (Negative)

```markdown
# Test: Validation for <Field>

# Test invalid value - should fail
cat <<EOF | oc apply -f - 2>&1
apiVersion: <apiVersion>
kind: <Kind>
metadata:
  name: test-invalid
spec:
  <field>: <invalidValue>
EOF

# Test missing required field - should fail
cat <<EOF | oc apply -f - 2>&1
apiVersion: <apiVersion>
kind: <Kind>
metadata:
  name: test-missing
spec:
  # Missing required <field>
EOF
```

### Step 4: Output Generation

1. **Create output directory** with naming pattern:
   ```
   op_pr_<short-description>/
   ```
   
   Where `<short-description>` is derived from PR title:
   - Convert to lowercase
   - Replace spaces with hyphens
   - Remove special characters
   - Truncate to ~50 chars
   
   **Examples**:
   - PR: "Add trustDomain field to SpireServer" → `op_pr_add-trustdomain-field-to-spireserver/`
   - PR: "Fix must-gather scripts directory discovery" → `op_pr_fix-must-gather-scripts-directory-discovery/`
   - PR: "OCPBUGS-12345: Update controller reconcile logic" → `op_pr_update-controller-reconcile-logic/`

2. **Generate test-cases.md** with:
   - PR summary (title, URL, files changed)
   - Prerequisites (cluster, operator, CRDs)
   - Test cases organized by category
   - Cleanup section

3. **Display summary** to user with output path

## Arguments

- **$1 (pr-url)**: Any GitHub PR URL
  - `https://github.com/{owner}/{repo}/pull/{number}`
  
- **--output**: Custom output path (optional)

## Examples

### Example 1: Operator PR
```
/generate-from-pr https://github.com/openshift/zero-trust-workload-identity-manager/pull/72
```

### Example 2: Kubernetes Controller PR
```
/generate-from-pr https://github.com/openshift/cluster-api-provider-aws/pull/1234
```

### Example 3: CLI Tool PR
```
/generate-from-pr https://github.com/openshift/oc/pull/5678
```

### Example 4: Library/SDK PR
```
/generate-from-pr https://github.com/openshift/client-go/pull/999
```

## How It Works

1. **You provide**: PR URL
2. **Plugin analyzes**: Files changed, PR description, code diffs
3. **Plugin identifies**: 
   - API version and Kind from `*_types.go`
   - Resource names from CRDs
   - Operator namespace from deployment files
   - Test patterns from existing e2e tests
4. **Plugin generates**: Customized `oc` commands for that specific PR

## Output Format

```markdown
# Test Cases for PR #<number>: <title>

## PR Info
- Repository: <owner>/<repo>
- URL: <pr-url>
- Files Changed: <count>
- Categories: <API|Controller|CLI|Config>

## Prerequisites
- oc CLI installed
- Cluster access with admin privileges
- <Operator> installed (if applicable)
- CRD <name> exists (if applicable)

## Test Cases

### TC-001: <Test Name>
<oc commands>

### TC-002: <Test Name>
<oc commands>

...

## Cleanup
oc delete namespace test-<pr-number>
```

## Notes

- **Use browser tools (browser_navigate, browser_snapshot) to analyze PRs - NOT `gh` CLI**
- Analyzes actual PR changes to generate relevant tests
- Extracts API versions, Kinds, and field names from code
- Uses PR description for context and examples
- Works with any OpenShift/Kubernetes operator PR

## Tool Usage

To analyze a PR, use these browser tools in order:

```
1. browser_navigate to <pr-url>
2. browser_snapshot to read PR description
3. browser_navigate to <pr-url>/files
4. browser_snapshot to read changed files
5. For each interesting file, navigate to the raw file URL to read full content
```

Do NOT use:
- `gh` CLI (may not be installed)
- `curl` to GitHub API (requires authentication)
