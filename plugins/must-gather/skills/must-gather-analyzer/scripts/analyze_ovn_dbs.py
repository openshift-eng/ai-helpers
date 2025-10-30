#!/usr/bin/env python3
"""
Analyze OVN Northbound and Southbound databases from must-gather.
Uses ovsdb-tool to read binary .db files collected per-node.

Must-gather structure:
  network_logs/
  └── ovnk_database_store.tar.gz
      └── ovnk_database_store/
          ├── ovnkube-node-{pod}_nbdb  (per-zone NBDB)
          ├── ovnkube-node-{pod}_sbdb  (per-zone SBDB)
          └── ...
"""

import subprocess
import json
import sys
import os
import tarfile
import yaml
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional


class OVNDatabase:
    """Wrapper for querying OVSDB files using ovsdb-tool"""

    def __init__(self, db_path: Path, db_type: str, node_name: str = None):
        self.db_path = db_path
        self.db_type = db_type  # 'nbdb' or 'sbdb'
        self.pod_name = db_path.stem.replace('_nbdb', '').replace('_sbdb', '')
        self.node_name = node_name or self.pod_name  # Use node name if available

    def query(self, table: str, columns: List[str] = None, where: List = None) -> List[Dict]:
        """Query OVSDB table using ovsdb-tool query command"""
        schema = "OVN_Northbound" if self.db_type == "nbdb" else "OVN_Southbound"

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
                ['ovsdb-tool', 'query', str(self.db_path), query_json],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                print(f"Warning: Query failed for {self.db_path}: {result.stderr}", file=sys.stderr)
                return []

            data = json.loads(result.stdout)
            return data[0].get('rows', [])

        except Exception as e:
            print(f"Warning: Failed to query {table} from {self.db_path}: {e}", file=sys.stderr)
            return []


def build_pod_to_node_mapping(mg_path: Path) -> Dict[str, str]:
    """Build mapping of ovnkube pod names to node names"""
    pod_to_node = {}

    # Look for ovnkube-node pods in openshift-ovn-kubernetes namespace
    ovn_ns_path = mg_path / "namespaces" / "openshift-ovn-kubernetes" / "pods"

    if not ovn_ns_path.exists():
        print(f"Warning: OVN namespace pods not found at {ovn_ns_path}", file=sys.stderr)
        return pod_to_node

    # Find all ovnkube-node pod directories
    for pod_dir in ovn_ns_path.glob("ovnkube-node-*"):
        if not pod_dir.is_dir():
            continue

        pod_name = pod_dir.name
        pod_yaml = pod_dir / f"{pod_name}.yaml"

        if not pod_yaml.exists():
            continue

        try:
            with open(pod_yaml, 'r') as f:
                pod = yaml.safe_load(f)
                node_name = pod.get('spec', {}).get('nodeName')
                if node_name:
                    pod_to_node[pod_name] = node_name
        except Exception as e:
            print(f"Warning: Failed to parse {pod_yaml}: {e}", file=sys.stderr)

    return pod_to_node


def extract_db_tarball(mg_path: Path) -> Path:
    """Extract ovnk_database_store.tar.gz if not already extracted"""
    network_logs = mg_path / "network_logs"
    tarball = network_logs / "ovnk_database_store.tar.gz"
    extract_dir = network_logs / "ovnk_database_store"

    if not tarball.exists():
        print(f"Error: Database tarball not found: {tarball}", file=sys.stderr)
        return None

    # Extract if directory doesn't exist
    if not extract_dir.exists():
        print(f"Extracting {tarball}...")
        with tarfile.open(tarball, 'r:gz') as tar:
            tar.extractall(path=network_logs)

    return extract_dir


def get_nb_databases(db_dir: Path, pod_to_node: Dict[str, str]) -> List[OVNDatabase]:
    """Find all NB database files and map them to nodes"""
    databases = []
    for db in sorted(db_dir.glob("*_nbdb")):
        pod_name = db.stem.replace('_nbdb', '')
        node_name = pod_to_node.get(pod_name)
        databases.append(OVNDatabase(db, 'nbdb', node_name))
    return databases


def get_sb_databases(db_dir: Path, pod_to_node: Dict[str, str]) -> List[OVNDatabase]:
    """Find all SB database files and map them to nodes"""
    databases = []
    for db in sorted(db_dir.glob("*_sbdb")):
        pod_name = db.stem.replace('_sbdb', '')
        node_name = pod_to_node.get(pod_name)
        databases.append(OVNDatabase(db, 'sbdb', node_name))
    return databases


def analyze_logical_switches(db: OVNDatabase):
    """Analyze logical switches in the zone"""
    switches = db.query("Logical_Switch", columns=["name", "ports", "other_config"])

    if not switches:
        print("  No logical switches found.")
        return

    print(f"\n  LOGICAL SWITCHES ({len(switches)}):")
    print(f"  {'NAME':<60} PORTS")
    print(f"  {'-'*80}")

    for sw in switches:
        name = sw.get('name', 'unknown')
        # ports is a UUID set, just count them
        port_count = 0
        ports = sw.get('ports', [])
        if isinstance(ports, list) and len(ports) == 2 and ports[0] == "set":
            port_count = len(ports[1])

        print(f"  {name:<60} {port_count}")


def analyze_logical_switch_ports(db: OVNDatabase):
    """Analyze logical switch ports, focusing on pods"""
    lsps = db.query("Logical_Switch_Port", columns=["name", "external_ids", "addresses"])

    # Filter for pod ports (have pod=true in external_ids)
    pod_ports = []
    for lsp in lsps:
        ext_ids = lsp.get('external_ids', [])
        if isinstance(ext_ids, list) and len(ext_ids) == 2 and ext_ids[0] == "map":
            ext_map = dict(ext_ids[1])
            if ext_map.get('pod') == 'true':
                # Pod name is in the LSP name (format: namespace_podname)
                lsp_name = lsp.get('name', '')
                namespace = ext_map.get('namespace', '')

                # Extract pod name from LSP name
                pod_name = lsp_name
                if lsp_name.startswith(namespace + '_'):
                    pod_name = lsp_name[len(namespace) + 1:]

                # Extract IP from addresses (format can be string "MAC IP" or empty)
                ip = ""
                addrs = lsp.get('addresses', '')
                if isinstance(addrs, str) and addrs:
                    parts = addrs.split()
                    if len(parts) > 1:
                        ip = parts[1]

                pod_ports.append({
                    'name': lsp_name,
                    'namespace': namespace,
                    'pod_name': pod_name,
                    'ip': ip
                })

    if not pod_ports:
        print("  No pod logical switch ports found.")
        return

    print(f"\n  POD LOGICAL SWITCH PORTS ({len(pod_ports)}):")
    print(f"  {'NAMESPACE':<40} {'POD':<45} IP")
    print(f"  {'-'*120}")

    for port in sorted(pod_ports, key=lambda x: (x['namespace'], x['pod_name']))[:20]:  # Show first 20
        namespace = port['namespace'][:40]
        pod_name = port['pod_name'][:45]
        ip = port['ip']

        print(f"  {namespace:<40} {pod_name:<45} {ip}")

    if len(pod_ports) > 20:
        print(f"  ... and {len(pod_ports) - 20} more")


def analyze_acls(db: OVNDatabase):
    """Analyze ACLs in the zone"""
    acls = db.query("ACL", columns=["priority", "direction", "match", "action", "severity"])

    if not acls:
        print("  No ACLs found.")
        return

    print(f"\n  ACCESS CONTROL LISTS ({len(acls)}):")
    print(f"  {'PRIORITY':<10} {'DIRECTION':<15} {'ACTION':<15} MATCH")
    print(f"  {'-'*120}")

    # Show highest priority ACLs first
    sorted_acls = sorted(acls, key=lambda x: x.get('priority', 0), reverse=True)

    for acl in sorted_acls[:15]:  # Show top 15
        priority = acl.get('priority', 0)
        direction = acl.get('direction', '')
        action = acl.get('action', '')
        match = acl.get('match', '')[:70]  # Truncate long matches

        print(f"  {priority:<10} {direction:<15} {action:<15} {match}")

    if len(acls) > 15:
        print(f"  ... and {len(acls) - 15} more")


def analyze_logical_routers(db: OVNDatabase):
    """Analyze logical routers in the zone"""
    routers = db.query("Logical_Router", columns=["name", "ports", "static_routes"])

    if not routers:
        print("  No logical routers found.")
        return

    print(f"\n  LOGICAL ROUTERS ({len(routers)}):")
    print(f"  {'NAME':<60} PORTS")
    print(f"  {'-'*80}")

    for router in routers:
        name = router.get('name', 'unknown')

        # Count ports
        port_count = 0
        ports = router.get('ports', [])
        if isinstance(ports, list) and len(ports) == 2 and ports[0] == "set":
            port_count = len(ports[1])

        print(f"  {name:<60} {port_count}")


def analyze_zone_summary(db: OVNDatabase):
    """Print summary for a zone"""
    # Get counts - for ACLs we need multiple columns to get accurate count
    switches = db.query("Logical_Switch", columns=["name"])
    lsps = db.query("Logical_Switch_Port", columns=["name"])
    acls = db.query("ACL", columns=["priority", "direction", "match"])
    routers = db.query("Logical_Router", columns=["name"])

    print(f"\n{'='*80}")
    print(f"Node: {db.node_name}")
    if db.node_name != db.pod_name:
        print(f"Pod:  {db.pod_name}")
    print(f"{'='*80}")
    print(f"  Logical Switches:      {len(switches)}")
    print(f"  Logical Switch Ports:  {len(lsps)}")
    print(f"  ACLs:                  {len(acls)}")
    print(f"  Logical Routers:       {len(routers)}")


def run_raw_query(mg_path: str, node_filter: str, query_json: str):
    """Run a raw JSON query against OVN databases"""
    base_path = Path(mg_path)

    # Build pod-to-node mapping
    pod_to_node = build_pod_to_node_mapping(base_path)

    # Extract tarball
    db_dir = extract_db_tarball(base_path)
    if not db_dir:
        return 1

    # Get all NB databases
    nb_dbs = get_nb_databases(db_dir, pod_to_node)

    if not nb_dbs:
        print("No Northbound databases found in must-gather.", file=sys.stderr)
        return 1

    # Filter by node if specified
    if node_filter:
        filtered_dbs = [db for db in nb_dbs if node_filter in db.node_name]
        if not filtered_dbs:
            print(f"Error: No databases found for node matching '{node_filter}'", file=sys.stderr)
            print(f"\nAvailable nodes:", file=sys.stderr)
            for db in nb_dbs:
                print(f"  - {db.node_name}", file=sys.stderr)
            return 1
        nb_dbs = filtered_dbs

    # Run query on each database
    for db in nb_dbs:
        print(f"\n{'='*80}")
        print(f"Node: {db.node_name}")
        if db.node_name != db.pod_name:
            print(f"Pod:  {db.pod_name}")
        print(f"{'='*80}\n")

        try:
            # Run the raw query using ovsdb-tool
            result = subprocess.run(
                ['ovsdb-tool', 'query', str(db.db_path), query_json],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                print(f"Error: Query failed: {result.stderr}", file=sys.stderr)
                continue

            # Pretty print the JSON result
            try:
                data = json.loads(result.stdout)
                print(json.dumps(data, indent=2))
            except json.JSONDecodeError:
                # If not valid JSON, just print raw output
                print(result.stdout)

        except Exception as e:
            print(f"Error: Failed to execute query: {e}", file=sys.stderr)

    return 0


def analyze_northbound_databases(mg_path: str, node_filter: str = None):
    """Analyze all Northbound databases"""
    base_path = Path(mg_path)

    # Build pod-to-node mapping
    pod_to_node = build_pod_to_node_mapping(base_path)

    # Extract tarball
    db_dir = extract_db_tarball(base_path)
    if not db_dir:
        return 1

    # Get all NB databases
    nb_dbs = get_nb_databases(db_dir, pod_to_node)

    if not nb_dbs:
        print("No Northbound databases found in must-gather.", file=sys.stderr)
        return 1

    # Filter by node if specified
    if node_filter:
        filtered_dbs = [db for db in nb_dbs if node_filter in db.node_name]
        if not filtered_dbs:
            print(f"Error: No databases found for node matching '{node_filter}'", file=sys.stderr)
            print(f"\nAvailable nodes:", file=sys.stderr)
            for db in nb_dbs:
                print(f"  - {db.node_name}", file=sys.stderr)
            return 1
        nb_dbs = filtered_dbs

    print(f"\nFound {len(nb_dbs)} node(s)\n")

    # Analyze each zone
    for db in nb_dbs:
        analyze_zone_summary(db)
        analyze_logical_switches(db)
        analyze_logical_switch_ports(db)
        analyze_acls(db)
        analyze_logical_routers(db)
        print()

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Analyze OVN databases from must-gather",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze all nodes
  analyze_ovn_dbs.py ./must-gather.local.123456789

  # Analyze specific node
  analyze_ovn_dbs.py ./must-gather.local.123456789 --node ip-10-0-26-145

  # Run raw OVSDB query (Claude can construct the JSON)
  analyze_ovn_dbs.py ./must-gather/ --query '["OVN_Northbound", {"op":"select", "table":"ACL", "where":[["priority", ">", 1000]], "columns":["priority","match","action"]}]'

  # Query specific node
  analyze_ovn_dbs.py ./must-gather/ --node master-0 --query '["OVN_Northbound", {"op":"select", "table":"Logical_Switch", "where":[], "columns":["name"]}]'
        """
    )
    parser.add_argument('must_gather_path', help='Path to must-gather directory')
    parser.add_argument('--node', '-n', help='Filter by node name (supports partial matches)')
    parser.add_argument('--query', '-q', help='Run raw OVSDB JSON query instead of standard analysis')

    args = parser.parse_args()

    if not os.path.isdir(args.must_gather_path):
        print(f"Error: Directory not found: {args.must_gather_path}", file=sys.stderr)
        return 1

    # Check if ovsdb-tool is available
    try:
        subprocess.run(['ovsdb-tool', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: ovsdb-tool not found. Please install openvswitch package.", file=sys.stderr)
        return 1

    # Run query mode or standard analysis
    if args.query:
        return run_raw_query(args.must_gather_path, args.node, args.query)
    else:
        return analyze_northbound_databases(args.must_gather_path, args.node)


if __name__ == '__main__':
    sys.exit(main())
