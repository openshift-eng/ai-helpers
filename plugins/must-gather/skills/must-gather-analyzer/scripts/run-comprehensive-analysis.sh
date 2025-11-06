#!/bin/bash
# run-comprehensive-analysis.sh
#
# Automated comprehensive must-gather analysis script
# Runs all analysis scripts in systematic order and generates a consolidated report
#
# Usage: ./run-comprehensive-analysis.sh <must-gather-path> [output-file]

set -uo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <must-gather-path> [output-file]"
    echo ""
    echo "Example:"
    echo "  $0 /path/to/must-gather"
    echo "  $0 /path/to/must-gather my-report.txt"
    exit 1
fi

MG_PATH="$1"
REPORT_FILE="${2:-cluster-analysis-report-$(date +%Y%m%d-%H%M%S).txt}"

# Validate must-gather path
if [ ! -d "$MG_PATH" ]; then
    echo -e "${RED}Error: Directory not found: $MG_PATH${NC}"
    exit 1
fi

# Check if we need to find the subdirectory with hash
if [ ! -d "$MG_PATH/cluster-scoped-resources" ]; then
    echo -e "${YELLOW}Looking for must-gather subdirectory...${NC}"
    # Find subdirectory containing cluster-scoped-resources
    SUBDIR=$(find "$MG_PATH" -maxdepth 1 -type d -name "*sha256*" | head -n 1)
    if [ -n "$SUBDIR" ]; then
        echo -e "${GREEN}Found: $SUBDIR${NC}"
        MG_PATH="$SUBDIR"
    else
        echo -e "${RED}Error: Could not find must-gather data in $MG_PATH${NC}"
        echo "Expected structure: must-gather/.../cluster-scoped-resources/"
        exit 1
    fi
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}MUST-GATHER COMPREHENSIVE ANALYSIS${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Must-Gather Path: $MG_PATH"
echo "Report File: $REPORT_FILE"
echo "Analysis Start: $(date)"
echo ""

# Function to run script with error handling
run_script() {
    local script_name=$1
    local script_args=${2:-}
    local phase=$3

    echo -e "${BLUE}Running: $script_name $script_args${NC}"

    if [ -f "$SCRIPT_DIR/$script_name" ]; then
        # Run script and capture exit code, but don't exit on failure
        if python3 "$SCRIPT_DIR/$script_name" "$MG_PATH" $script_args 2>&1; then
            echo -e "${GREEN}✓ Completed: $script_name${NC}"
            return 0
        else
            local exit_code=$?
            echo -e "${YELLOW}⚠ Warning: $script_name encountered issues (exit code: $exit_code)${NC}"
            echo -e "${YELLOW}   Continuing with remaining scripts...${NC}"
            return 0  # Return success to continue with other scripts
        fi
    else
        echo -e "${RED}✗ Script not found: $script_name${NC}"
        echo -e "${YELLOW}   Continuing with remaining scripts...${NC}"
        return 0  # Return success to continue
    fi
}

# Generate report
{
    echo "================================================================================"
    echo "MUST-GATHER COMPREHENSIVE ANALYSIS REPORT"
    echo "================================================================================"
    echo "Generated: $(date)"
    echo "Must-Gather Path: $MG_PATH"
    echo ""

    echo "================================================================================"
    echo "PHASE 1: CLUSTER-LEVEL HEALTH"
    echo "================================================================================"
    echo ""

    echo "--- Cluster Version ---"
    run_script "analyze_clusterversion.py" "" "Phase 1"
    echo ""

    echo "--- Cluster Operators ---"
    run_script "analyze_clusteroperators.py" "" "Phase 1"
    echo ""

    echo "================================================================================"
    echo "PHASE 2: INFRASTRUCTURE HEALTH"
    echo "================================================================================"
    echo ""

    echo "--- Nodes ---"
    run_script "analyze_nodes.py" "" "Phase 2"
    echo ""

    echo "--- Network ---"
    run_script "analyze_network.py" "" "Phase 2"
    echo ""

    echo "--- Ingress Controllers ---"
    run_script "analyze_ingress.py" "--ingresscontrollers" "Phase 2"
    echo ""

    echo "--- Routes (Problems Only) ---"
    run_script "analyze_ingress.py" "--routes --problems-only" "Phase 2"
    echo ""

    echo "================================================================================"
    echo "PHASE 3: WORKLOAD HEALTH"
    echo "================================================================================"
    echo ""

    echo "--- Pods (Problems Only) ---"
    run_script "analyze_pods.py" "--problems-only" "Phase 3"
    echo ""

    echo "--- Storage (PVs/PVCs) ---"
    run_script "analyze_pvs.py" "" "Phase 3"
    echo ""

    echo "--- MachineConfigPools ---"
    run_script "analyze_machineconfigpools.py" "" "Phase 3"
    echo ""

    echo "================================================================================"
    echo "PHASE 4: CRITICAL COMPONENTS"
    echo "================================================================================"
    echo ""

    echo "--- etcd Cluster Health ---"
    run_script "analyze_etcd.py" "" "Phase 4"
    echo ""

    echo "--- Warning Events (Last 100) ---"
    run_script "analyze_events.py" "--type Warning --count 100" "Phase 4"
    echo ""

    echo "================================================================================"
    echo "PHASE 5: DETAILED DIAGNOSTICS (LOG ANALYSIS)"
    echo "================================================================================"
    echo ""

    echo "--- Service Logs (Errors Only) ---"
    run_script "analyze_servicelogs.py" "--errors-only" "Phase 5"
    echo ""

    echo "--- Pod Logs (Errors Only, Top 5 Patterns) ---"
    run_script "analyze_pod_logs.py" "--errors-only --top 5" "Phase 5"
    echo ""

    echo "--- Node Logs - Kubelet (Errors Only, Top 5 Patterns) ---"
    run_script "analyze_node_logs.py" "--log-type kubelet --errors-only --top 5" "Phase 5"
    echo ""

    echo "================================================================================"
    echo "ANALYSIS COMPLETE"
    echo "================================================================================"
    echo "Completed: $(date)"
    echo "Report saved to: $REPORT_FILE"
    echo ""
    echo "NEXT STEPS:"
    echo "1. Review the report for critical issues and warnings"
    echo "2. Cross-reference issues across different phases"
    echo "3. Focus on persistent error patterns with high occurrence counts"
    echo "4. Investigate specific components identified as problematic"
    echo "5. Consult detailed logs for root cause analysis"
    echo ""

} 2>&1 | tee "$REPORT_FILE"

# Print summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Analysis Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "Report saved to: ${BLUE}$REPORT_FILE${NC}"
echo ""
echo "To view the report:"
echo "  cat $REPORT_FILE"
echo ""
echo "To search for specific patterns in the report:"
echo "  grep -i 'degraded' $REPORT_FILE"
echo "  grep -i 'error' $REPORT_FILE"
echo "  grep -i '⚠️' $REPORT_FILE"
