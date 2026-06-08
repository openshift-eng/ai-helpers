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
      - Parse `--features` flag or use defaults (all Beta features)
      - Map features to their graduation level for this K8s version
      - Filter out features unavailable on this K8s version
      - Check CDMM status for MIG test skipping (Grace-Blackwell systems)
   
   c. **Feature Gate Validation** (Alpha features only):
      - Query cluster FeatureGate status
      - Skip Alpha features if their feature gate is not enabled
      - Provide enablement command in skip message
   
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
- `--features <list>` - Comma-separated features to test (default: all Beta features)
  - `partitionable` - DRA Partitionable Devices (KEP-4815)
  - `admin-access` - DRA Admin Access
  - `prioritized-list` - DRA Prioritized List (KEP-4816)
  - `podresources-api` - PodResources API for DRA
  - `device-taints` - Device Taints (Alpha in K8s 1.34-1.35, Beta in 1.36+)
  - `extended-resources` - Extended Resources (requires K8s 1.35+)
  - `all` - All Beta features available for this K8s version
- `--output-dir <path>` - Output directory for artifacts (default: ./dra-validation-<timestamp>)

## Return Value
- **Success**: All tests passed or skipped with valid reasons
- **Failure**: One or more tests failed

Test results summary:
- ✅ PASS - Feature validated successfully
- ⚠️ SKIP - Feature skipped (reason provided)
- ❌ FAIL - Feature validation failed

## Examples

### Example 1: Run all Beta tests
```
/dra-ocp-validator:test ~/kubeconfig
```

**Output:**
```
✓ Cluster accessible (OCP 4.21.16, K8s 1.34.7)
✓ DRA driver ready (DeviceClass: mig.nvidia.com, ResourceSlices: 4)
✓ Available features: partitionable, admin-access, prioritized-list, podresources-api
✓ CDMM disabled - MIG tests can run

Running tests:
  ✅ Partitionable Devices: PASS (4 pods scheduled, SharedCounters verified)
  ✅ Admin Access: PASS (namespace enforcement validated)
  ✅ Prioritized List: PASS (scheduler preference confirmed)
  ✅ PodResources API: PASS (claim status populated)

✓ Artifacts collected: ./dra-validation-20260603/
✓ Report generated: ./dra-validation-20260603/DRA-VALIDATION-REPORT.md

Results: 4/4 PASS
```

### Example 2: Test specific features
```
/dra-ocp-validator:test ~/kubeconfig --features partitionable,prioritized-list
```

**Output:**
```
Running tests:
  ✅ Partitionable Devices: PASS
  ✅ Prioritized List: PASS

Results: 2/2 PASS
```

### Example 3: Alpha feature (requires feature gate)
```
/dra-ocp-validator:test ~/kubeconfig --features device-taints
```

**Output:**
```
Running tests:
  ⚠️ Device Taints: SKIP (DRADeviceTaints feature gate not enabled)

To enable:
  oc patch featuregate cluster --type=merge \
    -p '{"spec":{"customNoUpgrade":{"enabled":["DRADeviceTaints"]}}}'

Results: 0/1 PASS, 1 SKIP
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
