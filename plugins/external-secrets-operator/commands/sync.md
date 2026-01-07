---
description: Force refresh ExternalSecrets to sync from external providers
argument-hint: "<name> --namespace <namespace> | --all [--namespace <namespace>] | --store <store-name>"
---

## Name
external-secrets-operator:sync

## Synopsis
```
/external-secrets-operator:sync <name> --namespace <namespace>
/external-secrets-operator:sync --all [--namespace <namespace>]
/external-secrets-operator:sync --store <store-name> [--namespace <namespace>]
/external-secrets-operator:sync --failed [--namespace <namespace>]
```

## Description
The `external-secrets-operator:sync` command forces an immediate refresh of ExternalSecrets, triggering them to sync from their external providers. This is useful when:

- You've updated a secret in the external provider and want it reflected immediately
- An ExternalSecret is stuck and you want to retry the sync
- You want to verify connectivity to the external provider
- You need to refresh secrets after fixing a SecretStore configuration

The command works by annotating the ExternalSecret with a force-sync annotation, which triggers the controller to immediately reconcile and fetch the latest secret values.

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - `$1`: ExternalSecret name (required unless using `--all`, `--store`, or `--failed`)
   - `--namespace`: Namespace of the ExternalSecret (required for single secret)
   - `--all`: Sync all ExternalSecrets
   - `--store`: Sync all ExternalSecrets using a specific store
   - `--failed`: Sync only failed ExternalSecrets
   - `--dry-run`: Show what would be synced without actually syncing

2. **Validate Arguments**:
   ```bash
   # Check that required arguments are provided
   if [[ -z "$NAME" && -z "$ALL" && -z "$STORE" && -z "$FAILED" ]]; then
     echo "Error: Must specify ExternalSecret name, --all, --store, or --failed"
     exit 1
   fi
   
   # If specific name provided, namespace is required
   if [[ -n "$NAME" && -z "$NAMESPACE" ]]; then
     echo "Error: --namespace is required when specifying ExternalSecret name"
     exit 1
   fi
   ```

3. **Get ExternalSecrets to Sync**:

   **Single ExternalSecret**:
   ```bash
   oc get externalsecret $NAME -n $NAMESPACE -o json
   ```

   **All ExternalSecrets**:
   ```bash
   oc get externalsecrets ${NAMESPACE:+-n $NAMESPACE} -A -o json
   ```

   **By Store**:
   ```bash
   oc get externalsecrets ${NAMESPACE:+-n $NAMESPACE} -A -o json | \
     jq --arg store "$STORE" '.items[] | select(.spec.secretStoreRef.name == $store)'
   ```

   **Failed Only**:
   ```bash
   oc get externalsecrets ${NAMESPACE:+-n $NAMESPACE} -A -o json | \
     jq '.items[] | select(.status.conditions[] | select(.type=="Ready" and .status=="False"))'
   ```

4. **Display Sync Plan**:
   ```
   ═══════════════════════════════════════════════════════════
   EXTERNAL SECRETS SYNC PLAN
   ═══════════════════════════════════════════════════════════
   
   The following ExternalSecrets will be synced:
   
   NAMESPACE          NAME                    STORE                   CURRENT STATUS
   ─────────────────────────────────────────────────────────────────────────────────
   production         db-credentials          vault-backend           Synced (1h ago)
   production         api-keys                aws-secretsmanager      Synced (30m ago)
   staging            db-credentials          vault-backend           Synced (2h ago)
   
   Total: 3 ExternalSecrets
   
   Proceed with sync? (yes/no)
   ```

5. **Force Sync Using Annotation**:
   
   The External Secrets Operator watches for a specific annotation to trigger immediate reconciliation:
   
   ```bash
   # Add/update force-sync annotation with current timestamp
   TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
   
   oc annotate externalsecret $NAME -n $NAMESPACE \
     force-sync=$TIMESTAMP \
     --overwrite
   ```

   Alternative method - delete and let controller recreate the target secret:
   ```bash
   # Get target secret name
   TARGET=$(oc get externalsecret $NAME -n $NAMESPACE -o jsonpath='{.spec.target.name}')
   
   # Delete the target secret (controller will recreate it)
   # Note: This causes brief unavailability of the secret
   oc delete secret $TARGET -n $NAMESPACE
   ```

6. **Wait for Sync Completion**:
   ```bash
   # Wait for the ExternalSecret to be reconciled
   # Check the refreshTime field for update
   
   INITIAL_REFRESH=$(oc get externalsecret $NAME -n $NAMESPACE -o jsonpath='{.status.refreshTime}')
   
   echo "Waiting for sync to complete..."
   
   for i in {1..30}; do
     sleep 2
     CURRENT_REFRESH=$(oc get externalsecret $NAME -n $NAMESPACE -o jsonpath='{.status.refreshTime}')
     
     if [[ "$CURRENT_REFRESH" != "$INITIAL_REFRESH" ]]; then
       echo "✓ Sync completed"
       break
     fi
     
     if [[ $i -eq 30 ]]; then
       echo "⚠ Sync timeout - check status manually"
     fi
   done
   ```

7. **Verify Sync Status**:
   ```bash
   # Check the status after sync
   oc get externalsecret $NAME -n $NAMESPACE -o json | jq '{
     name: .metadata.name,
     namespace: .metadata.namespace,
     status: (.status.conditions[] | select(.type=="Ready")),
     refreshTime: .status.refreshTime,
     syncedResourceVersion: .status.syncedResourceVersion
   }'
   ```

8. **Display Results**:
   ```
   ═══════════════════════════════════════════════════════════
   SYNC RESULTS
   ═══════════════════════════════════════════════════════════
   
   ✓ production/db-credentials
     Previous Sync: 2024-01-15T13:30:00Z
     Current Sync:  2024-01-15T14:45:00Z
     Status: SecretSynced
     Target Secret: db-secret (updated)
   
   ✓ production/api-keys
     Previous Sync: 2024-01-15T14:15:00Z
     Current Sync:  2024-01-15T14:45:00Z
     Status: SecretSynced
     Target Secret: api-secret (updated)
   
   ❌ staging/db-credentials
     Previous Sync: 2024-01-15T12:45:00Z
     Current Sync:  Failed
     Status: SecretSyncedError
     Error: permission denied
     
     Troubleshooting:
     /external-secrets-operator:diagnose --external-secret db-credentials --namespace staging
   
   ─────────────────────────────────────────────────────────────
   Summary: 2 synced, 1 failed
   ```

9. **Batch Sync Progress** (for `--all`, `--store`, or `--failed`):
   ```
   Syncing ExternalSecrets...
   
   [1/10] production/db-credentials      ✓ Synced
   [2/10] production/api-keys            ✓ Synced
   [3/10] production/oauth-config        ❌ Failed (store not ready)
   [4/10] staging/db-credentials         ✓ Synced
   ...
   
   ═══════════════════════════════════════════════════════════
   SYNC COMPLETE
   ═══════════════════════════════════════════════════════════
   
   Total:   10
   Synced:  8
   Failed:  2
   
   Failed ExternalSecrets:
   - production/oauth-config: SecretStore azure-keyvault is not ready
   - development/test-secret: AccessDeniedException
   
   Run /external-secrets-operator:diagnose to troubleshoot failures.
   ```

## Return Value
- **Success**: All specified ExternalSecrets synced successfully
- **Partial Success**: Some ExternalSecrets synced, some failed
- **Error**: Sync failed with error details
- **Format**: Progress indicator and summary of results

## Examples

1. **Sync a specific ExternalSecret**:
   ```
   /external-secrets-operator:sync db-credentials --namespace production
   ```

2. **Sync all ExternalSecrets in a namespace**:
   ```
   /external-secrets-operator:sync --all --namespace production
   ```

3. **Sync all ExternalSecrets cluster-wide**:
   ```
   /external-secrets-operator:sync --all
   ```

4. **Sync all ExternalSecrets using a specific store**:
   ```
   /external-secrets-operator:sync --store vault-backend
   ```

5. **Sync only failed ExternalSecrets**:
   ```
   /external-secrets-operator:sync --failed
   ```

6. **Sync failed ExternalSecrets in a namespace**:
   ```
   /external-secrets-operator:sync --failed --namespace production
   ```

7. **Dry run to see what would be synced**:
   ```
   /external-secrets-operator:sync --all --dry-run
   ```

8. **Sync after updating a secret in external provider**:
   ```
   # After updating secret in AWS Secrets Manager:
   /external-secrets-operator:sync my-aws-secret --namespace my-app
   ```

## Arguments
- **$1** (name): Name of the ExternalSecret to sync
  - Required unless using `--all`, `--store`, or `--failed`
  - Example: `db-credentials`
- **--namespace** (required for single secret): Namespace of the ExternalSecret
  - Optional when used with `--all`, `--store`, or `--failed` (filters to namespace)
  - Example: `--namespace production`
- **--all** (optional): Sync all ExternalSecrets
  - Can be combined with `--namespace` to limit scope
  - Example: `--all --namespace production`
- **--store** (optional): Sync all ExternalSecrets using a specific SecretStore
  - Syncs ExternalSecrets referencing this store name
  - Example: `--store vault-backend`
- **--failed** (optional): Sync only ExternalSecrets that are currently in failed state
  - Useful for retrying after fixing issues
  - Example: `--failed`
- **--dry-run** (optional): Show what would be synced without actually syncing
  - Example: `--dry-run`

## Use Cases

### 1. Immediate Secret Update
When you've updated a secret in your external provider and need it reflected immediately:
```
/external-secrets-operator:sync api-key --namespace production
```

### 2. Retry After Fixing Store Configuration
After fixing a SecretStore configuration issue:
```
/external-secrets-operator:sync --store azure-keyvault
```

### 3. Retry Failed Syncs
After resolving external provider issues:
```
/external-secrets-operator:sync --failed
```

### 4. Verify Connectivity
To test that the external provider connection is working:
```
/external-secrets-operator:sync test-secret --namespace test
```

### 5. Batch Refresh Before Deployment
Before a deployment, ensure all secrets are fresh:
```
/external-secrets-operator:sync --all --namespace production
```

## Notes

- **Sync Mechanism**: The sync is triggered by adding/updating an annotation on the ExternalSecret, which causes the controller to reconcile immediately
- **Rate Limiting**: Be aware of rate limits on your external secret provider when syncing many secrets
- **Sync Timeout**: The command waits up to 60 seconds for each sync to complete
- **Failed Syncs**: Failed syncs indicate issues with the external provider or configuration - use `/external-secrets-operator:diagnose` to troubleshoot
- **Target Secret**: The Kubernetes secret is updated in-place; pods using the secret may need to be restarted to pick up changes (unless using something like Reloader)

## Related Commands

- `/external-secrets-operator:status` - Check sync status
- `/external-secrets-operator:list` - List ExternalSecrets
- `/external-secrets-operator:diagnose` - Troubleshoot sync failures
- `/external-secrets-operator:guide` - Provider configuration help

## Additional Resources

- [External Secrets Operator for Red Hat OpenShift](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift)
- [ExternalSecret Refresh](https://external-secrets.io/latest/api/externalsecret/#refresh-interval)

