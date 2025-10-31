---
description: Fix RBAC permission issues for a ClusterExtension (OLM v1 only)
argument-hint: <extension-name>
---

## Name
olm:fix-rbac

## Synopsis
```
/olm:fix-rbac <extension-name>
```

## Description
The `olm:fix-rbac` command diagnoses and fixes RBAC permission issues for a ClusterExtension that failed preflight checks in OLM v1.

**⚠️  OLM v1 ONLY**: This command only works with OLM v1. OLM v0 manages RBAC automatically via cluster-admin privileges.

When a ClusterExtension fails to install due to missing RBAC permissions (pre-authorization failures), this command:
- Identifies the missing permissions from status conditions
- Parses the RBAC requirements
- Updates the ClusterRole automatically or provides manual instructions
- Verifies the fix worked

## Implementation

The command performs the following steps:

1. **Check OLM Version** (v1 ONLY):
   ```bash
   # Check if version context is set
   if [ -f .work/olm/context.txt ]; then
     OLM_VERSION=$(cat .work/olm/context.txt)
     if [ "$OLM_VERSION" == "v0" ]; then
       echo "❌ Command not available for OLM v0"
       echo ""
       echo "The /olm:fix-rbac command is only available for OLM v1."
       echo "Current context: v0"
       echo ""
       echo "OLM v0 manages RBAC automatically via cluster-admin privileges."
       echo ""
       echo "To use this command with v1:"
       echo "  /olm:use-version v1"
       exit 1
     fi
   fi
   ```

2. **Prerequisites Check**:
   ```bash
   if ! command -v kubectl &> /dev/null; then
     echo "❌ 'kubectl' command not found"
     exit 1
   fi
   
   if ! kubectl get namespace olmv1-system &> /dev/null; then
     echo "❌ OLM v1 not installed"
     exit 1
   fi
   ```

3. **Verify ClusterExtension exists**:
   ```bash
   if ! kubectl get clusterextension {extension-name} &> /dev/null; then
     echo "❌ ClusterExtension not found: {extension-name}"
     echo ""
     echo "List available extensions: /olm:list"
     exit 1
   fi
   ```

4. **Get ClusterExtension status**:
   ```bash
   EXT=$(kubectl get clusterextension {extension-name} -o json)
   
   NAMESPACE=$(echo "$EXT" | jq -r '.spec.namespace')
   SA_NAME=$(echo "$EXT" | jq -r '.spec.serviceAccount.name')
   ```

5. **Check for pre-authorization failure**:
   ```bash
   PRE_AUTH_MSG=$(echo "$EXT" | jq -r '.status.conditions[] | 
     select(.message | contains("pre-authorization failed")) | .message')
   
   if [ -z "$PRE_AUTH_MSG" ]; then
     echo "✓ No pre-authorization errors found"
     echo ""
     echo "The ClusterExtension may already be installed or have different issues."
     echo "Check status: /olm:status {extension-name}"
     exit 0
   fi
   ```

6. **Parse missing permissions**:
   ```bash
   echo "Analyzing RBAC permissions for extension: {extension-name}"
   echo ""
   echo "Found pre-authorization failure in status conditions."
   echo ""
   
   # Extract permission lines from error message
   # Format:  Namespace:"" APIGroups:[] Resources:[services] Verbs:[list,watch]
   
   PERMISSION_LINES=$(echo "$PRE_AUTH_MSG" | grep -E '^\s*Namespace:')
   
   # Parse each line into structured format
   # This requires parsing:
   # - Namespace value (empty string means cluster-scoped)
   # - APIGroups list (empty [] means core group "")
   # - Resources list
   # - Verbs list
   ```

7. **Find existing ClusterRole**:
   ```bash
   # Find ClusterRoleBinding for this ServiceAccount
   CRB_NAME=$(kubectl get clusterrolebindings -o json | \
     jq -r --arg sa "$SA_NAME" --arg ns "$NAMESPACE" \
     '.items[] | select(.subjects[]? | 
       select(.kind=="ServiceAccount" and .name==$sa and .namespace==$ns)) | 
     .metadata.name' | head -1)
   
   if [ -z "$CRB_NAME" ]; then
     echo "❌ Cannot find ClusterRoleBinding for ServiceAccount: $SA_NAME"
     echo "The extension may not have been installed with proper RBAC."
     echo ""
     echo "Reinstall: /olm:install {extension-name} --channel <channel> --namespace $NAMESPACE"
     exit 1
   fi
   
   CR_NAME=$(kubectl get clusterrolebinding $CRB_NAME -o jsonpath='{.roleRef.name}')
   echo "Found ClusterRole: $CR_NAME"
   ```

8. **Display missing permissions**:
   ```bash
   echo ""
   echo "Missing RBAC Permissions:"
   echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
   echo ""
   
   # Parse and display permissions grouped by scope
   # - Cluster-scoped (Namespace:"")
   # - Namespace-scoped (Namespace:"xxx")
   
   echo "Cluster-scoped permissions needed:"
   # Display parsed permissions with API groups, resources, verbs
   
   echo ""
   echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
   echo ""
   echo "Current ServiceAccount: $SA_NAME (namespace: $NAMESPACE)"
   echo "Current ClusterRole: $CR_NAME"
   ```

9. **Offer to apply fixes**:
   ```bash
   read -p "Apply these fixes? (yes/no/show-yaml): " CHOICE
   
   case "$CHOICE" in
     yes|y)
       # Fetch current ClusterRole
       CURRENT_CR=$(kubectl get clusterrole $CR_NAME -o json)
       
       # Generate new rules from parsed permissions
       # Combine with existing rules
       
       # Apply updated ClusterRole
       echo "$UPDATED_CR" | kubectl apply -f -
       echo "✓ ClusterRole updated successfully"
       ;;
     show-yaml|show)
       # Display the complete updated ClusterRole YAML
       echo ""
       echo "Apply with: kubectl apply -f <file>"
       echo "$UPDATED_CR"
       ;;
     *)
       echo "Skipping automatic fix"
       exit 0
       ;;
   esac
   ```

10. **Monitor reconciliation**:
    ```bash
    if [ "$CHOICE" == "yes" ] || [ "$CHOICE" == "y" ]; then
      echo ""
      echo "Waiting for operator-controller to retry installation..."
      sleep 5
      
      # Check if pre-authorization error is cleared
      for i in {1..30}; do
        NEW_MSG=$(kubectl get clusterextension {extension-name} -o jsonpath='{.status.conditions[?(@.type=="Progressing")].message}')
        
        if [[ "$NEW_MSG" != *"pre-authorization failed"* ]]; then
          echo "✓ Pre-authorization check passed"
          
          INSTALLED=$(kubectl get clusterextension {extension-name} -o jsonpath='{.status.conditions[?(@.type=="Installed")].status}')
          if [ "$INSTALLED" == "True" ]; then
            echo "✓ Installation completed successfully"
          else
            echo "✓ Installation is now progressing"
          fi
          break
        fi
        sleep 2
      done
      
      echo ""
      echo "Monitor with: kubectl get clusterextension {extension-name} -w"
    fi
    ```

## Return Value
- **Success**: RBAC fixed and extension installation proceeding
- **No errors**: Extension already has proper RBAC
- **Error**: ClusterExtension not found, no ClusterRole, or permission denied

## Examples

### Example 1: Fix RBAC for failed extension

```bash
/olm:fix-rbac postgres-operator
```

Output:
```
Analyzing RBAC permissions for extension: postgres-operator

Found pre-authorization failure in status conditions.

Missing RBAC Permissions:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cluster-scoped permissions needed:
1. Core resources (APIGroup: "")
   - Resources: persistentvolumeclaims
   - Verbs: create, delete, get, list

2. Apps API (APIGroup: apps)
   - Resources: statefulsets
   - Verbs: create, update, patch, delete

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Current ServiceAccount: postgres-operator-sa (namespace: postgres-operator)
Current ClusterRole: postgres-operator-installer

Apply these fixes? (yes/no/show-yaml): yes

Updating ClusterRole: postgres-operator-installer...
✓ ClusterRole updated successfully

Waiting for operator-controller to retry installation...
✓ Pre-authorization check passed
✓ Installation is now progressing

Monitor with: kubectl get clusterextension postgres-operator -w
```

### Example 2: No errors found

```bash
/olm:fix-rbac cert-manager
```

Output:
```
Analyzing RBAC permissions for extension: cert-manager

✓ No pre-authorization errors found

The ClusterExtension is successfully installed with proper RBAC permissions.

Current RBAC configuration:
- ServiceAccount: cert-manager-sa (namespace: cert-manager)
- ClusterRole: cert-manager-installer
- All required permissions are granted
```

## Arguments
- **$1** (extension-name): Name of the ClusterExtension to fix (required)

## Notes

### Prerequisites
- OLM v1 must be installed
- Ideally, `PreflightPermissions` feature gate should be enabled for detailed error messages
- User must have permissions to update ClusterRoles

### Parsing Error Format
The pre-authorization error format from operator-controller:
```
pre-authorization failed: service account requires the following permissions to manage cluster extension:
 Namespace:"" APIGroups:[] Resources:[services] Verbs:[list,watch]
 Namespace:"myns" APIGroups:[apps] Resources:[deployments] Verbs:[create]
```

Rules:
- `Namespace:""` → cluster-scoped
- `APIGroups:[]` → core API group (use `""` in YAML)
- Parse comma-separated lists in brackets

### Automatic Retry
Once RBAC is fixed, operator-controller automatically retries installation without manual intervention.

### Feature Gate
If `PreflightPermissions` is not enabled:
- RBAC errors won't be caught early
- Installation will fail with less helpful error messages
- This command can still help but may require more manual investigation

### Troubleshooting
- If fix doesn't work, check operator-controller logs
- Verify feature gates are enabled correctly
- Ensure ServiceAccount and ClusterRole exist
- Use `/olm:status {extension-name}` for detailed status

