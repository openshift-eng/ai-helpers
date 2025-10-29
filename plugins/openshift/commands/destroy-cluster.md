---
description: Destroy an OpenShift cluster created by create-cluster command
argument-hint: "[install-dir]"
---

## Name
openshift:destroy-cluster

## Synopsis
```
/openshift:destroy-cluster [install-dir]
```

## Description

The `destroy-cluster` command safely destroys an OpenShift Container Platform (OCP) cluster that was previously created using the `/openshift:create-cluster` command. It locates the appropriate installer binary, verifies the cluster information, and performs cleanup of all cloud resources.

This command is useful for:
- Cleaning up development/test clusters after testing
- Removing failed cluster installations
- Freeing up cloud resources and quotas

**⚠️ WARNING**: This operation is **irreversible** and will permanently delete:
- All cluster resources (VMs, load balancers, storage, etc.)
- All data stored in the cluster
- All configuration and credentials
- DNS records (if managed by the installer)

## Prerequisites

Before using this command, ensure you have:

1. **Installation directory** from the original cluster creation
   - Contains the cluster metadata and terraform state
   - Located at `{cluster-name}-install-{timestamp}` by default

2. **OpenShift installer binary** that matches the cluster version
   - Should be available at `~/.openshift-installers/openshift-install-{version}`
   - Same version used to create the cluster

3. **Cloud Provider Credentials** still configured and valid
   - Same credentials used during cluster creation
   - Must have permissions to delete resources

4. **Network connectivity** to the cloud provider
   - Required to communicate with cloud APIs

## Arguments

- **install-dir** (optional): Path to the cluster installation directory
  - Default: Interactive prompt to select from available installation directories
  - Must contain cluster metadata files (metadata.json, terraform.tfstate, etc.)
  - Example: `./my-cluster-install-20251028-120000`

## Implementation

The command performs the following steps:

### 1. Locate Installation Directory

If `install-dir` is not provided:
- Search for installation directories in the current directory
- Look for directories matching pattern `*-install-*` or containing `.openshift_install_state.json`
- Present a list of found directories to the user for selection
- Allow user to manually enter a path if directory not found

If `install-dir` is provided:
- Validate the directory exists
- Verify it contains cluster metadata files

### 2. Extract Cluster Information

Read cluster details from the installation directory:
```bash
# Read cluster metadata
if [ -f "$INSTALL_DIR/metadata.json" ]; then
    CLUSTER_NAME=$(jq -r '.clusterName' "$INSTALL_DIR/metadata.json")
    INFRA_ID=$(jq -r '.infraID' "$INSTALL_DIR/metadata.json")
    PLATFORM=$(jq -r '.platform' "$INSTALL_DIR/metadata.json")
fi

# Try to extract version from cluster-info or log files
VERSION=$(grep -oE 'openshift-install.*v[0-9]+\.[0-9]+\.[0-9]+' "$INSTALL_DIR/.openshift_install.log" | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+[^"]*' | head -1)
```

### 3. Display Cluster Information and Confirm

Show the user what will be destroyed:
```
Cluster Information:
  Name: ${CLUSTER_NAME}
  Infrastructure ID: ${INFRA_ID}
  Platform: ${PLATFORM}
  Installation Directory: ${INSTALL_DIR}
  Version: ${VERSION}

⚠️  WARNING: This will permanently destroy the cluster and all its resources!

This action will delete:
  - All cluster VMs and compute resources
  - Load balancers and networking resources
  - Storage volumes and persistent data
  - DNS records
  - All cluster configuration

Are you sure you want to destroy this cluster? (yes/no):
```

**Important**: Require the user to type "yes" (not just "y") to confirm destruction.

### 4. Locate the Correct Installer

Find the installer binary that matches the cluster version:
```bash
INSTALLER_DIR="${HOME}/.openshift-installers"
INSTALLER_PATH="$INSTALLER_DIR/openshift-install-${VERSION}"

# Check if the version-specific installer exists
if [ ! -f "$INSTALLER_PATH" ]; then
    echo "Warning: Installer for version ${VERSION} not found at ${INSTALLER_PATH}"
    echo "Searching for alternative installers..."

    # Look for any installer in the installers directory
    AVAILABLE_INSTALLERS=$(find "$INSTALLER_DIR" -name "openshift-install-*" -type f 2>/dev/null)

    if [ -n "$AVAILABLE_INSTALLERS" ]; then
        echo "Found installers:"
        echo "$AVAILABLE_INSTALLERS"
        echo ""
        echo "You may use a different version installer, but this may cause issues."
        echo "Would you like to:"
        echo "  1. Use an available installer from the list above"
        echo "  2. Extract the correct installer from the release image"
        echo "  3. Cancel the operation"
    else
        echo "No installers found. Would you like to extract the installer? (yes/no):"
    fi
fi

# Verify installer works
"$INSTALLER_PATH" version
```

### 5. Backup Important Files (Optional)

Offer to backup key files before destruction:
```
Would you like to backup cluster information before destroying? (yes/no):
```

If yes, create a backup:
```bash
BACKUP_DIR="${INSTALL_DIR}-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup key files
cp "$INSTALL_DIR/metadata.json" "$BACKUP_DIR/" 2>/dev/null
cp "$INSTALL_DIR/auth/kubeconfig" "$BACKUP_DIR/" 2>/dev/null
cp "$INSTALL_DIR/auth/kubeadmin-password" "$BACKUP_DIR/" 2>/dev/null
cp "$INSTALL_DIR/.openshift_install.log" "$BACKUP_DIR/" 2>/dev/null
cp "$INSTALL_DIR/install-config.yaml.backup" "$BACKUP_DIR/" 2>/dev/null

echo "Backup created at: $BACKUP_DIR"
```

### 6. Run Cluster Destroy

Execute the destroy command:
```bash
cd "$INSTALL_DIR"

echo "Starting cluster destruction..."
echo "This may take 10-15 minutes..."

"$INSTALLER_PATH" destroy cluster --dir=. --log-level=debug

DESTROY_EXIT_CODE=$?
```

Monitor the destruction progress and display status updates.

### 7. Verify Cleanup

After the destroy command completes:

1. **Check exit code**:
   ```bash
   if [ $DESTROY_EXIT_CODE -eq 0 ]; then
       echo "✅ Cluster destroyed successfully"
   else
       echo "❌ Cluster destruction failed with exit code: $DESTROY_EXIT_CODE"
       echo "Check logs at: $INSTALL_DIR/.openshift_install.log"
   fi
   ```

2. **Verify cloud resources** (platform-specific):
   - AWS: Check for lingering resources with tag `kubernetes.io/cluster/${INFRA_ID}`
   - Azure: Verify resource group deletion
   - GCP: Check project for remaining resources

3. **List any remaining resources**:
   ```
   If any resources remain, provide commands to manually clean them up.
   ```

### 8. Cleanup Installation Directory (Optional)

Ask the user if they want to remove the installation directory:
```
The cluster has been destroyed. Would you like to delete the installation directory? (yes/no):
  Directory: $INSTALL_DIR
  Size: $(du -sh "$INSTALL_DIR" | cut -f1)
```

If yes:
```bash
rm -rf "$INSTALL_DIR"
echo "Installation directory removed"
```

If no:
```bash
echo "Installation directory preserved at: $INSTALL_DIR"
echo "You can manually remove it later with: rm -rf $INSTALL_DIR"
```

### 9. Display Summary

Show final summary:
```
Cluster Destruction Summary:
  Cluster Name: ${CLUSTER_NAME}
  Status: Successfully destroyed
  Platform: ${PLATFORM}
  Duration: ${DURATION}
  Backup: ${BACKUP_DIR} (if created)

Next steps:
  - Verify your cloud console for any lingering resources
  - Check your cloud billing to ensure resources are no longer incurring charges
  - Remove installation directory if not already deleted: ${INSTALL_DIR}
```

## Error Handling

If destruction fails, the command should:

1. **Capture error logs** from `.openshift_install.log`
2. **Identify the failure point**:
   - Timeout waiting for resource deletion
   - Permission errors
   - API rate limiting
   - Network connectivity issues
   - Resources locked or in use
3. **Provide recovery options**:
   - Retry the destroy operation
   - Manual cleanup instructions for specific resources
   - Contact support if critical errors occur

Common failure scenarios:

**Timeout errors**:
```bash
# Some resources may take longer to delete
# Retry the destroy command:
"$INSTALLER_PATH" destroy cluster --dir="$INSTALL_DIR"
```

**Permission errors**:
```
Error: Cloud credentials may have expired or lack permissions
Solution:
  1. Verify cloud credentials are still valid
  2. Check IAM permissions for resource deletion
  3. Re-run the destroy command after fixing credentials
```

**Partial destruction**:
```
Warning: Some resources could not be deleted automatically.

Remaining resources:
  - Load balancer: ${LB_NAME}
  - Security group: ${SG_NAME}
  - S3 bucket: ${BUCKET_NAME}

Manual cleanup commands:
  [Platform-specific commands to delete remaining resources]
```

## Examples

### Example 1: Destroy cluster with interactive directory selection
```
/openshift:destroy-cluster
```
The command will search for installation directories and prompt you to select one.

### Example 2: Destroy cluster with specific directory
```
/openshift:destroy-cluster ./my-cluster-install-20251028-120000
```

### Example 3: Destroy cluster with full path
```
/openshift:destroy-cluster /home/user/clusters/test-cluster-install-20251028-120000
```

## Common Issues

1. **Installation directory not found**:
   - Ensure you're in the correct directory
   - Provide the full path to the installation directory
   - Check if the directory was moved or renamed

2. **Installer binary not found**:
   - The command will help you extract the correct installer
   - Alternatively, manually place the installer in `~/.openshift-installers/`

3. **Cloud credentials expired**:
   - Refresh your cloud credentials
   - Re-authenticate with the cloud provider CLI
   - Re-run the destroy command

4. **Resources already deleted manually**:
   - The destroy command may fail if resources were manually deleted
   - Check the logs and manually clean up any remaining resources
   - Remove the installation directory manually

5. **Destroy hangs or times out**:
   - Some resources may take longer to delete (especially load balancers)
   - Wait for the operation to complete (can take 15-30 minutes)
   - If truly stuck, cancel and retry
   - Check cloud console for resource status

## Safety Features

This command includes several safety measures:

1. **Confirmation required**: Must type "yes" to proceed
2. **Cluster information displayed**: Shows what will be destroyed before proceeding
3. **Backup option**: Offers to backup important files
4. **Validation checks**: Verifies installation directory and metadata
5. **Detailed logging**: All operations logged for troubleshooting
6. **Error recovery**: Provides manual cleanup instructions if automated cleanup fails

## Return Value

- **Success**: Returns 0 and displays destruction summary
- **Failure**: Returns non-zero and displays error diagnostics with recovery instructions

## See Also

- `/openshift:create-cluster` - Create a new OCP cluster
- OpenShift Documentation: https://docs.openshift.com/container-platform/latest/installing/
- Platform-specific cleanup guides

## Arguments:

- **$1** (install-dir): Path to the cluster installation directory created by create-cluster (optional, interactive if not provided)
