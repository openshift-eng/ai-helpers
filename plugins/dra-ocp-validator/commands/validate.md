---
description: Complete DRA validation (setup + test + report) on OpenShift clusters
argument-hint: "<kubeconfig-path> [options]"
---

## Name
dra-ocp-validator:validate

## Synopsis
```
/dra-ocp-validator:validate <kubeconfig-path> [options]
```

## Description
The `dra-ocp-validator:validate` command performs comprehensive end-to-end validation of Dynamic Resource Allocation (DRA) features on an OpenShift cluster. It combines cluster setup, feature testing, and report generation into a single workflow.

**Complete workflow:**
1. Verify cluster access and detect hardware
2. Install prerequisites (NFD, GPU operator, DRA driver)
3. Determine available DRA features based on K8s version
4. Check CDMM status and feature gates
5. Run feature validation tests
6. Collect artifacts and generate validation report
7. Package results in tarball for JIRA attachment

This is the recommended command for full DRA validation.

## Implementation

This command executes the complete end-to-end DRA validation workflow, combining setup, testing, and reporting into a single operation. This is a long-running command (10-20 minutes) that performs cluster modifications.

### Steps

1. **Parse and Validate Arguments**:
   - Extract kubeconfig path from first positional argument (required)
   - Parse optional flags: `--driver`, `--features`, `--skip-install`, `--enable-dynamic-mig`, `--driver-version`, `--output-dir`
   - Expand tilde (`~`) to `$HOME` in paths
   - Verify kubeconfig file exists

2. **Execute Validation Workflow Script**:
   
   Use the Bash tool to run the plugin's comprehensive validation script:
   
   ```bash
   PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
   SCRIPT="${PLUGIN_ROOT}/tools/validate-dra.sh"
   
   # Pass all arguments to validation script
   ${SCRIPT} "$@"
   ```
   
   The validation script orchestrates the complete workflow:
   
   a. **Setup Phase** (unless `--skip-install`):
      - Verify cluster connectivity and admin access
      - Detect GPU vendor from NFD labels (or use `--driver` flag)
      - Install NFD if not present
      - Install appropriate DRA driver stack:
        - NVIDIA: GPU Operator + NVIDIA DRA Driver
        - Example: dra-example-driver (software-only)
      - Enable feature gates if `--enable-dynamic-mig` specified
      - Verify driver installation (DeviceClass, ResourceSlice)
   
   b. **Pre-Test Checks**:
      - Detect cluster K8s version (1.32-1.36)
      - Determine available DRA features for this version
      - Check CDMM status (Grace-Blackwell MIG compatibility)
      - Validate feature gates for Alpha features
      - Parse `--features` flag or select all Beta features
   
   c. **Test Execution**:
      - For each selected feature:
        - Create timestamped test directory
        - Run corresponding test from `tests/` directory
        - Capture test output and resource logs
        - Mark as PASS, FAIL, or SKIP with reason
      - All tests run to completion (no fail-fast)
   
   d. **Artifact Collection & Reporting**:
      - Collect all test logs and manifests
      - Gather cluster diagnostics (nodes, GPU info, DRA resources)
      - Generate comprehensive validation report (markdown)
      - Package everything into tarball for JIRA attachment
      - Create summary with next-step recommendations

3. **Monitor Progress**:
   
   The script outputs detailed progress throughout the workflow. Present these updates to the user:
   - Setup phase progress (NFD install, GPU operator install, driver install)
   - Test execution status (which test is running, results)
   - Artifact collection progress
   - Report generation
   
   The workflow is long-running (10-20 minutes), so keeping the user informed is important.

4. **Handle Failures**:
   
   The script handles failures at each phase:
   
   - **Setup failures**: Driver installation errors, operator deployment issues
     - Displays error diagnostics
     - Suggests troubleshooting steps
     - Exits without running tests
   
   - **Test failures**: Feature validation failures
     - Continues running remaining tests
     - Collects failure logs and diagnostics
     - Includes failure analysis in report
     - Exits with non-zero status
   
   Present failure details to the user and suggest running `/dra-ocp-validator:analyze` for detailed failure diagnosis.

5. **Report Completion**:
   
   When validation completes, the script outputs:
   - Test results summary (X/Y PASS, Z SKIP, W FAIL)
   - Path to validation report (markdown)
   - Path to artifact tarball (for JIRA attachment)
   - Cleanup command (if needed)
   - Next steps based on results
   
   Present this summary to the user.

## Arguments

### Required
- `kubeconfig-path` - Path to cluster kubeconfig file

### Optional
- `--driver <nvidia|amd|example>` - Driver to install (default: auto-detect)
  - `nvidia` - NVIDIA GPU Operator + DRA driver
  - `amd` - AMD GPU driver (planned)
  - `example` - dra-example-driver (no GPU required)
- `--features <list>` - Comma-separated features to test (default: all Beta)
  - `partitionable` - DRA Partitionable Devices (KEP-4815)
  - `admin-access` - DRA Admin Access
  - `prioritized-list` - DRA Prioritized List (KEP-4816)
  - `podresources-api` - PodResources API
  - `device-taints` - Device Taints (Alpha/Beta)
  - `extended-resources` - Extended Resources (K8s 1.35+)
  - `all` - All Beta features for this K8s version
- `--skip-install` - Skip driver/operator installation (assumes already installed)
- `--enable-dynamic-mig` - Enable DynamicMIG feature gate (required for Partitionable Devices)
- `--driver-version <version>` - Specific driver version (default: 580.126.20)
- `--output-dir <path>` - Output directory (default: ./dra-validation-<timestamp>)

## Return Value
- **Success**: All requested features validated or skipped with valid reasons
- **Failure**: One or more features failed validation

## Examples

### Example 1: Full validation on NVIDIA cluster with MIG
```
/dra-ocp-validator:validate ~/clusters/a100/kubeconfig \
  --driver nvidia \
  --enable-dynamic-mig
```

**Output:**
```
✓ Cluster accessible (OCP 4.21.16, K8s 1.34.7)
✓ Hardware detected: 2x NVIDIA A100-SXM4-40GB
✓ Installing NFD...
✓ Installing NVIDIA GPU Operator...
✓ Installing NVIDIA DRA Driver (DYNAMIC_MIG=true)...
✓ MIG devices found: 14
✓ CDMM disabled - MIG tests can run

Running tests:
  ✅ Partitionable Devices: PASS
  ✅ Admin Access: PASS
  ✅ Prioritized List: PASS
  ✅ PodResources API: PASS

✓ Artifacts collected: ./dra-validation-20260603/
✓ Report generated: ./dra-validation-20260603/DRA-VALIDATION-REPORT.md
✓ Tarball created: ./dra-validation-20260603.tar.gz (2.3M)

Results: 4/4 Beta features VALIDATED
```

### Example 2: Validation without physical GPUs
```
/dra-ocp-validator:validate ~/kubeconfig \
  --driver example \
  --features admin-access,prioritized-list
```

**Output:**
```
✓ Cluster accessible (OCP 4.21.16, K8s 1.34.7)
⚠ No GPUs detected - using dra-example-driver
✓ Installing dra-example-driver...
✓ ResourceSlices created: 2

Running tests:
  ✅ Admin Access: PASS
  ✅ Prioritized List: PASS

Results: 2/2 VALIDATED
```

### Example 3: Test specific features on pre-configured cluster
```
/dra-ocp-validator:validate ~/kubeconfig \
  --skip-install \
  --features partitionable,admin-access
```

### Example 4: Custom output directory
```
/dra-ocp-validator:validate ~/kubeconfig \
  --driver nvidia \
  --enable-dynamic-mig \
  --output-dir ./validation-results-$(date +%Y%m%d)
```

## Prerequisites
- Cluster admin access
- Internet connectivity for pulling images
- Local tools: `oc`, `kubectl`, `helm`, `jq`

## Notes
- Full validation can take 20-30 minutes depending on cluster size
- Test namespaces are created: `dra-*-test`
- Alpha features require feature gates to be enabled
- CDMM detection auto-skips MIG tests on Grace-Blackwell
- Use `/dra-ocp-validator:cleanup` to remove test resources after validation

## Troubleshooting

### Driver installation fails
```
ERROR: Helm release failed
```
**Solution:** Check cluster permissions and network connectivity
```bash
oc auth can-i create namespace
helm repo list
```

### Feature gate not enabled
```
SKIP: DRADeviceTaints requires feature gate
```
**Solution:** Enable feature gate (shown in output) or skip Alpha features

### CDMM blocks MIG tests
```
SKIP: Partitionable Devices (CDMM enabled)
```
**Solution:** This is expected on Grace-Blackwell with CDMM. Test non-MIG features instead.

## See Also
- `/dra-ocp-validator:setup` - Install prerequisites only
- `/dra-ocp-validator:test` - Run tests on pre-configured cluster
- `/dra-ocp-validator:cleanup` - Clean up test resources
