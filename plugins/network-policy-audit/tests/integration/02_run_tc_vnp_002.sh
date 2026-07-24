#!/bin/bash
# TC-VNP-002: Specific Allow with Namespace Isolation Test
# Date: 2026-07-02

set -e

TEST_ID="tc-vnp-002"
NAMESPACE_BACKEND="${TEST_ID}-backend"
NAMESPACE_FRONTEND="${TEST_ID}-frontend"
OUTPUT_DIR="/tmp/netpol-test-results"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

mkdir -p ${OUTPUT_DIR}

echo "=== Starting ${TEST_ID}: Specific Allow with Namespace Isolation ==="
echo "Timestamp: $(date)"

# Step 1: Create namespaces
echo "Step 1: Creating namespaces..."
oc create namespace ${NAMESPACE_BACKEND} > ${OUTPUT_DIR}/${TEST_ID}_step1_create_backend_ns.log 2>&1
oc create namespace ${NAMESPACE_FRONTEND} > ${OUTPUT_DIR}/${TEST_ID}_step1_create_frontend_ns.log 2>&1

# Step 2: Label frontend namespace
echo "Step 2: Labeling frontend namespace..."
oc label namespace ${NAMESPACE_FRONTEND} name=${NAMESPACE_FRONTEND} > ${OUTPUT_DIR}/${TEST_ID}_step2_label_ns.log 2>&1

# Step 3: Create default-deny policy
echo "Step 3: Creating default-deny ingress policy..."
cat <<EOF | oc apply -f - > ${OUTPUT_DIR}/${TEST_ID}_step3_default_deny.log 2>&1
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: ${NAMESPACE_BACKEND}
  annotations:
    policy.kubernetes.io/description: "Default-deny baseline"
spec:
  podSelector: {}
  policyTypes:
  - Ingress
EOF

# Step 4: Create specific allow policy
echo "Step 4: Creating specific allow policy..."
cat <<EOF | oc apply -f - > ${OUTPUT_DIR}/${TEST_ID}_step4_allow_policy.log 2>&1
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-backend
  namespace: ${NAMESPACE_BACKEND}
  annotations:
    policy.kubernetes.io/description: "Allow frontend pods to reach backend on port 8080"
    policy.kubernetes.io/owner: "platform-team@company.com"
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ${NAMESPACE_FRONTEND}
      podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8080
EOF

# Step 5: Verify policies
echo "Step 5: Verifying policies..."
oc get networkpolicy -n ${NAMESPACE_BACKEND} > ${OUTPUT_DIR}/${TEST_ID}_step5_verify_policies.log 2>&1

# Step 6: Run plugin analysis
echo "Step 6: Running plugin analysis..."
cd ${PLUGIN_DIR}
source venv/bin/activate
python3 scripts/netpol_analyzer_cli.py --namespace=${NAMESPACE_BACKEND} --mode=security > ${OUTPUT_DIR}/${TEST_ID}_step6_plugin_output.txt 2>&1

# Step 7: Validation
echo "Step 7: Running validation checks..."
{
    echo "=== VALIDATION RESULTS FOR ${TEST_ID} ==="
    echo ""

    # Check for 2 policies
    if grep -q "Total policies: 2" ${OUTPUT_DIR}/${TEST_ID}_step6_plugin_output.txt; then
        echo "✅ PASS: Both policies detected"
    else
        echo "❌ FAIL: Expected 2 policies"
    fi

    # Check for critical findings = 0
    if grep -q "Critical findings: 0" ${OUTPUT_DIR}/${TEST_ID}_step6_plugin_output.txt; then
        echo "✅ PASS: No critical findings (BUG-001 FIXED)"
    else
        echo "❌ FAIL: Critical findings detected (BUG-001 NOT FIXED)"
    fi

    # Check for security score = 100/100
    if grep -q "100/100" ${OUTPUT_DIR}/${TEST_ID}_step6_plugin_output.txt; then
        echo "✅ PASS: Perfect security score (100/100)"
    else
        SCORE=$(grep "Security score:" ${OUTPUT_DIR}/${TEST_ID}_step6_plugin_output.txt || echo "NOT FOUND")
        echo "❌ FAIL: Score not 100/100. Got: ${SCORE}"
    fi

    echo ""
    echo "=== PLUGIN OUTPUT ==="
    cat ${OUTPUT_DIR}/${TEST_ID}_step6_plugin_output.txt

} > ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt 2>&1

# Step 8: Cleanup
echo "Step 8: Cleaning up..."
oc delete namespace ${NAMESPACE_BACKEND} ${NAMESPACE_FRONTEND} > ${OUTPUT_DIR}/${TEST_ID}_step8_cleanup.log 2>&1

echo ""
echo "=== ${TEST_ID} COMPLETE ==="
echo "Validation results: ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt"
echo ""
cat ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt

exit 0
