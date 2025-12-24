---
name: PR Test Case Generator
description: Generate oc command-based test cases from any GitHub PR
---

# PR Test Case Generator Skill

Generate test cases with `oc` commands by analyzing any GitHub PR.

## How to Analyze Any PR

### Step 1: Open PR in Browser

Navigate to the PR URL and gather information from:
- **Conversation tab**: PR title, description, JIRA links
- **Files changed tab**: List of modified files
- **Commits tab**: Individual commit messages

### Step 2: Identify PR Category

| Files Changed | Category | What to Test |
|--------------|----------|--------------|
| `api/*_types.go` | API Types | New fields, validation |
| `config/crd/*.yaml` | CRD | Schema changes |
| `*controller*.go` | Controller | Reconciliation, child resources |
| `*reconcile*.go` | Reconciler | Status updates, conditions |
| `cmd/*.go` | CLI | Command behavior |
| `test/e2e/*.go` | E2E Tests | Follow same patterns |

### Step 3: Extract Key Information

#### From `*_types.go` files:
```go
// Look for API Group, Kind, and fields
type MyResourceSpec struct {
    NewField string `json:"newField"`
}
```

#### From CRD YAML files:
```yaml
metadata:
  name: myresources.example.com  # CRD name
spec:
  group: example.com             # API group
  names:
    kind: MyResource             # Kind
    plural: myresources          # Resource name
```

## Test Templates

### Template 1: Operator Installation via OLM

For testing operator PRs, first install the operator:

```bash
# Create namespace
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
EOF

# Create Subscription
oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: <operator-subscription>
  namespace: <operator-namespace>
spec:
  source: redhat-operators
  sourceNamespace: openshift-marketplace
  name: <operator-package>
  channel: <channel>
EOF

# Wait for operator to be ready
oc wait --for=condition=Available deployment/<operator-deployment> \
  -n <operator-namespace> --timeout=300s
```

### Template 2: Multi-CR Setup (like ZTWIM)

When operator requires multiple CRs:

```bash
# Get cluster info for configuration
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')
export CLUSTER_NAME=$(oc get infrastructure cluster -o jsonpath='{.status.infrastructureName}')

# Create main CR
oc apply -f - <<EOF
apiVersion: <apiVersion>
kind: <MainKind>
metadata:
  name: cluster
spec:
  trustDomain: $APP_DOMAIN
  clusterName: $CLUSTER_NAME
EOF

# Wait for main CR
oc wait --for=condition=Available <main-resource>/cluster --timeout=120s

# Create dependent CRs
oc apply -f - <<EOF
apiVersion: <apiVersion>
kind: <DependentKind1>
metadata:
  name: cluster
spec:
  <spec>
---
apiVersion: <apiVersion>
kind: <DependentKind2>
metadata:
  name: cluster
spec:
  <spec>
EOF

# Wait for all CRs
oc wait --for=condition=Ready <resource1>/cluster --timeout=120s
oc wait --for=condition=Ready <resource2>/cluster --timeout=120s
```

### Template 3: ZTWIM Example (Reference)

Complete test setup for Zero Trust Workload Identity Manager:

```bash
# 1. Install operator
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

# 2. Wait for operator
oc wait --for=condition=Available deployment -l app=zero-trust-workload-identity-manager \
  -n zero-trust-workload-identity-manager --timeout=300s

# 3. Set environment variables
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')
export JWT_ISSUER_ENDPOINT=oidc-discovery.${APP_DOMAIN}
export CLUSTER_NAME=test01

# 4. Create main CR
oc apply -f - <<EOF
apiVersion: operator.openshift.io/v1alpha1
kind: ZeroTrustWorkloadIdentityManager
metadata:
  name: cluster
spec:
  trustDomain: $APP_DOMAIN
  clusterName: $CLUSTER_NAME
EOF

# 5. Create all operand CRs
oc apply -f - <<EOF
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
    maxOpenConns: 100
    maxIdleConns: 2
    connMaxLifetime: 3600
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
    workloadAttestorsVerification:
      type: "auto"
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

# 6. Verify all CRs are ready
oc get zerotrustwworkloadidentitymanager cluster
oc get spireserver cluster
oc get spireagent cluster
oc get spiffecsidriver cluster
oc get spireoidcdiscoveryprovider cluster

# 7. Wait for resources to be available
oc wait --for=condition=Available zerotrustwworkloadidentitymanager/cluster --timeout=300s
oc wait --for=condition=Available spireserver/cluster --timeout=300s
oc wait --for=condition=Available spireagent/cluster --timeout=300s
```

### Template 4: API Field Change Test

When PR adds/modifies a field:

```bash
# Setup environment
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')

# Create CR with new field
oc apply -f - <<EOF
apiVersion: <apiVersion>
kind: <Kind>
metadata:
  name: test-instance
spec:
  <existingFields>
  <newField>: <value>
EOF

# Verify field is accepted
oc get <resource> test-instance -o jsonpath='{.spec.<newField>}'

# Test field update
oc patch <resource> test-instance --type=merge \
  -p '{"spec":{"<newField>":"<newValue>"}}'

oc get <resource> test-instance -o jsonpath='{.spec.<newField>}'
```

### Template 5: Config Propagation Test

When PR changes how config flows between CRs (like PR #72):

```bash
# Setup
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')

# Create main CR with common config
oc apply -f - <<EOF
apiVersion: operator.openshift.io/v1alpha1
kind: ZeroTrustWorkloadIdentityManager
metadata:
  name: cluster
spec:
  commonConfig:
    trustDomain: $APP_DOMAIN
    clusterName: test-cluster
EOF

# Wait for reconciliation
oc wait --for=condition=Available zerotrustwworkloadidentitymanager/cluster --timeout=120s

# Verify operands inherit config
oc get spireserver cluster -o jsonpath='{.spec.trustDomain}'
oc get spireagent cluster -o jsonpath='{.spec.trustDomain}'

# Update config in main CR
oc patch zerotrustwworkloadidentitymanager cluster --type=merge \
  -p '{"spec":{"commonConfig":{"trustDomain":"updated.example.org"}}}'

sleep 15

# Verify propagation to operands
oc get spireserver cluster -o jsonpath='{.spec.trustDomain}'
oc get spireagent cluster -o jsonpath='{.spec.trustDomain}'
```

### Template 6: Negative Test

```bash
# Test invalid value
oc apply -f - <<EOF 2>&1
apiVersion: <apiVersion>
kind: <Kind>
metadata:
  name: test-invalid
spec:
  trustDomain: ""  # Empty - should fail
EOF
# Should show validation error

# Test missing required field
oc apply -f - <<EOF 2>&1
apiVersion: <apiVersion>
kind: <Kind>
metadata:
  name: test-missing
spec:
  # Missing trustDomain
EOF
```

## Common Patterns

### Get Cluster Configuration
```bash
# Get base domain
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')

# Get cluster name
export CLUSTER_NAME=$(oc get infrastructure cluster -o jsonpath='{.status.infrastructureName}')

# Get API server URL
export API_SERVER=$(oc whoami --show-server)
```

### Wait for Resources
```bash
# Wait for deployment
oc wait --for=condition=Available deployment/<name> -n <ns> --timeout=300s

# Wait for CR condition
oc wait --for=condition=Ready <resource>/<name> --timeout=120s

# Wait for pod
oc wait --for=condition=Ready pod -l app=<label> -n <ns> --timeout=120s

# Wait for CSV (operator)
oc wait --for=jsonpath='{.status.phase}'=Succeeded csv/<csv-name> -n <ns> --timeout=300s
```

### Verify Resources
```bash
# Get specific field
oc get <resource> <name> -o jsonpath='{.spec.field}'

# Get status
oc get <resource> <name> -o jsonpath='{.status}'

# Get conditions
oc get <resource> <name> -o jsonpath='{.status.conditions}'

# Check all related resources
oc get zerotrustwworkloadidentitymanager,spireserver,spireagent,spiffecsidriver,spireoidcdiscoveryprovider
```

### Check Operator Logs
```bash
# Get operator pod logs
oc logs -n <operator-ns> deployment/<operator> --tail=100

# Follow logs
oc logs -n <operator-ns> deployment/<operator> -f --tail=20

# Check for errors
oc logs -n <operator-ns> deployment/<operator> --tail=200 | grep -i error
```

## Cleanup

```bash
# Delete CRs first
oc delete zerotrustwworkloadidentitymanager cluster
oc delete spireserver cluster
oc delete spireagent cluster
oc delete spiffecsidriver cluster
oc delete spireoidcdiscoveryprovider cluster

# Delete operator subscription
oc delete subscription openshift-zero-trust-workload-identity-manager \
  -n zero-trust-workload-identity-manager

# Delete namespace (removes everything)
oc delete namespace zero-trust-workload-identity-manager
```

## Output Guidelines

- Extract actual values from PR (API version, Kind, field names)
- Include OLM installation steps when testing operator PRs
- Use environment variables for cluster-specific values
- Include all related CRs when operator creates multiple resources
- Self-verifying commands with `oc wait` and `jsonpath`
