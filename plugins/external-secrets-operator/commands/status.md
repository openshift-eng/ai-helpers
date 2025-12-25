---
description: Check External Secrets Operator health and ExternalSecret sync status
argument-hint: "[--namespace <namespace>] [--external-secret <name>] [--watch]"
---

## Name
external-secrets-operator:status

## Synopsis
```
/external-secrets-operator:status [--namespace <namespace>] [--external-secret <name>] [--watch]
```

## Description
The `external-secrets-operator:status` command provides a quick overview of the External Secrets Operator health and the sync status of ExternalSecrets. It's designed for day-to-day operations to quickly check if secrets are syncing correctly.

This command shows:
- Operator deployment health and version
- SecretStore and ClusterSecretStore connectivity status
- ExternalSecret sync status with last sync times
- Any secrets that are failing to sync
- Quick summary metrics

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - `--namespace`: Filter to specific namespace
   - `--external-secret`: Show detailed status for specific ExternalSecret
   - `--watch`: Continuously monitor status (refresh every 10 seconds)

2. **Check Operator Status**:
   ```bash
   # Find operator namespace
   OPERATOR_NS=$(oc get subscription external-secrets-operator -A -o jsonpath='{.items[0].metadata.namespace}' 2>/dev/null)
   
   # Get CSV status
   oc get csv -n $OPERATOR_NS -l operators.coreos.com/external-secrets-operator.$OPERATOR_NS= \
     -o jsonpath='{.items[0].metadata.name} {.items[0].spec.version} {.items[0].status.phase}'
   
   # Check operator deployment
   oc get deployment -n $OPERATOR_NS -l app.kubernetes.io/name=external-secrets-operator \
     -o jsonpath='{.items[0].status.readyReplicas}/{.items[0].status.replicas}'
   ```

3. **Check ClusterSecretStores**:
   ```bash
   oc get clustersecretstores -o json | jq -r '.items[] | {
     name: .metadata.name,
     provider: (.spec.provider | keys[0]),
     ready: (.status.conditions[] | select(.type=="Ready") | .status),
     message: (.status.conditions[] | select(.type=="Ready") | .message)
   }'
   ```

4. **Check SecretStores** (namespace-scoped):
   ```bash
   # All namespaces or specific namespace
   oc get secretstores ${NAMESPACE:+-n $NAMESPACE} -A -o json | jq -r '.items[] | {
     namespace: .metadata.namespace,
     name: .metadata.name,
     provider: (.spec.provider | keys[0]),
     ready: (.status.conditions[] | select(.type=="Ready") | .status)
   }'
   ```

5. **Check ExternalSecrets**:
   ```bash
   oc get externalsecrets ${NAMESPACE:+-n $NAMESPACE} -A -o json | jq -r '.items[] | {
     namespace: .metadata.namespace,
     name: .metadata.name,
     store: .spec.secretStoreRef.name,
     storeKind: .spec.secretStoreRef.kind,
     target: .spec.target.name,
     status: (.status.conditions[] | select(.type=="Ready") | .status),
     lastSync: .status.refreshTime,
     message: (.status.conditions[] | select(.type=="Ready") | .message)
   }'
   ```

6. **Calculate Summary Metrics**:
   ```bash
   # Count totals
   TOTAL_ES=$(oc get externalsecrets -A --no-headers | wc -l)
   SYNCED_ES=$(oc get externalsecrets -A -o json | jq '[.items[] | select(.status.conditions[] | select(.type=="Ready" and .status=="True"))] | length')
   FAILED_ES=$((TOTAL_ES - SYNCED_ES))
   
   # Count stores
   TOTAL_CSS=$(oc get clustersecretstores --no-headers | wc -l)
   READY_CSS=$(oc get clustersecretstores -o json | jq '[.items[] | select(.status.conditions[] | select(.type=="Ready" and .status=="True"))] | length')
   ```

7. **Display Status Report**:
   ```
   ═══════════════════════════════════════════════════════════
   EXTERNAL SECRETS OPERATOR STATUS
   ═══════════════════════════════════════════════════════════
   
   Operator:
   ✓ external-secrets-operator.v0.10.0 (Succeeded)
   ✓ Deployment: 1/1 ready
   
   ───────────────────────────────────────────────────────────
   CLUSTER SECRET STORES
   ───────────────────────────────────────────────────────────
   
   ✓ aws-secretsmanager      AWS SecretsManager     Ready
   ✓ vault-backend           Vault                  Ready
   ❌ azure-keyvault          Azure KeyVault         NotReady
      └─ Error: authentication failed: invalid client secret
   
   Total: 3 (2 ready, 1 not ready)
   
   ───────────────────────────────────────────────────────────
   SECRET STORES (namespace-scoped)
   ───────────────────────────────────────────────────────────
   
   ✓ my-app/local-vault      Vault                  Ready
   
   Total: 1 (1 ready)
   
   ───────────────────────────────────────────────────────────
   EXTERNAL SECRETS SUMMARY
   ───────────────────────────────────────────────────────────
   
   Total: 15 across 5 namespaces
   ✓ Synced: 13
   ❌ Failed: 2
   
   Recently Synced (last 5 minutes):
   ✓ production/db-credentials      → db-secret           2m ago
   ✓ production/api-keys            → api-secret          3m ago
   ✓ staging/db-credentials         → db-secret           4m ago
   
   Failed ExternalSecrets:
   ❌ production/oauth-config        → oauth-secret
      Store: azure-keyvault (ClusterSecretStore)
      Error: SecretStore not ready
      Last Attempt: 5m ago
   
   ❌ development/test-secret        → test-k8s-secret
      Store: aws-secretsmanager (ClusterSecretStore)
      Error: AccessDeniedException: not authorized
      Last Attempt: 1m ago
   
   ───────────────────────────────────────────────────────────
   
   Quick Commands:
   • Diagnose issues: /external-secrets-operator:diagnose
   • List all resources: /external-secrets-operator:list
   • Force sync: /external-secrets-operator:sync <name> -n <namespace>
   ```

8. **Detailed Status for Specific ExternalSecret** (if `--external-secret` provided):
   ```
   ═══════════════════════════════════════════════════════════
   EXTERNAL SECRET: production/db-credentials
   ═══════════════════════════════════════════════════════════
   
   Configuration:
   ─────────────────────────────────────────────────────────
   Store Reference: vault-backend (ClusterSecretStore)
   Refresh Interval: 1h
   Target Secret: db-secret
   Creation Policy: Owner
   
   Data Mappings:
   ─────────────────────────────────────────────────────────
   secretKey          remoteRef.key                    remoteRef.property
   ──────────────────────────────────────────────────────────
   username           secret/data/prod/database        username
   password           secret/data/prod/database        password
   host               secret/data/prod/database        host
   
   Status:
   ─────────────────────────────────────────────────────────
   Condition: Ready
   Status: True
   Reason: SecretSynced
   Message: Secret was synced
   
   Sync History:
   ─────────────────────────────────────────────────────────
   Last Sync: 2024-01-15T14:30:00Z (10 minutes ago)
   Synced Resource Version: 12345
   
   Target Secret:
   ─────────────────────────────────────────────────────────
   Name: db-secret
   Namespace: production
   Keys: username, password, host
   Created: 2024-01-10T08:00:00Z
   Last Modified: 2024-01-15T14:30:00Z
   
   ✓ ExternalSecret is healthy and syncing correctly
   ```

9. **Watch Mode** (if `--watch` provided):
   - Clear screen and refresh every 10 seconds
   - Show timestamp of last refresh
   - Highlight changes since last refresh

## Return Value
- **Success**: Status report with health indicators
- **Format**: Structured output with:
  - Operator health
  - Store connectivity status
  - ExternalSecret sync summary
  - Failed secrets with error details

## Examples

1. **Quick status check**:
   ```
   /external-secrets-operator:status
   ```

2. **Status for specific namespace**:
   ```
   /external-secrets-operator:status --namespace production
   ```

3. **Detailed status for specific ExternalSecret**:
   ```
   /external-secrets-operator:status --external-secret db-credentials --namespace production
   ```

4. **Watch mode (continuous monitoring)**:
   ```
   /external-secrets-operator:status --watch
   ```

5. **Watch specific namespace**:
   ```
   /external-secrets-operator:status --namespace production --watch
   ```

## Arguments
- **--namespace** (optional): Filter to specific namespace
  - Example: `--namespace production`
- **--external-secret** (optional): Show detailed status for specific ExternalSecret
  - Requires `--namespace` to be specified
  - Example: `--external-secret db-credentials`
- **--watch** (optional): Continuously monitor status
  - Refreshes every 10 seconds
  - Press Ctrl+C to stop

## Notes

- **Quick Overview**: This command is designed for quick health checks, not deep diagnostics
- **For Troubleshooting**: Use `/external-secrets-operator:diagnose` for detailed issue analysis
- **Sync Times**: "Last Sync" shows when the secret was last successfully refreshed from the external provider
- **Stale Detection**: Secrets not synced within 2x their refresh interval are flagged as potentially stale

## Related Commands

- `/external-secrets-operator:diagnose` - Detailed troubleshooting and diagnostics
- `/external-secrets-operator:list` - List all resources with filtering
- `/external-secrets-operator:sync` - Force refresh of ExternalSecrets
- `/external-secrets-operator:guide` - Provider configuration guides

## Additional Resources

- [External Secrets Operator for Red Hat OpenShift](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift)
- [External Secrets API Reference](https://external-secrets.io/latest/api/externalsecret/)

