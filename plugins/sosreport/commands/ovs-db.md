---
description: Analyze OVS data from sosreport (text files or database)
argument-hint: "[sosreport-path] [--db] [--flows-only] [--query <json>]"
---

## Name
sosreport:ovs-db

## Synopsis
```
/sosreport:ovs-db [sosreport-path] [--db] [--flows-only] [--query <json>]
```

## Description

The `ovs-db` command analyzes Open vSwitch data collected in sosreports. It operates in four modes:

1. **Default mode**: Full analysis - conf.db + all text files (requires ovsdb-tool)
2. **Database mode** (`--db`): Database only - analyze conf.db (requires ovsdb-tool)
3. **Text files mode** (`--flows-only`): Text files only - no ovsdb-tool needed!
4. **Query mode** (`--query`): Run custom OVSDB JSON queries (requires ovsdb-tool)

**What it analyzes:**

### From Database (Default or `--db` Mode)
- **System Information**: OVS version, DPDK settings, external IDs (from conf.db)
- **Bridge Details**: Datapath type (kernel/userspace), fail mode, ports (from conf.db)
- **Interface Inventory**: By type, with pod-to-interface mapping (from conf.db)

### From Text Files (Default or `--flows-only` Mode)
- **System Information**: OVS version, DPDK settings, external IDs (from `ovs-vsctl list Open_vSwitch`)
- **Topology**: Bridges with ports grouped by type (from `ovs-vsctl show`)
- **Bridge Details**: Datapath type, fail mode, CT zones (from `ovs-vsctl list bridge`)
- **Interface Inventory**: By type, with pod-to-interface mapping (from `ovs-vsctl list interface`)
- **OpenFlow Flows**: Flow counts, drop detection, top flows (from `ovs-ofctl dump-flows`)
- **Port Statistics**: RX/TX drops and errors (from `ovs-ofctl dump-ports`)
- **Tunnel Ports**: Configured tunnels (from `ovs-appctl tnl.ports.show`)
- **Datapath Health**: Flow table usage vs limit (from `ovs-appctl upcall.show`)
- **OVS Internal Stats**: Netlink, OpenFlow, OVSDB counters (from `ovs-appctl coverage.show`)

### Custom Queries (`--query` Mode)
- Direct OVSDB table queries (requires ovsdb-tool)

**Modes of operation:**
1. **Default**: Full analysis - conf.db + all text files (requires ovsdb-tool, falls back to text files if not available)
2. **Database** (`--db`): Database only - analyze conf.db (requires ovsdb-tool)
3. **Text Files** (`--flows-only`): Text files only - no ovsdb-tool needed
4. **Query Mode** (`--query`): Run custom OVSDB JSON queries (requires ovsdb-tool)

## Prerequisites

**Default mode** (full analysis):
- `ovsdb-tool` must be installed (from openvswitch package)
- Falls back to `--flows-only` if ovsdb-tool not found
- Sosreport with `sos_commands/openvswitch/` directory and `conf.db`

**Database mode** (`--db`):
- `ovsdb-tool` must be installed (from openvswitch package)
  - Check: `which ovsdb-tool`
  - Fedora/RHEL: `sudo dnf install openvswitch`
  - Ubuntu/Debian: `sudo apt install openvswitch-common`
- Sosreport with `conf.db` file

**Text files mode** (`--flows-only`):
- No special tools needed - works out of the box!
- Sosreport with `sos_commands/openvswitch/` directory

**Query mode** (`--query`):
- `ovsdb-tool` must be installed
- Incompatible with `--flows-only`

**Sosreport Data:**

The sosreport should contain:
```
sosreport-hostname-date/
├── etc/openvswitch/conf.db              (for --db mode)
│   OR var/lib/openvswitch/conf.db
└── sos_commands/openvswitch/            (default mode)
    ├── ovs-vsctl_-t_5_show              (topology)
    ├── ovs-vsctl_-t_5_list_*            (tables)
    ├── ovs-ofctl_dump-flows_<bridge>    (flows)
    ├── ovs-ofctl_dump-ports_<bridge>    (port stats)
    ├── ovs-appctl_coverage.show         (internal stats)
    ├── ovs-appctl_upcall.show           (datapath health)
    └── ...
```

**Analysis Script:**

The script is bundled with this plugin:
```
<plugin-root>/skills/ovs-db-analysis/scripts/analyze_ovs_db.py
```

## Implementation

The command performs the following steps:

1. **Locate Analysis Script**:
   ```bash
   SCRIPT_PATH=$(find ~ -name "analyze_ovs_db.py" -path "*/sosreport/skills/ovs-db-analysis/scripts/*" 2>/dev/null | head -1)
   
   if [ -z "$SCRIPT_PATH" ]; then
       echo "ERROR: analyze_ovs_db.py script not found."
       exit 1
   fi
   ```

2. **Handle Input Path**:
   - If sosreport archive (`.tar.gz`, `.tar.xz`): Extract to temporary directory
   - If directory: Use directly
   - If `conf.db` file: Use database mode automatically

3. **Run Analysis**:
   - **Default mode**: Parse text files in `sos_commands/openvswitch/`
   - **--db mode**: Query `conf.db` using `ovsdb-tool`
   - **--query mode**: Execute custom OVSDB query

4. **Analyze Data**:
   - Parse topology and system info
   - Parse bridge and interface details
   - Analyze OpenFlow flows (in default and `--flows-only` modes)
   - Report drops, errors, and health indicators

## Return Value

The command outputs structured analysis:

```
================================================================================
OVS ANALYSIS - sosreport-hostname-2024-01-15
================================================================================
Mode: Text file analysis (no ovsdb-tool required)

================================================================================
OVS SYSTEM INFORMATION
================================================================================

  Field                     Value
  ------------------------- --------------------------------------------------
  OVS Version               "3.3.4-62.el9fdp"
  DB Version                "8.5.0"
  System Type               rhcos
  System Version            "4.16"
  DPDK Initialized          false
  Datapath Types            [netdev, system]

  External IDs:
    hostname: master2.example.com
    ovn-encap-ip: 10.32.110.5
    ovn-encap-type: geneve
    ovn-bridge-mappings: physnet:br-ex

================================================================================
OVS TOPOLOGY
================================================================================

  System UUID: 7e9a3f70-86fa-4578-a849-4fd807a64a10
  Total Bridges: 2

  Bridge: br-ex
    ports: 3
      internal: br-ex
      patch: patch-br-ex-to-br-int
      system: nm-bond

  Bridge: br-int
    fail_mode: secure
    datapath_type: system
    ports: 12
      geneve: 9 ports
      internal: ovn-k8s-mp0, br-int
      patch: patch-br-int-to-br-ex

================================================================================
BRIDGE DETAILS
================================================================================

  Bridge: br-int
  ------------------------------------------------------------
    Datapath: system (kernelspace)
    Fail Mode: secure
    Datapath ID: "00005ac5dfc26094"
    Port Count: 12
    CT Zones: 19

================================================================================
INTERFACE ANALYSIS
================================================================================

  Total Interfaces: 15

  By Type:
    geneve: 9 interfaces
    internal: br-int, ovn-k8s-mp0, br-ex
    patch: patch-br-ex-to-br-int, patch-br-int-to-br-ex
    system: nm-bond

  Pod Interfaces: 0
  ----------------------------------------------------------------------
    (none on this node)

================================================================================
OPENFLOW ANALYSIS
================================================================================

  Bridge: br-int
  ----------------------------------------------------------------------
  Total flows: 2,017
  Flows with hits: 318
  Drop flows: 150 (9 actively dropping)
  Tables used: 53 (0-79)
  Top tables by flow count:
    Table 21: 200 flows
    Table 13: 163 flows

  ⚠️  ACTIVE DROP FLOWS (9):
    table=40, priority=0, packets=8,105
    table=79, priority=100, packets=1,356
      match: ip,reg14=0x2,metadata=0x5,dl_src=00:62:0b:ea:b5:e0

--------------------------------------------------------------------------------
PORT STATISTICS
--------------------------------------------------------------------------------

  Bridge: br-int
  Total ports: 12

  ⚠️  Ports with drops/errors:
    Port 1: drops=11, errors=0
      RX: 852 pkts, 23,856 bytes
      TX: 7 pkts, 826 bytes

--------------------------------------------------------------------------------
DATAPATH FLOW TABLE HEALTH
--------------------------------------------------------------------------------

  Current flows: 155 / 200,000 (0.1% used)
  Average: 156, Max seen: 215
  ✓ Flow table healthy

--------------------------------------------------------------------------------
OVS INTERNAL STATISTICS
--------------------------------------------------------------------------------

  METRIC                    DESCRIPTION                         TOTAL           RATE/s
  ------------------------- ----------------------------------- --------------- ----------
  netlink_sent              Netlink messages sent               46,153          12.8
  netlink_received          Netlink messages received           56,078          15.5
  txn_success               OVSDB transactions (success)        471             0.1
```

## Examples

### Default Mode (Full Analysis)

1. **Full analysis** (requires ovsdb-tool):
   ```
   /sosreport:ovs-db /tmp/sosreport-server01-2024-01-15/
   ```
   Analyzes conf.db + all text files. Falls back to text files if ovsdb-tool not installed.

2. **Analyze from archive**:
   ```
   /sosreport:ovs-db /tmp/sosreport-server01-2024-01-15.tar.xz
   ```
   Extracts and runs full analysis.

### Database Mode (`--db`)

3. **Database only** (requires ovsdb-tool):
   ```
   /sosreport:ovs-db /tmp/sosreport/ --db
   ```
   Queries `conf.db` only - no flow analysis.

4. **Analyze conf.db directly**:
   ```
   /sosreport:ovs-db /var/lib/openvswitch/conf.db
   ```
   Automatically uses database mode.

### Text Files Mode (`--flows-only`)

5. **Text files only** (no ovsdb-tool needed):
   ```
   /sosreport:ovs-db /tmp/sosreport/ --flows-only
   ```
   Parses all text files in `sos_commands/openvswitch/`.

### Query Mode (`--query`)

6. **Query all bridges**:
   ```
   /sosreport:ovs-db /tmp/sosreport/ --query '["Open_vSwitch", {"op":"select", "table":"Bridge", "where":[], "columns":["name","datapath_type"]}]'
   ```

7. **Query VXLAN tunnels**:
   ```
   /sosreport:ovs-db /tmp/sosreport/ --query '["Open_vSwitch", {"op":"select", "table":"Interface", "where":[["type","==","vxlan"]], "columns":["name","options"]}]'
   ```

8. **Check interface errors**:
   ```
   /sosreport:ovs-db /tmp/sosreport/ --query '["Open_vSwitch", {"op":"select", "table":"Interface", "where":[], "columns":["name","error","link_state"]}]'
   ```

9. **Check DPDK configuration**:
   ```
   /sosreport:ovs-db /tmp/sosreport/ --query '["Open_vSwitch", {"op":"select", "table":"Open_vSwitch", "where":[], "columns":["dpdk_initialized","other_config"]}]'
   ```

## Error Handling

**Missing ovsdb-tool (only for --db mode):**
```
Error: ovsdb-tool not found. Please install openvswitch package.
  Fedora/RHEL: sudo dnf install openvswitch
  Ubuntu/Debian: sudo apt install openvswitch-common
```
Solution: Either install ovsdb-tool or use default mode (without `--db`).

**sos_commands/openvswitch not found:**
```
Error: sos_commands/openvswitch not found in /path/to/sosreport
```
Solution: Ensure the sosreport has OVS data collected.

**conf.db not found (for --db mode):**
```
Error: conf.db not found in /path/to/sosreport

Looked for conf.db in:
  - etc/openvswitch/conf.db
  - var/lib/openvswitch/conf.db

Tip: Run without --db to analyze text files only
```

## Notes

- **Default mode** runs full analysis (conf.db + text files), requires ovsdb-tool, falls back to text files if not available
- **Database mode** (`--db`) analyzes conf.db only, requires `ovsdb-tool`
- **Text files mode** (`--flows-only`) parses text files only - no special tools needed
- **Query mode** (`--query`) runs raw OVSDB JSON queries, requires ovsdb-tool, incompatible with `--flows-only`
- **Pod-to-Interface Mapping**: Uses `external_ids` and interface naming conventions
- **Drop Detection**: Identifies flows with `actions=drop` that have packet hits
- **Datapath Health**: Checks flow table usage vs limit from upcall stats
- **Query Format**: Accepts raw OVSDB JSON queries in format `["Open_vSwitch", {"op":"select", ...}]`

## Use Cases

1. **Troubleshoot Packet Drops**:
   - Run default analysis to see active drop flows
   - Check port statistics for RX/TX drops

2. **Check Datapath Health**:
   - Review flow table usage vs limit
   - If usage > 90%, flows are being evicted too aggressively

3. **Map Pods to Interfaces**:
   - See pod-to-OVS interface mapping
   - Find which ofport a pod uses

4. **Investigate DPDK Configuration**:
   - Check DPDK initialization status
   - Review datapath types (kernelspace vs userspace)

5. **Debug OVN Connectivity**:
   - Check external_ids for OVN configuration
   - Review tunnel endpoints (geneve ports)
   - Verify patch port connections between bridges

6. **Audit Configuration**:
   - Review all bridges and their ports
   - Check fail modes and CT zones
   - Review OVS version and system info

## Arguments

- **$1** (sosreport-path): Required. Path to sosreport archive (`.tar.gz`, `.tar.xz`), extracted directory, or direct `conf.db` file.
- **--db**: Optional. Database only mode - analyze conf.db only (requires ovsdb-tool).
- **--flows-only**: Optional. Text files only mode - no ovsdb-tool needed.
- **--query, -q** (json-query): Optional. Run a raw OVSDB JSON query (requires ovsdb-tool, incompatible with `--flows-only`).

## See Also

- **OVN Database Analysis**: `/must-gather:ovn-dbs` - For analyzing OVN Northbound/Southbound databases
- **Sosreport Analysis**: `/sosreport:analyze` - Comprehensive sosreport analysis
- **Network Analysis**: `/sosreport:analyze --only network` - Network-focused analysis
