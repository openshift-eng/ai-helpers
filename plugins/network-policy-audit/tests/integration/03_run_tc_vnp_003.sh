#!/bin/bash
# TC-VNP-003: External API Access (Specific IPs) Test
set -e
TEST_ID="tc-vnp-003"
NAMESPACE="${TEST_ID}-external-api"
OUTPUT_DIR="/tmp/netpol-test-results"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p ${OUTPUT_DIR}

echo "=== Starting ${TEST_ID}: External API Access ==="
oc create namespace ${NAMESPACE}

cat <<EOF | oc apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-egress
  namespace: ${NAMESPACE}
  annotations:
    policy.kubernetes.io/description: "Default-deny egress for zero-trust"
spec:
  podSelector: {}
  policyTypes:
  - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-payment-gateway-egress
  namespace: ${NAMESPACE}
  annotations:
    policy.kubernetes.io/description: "Allow egress to payment gateway API"
    policy.kubernetes.io/owner: "integrations-team@company.com"
spec:
  podSelector:
    matchLabels:
      app: checkout
  policyTypes:
  - Egress
  egress:
  - to:
    - ipBlock:
        cidr: 52.1.2.3/32
    ports:
    - protocol: TCP
      port: 443
EOF

oc get networkpolicy -n ${NAMESPACE} > ${OUTPUT_DIR}/${TEST_ID}_policies.log 2>&1

set +e  # Disable exit-on-error for plugin execution and validation
cd ${PLUGIN_DIR}
source venv/bin/activate
python3 scripts/netpol_analyzer_cli.py --namespace=${NAMESPACE} --mode=security > ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt 2>&1
{
    echo "=== VALIDATION RESULTS FOR ${TEST_ID} ==="
    grep -q "Total policies: 2" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: 2 policies detected" || echo "❌ FAIL: Policy count mismatch"
    grep -q "Missing default-deny ingress" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: Missing ingress default-deny detected (expected)" || echo "⚠️  Unexpected"
    grep -q "Security score: 90/100" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: Score 90/100 (expected)" || echo "⚠️  Score mismatch"
    echo ""
    cat ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt
} > ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt 2>&1
set -e  # Re-enable exit-on-error

oc delete namespace ${NAMESPACE}
cat ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt
