---
description: Analyze OVN databases from a must-gather using ovsdb-tool
argument-hint: [must-gather-path]
---

## Name
must-gather:ovn-dbs

## Synopsis
```
/must-gather:ovn-dbs [must-gather-path] [--node <node-name>] [--query <json>]
```

## Description

The `ovn-dbs` command analyzes OVN Northbound and Southbound databases collected from clusters. It uses `ovsdb-tool` to query the binary database files (`.db`) collected per-node, providing detailed information about the logical network topology, pods, ACLs, and routers on each node.

The command automatically maps ovnkube pods to their corresponding nodes by reading pod specifications from the must-gather data.

**Two modes of operation:**
1. **Standard Analysis** (default): Runs pre-built analysis showing switches, ports, ACLs, and routers
2. **Query Mode** (`--query`): Run custom OVSDB JSON queries for specific data extraction

**What it analyzes:**
- **Per-zone logical network topology**
- **Logical Switches** and their ports
- **Pod Logical Switch Ports** with namespace, pod name, and IP addresses
- **Access Control Lists (ACLs)** with priorities, directions, and match rules
- **Logical Routers** and their ports

**Important:** This command only works with must-gathers from clusters, where each node/zone has its own database files.

## Prerequisites

The must-gather should contain:
```
network_logs/
└── ovnk_database_store.tar.gz
```

**Required Tools:**

- `ovsdb-tool` must be installed (from openvswitch package)
  - Check with: `which ovsdb-tool`
  - Install: `sudo dnf install openvswitch` or `sudo apt install openvswitch-common`

**Analysis Script:**

The script is located in the plugin directory:
```
plugins/must-gather/skills/must-gather-analyzer/scripts/analyze_ovn_dbs.py
```

Claude will automatically locate it from the plugin installation.

## Implementation

The command performs the following steps:

1. **Extract Database Tarball**:
   - Locate `network_logs/ovnk_database_store.tar.gz`
   - Extract if not already extracted
   - Find all `*_nbdb` and `*_sbdb` files

2. **Query Each Zone's Database**:
   For each zone (node), query the Northbound database using `ovsdb-tool query`:

   ```bash
   ovsdb-tool query <zone>_nbdb '["OVN_Northbound", {"op":"select", "table":"<table>", "where":[], "columns":[...]}]'
   ```

3. **Analyze and Display**:
   - **Logical Switches**: Names and port counts
   - **Logical Switch Ports**: Filter for pods (external_ids.pod=true), show namespace, pod name, and IP
   - **ACLs**: Priority, direction, match rules, and actions
   - **Logical Routers**: Names and port counts

4. **Present Zone Summary**:
   - Total counts per zone
   - Detailed breakdowns
   - Sorted and formatted output

## Return Value

The command outputs structured analysis for each node:

```
Found 6 node(s)

================================================================================
Node: ip-10-0-26-145.us-east-2.compute.internal
Pod:  ovnkube-node-79cbh
================================================================================
  Logical Switches:      4
  Logical Switch Ports:  55
  ACLs:                  7
  Logical Routers:       2

  LOGICAL SWITCHES (4):
  NAME                                                         PORTS
  --------------------------------------------------------------------------------
  transit_switch                                               6
  ip-10-0-1-10.us-east-2.compute.internal                      7
  ext_ip-10-0-1-10.us-east-2.compute.internal                  2
  join                                                         2

  POD LOGICAL SWITCH PORTS (5):
  NAMESPACE                                POD                                           IP
  ------------------------------------------------------------------------------------------------------------------------
  openshift-dns                            dns-default-abc123                            10.128.0.5
  openshift-monitoring                     prometheus-k8s-0                              10.128.0.10
  openshift-etcd                           etcd-master-0                                 10.128.0.3
  ...

  ACCESS CONTROL LISTS (7):
  PRIORITY   DIRECTION       ACTION          MATCH
  ------------------------------------------------------------------------------------------------------------------------
  1012       from-lport      allow           inport == @a4743249366342378346 && (ip4.mcast ...
  1011       to-lport        drop            (ip4.mcast || mldv1 || mldv2 || ...
  1001       to-lport        allow-related   ip4.src==10.128.0.2
  ...

  LOGICAL ROUTERS (2):
  NAME                                                         PORTS
  --------------------------------------------------------------------------------
  ovn_cluster_router                                           3
  GR_ip-10-0-1-10.us-east-2.compute.internal                   2
```

## Examples

1. **Analyze all nodes in a must-gather**:
   ```
   /must-gather:ovn-dbs ./must-gather/registry-ci-openshift-org-origin-4-20-...-sha256-abc123/
   ```
   Shows logical network topology for all nodes.

2. **Analyze specific node**:
   ```
   /must-gather:ovn-dbs ./must-gather/.../ --node ip-10-0-26-145
   ```
   Shows OVN database information only for the specified node (supports partial name matching).

3. **Analyze master node**:
   ```
   /must-gather:ovn-dbs ./must-gather/.../ --node master-0
   ```
   Filter to a specific master node using partial name matching.

4. **Interactive usage without path**:
   ```
   /must-gather:ovn-dbs
   ```
   The command will ask for the must-gather path.

5. **Check if pod exists in OVN**:
   ```
   /must-gather:ovn-dbs ./must-gather/.../
   ```
   Then search the output for the pod name to see which node it's on and its IP allocation.

6. **Investigate ACL rules on a specific node**:
   ```
   /must-gather:ovn-dbs ./must-gather/.../ --node worker-1
   ```
   Review the ACL section for a specific node to understand traffic filtering rules.

7. **Run custom OVSDB query** (Query Mode):
   ```
   /must-gather:ovn-dbs ./must-gather/.../ --query '["OVN_Northbound", {"op":"select", "table":"ACL", "where":[["priority", ">", 1000]], "columns":["priority","match","action"]}]'
   ```
   Query ACLs with priority > 1000 across all nodes. Claude can construct the JSON query for any OVSDB table.

8. **Query specific node with custom query**:
   ```
   /must-gather:ovn-dbs ./must-gather/.../ --node master-0 --query '["OVN_Northbound", {"op":"select", "table":"Logical_Switch", "where":[], "columns":["name","ports"]}]'
   ```
   List all logical switches with their ports on master-0.

9. **Query specific table** (Claude constructs JSON):
   Just ask Claude to query a specific OVSDB table and it will construct the appropriate JSON query. For example:
   - "Show all Logical_Router_Static_Route entries"
   - "Find ACLs with action 'drop'"
   - "List Logical_Switch_Port entries where external_ids contains 'openshift-etcd'"

## Error Handling

**Missing ovsdb-tool:**
```
Error: ovsdb-tool not found. Please install openvswitch package.
```
Solution: Install openvswitch: `sudo dnf install openvswitch`

**Missing database tarball:**
```
Error: Database tarball not found: network_logs/ovnk_database_store.tar.gz
```
Solution: Ensure this is a must-gather from an OVN cluster.


**Node not found:**
```
Error: No databases found for node matching 'master-5'

Available nodes:
  - ip-10-0-77-117.us-east-2.compute.internal
  - ip-10-0-26-145.us-east-2.compute.internal
  - ip-10-0-1-194.us-east-2.compute.internal
```
Solution: Use one of the listed node names or a partial match.

## Notes

- **Binary Database Format**: Uses `ovsdb-tool` to read OVSDB binary files directly
- **Per-Node Analysis**: Each node in IC mode has its own database (one NB and one SB per zone)
- **Node Mapping**: Automatically correlates ovnkube pods to nodes by reading pod specs from must-gather
- **Pod Discovery**: Pods are identified by `external_ids` with `pod=true`
- **IP Extraction**: Pod IPs are parsed from the `addresses` field (format: "MAC IP")
- **ACL Priorities**: Higher priority ACLs are processed first (shown at top)
- **Node Filtering**: Supports partial name matching for convenience (e.g., "--node master" matches all masters)
- **Query Mode**: Accepts raw OVSDB JSON queries in the format `["OVN_Northbound", {"op":"select", "table":"...", ...}]`
- **Claude Query Construction**: Claude can automatically construct OVSDB JSON queries based on natural language requests
- **Performance**: Querying large databases may take a few seconds per node

## Use Cases

1. **Verify Pod Network Configuration**:
   - Check if pods are registered in OVN
   - Verify IP address assignments
   - Confirm logical switch port creation

2. **Troubleshoot Connectivity Issues**:
   - Review ACL rules blocking traffic
   - Check if pods are in correct logical switches
   - Verify router configurations

3. **Understand Topology**:
   - See how zones are interconnected via transit_switch
   - Review gateway router configurations
   - Understand logical network structure

4. **Audit Network Policies**:
   - See ACL rules generated from NetworkPolicies
   - Identify overly permissive or restrictive rules
   - Check rule priorities and match conditions

## Arguments

- **$1** (must-gather-path): Optional. Path to the must-gather directory containing network_logs/. If not provided, user will be prompted.
- **--node, -n** (node-name): Optional. Filter analysis to a specific node. Supports partial name matching (e.g., "master-0", "ip-10-0-26-145"). If no match is found, displays list of available nodes.
- **--query, -q** (json-query): Optional. Run a raw OVSDB JSON query instead of standard analysis. Claude can construct the JSON query based on OVSDB transaction format. When provided, outputs raw JSON results instead of formatted analysis.
