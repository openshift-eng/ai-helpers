---
description: Install a day-2 operator using Operator Lifecycle Manager
argument-hint: <operator-name> [namespace] [channel] [source] [--approval=Automatic|Manual]
---

## Name
olm:install

## Synopsis
```
/olm:install <operator-name> [namespace] [channel] [source] [--approval=Automatic|Manual]
```

## Description
The `olm:install` command installs a day-2 operator in an OpenShift cluster using Operator Lifecycle Manager (OLM). It automates the creation of the required namespace, OperatorGroup, and Subscription resources needed to install an operator.

This command handles the complete operator installation workflow:
- Creates or verifies the target namespace exists
- Creates an OperatorGroup if needed
- Creates a Subscription to install the operator
- Verifies the installation by checking the operator's CSV (ClusterServiceVersion) status
- Provides detailed feedback on the installation progress

The command is designed to work with operators from the OperatorHub catalog, including Red Hat certified operators, community operators, and custom catalog sources.

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - `$1`: Operator name (required) - The name of the operator to install (e.g., "openshift-cert-manager-operator")
   - `$2`: Namespace (optional) - Target namespace for the operator. If not provided, defaults to `{operator-name}-operator` (e.g., "cert-manager-operator")
   - `$3`: Channel (optional) - Subscription channel. If not provided, discovers the default channel from the operator's PackageManifest
   - `$4`: Source (optional) - CatalogSource name. Defaults to "redhat-operators" for Red Hat operators
   - `$5+`: Flags (optional):
     - `--approval=Automatic|Manual`: InstallPlan approval mode (default: Automatic)
     - Automatic: Operator upgrades are automatically installed
     - Manual: Operator upgrades require manual approval via `/olm:approve` or `oc patch`

2. **Prerequisites Check**:
   - Verify `oc` CLI is installed: `which oc`
   - Verify cluster access: `oc whoami`
   - Check if user has cluster-admin or sufficient privileges
   - If not installed or not authenticated, provide clear instructions

3. **Discover Operator Metadata** (if channel or source not provided):
   - Search for the operator in available catalogs:
     ```bash
     oc get packagemanifests -n openshift-marketplace | grep {operator-name}
     ```
   - Get the PackageManifest details:
     ```bash
     oc get packagemanifest {operator-name} -n openshift-marketplace -o json
     ```
   - Extract:
     - Default channel: `.status.defaultChannel`
     - CatalogSource: `.status.catalogSource`
     - CatalogSourceNamespace: `.status.catalogSourceNamespace`
   - If operator not found, provide error with list of available operators

4. **Create Namespace**:
   - Check if namespace exists: `oc get namespace {namespace} --ignore-not-found`
   - If not exists, create it:
     ```bash
     oc create namespace {namespace}
     ```
   - If exists, inform user and continue

5. **Create OperatorGroup**:
   - Check if OperatorGroup exists in the namespace:
     ```bash
     oc get operatorgroup -n {namespace} --ignore-not-found
     ```
   - If no OperatorGroup exists, create one:
     ```yaml
     apiVersion: operators.coreos.com/v1
     kind: OperatorGroup
     metadata:
       name: {namespace}-operatorgroup
       namespace: {namespace}
     spec:
       targetNamespaces:
       - {namespace}
     ```
   - Save to temporary file and apply:
     ```bash
     oc apply -f /tmp/operatorgroup-{operator-name}.yaml
     ```
   - If OperatorGroup already exists, inform user and continue

6. **Create Subscription**:
   - Parse approval mode from flags (default: Automatic)
   - Create Subscription manifest:
     ```yaml
     apiVersion: operators.coreos.com/v1alpha1
     kind: Subscription
     metadata:
       name: {operator-name}
       namespace: {namespace}
     spec:
       channel: {channel}
       name: {operator-name}
       source: {source}
       sourceNamespace: openshift-marketplace
       installPlanApproval: {Automatic|Manual}
     ```
   - Save to temporary file and apply:
     ```bash
     oc apply -f /tmp/subscription-{operator-name}.yaml
     ```
   - Display the created subscription details
   - If approval mode is Manual, display informational message:
     ```
     ℹ️  InstallPlan approval set to Manual
     You will need to manually approve InstallPlans for this operator.
     Use: /olm:approve {operator-name} {namespace}
     
     Reference: https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-approving-operator-upgrades_olm-updating-operators
     ```

7. **Verify Installation**:
   - Wait for InstallPlan to be created:
     ```bash
     oc get installplan -n {namespace} -l operators.coreos.com/operator={operator-name}
     ```
   - If approval mode is Manual, check if InstallPlan needs approval:
     ```bash
     oc get installplan -n {namespace} -o json | jq '.items[] | select(.spec.approved==false)'
     ```
   - If Manual and not approved, display message:
     ```
     ⏸️  InstallPlan created but requires manual approval
     
     InstallPlan: {installplan-name}
     To approve: /olm:approve {operator-name} {namespace}
     Or manually: oc patch installplan {installplan-name} -n {namespace} \
                    --type merge --patch '{"spec":{"approved":true}}'
     
     Waiting for approval...
     ```
   - Wait for CSV to be created and reach "Succeeded" phase:
     ```bash
     oc get csv -n {namespace} -w
     ```
   - Use a timeout of 5 minutes for the installation to complete (10 minutes if Manual approval)
   - Poll every 10 seconds to check CSV status
   - Display progress updates to the user

8. **Display Results**:
   - Show the installed operator's CSV name and version
   - Show the operator deployment status:
     ```bash
     oc get deployments -n {namespace}
     ```
   - List any pods created by the operator:
     ```bash
     oc get pods -n {namespace}
     ```
   - Display success message with next steps or usage instructions

9. **Cleanup Temporary Files**:
   - Remove temporary YAML files created during installation:
     ```bash
     rm -f /tmp/operatorgroup-{operator-name}.yaml /tmp/subscription-{operator-name}.yaml
     ```

## Return Value
- **Success**: Operator installed successfully with details about the CSV, deployments, and pods
- **Error**: Installation failed with specific error message and troubleshooting suggestions
- **Format**: Structured output showing:
  - Namespace created/used
  - OperatorGroup status
  - Subscription created
  - CSV status and version
  - Deployment and pod status

## Examples

1. **Install cert-manager-operator with defaults**:
   ```
   /olm:install openshift-cert-manager-operator
   ```
   This will:
   - Create namespace `cert-manager-operator`
   - Discover default channel from PackageManifest
   - Use `redhat-operators` catalog source
   - Install the operator

2. **Install cert-manager-operator with custom namespace**:
   ```
   /olm:install openshift-cert-manager-operator my-cert-manager
   ```
   This will install the operator in the `my-cert-manager` namespace.

3. **Install with specific channel**:
   ```
   /olm:install openshift-cert-manager-operator cert-manager-operator stable-v1
   ```
   This will install from the `stable-v1` channel.

4. **Install from community catalog**:
   ```
   /olm:install prometheus community-operators stable community-operators
   ```
   This will install Prometheus from the community-operators catalog.

5. **Install Red Hat Advanced Cluster Security**:
   ```
   /olm:install rhacs-operator rhacs-operator stable
   ```

6. **Install with manual approval mode**:
   ```
   /olm:install openshift-cert-manager-operator cert-manager-operator stable-v1 redhat-operators --approval=Manual
   ```
   This will install the operator but require manual approval for all upgrades.

7. **Install with all parameters specified**:
   ```
   /olm:install external-secrets-operator eso-operator stable-v0.10 redhat-operators --approval=Automatic
   ```

## Arguments
- **$1** (operator-name): The name of the operator to install (required)
  - Example: "openshift-cert-manager-operator"
  - Must match the name in the operator's PackageManifest
- **$2** (namespace): Target namespace for the operator installation (optional)
  - Default: `{operator-name}` (operator name without "openshift-" prefix if present)
  - Example: "cert-manager-operator"
- **$3** (channel): Subscription channel (optional)
  - Default: Auto-discovered from PackageManifest's default channel
  - Example: "stable-v1", "tech-preview", "stable"
- **$4** (source): CatalogSource name (optional)
  - Default: "redhat-operators"
  - Other options: "certified-operators", "community-operators", "redhat-marketplace"
- **$5+** (flags): Optional flags
  - `--approval=Automatic|Manual`: InstallPlan approval mode
    - **Automatic** (default): Operator upgrades are automatically installed without user intervention
    - **Manual**: Operator upgrades require explicit approval. Useful for:
      - Production environments requiring change control
      - Testing upgrades before applying
      - Preventing unexpected operator updates
    - Reference: https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/operators/administrator-tasks#olm-approving-operator-upgrades_olm-updating-operators

## Notes

- **Automatic Channel Discovery**: If no channel is specified, the command automatically discovers and uses the operator's default channel from its PackageManifest
- **Namespace Convention**: By default, operators are installed in a namespace following the pattern `{operator-name}-operator`
- **OperatorGroup Scope**: The created OperatorGroup targets only the installation namespace for better isolation
- **InstallPlan Approval**: Set to "Automatic" by default for seamless installation. Can be changed to "Manual" using `--approval=Manual` flag
- **Manual Approval Mode**: When using `--approval=Manual`:
  - Initial installation may require manual approval of the InstallPlan
  - All future upgrades will require explicit approval via `/olm:approve` command
  - Provides better control over operator updates in production environments
- **Verification Timeout**: The command waits up to 5 minutes for the operator to install successfully (10 minutes for manual approval mode)
- **Cleanup**: Temporary YAML files are automatically removed after installation

## Troubleshooting

- **Operator not found**: Run `oc get packagemanifests -n openshift-marketplace` to see available operators
- **Permission denied**: Ensure you have cluster-admin privileges or the necessary RBAC permissions
- **Installation timeout**: Check the InstallPlan and CSV status manually:
  ```bash
  oc get installplan -n {namespace}
  oc get csv -n {namespace}
  oc describe csv -n {namespace}
  ```
- **Operator pod not starting**: Check pod logs:
  ```bash
  oc logs -n {namespace} deployment/{operator-deployment}
  ```

