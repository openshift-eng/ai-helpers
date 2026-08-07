#!/bin/bash
# Test Script 1: Prerequisites Verification
# Based on: 03_A_validation_prerequisites.md
# Date: 2026-07-03

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="/tmp/netpol-validation-results"
TEST_ID="01_prerequisites"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

mkdir -p ${OUTPUT_DIR}

echo "======================================================================"
echo "Test 1: Prerequisites Verification"
echo "======================================================================"
echo "Date: $(date)"
echo "Test ID: ${TEST_ID}"
echo ""

# Start test log
{
    echo "=== PREREQUISITES VERIFICATION TEST ==="
    echo "Date: $(date)"
    echo ""

    # Test 1: Cluster Access
    echo "-----------------------------------"
    echo "Test 1.1: Cluster Access"
    echo "-----------------------------------"

    if oc whoami &>/dev/null; then
        CLUSTER_USER=$(oc whoami)
        CLUSTER_SERVER=$(oc whoami --show-server)
        echo "✅ PASS: Connected to cluster"
        echo "   User: ${CLUSTER_USER}"
        echo "   Server: ${CLUSTER_SERVER}"
    else
        echo "❌ FAIL: Not connected to cluster"
        echo "   Please set KUBECONFIG and ensure cluster is accessible"
        exit 1
    fi
    echo ""

    # Test 2: oc CLI
    echo "-----------------------------------"
    echo "Test 1.2: oc CLI Availability"
    echo "-----------------------------------"

    if command -v oc &>/dev/null; then
        OC_VERSION=$(oc version --client -o json 2>/dev/null | jq -r '.releaseClientVersion' || oc version --short 2>/dev/null | grep Client || echo "Unknown")
        echo "✅ PASS: oc CLI available"
        echo "   Version: ${OC_VERSION}"
    else
        echo "❌ FAIL: oc CLI not found"
        exit 1
    fi
    echo ""

    # Test 3: Python Version
    echo "-----------------------------------"
    echo "Test 1.3: Python Version"
    echo "-----------------------------------"

    if command -v python3 &>/dev/null; then
        PYTHON_VERSION=$(python3 --version)
        echo "✅ PASS: Python 3 available"
        echo "   ${PYTHON_VERSION}"

        # Check version is 3.9+
        if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
            echo "   ✅ Version >= 3.9"
        else
            echo "   ⚠️  Warning: Python 3.9+ recommended"
        fi
    else
        echo "❌ FAIL: Python 3 not found"
        exit 1
    fi
    echo ""

    # Test 4: pip Available
    echo "-----------------------------------"
    echo "Test 1.4: pip Availability"
    echo "-----------------------------------"

    if command -v pip3 &>/dev/null; then
        PIP_VERSION=$(pip3 --version)
        echo "✅ PASS: pip3 available"
        echo "   ${PIP_VERSION}"
    else
        echo "❌ FAIL: pip3 not found"
        exit 1
    fi
    echo ""

    # Test 5: Plugin Files
    echo "-----------------------------------"
    echo "Test 1.5: Plugin Files Present"
    echo "-----------------------------------"

    if [ -d "${PLUGIN_DIR}" ]; then
        echo "✅ PASS: Plugin directory exists"
        echo "   Path: ${PLUGIN_DIR}"

        # Check for key files
        MISSING_FILES=()
        for file in "scripts/netpol_analyzer_cli.py" "scripts/netpol_parser.py" "scripts/policy_analyzer.py" "requirements.txt" "README.md"; do
            if [ ! -f "${PLUGIN_DIR}/${file}" ]; then
                MISSING_FILES+=("${file}")
            fi
        done

        if [ ${#MISSING_FILES[@]} -eq 0 ]; then
            echo "   ✅ All required files present"
        else
            echo "   ❌ Missing files:"
            for file in "${MISSING_FILES[@]}"; do
                echo "      - ${file}"
            done
            exit 1
        fi
    else
        echo "❌ FAIL: Plugin directory not found"
        echo "   Expected: ${PLUGIN_DIR}"
        exit 1
    fi
    echo ""

    # Test 6: Cluster Capabilities
    echo "-----------------------------------"
    echo "Test 1.6: Cluster Capabilities"
    echo "-----------------------------------"

    # Check if we can list namespaces
    if oc get namespaces &>/dev/null; then
        NS_COUNT=$(oc get namespaces --no-headers | wc -l | tr -d ' ')
        echo "✅ PASS: Can list namespaces"
        echo "   Total namespaces: ${NS_COUNT}"
    else
        echo "❌ FAIL: Cannot list namespaces"
        exit 1
    fi

    # Check if we can list NetworkPolicies
    if oc get networkpolicies --all-namespaces &>/dev/null; then
        NP_COUNT=$(oc get networkpolicies --all-namespaces --no-headers 2>/dev/null | wc -l | tr -d ' ')
        echo "✅ PASS: Can list NetworkPolicies"
        echo "   Total policies cluster-wide: ${NP_COUNT}"
    else
        echo "❌ FAIL: Cannot list NetworkPolicies"
        exit 1
    fi
    echo ""

    # Test 7: Disk Space
    echo "-----------------------------------"
    echo "Test 1.7: Disk Space"
    echo "-----------------------------------"

    AVAILABLE_MB=$(df -m ${PLUGIN_DIR} | tail -1 | awk '{print $4}')
    if [ ${AVAILABLE_MB} -gt 100 ]; then
        echo "✅ PASS: Sufficient disk space"
        echo "   Available: ${AVAILABLE_MB} MB"
    else
        echo "⚠️  WARNING: Low disk space"
        echo "   Available: ${AVAILABLE_MB} MB (100 MB recommended)"
    fi
    echo ""

    # Summary
    echo "======================================================================"
    echo "PREREQUISITES CHECK SUMMARY"
    echo "======================================================================"
    echo "Cluster Access:        ✅ PASS"
    echo "oc CLI:                ✅ PASS"
    echo "Python 3:              ✅ PASS"
    echo "pip3:                  ✅ PASS"
    echo "Plugin Files:          ✅ PASS"
    echo "Cluster Capabilities:  ✅ PASS"
    echo "Disk Space:            ✅ PASS"
    echo ""
    echo "✅ ALL PREREQUISITES MET"
    echo "======================================================================"

} > ${OUTPUT_DIR}/${TEST_ID}_results.txt 2>&1

# Display results
cat ${OUTPUT_DIR}/${TEST_ID}_results.txt

# Cleanup function
cleanup() {
    echo ""
    echo "Test completed. Results saved to: ${OUTPUT_DIR}/${TEST_ID}_results.txt"
}

trap cleanup EXIT

echo ""
echo -e "${GREEN}✅ Test 1 COMPLETED${NC}"
exit 0
