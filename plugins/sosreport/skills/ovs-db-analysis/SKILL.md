---
name: OVS Database and Flow Analysis
description: Analyze Open vSwitch data from sosreport
---

# OVS Database and Flow Analysis

This skill provides detailed analysis of Open vSwitch (OVS) data collected via sosreport. It operates in four modes:

1. **Default mode**: Full analysis - conf.db + all text files (requires ovsdb-tool, falls back to text files if not available)
2. **Database mode (`--db`)**: Database only - analyze conf.db (requires ovsdb-tool)
3. **Text files mode (`--flows-only`)**: Text files only - no ovsdb-tool needed
4. **Query mode (`--query`)**: Run custom OVSDB JSON queries (requires ovsdb-tool)

## When to Use This Skill

Use this skill when:
- **Troubleshooting packet drops** - Find drop flows being hit
- **Analyzing flow performance** - View top flows by packet count
- Analyzing OVS configuration from a sosreport
- Troubleshooting bridge, port, or interface issues
- Investigating DPDK vs kernelspace datapath
- Reviewing tunnel configurations (VXLAN, Geneve, GRE)
- Checking port statistics (drops, errors, traffic)
- Mapping Kubernetes pods to OVS interfaces

## Prerequisites

**Default mode** (full analysis):
- **ovsdb-tool** must be installed (from openvswitch package)
- Falls back to `--flows-only` if ovsdb-tool not found
- Sosreport with `sos_commands/openvswitch/` directory and `conf.db`

**Database mode** (`--db`):
- **ovsdb-tool** must be installed (from openvswitch package)
  - Check: `which ovsdb-tool`
  - Fedora/RHEL: `sudo dnf install openvswitch`
  - Ubuntu/Debian: `sudo apt install openvswitch-common`
- Sosreport with `conf.db` file

**Text files mode** (`--flows-only`):
- No special tools needed - works out of the box!
- Sosreport with `sos_commands/openvswitch/` directory

**Query mode** (`--query`):
- **ovsdb-tool** must be installed
- Incompatible with `--flows-only`

## File Locations in Sosreport

The sosreport collects:
```
sosreport-hostname-date/
├── etc/openvswitch/conf.db              (OVS database - for --db mode)
├── var/lib/openvswitch/conf.db          (alternate location)
└── sos_commands/openvswitch/            (default mode uses these)
    ├── ovs-vsctl_-t_5_show              (topology)
    ├── ovs-vsctl_-t_5_list_bridge       (bridge details)
    ├── ovs-vsctl_-t_5_list_interface    (interface details)
    ├── ovs-vsctl_-t_5_list_Open_vSwitch (system info)
    ├── ovs-ofctl_dump-flows_<bridge>    (OpenFlow entries)
    ├── ovs-ofctl_dump-ports_<bridge>    (Port statistics)
    ├── ovs-appctl_coverage.show         (internal stats)
    ├── ovs-appctl_upcall.show           (datapath health)
    ├── ovs-appctl_tnl.ports.show_-v     (tunnel ports)
    └── ...
```

## Analysis Script

The analysis script is located at:
```
<plugin-root>/skills/ovs-db-analysis/scripts/analyze_ovs_db.py
```

## Implementation Steps

### Step 1: Locate the Analysis Script

```bash
SCRIPT_PATH=$(find ~ -name "analyze_ovs_db.py" -path "*/sosreport/skills/ovs-db-analysis/scripts/*" 2>/dev/null | head -1)

if [ -z "$SCRIPT_PATH" ]; then
    echo "ERROR: analyze_ovs_db.py script not found."
    exit 1
fi
```

### Step 2: Run the Analysis

```bash
# Default: Full analysis - conf.db + text files (requires ovsdb-tool)
python3 "$SCRIPT_PATH" /path/to/sosreport-hostname-date/

# Analyze from archive
python3 "$SCRIPT_PATH" /path/to/sosreport-hostname-date.tar.xz

# Database only mode (requires ovsdb-tool)
python3 "$SCRIPT_PATH" /path/to/sosreport/ --db

# Text files only mode (no ovsdb-tool needed)
python3 "$SCRIPT_PATH" /path/to/sosreport/ --flows-only
```

### Step 3: Custom Queries (Optional, requires --db)

For specific investigations, use raw OVSDB queries:

```bash
# Query all bridges
python3 "$SCRIPT_PATH" /path/to/sosreport/ --query '["Open_vSwitch", {"op":"select", "table":"Bridge", "where":[], "columns":["name","datapath_type","fail_mode"]}]'

# Query VXLAN interfaces
python3 "$SCRIPT_PATH" /path/to/sosreport/ --query '["Open_vSwitch", {"op":"select", "table":"Interface", "where":[["type","==","vxlan"]], "columns":["name","options"]}]'

# Query interfaces with errors
python3 "$SCRIPT_PATH" /path/to/sosreport/ --query '["Open_vSwitch", {"op":"select", "table":"Interface", "where":[], "columns":["name","error"]}]'
```

## Analysis Output

The default mode analyzes:

| Analysis | Source File | Description |
|----------|-------------|-------------|
| System Info | `ovs-vsctl_-t_5_list_Open_vSwitch` | OVS/DPDK version, system type, external IDs |
| Topology | `ovs-vsctl_-t_5_show` | Bridge overview with ports grouped by type |
| Bridge Details | `ovs-vsctl_-t_5_list_bridge` | Datapath type, fail mode, CT zones |
| Interfaces | `ovs-vsctl_-t_5_list_interface` | By type, pod interfaces with mapping |
| OpenFlow | `ovs-ofctl_dump-flows_*` | Flow counts, drops, top flows |
| Port Stats | `ovs-ofctl_dump-ports_*` | RX/TX drops and errors |
| Tunnels | `ovs-appctl_tnl.ports.show_-v` | Configured tunnel ports |
| Datapath Health | `ovs-appctl_upcall.show` | Flow table usage vs limit |
| OVS Stats | `ovs-appctl_coverage.show` | Internal counters (netlink, OVSDB, etc.) |

## OpenFlow Analysis Features

| Feature | Description |
|---------|-------------|
| Flow Count | Total flows per bridge (total, drop, with hits) |
| Drop Detection | Flows with `actions=drop` that have packet hits |
| Top Flows | Most active flows sorted by n_packets |
| Table Distribution | Flow counts per OpenFlow table |
| Port Drops | RX/TX drop counters per port |
| Port Errors | RX/TX error counters per port |
| Datapath Health | Flow table usage vs limit (from upcall.show) |
| OVS Stats | Internal statistics (netlink, OpenFlow, OVSDB transactions) |

## OVN Internal Tables (Ignore Drops in These)

When analyzing drop flows in OVN-managed bridges (br-int), **ignore drops in table 44 and tables 64-87** as these are internal OVN mechanics, not security policy or real packet drops.

> **⚠️ Note:** OVN and OVS are complex systems and table mappings can change between releases. Always verify drop analysis against the specific OVN version in use. When in doubt, check the OVN source code for your release.

| Table | Name | Purpose |
|-------|------|---------|
| **44** | **CHK_LB_OUTPUT** | **Loopback prevention - drops packets that would loop back (high volume, normal)** |
| 64 | SAVE_INPORT | Save ingress port for later |
| 65 | LOG_TO_PHY | Logical to physical mapping |
| 66 | MAC_BINDING | MAC binding lookups |
| 67 | MAC_LOOKUP | MAC address table lookups |
| 68-69 | CHK_LB_HAIRPIN | Load balancer hairpin checks |
| 70 | CT_SNAT_HAIRPIN | Conntrack SNAT hairpin |
| 71-72 | GET/LOOKUP_FDB | FDB (forwarding DB) lookups |
| 73-74 | CHK_IN_PORT_SEC | Ingress port security |
| 75 | CHK_OUT_PORT_SEC | Egress port security |
| 76-77 | ECMP_NH | ECMP next-hop handling |
| 78 | CHK_LB_AFFINITY | Load balancer affinity |
| **79** | **MAC_CACHE_USE** | **MAC cache miss (high volume, normal)** |
| 80 | CT_ZONE_LOOKUP | Conntrack zone lookup |
| 81-83 | CT_ORIG_*_LOAD | Conntrack original tuple loading |
| 84 | FLOOD_REMOTE_CHASSIS | Remote chassis flooding |
| 85 | CT_STATE_SAVE | Conntrack state save |
| 86 | CT_ORIG_PROTO_LOAD | Conntrack protocol loading |
| 87 | GET_REMOTE_FDB | Remote FDB lookup |

**Relevant drop tables for troubleshooting:**
- **Table 9**: Ingress ACLs - actual policy drops (look for `reg0=0x8000`)
- **Table 0**: Initial classification drops
- **Tables < 64**: Generally meaningful drops

## Common Analysis Scenarios

### 1. Troubleshooting Packet Drops

```bash
# Quick analysis (default mode, no ovsdb-tool)
python3 "$SCRIPT_PATH" /path/to/sosreport/
```

Look for:
- **ACTIVE DROP FLOWS** section showing flows dropping packets
- **PORT STATISTICS** showing ports with drops/errors

### 2. Checking DPDK Configuration

```bash
# Default mode shows DPDK info from text files
python3 "$SCRIPT_PATH" /path/to/sosreport/

# Or use database mode for custom queries
python3 "$SCRIPT_PATH" /path/to/sosreport/ --query '["Open_vSwitch", {"op":"select", "table":"Open_vSwitch", "where":[], "columns":["dpdk_initialized","other_config"]}]'
```

### 3. Investigating Pod Connectivity

The interface analysis shows pod-to-OVS mapping:
- Interfaces with `external_ids` containing `iface-id`
- Interface names ending with `_h` (veth host side)

### 4. Datapath Health Check

The upcall stats show:
```
DATAPATH FLOW TABLE HEALTH
  Current flows: 155 / 200,000 (0.1% used)
  Average: 156, Max seen: 215
  ✓ Flow table healthy
```

If usage > 90%, flows are being evicted too aggressively.

## Output Example

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
OPENFLOW ANALYSIS
================================================================================

  Bridge: br-int
  ----------------------------------------------------------------------
  Total flows: 2,017
  Flows with hits: 318
  Drop flows: 150 (9 actively dropping)

  ⚠️  ACTIVE DROP FLOWS (9):
    table=40, priority=0, packets=8,105
    table=79, priority=100, packets=1,356
      match: ip,reg14=0x2,metadata=0x5,dl_src=00:62:0b:ea:b5:e0

--------------------------------------------------------------------------------
DATAPATH FLOW TABLE HEALTH
--------------------------------------------------------------------------------

  Current flows: 155 / 200,000 (0.1% used)
  Average: 156, Max seen: 215
  ✓ Flow table healthy
```

## Error Handling

| Error | Solution |
|-------|----------|
| `ovsdb-tool not found` | Install openvswitch package OR use default mode (no --db) |
| `conf.db not found` | Use default mode (analyzes text files instead) |
| `sos_commands/openvswitch not found` | Ensure sosreport has OVS data collected |

## See Also

- [OVN Database Analysis](../../must-gather/skills/must-gather-analyzer/scripts/analyze_ovn_dbs.py) - For OVN NB/SB databases
- [sosreport openvswitch plugin](https://github.com/sosreport/sos/blob/main/sos/report/plugins/openvswitch.py) - What sosreport collects
