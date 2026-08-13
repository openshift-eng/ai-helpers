#!/bin/bash
# TC-INV-007: Missing Documentation Test
set -e
TEST_ID="tc-inv-007"
NAMESPACE="${TEST_ID}-no-docs"
OUTPUT_DIR="/tmp/netpol-test-results"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p ${OUTPUT_DIR}

echo "=== Starting ${TEST_ID}: Missing Documentation ==="
oc create namespace ${NAMESPACE}

cat <<EOF | oc apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: ${NAMESPACE}
spec:
  podSelector: {}
  policyTypes:
  - Ingress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-database
  namespace: ${NAMESPACE}
spec:
  podSelector:
    matchLabels:
      app: postgres
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: backend
EOF

cd ${PLUGIN_DIR}
source venv/bin/activate
python3 scripts/netpol_analyzer_cli.py --namespace=${NAMESPACE} --mode=compliance > ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt 2>&1

{
    echo "=== VALIDATION RESULTS FOR ${TEST_ID} ==="
    grep -q "Missing documentation annotations" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: Missing documentation detected" || echo "❌ FAIL: Not detected"
    echo ""
    cat ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt
} > ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt 2>&1

oc delete namespace ${NAMESPACE}
cat ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt
