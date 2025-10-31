---
description: Extract OpenShift installer from release image and create an OCP cluster
argument-hint: "[release-image] [platform] [options]"
---

## Name
openshift:create-cluster

## Synopsis
```
/openshift:create-cluster [release-image] [platform] [options]
```

## Description

The `create-cluster` command automates the process of extracting the OpenShift installer from a release image (if not already present) and creating a new OpenShift Container Platform (OCP) cluster. It handles installer extraction from OCP release images, configuration preparation, and cluster creation in a streamlined workflow.

This command is useful for:
- Setting up development/test clusters quickly

## ⚠️ When to Use This Tool

**IMPORTANT**: This is a last resort tool for advanced use cases. For most development workflows, you should use one of these better alternatives:

### Recommended Alternatives

1. **Cluster Bot**: Request ephemeral test clusters without managing infrastructure
   - No cloud credentials needed
   - Supports dependent PR testing
   - Automatically cleaned up

2. **Gangway**

3. **Multi-PR Testing in CI**: Test multiple dependent PRs together using `/test-with` commands

### When to Use create-cluster

Only use this command when:
- You need full control over cluster configuration
- You're testing installer changes that aren't suitable for CI
- You need a long-lived development cluster on your own cloud account
- The alternatives don't meet your specific requirements

**Note**: This command requires significant setup (cloud credentials, pull secrets, DNS configuration, understanding of OCP versions). If you're new to OpenShift development, start with Cluster Bot or Gangway instead.

## Prerequisites

Before using this command, ensure you have:

1. **OpenShift CLI (`oc`)**: Required to extract the installer from the release image
   - Install from: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/
   - Or use your package manager: `brew install openshift-cli` (macOS)
   - Verify with: `oc version`

2. **Cloud Provider Credentials** configured for your chosen platform:
   - **AWS**: `~/.aws/credentials` configured with appropriate permissions
   - **Azure**: Azure CLI authenticated (`az login`)
   - **GCP**: The command will guide you through service account setup (either using an existing service account JSON or creating a new one)
   - **vSphere**: vCenter credentials
   - **OpenStack**: clouds.yaml configured

3. **Pull Secret**: Download from [Red Hat Console](https://console.redhat.com/openshift/install/pull-secret)

4. **Domain/DNS Configuration**:
   - AWS: Route53 hosted zone
   - Other platforms: Appropriate DNS setup

## Arguments

The command accepts arguments in multiple ways:

### Positional Arguments
```
/openshift:create-cluster [release-image] [platform]
```

### Interactive Mode
If arguments are not provided, the command will interactively prompt for:
- OpenShift release image
- Platform (aws, azure, gcp, vsphere, openstack, none/baremetal)
- Cluster name
- Base domain
- Pull secret location

### Argument Details

- **release-image** (required): OpenShift release image to extract the installer from
  - Production release: `quay.io/openshift-release-dev/ocp-release:4.21.0-ec.2-x86_64`
  - CI build: `registry.ci.openshift.org/ocp/release:4.21.0-0.ci-2025-10-27-031915`
  - Stable release: `quay.io/openshift-release-dev/ocp-release:4.20.1-x86_64`
  - The command will prompt for this if not provided

- **platform** (optional): Target platform for the cluster
  - `aws`: Amazon Web Services
  - `azure`: Microsoft Azure
  - `gcp`: Google Cloud Platform
  - `vsphere`: VMware vSphere
  - `openstack`: OpenStack
  - `none`: Bare metal / platform-agnostic
  - Default: Prompts user to select

- **cluster-name** (optional): Name for the cluster
  - Default: `ocp-cluster`
  - Must be DNS-compatible

- **base-domain** (required): Base domain for the cluster
  - Example: `example.com` → Cluster API will be `api.{cluster-name}.{base-domain}`

- **pull-secret** (required): Path to pull secret file
  - User will be prompted to provide the path

- **installer-dir** (optional): Directory to store/find installer binaries
  - Default: `~/.openshift-installers`

## Implementation

The command performs the following steps:

### 1. Validate Prerequisites

Check that required tools and credentials are available:
- Verify `oc` CLI is installed and available
- Verify cloud provider credentials are configured (if applicable)
- Confirm domain/DNS requirements

If any prerequisites are missing, provide clear instructions on how to configure them.

### 2. Get Release Image from User

If not provided as an argument, **prompt the user** for the OpenShift release image:

```
Please provide the OpenShift release image:

Examples:
  - Production release: quay.io/openshift-release-dev/ocp-release:4.21.0-ec.2-x86_64
  - CI build:          registry.ci.openshift.org/ocp/release:4.21.0-0.ci-2025-10-27-031915
  - Stable release:    quay.io/openshift-release-dev/ocp-release:4.20.1-x86_64

Release image:
```

Store the user's input as `$RELEASE_IMAGE`.

**Extract version from image** for naming:
```bash
# Parse version from image tag (e.g., "4.21.0-ec.2" or "4.21.0-0.ci-2025-10-27-031915")
VERSION=$(echo "$RELEASE_IMAGE" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+[^"]*' | head -1)
```

### 3. Determine Installer Location and Extract if Needed

```bash
INSTALLER_DIR="${installer-dir:-$HOME/.openshift-installers}"
INSTALLER_PATH="$INSTALLER_DIR/openshift-install-${VERSION}"
```

**Check if installer directory exists**:
- If `$INSTALLER_DIR` does not exist:
  - **Ask user for confirmation**: "The installer directory `$INSTALLER_DIR` does not exist. Would you like to create it?"
  - If user confirms (yes): Create the directory with `mkdir -p "$INSTALLER_DIR"`
  - If user declines (no): Exit with error message suggesting an alternative path

**Check if the installer already exists** at `$INSTALLER_PATH`:
- If present: Verify it works with `"$INSTALLER_PATH" version`
  - If version matches the release image: Skip extraction
  - If different or fails: Proceed with extraction
- If not present: Proceed with extraction

**Extract installer from release image**:

1. **Verify `oc` CLI is available**:
   ```bash
   if ! command -v oc &> /dev/null; then
       echo "Error: 'oc' CLI not found. Please install the OpenShift CLI."
       exit 1
   fi
   ```

2. **Extract the installer binary**:
   ```bash
   oc adm release extract \
       --tools \
       --from="$RELEASE_IMAGE" \
       --to="$INSTALLER_DIR"
   ```

   This extracts the `openshift-install` binary and other tools from the release image.

3. **Locate and rename the extracted installer**:
   ```bash
   # The extract command creates a tar.gz with the tools
   # Find the most recently extracted openshift-install tar (compatible with both GNU and BSD find)
   INSTALLER_TAR=$(find "$INSTALLER_DIR" -name "openshift-install-*.tar.gz" -type f -exec ls -t {} + | head -1)

   # Extract from tar and rename
   cd "$INSTALLER_DIR"
   tar -xzf "$INSTALLER_TAR" openshift-install
   mv openshift-install "openshift-install-${VERSION}"
   chmod +x "openshift-install-${VERSION}"

   # Clean up the tar file
   rm "$INSTALLER_TAR"
   ```

4. **Verify the installer**:
   ```bash
   "$INSTALLER_PATH" version
   ```

   Expected output should show the version matching `$VERSION`.

### 4. Prepare Installation Directory

Create a clean installation directory:
```bash
INSTALL_DIR="${cluster-name}-install-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"
```

### 5. Collect Required Information and Generate install-config.yaml

**IMPORTANT**: Do NOT run the installer interactively. Instead, collect all required information from the user and generate the install-config.yaml programmatically.

**Step 5.1: Collect Information**

Prompt the user for the following information (if not already provided as arguments):

1. **SSH Public Key**:
   - Check for existing SSH keys: `ls -la ~/.ssh/*.pub`
   - Ask user to select from available keys or specify path
   - Default: `~/.ssh/id_rsa.pub`

2. **Platform** (if not provided as argument):
   - Ask user to select: aws, azure, gcp, vsphere, openstack, none

3. **Platform-specific details**:
   - For AWS:
     - Region (e.g., us-east-1, us-west-2)
   - For Azure:
     - Region (e.g., centralus, eastus)
     - Cloud name (e.g., AzurePublicCloud)
   - For GCP:
     - Follow the **GCP Service Account Setup** (see Step 5.2a below)
     - Project ID
     - Region (e.g., us-central1)
   - For other platforms: collect required platform-specific info

4. **Base Domain**:
   - Ask for base domain (e.g., example.com, devcluster.openshift.com)
   - Validate that domain is configured (e.g., Route53 hosted zone for AWS)

5. **Cluster Name**:
   - Ask for cluster name or use default: `ocp-cluster`
   - Validate DNS compatibility (lowercase, hyphens only)

6. **Pull Secret**:
   - **IMPORTANT**: Always ask user to provide the path to their pull secret file
   - Do NOT use default paths like `~/pull-secret.txt` or `~/Downloads/pull-secret.txt`
   - Prompt: "Please provide the path to your pull secret file (download from https://console.redhat.com/openshift/install/pull-secret):"
   - Read contents of pull secret file from the provided path

**Step 5.2a: GCP Service Account Setup** (Only for GCP platform)

If the platform is GCP, the installer requires a service account JSON file with appropriate permissions. Present the user with two options:

1. **Use an existing service account JSON file**
2. **Create a new service account**

**Ask the user**: "Do you want to use an existing service account JSON file or create a new one?"

**Option 1: Use Existing Service Account**

If the user chooses to use an existing service account:
- Prompt: "Please provide the path to your GCP service account JSON file:"
- Store the path as `$GCP_SERVICE_ACCOUNT_PATH`
- Verify the file exists and is valid JSON
- Set the environment variable:
  ```bash
  export GOOGLE_APPLICATION_CREDENTIALS="$GCP_SERVICE_ACCOUNT_PATH"
  ```

**Option 2: Create New Service Account**

If the user chooses to create a new service account:

1. **Verify gcloud CLI is installed**:
   ```bash
   if ! command -v gcloud &> /dev/null; then
       echo "Error: 'gcloud' CLI not found. Please install the Google Cloud SDK."
       echo "Visit: https://cloud.google.com/sdk/docs/install"
       exit 1
   fi
   ```

2. **Prompt for Kerberos ID**:
   - Ask: "Please provide your Kerberos ID (e.g., jsmith):"
   - Store as `$KERBEROS_ID`
   - Validate it's not empty

3. **Set service account name**:
   ```bash
   SERVICE_ACCOUNT_NAME="${KERBEROS_ID}-development"
   ```

4. **Create the service account**:
   ```bash
   echo "Creating service account: $SERVICE_ACCOUNT_NAME"
   gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" --display-name="$SERVICE_ACCOUNT_NAME"
   ```

5. **Extract service account details**:
   ```bash
   # Get service account information
   SERVICE_ACCOUNT_JSON="$(gcloud iam service-accounts list --format json | jq -r '.[] | select(.name | match("/\(env.SERVICE_ACCOUNT_NAME)@"))')"
   SERVICE_ACCOUNT_EMAIL="$(jq -r .email <<< "$SERVICE_ACCOUNT_JSON")"
   PROJECT_ID="$(jq -r .projectId <<< "$SERVICE_ACCOUNT_JSON")"

   echo "Service Account Email: $SERVICE_ACCOUNT_EMAIL"
   echo "Project ID: $PROJECT_ID"
   ```

6. **Grant required permissions**:
   ```bash
   echo "Granting IAM roles to service account..."

   while IFS= read -r ROLE_TO_ADD ; do
      echo "Adding role: $ROLE_TO_ADD"
      gcloud projects add-iam-policy-binding "$PROJECT_ID" \
         --condition="None" \
         --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
         --role="$ROLE_TO_ADD"
   done << 'END_OF_ROLES'
   roles/compute.admin
   roles/iam.securityAdmin
   roles/iam.serviceAccountAdmin
   roles/iam.serviceAccountKeyAdmin
   roles/iam.serviceAccountUser
   roles/storage.admin
   roles/dns.admin
   roles/compute.loadBalancerAdmin
   roles/iam.roleAdmin
   END_OF_ROLES

   echo "All roles granted successfully."
   ```

7. **Create and download service account key**:
   ```bash
   KEY_FILE="${HOME}/.gcp/${SERVICE_ACCOUNT_NAME}-key.json"
   mkdir -p "$(dirname "$KEY_FILE")"

   echo "Creating service account key..."
   gcloud iam service-accounts keys create "$KEY_FILE" \
      --iam-account="$SERVICE_ACCOUNT_EMAIL"

   echo "Service account key saved to: $KEY_FILE"
   ```

8. **Set environment variable**:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="$KEY_FILE"
   echo "GOOGLE_APPLICATION_CREDENTIALS set to: $KEY_FILE"
   ```

9. **Store PROJECT_ID for later use** in install-config.yaml generation.

**Step 5.2: Generate install-config.yaml**

Create the install-config.yaml file programmatically based on collected information:

```bash
# Read SSH public key
SSH_KEY=$(cat "$SSH_KEY_PATH")

# Read pull secret
PULL_SECRET=$(cat "$PULL_SECRET_PATH")

# Generate install-config.yaml
cat > install-config.yaml <<EOF
apiVersion: v1
baseDomain: ${BASE_DOMAIN}
metadata:
  name: ${CLUSTER_NAME}
compute:
- name: worker
  replicas: 3
controlPlane:
  name: master
  replicas: 3
networking:
  networkType: OVNKubernetes
  clusterNetwork:
  - cidr: 10.128.0.0/14
    hostPrefix: 23
  serviceNetwork:
  - 172.30.0.0/16
platform:
  ${PLATFORM}:
    region: ${REGION}
pullSecret: '${PULL_SECRET}'
sshKey: '${SSH_KEY}'
EOF
```

**Platform-specific configurations**:

For **AWS**:
```yaml
platform:
  aws:
    region: us-east-1
```

For **Azure**:
```yaml
platform:
  azure:
    region: centralus
    baseDomainResourceGroupName: ${RESOURCE_GROUP_NAME}
    cloudName: AzurePublicCloud
```

For **GCP**:
```yaml
platform:
  gcp:
    projectID: ${PROJECT_ID}
    region: us-central1
```

For **None/Baremetal**:
```yaml
platform:
  none: {}
```

**IMPORTANT**: Always backup install-config.yaml after creation:
```bash
cp install-config.yaml install-config.yaml.backup
```

The installer consumes this file, so the backup is essential for reference.

### 6. Create the Cluster

Run the installer:
```bash
"$INSTALLER_PATH" create cluster --dir=.
```

Monitor the installation progress. This typically takes 30-45 minutes.

### 7. Post-Installation

Once installation completes:

1. **Display kubeconfig location**:
   ```
   Kubeconfig: $INSTALL_DIR/auth/kubeconfig
   ```

2. **Display cluster credentials**:
   ```
   Console URL: https://console-openshift-console.apps.${cluster-name}.${base-domain}
   Username: kubeadmin
   Password: (from $INSTALL_DIR/auth/kubeadmin-password)
   ```

3. **Export KUBECONFIG** (offer to add to shell profile):
   ```bash
   export KUBECONFIG="$PWD/auth/kubeconfig"
   ```

4. **Verify cluster access**:
   ```bash
   oc get nodes
   oc get co  # cluster operators
   ```

5. **Save cluster information** to a summary file:
   ```
   Cluster: ${cluster-name}
   Version: ${VERSION}
   Release Image: ${RELEASE_IMAGE}
   Platform: ${platform}
   Console: https://console-openshift-console.apps.${cluster-name}.${base-domain}
   API: https://api.${cluster-name}.${base-domain}:6443
   Kubeconfig: $INSTALL_DIR/auth/kubeconfig
   Created: $(date)
   ```

### 8. Error Handling

If installation fails:

1. **Capture logs**: Installation logs are in `.openshift_install.log`
2. **Provide diagnostics**: Check common failure points:
   - Quota limits on cloud provider
   - DNS configuration issues
   - Invalid pull secret
   - Network/firewall issues
3. **Cleanup guidance**: Inform user about cleanup:
   ```bash
   "$INSTALLER_PATH" destroy cluster --dir=.
   ```

## Examples

### Example 1: Basic cluster creation (interactive)
```
/openshift:create-cluster
```
The command will prompt for release image and all necessary information.

### Example 2: Create AWS cluster with production release
```
/openshift:create-cluster quay.io/openshift-release-dev/ocp-release:4.21.0-ec.2-x86_64 aws
```

### Example 3: Create cluster with CI build
```
/openshift:create-cluster registry.ci.openshift.org/ocp/release:4.21.0-0.ci-2025-10-27-031915 gcp
```

## Cleanup

To destroy the cluster after testing:
```bash
cd $INSTALL_DIR
"$INSTALLER_PATH" destroy cluster --dir=.
```

**WARNING**: This will permanently delete all cluster resources.

## Common Issues

1. **Pull secret not found**:
   - Download from https://console.redhat.com/openshift/install/pull-secret
   - Save to a secure location of your choice
   - Provide the path when prompted during cluster creation

2. **Insufficient cloud quotas**:
   - Check cloud provider quota limits
   - Request quota increase if needed

3. **DNS issues**:
   - Ensure base domain is properly configured
   - For AWS, verify Route53 hosted zone exists

4. **SSH key not found**:
   - Generate with `ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa`

5. **Unauthorized access to release image**:
   - Error: `error: unable to read image quay.io/openshift-release-dev/ocp-v4.0-art-dev@sha256:...: unauthorized: access to the requested resource is not authorized`
   - For `quay.io/openshift-release-dev/ocp-v4.0-art-dev` you can get the pull secret from https://console.redhat.com/openshift/install/pull-secret and save it in a file and provide it here.

## Security Considerations

- **Pull secret**: Contains authentication for Red Hat registries. Keep secure.
- **kubeadmin password**: Stored in plaintext in auth directory. Rotate after cluster creation.
- **kubeconfig**: Contains cluster admin credentials. Protect appropriately.
- **Cloud credentials**: Never commit to version control.

## Return Value

- **Success**: Returns 0 and displays cluster information including kubeconfig path
- **Failure**: Returns non-zero and displays error diagnostics

## See Also

- OpenShift Documentation: https://docs.openshift.com/container-platform/latest/installing/
- OpenShift Install: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/
- Platform-specific installation guides

## Arguments:

- **$1** (release-image): OpenShift release image to extract the installer from (e.g., `quay.io/openshift-release-dev/ocp-release:4.21.0-ec.2-x86_64`)
- **$2** (platform): Target cloud platform for cluster deployment (aws, azure, gcp, vsphere, openstack, none)
