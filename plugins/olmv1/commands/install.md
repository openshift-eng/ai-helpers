# Install Extension Command

You are helping the user install a Kubernetes extension using OLM v1.

## Task

Install an extension with the specified version/channel constraints, including proper service account and RBAC setup.

## Important: Service Account and RBAC Requirements

**CRITICAL**: OLM v1 requires that YOU (the cluster admin) provide a ServiceAccount with sufficient RBAC permissions. Unlike OLM v0, OLM v1 does NOT have cluster-admin privileges. The ServiceAccount you provide must have all necessary permissions for the extension to install and operate.

If the `PreflightPermissions` feature gate is enabled in the cluster, OLM will perform a preflight check and report missing permissions in the ClusterExtension status conditions before attempting installation. This helps you identify and fix RBAC issues up front.

## Steps

1. **Check operator-controller feature gates**:

   Before starting installation, check if necessary feature gates are enabled:

   ```bash
   kubectl get deployment operator-controller-controller-manager -n olmv1-system \
     -o jsonpath='{.spec.template.spec.containers[0].args}' | jq -r '.[]' | grep feature-gates
   ```

   Important feature gates:
   - **WebhookProviderCertManager** or **WebhookProviderOpenshiftServiceCA**: Required for operators with webhooks (mutating/validating webhook configurations)
   - **PreflightPermissions**: Enables RBAC validation before installation, providing clear error messages about missing permissions

   If webhooks are needed but feature gate is not enabled:
   - Check if cert-manager is installed: `kubectl get pods -n cert-manager`
   - Enable the feature gate (this command is in the allow-list):
     ```bash
     kubectl patch deployment operator-controller-controller-manager -n olmv1-system --type=json \
       -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--feature-gates=WebhookProviderCertManager=true"}]'
     ```
   - Wait for rollout: `kubectl rollout status deployment operator-controller-controller-manager -n olmv1-system`

2. **Gather installation parameters**:
   - Extension name (required)
   - Version constraint (optional: specific version, range, or channel)
   - Catalog source (optional: auto-detect if not specified)
   - Target namespace (required for service account and resources)
   - Service account name (default: `<extension-name>-sa`)

3. **Validate extension exists**:
   ```bash
   kubectl get packages -A | grep <extension-name>
   ```

4. **Determine installation strategy**:
   - Channel-based: If --channel specified
   - Version-specific: If --version with exact version
   - Version range: If --version with range (e.g., ">=1.0.0 <2.0.0")

5. **Create namespace if it doesn't exist**:
   ```bash
   kubectl create namespace <namespace> --dry-run=client -o yaml | kubectl apply -f -
   ```

6. **Create ServiceAccount**:
   ```bash
   kubectl create serviceaccount <extension-name>-sa -n <namespace> --dry-run=client -o yaml | kubectl apply -f -
   ```

7. **Create initial RBAC permissions**:

   Start with a baseline ClusterRole that grants common permissions needed by most extensions:

   ```yaml
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRole
   metadata:
     name: <extension-name>-installer
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
   # RBAC (needed to create operator's own roles)
   - apiGroups: ["rbac.authorization.k8s.io"]
     resources: ["roles", "rolebindings", "clusterroles", "clusterrolebindings"]
     verbs: ["get", "list", "watch", "create", "update", "patch", "delete", "bind", "escalate"]
   # CRDs
   - apiGroups: ["apiextensions.k8s.io"]
     resources: ["customresourcedefinitions"]
     verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
   # Admission webhooks (if needed)
   - apiGroups: ["admissionregistration.k8s.io"]
     resources: ["validatingwebhookconfigurations", "mutatingwebhookconfigurations"]
     verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
   ```

   Bind the ClusterRole to the ServiceAccount:

   ```yaml
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRoleBinding
   metadata:
     name: <extension-name>-installer
   roleRef:
     apiGroup: rbac.authorization.k8s.io
     kind: ClusterRole
     name: <extension-name>-installer
   subjects:
   - kind: ServiceAccount
     name: <extension-name>-sa
     namespace: <namespace>
   ```

8. **Create ClusterExtension resource**:
   ```yaml
   apiVersion: olm.operatorframework.io/v1alpha1
   kind: ClusterExtension
   metadata:
     name: <extension-name>
   spec:
     namespace: <namespace>
     serviceAccount:
       name: <extension-name>-sa
     source:
       sourceType: Catalog
       catalog:
         packageName: <package-name>
         version: "<version-constraint>"  # or omit for channel
         channel: "<channel>"               # or omit for version
   ```

9. **Apply the resources**:
   ```bash
   kubectl apply -f <namespace-file>
   kubectl apply -f <serviceaccount-file>
   kubectl apply -f <clusterrole-file>
   kubectl apply -f <clusterrolebinding-file>
   kubectl apply -f <clusterextension-file>
   ```

10. **Monitor installation**:
   ```bash
   kubectl wait --for=condition=Installed clusterextension/<extension-name> --timeout=5m
   kubectl get clusterextension <extension-name> -o yaml
   ```

11. **Check for webhook-related errors**:

    If you see errors like "unsupported bundle: webhookDefinitions are not supported":
    - This means the operator bundle includes webhooks but the feature gate is not enabled
    - Check if cert-manager is available: `kubectl get pods -n cert-manager`
    - Enable the WebhookProviderCertManager feature gate (see step 1)
    - Trigger reconciliation: `kubectl annotate clusterextension <extension-name> reconcile="$(date +%s)" --overwrite`

    If webhooks are enabled but you see cert-manager permission errors:
    - Add cert-manager permissions to the ClusterRole:
      ```yaml
      - apiGroups: ["cert-manager.io"]
        resources: ["certificates", "issuers", "certificaterequests"]
        verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
      ```

12. **Check for RBAC/preflight errors**:
    If installation fails or hangs, check the ClusterExtension status conditions:

    ```bash
    kubectl get clusterextension <extension-name> -o jsonpath='{.status.conditions}' | jq '.[] | select(.type=="Progressing" or .type=="Installing")'
    ```

    Look for messages starting with "pre-authorization failed:" which will list missing RBAC permissions in this format:
    ```
    Namespace:"" APIGroups:[] Resources:[services] Verbs:[list,watch]
    Namespace:"<namespace>" APIGroups:[apps] Resources:[deployments] Verbs:[create]
    ```

    - `Namespace:""` means cluster-scoped permissions needed
    - `APIGroups:[]` means core API group (no group)
    - Add the missing permissions to the ClusterRole and reapply

13. **Iteratively fix RBAC if needed**:
    If preflight checks fail:
    - Parse the error message to extract missing permissions
    - Update the ClusterRole with additional rules
    - Reapply the ClusterRole
    - The controller will automatically retry installation

14. **Verify installation**:
    - Check ClusterExtension status shows "Installed"
    - Verify CRDs were created
    - Check associated deployments/pods
    - Validate extension is functioning

15. **Report results**:
    - Installation success with version installed
    - List created resources (CRDs, namespaces, service accounts, RBAC)
    - Provide next steps or usage examples
    - If RBAC issues encountered, show the final working RBAC configuration

## Error Handling

- Extension not found: Suggest running `/olmv1:search <keyword>` first
- Version/channel doesn't exist: Show available versions/channels using search
- Namespace doesn't exist: Create it automatically
- ServiceAccount doesn't exist: Create it automatically
- **Webhook-related errors**:
  - "unsupported bundle: webhookDefinitions are not supported": Enable WebhookProviderCertManager feature gate
  - Check if cert-manager is installed before enabling webhook support
  - Automatically enable the feature gate if cert-manager is available (kubectl patch command is in allow-list)
  - After enabling, trigger reconciliation with annotation
  - Add cert-manager.io permissions to ClusterRole if needed
- **RBAC/Pre-authorization errors**:
  - Parse the "pre-authorization failed" message from status conditions
  - Extract the missing permissions (Namespace, APIGroups, Resources, Verbs)
  - Suggest specific RBAC rules to add to the ClusterRole
  - Remind user to reapply after fixing RBAC
  - Suggest using `/olmv1:fix-rbac <extension-name>` to automatically generate missing permissions
- Installation failed (other): Parse status conditions and provide specific error
- Resource conflicts: Identify conflicting resources

## Example Output

### Successful Installation

```
Installing postgres-operator...

✓ Created namespace: postgres-operator
✓ Created ServiceAccount: postgres-operator-sa
✓ Created ClusterRole: postgres-operator-installer
✓ Created ClusterRoleBinding: postgres-operator-installer
✓ Validated extension exists in catalog: operatorhubio
✓ Created ClusterExtension resource
✓ Waiting for installation to complete...
✓ Extension installed successfully

Installed: postgres-operator
Version: 1.2.0
Channel: stable
Namespace: postgres-operator

Created Resources:
- Namespace: postgres-operator
- ServiceAccount: postgres-operator-sa (with ClusterRole permissions)
- CRDs: postgresqls.acid.zalan.do, operatorconfigurations.acid.zalan.do
- Deployment: postgres-operator (1/1 ready)

Next steps:
- Check status: /olmv1:status postgres-operator
- View all extensions: /olmv1:list
```

### Installation with RBAC Fixes

```
Installing postgres-operator...

✓ Created namespace: postgres-operator
✓ Created ServiceAccount: postgres-operator-sa
✓ Created ClusterRole: postgres-operator-installer (baseline permissions)
✓ Created ClusterRoleBinding: postgres-operator-installer
✓ Validated extension exists in catalog: operatorhubio
✓ Created ClusterExtension resource
⚠ Preflight check failed - missing RBAC permissions

Missing permissions detected:
  Namespace:"" APIGroups:[] Resources:[persistentvolumeclaims] Verbs:[create,delete]
  Namespace:"" APIGroups:[apps] Resources:[statefulsets] Verbs:[create,update]

Updating ClusterRole with missing permissions...
✓ Updated ClusterRole: postgres-operator-installer
✓ Waiting for installation to retry...
✓ Extension installed successfully

Installed: postgres-operator
Version: 1.2.0
Channel: stable
Namespace: postgres-operator

Final RBAC Configuration:
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: postgres-operator-installer
rules:
# (baseline permissions)
# ...
# Additional permissions required:
- apiGroups: [""]
  resources: ["persistentvolumeclaims"]
  verbs: ["create", "delete"]
- apiGroups: ["apps"]
  resources: ["statefulsets"]
  verbs: ["create", "update"]

Next steps:
- Check status: /olmv1:status postgres-operator
- View all extensions: /olmv1:list
- Save RBAC config for future reference
```
