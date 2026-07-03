# Validation Test Scripts

This directory contains validation test scripts that verify prerequisites, installation, and basic functionality of the NetworkPolicy Audit Plugin.

## Scripts Overview

### 1. run_all_tests.sh

**Purpose:** Master test runner that executes all 4 validation test suites in sequence.

**What It Does:**
- Runs all validation tests (prerequisites, installation, functionality, modes)
- Generates consolidated test summary
- Provides automatic cleanup prompts
- Reports overall pass/fail status

**Usage:**
```bash
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

**Duration:** ~20-25 seconds

---

### 2. prerequisites_check.sh

**Purpose:** Verifies all prerequisites are met before running tests.

**What It Checks (7 checks):**
1. **Cluster Access** - Connected to OpenShift cluster
2. **oc CLI** - oc command available and working
3. **Python 3** - Python version ≥3.9
4. **pip3** - pip3 available for package installation
5. **Plugin Files** - All required plugin files present
6. **Cluster Capabilities** - Can list namespaces and NetworkPolicies
7. **Disk Space** - Sufficient disk space (>100 MB free)

**Usage:**
```bash
./prerequisites_check.sh
```

**Expected Output:**
```
Cluster Access:        ✅ PASS
oc CLI:                ✅ PASS
Python 3:              ✅ PASS (3.14.5)
pip3:                  ✅ PASS
Plugin Files:          ✅ PASS
Cluster Capabilities:  ✅ PASS
Disk Space:            ✅ PASS (148 GB free)

✅ ALL PREREQUISITES MET
```

**Exit Code:**
- 0 = All checks passed
- 1 = One or more checks failed

**Duration:** ~6 seconds

**Output File:** `/tmp/netpol-validation-results/01_prerequisites_results.txt`

---

### 3. installation_test.sh

**Purpose:** Tests installation of dependencies and plugin functionality.

**What It Tests (8 checks):**
1. **Virtual Environment** - Creates/verifies venv exists
2. **Venv Activation** - Verifies Python is from venv
3. **Dependency Installation** - Installs requirements.txt
4. **kubernetes Package** - Verifies kubernetes ≥28.1.0
5. **pyyaml Package** - Verifies pyyaml ≥6.0
6. **Import kubernetes** - Tests Python import
7. **Import yaml** - Tests Python import
8. **Help Command** - Plugin help command works
9. **Cluster Connection** - Plugin can connect to cluster

**Usage:**
```bash
./installation_test.sh
```

**Expected Output:**
```
Virtual Environment:   ✅ Created and activated
Dependencies:          ✅ Installed (kubernetes 36.0.2, pyyaml 6.0.3)
Python Imports:        ✅ Working
Plugin Scripts:        ✅ Available
Help Command:          ✅ Working
Cluster Connection:    ✅ Verified

✅ INSTALLATION SUCCESSFUL
```

**Exit Code:**
- 0 = Installation successful
- 1 = Installation failed

**Duration:** ~3 seconds (or longer if installing dependencies)

**Output File:** `/tmp/netpol-validation-results/02_installation_results.txt`

**Note:** Creates venv if it doesn't exist, reuses if it does.

---

### 4. basic_functionality_test.sh

**Purpose:** Tests core plugin functionality with real namespaces.

**What It Tests (3 tests):**

#### Test 3.1: Analyze Namespace WITH NetworkPolicies
- **Namespace:** openshift-apiserver-operator (existing)
- **Policies:** 2 (allow-operator, default-deny)
- **Verifies:**
  - Header present in output
  - Statistics section shown
  - Policy count accurate
  - Findings detected

#### Test 3.2: Analyze Namespace WITHOUT NetworkPolicies
- **Namespace:** netpol-test-empty (created)
- **Policies:** 0
- **Verifies:**
  - "No NetworkPolicies found" message
  - Critical security warning shown
  - Exit code 1 (critical finding)

#### Test 3.3: Error Handling - Invalid Namespace
- **Namespace:** does-not-exist-12345 (non-existent)
- **Verifies:**
  - Graceful error handling
  - No crash
  - Appropriate message

**Usage:**
```bash
./basic_functionality_test.sh
```

**Expected Output:**
```
Test 3.1 (Namespace with policies):  ✅ PASS
Test 3.2 (Empty namespace):           ✅ PASS
Test 3.3 (Invalid namespace):         ✅ PASS

✅ Test 3 COMPLETED
```

**Exit Code:**
- 0 = All tests passed
- 1 = One or more tests failed

**Duration:** ~7 seconds

**Output Files:**
- `/tmp/netpol-validation-results/03_basic_functionality_results.txt`
- `/tmp/netpol-validation-results/test3.1_output.txt`
- `/tmp/netpol-validation-results/test3.2_output.txt`
- `/tmp/netpol-validation-results/test3.3_output.txt`

**Cleanup:** Automatically deletes test namespace `netpol-test-empty`

---

### 5. analysis_modes_test.sh

**Purpose:** Tests all three analysis modes (security, performance, compliance) and error handling.

**What It Tests (4 tests):**

#### Test 4.1: Security Mode Analysis
- **Mode:** `--mode=security`
- **Namespace:** openshift-apiserver-operator
- **Verifies:**
  - Security analysis header
  - Security score shown
  - Critical/warning sections present
  - Recommended actions shown

#### Test 4.2: Performance Mode Analysis
- **Mode:** `--mode=performance`
- **Namespace:** openshift-apiserver-operator
- **Verifies:**
  - Performance analysis header
  - No errors during execution
  - Performance-specific output

#### Test 4.3: Compliance Mode Analysis
- **Mode:** `--mode=compliance`
- **Namespace:** openshift-apiserver-operator
- **Verifies:**
  - Compliance analysis header
  - Documentation checks present
  - INFO findings for missing annotations

#### Test 4.4: Error Handling - Invalid Mode
- **Mode:** `--mode=invalid-mode`
- **Verifies:**
  - Error message shown
  - Valid mode choices listed
  - Exit with error code

**Usage:**
```bash
./analysis_modes_test.sh
```

**Expected Output:**
```
Test 4.1 (Security mode):     ✅ PASS
Test 4.2 (Performance mode):  ✅ PASS
Test 4.3 (Compliance mode):   ✅ PASS
Test 4.4 (Invalid mode):      ✅ PASS

✅ Test 4 COMPLETED
```

**Exit Code:**
- 0 = All tests passed
- 1 = One or more tests failed

**Duration:** ~4 seconds

**Output Files:**
- `/tmp/netpol-validation-results/04_analysis_modes_results.txt`
- `/tmp/netpol-validation-results/test4.1_security.txt`
- `/tmp/netpol-validation-results/test4.2_performance.txt`
- `/tmp/netpol-validation-results/test4.3_compliance.txt`
- `/tmp/netpol-validation-results/test4.4_invalid.txt`

---

## Prerequisites

Before running validation tests:

1. **Cluster Access:**
   ```bash
   export KUBECONFIG=/path/to/cluster.kubeconfig
   oc whoami  # Should succeed
   ```

2. **Plugin Directory:**
   ```bash
   cd /path/to/ai-helpers/plugins/network-policy-audit
   # Validation scripts expect plugin files at ../scripts/
   ```

3. **Python Environment:**
   ```bash
   python3 --version  # Should be ≥3.9
   pip3 --version     # Should be available
   ```

## Running Tests

### Run All Validation Tests

```bash
cd validation
./run_all_tests.sh
```

### Run Individual Tests

```bash
# Test prerequisites only
./prerequisites_check.sh

# Test installation only
./installation_test.sh

# Test basic functionality only
./basic_functionality_test.sh

# Test analysis modes only
./analysis_modes_test.sh
```

## Test Results Location

All test results are saved to `/tmp/netpol-validation-results/`:

```
/tmp/netpol-validation-results/
├── 00_test_summary.txt               # Overall summary (from run_all_tests.sh)
├── 01_prerequisites_results.txt      # Prerequisites check results
├── 02_installation_results.txt       # Installation test results
├── 03_basic_functionality_results.txt # Basic functionality results
├── 04_analysis_modes_results.txt     # Analysis modes results
├── test3.1_output.txt                # Namespace with policies output
├── test3.2_output.txt                # Empty namespace output
├── test3.3_output.txt                # Invalid namespace output
├── test4.1_security.txt              # Security mode output
├── test4.2_performance.txt           # Performance mode output
├── test4.3_compliance.txt            # Compliance mode output
└── test4.4_invalid.txt               # Invalid mode error output
```

## Expected Pass Rate

**All validation tests: 100% (4/4 test suites, 22 total checks)**

- Prerequisites: 7/7 checks ✅
- Installation: 8/8 checks ✅
- Basic Functionality: 3/3 tests ✅
- Analysis Modes: 4/4 modes ✅

## Troubleshooting

### Issue: Prerequisites check fails

**Check cluster connection:**
```bash
oc whoami
oc get nodes
```

**Verify Python version:**
```bash
python3 --version  # Should be ≥3.9
```

### Issue: Installation test fails

**Check virtual environment:**
```bash
ls -la ../venv/  # Should exist
source ../venv/bin/activate
which python3  # Should point to venv
```

**Reinstall dependencies:**
```bash
cd ..
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

### Issue: Basic functionality test fails

**Verify namespace exists:**
```bash
oc get namespace openshift-apiserver-operator
```

**Check plugin script:**
```bash
ls -la ../scripts/netpol_analyzer_cli.py
python3 ../scripts/netpol_analyzer_cli.py --help
```

### Issue: Analysis modes test fails

**Test plugin manually:**
```bash
cd ..
source venv/bin/activate
python3 scripts/netpol_analyzer_cli.py --namespace=openshift-apiserver-operator --mode=security
```

## Cleanup

Validation tests automatically clean up test namespaces. Manual cleanup:

```bash
# Delete test namespace
oc delete namespace netpol-test-empty --ignore-not-found=true

# Clean local results
rm -rf /tmp/netpol-validation-results
```

## Summary

| Script | Purpose | Checks/Tests | Duration |
|--------|---------|--------------|----------|
| run_all_tests.sh | Master runner | Runs all 4 suites | ~25s |
| prerequisites_check.sh | Prerequisites | 7 checks | ~6s |
| installation_test.sh | Installation | 8 checks | ~3s |
| basic_functionality_test.sh | Functionality | 3 tests | ~7s |
| analysis_modes_test.sh | Analysis modes | 4 modes | ~4s |

**Total:** 5 scripts, 4 test suites, 22 checks, 100% pass rate
