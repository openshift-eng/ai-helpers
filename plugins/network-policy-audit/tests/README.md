# NetworkPolicy Audit Plugin - Test Suite

This directory contains comprehensive tests for the NetworkPolicy Audit Plugin, validated on AWS OpenShift clusters.

**Quick Links:**
- [Setup & Readiness Check](SETUP_READINESS.md) - Quick setup guide
- [Test Execution Guide](TEST_EXECUTION_GUIDE.md) - Complete execution instructions
- [Test Cases Summary](TEST_CASES_SUMMARY.md) - All test cases with results

## Test Structure

```
tests/
├── README.md                           # This file
├── TEST_EXECUTION_GUIDE.md             # Complete execution guide
├── TEST_CASES_SUMMARY.md               # All test cases with results
├── integration/                        # Integration test scripts
│   ├── run_all_integration_tests.sh   # Master integration test runner
│   ├── 01_run_tc_vnp_001.sh          # Valid: Default-deny baseline
│   ├── 02_run_tc_vnp_002.sh          # Valid: Namespace isolation
│   ├── 03_run_tc_vnp_003.sh          # Valid: External API access
│   ├── 04_run_tc_vnp_004.sh          # Valid: Three-tier application
│   ├── 05_run_tc_vnp_005.sh          # Valid: Monitoring access
│   ├── 06_run_tc_inv_001.sh          # Invalid: Missing default-deny
│   ├── 07_run_tc_inv_002.sh          # Invalid: Empty from[]
│   ├── 08_run_tc_inv_003.sh          # Invalid: Public internet ingress
│   ├── 09_run_tc_inv_004.sh          # Invalid: Public internet egress
│   ├── 10_run_tc_inv_005.sh          # Invalid: Empty to[]
│   ├── 11_run_tc_inv_006.sh          # Invalid: Missing namespace selector
│   ├── 12_run_tc_inv_007.sh          # Invalid: Missing documentation
│   └── cleanup.sh                     # Cleanup test resources
├── validation/                         # Validation test scripts
│   ├── run_all_tests.sh              # Master validation test runner
│   ├── prerequisites_check.sh         # Prerequisites verification
│   ├── installation_test.sh           # Installation verification
│   ├── basic_functionality_test.sh    # Basic functionality tests
│   └── analysis_modes_test.sh         # Analysis modes tests
└── fixtures/                          # Test fixtures (NetworkPolicy YAML)
    ├── valid/                         # Valid policy examples (future)
    └── invalid/                       # Invalid policy examples (future)
```

## Test Categories

### 1. Validation Tests (`validation/`)

Installation and functionality validation (4 test suites):
- **Prerequisites verification:** Cluster access, Python, dependencies
- **Installation testing:** Virtual environment, dependencies, imports
- **Basic functionality:** Namespace analysis, error handling
- **Analysis modes:** Security, performance, compliance modes

**Prerequisites:**
- Active OpenShift cluster
- `oc` CLI configured
- Python 3.9+
- Plugin files present

### 2. Integration Tests (`integration/`)

End-to-end NetworkPolicy validation tests (12 test cases):

**Valid Policy Tests (5 tests):**
- TC-VNP-001: Default-deny baseline
- TC-VNP-002: Namespace isolation (BUG-001 verification)
- TC-VNP-003: External API access
- TC-VNP-004: Three-tier application (BUG-001 verification)
- TC-VNP-005: Monitoring access (BUG-003 verification)

**Invalid Policy Tests (7 tests):**
- TC-INV-001: Missing default-deny
- TC-INV-002: Empty from[] in ingress
- TC-INV-003: Public internet ingress (BUG-002 verification)
- TC-INV-004: Public internet egress
- TC-INV-005: Empty to[] in egress
- TC-INV-006: Missing namespace selector
- TC-INV-007: Missing documentation

**Prerequisites:**
- Active OpenShift cluster with admin access
- Virtual environment with plugin installed
- Sufficient cluster resources for test namespaces

### 3. Test Fixtures (`fixtures/`)

Sample NetworkPolicy YAML files for testing (planned):
- Valid policies (default-deny, namespace isolation, specific allows)
- Invalid policies (overly permissive, missing selectors, public exposure)

## Setup and Readiness Check

Before running tests, ensure your environment is properly configured:

### 1. Install Plugin Dependencies

```bash
cd ai-helpers/plugins/network-policy-audit

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip3 install -r requirements.txt

# Verify installations
pip3 list | grep -E "kubernetes|pyyaml"
python3 -c "import kubernetes; print('✅ kubernetes:', kubernetes.__version__)"
python3 -c "import yaml; print('✅ pyyaml: OK')"
```

**Expected Output:**
```
✅ kubernetes: 36.0.2 (or higher)
✅ pyyaml: OK
```

### 2. Configure Cluster Access

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
system:admin (or your username)

# oc get nodes
NAME                        STATUS   ROLES    AGE   VERSION
ip-10-0-xx-xx.ec2.internal  Ready    master   1h    v1.35.5
...
```

### 3. Navigate to Tests Directory

```bash
cd ai-helpers/plugins/network-policy-audit/tests
```

**Readiness Checklist:**
- ✅ Virtual environment created and activated
- ✅ Dependencies installed (kubernetes, pyyaml)
- ✅ Python imports working
- ✅ KUBECONFIG set
- ✅ Cluster accessible (`oc whoami` works)
- ✅ In tests/ directory

## Quick Start

### Run All Tests

```bash
cd plugins/network-policy-audit/tests

# Set cluster connection
export KUBECONFIG=/path/to/cluster.kubeconfig

# Run all validation tests (4 test suites, ~25 seconds)
./validation/run_all_tests.sh

# Run all integration tests (12 test cases, ~2-3 minutes)
./integration/run_all_integration_tests.sh

# Cleanup all test resources
./integration/cleanup.sh
```

### Run Individual Validation Tests

```bash
cd validation

# Prerequisites check only
./prerequisites_check.sh

# Installation test only
./installation_test.sh

# Basic functionality test
./basic_functionality_test.sh

# Analysis modes test
./analysis_modes_test.sh
```

### Run Individual Integration Tests

```bash
cd integration

# Run all valid policy tests
./01_run_tc_vnp_001.sh
./02_run_tc_vnp_002.sh
./03_run_tc_vnp_003.sh
./04_run_tc_vnp_004.sh
./05_run_tc_vnp_005.sh

# Run all invalid policy tests
./06_run_tc_inv_001.sh
./07_run_tc_inv_002.sh
./08_run_tc_inv_003.sh
./09_run_tc_inv_004.sh
./10_run_tc_inv_005.sh
./11_run_tc_inv_006.sh
./12_run_tc_inv_007.sh
```

### Test Plugin Directly

```bash
cd plugins/network-policy-audit
source venv/bin/activate

# Test specific analysis mode
python3 scripts/netpol_analyzer_cli.py --namespace=test-ns --mode=security
```

## Test Results

All tests have been validated on AWS OpenShift clusters with **100% pass rate**:

### Validation Tests (Automated Scripts)
- **Prerequisites:** ✅ PASS (7 checks: cluster, Python, oc CLI, plugin files, etc.)
- **Installation:** ✅ PASS (8 checks: venv, dependencies, imports, help command)
- **Basic Functionality:** ✅ PASS (3 tests: namespace analysis, empty namespace, error handling)
- **Analysis Modes:** ✅ PASS (4 modes: security, performance, compliance, invalid mode)

**Success Rate:** 100% (4/4 test suites, 22 total checks)

### Integration Tests (Automated Scripts)
- **Valid Policies:** ✅ PASS (5/5 test cases)
  - TC-VNP-001: Default-deny baseline (100/100 score)
  - TC-VNP-002: Namespace isolation (100/100, BUG-001 verified)
  - TC-VNP-003: External API access (90/100, expected)
  - TC-VNP-004: Three-tier application (100/100, BUG-001 verified)
  - TC-VNP-005: Monitoring access (≥90/100, BUG-003 verified)
- **Invalid Policies:** ✅ PASS (7/7 test cases)
  - TC-INV-001: Missing default-deny (critical detected)
  - TC-INV-002: Empty from[] (critical detected)
  - TC-INV-003: Public internet ingress (BUG-002 verified)
  - TC-INV-004: Public internet egress (critical detected)
  - TC-INV-005: Empty to[] (critical detected)
  - TC-INV-006: Missing namespace selector (critical detected)
  - TC-INV-007: Missing documentation (info findings)

**Success Rate:** 100% (12/12 integration test cases)

**Overall:** 16/16 tests passing (4 validation suites + 12 integration tests)

## Test Coverage

| Feature | Coverage | Test Script |
|---------|----------|-------------|
| Cluster connection | ✅ 100% | prerequisites_check.sh |
| Python dependencies | ✅ 100% | prerequisites_check.sh, installation_test.sh |
| Virtual environment | ✅ 100% | installation_test.sh |
| Plugin imports | ✅ 100% | installation_test.sh |
| Namespace analysis | ✅ 100% | basic_functionality_test.sh |
| Empty namespace handling | ✅ 100% | basic_functionality_test.sh |
| Security mode | ✅ 100% | analysis_modes_test.sh |
| Performance mode | ✅ 100% | analysis_modes_test.sh |
| Compliance mode | ✅ 100% | analysis_modes_test.sh |
| Error handling | ✅ 100% | basic_functionality_test.sh, analysis_modes_test.sh |
| Cleanup | ✅ 100% | cleanup.sh |

**Additional Coverage** (documented in TEST_CASES_SUMMARY.md):
- Valid policies: 5 test cases (100% pass rate)
- Invalid policies: 7 test cases (100% pass rate)
- Bug fixes: 4 bugs verified (BUG-PARSER, BUG-001, BUG-002, BUG-003)

## Environment

### Tested On

**Cluster:**
- Platform: AWS (Cluster Bot)
- OpenShift Version: 4.x
- Kubernetes Version: v1.35.5
- Nodes: 3-4 (control-plane + workers)

**Client:**
- OS: macOS
- Python: 3.9+ (tested with 3.14.5)
- oc CLI: Latest compatible version

**Dependencies:**
- kubernetes: 36.0.2
- pyyaml: 6.0.3

### Test Duration

**Validation Tests:**
- Prerequisites Check: ~6 seconds
- Installation Test: ~3 seconds
- Basic Functionality: ~7 seconds
- Analysis Modes: ~4 seconds
- **Subtotal:** ~20-25 seconds

**Integration Tests:**
- Valid policies (5 tests): ~1-2 minutes
- Invalid policies (7 tests): ~1-2 minutes
- **Subtotal:** ~2-4 minutes

**Total (all tests):** ~4-5 minutes

## Cleanup

Both validation and integration tests include cleanup. To manually cleanup:

```bash
# Run comprehensive cleanup script
./integration/cleanup.sh

# Or manually delete test namespaces
# Validation test namespaces
oc delete namespace netpol-test-empty netpol-validation-test --ignore-not-found=true

# Integration test namespaces (valid policies)
oc delete namespace tc-vnp-001-valid-default-deny tc-vnp-002-backend tc-vnp-002-frontend \
  tc-vnp-003-external-api tc-vnp-004-webapp tc-vnp-005-monitoring --ignore-not-found=true

# Integration test namespaces (invalid policies)
oc delete namespace tc-inv-001-no-default-deny tc-inv-002-permissive-ingress \
  tc-inv-003-public-ingress tc-inv-004-public-egress tc-inv-005-permissive-egress \
  tc-inv-006-no-ns-selector tc-inv-007-no-docs --ignore-not-found=true

# Cleanup local test results
rm -rf /tmp/netpol-validation-results
rm -rf /tmp/netpol-test-results
```

## Troubleshooting

### Cluster Connection Issues

```bash
# Check cluster connection
oc whoami
oc get nodes

# Set KUBECONFIG
export KUBECONFIG=/path/to/cluster.kubeconfig
```

### Dependency Issues

```bash
# Recreate virtual environment
cd plugins/network-policy-audit
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Test Failures

```bash
# Check test logs
cat /tmp/netpol-test-results/*.txt
cat /tmp/netpol-validation-results/*.txt

# Re-run specific test
./integration/test_basic_functionality.sh
```

## Contributing

When adding new tests:

1. **Validation tests:** Add to `validation/` directory
2. **Fixtures:** Add sample policies to `fixtures/`
3. **Documentation:** Update this README and TEST_EXECUTION_GUIDE.md
4. **Cleanup:** Update cleanup.sh with new test namespaces

### Test Template

```bash
#!/bin/bash
# Test: <description>
# Date: <date>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="/tmp/netpol-validation-results"
TEST_ID="test-name"
PLUGIN_DIR="/Users/shbehera/Desktop/WS/10_ShiftWeek/ai-helpers/plugins/network-policy-audit"

mkdir -p ${OUTPUT_DIR}

echo "======================================================================"
echo "Test: <description>"
echo "======================================================================"

# Test execution
cd ${PLUGIN_DIR}
source venv/bin/activate
python3 scripts/netpol_analyzer_cli.py --namespace=test-ns > ${OUTPUT_DIR}/${TEST_ID}_output.txt

# Validation
if grep -q "expected-output" ${OUTPUT_DIR}/${TEST_ID}_output.txt; then
    echo "✅ PASS"
else
    echo "❌ FAIL"
    exit 1
fi

# Save results
echo "Test results saved to: ${OUTPUT_DIR}/${TEST_ID}_results.txt"
```

## References

- **Plugin README:** `../README.md`
- **Installation Guide:** `../README.md#installation`
- **Usage Guide:** `../README.md#usage`
- **Examples:** `../examples/`

## Test History

| Date | Tests | Pass Rate | Notes |
|------|-------|-----------|-------|
| 2026-07-03 | 4 validation suites (22 checks) | 100% | Automated validation scripts added |
| 2026-07-03 | 12 integration tests | 100% | Bug fixes verified (BUG-001, BUG-002, BUG-003) |
| 2026-07-01 | Initial integration tests | 100% | Parser bug fixed (BUG-PARSER) |

---

**Status:** ✅ All tests passing  
**Last Updated:** July 3, 2026  
**Validated On:** AWS OpenShift 4.x clusters
