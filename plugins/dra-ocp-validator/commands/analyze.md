---
description: Analyze DRA test failure and provide debugging guidance
argument-hint: "<test-output-directory>"
---

## Name
dra-ocp-validator:analyze

## Synopsis
```
/dra-ocp-validator:analyze <test-output-directory>
```

## Description
The `dra-ocp-validator:analyze` command analyzes a failed DRA test and provides:
- Failure root cause analysis from logs and events
- Common issue detection (scheduling failures, allocation errors, permissions)
- Test-specific debugging guidance
- Recommended next steps

This is useful when:
- A test fails and you need to understand why
- You want automated analysis of collected debug artifacts
- You need specific debugging commands for the failure type

The command analyzes:
1. Test summary and validation status
2. Kubernetes events (scheduling/allocation failures)
3. ResourceClaim status and conditions
4. Pod status and scheduling decisions
5. DRA driver logs for errors
6. Test-specific patterns

## Implementation

This command performs automated analysis of DRA test failures by examining collected logs, events, and resource states. It identifies common failure patterns and provides targeted debugging guidance.

### Steps

1. **Validate Arguments**:
   - Extract test output directory path from first argument (required)
   - Verify directory exists and contains test artifacts
   - Check for required files (test-summary.txt, resource manifests, logs)

2. **Execute Failure Analysis Script**:
   
   Use the Bash tool to run the plugin's analysis script:
   
   ```bash
   PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
   SCRIPT="${PLUGIN_ROOT}/tools/analyze-failure.sh"
   
   # Pass test output directory to analyzer
   ${SCRIPT} "$1"
   ```
   
   The analysis script performs structured examination:
   
   a. **Test Context**:
      - Identify test type from directory name
      - Read test summary file for overall status
      - Extract test start/end timestamps
   
   b. **Event Analysis**:
      - Parse Kubernetes events from captured logs
      - Identify scheduling failures (FailedScheduling events)
      - Find allocation errors (ResourceClaim conditions)
      - Detect permission/RBAC issues (Forbidden errors)
      - Extract DRA-specific error messages
   
   c. **ResourceClaim Analysis**:
      - Check ResourceClaim status (allocated vs pending)
      - Examine allocation conditions and error messages
      - Verify device assignments in allocation results
      - Identify unallocated claims and reasons
   
   d. **Pod Analysis**:
      - Check pod scheduling status (Pending, Running, Failed)
      - Examine pod conditions for scheduling blocks
      - Review container logs for application-level failures
      - Verify resource claim references in pod specs
   
   e. **Driver Log Analysis**:
      - Search DRA driver logs for ERROR/WARN messages
      - Correlate driver errors with claim failures
      - Identify driver-specific issues (device unavailable, config errors)
   
   f. **Pattern Matching**:
      - Match failure symptoms to known issue patterns:
        - Feature gate not enabled
        - CDMM + MIG incompatibility
        - Device already allocated
        - Namespace admin access missing
        - Scheduler configuration issues
      - Provide test-specific debugging guidance

3. **Present Analysis Results**:
   
   The script outputs structured analysis with sections:
   - Test summary and overall status
   - Identified failures with error messages
   - Root cause analysis (if pattern matches)
   - Debugging commands to run
   - Recommended next steps
   
   Present this output to the user, highlighting:
   - Key failure messages
   - Recommended actions
   - Where to look for more details

4. **Provide Debugging Guidance**:
   
   Based on the failure type, the script suggests:
   - Specific kubectl/oc commands to investigate further
   - Configuration changes to try
   - Related tests to check
   - JIRA search queries for known issues
   
   Present these suggestions as actionable next steps.

## Arguments

### Required
- `test-output-directory` - Path to test output directory (e.g., `./dra-admin-access-20260604-202015`)

## Return Value
- **Success**: Analysis completed, findings displayed
- **Failure**: Directory not found or missing required files

## Examples

### Example 1: Analyze admin-access test failure
```
/dra-ocp-validator:analyze ./dra-admin-access-20260604-202015
```

**Output:**
```
=========================================
DRA Test Failure Analysis
=========================================
Analyzing: ./dra-admin-access-20260604-202015

Test Type: admin-access

=== Test Summary ===

==========================================
VALIDATION SUMMARY
==========================================

Test Results:
  Unauthorized namespace: FAIL (accepted)
  Authorized namespace:   PASS (accepted)

⚠ VALIDATION INCOMPLETE

=== Failure Analysis ===

📋 Checking Events for Failures:

  ❌ Found Forbidden/Permission errors:
     The ResourceClaim "claim-admin-test" is invalid: spec.devices.requests[0].adminAccess: Forbidden: admin access to devices requires the `resource.kubernetes.io/admin-access: true` label

📋 Checking ResourceClaim Status:

  ⚠ Unallocated ResourceClaims found:
     claim-admin-test

📋 Checking Pod Status:

  ✓ No pending or failed pods

📋 Checking Driver Logs:

  ✓ No errors in driver logs

=== Debugging Guidance ===

Admin Access Test Debugging:

1. Check namespace labels:
   oc get namespace dra-no-admin dra-with-admin -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.labels}{"\n"}{end}'

2. Check ResourceClaim rejection reason:
   cat ./dra-admin-access-20260604-202015/test1-result.txt

3. Verify API server enforces adminAccess:
   - Look for 'Forbidden' in ./dra-admin-access-20260604-202015/debug/events.txt

=== Summary ===

⚠ Found 2 potential issue(s)
  Review detailed logs in ./dra-admin-access-20260604-202015/debug/

Key Files:
  - ./dra-admin-access-20260604-202015/test-output.log
  - ./dra-admin-access-20260604-202015/debug/events.txt
  - ./dra-admin-access-20260604-202015/debug/resourceclaims-status.json

Next Steps:
  1. Review the specific errors shown above
  2. Check the recommended debug commands for this test type
  3. Look at ./dra-admin-access-20260604-202015/debug/README.txt
```

### Example 2: Analyze partitionable devices test
```
/dra-ocp-validator:analyze ./dra-validation-20260604-153143
```

**Output:**
```
=========================================
DRA Test Failure Analysis
=========================================
Analyzing: ./dra-validation-20260604-153143

Test Type: partitionable

=== Failure Analysis ===

📋 Checking Events for Failures:

  ❌ Found FailedScheduling events:
     0/6 nodes are available: 3 Insufficient gpu.example.com
     Pod "pod-4g" failed to schedule: no devices match selector

📋 Checking ResourceClaim Status:

  ⚠ Unallocated ResourceClaims found:
     claim-4g

=== Debugging Guidance ===

Partitionable Devices Test Debugging:

1. Check if SharedCounters exist in ResourceSlices:
   oc get resourceslice -o jsonpath='{.items[0].spec.devices[0].basic.sharedCounters}'

2. Check driver supports MIG/partitioning:
   cat ./dra-validation-20260604-153143/debug/*-driver-logs.txt | grep -i 'mig|partition'

3. Verify CEL selectors in DeviceClass:
   oc get deviceclass -o yaml | grep -A5 selectors

=== Summary ===

⚠ Found 2 potential issue(s)

Next Steps:
  1. Review the specific errors shown above
  2. Check the recommended debug commands for this test type
  3. Look at ./dra-validation-20260604-153143/debug/README.txt
```

### Example 3: Analyze with no debug directory
```
/dra-ocp-validator:analyze ./dra-old-test-20260601-120000
```

**Output:**
```
=========================================
DRA Test Failure Analysis
=========================================
Analyzing: ./dra-old-test-20260601-120000

Test Type: admin-access

=== Test Summary ===

(Test summary shown)

=== Failure Analysis ===

⚠ No debug/ directory found
  This test may not have collected debug info on failure
  Try re-running the test to collect full diagnostics
```

## Notes
- The analyzer reads debug artifacts collected during test execution
- Tests automatically collect debug info on failure (since latest update)
- Older test runs may not have debug/ directories
- The analyzer provides test-specific debugging commands
- Analysis is read-only - no cluster state is modified

## Common Issues Detected

### Scheduling Failures
- **Symptom**: "FailedScheduling" in events
- **Cause**: No nodes with available devices, node selector mismatch
- **Fix**: Check ResourceSlice capacity, node labels

### Allocation Failures
- **Symptom**: "FailedAllocation" or "no devices available"
- **Cause**: All devices in use, selector doesn't match any device
- **Fix**: Check ResourceSlice device attributes, verify CEL selectors

### Permission Errors
- **Symptom**: "Forbidden" errors
- **Cause**: Missing namespace labels, RBAC issues
- **Fix**: Check namespace `resource.kubernetes.io/admin-access` label

### Unallocated Claims
- **Symptom**: ResourceClaim has no `.status.allocation`
- **Cause**: Driver not running, claim request invalid
- **Fix**: Check driver pods, verify claim spec

### Pending Pods
- **Symptom**: Pod stuck in Pending
- **Cause**: ResourceClaim not allocated, node constraints
- **Fix**: Check `oc describe pod` Events section

## See Also
- `/dra-ocp-validator:test` - Run tests (auto-collects debug info on failure)
- `/dra-ocp-validator:validate` - Full validation workflow
- `/dra-ocp-validator:cleanup` - Clean up test resources
