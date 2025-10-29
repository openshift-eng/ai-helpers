# Extension Status Command

You are helping the user get detailed status information for an installed extension.

## Task

Provide comprehensive health and status information for a specific extension.

## Steps

1. **Check operator-controller feature gates**:

   Check current feature gates to understand enabled capabilities:

   ```bash
   kubectl get deployment operator-controller-controller-manager -n olmv1-system \
     -o jsonpath='{.spec.template.spec.containers[0].args}' | jq -r '.[]' | grep feature-gates
   ```

   Report on feature gate status:
   - **WebhookProviderCertManager**: Webhook support via cert-manager
   - **WebhookProviderOpenshiftServiceCA**: Webhook support via OpenShift service CA
   - **PreflightPermissions**: RBAC preflight validation (provides detailed permission errors)

2. **Verify extension exists**:
   ```bash
   kubectl get clusterextension <extension-name>
   ```

3. **Get detailed status**:
   ```bash
   kubectl get clusterextension <extension-name> -o yaml
   ```

4. **Parse status information**:
   - Installation phase (Installed, Progressing, Failed)
   - Resolved version and channel
   - Status conditions and messages
   - Installation timestamp
   - **Check for webhook errors**: Look for "webhookDefinitions are not supported" in condition messages
   - **Check for RBAC/preflight permission errors**: Look for "pre-authorization failed" in condition messages

5. **Check associated resources**:
   ```bash
   # Get CRDs created by this extension
   kubectl get crds -l olm.operatorframework.io/owner-name=<extension-name>

   # Get extension namespace and resources
   kubectl get all -n <extension-namespace>

   # Get deployment status
   kubectl get deployments -n <extension-namespace>
   ```

6. **Check for recent events**:
   ```bash
   kubectl get events -n <extension-namespace> --sort-by='.lastTimestamp'
   ```

7. **Analyze health**:
   - All pods running and ready
   - No crash loops or errors
   - CRDs properly installed
   - Service endpoints available
   - Webhooks configured if needed

8. **Identify webhook issues if present**:

   Check for webhook-related errors:
   ```bash
   kubectl get clusterextension <extension-name> -o jsonpath='{.status.conditions}' | \
     jq -r '.[] | select(.message | contains("webhookDefinitions")) | .message'
   ```

   If found:
   - Check current feature gates (see step 1)
   - Verify cert-manager is installed
   - Suggest enabling WebhookProviderCertManager feature gate
   - May automatically enable if cert-manager is available

9. **Identify RBAC/permission issues if present**:

   Check specifically for pre-authorization failures:
   ```bash
   kubectl get clusterextension <extension-name> -o jsonpath='{.status.conditions}' | \
     jq -r '.[] | select(.message | contains("pre-authorization failed")) | .message'
   ```

   If found:
   - Extract and display the missing permissions in a readable format
   - Identify the ServiceAccount and current RBAC configuration
   - Suggest using `/olmv1:fix-rbac <extension-name>` to automatically fix the issues

10. **Report comprehensive status**:
   - Overall health summary
   - Feature gate status (webhook support, preflight permissions)
   - Version and channel information
   - ServiceAccount and RBAC status
   - Resource details
   - Any warnings or errors (especially webhook and RBAC-related)
   - Suggested actions if unhealthy

## Error Handling

- Extension not found: List available extensions
- Namespace not accessible: Check RBAC permissions
- Incomplete installation: Suggest troubleshooting steps
- **Webhook errors detected**:
  - Check if WebhookProviderCertManager or WebhookProviderOpenshiftServiceCA is enabled
  - Verify cert-manager installation status
  - Suggest enabling feature gate via kubectl patch
  - May automatically enable if cert-manager is present (command is in allow-list)
- **RBAC/Pre-authorization errors detected**:
  - Display the missing permissions clearly
  - Show current ServiceAccount configuration
  - Suggest running `/olmv1:fix-rbac <extension-name>` to resolve
  - Explain that PreflightPermissions feature gate must be enabled for detailed checks
  - Note: Without PreflightPermissions, RBAC errors may only appear as generic installation failures

## Example Output

```
Status: cert-manager-operator

Overall Health: ✓ Healthy
Installation Status: Installed
Installed Version: 1.14.5
Channel: stable
Catalog Source: operatorhubio
Namespace: cert-manager
Installed At: 2025-10-28T09:30:00Z

Conditions:
✓ Installed: True (Last transition: 2025-10-28T09:32:15Z)
✓ Resolved: True (Resolved to version 1.14.5)

Custom Resource Definitions (3):
✓ certificates.cert-manager.io
✓ issuers.cert-manager.io
✓ clusterissuers.cert-manager.io

Workload Status:
Deployment: cert-manager-controller
  ✓ 1/1 pods ready
  ✓ Last updated: 2025-10-28T09:31:30Z

Deployment: cert-manager-webhook
  ✓ 1/1 pods ready

Deployment: cert-manager-cainjector
  ✓ 1/1 pods ready

Recent Events:
- Successfully reconciled ClusterExtension (2 minutes ago)
- All deployments scaled to desired replicas (3 minutes ago)

No issues detected. Extension is operating normally.
```

### With RBAC/Permission Issues

```
Status: postgres-operator

Overall Health: ⚠ Installation Blocked
Installation Status: Progressing (Retrying)
Channel: stable
Catalog Source: operatorhubio
Namespace: postgres-operator
ServiceAccount: postgres-operator-sa

Conditions:
⚠ Progressing: True (Reason: Retrying)
  Message: pre-authorization failed: service account requires the following permissions to manage cluster extension:
   Namespace:"" APIGroups:[] Resources:[persistentvolumeclaims] Verbs:[create,delete]
   Namespace:"" APIGroups:[apps] Resources:[statefulsets] Verbs:[create,update]

✗ Installed: False

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠ RBAC Permission Issues Detected

Missing permissions for ServiceAccount "postgres-operator-sa":

Cluster-scoped:
1. Core API: persistentvolumeclaims [create, delete]
2. apps API: statefulsets [create, update]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Current RBAC Configuration:
- ServiceAccount: postgres-operator-sa (namespace: postgres-operator)
- ClusterRole: postgres-operator-installer (missing required permissions)

Recommended Action:
Run the following command to automatically fix RBAC permissions:
  /olmv1:fix-rbac postgres-operator

Or manually update the ClusterRole to include the missing permissions.
Once fixed, the operator-controller will automatically retry installation.
```

### With Webhook Issues

```
Status: cloudnative-pg

Overall Health: ⚠ Installation Blocked - Webhook Support Required
Installation Status: Progressing (Retrying)
Channel: stable
Catalog Source: operatorhubio
Namespace: cloudnative-pg
ServiceAccount: cloudnative-pg-sa

OLM v1 Feature Gates:
⚠ WebhookProviderCertManager: Not Enabled
✓ cert-manager: Installed and ready

Conditions:
⚠ Progressing: True (Reason: Retrying)
  Message: error for resolved bundle "cloudnative-pg.v1.27.1" with version "1.27.1":
   unsupported bundle: webhookDefinitions are not supported

✗ Installed: False

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠ Webhook Support Required

This operator requires webhook support, but the WebhookProviderCertManager
feature gate is not enabled on operator-controller.

cert-manager is installed and available, so webhook support can be enabled.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Recommended Action:
Enable the WebhookProviderCertManager feature gate with:

  kubectl patch deployment operator-controller-controller-manager -n olmv1-system --type=json \
    -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-",
    "value": "--feature-gates=WebhookProviderCertManager=true"}]'

Then wait for rollout:
  kubectl rollout status deployment operator-controller-controller-manager -n olmv1-system

After enabling, trigger reconciliation:
  kubectl annotate clusterextension cloudnative-pg reconcile="$(date +%s)" --overwrite
```

