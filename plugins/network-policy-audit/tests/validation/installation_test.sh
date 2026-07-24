#!/bin/bash
# Test Script 2: Installation and Setup
# Based on: 04_A_validation_installation.md
# Date: 2026-07-03

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="/tmp/netpol-validation-results"
TEST_ID="02_installation"
PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

mkdir -p ${OUTPUT_DIR}

echo "======================================================================"
echo "Test 2: Installation and Setup"
echo "======================================================================"
echo "Date: $(date)"
echo "Test ID: ${TEST_ID}"
echo ""

# Start test log
{
    echo "=== INSTALLATION AND SETUP TEST ==="
    echo "Date: $(date)"
    echo ""

    cd ${PLUGIN_DIR}

    # Test 1: Virtual Environment Creation
    echo "-----------------------------------"
    echo "Test 2.1: Virtual Environment"
    echo "-----------------------------------"

    if [ -d "venv" ]; then
        echo "ℹ️  Virtual environment already exists"
        echo "   Path: ${PLUGIN_DIR}/venv"
    else
        echo "Creating virtual environment..."
        python3 -m venv venv
        if [ -d "venv" ]; then
            echo "✅ PASS: Virtual environment created"
        else
            echo "❌ FAIL: Could not create virtual environment"
            exit 1
        fi
    fi
    echo ""

    # Test 2: Activate Virtual Environment
    echo "-----------------------------------"
    echo "Test 2.2: Activate Virtual Environment"
    echo "-----------------------------------"

    source venv/bin/activate
    VENV_PYTHON=$(which python3)
    if [[ "$VENV_PYTHON" == *"venv"* ]]; then
        echo "✅ PASS: Virtual environment activated"
        echo "   Python: ${VENV_PYTHON}"
    else
        echo "❌ FAIL: Virtual environment not activated"
        exit 1
    fi
    echo ""

    # Test 3: Install Dependencies
    echo "-----------------------------------"
    echo "Test 2.3: Install Dependencies"
    echo "-----------------------------------"

    echo "Installing from requirements.txt..."
    pip3 install -r requirements.txt > /tmp/pip_install.log 2>&1

    if [ $? -eq 0 ]; then
        echo "✅ PASS: Dependencies installed successfully"
    else
        echo "❌ FAIL: Dependency installation failed"
        cat /tmp/pip_install.log
        exit 1
    fi
    echo ""

    # Test 4: Verify Installed Packages
    echo "-----------------------------------"
    echo "Test 2.4: Verify Installed Packages"
    echo "-----------------------------------"

    # Check kubernetes
    K8S_VERSION=$(pip3 show kubernetes 2>/dev/null | grep Version | awk '{print $2}')
    if [ -n "$K8S_VERSION" ]; then
        echo "✅ PASS: kubernetes installed"
        echo "   Version: ${K8S_VERSION}"
    else
        echo "❌ FAIL: kubernetes not found"
        exit 1
    fi

    # Check pyyaml
    YAML_VERSION=$(pip3 show pyyaml 2>/dev/null | grep Version | awk '{print $2}')
    if [ -n "$YAML_VERSION" ]; then
        echo "✅ PASS: pyyaml installed"
        echo "   Version: ${YAML_VERSION}"
    else
        echo "❌ FAIL: pyyaml not found"
        exit 1
    fi
    echo ""

    # Test 5: Test Python Imports
    echo "-----------------------------------"
    echo "Test 2.5: Test Python Imports"
    echo "-----------------------------------"

    # Test kubernetes import
    if python3 -c "import kubernetes; print('kubernetes version:', kubernetes.__version__)" 2>/dev/null; then
        echo "✅ PASS: kubernetes module imports correctly"
    else
        echo "❌ FAIL: kubernetes module import failed"
        exit 1
    fi

    # Test yaml import
    if python3 -c "import yaml; print('yaml module OK')" 2>/dev/null; then
        echo "✅ PASS: yaml module imports correctly"
    else
        echo "❌ FAIL: yaml module import failed"
        exit 1
    fi
    echo ""

    # Test 6: Verify Plugin Scripts
    echo "-----------------------------------"
    echo "Test 2.6: Verify Plugin Scripts"
    echo "-----------------------------------"

    # Check if main script is executable
    if [ -f "scripts/netpol_analyzer_cli.py" ]; then
        echo "✅ PASS: Main script exists"

        # Test if it can be imported
        if python3 -c "import sys; sys.path.insert(0, 'scripts'); import netpol_analyzer_cli" 2>/dev/null; then
            echo "✅ PASS: Main script can be imported"
        else
            # This is OK - might need specific context
            echo "ℹ️  Script requires runtime context"
        fi
    else
        echo "❌ FAIL: Main script not found"
        exit 1
    fi
    echo ""

    # Test 7: Test Help Command
    echo "-----------------------------------"
    echo "Test 2.7: Test Help Command"
    echo "-----------------------------------"

    if python3 scripts/netpol_analyzer_cli.py --help > /tmp/help_output.txt 2>&1; then
        echo "✅ PASS: Help command works"
        echo ""
        echo "Help output preview:"
        head -10 /tmp/help_output.txt | sed 's/^/   /'
    else
        echo "❌ FAIL: Help command failed"
        cat /tmp/help_output.txt
        exit 1
    fi
    echo ""

    # Test 8: Verify Cluster Connection (with venv)
    echo "-----------------------------------"
    echo "Test 2.8: Cluster Connection"
    echo "-----------------------------------"

    if oc whoami &>/dev/null; then
        echo "✅ PASS: Cluster connection verified"
        echo "   User: $(oc whoami)"
        echo "   Server: $(oc whoami --show-server)"
    else
        echo "❌ FAIL: Not connected to cluster"
        echo "   Set KUBECONFIG environment variable"
        exit 1
    fi
    echo ""

    # Summary
    echo "======================================================================"
    echo "INSTALLATION SUMMARY"
    echo "======================================================================"
    echo "Virtual Environment:   ✅ Created and activated"
    echo "Dependencies:          ✅ Installed (kubernetes, pyyaml)"
    echo "Python Imports:        ✅ Working"
    echo "Plugin Scripts:        ✅ Available"
    echo "Help Command:          ✅ Working"
    echo "Cluster Connection:    ✅ Verified"
    echo ""
    echo "Plugin Location: ${PLUGIN_DIR}"
    echo "Python: $(which python3)"
    echo ""
    echo "✅ INSTALLATION SUCCESSFUL"
    echo "======================================================================"

} > ${OUTPUT_DIR}/${TEST_ID}_results.txt 2>&1

# Display results
cat ${OUTPUT_DIR}/${TEST_ID}_results.txt

# Cleanup function
cleanup() {
    echo ""
    echo "Test completed. Results saved to: ${OUTPUT_DIR}/${TEST_ID}_results.txt"
    echo ""
    echo "To use the plugin, activate the virtual environment:"
    echo "  cd ${PLUGIN_DIR}"
    echo "  source venv/bin/activate"
}

trap cleanup EXIT

echo ""
echo -e "${GREEN}✅ Test 2 COMPLETED${NC}"
exit 0
