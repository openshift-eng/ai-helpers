#!/bin/bash
# TC-INV-006: Missing Namespace Selector Test
set -e
TEST_ID="tc-inv-006"
NAMESPACE="${TEST_ID}-no-ns-selector"
OUTPUT_DIR="/tmp/netpol-test-results"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p ${OUTPUT_DIR}

echo "=== Starting ${TEST_ID}: Missing Namespace Selector ==="
oc create namespace ${NAMESPACE}

cat <<EOF | oc apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-to-backend
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
    ports:
    - protocol: TCP
      port: 8080
EOF

set +e  # Disable exit-on-error for plugin execution and validation
cd ${PLUGIN_DIR}
source venv/bin/activate
python3 scripts/netpol_analyzer_cli.py --namespace=${NAMESPACE} --mode=security > ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt 2>&1

{
    echo "=== VALIDATION RESULTS FOR ${TEST_ID} ==="
    grep -q "Missing default-deny" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: Missing default-deny detected" || echo "⚠️  Not detected"
    SCORE=$(grep "Security score:" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt | grep -o '[0-9]\+/100' | head -1)
    echo "Score: ${SCORE}"
    echo ""
    cat ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt
} > ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt 2>&1
set -e  # Re-enable exit-on-error

oc delete namespace ${NAMESPACE}
cat ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt
