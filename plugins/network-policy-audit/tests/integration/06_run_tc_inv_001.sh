#!/bin/bash
# TC-INV-001: Missing Default-Deny Test
set -e
TEST_ID="tc-inv-001"
NAMESPACE="${TEST_ID}-no-default-deny"
OUTPUT_DIR="/tmp/netpol-test-results"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p ${OUTPUT_DIR}

echo "=== Starting ${TEST_ID}: Missing Default-Deny ==="
oc create namespace ${NAMESPACE}

cat <<EOF | oc apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend
  namespace: ${NAMESPACE}
spec:
  podSelector:
    matchLabels:
      tier: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          tier: frontend
EOF

oc get networkpolicy -n ${NAMESPACE} > ${OUTPUT_DIR}/${TEST_ID}_policies.log 2>&1

set +e  # Disable exit-on-error for plugin execution and validation
cd ${PLUGIN_DIR}
source venv/bin/activate
python3 scripts/netpol_analyzer_cli.py --namespace=${NAMESPACE} --mode=security > ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt 2>&1
echo "Exit code: $?" >> ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt

{
    echo "=== VALIDATION RESULTS FOR ${TEST_ID} ==="
    grep -q "Missing default-deny ingress" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: Missing default-deny detected" || echo "❌ FAIL: Not detected"
    SCORE=$(grep "Security score:" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt | grep -o '[0-9]\+/100' | head -1)
    if [[ ${SCORE%%/*} -lt 90 ]]; then
        echo "✅ PASS: Score <90 (${SCORE}) - Correctly flagged as invalid"
    else
        echo "❌ FAIL: Score too high (${SCORE})"
    fi
    grep -q "Exit code: 1" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: Correct exit code (1)" || echo "⚠️  Exit code not 1"
    echo ""
    cat ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt
} > ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt 2>&1
set -e  # Re-enable exit-on-error

oc delete namespace ${NAMESPACE}
cat ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt
