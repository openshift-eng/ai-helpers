# External Secrets Operator Plugin

A plugin for managing the [External Secrets Operator for Red Hat OpenShift](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift), which synchronizes secrets from external secret management systems (AWS Secrets Manager, HashiCorp Vault, Google Cloud Secret Manager, Azure Key Vault, Bitwarden, and more) into Kubernetes secrets.

## Overview

The External Secrets Operator allows you to:
- Sync secrets from external providers into Kubernetes secrets
- Support multiple secret providers (AWS, Azure, GCP, HashiCorp Vault, Bitwarden, and more)
- Automatically refresh secrets based on configurable intervals
- Use templating to transform secrets during synchronization

## Commands

### Installation & Lifecycle

#### `/external-secrets-operator:install`

Install the External Secrets Operator for Red Hat OpenShift and optionally configure a secret store.

```bash
/external-secrets-operator:install [--namespace <namespace>] [--channel <channel>] [--store-type <provider>]
```

#### `/external-secrets-operator:uninstall`

Uninstall the External Secrets Operator and optionally clean up all related resources.

```bash
/external-secrets-operator:uninstall [--namespace <namespace>] [--remove-crds] [--remove-namespace]
```

### Day-to-Day Operations

#### `/external-secrets-operator:status`

Quick health check showing operator status and ExternalSecret sync status.

```bash
/external-secrets-operator:status [--namespace <namespace>] [--watch]
```

#### `/external-secrets-operator:list`

List ExternalSecrets, SecretStores, and ClusterSecretStores with filtering options.

```bash
/external-secrets-operator:list [externalsecrets|secretstores|clustersecretstores|all] [--namespace <namespace>] [--status synced|failed]
```

#### `/external-secrets-operator:sync`

Force refresh ExternalSecrets to sync from external providers.

```bash
/external-secrets-operator:sync <name> --namespace <namespace>
/external-secrets-operator:sync --all [--namespace <namespace>]
/external-secrets-operator:sync --failed
```

### Troubleshooting & Help

#### `/external-secrets-operator:diagnose`

Diagnose issues with the External Secrets Operator, SecretStores, and ExternalSecrets.

```bash
/external-secrets-operator:diagnose [--namespace <namespace>] [--external-secret <name>] [--store <name>]
```

#### `/external-secrets-operator:guide`

Get step-by-step configuration guides for specific secret providers, including account setup, SecretStore configuration, and ExternalSecret examples.

```bash
/external-secrets-operator:guide <provider>
```

**Supported providers**: `aws`, `azure`, `gcp`, `vault`, `bitwarden`, `kubernetes`, `1password`, `doppler`, `infisical`, and more.

## Key Resources

### Operator Resources
- **OperatorConfig**: Configure the External Secrets Operator behavior
- **Deployment**: The operator controller managing external secrets

### Secret Store Resources
- **SecretStore**: Namespace-scoped secret store configuration
- **ClusterSecretStore**: Cluster-wide secret store configuration

### External Secret Resources
- **ExternalSecret**: Namespace-scoped external secret definition
- **ClusterExternalSecret**: Cluster-wide external secret template
- **PushSecret**: Push Kubernetes secrets to external providers

## Supported Providers

The External Secrets Operator supports multiple secret management providers:

- **AWS Secrets Manager / Parameter Store**
- **Azure Key Vault**
- **Google Cloud Secret Manager**
- **HashiCorp Vault**
- **Bitwarden Secrets Manager**
- **1Password**
- **Doppler**
- **Infisical**
- **IBM Cloud Secrets Manager**
- **CyberArk Conjur**
- **Kubernetes Secrets** (for secret replication)
- **Oracle Vault**
- **Keeper Security**
- And many more...

## Quick Start

### 1. Install the operator

```bash
/external-secrets-operator:install
```

### 2. Get help configuring your provider

```bash
/external-secrets-operator:guide bitwarden
```

### 3. Check status

```bash
/external-secrets-operator:status
```

### 4. List all ExternalSecrets

```bash
/external-secrets-operator:list es
```

### 5. Force sync a secret

```bash
/external-secrets-operator:sync my-secret --namespace my-app
```

### 6. Diagnose issues

```bash
/external-secrets-operator:diagnose --external-secret my-secret --namespace my-app
```

## Documentation

- [External Secrets Operator for Red Hat OpenShift](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/security_and_compliance/external-secrets-operator-for-red-hat-openshift)
- [External Secrets Operator Community Documentation](https://external-secrets.io/latest/)
- [GitHub: openshift/external-secrets-operator-release](https://github.com/openshift/external-secrets-operator-release)
- [GitHub: external-secrets/external-secrets](https://github.com/external-secrets/external-secrets)

## Prerequisites

- OpenShift Container Platform 4.14 or later
- `oc` CLI installed and authenticated to the cluster
- Cluster-admin privileges for installation
