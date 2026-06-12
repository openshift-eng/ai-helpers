#!/usr/bin/env bash
# Analyze DRA test failure and provide debugging guidance
# Usage: analyze-failure.sh <test-output-directory>

set -euo pipefail

TEST_DIR="${1:-}"

if [ -z "${TEST_DIR}" ]; then
    echo "ERROR: Missing required argument: test-output-directory"
    echo "Usage: $0 <test-output-directory>"
    echo ""
    echo "Example:"
    echo "  $0 ./dra-admin-access-20260604-202015"
    exit 1
fi

if [ ! -d "${TEST_DIR}" ]; then
    echo "ERROR: Directory not found: ${TEST_DIR}"
    exit 1
fi

echo "========================================="
echo "DRA Test Failure Analysis"
echo "========================================="
echo "Analyzing: ${TEST_DIR}"
echo ""

# Detect test type from directory name
TEST_NAME=$(basename "${TEST_DIR}" | sed -E 's/dra-([a-z-]+)-[0-9]{8}-.*/\1/')
echo "Test Type: ${TEST_NAME}"
echo ""

#==============================================
# 1. Extract test summary from output log
#==============================================
echo "=== Test Summary ==="
if [ -f "${TEST_DIR}/test-output.log" ]; then
    # Show validation summary
    sed -n '/VALIDATION SUMMARY/,/Logs:/p' "${TEST_DIR}/test-output.log" | head -20
    echo ""
else
    echo "⚠ No test-output.log found"
    echo ""
fi

#==============================================
# 2. Check for common failure patterns
#==============================================
echo "=== Failure Analysis ==="
echo ""

ISSUES_FOUND=0

# Check debug directory exists
if [ ! -d "${TEST_DIR}/debug" ]; then
    echo "⚠ No debug/ directory found"
    echo "  This test may not have collected debug info on failure"
    echo "  Try re-running the test to collect full diagnostics"
    echo ""
    exit 0
fi

# Analyze events for scheduling failures
if [ -f "${TEST_DIR}/debug/events.txt" ]; then
    echo "📋 Checking Events for Failures:"
    echo ""

    # Common failure patterns
    FAILED_SCHEDULING=$(grep -i "FailedScheduling\|failed to schedule" "${TEST_DIR}/debug/events.txt" 2>/dev/null || true)
    FAILED_ALLOCATION=$(grep -i "FailedAllocation\|allocation failed\|no devices available" "${TEST_DIR}/debug/events.txt" 2>/dev/null || true)
    FORBIDDEN_ERRORS=$(grep -i "Forbidden\|forbidden" "${TEST_DIR}/debug/events.txt" 2>/dev/null || true)

    if [ -n "${FAILED_SCHEDULING}" ]; then
        echo "  ❌ Found FailedScheduling events:"
        echo "${FAILED_SCHEDULING}" | head -5 | sed 's/^/     /'
        echo ""
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi

    if [ -n "${FAILED_ALLOCATION}" ]; then
        echo "  ❌ Found FailedAllocation events:"
        echo "${FAILED_ALLOCATION}" | head -5 | sed 's/^/     /'
        echo ""
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi

    if [ -n "${FORBIDDEN_ERRORS}" ]; then
        echo "  ❌ Found Forbidden/Permission errors:"
        echo "${FORBIDDEN_ERRORS}" | head -5 | sed 's/^/     /'
        echo ""
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
fi

# Analyze ResourceClaim status
if [ -f "${TEST_DIR}/debug/resourceclaims-status.json" ]; then
    echo "📋 Checking ResourceClaim Status:"
    echo ""

    UNALLOCATED_CLAIMS=$(jq -r '.[] | select(.allocated == null) | .name' "${TEST_DIR}/debug/resourceclaims-status.json" 2>/dev/null || true)

    if [ -n "${UNALLOCATED_CLAIMS}" ]; then
        echo "  ⚠ Unallocated ResourceClaims found:"
        echo "${UNALLOCATED_CLAIMS}" | sed 's/^/     /'
        echo ""
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi

    # Check claim conditions
    CLAIM_ERRORS=$(jq -r '.[] | select(.conditions != null) | .conditions[] | select(.status == "False" or .type == "Failed") | "\(.type): \(.message)"' "${TEST_DIR}/debug/resourceclaims-status.json" 2>/dev/null || true)

    if [ -n "${CLAIM_ERRORS}" ]; then
        echo "  ❌ ResourceClaim errors:"
        echo "${CLAIM_ERRORS}" | sed 's/^/     /'
        echo ""
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
fi

# Analyze pod status
if [ -f "${TEST_DIR}/debug/pods-status.json" ]; then
    echo "📋 Checking Pod Status:"
    echo ""

    PENDING_PODS=$(jq -r '.[] | select(.phase == "Pending") | .name' "${TEST_DIR}/debug/pods-status.json" 2>/dev/null || true)
    FAILED_PODS=$(jq -r '.[] | select(.phase == "Failed") | .name' "${TEST_DIR}/debug/pods-status.json" 2>/dev/null || true)

    if [ -n "${PENDING_PODS}" ]; then
        echo "  ⚠ Pending Pods:"
        echo "${PENDING_PODS}" | sed 's/^/     /'
        echo ""
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi

    if [ -n "${FAILED_PODS}" ]; then
        echo "  ❌ Failed Pods:"
        echo "${FAILED_PODS}" | sed 's/^/     /'
        echo ""
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
fi

# Check driver logs for errors
echo "📋 Checking Driver Logs:"
echo ""

DRIVER_LOG=$(find "${TEST_DIR}/debug" -name "*-driver-logs.txt" 2>/dev/null | head -1)
if [ -n "${DRIVER_LOG}" ]; then
    DRIVER_ERRORS=$(grep -i "error\|fatal\|panic" "${DRIVER_LOG}" 2>/dev/null | tail -5 || true)
    if [ -n "${DRIVER_ERRORS}" ]; then
        echo "  ⚠ Driver errors found:"
        echo "${DRIVER_ERRORS}" | sed 's/^/     /'
        echo ""
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    else
        echo "  ✓ No errors in driver logs"
        echo ""
    fi
else
    echo "  ℹ No driver logs found"
    echo ""
fi

#==============================================
# 3. Provide specific guidance based on test type
#==============================================
echo "=== Debugging Guidance ==="
echo ""

case "${TEST_NAME}" in
    admin-access)
        echo "Admin Access Test Debugging:"
        echo ""
        echo "1. Check namespace labels:"
        echo "   oc get namespace dra-no-admin dra-with-admin -o jsonpath='{range .items[*]}{.metadata.name}{\"\\t\"}{.metadata.labels}{\"\\n\"}{end}'"
        echo ""
        echo "2. Check ResourceClaim rejection reason:"
        echo "   cat ${TEST_DIR}/test1-result.txt"
        echo ""
        echo "3. Verify API server enforces adminAccess:"
        echo "   - Look for 'Forbidden' in ${TEST_DIR}/debug/events.txt"
        echo ""
        ;;

    partitionable)
        echo "Partitionable Devices Test Debugging:"
        echo ""
        echo "1. Check if SharedCounters exist in ResourceSlices:"
        echo "   oc get resourceslice -o jsonpath='{.items[0].spec.devices[0].basic.sharedCounters}'"
        echo ""
        echo "2. Check driver supports MIG/partitioning:"
        echo "   cat ${TEST_DIR}/debug/*-driver-logs.txt | grep -i 'mig\|partition'"
        echo ""
        echo "3. Verify CEL selectors in DeviceClass:"
        echo "   oc get deviceclass -o yaml | grep -A5 selectors"
        echo ""
        ;;

    podresources-api)
        echo "PodResources API Test Debugging:"
        echo ""
        echo "1. Check pod.status.resourceClaimStatuses field:"
        echo "   cat ${TEST_DIR}/debug/pods-status.json | jq '.[] | .resourceClaimStatuses'"
        echo ""
        echo "2. Verify kubelet API socket exists on nodes:"
        echo "   oc debug node/<node> -- chroot /host ls -la /var/lib/kubelet/pod-resources/"
        echo ""
        ;;

    prioritized-list)
        echo "Prioritized List Test Debugging:"
        echo ""
        echo "1. Check scheduler decision logs:"
        echo "   cat ${TEST_DIR}/debug/scheduler-logs.txt | grep -i 'prioritized\|preference'"
        echo ""
        echo "2. Verify DeviceClass has selector preferences:"
        echo "   oc get deviceclass -o jsonpath='{.items[0].spec.suitableNodes.preferences}'"
        echo ""
        ;;

    *)
        echo "General DRA Debugging Steps:"
        echo ""
        echo "1. Check events for failures:"
        echo "   cat ${TEST_DIR}/debug/events.txt"
        echo ""
        echo "2. Check ResourceClaim allocation:"
        echo "   cat ${TEST_DIR}/debug/resourceclaims-status.json"
        echo ""
        echo "3. Check pod describe for scheduling decisions:"
        echo "   ls ${TEST_DIR}/debug/describe-*.txt"
        echo ""
        ;;
esac

#==============================================
# 4. Summary
#==============================================
echo ""
echo "=== Summary ==="
echo ""

if [ ${ISSUES_FOUND} -eq 0 ]; then
    echo "✓ No obvious issues found in logs"
    echo "  Review ${TEST_DIR}/test-output.log for test-specific details"
else
    echo "⚠ Found ${ISSUES_FOUND} potential issue(s)"
    echo "  Review detailed logs in ${TEST_DIR}/debug/"
fi

echo ""
echo "Key Files:"
echo "  - ${TEST_DIR}/test-output.log          - Full test transcript"
echo "  - ${TEST_DIR}/debug/events.txt         - Events (most useful)"
echo "  - ${TEST_DIR}/debug/resourceclaims-status.json - Allocation status"
echo "  - ${TEST_DIR}/debug/pods-status.json   - Pod details"
echo "  - ${TEST_DIR}/debug/describe-*.txt     - Pod scheduling details"
echo ""
echo "Next Steps:"
if [ ${ISSUES_FOUND} -gt 0 ]; then
    echo "  1. Review the specific errors shown above"
    echo "  2. Check the recommended debug commands for this test type"
    echo "  3. Look at ${TEST_DIR}/debug/README.txt for more guidance"
else
    echo "  1. Review ${TEST_DIR}/test-output.log for test logic"
    echo "  2. Check if test expectations match cluster behavior"
    echo "  3. Verify feature gates are enabled (if Alpha feature)"
fi
echo ""
