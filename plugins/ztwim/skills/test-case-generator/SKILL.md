---
name: ZTWIM Test Case Generator
description: Generate oc command-based test cases for Zero Trust Workload Identity Manager operator PRs
---

# ZTWIM Test Case Generator Skill

Generate test cases with `oc` commands by analyzing Zero Trust Workload Identity Manager (ZTWIM) operator PRs.

## ZTWIM Operator Overview

### Repository
https://github.com/openshift/zero-trust-workload-identity-manager

### Custom Resources

| CR | API | Description |
|----|-----|-------------|
| `ZeroTrustWorkloadIdentityManager` | `operator.openshift.io/v1alpha1` | Main CR, manages all components |
| `SpireServer` | `operator.openshift.io/v1alpha1` | SPIRE server configuration |
| `SpireAgent` | `operator.openshift.io/v1alpha1` | SPIRE agent daemonset |
| `SpiffeCSIDriver` | `operator.openshift.io/v1alpha1` | CSI driver for SVID injection |
| `SpireOIDCDiscoveryProvider` | `operator.openshift.io/v1alpha1` | OIDC discovery endpoint |

### Key Fields

| CR | Important Fields |
|----|------------------|
| `ZeroTrustWorkloadIdentityManager` | `trustDomain`, `clusterName` |
| `SpireServer` | `caSubject`, `persistence`, `datastore`, `jwtIssuer`, `trustDomain` |
| `SpireAgent` | `nodeAttestor`, `workloadAttestors`, `trustDomain` |
| `SpireOIDCDiscoveryProvider` | `jwtIssuer` |

## How to Analyze ZTWIM PRs

### Step 1: Open PR in Browser

Navigate to the PR URL and gather information from:
- **Conversation tab**: PR title, description, JIRA links
- **Files changed tab**: List of modified files
- **Commits tab**: Individual commit messages

### Step 2: Identify PR Category

| Files Changed | Category | What to Test |
|--------------|----------|--------------|
| `api/v1alpha1/*_types.go` | API Types | New fields in ZTWIM CRs |
| `config/crd/*.yaml` | CRD | Schema changes |
| `internal/controller/*controller*.go` | Controller | Reconciliation, operand creation |
| `internal/controller/*reconcile*.go` | Reconciler | Status updates, config propagation |
| `test/e2e/*.go` | E2E Tests | Follow same patterns |

### Step 3: Extract Key Information

#### From `api/v1alpha1/*_types.go` files:
```go
// Look for which CR is affected
type SpireServerSpec struct {
    // New field added by PR
    TrustDomain string `json:"trustDomain,omitempty"`
}
```

#### From CRD YAML files:
```yaml
# config/crd/bases/operator.openshift.io_spireservers.yaml
spec:
  properties:
    trustDomain:
      type: string
      description: Trust domain for SPIRE
```

## Test Templates

### Template 1: ZTWIM Operator Installation via OLM

```bash
# Create namespace
oc apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: zero-trust-workload-identity-manager
EOF

# Create OperatorGroup
oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: zero-trust-workload-identity-manager-og
  namespace: zero-trust-workload-identity-manager
spec:
  upgradeStrategy: Default
EOF

# Create Subscription
oc apply -f - <<EOF
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

# Wait for operator to be ready
oc wait --for=condition=Available deployment -l app=zero-trust-workload-identity-manager \
  -n zero-trust-workload-identity-manager --timeout=300s
```

### Template 2: Complete ZTWIM Stack Setup

```bash
# 1. Set environment variables
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')
export JWT_ISSUER_ENDPOINT=oidc-discovery.${APP_DOMAIN}
export CLUSTER_NAME=$(oc get infrastructure cluster -o jsonpath='{.status.infrastructureName}')

# 2. Create main CR
oc apply -f - <<EOF
apiVersion: operator.openshift.io/v1alpha1
kind: ZeroTrustWorkloadIdentityManager
metadata:
  name: cluster
spec:
  trustDomain: $APP_DOMAIN
  clusterName: $CLUSTER_NAME
EOF

# 3. Wait for main CR
oc wait --for=condition=Available zerotrustwworkloadidentitymanager/cluster --timeout=120s

# 4. Create all operand CRs
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

# 5. Verify all CRs are ready
oc get zerotrustwworkloadidentitymanager cluster
oc get spireserver cluster
oc get spireagent cluster
oc get spiffecsidriver cluster
oc get spireoidcdiscoveryprovider cluster

# 6. Wait for resources to be available
oc wait --for=condition=Available zerotrustwworkloadidentitymanager/cluster --timeout=300s
oc wait --for=condition=Available spireserver/cluster --timeout=300s
oc wait --for=condition=Available spireagent/cluster --timeout=300s
```

### Template 3: SpireServer Field Test

When PR adds/modifies a field on SpireServer:

```bash
# Setup environment
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')
export JWT_ISSUER_ENDPOINT=oidc-discovery.${APP_DOMAIN}

# Create SpireServer with new field
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
  jwtIssuer: https://$JWT_ISSUER_ENDPOINT
  # NEW FIELD FROM PR
  <newField>: <value>
EOF

# Verify field is accepted
oc get spireserver cluster -o jsonpath='{.spec.<newField>}'

# Test field update
oc patch spireserver cluster --type=merge \
  -p '{"spec":{"<newField>":"<newValue>"}}'

oc get spireserver cluster -o jsonpath='{.spec.<newField>}'
```

### Template 4: SpireAgent Field Test

When PR adds/modifies a field on SpireAgent:

```bash
# Create SpireAgent with new field
oc apply -f - <<EOF
apiVersion: operator.openshift.io/v1alpha1
kind: SpireAgent
metadata:
  name: cluster
spec:
  nodeAttestor:
    k8sPSATEnabled: "true"
  workloadAttestors:
    k8sEnabled: "true"
  # NEW FIELD FROM PR
  <newField>: <value>
EOF

# Verify field
oc get spireagent cluster -o jsonpath='{.spec.<newField>}'
```

### Template 5: Config Propagation Test

When PR changes how config flows from main CR to operands:

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
  trustDomain: $APP_DOMAIN
  clusterName: test-cluster
EOF

# Wait for reconciliation
oc wait --for=condition=Available zerotrustwworkloadidentitymanager/cluster --timeout=120s

# Create operand CRs
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

# Verify operands inherit config
oc get spireserver cluster -o jsonpath='{.spec.trustDomain}'
oc get spireagent cluster -o jsonpath='{.spec.trustDomain}'

# Update config in main CR
oc patch zerotrustwworkloadidentitymanager cluster --type=merge \
  -p '{"spec":{"trustDomain":"updated.example.org"}}'

sleep 15

# Verify propagation to operands
oc get spireserver cluster -o jsonpath='{.spec.trustDomain}'
oc get spireagent cluster -o jsonpath='{.spec.trustDomain}'
```

### Template 6: Negative Test

```bash
# Test invalid value
oc apply -f - <<EOF 2>&1
apiVersion: operator.openshift.io/v1alpha1
kind: SpireServer
metadata:
  name: test-invalid
spec:
  trustDomain: ""  # Empty - should fail
EOF
# Should show validation error

# Test missing required field
oc apply -f - <<EOF 2>&1
apiVersion: operator.openshift.io/v1alpha1
kind: SpireServer
metadata:
  name: test-missing
spec:
  # Missing caSubject
EOF
```

### Template 7: Controller Reconciliation Test

```bash
# Create CR and wait
oc apply -f - <<EOF
apiVersion: operator.openshift.io/v1alpha1
kind: SpireServer
metadata:
  name: cluster
spec:
  caSubject:
    commonName: test.example.com
EOF

oc wait --for=condition=Available spireserver/cluster --timeout=120s

# Delete a managed resource
oc delete deployment spire-server -n zero-trust-workload-identity-manager

# Wait and verify controller recreates it
sleep 30
oc get deployment spire-server -n zero-trust-workload-identity-manager

# Check reconciliation in logs
oc logs -n zero-trust-workload-identity-manager deployment/zero-trust-workload-identity-manager --tail=50 | grep -i reconcil
```

## Common Patterns

### Get Cluster Configuration
```bash
# Get base domain
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')

# Get OIDC endpoint
export JWT_ISSUER_ENDPOINT=oidc-discovery.${APP_DOMAIN}

# Get cluster name
export CLUSTER_NAME=$(oc get infrastructure cluster -o jsonpath='{.status.infrastructureName}')

# Get API server URL
export API_SERVER=$(oc whoami --show-server)
```

### Wait for ZTWIM Resources
```bash
# Wait for main CR
oc wait --for=condition=Available zerotrustwworkloadidentitymanager/cluster --timeout=300s

# Wait for SpireServer
oc wait --for=condition=Available spireserver/cluster --timeout=300s

# Wait for SpireAgent
oc wait --for=condition=Available spireagent/cluster --timeout=300s

# Wait for operator deployment
oc wait --for=condition=Available deployment -l app=zero-trust-workload-identity-manager \
  -n zero-trust-workload-identity-manager --timeout=300s

# Wait for CSV
oc wait --for=jsonpath='{.status.phase}'=Succeeded \
  csv -l operators.coreos.com/openshift-zero-trust-workload-identity-manager.zero-trust-workload-identity-manager \
  -n zero-trust-workload-identity-manager --timeout=300s
```

### Verify ZTWIM Resources
```bash
# Get all ZTWIM CRs
oc get zerotrustwworkloadidentitymanager,spireserver,spireagent,spiffecsidriver,spireoidcdiscoveryprovider

# Get specific field
oc get spireserver cluster -o jsonpath='{.spec.trustDomain}'

# Get status
oc get spireserver cluster -o jsonpath='{.status}'

# Get conditions
oc get spireserver cluster -o jsonpath='{.status.conditions}'

# Check pods
oc get pods -n zero-trust-workload-identity-manager
```

### Check Operator Logs
```bash
# Get operator pod logs
oc logs -n zero-trust-workload-identity-manager deployment/zero-trust-workload-identity-manager --tail=100

# Follow logs
oc logs -n zero-trust-workload-identity-manager deployment/zero-trust-workload-identity-manager -f --tail=20

# Check for errors
oc logs -n zero-trust-workload-identity-manager deployment/zero-trust-workload-identity-manager --tail=200 | grep -i error

# Check for reconciliation
oc logs -n zero-trust-workload-identity-manager deployment/zero-trust-workload-identity-manager --tail=100 | grep -i reconcil
```

## Cleanup

```bash
# Delete CRs first (in reverse order)
oc delete spireoidcdiscoveryprovider cluster --ignore-not-found
oc delete spiffecsidriver cluster --ignore-not-found
oc delete spireagent cluster --ignore-not-found
oc delete spireserver cluster --ignore-not-found
oc delete zerotrustwworkloadidentitymanager cluster --ignore-not-found

# Delete operator subscription
oc delete subscription openshift-zero-trust-workload-identity-manager \
  -n zero-trust-workload-identity-manager

# Delete CSV
oc delete csv -l operators.coreos.com/openshift-zero-trust-workload-identity-manager.zero-trust-workload-identity-manager \
  -n zero-trust-workload-identity-manager

# Delete namespace (removes everything)
oc delete namespace zero-trust-workload-identity-manager
```

## Output Guidelines

- Extract actual values from PR (API version, Kind, field names)
- Include OLM installation steps
- Use environment variables for cluster-specific values (APP_DOMAIN, JWT_ISSUER_ENDPOINT)
- Include all related ZTWIM CRs when testing
- Self-verifying commands with `oc wait` and `jsonpath`
- Cleanup in reverse order of creation
