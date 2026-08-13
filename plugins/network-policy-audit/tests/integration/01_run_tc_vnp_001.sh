#!/bin/bash
# TC-VNP-001: Default-Deny Baseline Test
# Date: 2026-07-02

set -e

TEST_ID="tc-vnp-001"
NAMESPACE="${TEST_ID}-valid-default-deny"
OUTPUT_DIR="/tmp/netpol-test-results"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Create output directory
mkdir -p ${OUTPUT_DIR}

echo "=== Starting ${TEST_ID}: Default-Deny Baseline ==="
echo "Timestamp: $(date)"

# Step 1: Create test namespace
echo "Step 1: Creating namespace ${NAMESPACE}..."
oc create namespace ${NAMESPACE} > ${OUTPUT_DIR}/${TEST_ID}_step1_create_ns.log 2>&1

# Step 2: Create default-deny ingress policy
echo "Step 2: Creating default-deny ingress policy..."
cat <<EOF | oc apply -f - > ${OUTPUT_DIR}/${TEST_ID}_step2_create_policy.log 2>&1
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: ${NAMESPACE}
  annotations:
    policy.kubernetes.io/description: "Default-deny ingress for zero-trust"
    policy.kubernetes.io/owner: "test-team@company.com"
spec:
  podSelector: {}
  policyTypes:
  - Ingress
EOF

# Step 3: Verify policy created
echo "Step 3: Verifying policy creation..."
oc get networkpolicy -n ${NAMESPACE} > ${OUTPUT_DIR}/${TEST_ID}_step3_verify_policy.log 2>&1

# Step 4: Run plugin analysis
echo "Step 4: Running plugin analysis..."
cd ${PLUGIN_DIR}
source venv/bin/activate
python3 scripts/netpol_analyzer_cli.py --namespace=${NAMESPACE} --mode=security > ${OUTPUT_DIR}/${TEST_ID}_step4_plugin_output.txt 2>&1

# Step 5: Validation checks
echo "Step 5: Running validation checks..."
{
    echo "=== VALIDATION RESULTS FOR ${TEST_ID} ==="
    echo ""

    # Check for critical findings = 0
    if grep -q "Critical findings: 0" ${OUTPUT_DIR}/${TEST_ID}_step4_plugin_output.txt; then
        echo "✅ PASS: No critical findings"
    else
        echo "❌ FAIL: Critical findings detected"
    fi

    # Check for security score = 100/100
    if grep -q "Security score: 100/100" ${OUTPUT_DIR}/${TEST_ID}_step4_plugin_output.txt; then
        echo "✅ PASS: Perfect security score (100/100)"
    else
        SCORE=$(grep "Security score:" ${OUTPUT_DIR}/${TEST_ID}_step4_plugin_output.txt || echo "NOT FOUND")
        echo "⚠️  PARTIAL: Score is ${SCORE}"
    fi

    # Display plugin output
    echo ""
    echo "=== PLUGIN OUTPUT ==="
    cat ${OUTPUT_DIR}/${TEST_ID}_step4_plugin_output.txt

} > ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt 2>&1

# Step 6: Cleanup
echo "Step 6: Cleaning up..."
oc delete namespace ${NAMESPACE} > ${OUTPUT_DIR}/${TEST_ID}_step6_cleanup.log 2>&1

# Final summary
echo ""
echo "=== ${TEST_ID} COMPLETE ==="
echo "Results saved to: ${OUTPUT_DIR}/${TEST_ID}_*.log"
echo "Validation results: ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt"
echo ""
cat ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt

exit 0
