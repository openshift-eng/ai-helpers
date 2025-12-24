---
description: Generate step-by-step ZTWIM test execution procedure for any ZTWIM PR
argument-hint: "<pr-url> [--env <cluster-type>]"
---

## Name
ztwim:generate-execution-steps

## Synopsis
```
/ztwim:generate-execution-steps <pr-url> [--env <cluster-type>]
```

## Description

Generates a complete test execution procedure for Zero Trust Workload Identity Manager (ZTWIM) operator PRs, including operator installation, all CR creation, and verification.

## ZTWIM Context

- **Operator**: Zero Trust Workload Identity Manager
- **Namespace**: `zero-trust-workload-identity-manager`
- **API Group**: `operator.openshift.io/v1alpha1`
- **Channel**: `tech-preview-v0.2`

### CRs (in creation order)
1. `ZeroTrustWorkloadIdentityManager` - Main CR
2. `SpireServer` - SPIRE server
3. `SpireAgent` - SPIRE agent
4. `SpiffeCSIDriver` - CSI driver
5. `SpireOIDCDiscoveryProvider` - OIDC provider

## Implementation

### Step 1: Generate Prerequisites

```bash
# Check oc CLI
which oc
oc version

# Check cluster access
oc whoami
oc get nodes

# Check cluster version
oc get clusterversion

# Check OLM is available
oc get packagemanifests -n openshift-marketplace | grep zero-trust
```

### Step 2: Generate ZTWIM Operator Installation

```bash
# Create namespace and install operator
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

# Wait for CSV to succeed
oc wait --for=jsonpath='{.status.phase}'=Succeeded \
  csv -l operators.coreos.com/openshift-zero-trust-workload-identity-manager.zero-trust-workload-identity-manager \
  -n zero-trust-workload-identity-manager --timeout=300s

# Verify operator pod is running
oc get pods -n zero-trust-workload-identity-manager
oc wait --for=condition=Available deployment -l app=zero-trust-workload-identity-manager \
  -n zero-trust-workload-identity-manager --timeout=300s
```

### Step 3: Generate Environment Setup

```bash
# Get cluster configuration for ZTWIM
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')
export JWT_ISSUER_ENDPOINT=oidc-discovery.${APP_DOMAIN}
export CLUSTER_NAME=$(oc get infrastructure cluster -o jsonpath='{.status.infrastructureName}')

# Verify variables
echo "APP_DOMAIN: $APP_DOMAIN"
echo "JWT_ISSUER_ENDPOINT: $JWT_ISSUER_ENDPOINT"
echo "CLUSTER_NAME: $CLUSTER_NAME"
```

### Step 4: Generate All ZTWIM CRs

```bash
# Create main CR first
oc apply -f - <<EOF
apiVersion: operator.openshift.io/v1alpha1
kind: ZeroTrustWorkloadIdentityManager
metadata:
  name: cluster
spec:
  trustDomain: $APP_DOMAIN
  clusterName: $CLUSTER_NAME
EOF

# Wait for main CR
oc wait --for=condition=Available zerotrustwworkloadidentitymanager/cluster --timeout=120s

# Create all operand CRs
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

# Wait for all CRs
oc wait --for=condition=Available spireserver/cluster --timeout=300s
oc wait --for=condition=Available spireagent/cluster --timeout=300s
```

### Step 5: Generate Verification

```bash
# Check all CRs exist
oc get zerotrustwworkloadidentitymanager,spireserver,spireagent,spiffecsidriver,spireoidcdiscoveryprovider

# Verify status of each CR
oc get zerotrustwworkloadidentitymanager cluster -o jsonpath='{.status}' | jq .
oc get spireserver cluster -o jsonpath='{.status}' | jq .
oc get spireagent cluster -o jsonpath='{.status}' | jq .

# Check pods created by operator
oc get pods -n zero-trust-workload-identity-manager

# Check operator logs
oc logs -n zero-trust-workload-identity-manager deployment/zero-trust-workload-identity-manager --tail=50

# Check events
oc get events -n zero-trust-workload-identity-manager --sort-by='.lastTimestamp' | tail -10
```

### Step 6: Generate Test for PR Changes

Based on what the PR modifies, generate specific tests:

#### Field Change Test
```bash
# Verify new field works (e.g., trustDomain on SpireServer)
oc get spireserver cluster -o jsonpath='{.spec.<newField>}'

# Update field
oc patch spireserver cluster --type=merge \
  -p '{"spec":{"<newField>":"<newValue>"}}'

# Verify update
oc get spireserver cluster -o jsonpath='{.spec.<newField>}'
```

#### Config Propagation Test
```bash
# Update main CR config
oc patch zerotrustwworkloadidentitymanager cluster --type=merge \
  -p '{"spec":{"trustDomain":"updated.example.org"}}'

sleep 15

# Verify propagation to operands
oc get spireserver cluster -o jsonpath='{.spec.trustDomain}'
oc get spireagent cluster -o jsonpath='{.spec.trustDomain}'
```

#### Controller Reconciliation Test
```bash
# Delete a child resource
oc delete deployment spire-server -n zero-trust-workload-identity-manager

# Verify operator recreates it
sleep 30
oc get deployment spire-server -n zero-trust-workload-identity-manager

# Check operator logs for reconciliation
oc logs -n zero-trust-workload-identity-manager deployment/zero-trust-workload-identity-manager --tail=20 | grep -i reconcil
```

### Step 7: Generate Cleanup

```bash
# Delete CRs (in reverse order of creation)
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

# Delete namespace
oc delete namespace zero-trust-workload-identity-manager

# Verify cleanup
oc get namespace zero-trust-workload-identity-manager 2>&1 | grep -q "not found" && echo "Cleanup complete"
```

## Example Output

For a ZTWIM PR like #72 (trustDomain propagation):

```markdown
# ZTWIM Execution Steps: PR #72 - Add trustDomain field propagation

## 1. Prerequisites

```bash
oc whoami
oc get clusterversion
oc get packagemanifests -n openshift-marketplace | grep zero-trust
```

## 2. Install ZTWIM Operator

```bash
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
```

## 3. Setup Environment

```bash
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')
export JWT_ISSUER_ENDPOINT=oidc-discovery.${APP_DOMAIN}
export CLUSTER_NAME=test01

echo "APP_DOMAIN: $APP_DOMAIN"
```

## 4. Create All ZTWIM CRs

```bash
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
```

## 5. Verify Setup

```bash
oc get zerotrustwworkloadidentitymanager,spireserver,spireagent,spiffecsidriver,spireoidcdiscoveryprovider
oc get pods -n zero-trust-workload-identity-manager
```

## 6. Test PR Changes (trustDomain propagation)

```bash
# Verify initial trustDomain
oc get spireserver cluster -o jsonpath='{.spec.trustDomain}'
oc get spireagent cluster -o jsonpath='{.spec.trustDomain}'

# Update trustDomain in main CR
oc patch zerotrustwworkloadidentitymanager cluster --type=merge \
  -p '{"spec":{"trustDomain":"updated.example.org"}}'

sleep 15

# Verify propagation to operands
oc get spireserver cluster -o jsonpath='{.spec.trustDomain}'
oc get spireagent cluster -o jsonpath='{.spec.trustDomain}'
```

## 7. Cleanup

```bash
oc delete spireoidcdiscoveryprovider cluster
oc delete spiffecsidriver cluster
oc delete spireagent cluster
oc delete spireserver cluster
oc delete zerotrustwworkloadidentitymanager cluster
oc delete subscription openshift-zero-trust-workload-identity-manager \
  -n zero-trust-workload-identity-manager
oc delete namespace zero-trust-workload-identity-manager
```

## Arguments

- **$1 (pr-url)**: ZTWIM GitHub PR URL
- **--env**: Target environment (optional: `aws`, `gcp`, `azure`, `vsphere`)

## Output

Complete ZTWIM execution procedure with:
1. Prerequisites check
2. ZTWIM operator installation via OLM
3. Environment variable setup (APP_DOMAIN, JWT_ISSUER_ENDPOINT, CLUSTER_NAME)
4. All ZTWIM CR creation (ZeroTrustWorkloadIdentityManager, SpireServer, SpireAgent, SpiffeCSIDriver, SpireOIDCDiscoveryProvider)
5. Verification steps
6. PR-specific test steps
7. Cleanup (in correct order)
