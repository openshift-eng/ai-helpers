---
description: Generate step-by-step test execution procedure for any PR
argument-hint: "<pr-url> [--env <cluster-type>]"
---

## Name
pr-test-generator:generate-execution-steps

## Synopsis
```
/pr-test-generator:generate-execution-steps <pr-url> [--env <cluster-type>]
```

## Description

Generates a complete test execution procedure including operator installation, CR creation, and verification.

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
oc get packagemanifests -n openshift-marketplace | head -5
```

### Step 2: Generate Operator Installation (OLM)

```bash
# Create namespace for operator
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

# Wait for CSV to succeed
oc wait --for=jsonpath='{.status.phase}'=Succeeded \
  csv -l operators.coreos.com/<operator-package>.<operator-namespace> \
  -n <operator-namespace> --timeout=300s

# Verify operator pod is running
oc get pods -n <operator-namespace>
```

### Step 3: Generate Environment Setup

```bash
# Get cluster configuration
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')
export JWT_ISSUER_ENDPOINT=oidc-discovery.${APP_DOMAIN}
export CLUSTER_NAME=$(oc get infrastructure cluster -o jsonpath='{.status.infrastructureName}')

# Verify variables
echo "APP_DOMAIN: $APP_DOMAIN"
echo "JWT_ISSUER_ENDPOINT: $JWT_ISSUER_ENDPOINT"
echo "CLUSTER_NAME: $CLUSTER_NAME"
```

### Step 4: Generate CR Creation

Based on PR type, generate appropriate CRs:

#### Single CR
```bash
oc apply -f - <<EOF
apiVersion: <apiVersion>
kind: <Kind>
metadata:
  name: cluster
spec:
  <field1>: $VAR1
  <field2>: $VAR2
EOF

oc wait --for=condition=Available <resource>/cluster --timeout=120s
```

#### Multiple Related CRs
```bash
# Create main CR
oc apply -f - <<EOF
apiVersion: <apiVersion>
kind: <MainKind>
metadata:
  name: cluster
spec:
  <mainSpec>
EOF

# Wait for main CR
oc wait --for=condition=Available <main-resource>/cluster --timeout=120s

# Create dependent CRs
oc apply -f - <<EOF
apiVersion: <apiVersion>
kind: <Kind1>
metadata:
  name: cluster
spec:
  <spec1>
---
apiVersion: <apiVersion>
kind: <Kind2>
metadata:
  name: cluster
spec:
  <spec2>
---
apiVersion: <apiVersion>
kind: <Kind3>
metadata:
  name: cluster
spec:
  <spec3>
EOF
```

### Step 5: Generate Verification

```bash
# Check all CRs exist
oc get <resource1>,<resource2>,<resource3>

# Verify status of each CR
oc get <resource1> cluster -o jsonpath='{.status}'
oc get <resource2> cluster -o jsonpath='{.status}'

# Check pods created by operator
oc get pods -n <operator-namespace>

# Check operator logs
oc logs -n <operator-namespace> deployment/<operator> --tail=50

# Check events
oc get events -n <operator-namespace> --sort-by='.lastTimestamp' | tail -10
```

### Step 6: Generate Test for PR Changes

Based on what the PR modifies:

#### Field Change Test
```bash
# Verify new field works
oc get <resource> cluster -o jsonpath='{.spec.<newField>}'

# Update field
oc patch <resource> cluster --type=merge \
  -p '{"spec":{"<newField>":"<newValue>"}}'

# Verify update
oc get <resource> cluster -o jsonpath='{.spec.<newField>}'
```

#### Config Propagation Test
```bash
# Update main CR
oc patch <main-resource> cluster --type=merge \
  -p '{"spec":{"<config>":"<newValue>"}}'

sleep 15

# Verify propagation to operands
oc get <operand1> cluster -o jsonpath='{.spec.<field>}'
oc get <operand2> cluster -o jsonpath='{.spec.<field>}'
```

### Step 7: Generate Cleanup

```bash
# Delete CRs (in reverse order of creation)
oc delete <operand3> cluster --ignore-not-found
oc delete <operand2> cluster --ignore-not-found
oc delete <operand1> cluster --ignore-not-found
oc delete <main-resource> cluster --ignore-not-found

# Delete operator subscription
oc delete subscription <subscription-name> -n <operator-namespace>

# Delete CSV
oc delete csv -l operators.coreos.com/<operator>.<namespace> -n <operator-namespace>

# Delete namespace
oc delete namespace <operator-namespace>

# Verify cleanup
oc get namespace <operator-namespace> 2>&1 | grep -q "not found" && echo "Cleanup complete"
```

## Example Output: ZTWIM PR

For a ZTWIM operator PR:

```markdown
# Execution Steps: PR #72

## 1. Prerequisites

oc whoami
oc get clusterversion
oc get packagemanifests -n openshift-marketplace | grep zero-trust

## 2. Install Operator

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

## 3. Setup Environment

export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{ .spec.baseDomain }')
export JWT_ISSUER_ENDPOINT=oidc-discovery.${APP_DOMAIN}
export CLUSTER_NAME=test01

## 4. Create CRs

oc apply -f - <<EOF
apiVersion: operator.openshift.io/v1alpha1
kind: ZeroTrustWorkloadIdentityManager
metadata:
  name: cluster
spec:
  trustDomain: $APP_DOMAIN
  clusterName: $CLUSTER_NAME
EOF

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

## 5. Verify

oc get zerotrustwworkloadidentitymanager,spireserver,spireagent,spiffecsidriver,spireoidcdiscoveryprovider

oc get pods -n zero-trust-workload-identity-manager

## 6. Test PR Changes (if config propagation PR)

oc patch zerotrustwworkloadidentitymanager cluster --type=merge \
  -p '{"spec":{"commonConfig":{"trustDomain":"updated.example.org"}}}'

sleep 15

oc get spireserver cluster -o jsonpath='{.spec.trustDomain}'
oc get spireagent cluster -o jsonpath='{.spec.trustDomain}'

## 7. Cleanup

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

- **$1 (pr-url)**: Any GitHub PR URL
- **--env**: Target environment (optional)

## Output

Complete execution procedure with:
1. Prerequisites check
2. Operator installation via OLM
3. Environment variable setup
4. CR creation (all related CRs)
5. Verification steps
6. PR-specific test steps
7. Cleanup
