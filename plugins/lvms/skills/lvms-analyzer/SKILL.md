---
name: LVMS Analyzer
description: Analyzes LVMS must-gather data to diagnose storage issues
---

# LVMS Analyzer Skill

This skill provides detailed guidance for analyzing LVMS (Logical Volume Manager Storage) must-gather data to identify and troubleshoot storage issues.

## When to Use This Skill

Use this skill when:
- Analyzing LVMS must-gather data offline
- Diagnosing PVCs stuck in Pending state
- Investigating LVMCluster readiness issues
- Troubleshooting volume group creation failures
- Debugging TopoLVM CSI driver problems
- Checking operator health in LVMS namespace

This skill is automatically invoked by the `/lvms:analyze` command when working with must-gather data.

## Prerequisites

**Required:**
- LVMS must-gather directory extracted and accessible
- Must-gather contains LVMS namespace directory:
  - `namespaces/openshift-lvm-storage/` (newer versions)
  - OR `namespaces/openshift-storage/` (older versions)
- Python 3.6 or higher installed
- PyYAML library: `pip install pyyaml`

**Namespace Compatibility:**
- LVMS namespace changed from `openshift-storage` to `openshift-lvm-storage` in recent versions
- The analysis script automatically detects which namespace is present
- Both namespaces are fully supported for backward compatibility

**Must-Gather Structure:**
```
must-gather/
└── registry-{image-registry}-lvms-must-gather-{version}-sha256-{hash}/
    ├── cluster-scoped-resources/
    │   ├── core/
    │   │   └── persistentvolumes/
    │   │       └── pvc-*.yaml               # Individual PV files
    │   ├── storage.k8s.io/
    │   │   └── storageclasses/
    │   │       ├── lvms-vg1.yaml
    │   │       └── lvms-vg1-immediate.yaml
    │   └── security.openshift.io/
    │       └── securitycontextconstraints/
    │           └── lvms-vgmanager.yaml
    ├── namespaces/
    │   └── openshift-lvm-storage/           # or openshift-storage for older versions
    │       ├── oc_output/                   # IMPORTANT: Primary location for LVMS resources
    │       │   ├── lvmcluster.yaml          # Full LVMCluster resource with status
    │       │   ├── lvmcluster               # Text output (oc describe)
    │       │   ├── lvmvolumegroup           # Text output
    │       │   ├── lvmvolumegroupnodestatus # Text output
    │       │   ├── logicalvolume            # Text output
    │       │   ├── pods                     # Text output (oc get pods)
    │       │   └── events                   # Text output
    │       ├── pods/
    │       │   ├── lvms-operator-{hash}/
    │       │   │   └── lvms-operator-{hash}.yaml
    │       │   └── vg-manager-{hash}/
    │       │       └── vg-manager-{hash}.yaml
    │       └── apps/                        # May contain deployments/daemonsets
    └── ...
```

**Key Note:** LVMS resources are primarily in the `oc_output/` directory, with `lvmcluster.yaml` being the most important file containing full cluster and node status.

## Implementation Steps

### Step 1: Validate Must-Gather Path

Before running analysis, verify the must-gather directory structure:

```bash
# Check if LVMS namespace directory exists (try both namespaces)
ls {must-gather-path}/namespaces/openshift-lvm-storage 2>/dev/null || \
  ls {must-gather-path}/namespaces/openshift-storage

# Verify required resource directories
ls {must-gather-path}/cluster-scoped-resources/core/persistentvolumes
```

**Namespace Detection:**
The analysis script automatically detects which namespace is present:
- Newer LVMS versions use `openshift-lvm-storage`
- Older LVMS versions use `openshift-storage`
- The script will inform you which namespace was detected

**Common Issue:** User provides parent directory instead of subdirectory
- Must-gather extracts to a directory like `must-gather.local.12345/`
- Inside is a subdirectory like `registry-ci-openshift-org-origin-4-18.../`
- Always use the **subdirectory** (the one with cluster-scoped-resources/ and namespaces/)

**Handling:**
```bash
# If user provides parent directory, try to find the correct subdirectory
if [ ! -d "{path}/namespaces/openshift-lvm-storage" ] && \
   [ ! -d "{path}/namespaces/openshift-storage" ]; then
    # Try to find either namespace
    find {path} -type d \( -name "openshift-lvm-storage" -o -name "openshift-storage" \) -path "*/namespaces/*"
    # Suggest the correct path to user
fi
```

### Step 2: Run Analysis Script

Use the Python analysis script for structured analysis:

```bash
python3 plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py \
    {must-gather-path}
```

**Script Location:**
- Always use: `plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py`
- Use relative path from repository root
- Script is part of the LVMS plugin

**Component-Specific Analysis:**

For focused analysis on specific components:

```bash
# Analyze only storage/PVC issues
python3 plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py \
    {must-gather-path} --component storage

# Analyze only operator health
python3 plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py \
    {must-gather-path} --component operator

# Analyze only volume groups
python3 plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py \
    {must-gather-path} --component volumes

# Analyze only pod logs
python3 plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py \
    {must-gather-path} --component logs
```

### Step 3: Interpret Analysis Results

The script provides structured output across several sections:

**1. LVMCluster Status**

Key fields to check:
- `state`: Should be "Ready"
- `ready`: Should be true
- `conditions`: All should have status "True"
  - ResourcesAvailable: Resources deployed successfully
  - VolumeGroupsReady: VGs created on all nodes

Example healthy output:
```
LVMCluster: lvmcluster-sample
✓ State: Ready
✓ Ready: true

Conditions:
✓ ResourcesAvailable: True
✓ VolumeGroupsReady: True
```

Example unhealthy output (real case from must-gather):
```
LVMCluster: my-lvmcluster
❌ State: Degraded
❌ Ready: false

Conditions:
✓ ResourcesAvailable: True
  Reason: ResourcesAvailable
  Message: Reconciliation is complete and all the resources are available
❌ VolumeGroupsReady: False
  Reason: VGsDegraded
  Message: One or more VGs are degraded
```

**2. Volume Group Status**

Checks volume group creation per node and device availability:

Example output (real case from must-gather):
```
Volume Group/Device Class: vg1
Nodes: 3

  Node: ocpnode1.ocpiopex.growipx.com
  ⚠  Status: Progressing

  Devices: /dev/mapper/3600a098038315048302b586c38397562, /dev/mapper/mpatha

  Excluded devices: 24 device(s)
    - /dev/sdb: /dev/sdb has children block devices and could not be considered
    - /dev/sdb4: /dev/sdb4 has an invalid filesystem signature (xfs) and cannot be used
    - /dev/mapper/3600a098038315047433f586c53477272: has an invalid filesystem signature (xfs)
    ... and 21 more excluded devices

  Node: ocpnode2.ocpiopex.growipx.com
  ❌ Status: Degraded

  Reason:
  failed to create/extend volume group vg1: failed to extend volume group vg1:
  WARNING: VG name vg0 is used by VGs VVnkhP-khYQ-blyc-2TNo-d3cv-b6di-4RbSyY and EUV3xv-ft6q-39xK-J3ki-rglf-9H44-rVIHIq.
  Fix duplicate VG names with vgrename uuid, a device filter, or system IDs.
  Physical volume '/dev/mapper/3600a098038315048302b586c38397578p3' is already in volume group 'vg0'
  Unable to add physical volume '/dev/mapper/3600a098038315048302b586c38397578p3' to volume group 'vg0'
  ... (truncated, see LVMCluster status for full details)

  Devices: /dev/mapper/mpatha
```

This real example shows a common LVMS issue: duplicate volume group names preventing VG extension.

**3. Storage (PVC/PV) Status**

Lists pending or failed PVCs:

Example output:
```
Pending PVCs:

database/postgres-data
❌ Status: Pending (10m)
  Storage Class: lvms-vg1
  Requested: 100Gi

  Recent Events:
  ⚠  ProvisioningFailed: no node has enough free space
```

**4. Operator Health**

Checks LVMS operator pods, deployments, and daemonsets:

Example issues:
```
❌ vg-manager-abc123 (worker-0)
  Status: CrashLoopBackOff
  Restarts: 15
  Error: volume group "vg1" not found
```

**5. Pod Logs**

Extracts and analyzes error/warning messages from pod logs:

Example output (from real must-gather):
```
═══════════════════════════════════════════════════════════
POD LOGS ANALYSIS
═══════════════════════════════════════════════════════════

Pod: vg-manager-nz4pc
Unique errors/warnings: 1

❌ 2025-10-28T10:47:28Z: Reconciler error
  Controller: lvmvolumegroup
  Error Details:
    failed to create/extend volume group vg1: failed to extend volume group vg1:
    WARNING: VG name vg0 is used by VGs WsNJwk-DK3q-tSHg-zvQJ-imF1-SdRv-8oh4e0 ...
    Cannot use /dev/dm-10: device is too small (pv_min_size)
    Command requires all devices to be found.

Pod: lvms-operator-65df9f4dbb-92jwl
Unique errors/warnings: 1

❌ 2025-10-28T10:52:48Z: failed to validate device class setup
  Controller: lvmcluster
  Error: VG vg1 on node Degraded is not in ready state (ocpnode1.ocpiopex.growipx.com)
```

**Key Points:**
- Logs are parsed from JSON format
- Errors are deduplicated (same error repeated in reconciliation loops)
- Shows unique error messages with first occurrence timestamp
- Provides additional context not visible in resource status

### Step 4: Analyze Root Causes

Connect related issues to identify root causes:

**Common Pattern 1: Device Filesystem Conflict**
```
Chain of failures:
1. Device /dev/sdb has existing ext4 filesystem
2. vg-manager cannot create volume group
3. Volume group missing on node
4. PVCs stuck in Pending

Root cause: Device not properly wiped before LVMS use
```

**Common Pattern 2: Insufficient Capacity**
```
Chain of failures:
1. Thin pool at 95% capacity
2. No free space for new volumes
3. PVCs stuck in Pending

Root cause: Insufficient storage capacity or old volumes not cleaned up
```

**Common Pattern 3: Node-Specific Failures**
```
Chain of failures:
1. Volume group missing on specific node
2. TopoLVM CSI driver not functional on that node
3. PVCs with node affinity to that node stuck Pending

Root cause: Node-specific device configuration issue
```

### Step 5: Generate Remediation Plan

Based on analysis results, provide prioritized recommendations:

**CRITICAL Issues (Fix Immediately):**

1. **Device Conflicts:**
   ```bash
   # Clean device on affected node
   oc debug node/{node-name}
   chroot /host wipefs -a /dev/{device}

   # Restart vg-manager to recreate VG
   oc delete pod -n openshift-lvm-storage -l app.kubernetes.io/component=vg-manager
   ```

2. **Pod Crashes:**
   ```bash
   # After fixing underlying issue, restart failed pods
   oc delete pod -n openshift-lvm-storage {pod-name}
   ```

3. **LVMCluster Not Ready:**
   ```bash
   # Review and fix device configuration
   oc edit lvmcluster -n openshift-lvm-storage

   # Ensure devices match actual available devices
   ```

**WARNING Issues (Address Soon):**

1. **Capacity Issues:**
   ```bash
   # Check logical volume usage
   oc debug node/{node} -- chroot /host lvs --units g

   # Remove unused volumes or expand thin pool
   ```

2. **Partial Node Coverage:**
   ```bash
   # Investigate why daemonsets not on all nodes
   oc get nodes --show-labels
   oc describe daemonset -n openshift-lvm-storage
   ```

### Step 6: Provide Next Steps

Always provide clear next steps:

1. **Review logs** (if available in must-gather):
   - Operator logs: `namespaces/openshift-lvm-storage/pods/lvms-operator-*/logs/`
   - VG-manager logs: `namespaces/openshift-lvm-storage/pods/vg-manager-*/logs/`
   - TopoLVM logs: `namespaces/openshift-lvm-storage/pods/topolvm-*/logs/`

2. **Verify fixes** (if cluster is accessible):
   ```bash
   # After implementing fixes, verify:
   oc get lvmcluster -n openshift-lvm-storage
   oc get lvmvolumegroup -A
   oc get pvc -A | grep Pending
   ```

3. **Re-collect must-gather** (if making changes):
   ```bash
   oc adm must-gather --image=quay.io/lvms_dev/lvms-must-gather:latest
   ```

## Error Handling

### Script Execution Errors

**Script not found:**
```bash
# Verify script exists
ls plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py

# Ensure it's executable
chmod +x plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py
```

**Python dependencies missing:**
```bash
# Install PyYAML
pip install pyyaml

# Or use pip3
pip3 install pyyaml
```

**Invalid YAML in must-gather:**
- Script handles YAML parsing errors gracefully
- Reports which files failed to parse
- Continues analysis with available data

### Must-Gather Issues

**Missing directories:**
- Script validates required directories exist
- Reports missing components
- Provides guidance on what's missing

**Incomplete must-gather:**
- If critical resources missing, script reports what it can analyze
- Suggests re-collecting must-gather

## Examples

### Example 1: Full Analysis

```bash
# Run comprehensive analysis
python3 plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py \
    ./must-gather/registry-ci-openshift-org-origin-4-18.../
```

Output:
```
═══════════════════════════════════════════════════════════
LVMCLUSTER STATUS
═══════════════════════════════════════════════════════════

LVMCluster: lvmcluster-sample
❌ State: Failed
❌ Ready: false
...

═══════════════════════════════════════════════════════════
LVMS ANALYSIS SUMMARY
═══════════════════════════════════════════════════════════

❌ CRITICAL ISSUES: 3
  - LVMCluster not Ready (state: Failed)
  - Volume group vg1 not created on worker-0
  - 3 PVCs stuck in Pending state
```

### Example 2: Storage-Only Analysis

```bash
# Focus on PVC issues
python3 plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py \
    ./must-gather/... --component storage
```

Analyzes only:
- PVC/PV status
- Storage class configuration
- Volume provisioning issues

### Example 3: Operator Health Check

```bash
# Check operator components
python3 plugins/lvms/skills/lvms-analyzer/scripts/analyze_lvms.py \
    ./must-gather/... --component operator
```

Analyzes only:
- LVMCluster resource
- Deployments and daemonsets
- Pod status and crashes

## Best Practices

1. **Always validate path first:**
   - Check for `namespaces/openshift-lvm-storage/` directory
   - Use the correct subdirectory, not parent

2. **Run full analysis first:**
   - Get overall health picture
   - Then drill down with component-specific analysis if needed

3. **Correlate issues:**
   - Look for patterns across components
   - Connect pod failures to VG issues to PVC problems

4. **Check timestamps:**
   - Events and pod restarts have timestamps
   - Helps understand sequence of failures

5. **Provide actionable output:**
   - Don't just list issues
   - Explain root causes
   - Give specific remediation steps
   - Include verification commands

6. **Reference documentation:**
   - Link to LVMS troubleshooting guide
   - Point to relevant sections in must-gather logs

## Additional Resources

- [LVMS Troubleshooting Guide](https://github.com/openshift/lvm-operator/blob/main/docs/troubleshooting.md)
- [LVMS Architecture](https://github.com/openshift/lvm-operator/tree/main/docs)
- [TopoLVM Documentation](https://github.com/topolvm/topolvm)
- [Must-Gather Collection](https://github.com/openshift/lvm-operator/tree/main/must-gather)
