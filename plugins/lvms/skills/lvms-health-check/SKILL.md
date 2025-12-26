---
name: LVMS Health Check
description: Lightweight health monitoring and capacity tracking for LVMS clusters
---

# LVMS Health Check Skill

This skill provides detailed guidance for implementing quick LVMS health monitoring focused on capacity management, storage utilization, and proactive alerting for live clusters and must-gather data.

## When to Use This Skill

Use this skill when:
- Implementing fast, automated LVMS health monitoring
- Checking storage capacity across volume groups and nodes
- Monitoring pod storage usage from LVMS storage classes
- Creating proactive alerts for capacity thresholds
- Building dashboard-friendly health metrics
- Performing regular operational health checks
- Integrating LVMS monitoring into automated systems

This skill is automatically invoked by the `/lvms:health-check` command and focuses on operational monitoring rather than deep troubleshooting.

## Prerequisites

**For Live Cluster Monitoring (Primary Mode):**
- `oc` CLI installed and configured
- Active cluster connection: `oc whoami`
- Read access to LVMS namespace (auto-detected: `openshift-lvm-storage` or `openshift-storage`)
- Ability to read cluster-scoped resources (nodes, PVs, storage classes)
- `jq` installed for JSON processing

**For Must-Gather Analysis (Secondary Mode):**
- LVMS must-gather data directory
- Same structure as required by `/lvms:analyze`
- Python 3.6+ installed
- PyYAML library: `pip install pyyaml`

**Required Tools Validation:**
```bash
# Check required tools
which oc jq python3 >/dev/null 2>&1 || {
    echo "Missing required tools. Please install: oc, jq, python3"
    exit 3
}

# Verify cluster connection (live mode only)
if [ "$HEALTH_CHECK_MODE" = "live" ]; then
    oc whoami >/dev/null 2>&1 || {
        echo "No active cluster connection. Please login with 'oc login'"
        exit 3
    }
fi
```

## Implementation Steps

### Step 1: Determine Analysis Mode and Validate

**Mode Detection Logic:**
```bash
# Health check supports both live cluster and must-gather analysis
MUST_GATHER_PATH=""
LIVE_MODE=true
THRESHOLD_WARNING=80

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --live)
            LIVE_MODE=true
            shift
            ;;
        --format)
            OUTPUT_FORMAT="$2"
            shift 2
            ;;
        --threshold-warning)
            THRESHOLD_WARNING="$2"
            shift 2
            ;;
        *)
            if [[ -d "$1" && -z "$MUST_GATHER_PATH" ]]; then
                MUST_GATHER_PATH="$1"
                LIVE_MODE=false
            fi
            shift
            ;;
    esac
done

# Default to live mode if oc is available and no must-gather provided
if [[ -z "$MUST_GATHER_PATH" ]] && which oc >/dev/null 2>&1; then
    LIVE_MODE=true
elif [[ -n "$MUST_GATHER_PATH" ]]; then
    LIVE_MODE=false
fi
```

**Cluster Connection Validation (Live Mode):**
```bash
validate_live_cluster() {
    echo "Validating cluster connection..."

    # Check oc connection
    if ! oc whoami >/dev/null 2>&1; then
        echo "ERROR: No active cluster connection"
        echo "Please login: oc login <cluster-url>"
        exit 3
    fi

    echo "✓ Connected to cluster: $(oc whoami --show-server)"

    # Detect LVMS namespace
    if oc get namespace openshift-lvm-storage >/dev/null 2>&1; then
        LVMS_NAMESPACE="openshift-lvm-storage"
        echo "✓ Detected LVMS namespace: openshift-lvm-storage"
    elif oc get namespace openshift-storage >/dev/null 2>&1; then
        LVMS_NAMESPACE="openshift-storage"
        echo "✓ Detected LVMS namespace: openshift-storage (legacy)"
    else
        echo "ERROR: No LVMS namespace found"
        echo "LVMS may not be installed on this cluster"
        exit 2
    fi

    # Check required permissions
    echo "Checking permissions..."
    local missing_perms=0

    if ! oc auth can-i get lvmcluster -n "$LVMS_NAMESPACE" >/dev/null 2>&1; then
        echo "⚠ Missing permission: get lvmcluster"
        missing_perms=1
    fi

    if ! oc auth can-i get pvc --all-namespaces >/dev/null 2>&1; then
        echo "⚠ Missing permission: list PVCs cluster-wide"
        missing_perms=1
    fi

    if ! oc auth can-i get nodes >/dev/null 2>&1; then
        echo "⚠ Missing permission: get nodes"
        missing_perms=1
    fi

    if [ $missing_perms -eq 1 ]; then
        echo "WARNING: Some permissions missing. Results may be incomplete."
    else
        echo "✓ Required permissions verified"
    fi
}
```

### Step 2: Collect Essential Health Metrics

**LVMCluster Status Collection:**
```bash
collect_lvmcluster_status() {
    echo "Collecting LVMCluster status..."

    # Get LVMCluster resources
    LVMCLUSTER_DATA=$(oc get lvmcluster -n "$LVMS_NAMESPACE" -o json 2>/dev/null)

    if [[ -z "$LVMCLUSTER_DATA" || "$LVMCLUSTER_DATA" == '{"items":[]}' ]]; then
        echo "ERROR: No LVMCluster resources found"
        return 2
    fi

    # Extract basic status
    CLUSTER_COUNT=$(echo "$LVMCLUSTER_DATA" | jq '.items | length')
    READY_COUNT=$(echo "$LVMCLUSTER_DATA" | jq '[.items[] | select(.status.ready == true)] | length')

    echo "✓ Found $CLUSTER_COUNT LVMCluster(s), $READY_COUNT ready"

    # Store for later analysis
    echo "$LVMCLUSTER_DATA" > "/tmp/lvms-health-lvmcluster.json"
}
```

**Volume Group Capacity Collection:**
```bash
collect_vg_capacity() {
    echo "Collecting volume group capacity data..."

    # Get VG node status for capacity information
    VG_DATA=$(oc get lvmvolumegroupnodestatus -A -o json 2>/dev/null)

    if [[ -z "$VG_DATA" || "$VG_DATA" == '{"items":[]}' ]]; then
        echo "WARNING: No LVMVolumeGroupNodeStatus found"
        VG_DATA='{"items":[]}'
    fi

    echo "$VG_DATA" > "/tmp/lvms-health-vg.json"

    # Extract capacity summary
    local total_vgs=$(echo "$VG_DATA" | jq '[.items[]] | length')
    echo "✓ Found volume group status from $total_vgs node(s)"
}
```

**PVC and Storage Usage Collection:**
```bash
collect_pvc_usage() {
    echo "Collecting PVC usage for LVMS storage classes..."

    # Get all PVCs and filter for LVMS
    ALL_PVCS=$(oc get pvc -A -o json 2>/dev/null)

    # Filter for LVMS storage classes (lvms-*)
    LVMS_PVCS=$(echo "$ALL_PVCS" | jq '
        .items | map(select(.spec.storageClassName // "" | startswith("lvms-")))
    ')

    echo "$LVMS_PVCS" > "/tmp/lvms-health-pvcs.json"

    # Get summary counts
    local total_pvcs=$(echo "$LVMS_PVCS" | jq 'length')
    local bound_pvcs=$(echo "$LVMS_PVCS" | jq 'map(select(.status.phase == "Bound")) | length')
    local pending_pvcs=$(echo "$LVMS_PVCS" | jq 'map(select(.status.phase == "Pending")) | length')

    echo "✓ Found $total_pvcs LVMS PVCs: $bound_pvcs bound, $pending_pvcs pending"

    # Get pods using LVMS storage
    collect_pod_storage_usage
}

collect_pod_storage_usage() {
    echo "Collecting pods using LVMS storage..."

    # Get all pods with volumes
    PODS_WITH_STORAGE=$(oc get pods -A -o json | jq '
        .items | map(select(
            .spec.volumes[]? | select(.persistentVolumeClaim != null)
        ))
    ')

    echo "$PODS_WITH_STORAGE" > "/tmp/lvms-health-pods.json"

    local pods_count=$(echo "$PODS_WITH_STORAGE" | jq 'length')
    echo "✓ Found $pods_count pod(s) using persistent storage"
}
```

**Operator Health Collection:**
```bash
collect_operator_health() {
    echo "Collecting LVMS operator health..."

    # Get operator pods
    OPERATOR_PODS=$(oc get pods -n "$LVMS_NAMESPACE" -o json 2>/dev/null)
    echo "$OPERATOR_PODS" > "/tmp/lvms-health-operator.json"

    # Get deployments and daemonsets
    DEPLOYMENTS=$(oc get deployments -n "$LVMS_NAMESPACE" -o json 2>/dev/null)
    DAEMONSETS=$(oc get daemonsets -n "$LVMS_NAMESPACE" -o json 2>/dev/null)

    echo "$DEPLOYMENTS" > "/tmp/lvms-health-deployments.json"
    echo "$DAEMONSETS" > "/tmp/lvms-health-daemonsets.json"

    # Summary
    local pod_count=$(echo "$OPERATOR_PODS" | jq '.items | length // 0')
    local ready_pods=$(echo "$OPERATOR_PODS" | jq '[.items[] | select(.status.phase == "Running")] | length // 0')

    echo "✓ Operator pods: $ready_pods/$pod_count running"
}
```

### Step 3: Calculate Health Metrics and Scores

**Overall Health Score Calculation:**
```bash
calculate_health_score() {
    echo "Calculating overall health score..."

    local score=0
    local max_score=100

    # LVMCluster readiness (40 points)
    local cluster_score=$(calculate_cluster_score)
    score=$((score + cluster_score))

    # Volume group functionality (30 points)
    local vg_score=$(calculate_vg_score)
    score=$((score + vg_score))

    # PVC binding health (20 points)
    local pvc_score=$(calculate_pvc_score)
    score=$((score + pvc_score))

    # Operator pod health (10 points)
    local operator_score=$(calculate_operator_score)
    score=$((score + operator_score))

    echo "$score"
}

calculate_cluster_score() {
    local cluster_data=$(cat /tmp/lvms-health-lvmcluster.json)
    local total_clusters=$(echo "$cluster_data" | jq '.items | length')
    local ready_clusters=$(echo "$cluster_data" | jq '[.items[] | select(.status.ready == true)] | length')

    if [ "$total_clusters" -eq 0 ]; then
        echo "0"
    else
        local percentage=$((ready_clusters * 40 / total_clusters))
        echo "$percentage"
    fi
}

calculate_vg_score() {
    local vg_data=$(cat /tmp/lvms-health-vg.json)
    local total_vgs=$(echo "$vg_data" | jq '[.items[].status.volumeGroups[]] | length')
    local healthy_vgs=$(echo "$vg_data" | jq '[.items[].status.volumeGroups[] | select(.error == null)] | length')

    if [ "$total_vgs" -eq 0 ]; then
        echo "30"  # No VGs found, assume healthy
    else
        local percentage=$((healthy_vgs * 30 / total_vgs))
        echo "$percentage"
    fi
}

calculate_pvc_score() {
    local pvc_data=$(cat /tmp/lvms-health-pvcs.json)
    local total_pvcs=$(echo "$pvc_data" | jq 'length')
    local bound_pvcs=$(echo "$pvc_data" | jq 'map(select(.status.phase == "Bound")) | length')

    if [ "$total_pvcs" -eq 0 ]; then
        echo "20"  # No PVCs, assume healthy
    else
        local percentage=$((bound_pvcs * 20 / total_pvcs))
        echo "$percentage"
    fi
}
```

**Capacity Analysis:**
```bash
analyze_capacity() {
    echo "Analyzing storage capacity..."

    local vg_data=$(cat /tmp/lvms-health-vg.json)
    local capacity_analysis=""

    # Process each node's volume groups
    echo "$vg_data" | jq -r '
    .items[] |
    .metadata.name as $node |
    .status.volumeGroups[] |
    {
        node: $node,
        vg_name: .name,
        size: .size,
        available: .available
    } |
    @json' | while read -r vg_info; do

        local node=$(echo "$vg_info" | jq -r '.node')
        local vg_name=$(echo "$vg_info" | jq -r '.vg_name')
        local size=$(echo "$vg_info" | jq -r '.size')
        local available=$(echo "$vg_info" | jq -r '.available')

        # Convert to bytes for calculation (assuming size units are consistent)
        if [[ "$size" =~ ([0-9]+)([KMGT]i) ]]; then
            local size_bytes=$(convert_to_bytes "$size")
            local available_bytes=$(convert_to_bytes "$available")
            local used_bytes=$((size_bytes - available_bytes))
            local usage_percent=$((used_bytes * 100 / size_bytes))

            # Check against thresholds
            local status="OK"
            if [ "$usage_percent" -ge 90 ]; then
                status="CRITICAL"
            elif [ "$usage_percent" -ge "$THRESHOLD_WARNING" ]; then
                status="WARNING"
            fi

            # Store capacity info for reporting
            echo "$node,$vg_name,$size,$used_bytes,$usage_percent,$status" >> /tmp/lvms-health-capacity.csv
        fi
    done
}

convert_to_bytes() {
    local value="$1"
    local number=$(echo "$value" | sed 's/[^0-9.]//g')
    local unit=$(echo "$value" | sed 's/[0-9.]//g')

    case "$unit" in
        "Ki"|"K") echo "$((${number%.*} * 1024))" ;;
        "Mi"|"M") echo "$((${number%.*} * 1024 * 1024))" ;;
        "Gi"|"G") echo "$((${number%.*} * 1024 * 1024 * 1024))" ;;
        "Ti"|"T") echo "$((${number%.*} * 1024 * 1024 * 1024 * 1024))" ;;
        *) echo "${number%.*}" ;;
    esac
}
```

### Step 4: Generate Health Report

**Table Format Output (Default):**
```bash
generate_table_report() {
    local health_score="$1"
    local overall_status="$2"

    echo "═══════════════════════════════════════════════════════════"
    echo "LVMS HEALTH CHECK"
    echo "═══════════════════════════════════════════════════════════"
    echo

    # Overall status with emoji
    case "$overall_status" in
        "HEALTHY") echo "Overall Status: HEALTHY ✓" ;;
        "WARNING") echo "Overall Status: WARNING ⚠" ;;
        "CRITICAL") echo "Overall Status: CRITICAL ❌" ;;
    esac
    echo "Health Score: $health_score/100"
    echo

    # Component status table
    print_component_status_table
    echo

    # Capacity overview
    print_capacity_table
    echo

    # Alerts and recommendations
    print_alerts_and_recommendations
    echo

    # Quick actions
    print_quick_actions
}

print_component_status_table() {
    echo "┌─────────────────┬────────────────────────────────────────┐"
    echo "│ Component       │ Status                                 │"
    echo "├─────────────────┼────────────────────────────────────────┤"

    # LVMCluster status
    local cluster_data=$(cat /tmp/lvms-health-lvmcluster.json)
    local ready_count=$(echo "$cluster_data" | jq '[.items[] | select(.status.ready == true)] | length')
    local total_count=$(echo "$cluster_data" | jq '.items | length')

    if [ "$ready_count" -eq "$total_count" ] && [ "$total_count" -gt 0 ]; then
        echo "│ LVMCluster      │ ✓ Ready                                │"
    else
        echo "│ LVMCluster      │ ❌ $ready_count/$total_count ready                     │"
    fi

    # Volume Groups
    local vg_functional=$(count_functional_vgs)
    local vg_total=$(count_total_vgs)

    if [ "$vg_functional" -eq "$vg_total" ] && [ "$vg_total" -gt 0 ]; then
        echo "│ Volume Groups   │ ✓ $vg_functional/$vg_total functional                   │"
    else
        echo "│ Volume Groups   │ ⚠ $vg_functional/$vg_total functional                   │"
    fi

    # PVC Binding
    local pvc_data=$(cat /tmp/lvms-health-pvcs.json)
    local bound_pvcs=$(echo "$pvc_data" | jq 'map(select(.status.phase == "Bound")) | length')
    local total_pvcs=$(echo "$pvc_data" | jq 'length')

    if [ "$total_pvcs" -eq 0 ]; then
        echo "│ PVC Binding     │ ℹ No LVMS PVCs found                    │"
    elif [ "$bound_pvcs" -eq "$total_pvcs" ]; then
        echo "│ PVC Binding     │ ✓ $bound_pvcs/$total_pvcs bound (100%)               │"
    else
        local bind_rate=$((bound_pvcs * 100 / total_pvcs))
        echo "│ PVC Binding     │ ⚠ $bound_pvcs/$total_pvcs bound ($bind_rate%)                 │"
    fi

    # Operator Health
    local operator_data=$(cat /tmp/lvms-health-operator.json)
    local running_pods=$(echo "$operator_data" | jq '[.items[] | select(.status.phase == "Running")] | length')
    local total_pods=$(echo "$operator_data" | jq '.items | length')

    if [ "$running_pods" -eq "$total_pods" ] && [ "$total_pods" -gt 0 ]; then
        echo "│ Operator        │ ✓ All pods ready                       │"
    else
        echo "│ Operator        │ ⚠ $running_pods/$total_pods pods ready                    │"
    fi

    echo "└─────────────────┴────────────────────────────────────────┘"
}

print_capacity_table() {
    echo "═══════════════════════════════════════════════════════════"
    echo "CAPACITY OVERVIEW"
    echo "═══════════════════════════════════════════════════════════"
    echo

    if [ ! -f /tmp/lvms-health-capacity.csv ]; then
        echo "No capacity data available"
        return
    fi

    echo "┌──────────────┬───────────┬─────────────┬─────────┬────────┐"
    echo "│ Volume Group │ Node      │ Total       │ Used    │ Usage  │"
    echo "├──────────────┼───────────┼─────────────┼─────────┼────────┤"

    local total_capacity=0
    local total_used=0
    local node_count=0

    while IFS=',' read -r node vg_name size used_bytes usage_percent status; do
        local usage_display="$usage_percent%"

        # Add status indicator
        case "$status" in
            "WARNING") usage_display="$usage_percent% ⚠" ;;
            "CRITICAL") usage_display="$usage_percent% ❌" ;;
        esac

        # Format sizes for display
        local size_display=$(format_bytes_for_display "$size")
        local used_display=$(format_bytes_for_display "$used_bytes")

        printf "│ %-12s │ %-9s │ %-11s │ %-7s │ %-6s │\n" \
            "$vg_name" "$node" "$size_display" "$used_display" "$usage_display"

        # Accumulate totals
        local size_bytes=$(convert_to_bytes "$size")
        total_capacity=$((total_capacity + size_bytes))
        total_used=$((total_used + used_bytes))
        node_count=$((node_count + 1))

    done < /tmp/lvms-health-capacity.csv

    # Print totals
    if [ $node_count -gt 0 ]; then
        echo "├──────────────┼───────────┼─────────────┼─────────┼────────┤"
        local total_usage_percent=$((total_used * 100 / total_capacity))
        local total_cap_display=$(format_bytes_for_display "$total_capacity")
        local total_used_display=$(format_bytes_for_display "$total_used")

        printf "│ %-12s │ %-9s │ %-11s │ %-7s │ %-6s │\n" \
            "TOTAL" "$node_count nodes" "$total_cap_display" "$total_used_display" "$total_usage_percent%"
    fi

    echo "└──────────────┴───────────┴─────────────┴─────────┴────────┘"
}

format_bytes_for_display() {
    local bytes="$1"
    local units=("B" "KiB" "MiB" "GiB" "TiB")
    local unit_index=0
    local size=$bytes

    while [ $size -gt 1024 ] && [ $unit_index -lt 4 ]; do
        size=$((size / 1024))
        unit_index=$((unit_index + 1))
    done

    echo "${size} ${units[$unit_index]}"
}
```

**JSON Format Output:**
```bash
generate_json_report() {
    local health_score="$1"
    local overall_status="$2"

    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Build JSON structure
    jq -n \
        --arg timestamp "$timestamp" \
        --arg status "$overall_status" \
        --argjson score "$health_score" \
        --argjson lvmcluster "$(generate_lvmcluster_json)" \
        --argjson capacity "$(generate_capacity_json)" \
        --argjson volume_groups "$(generate_vg_json)" \
        --argjson pvcs "$(generate_pvc_json)" \
        --argjson operator "$(generate_operator_json)" \
        --argjson alerts "$(generate_alerts_json)" \
        --argjson recommendations "$(generate_recommendations_json)" \
        '{
            timestamp: $timestamp,
            overall_status: $status,
            health_score: $score,
            lvmcluster: $lvmcluster,
            capacity: $capacity,
            volume_groups: $volume_groups,
            pvcs: $pvcs,
            operator: $operator,
            alerts: $alerts,
            recommendations: $recommendations
        }'
}

generate_capacity_json() {
    if [ ! -f /tmp/lvms-health-capacity.csv ]; then
        echo '{"total_bytes": 0, "used_bytes": 0, "available_bytes": 0, "usage_percentage": 0}'
        return
    fi

    local total_capacity=0
    local total_used=0

    while IFS=',' read -r node vg_name size used_bytes usage_percent status; do
        local size_bytes=$(convert_to_bytes "$size")
        total_capacity=$((total_capacity + size_bytes))
        total_used=$((total_used + used_bytes))
    done < /tmp/lvms-health-capacity.csv

    local total_available=$((total_capacity - total_used))
    local usage_percentage=0
    if [ $total_capacity -gt 0 ]; then
        usage_percentage=$((total_used * 100 / total_capacity))
    fi

    jq -n \
        --argjson total_bytes "$total_capacity" \
        --argjson used_bytes "$total_used" \
        --argjson available_bytes "$total_available" \
        --argjson usage_percentage "$usage_percentage" \
        '{
            total_bytes: $total_bytes,
            used_bytes: $used_bytes,
            available_bytes: $available_bytes,
            usage_percentage: $usage_percentage
        }'
}
```

### Step 5: Alert Generation and Threshold Monitoring

**Alert Detection Logic:**
```bash
generate_alerts() {
    local alerts=()

    # Check capacity thresholds
    if [ -f /tmp/lvms-health-capacity.csv ]; then
        while IFS=',' read -r node vg_name size used_bytes usage_percent status; do
            if [ "$status" = "CRITICAL" ]; then
                alerts+=("CRITICAL:volume_group:$node:Volume group at $usage_percent% capacity (critical threshold)")
            elif [ "$status" = "WARNING" ]; then
                alerts+=("WARNING:volume_group:$node:Volume group at $usage_percent% capacity")
            fi
        done < /tmp/lvms-health-capacity.csv
    fi

    # Check PVC binding issues
    local pvc_data=$(cat /tmp/lvms-health-pvcs.json)
    local pending_pvcs=$(echo "$pvc_data" | jq 'map(select(.status.phase == "Pending")) | length')
    local total_pvcs=$(echo "$pvc_data" | jq 'length')

    if [ "$total_pvcs" -gt 0 ] && [ "$pending_pvcs" -gt 0 ]; then
        local pending_rate=$((pending_pvcs * 100 / total_pvcs))
        if [ "$pending_rate" -gt 5 ]; then
            alerts+=("CRITICAL:pvc:cluster:$pending_pvcs PVCs stuck pending ($pending_rate%)")
        else
            alerts+=("WARNING:pvc:cluster:$pending_pvcs PVCs pending")
        fi
    fi

    # Check LVMCluster readiness
    local cluster_data=$(cat /tmp/lvms-health-lvmcluster.json)
    local not_ready=$(echo "$cluster_data" | jq '[.items[] | select(.status.ready != true)] | length')

    if [ "$not_ready" -gt 0 ]; then
        alerts+=("CRITICAL:lvmcluster:cluster:$not_ready LVMCluster(s) not ready")
    fi

    # Check operator pod health
    local operator_data=$(cat /tmp/lvms-health-operator.json)
    local failed_pods=$(echo "$operator_data" | jq '[.items[] | select(.status.phase != "Running")] | length')

    if [ "$failed_pods" -gt 0 ]; then
        alerts+=("WARNING:operator:cluster:$failed_pods operator pod(s) not running")
    fi

    # Output alerts
    for alert in "${alerts[@]}"; do
        echo "$alert"
    done
}

generate_recommendations() {
    local alerts_output=$(generate_alerts)
    local recommendations=()

    # Analyze alerts and generate recommendations
    if echo "$alerts_output" | grep -q "volume_group.*capacity"; then
        recommendations+=("Consider expanding storage or cleaning up unused volumes")
        recommendations+=("Monitor capacity trends regularly with /lvms:health-check")
    fi

    if echo "$alerts_output" | grep -q "PVCs.*pending"; then
        recommendations+=("Investigate volume group availability on nodes")
        recommendations+=("Check storage class configuration and node affinity")
    fi

    if echo "$alerts_output" | grep -q "LVMCluster.*not ready"; then
        recommendations+=("Run /lvms:analyze for detailed troubleshooting")
        recommendations+=("Check device availability and configuration")
    fi

    # Output recommendations
    for rec in "${recommendations[@]}"; do
        echo "$rec"
    done
}
```

### Step 6: Must-Gather Analysis Mode

**Must-Gather Health Check Implementation:**
```bash
analyze_must_gather() {
    local must_gather_path="$1"

    echo "Analyzing LVMS health from must-gather: $must_gather_path"

    # Validate must-gather structure
    if ! validate_must_gather_structure "$must_gather_path"; then
        echo "ERROR: Invalid must-gather structure"
        return 3
    fi

    # Use existing analyze_lvms.py script with health focus
    local analyzer_script="plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py"

    if [ ! -f "$analyzer_script" ]; then
        echo "ERROR: LVMS analyzer script not found at $analyzer_script"
        return 3
    fi

    # Run analysis and extract health metrics
    python3 "$analyzer_script" "$must_gather_path" --component all > /tmp/lvms-health-analyze-output.txt 2>&1
    local exit_code=$?

    # Parse analysis output for health metrics
    extract_health_from_analysis

    return $exit_code
}

extract_health_from_analysis() {
    local analysis_output="/tmp/lvms-health-analyze-output.txt"

    # Extract key metrics from analysis output
    local critical_issues=$(grep -c "CRITICAL ISSUES:" "$analysis_output" || echo "0")
    local warning_issues=$(grep -c "WARNINGS:" "$analysis_output" || echo "0")

    # Calculate health score based on analysis
    local health_score=100
    if [ "$critical_issues" -gt 0 ]; then
        health_score=$((health_score - critical_issues * 20))
    fi
    if [ "$warning_issues" -gt 0 ]; then
        health_score=$((health_score - warning_issues * 10))
    fi

    # Ensure score doesn't go below 0
    if [ "$health_score" -lt 0 ]; then
        health_score=0
    fi

    echo "$health_score" > /tmp/lvms-health-score.txt

    # Determine overall status
    local overall_status="HEALTHY"
    if [ "$critical_issues" -gt 0 ]; then
        overall_status="CRITICAL"
    elif [ "$warning_issues" -gt 0 ]; then
        overall_status="WARNING"
    fi

    echo "$overall_status" > /tmp/lvms-health-status.txt
}
```

### Step 7: Main Implementation Flow

**Complete Health Check Implementation:**
```bash
#!/bin/bash
# Health check implementation entry point

set -euo pipefail

# Global variables
LVMS_NAMESPACE=""
OUTPUT_FORMAT="table"
THRESHOLD_WARNING=80
LIVE_MODE=true
MUST_GATHER_PATH=""
HEALTH_SCORE=0
OVERALL_STATUS="UNKNOWN"

# Main execution flow
main() {
    # Parse arguments and determine mode
    parse_arguments "$@"

    # Create temp directory for data
    mkdir -p /tmp/lvms-health-check
    cd /tmp/lvms-health-check

    # Execute health check based on mode
    if [ "$LIVE_MODE" = true ]; then
        execute_live_health_check
    else
        execute_mustgather_health_check "$MUST_GATHER_PATH"
    fi

    # Generate final report
    generate_final_report

    # Cleanup and exit
    cleanup_temp_files

    # Set exit code based on health status
    case "$OVERALL_STATUS" in
        "HEALTHY") exit 0 ;;
        "WARNING") exit 1 ;;
        "CRITICAL") exit 2 ;;
        *) exit 3 ;;
    esac
}

execute_live_health_check() {
    echo "Executing live cluster health check..."

    # Validate cluster connection
    validate_live_cluster

    # Collect all metrics
    collect_lvmcluster_status
    collect_vg_capacity
    collect_pvc_usage
    collect_operator_health

    # Analyze metrics
    analyze_capacity

    # Calculate health score
    HEALTH_SCORE=$(calculate_health_score)

    # Determine overall status
    determine_overall_status
}

determine_overall_status() {
    # Generate alerts to determine status
    local alerts_output=$(generate_alerts)

    if echo "$alerts_output" | grep -q "CRITICAL:"; then
        OVERALL_STATUS="CRITICAL"
    elif echo "$alerts_output" | grep -q "WARNING:" || [ "$HEALTH_SCORE" -lt 80 ]; then
        OVERALL_STATUS="WARNING"
    else
        OVERALL_STATUS="HEALTHY"
    fi
}

generate_final_report() {
    case "$OUTPUT_FORMAT" in
        "json")
            generate_json_report "$HEALTH_SCORE" "$OVERALL_STATUS"
            ;;
        "table"|*)
            generate_table_report "$HEALTH_SCORE" "$OVERALL_STATUS"
            ;;
    esac
}

# Execute main function if script is called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```

## Error Handling

**Connection and Permission Issues:**
```bash
handle_connection_error() {
    local error_type="$1"
    local error_message="$2"

    case "$error_type" in
        "no_cluster")
            echo "ERROR: Not connected to any OpenShift cluster"
            echo "SOLUTION: Run 'oc login <cluster-url>' to connect"
            exit 3
            ;;
        "no_lvms")
            echo "ERROR: LVMS not found on this cluster"
            echo "SOLUTION: Verify LVMS is installed or check cluster context"
            exit 2
            ;;
        "permissions")
            echo "WARNING: Limited permissions detected"
            echo "IMPACT: Some health metrics may be incomplete"
            echo "SOLUTION: Ensure service account has cluster-reader permissions"
            # Continue with limited data
            ;;
    esac
}
```

**Data Collection Failures:**
```bash
handle_collection_error() {
    local component="$1"
    local error="$2"

    echo "WARNING: Failed to collect $component data: $error"

    # Create empty data file to prevent downstream errors
    case "$component" in
        "lvmcluster")
            echo '{"items":[]}' > /tmp/lvms-health-lvmcluster.json
            ;;
        "vg")
            echo '{"items":[]}' > /tmp/lvms-health-vg.json
            ;;
        "pvc")
            echo '[]' > /tmp/lvms-health-pvcs.json
            ;;
    esac

    # Note in final report that data is incomplete
    echo "$component collection failed" >> /tmp/lvms-health-warnings.txt
}
```

## Examples

### Example 1: Live Cluster Health Check

**Command:**
```bash
/lvms:health-check
```

**Implementation:**
```bash
# Execute all collection steps for live cluster
validate_live_cluster
collect_all_metrics
analyze_capacity
calculate_health_score
generate_table_report
```

**Output:**
```
═══════════════════════════════════════════════════════════
LVMS HEALTH CHECK
═══════════════════════════════════════════════════════════

Overall Status: WARNING ⚠
Health Score: 85/100

┌─────────────────┬────────────────────────────────────────┐
│ Component       │ Status                                 │
├─────────────────┼────────────────────────────────────────┤
│ LVMCluster      │ ✓ Ready                                │
│ Volume Groups   │ ✓ 3/3 functional                       │
│ PVC Binding     │ ✓ 45/46 bound (97.8%)                  │
│ Operator        │ ✓ All pods ready                       │
└─────────────────┴────────────────────────────────────────┘
```

### Example 2: JSON Output for Monitoring

**Command:**
```bash
/lvms:health-check --format json --threshold-warning 75
```

**Output:**
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "overall_status": "WARNING",
  "health_score": 85,
  "lvmcluster": {
    "name": "lvmcluster-sample",
    "state": "Ready",
    "ready": true
  },
  "capacity": {
    "total_bytes": 1610612736000,
    "used_bytes": 996147200000,
    "usage_percentage": 62
  },
  "alerts": [
    {
      "level": "WARNING",
      "component": "volume_group",
      "node": "worker-1",
      "message": "Volume group at 85% capacity"
    }
  ]
}
```

## Best Practices

1. **Regular Monitoring Schedule:**
   ```bash
   # Run health checks every 15 minutes
   */15 * * * * /usr/local/bin/lvms-health-check --format json > /var/log/lvms-health.json
   ```

2. **Threshold Customization:**
   - Development clusters: `--threshold-warning 90`
   - Production clusters: `--threshold-warning 75`
   - High-capacity environments: `--threshold-warning 85`

3. **Integration with Monitoring:**
   ```bash
   # Prometheus metrics integration
   lvms_health_score=$(lvms-health-check --format json | jq '.health_score')
   echo "lvms_cluster_health_score $lvms_health_score" > /var/lib/node_exporter/textfile_collector/lvms.prom
   ```

4. **Automation-Friendly Usage:**
   ```bash
   #!/bin/bash
   /lvms:health-check --format json > /tmp/health.json
   exit_code=$?

   case $exit_code in
       0) echo "✓ LVMS healthy" ;;
       1) echo "⚠ LVMS warnings detected" ;;
       2) echo "❌ LVMS critical issues" ;;
       *) echo "✗ Health check failed" ;;
   esac
   ```

## Related Commands

- `/lvms:analyze` - Detailed troubleshooting and root cause analysis
- `/lvms:analyze --live --component storage` - Focused storage analysis
- `/utils:generate-test-plan` - Create monitoring test plans

## Additional Resources

- [LVMS Capacity Planning](https://github.com/openshift/lvm-operator/blob/main/docs/capacity-planning.md)
- [OpenShift Storage Monitoring](https://docs.openshift.com/container-platform/latest/storage/monitoring-storage.html)
- [LVMS Troubleshooting Guide](https://github.com/openshift/lvm-operator/blob/main/docs/troubleshooting.md)