---
description: Analyze IPsec configuration and tunnel status from must-gather
argument-hint: [must-gather-path]
---

## Name
must-gather:ipsec

## Synopsis
```
/must-gather:ipsec [must-gather-path] [node-name]
```

## Description

The `ipsec` command analyzes IPsec configuration and tunnel status from OpenShift must-gather data. It examines the `ovn-ipsec-host` daemonset pods that run on each node to configure IPsec tunnels, and verifies the establishment status of all IPsec connections.

**What it analyzes:**
- **IPsec Configuration**: Checks if IPsec is enabled in the cluster network configuration
- **ovn-ipsec-host Pods**: Status of the daemonset pods that configure IPsec on each node
- **Tunnel Status**: Per-pod connection status by parsing IPsec configuration and status logs

The command parses the `network_logs/ipsec/<pod>_ipsec.d/openshift.conf` file to extract connection names, then checks the corresponding status logs to verify that each connection has established an IKE SA (indicated by the presence of `ESTABLISHED_CHILD_SA` in the status logs).

**Node Filtering**: You can optionally specify a node name to analyze only the IPsec pod and tunnels for that specific node. This is useful when troubleshooting node-specific connectivity issues. Use `all` or omit the parameter to analyze all nodes.

## Prerequisites

The must-gather should contain:
```plaintext
cluster-scoped-resources/
└── operator.openshift.io/
    └── networks/
        └── cluster.yaml                            # Cluster network configuration (IPsec settings)

namespaces/
└── openshift-ovn-kubernetes/
    └── pods/
        └── ovn-ipsec-host-<pod-id>/               # Pod metadata and status
            └── ovn-ipsec-host-<pod-id>.yaml

network_logs/
└── ipsec/
    ├── <pod>_ipsec.d/
    │   └── openshift.conf                          # IPsec connection configurations
    └── status/
        └── <pod>.log                               # Connection status logs
```

**Analysis Script:**

The script is located in the plugin directory:
```plaintext
plugins/must-gather/skills/must-gather-analyzer/scripts/analyze_ipsec.py
```

Claude will automatically locate it from the plugin installation.

## Implementation

The command performs the following steps:

1. **Parse Arguments**:
   - Extract must-gather path (required)
   - Extract node name filter (optional) - if provided, only analyze that node's IPsec pod and tunnels

2. **Check IPsec Configuration**:
   - Read cluster network configuration from `cluster-scoped-resources/operator.openshift.io/networks/cluster.yaml`
   - Check if `ipsecConfig` is present under `ovnKubernetesConfig`
   - Extract IPsec mode and other configuration details

3. **Check ovn-ipsec-host Pods**:
   - Locate all `ovn-ipsec-host-*` pods in the `openshift-ovn-kubernetes` namespace
   - If node filter is specified, only include pods running on that node
   - Check pod status (Running, CrashLoopBackOff, etc.)
   - Count ready containers and restart counts
   - Map pods to their corresponding nodes

4. **Analyze Tunnel Status** (from `network_logs/ipsec/`):
   - For each `<pod>_ipsec.d/` directory:
     - Match pod to node name using pod metadata
     - If node filter is specified, skip pods not on that node
     - Parse `<pod>_ipsec.d/openshift.conf` to extract connection names (lines starting with `conn <name>`)
     - Locate status log in `network_logs/ipsec/status/<pod>.log` (status directory is a sibling, not inside the pod directory)
     - For each connection, grep the status log for the connection name
     - Check if `ESTABLISHED_CHILD_SA` is present in the matching lines
   - Report established vs. not established connections per pod

5. **Generate Summary**:
   - Overall IPsec health status
   - Count of total, established, and failed connections (for analyzed nodes)
   - List of issues detected (if any)

## Return Value

The command outputs a comprehensive analysis including:

```plaintext
====================================================================================================
IPSEC CONFIGURATION
====================================================================================================
Status: ✓ ENABLED
Mode:   Full

====================================================================================================
OVN-IPSEC-HOST PODS (Daemonset)
====================================================================================================

Found 3 ovn-ipsec-host pod(s):
NAME                                      READY      STATUS          RESTARTS   NODE
ovn-ipsec-host-abc123                     1/1        Running         0          worker-0
ovn-ipsec-host-def456                     1/1        Running         0          worker-1
ovn-ipsec-host-ghi789                     1/1        Running         0          master-0

====================================================================================================
IPSEC TUNNEL STATUS
====================================================================================================

Total Connections: 6
Established:       5 ✓
Not Established:   1 ✗

----------------------------------------------------------------------------------------------------
Pod: ovn-ipsec-host-abc123
----------------------------------------------------------------------------------------------------

  Connections (2):
  CONNECTION NAME                                    STATUS          INFO
  -----------------------------------------------------------------------------------------------
  ✓ conn-to-10-0-1-20                                ESTABLISHED     ESTABLISHED_CHILD_SA
  ✗ conn-to-10-0-1-30                                NOT ESTABLISHED No ESTABLISHED_CHILD_SA found

====================================================================================================
SUMMARY
====================================================================================================

⚠ Issues Detected:
1. 1 IPsec connections not established
```

## Examples

1. **Analyze IPsec for all nodes**:
   ```bash
   /must-gather:ipsec ./must-gather.local.123456789
   ```
   Shows complete IPsec analysis including configuration, all pods, and tunnel status for all nodes.

2. **Analyze IPsec for a specific node**:
   ```bash
   /must-gather:ipsec ./must-gather.local.123456789 worker-0
   ```
   Shows IPsec analysis filtered to only the `worker-0` node. Useful when troubleshooting node-specific issues.

3. **Explicitly analyze all nodes**:
   ```bash
   /must-gather:ipsec ./must-gather.local.123456789 all
   ```
   Same as omitting the node parameter - analyzes all nodes.

4. **Interactive usage without path**:
   ```bash
   /must-gather:ipsec
   ```
   The command will ask for the must-gather path.

5. **Check if IPsec is enabled**:
   ```bash
   /must-gather:ipsec ./must-gather/...
   ```
   The output's "IPSEC CONFIGURATION" section shows whether IPsec is enabled and its mode.

6. **Verify tunnel establishment for specific node**:
   ```bash
   /must-gather:ipsec ./must-gather/... master-0
   ```
   The "IPSEC TUNNEL STATUS" section shows which connections are established on master-0.

7. **Troubleshoot connection failures on a node**:
   ```bash
   /must-gather:ipsec ./must-gather/... worker-1
   ```
   Look for connections with "NOT ESTABLISHED" status on worker-1 - these indicate tunnels that failed to come up.

## Error Handling

**Missing network_logs/ipsec directory:**
```plaintext
No IPsec tunnel data found in network_logs/ipsec/
(Expected location: network_logs/ipsec/<pod>_ipsec.d/)
```
This indicates either IPsec is not enabled or the must-gather didn't collect IPsec logs.

**Missing openshift.conf:**
```plaintext
⚠ Error: openshift.conf not found
```
The IPsec configuration file is missing for this pod.

**Missing status logs:**
```plaintext
⚠ status directory not found
```
Status logs are not available to verify connection state.

**No ovn-ipsec-host pods found:**
```plaintext
No ovn-ipsec-host pods found
(This is expected if IPsec is not enabled)
```
Either IPsec is disabled or the daemonset failed to deploy.

## Notes

- **IPsec Daemonset**: The `ovn-ipsec-host` daemonset runs one pod per node to manage IPsec configuration
- **Connection Naming**: Connections in `openshift.conf` follow the pattern `conn <name>`
- **Establishment Check**: A connection is considered established only if `ESTABLISHED_CHILD_SA` appears in the status log
- **Per-Node Analysis**: Each node has its own set of IPsec connections to other nodes
- **Network Logs Structure**: IPsec logs are collected under `network_logs/ipsec/`
  - `<pod>_ipsec.d/openshift.conf`: Contains all connection definitions for that pod/node
  - `status/<pod>.log`: Contains runtime status information for all connections (status is a sibling directory to the pod directories)

## Use Cases

1. **Verify IPsec Deployment**:
   - Check if IPsec is enabled in cluster configuration
   - Verify ovn-ipsec-host pods are running on all nodes
   - Confirm certificates and secrets are present

2. **Troubleshoot Connectivity Issues**:
   - Identify which IPsec tunnels failed to establish
   - Check for pod failures or high restart counts
   - Look for patterns in failed connections (e.g., all to same node)

3. **Validate Cluster Upgrade**:
   - Verify IPsec remains functional after upgrade
   - Check for certificate issues
   - Ensure all connections re-established

4. **Audit IPsec Health**:
   - Get count of total vs. established connections
   - Identify nodes with connection problems
   - Review pod status across all nodes

## Arguments

- **$1** (must-gather-path): Optional. Path to the must-gather directory. If not provided, user will be prompted.
- **$2** (node-name): Optional. Node name to filter analysis. If provided, only analyze the IPsec pod and tunnels for that specific node. Use `all` or omit to analyze all nodes. Examples: `worker-0`, `master-1`.
