---
description: Clean up DRA test resources and optionally uninstall drivers
argument-hint: "<kubeconfig-path> [options]"
---

## Name
dra-ocp-validator:cleanup

## Synopsis
```
/dra-ocp-validator:cleanup <kubeconfig-path> [options]
```

## Description
The `dra-ocp-validator:cleanup` command performs complete cleanup of DRA resources from an OpenShift cluster, auto-detecting and removing the installed driver type (NVIDIA or example).

**Default behavior** (no flags):
- Deletes all test namespaces (`dra-*-test`)
- Auto-detects driver type (NVIDIA or example)
- Removes DRA driver (Helm release + namespace)
- Removes GPU operator (if present)
- Preserves NFD (foundational cluster infrastructure)

**Selective preservation flags**:
- `--keep-driver`: Preserve DRA driver installation
- `--keep-operator`: Preserve GPU operator installation
- Both can be combined to clean only test namespaces

This is useful for:
- Complete teardown after DRA testing/validation
- Freeing cluster resources
- Resetting cluster to clean state
- Partial cleanup when preserving infrastructure components

## Implementation

This command performs comprehensive cleanup of DRA resources and drivers from an OpenShift cluster. It auto-detects the installed driver type and removes components based on flags.

### Steps

1. **Parse and Validate Arguments**:
   - Extract kubeconfig path from first positional argument (required)
   - Parse optional flags: `--keep-driver`, `--keep-operator`, `--force`
   - Expand tilde (`~`) to `$HOME` in kubeconfig path
   - Verify kubeconfig file exists

2. **Execute Cleanup Script**:
   
   Use the Bash tool to run the plugin's cleanup script:
   
   ```bash
   PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
   SCRIPT="${PLUGIN_ROOT}/tools/cleanup-dra.sh"
   
   # Pass all arguments to cleanup script
   ${SCRIPT} "$@"
   ```
   
   The cleanup script performs ordered resource removal:
   
   a. **Driver Type Detection**:
      - Check for NVIDIA DRA driver Helm release
      - Check for dra-example-driver Helm release
      - Determine which driver is installed (if any)
   
   b. **Test Namespace Cleanup**:
      - List all namespaces matching `dra-*-test` pattern
      - Delete each test namespace:
        - Remove ResourceClaims first (to trigger cleanup handlers)
        - Delete Pods using claims
        - Delete namespace (waits for finalizers)
      - Display progress for each namespace
   
   c. **DRA Driver Removal** (unless `--keep-driver`):
      - Confirm destructive operation (unless `--force`)
      - For NVIDIA driver:
        - Delete Helm release: `helm uninstall nvidia-dra-driver -n nvidia-dra-driver`
        - Delete namespace: `nvidia-dra-driver`
        - Wait for resources to be removed
      - For example driver:
        - Delete Helm release: `helm uninstall dra-example-driver -n dra-example-driver`
        - Delete namespace: `dra-example-driver`
      - Verify DeviceClass and ResourceSlice resources are removed
   
   d. **GPU Operator Removal** (unless `--keep-operator`):
      - Confirm destructive operation (unless `--force`)
      - Delete GPU operator Helm release
      - Delete GPU operator namespace
      - Wait for node-level resources to be cleaned up
      - Note: This step only runs for NVIDIA driver cleanup
   
   e. **NFD Preservation**:
      - NFD is intentionally preserved (foundational infrastructure)
      - Script displays message: "Preserving NFD (foundational infrastructure)"
   
   f. **Verification**:
      - Check that DeviceClass resources are gone
      - Check that ResourceSlice resources are gone
      - Check that test namespaces are removed
      - Display final cleanup status

3. **Handle User Confirmations**:
   
   The cleanup script prompts for confirmation before destructive operations (unless `--force`):
   - "This will uninstall <driver-name> driver. Continue? (y/N)"
   - "This will uninstall GPU operator. Continue? (y/N)"
   
   When running via Claude Code:
   - If `--force` is NOT specified, the script will wait for user input
   - Claude should inform the user that confirmation is needed
   - User must respond in terminal or command should be re-run with `--force`
   
   **Recommendation**: Always suggest adding `--force` flag when calling cleanup via automation.

4. **Monitor Progress**:
   
   The script outputs progress messages during cleanup:
   - Which resources are being deleted
   - Helm release deletion status
   - Namespace deletion progress (may take 30-60s for finalizers)
   - Verification results
   
   Present these updates to the user.

5. **Handle Errors**:
   
   Cleanup can fail at various stages:
   - Namespace stuck in Terminating (finalizer issues)
   - Helm release deletion timeout
   - ResourceClaim finalizers blocking deletion
   
   If errors occur:
   - Display error message from script
   - Show which resources failed to delete
   - Suggest manual cleanup commands
   - Note: Script continues with remaining cleanup even if some steps fail

6. **Report Completion**:
   
   When cleanup completes, the script outputs:
   - Summary of what was removed
   - What was preserved (NFD, optionally driver/operator)
   - Verification of resource removal
   - Cluster is ready for fresh DRA installation
   
   Present this summary to the user.

## Arguments

### Required
- `kubeconfig-path` - Path to cluster kubeconfig file

### Optional
- `--keep-driver` - Preserve DRA driver installation (default: remove)
- `--keep-operator` - Preserve GPU operator installation (default: remove)
- `--force` - Skip confirmation prompts for destructive operations

## Return Value
- **Success**: Resources cleaned up successfully
- **Failure**: Cleanup error with diagnostic information

## Examples

### Example 1: Full cleanup (default)
```
/dra-ocp-validator:cleanup ~/kubeconfig
```

**Output:**
```
⚠ WARNING: This will uninstall nvidia driver. Continue? (y/N): y

Deleting test namespaces...
  ✓ dra-podresources-test deleted
  ✓ dra-prioritized-test deleted

Detected: NVIDIA DRA driver
Uninstalling NVIDIA DRA driver...
  Cleaning up SCC permissions...
  ✓ Helm release removed
  ✓ Namespace deletion initiated

Detected: NVIDIA GPU Operator
Uninstalling NVIDIA GPU Operator...
  ✓ ClusterPolicy deleted
  ✓ Subscription deleted
  ✓ CSV deleted
  ✓ Namespace deletion initiated

Cleanup complete!
```

### Example 2: Clean test namespaces only
```
/dra-ocp-validator:cleanup ~/kubeconfig --keep-driver --keep-operator
```

**Output:**
```
Deleting test namespaces...
  ✓ dra-podresources-test deleted
  ✓ dra-prioritized-test deleted

Driver installation preserved.
GPU operator preserved.

Cleanup complete!
```

### Example 3: Non-interactive full cleanup
```
/dra-ocp-validator:cleanup ~/kubeconfig --force
```

**Output:**
```
Deleting test namespaces... ✓
Uninstalling NVIDIA DRA driver... ✓
Uninstalling NVIDIA GPU Operator... ✓

Cleanup complete!
```

### Example 4: Keep driver, remove operator
```
/dra-ocp-validator:cleanup ~/kubeconfig --keep-driver
```

**Output:**
```
Deleting test namespaces... ✓
Driver preserved.
Uninstalling GPU operator... ✓

Cleanup complete!
```

## Safety Features

### Confirmation Prompts
Destructive operations require confirmation unless `--force` is specified:
- Driver removal: Confirms before uninstalling DRA driver
- Operator removal: Confirms before uninstalling GPU operator

### What's Preserved
- **NFD** - Foundational cluster infrastructure (may be used by other components)
- **FeatureGate settings** - Cluster configuration unchanged
- **Node labels** - GPU/hardware labels remain (until node reboot)

### What's Removed
**Default (no flags) - Full cleanup:**
- Test namespaces: `dra-*-test`
- Test pods, ResourceClaims, ResourceClaimTemplates
- DRA driver (auto-detected: NVIDIA or example)
- GPU operator (if present)
- DeviceClasses and ResourceSlices
- SCC permissions for driver

**With `--keep-driver`:**
- Test namespaces removed
- Driver and operator preserved

**With `--keep-operator`:**
- Test namespaces and driver removed
- GPU operator preserved

## Impact Analysis

### Full Cleanup (default)
- **Downtime**: All GPU and DRA functionality unavailable
- **Remaining resources**: NFD only (foundational cluster infrastructure)
- **Can re-test**: After running `/dra-ocp-validator:setup`
- **Cluster state**: DRA/GPU stack removed, NFD preserved

### Partial Cleanup (with --keep-driver/--keep-operator)
- **Downtime**: Test workloads only
- **Remaining resources**: As specified by keep flags (plus NFD always)
- **Can re-test**: Immediately (if driver kept) or after setup
- **Cluster state**: Infrastructure intact

## Notes
- Cleanup requires cluster-admin privileges
- Test namespaces are detected by `dra-*-test` pattern
- Helm releases are uninstalled cleanly (no orphaned resources)
- Namespace deletion waits for finalizers (may take 1-2 minutes)
- If cleanup fails partway, it's safe to re-run
- GPU workloads using DRA will fail if driver is removed
- Removing GPU operator affects all GPU functionality (not just DRA)
- **NFD is never removed** - it's foundational cluster infrastructure that may be used by other operators

## Troubleshooting

### Namespace stuck in Terminating
```
ERROR: Namespace dra-partitionable-test stuck in Terminating
```
**Solution:** Check for finalizers:
```bash
oc get namespace dra-partitionable-test -o json | jq '.spec.finalizers'
oc patch namespace dra-partitionable-test -p '{"spec":{"finalizers":[]}}' --type=merge
```

### Helm release not found
```
WARNING: Release 'nvidia-dra-driver' not found
```
**Solution:** Normal if driver was installed manually (not via Helm). Delete namespace directly:
```bash
oc delete namespace nvidia-dra-driver
```

### Resources still in use
```
ERROR: Cannot delete namespace - pods still running
```
**Solution:** Force delete pods first:
```bash
oc delete pods --all -n dra-partitionable-test --grace-period=0 --force
```

## See Also
- `/dra-ocp-validator:validate` - Full validation (creates test resources)
- `/dra-ocp-validator:setup` - Install DRA stack
- `/dra-ocp-validator:test` - Run tests (creates test namespaces)
