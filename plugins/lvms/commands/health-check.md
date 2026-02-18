---
description: Quick LVMS health monitoring - capacity overview, status summary, and proactive alerts for regular monitoring
argument-hint: "[--format json|table] [--threshold-warning 80] [--namespace custom-ns]"
---

## Name
lvms:health-check

## Synopsis
```
/lvms:health-check [--format json|table] [--threshold-warning <percentage>] [--namespace <namespace>]
```

## Description

The `lvms:health-check` command provides fast, lightweight monitoring of LVMS health and storage capacity. Designed for regular monitoring and automation, it delivers a concise overview of LVMS status, capacity utilization, and proactive alerts without the comprehensive analysis of `/lvms:analyze`.

This command is ideal for:
- Regular automated monitoring
- Dashboard integration
- Quick daily health checks
- Proactive capacity management
- Early warning system for storage issues

The command focuses on key metrics and thresholds rather than deep troubleshooting, making it suitable for scheduled execution and monitoring systems.

## Prerequisites

- `oc` CLI installed and configured
- Active cluster connection: `oc whoami`
- Read access to LVMS namespace (default: `openshift-lvm-storage` or custom via `--namespace`)
- Ability to read cluster-scoped resources (Nodes, PVs)

## Implementation

1. **Validate LVMS Namespace**:
   ```bash
   # Use default or custom namespace
   LVMS_NS="${NAMESPACE:-openshift-lvm-storage}"

   # Validate namespace exists
   oc get namespace "$LVMS_NS" >/dev/null 2>&1 || {
       echo "ERROR: LVMS namespace '$LVMS_NS' not found"
       exit 2
   }
   ```

2. **Collect Essential Metrics**:

   **LVMCluster Status:**
   ```bash
   # Quick status check
   oc get lvmcluster -n $LVMS_NS -o json | jq -r '.items[] | {
     name: .metadata.name,
     state: .status.state,
     ready: .status.ready
   }'
   ```

   **Volume Group Capacity:**
   ```bash
   # Get VG capacity across all nodes
   oc get lvmvolumegroupnodestatus -A -o json | jq -r '.items[] | {
     node: .metadata.name,
     vgs: .status.volumeGroups[] | {
       name: .name,
       available: .available,
       size: .size
     }
   }'
   ```

   **PVC Summary:**
   ```bash
   # Count PVCs by status
   oc get pvc -A -o json | jq -r '
   [.items[] | select(.spec.storageClassName | startswith("lvms-"))] |
   group_by(.status.phase) |
   map({phase: .[0].status.phase, count: length})'
   ```

   **Operator Health:**
   ```bash
   # Quick operator status
   oc get pods -n $LVMS_NS -o json | jq -r '.items[] | {
     name: .metadata.name,
     phase: .status.phase,
     ready: (.status.conditions[] | select(.type=="Ready") | .status)
   }'
   ```

   **Storage Class Status:**
   ```bash
   # Check LVMS storage classes (1:1 mapping with device classes)
   oc get storageclass -o json | jq -r '.items[] |
   select(.provisioner == "topolvm.io") | {
     name: .metadata.name,
     provisioner: .provisioner,
     parameters: .parameters
   }'

   # Validate against LVMCluster device classes
   oc get lvmcluster -n $LVMS_NS -o json | jq -r '.items[].spec.storage.deviceClasses[] | .name'
   ```

   **CSI Driver Health:**
   ```bash
   # Check CSI driver registration
   oc get csidriver topolvm.io -o json | jq '{
     name: .metadata.name,
     attachRequired: .spec.attachRequired,
     podInfoOnMount: .spec.podInfoOnMount
   }'

   # Check CSI controller and node pods
   oc get pods -n $LVMS_NS -l "app.kubernetes.io/component in (controller,node)" -o json | jq -r '.items[] | {
     name: .metadata.name,
     component: .metadata.labels."app.kubernetes.io/component",
     phase: .status.phase,
     node: .spec.nodeName
   }'
   ```

3. **Calculate Health Metrics**:

   **Overall Health Score:**
   - LVMCluster Ready: 25%
   - All VGs functional: 25%
   - No critical PVC issues: 15%
   - Operator pods healthy: 10%
   - **Storage classes properly mapped: 15%** _(CRITICAL - All-or-nothing scoring)_
   - CSI driver operational: 10%

   **Capacity Calculations:**
   ```bash
   # Per volume group and overall
   total_capacity=0
   total_available=0

   for vg in volume_groups; do
     vg_total=$(get_vg_size $vg)
     vg_available=$(get_vg_available $vg)
     vg_usage_pct=$(((vg_total - vg_available) * 100 / vg_total))

     total_capacity=$((total_capacity + vg_total))
     total_available=$((total_available + vg_available))
   done

   overall_usage_pct=$(((total_capacity - total_available) * 100 / total_capacity))
   ```

   **Threshold Checks:**
   ```bash
   # Check against configurable thresholds
   WARNING_THRESHOLD=${threshold_warning:-80}
   CRITICAL_THRESHOLD=90

   if [ $usage_pct -ge $CRITICAL_THRESHOLD ]; then
     alert_level="CRITICAL"
   elif [ $usage_pct -ge $WARNING_THRESHOLD ]; then
     alert_level="WARNING"
   else
     alert_level="OK"
   fi
   ```

4. **Generate Concise Health Report**:

   **Table Format (Default):**
   ```
   ═══════════════════════════════════════════════════════════
   LVMS HEALTH CHECK
   ═══════════════════════════════════════════════════════════

   Overall Status: HEALTHY ✓ | WARNING ⚠ | CRITICAL ❌
   Health Score: 95/100

   ┌─────────────────┬────────────────────────────────────────┐
   │ Component       │ Status                                 │
   ├─────────────────┼────────────────────────────────────────┤
   │ LVMCluster      │ ✓ Ready                                │
   │ Volume Groups   │ ✓ 3/3 functional                       │
   │ PVC Binding     │ ✓ 45/46 bound (97.8%)                  │
   │ Operator        │ ✓ All pods ready                       │
   │ Storage Classes │ ✓ 2/2 perfect mapping                   │
   │ CSI Driver      │ ✓ Registered and running               │
   └─────────────────┴────────────────────────────────────────┘

   ═══════════════════════════════════════════════════════════
   CAPACITY OVERVIEW
   ═══════════════════════════════════════════════════════════

   ┌──────────────┬───────────┬─────────────┬─────────┬────────┐
   │ Volume Group │ Node      │ Total       │ Used    │ Usage  │
   ├──────────────┼───────────┼─────────────┼─────────┼────────┤
   │ vg1          │ master-0  │ 500 GiB     │ 120 GiB │ 24%    │
   │ vg1          │ worker-0  │ 500 GiB     │ 380 GiB │ 76%    │
   │ vg1          │ worker-1  │ 500 GiB     │ 425 GiB │ 85% ⚠  │
   ├──────────────┼───────────┼─────────────┼─────────┼────────┤
   │ TOTAL        │ 3 nodes   │ 1.46 TiB    │ 905 GiB │ 62%    │
   └──────────────┴───────────┴─────────────┴─────────┴────────┘

   ═══════════════════════════════════════════════════════════
   ALERTS & RECOMMENDATIONS
   ═══════════════════════════════════════════════════════════

   ⚠  WARNING: worker-1 volume group at 85% capacity
      • Consider expanding storage or cleaning up unused volumes
      • Monitor: /lvms:health-check or /lvms:analyze --live --component volumes

   ℹ  INFO: Overall storage utilization is healthy at 62%

   ═══════════════════════════════════════════════════════════
   QUICK ACTIONS
   ═══════════════════════════════════════════════════════════

   • Detailed analysis: /lvms:analyze --live
   • Expand storage: See LVMS documentation for adding devices
   • Monitor trends: Set up regular /lvms:health-check execution
   ```

   **JSON Format:**
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
       "available_bytes": 614465536000,
       "usage_percentage": 62
     },
     "volume_groups": [
       {
         "name": "vg1",
         "node": "worker-1",
         "total_bytes": 536870912000,
         "used_bytes": 456755200000,
         "usage_percentage": 85,
         "status": "WARNING"
       }
     ],
     "pvcs": {
       "total": 46,
       "bound": 45,
       "pending": 1,
       "failed": 0,
       "bind_rate": 97.8
     },
     "operator": {
       "pods_total": 4,
       "pods_ready": 4,
       "deployments_ready": 1,
       "daemonsets_ready": 1
     },
     "alerts": [
       {
         "level": "WARNING",
         "component": "volume_group",
         "node": "worker-1",
         "message": "Volume group at 85% capacity",
         "threshold": 80
       }
     ],
     "recommendations": [
       "Consider expanding storage on worker-1",
       "Monitor capacity trends regularly"
     ]
   }
   ```

5. **Quick Issue Detection**:

   **Critical Issues (Immediate attention):**
   - LVMCluster not Ready
   - Volume groups missing/failed on nodes
   - Multiple PVCs stuck pending (>5% pending)
   - Operator pods not ready
   - Any VG >90% capacity

   **Warnings (Monitor closely):**
   - VG capacity >80% (configurable threshold)
   - Individual PVCs pending for >5 minutes
   - Operator pod restarts in last hour
   - VG capacity growth >10% since last check

6. **Automation-Friendly Output**:

   **Exit Codes:**
   - 0: All healthy (green status)
   - 1: Warnings present (yellow status)
   - 2: Critical issues found (red status)
   - 3: Command/connection error

   **Structured Data:**
   - JSON format for programmatic consumption
   - Consistent field names for monitoring integration
   - Threshold values included for trend analysis

## Return Value

**Format**: Structured health report showing LVMS status, capacity metrics, and actionable alerts

**Success States:**
- **HEALTHY** (Score: 90-100): All components functional, capacity <80%
- **WARNING** (Score: 70-89): Minor issues or approaching thresholds
- **CRITICAL** (Score: <70): Major issues requiring immediate attention

**Output Modes:**
- **table** (default): Human-readable tabular format with visual indicators
- **json**: Machine-readable JSON for automation and monitoring systems

## Examples

1. **Quick health check (default table format)**:
   ```
   /lvms:health-check
   ```
   Shows overall status, capacity summary, and any alerts in table format.

2. **JSON output for monitoring systems**:
   ```
   /lvms:health-check --format json
   ```
   Returns structured JSON data suitable for monitoring dashboards.

3. **Custom warning threshold**:
   ```
   /lvms:health-check --threshold-warning 75
   ```
   Alerts when any volume group exceeds 75% capacity (default: 80%).

4. **Custom namespace installation**:
   ```
   /lvms:health-check --namespace my-custom-lvms-ns
   ```
   Monitor LVMS installed in a custom namespace instead of the default locations.

5. **Automated monitoring script**:
   ```bash
   #!/bin/bash
   /lvms:health-check --format json > /tmp/lvms-health.json
   if [ $? -gt 1 ]; then
     echo "CRITICAL: LVMS issues detected!"
     cat /tmp/lvms-health.json | jq '.alerts'
   fi
   ```

## Arguments

- **--format**: Optional. Output format: `table` (default) or `json`
  - `table`: Human-readable format with visual indicators
  - `json`: Structured data for automation and integration

- **--threshold-warning**: Optional. Percentage threshold for capacity warnings (default: 80)
  - Example: `--threshold-warning 75` alerts at 75% capacity

- **--namespace**: Optional. Specify custom LVMS namespace (default: openshift-lvm-storage)
  - Uses `openshift-lvm-storage` by default
  - Example: `--namespace my-custom-lvms-namespace` for custom installations

## Notes

- **Lightweight Design**: Much faster than `/lvms:analyze` - focuses on key metrics only
- **Automation Ready**: Consistent exit codes and JSON format for monitoring integration
- **Proactive Monitoring**: Designed to catch issues before they become critical
- **Complementary Tool**: Use with `/lvms:analyze` for detailed troubleshooting when issues are found
- **Threshold Customization**: Adjust warning thresholds based on your environment and policies
- **Trend Analysis**: Regular execution provides capacity growth trends over time
- **Live Monitoring**: Focuses on real-time cluster health monitoring
- **🚨 CRITICAL**: **Storage Class Mapping** - Perfect 1:1 mapping between device classes and storage classes is essential. Any mismatch renders storage provisioning non-functional and results in zero points for this component.

## Troubleshooting

**Cannot connect to cluster:**
```bash
# Verify oc configuration
oc whoami && oc cluster-info
```

**No LVMS found:**
```bash
# Check if LVMS is installed
oc get namespace openshift-lvm-storage 2>/dev/null
oc get crd | grep lvm
```

**Permission denied:**
```bash
# Check required permissions
oc auth can-i get lvmcluster
oc auth can-i get pvc --all-namespaces
```

**Storage Class mapping issues:**
```bash
# Check device classes in LVMCluster
oc get lvmcluster -n openshift-lvm-storage -o json | jq '.items[].spec.storage.deviceClasses[].name'

# Check LVMS storage classes
oc get storageclass -o json | jq '.items[] | select(.provisioner=="topolvm.io") | .metadata.name'

# Verify 1:1 mapping - should be identical lists
# If missing storage classes, check operator logs:
oc logs -n openshift-lvm-storage -l app.kubernetes.io/name=lvms-operator
```

## Related Commands

- `/lvms:analyze` - Comprehensive troubleshooting and diagnosis
- `/lvms:analyze --live --component storage` - Focused storage analysis
- `/utils:generate-test-plan` - Create monitoring test plans

## Additional Resources

- [LVMS Monitoring Guide](https://github.com/openshift/lvm-operator/blob/main/docs/monitoring.md)
- [OpenShift Storage Monitoring](https://docs.openshift.com/container-platform/latest/storage/monitoring-storage.html)
- [LVMS Capacity Planning](https://github.com/openshift/lvm-operator/blob/main/docs/capacity-planning.md)