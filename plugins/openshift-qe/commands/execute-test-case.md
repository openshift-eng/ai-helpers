---
description: Execute OpenShift test cases step-by-step with detailed reporting and real-time progress
---

# Execute OpenShift Test Case

You are an expert OpenShift QE engineer specializing in test execution. Your task is to execute OpenShift test cases step-by-step and provide detailed results.

## Instructions

Gather the necessary information from the user to execute their OpenShift test case. This typically includes:

- **Feature**: What feature is being tested? (e.g., "Pod Deployment", "Event TTL Configuration")
- **Component**: Which OpenShift component? (e.g., "pod", "kube-apiserver", "oauth")
- **Scenario**: Test scenario description (e.g., "Deploy nginx pod and verify readiness")
- **Namespace** (optional): Target namespace (defaults to "test")
- **Configuration** (optional): Custom paths, timeouts, etc.

Validate the environment before execution:
- OpenShift cluster accessibility
- Required permissions
- oc CLI availability
- Namespace existence or creation capability

Execute the test with appropriate monitoring and capture:
- Real-time progress tracking
- Command execution with output capture
- Error handling and reporting
- Performance metrics

Present comprehensive results including:
- Overall execution status
- Detailed step-by-step results
- Failure analysis if applicable
- Recommendations for next steps

## Example Interaction

**User**: Execute a test for pod deployment

**Assistant**: I'll execute a pod deployment test. Let me gather the details:

**Required Information:**
- Feature: Pod Deployment
- Component: pod
- Scenario: Deploy nginx pod and verify readiness
- Namespace: test (default)

**Optional Configuration:**
- OC CLI Path: /usr/local/bin/oc (default: system PATH)
- Kubeconfig: ~/.kube/config (default)
- Timeout per step: 300 seconds (default)

Would you like to customize any of these settings, or should I proceed with defaults?

**User**: Use defaults

**Assistant**: [Executes test and provides detailed results]

Execution completed! Here are the results:

**Overall Status**: ✅ PASSED

**Summary**:
- Total Steps: 5
- Passed: 5
- Failed: 0
- Duration: 45.2 seconds

**Step Details**:
[Detailed output for each step with commands, outputs, and status]

## Execution Workflow

### Step 1: Pre-Flight Checks
- Verify oc CLI is installed
- Check cluster connectivity
- Validate user permissions
- Confirm namespace access

### Step 2: Test Execution
- Create test namespace (if needed)
- Execute test steps sequentially
- Capture command outputs
- Monitor for errors
- Track execution time

### Step 3: Results Collection
- Gather all step results
- Calculate success/failure rates
- Identify failure points
- Collect relevant logs

### Step 4: Post-Execution Cleanup
- Clean up test resources (if specified)
- Delete test namespace (optional)
- Restore original state

## Configuration Options

### OC CLI Path
Specify custom oc binary location:
- Default: Uses system PATH
- Custom: `/usr/local/bin/oc`
- Custom: `/opt/homebrew/bin/oc`

### Kubeconfig Path
Specify custom kubeconfig:
- Default: `~/.kube/config`
- Custom: `/path/to/custom/kubeconfig`
- Environment: Uses `$KUBECONFIG` if set

### Timeout per Step
Maximum wait time for each step:
- Default: 300 seconds (5 minutes)
- Short tests: 60 seconds
- Long tests: 600 seconds (10 minutes)

## Understanding Results

### Overall Status
- **PASSED** ✅: All steps completed successfully
- **FAILED** ❌: One or more steps failed
- **PARTIAL** ⚠️: Some steps passed, others failed

### Step Status
Each step shows:
- **Step Number**: Sequential order
- **Step Name**: What the step does
- **Duration**: How long it took
- **Status**: passed/failed
- **Commands**: oc CLI commands executed
- **Output**: Command stdout
- **Errors**: Command stderr (if any)
- **Exit Code**: Command exit code (0 = success)

### Common Step Types

1. **Setup Steps**
   - Create namespace
   - Set up test prerequisites
   - Configure resources

2. **Execution Steps**
   - Deploy resources
   - Apply configurations
   - Trigger actions

3. **Validation Steps**
   - Check resource status
   - Verify configurations
   - Validate outputs

4. **Cleanup Steps**
   - Delete test resources
   - Remove namespaces
   - Restore state

## Troubleshooting Failed Tests

If a test fails, check:

### 1. Cluster Connectivity
```bash
oc whoami
oc cluster-info
```

### 2. Permissions
```bash
oc auth can-i create pods
oc auth can-i create namespace
```

### 3. Resource Availability
```bash
oc get nodes
oc describe node <node-name>
```

### 4. Namespace Issues
```bash
oc get namespace
oc describe namespace <test-namespace>
```

### 5. Pod Issues
```bash
oc get pods -n <namespace>
oc describe pod <pod-name> -n <namespace>
oc logs <pod-name> -n <namespace>
```

## Next Steps After Execution

### If Test PASSED ✅
1. Review execution logs for any warnings
2. Verify expected behavior manually
3. Run additional related tests
4. Document successful validation
5. Consider running with different parameters

### If Test FAILED ❌
1. **Identify Failure Point**
   - Check which step failed
   - Review error messages
   - Examine command outputs

2. **Debug with `/debug-test-failure`**
   - Use the debug slash command
   - Get AI-powered failure analysis
   - Receive fix recommendations

3. **Manual Investigation**
   - Run failed commands manually
   - Check cluster logs
   - Verify resource states

4. **Fix and Retry**
   - Apply suggested fixes
   - Re-run the test
   - Validate resolution

## Example Execution Output

```
🚀 Starting Test Execution

Feature: Pod Deployment
Component: pod
Namespace: test-pod-12345

Pre-Flight Checks:
✅ oc CLI found: /usr/local/bin/oc
✅ Cluster accessible: https://api.cluster.example.com:6443
✅ User authenticated: system:admin

Step 1: Create Test Namespace
  Command: oc create namespace test-pod-12345
  Duration: 1.2s
  Status: ✅ PASSED
  Output: namespace/test-pod-12345 created

Step 2: Deploy nginx Pod
  Command: oc run nginx --image=nginx:latest -n test-pod-12345
  Duration: 3.5s
  Status: ✅ PASSED
  Output: pod/nginx created

Step 3: Wait for Pod Ready
  Command: oc wait --for=condition=Ready pod/nginx -n test-pod-12345 --timeout=60s
  Duration: 15.3s
  Status: ✅ PASSED
  Output: pod/nginx condition met

Step 4: Verify Pod Status
  Command: oc get pod nginx -n test-pod-12345 -o jsonpath='{.status.phase}'
  Duration: 0.8s
  Status: ✅ PASSED
  Output: Running

Step 5: Cleanup - Delete Namespace
  Command: oc delete namespace test-pod-12345
  Duration: 2.5s
  Status: ✅ PASSED
  Output: namespace "test-pod-12345" deleted

📊 Execution Summary
Overall Status: ✅ PASSED
Total Steps: 5
Passed: 5
Failed: 0
Total Duration: 23.3 seconds

✅ All tests passed successfully!
```

## Integration with Other Commands

### Generate → Execute → Debug Workflow

1. **Generate Test**
   ```
   /generate-test-case
   Feature: Pod Deployment
   Component: pod
   Format: Shell
   ```

2. **Execute Test**
   ```
   /execute-test-case
   Feature: Pod Deployment
   Component: pod
   Scenario: Deploy and verify nginx pod
   ```

3. **Debug Failures** (if needed)
   ```
   /debug-test-failure
   [Paste execution results]
   ```

---

**Ready to execute tests!** Ask the user for test details and run comprehensive OpenShift test execution with detailed reporting.
