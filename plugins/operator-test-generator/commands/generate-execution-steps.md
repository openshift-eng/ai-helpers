---
description: Generate step-by-step test execution procedure for any OpenShift operator PR
argument-hint: "<pr-url> [--env <cluster-type>]"
---

## Name
operator-test-generator:generate-execution-steps

## Synopsis
```
/operator-test-generator:generate-execution-steps <pr-url> [--env <cluster-type>]
```

## Description

Generates a complete test execution procedure for any OpenShift operator PR. The plugin dynamically extracts operator context and generates customized installation, CR creation, and verification steps.

## Implementation

### Step 1: Extract Operator Context

Navigate to the repository and extract:

```yaml
# Operator Context (to be filled dynamically)
operatorName: <extracted-from-repo>
namespace: <extracted-from-csv-or-manager>
packageName: <extracted-from-csv>
channel: <extracted-from-csv>
catalogSource: <redhat-operators|community-operators|custom>
crds:
  - group: <api-group>
    version: <version>
    kind: <Kind>
    plural: <plural>
installMode: <OwnNamespace|AllNamespaces>
```

### Step 2: Generate Prerequisites

```bash
# Check oc CLI
which oc
oc version

# Check cluster access
oc whoami
oc get nodes

# Check cluster version
oc get clusterversion

# Check if operator is available in catalog
oc get packagemanifests -n openshift-marketplace | grep -i <operator-keyword>

# Check existing CRDs (if upgrading)
oc get crd | grep <api-group>
```

### Step 3: Generate Operator Installation

#### For OLM-based Operators (most common)

```bash
# Create namespace
oc apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: <operator-namespace>
  labels:
    # Add any required labels from CSV
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
  name: <subscription-name>
  namespace: <operator-namespace>
spec:
  source: <catalog-source>
  sourceNamespace: openshift-marketplace
  name: <package-name>
  channel: <channel>
  installPlanApproval: Automatic
EOF

# Wait for CSV
oc wait --for=jsonpath='{.status.phase}'=Succeeded \
  csv -l operators.coreos.com/<package>.<namespace> \
  -n <operator-namespace> --timeout=300s

# Verify operator deployment
oc get pods -n <operator-namespace>
oc wait --for=condition=Available deployment/<operator-deployment> \
  -n <operator-namespace> --timeout=300s
```

#### For Direct Deployment (no OLM)

```bash
# Apply CRDs
oc apply -f https://raw.githubusercontent.com/<org>/<repo>/main/config/crd/bases/

# Apply RBAC
oc apply -f https://raw.githubusercontent.com/<org>/<repo>/main/config/rbac/

# Apply manager deployment
oc apply -f https://raw.githubusercontent.com/<org>/<repo>/main/config/manager/
```

### Step 4: Generate Environment Setup

```bash
# Common cluster variables
export CLUSTER_DOMAIN=$(oc get ingresses.config cluster -o jsonpath='{.spec.domain}')
export CLUSTER_NAME=$(oc get infrastructure cluster -o jsonpath='{.status.infrastructureName}')
export BASE_DOMAIN=$(oc get dns cluster -o jsonpath='{.spec.baseDomain}')

# Operator-specific variables (extracted from context)
# Examples:
# - For ingress operators: export APP_DOMAIN=apps.${BASE_DOMAIN}
# - For identity operators: export OIDC_ENDPOINT=...
# - For storage operators: export STORAGE_CLASS=...

echo "CLUSTER_DOMAIN: $CLUSTER_DOMAIN"
echo "CLUSTER_NAME: $CLUSTER_NAME"
```

### Step 5: Generate CR Creation

For each CRD found in the operator:

```bash
# Create <Kind> CR
oc apply -f - <<EOF
apiVersion: <group>/<version>
kind: <Kind>
metadata:
  name: <instance-name>
  namespace: <namespace>  # if namespaced scope
spec:
  # Fields from config/samples/ or CRD defaults
  <field1>: <value1>
  <field2>: <value2>
EOF

# Wait for CR to be ready
oc wait --for=condition=Ready <plural>/<instance-name> \
  -n <namespace> --timeout=120s
```

### Step 6: Generate PR-Specific Tests

Based on what the PR modifies:

#### For API/Field Changes
```bash
# Verify new field works
oc get <plural> <name> -o jsonpath='{.spec.<newField>}'

# Test field update
oc patch <plural> <name> --type=merge \
  -p '{"spec":{"<newField>":"<newValue>"}}'

# Verify update
oc get <plural> <name> -o jsonpath='{.spec.<newField>}'
```

#### For Controller Changes
```bash
# Check reconciliation
oc logs -n <operator-namespace> deployment/<operator> --tail=50 | grep -i reconcil

# Verify child resources created
oc get all -l <owner-label>=<cr-name>

# Check status conditions
oc get <plural> <name> -o jsonpath='{.status.conditions}' | jq .
```

#### For RBAC Changes
```bash
# Verify operator has new permissions
oc auth can-i <verb> <resource> --as=system:serviceaccount:<ns>:<sa>
```

### Step 7: Generate Verification

```bash
# Check all CRs
oc get <crd1>,<crd2>,<crd3>

# Verify status
oc get <plural> <name> -o jsonpath='{.status}'

# Check operator logs for errors
oc logs -n <operator-namespace> deployment/<operator> --tail=100 | grep -iE "error|warning" || echo "No errors"

# Check events
oc get events -n <operator-namespace> --sort-by='.lastTimestamp' | tail -10

# Check pods created by operator
oc get pods -l <operator-label>
```

### Step 8: Generate Cleanup

```bash
# Delete CRs (in reverse dependency order)
oc delete <plural-n> <name-n> --ignore-not-found
# ... repeat for each CR type

# Delete operator subscription
oc delete subscription <subscription-name> -n <operator-namespace>

# Delete CSV
oc delete csv -l operators.coreos.com/<package>.<namespace> -n <operator-namespace>

# Delete operator group
oc delete operatorgroup <operator>-og -n <operator-namespace>

# Delete namespace
oc delete namespace <operator-namespace>

# Verify cleanup
oc get namespace <operator-namespace> 2>&1 | grep -q "not found" && echo "Cleanup complete"
```

## Example Outputs

### Example 1: Generic Operator (LVMS)

```markdown
# Execution Steps: lvm-operator PR #500

## 1. Prerequisites
oc whoami
oc get packagemanifests -n openshift-marketplace | grep lvm

## 2. Install Operator
oc apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: openshift-storage
---
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: openshift-storage-og
  namespace: openshift-storage
---
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: lvms-operator
  namespace: openshift-storage
spec:
  source: redhat-operators
  sourceNamespace: openshift-marketplace
  name: lvms-operator
  channel: stable-4.14
EOF

## 3. Create LVMCluster CR
oc apply -f - <<EOF
apiVersion: lvm.topolvm.io/v1alpha1
kind: LVMCluster
metadata:
  name: my-lvmcluster
  namespace: openshift-storage
spec:
  storage:
    deviceClasses:
    - name: vg1
      default: true
      thinPoolConfig:
        name: thin-pool-1
        sizePercent: 90
        overprovisionRatio: 10
EOF

## 4. Verify
oc get lvmcluster -n openshift-storage
oc wait --for=condition=Ready lvmcluster/my-lvmcluster -n openshift-storage --timeout=300s

## 5. Cleanup
oc delete lvmcluster my-lvmcluster -n openshift-storage
oc delete subscription lvms-operator -n openshift-storage
oc delete namespace openshift-storage
```

### Example 2: Multi-CRD Operator (ZTWIM)

```markdown
# Execution Steps: zero-trust-workload-identity-manager PR #72

## 1. Prerequisites
oc whoami
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
  name: ztwim-og
  namespace: zero-trust-workload-identity-manager
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

## 3. Setup Environment
export APP_DOMAIN=apps.$(oc get dns cluster -o jsonpath='{.spec.baseDomain}')
export JWT_ISSUER=oidc-discovery.${APP_DOMAIN}

## 4. Create All CRs
oc apply -f - <<EOF
apiVersion: operator.openshift.io/v1alpha1
kind: ZeroTrustWorkloadIdentityManager
metadata:
  name: cluster
spec:
  trustDomain: $APP_DOMAIN
---
apiVersion: operator.openshift.io/v1alpha1
kind: SpireServer
metadata:
  name: cluster
spec:
  jwtIssuer: https://$JWT_ISSUER
---
apiVersion: operator.openshift.io/v1alpha1
kind: SpireAgent
metadata:
  name: cluster
spec:
  nodeAttestor:
    k8sPSATEnabled: "true"
EOF

## 5. Verify
oc get zerotrustwworkloadidentitymanager,spireserver,spireagent

## 6. Cleanup
oc delete spireagent cluster
oc delete spireserver cluster
oc delete zerotrustwworkloadidentitymanager cluster
oc delete namespace zero-trust-workload-identity-manager
```

## Arguments

- **$1 (pr-url)**: Any OpenShift operator GitHub PR URL
- **--env**: Target environment (`aws`, `gcp`, `azure`, `vsphere`, `baremetal`)

## Notes

- Dynamically extracts operator context from repository
- Adapts to OLM vs direct deployment
- Generates CR creation for all CRDs found
- Uses samples from repository when available
- Orders cleanup correctly based on dependencies
