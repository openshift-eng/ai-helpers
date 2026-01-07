---
description: Install the External Secrets Operator for Red Hat OpenShift and optionally configure a secret store
argument-hint: "[--namespace <namespace>] [--channel <channel>] [--store-type <provider>]"
---

## Name
external-secrets-operator:install

## Synopsis
```
/external-secrets-operator:install [--namespace <namespace>] [--channel <channel>] [--store-type <provider>]
```

## Description
The `external-secrets-operator:install` command installs the External Secrets Operator for Red Hat OpenShift using OLM (Operator Lifecycle Manager). This operator synchronizes secrets from external secret management systems into Kubernetes secrets.

The command handles:
- Creating the operator namespace
- Installing the operator via OLM Subscription
- Waiting for the operator to become ready
- Optionally guiding through SecretStore/ClusterSecretStore configuration

### Supported Secret Providers

The External Secrets Operator supports multiple providers:
- **AWS Secrets Manager** and **AWS Parameter Store**
- **Azure Key Vault**
- **Google Cloud Secret Manager**
- **HashiCorp Vault**
- **IBM Cloud Secrets Manager**
- **CyberArk Conjur**
- **Kubernetes** (for secret replication between namespaces/clusters)

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - `--namespace`: Target namespace for the operator (default: `external-secrets-operator`)
   - `--channel`: OLM subscription channel (default: auto-discovered from PackageManifest)
   - `--store-type`: Optional secret store provider to configure after installation

2. **Prerequisites Check**:
   - Verify `oc` CLI is installed: `which oc`
   - Verify cluster access: `oc whoami`
   - Check OpenShift version is 4.14+:
     ```bash
     oc version -o json | jq -r '.openshiftVersion'
     ```
   - Verify cluster-admin privileges

3. **Check if Already Installed**:
   - Check for existing subscription:
     ```bash
     oc get subscription external-secrets-operator -n external-secrets-operator --ignore-not-found
     ```
   - If already installed, inform user and offer to check status instead

4. **Discover Operator Metadata**:
   - Get the PackageManifest:
     ```bash
     oc get packagemanifest external-secrets-operator -n openshift-marketplace -o json
     ```
   - Extract default channel and catalog source
   - If not found, operator may not be available in the cluster's catalog sources

5. **Create Namespace**:
   - Check if namespace exists:
     ```bash
     oc get namespace {namespace} --ignore-not-found
     ```
   - If not exists, create it:
     ```bash
     oc create namespace {namespace}
     ```
   - Apply recommended labels:
     ```bash
     oc label namespace {namespace} openshift.io/cluster-monitoring=true --overwrite
     ```

6. **Create OperatorGroup**:
   - Check if OperatorGroup exists:
     ```bash
     oc get operatorgroup -n {namespace} --ignore-not-found
     ```
   - If not exists, create one:
     ```yaml
     apiVersion: operators.coreos.com/v1
     kind: OperatorGroup
     metadata:
       name: external-secrets-operator
       namespace: {namespace}
     spec:
       targetNamespaces:
       - {namespace}
     ```
   - Apply with:
     ```bash
     oc apply -f /tmp/external-secrets-operatorgroup.yaml
     ```

7. **Create Subscription**:
   - Create the subscription manifest:
     ```yaml
     apiVersion: operators.coreos.com/v1alpha1
     kind: Subscription
     metadata:
       name: external-secrets-operator
       namespace: {namespace}
     spec:
       channel: {channel}
       name: external-secrets-operator
       source: redhat-operators
       sourceNamespace: openshift-marketplace
       installPlanApproval: Automatic
     ```
   - Apply with:
     ```bash
     oc apply -f /tmp/external-secrets-subscription.yaml
     ```

8. **Wait for Operator Installation**:
   - Wait for CSV to be created and reach "Succeeded" phase:
     ```bash
     oc get csv -n {namespace} -l operators.coreos.com/external-secrets-operator.{namespace}= -o jsonpath='{.items[0].status.phase}'
     ```
   - Poll every 10 seconds with 5-minute timeout
   - Display progress updates to user

9. **Verify Operator Deployment**:
   - Check the operator deployment is ready:
     ```bash
     oc get deployment -n {namespace} -l app.kubernetes.io/name=external-secrets-operator
     ```
   - Check pods are running:
     ```bash
     oc get pods -n {namespace}
     ```
   - Verify CRDs are installed:
     ```bash
     oc get crd | grep external-secrets.io
     ```

10. **Configure Secret Store** (if `--store-type` provided):
    - Guide user through provider-specific configuration
    - For each provider, explain required credentials and configuration
    
    **AWS Secrets Manager**:
    ```yaml
    apiVersion: external-secrets.io/v1beta1
    kind: ClusterSecretStore
    metadata:
      name: aws-secretsmanager
    spec:
      provider:
        aws:
          service: SecretsManager
          region: {region}
          auth:
            secretRef:
              accessKeyIDSecretRef:
                name: aws-credentials
                key: access-key-id
                namespace: {namespace}
              secretAccessKeySecretRef:
                name: aws-credentials
                key: secret-access-key
                namespace: {namespace}
    ```
    
    **Azure Key Vault**:
    ```yaml
    apiVersion: external-secrets.io/v1beta1
    kind: ClusterSecretStore
    metadata:
      name: azure-keyvault
    spec:
      provider:
        azurekv:
          tenantId: {tenant-id}
          vaultUrl: https://{vault-name}.vault.azure.net
          authSecretRef:
            clientId:
              name: azure-credentials
              key: client-id
              namespace: {namespace}
            clientSecret:
              name: azure-credentials
              key: client-secret
              namespace: {namespace}
    ```
    
    **HashiCorp Vault**:
    ```yaml
    apiVersion: external-secrets.io/v1beta1
    kind: ClusterSecretStore
    metadata:
      name: vault-backend
    spec:
      provider:
        vault:
          server: https://{vault-addr}
          path: secret
          version: v2
          auth:
            tokenSecretRef:
              name: vault-token
              key: token
              namespace: {namespace}
    ```
    
    **Google Cloud Secret Manager**:
    ```yaml
    apiVersion: external-secrets.io/v1beta1
    kind: ClusterSecretStore
    metadata:
      name: gcp-secretmanager
    spec:
      provider:
        gcpsm:
          projectID: {project-id}
          auth:
            secretRef:
              secretAccessKeySecretRef:
                name: gcp-credentials
                key: credentials.json
                namespace: {namespace}
    ```

11. **Display Installation Summary**:
    ```
    ✓ External Secrets Operator Installation Complete
    
    Operator Details:
    - Namespace: {namespace}
    - CSV: {csv-name}
    - Version: {version}
    
    Installed CRDs:
    - externalsecrets.external-secrets.io
    - secretstores.external-secrets.io
    - clustersecretstores.external-secrets.io
    - clusterexternalsecrets.external-secrets.io
    - pushsecrets.external-secrets.io
    
    Next Steps:
    1. Create a SecretStore or ClusterSecretStore for your provider
    2. Create ExternalSecret resources to sync secrets
    
    Documentation:
    - Red Hat: https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift
    - Community: https://external-secrets.io/latest/
    
    Example ExternalSecret:
    ---
    apiVersion: external-secrets.io/v1beta1
    kind: ExternalSecret
    metadata:
      name: my-secret
      namespace: my-app
    spec:
      refreshInterval: 1h
      secretStoreRef:
        name: {store-name}
        kind: ClusterSecretStore
      target:
        name: my-k8s-secret
      data:
      - secretKey: password
        remoteRef:
          key: my-secret-path
          property: password
    ```

12. **Cleanup Temporary Files**:
    - Remove temporary YAML files:
      ```bash
      rm -f /tmp/external-secrets-*.yaml
      ```

## Return Value
- **Success**: Operator installed successfully with details about the CSV, deployments, and CRDs
- **Error**: Installation failed with specific error message and troubleshooting suggestions
- **Format**: Structured output showing:
  - Namespace created/used
  - Subscription and CSV status
  - Installed CRDs
  - Next steps for configuration

## Examples

1. **Install with defaults**:
   ```
   /external-secrets:install
   ```
   Installs the operator in `external-secrets-operator` namespace using the default channel.

2. **Install in custom namespace**:
   ```
   /external-secrets:install --namespace my-eso
   ```

3. **Install with specific channel**:
   ```
   /external-secrets:install --channel stable-v0.10
   ```

4. **Install and configure AWS provider**:
   ```
   /external-secrets:install --store-type aws
   ```
   This will install the operator and guide through AWS Secrets Manager configuration.

5. **Install and configure HashiCorp Vault**:
   ```
   /external-secrets:install --store-type vault
   ```

## Arguments
- **--namespace** (optional): Target namespace for the operator installation
  - Default: `external-secrets-operator`
  - Example: `--namespace my-eso`
- **--channel** (optional): OLM subscription channel
  - Default: Auto-discovered from PackageManifest
  - Example: `--channel stable-v0.10`
- **--store-type** (optional): Secret store provider to configure after installation
  - Options: `aws`, `azure`, `gcp`, `vault`, `kubernetes`
  - Example: `--store-type aws`

## Notes

- **OpenShift Version**: Requires OpenShift Container Platform 4.14 or later
- **Network Policy**: Consider configuring network policies for the operand namespace. See [Configuring network policy for the operand](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift#eso-network-policy_external-secrets-operator-for-red-hat-openshift)
- **Egress Proxy**: If your cluster uses an egress proxy, configure it for the operator. See [About the egress proxy](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift#eso-egress-proxy_external-secrets-operator-for-red-hat-openshift)
- **Monitoring**: Enable monitoring by setting `openshift.io/cluster-monitoring=true` label on the namespace

## Troubleshooting

- **Operator not found in catalog**:
  ```bash
  oc get packagemanifests -n openshift-marketplace | grep external-secrets
  ```
  If not listed, ensure the Red Hat operators catalog is available.

- **Installation timeout**: Check InstallPlan and CSV status:
  ```bash
  oc get installplan -n {namespace}
  oc get csv -n {namespace}
  oc describe csv -n {namespace}
  ```

- **Operator pod not starting**: Check pod logs:
  ```bash
  oc logs -n {namespace} deployment/external-secrets-operator
  ```

- **CRDs not installed**: Verify the CSV succeeded:
  ```bash
  oc get csv -n {namespace} -o jsonpath='{.items[0].status.phase}'
  ```

## Related Commands

- `/external-secrets-operator:status` - Check operator and sync status
- `/external-secrets-operator:list` - List all External Secrets resources
- `/external-secrets-operator:diagnose` - Diagnose operator and secret sync issues
- `/external-secrets-operator:uninstall` - Uninstall the operator
- `/external-secrets-operator:guide` - Get provider-specific configuration guides

## Additional Resources

- [External Secrets Operator for Red Hat OpenShift](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift)
- [Installing the External Secrets Operator](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift#eso-install_external-secrets-operator-for-red-hat-openshift)
- [External Secrets Community Documentation](https://external-secrets.io/latest/)
- [GitHub: openshift/external-secrets-operator-release](https://github.com/openshift/external-secrets-operator-release)

