#!/bin/bash
# TC-INV-003: CIDR 0.0.0.0/0 in Ingress Test
set -e
TEST_ID="tc-inv-003"
NAMESPACE="${TEST_ID}-public-ingress"
OUTPUT_DIR="/tmp/netpol-test-results"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p ${OUTPUT_DIR}

echo "=== Starting ${TEST_ID}: Public Internet Ingress (0.0.0.0/0) ==="
oc create namespace ${NAMESPACE}

cat <<EOF | oc apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-public-ingress
  namespace: ${NAMESPACE}
spec:
  podSelector:
    matchLabels:
      app: web
  policyTypes:
  - Ingress
  ingress:
  - from:
    - ipBlock:
        cidr: 0.0.0.0/0
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
    grep -q "Public internet ingress allowed" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: Public internet message (BUG-002 FIXED)" || echo "❌ FAIL: BUG-002 NOT FIXED"
    grep -q "0.0.0.0/0" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: CIDR shown" || echo "⚠️  CIDR not shown"
    echo ""
    cat ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt
} > ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt 2>&1
set -e  # Re-enable exit-on-error

oc delete namespace ${NAMESPACE}
cat ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt
