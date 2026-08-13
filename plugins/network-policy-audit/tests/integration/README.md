# Integration Test Scripts

This directory contains integration test scripts that validate the NetworkPolicy Audit Plugin with real NetworkPolicy configurations on OpenShift clusters.

## Scripts Overview

### Master Test Runner

#### run_all_integration_tests.sh

**Purpose:** Master test runner that executes all 12 integration test cases in sequence.

**What It Does:**
- Cleans up old test namespaces
- Runs 5 valid policy tests (TC-VNP-001 through TC-VNP-005)
- Runs 7 invalid policy tests (TC-INV-001 through TC-INV-007)
- Verifies bug fixes (BUG-001, BUG-002, BUG-003)
- Generates detailed summary with results
- Reports bug fix verification status

**Usage:**
```bash
./run_all_integration_tests.sh
```

**Expected Output:**
```
Total Tests:   12
Passed:        12
Failed:        0
Success Rate:  100%

✅ BUG-001 FIXED: TC-VNP-002 passed
✅ BUG-001 FIXED: TC-VNP-004 passed
✅ BUG-002 FIXED: TC-INV-003 shows specific message
✅ BUG-003 FIXED: TC-VNP-005 shows empty podSelector warning

✅ ALL TESTS PASSED!
```

**Duration:** ~2-4 minutes

**Exit Code:**
- 0 = All tests passed
- 1 = One or more tests failed

---

## Valid NetworkPolicy Tests

These tests verify the plugin correctly analyzes valid NetworkPolicy configurations without false positives.

### 01_run_tc_vnp_001.sh

**Test:** TC-VNP-001 - Default-Deny Baseline

**Purpose:** Verify basic default-deny ingress policy is recognized as valid.

**What It Does:**
1. Creates namespace `tc-vnp-001-valid-default-deny`
2. Applies default-deny-ingress NetworkPolicy
3. Runs plugin analysis
4. Verifies high security score (100/100)
5. Confirms no critical findings

**NetworkPolicy:**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
spec:
  podSelector: {}
  policyTypes:
  - Ingress
```

**Expected Results:**
- Security Score: 100/100
- Critical Findings: 0
- Warnings: 1 (missing egress default-deny)

**Duration:** ~10-15 seconds

---

### 02_run_tc_vnp_002.sh

**Test:** TC-VNP-002 - Specific Allow with Namespace Isolation

**Purpose:** **BUG-001 Verification** - Valid namespace+pod selectors should NOT be flagged as overly permissive.

**What It Does:**
1. Creates namespaces: `tc-vnp-002-backend`, `tc-vnp-002-frontend`
2. Labels frontend namespace: `tier=frontend`
3. Applies default-deny policy
4. Applies allow policy with namespace+pod selectors
5. Runs plugin analysis
6. Verifies NO false positives (BUG-001 fixed)

**Key NetworkPolicy:**
```yaml
spec:
  podSelector:
    matchLabels:
      tier: backend
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          tier: frontend
      podSelector:
        matchLabels:
          tier: frontend
```

**Expected Results:**
- Security Score: 100/100
- Critical Findings: 0 (BUG-001 FIXED)
- No false positives on valid selectors

**Bug Verified:** BUG-001

**Duration:** ~15-20 seconds

---

### 03_run_tc_vnp_003.sh

**Test:** TC-VNP-003 - External API Access

**Purpose:** Verify specific IP-based egress policies are correctly analyzed.

**What It Does:**
1. Creates namespace `tc-vnp-003-external-api`
2. Applies default-deny-egress policy
3. Applies allow policy for specific IP (52.1.2.3/32:443)
4. Runs plugin analysis
5. Verifies expected security score

**Key NetworkPolicy:**
```yaml
spec:
  egress:
  - to:
    - ipBlock:
        cidr: 52.1.2.3/32
    ports:
    - protocol: TCP
      port: 443
```

**Expected Results:**
- Security Score: 90/100
- Critical Findings: 1 (missing ingress default-deny - expected)

**Duration:** ~10-15 seconds

---

### 04_run_tc_vnp_004.sh

**Test:** TC-VNP-004 - Three-Tier Application

**Purpose:** **BUG-001 Verification** - Complex multi-tier policies should not trigger false positives.

**What It Does:**
1. Creates namespace `tc-vnp-004-webapp`
2. Applies default-deny policy
3. Applies allow policies for frontend, backend, database tiers
4. Runs plugin analysis
5. Verifies NO false positives on complex policies

**Policies:** 4 (default-deny + 3 allow policies)

**Expected Results:**
- Security Score: 100/100
- Critical Findings: 0 (BUG-001 FIXED)
- 4 policies detected

**Bug Verified:** BUG-001

**Duration:** ~15-20 seconds

---

### 05_run_tc_vnp_005.sh

**Test:** TC-VNP-005 - Monitoring Access Pattern

**Purpose:** **BUG-003 Verification** - Empty podSelector should trigger warning.

**What It Does:**
1. Creates namespace `tc-vnp-005-monitoring`
2. Applies policy with empty podSelector
3. Runs plugin analysis
4. Verifies "Empty podSelector" warning is shown

**Key NetworkPolicy:**
```yaml
spec:
  podSelector: {}  # Empty - applies to all pods
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: openshift-monitoring
      podSelector:
        matchLabels:
          app: prometheus
```

**Expected Results:**
- Security Score: ≥90/100
- Critical Findings: 1 (missing ingress default-deny)
- Warning: "Empty podSelector" (BUG-003 FIXED)

**Bug Verified:** BUG-003

**Duration:** ~10-15 seconds

---

## Invalid NetworkPolicy Tests

These tests verify the plugin correctly detects security issues in NetworkPolicy configurations.

### 06_run_tc_inv_001.sh

**Test:** TC-INV-001 - Missing Default-Deny

**Purpose:** Detect missing default-deny policy.

**What It Does:**
1. Creates namespace `tc-inv-001-no-default-deny`
2. Applies only allow-frontend policy (no default-deny)
3. Runs plugin analysis
4. Verifies critical finding detected

**Expected Results:**
- Critical Finding: "Missing default-deny"
- Security Score: <90
- Exit Code: 1

**Duration:** ~10 seconds

---

### 07_run_tc_inv_002.sh

**Test:** TC-INV-002 - Empty from[] in Ingress

**Purpose:** Detect overly permissive empty from[] list.

**What It Does:**
1. Creates namespace `tc-inv-002-permissive-ingress`
2. Applies policy with empty from[] (allows from ANYWHERE)
3. Runs plugin analysis
4. Verifies critical finding detected

**Key Issue:**
```yaml
spec:
  ingress:
  - from: []  # Empty - allows traffic from ALL sources
```

**Expected Results:**
- Critical Finding: "Overly permissive ingress rule"
- Message: "empty from[] list"
- Security Score: <90

**Duration:** ~8 seconds

---

### 08_run_tc_inv_003.sh

**Test:** TC-INV-003 - Public Internet Ingress (0.0.0.0/0)

**Purpose:** **BUG-002 Verification** - Should show specific "Public internet ingress allowed" message.

**What It Does:**
1. Creates namespace `tc-inv-003-public-ingress`
2. Applies policy allowing 0.0.0.0/0 ingress
3. Runs plugin analysis
4. Verifies specific public internet message (BUG-002 fixed)

**Key Issue:**
```yaml
spec:
  ingress:
  - from:
    - ipBlock:
        cidr: 0.0.0.0/0  # Public internet!
```

**Expected Results:**
- Critical Finding: Yes
- Specific Message: "Public internet ingress allowed" (BUG-002 FIXED)
- Security Score: <90

**Bug Verified:** BUG-002

**Duration:** ~8 seconds

---

### 09_run_tc_inv_004.sh

**Test:** TC-INV-004 - Public Internet Egress (0.0.0.0/0)

**Purpose:** Detect public internet egress exposure.

**What It Does:**
1. Creates namespace `tc-inv-004-public-egress`
2. Applies policy allowing 0.0.0.0/0 egress
3. Runs plugin analysis
4. Verifies critical finding detected

**Key Issue:**
```yaml
spec:
  egress:
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0  # Public internet!
```

**Expected Results:**
- Critical Finding: Yes
- Security Score: <90

**Duration:** ~8 seconds

---

### 10_run_tc_inv_005.sh

**Test:** TC-INV-005 - Empty to[] in Egress

**Purpose:** Detect overly permissive empty to[] list.

**What It Does:**
1. Creates namespace `tc-inv-005-permissive-egress`
2. Applies policy with empty to[] (allows to ANYWHERE)
3. Runs plugin analysis
4. Verifies critical finding detected

**Key Issue:**
```yaml
spec:
  egress:
  - to: []  # Empty - allows traffic to ALL destinations
```

**Expected Results:**
- Critical Finding: "Overly permissive egress rule"
- Security Score: <90

**Duration:** ~8 seconds

---

### 11_run_tc_inv_006.sh

**Test:** TC-INV-006 - Missing Namespace Selector

**Purpose:** Detect missing namespace isolation.

**What It Does:**
1. Creates namespace `tc-inv-006-no-ns-selector`
2. Applies policy with only podSelector (allows from ANY namespace)
3. Runs plugin analysis
4. Verifies critical finding detected

**Key Issue:**
```yaml
spec:
  ingress:
  - from:
    - podSelector:
        matchLabels:
          tier: frontend
    # Missing namespaceSelector - allows from ANY namespace!
```

**Expected Results:**
- Critical Finding: Yes
- Security Score: <90

**Duration:** ~8 seconds

---

### 12_run_tc_inv_007.sh

**Test:** TC-INV-007 - Missing Documentation

**Purpose:** Detect missing compliance annotations.

**What It Does:**
1. Creates namespace `tc-inv-007-no-docs`
2. Applies policies without documentation annotations
3. Runs plugin in compliance mode
4. Verifies INFO findings for missing annotations

**Key Issue:**
```yaml
metadata:
  # Missing: policy.kubernetes.io/description annotation
```

**Expected Results:**
- Mode: Compliance
- INFO Findings: "Missing documentation annotations"

**Duration:** ~8 seconds

---

## Cleanup Script

### cleanup.sh

**Purpose:** Comprehensive cleanup of all test resources.

**What It Cleans:**
- All valid test namespaces (tc-vnp-*)
- All invalid test namespaces (tc-inv-*)
- Validation test namespaces (netpol-*)
- Local test results (/tmp/netpol-*)

**Usage:**
```bash
./cleanup.sh
```

**Features:**
- User confirmation prompt
- Discovers all tc-* and netpol-* namespaces
- Waits for deletion to complete (up to 60 seconds)
- Handles stuck/terminating namespaces
- Status reporting

**Expected Output:**
```
Found 14 test namespace(s):
  - tc-vnp-001-valid-default-deny
  - tc-vnp-002-backend
  ...

Continue with cleanup? (y/n) [n]: y

✅ All test namespaces cleaned up
✅ CLEANUP COMPLETE - Cluster is clean
```

---

## Prerequisites

Before running integration tests:

1. **Cluster Access:**
   ```bash
   export KUBECONFIG=/path/to/cluster.kubeconfig
   oc whoami  # Should succeed with admin user
   ```

2. **Virtual Environment:**
   ```bash
   cd ../..  # Go to plugin root
   source venv/bin/activate
   ```

3. **Cluster Resources:**
   - Admin permissions to create/delete namespaces
   - Sufficient cluster resources for ~14 test namespaces

## Running Tests

### Run All Integration Tests

```bash
cd integration
./run_all_integration_tests.sh
```

### Run Individual Valid Policy Tests

```bash
./01_run_tc_vnp_001.sh  # Default-deny baseline
./02_run_tc_vnp_002.sh  # Namespace isolation (BUG-001)
./03_run_tc_vnp_003.sh  # External API access
./04_run_tc_vnp_004.sh  # Three-tier app (BUG-001)
./05_run_tc_vnp_005.sh  # Monitoring access (BUG-003)
```

### Run Individual Invalid Policy Tests

```bash
./06_run_tc_inv_001.sh  # Missing default-deny
./07_run_tc_inv_002.sh  # Empty from[]
./08_run_tc_inv_003.sh  # Public ingress (BUG-002)
./09_run_tc_inv_004.sh  # Public egress
./10_run_tc_inv_005.sh  # Empty to[]
./11_run_tc_inv_006.sh  # Missing namespace selector
./12_run_tc_inv_007.sh  # Missing documentation
```

## Test Results Location

All test results are saved to `/tmp/netpol-test-results/`:

```
/tmp/netpol-test-results/
├── 00_test_summary.txt               # Overall summary with bug verification
├── tc-vnp-001_validation_results.txt # TC-VNP-001 results
├── tc-vnp-001_plugin_output.txt      # TC-VNP-001 plugin output
├── tc-vnp-002_validation_results.txt # TC-VNP-002 results
├── tc-vnp-002_plugin_output.txt      # TC-VNP-002 plugin output
... (24 files total - 12 tests × 2 files each)
```

## Expected Pass Rate

**All integration tests: 100% (12/12 test cases)**

- Valid Policies: 5/5 ✅
  - TC-VNP-001: Default-deny baseline
  - TC-VNP-002: Namespace isolation (BUG-001)
  - TC-VNP-003: External API access
  - TC-VNP-004: Three-tier app (BUG-001)
  - TC-VNP-005: Monitoring access (BUG-003)

- Invalid Policies: 7/7 ✅
  - TC-INV-001: Missing default-deny
  - TC-INV-002: Empty from[]
  - TC-INV-003: Public ingress (BUG-002)
  - TC-INV-004: Public egress
  - TC-INV-005: Empty to[]
  - TC-INV-006: Missing namespace selector
  - TC-INV-007: Missing documentation

## Bug Verification Summary

All bugs verified in integration tests:

✅ **BUG-PARSER** - Parser attribute fix (`_from` vs `from_`)  
✅ **BUG-001** - False positives on valid selectors (TC-VNP-002, TC-VNP-004)  
✅ **BUG-002** - Public internet specific messages (TC-INV-003)  
✅ **BUG-003** - Empty podSelector warning (TC-VNP-005)

## Troubleshooting

### Issue: Namespace already exists

**Symptom:**
```
Error: namespace "tc-vnp-001-valid-default-deny" already exists
```

**Solution:**
```bash
./cleanup.sh  # Run cleanup first
```

### Issue: No cluster access

**Symptom:**
```
error: You must be logged in to the server (Unauthorized)
```

**Solution:**
```bash
export KUBECONFIG=/path/to/cluster.kubeconfig
oc whoami  # Verify
```

### Issue: Plugin not found

**Symptom:**
```
No such file or directory: ../scripts/netpol_analyzer_cli.py
```

**Solution:**
```bash
cd /path/to/ai-helpers/plugins/network-policy-audit
# Run tests from plugin root or tests/ directory
```

## Summary

| Category | Scripts | Tests | Duration |
|----------|---------|-------|----------|
| Master Runner | 1 | Runs all 12 | ~2-4 min |
| Valid Policies | 5 | TC-VNP-001 to 005 | ~1-2 min |
| Invalid Policies | 7 | TC-INV-001 to 007 | ~1-2 min |
| Cleanup | 1 | N/A | ~30s |
| **Total** | **14** | **12** | **~4-5 min** |

**Pass Rate:** 100% (12/12 tests)  
**Bugs Verified:** 4 (BUG-PARSER, BUG-001, BUG-002, BUG-003)
