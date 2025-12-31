---
name: Operator Test Case Generator
description: Generate oc command-based test cases for any OpenShift operator PR based on context
---

# Operator Test Case Generator Skill

Generate test cases with `oc` commands by analyzing any OpenShift operator PR. The skill dynamically extracts operator context and adapts test generation accordingly.

## How to Extract Operator Context

### Step 1: Identify Operator from Repository

From the PR URL, extract:
- **Organization**: openshift, openshift-eng, red-hat-storage, etc.
- **Repository name**: Usually hints at operator name
- **Branch**: main, master, release-*

### Step 2: Find Key Files in Repository

Navigate to these paths to extract operator details:

| Path | What to Extract |
|------|-----------------|
| `config/manifests/bases/*.clusterserviceversion.yaml` | Package name, displayName, channel, installModes |
| `bundle/manifests/*.clusterserviceversion.yaml` | Alternative CSV location |
| `config/crd/bases/*.yaml` | CRD names, API groups, kinds, schemas |
| `api/**/types.go` or `api/**/*_types.go` | Go structs, field definitions |
| `config/manager/manager.yaml` | Deployment name, namespace, labels |
| `config/rbac/` | ServiceAccount, Roles, permissions |
| `config/samples/*.yaml` | Example CR manifests |
| `PROJECT` or `Makefile` | Domain, project name |

### Step 3: Extract OLM Information

From ClusterServiceVersion (CSV):

```yaml
# Key fields to extract
metadata:
  name: <operator>.v<version>  # Package name
spec:
  displayName: <Display Name>
  
  # Installation namespace
  installModes:
  - type: OwnNamespace
    supported: true
  - type: AllNamespaces
    supported: false
    
  # Owned CRDs
  customresourcedefinitions:
    owned:
    - name: <plural>.<group>
      version: <version>
      kind: <Kind>
      displayName: <CRD Display Name>
```

### Step 4: Extract CRD Information

From CRD YAML files:

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: <plural>.<group>
spec:
  group: <group>
  names:
    kind: <Kind>
    plural: <plural>
    singular: <singular>
  scope: Namespaced | Cluster
  versions:
  - name: <version>
    schema:
      openAPIV3Schema:
        properties:
          spec:
            properties:
              <field>:
                type: <type>
                description: <description>
```

### Step 5: Extract API Types

From Go type definitions:

```go
// api/v1alpha1/<kind>_types.go
type <Kind>Spec struct {
    // Field description
    Field1 string `json:"field1"`
    
    // +optional
    OptionalField string `json:"optionalField,omitempty"`
    
    // +kubebuilder:validation:Required
    RequiredField string `json:"requiredField"`
}
```

## Dynamic Templates

### Template 1: OLM Installation (Auto-detected)

```bash
# Variables extracted from CSV
OPERATOR_NAME="<from-csv-metadata.name>"
OPERATOR_NAMESPACE="<from-install-modes-or-default>"
PACKAGE_NAME="<from-csv-spec.name>"
CHANNEL="<from-csv-or-default>"
CATALOG_SOURCE="<redhat-operators|community-operators>"

# Create namespace
oc apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: $OPERATOR_NAMESPACE
EOF

# Create OperatorGroup
oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: ${OPERATOR_NAME}-og
  namespace: $OPERATOR_NAMESPACE
spec:
  upgradeStrategy: Default
EOF

# Create Subscription
oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: $OPERATOR_NAME
  namespace: $OPERATOR_NAMESPACE
spec:
  source: $CATALOG_SOURCE
  sourceNamespace: openshift-marketplace
  name: $PACKAGE_NAME
  channel: $CHANNEL
EOF

# Wait for operator
oc wait --for=condition=Available deployment -l app=$OPERATOR_NAME \
  -n $OPERATOR_NAMESPACE --timeout=300s
```

### Template 2: CR Creation (Auto-generated from CRD)

```bash
# Variables extracted from CRD
API_GROUP="<from-crd-spec.group>"
API_VERSION="<from-crd-spec.versions[0].name>"
KIND="<from-crd-spec.names.kind>"
PLURAL="<from-crd-spec.names.plural>"

# Create CR with fields from samples or schema
oc apply -f - <<EOF
apiVersion: $API_GROUP/$API_VERSION
kind: $KIND
metadata:
  name: test-instance
  namespace: $OPERATOR_NAMESPACE  # if namespaced
spec:
  # Fields auto-populated from:
  # 1. config/samples/*.yaml (preferred)
  # 2. CRD schema defaults
  # 3. PR changes
EOF

# Wait for CR
oc wait --for=condition=Ready $PLURAL/test-instance \
  -n $OPERATOR_NAMESPACE --timeout=120s
```

### Template 3: Multi-CRD Operator

When operator has multiple CRDs with dependencies:

```bash
# Create CRs in dependency order
# 1. Main/Manager CR first
# 2. Dependent CRs after

# Step 1: Create main CR
oc apply -f - <<EOF
apiVersion: <group>/<version>
kind: <MainKind>
metadata:
  name: cluster
spec:
  # Common configuration
EOF

oc wait --for=condition=Ready <main-plural>/cluster --timeout=120s

# Step 2: Create dependent CRs
oc apply -f - <<EOF
apiVersion: <group>/<version>
kind: <DependentKind1>
metadata:
  name: cluster
spec:
  # Inherits config from main CR
---
apiVersion: <group>/<version>
kind: <DependentKind2>
metadata:
  name: cluster
spec:
  # Another dependent
EOF
```

### Template 4: Field Test (Dynamic)

```bash
# Test new field from PR
FIELD_NAME="<extracted-from-pr>"
FIELD_VALUE="<from-pr-or-default>"

# Create with new field
oc apply -f - <<EOF
apiVersion: $API_GROUP/$API_VERSION
kind: $KIND
metadata:
  name: test-field
spec:
  $FIELD_NAME: $FIELD_VALUE
  # Required fields from CRD
EOF

# Verify
oc get $PLURAL test-field -o jsonpath="{.spec.$FIELD_NAME}"

# Update
oc patch $PLURAL test-field --type=merge \
  -p "{\"spec\":{\"$FIELD_NAME\":\"new-value\"}}"
```

### Template 5: Controller Test

```bash
# Check operator reconciles correctly
oc apply -f - <<EOF
apiVersion: $API_GROUP/$API_VERSION
kind: $KIND
metadata:
  name: test-reconcile
spec:
  <spec-from-samples>
EOF

# Wait for reconciliation
oc wait --for=condition=Ready $PLURAL/test-reconcile --timeout=120s

# Check child resources (labels from operator)
oc get all -l app.kubernetes.io/managed-by=$OPERATOR_NAME
oc get configmaps -l app.kubernetes.io/managed-by=$OPERATOR_NAME
oc get secrets -l app.kubernetes.io/managed-by=$OPERATOR_NAME

# Check operator logs
oc logs -n $OPERATOR_NAMESPACE deployment/$OPERATOR_NAME --tail=50
```

### Template 6: Negative Test

```bash
# Test validation
# Invalid value
oc apply -f - <<EOF 2>&1
apiVersion: $API_GROUP/$API_VERSION
kind: $KIND
metadata:
  name: test-invalid
spec:
  <required-field>: ""  # Empty when required
EOF
# Should show validation error

# Missing required field
oc apply -f - <<EOF 2>&1
apiVersion: $API_GROUP/$API_VERSION
kind: $KIND
metadata:
  name: test-missing
spec:
  # Missing <required-field>
EOF
```

## Common Cluster Variables

```bash
# These work for any OpenShift cluster
export CLUSTER_DOMAIN=$(oc get ingresses.config cluster -o jsonpath='{.spec.domain}')
export CLUSTER_NAME=$(oc get infrastructure cluster -o jsonpath='{.status.infrastructureName}')
export BASE_DOMAIN=$(oc get dns cluster -o jsonpath='{.spec.baseDomain}')
export API_SERVER=$(oc whoami --show-server)
export CLUSTER_VERSION=$(oc get clusterversion version -o jsonpath='{.status.desired.version}')
```

## Wait Patterns

```bash
# Wait for deployment
oc wait --for=condition=Available deployment/<name> -n <ns> --timeout=300s

# Wait for CR with Ready condition
oc wait --for=condition=Ready <plural>/<name> -n <ns> --timeout=120s

# Wait for CR with custom condition
oc wait --for=condition=<Condition>=True <plural>/<name> --timeout=120s

# Wait for pod
oc wait --for=condition=Ready pod -l <label> -n <ns> --timeout=120s

# Wait for CSV
oc wait --for=jsonpath='{.status.phase}'=Succeeded \
  csv -l operators.coreos.com/<package>.<namespace> -n <ns> --timeout=300s

# Wait for CRD to exist
until oc get crd <crd-name> 2>/dev/null; do sleep 5; done
```

## Verification Patterns

```bash
# Get CR status
oc get <plural> <name> -o jsonpath='{.status}'

# Get specific condition
oc get <plural> <name> -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'

# Get spec field
oc get <plural> <name> -o jsonpath='{.spec.<field>}'

# Check operator logs
oc logs -n <ns> deployment/<operator> --tail=100

# Check events
oc get events -n <ns> --sort-by='.lastTimestamp' | tail -10

# Check RBAC
oc auth can-i <verb> <resource> --as=system:serviceaccount:<ns>:<sa>
```

## Cleanup Pattern

```bash
# Always cleanup in reverse dependency order

# 1. Delete CRs (dependent first, main last)
oc delete <dependent-plural> <name> --ignore-not-found
oc delete <main-plural> <name> --ignore-not-found

# 2. Delete subscription
oc delete subscription <name> -n <namespace>

# 3. Delete CSV
oc delete csv -l operators.coreos.com/<package>.<namespace> -n <namespace>

# 4. Delete operator group
oc delete operatorgroup <name> -n <namespace>

# 5. Delete namespace
oc delete namespace <namespace>

# Verify
oc get namespace <namespace> 2>&1 | grep -q "not found" && echo "Cleanup complete"
```

## Operator-Specific Patterns

### Storage Operators
```bash
# Check storage classes
oc get sc

# Check PVs/PVCs
oc get pv,pvc -A
```

### Networking Operators
```bash
# Check routes
oc get routes -A

# Check ingress
oc get ingress -A
```

### Security Operators
```bash
# Check security context constraints
oc get scc

# Check secrets
oc get secrets -n <ns>
```

### Identity Operators
```bash
# Check OIDC endpoints
curl -k https://<oidc-endpoint>/.well-known/openid-configuration

# Check service accounts
oc get sa -n <ns>
```

## Output Guidelines

- **Extract actual values** from repository files
- **Use samples** from `config/samples/` when available
- **Include required fields** from CRD schema
- **Add environment variables** for cluster-specific values
- **Use `oc wait`** for self-verifying commands
- **Order cleanup correctly** based on dependencies
- **Include operator logs** check for debugging
