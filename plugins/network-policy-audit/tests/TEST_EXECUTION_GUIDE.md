# Test Execution Guide

Complete guide for executing all NetworkPolicy Audit Plugin tests.

## Overview

This document provides step-by-step instructions for running all test suites that have been validated with **100% pass rate** on AWS OpenShift clusters.

## Test Suites

### Validation Tests (Automated Scripts)

**Purpose:** Validate installation, prerequisites, and basic functionality  
**Location:** `tests/validation/`  
**Tests:** 4 test suites (22 total checks)  
**Pass Rate:** 100%

**Test Suites:**
1. **Prerequisites Check** - 7 checks (cluster, Python, oc, dependencies, disk space)
2. **Installation Test** - 8 checks (venv, dependencies, imports, help command)
3. **Basic Functionality** - 3 tests (namespace analysis, empty namespace, error handling)
4. **Analysis Modes** - 4 modes (security, performance, compliance, invalid mode)

### Integration Tests (Automated Scripts)

**Purpose:** Validate plugin with real NetworkPolicies  
**Location:** `tests/integration/`  
**Tests:** 12 test cases (5 valid + 7 invalid policies)  
**Pass Rate:** 100%

**Test Cases:**
- **Valid Policies (5):** TC-VNP-001 through TC-VNP-005
- **Invalid Policies (7):** TC-INV-001 through TC-INV-007
- **Bug Verification:** BUG-001, BUG-002, BUG-003, BUG-PARSER

All tests create real namespaces, apply NetworkPolicies, run the plugin, and verify expected results.

## Prerequisites

### Required

- **OpenShift Cluster:** AWS cluster (Cluster Bot recommended)
- **oc CLI:** Latest version compatible with cluster
- **Python:** 3.9 or higher
- **pip:** For dependency installation
- **Git:** For cloning repository (if needed)

### Verify Prerequisites

```bash
# Check cluster connection
oc whoami
oc get nodes

# Check Python
python3 --version  # Should be >= 3.9

# Check oc CLI
oc version

# Check pip
pip3 --version
```

## Setup

### 1. Clone Repository (if needed)

```bash
git clone https://github.com/openshift-eng/ai-helpers.git
cd ai-helpers
```

### 2. Navigate to Plugin

```bash
cd plugins/network-policy-audit
```

### 3. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip3 install -r requirements.txt
```

### 5. Verify Installation

```bash
# Check installed packages
pip3 list | grep -E "kubernetes|pyyaml"

# Verify Python imports
python3 -c "import kubernetes; print('✅ kubernetes:', kubernetes.__version__)"
python3 -c "import yaml; print('✅ pyyaml: OK')"

# Test plugin help command
python3 scripts/netpol_analyzer_cli.py --help
```

**Expected Output:**
```
✅ kubernetes: 36.0.2
✅ pyyaml: OK

usage: netpol_analyzer_cli.py [-h] [--namespace NAMESPACE] ...
```

### 6. Configure Cluster Access

```bash
# Set KUBECONFIG
export KUBECONFIG=~/kubeconfig/cluster.kubeconfig

# Verify cluster connection
oc get nodes
oc whoami
oc cluster-info
```

**Expected Output:**
```
# oc whoami
system:admin

# oc get nodes
NAME                        STATUS   ROLES    AGE   VERSION
ip-10-0-xx-xx.ec2.internal  Ready    master   1h    v1.35.5
...
```

### 7. Navigate to Tests Directory

```bash
cd tests
pwd
# Expected: .../ai-helpers/plugins/network-policy-audit/tests
```

### Readiness Checklist

Before running tests, verify:

- ✅ Virtual environment created: `venv/` directory exists
- ✅ Virtual environment activated: `(venv)` in prompt
- ✅ Dependencies installed: `pip3 list | grep kubernetes` shows version
- ✅ Python imports working: `import kubernetes` and `import yaml` succeed
- ✅ Plugin files present: `../scripts/netpol_analyzer_cli.py` exists
- ✅ KUBECONFIG set: `echo $KUBECONFIG` shows path
- ✅ Cluster accessible: `oc whoami` returns username
- ✅ Cluster nodes visible: `oc get nodes` shows nodes
- ✅ In tests directory: `pwd` ends with `/tests`

**Quick Verification Command:**
```bash
# All-in-one check
(venv) $ python3 -c "import kubernetes, yaml; print('✅ Python OK')" && \
         oc whoami &>/dev/null && echo "✅ Cluster OK" && \
         pwd | grep -q "/tests$" && echo "✅ Directory OK"
```

**Expected Output:**
```
✅ Python OK
✅ Cluster OK
✅ Directory OK
```

## Test Execution

### Quick Start (All Tests)

```bash
# From plugin root directory
cd tests

# Set cluster connection
export KUBECONFIG=/path/to/cluster.kubeconfig

# Run all validation tests (4 test suites, ~25 seconds)
./validation/run_all_tests.sh

# Run all integration tests (12 test cases, ~2-4 minutes)
./integration/run_all_integration_tests.sh

# Cleanup all test resources
./integration/cleanup.sh
```

### Detailed Execution

#### Step 1: Validation Tests

**Purpose:** Verify prerequisites and installation

```bash
cd tests/validation

# 1. Check prerequisites
./prerequisites_check.sh
# Expected: All checks pass (cluster, Python, oc, files)

# 2. Test installation
./installation_test.sh
# Expected: Venv created, dependencies installed

# 3. Test basic functionality
./basic_functionality_test.sh
# Expected: Namespace analysis works

# 4. Test analysis modes
./analysis_modes_test.sh
# Expected: Security/performance/compliance modes work

# OR run all at once
./run_all_tests.sh
```

**Expected Output:**
```
Total Tests:  4
Passed:       4
Failed:       0
Success Rate: 100%

✅ ALL TESTS PASSED
```

#### Step 2: Integration Tests

**Purpose:** Test plugin with real NetworkPolicies

```bash
cd tests/integration

# Run all integration tests (12 test cases)
./run_all_integration_tests.sh
```

**Expected Output:**
```
Total Tests:   12
Passed:        12
Failed:        0
Success Rate:  100%

✅ ALL TESTS PASSED!
```

**What It Does:**
1. Cleans up any old test namespaces
2. Runs 5 valid policy tests (TC-VNP-001 through TC-VNP-005)
3. Runs 7 invalid policy tests (TC-INV-001 through TC-INV-007)
4. Verifies bug fixes (BUG-001, BUG-002, BUG-003)
5. Generates summary with results

**Individual Integration Tests:**

```bash
cd tests/integration

# Run individual valid policy tests
./01_run_tc_vnp_001.sh  # Default-deny baseline
./02_run_tc_vnp_002.sh  # Namespace isolation (BUG-001)
./03_run_tc_vnp_003.sh  # External API access
./04_run_tc_vnp_004.sh  # Three-tier app (BUG-001)
./05_run_tc_vnp_005.sh  # Monitoring access (BUG-003)

# Run individual invalid policy tests
./06_run_tc_inv_001.sh  # Missing default-deny
./07_run_tc_inv_002.sh  # Empty from[]
./08_run_tc_inv_003.sh  # Public ingress (BUG-002)
./09_run_tc_inv_004.sh  # Public egress
./10_run_tc_inv_005.sh  # Empty to[]
./11_run_tc_inv_006.sh  # Missing namespace selector
./12_run_tc_inv_007.sh  # Missing documentation
```

#### Step 3: Cleanup

```bash
cd tests/integration

# Run cleanup script to remove all test namespaces
./cleanup.sh
# Confirm when prompted: y
```

**Cleanup:**
- Deletes validation test namespaces (netpol-test-empty, netpol-validation-test)
- Deletes integration test namespaces (tc-vnp-*, tc-inv-*)
- Removes local test results (/tmp/netpol-validation-results, /tmp/netpol-test-results)
- Waits for deletion to complete

## Individual Test Execution

### Run Single Validation Test

```bash
cd tests/validation

# Run just prerequisites check
./prerequisites_check.sh

# Run just installation test
./installation_test.sh

# Run just basic functionality test
./basic_functionality_test.sh

# Run just analysis modes test
./analysis_modes_test.sh
```

### Test Plugin on Custom Namespace

```bash
cd plugins/network-policy-audit
source venv/bin/activate

# Create test namespace
oc create namespace my-test-namespace

# Create a simple NetworkPolicy
cat <<EOF | oc apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: my-test-namespace
spec:
  podSelector: {}
  policyTypes:
  - Ingress
EOF

# Run analysis
python3 scripts/netpol_analyzer_cli.py --namespace=my-test-namespace --mode=security

# Cleanup
oc delete namespace my-test-namespace
```

### Test Specific Analysis Mode

```bash
# Security mode
python3 scripts/netpol_analyzer_cli.py --namespace=<namespace> --mode=security

# Performance mode
python3 scripts/netpol_analyzer_cli.py --namespace=<namespace> --mode=performance

# Compliance mode
python3 scripts/netpol_analyzer_cli.py --namespace=<namespace> --mode=compliance
```

### Test Error Handling

```bash
# Empty namespace
oc create namespace test-empty
python3 scripts/netpol_analyzer_cli.py --namespace=test-empty --mode=security
# Expected: Exit code 1, "No NetworkPolicies found" message

# Invalid namespace
python3 scripts/netpol_analyzer_cli.py --namespace=does-not-exist --mode=security
# Expected: "No NetworkPolicies found" (treats as empty)

# Invalid mode
python3 scripts/netpol_analyzer_cli.py --namespace=test-ns --mode=invalid
# Expected: Error with valid mode choices

# Cleanup
oc delete namespace test-empty
```

## Expected Results

### Overall Success Rate

**All Tests Combined:**
- Total: 16 tests (4 validation + 12 integration)
- Passed: 16
- Failed: 0
- **Success Rate: 100%**

### Validation Tests

| Suite | Checks/Tests | Pass | Fail | Rate |
|-------|--------------|------|------|------|
| Prerequisites | 7 checks | 7 | 0 | 100% |
| Installation | 8 checks | 8 | 0 | 100% |
| Basic Functionality | 3 tests | 3 | 0 | 100% |
| Analysis Modes | 4 modes | 4 | 0 | 100% |

### Integration Tests

| Suite | Tests | Pass | Fail | Rate |
|-------|-------|------|------|------|
| Valid Policies | 5 | 5 | 0 | 100% |
| Invalid Policies | 7 | 7 | 0 | 100% |

### Bug Fix Verification

All bug fixes verified in integration tests:

✅ **BUG-PARSER:** Parser attribute fix (`_from` vs `from_`)  
✅ **BUG-001:** False positives on valid selectors (TC-VNP-002, TC-VNP-004)  
✅ **BUG-002:** Public internet specific messages (TC-INV-003)  
✅ **BUG-003:** Empty podSelector warning (TC-VNP-005)

## Results Location

### Validation Test Output

```
/tmp/netpol-validation-results/
├── 00_test_summary.txt               # Overall summary
├── 01_prerequisites_results.txt      # Prerequisites check results
├── 02_installation_results.txt       # Installation test results
├── 03_basic_functionality_results.txt # Basic functionality results
├── 04_analysis_modes_results.txt     # Analysis modes results
├── test3.1_output.txt                # Namespace with policies
├── test3.2_output.txt                # Empty namespace
├── test3.3_output.txt                # Invalid namespace
├── test4.1_security.txt              # Security mode output
├── test4.2_performance.txt           # Performance mode output
├── test4.3_compliance.txt            # Compliance mode output
└── test4.4_invalid.txt               # Invalid mode error
```

### Integration Test Output

```
/tmp/netpol-test-results/
├── 00_test_summary.txt               # Overall summary with bug verification
├── tc-vnp-001_validation_results.txt # TC-VNP-001 results
├── tc-vnp-001_plugin_output.txt      # TC-VNP-001 plugin output
├── tc-vnp-002_validation_results.txt # TC-VNP-002 results
├── tc-vnp-002_plugin_output.txt      # TC-VNP-002 plugin output
├── ...                               # (all 12 test cases)
├── tc-inv-007_validation_results.txt # TC-INV-007 results
└── tc-inv-007_plugin_output.txt      # TC-INV-007 plugin output
```

### View Results

```bash
# Validation test summary
cat /tmp/netpol-validation-results/00_test_summary.txt

# Integration test summary
cat /tmp/netpol-test-results/00_test_summary.txt

# Specific validation test
cat /tmp/netpol-validation-results/01_prerequisites_results.txt

# Specific integration test
cat /tmp/netpol-test-results/tc-vnp-002_validation_results.txt
cat /tmp/netpol-test-results/tc-vnp-002_plugin_output.txt
```

## Troubleshooting

### Cluster Connection Issues

**Problem:** "Not connected to cluster"

**Solution:**
```bash
export KUBECONFIG=/path/to/cluster.kubeconfig
oc whoami
oc get nodes
```

### Dependency Installation Issues

**Problem:** "Dependency installation failed"

**Solution:**
```bash
cd plugins/network-policy-audit
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Test Failures

**Problem:** Tests fail unexpectedly

**Solution:**
```bash
# Check test logs
cat /tmp/netpol-test-results/*.txt

# Verify cluster has sufficient resources
oc get nodes
oc get namespaces

# Clean up old test resources
./tests/integration/cleanup.sh

# Re-run tests
./tests/validation/run_all_tests.sh
```

### Namespaces Stuck in Terminating

**Problem:** Namespaces won't delete

**Solution:**
```bash
# Check namespace status
oc get ns | grep -E 'tc-|netpol-'

# Force delete
oc delete namespace <namespace> --grace-period=0 --force
```

## Test Execution Time

| Test Suite | Duration | Notes |
|------------|----------|-------|
| Validation Tests | ~20 seconds | Prerequisites, installation, functionality, modes |
| Valid Policies | ~1-2 minutes | 5 test cases with namespace creation |
| Invalid Policies | ~1-2 minutes | 7 test cases with namespace creation |
| Cleanup | ~30 seconds | Namespace deletion |
| **Total** | **~4-5 minutes** | Complete test execution |

## CI/CD Integration

### GitHub Actions Example

```yaml
name: NetworkPolicy Plugin Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: |
          cd plugins/network-policy-audit
          pip install -r requirements.txt
      
      - name: Set up cluster access
        run: |
          mkdir -p ~/.kube
          echo "${{ secrets.KUBECONFIG }}" > ~/.kube/config
      
      - name: Run validation tests
        run: |
          cd plugins/network-policy-audit/tests
          ./validation/run_all_tests.sh
      
      - name: Cleanup
        if: always()
        run: |
          cd plugins/network-policy-audit/tests
          ./integration/cleanup.sh
```

## Best Practices

### Before Running Tests

1. ✅ Verify cluster connection
2. ✅ Check cluster has available resources
3. ✅ Ensure no conflicting namespaces exist
4. ✅ Activate virtual environment
5. ✅ Confirm dependencies are installed

### During Test Execution

1. ✅ Monitor test output for errors
2. ✅ Check logs if tests fail
3. ✅ Don't interrupt long-running tests
4. ✅ Keep cluster connection active

### After Test Execution

1. ✅ Review test results
2. ✅ Save test logs if needed
3. ✅ Run cleanup script
4. ✅ Verify all namespaces deleted

## Support

For issues or questions:

1. Check this guide
2. Review test logs in `/tmp/netpol-*-results/`
3. Check plugin README: `../README.md`
4. Open issue on GitHub: https://github.com/openshift-eng/ai-helpers

---

**Last Updated:** July 3, 2026  
**Validated On:** AWS OpenShift 4.x clusters  
**Success Rate:** 100% (16/16 tests)
