---
description: Uninstall an operator (v0) or extension (v1) from the cluster
argument-hint: <name> [namespace] [--remove-crds] [--remove-namespace] [--version v0|v1]
---

## Name
olm:uninstall

## Synopsis
```
/olm:uninstall <name> [namespace] [--remove-crds] [--remove-namespace] [--version v0|v1]
```

## Description
Safely uninstall an operator (OLM v0) or extension (OLM v1) from the cluster with optional cleanup of CRDs and namespaces.

**You must explicitly specify which OLM version to use** via `--version` flag or context.

## Implementation

### 1. Determine OLM Version
**See [skills/version-detection/SKILL.md](../../skills/version-detection/SKILL.md)**

---

## OLM v0 Implementation

### Steps

1. **Parse Arguments**:
   - `<operator-name>` (required)
   - `[namespace]` (optional, auto-discovered if not provided)
   - `--remove-crds`: Remove CRDs (WARNING: affects entire cluster)
   - `--remove-namespace`: Remove namespace after uninstall
   - `--force`: Skip confirmation prompts

2. **Find Operator**:
   ```bash
   if [ -z "{namespace}" ]; then
     CSV=$(oc get csv --all-namespaces -o json | \
       jq --arg op "{operator-name}" '.items[] | select(.metadata.name | contains($op))' | head -1)
     NAMESPACE=$(echo "$CSV" | jq -r '.metadata.namespace')
     CSV_NAME=$(echo "$CSV" | jq -r '.metadata.name')
   else
     NAMESPACE="{namespace}"
     CSV_NAME=$(oc get csv -n $NAMESPACE | grep {operator-name} | awk '{print $1}')
   fi
   ```

3. **Show What Will Be Removed**:
   ```bash
   echo "Preparing to uninstall: {operator-name}"
   echo ""
   echo "The following will be removed:"
   echo "  - Subscription"
   echo "  - CSV: $CSV_NAME"
   echo "  - Namespace: $NAMESPACE"
   
   if [ "{remove-crds}" == "true" ]; then
     CRD_COUNT=$(oc get crds -o json | jq --arg csv "$CSV_NAME" \
       '[.items[] | select(.metadata.annotations["olm.managed"]=="true")] | length')
     echo "  - CRDs: $CRD_COUNT (⚠️  AFFECTS ENTIRE CLUSTER)"
   fi
   ```

4. **Confirm with User** (if not --force):
   ```bash
   if [ "{force}" != "true" ]; then
     read -p "Do you want to proceed? (y/N): " CONFIRM
     if [ "$CONFIRM" != "y" ]; then
       echo "Uninstall cancelled"
       exit 0
     fi
   fi
   ```

5. **Delete Subscription**:
   ```bash
   SUB_NAME=$(oc get subscription -n $NAMESPACE -o json | \
     jq -r --arg csv "$CSV_NAME" '.items[] | select(.status.installedCSV==$csv) | .metadata.name')
   
   if [ -n "$SUB_NAME" ]; then
     oc delete subscription $SUB_NAME -n $NAMESPACE
     echo "✓ Deleted Subscription: $SUB_NAME"
   fi
   ```

6. **Delete CSV**:
   ```bash
   oc delete csv $CSV_NAME -n $NAMESPACE
   echo "✓ Deleted CSV: $CSV_NAME"
   ```

7. **Delete CRDs** (if requested):
   ```bash
   if [ "{remove-crds}" == "true" ]; then
     CRDS=$(oc get crds -o json | \
       jq -r --arg csv "$CSV_NAME" \
       '.items[] | select(.metadata.annotations["olm.managed"]=="true") | .metadata.name')
     
     for CRD in $CRDS; do
       oc delete crd $CRD
       echo "✓ Deleted CRD: $CRD"
     done
   fi
   ```

8. **Delete Namespace** (if requested):
   ```bash
   if [ "{remove-namespace}" == "true" ]; then
     oc delete namespace $NAMESPACE
     echo "✓ Deleted Namespace: $NAMESPACE"
   fi
   ```

---

## OLM v1 Implementation

### Steps

1. **Parse Arguments**:
   - `<extension-name>` (required)
   - `--remove-crds`: Remove CRDs
   - `--remove-namespace`: Remove namespace
   - `--force`: Skip confirmation

2. **Get ClusterExtension**:
   ```bash
   EXT=$(kubectl get clusterextension {extension-name} -o json 2>/dev/null)
   if [ -z "$EXT" ]; then
     echo "❌ Extension not found: {extension-name}"
     exit 1
   fi
   
   NAMESPACE=$(echo "$EXT" | jq -r '.spec.namespace')
   ```

3. **Show What Will Be Removed**:
   ```bash
   echo "Preparing to uninstall: {extension-name}"
   echo ""
   
   CRD_COUNT=$(kubectl get crds -l operators.coreos.com/clusterextension={extension-name} --no-headers | wc -l)
   
   echo "The following will be removed:"
   echo "  - ClusterExtension: {extension-name}"
   echo "  - ServiceAccount and RBAC"
   echo "  - Namespace: $NAMESPACE"
   
   if [ "{remove-crds}" == "true" ]; then
     echo "  - CRDs: $CRD_COUNT (⚠️  AFFECTS ENTIRE CLUSTER)"
   fi
   ```

4. **Confirm** (if not --force):
   ```bash
   if [ "{force}" != "true" ]; then
     read -p "Proceed with uninstall? (y/N): " CONFIRM
     if [ "$CONFIRM" != "y" ]; then
       exit 0
     fi
   fi
   ```

5. **Delete ClusterExtension**:
   ```bash
   kubectl delete clusterextension {extension-name}
   echo "✓ Deleted ClusterExtension: {extension-name}"
   ```

6. **Delete RBAC**:
   ```bash
   kubectl delete clusterrolebinding {extension-name}-installer --ignore-not-found
   kubectl delete clusterrole {extension-name}-installer --ignore-not-found
   kubectl delete serviceaccount {extension-name}-sa -n $NAMESPACE --ignore-not-found
   echo "✓ Deleted RBAC resources"
   ```

7. **Delete CRDs** (if requested):
   ```bash
   if [ "{remove-crds}" == "true" ]; then
     kubectl delete crds -l operators.coreos.com/clusterextension={extension-name}
     echo "✓ Deleted CRDs"
   fi
   ```

8. **Delete Namespace** (if requested):
   ```bash
   if [ "{remove-namespace}" == "true" ]; then
     kubectl delete namespace $NAMESPACE
     echo "✓ Deleted Namespace: $NAMESPACE"
   fi
   ```

---

## Return Value
- Confirmation of deleted resources
- Warning if any resources couldn't be deleted

## Examples

```bash
# Basic uninstall
/olm:uninstall cert-manager --version v1

# Full cleanup
/olm:uninstall postgres-operator --remove-crds --remove-namespace --version v0

# Force without confirmation
/olm:uninstall legacy-operator --force --version v0
```

## Arguments
- **$1** (name): Operator/extension name (required)
- **$2** (namespace): Namespace (v0 only, optional)
- **--remove-crds**: Remove CRDs (⚠️  WARNING: affects entire cluster)
- **--remove-namespace**: Remove namespace
- **--force**: Skip confirmation prompts
- **--version v0|v1**: OLM version

## Notes
- **CRD Removal**: Use with caution - affects entire cluster and deletes all custom resources
- **v0**: Deletes Subscription and CSV
- **v1**: Deletes ClusterExtension and associated RBAC
- Always backs up important custom resources before uninstalling
