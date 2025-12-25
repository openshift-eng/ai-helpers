---
description: List ExternalSecrets, SecretStores, and ClusterSecretStores with filtering options
argument-hint: "[externalsecrets|secretstores|clustersecretstores|all] [--namespace <namespace>] [--store <name>] [--status <synced|failed|pending>]"
---

## Name
external-secrets-operator:list

## Synopsis
```
/external-secrets-operator:list [resource-type] [--namespace <namespace>] [--store <name>] [--status <synced|failed|pending>] [--output <table|wide|yaml|json>]
```

## Description
The `external-secrets-operator:list` command lists External Secrets resources with various filtering and output options. It provides a convenient way to view and filter ExternalSecrets, SecretStores, ClusterSecretStores, ClusterExternalSecrets, and PushSecrets.

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - `$1`: Resource type (default: `all`)
     - `externalsecrets` / `es`: List ExternalSecrets
     - `secretstores` / `ss`: List SecretStores
     - `clustersecretstores` / `css`: List ClusterSecretStores
     - `clusterexternalsecrets` / `ces`: List ClusterExternalSecrets
     - `pushsecrets` / `ps`: List PushSecrets
     - `all`: List all resource types
   - `--namespace`: Filter to specific namespace
   - `--store`: Filter ExternalSecrets by SecretStore name
   - `--status`: Filter by sync status (synced, failed, pending)
   - `--output`: Output format (table, wide, yaml, json)

2. **List ClusterSecretStores**:
   ```bash
   oc get clustersecretstores -o json | jq -r '
     .items[] | [
       .metadata.name,
       (.spec.provider | keys[0]),
       (.status.conditions[] | select(.type=="Ready") | .status),
       .metadata.creationTimestamp
     ] | @tsv'
   ```

   Output (table format):
   ```
   CLUSTER SECRET STORES
   ─────────────────────────────────────────────────────────────────────────────
   NAME                    PROVIDER              READY    AGE
   aws-secretsmanager      aws                   True     30d
   vault-backend           vault                 True     25d
   azure-keyvault          azurekv               False    10d
   gcp-secretmanager       gcpsm                 True     5d
   bitwarden-sm            bitwardensecretsmanager True   2d
   ```

3. **List SecretStores** (namespace-scoped):
   ```bash
   oc get secretstores ${NAMESPACE:+-n $NAMESPACE} -A -o json | jq -r '
     .items[] | [
       .metadata.namespace,
       .metadata.name,
       (.spec.provider | keys[0]),
       (.status.conditions[] | select(.type=="Ready") | .status),
       .metadata.creationTimestamp
     ] | @tsv'
   ```

   Output (table format):
   ```
   SECRET STORES
   ─────────────────────────────────────────────────────────────────────────────
   NAMESPACE       NAME                PROVIDER    READY    AGE
   team-a          team-vault          vault       True     15d
   team-b          team-aws            aws         True     10d
   dev             local-secrets       kubernetes  True     5d
   ```

4. **List ExternalSecrets**:
   ```bash
   oc get externalsecrets ${NAMESPACE:+-n $NAMESPACE} -A -o json | jq -r '
     .items[] | [
       .metadata.namespace,
       .metadata.name,
       .spec.secretStoreRef.name,
       .spec.secretStoreRef.kind,
       .spec.target.name,
       (.status.conditions[] | select(.type=="Ready") | .status),
       .status.refreshTime
     ] | @tsv'
   ```

   Output (table format):
   ```
   EXTERNAL SECRETS
   ─────────────────────────────────────────────────────────────────────────────
   NAMESPACE       NAME                    STORE                   TARGET SECRET       SYNCED    LAST SYNC
   production      db-credentials          vault-backend           db-secret           True      5m ago
   production      api-keys                aws-secretsmanager      api-secret          True      10m ago
   production      oauth-config            azure-keyvault          oauth-secret        False     Never
   staging         db-credentials          vault-backend           db-secret           True      3m ago
   development     test-secret             aws-secretsmanager      test-k8s-secret     False     1h ago
   ```

   Output (wide format adds more columns):
   ```
   EXTERNAL SECRETS (wide)
   ─────────────────────────────────────────────────────────────────────────────────────────────────────────
   NAMESPACE       NAME                STORE               KIND                  TARGET          SYNCED    REFRESH     LAST SYNC    AGE
   production      db-credentials      vault-backend       ClusterSecretStore    db-secret       True      1h          5m ago       30d
   production      api-keys            aws-secretsmanager  ClusterSecretStore    api-secret      True      30m         10m ago      25d
   ```

5. **List ClusterExternalSecrets**:
   ```bash
   oc get clusterexternalsecrets -o json | jq -r '
     .items[] | [
       .metadata.name,
       .spec.externalSecretName,
       (.spec.namespaceSelector | if .matchLabels then (.matchLabels | to_entries | map("\(.key)=\(.value)") | join(",")) else "All" end),
       (.status.provisionedNamespaces | length),
       (.status.failedNamespaces | length)
     ] | @tsv'
   ```

   Output:
   ```
   CLUSTER EXTERNAL SECRETS
   ─────────────────────────────────────────────────────────────────────────────
   NAME                    EXTERNAL SECRET NAME    NAMESPACE SELECTOR         PROVISIONED    FAILED
   shared-db-creds         db-credentials          env=production             5              0
   api-keys-all            api-keys                All                        12             1
   ```

6. **List PushSecrets**:
   ```bash
   oc get pushsecrets ${NAMESPACE:+-n $NAMESPACE} -A -o json | jq -r '
     .items[] | [
       .metadata.namespace,
       .metadata.name,
       .spec.secretStoreRefs[0].name,
       (.status.conditions[] | select(.type=="Ready") | .status),
       .status.refreshTime
     ] | @tsv'
   ```

   Output:
   ```
   PUSH SECRETS
   ─────────────────────────────────────────────────────────────────────────────
   NAMESPACE       NAME                    STORE               SYNCED    LAST PUSH
   production      push-to-vault           vault-backend       True      5m ago
   staging         push-api-key            aws-secretsmanager  True      1h ago
   ```

7. **Apply Filters**:

   **Filter by store**:
   ```bash
   # Filter ExternalSecrets using specific store
   oc get externalsecrets -A -o json | jq -r --arg store "$STORE" '
     .items[] | select(.spec.secretStoreRef.name == $store)'
   ```

   **Filter by status**:
   ```bash
   # Synced only
   oc get externalsecrets -A -o json | jq -r '
     .items[] | select(.status.conditions[] | select(.type=="Ready" and .status=="True"))'
   
   # Failed only
   oc get externalsecrets -A -o json | jq -r '
     .items[] | select(.status.conditions[] | select(.type=="Ready" and .status=="False"))'
   
   # Pending (no status yet)
   oc get externalsecrets -A -o json | jq -r '
     .items[] | select(.status.conditions == null or (.status.conditions | length == 0))'
   ```

8. **Display All Resources** (if `all` specified):
   ```
   ═══════════════════════════════════════════════════════════════════════════════
   EXTERNAL SECRETS RESOURCES
   ═══════════════════════════════════════════════════════════════════════════════
   
   CLUSTER SECRET STORES (5)
   ─────────────────────────────────────────────────────────────────────────────
   NAME                    PROVIDER              READY    AGE
   aws-secretsmanager      aws                   True     30d
   vault-backend           vault                 True     25d
   azure-keyvault          azurekv               False    10d
   gcp-secretmanager       gcpsm                 True     5d
   bitwarden-sm            bitwardensecretsmanager True   2d
   
   SECRET STORES (3)
   ─────────────────────────────────────────────────────────────────────────────
   NAMESPACE       NAME                PROVIDER    READY    AGE
   team-a          team-vault          vault       True     15d
   team-b          team-aws            aws         True     10d
   dev             local-secrets       kubernetes  True     5d
   
   EXTERNAL SECRETS (15)
   ─────────────────────────────────────────────────────────────────────────────
   NAMESPACE       NAME                    STORE                   TARGET SECRET       SYNCED    LAST SYNC
   production      db-credentials          vault-backend           db-secret           True      5m ago
   production      api-keys                aws-secretsmanager      api-secret          True      10m ago
   ...
   
   CLUSTER EXTERNAL SECRETS (2)
   ─────────────────────────────────────────────────────────────────────────────
   NAME                    EXTERNAL SECRET NAME    NAMESPACE SELECTOR         PROVISIONED    FAILED
   shared-db-creds         db-credentials          env=production             5              0
   api-keys-all            api-keys                All                        12             1
   
   PUSH SECRETS (2)
   ─────────────────────────────────────────────────────────────────────────────
   NAMESPACE       NAME                    STORE               SYNCED    LAST PUSH
   production      push-to-vault           vault-backend       True      5m ago
   staging         push-api-key            aws-secretsmanager  True      1h ago
   
   ═══════════════════════════════════════════════════════════════════════════════
   SUMMARY
   ═══════════════════════════════════════════════════════════════════════════════
   ClusterSecretStores:    5 (4 ready, 1 not ready)
   SecretStores:           3 (3 ready)
   ExternalSecrets:        15 (13 synced, 2 failed)
   ClusterExternalSecrets: 2
   PushSecrets:            2 (2 synced)
   ```

9. **Output Formats**:

   **YAML output**:
   ```bash
   oc get externalsecrets -A -o yaml
   ```

   **JSON output**:
   ```bash
   oc get externalsecrets -A -o json
   ```

## Return Value
- **Success**: Formatted list of resources
- **Format**: Table, wide, YAML, or JSON output

## Examples

1. **List all resources**:
   ```
   /external-secrets-operator:list
   ```
   or
   ```
   /external-secrets-operator:list all
   ```

2. **List only ExternalSecrets**:
   ```
   /external-secrets-operator:list externalsecrets
   ```
   or shorthand:
   ```
   /external-secrets-operator:list es
   ```

3. **List ClusterSecretStores**:
   ```
   /external-secrets-operator:list clustersecretstores
   ```
   or shorthand:
   ```
   /external-secrets-operator:list css
   ```

4. **List ExternalSecrets in specific namespace**:
   ```
   /external-secrets-operator:list es --namespace production
   ```

5. **List ExternalSecrets using specific store**:
   ```
   /external-secrets-operator:list es --store vault-backend
   ```

6. **List only failed ExternalSecrets**:
   ```
   /external-secrets-operator:list es --status failed
   ```

7. **List synced ExternalSecrets in production**:
   ```
   /external-secrets-operator:list es --namespace production --status synced
   ```

8. **Wide output with more details**:
   ```
   /external-secrets-operator:list es --output wide
   ```

9. **YAML output for scripting**:
   ```
   /external-secrets-operator:list es --namespace production --output yaml
   ```

10. **JSON output for processing**:
    ```
    /external-secrets-operator:list css --output json
    ```

## Arguments
- **$1** (resource-type): Type of resource to list (optional, default: `all`)
  - `externalsecrets` / `es`: ExternalSecrets
  - `secretstores` / `ss`: SecretStores (namespace-scoped)
  - `clustersecretstores` / `css`: ClusterSecretStores
  - `clusterexternalsecrets` / `ces`: ClusterExternalSecrets
  - `pushsecrets` / `ps`: PushSecrets
  - `all`: All resource types
- **--namespace** (optional): Filter to specific namespace
  - Only applies to namespace-scoped resources (ExternalSecrets, SecretStores, PushSecrets)
  - Example: `--namespace production`
- **--store** (optional): Filter ExternalSecrets by SecretStore name
  - Example: `--store vault-backend`
- **--status** (optional): Filter by sync status
  - `synced`: Only successfully synced resources
  - `failed`: Only failed resources
  - `pending`: Resources without status yet
  - Example: `--status failed`
- **--output** (optional): Output format
  - `table`: Default tabular format
  - `wide`: Extended table with more columns
  - `yaml`: YAML format
  - `json`: JSON format
  - Example: `--output wide`

## Notes

- **Shorthand Names**: Use `es`, `ss`, `css`, `ces`, `ps` for quicker typing
- **Namespace Scope**: ClusterSecretStores and ClusterExternalSecrets are cluster-scoped
- **Age Calculation**: Age shows time since resource creation
- **Last Sync**: Shows time since last successful sync for ExternalSecrets

## Related Commands

- `/external-secrets-operator:status` - Quick health check and summary
- `/external-secrets-operator:diagnose` - Detailed troubleshooting
- `/external-secrets-operator:sync` - Force refresh ExternalSecrets

## Additional Resources

- [External Secrets API Reference](https://external-secrets.io/latest/api/externalsecret/)
- [External Secrets Operator for Red Hat OpenShift](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift)

