---
description: Generate test cases with oc commands from any OpenShift operator PR
argument-hint: "<pr-url> [--output <path>]"
---

## Name
operator-test-generator:generate-from-pr

## Synopsis

```text
/operator-test-generator:generate-from-pr <pr-url> [--output <path>]
```

## Description

Analyzes any OpenShift operator Pull Request and generates test cases with executable `oc` commands. The plugin **dynamically extracts** operator information from the PR context including:

- Operator name and namespace
- OLM installation details (package name, channel, catalog source)
- Custom Resource Definitions (CRDs) and their structure
- Required permissions and RBAC
- Environment variables needed

## Implementation

### Step 1: Open PR and Extract Operator Context

**IMPORTANT: Use browser tools to analyze the PR. Do NOT use `gh` CLI.**

1. **Use browser_navigate** to open the PR URL
2. **Use browser_snapshot** to read PR description
3. **Extract repository info** from URL:
   - Repository name → likely operator name
   - Organization (openshift, openshift-eng, etc.)

4. **Navigate to key files** to extract operator details:

   | File to Find | Information to Extract |
   |--------------|------------------------|
   | `config/manifests/bases/*.clusterserviceversion.yaml` | Operator name, displayName, channel |
   | `bundle/manifests/*.clusterserviceversion.yaml` | Package name, install modes |
   | `config/manager/manager.yaml` | Operator deployment, namespace |
   | `config/rbac/*.yaml` | Required permissions |
   | `config/crd/bases/*.yaml` | CRD names, API groups, kinds |
   | `api/**/types.go` or `api/**/*_types.go` | API versions, spec fields |
   | `Makefile` or `PROJECT` | Operator SDK info, domain |

5. **Identify operator installation method**:
   - OLM (if CSV exists)
   - Direct deployment (if no CSV)
   - Helm (if Chart.yaml exists)

### Step 2: Extract Operator Details

From the repository, extract:

#### OLM Installation Info
```yaml
# From ClusterServiceVersion
name: <operator-name>.v<version>
displayName: <Display Name>
namespace: <operator-namespace>
channel: <channel-name>
catalogSource: redhat-operators | community-operators | custom
packageName: <package-name>
```

#### CRD Information
```yaml
# From CRD files
apiVersion: <group>/<version>
kind: <Kind>
plural: <plural-name>
scope: Namespaced | Cluster
```

#### API Types
```go
// From *_types.go
type <Kind>Spec struct {
    Field1 string `json:"field1"`
    Field2 int    `json:"field2,omitempty"`
}
```

### Step 3: Analyze PR Changes

**Navigate to "Files changed" tab** (append `/files` to PR URL):

| File Pattern | Category | Test Focus |
|--------------|----------|------------|
| `api/**/*_types.go` | API Types | New fields, validation |
| `config/crd/**/*.yaml` | CRD Changes | Schema updates |
| `*controller*.go`, `*reconcile*.go` | Controller | Reconciliation logic |
| `config/rbac/*.yaml` | RBAC | Permission changes |
| `config/samples/*.yaml` | Samples | Example CR usage |
| `test/e2e/**` | E2E Tests | Test patterns |

### Step 4: Generate Dynamic Test Cases

Based on extracted context, generate:

#### Template: Dynamic OLM Installation

```markdown
# Operator Installation: <operator-display-name>

## Prerequisites Check
```bash
oc whoami
oc get clusterversion
oc get packagemanifests -n openshift-marketplace | grep <package-name>
```

## Install Operator via OLM
```bash
# Create namespace (if namespaced install)
oc apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: <operator-namespace>
EOF

# Create OperatorGroup
oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: <operator>-og
  namespace: <operator-namespace>
spec:
  upgradeStrategy: Default
  # For AllNamespaces install mode, omit targetNamespaces
  # For OwnNamespace, add:
  # targetNamespaces:
  # - <operator-namespace>
EOF

# Create Subscription
oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: <subscription-name>
  namespace: <operator-namespace>
spec:
  source: <catalog-source>
  sourceNamespace: openshift-marketplace
  name: <package-name>
  channel: <channel>
EOF

# Wait for operator
oc wait --for=condition=Available deployment -l <operator-label> \
  -n <operator-namespace> --timeout=300s
```

#### Template: Dynamic CR Creation

````markdown
# Create <Kind> Custom Resource

## Environment Setup (if needed)

```bash
# Extract cluster-specific values
export CLUSTER_DOMAIN=$(oc get ingresses.config cluster -o jsonpath='{.spec.domain}')
export CLUSTER_NAME=$(oc get infrastructure cluster -o jsonpath='{.status.infrastructureName}')
```

## Create CR

```bash
oc apply -f - <<EOF
apiVersion: <group>/<version>
kind: <Kind>
metadata:
  name: <instance-name>
  namespace: <namespace>  # if namespaced
spec:
  # Fields extracted from PR changes and samples
  <field1>: <value1>
  <field2>: <value2>
EOF
```

## Verify CR

```bash
oc get <plural> <instance-name> -n <namespace>
oc wait --for=condition=Ready <plural>/<instance-name> -n <namespace> --timeout=120s
```
````

#### Template: API Field Test

````markdown
# Test: New Field <fieldName> in <Kind>

## Test Steps

```bash
# Create CR with new field
oc apply -f - <<EOF
apiVersion: <group>/<version>
kind: <Kind>
metadata:
  name: test-new-field
spec:
  <newField>: <testValue>
  # Include required fields from CRD
EOF

# Verify field is accepted
oc get <plural> test-new-field -o jsonpath='{.spec.<newField>}'

# Test field update
oc patch <plural> test-new-field --type=merge \
  -p '{"spec":{"<newField>":"<updatedValue>"}}'

# Verify update
oc get <plural> test-new-field -o jsonpath='{.spec.<newField>}'
```
````

#### Template: Controller Reconciliation Test

````markdown
# Test: Controller Reconciliation

```bash
# Create CR
oc apply -f - <<EOF
apiVersion: <group>/<version>
kind: <Kind>
metadata:
  name: test-reconcile
spec:
  <spec-from-samples>
EOF

# Wait for reconciliation
oc wait --for=condition=Ready <plural>/test-reconcile --timeout=120s

# Check created child resources
oc get all -l <owner-label>=test-reconcile
oc get configmaps -l <owner-label>=test-reconcile
oc get secrets -l <owner-label>=test-reconcile

# Check operator logs
oc logs -n <operator-namespace> deployment/<operator-deployment> --tail=50

# Verify status
oc get <plural> test-reconcile -o jsonpath='{.status}'
```
````

### Step 5: Output Generation

1. **Create output directory**:

   ```text
   op_<operator-name>_pr_<number>_<short-description>/
   ```

2. **Generate test-cases.md** with:
   - Operator info (name, namespace, version)
   - OLM installation steps
   - CR creation for each CRD
   - PR-specific test cases
   - Cleanup steps

## Arguments

- **$1 (pr-url)**: Any OpenShift operator GitHub PR URL
  - `https://github.com/{org}/{repo}/pull/{number}`
  
- **--output**: Custom output path (optional)

## Examples

### Example 1: ZTWIM Operator

```bash
/operator-test-generator:generate-from-pr https://github.com/openshift/zero-trust-workload-identity-manager/pull/72
```

### Example 2: Cluster API Provider AWS

```bash
/operator-test-generator:generate-from-pr https://github.com/openshift/cluster-api-provider-aws/pull/1234
```

### Example 3: LVMS Operator

```bash
/operator-test-generator:generate-from-pr https://github.com/openshift/lvm-operator/pull/500
```

### Example 4: Node Tuning Operator

```bash
/operator-test-generator:generate-from-pr https://github.com/openshift/cluster-node-tuning-operator/pull/800
```

### Example 5: HyperShift

```bash
/operator-test-generator:generate-from-pr https://github.com/openshift/hypershift/pull/2000
```

## How Context Extraction Works

1. **Repository URL** → Operator name hint
2. **CSV file** → OLM package name, channel, install mode
3. **CRD files** → API group, kinds, required fields
4. **Manager deployment** → Namespace, labels, selectors
5. **Sample CRs** → Example spec values
6. **RBAC files** → Required permissions
7. **PR changes** → What specifically to test

## Output Format

```markdown
# Test Cases for <Operator Name> PR #<number>: <title>

## Operator Info
- Name: <operator-name>
- Namespace: <operator-namespace>
- Package: <package-name>
- Channel: <channel>
- CRDs: <list of CRDs>

## Prerequisites
- oc CLI installed
- Cluster access with admin privileges
- OLM available

## 1. Install Operator
<dynamic OLM installation commands>

## 2. Create Custom Resources
<dynamic CR creation for each CRD>

## 3. Test PR Changes
<test cases specific to PR changes>

## 4. Verification
<status checks, log inspection>

## 5. Cleanup
<cleanup in correct order>
```

## Notes

- **Use browser tools to analyze PRs** - NOT `gh` CLI
- **Dynamically extracts** operator context from repository files
- **Adapts** installation and CR creation based on operator type
- **Falls back to defaults** if specific info not found
- **Uses samples** from `config/samples/` when available

## Tool Usage

```text
1. browser_navigate to <pr-url>
2. browser_snapshot to read PR description
3. browser_navigate to repo root to find key files
4. browser_navigate to config/manifests/ or bundle/ for CSV
5. browser_navigate to config/crd/ for CRDs
6. browser_navigate to config/samples/ for example CRs
7. browser_navigate to <pr-url>/files for changes
8. browser_snapshot to read changes
```
