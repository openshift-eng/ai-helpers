---
description: Generate ZTWIM test cases with oc commands from any ZTWIM operator PR
argument-hint: "<pr-url> [--output <path>]"
---

## Name
ztwim:generate-from-pr

## Synopsis
```
/ztwim:generate-from-pr <pr-url> [--output <path>]
```

## Description

Analyzes Zero Trust Workload Identity Manager (ZTWIM) operator Pull Requests and generates test cases with executable `oc` commands based on the actual changes in the PR.

## ZTWIM Context

The ZTWIM operator manages these Custom Resources:
- **ZeroTrustWorkloadIdentityManager** - Main CR that manages all SPIRE components
- **SpireServer** - SPIRE server configuration
- **SpireAgent** - SPIRE agent daemonset
- **SpiffeCSIDriver** - CSI driver for SVID injection
- **SpireOIDCDiscoveryProvider** - OIDC discovery endpoint

API Group: `operator.openshift.io/v1alpha1`
Namespace: `zero-trust-workload-identity-manager`

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
   | `api/*_types.go` | API Types | New fields in SpireServer, SpireAgent, etc. |
   | `config/crd/*.yaml` | CRD Changes | Schema updates for ZTWIM CRDs |
   | `*controller*.go`, `*reconcile*.go` | Controller | Reconciliation logic, operand creation |
   | `pkg/`, `internal/` | Business Logic | Config propagation, validation |
   | `test/e2e/` | E2E Tests | Test patterns to follow |

6. **Read PR description** for:
   - JIRA ticket references (OCPBUGS-*, SPIRE-*)
   - Feature description
   - Bug reproduction steps
   - Acceptance criteria

### Step 2: Extract Test Information from PR

For each changed file, extract:

1. **For API type changes** (`*_types.go`):
   - New struct fields (trustDomain, clusterName, jwtIssuer, etc.)
   - Field types and validation tags
   - Which CR is affected (SpireServer, SpireAgent, etc.)

2. **For CRD changes** (`*.yaml` in config/crd):
   - New properties in spec
   - Validation rules
   - Required fields

3. **For controller changes**:
   - Which operand CRs are affected
   - Config propagation from main CR to operands
   - Status conditions set

4. **From PR description**:
   - Example YAML snippets
   - Expected behavior
   - Bug scenario (if bug fix)

### Step 3: Generate Test Cases

Based on analyzed changes, generate `oc` command test cases:

#### Template: ZTWIM Field Addition

```markdown
# Test: New Field in <ZTWIM-CR>

## Setup
# Install ZTWIM operator (if not installed)
oc apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: zero-trust-workload-identity-manager
---
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: zero-trust-workload-identity-manager-og
  namespace: zero-trust-workload-identity-manager
spec:
  upgradeStrategy: Default
---
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: openshift-zero-trust-workload-identity-manager
  namespace: zero-trust-workload-identity-manager
spec:
  source: redhat-operators
  sourceNamespace: openshift-marketplace
  name: openshift-zero-trust-workload-identity-manager
  channel: tech-preview-v0.2
EOF

oc wait --for=condition=Available deployment -l app=zero-trust-workload-identity-manager \
  -n zero-trust-workload-identity-manager --timeout=300s

## Environment Setup
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')
export JWT_ISSUER_ENDPOINT=oidc-discovery.${APP_DOMAIN}

## Test Steps

# 1. Create main CR
oc apply -f - <<EOF
apiVersion: operator.openshift.io/v1alpha1
kind: ZeroTrustWorkloadIdentityManager
metadata:
  name: cluster
spec:
  trustDomain: $APP_DOMAIN
  clusterName: test01
EOF

# 2. Create CR with new field
oc apply -f - <<EOF
apiVersion: operator.openshift.io/v1alpha1
kind: <SpireServer|SpireAgent|etc>
metadata:
  name: cluster
spec:
  <newField>: <testValue>
  <existingRequiredFields>
EOF

# 3. Verify field is accepted
oc get <resource> cluster -o jsonpath='{.spec.<newField>}'

# 4. Verify operator processes it
oc wait --for=condition=Available <resource>/cluster --timeout=120s

# 5. Test field update
oc patch <resource> cluster --type=merge \
  -p '{"spec":{"<newField>":"<updatedValue>"}}'

oc get <resource> cluster -o jsonpath='{.spec.<newField>}'

## Cleanup
oc delete spireoidcdiscoveryprovider cluster --ignore-not-found
oc delete spiffecsidriver cluster --ignore-not-found
oc delete spireagent cluster --ignore-not-found
oc delete spireserver cluster --ignore-not-found
oc delete zerotrustwworkloadidentitymanager cluster --ignore-not-found
```

#### Template: Config Propagation Test

```markdown
# Test: Config Propagation from ZeroTrustWorkloadIdentityManager to Operands

## Setup
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')

## Test Steps

# 1. Create main CR with config
oc apply -f - <<EOF
apiVersion: operator.openshift.io/v1alpha1
kind: ZeroTrustWorkloadIdentityManager
metadata:
  name: cluster
spec:
  trustDomain: $APP_DOMAIN
  clusterName: test-cluster
EOF

oc wait --for=condition=Available zerotrustwworkloadidentitymanager/cluster --timeout=120s

# 2. Create operand CRs
oc apply -f - <<EOF
apiVersion: operator.openshift.io/v1alpha1
kind: SpireServer
metadata:
  name: cluster
spec:
  caSubject:
    commonName: $APP_DOMAIN
---
apiVersion: operator.openshift.io/v1alpha1
kind: SpireAgent
metadata:
  name: cluster
spec:
  nodeAttestor:
    k8sPSATEnabled: "true"
EOF

# 3. Verify operands inherit config
oc get spireserver cluster -o jsonpath='{.spec.trustDomain}'
oc get spireagent cluster -o jsonpath='{.spec.trustDomain}'

# 4. Update config in main CR
oc patch zerotrustwworkloadidentitymanager cluster --type=merge \
  -p '{"spec":{"trustDomain":"updated.example.org"}}'

sleep 15

# 5. Verify propagation to operands
oc get spireserver cluster -o jsonpath='{.spec.trustDomain}'
oc get spireagent cluster -o jsonpath='{.spec.trustDomain}'
```

#### Template: Full ZTWIM Stack Test

```markdown
# Test: Complete ZTWIM Stack

## Setup
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')
export JWT_ISSUER_ENDPOINT=oidc-discovery.${APP_DOMAIN}
export CLUSTER_NAME=test01

## Test Steps

# 1. Create all CRs
oc apply -f - <<EOF
apiVersion: operator.openshift.io/v1alpha1
kind: ZeroTrustWorkloadIdentityManager
metadata:
  name: cluster
spec:
  trustDomain: $APP_DOMAIN
  clusterName: $CLUSTER_NAME
---
apiVersion: operator.openshift.io/v1alpha1
kind: SpireServer
metadata:
  name: cluster
spec:
  caSubject:
    commonName: $APP_DOMAIN
    country: "US"
    organization: "RH"
  persistence:
    type: pvc
    size: "1Gi"
    accessMode: ReadWriteOncePod
  datastore:
    databaseType: sqlite3
    connectionString: "/run/spire/data/datastore.sqlite3"
  jwtIssuer: https://$JWT_ISSUER_ENDPOINT
---
apiVersion: operator.openshift.io/v1alpha1
kind: SpireAgent
metadata:
  name: cluster
spec:
  nodeAttestor:
    k8sPSATEnabled: "true"
  workloadAttestors:
    k8sEnabled: "true"
---
apiVersion: operator.openshift.io/v1alpha1
kind: SpiffeCSIDriver
metadata:
  name: cluster
spec: {}
---
apiVersion: operator.openshift.io/v1alpha1
kind: SpireOIDCDiscoveryProvider
metadata:
  name: cluster
spec:
  jwtIssuer: https://$JWT_ISSUER_ENDPOINT
EOF

# 2. Verify all CRs
oc get zerotrustwworkloadidentitymanager,spireserver,spireagent,spiffecsidriver,spireoidcdiscoveryprovider

# 3. Wait for resources
oc wait --for=condition=Available zerotrustwworkloadidentitymanager/cluster --timeout=300s
oc wait --for=condition=Available spireserver/cluster --timeout=300s
oc wait --for=condition=Available spireagent/cluster --timeout=300s

# 4. Check pods
oc get pods -n zero-trust-workload-identity-manager

# 5. Check operator logs
oc logs -n zero-trust-workload-identity-manager deployment/zero-trust-workload-identity-manager --tail=50
```

#### Template: Bug Fix Verification

```markdown
# Test: Bug Fix Verification for <JIRA-ID>

## Setup
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')

## Test Steps

# 1. Create scenario from bug report
oc apply -f - <<EOF
<yaml-from-bug-report>
EOF

# 2. Verify issue is fixed
oc wait --for=condition=Ready <resource>/cluster --timeout=60s

# 3. Check no error events
oc get events -n zero-trust-workload-identity-manager --field-selector type=Warning

# 4. Check logs
oc logs -n zero-trust-workload-identity-manager deployment/zero-trust-workload-identity-manager --tail=100 | grep -i error || echo "No errors"

## Cleanup
oc delete namespace zero-trust-workload-identity-manager
```

### Step 4: Output Generation

1. **Create output directory** with naming pattern:
   ```
   ztwim_pr_<number>_<short-description>/
   ```
   
   Where `<short-description>` is derived from PR title:
   - Convert to lowercase
   - Replace spaces with hyphens
   - Remove special characters
   - Truncate to ~50 chars
   
   **Examples**:
   - PR: "Add trustDomain field to SpireServer" → `ztwim_pr_72_add-trustdomain-field-to-spireserver/`
   - PR: "Fix config propagation" → `ztwim_pr_85_fix-config-propagation/`

2. **Generate test-cases.md** with:
   - PR summary (title, URL, files changed)
   - Prerequisites (cluster, ZTWIM operator)
   - Test cases organized by category
   - Cleanup section

3. **Display summary** to user with output path

## Arguments

- **$1 (pr-url)**: ZTWIM GitHub PR URL
  - `https://github.com/openshift/zero-trust-workload-identity-manager/pull/{number}`
  
- **--output**: Custom output path (optional)

## Examples

### Example 1: API Field Addition
```
/ztwim:generate-from-pr https://github.com/openshift/zero-trust-workload-identity-manager/pull/72
```

### Example 2: Controller Bug Fix
```
/ztwim:generate-from-pr https://github.com/openshift/zero-trust-workload-identity-manager/pull/85
```

### Example 3: Config Propagation PR
```
/ztwim:generate-from-pr https://github.com/openshift/zero-trust-workload-identity-manager/pull/90
```

## How It Works

1. **You provide**: ZTWIM PR URL
2. **Plugin analyzes**: Files changed, PR description, code diffs
3. **Plugin identifies**: 
   - Which ZTWIM CRs are affected (SpireServer, SpireAgent, etc.)
   - New fields or changed behavior
   - Config propagation patterns
4. **Plugin generates**: Customized `oc` commands for that specific PR

## Output Format

```markdown
# ZTWIM Test Cases for PR #<number>: <title>

## PR Info
- Repository: openshift/zero-trust-workload-identity-manager
- URL: <pr-url>
- Files Changed: <count>
- Affected CRs: <SpireServer|SpireAgent|etc>

## Prerequisites
- oc CLI installed
- Cluster access with admin privileges
- ZTWIM operator installed (or will be installed by tests)

## Test Cases

### TC-001: <Test Name>
<oc commands>

### TC-002: <Test Name>
<oc commands>

...

## Cleanup
oc delete spireoidcdiscoveryprovider cluster --ignore-not-found
oc delete spiffecsidriver cluster --ignore-not-found
oc delete spireagent cluster --ignore-not-found
oc delete spireserver cluster --ignore-not-found
oc delete zerotrustwworkloadidentitymanager cluster --ignore-not-found
oc delete subscription openshift-zero-trust-workload-identity-manager -n zero-trust-workload-identity-manager
oc delete namespace zero-trust-workload-identity-manager
```

## Notes

- **Use browser tools (browser_navigate, browser_snapshot) to analyze PRs - NOT `gh` CLI**
- Analyzes actual PR changes to generate relevant ZTWIM tests
- Extracts API versions, Kinds, and field names from code
- Uses PR description for context and examples
- Generates tests specific to ZTWIM operator patterns

## Tool Usage

To analyze a ZTWIM PR, use these browser tools in order:

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
