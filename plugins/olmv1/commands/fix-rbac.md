# Fix RBAC Permissions Command

You are helping the user diagnose and fix RBAC permission issues for a ClusterExtension that failed preflight checks.

## Task

Analyze a ClusterExtension's status conditions to identify missing RBAC permissions and either suggest or automatically apply the fixes.

## Prerequisites

- The ClusterExtension must exist in the cluster
- Ideally, the `PreflightPermissions` feature gate should be enabled for detailed permission analysis
- User must have permissions to update ClusterRoles and ClusterRoleBindings

## Steps

1. **Verify ClusterExtension exists**:
   ```bash
   kubectl get clusterextension <extension-name>
   ```

2. **Get ClusterExtension full status**:
   ```bash
   kubectl get clusterextension <extension-name> -o yaml
   ```

3. **Extract namespace and service account information**:
   ```bash
   # Get namespace
   NAMESPACE=$(kubectl get clusterextension <extension-name> -o jsonpath='{.spec.namespace}')

   # Get service account name
   SA_NAME=$(kubectl get clusterextension <extension-name> -o jsonpath='{.spec.serviceAccount.name}')
   ```

4. **Check for pre-authorization failure in status conditions**:
   ```bash
   kubectl get clusterextension <extension-name> -o jsonpath='{.status.conditions}' | \
     jq -r '.[] | select(.message | contains("pre-authorization failed")) | .message'
   ```

5. **Parse missing permissions from the error message**:

   The error message format looks like:
   ```
   pre-authorization failed: service account requires the following permissions to manage cluster extension:
    Namespace:"" APIGroups:[] Resources:[services] Verbs:[list,watch]
    Namespace:"postgres-operator" APIGroups:[apps] Resources:[statefulsets] Verbs:[create,update,delete]
   ```

   Extract each permission line and parse into structured data:
   - `Namespace:""` → cluster-scoped (empty namespace)
   - `Namespace:"<name>"` → namespace-scoped
   - `APIGroups:[]` → core API group (use `""` in YAML)
   - `APIGroups:[group1,group2]` → specific API groups
   - `Resources:[...]` → resource types
   - `Verbs:[...]` → required verbs

6. **Find existing ClusterRole or RoleBinding**:
   ```bash
   # Find ClusterRoleBindings for the service account
   kubectl get clusterrolebindings -o json | \
     jq -r --arg sa "$SA_NAME" --arg ns "$NAMESPACE" \
     '.items[] | select(.subjects[]? | select(.kind=="ServiceAccount" and .name==$sa and .namespace==$ns)) | .metadata.name'

   # Get the ClusterRole name from the binding
   CLUSTERROLE=$(kubectl get clusterrolebinding <binding-name> -o jsonpath='{.roleRef.name}')
   ```

7. **Generate RBAC rules from parsed permissions**:

   For each missing permission, create a YAML rule:

   ```yaml
   - apiGroups: ["<group>"]  # or [""] for core
     resources: ["<resource1>", "<resource2>"]
     verbs: ["<verb1>", "<verb2>"]
     # Add resourceNames: [] if specific resource names are mentioned
   ```

   Special cases:
   - If namespace is empty (`Namespace:""`), this goes in a ClusterRole (cluster-scoped)
   - If namespace is specified, this could go in a Role (namespace-scoped) OR ClusterRole
   - Multiple resources with same APIGroup and Namespace can be combined into one rule
   - Combine verbs when resources and APIGroups match

8. **Present the missing permissions**:

   Show a clear summary:
   ```
   Missing RBAC Permissions for <extension-name>:

   Cluster-scoped permissions (ClusterRole):
   - APIGroups: [""], Resources: ["services"], Verbs: ["list", "watch"]
   - APIGroups: ["apps"], Resources: ["statefulsets"], Verbs: ["create", "update", "delete"]

   Namespace-scoped permissions in '<namespace>':
   - APIGroups: [""], Resources: ["configmaps"], Verbs: ["get", "create"]
   ```

9. **Offer to apply fixes automatically OR show manual instructions**:

   **Option A: Automatic (if user wants)**
   - Fetch the existing ClusterRole
   - Add the missing rules to the ClusterRole
   - Apply the updated ClusterRole
   - Wait for the ClusterExtension to reconcile and retry installation

   **Option B: Manual instructions**
   - Display the complete YAML for the updated ClusterRole
   - Provide `kubectl apply -f` command
   - Explain that the operator-controller will automatically retry once RBAC is fixed

10. **Verify the fix worked**:
    After applying RBAC changes, monitor the ClusterExtension:
    ```bash
    kubectl get clusterextension <extension-name> -w
    ```

    Check if the pre-authorization error is cleared:
    ```bash
    kubectl get clusterextension <extension-name> -o jsonpath='{.status.conditions}' | \
      jq '.[] | select(.type=="Progressing" or .type=="Installed")'
    ```

11. **Report results**:
    - If automatic fix applied: Show the updated ClusterRole and confirm installation is proceeding
    - If manual instructions: Provide the complete YAML and apply command
    - Show the expected next state (installation should proceed automatically)

## Error Handling

- **ClusterExtension not found**: Suggest using `/olmv1:list` to see available extensions
- **No pre-authorization errors**: Check if extension is already installed or has other errors
- **PreflightPermissions feature gate disabled**:
  - Explain that preflight checks are not enabled
  - Suggest enabling the feature gate or reviewing operator-controller logs
  - Provide general RBAC troubleshooting guidance
- **Cannot find existing ClusterRole**:
  - Explain that RBAC may not have been set up
  - Suggest using `/olmv1:install` which creates RBAC automatically
- **Permission denied updating ClusterRole**:
  - User doesn't have cluster-admin or sufficient RBAC permissions
  - Show the YAML they need to apply manually or ask their cluster admin

## Parsing Pre-authorization Error Format

The error message format from operator-controller is:
```
pre-authorization failed: service account requires the following permissions to manage cluster extension:
 Namespace:"<ns-or-empty>" APIGroups:[<groups>] Resources:[<resources>] Verbs:[<verbs>]
```

Parsing rules:
1. Look for lines starting with ` Namespace:"`
2. Extract namespace value (empty string means cluster-scoped)
3. Extract APIGroups (comma-separated list in brackets, empty `[]` means core group)
4. Extract Resources (comma-separated list in brackets)
5. Extract Verbs (comma-separated list in brackets)

Example parsing:
```
Input:  Namespace:"" APIGroups:[] Resources:[services] Verbs:[list,watch]
Output: {namespace: "", apiGroups: [""], resources: ["services"], verbs: ["list", "watch"]}

Input:  Namespace:"myns" APIGroups:[apps,batch] Resources:[deployments,jobs] Verbs:[create]
Output: {namespace: "myns", apiGroups: ["apps", "batch"], resources: ["deployments", "jobs"], verbs: ["create"]}
```

## Example Output

### When Pre-authorization Errors Found

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

Namespace-scoped permissions in "postgres-operator":
3. Core resources (APIGroup: "")
   - Resources: secrets
   - Verbs: get, list, watch

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Current ServiceAccount: postgres-operator-sa (namespace: postgres-operator)
Current ClusterRole: postgres-operator-installer

Apply these fixes? (yes/no/show-yaml): yes

Updating ClusterRole: postgres-operator-installer...
✓ ClusterRole updated successfully

Waiting for operator-controller to retry installation...
✓ Pre-authorization check passed
✓ Installation is now progressing

The ClusterExtension should install successfully now.
Monitor with: kubectl get clusterextension postgres-operator -w
```

### When No Errors Found

```
Analyzing RBAC permissions for extension: postgres-operator

✓ No pre-authorization errors found

Status: Installed
The ClusterExtension is successfully installed with proper RBAC permissions.

Current RBAC configuration:
- ServiceAccount: postgres-operator-sa (namespace: postgres-operator)
- ClusterRole: postgres-operator-installer
- All required permissions are granted
```

### When Feature Gate Disabled

```
Analyzing RBAC permissions for extension: postgres-operator

⚠ PreflightPermissions feature gate is not enabled

Without the PreflightPermissions feature gate, the operator-controller does not
perform pre-authorization checks or report missing permissions in status conditions.

Current status: Failed (or Progressing)
Error: <actual error from conditions>

To enable detailed RBAC checking:
1. Enable PreflightPermissions feature gate in operator-controller
2. Restart the operator-controller pod
3. The next reconciliation will perform preflight checks

Alternative: Check operator-controller logs for RBAC errors:
kubectl logs -n olmv1-system -l app.kubernetes.io/name=operator-controller
```
