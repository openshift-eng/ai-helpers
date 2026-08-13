#!/bin/bash
# TC-INV-002: Empty from[] in Ingress Test
set -e
TEST_ID="tc-inv-002"
NAMESPACE="${TEST_ID}-permissive-ingress"
OUTPUT_DIR="/tmp/netpol-test-results"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p ${OUTPUT_DIR}

echo "=== Starting ${TEST_ID}: Empty from[] in Ingress ==="
oc create namespace ${NAMESPACE}

cat <<EOF | oc apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-all-ingress
  namespace: ${NAMESPACE}
spec:
  podSelector:
    matchLabels:
      app: web
  policyTypes:
  - Ingress
  ingress:
  - from: []
    ports:
    - protocol: TCP
      port: 80
EOF

set +e  # Disable exit-on-error for plugin execution and validation
cd ${PLUGIN_DIR}
source venv/bin/activate
python3 scripts/netpol_analyzer_cli.py --namespace=${NAMESPACE} --mode=security > ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt 2>&1

{
    echo "=== VALIDATION RESULTS FOR ${TEST_ID} ==="
    grep -q "Overly permissive ingress rule" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: Overly permissive detected" || echo "❌ FAIL: Not detected"
    grep -q "Critical findings: 2" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: 2 critical findings" || echo "⚠️  Critical count mismatch"
    echo ""
    cat ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt
} > ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt 2>&1
set -e  # Re-enable exit-on-error

oc delete namespace ${NAMESPACE}
cat ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt
