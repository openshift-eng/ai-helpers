# Uninstall Extension Command

You are helping the user safely remove an installed extension from their cluster.

## Task

Uninstall an extension and clean up associated resources.

## Steps

1. **Verify extension exists**:
   ```bash
   kubectl get clusterextension <extension-name>
   ```

2. **Check for dependent resources**:
   - List custom resources created by this extension
   - Warn about data loss if CRs exist
   - Get user confirmation before proceeding

3. **Show what will be removed**:
   ```bash
   # Show CRDs
   kubectl get crds -l olm.operatorframework.io/owner-name=<extension-name>

   # Show namespace resources
   kubectl get all -n <extension-namespace>
   ```

4. **Request confirmation**:
   Ask user to confirm uninstallation with awareness of:
   - CRDs that will be removed
   - Custom resources that will be deleted
   - Namespaces that may be cleaned up

5. **Delete custom resources** (if requested):
   ```bash
   # Delete all CRs for each CRD
   kubectl delete <crd-resource-type> --all --all-namespaces
   ```

6. **Delete ClusterExtension**:
   ```bash
   kubectl delete clusterextension <extension-name>
   ```

7. **Verify removal**:
   ```bash
   kubectl get clusterextension <extension-name>  # Should not exist
   kubectl get crds -l olm.operatorframework.io/owner-name=<extension-name>  # Should be empty
   ```

8. **Clean up namespace** (if empty and created by extension):
   ```bash
   kubectl delete namespace <extension-namespace>
   ```

9. **Report results**:
   - Confirmation of deletion
   - List of removed resources
   - Any manual cleanup steps required

## Safety Checks

- WARNING: Uninstalling will remove CRDs and all custom resources
- Dependency Check: Look for resources in other namespaces using this extension
- Confirmation Required: Always require explicit user confirmation
- Backup Suggestion: Suggest backing up custom resources before deletion

## Error Handling

- Extension not found: List available extensions
- Deletion blocked: Check for finalizers or dependent resources
- RBAC errors: Suggest required permissions
- Partial deletion: Report what was deleted and what remains

## Example Output

```
Preparing to uninstall: cert-manager-operator

The following resources will be removed:

Custom Resource Definitions (3):
- certificates.cert-manager.io (15 instances found)
- issuers.cert-manager.io (8 instances found)
- clusterissuers.cert-manager.io (2 instances found)

Namespace: cert-manager
Deployments: 3
Pods: 3
Services: 2

WARNING: This will delete all Certificate, Issuer, and ClusterIssuer resources!

Do you want to proceed with uninstallation? (y/N): y

Uninstalling...
✓ Deleted 15 Certificates
✓ Deleted 8 Issuers
✓ Deleted 2 ClusterIssuers
✓ Deleted ClusterExtension: cert-manager-operator
✓ Removed CRDs
✓ Deleted namespace: cert-manager

Uninstallation complete.

cert-manager-operator has been successfully removed from the cluster.
```
