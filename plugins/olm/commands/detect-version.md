---
description: Auto-detect which OLM version(s) are installed in the cluster
---

## Name
olm:detect-version

## Synopsis
```
/olm:detect-version
```

## Description
The `olm:detect-version` command automatically detects which OLM version(s) are installed in your Kubernetes cluster by checking for characteristic namespaces, deployments, and resources. This helps you determine which version to use with OLM commands.

**Use this command when:**
- You're unsure which OLM version is installed in your cluster
- You want to verify OLM installation before running other commands
- You're working with a new cluster and need to understand its OLM setup
- Both OLM versions are installed and you want to know which to use

The command checks for both OLM v0 (traditional) and OLM v1 (next-generation) installations and provides detailed information about what was found.

## Implementation

1. **Check prerequisites**:
   ```bash
   # Check for oc CLI (used by OLM v0)
   if ! command -v oc &> /dev/null; then
     echo "⚠️  'oc' command not found - OLM v0 detection may be limited"
     echo "   Install from: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html"
     echo ""
   fi
   
   # Check for kubectl CLI (used by OLM v1)
   if ! command -v kubectl &> /dev/null; then
     echo "⚠️  'kubectl' command not found - OLM v1 detection may be limited"
     echo "   Install from: https://kubernetes.io/docs/tasks/tools/"
     echo ""
   fi
   
   # Check cluster access
   if ! oc whoami &> /dev/null && ! kubectl auth can-i get nodes &> /dev/null; then
     echo "❌ Cannot access cluster"
     echo "   Please ensure you are logged in to a Kubernetes/OpenShift cluster"
     exit 1
   fi
   ```

2. **Detect OLM v0**:
   ```bash
   echo "Checking for OLM v0 (traditional OLM)..."
   echo ""
   
   V0_DETECTED=false
   
   # Check for OLM v0 namespace
   if oc get namespace openshift-operator-lifecycle-manager --ignore-not-found &> /dev/null; then
     echo "✓ OLM v0 namespace found: openshift-operator-lifecycle-manager"
     V0_DETECTED=true
     
     # Check for OLM operator
     if oc get deployment olm-operator -n openshift-operator-lifecycle-manager --ignore-not-found &> /dev/null; then
       OLM_STATUS=$(oc get deployment olm-operator -n openshift-operator-lifecycle-manager -o jsonpath='{.status.conditions[?(@.type=="Available")].status}')
       if [ "$OLM_STATUS" == "True" ]; then
         echo "  ✓ olm-operator: Running"
       else
         echo "  ⚠️  olm-operator: Not ready"
       fi
     else
       echo "  ✗ olm-operator: Not found"
     fi
     
     # Check for Catalog operator
     if oc get deployment catalog-operator -n openshift-operator-lifecycle-manager --ignore-not-found &> /dev/null; then
       CATALOG_STATUS=$(oc get deployment catalog-operator -n openshift-operator-lifecycle-manager -o jsonpath='{.status.conditions[?(@.type=="Available")].status}')
       if [ "$CATALOG_STATUS" == "True" ]; then
         echo "  ✓ catalog-operator: Running"
       else
         echo "  ⚠️  catalog-operator: Not ready"
       fi
     else
       echo "  ✗ catalog-operator: Not found"
     fi
     
     # Get PackageServer version
     PACKAGESERVER_CSV=$(oc get csv -A -l olm.clusteroperator.name=packageserver --ignore-not-found -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
     if [ -n "$PACKAGESERVER_CSV" ]; then
       echo "  ✓ PackageServer CSV: $PACKAGESERVER_CSV"
     fi
     
     # Count catalog sources
     CATALOG_COUNT=$(oc get catalogsources -n openshift-marketplace --ignore-not-found 2>/dev/null | grep -v NAME | wc -l)
     if [ "$CATALOG_COUNT" -gt 0 ]; then
       echo "  ✓ CatalogSources: $CATALOG_COUNT available"
     else
       echo "  ⚠️  CatalogSources: None found"
     fi
     
     # Count installed operators
     CSV_COUNT=$(oc get csv --all-namespaces --ignore-not-found 2>/dev/null | grep -v NAME | wc -l)
     if [ "$CSV_COUNT" -gt 0 ]; then
       echo "  ✓ Installed operators: $CSV_COUNT"
     fi
     
   else
     echo "✗ OLM v0 not detected"
     echo "  Namespace 'openshift-operator-lifecycle-manager' not found"
   fi
   
   echo ""
   ```

3. **Detect OLM v1**:
   ```bash
   echo "Checking for OLM v1 (next-generation OLM)..."
   echo ""
   
   V1_DETECTED=false
   
   # Check for OLM v1 namespace
   if kubectl get namespace olmv1-system --ignore-not-found &> /dev/null; then
     echo "✓ OLM v1 namespace found: olmv1-system"
     V1_DETECTED=true
     
     # Check for operator-controller
     if kubectl get deployment operator-controller-controller-manager -n olmv1-system --ignore-not-found &> /dev/null; then
       CONTROLLER_STATUS=$(kubectl get deployment operator-controller-controller-manager -n olmv1-system -o jsonpath='{.status.conditions[?(@.type=="Available")].status}')
       if [ "$CONTROLLER_STATUS" == "True" ]; then
         echo "  ✓ operator-controller: Running"
       else
         echo "  ⚠️  operator-controller: Not ready"
       fi
       
       # Get controller image/version
       CONTROLLER_IMAGE=$(kubectl get deployment operator-controller-controller-manager -n olmv1-system -o jsonpath='{.spec.template.spec.containers[0].image}')
       if [ -n "$CONTROLLER_IMAGE" ]; then
         CONTROLLER_VERSION=$(echo "$CONTROLLER_IMAGE" | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1)
         if [ -n "$CONTROLLER_VERSION" ]; then
           echo "  ✓ Version: $CONTROLLER_VERSION"
         else
           echo "  ✓ Image: $CONTROLLER_IMAGE"
         fi
       fi
       
       # Check feature gates
       FEATURE_GATES=$(kubectl get deployment operator-controller-controller-manager -n olmv1-system -o jsonpath='{.spec.template.spec.containers[0].args}' | grep -o 'feature-gates=[^"]*' | head -1)
       if [ -n "$FEATURE_GATES" ]; then
         echo "  ✓ Feature gates: $FEATURE_GATES"
       fi
     else
       echo "  ✗ operator-controller: Not found"
     fi
     
     # Check for catalogd service
     if kubectl get service catalogd-service -n olmv1-system --ignore-not-found &> /dev/null; then
       echo "  ✓ catalogd-service: Available"
     fi
     
     # Count cluster catalogs
     CATALOG_COUNT=$(kubectl get clustercatalogs --ignore-not-found 2>/dev/null | grep -v NAME | wc -l)
     if [ "$CATALOG_COUNT" -gt 0 ]; then
       echo "  ✓ ClusterCatalogs: $CATALOG_COUNT available"
       # List them
       kubectl get clustercatalogs --no-headers 2>/dev/null | awk '{print "    - " $1}'
     else
       echo "  ⚠️  ClusterCatalogs: None found"
     fi
     
     # Count installed extensions
     EXTENSION_COUNT=$(kubectl get clusterextensions --ignore-not-found 2>/dev/null | grep -v NAME | wc -l)
     if [ "$EXTENSION_COUNT" -gt 0 ]; then
       echo "  ✓ Installed extensions: $EXTENSION_COUNT"
     fi
     
   else
     echo "✗ OLM v1 not detected"
     echo "  Namespace 'olmv1-system' not found"
   fi
   
   echo ""
   ```

4. **Provide summary and recommendations**:
   ```bash
   echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
   echo ""
   
   if [ "$V0_DETECTED" = true ] && [ "$V1_DETECTED" = true ]; then
     echo "📊 Summary: Both OLM v0 and v1 are installed"
     echo ""
     echo "You can use either version with this plugin:"
     echo ""
     echo "OLM v0 (Traditional):"
     echo "  - Best for: OpenShift operators, existing installations"
     echo "  - Resources: Subscription, CSV, InstallPlan"
     echo "  - Catalogs: CatalogSource"
     echo "  - Set context: /olm:use-version v0"
     echo ""
     echo "OLM v1 (Next-Generation):"
     echo "  - Best for: New installations, GitOps, flexible versioning"
     echo "  - Resources: ClusterExtension"
     echo "  - Catalogs: ClusterCatalog"
     echo "  - RBAC: User-managed (more control, more setup)"
     echo "  - Set context: /olm:use-version v1"
     echo ""
     echo "💡 Recommendation: Use v0 for OpenShift, v1 for new projects"
     
   elif [ "$V0_DETECTED" = true ]; then
     echo "📊 Summary: Only OLM v0 detected"
     echo ""
     echo "Your cluster has traditional OLM installed."
     echo ""
     echo "To use OLM commands with v0:"
     echo "  /olm:use-version v0"
     echo ""
     echo "Or use --version flag on each command:"
     echo "  /olm:install <operator> --version v0 [options]"
     
   elif [ "$V1_DETECTED" = true ]; then
     echo "📊 Summary: Only OLM v1 detected"
     echo ""
     echo "Your cluster has next-generation OLM installed."
     echo ""
     echo "To use OLM commands with v1:"
     echo "  /olm:use-version v1"
     echo ""
     echo "Or use --version flag on each command:"
     echo "  /olm:install <extension> --version v1 [options]"
     echo ""
     echo "⚠️  Note: OLM v1 requires user-managed RBAC (ServiceAccount + ClusterRole)"
     
   else
     echo "📊 Summary: No OLM installation detected"
     echo ""
     echo "Neither OLM v0 nor OLM v1 were found in this cluster."
     echo ""
     echo "To install OLM:"
     echo ""
     echo "For OLM v0 (traditional):"
     echo "  - OpenShift clusters have this pre-installed"
     echo "  - For vanilla Kubernetes: https://olm.operatorframework.io/"
     echo ""
     echo "For OLM v1 (next-generation):"
     echo "  - Installation guide: https://operator-framework.github.io/operator-controller/"
     echo "  - GitHub: https://github.com/operator-framework/operator-controller"
   fi
   
   echo ""
   echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
   ```

## Return Value
- **Success**: Detection report showing which OLM version(s) are installed with component status
- **Format**: Multi-section report with:
  - OLM v0 detection results
  - OLM v1 detection results
  - Summary and recommendations
  - Next steps for setting context

## Examples

1. **Both versions installed**:
   ```
   /olm:detect-version
   ```
   
   Output:
   ```
   Checking for OLM v0 (traditional OLM)...
   
   ✓ OLM v0 namespace found: openshift-operator-lifecycle-manager
     ✓ olm-operator: Running
     ✓ catalog-operator: Running
     ✓ PackageServer CSV: packageserver.v0.28.0
     ✓ CatalogSources: 4 available
     ✓ Installed operators: 12
   
   Checking for OLM v1 (next-generation OLM)...
   
   ✓ OLM v1 namespace found: olmv1-system
     ✓ operator-controller: Running
     ✓ Version: v0.5.0
     ✓ Feature gates: feature-gates=WebhookProviderCertManager=true
     ✓ catalogd-service: Available
     ✓ ClusterCatalogs: 2 available
       - operatorhubio
       - certified-operators
     ✓ Installed extensions: 3
   
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   
   📊 Summary: Both OLM v0 and v1 are installed
   
   You can use either version with this plugin:
   
   OLM v0 (Traditional):
     - Best for: OpenShift operators, existing installations
     - Set context: /olm:use-version v0
   
   OLM v1 (Next-Generation):
     - Best for: New installations, GitOps, flexible versioning
     - Set context: /olm:use-version v1
   ```

2. **Only v0 installed**:
   ```
   /olm:detect-version
   ```
   
   Output:
   ```
   Checking for OLM v0 (traditional OLM)...
   
   ✓ OLM v0 namespace found: openshift-operator-lifecycle-manager
     ✓ olm-operator: Running
     ✓ catalog-operator: Running
     ✓ CatalogSources: 4 available
   
   Checking for OLM v1 (next-generation OLM)...
   
   ✗ OLM v1 not detected
     Namespace 'olmv1-system' not found
   
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   
   📊 Summary: Only OLM v0 detected
   
   To use OLM commands with v0:
     /olm:use-version v0
   ```

3. **No OLM installed**:
   ```
   /olm:detect-version
   ```
   
   Output:
   ```
   Checking for OLM v0 (traditional OLM)...
   
   ✗ OLM v0 not detected
   
   Checking for OLM v1 (next-generation OLM)...
   
   ✗ OLM v1 not detected
   
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   
   📊 Summary: No OLM installation detected
   
   To install OLM:
   
   For OLM v0: https://olm.operatorframework.io/
   For OLM v1: https://operator-framework.github.io/operator-controller/
   ```

## Arguments
None - this command takes no arguments

## Notes

- **Cluster access required**: The command needs access to a Kubernetes/OpenShift cluster
- **Read-only**: This command only reads cluster state, it makes no changes
- **CLI requirements**: Works best with both `oc` and `kubectl` installed
- **Multiple versions**: It's possible (and sometimes useful) to have both OLM v0 and v1 installed
- **Feature gates**: For OLM v1, feature gates like `WebhookProviderCertManager` affect functionality
- **Next step**: After detecting OLM version(s), use `/olm:use-version` to set your context

