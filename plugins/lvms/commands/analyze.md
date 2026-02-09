---
description: Comprehensive LVMS troubleshooting - analyzes LVMCluster, volume groups, PVCs, and storage issues on live clusters or must-gather
argument-hint: "[must-gather-path|--live] [--component storage|operator|volumes]"
---

## Name
lvms:analyze

## Synopsis
```
/lvms:analyze [must-gather-path] [--live] [--component <component>]
```

## Description

The `lvms:analyze` command provides comprehensive troubleshooting for OpenShift LVMS (Logical Volume Manager Storage). It analyzes the health and configuration of LVMCluster, volume groups, PVCs, TopoLVM CSI driver, and node-level storage to identify and diagnose common LVMS issues.

The command can operate in two modes:
- **Must-gather analysis**: Analyzes LVMS must-gather data offline
- **Live cluster analysis**: Connects to a running cluster and performs real-time diagnostics

Common issues detected:
- PVCs stuck in Pending state
- LVMCluster not reaching Ready state
- Volume group creation failures
- Missing or unhealthy physical volumes
- TopoLVM CSI driver issues
- Node-level disk availability problems
- Thin pool configuration issues
- Device class misconfigurations
- Operator and vg-manager pod errors (from log analysis)

## Prerequisites

**For Live Cluster Analysis:**
- `oc` CLI installed and configured
- Active cluster connection: `oc whoami`
- Read access to LVMS namespace (`openshift-lvm-storage` or older `openshift-storage`)
- Ability to read cluster-scoped resources (CRDs, Nodes, PVs)

**For Must-Gather Analysis:**
- LVMS must-gather data extracted to a directory
- Must-gather structure:
  ```
  must-gather/
  └── registry-ci-openshift-org.../
      ├── cluster-scoped-resources/
      ├── namespaces/
      │   └── openshift-lvm-storage/  (or openshift-storage for older versions)
      └── ...
  ```

**Namespace Compatibility:**
- LVMS namespace changed from `openshift-storage` to `openshift-lvm-storage` in recent versions
- The command automatically detects which namespace is used in the must-gather
- Both namespaces are supported for backward compatibility

**Analysis Script:**
- Python 3 script at: `plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py`
- If script is missing, command will use built-in analysis logic

## Implementation

The command performs the following steps:

1. **Determine Analysis Mode**:
   - If the `--live` flag is present, proceed with live cluster analysis
   - If path argument is provided, proceed with must-gather analysis
   - If neither provided, ask user which mode to use
   - Validate prerequisites for selected mode

2. **Validate Environment**:

   **For Live Cluster:**
   ```bash
   # Verify oc CLI
   which oc

   # Verify cluster connection
   oc whoami

   # Check LVMS namespace exists (try both namespaces)
   oc get namespace openshift-lvm-storage 2>/dev/null || oc get namespace openshift-storage
   ```

   **For Must-Gather:**
   ```bash
   # Verify path exists (checks both old and new namespaces)
   ls {must-gather-path}/namespaces/openshift-lvm-storage 2>/dev/null || \
     ls {must-gather-path}/namespaces/openshift-storage

   # Check for required directories
   ls {must-gather-path}/cluster-scoped-resources/core/persistentvolumes

   # Note: The analysis script automatically detects which namespace is used
   ```

3. **Determine Analysis Scope**:

   Check for component-specific keywords in arguments:
   - If the argument contains one or more of `storage`, `pvc`, `pv`, `volumes`, `pending` then only do storage/pvc analysis.
   - If the argument contains one or more of `operator`, `lvmcluster`, `deployment`, `pods` then analyze operator health only
   - If the argument contains one or more of `vg`, `volume group`, `disk`, `device` then do Volume group analysis only
   - If the argument contains one or more of `node`, `devices`, `lsblk` then do node-level device analysis only (live cluster only)
   - If the argument contains one or more of `logs`, `errors` then do pod log analysis only
   - If no specific component provided then do full comprehensive analysis

4. **Collect LVMS Resources**:

   **Live Cluster Collection:**

   First, detect which namespace LVMS is using:
   ```bash
   # Detect LVMS namespace (newer versions use openshift-lvm-storage, older use openshift-storage)
   LVMS_NS=$(oc get namespace openshift-lvm-storage -o name 2>/dev/null | cut -d/ -f2)
   if [ -z "$LVMS_NS" ]; then
       LVMS_NS="openshift-storage"
   fi
   ```

   Then collect resources:
   ```bash
   # LVMCluster resources
   oc get lvmcluster -n $LVMS_NS -o yaml

   # LVMVolumeGroup status
   oc get lvmvolumegroup -A -o yaml
   oc get lvmvolumegroupnodestatus -A -o yaml

   # Operator pods
   oc get pods -n $LVMS_NS -o wide
   oc get pods -n $LVMS_NS -o yaml

   # Storage resources
   oc get pvc -A -o yaml | grep -A 50 "storageClassName: lvms-"
   oc get pv -o yaml | grep -A 50 "storageClassName: lvms-"

   # Events in LVMS namespace
   oc get events -n $LVMS_NS --sort-by='.lastTimestamp'

   # Storage classes
   oc get storageclass | grep lvms
   oc get storageclass -o yaml | grep -A 20 "provisioner: topolvm.io"

   # Node information
   oc get nodes -o wide

   # TopoLVM CSI components
   oc get daemonset -n $LVMS_NS
   oc get deployment -n $LVMS_NS
   ```

   **Must-Gather Collection:**
   Use Python script if available (automatically detects namespace):
   ```bash
   python3 plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py {must-gather-path}
   ```

   The script automatically detects and uses the correct namespace (openshift-lvm-storage or openshift-storage).

   Or use built-in file reading:
   ```bash
   # Find LVMCluster resources
   find {must-gather-path} -name "lvmclusters.yaml"

   # Find LVMVolumeGroup resources
   find {must-gather-path} -name "lvmvolumegroups.yaml"

   # Find operator pods
   cat {must-gather-path}/namespaces/openshift-lvm-storage/pods.yaml

   # Find events
   cat {must-gather-path}/namespaces/openshift-lvm-storage/events.yaml
   ```

5. **Analyze LVMCluster Health**:

   Check critical status fields:
   ```yaml
   # LVMCluster Status
   status:
     state: Ready | Progressing | Failed | Degraded | Unknown
     ready: true | false
     conditions:
       - type: ResourcesAvailable
         status: True | False
         reason: ...
         message: ...
       - type: VolumeGroupsReady
         status: True | False
         reason: ...
         message: ...
   ```

   Report findings:
   ```
   ═══════════════════════════════════════════════════════════
   LVMCLUSTER STATUS
   ═══════════════════════════════════════════════════════════

   LVMCluster: lvmcluster-sample
   State: Ready ✓ | Progressing ⚠ | Failed ❌
   Ready: true ✓ | false ❌

   Conditions:
   ✓ ResourcesAvailable: True (All resources deployed)
   ❌ VolumeGroupsReady: False (Volume group vg1 not found on node worker-0)

   Device Classes:
   - vg1: 3 nodes, thin pool enabled
     Status: 2/3 nodes ready
     Missing: worker-0

   Issues Detected:
   ❌ CRITICAL: Volume group not created on worker-0
   ⚠  WARNING: Thin pool size at 85% capacity
   ```

6. **Analyze Volume Groups**:

   For each LVMVolumeGroup and LVMVolumeGroupNodeStatus:
   ```bash
   # Check VG status across nodes
   oc get lvmvolumegroup -A -o json | jq -r '.items[] | {
     name: .metadata.name,
     namespace: .metadata.namespace,
     status: .status
   }'

   # Check node-level VG status
   oc get lvmvolumegroupnodestatus -A -o json | jq -r '.items[] | {
     node: .metadata.name,
     vgs: .spec.volumeGroups,
     status: .status
   }'
   ```

   Report findings:
   ```
   ═══════════════════════════════════════════════════════════
   VOLUME GROUP STATUS
   ═══════════════════════════════════════════════════════════

   Volume Group: vg1
   Nodes: 3

   Node: master-0
   ✓ VG Created: vg1
   ✓ PV Count: 1
   ✓ Free Space: 450 GiB / 500 GiB
   ✓ Thin Pool: lvm-thin-pool-0 (90% allocated, 75% used)

   Node: worker-0
   ❌ VG Status: Failed
   ❌ Error: No available devices found
   ℹ  Devices: /dev/sdb (rejected: already in use)

   Issues Detected:
   ❌ worker-0: Device /dev/sdb already has filesystem
   ⚠  master-0: Thin pool nearing capacity
   ```

7. **Analyze PVC/PV Issues**:

   Find problematic PVCs:
   ```bash
   # Find pending PVCs using LVMS
   oc get pvc -A -o json | jq -r '.items[] |
     select(.spec.storageClassName | startswith("lvms-")) |
     select(.status.phase != "Bound") |
     {namespace: .metadata.namespace, name: .metadata.name,
      phase: .status.phase, storageClass: .spec.storageClassName}'
   ```

   For each problematic PVC:
   ```bash
   # Get PVC details
   oc describe pvc {pvc-name} -n {namespace}

   # Check events
   oc get events -n {namespace} --field-selector involvedObject.name={pvc-name}
   ```

   Report findings:
   ```
   ═══════════════════════════════════════════════════════════
   STORAGE (PVC/PV) STATUS
   ═══════════════════════════════════════════════════════════

   Total PVCs using LVMS: 15
   Bound: 12 ✓
   Pending: 3 ❌

   Pending PVCs:

   1. test-app/data-volume
      Status: Pending (10m)
      Storage Class: lvms-vg1
      Requested: 100Gi

      Recent Events:
      - 10m Warning ProvisioningFailed:
        "failed to provision volume: no node has enough free space"

      Root Cause:
      ❌ Insufficient free space in volume group vg1
      Current available: 45Gi across all nodes
      Largest available on single node: 20Gi

   2. database/postgres-data
      Status: Pending (5m)
      Storage Class: lvms-vg1
      Requested: 50Gi

      Recent Events:
      - 5m Warning ProvisioningFailed:
        "topology constraint not satisfied"

      Root Cause:
      ⚠  PVC has node affinity requiring worker-0
      ❌ worker-0 has no functional volume group
   ```

8. **Analyze Operator Health**:

   Check operator pods:
   ```bash
   # Get all pods in LVMS namespace
   oc get pods -n $LVMS_NS -o json

   # Check for crashloops, errors, restarts
   oc get pods -n $LVMS_NS -o json | jq -r '.items[] |
     {name: .metadata.name,
      phase: .status.phase,
      ready: .status.conditions[] | select(.type=="Ready") | .status,
      restarts: .status.containerStatuses[].restartCount}'
   ```

   Check deployments and daemonsets:
   ```bash
   oc get deployment -n $LVMS_NS -o wide
   oc get daemonset -n $LVMS_NS -o wide
   ```

   Report findings:
   ```
   ═══════════════════════════════════════════════════════════
   OPERATOR HEALTH
   ═══════════════════════════════════════════════════════════

   Deployments:
   ✓ lvms-operator: 1/1 replicas ready

   DaemonSets:
   ✓ vg-manager: 3/3 nodes ready

   Pod Issues:

   ❌ vg-manager-abc123 (worker-0)
      Status: CrashLoopBackOff
      Restarts: 15

      Container Logs (last 20 lines):
      Error: failed to create volume group: exit status 5
      Error: volume group "vg1" creation failed

      Root Cause:
      Volume group vg1 not created on worker-0 due to device conflicts
   ```

9. **Analyze Node Device Status**:

   For live clusters, check devices on nodes:
   ```bash
   # For each node, check available block devices
   oc debug node/{node-name} -- chroot /host lsblk --paths --json -o NAME,ROTA,TYPE,SIZE,MODEL,FSTYPE,MOUNTPOINT

   # Check which devices are being used by LVMS
   oc debug node/{node-name} -- chroot /host vgs -o vg_name,pv_name,vg_size,vg_free
   oc debug node/{node-name} -- chroot /host pvs -o pv_name,vg_name,pv_size,pv_free,pv_used
   ```

   Report findings:
   ```
   ═══════════════════════════════════════════════════════════
   NODE DEVICE STATUS
   ═══════════════════════════════════════════════════════════

   Node: worker-0

   Block Devices:
   ✓ /dev/sda: 100GB (system disk, mounted as /)
   ⚠  /dev/sdb: 500GB (has ext4 filesystem, not available)
   ✓ /dev/sdc: 500GB (available for LVMS)

   Current VG Configuration:
   ❌ No volume groups found

   Issues:
   ❌ Device /dev/sdb has existing filesystem (ext4)
   ℹ  Device /dev/sdc is available but not configured

   Recommendations:
   1. Wipe filesystem on /dev/sdb: wipefs -a /dev/sdb
   2. Update LVMCluster to use /dev/sdc
   3. Or remove /dev/sdb from LVMCluster deviceSelector
   ```

10. **Check TopoLVM Configuration**:

    Verify operator installation:
    ```bash
    # Check operator pods
    oc get pods -n $LVMS_NS -l app.kubernetes.io/component=lvms-operator

    # Check storage classes
    oc get storageclass -o json | jq -r '.items[] |
      select(.provisioner == "topolvm.io") |
      {name: .metadata.name,
       parameters: .parameters,
       volumeBindingMode: .volumeBindingMode}'
    ```

    Report findings:
    ```
    ═══════════════════════════════════════════════════════════
    TOPOLVM CSI DRIVER
    ═══════════════════════════════════════════════════════════

    Operator Deployment:
    ✓ lvms-operator: Running

    Storage Classes:
    ✓ lvms-vg1
      Provisioner: topolvm.io
      Volume Binding: WaitForFirstConsumer
      Device Class: vg1
      Filesystem: xfs

    Note: CSI driver is integrated into the LVMS operator and vg-manager components
    ```

11. **Analyze Pod Logs**:

    Extract and analyze error/warning messages from pod logs:

    **Live Cluster:**
    ```bash
    # Get logs from vg-manager pods
    for pod in $(oc get pods -n $LVMS_NS -l app.kubernetes.io/component=vg-manager -o name); do
        oc logs -n $LVMS_NS $pod --tail=1000
    done

    # Get logs from lvms-operator pod
    oc logs -n $LVMS_NS deployment/lvms-operator --tail=1000
    ```

    **Must-Gather:**
    ```bash
    # Pod logs are located at:
    # namespaces/{lvms-namespace}/pods/{pod-name}/{container}/{container}/logs/current.log
    ```

    **Processing:**
    ```bash
    # Parse JSON-formatted log entries
    # Extract error and warning level messages
    # Deduplicate repeated errors from reconciliation loops
    ```

    Report findings:
    ```
    ═══════════════════════════════════════════════════════════
    POD LOGS ANALYSIS
    ═══════════════════════════════════════════════════════════

    Pod: vg-manager-abc123
    Unique errors/warnings: 2

    ❌ 2025-10-28T10:47:28Z: Reconciler error
      Controller: lvmvolumegroup
      Error Details:
        failed to create/extend volume group vg1: failed to extend volume group vg1:
        WARNING: VG name vg0 is used by VGs ...
        Cannot use /dev/dm-10: device has a signature
        Command requires all devices to be found.

    Pod: lvms-operator-xyz456
    Unique errors/warnings: 1

    ❌ 2025-10-28T10:52:48Z: failed to validate device class setup
      Controller: lvmcluster
      Error: VG vg1 on node Degraded is not in ready state
    ```

12. **Generate Comprehensive Report**:

    Synthesize all findings:
    ```
    ═══════════════════════════════════════════════════════════
    LVMS ANALYSIS SUMMARY
    ═══════════════════════════════════════════════════════════

    Analysis Mode: Live Cluster | Must-Gather
    Cluster: {cluster-name}
    LVMS Version: {version}
    Analysis Time: {timestamp}

    ✓ HEALTHY: {count}
    - LVMCluster in Ready state
    - 12/15 PVCs successfully bound
    - Operator pods running on 2/3 nodes

    ⚠  WARNINGS: {count}
    - Thin pool at 85% capacity on master-0
    - vg-manager daemonset not ready on all nodes

    ❌ CRITICAL ISSUES: {count}
    - Volume group vg1 not created on worker-0
    - 3 PVCs stuck in Pending state
    - Device /dev/sdb on worker-0 has conflicting filesystem

    ═══════════════════════════════════════════════════════════
    ROOT CAUSE ANALYSIS
    ═══════════════════════════════════════════════════════════

    Primary Issue: Volume Group Creation Failure on worker-0

    Chain of Impact:
    1. Device /dev/sdb on worker-0 has existing ext4 filesystem
    2. vg-manager cannot create volume group vg1
    3. Volume group missing on worker-0
    4. Storage provisioning not functional on worker-0
    5. PVCs with node affinity to worker-0 stuck Pending

    ═══════════════════════════════════════════════════════════
    RECOMMENDATIONS (Prioritized)
    ═══════════════════════════════════════════════════════════

    CRITICAL (Fix Immediately):

    1. Clean device on worker-0:
       # Access the node
       oc debug node/worker-0

       # Wipe the filesystem
       chroot /host wipefs -a /dev/sdb

       # Verify device is clean
       chroot /host lsblk /dev/sdb

    2. Restart vg-manager to recreate volume group:
       oc delete pod -n openshift-lvm-storage -l app.kubernetes.io/component=vg-manager

    3. Verify volume group created:
       oc debug node/worker-0 -- chroot /host vgs

    4. Restart vg-manager on worker-0:
       oc delete pod -n openshift-lvm-storage -l app.kubernetes.io/component=vg-manager

    5. Verify PVCs bind:
       oc get pvc -A | grep Pending

    WARNINGS (Address Soon):

    6. Expand thin pool or clean up unused volumes:
       # List logical volumes by size
       oc debug node/master-0 -- chroot /host lvs --units g

       # Consider expanding thin pool or removing old volumes

    ═══════════════════════════════════════════════════════════
    NEXT STEPS
    ═══════════════════════════════════════════════════════════

    1. Review and execute recommendations above
    2. Monitor LVMS operator logs:
       oc logs -n openshift-lvm-storage deployment/lvms-operator -f
    3. Check volume group status after fixes:
       /lvms:analyze --live --component volumes
    4. If issues persist, collect must-gather:
       oc adm must-gather --image=quay.io/lvms_dev/lvms-must-gather:latest

    ═══════════════════════════════════════════════════════════
    ADDITIONAL RESOURCES
    ═══════════════════════════════════════════════════════════

    - LVMS Documentation:
      https://github.com/openshift/lvm-operator/tree/main/docs

    - Troubleshooting Guide:
      https://github.com/openshift/lvm-operator/blob/main/docs/troubleshooting.md

    - TopoLVM Documentation:
      https://github.com/topolvm/topolvm

    Logs to Review:
    - /namespaces/openshift-lvm-storage/pods/lvms-operator-*/logs/manager/current.log
    - /namespaces/openshift-lvm-storage/pods/vg-manager-*/logs/vg-manager/current.log
    ```

12. **Component-Specific Analysis**:

    If user requests specific component:
    - Run only relevant analysis sections
    - Provide focused output for that component
    - Skip irrelevant checks

## Return Value

The command outputs a comprehensive analysis report to stdout:

**Format:**
- Structured sections for each component
- Visual indicators: ✓ (healthy), ⚠ (warning), ❌ (critical)
- Root cause analysis connecting related issues
- Prioritized recommendations with specific commands
- Links to relevant logs and documentation

**Success States:**
- **All Healthy**: Summary of healthy state with key metrics
- **Warnings Found**: Issues identified with recommendations
- **Critical Issues**: Detailed diagnosis with step-by-step remediation

## Examples

1. **Analyze live cluster (full analysis)**:
   ```
   /lvms:analyze --live
   ```
   Connects to current cluster and runs comprehensive LVMS diagnostics.

2. **Analyze must-gather data**:
   ```
   /lvms:analyze ./must-gather/registry-ci-openshift-org-origin-4-18.../
   ```
   Analyzes LVMS must-gather data offline.

3. **Check only PVC issues on live cluster**:
   ```
   /lvms:analyze --live check pending PVCs
   ```
   Runs focused analysis on storage/PVC issues only.

4. **Analyze volume groups in must-gather**:
   ```
   /lvms:analyze ./must-gather/... --component volumes
   ```
   Analyzes only volume group status and configuration.

5. **Debug operator health**:
   ```
   /lvms:analyze --live analyze operator pods
   ```
   Focuses on LVMS operator and TopoLVM component health.

6. **Check specific node's storage**:
   ```
   /lvms:analyze --live check devices on worker-0
   ```
   Analyzes block devices and volume groups on specific node.

7. **Analyze pod logs only (must-gather)**:
   ```
   /lvms:analyze ./must-gather/... --component logs
   ```
   Extracts and analyzes error messages from vg-manager and lvms-operator pod logs.

8. **Analyze pod logs on live cluster**:
   ```
   /lvms:analyze --live --component logs
   ```
   Retrieves and analyzes current pod logs from running cluster.

## Notes

- **Must-Gather Path**: Always use the subdirectory containing `cluster-scoped-resources/` and `namespaces/`, not the parent directory
- **Namespace Compatibility**: LVMS namespace changed from `openshift-storage` (older versions) to `openshift-lvm-storage` (newer versions). The command automatically detects and uses the correct namespace in both live clusters and must-gathers
- **Live Cluster Access**: Requires read permissions to LVMS namespace and cluster-scoped resources
- **Node Debugging**: For device-level analysis on live clusters, the command uses `oc debug node/...` which requires elevated privileges
- **Pod Log Analysis**: Available for both live clusters (via `oc logs`) and must-gather data. Parses JSON-formatted logs, extracts errors/warnings, and deduplicates repeated reconciliation errors
- **Python Script**: If `analyze_lvms.py` script is available, it will be used for must-gather analysis for better performance
- **Cross-Component Correlation**: The analysis attempts to correlate issues across components (e.g., missing VG → pod crash → PVC pending → pod log errors)
- **Actionable Output**: Focuses on root causes and specific remediation steps rather than raw data dumps
- **Safety**: All recommendations include verification steps; no destructive operations are performed automatically

## Arguments

- **$1** (must-gather-path): Optional. Path to LVMS must-gather directory. If provided without `--live`, assumes must-gather analysis mode.
  - Example: `./must-gather/registry-ci-openshift-org-origin-4-18.../`

- **--live**: Optional flag. Use live cluster analysis mode. Requires active `oc` connection.
  - Example: `/lvms:analyze --live`

- **--component**: Optional. Focus analysis on specific component:
  - `storage` / `pvc` / `volumes`: PVC and PV analysis
  - `operator` / `pods`: Operator health and pod status
  - `vg` / `volume-group`: Volume group configuration
  - `node` / `devices`: Node-level device analysis
  - `logs`: Pod log analysis
  - `all`: Full analysis (default)

- **Additional text**: Natural language text describing what to focus on (parsed for component keywords)
  - Example: `check why PVCs are pending`
  - Example: `analyze volume group on worker-0`

## Troubleshooting

**Cannot connect to cluster:**
```bash
# Verify oc is configured
oc whoami
oc cluster-info

# Check namespace exists (try both old and new namespaces)
oc get namespace openshift-lvm-storage 2>/dev/null || \
  oc get namespace openshift-storage
```

**Must-gather path not found:**
```bash
# Verify directory structure (checks both namespaces)
ls {must-gather-path}/namespaces/openshift-lvm-storage 2>/dev/null || \
  ls {must-gather-path}/namespaces/openshift-storage

# Use the correct subdirectory
ls {must-gather-path}/*/namespaces/openshift-lvm-storage 2>/dev/null || \
  ls {must-gather-path}/*/namespaces/openshift-storage
```

**Permission denied for node debugging:**
```bash
# Check permissions
oc auth can-i debug node

# May require cluster-admin or privileged SCC
```

**Python script not found:**
- Command will fall back to built-in analysis
- For better performance, ensure script exists at:
  `plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py`

## Related Commands

- `/must-gather:analyze` - General cluster analysis
- `/olm:diagnose` - OLM and operator troubleshooting
- `/ci:analyze-prow-job-test-failure` - CI test failure analysis

## Additional Resources

- [LVMS GitHub Repository](https://github.com/openshift/lvm-operator)
- [LVMS Troubleshooting Guide](https://github.com/openshift/lvm-operator/blob/main/docs/troubleshooting.md)
- [TopoLVM Documentation](https://github.com/topolvm/topolvm)
- [OpenShift Storage Documentation](https://docs.openshift.com/container-platform/latest/storage/index.html)
