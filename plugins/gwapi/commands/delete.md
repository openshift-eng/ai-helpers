---
description: Delete Gateway API resources from a Kubernetes/OpenShift cluster
argument-hint: "[namespace]"
---

## Name
gwapi:delete

## Synopsis
```bash
/gwapi:delete [namespace]
```

## Description
The `gwapi:delete` command removes Gateway API resources from a Kubernetes or OpenShift cluster. It deletes:
1. Gateway resources (namespace-scoped)
2. GatewayClass resources (cluster-scoped)

The command uses `oc` (preferred) or `kubectl` to delete the resources safely. It provides confirmation before deletion and verifies successful removal.

## Arguments
- `$1` (optional): Target namespace for deleting Gateway resources. If not specified, deletes Gateway resources from the `openshift-ingress` namespace (as defined in the YAML files) and the cluster-scoped GatewayClass.

## Implementation

1. **Tool Detection**
   - Check if `oc` is available: `which oc`
   - If not available, check for `kubectl`: `which kubectl`
   - If neither is available, inform the user to install one of these tools:
     - OpenShift CLI: <https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html>
     - Kubernetes CLI: <https://kubernetes.io/docs/tasks/tools/>

2. **Cluster Connection Verification**
   - Verify cluster connectivity: `oc whoami` or `kubectl cluster-info`
   - If connection fails, inform the user to authenticate to their cluster:
     - For OpenShift: `oc login <cluster-url>`
     - For Kubernetes: Configure kubeconfig properly

3. **Resource Discovery**
   - Check for existing Gateway resources:
     - If namespace argument provided: `oc get gateway -n <namespace>`
     - If no namespace argument: `oc get gateway --all-namespaces`
   - Check for existing GatewayClass resources: `oc get gatewayclass`
   - If no resources found:
     - Display: "No Gateway API resources found to delete"
     - Exit successfully

4. **Display Resources to be Deleted**
   - Show a clear list of resources that will be deleted:
     ```text
     The following resources will be deleted:

     GatewayClass:
     - openshift-default

     Gateway (openshift-ingress):
     - gateway
     ```

5. **User Confirmation**
   - Ask for confirmation before proceeding with deletion
   - Use AskUserQuestion tool to confirm:
     - Question: "Are you sure you want to delete these Gateway API resources?"
     - Options:
       - "Yes, delete all resources"
       - "No, cancel deletion"
   - If user selects "No" or cancels, exit without making changes

6. **Delete Gateway Resources**
   - If namespace argument provided:
     - Delete Gateway resources from specified namespace
     - For each Gateway found: `oc delete gateway <name> -n <namespace>`
   - If no namespace argument:
     - Delete the specific Gateway from the YAML: `oc delete -f plugins/gwapi/resources/gateway.yaml --ignore-not-found`
     - Alternative: Delete by name if known: `oc delete gateway gateway -n openshift-ingress --ignore-not-found`
   - Display deletion status for each Gateway
   - Use `--ignore-not-found` flag to handle already-deleted resources gracefully

7. **Delete GatewayClass Resources**
   - Delete the GatewayClass resource: `oc delete -f plugins/gwapi/resources/gatewayclass.yaml --ignore-not-found`
   - Alternative: Delete by name: `oc delete gatewayclass openshift-default --ignore-not-found`
   - Display deletion status
   - Note: GatewayClass is cluster-scoped, so namespace argument doesn't apply

8. **Deletion Verification**
   - Verify Gateway resources are deleted:
     - If namespace was specified: `oc get gateway -n <namespace>`
     - Otherwise: `oc get gateway --all-namespaces`
   - Verify GatewayClass is deleted: `oc get gatewayclass`
   - If resources still exist, display warning with resource names
   - If all resources are deleted, display success confirmation

9. **Error Handling**
   - If deletion fails due to permissions:
     - Display: "Insufficient permissions. Deleting GatewayClass requires cluster-admin privileges, Gateway requires namespace delete permissions"
   - If resources are in use (have attached routes):
     - Display warning about attached routes
     - Show number of attached routes per Gateway
     - Confirm user still wants to proceed
   - If deletion partially fails:
     - Display which resources were successfully deleted
     - Display which resources failed with error messages
     - Provide troubleshooting steps for failed deletions

10. **Cleanup Summary**
    - Display a summary of deletion results:
      - Number of Gateways deleted
      - Number of GatewayClasses deleted
      - Any errors or warnings encountered

## Return Value
- **Success**: Confirmation message listing all deleted resources
- **No Resources**: Information that no Gateway API resources were found
- **Partial Success**: List of successfully deleted and failed resources
- **Cancelled**: Message that deletion was cancelled by user
- **Failure**: Error message with troubleshooting steps

## Examples

1. **Delete all Gateway API resources**:
   ```bash
   /gwapi:delete
   ```
   Prompts for confirmation, then deletes Gateway from `openshift-ingress` namespace and the GatewayClass.

2. **Delete Gateway from specific namespace**:
   ```bash
   /gwapi:delete gateway-system
   ```
   Deletes Gateway resources only from the `gateway-system` namespace and the cluster-scoped GatewayClass (after confirmation).

## Notes
- **Destructive Operation**: This command permanently deletes resources. Always confirm before proceeding.
- **Attached Routes**: If HTTPRoute or other route resources reference the Gateway, they may become non-functional after deletion
- **Cluster-Scoped**: GatewayClass deletion requires cluster-admin or equivalent permissions
- **Idempotent**: Safe to run multiple times - uses `--ignore-not-found` flag
- **No Cascade**: Deleting GatewayClass does not automatically delete associated Gateways
- **Service Impact**: Deleting Gateway resources will stop routing traffic through the Gateway
- **Confirmation Required**: User must explicitly confirm deletion to prevent accidental resource removal
- **Resource Files**: The original YAML files in `plugins/gwapi/resources/` are not modified or deleted

## Safety Features
- Requires explicit user confirmation before deletion
- Displays all resources to be deleted before proceeding
- Uses `--ignore-not-found` to handle already-deleted resources
- Provides clear error messages for troubleshooting
- Verifies deletion was successful
- Warns about attached routes that may be impacted
