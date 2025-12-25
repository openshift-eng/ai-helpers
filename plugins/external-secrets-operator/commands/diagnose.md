---
description: Diagnose issues with External Secrets Operator, SecretStores, and ExternalSecrets
argument-hint: "[--namespace <namespace>] [--external-secret <name>] [--store <name>] [--cluster-wide]"
---

## Name
external-secrets-operator:diagnose

## Synopsis
```
/external-secrets-operator:diagnose [--namespace <namespace>] [--external-secret <name>] [--store <name>] [--cluster-wide]
```

## Description
The `external-secrets-operator:diagnose` command diagnoses issues with the External Secrets Operator for Red Hat OpenShift, including operator health, SecretStore connectivity, and ExternalSecret synchronization problems.

This command helps you:
- Check operator deployment health and logs
- Verify SecretStore and ClusterSecretStore connectivity
- Debug ExternalSecret sync failures
- Identify authentication and authorization issues with external providers
- Detect configuration problems
- Generate comprehensive troubleshooting reports

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - `--namespace`: Specific namespace to check (default: all namespaces)
   - `--external-secret`: Specific ExternalSecret name to diagnose
   - `--store`: Specific SecretStore or ClusterSecretStore name to check
   - `--cluster-wide`: Run cluster-wide diagnostics

2. **Prerequisites Check**:
   - Verify `oc` CLI is installed: `which oc`
   - Verify cluster access: `oc whoami`
   - Check if External Secrets Operator is installed:
     ```bash
     oc get csv -A | grep external-secrets-operator
     ```

3. **Check Operator Health**:
   - Get operator namespace:
     ```bash
     oc get subscription external-secrets-operator -A -o jsonpath='{.items[0].metadata.namespace}'
     ```
   - Check CSV status:
     ```bash
     oc get csv -n {operator-namespace} -l operators.coreos.com/external-secrets-operator.{operator-namespace}= -o json
     ```
   - Check operator deployment:
     ```bash
     oc get deployment -n {operator-namespace} -l app.kubernetes.io/name=external-secrets-operator -o json
     ```
   - Check operator pods:
     ```bash
     oc get pods -n {operator-namespace} -l app.kubernetes.io/name=external-secrets-operator
     ```
   - Get recent operator logs:
     ```bash
     oc logs -n {operator-namespace} deployment/external-secrets-operator --tail=100
     ```
   - Check for error patterns in logs:
     - Authentication failures
     - Network connectivity issues
     - Rate limiting
     - Permission denied errors
   - Report findings:
     ```
     🔍 Operator Health Check
     
     Operator Namespace: {operator-namespace}
     CSV: {csv-name} (Phase: {phase})
     Deployment: {deployment-name} (Ready: {ready}/{desired})
     
     ✓ Operator is healthy
     
     [OR if issues found:]
     
     ❌ Operator Issues Detected
     
     - Pod {pod-name} is in CrashLoopBackOff
     - Recent errors in logs:
       - {error-message-1}
       - {error-message-2}
     ```

4. **Check ClusterSecretStores** (if `--cluster-wide` or no specific store):
   - Get all ClusterSecretStores:
     ```bash
     oc get clustersecretstores -o json
     ```
   - For each ClusterSecretStore:
     - Check status conditions:
       ```bash
       oc get clustersecretstore {name} -o jsonpath='{.status.conditions}'
       ```
     - Verify provider configuration
     - Check authentication secret references
   - Report findings:
     ```
     🔍 ClusterSecretStore Health
     
     ✓ aws-secretsmanager: Ready (Provider: AWS SecretsManager)
     ❌ vault-backend: Not Ready
        Reason: SecretAccessError
        Message: unable to authenticate: permission denied
     ⚠️ azure-keyvault: Unknown (no status reported)
     ```

5. **Check SecretStores** (namespace-scoped):
   - Get SecretStores in target namespace(s):
     ```bash
     oc get secretstores -n {namespace} -o json
     # OR for all namespaces:
     oc get secretstores -A -o json
     ```
   - For each SecretStore:
     - Check status conditions
     - Verify provider configuration
     - Check authentication secrets exist:
       ```bash
       oc get secret {auth-secret-name} -n {namespace} --ignore-not-found
       ```
   - Report findings similar to ClusterSecretStores

6. **Check ExternalSecrets**:
   - Get ExternalSecrets based on scope:
     ```bash
     # Specific ExternalSecret:
     oc get externalsecret {name} -n {namespace} -o json
     
     # All in namespace:
     oc get externalsecrets -n {namespace} -o json
     
     # Cluster-wide:
     oc get externalsecrets -A -o json
     ```
   - For each ExternalSecret, check:
     - Sync status: `.status.conditions`
     - Last sync time: `.status.refreshTime`
     - Synced resource version: `.status.syncedResourceVersion`
     - Target secret exists:
       ```bash
       oc get secret {target-secret-name} -n {namespace} --ignore-not-found
       ```
   - Identify common issues:
     - **SecretStore not found**: Referenced store doesn't exist
     - **SecretAccessError**: Cannot access secret from provider
     - **InvalidSecretStore**: Store configuration is invalid
     - **InvalidRemoteRef**: Secret path or key doesn't exist in provider
   - Report findings:
     ```
     🔍 ExternalSecret Status
     
     Namespace: {namespace}
     
     ✓ database-credentials
       Store: vault-backend (ClusterSecretStore)
       Target: db-secret
       Last Sync: 2024-01-15T10:30:00Z
       Status: SecretSynced
     
     ❌ api-keys
       Store: aws-secretsmanager (ClusterSecretStore)
       Target: api-secret
       Last Sync: Never
       Status: SecretSyncedError
       Reason: could not get secret data from provider
       Message: AccessDeniedException: User is not authorized to perform secretsmanager:GetSecretValue
     
     ⚠️ oauth-token
       Store: azure-keyvault (ClusterSecretStore)
       Target: oauth-secret
       Last Sync: 2024-01-14T08:00:00Z (24h ago - stale)
       Status: SecretSynced
       Warning: Last sync was over 24 hours ago, may be stale
     ```

7. **Check ClusterExternalSecrets**:
   - Get ClusterExternalSecrets:
     ```bash
     oc get clusterexternalsecrets -o json
     ```
   - Check which namespaces are targeted
   - Verify ExternalSecrets are created in target namespaces
   - Report any provisioning failures

8. **Check PushSecrets**:
   - Get PushSecrets:
     ```bash
     oc get pushsecrets -A -o json
     ```
   - Check sync status for pushing secrets to external providers
   - Report any push failures

9. **Diagnose Specific ExternalSecret** (if `--external-secret` provided):
   - Get detailed ExternalSecret info:
     ```bash
     oc get externalsecret {name} -n {namespace} -o yaml
     ```
   - Check the referenced SecretStore/ClusterSecretStore:
     ```bash
     oc get {store-kind} {store-name} [-n {namespace}] -o yaml
     ```
   - Verify authentication secrets:
     ```bash
     oc get secret {auth-secret} -n {auth-namespace} -o json
     ```
   - Check if target secret was created:
     ```bash
     oc get secret {target-secret} -n {namespace} -o yaml
     ```
   - Get operator logs filtered for this ExternalSecret:
     ```bash
     oc logs -n {operator-namespace} deployment/external-secrets-operator --tail=500 | grep -i {external-secret-name}
     ```
   - Provide detailed diagnosis:
     ```
     🔍 Detailed Diagnosis: {external-secret-name}
     
     ExternalSecret Configuration:
     - Namespace: {namespace}
     - Store Reference: {store-name} (kind: {store-kind})
     - Refresh Interval: {interval}
     - Target Secret: {target-name}
     - Data Keys: {keys}
     
     Store Status:
     - Name: {store-name}
     - Provider: {provider-type}
     - Status: {ready/not-ready}
     - Auth Method: {auth-method}
     
     Current Status:
     - Condition: {condition-type}
     - Status: {status}
     - Reason: {reason}
     - Message: {message}
     - Last Transition: {timestamp}
     
     [If error:]
     
     Root Cause Analysis:
     
     The ExternalSecret failed to sync because: {detailed-explanation}
     
     Recommended Actions:
     1. {action-1}
     2. {action-2}
     3. {action-3}
     
     Relevant Documentation:
     - {doc-link}
     ```

10. **Provider-Specific Diagnostics**:

    **AWS Secrets Manager/Parameter Store**:
    - Verify IAM credentials are valid
    - Check region configuration
    - Verify secret path exists in AWS:
      ```
      Suggested manual verification:
      aws secretsmanager get-secret-value --secret-id {secret-path} --region {region}
      ```
    - Common issues:
      - AccessDeniedException: IAM policy doesn't allow secretsmanager:GetSecretValue
      - ResourceNotFoundException: Secret doesn't exist
      - Region mismatch

    **HashiCorp Vault**:
    - Check Vault connectivity
    - Verify token/auth method validity
    - Check secret path and mount path
    - Common issues:
      - Permission denied: Policy doesn't allow reading secret
      - Path not found: Wrong secret path or mount
      - Token expired: Authentication token needs renewal

    **Azure Key Vault**:
    - Verify service principal credentials
    - Check vault URL and tenant ID
    - Verify secret exists in vault
    - Common issues:
      - Unauthorized: Service principal lacks access
      - SecretNotFound: Secret doesn't exist in vault
      - Certificate issues with vault endpoint

    **Google Cloud Secret Manager**:
    - Verify service account credentials
    - Check project ID configuration
    - Verify secret exists and version is accessible
    - Common issues:
      - Permission denied: IAM role missing secretmanager.secretAccessor
      - Not found: Secret or version doesn't exist

11. **Generate Comprehensive Report**:
    ```
    ═══════════════════════════════════════════════════════════
    EXTERNAL SECRETS OPERATOR HEALTH REPORT
    ═══════════════════════════════════════════════════════════
    
    Scan Time: {timestamp}
    Scope: {namespace-specific | cluster-wide}
    
    OPERATOR STATUS
    ───────────────────────────────────────────────────────────
    ✓ Operator: Running (v{version})
    ✓ CSV: Succeeded
    ✓ Pods: 1/1 Ready
    
    SECRET STORES
    ───────────────────────────────────────────────────────────
    ClusterSecretStores: {count} ({ready} ready, {not-ready} not ready)
    SecretStores: {count} ({ready} ready, {not-ready} not ready)
    
    EXTERNAL SECRETS
    ───────────────────────────────────────────────────────────
    Total: {count}
    ✓ Synced: {synced-count}
    ❌ Failed: {failed-count}
    ⚠️ Stale (>24h): {stale-count}
    
    ISSUES FOUND
    ───────────────────────────────────────────────────────────
    
    ❌ Critical Issues: {count}
    {list of critical issues}
    
    ⚠️ Warnings: {count}
    {list of warnings}
    
    RECOMMENDATIONS
    ───────────────────────────────────────────────────────────
    
    1. {recommendation-1}
    2. {recommendation-2}
    
    ═══════════════════════════════════════════════════════════
    
    For more details, see:
    - Red Hat Docs: https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift
    - Community Docs: https://external-secrets.io/latest/
    ```

## Return Value
- **Success**: Report generated with health status
- **Issues Found**: Detailed report with warnings and errors
- **Format**: Structured report showing:
  - Operator health status
  - SecretStore connectivity
  - ExternalSecret sync status
  - Detailed error analysis
  - Recommended remediation steps

## Examples

1. **Basic cluster-wide health check**:
   ```
   /external-secrets:diagnose --cluster-wide
   ```

2. **Check specific namespace**:
   ```
   /external-secrets:diagnose --namespace my-app
   ```

3. **Diagnose specific ExternalSecret**:
   ```
   /external-secrets:diagnose --external-secret database-creds --namespace production
   ```

4. **Check specific SecretStore**:
   ```
   /external-secrets:diagnose --store aws-secretsmanager
   ```

5. **Diagnose all ExternalSecrets using a specific store**:
   ```
   /external-secrets:diagnose --store vault-backend --cluster-wide
   ```

## Arguments
- **--namespace** (optional): Specific namespace to check
  - If not provided with `--cluster-wide`, checks all namespaces
  - Example: `--namespace production`
- **--external-secret** (optional): Specific ExternalSecret name to diagnose
  - Requires `--namespace` to be specified
  - Example: `--external-secret database-credentials`
- **--store** (optional): Specific SecretStore or ClusterSecretStore name
  - Checks the store health and all ExternalSecrets using it
  - Example: `--store aws-secretsmanager`
- **--cluster-wide** (optional): Run cluster-wide diagnostics
  - Checks all namespaces and all resources
  - Provides comprehensive overview

## Common Issues and Solutions

### SecretStore Authentication Failures

**Symptom**: SecretStore shows "NotReady" with authentication errors

**Diagnosis**:
```bash
oc get clustersecretstore {name} -o jsonpath='{.status.conditions}'
```

**Common Causes**:
1. **Invalid credentials**: Secret containing auth credentials is missing or incorrect
2. **Expired tokens**: Authentication token has expired (common with Vault)
3. **Wrong endpoint**: Provider URL is incorrect or unreachable

**Solutions**:
- Verify auth secret exists and contains correct keys
- Rotate/refresh credentials
- Check network connectivity to provider

### ExternalSecret Sync Failures

**Symptom**: ExternalSecret shows "SecretSyncedError"

**Diagnosis**:
```bash
oc get externalsecret {name} -n {namespace} -o jsonpath='{.status}'
```

**Common Causes**:
1. **Secret not found**: Remote secret path doesn't exist
2. **Permission denied**: Credentials lack permission to read secret
3. **Invalid key reference**: Property/key doesn't exist in remote secret

**Solutions**:
- Verify secret exists in external provider
- Check IAM/RBAC permissions in external provider
- Validate remoteRef path and property names

### Stale Secrets

**Symptom**: Secrets not updating despite changes in external provider

**Diagnosis**:
```bash
oc get externalsecret {name} -n {namespace} -o jsonpath='{.status.refreshTime}'
```

**Common Causes**:
1. **Operator not running**: Controller pod is down
2. **Rate limiting**: Provider is rate limiting requests
3. **Webhook issues**: If using refresh webhooks

**Solutions**:
- Check operator pod health
- Increase refresh interval to reduce API calls
- Force refresh by deleting and recreating ExternalSecret

## Related Commands

- `/external-secrets-operator:status` - Quick health check
- `/external-secrets-operator:list` - List all resources
- `/external-secrets-operator:sync` - Force refresh ExternalSecrets
- `/external-secrets-operator:install` - Install the operator
- `/external-secrets-operator:uninstall` - Uninstall the operator
- `/external-secrets-operator:guide` - Get provider-specific configuration guides

## Additional Resources

- [External Secrets Operator for Red Hat OpenShift](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift)
- [Monitoring the External Secrets Operator](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift#eso-monitoring_external-secrets-operator-for-red-hat-openshift)
- [External Secrets Troubleshooting Guide](https://external-secrets.io/latest/guides/troubleshooting/)
- [External Secrets API Reference](https://external-secrets.io/latest/api/externalsecret/)

