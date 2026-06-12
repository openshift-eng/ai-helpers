---
description: Install DRA stack (auto-detects hardware and installs appropriate driver)
argument-hint: "<kubeconfig-path> [options]"
---

## Name
dra-ocp-validator:setup

## Synopsis
```
/dra-ocp-validator:setup <kubeconfig-path> [options]
```

## Description
The `dra-ocp-validator:setup` command installs and configures the appropriate DRA driver on an OpenShift cluster based on detected hardware, without running validation tests. This is useful when you want to:

- Prepare a cluster for manual DRA testing
- Install prerequisites before running tests at a later time
- Verify installation works before committing to full validation

**The command performs:**
1. Cluster access verification
2. NFD installation (always - required for hardware detection)
3. Hardware discovery via NFD labels
4. **Auto-select driver** based on detected hardware:
   - **NVIDIA GPUs detected** → Install GPU operator + NVIDIA DRA driver
   - **AMD GPUs detected** → Install GPU operator + AMD DRA driver  
   - **No GPUs detected** → Install dra-example-driver (software-only)
5. Driver installation (conditional based on step 4)
6. Installation verification (DeviceClasses, ResourceSlices)

After setup completes, you can run `/dra-ocp-validator:test` to execute validation tests.

## Implementation

This command executes a comprehensive setup script that installs the DRA stack on an OpenShift cluster. The setup is a long-running operation (5-10 minutes) that installs operators and waits for them to be ready.

### Steps

1. **Parse and Validate Arguments**:
   - Extract kubeconfig path from first positional argument (required)
   - Parse optional flags: `--driver`, `--enable-dynamic-mig`, `--driver-version`
   - Expand tilde (`~`) to `$HOME` in kubeconfig path
   - Verify kubeconfig file exists

2. **Execute Setup Script**:
   
   Use the Bash tool to run the plugin's setup script, passing all arguments:
   
   ```bash
   PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
   SCRIPT="${PLUGIN_ROOT}/tools/setup-dra.sh"
   
   # Pass all arguments to setup script
   ${SCRIPT} "$@"
   ```
   
   The setup script performs these steps automatically:
   
   a. **Cluster Validation**:
      - Verify cluster connectivity
      - Check cluster is OpenShift 4.21+ (K8s 1.34+)
      - Verify cluster-admin access
   
   b. **NFD Installation** (always required):
      - Install Node Feature Discovery operator if not present
      - Wait for NFD DaemonSet to be ready on all nodes
      - Verify nodes are labeled with hardware information
   
   c. **Hardware Detection**:
      - Query NFD labels to detect GPU vendor (NVIDIA, AMD, Intel)
      - Auto-select driver based on detection (unless `--driver` flag provided)
      - If no GPUs found: default to `dra-example-driver`
   
   d. **Driver Installation**:
      - **NVIDIA**: Install GPU Operator + NVIDIA DRA Driver via Helm
        - Configure `DYNAMIC_MIG=true` if `--enable-dynamic-mig` flag set
        - Use specified version or latest stable
      - **Example**: Install dra-example-driver via Helm
        - Configure `gpuPartitions=4` if `--enable-dynamic-mig` flag set
   
   e. **Feature Gate Enablement** (if `--enable-dynamic-mig`):
      - Patch OpenShift FeatureGate to enable `DRAPartitionableDevices`
      - Uses `customNoUpgrade` field for alpha feature gates
      - Wait for feature gate to be applied
   
   f. **Installation Verification**:
      - Wait for all driver pods to be Running
      - Verify DeviceClass resources are created
      - Verify ResourceSlice resources are created
      - Display summary of installed resources

3. **Monitor Progress**:
   
   The script outputs progress messages during installation. Present these to the user in real-time to show:
   - Which step is currently executing
   - When operators/pods are being waited on
   - When installation completes successfully

4. **Handle Errors**:
   
   If setup fails, the script will:
   - Display specific error message (e.g., "NFD pods not ready", "Helm install failed")
   - Show relevant diagnostic information (pod logs, resource status)
   - Exit with non-zero status
   
   Present error details to the user and suggest next steps (e.g., check cluster logs, verify prerequisites)

5. **Report Completion**:
   
   When setup completes successfully, the script outputs:
   - Summary of what was installed
   - Verification of DRA resources (DeviceClasses, ResourceSlices)
   - Suggested next command: `/dra-ocp-validator:test`
   
   Present this summary to the user.

## Arguments

### Required
- `kubeconfig-path` - Path to cluster kubeconfig file

### Optional
- `--driver <nvidia|amd|example>` - Driver to install (default: auto-detect based on hardware)

- `--enable-dynamic-mig` - **Enable DRAPartitionableDevices testing** (does TWO things):
  1. **OCP cluster**: Enables DRAPartitionableDevices feature gate via CustomNoUpgrade
  2. **Driver**: Configures driver with partition support
     - NVIDIA: Sets DYNAMIC_MIG=true
     - Example: Sets gpuPartitions=4
  
  **IMPORTANT**: Only use this flag if you plan to test partitionable devices. Without it:
  - OCP feature gate remains disabled
  - Driver installed without partition support  
  - Partitionable device tests will be skipped
  
- `--driver-version <version>` - Specific driver version (default: latest/recommended)

## Return Value
- **Success**: Installation completed, DRA driver ready
- **Failure**: Installation error with diagnostic information

## Examples

### Example 1: Setup NVIDIA stack with MIG support
```
/dra-ocp-validator:setup ~/clusters/gb300/kubeconfig --driver nvidia --enable-dynamic-mig
```

**Output:**
```
✓ Cluster accessible (OCP 4.21.16, K8s 1.34.7)
✓ Hardware detected: 4x NVIDIA GB300
✓ Installing NFD...
✓ Installing NVIDIA GPU Operator...
✓ Installing NVIDIA DRA Driver (DYNAMIC_MIG=true)...
✓ DeviceClass created: mig.nvidia.com
✓ ResourceSlices created: 4
✓ MIG devices found: 16

Setup complete! Ready for testing.
Run: /dra-ocp-validator:test ~/clusters/gb300/kubeconfig
```

### Example 2: Setup without physical GPUs
```
/dra-ocp-validator:setup ~/clusters/test/kubeconfig --driver example
```

**Output:**
```
✓ Cluster accessible (OCP 4.21.16, K8s 1.34.7)
⚠ No GPUs detected - using dra-example-driver
✓ Installing dra-example-driver...
✓ DeviceClass created: example.com
✓ ResourceSlices created: 2

Setup complete! Ready for testing.
```

### Example 3: Setup with specific driver version
```
/dra-ocp-validator:setup ~/kubeconfig --driver nvidia --driver-version 580.126.20 --enable-dynamic-mig
```

## Notes
- Setup requires cluster-admin privileges
- Installation can take 5-10 minutes depending on cluster size and image pull times
- NFD is always installed (or verified if already present) - it's required for hardware detection
- NFD installation does NOT require cluster restart - it uses DaemonSets that roll out automatically
- GPU operator and DRA driver installations wait for all pods to be Ready before completing
- If installation fails, diagnostic logs are displayed
- Use `/dra-ocp-validator:cleanup` to uninstall (removes driver + operator by default, preserves NFD)

## See Also
- `/dra-ocp-validator:validate` - Full validation (setup + test + report)
- `/dra-ocp-validator:test` - Run tests only (assumes setup done)
- `/dra-ocp-validator:cleanup` - Clean up test resources and drivers
