---
description: Analyze FRR-K8s BGP configuration and routing state
argument-hint: [must-gather-path] [--verbose] [--node <node>]
---

## Name
must-gather:bgp

## Synopsis
```
/must-gather:bgp [must-gather-path] [--verbose] [--node <node-name>]
```

## Description

The `bgp` command analyzes FRR-K8s (FRRouting Kubernetes) BGP configuration and
routing state from OpenShift must-gather diagnostic data. It provides insights into
BGP neighbor relationships, route advertisements, and routing policies for clusters
using FRR-K8s for network routing.

This command is useful for:
- Diagnosing BGP session establishment issues
- Reviewing BGP neighbor configurations and status
- Analyzing route advertisement and reception policies
- Troubleshooting OpenShift Virtualization VM network routing
- Validating FRR-K8s configuration across nodes
- Detecting synchronization issues between FRR-K8s and FRR daemon
- Identifying unsupported raw configuration usage

**Scope**: This command analyzes FRR-K8s and FRRouting only. MetalLB-specific
analysis is not included.

## Prerequisites

**FRR-K8s Resources in Must-Gather:**

FRR-K8s data is typically located at:
```
must-gather/
└── <registry-path>/
    ├── cluster-scoped-resources/
    │   └── frrk8s.metallb.io/
    │       ├── frrconfigurations/
    │       └── frrnodestates/
    └── namespaces/
        └── openshift-frr-k8s/
            ├── frrk8s.metallb.io/
            │   └── frrconfigurations/
            └── pods/
                └── <frr-pod>/
                    ├── <frr-pod>.yaml
                    └── frr/frr/logs/
                        └── dump_frr
```

**Note**: FRR-K8s must be installed in the cluster for this analysis to be meaningful.

## Implementation

1. **Validate Must-Gather Path**:
   - Verify path exists and is readable
   - Check for FRR-K8s resource presence

2. **Detect FRR-K8s Installation**:
   - Search for `frrk8s.metallb.io` API resources (FRRNodeState CRDs)
   - Check for `openshift-frr-k8s` namespace
   - Parse FRR pod status and count
   - Report installation status

3. **Parse FRRConfiguration CRDs** (Light Analysis):
   - Load all FRRConfiguration resources
   - Detect unsupported raw configuration usage (flag as warning)
   - Validate BFD profile references
   - Build neighbor index for issue correlation (best-effort hints)
   - **Note**: Does NOT attempt to map FRRConfiguration to running config
     - FRR-K8s merges multiple FRRConfigurations with complex logic
     - Mapping is non-trivial and error-prone
     - Focus is on actual running state instead

4. **Parse Actual Running State from dump_frr** (AUTHORITATIVE):
   - Extract `show running-config` output (ground truth for actual FRR config)
   - Parse BGP routers (ASN, VRF assignments)
   - Parse BGP neighbors with state and uptime (displayed as "Up (Established)" / "Down (Active/Idle)")
   - Parse BGP routing tables (IPv4 and IPv6)
   - **Detect route origin** (local vs received from peers):
     - Analyzes nexthop, weight, AS path, and origin code
     - Local routes: nexthop=0.0.0.0/::, weight=32768, origin=i, no AS path
     - Received routes: from BGP peers with actual nexthop
   - Identify route issues:
     - **Invalid routes (missing `*`)** - CRITICAL
     - Routes without best path selected (has `*`, missing `>`)
     - RIB-failure routes (`r` status code)
     - Stale routes (`S` status code)
     - Removed routes (`R` status code)

5. **Parse FRRNodeState** (Reported State):
   - Extract FRR-K8s reported running configuration
   - Check reload status (success/failure/errors)
   - **Compare with dump_frr** to detect synchronization issues
     - Flag discrepancies as critical FRR-K8s sync problems
     - Note if raw config usage may be the cause

6. **Issue Correlation** (Best-Effort Hints):
   - When neighbor or route issues found:
     - Search FRRConfigurations for relevant neighbor definitions
     - Provide hints about which configs may be related
   - **No complex mapping** - just helpful pointers

7. **Analyze FRR Pod Status**:
   - Parse FRR daemon pod YAML files
   - Extract pod status (Running, CrashLoopBackOff, etc.)
   - Extract container restart counts
   - Map pods to nodes for per-node analysis

8. **Generate Report**:
   - Installation summary
   - Per-node BGP status:
     - BGP routers (VRF, ASN)
     - Neighbors (address, ASN, state as "Up (Established)" or "Down (state)", uptime)
     - Routes (IPv4/IPv6 counts with local vs received breakdown)
     - Individual route details in verbose mode with origin indicators
   - Issues detected:
     - Critical issues (session failures, sync problems, invalid routes)
     - Warnings (no routes received, raw config usage, reload errors)
     - Configuration issues (missing BFD profiles, validation errors)
   - Recommendations for remediation

## Return Value

The command runs the analysis script:
```bash
python3 plugins/must-gather/skills/must-gather-analyzer/scripts/analyze_bgp.py <must-gather-path> [options]
```

**Standard Output**:
```
================================================================================
BGP ANALYSIS SUMMARY
================================================================================
FRR-K8s Status:    Installed
Namespace:         openshift-frr-k8s
FRR Pods:          6/6 Running
Configurations:    8 FRRConfiguration resources found

PER-NODE BGP STATUS (from actual running config):

NODE: master-0.ostest.test.metalkube.org
─────────────────────────────────────────────────────────────────
BGP ROUTERS:
VRF             ASN
default         64512
evpnl2          64512

NEIGHBORS:
PEER ADDRESS                             ASN        STATE                UPTIME
192.168.111.3                            64512      Up (Established)     3h15m
fd2e:6f44:5dd8:c956::3                   64512      Up (Established)     3h15m

ROUTES (IPv4) [VRF: default]: 2 total, 2 best (1 local, 1 received)
ROUTES (IPv6) [VRF: default]: 2 total, 2 best (1 local, 1 received)

[... other nodes ...]

================================================================================
ISSUES DETECTED
================================================================================

CRITICAL ISSUES:
✅ No critical issues detected

WARNINGS:
master-0: ⚠️  Multiple VRFs configured (default, extranet) but only default VRF routes available in must-gather

RECOMMENDATIONS:

Issue: Multiple VRFs configured but only default VRF routes available
→ VRF-specific routes not collected in must-gather
→ Only default VRF route data is available for analysis
→ To collect all VRF routes, enhance must-gather collection to include VRF-specific route tables

================================================================================
```

**Verbose Output** (with --verbose):
- Individual route entries with status codes, next hops, and origin indicators (local/received)
- Example:
  ```
  ROUTES (IPv4) [VRF: default]: 2 total, 2 best (1 local, 1 received)
    *>    10.130.0.0/23        via 0.0.0.0                                  (local)
    *>i   172.20.100.0/24      via 192.168.111.3                            (received)
  ```

## Examples

1. **Basic BGP analysis**:
   ```
   /must-gather:bgp ./must-gather.local.123/quay-io-...
   ```
   Analyzes all FRR-K8s BGP configurations and state.

2. **Verbose output**:
   ```
   /must-gather:bgp ./must-gather.local.123/quay-io-... --verbose
   ```
   Shows detailed route information including individual prefixes.

3. **Node-specific analysis**:
   ```
   /must-gather:bgp ./must-gather.local.123/quay-io-... --node master-2
   ```
   Filters analysis to FRR instance on specific node (matches substring).

4. **Combined filters**:
   ```
   /must-gather:bgp ./must-gather.local.123/quay-io-... --node worker-0 --verbose
   ```
   Detailed analysis for specific node.

## Notes

- **FRR-K8s Only**: This command analyzes FRR-K8s configurations. MetalLB-specific
  resources are not included in this analysis.
- **dump_frr is Authoritative**: The `show running-config` output from dump_frr
  is the ground truth for actual FRR state. FRRNodeState should match but may not
  due to FRR-K8s synchronization issues or raw config usage.
- **Raw Config is Unsupported**: Use of `spec.raw.rawConfig` in FRRConfiguration
  is unsupported and can cause synchronization issues. The script flags this usage.
- **Route Status Codes**:
  - `*` = valid route
  - `>` = best path (selected route)
  - `r` = RIB-failure (route rejected)
  - `S` = Stale route
  - `R` = Removed route
  - Missing `*` = INVALID route (critical issue)
- **State Availability**: BGP session state and routes depend on dump_frr file
  availability in must-gather. If unavailable, only configuration analysis is performed.
- **Node Mapping**: FRR-K8s runs one daemon pod per node. The script maps pods to
  nodes for per-node analysis.
- **VRF Support**: Configurations may define multiple VRFs with separate BGP instances.

## Arguments

- **$1** (must-gather-path): Optional. Path to must-gather directory. If not provided,
  will prompt for the path or Claude Code will identify the most recent must-gather.
- **--verbose**: Optional. Show detailed route information with individual prefixes.
- **--node <node-name>**: Optional. Filter to specific node (substring match on node name).
