#!/bin/bash
# Master Script: Run All Validation Tests
# Runs all validation tests in sequence with automatic cleanup
# Date: 2026-07-03

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="/tmp/netpol-validation-results"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================================================"
echo "NetworkPolicy Audit Plugin - Complete Validation Test Suite"
echo "======================================================================${NC}"
echo "Date: $(date)"
echo "Output Directory: ${OUTPUT_DIR}"
echo ""

# Prepare output directory
rm -rf ${OUTPUT_DIR}
mkdir -p ${OUTPUT_DIR}

# Test counter
TOTAL_TESTS=4
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run a test
run_test() {
    local test_script=$1
    local test_name=$2

    echo ""
    echo -e "${BLUE}======================================================================"
    echo "Running: ${test_name}"
    echo "======================================================================${NC}"

    if bash ${SCRIPT_DIR}/${test_script} 2>&1; then
        echo -e "${GREEN}✅ ${test_name} COMPLETED${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}❌ ${test_name} FAILED${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Run tests
echo -e "${YELLOW}Starting validation test suite...${NC}"
echo ""

# Test 1: Prerequisites
run_test "prerequisites_check.sh" "Test 1: Prerequisites Check" || true

# Test 2: Installation
run_test "installation_test.sh" "Test 2: Installation and Setup" || true

# Test 3: Basic Functionality
run_test "basic_functionality_test.sh" "Test 3: Basic Functionality" || true

# Test 4: Analysis Modes
run_test "analysis_modes_test.sh" "Test 4: Analysis Modes" || true

# Generate summary
echo ""
echo -e "${BLUE}======================================================================"
echo "TEST SUITE COMPLETE"
echo "======================================================================${NC}"

cat > ${OUTPUT_DIR}/00_test_summary.txt <<EOF
NetworkPolicy Audit Plugin - Validation Test Summary
======================================================================
Date: $(date)
Total Tests:  ${TOTAL_TESTS}
Passed:       ${PASSED_TESTS}
Failed:       ${FAILED_TESTS}
Success Rate: $(( PASSED_TESTS * 100 / TOTAL_TESTS ))%

Test Results:
  1. Prerequisites Check:       See ${OUTPUT_DIR}/01_prerequisites_results.txt
  2. Installation and Setup:    See ${OUTPUT_DIR}/02_installation_results.txt
  3. Basic Functionality:       See ${OUTPUT_DIR}/03_basic_functionality_results.txt
  4. Analysis Modes:            See ${OUTPUT_DIR}/04_analysis_modes_results.txt

Individual Test Outputs:
  - ${OUTPUT_DIR}/test3.1_output.txt (Namespace with policies)
  - ${OUTPUT_DIR}/test3.2_output.txt (Empty namespace)
  - ${OUTPUT_DIR}/test3.3_output.txt (Invalid namespace)
  - ${OUTPUT_DIR}/test4.1_security.txt (Security mode)
  - ${OUTPUT_DIR}/test4.2_performance.txt (Performance mode)
  - ${OUTPUT_DIR}/test4.3_compliance.txt (Compliance mode)
  - ${OUTPUT_DIR}/test4.4_invalid.txt (Invalid mode)

======================================================================
EOF

cat ${OUTPUT_DIR}/00_test_summary.txt

# Cleanup function
cleanup_resources() {
    echo ""
    echo -e "${YELLOW}======================================================================"
    echo "Cleaning up test resources..."
    echo "======================================================================${NC}"

    # Delete test namespaces
    echo "Deleting test namespaces..."
    oc delete namespace netpol-test-empty --ignore-not-found=true 2>/dev/null &
    oc delete namespace netpol-validation-test --ignore-not-found=true 2>/dev/null &

    # Wait a bit for deletion to start
    sleep 2

    # Check remaining test namespaces
    REMAINING=$(oc get namespaces -o name 2>/dev/null | grep -E 'netpol-test|netpol-validation' | wc -l | tr -d ' ')

    if [ "$REMAINING" -eq 0 ]; then
        echo -e "${GREEN}✅ All test namespaces cleaned up${NC}"
    else
        echo -e "${YELLOW}⚠️  ${REMAINING} test namespace(s) still deleting${NC}"
        echo "Run this command to check status:"
        echo "  oc get ns | grep netpol"
    fi

    echo ""
    echo "Test results saved to: ${OUTPUT_DIR}"
    echo ""
}

# Ask user if they want cleanup
echo ""
echo -e "${YELLOW}Cleanup test resources?${NC}"
echo "This will delete:"
echo "  - netpol-test-empty namespace"
echo "  - netpol-validation-test namespace"
echo ""
read -p "Cleanup now? (y/n) [y]: " CLEANUP
CLEANUP=${CLEANUP:-y}

if [[ "$CLEANUP" =~ ^[Yy] ]]; then
    cleanup_resources
else
    echo ""
    echo "Skipping cleanup. To cleanup later, run:"
    echo "  oc delete namespace netpol-test-empty netpol-validation-test"
fi

# Final summary
echo ""
echo -e "${BLUE}======================================================================"
echo "VALIDATION TEST SUITE SUMMARY"
echo "======================================================================${NC}"
echo "Total Tests:   ${TOTAL_TESTS}"
echo "Passed:        ${PASSED_TESTS}"
echo "Failed:        ${FAILED_TESTS}"
echo "Success Rate:  $(( PASSED_TESTS * 100 / TOTAL_TESTS ))%"
echo ""

if [ ${FAILED_TESTS} -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED${NC}"
    echo ""
    echo "The NetworkPolicy Audit Plugin is ready for production use!"
else
    echo -e "${YELLOW}⚠️  SOME TESTS FAILED (${FAILED_TESTS}/${TOTAL_TESTS})${NC}"
    echo ""
    echo "Review test results in: ${OUTPUT_DIR}"
fi

echo -e "${BLUE}======================================================================${NC}"

# Exit with appropriate code
exit ${FAILED_TESTS}
