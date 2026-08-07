#!/bin/bash
# TC-INV-005: Empty to[] in Egress Test
set -e
TEST_ID="tc-inv-005"
NAMESPACE="${TEST_ID}-permissive-egress"
OUTPUT_DIR="/tmp/netpol-test-results"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p ${OUTPUT_DIR}

echo "=== Starting ${TEST_ID}: Empty to[] in Egress ==="
oc create namespace ${NAMESPACE}

cat <<EOF | oc apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-all-egress
  namespace: ${NAMESPACE}
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Egress
  egress:
  - to: []
EOF

set +e  # Disable exit-on-error for plugin execution and validation
cd ${PLUGIN_DIR}
source venv/bin/activate
python3 scripts/netpol_analyzer_cli.py --namespace=${NAMESPACE} --mode=security > ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt 2>&1

{
    echo "=== VALIDATION RESULTS FOR ${TEST_ID} ==="
    grep -q "Overly permissive egress rule" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: Overly permissive egress detected" || echo "❌ FAIL: Not detected"
    echo ""
    cat ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt
} > ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt 2>&1
set -e  # Re-enable exit-on-error

oc delete namespace ${NAMESPACE}
cat ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt
