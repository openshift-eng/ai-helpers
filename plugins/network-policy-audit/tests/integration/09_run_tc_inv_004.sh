#!/bin/bash
# TC-INV-004: CIDR 0.0.0.0/0 in Egress Test
set -e
TEST_ID="tc-inv-004"
NAMESPACE="${TEST_ID}-public-egress"
OUTPUT_DIR="/tmp/netpol-test-results"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p ${OUTPUT_DIR}

echo "=== Starting ${TEST_ID}: Public Internet Egress (0.0.0.0/0) ==="
oc create namespace ${NAMESPACE}

cat <<EOF | oc apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-internet-egress
  namespace: ${NAMESPACE}
spec:
  podSelector:
    matchLabels:
      app: worker
  policyTypes:
  - Egress
  egress:
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0
EOF

set +e  # Disable exit-on-error for plugin execution and validation
cd ${PLUGIN_DIR}
source venv/bin/activate
python3 scripts/netpol_analyzer_cli.py --namespace=${NAMESPACE} --mode=security > ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt 2>&1

{
    echo "=== VALIDATION RESULTS FOR ${TEST_ID} ==="
    grep -q "Public internet egress allowed" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: Public internet egress detected" || echo "❌ FAIL: Not detected"
    grep -A5 "Public internet egress" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt | grep -q "⚠️" && echo "✅ PASS: Correct severity (WARNING)" || echo "⚠️  Severity check"
    echo ""
    cat ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt
} > ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt 2>&1
set -e  # Re-enable exit-on-error

oc delete namespace ${NAMESPACE}
cat ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt
