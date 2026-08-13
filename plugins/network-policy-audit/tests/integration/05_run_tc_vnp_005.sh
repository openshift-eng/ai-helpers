#!/bin/bash
# TC-VNP-005: Monitoring Access Pattern Test
set -e
TEST_ID="tc-vnp-005"
NAMESPACE="${TEST_ID}-monitoring"
OUTPUT_DIR="/tmp/netpol-test-results"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
mkdir -p ${OUTPUT_DIR}

echo "=== Starting ${TEST_ID}: Monitoring Access Pattern ==="
oc create namespace ${NAMESPACE}

cat <<EOF | oc apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-prometheus-scraping
  namespace: ${NAMESPACE}
  annotations:
    policy.kubernetes.io/description: "Allow Prometheus to scrape metrics from all pods"
    policy.kubernetes.io/owner: "monitoring-team@company.com"
    policy.kubernetes.io/justification: "All pods expose metrics on port 8080"
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: openshift-monitoring
      podSelector:
        matchLabels:
          app: prometheus
    ports:
    - protocol: TCP
      port: 8080
EOF

oc get networkpolicy -n ${NAMESPACE} > ${OUTPUT_DIR}/${TEST_ID}_policies.log 2>&1

set +e  # Disable exit-on-error for plugin execution and validation
cd ${PLUGIN_DIR}
source venv/bin/activate
python3 scripts/netpol_analyzer_cli.py --namespace=${NAMESPACE} --mode=security > ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt 2>&1
{
    echo "=== VALIDATION RESULTS FOR ${TEST_ID} ==="
    grep -q "Critical findings: 1" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: 1 critical (missing default-deny ingress)" || echo "⚠️  Critical count mismatch"
    grep -q "Empty podSelector" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt && echo "✅ PASS: Empty podSelector warning detected (BUG-003 FIXED)" || echo "❌ FAIL: BUG-003 NOT FIXED"
    SCORE=$(grep "Security score:" ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt | grep -o '[0-9]\+/100' | head -1)
    if [[ ${SCORE%%/*} -ge 90 ]]; then
        echo "✅ PASS: Score ≥90 (${SCORE})"
    else
        echo "⚠️  Score: ${SCORE}"
    fi
    echo ""
    cat ${OUTPUT_DIR}/${TEST_ID}_plugin_output.txt
} > ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt 2>&1
set -e  # Re-enable exit-on-error

oc delete namespace ${NAMESPACE}
cat ${OUTPUT_DIR}/${TEST_ID}_validation_results.txt
