---
description: Run DRA feature tests on a cluster with prerequisites already installed
argument-hint: "<kubeconfig-path> [options]"
---

## Name
dra-ocp-validator:test

## Synopsis
```
/dra-ocp-validator:test <kubeconfig-path> [options]
```

## Description
The `dra-ocp-validator:test` command runs DRA feature validation tests on a cluster where the DRA driver and GPU operator have already been installed (via `/dra-ocp-validator:setup` or manually).

This is useful when you want to:
- Re-run tests after fixing issues
- Test a subset of features
- Run tests on a pre-configured cluster
- Validate after cluster or driver configuration changes

The command performs:
1. Cluster access verification
2. DRA driver readiness check (DeviceClass, ResourceSlice)
3. K8s version detection and feature availability mapping
4. CDMM detection (Grace-Blackwell) for MIG test skipping
5. Feature gate validation (Alpha features only)
6. Test execution for selected features
7. Artifact collection and report generation

## Implementation

This command executes comprehensive DRA feature tests on a cluster where the DRA driver has already been installed. Tests are selected based on K8s version and feature gates.

### Steps

1. **Parse and Validate Arguments**:
   - Extract kubeconfig path from first positional argument (required)
   - Parse optional flags: `--features`, `--output-dir`
   - Expand tilde (`~`) to `$HOME` in paths
   - Verify kubeconfig file exists

2. **Execute Test Runner Script**:
   
   Use the Bash tool to run the plugin's test runner script:
   
   ```bash
   PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
   SCRIPT="${PLUGIN_ROOT}/tools/run-tests.sh"
   
   # Pass all arguments to test script
   ${SCRIPT} "$@"
   ```
   
   The test script performs these steps automatically:
   
   a. **Cluster Validation**:
      - Verify cluster connectivity
      - Check DRA driver is installed (DeviceClass and ResourceSlice resources exist)
      - Detect cluster K8s version (1.32-1.36)
      - Verify cluster-admin access for test operations
   
   b. **Feature Selection**:
      - Parse `--features` flag or use defaults (Beta + GA features only)
      - Map features to their graduation level for this K8s version
      - Filter out features unavailable on this K8s version
      - **IMPORTANT**: Default behavior excludes Alpha features
      - If Alpha features are explicitly requested via `--features`, the test runner will ERROR and require manual feature gate enablement
   
   c. **Alpha Feature Handling**:
      - If user requests Alpha features explicitly (e.g., `--features partitionable,device-taints`), the test runner will:
        - Detect that Alpha features require feature gates
        - ERROR with detailed message explaining:
          - Which feature gates are required
          - OpenShift featureset conflict (TechPreviewNoUpgrade vs CustomNoUpgrade)
          - Manual steps to enable feature gates
        - Exit without running tests
      - User must manually enable feature gates and re-run tests
      - This prevents automatic featureset conflicts
   
   d. **Test Execution**:
      - For each feature in the selected list:
        - Create timestamped test directory in output-dir
        - Execute corresponding test script from `tests/` directory
        - Capture test output and pod logs
        - Mark result as PASS, FAIL, or SKIP
      - Test scripts are self-contained and validate specific DRA functionality
   
   e. **Artifact Collection**:
      - Run `tools/collect-artifacts.sh` to gather:
        - All test logs
        - Pod manifests and logs
        - DeviceClass and ResourceSlice definitions
        - Cluster diagnostics
      - Package artifacts into tarball
   
   f. **Report Generation**:
      - Generate markdown validation report with:
        - Cluster details (version, nodes, GPU info)
        - Test results summary (PASS/FAIL/SKIP counts)
        - Per-feature test details
        - Recommendations for failed tests
      - Write report to output directory

3. **Monitor Progress**:
   
   The script outputs progress messages during test execution. Present these to the user to show:
   - Which tests are being run
   - Test execution status (running, passed, failed, skipped)
   - Reasons for skipped tests
   - Where artifacts are being collected

4. **Handle Test Failures**:
   
   If tests fail, the script will:
   - Display which tests failed
   - Show relevant error messages from test logs
   - Continue running remaining tests (fail-fast is not used)
   - Exit with non-zero status if any test failed
   
   Present failure details to the user and suggest:
   - Running `/dra-ocp-validator:analyze` to diagnose failures
   - Checking the generated report for detailed failure information
   - Reviewing test logs in the output directory

5. **Report Completion**:
   
   When all tests complete, the script outputs:
   - Test results summary (X/Y PASS, Z SKIP, W FAIL)
   - Path to generated report
   - Path to artifact tarball
   - Suggested next steps
   
   Present this summary to the user.

## Arguments

### Required
- `kubeconfig-path` - Path to cluster kubeconfig file

### Optional
- `--features <list>` - Comma-separated features to test (default: `all` = Beta + GA only)
  
  **Beta/GA Features** (safe to test without manual feature gate setup):
  - `structured-parameters` - DRA Structured Parameters (GA in K8s 1.34+)
  - `admin-access` - Namespace Admin Access Control (Beta in K8s 1.34-1.35)
  - `prioritized-list` - Scheduler Preference Ordering (Beta in K8s 1.34-1.35)
  - `resource-claim-status` - Enhanced Claim Status (Beta in K8s 1.32+)
  - `podresources-api` - Kubelet PodResources API (Beta in K8s 1.34+)
  
  **Alpha Features** (require manual feature gate enablement - will ERROR if requested):
  - `partitionable` - GPU Partitioning/MIG Support (Alpha, requires DRAPartitionableDevices gate)
  - `device-taints` - Automatic Node Tainting (Alpha, requires DRADeviceTaints gate)
  - `consumable-capacity` - Consumable Resources (Alpha, requires DRAConsumableCapacity gate)
  - `extended-resources` - Extended Resource Requests (Alpha, requires DRAExtendedResources gate)
  - `resource-health-status` - Device Health Info (Alpha, requires DRAResourceHealthStatus gate)
  - `device-binding-conditions` - Enhanced Binding Conditions (Alpha, requires DRADeviceBindingConditions gate)
  
  **Special values**:
  - `all` - All Beta + GA features (excludes Alpha)
  
  **⚠️ Important**: Requesting Alpha features will ERROR with instructions to manually enable feature gates
  
- `--output-dir <path>` - Output directory for artifacts (default: ./dra-validation-<timestamp>)

## Return Value
- **Success**: All tests passed or skipped with valid reasons
- **Failure**: One or more tests failed

Test results summary:
- ✅ PASS - Feature validated successfully
- ⚠️ SKIP - Feature skipped (reason provided)
- ❌ FAIL - Feature validation failed

## Examples

### Example 1: Run all Beta + GA tests (default)
```
/dra-ocp-validator:test ~/kubeconfig
```

**Output:**
```
✓ Cluster accessible (OCP 4.21.16, K8s 1.34.7)
✓ DRA driver ready (DeviceClass: gpu.example.com, ResourceSlices: 3)
Default mode: Testing Beta and GA features only

Running tests:
  ✅ Structured Parameters: PASS
  ✅ Admin Access: PASS (namespace enforcement validated)
  ✅ Prioritized List: PASS (scheduler preference confirmed)
  ✅ Resource Claim Status: PASS
  ✅ PodResources API: PASS (claim status populated)

✓ Artifacts collected: ./dra-validation-20260603/
✓ Report generated: ./dra-validation-20260603/DRA-VALIDATION-REPORT.md

Results: 5/5 PASS
```

### Example 2: Test specific Beta features
```
/dra-ocp-validator:test ~/kubeconfig --features admin-access,prioritized-list
```

**Output:**
```
Running tests:
  ✅ Admin Access: PASS
  ✅ Prioritized List: PASS

Results: 2/2 PASS
```

### Example 3: Request Alpha feature (ERROR with instructions)
```
/dra-ocp-validator:test ~/kubeconfig --features device-taints,consumable-capacity
```

**Output:**
```
❌ ERROR: Alpha features requested but not enabled

The following Alpha features require feature gate enablement:
  - device-taints → requires 'DRADeviceTaints' feature gate
  - consumable-capacity → requires 'DRAConsumableCapacity' feature gate

⚠️  IMPORTANT: OpenShift only allows ONE featureset at a time:
  - TechPreviewNoUpgrade (for officially supported tech preview features)
  - CustomNoUpgrade (for upstream Alpha features not in downstream)

You cannot enable features from different featuresets simultaneously.

To enable Alpha features, you must:
  1. Determine which featureset each feature requires
  2. Choose features from the SAME featureset
  3. Enable the feature gate(s) manually via:

     For TechPreviewNoUpgrade (e.g., DRAPartitionableDevices):
       oc patch featuregate cluster --type=merge \
         -p '{"spec":{"featureSet":"TechPreviewNoUpgrade"}}'

     For CustomNoUpgrade (e.g., DRADeviceTaints, DRAConsumableCapacity):
       oc patch featuregate cluster --type=merge \
         -p '{"spec":{"customNoUpgrade":{"enabled":["DRADeviceTaints","DRAConsumableCapacity"]}}}'

  4. Re-run setup if driver configuration is needed:
       /dra-ocp-validator:setup ~/kubeconfig [--enable-dynamic-mig]

  5. Re-run tests with the same --features flag
```

### Example 4: MIG test with CDMM enabled (auto-skip)
```
/dra-ocp-validator:test ~/kubeconfig --features partitionable
```

**Output:**
```
✓ CDMM enabled (2 NUMA nodes detected)
⚠️ CDMM + MIG incompatible (NVIDIA driver limitation)

Running tests:
  ⚠️ Partitionable Devices: SKIP (CDMM enabled, MIG unavailable)

Reference: NVIDIA GPU Operator Known Issues
Results: 0/1 PASS, 1 SKIP
```

### Example 5: Version-gated feature
```
/dra-ocp-validator:test ~/kubeconfig --features extended-resources
```

**K8s 1.34 Output:**
```
Running tests:
  ⚠️ Extended Resources: SKIP (requires Kubernetes 1.35+, cluster has 1.34.7)

Results: 0/1 PASS, 1 SKIP
```

## Prerequisites
- DRA driver must be installed and running
- DeviceClass and ResourceSlice resources must exist
- For Alpha features: Required feature gates must be enabled
- For MIG tests: CDMM must be disabled (auto-detected)

## Test Output Structure

Each test creates a timestamped directory:
```
dra-<feature>-<timestamp>/
├── test-output.log              # Complete test transcript
├── 00-cluster-version.txt       # Cluster information
├── 01-nodes.txt                 # Node details
├── 02-deviceclass-*.yaml        # DeviceClass config
├── 03-resourceslice-*.json      # ResourceSlice state
├── test1-manifest.yaml          # Test 1 manifests
├── test1-allocation.json        # Test 1 device allocation
├── test2-*                      # Test 2 artifacts
└── 99-*-final.txt               # Final state captures
```

## Notes
- Tests create temporary namespaces (e.g., `dra-partitionable-test`)
- Each test is independent and can run in parallel
- Test scripts have comprehensive logging and state capture
- Failed tests leave resources for debugging
- Use `/dra-ocp-validator:cleanup` to remove test namespaces
- Tests require ~5-10 minutes per feature
- Network policies or security constraints may affect pod scheduling

## Troubleshooting

### DRA driver not found
```
ERROR: No DeviceClass found - DRA driver not installed
```
**Solution:** Run `/dra-ocp-validator:setup` first

### Feature gate not enabled
```
SKIP: Feature requires DRADeviceTaints=true
```
**Solution:** Patch FeatureGate (command shown in output)

### CDMM blocks MIG tests
```
SKIP: CDMM enabled, MIG unavailable (NVIDIA limitation)
```
**Solution:** Accept skip (known limitation) or disable CDMM (not recommended for production)

## See Also
- `/dra-ocp-validator:validate` - Full validation (setup + test + report)
- `/dra-ocp-validator:setup` - Install prerequisites only
- `/dra-ocp-validator:cleanup` - Clean up test resources
