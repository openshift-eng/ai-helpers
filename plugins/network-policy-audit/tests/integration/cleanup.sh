#!/bin/bash
# NetworkPolicy Audit Plugin - Test Cleanup Script
# Cleans up all test resources created during testing
# Date: 2026-07-03

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================================================"
echo "NetworkPolicy Audit Plugin - Test Cleanup"
echo "======================================================================${NC}"
echo "Date: $(date)"
echo ""

# Check cluster connection
if ! oc whoami &>/dev/null; then
    echo -e "${RED}❌ ERROR: Not connected to OpenShift cluster${NC}"
    echo "Please login first:"
    echo "  oc login <api-server-url>"
    echo "Or set KUBECONFIG:"
    echo "  export KUBECONFIG=<path-to-kubeconfig>"
    exit 1
fi

CLUSTER_USER=$(oc whoami 2>/dev/null)
CLUSTER_SERVER=$(oc whoami --show-server 2>/dev/null)
echo -e "${GREEN}✅ Connected to cluster${NC}"
echo "   User: ${CLUSTER_USER}"
echo "   Server: ${CLUSTER_SERVER}"
echo ""

# Define test namespaces
VALID_TEST_NAMESPACES=(
    "tc-vnp-001-valid-default-deny"
    "tc-vnp-002-backend"
    "tc-vnp-002-frontend"
    "tc-vnp-003-external-api"
    "tc-vnp-004-webapp"
    "tc-vnp-005-monitoring"
)

INVALID_TEST_NAMESPACES=(
    "tc-inv-001-no-default-deny"
    "tc-inv-002-permissive-ingress"
    "tc-inv-003-public-ingress"
    "tc-inv-004-public-egress"
    "tc-inv-005-permissive-egress"
    "tc-inv-006-no-ns-selector"
    "tc-inv-007-no-docs"
)

VALIDATION_TEST_NAMESPACES=(
    "netpol-test-empty"
    "netpol-validation-test"
)

# Combine all namespaces
ALL_TEST_NAMESPACES=("${VALID_TEST_NAMESPACES[@]}" "${INVALID_TEST_NAMESPACES[@]}" "${VALIDATION_TEST_NAMESPACES[@]}")

echo -e "${BLUE}======================================================================"
echo "Step 1: Finding test namespaces"
echo "======================================================================${NC}"

# Find existing test namespaces
EXISTING_NS=()
for ns in "${ALL_TEST_NAMESPACES[@]}"; do
    if oc get namespace "$ns" &>/dev/null; then
        EXISTING_NS+=("$ns")
    fi
done

# Also find any namespace starting with tc- or netpol-
ADDITIONAL_NS=$(oc get namespaces -o name 2>/dev/null | grep -E 'namespace/(tc-|netpol-)' | cut -d'/' -f2 || true)

if [ -n "$ADDITIONAL_NS" ]; then
    while IFS= read -r ns; do
        if [[ ! " ${EXISTING_NS[@]} " =~ " ${ns} " ]]; then
            EXISTING_NS+=("$ns")
        fi
    done <<< "$ADDITIONAL_NS"
fi

if [ ${#EXISTING_NS[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ No test namespaces found - cluster is clean${NC}"
    exit 0
fi

echo -e "${YELLOW}Found ${#EXISTING_NS[@]} test namespace(s):${NC}"
for ns in "${EXISTING_NS[@]}"; do
    STATUS=$(oc get namespace "$ns" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
    if [ "$STATUS" = "Terminating" ]; then
        echo -e "  - ${YELLOW}$ns${NC} (Status: ${YELLOW}Terminating${NC})"
    else
        echo "  - $ns (Status: $STATUS)"
    fi
done
echo ""

# Ask for confirmation
echo -e "${YELLOW}WARNING: This will delete all test namespaces and their resources.${NC}"
echo ""
read -p "Continue with cleanup? (y/n) [n]: " CONFIRM
CONFIRM=${CONFIRM:-n}

if [[ ! "$CONFIRM" =~ ^[Yy] ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo -e "${BLUE}======================================================================"
echo "Step 2: Deleting test namespaces"
echo "======================================================================${NC}"

DELETED_COUNT=0
FAILED_COUNT=0

for ns in "${EXISTING_NS[@]}"; do
    echo "Deleting namespace: $ns"
    if oc delete namespace "$ns" --wait=false 2>/dev/null; then
        DELETED_COUNT=$((DELETED_COUNT + 1))
    else
        echo -e "  ${RED}❌ Failed to delete${NC}"
        FAILED_COUNT=$((FAILED_COUNT + 1))
    fi
done

echo ""
echo -e "${GREEN}✅ Delete requests sent for ${DELETED_COUNT} namespace(s)${NC}"

if [ ${FAILED_COUNT} -gt 0 ]; then
    echo -e "${RED}❌ ${FAILED_COUNT} namespace(s) failed to delete${NC}"
fi

# Wait for deletion
echo ""
echo -e "${BLUE}======================================================================"
echo "Step 3: Waiting for deletion to complete"
echo "======================================================================${NC}"
echo "Waiting up to 60 seconds..."
echo ""

WAITED=0
MAX_WAIT=60

while [ $WAITED -lt $MAX_WAIT ]; do
    REMAINING=0
    for ns in "${EXISTING_NS[@]}"; do
        if oc get namespace "$ns" &>/dev/null; then
            REMAINING=$((REMAINING + 1))
        fi
    done

    if [ $REMAINING -eq 0 ]; then
        echo -e "${GREEN}✅ All test namespaces deleted successfully${NC}"
        echo "   Total time: ${WAITED} seconds"
        break
    fi

    if [ $((WAITED % 10)) -eq 0 ] && [ $WAITED -gt 0 ]; then
        echo "  Still waiting... (${REMAINING} namespace(s) remaining)"
    fi

    sleep 2
    WAITED=$((WAITED + 2))
done

# Check final status
REMAINING=0
for ns in "${EXISTING_NS[@]}"; do
    if oc get namespace "$ns" &>/dev/null; then
        REMAINING=$((REMAINING + 1))
    fi
done

if [ $REMAINING -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Timeout reached - ${REMAINING} namespace(s) still deleting${NC}"
    echo ""
    echo "Namespaces still in Terminating state:"
    for ns in "${EXISTING_NS[@]}"; do
        if oc get namespace "$ns" &>/dev/null; then
            echo "  - $ns"
        fi
    done
    echo ""
    echo "These namespaces may be stuck. To force delete:"
    echo "  oc delete namespace <namespace> --grace-period=0 --force"
fi

# Clean up local test results
echo ""
echo -e "${BLUE}======================================================================"
echo "Step 4: Cleaning up local test results"
echo "======================================================================${NC}"

if [ -d "/tmp/netpol-test-results" ]; then
    echo "Removing /tmp/netpol-test-results/"
    rm -rf /tmp/netpol-test-results
    echo -e "${GREEN}✅ Local test results cleaned${NC}"
else
    echo "ℹ️  No local test results found"
fi

if [ -d "/tmp/netpol-validation-results" ]; then
    echo "Removing /tmp/netpol-validation-results/"
    rm -rf /tmp/netpol-validation-results
    echo -e "${GREEN}✅ Local validation results cleaned${NC}"
else
    echo "ℹ️  No local validation results found"
fi

# Summary
echo ""
echo -e "${BLUE}======================================================================"
echo "Cleanup Summary"
echo "======================================================================${NC}"
echo "Namespaces deleted: ${DELETED_COUNT}"
echo "Failed deletions: ${FAILED_COUNT}"
echo "Final remaining: ${REMAINING}"
echo ""

if [ $REMAINING -eq 0 ]; then
    echo -e "${GREEN}✅ CLEANUP COMPLETE - Cluster is clean${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  CLEANUP INCOMPLETE - ${REMAINING} namespace(s) still present${NC}"
    echo ""
    echo "To check status:"
    echo "  oc get ns | grep -E 'tc-|netpol-'"
    echo ""
    echo "To force delete stuck namespaces:"
    echo "  oc delete namespace <namespace> --grace-period=0 --force"
    exit 1
fi
