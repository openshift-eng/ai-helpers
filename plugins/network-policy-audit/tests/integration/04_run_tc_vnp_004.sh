#!/bin/bash
# TC-VNP-004: Three-Tier Application Test
set -e
TEST_ID="tc-vnp-004"
NAMESPACE="${TEST_ID}-webapp"
OUTPUT_DIR="/tmp/netpol-test-results"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p ${OUTPUT_DIR}

echo "=== Starting ${TEST_ID}: Three-Tier Application ==="
oc create namespace ${NAMESPACE}

cat <<EOF | oc apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: ${NAMESPACE}
  annotations:
    policy.kubernetes.io/description: "Default-deny ingress for webapp namespace"
spec:
  podSelector: {}
  policyTypes:
  - Ingress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-ingress-to-frontend
  namespace: ${NAMESPACE}
  annotations:
    policy.kubernetes.io/description: "Allow ingress controller to reach frontend"
spec:
  podSelector:
    matchLabels:
      tier: frontend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          network.openshift.io/policy-group: ingress
    ports:
    - protocol: TCP
      port: 8080
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-backend
  namespace: ${NAMESPACE}
  annotations:
    policy.kubernetes.io/description: "Allow frontend to reach backend REST API"
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
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-backend-to-database
  namespace: ${NAMESPACE}
  annotations:
    policy.kubernetes.io/description: "Allow backend to reach PostgreSQL"
spec:
  podSelector:
    matchLabels:
      tier: database
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          tier: backend
    ports:
    - protocol: TCP
      port: 5432
EOF

oc get networkpolicy -n ${NAMESPACE} > ${OUTPUT_DIR}/${TEST_ID}_policies.log 2>&1

cd ${PLUGIN_DIR}
source venv/bin/activate
python3 scripts/netpol_analyzer_cli.py --namespace=${NAMESPACE} --mode=security > ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt 2>&1

{
    echo "=== VALIDATION RESULTS FOR ${TEST_ID} ==="
    grep -q "Total policies: 4" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: 4 policies detected" || echo "❌ FAIL: Policy count mismatch"
    grep -q "Critical findings: 0" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: No critical findings (BUG-001 FIXED)" || echo "❌ FAIL: Critical findings detected (BUG-001 NOT FIXED)"
    grep -q "100/100" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: Perfect score (100/100)" || echo "❌ FAIL: Score not 100/100"
    echo ""
    cat ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt
} > ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt 2>&1

oc delete namespace ${NAMESPACE}
cat ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt
