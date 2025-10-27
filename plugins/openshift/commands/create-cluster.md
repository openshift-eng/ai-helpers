---
description: Extract OpenShift installer from release image and create an OCP cluster
argument-hint: [release-image] [platform] [options]
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
- Ensuring consistent cluster creation across team members
- Automating CI/CD cluster provisioning
- Testing specific OpenShift versions

## Prerequisites

Before using this command, ensure you have:

1. **OpenShift CLI (`oc`)**: Required to extract the installer from the release image
   - Install from: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/
   - Or use your package manager: `brew install openshift-cli` (macOS)
   - Verify with: `oc version`

2. **Cloud Provider Credentials** configured for your chosen platform:
   - **AWS**: `~/.aws/credentials` configured with appropriate permissions
   - **Azure**: Azure CLI authenticated (`az login`)
   - **GCP**: Service account key configured
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

- **pull-secret** (optional): Path to pull secret file
  - Default: `~/pull-secret.txt`

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

### 5. Generate install-config.yaml

Run the installer's interactive config generation:
```bash
"$INSTALLER_PATH" create install-config --dir=.
```

This will interactively prompt for:
- SSH public key
- Platform selection
- Platform-specific details (region, instance types, etc.)
- Base domain
- Cluster name
- Pull secret

**IMPORTANT**: Always backup install-config.yaml before proceeding:
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
   - Save to `~/pull-secret.txt`

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
