#!/bin/bash
# Master script to run all NetworkPolicy test cases (Version 2 - with cleanup)
# Date: 2026-07-02

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
OUTPUT_DIR="/tmp/netpol-test-results"
SUMMARY_FILE="${OUTPUT_DIR}/00_test_summary.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================================================"
echo "NetworkPolicy Audit Plugin - Full Test Suite (v2)"
echo "======================================================================"
echo "Date: $(date)"
echo "Output Directory: ${OUTPUT_DIR}"
echo ""

# Step 1: Cleanup old test namespaces
echo "======================================================================"
echo "STEP 1: Cleaning up old test namespaces"
echo "======================================================================"

echo "Finding test namespaces..."
TEST_NS=$(oc get namespaces -o name 2>/dev/null | grep 'namespace/tc-' | cut -d'/' -f2 || true)

if [ -n "$TEST_NS" ]; then
    echo "Found existing test namespaces:"
    echo "$TEST_NS" | while read ns; do echo "  - $ns"; done
    echo ""
    echo "Deleting..."
    echo "$TEST_NS" | xargs -r oc delete namespace --wait=false
    echo "Waiting 10 seconds for deletion to start..."
    sleep 10
else
    echo "✅ No old test namespaces found"
fi

echo ""

# Step 2: Clean output directory
echo "======================================================================"
echo "STEP 2: Preparing output directory"
echo "======================================================================"
rm -rf ${OUTPUT_DIR}
mkdir -p ${OUTPUT_DIR}
echo "✅ Output directory ready: ${OUTPUT_DIR}"
echo ""

# Initialize summary
cat > ${SUMMARY_FILE} <<EOF
NetworkPolicy Audit Plugin - Test Execution Summary
====================================================================
Date: $(date)
Test Suite: All Test Cases (12 total)

EOF

# Test counters
TOTAL_TESTS=12
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run a test
run_test() {
    local test_script=$1
    local test_name=$(basename ${test_script} .sh)

    echo ""
    echo "======================================================================"
    echo "Running: ${test_name}"
    echo "======================================================================"

    # Run test and capture result
    if bash ${test_script} 2>&1; then
        echo -e "${GREEN}✅ ${test_name} COMPLETED${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        echo "[PASS] ${test_name}" >> ${SUMMARY_FILE}
    else
        echo -e "${RED}❌ ${test_name} FAILED${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        echo "[FAIL] ${test_name}" >> ${SUMMARY_FILE}
    fi
}

# Run all valid test cases
echo ""
echo "======================================================================"
echo "VALID NetworkPolicy Tests (Expected: High Scores, No Critical)"
echo "======================================================================"

run_test "${SCRIPT_DIR}/01_run_tc_vnp_001.sh"
run_test "${SCRIPT_DIR}/02_run_tc_vnp_002.sh"
run_test "${SCRIPT_DIR}/03_run_tc_vnp_003.sh"
run_test "${SCRIPT_DIR}/04_run_tc_vnp_004.sh"
run_test "${SCRIPT_DIR}/05_run_tc_vnp_005.sh"

# Run all invalid test cases
echo ""
echo "======================================================================"
echo "INVALID NetworkPolicy Tests (Expected: Low Scores, Critical Findings)"
echo "======================================================================"

run_test "${SCRIPT_DIR}/06_run_tc_inv_001.sh"
run_test "${SCRIPT_DIR}/07_run_tc_inv_002.sh"
run_test "${SCRIPT_DIR}/08_run_tc_inv_003.sh"
run_test "${SCRIPT_DIR}/09_run_tc_inv_004.sh"
run_test "${SCRIPT_DIR}/10_run_tc_inv_005.sh"
run_test "${SCRIPT_DIR}/11_run_tc_inv_006.sh"
run_test "${SCRIPT_DIR}/12_run_tc_inv_007.sh"

# Generate final summary
cat >> ${SUMMARY_FILE} <<EOF

====================================================================
FINAL RESULTS
====================================================================
Total Tests:   ${TOTAL_TESTS}
Passed:        ${PASSED_TESTS}
Failed:        ${FAILED_TESTS}
Success Rate:  $(( PASSED_TESTS * 100 / TOTAL_TESTS ))%

Test Results Location: ${OUTPUT_DIR}

Individual Test Results:
EOF

# List all result files
ls -1 ${OUTPUT_DIR}/*_validation_results.txt 2>/dev/null | while read file; do
    echo "  - $(basename ${file})" >> ${SUMMARY_FILE}
done

# Display summary
echo ""
echo "======================================================================"
echo "TEST SUITE COMPLETE"
echo "======================================================================"
cat ${SUMMARY_FILE}

echo ""
echo "======================================================================"
echo "Detailed Results Analysis"
echo "======================================================================"

# Analyze bug fixes
echo ""
echo "BUG FIX VERIFICATION:"
echo "--------------------------------------------------------------------"

# BUG-001: Check TC-VNP-002, TC-VNP-004
if grep -q "✅ PASS.*BUG-001 FIXED\|✅ PASS.*No critical findings (BUG-001 FIXED)\|✅ PASS: No critical findings (BUG-001 FIXED)" ${OUTPUT_DIR}/tc-vnp-002_validation_results.txt 2>/dev/null; then
    echo -e "${GREEN}✅ BUG-001 FIXED: TC-VNP-002 passed${NC}"
else
    echo -e "${RED}❌ BUG-001 NOT FIXED: TC-VNP-002 failed${NC}"
fi

if grep -q "✅ PASS.*BUG-001 FIXED\|✅ PASS.*No critical findings (BUG-001 FIXED)\|✅ PASS: No critical findings (BUG-001 FIXED)" ${OUTPUT_DIR}/tc-vnp-004_validation_results.txt 2>/dev/null; then
    echo -e "${GREEN}✅ BUG-001 FIXED: TC-VNP-004 passed${NC}"
else
    echo -e "${RED}❌ BUG-001 NOT FIXED: TC-VNP-004 failed${NC}"
fi

# BUG-002: Check TC-INV-003
if grep -q "✅ PASS.*BUG-002 FIXED\|Public internet ingress allowed" ${OUTPUT_DIR}/tc-inv-003_validation_results.txt 2>/dev/null || \
   grep -q "Public internet ingress allowed" ${OUTPUT_DIR}/tc-inv-003_plugin_output.txt 2>/dev/null; then
    echo -e "${GREEN}✅ BUG-002 FIXED: TC-INV-003 shows specific message${NC}"
else
    echo -e "${RED}❌ BUG-002 NOT FIXED: TC-INV-003 no specific message${NC}"
fi

# BUG-003: Check TC-VNP-005
if grep -q "✅ PASS.*BUG-003 FIXED\|Empty podSelector" ${OUTPUT_DIR}/tc-vnp-005_validation_results.txt 2>/dev/null || \
   grep -q "Empty podSelector" ${OUTPUT_DIR}/tc-vnp-005_plugin_output.txt 2>/dev/null; then
    echo -e "${GREEN}✅ BUG-003 FIXED: TC-VNP-005 shows empty podSelector warning${NC}"
else
    echo -e "${RED}❌ BUG-003 NOT FIXED: TC-VNP-005 no warning${NC}"
fi

echo ""
echo "======================================================================"
echo "All test results saved to: ${OUTPUT_DIR}"
echo "Summary: ${SUMMARY_FILE}"
echo "======================================================================"

# Exit with appropriate code
if [ ${FAILED_TESTS} -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED (${FAILED_TESTS}/${TOTAL_TESTS})${NC}"
    exit 1
fi
