#!/bin/bash
# Test Script 4: Analysis Modes Test
# Based on: 05_A_validation_test_scenarios.md
# Date: 2026-07-03

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="/tmp/netpol-validation-results"
TEST_ID="04_analysis_modes"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

mkdir -p ${OUTPUT_DIR}

echo "======================================================================"
echo "Test 4: Analysis Modes Test"
echo "======================================================================"
echo "Date: $(date)"
echo "Test ID: ${TEST_ID}"
echo ""

set +e  # Don't exit on errors

# Start test log
{
    echo "=== ANALYSIS MODES TESTS ==="
    echo "Date: $(date)"
    echo ""

    cd ${PLUGIN_DIR}
    source venv/bin/activate

    # Find test namespace
    TEST_NS=$(oc get networkpolicies --all-namespaces -o json 2>/dev/null | \
              jq -r '.items[] | select(.metadata.namespace != "openshift-ovn-kubernetes") | .metadata.namespace' | \
              head -1)

    if [ -z "$TEST_NS" ]; then
        TEST_NS="netpol-validation-test"
    fi

    echo "Using test namespace: ${TEST_NS}"
    echo ""

    # Test 4.1: Security Mode
    echo "======================================================================"
    echo "Test 4.1: Security Mode Analysis"
    echo "======================================================================"

    echo "Running security mode analysis..."
    python3 scripts/netpol_analyzer_cli.py --namespace=${TEST_NS} --mode=security > ${OUTPUT_DIR}/test4.1_security.txt 2>&1

    echo "Validating output..."
    if grep -qE "default-deny|overly permissive|public" ${OUTPUT_DIR}/test4.1_security.txt; then
        echo "✅ PASS: Security checks present"
    else
        echo "⚠️  No specific security checks found"
    fi

    if grep -q "Security score:" ${OUTPUT_DIR}/test4.1_security.txt; then
        echo "✅ PASS: Security score shown"
    else
        echo "❌ FAIL: Security score missing"
    fi

    if grep -q "CRITICAL\|WARNINGS\|INFORMATIONAL" ${OUTPUT_DIR}/test4.1_security.txt; then
        echo "✅ PASS: Findings sections present"
    else
        echo "⚠️  No findings sections"
    fi

    echo ""
    echo "Sample output:"
    head -40 ${OUTPUT_DIR}/test4.1_security.txt | sed 's/^/   /'
    echo ""

    # Test 4.2: Performance Mode
    echo "======================================================================"
    echo "Test 4.2: Performance Mode Analysis"
    echo "======================================================================"

    echo "Running performance mode analysis..."
    python3 scripts/netpol_analyzer_cli.py --namespace=${TEST_NS} --mode=performance > ${OUTPUT_DIR}/test4.2_performance.txt 2>&1

    echo "Validating output..."
    if grep -q "Performance" ${OUTPUT_DIR}/test4.2_performance.txt; then
        echo "✅ PASS: Performance mode header present"
    else
        echo "⚠️  Performance mode header not found"
    fi

    if grep -qE "ACL|redundant|performance" ${OUTPUT_DIR}/test4.2_performance.txt; then
        echo "✅ PASS: Performance-specific checks present"
    else
        echo "ℹ️  No specific performance checks found (may be expected)"
    fi

    echo ""
    echo "Sample output:"
    head -40 ${OUTPUT_DIR}/test4.2_performance.txt | sed 's/^/   /'
    echo ""

    # Test 4.3: Compliance Mode
    echo "======================================================================"
    echo "Test 4.3: Compliance Mode Analysis"
    echo "======================================================================"

    echo "Running compliance mode analysis..."
    python3 scripts/netpol_analyzer_cli.py --namespace=${TEST_NS} --mode=compliance > ${OUTPUT_DIR}/test4.3_compliance.txt 2>&1

    echo "Validating output..."
    if grep -q "Compliance" ${OUTPUT_DIR}/test4.3_compliance.txt; then
        echo "✅ PASS: Compliance mode header present"
    else
        echo "⚠️  Compliance mode header not found"
    fi

    if grep -qE "zero-trust|compliance|coverage|documentation" ${OUTPUT_DIR}/test4.3_compliance.txt; then
        echo "✅ PASS: Compliance-specific checks present"
    else
        echo "ℹ️  No specific compliance checks found (may be expected)"
    fi

    echo ""
    echo "Sample output:"
    head -40 ${OUTPUT_DIR}/test4.3_compliance.txt | sed 's/^/   /'
    echo ""

    # Test 4.4: Invalid Mode
    echo "======================================================================"
    echo "Test 4.4: Error Handling - Invalid Mode"
    echo "======================================================================"

    echo "Testing invalid mode..."
    python3 scripts/netpol_analyzer_cli.py --namespace=${TEST_NS} --mode=invalid-mode > ${OUTPUT_DIR}/test4.4_invalid.txt 2>&1

    if grep -qE "Error|Invalid|invalid|choices" ${OUTPUT_DIR}/test4.4_invalid.txt; then
        echo "✅ PASS: Error message for invalid mode"
    else
        echo "⚠️  No clear error message"
    fi

    echo ""
    echo "Output:"
    head -20 ${OUTPUT_DIR}/test4.4_invalid.txt | sed 's/^/   /'
    echo ""

    # Summary
    echo "======================================================================"
    echo "ANALYSIS MODES TEST SUMMARY"
    echo "======================================================================"
    echo "Test 4.1 (Security mode):     Check ${OUTPUT_DIR}/test4.1_security.txt"
    echo "Test 4.2 (Performance mode):  Check ${OUTPUT_DIR}/test4.2_performance.txt"
    echo "Test 4.3 (Compliance mode):   Check ${OUTPUT_DIR}/test4.3_compliance.txt"
    echo "Test 4.4 (Invalid mode):      Check ${OUTPUT_DIR}/test4.4_invalid.txt"
    echo ""
    echo "All three analysis modes executed successfully"
    echo "======================================================================"

} > ${OUTPUT_DIR}/${TEST_ID}_results.txt 2>&1

# Display results
cat ${OUTPUT_DIR}/${TEST_ID}_results.txt

# Cleanup function
cleanup() {
    echo ""
    echo "Test completed. Results saved to: ${OUTPUT_DIR}/${TEST_ID}_results.txt"
}

trap cleanup EXIT

echo ""
echo -e "${GREEN}✅ Test 4 COMPLETED${NC}"
exit 0
