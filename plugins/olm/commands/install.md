---
description: Install an operator (v0) or extension (v1) using OLM
argument-hint: <name> [options] [--version v0|v1]
---

## Name
olm:install

## Synopsis
```
/olm:install <name> [options] [--version v0|v1]
```

## Description
The `olm:install` command installs a Kubernetes operator or extension using Operator Lifecycle Manager. This unified command supports both OLM v0 (traditional) and OLM v1 (next-generation) architectures.

**You must explicitly specify which OLM version to use** via:
- `--version` flag on this command, OR
- Setting the context with `/olm:use-version v0|v1`

**OLM v0 (Traditional):**
- Installs operators using Subscription and CSV resources
- Requires OperatorGroup in the namespace
- Uses PackageManifest for operator discovery
- CLI: `oc` (OpenShift CLI)

**OLM v1 (Next-Generation):**
- Installs extensions using ClusterExtension resources
- Requires user-managed ServiceAccount with RBAC permissions
- Uses ClusterCatalog for package discovery
- CLI: `kubectl`
- More setup required but provides better control

## Implementation

### 1. Determine OLM Version

**See [skills/version-detection/SKILL.md](../../skills/version-detection/SKILL.md) for complete logic.**

```bash
# Check for --version flag in arguments
# If not found, check context file: .work/olm/context.txt
# If neither found, display error and exit
# Validate version is v0 or v1
```

### 2. Branch to Version-Specific Implementation

Based on the determined version, execute the appropriate implementation:

---

## OLM v0 Implementation

Used when `--version v0` or context is set to v0.

### Synopsis (v0)
```
/olm:install <operator-name> [namespace] [channel] [source] [--approval=Automatic|Manual] [--version v0]
```

### Steps

1. **Parse v0 Arguments**:
   - `$1`: Operator name (required) - e.g., "openshift-cert-manager-operator"
   - `$2`: Namespace (optional) - defaults to `{operator-name}`
   - `$3`: Channel (optional) - auto-discovered from PackageManifest if not provided
   - `$4`: Source (optional) - defaults to "redhat-operators"
   - `--approval=Automatic|Manual`: InstallPlan approval mode (default: Automatic)
   - `--version v0`: OLM version (optional if context is set)

2. **Prerequisites Check**:
   ```bash
   # Verify oc CLI is installed
   if ! command -v oc &> /dev/null; then
     echo "❌ 'oc' command not found"
     echo "Install from: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html"
     exit 1
   fi
   
   # Verify cluster access
   if ! oc whoami &> /dev/null; then
     echo "❌ Not logged in to OpenShift cluster"
     echo "Run: oc login <cluster-url>"
     exit 1
   fi
   ```

3. **Discover Operator Metadata** (if channel or source not provided):
   ```bash
   # Search for operator
   oc get packagemanifests -n openshift-marketplace | grep {operator-name}
   
   # Get PackageManifest details
   oc get packagemanifest {operator-name} -n openshift-marketplace -o json
   
   # Extract metadata
   DEFAULT_CHANNEL=$(oc get packagemanifest {operator-name} -n openshift-marketplace -o jsonpath='{.status.defaultChannel}')
   CATALOG_SOURCE=$(oc get packagemanifest {operator-name} -n openshift-marketplace -o jsonpath='{.status.catalogSource}')
   CATALOG_SOURCE_NS=$(oc get packagemanifest {operator-name} -n openshift-marketplace -o jsonpath='{.status.catalogSourceNamespace}')
   ```

4. **Create Namespace**:
   ```bash
   # Check if namespace exists
   if ! oc get namespace {namespace} &> /dev/null; then
     oc create namespace {namespace}
     echo "✓ Created namespace: {namespace}"
   else
     echo "ℹ️  Namespace already exists: {namespace}"
   fi
   ```

5. **Create OperatorGroup**:
   ```bash
   # Check if OperatorGroup exists
   OG_EXISTS=$(oc get operatorgroup -n {namespace} --no-headers 2>/dev/null | wc -l)
   
   if [ "$OG_EXISTS" -eq 0 ]; then
     cat <<EOF | oc apply -f -
   apiVersion: operators.coreos.com/v1
   kind: OperatorGroup
   metadata:
     name: {namespace}-operatorgroup
     namespace: {namespace}
   spec:
     targetNamespaces:
     - {namespace}
   EOF
     echo "✓ Created OperatorGroup: {namespace}-operatorgroup"
   else
     echo "ℹ️  OperatorGroup already exists in namespace"
   fi
   ```

6. **Create Subscription**:
   ```bash
   cat <<EOF | oc apply -f -
   apiVersion: operators.coreos.com/v1alpha1
   kind: Subscription
   metadata:
     name: {operator-name}
     namespace: {namespace}
   spec:
     channel: {channel}
     name: {operator-name}
     source: {source}
     sourceNamespace: {catalog-source-namespace}
     installPlanApproval: {approval}
   EOF
   echo "✓ Created Subscription: {operator-name}"
   ```

7. **Monitor Installation**:
   ```bash
   echo "Waiting for CSV to be created..."
   
   # Wait for InstallPlan
   oc wait --for=condition=AtLatestKnown subscription/{operator-name} -n {namespace} --timeout=5m
   
   # Check if manual approval needed
   if [ "{approval}" == "Manual" ]; then
     PENDING=$(oc get installplan -n {namespace} -l operators.coreos.com/{operator-name} -o jsonpath='{.items[?(@.spec.approved==false)].metadata.name}')
     if [ -n "$PENDING" ]; then
       echo "⏸️  InstallPlan requires manual approval: $PENDING"
       echo "To approve: /olm:approve {operator-name} {namespace}"
     fi
   fi
   
   # Wait for CSV to reach Succeeded
   CSV_NAME=""
   for i in {1..30}; do
     CSV_NAME=$(oc get csv -n {namespace} --no-headers 2>/dev/null | grep {operator-name} | awk '{print $1}' | head -1)
     if [ -n "$CSV_NAME" ]; then
       CSV_PHASE=$(oc get csv $CSV_NAME -n {namespace} -o jsonpath='{.status.phase}')
       if [ "$CSV_PHASE" == "Succeeded" ]; then
         break
       fi
     fi
     sleep 10
   done
   ```

8. **Display Results**:
   ```bash
   if [ "$CSV_PHASE" == "Succeeded" ]; then
     echo "✓ Operator installed successfully"
     echo ""
     echo "CSV: $CSV_NAME"
     echo "Status: $CSV_PHASE"
     echo "Namespace: {namespace}"
     echo ""
     oc get deployments -n {namespace}
     echo ""
     oc get pods -n {namespace}
   else
     echo "⚠️  Installation may still be in progress"
     echo "Check status with: /olm:status {operator-name} {namespace}"
   fi
   ```

---

## OLM v1 Implementation

Used when `--version v1` or context is set to v1.

### Synopsis (v1)
```
/olm:install <extension-name> [--channel <channel>] [--version <version>] [--catalog <catalog>] [--namespace <namespace>] [--version v1]
```

### Steps

1. **Parse v1 Arguments**:
   - `$1`: Extension name (required) - e.g., "cert-manager"
   - `--channel <channel>`: Channel to track (optional)
   - `--version <version>`: Version constraint (optional, e.g., "1.14.5" or ">=1.14.0 <1.15.0")
   - `--catalog <catalog>`: ClusterCatalog name (optional, auto-detected if not specified)
   - `--namespace <namespace>`: Target namespace (required for installation)
   - `--version v1`: OLM version (optional if context is set)
   
   Note: Either `--channel` OR `--version` should be specified, not both.

2. **Prerequisites Check**:
   ```bash
   # Verify kubectl CLI is installed
   if ! command -v kubectl &> /dev/null; then
     echo "❌ 'kubectl' command not found"
     echo "Install from: https://kubernetes.io/docs/tasks/tools/"
     exit 1
   fi
   
   # Verify cluster access
   if ! kubectl auth can-i get clusterextensions &> /dev/null; then
     echo "❌ Cannot access cluster or insufficient permissions"
     exit 1
   fi
   
   # Check if OLM v1 is installed
   if ! kubectl get namespace olmv1-system &> /dev/null; then
     echo "❌ OLM v1 not installed in this cluster"
     echo "Install from: https://operator-framework.github.io/operator-controller/"
     exit 1
   fi
   ```

3. **Check operator-controller Feature Gates**:
   ```bash
   echo "Checking operator-controller configuration..."
   
   FEATURE_GATES=$(kubectl get deployment operator-controller-controller-manager -n olmv1-system \
     -o jsonpath='{.spec.template.spec.containers[0].args}' | grep -o 'feature-gates=[^"]*' || echo "none")
   
   echo "Feature gates: $FEATURE_GATES"
   
   # Check if webhook support is enabled
   if [[ "$FEATURE_GATES" != *"WebhookProviderCertManager"* ]] && [[ "$FEATURE_GATES" != *"WebhookProviderOpenshiftServiceCA"* ]]; then
     echo "⚠️  Webhook support not enabled - operators with webhooks will fail"
     echo "To enable: kubectl patch deployment operator-controller-controller-manager -n olmv1-system --type=json \\"
     echo "  -p='[{\"op\": \"add\", \"path\": \"/spec/template/spec/containers/0/args/-\", \"value\": \"--feature-gates=WebhookProviderCertManager=true\"}]'"
   fi
   ```

4. **Validate Extension Exists**:
   ```bash
   echo "Searching for extension: {extension-name}"
   
   # If catalog specified, search only that catalog
   if [ -n "{catalog}" ]; then
     FOUND=$(kubectl get packages -A -l catalog={catalog} | grep {extension-name} || true)
   else
     # Search all catalogs
     FOUND=$(kubectl get packages -A | grep {extension-name} || true)
   fi
   
   if [ -z "$FOUND" ]; then
     echo "❌ Extension not found: {extension-name}"
     echo "Search for available extensions: /olm:search {extension-name} --version v1"
     exit 1
   fi
   
   echo "✓ Extension found in catalog"
   ```

5. **Create Namespace**:
   ```bash
   if ! kubectl get namespace {namespace} &> /dev/null; then
     kubectl create namespace {namespace}
     echo "✓ Created namespace: {namespace}"
   else
     echo "ℹ️  Namespace already exists: {namespace}"
   fi
   ```

6. **Create ServiceAccount**:
   ```bash
   SA_NAME="{extension-name}-sa"
   
   kubectl create serviceaccount $SA_NAME -n {namespace} --dry-run=client -o yaml | kubectl apply -f -
   echo "✓ Created ServiceAccount: $SA_NAME"
   ```

7. **Create Baseline ClusterRole with RBAC**:
   ```bash
   cat <<EOF | kubectl apply -f -
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRole
   metadata:
     name: {extension-name}-installer
   rules:
   # Common core resources
   - apiGroups: [""]
     resources: ["services", "serviceaccounts", "configmaps", "secrets"]
     verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
   - apiGroups: [""]
     resources: ["namespaces"]
     verbs: ["get", "list", "watch"]
   # Apps resources
   - apiGroups: ["apps"]
     resources: ["deployments", "statefulsets", "daemonsets"]
     verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
   # RBAC (needed for operator to create its own roles)
   - apiGroups: ["rbac.authorization.k8s.io"]
     resources: ["roles", "rolebindings", "clusterroles", "clusterrolebindings"]
     verbs: ["get", "list", "watch", "create", "update", "patch", "delete", "bind", "escalate"]
   # CRDs
   - apiGroups: ["apiextensions.k8s.io"]
     resources: ["customresourcedefinitions"]
     verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
   # Admission webhooks
   - apiGroups: ["admissionregistration.k8s.io"]
     resources: ["validatingwebhookconfigurations", "mutatingwebhookconfigurations"]
     verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
   # cert-manager resources (if webhooks are enabled)
   - apiGroups: ["cert-manager.io"]
     resources: ["certificates", "issuers", "certificaterequests"]
     verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
   EOF
   echo "✓ Created ClusterRole: {extension-name}-installer"
   ```

8. **Create ClusterRoleBinding**:
   ```bash
   cat <<EOF | kubectl apply -f -
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRoleBinding
   metadata:
     name: {extension-name}-installer
   roleRef:
     apiGroup: rbac.authorization.k8s.io
     kind: ClusterRole
     name: {extension-name}-installer
   subjects:
   - kind: ServiceAccount
     name: $SA_NAME
     namespace: {namespace}
   EOF
   echo "✓ Created ClusterRoleBinding: {extension-name}-installer"
   ```

9. **Create ClusterExtension**:
   ```bash
   # Build version/channel constraint
   if [ -n "{channel}" ]; then
     VERSION_SPEC="channel: \"{channel}\""
   elif [ -n "{version}" ]; then
     VERSION_SPEC="version: \"{version}\""
   else
     echo "❌ Must specify either --channel or --version"
     exit 1
   fi
   
   cat <<EOF | kubectl apply -f -
   apiVersion: olm.operatorframework.io/v1alpha1
   kind: ClusterExtension
   metadata:
     name: {extension-name}
   spec:
     namespace: {namespace}
     serviceAccount:
       name: $SA_NAME
     source:
       sourceType: Catalog
       catalog:
         packageName: {extension-name}
         $VERSION_SPEC
   EOF
   echo "✓ Created ClusterExtension: {extension-name}"
   ```

10. **Monitor Installation and Handle Errors**:
    ```bash
    echo ""
    echo "Monitoring installation..."
    
    # Wait and check status
    for i in {1..60}; do
      STATUS=$(kubectl get clusterextension {extension-name} -o jsonpath='{.status.conditions[?(@.type=="Installed")].status}' 2>/dev/null || echo "Unknown")
      PROGRESSING=$(kubectl get clusterextension {extension-name} -o jsonpath='{.status.conditions[?(@.type=="Progressing")].status}' 2>/dev/null || echo "Unknown")
      
      if [ "$STATUS" == "True" ]; then
        echo "✓ Installation completed successfully"
        break
      fi
      
      # Check for errors
      ERROR_MSG=$(kubectl get clusterextension {extension-name} -o jsonpath='{.status.conditions[?(@.type=="Progressing")].message}' 2>/dev/null || echo "")
      
      # Check for webhook errors
      if [[ "$ERROR_MSG" == *"webhookDefinitions are not supported"* ]]; then
        echo ""
        echo "❌ Webhook support required but not enabled"
        echo ""
        echo "This extension requires webhooks. Enable the feature gate:"
        echo "  kubectl patch deployment operator-controller-controller-manager -n olmv1-system --type=json \\"
        echo "    -p='[{\"op\": \"add\", \"path\": \"/spec/template/spec/containers/0/args/-\", \"value\": \"--feature-gates=WebhookProviderCertManager=true\"}]'"
        echo ""
        echo "Then trigger reconciliation:"
        echo "  kubectl annotate clusterextension {extension-name} reconcile=\"\$(date +%s)\" --overwrite"
        exit 1
      fi
      
      # Check for RBAC errors
      if [[ "$ERROR_MSG" == *"pre-authorization failed"* ]]; then
        echo ""
        echo "⚠️  RBAC permission issues detected"
        echo ""
        echo "$ERROR_MSG"
        echo ""
        echo "Missing permissions need to be added to the ClusterRole."
        echo "Use: /olm:fix-rbac {extension-name} --version v1"
        echo ""
        # Don't exit, continue monitoring in case of auto-fix
      fi
      
      sleep 5
    done
    ```

11. **Display Results**:
    ```bash
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "Installation Summary"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    # Get resolved version
    RESOLVED_VERSION=$(kubectl get clusterextension {extension-name} -o jsonpath='{.status.resolution.bundle.version}')
    RESOLVED_CHANNEL=$(kubectl get clusterextension {extension-name} -o jsonpath='{.status.resolution.bundle.channel}')
    
    echo "Extension: {extension-name}"
    echo "Version: $RESOLVED_VERSION"
    echo "Channel: $RESOLVED_CHANNEL"
    echo "Namespace: {namespace}"
    echo "ServiceAccount: $SA_NAME"
    echo "ClusterRole: {extension-name}-installer"
    echo ""
    
    # Show CRDs
    echo "Custom Resource Definitions:"
    kubectl get crds -l operators.coreos.com/clusterextension={extension-name} --no-headers 2>/dev/null | awk '{print "  - " $1}'
    echo ""
    
    # Show workloads
    echo "Workloads in {namespace}:"
    kubectl get deployments,statefulsets,daemonsets -n {namespace} --no-headers 2>/dev/null | awk '{print "  - " $1 " (" $2 ")"}'
    echo ""
    
    echo "Next steps:"
    echo "  - Check status: /olm:status {extension-name} --version v1"
    echo "  - List all extensions: /olm:list --version v1"
    ```

---

## Return Value

### OLM v0
- **Success**: Operator installed with CSV in Succeeded state
- **Format**: 
  - Namespace created/used
  - OperatorGroup status
  - Subscription created
  - CSV status and version
  - Deployment and pod status

### OLM v1
- **Success**: Extension installed with ClusterExtension in Installed state
- **Format**:
  - Namespace created/used
  - ServiceAccount and RBAC created
  - ClusterExtension status
  - Resolved version and channel
  - CRDs and workloads

## Examples

### Example 1: Install with OLM v0 (using context)

```bash
# Set context once
/olm:use-version v0

# Install operator with defaults
/olm:install openshift-cert-manager-operator

# Install with custom namespace and channel
/olm:install external-secrets-operator eso-operator stable-v0.10
```

### Example 2: Install with OLM v1 (using flag)

```bash
# Install extension with explicit version flag
/olm:install cert-manager --version v1 --channel stable --namespace cert-manager

# Install with specific version constraint
/olm:install postgres-operator --version v1 --version ">=1.0.0 <2.0.0" --namespace postgres
```

### Example 3: Mixed workflow

```bash
# Set default to v0
/olm:use-version v0

# Install v0 operator (uses context)
/olm:install openshift-pipelines-operator

# Install v1 extension (override with flag)
/olm:install argocd --version v1 --channel stable --namespace argocd
```

### Example 4: Manual approval mode (v0 only)

```bash
/olm:install prometheus --version v0 --approval=Manual
# Then later approve with: /olm:approve prometheus
```

## Arguments

### Common
- **--version v0|v1**: OLM version to use (optional if context is set)

### OLM v0 Specific
- **$1** (operator-name): Name of the operator (required)
- **$2** (namespace): Target namespace (optional, defaults to operator name)
- **$3** (channel): Subscription channel (optional, auto-discovered)
- **$4** (source): CatalogSource name (optional, defaults to "redhat-operators")
- **--approval=Automatic|Manual**: InstallPlan approval mode (default: Automatic)

### OLM v1 Specific
- **$1** (extension-name): Name of the extension (required)
- **--channel <channel>**: Channel to track (optional, conflicts with --version)
- **--version <version>**: Version constraint (optional, conflicts with --channel)
- **--catalog <catalog>**: ClusterCatalog name (optional, auto-detected)
- **--namespace <namespace>**: Target namespace (required)

## Notes

### OLM v0 Notes
- Namespace convention: Defaults to `{operator-name}`
- OperatorGroup is automatically created if none exists
- InstallPlan approval can be Automatic or Manual
- Verification timeout: 5 minutes

### OLM v1 Notes
- **CRITICAL**: User must provide ServiceAccount with RBAC (unlike v0 which has cluster-admin)
- Baseline RBAC is created but may need additional permissions
- If preflight checks fail, use `/olm:fix-rbac` to add missing permissions
- Webhook support requires feature gate enabled
- Either specify `--channel` OR `--version`, not both
- Version constraints support semver ranges (e.g., ">=1.0.0 <2.0.0", "~1.14.0")

### Common Notes
- Use `/olm:detect-version` if unsure which OLM version is installed
- Use `/olm:use-version` to set context and avoid repeating --version flag
- Flag always overrides context
- No default version - must be explicitly specified
