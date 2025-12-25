---
description: Get step-by-step configuration guides for specific secret providers
argument-hint: <provider>
---

## Name
external-secrets-operator:guide

## Synopsis
```
/external-secrets-operator:guide <provider>
```

## Description
The `external-secrets-operator:guide` command provides comprehensive step-by-step guides for configuring specific secret providers with the External Secrets Operator. It covers:

- Account creation and prerequisites for the provider
- Authentication setup and credential configuration
- SecretStore or ClusterSecretStore configuration
- ExternalSecret examples for common use cases
- Troubleshooting tips specific to the provider

This command helps users understand what's required end-to-end to integrate a specific secret management provider with their OpenShift cluster.

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - `$1`: Provider name (required)
   - Supported providers: `aws`, `azure`, `gcp`, `vault`, `bitwarden`, `kubernetes`, `ibm`, `conjur`, `1password`, `doppler`, `infisical`, `keeper`, `oracle`, `scaleway`, `webhook`, `yandex`

2. **Validate Provider**:
   - Check if the provider is supported
   - If not supported, list available providers

3. **Display Provider Guide**:
   - Based on the provider, display the appropriate configuration guide

---

### Provider: Bitwarden Secrets Manager

**Documentation**: https://external-secrets.io/latest/provider/bitwarden-secrets-manager/

#### Step 1: Prerequisites - Create Bitwarden Account

1. **Create a Bitwarden Organization**:
   - Go to https://bitwarden.com/products/secrets-manager/
   - Sign up for Bitwarden Secrets Manager
   - Create an organization or use an existing one

2. **Create a Machine Account**:
   - Navigate to Secrets Manager in your Bitwarden organization
   - Go to Machine Accounts → New Machine Account
   - Give it a name (e.g., `openshift-external-secrets`)
   - Note: Machine accounts are service accounts for programmatic access

3. **Generate Access Token**:
   - Select your machine account
   - Go to Access Tokens → Create Access Token
   - Copy the access token (you won't see it again)
   - This token will be used for authentication

4. **Create Projects and Secrets**:
   - Create a Project in Secrets Manager
   - Add secrets to your project
   - Grant the machine account access to the project

#### Step 2: Create Authentication Secret in OpenShift

Create a Kubernetes secret containing the Bitwarden access token:

```bash
oc create secret generic bitwarden-credentials \
  --from-literal=token='<your-access-token>' \
  -n external-secrets-operator
```

Or using YAML:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: bitwarden-credentials
  namespace: external-secrets-operator
type: Opaque
stringData:
  token: "<your-access-token>"
```

#### Step 3: Create ClusterSecretStore

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: bitwarden-secrets-manager
spec:
  provider:
    bitwardensecretsmanager:
      apiURL: https://api.bitwarden.com
      identityURL: https://identity.bitwarden.com
      auth:
        secretRef:
          credentials:
            name: bitwarden-credentials
            namespace: external-secrets-operator
            key: token
```

For self-hosted Bitwarden:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: bitwarden-self-hosted
spec:
  provider:
    bitwardensecretsmanager:
      apiURL: https://your-bitwarden-api.example.com
      identityURL: https://your-bitwarden-identity.example.com
      auth:
        secretRef:
          credentials:
            name: bitwarden-credentials
            namespace: external-secrets-operator
            key: token
```

#### Step 4: Create ExternalSecret

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: my-bitwarden-secret
  namespace: my-app
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: bitwarden-secrets-manager
    kind: ClusterSecretStore
  target:
    name: my-k8s-secret
    creationPolicy: Owner
  data:
  - secretKey: database-password
    remoteRef:
      key: <bitwarden-secret-uuid>  # UUID of the secret in Bitwarden
```

#### Bitwarden-Specific Notes

- **Secret Keys**: Bitwarden uses UUIDs to reference secrets, not paths
- **Project Access**: The machine account must have access to the project containing the secrets
- **Rate Limits**: Be mindful of API rate limits for refresh intervals
- **Self-Hosted**: Adjust `apiURL` and `identityURL` for self-hosted installations

---

### Provider: AWS Secrets Manager

**Documentation**: https://external-secrets.io/latest/provider/aws-secrets-manager/

#### Step 1: Prerequisites - AWS Setup

1. **Create IAM User or Role**:
   - Go to AWS IAM Console
   - Create a new IAM user or role for External Secrets
   - For EKS with IRSA (recommended), create an IAM role with trust policy for your service account

2. **Attach IAM Policy**:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "secretsmanager:GetSecretValue",
           "secretsmanager:DescribeSecret",
           "secretsmanager:ListSecrets"
         ],
         "Resource": "*"
       }
     ]
   }
   ```
   For production, scope the `Resource` to specific secret ARNs.

3. **Generate Access Keys** (if using static credentials):
   - In IAM Console, select the user
   - Security credentials → Create access key
   - Save the Access Key ID and Secret Access Key

#### Step 2: Create Authentication Secret

**Option A: Static Credentials**:

```bash
oc create secret generic aws-credentials \
  --from-literal=access-key-id='AKIAIOSFODNN7EXAMPLE' \
  --from-literal=secret-access-key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY' \
  -n external-secrets-operator
```

**Option B: Using IRSA (EKS)**:
Configure the operator service account with IAM role annotation.

#### Step 3: Create ClusterSecretStore

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secretsmanager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        secretRef:
          accessKeyIDSecretRef:
            name: aws-credentials
            namespace: external-secrets-operator
            key: access-key-id
          secretAccessKeySecretRef:
            name: aws-credentials
            namespace: external-secrets-operator
            key: secret-access-key
```

#### Step 4: Create ExternalSecret

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: database-credentials
  namespace: my-app
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secretsmanager
    kind: ClusterSecretStore
  target:
    name: db-credentials
  data:
  - secretKey: username
    remoteRef:
      key: prod/database/credentials
      property: username
  - secretKey: password
    remoteRef:
      key: prod/database/credentials
      property: password
```

---

### Provider: HashiCorp Vault

**Documentation**: https://external-secrets.io/latest/provider/hashicorp-vault/

#### Step 1: Prerequisites - Vault Setup

1. **Install/Access Vault**:
   - Self-hosted: https://developer.hashicorp.com/vault/docs/install
   - HCP Vault: https://cloud.hashicorp.com/products/vault

2. **Enable Secrets Engine**:
   ```bash
   vault secrets enable -path=secret kv-v2
   ```

3. **Create Policy for External Secrets**:
   ```hcl
   # external-secrets-policy.hcl
   path "secret/data/*" {
     capabilities = ["read"]
   }
   path "secret/metadata/*" {
     capabilities = ["read", "list"]
   }
   ```
   ```bash
   vault policy write external-secrets external-secrets-policy.hcl
   ```

4. **Configure Authentication** (choose one):

   **Token Auth**:
   ```bash
   vault token create -policy=external-secrets -ttl=768h
   ```

   **Kubernetes Auth** (recommended for OpenShift):
   ```bash
   vault auth enable kubernetes
   vault write auth/kubernetes/config \
     kubernetes_host="https://$KUBERNETES_SERVICE_HOST:$KUBERNETES_SERVICE_PORT"
   vault write auth/kubernetes/role/external-secrets \
     bound_service_account_names=external-secrets \
     bound_service_account_namespaces=external-secrets-operator \
     policies=external-secrets \
     ttl=1h
   ```

#### Step 2: Create Authentication Secret

**For Token Auth**:
```bash
oc create secret generic vault-token \
  --from-literal=token='hvs.CAESIG...' \
  -n external-secrets-operator
```

#### Step 3: Create ClusterSecretStore

**Token Auth**:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: vault-backend
spec:
  provider:
    vault:
      server: https://vault.example.com:8200
      path: secret
      version: v2
      auth:
        tokenSecretRef:
          name: vault-token
          namespace: external-secrets-operator
          key: token
```

**Kubernetes Auth**:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: vault-backend
spec:
  provider:
    vault:
      server: https://vault.example.com:8200
      path: secret
      version: v2
      auth:
        kubernetes:
          mountPath: kubernetes
          role: external-secrets
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets-operator
```

#### Step 4: Create ExternalSecret

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: vault-secret
  namespace: my-app
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: my-secret
  data:
  - secretKey: api-key
    remoteRef:
      key: secret/data/myapp/config
      property: api_key
```

---

### Provider: Azure Key Vault

**Documentation**: https://external-secrets.io/latest/provider/azure-key-vault/

#### Step 1: Prerequisites - Azure Setup

1. **Create Key Vault**:
   ```bash
   az keyvault create --name mykeyvault --resource-group mygroup --location eastus
   ```

2. **Create Service Principal**:
   ```bash
   az ad sp create-for-rbac --name external-secrets-sp --skip-assignment
   ```
   Save the output (appId, password, tenant).

3. **Assign Key Vault Permissions**:
   ```bash
   az keyvault set-policy --name mykeyvault \
     --spn <appId> \
     --secret-permissions get list
   ```

#### Step 2: Create Authentication Secret

```bash
oc create secret generic azure-credentials \
  --from-literal=client-id='<appId>' \
  --from-literal=client-secret='<password>' \
  -n external-secrets-operator
```

#### Step 3: Create ClusterSecretStore

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: azure-keyvault
spec:
  provider:
    azurekv:
      tenantId: "<tenant-id>"
      vaultUrl: "https://mykeyvault.vault.azure.net"
      authSecretRef:
        clientId:
          name: azure-credentials
          namespace: external-secrets-operator
          key: client-id
        clientSecret:
          name: azure-credentials
          namespace: external-secrets-operator
          key: client-secret
```

#### Step 4: Create ExternalSecret

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: azure-secret
  namespace: my-app
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: azure-keyvault
    kind: ClusterSecretStore
  target:
    name: my-secret
  data:
  - secretKey: password
    remoteRef:
      key: database-password
```

---

### Provider: Google Cloud Secret Manager

**Documentation**: https://external-secrets.io/latest/provider/google-secrets-manager/

#### Step 1: Prerequisites - GCP Setup

1. **Enable Secret Manager API**:
   ```bash
   gcloud services enable secretmanager.googleapis.com
   ```

2. **Create Service Account**:
   ```bash
   gcloud iam service-accounts create external-secrets \
     --display-name "External Secrets Operator"
   ```

3. **Grant Permissions**:
   ```bash
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:external-secrets@PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   ```

4. **Create Key File**:
   ```bash
   gcloud iam service-accounts keys create key.json \
     --iam-account external-secrets@PROJECT_ID.iam.gserviceaccount.com
   ```

#### Step 2: Create Authentication Secret

```bash
oc create secret generic gcp-credentials \
  --from-file=credentials.json=key.json \
  -n external-secrets-operator
```

#### Step 3: Create ClusterSecretStore

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: gcp-secretmanager
spec:
  provider:
    gcpsm:
      projectID: my-project-id
      auth:
        secretRef:
          secretAccessKeySecretRef:
            name: gcp-credentials
            namespace: external-secrets-operator
            key: credentials.json
```

#### Step 4: Create ExternalSecret

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: gcp-secret
  namespace: my-app
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: gcp-secretmanager
    kind: ClusterSecretStore
  target:
    name: my-secret
  data:
  - secretKey: api-key
    remoteRef:
      key: my-api-key
      version: latest
```

---

### Provider: 1Password

**Documentation**: https://external-secrets.io/latest/provider/1password-automation/

#### Step 1: Prerequisites - 1Password Setup

1. **Create 1Password Connect Server**:
   - Go to https://start.1password.com/
   - Navigate to Integrations → Secrets Automation
   - Set up a 1Password Connect server

2. **Create Connect Token**:
   - In 1Password, create a Connect Token
   - Download the `1password-credentials.json` file
   - Note the Connect server URL

3. **Create Vault Access Token**:
   - Create an access token for the vault containing your secrets

#### Step 2: Create Authentication Secret

```bash
oc create secret generic onepassword-credentials \
  --from-file=1password-credentials.json \
  --from-literal=token='<vault-access-token>' \
  -n external-secrets-operator
```

#### Step 3: Create ClusterSecretStore

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: onepassword
spec:
  provider:
    onepassword:
      connectHost: https://connect.1password.example.com
      vaults:
        my-vault: 1
      auth:
        secretRef:
          connectTokenSecretRef:
            name: onepassword-credentials
            namespace: external-secrets-operator
            key: token
```

#### Step 4: Create ExternalSecret

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: onepassword-secret
  namespace: my-app
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: onepassword
    kind: ClusterSecretStore
  target:
    name: my-secret
  data:
  - secretKey: password
    remoteRef:
      key: vaults/my-vault/items/Database Login
      property: password
```

---

### Provider: Doppler

**Documentation**: https://external-secrets.io/latest/provider/doppler/

#### Step 1: Prerequisites - Doppler Setup

1. **Create Doppler Account**:
   - Go to https://dashboard.doppler.com
   - Create a project and environments (dev, staging, prod)

2. **Create Service Token**:
   - Navigate to Project → Access
   - Create a Service Token with read access
   - Copy the token (starts with `dp.st.`)

#### Step 2: Create Authentication Secret

```bash
oc create secret generic doppler-credentials \
  --from-literal=token='dp.st.xxxx' \
  -n external-secrets-operator
```

#### Step 3: Create ClusterSecretStore

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: doppler
spec:
  provider:
    doppler:
      auth:
        secretRef:
          dopplerToken:
            name: doppler-credentials
            namespace: external-secrets-operator
            key: token
```

#### Step 4: Create ExternalSecret

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: doppler-secret
  namespace: my-app
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: doppler
    kind: ClusterSecretStore
  target:
    name: my-secret
  data:
  - secretKey: database-url
    remoteRef:
      key: DATABASE_URL
```

---

### Provider: Kubernetes (Secret Replication)

**Documentation**: https://external-secrets.io/latest/provider/kubernetes/

This provider replicates secrets between namespaces or clusters.

#### Step 2: Create Service Account and RBAC

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: eso-store-sa
  namespace: source-namespace
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: eso-store-role
  namespace: source-namespace
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: eso-store-rolebinding
  namespace: source-namespace
subjects:
- kind: ServiceAccount
  name: eso-store-sa
  namespace: source-namespace
roleRef:
  kind: Role
  name: eso-store-role
  apiGroup: rbac.authorization.k8s.io
```

#### Step 3: Create ClusterSecretStore

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: kubernetes-store
spec:
  provider:
    kubernetes:
      remoteNamespace: source-namespace
      server:
        caProvider:
          type: ConfigMap
          name: kube-root-ca.crt
          key: ca.crt
          namespace: source-namespace
      auth:
        serviceAccount:
          name: eso-store-sa
          namespace: source-namespace
```

#### Step 4: Create ExternalSecret

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: replicated-secret
  namespace: target-namespace
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: kubernetes-store
    kind: ClusterSecretStore
  target:
    name: copied-secret
  dataFrom:
  - extract:
      key: source-secret-name
```

---

4. **Display Quick Reference**:
   After showing the detailed guide, display a quick reference:
   
   ```
   ═══════════════════════════════════════════════════════════
   QUICK REFERENCE: {PROVIDER}
   ═══════════════════════════════════════════════════════════
   
   Steps Summary:
   1. ☐ Create account/setup provider
   2. ☐ Generate credentials/tokens
   3. ☐ Create authentication secret in OpenShift
   4. ☐ Create ClusterSecretStore
   5. ☐ Create ExternalSecret
   6. ☐ Verify sync: oc get externalsecret -n {namespace}
   
   Useful Commands:
   ─────────────────────────────────────────────────────────
   # Check SecretStore status
   oc get clustersecretstore {store-name} -o jsonpath='{.status}'
   
   # Check ExternalSecret sync status
   oc get externalsecret {name} -n {namespace}
   
   # View synced secret
   oc get secret {target-secret} -n {namespace} -o yaml
   
   # Debug sync issues
   /external-secrets-operator:diagnose --store {store-name}
   
   Documentation:
   ─────────────────────────────────────────────────────────
   - Provider Docs: {provider-doc-url}
   - ESO Reference: https://external-secrets.io/latest/
   - Red Hat Docs: https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift
   ```

## Return Value
- **Success**: Comprehensive provider configuration guide displayed
- **Error**: Unknown provider - list of supported providers shown
- **Format**: Step-by-step guide with:
  - Account setup instructions
  - Credential creation
  - SecretStore YAML examples
  - ExternalSecret YAML examples
  - Provider-specific notes
  - Quick reference summary

## Examples

1. **Get Bitwarden configuration guide**:
   ```
   /external-secrets-operator:guide bitwarden
   ```

2. **Get AWS Secrets Manager guide**:
   ```
   /external-secrets-operator:guide aws
   ```

3. **Get HashiCorp Vault guide**:
   ```
   /external-secrets-operator:guide vault
   ```

4. **Get Azure Key Vault guide**:
   ```
   /external-secrets-operator:guide azure
   ```

5. **Get 1Password guide**:
   ```
   /external-secrets-operator:guide 1password
   ```

6. **Get Kubernetes replication guide**:
   ```
   /external-secrets-operator:guide kubernetes
   ```

## Arguments
- **$1** (provider): The secret provider to get configuration guide for (required)
  - **aws**: AWS Secrets Manager / Parameter Store
  - **azure**: Azure Key Vault
  - **gcp**: Google Cloud Secret Manager
  - **vault**: HashiCorp Vault
  - **bitwarden**: Bitwarden Secrets Manager
  - **1password** / **onepassword**: 1Password Connect
  - **doppler**: Doppler SecretOps
  - **infisical**: Infisical
  - **kubernetes**: Kubernetes Secret Replication
  - **ibm**: IBM Cloud Secrets Manager
  - **conjur**: CyberArk Conjur
  - **keeper**: Keeper Security
  - **oracle**: Oracle Vault
  - **scaleway**: Scaleway Secret Manager
  - **webhook**: Generic Webhook Provider
  - **yandex**: Yandex Lockbox

## Related Commands

- `/external-secrets-operator:install` - Install the operator
- `/external-secrets-operator:status` - Check operator and sync status
- `/external-secrets-operator:list` - List all resources
- `/external-secrets-operator:sync` - Force refresh ExternalSecrets
- `/external-secrets-operator:diagnose` - Diagnose configuration issues
- `/external-secrets-operator:uninstall` - Uninstall the operator

## Additional Resources

- [External Secrets Operator Providers](https://external-secrets.io/latest/provider/aws-secrets-manager/)
- [External Secrets Operator for Red Hat OpenShift](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift)
- [Bitwarden Secrets Manager](https://bitwarden.com/products/secrets-manager/)
- [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/)
- [HashiCorp Vault](https://www.vaultproject.io/)
- [Azure Key Vault](https://azure.microsoft.com/en-us/products/key-vault)
- [Google Cloud Secret Manager](https://cloud.google.com/secret-manager)
- [1Password Secrets Automation](https://1password.com/products/secrets/)
- [Doppler](https://www.doppler.com/)

