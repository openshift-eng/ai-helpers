#!/usr/bin/env python3
"""
Analyze OVS (Open vSwitch) data from sosreport.

Four modes:
  1. Default:       Full analysis - conf.db + all text files (requires ovsdb-tool)
  2. --db:          Database only - analyze conf.db (requires ovsdb-tool)
  3. --flows-only:  Text files only - no ovsdb-tool needed
  4. --query:       Run custom OVSDB JSON query (requires ovsdb-tool)

Sosreport structure:
  sosreport-hostname-date/
  ├── etc/openvswitch/conf.db           (used with --db or default)
  │   OR var/lib/openvswitch/conf.db
  └── sos_commands/openvswitch/         (used with --flows-only or default)
      ├── ovs-vsctl_-t_5_show           (topology)
      ├── ovs-vsctl_-t_5_list_*         (bridge/interface/system info)
      ├── ovs-ofctl_dump-flows_<bridge> (OpenFlow entries)
      ├── ovs-ofctl_dump-ports_<bridge> (port statistics)
      ├── ovs-appctl_coverage.show      (internal stats)
      ├── ovs-appctl_upcall.show        (datapath health)
      └── ...
"""

import subprocess
import json
import sys
import os
import tarfile
import argparse
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict


# =============================================================================
# Database Mode Classes (for --db mode)
# =============================================================================

class OVSDatabase:
    """Wrapper for querying OVS database files using ovsdb-tool"""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def query(self, table: str, columns: List[str] = None, where: List = None) -> List[Dict]:
        """Query OVSDB table using ovsdb-tool query command"""
        schema = "Open_vSwitch"

        # Build query
        query_op = {
            "op": "select",
            "table": table,
            "where": where or []
        }

        if columns:
            query_op["columns"] = columns

        query_json = json.dumps([schema, query_op])

        try:
            result = subprocess.run(
                ["ovsdb-tool", "query", str(self.db_path), query_json],
                capture_output=True,
                text=True,
                check=True
            )

            # Parse result - it's a JSON array with one result object
            response = json.loads(result.stdout)
            if response and len(response) > 0:
                first_result = response[0]
                if isinstance(first_result, dict) and "rows" in first_result:
                    return first_result["rows"]
            return []

        except subprocess.CalledProcessError as e:
            print(f"Error querying database: {e.stderr}", file=sys.stderr)
            return []
        except json.JSONDecodeError as e:
            print(f"Error parsing query result: {e}", file=sys.stderr)
            return []

    def get_all_tables(self) -> List[str]:
        """Get list of all tables in the database"""
        return ["Open_vSwitch", "Bridge", "Port", "Interface", "Controller", 
                "Manager", "Mirror", "NetFlow", "sFlow", "IPFIX", "Flow_Table",
                "QoS", "Queue", "SSL", "AutoAttach", "Flow_Sample_Collector_Set",
                "Datapath", "CT_Zone", "CT_Timeout_Policy"]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class OFFlow:
    """Represents a single OpenFlow flow entry"""
    cookie: str
    duration: str
    table: int
    n_packets: int
    n_bytes: int
    priority: int
    match: str
    actions: str
    raw: str
    
    @property
    def is_drop(self) -> bool:
        """Check if this flow drops packets"""
        return self.actions.strip() in ['drop', ''] or 'drop' in self.actions.lower()
    
    @property
    def has_hits(self) -> bool:
        """Check if flow has been matched"""
        return self.n_packets > 0
    
    @property
    def is_ovn_internal_table(self) -> bool:
        """Check if flow is in OVN internal tables - drops here are normal mechanics"""
        # Table 44: loopback prevention (CHK_LB_OUTPUT)
        # Tables 64-87: MAC cache, FDB lookups, conntrack helpers, etc.
        return self.table == 44 or 64 <= self.table <= 87


# OVN internal tables where drops are normal (not policy drops)
# Table 44: loopback prevention (CHK_LB_OUTPUT) - drops packets that would loop back
# Tables 64-87: MAC cache, FDB lookups, conntrack helpers, etc.
# See SKILL.md for full table reference
OVN_INTERNAL_TABLES = {44} | set(range(64, 88))  # Table 44 + Tables 64-87


# =============================================================================
# Text File Parsers (Default Mode)
# =============================================================================

def parse_ovs_vsctl_show(file_path: Path) -> Dict[str, Any]:
    """Parse ovs-vsctl show output for topology"""
    if not file_path.exists():
        return {}
    
    result = {
        'uuid': None,
        'bridges': []
    }
    
    content = file_path.read_text()
    lines = content.strip().split('\n')
    
    if not lines:
        return result
    
    # First line is usually the system UUID
    if lines[0] and not lines[0].startswith(' '):
        result['uuid'] = lines[0].strip()
    
    current_bridge = None
    current_port = None
    
    for line in lines[1:]:
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        
        if stripped.startswith('Bridge '):
            bridge_name = stripped.replace('Bridge ', '').strip()
            current_bridge = {
                'name': bridge_name,
                'fail_mode': None,
                'datapath_type': None,
                'ports': []
            }
            result['bridges'].append(current_bridge)
            current_port = None
            
        elif current_bridge and stripped.startswith('fail_mode:'):
            current_bridge['fail_mode'] = stripped.split(':', 1)[1].strip()
            
        elif current_bridge and stripped.startswith('datapath_type:'):
            current_bridge['datapath_type'] = stripped.split(':', 1)[1].strip()
            
        elif current_bridge and stripped.startswith('Port '):
            port_name = stripped.replace('Port ', '').strip()
            current_port = {
                'name': port_name,
                'interfaces': []
            }
            current_bridge['ports'].append(current_port)
            
        elif current_port and stripped.startswith('Interface '):
            iface_name = stripped.replace('Interface ', '').strip()
            iface = {'name': iface_name, 'type': None, 'options': {}}
            current_port['interfaces'].append(iface)
            
        elif current_port and current_port['interfaces'] and stripped.startswith('type:'):
            current_port['interfaces'][-1]['type'] = stripped.split(':', 1)[1].strip()
            
        elif current_port and current_port['interfaces'] and stripped.startswith('options:'):
            opts_str = stripped.split(':', 1)[1].strip()
            # Parse {key=value, key2=value2}
            if opts_str.startswith('{') and opts_str.endswith('}'):
                opts_inner = opts_str[1:-1]
                for pair in opts_inner.split(', '):
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        current_port['interfaces'][-1]['options'][k] = v.strip('"')
    
    return result


def parse_ovs_vsctl_list_output(file_path: Path) -> List[Dict[str, str]]:
    """Parse ovs-vsctl list output into list of record dicts"""
    if not file_path.exists():
        return []
    
    records = []
    current_record = {}
    
    for line in file_path.read_text().split('\n'):
        if not line.strip():
            if current_record:
                records.append(current_record)
                current_record = {}
            continue
        
        if ':' in line:
            # Handle multi-line values by checking indentation
            if line[0] != ' ' and ':' in line.split()[0] if line.split() else False:
                # Key is the first part before ':'
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    current_record[key] = value
            else:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    current_record[key] = value
    
    if current_record:
        records.append(current_record)
    
    return records


def parse_external_ids(ext_ids_str: str) -> Dict[str, str]:
    """Parse external_ids string like {key=value, key2="value2"}"""
    result = {}
    if not ext_ids_str or ext_ids_str in ['{}', '[]']:
        return result
    
    # Remove braces
    inner = ext_ids_str.strip()
    if inner.startswith('{'):
        inner = inner[1:]
    if inner.endswith('}'):
        inner = inner[:-1]
    
    # Parse key=value pairs
    # Handle quoted values and commas inside quotes
    current_key = ""
    current_val = ""
    in_key = True
    in_quotes = False
    
    for char in inner:
        if char == '"':
            in_quotes = not in_quotes
        elif char == '=' and not in_quotes and in_key:
            in_key = False
        elif char == ',' and not in_quotes:
            if current_key:
                result[current_key.strip()] = current_val.strip().strip('"')
            current_key = ""
            current_val = ""
            in_key = True
        else:
            if in_key:
                current_key += char
            else:
                current_val += char
    
    # Don't forget last pair
    if current_key:
        result[current_key.strip()] = current_val.strip().strip('"')
    
    return result


# =============================================================================
# OpenFlow Parsing (shared by both modes)
# =============================================================================

def parse_flow_line(line: str) -> Optional[OFFlow]:
    """Parse a single OpenFlow flow line"""
    if not line.strip() or line.startswith('OFPST_FLOW') or line.startswith('NXST_FLOW'):
        return None
    
    # Extract fields using regex
    cookie_match = re.search(r'cookie=([^,\s]+)', line)
    duration_match = re.search(r'duration=([^,\s]+)', line)
    table_match = re.search(r'table=(\d+)', line)
    packets_match = re.search(r'n_packets=(\d+)', line)
    bytes_match = re.search(r'n_bytes=(\d+)', line)
    priority_match = re.search(r'priority=(\d+)', line)
    
    # Find actions - everything after "actions="
    actions_match = re.search(r'actions=(.+)$', line)
    
    # Match is between priority and actions
    match_str = ""
    if priority_match and actions_match:
        # Find what's between priority=N, and actions=
        start = priority_match.end()
        end = actions_match.start()
        match_part = line[start:end].strip()
        if match_part.startswith(','):
            match_part = match_part[1:]
        match_str = match_part.strip().rstrip(',')
    
    try:
        return OFFlow(
            cookie=cookie_match.group(1) if cookie_match else "0x0",
            duration=duration_match.group(1) if duration_match else "0s",
            table=int(table_match.group(1)) if table_match else 0,
            n_packets=int(packets_match.group(1)) if packets_match else 0,
            n_bytes=int(bytes_match.group(1)) if bytes_match else 0,
            priority=int(priority_match.group(1)) if priority_match else 0,
            match=match_str,
            actions=actions_match.group(1) if actions_match else "",
            raw=line
        )
    except (ValueError, AttributeError):
        return None


def parse_flow_file(file_path: Path) -> List[OFFlow]:
    """Parse a dump-flows file"""
    flows = []
    if not file_path.exists():
        return flows
    
    for line in file_path.read_text().split('\n'):
        flow = parse_flow_line(line)
        if flow:
            flows.append(flow)
    return flows


def parse_port_stats_file(file_path: Path) -> Dict[str, Dict[str, int]]:
    """Parse ovs-ofctl dump-ports output"""
    stats = {}
    if not file_path.exists():
        return stats
    
    current_port = None
    content = file_path.read_text()
    
    for line in content.split('\n'):
        # Match port line: "  port  1: rx pkts=1234, bytes=5678, drop=0, errs=0, frame=0, over=0, crc=0"
        # or "  port LOCAL: ..."
        port_match = re.match(r'\s*port\s+(\S+):', line)
        if port_match:
            current_port = port_match.group(1)
            stats[current_port] = {}
            
            # Parse rx stats on same line
            rx_match = re.search(r'rx pkts=(\d+), bytes=(\d+), drop=(\d+), errs=(\d+)', line)
            if rx_match:
                stats[current_port]['rx_packets'] = int(rx_match.group(1))
                stats[current_port]['rx_bytes'] = int(rx_match.group(2))
                stats[current_port]['rx_drop'] = int(rx_match.group(3))
                stats[current_port]['rx_errors'] = int(rx_match.group(4))
        
        elif current_port and 'tx pkts=' in line:
            tx_match = re.search(r'tx pkts=(\d+), bytes=(\d+), drop=(\d+), errs=(\d+)', line)
            if tx_match:
                stats[current_port]['tx_packets'] = int(tx_match.group(1))
                stats[current_port]['tx_bytes'] = int(tx_match.group(2))
                stats[current_port]['tx_drop'] = int(tx_match.group(3))
                stats[current_port]['tx_errors'] = int(tx_match.group(4))
    
    return stats


# =============================================================================
# Analysis Functions (Text File Mode)
# =============================================================================

def analyze_system_from_text(ovs_path: Path):
    """Analyze OVS system info from text files"""
    print("\n" + "="*80)
    print("OVS SYSTEM INFORMATION")
    print("="*80)
    
    # Parse Open_vSwitch table
    ovs_file = ovs_path / "ovs-vsctl_-t_5_list_Open_vSwitch"
    records = parse_ovs_vsctl_list_output(ovs_file)
    
    if not records:
        print("  No Open_vSwitch data found")
        return
    
    ovs_info = records[0]
    
    print(f"\n  {'Field':<25} {'Value'}")
    print(f"  {'-'*25} {'-'*50}")
    
    # Key fields to display
    key_fields = [
        ('ovs_version', 'OVS Version'),
        ('db_version', 'DB Version'),
        ('system_type', 'System Type'),
        ('system_version', 'System Version'),
        ('dpdk_initialized', 'DPDK Initialized'),
        ('dpdk_version', 'DPDK Version'),
        ('datapath_types', 'Datapath Types'),
        ('iface_types', 'Interface Types'),
    ]
    
    for field, display_name in key_fields:
        if field in ovs_info:
            value = ovs_info[field]
            if len(str(value)) > 50:
                value = str(value)[:47] + "..."
            print(f"  {display_name:<25} {value}")
    
    # External IDs (important for OVN)
    if 'external_ids' in ovs_info:
        ext_ids = parse_external_ids(ovs_info['external_ids'])
        if ext_ids:
            print(f"\n  External IDs:")
            important_keys = ['hostname', 'ovn-encap-ip', 'ovn-encap-type', 
                            'ovn-bridge-mappings', 'system-id', 'ovn-remote']
            for key in important_keys:
                if key in ext_ids:
                    print(f"    {key}: {ext_ids[key]}")


def analyze_topology_from_text(ovs_path: Path):
    """Analyze OVS topology from ovs-vsctl show output"""
    print("\n" + "="*80)
    print("OVS TOPOLOGY")
    print("="*80)
    
    show_file = ovs_path / "ovs-vsctl_-t_5_show"
    topology = parse_ovs_vsctl_show(show_file)
    
    if not topology.get('bridges'):
        print("  No topology data found")
        return
    
    print(f"\n  System UUID: {topology.get('uuid', 'N/A')}")
    print(f"  Total Bridges: {len(topology['bridges'])}")
    
    for bridge in topology['bridges']:
        print(f"\n  Bridge: {bridge['name']}")
        if bridge['fail_mode']:
            print(f"    fail_mode: {bridge['fail_mode']}")
        if bridge['datapath_type']:
            print(f"    datapath_type: {bridge['datapath_type']}")
        print(f"    ports: {len(bridge['ports'])}")
        
        # Categorize ports
        port_types = defaultdict(list)
        for port in bridge['ports']:
            for iface in port.get('interfaces', []):
                iface_type = iface.get('type') or 'system'
                port_types[iface_type].append(port['name'])
        
        for ptype, ports in sorted(port_types.items()):
            if len(ports) <= 5:
                print(f"      {ptype}: {', '.join(ports)}")
            else:
                print(f"      {ptype}: {len(ports)} ports")


def analyze_bridges_from_text(ovs_path: Path):
    """Analyze bridges from text files"""
    print("\n" + "="*80)
    print("BRIDGE DETAILS")
    print("="*80)
    
    bridge_file = ovs_path / "ovs-vsctl_-t_5_list_bridge"
    bridges = parse_ovs_vsctl_list_output(bridge_file)
    
    if not bridges:
        print("  No bridge data found")
        return
    
    for bridge in bridges:
        name = bridge.get('name', 'unknown')
        print(f"\n  Bridge: {name}")
        print(f"  {'-'*60}")
        
        # Key fields
        if 'datapath_type' in bridge:
            dp_type = bridge['datapath_type']
            # Empty string or 'system' means kernelspace, 'netdev' means userspace (DPDK)
            if dp_type in ['', '""', 'system', None]:
                dp_label = "kernelspace"
                dp_display = "system"
            else:
                dp_label = "userspace (DPDK)"
                dp_display = dp_type
            print(f"    Datapath: {dp_display} ({dp_label})")
        
        if 'fail_mode' in bridge:
            print(f"    Fail Mode: {bridge['fail_mode'] or 'standalone'}")
        
        if 'datapath_id' in bridge:
            print(f"    Datapath ID: {bridge['datapath_id']}")
        
        # Count ports from the ports field
        if 'ports' in bridge and bridge['ports'] not in ['[]', '']:
            # ports field looks like [uuid1, uuid2, ...]
            port_str = bridge['ports']
            if port_str.startswith('[') and port_str.endswith(']'):
                port_count = len([p for p in port_str[1:-1].split(',') if p.strip()])
                print(f"    Port Count: {port_count}")
        
        # External IDs
        if 'external_ids' in bridge:
            ext_ids = parse_external_ids(bridge['external_ids'])
            # Show CT zone info count
            ct_zones = [k for k in ext_ids.keys() if k.startswith('ct-zone-')]
            if ct_zones:
                print(f"    CT Zones: {len(ct_zones)}")


def analyze_interfaces_from_text(ovs_path: Path):
    """Analyze interfaces from text files"""
    print("\n" + "="*80)
    print("INTERFACE ANALYSIS")
    print("="*80)
    
    iface_file = ovs_path / "ovs-vsctl_-t_5_list_interface"
    interfaces = parse_ovs_vsctl_list_output(iface_file)
    
    if not interfaces:
        print("  No interface data found")
        return
    
    # Categorize interfaces
    by_type = defaultdict(list)
    pod_interfaces = []
    
    for iface in interfaces:
        name = iface.get('name', 'unknown')
        iface_type = iface.get('type', '') or 'system'
        by_type[iface_type].append(name)
        
        # Check for pod interfaces (exclude management port ovn-k8s-mp0)
        ext_ids = parse_external_ids(iface.get('external_ids', '{}'))
        iface_id = ext_ids.get('iface-id', '')
        
        # Skip management port (ovn-k8s-mp0 has iface-id starting with "k8s-")
        is_mgmt_port = name == 'ovn-k8s-mp0' or iface_id.startswith('k8s-')
        
        if not is_mgmt_port and ('iface-id' in ext_ids or name.endswith('_h')):
            pod_interfaces.append({
                'name': name,
                'external_ids': ext_ids,
                'ofport': iface.get('ofport', 'N/A'),
                'admin_state': iface.get('admin_state', 'unknown'),
                'link_state': iface.get('link_state', 'unknown'),
            })
    
    # Summary
    print(f"\n  Total Interfaces: {len(interfaces)}")
    print(f"\n  By Type:")
    for iface_type, names in sorted(by_type.items()):
        if len(names) <= 5:
            print(f"    {iface_type}: {', '.join(names)}")
        else:
            print(f"    {iface_type}: {len(names)} interfaces")
    
    # Pod interfaces
    if pod_interfaces:
        print(f"\n  Pod Interfaces: {len(pod_interfaces)}")
        print(f"  {'-'*70}")
        
        for pod_iface in pod_interfaces[:20]:  # Show first 20
            ext_ids = pod_iface['external_ids']
            iface_id = ext_ids.get('iface-id', 'N/A')
            
            # Try to extract pod info from iface-id (format: namespace_podname)
            pod_info = ""
            if '_' in iface_id:
                parts = iface_id.rsplit('_', 1)
                if len(parts) == 2:
                    pod_info = f" (ns: {parts[0].split('_')[0] if '_' in parts[0] else parts[0]})"
            
            print(f"    {pod_iface['name']:<30} ofport={pod_iface['ofport']:<5} "
                  f"state={pod_iface['admin_state']}/{pod_iface['link_state']}{pod_info}")
        
        if len(pod_interfaces) > 20:
            print(f"    ... and {len(pod_interfaces) - 20} more")


def analyze_openflow_data(sosreport_path: Path):
    """Analyze OpenFlow dumps from sosreport"""
    ovs_path = sosreport_path / "sos_commands" / "openvswitch"
    
    if not ovs_path.exists():
        print("\n  Warning: sos_commands/openvswitch not found")
        return
    
    # Find all dump-flows files
    flow_files = list(ovs_path.glob("ovs-ofctl_dump-flows_*"))
    port_files = list(ovs_path.glob("ovs-ofctl_dump-ports_*"))
    
    if not flow_files:
        print("\n  No OpenFlow dump files found")
        return
    
    print("\n" + "="*80)
    print("OPENFLOW ANALYSIS")
    print("="*80)
    
    # Parse all flows
    flows_by_bridge: Dict[str, List[OFFlow]] = {}
    for flow_file in flow_files:
        bridge_name = flow_file.name.replace("ovs-ofctl_dump-flows_", "")
        flows = parse_flow_file(flow_file)
        if flows:
            flows_by_bridge[bridge_name] = flows
    
    # Analyze each bridge
    for bridge_name, flows in sorted(flows_by_bridge.items()):
        print(f"\n  Bridge: {bridge_name}")
        print(f"  {'-'*70}")
        
        # Flow statistics
        total_flows = len(flows)
        drop_flows = [f for f in flows if f.is_drop]
        # Filter out OVN internal tables (64-87) - drops there are normal mechanics
        active_drops = [f for f in drop_flows if f.has_hits and not f.is_ovn_internal_table]
        ovn_internal_drops = [f for f in drop_flows if f.has_hits and f.is_ovn_internal_table]
        flows_with_hits = [f for f in flows if f.has_hits]
        
        print(f"  Total flows: {total_flows:,}")
        print(f"  Flows with hits: {len(flows_with_hits):,}")
        active_drop_info = f"{len(active_drops)} actively dropping"
        if ovn_internal_drops:
            active_drop_info += f", {len(ovn_internal_drops)} in OVN internal tables (ignored)"
        print(f"  Drop flows: {len(drop_flows)} ({active_drop_info})")
        
        # Flow table distribution
        tables = defaultdict(int)
        for flow in flows:
            tables[flow.table] += 1
        
        print(f"  Tables used: {len(tables)} ({min(tables.keys())}-{max(tables.keys())})")
        
        # Show tables with most flows
        top_tables = sorted(tables.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"  Top tables by flow count:")
        for table_id, count in top_tables:
            print(f"    Table {table_id}: {count:,} flows")
        
        # Active drop flows (important for troubleshooting)
        if active_drops:
            print(f"\n  ⚠️  ACTIVE DROP FLOWS ({len(active_drops)}):")
            for drop in sorted(active_drops, key=lambda x: x.n_packets, reverse=True)[:10]:
                print(f"    table={drop.table}, priority={drop.priority}, "
                      f"packets={drop.n_packets:,}")
                if drop.match:
                    # Truncate long matches
                    match_display = drop.match[:70] + "..." if len(drop.match) > 70 else drop.match
                    print(f"      match: {match_display}")
                # Always show actions for drop flows
                actions_display = drop.actions if drop.actions else "(empty - implicit drop)"
                print(f"      actions: {actions_display}")
        
        # Top flows by traffic
        top_flows = sorted(flows, key=lambda x: x.n_packets, reverse=True)[:5]
        print(f"\n  Top 5 flows by packet count:")
        for i, flow in enumerate(top_flows, 1):
            print(f"    {i}. table={flow.table}, priority={flow.priority}, "
                  f"packets={flow.n_packets:,}, bytes={flow.n_bytes:,}")
            # Show match (truncated if too long)
            if flow.match:
                match_display = flow.match[:80] + "..." if len(flow.match) > 80 else flow.match
                print(f"       match: {match_display}")
            # Show actions (truncated if too long)
            if flow.actions:
                actions_display = flow.actions[:80] + "..." if len(flow.actions) > 80 else flow.actions
                print(f"       actions: {actions_display}")
    
    # Port statistics
    if port_files:
        print("\n" + "-"*80)
        print("PORT STATISTICS")
        print("-"*80)
        
        # Build ofport -> name mapping from interface file
        ofport_map = {}
        iface_file = ovs_path / "ovs-vsctl_-t_5_list_interface"
        if iface_file.exists():
            interfaces = parse_ovs_vsctl_list_output(iface_file)
            for iface in interfaces:
                name = iface.get('name', '')
                ofport = iface.get('ofport', '')
                if name and ofport and ofport not in ['[]', '-1']:
                    ofport_map[ofport] = name
        
        for port_file in sorted(port_files):
            bridge_name = port_file.name.replace("ovs-ofctl_dump-ports_", "")
            stats = parse_port_stats_file(port_file)
            
            if not stats:
                continue
            
            # Find ports with drops or errors
            problem_ports = []
            for port_num, port_stats in stats.items():
                total_drops = port_stats.get('rx_drop', 0) + port_stats.get('tx_drop', 0)
                total_errors = port_stats.get('rx_errors', 0) + port_stats.get('tx_errors', 0)
                if total_drops > 0 or total_errors > 0:
                    # Get interface name from ofport mapping
                    iface_name = ofport_map.get(port_num, '')
                    problem_ports.append((port_num, iface_name, port_stats, total_drops, total_errors))
            
            print(f"\n  Bridge: {bridge_name}")
            print(f"  Total ports: {len(stats)}")
            
            if problem_ports:
                print(f"\n  ⚠️  Ports with drops/errors:")
                for port_num, iface_name, port_stats, drops, errors in sorted(problem_ports, 
                        key=lambda x: x[3] + x[4], reverse=True)[:10]:
                    # Show port number and name if available
                    port_display = f"{iface_name} (ofport={port_num})" if iface_name else f"ofport={port_num}"
                    print(f"    {port_display}: drops={drops:,}, errors={errors:,}")
                    print(f"      RX: {port_stats.get('rx_packets', 0):,} pkts, "
                          f"{port_stats.get('rx_bytes', 0):,} bytes")
                    print(f"      TX: {port_stats.get('tx_packets', 0):,} pkts, "
                          f"{port_stats.get('tx_bytes', 0):,} bytes")


def analyze_upcall_stats(sosreport_path: Path):
    """Analyze OVS upcall statistics (datapath flow table health)"""
    ovs_path = sosreport_path / "sos_commands" / "openvswitch"
    upcall_file = ovs_path / "ovs-appctl_upcall.show"
    
    if not upcall_file.exists():
        return
    
    print("\n" + "-"*80)
    print("DATAPATH FLOW TABLE HEALTH")
    print("-"*80)
    
    content = upcall_file.read_text()
    
    # Parse flow stats
    # Format: "flows         : (current 1234) (avg 1000) (max 5000) (limit 200000)"
    flow_match = re.search(
        r'flows\s*:\s*\(current\s+(\d+)\)\s*\(avg\s+(\d+)\)\s*\(max\s+(\d+)\)\s*\(limit\s+(\d+)\)',
        content
    )
    
    if flow_match:
        current = int(flow_match.group(1))
        avg = int(flow_match.group(2))
        max_flows = int(flow_match.group(3))
        limit = int(flow_match.group(4))
        
        usage_pct = (current / limit * 100) if limit > 0 else 0
        
        print(f"\n  Current flows: {current:,} / {limit:,} ({usage_pct:.1f}% used)")
        print(f"  Average: {avg:,}, Max seen: {max_flows:,}")
        
        # Health indicator
        if usage_pct > 90:
            print(f"  ⚠️  WARNING: Flow table near capacity!")
        elif usage_pct > 70:
            print(f"  ⚠️  NOTICE: Flow table usage elevated")
        else:
            print(f"  ✓ Flow table healthy")


def analyze_coverage_stats(sosreport_path: Path):
    """Analyze OVS coverage statistics for key metrics"""
    ovs_path = sosreport_path / "sos_commands" / "openvswitch"
    coverage_file = ovs_path / "ovs-appctl_coverage.show"
    
    if not coverage_file.exists():
        return
    
    print("\n" + "-"*80)
    print("OVS INTERNAL STATISTICS")
    print("-"*80)
    
    content = coverage_file.read_text()
    
    # Key metrics to look for
    key_metrics = {
        'netlink_sent': 'Netlink messages sent',
        'netlink_received': 'Netlink messages received',
        'netlink_recv_jumbo': 'Jumbo netlink receives',
        'ofproto_update_port': 'Port updates',
        'ofproto_packet_out': 'Packet-out messages',
        'ofproto_dpif_expired': 'Expired datapath flows',
        'rev_reconfigure': 'Reconfigurations',
        'rev_flow_table': 'Flow table revisions',
        'bridge_reconfigure': 'Bridge reconfigurations',
        'txn_success': 'OVSDB transactions (success)',
        'txn_incomplete': 'OVSDB transactions (incomplete)',
        'txn_try_again': 'OVSDB transactions (retry)',
        'dpif_flow_put_error': 'Datapath flow put errors',
        'dpif_execute_error': 'Datapath execute errors',
        'unixctl_received': 'Unix control messages',
    }
    
    print(f"\n  {'METRIC':<25} {'DESCRIPTION':<35} {'TOTAL':<15} RATE/s")
    print(f"  {'-'*25} {'-'*35} {'-'*15} {'-'*10}")
    
    for metric_name, description in key_metrics.items():
        # Format in coverage.show:
        # metric_name              123.4/sec     12.3/sec      1.2/sec   total: 12345
        pattern = rf'{metric_name}\s+[\d.]+/sec\s+[\d.]+/sec\s+([\d.]+)/sec\s+total:\s+(\d+)'
        match = re.search(pattern, content)
        
        if match:
            rate = match.group(1)
            total = int(match.group(2))
            print(f"  {metric_name:<25} {description:<35} {total:<15,} {rate}")


def analyze_tunnels(sosreport_path: Path):
    """Analyze OVS tunnels from interface list and tnl.ports.show"""
    ovs_path = sosreport_path / "sos_commands" / "openvswitch"
    
    print("\n" + "-"*80)
    print("TUNNEL INTERFACES")
    print("-"*80)
    
    # First, check interface list for tunnel types
    tunnel_types = ['geneve', 'vxlan', 'gre', 'stt', 'lisp', 'erspan', 'ip6erspan', 'ip6gre', 'gtpu', 'bareudp', 'srv6']
    iface_file = ovs_path / "ovs-vsctl_-t_5_list_interface"
    tunnel_interfaces = []
    
    if iface_file.exists():
        interfaces = parse_ovs_vsctl_list_output(iface_file)
        for iface in interfaces:
            iface_type = iface.get('type', '')
            if iface_type in tunnel_types:
                name = iface.get('name', 'unknown')
                options = iface.get('options', '{}')
                tunnel_interfaces.append({
                    'name': name,
                    'type': iface_type,
                    'options': options
                })
    
    if tunnel_interfaces:
        # Group by type
        by_type = defaultdict(list)
        for tun in tunnel_interfaces:
            by_type[tun['type']].append(tun)
        
        for tun_type, tunnels in sorted(by_type.items()):
            print(f"\n  {tun_type.upper()} tunnels ({len(tunnels)}):")
            for tun in tunnels[:5]:  # Show first 5
                # Parse options to get remote_ip
                opts = parse_external_ids(tun['options'])
                remote = opts.get('remote_ip', 'N/A')
                local = opts.get('local_ip', 'N/A')
                print(f"    {tun['name']}: local={local} -> remote={remote}")
            if len(tunnels) > 5:
                print(f"    ... and {len(tunnels) - 5} more")
    else:
        print("  No tunnel interfaces found")
    
    # Also check tnl.ports.show for listening ports
    tunnel_file = ovs_path / "ovs-appctl_tnl.ports.show_-v"
    if tunnel_file.exists():
        content = tunnel_file.read_text().strip()
        lines = content.split('\n')
        listening_count = 0
        for line in lines:
            if line.strip() and not line.startswith('Listening') and '(' in line:
                listening_count += 1
        if listening_count > 0:
            print(f"\n  Listening tunnel ports: {listening_count}")


# =============================================================================
# Database Mode Analysis Functions
# =============================================================================

def analyze_db_summary(db: OVSDatabase, db_path: Path):
    """Print summary when using database mode"""
    print("\n" + "="*80)
    print("OVS DATABASE ANALYSIS (conf.db mode)")
    print("="*80)
    print(f"\n  Database: {db_path}")
    
    # Get counts for each table
    tables = ["Bridge", "Port", "Interface", "Controller", "Manager"]
    for table in tables:
        rows = db.query(table)
        print(f"  {table}: {len(rows)} entries")


def analyze_db_system_info(db: OVSDatabase):
    """Analyze Open_vSwitch table from database"""
    print("\n" + "="*80)
    print("SYSTEM INFORMATION (from conf.db)")
    print("="*80)
    
    rows = db.query("Open_vSwitch")
    if not rows:
        print("  No Open_vSwitch data")
        return
    
    ovs = rows[0]
    
    print(f"\n  OVS Version: {ovs.get('ovs_version', 'N/A')}")
    print(f"  DB Version: {ovs.get('db_version', 'N/A')}")
    print(f"  System Type: {ovs.get('system_type', 'N/A')}")
    print(f"  System Version: {ovs.get('system_version', 'N/A')}")
    
    # External IDs
    ext_ids = ovs.get('external_ids', [])
    if ext_ids and isinstance(ext_ids, list) and len(ext_ids) > 1:
        ext_map = dict(ext_ids[1]) if ext_ids[0] == 'map' else {}
        if ext_map:
            print(f"\n  External IDs:")
            for key in ['hostname', 'ovn-encap-ip', 'ovn-encap-type', 'system-id']:
                if key in ext_map:
                    print(f"    {key}: {ext_map[key]}")


def analyze_db_bridges(db: OVSDatabase):
    """Analyze bridges from database"""
    print("\n" + "="*80)
    print("BRIDGES (from conf.db)")
    print("="*80)
    
    bridges = db.query("Bridge")
    
    for bridge in bridges:
        name = bridge.get('name', 'unknown')
        print(f"\n  Bridge: {name}")
        print(f"  {'-'*60}")
        
        dp_type = bridge.get('datapath_type', '') or 'system'
        print(f"    Datapath: {dp_type}")
        print(f"    Fail Mode: {bridge.get('fail_mode', 'standalone')}")
        
        ports = bridge.get('ports', [])
        if ports and isinstance(ports, list):
            port_count = len(ports[1]) if ports[0] == 'set' else 1
            print(f"    Ports: {port_count}")


def analyze_db_interfaces(db: OVSDatabase):
    """Analyze interfaces from database"""
    print("\n" + "="*80)
    print("INTERFACES (from conf.db)")
    print("="*80)
    
    interfaces = db.query("Interface")
    
    by_type = defaultdict(list)
    pod_interfaces = []
    
    for iface in interfaces:
        name = iface.get('name', 'unknown')
        iface_type = iface.get('type', '') or 'system'
        by_type[iface_type].append(name)
        
        # Check for pod interfaces (exclude management port)
        ext_ids = iface.get('external_ids', [])
        if ext_ids and isinstance(ext_ids, list) and ext_ids[0] == 'map':
            ext_map = dict(ext_ids[1])
            iface_id = ext_map.get('iface-id', '')
            # Skip management port (ovn-k8s-mp0 has iface-id starting with "k8s-")
            is_mgmt_port = name == 'ovn-k8s-mp0' or iface_id.startswith('k8s-')
            if 'iface-id' in ext_map and not is_mgmt_port:
                pod_interfaces.append({
                    'name': name,
                    'iface_id': iface_id,
                    'ofport': iface.get('ofport', 'N/A'),
                })
    
    print(f"\n  Total Interfaces: {len(interfaces)}")
    print(f"\n  By Type:")
    for iface_type, names in sorted(by_type.items()):
        print(f"    {iface_type}: {len(names)}")
    
    if pod_interfaces:
        print(f"\n  Pod Interfaces: {len(pod_interfaces)}")
        for pi in pod_interfaces[:10]:
            print(f"    {pi['name']}: {pi['iface_id']}")
        if len(pod_interfaces) > 10:
            print(f"    ... and {len(pod_interfaces) - 10} more")


# =============================================================================
# Sosreport Handling
# =============================================================================

def safe_tar_extract(tar: tarfile.TarFile, extract_dir: Path) -> None:
    """Safely extract tar archive, preventing path traversal attacks (CVE-2007-4559).
    
    For Python 3.12+, uses the built-in 'data' filter.
    For older versions, manually validates each member path.
    """
    # Python 3.12+ has built-in filter support
    if hasattr(tarfile, 'data_filter'):
        tar.extractall(extract_dir, filter='data')
    else:
        # Manual validation for older Python versions
        extract_dir_resolved = extract_dir.resolve()
        
        for member in tar.getmembers():
            # Get the target path for this member
            member_path = extract_dir / member.name
            
            # Resolve to absolute path (handles .. and symlinks)
            try:
                # For non-existent paths, resolve the parent
                resolved = member_path.resolve()
            except (OSError, ValueError):
                raise ValueError(f"Invalid path in archive: {member.name}")
            
            # Ensure the resolved path is within the extraction directory
            try:
                resolved.relative_to(extract_dir_resolved)
            except ValueError:
                raise ValueError(
                    f"Path traversal detected in archive member: {member.name}"
                )
            
            # Also reject absolute paths in the archive
            if member.name.startswith('/') or member.name.startswith('\\'):
                raise ValueError(f"Absolute path in archive: {member.name}")
        
        # All members validated, safe to extract
        tar.extractall(extract_dir)


def extract_sosreport(path: Path) -> Path:
    """Extract sosreport if needed, return path to sosreport directory"""
    if path.is_dir():
        # Check if this is the sosreport directory or contains one
        if (path / "sos_commands").exists():
            return path
        # Look for sosreport subdirectory
        for subdir in path.iterdir():
            if subdir.is_dir() and (subdir / "sos_commands").exists():
                return subdir
        return path
    
    # Handle archive
    if path.suffix in ['.xz', '.gz'] or '.tar' in path.name:
        extract_dir = path.parent / f"{path.stem}_extracted"
        
        if not extract_dir.exists():
            print(f"Extracting {path}...")
            extract_dir.mkdir(parents=True)
            
            if path.suffix == '.xz':
                import lzma
                with lzma.open(path, 'rb') as xz:
                    with tarfile.open(fileobj=xz) as tar:
                        safe_tar_extract(tar, extract_dir)
            elif path.suffix == '.gz':
                import gzip
                with gzip.open(path, 'rb') as gz:
                    with tarfile.open(fileobj=gz) as tar:
                        safe_tar_extract(tar, extract_dir)
            else:
                with tarfile.open(path) as tar:
                    safe_tar_extract(tar, extract_dir)
        
        # Find the actual sosreport directory inside
        for item in extract_dir.iterdir():
            if item.is_dir() and (item / "sos_commands").exists():
                return item
        return extract_dir
    
    return path


def find_ovs_db(sosreport_dir: Path) -> Optional[Path]:
    """Find conf.db in sosreport directory"""
    possible_paths = [
        sosreport_dir / "etc" / "openvswitch" / "conf.db",
        sosreport_dir / "var" / "lib" / "openvswitch" / "conf.db",
        sosreport_dir / "usr" / "local" / "etc" / "openvswitch" / "conf.db",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


def run_raw_query(db_path: Path, query: str) -> int:
    """Run a raw OVSDB query and print results"""
    try:
        result = subprocess.run(
            ["ovsdb-tool", "query", str(db_path), query],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr}", file=sys.stderr)
        return 1
    return 0


# =============================================================================
# Main Entry Points
# =============================================================================

def analyze_from_textfiles(sosreport_path: Path):
    """Analyze OVS from text files in sos_commands/openvswitch/ (--flows-only mode)"""
    ovs_path = sosreport_path / "sos_commands" / "openvswitch"
    
    if not ovs_path.exists():
        print(f"Error: sos_commands/openvswitch not found in {sosreport_path}", 
              file=sys.stderr)
        return 1
    
    print(f"\n{'='*80}")
    print(f"OVS ANALYSIS - {sosreport_path.name}")
    print(f"{'='*80}")
    print(f"Mode: Text file analysis (no ovsdb-tool required)")
    
    # Run analysis
    analyze_system_from_text(ovs_path)
    analyze_topology_from_text(ovs_path)
    analyze_bridges_from_text(ovs_path)
    analyze_interfaces_from_text(ovs_path)
    analyze_openflow_data(sosreport_path)
    analyze_tunnels(sosreport_path)
    analyze_upcall_stats(sosreport_path)
    analyze_coverage_stats(sosreport_path)
    
    print()
    return 0


def analyze_from_database(db_path: Path, sosreport_path: Path = None, 
                          include_flows: bool = True):
    """Analyze OVS from conf.db using ovsdb-tool (--db mode or default with include_flows)"""
    # Check if ovsdb-tool is available
    try:
        subprocess.run(['ovsdb-tool', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: ovsdb-tool not found. Please install openvswitch package.", 
              file=sys.stderr)
        print("  Fedora/RHEL: sudo dnf install openvswitch", file=sys.stderr)
        print("  Ubuntu/Debian: sudo apt install openvswitch-common", file=sys.stderr)
        return 1
    
    db = OVSDatabase(db_path)
    
    print(f"\n{'='*80}")
    print(f"OVS ANALYSIS - Database Mode")
    print(f"{'='*80}")
    print(f"Database: {db_path}")
    
    analyze_db_summary(db, db_path)
    analyze_db_system_info(db)
    analyze_db_bridges(db)
    analyze_db_interfaces(db)
    
    # Also run flow analysis if sosreport path available
    if include_flows and sosreport_path:
        analyze_openflow_data(sosreport_path)
        analyze_tunnels(sosreport_path)
        analyze_upcall_stats(sosreport_path)
        analyze_coverage_stats(sosreport_path)
    
    print()
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Analyze OVS data from sosreport",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  Default:      Full analysis - conf.db + all text files (requires ovsdb-tool)
  --db:         Database only - analyze conf.db (requires ovsdb-tool)
  --flows-only: Text files only - no ovsdb-tool needed
  --query:      Run custom OVSDB query (requires ovsdb-tool)

Examples:
  # Full analysis (default, requires ovsdb-tool)
  analyze_ovs_db.py ./sosreport-hostname-2024-01-15/

  # Analyze from archive
  analyze_ovs_db.py ./sosreport-hostname-2024-01-15.tar.xz

  # Database only (conf.db)
  analyze_ovs_db.py ./sosreport/ --db

  # Text files only (no ovsdb-tool needed)
  analyze_ovs_db.py ./sosreport/ --flows-only

  # Run raw OVSDB query
  analyze_ovs_db.py ./sosreport/ --query '["Open_vSwitch", {"op":"select", "table":"Bridge", "where":[]}]'

Analysis Features:
  Database analysis (--db or default):
    - System configuration and version info (from conf.db)
    - Bridge topology and datapath types (from conf.db)
    - Interface inventory with pod mapping (from conf.db)
  
  Text file analysis (--flows-only or default):
    - System info (from ovs-vsctl list_* files)
    - OpenFlow flow analysis (counts, drops, top flows)
    - Port statistics (drops, errors, traffic)
    - Tunnel ports overview
    - Datapath flow table health (upcall stats)
    - OVS internal statistics (coverage counters)
        """
    )
    parser.add_argument('path', help='Path to sosreport archive, directory, or conf.db file')
    parser.add_argument('--db', action='store_true',
                        help='Database only - analyze conf.db (requires ovsdb-tool)')
    parser.add_argument('--flows-only', action='store_true',
                        help='Text files only - no ovsdb-tool needed')
    parser.add_argument('--query', '-q', 
                        help='Run raw OVSDB JSON query (requires ovsdb-tool, incompatible with --flows-only)')

    args = parser.parse_args()

    input_path = Path(args.path)
    
    # Handle different input types
    if not input_path.exists():
        print(f"Error: Path not found: {input_path}", file=sys.stderr)
        return 1
    
    # Validate incompatible options
    if args.flows_only and args.query:
        print("Error: --flows-only and --query are incompatible", file=sys.stderr)
        return 1
    
    if args.flows_only and args.db:
        print("Error: --flows-only and --db are incompatible", file=sys.stderr)
        return 1
    
    # Direct conf.db file always uses database mode
    if input_path.is_file() and input_path.name == "conf.db":
        if args.flows_only:
            print("Error: --flows-only cannot be used with conf.db file", file=sys.stderr)
            return 1
        args.db = True
        db_path = input_path
        sosreport_dir = None
        
        # Try to find sosreport context
        for parent in input_path.parents:
            if (parent / "sos_commands").exists():
                sosreport_dir = parent
                break
    else:
        # Extract/find sosreport directory
        sosreport_dir = extract_sosreport(input_path)
        db_path = find_ovs_db(sosreport_dir) if sosreport_dir else None
    
    # Query mode (requires ovsdb-tool)
    if args.query:
        if not db_path:
            print("Error: conf.db not found for query mode", file=sys.stderr)
            return 1
        # Check ovsdb-tool
        try:
            subprocess.run(['ovsdb-tool', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Error: ovsdb-tool not found. Please install openvswitch package.", 
                  file=sys.stderr)
            return 1
        return run_raw_query(db_path, args.query)
    
    # Flows-only mode: text files only, no ovsdb-tool needed
    if args.flows_only:
        if not sosreport_dir:
            print(f"Error: Not a valid sosreport: {input_path}", file=sys.stderr)
            return 1
        return analyze_from_textfiles(sosreport_dir)
    
    # Database-only mode
    if args.db:
        if not db_path:
            print(f"Error: conf.db not found in {input_path}", file=sys.stderr)
            print("\nLooked for conf.db in:", file=sys.stderr)
            print("  - etc/openvswitch/conf.db", file=sys.stderr)
            print("  - var/lib/openvswitch/conf.db", file=sys.stderr)
            print("  - usr/local/etc/openvswitch/conf.db", file=sys.stderr)
            print("\nTip: Use --flows-only to analyze text files without ovsdb-tool", file=sys.stderr)
            return 1
        return analyze_from_database(db_path, sosreport_path=None, include_flows=False)
    
    # Default mode: full analysis (db + text files)
    if not sosreport_dir:
        print(f"Error: Not a valid sosreport: {input_path}", file=sys.stderr)
        return 1
    
    # Check ovsdb-tool for default mode
    if db_path:
        try:
            subprocess.run(['ovsdb-tool', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Warning: ovsdb-tool not found, falling back to --flows-only mode", 
                  file=sys.stderr)
            print("  Install openvswitch package for full analysis", file=sys.stderr)
            print()
            return analyze_from_textfiles(sosreport_dir)
        
        return analyze_from_database(db_path, sosreport_dir, include_flows=True)
    else:
        # No conf.db found, fall back to text files
        print("Note: conf.db not found, using text files only", file=sys.stderr)
        return analyze_from_textfiles(sosreport_dir)


if __name__ == '__main__':
    sys.exit(main())
