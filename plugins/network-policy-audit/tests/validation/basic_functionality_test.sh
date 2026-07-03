#!/bin/bash
# Test Script 3: Basic Functionality Tests
# Based on: 05_A_validation_test_scenarios.md
# Date: 2026-07-03

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="/tmp/netpol-validation-results"
TEST_ID="03_basic_functionality"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

mkdir -p ${OUTPUT_DIR}

echo "======================================================================"
echo "Test 3: Basic Functionality Tests"
echo "======================================================================"
echo "Date: $(date)"
echo "Test ID: ${TEST_ID}"
echo ""

set +e  # Don't exit on errors - we want to test error handling

# Start test log
{
    echo "=== BASIC FUNCTIONALITY TESTS ==="
    echo "Date: $(date)"
    echo ""

    cd ${PLUGIN_DIR}
    source venv/bin/activate

    # Test 3.1: Analyze Namespace WITH Policies
    echo "======================================================================"
    echo "Test 3.1: Analyze Namespace WITH NetworkPolicies"
    echo "======================================================================"

    # Find a namespace with policies
    TEST_NS=$(oc get networkpolicies --all-namespaces -o json 2>/dev/null | \
              jq -r '.items[] | select(.metadata.namespace != "openshift-ovn-kubernetes") | .metadata.namespace' | \
              head -1)

    if [ -z "$TEST_NS" ]; then
        echo "⚠️  No existing namespaces with policies found"
        echo "   Creating test namespace..."

        # Create test namespace
        oc create namespace netpol-validation-test 2>/dev/null || true
        TEST_NS="netpol-validation-test"

        # Create a sample policy
        cat <<EOF | oc apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: ${TEST_NS}
spec:
  podSelector: {}
  policyTypes:
  - Ingress
EOF

        echo "   Created test namespace: ${TEST_NS}"
    fi

    echo "Test namespace: ${TEST_NS}"
    echo ""

    # Show policies in namespace
    echo "Policies in namespace:"
    oc get networkpolicies -n ${TEST_NS}
    echo ""

    # Run analysis
    echo "Running plugin analysis..."
    python3 scripts/netpol_analyzer_cli.py --namespace=${TEST_NS} --mode=security > ${OUTPUT_DIR}/test3.1_output.txt 2>&1
    EXIT_CODE=$?
    echo "Exit code: $EXIT_CODE" >> ${OUTPUT_DIR}/test3.1_output.txt

    # Validate output
    echo "Validating output..."
    if grep -q "NetworkPolicy Security Analysis" ${OUTPUT_DIR}/test3.1_output.txt; then
        echo "✅ PASS: Header present"
    else
        echo "❌ FAIL: Header missing"
    fi

    if grep -q "STATISTICS" ${OUTPUT_DIR}/test3.1_output.txt; then
        echo "✅ PASS: Statistics section present"
    else
        echo "❌ FAIL: Statistics section missing"
    fi

    if grep -q "Total policies:" ${OUTPUT_DIR}/test3.1_output.txt; then
        echo "✅ PASS: Policy count shown"
    else
        echo "❌ FAIL: Policy count missing"
    fi

    echo ""
    echo "Sample output:"
    head -30 ${OUTPUT_DIR}/test3.1_output.txt | sed 's/^/   /'
    echo ""

    # Test 3.2: Analyze Namespace WITHOUT Policies
    echo "======================================================================"
    echo "Test 3.2: Analyze Namespace WITHOUT NetworkPolicies"
    echo "======================================================================"

    # Create empty namespace
    oc create namespace netpol-test-empty 2>/dev/null || true

    # Verify no policies
    echo "Verifying namespace has no policies..."
    oc get networkpolicies -n netpol-test-empty
    echo ""

    # Run analysis
    echo "Running plugin analysis on empty namespace..."
    python3 scripts/netpol_analyzer_cli.py --namespace=netpol-test-empty --mode=security > ${OUTPUT_DIR}/test3.2_output.txt 2>&1
    EXIT_CODE=$?
    echo "Exit code: $EXIT_CODE" >> ${OUTPUT_DIR}/test3.2_output.txt

    # Validate output
    echo "Validating output..."
    if grep -q "No NetworkPolicies found" ${OUTPUT_DIR}/test3.2_output.txt; then
        echo "✅ PASS: No policies message shown"
    else
        echo "❌ FAIL: No policies message missing"
    fi

    if grep -q "CRITICAL" ${OUTPUT_DIR}/test3.2_output.txt; then
        echo "✅ PASS: Critical security warning shown"
    else
        echo "❌ FAIL: Critical warning missing"
    fi

    if grep "Exit code: 1" ${OUTPUT_DIR}/test3.2_output.txt > /dev/null; then
        echo "✅ PASS: Correct exit code (1)"
    else
        echo "⚠️  Exit code not 1"
    fi

    echo ""
    echo "Sample output:"
    head -30 ${OUTPUT_DIR}/test3.2_output.txt | sed 's/^/   /'
    echo ""

    # Test 3.3: Invalid Namespace
    echo "======================================================================"
    echo "Test 3.3: Error Handling - Invalid Namespace"
    echo "======================================================================"

    echo "Running plugin on non-existent namespace..."
    python3 scripts/netpol_analyzer_cli.py --namespace=does-not-exist-12345 --mode=security > ${OUTPUT_DIR}/test3.3_output.txt 2>&1
    EXIT_CODE=$?
    echo "Exit code: $EXIT_CODE" >> ${OUTPUT_DIR}/test3.3_output.txt

    if grep -qE "Error|not found|Namespace .* not found" ${OUTPUT_DIR}/test3.3_output.txt; then
        echo "✅ PASS: Error message shown"
    else
        echo "⚠️  No explicit error message"
    fi

    echo ""
    echo "Output:"
    head -20 ${OUTPUT_DIR}/test3.3_output.txt | sed 's/^/   /'
    echo ""

    # Summary
    echo "======================================================================"
    echo "BASIC FUNCTIONALITY TEST SUMMARY"
    echo "======================================================================"
    echo "Test 3.1 (Namespace with policies):  Check output files for results"
    echo "Test 3.2 (Empty namespace):           Check output files for results"
    echo "Test 3.3 (Invalid namespace):         Check output files for results"
    echo ""
    echo "Output files:"
    echo "  - ${OUTPUT_DIR}/test3.1_output.txt"
    echo "  - ${OUTPUT_DIR}/test3.2_output.txt"
    echo "  - ${OUTPUT_DIR}/test3.3_output.txt"
    echo "======================================================================"

} > ${OUTPUT_DIR}/${TEST_ID}_results.txt 2>&1

# Display results
cat ${OUTPUT_DIR}/${TEST_ID}_results.txt

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up test resources..."

    # Delete test namespace (if we created it)
    oc delete namespace netpol-test-empty --ignore-not-found=true 2>/dev/null &
    # Note: Don't delete netpol-validation-test in case it has other tests

    echo ""
    echo "Test completed. Results saved to: ${OUTPUT_DIR}/${TEST_ID}_results.txt"
}

trap cleanup EXIT

echo ""
echo -e "${GREEN}✅ Test 3 COMPLETED${NC}"
exit 0
