#!/usr/bin/env python3
"""
Analyze FRR-K8s BGP configuration and state from must-gather data.

PRIMARY FOCUS: Analyze actual running state from dump_frr (authoritative).
SECONDARY: Check FRRConfiguration for suspicious patterns, relate to issues.
"""

import sys
import os
import yaml
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict


def parse_yaml_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse a YAML file."""
    try:
        with open(file_path, 'r') as f:
            doc = yaml.safe_load(f)
            return doc
    except Exception as e:
        print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
    return None


def detect_frrk8s_installation(must_gather_path: Path) -> Dict[str, Any]:
    """Detect FRR-K8s installation and gather basic info."""

    # Check for FRRNodeState CRDs
    patterns = [
        "cluster-scoped-resources/frrk8s.metallb.io/frrnodestates",
        "*/cluster-scoped-resources/frrk8s.metallb.io/frrnodestates",
    ]

    for pattern in patterns:
        for nodestate_dir in must_gather_path.glob(pattern):
            if nodestate_dir.is_dir():
                node_states = list(nodestate_dir.glob("*.yaml"))
                if node_states:
                    return {
                        'installed': True,
                        'namespace': 'openshift-frr-k8s',
                        'node_count': len(node_states)
                    }

    return {'installed': False}


def parse_dump_frr_running_config(dump_frr_path: Path) -> Optional[str]:
    """Parse actual running config from dump_frr - AUTHORITATIVE."""
    try:
        with open(dump_frr_path, 'r') as f:
            content = f.read()

        # Extract section between '###### show running-config' and next '######'
        match = re.search(r'###### show running-config\n(.*?)(?:\n######|$)', content, re.DOTALL)
        if match:
            return match.group(1).strip()
    except Exception as e:
        print(f"Warning: Failed to parse {dump_frr_path}: {e}", file=sys.stderr)

    return None


def parse_bgp_routers_from_config(running_config: str) -> List[Dict[str, Any]]:
    """Extract BGP routers from FRR running config."""
    routers = []

    # Pattern for: router bgp 64512
    # Pattern for: router bgp 64512 vrf evpnl2
    router_pattern = r'router bgp (\d+)(?: vrf (\S+))?'

    for match in re.finditer(router_pattern, running_config, re.MULTILINE):
        asn = int(match.group(1))
        vrf = match.group(2) if match.group(2) else 'default'

        routers.append({
            'asn': asn,
            'vrf': vrf
        })

    return routers


def parse_neighbor_config_from_running_config(running_config: str) -> Dict[str, Dict]:
    """
    Parse neighbor configuration to determine which neighbors are configured to receive routes.

    Returns dict mapping neighbor IP -> {
        'ipv4_activated': bool,
        'ipv6_activated': bool,
        'ipv4_route_map_in': str or None,
        'ipv6_route_map_in': str or None
    }
    """
    neighbors_config = {}

    # Split into router bgp sections
    router_sections = re.split(r'(?=^router bgp \d+)', running_config, flags=re.MULTILINE)

    for section in router_sections:
        if not section.strip().startswith('router bgp'):
            continue

        # Parse IPv4 address-family
        ipv4_af = re.search(r'address-family ipv4 unicast\n(.*?)exit-address-family', section, re.DOTALL)
        if ipv4_af:
            ipv4_content = ipv4_af.group(1)
            # Find activated neighbors and their route-maps
            for line in ipv4_content.split('\n'):
                activate_match = re.match(r'\s+neighbor\s+(\S+)\s+activate', line)
                if activate_match:
                    neighbor_ip = activate_match.group(1)
                    if neighbor_ip not in neighbors_config:
                        neighbors_config[neighbor_ip] = {
                            'ipv4_activated': False,
                            'ipv6_activated': False,
                            'ipv4_route_map_in': None,
                            'ipv6_route_map_in': None
                        }
                    neighbors_config[neighbor_ip]['ipv4_activated'] = True

                # Check for inbound route-map
                routemap_match = re.match(r'\s+neighbor\s+(\S+)\s+route-map\s+(\S+)\s+in', line)
                if routemap_match:
                    neighbor_ip = routemap_match.group(1)
                    route_map = routemap_match.group(2)
                    if neighbor_ip not in neighbors_config:
                        neighbors_config[neighbor_ip] = {
                            'ipv4_activated': False,
                            'ipv6_activated': False,
                            'ipv4_route_map_in': None,
                            'ipv6_route_map_in': None
                        }
                    neighbors_config[neighbor_ip]['ipv4_route_map_in'] = route_map

        # Parse IPv6 address-family
        ipv6_af = re.search(r'address-family ipv6 unicast\n(.*?)exit-address-family', section, re.DOTALL)
        if ipv6_af:
            ipv6_content = ipv6_af.group(1)
            # Find activated neighbors and their route-maps
            for line in ipv6_content.split('\n'):
                activate_match = re.match(r'\s+neighbor\s+(\S+)\s+activate', line)
                if activate_match:
                    neighbor_ip = activate_match.group(1)
                    if neighbor_ip not in neighbors_config:
                        neighbors_config[neighbor_ip] = {
                            'ipv4_activated': False,
                            'ipv6_activated': False,
                            'ipv4_route_map_in': None,
                            'ipv6_route_map_in': None
                        }
                    neighbors_config[neighbor_ip]['ipv6_activated'] = True

                # Check for inbound route-map
                routemap_match = re.match(r'\s+neighbor\s+(\S+)\s+route-map\s+(\S+)\s+in', line)
                if routemap_match:
                    neighbor_ip = routemap_match.group(1)
                    route_map = routemap_match.group(2)
                    if neighbor_ip not in neighbors_config:
                        neighbors_config[neighbor_ip] = {
                            'ipv4_activated': False,
                            'ipv6_activated': False,
                            'ipv4_route_map_in': None,
                            'ipv6_route_map_in': None
                        }
                    neighbors_config[neighbor_ip]['ipv6_route_map_in'] = route_map

    return neighbors_config


def parse_bgp_neighbors_from_dump_frr(dump_frr_path: Path) -> List[Dict[str, Any]]:
    """Extract BGP neighbor state from dump_frr."""
    neighbors = []

    try:
        with open(dump_frr_path, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"Warning: Failed to read {dump_frr_path}: {e}", file=sys.stderr)
        return neighbors

    # Find show bgp neighbor section
    neighbor_section = re.search(r'###### show bgp neighbor\n(.*?)(?:\n######|$)', content, re.DOTALL)
    if not neighbor_section:
        return neighbors

    neighbor_text = neighbor_section.group(1)

    # Split by "BGP neighbor is" to get individual neighbors
    neighbor_blocks = re.split(r'(?=BGP neighbor is )', neighbor_text)

    for block in neighbor_blocks:
        if not block.strip() or not block.startswith('BGP neighbor is'):
            continue

        neighbor = {}

        # Parse: "BGP neighbor is 192.168.111.3, remote AS 64512, local AS 64512, internal link"
        header_match = re.search(r'BGP neighbor is (\S+), remote AS (\d+), local AS (\d+)', block)
        if header_match:
            neighbor['address'] = header_match.group(1)
            neighbor['remote_asn'] = int(header_match.group(2))
            neighbor['local_asn'] = int(header_match.group(3))

        # Parse: "BGP state = Established, up for 00:11:08"
        state_match = re.search(r'BGP state = (\w+)(?:, up for ([\d:]+))?', block)
        if state_match:
            neighbor['state'] = state_match.group(1)
            neighbor['uptime'] = state_match.group(2) if state_match.group(2) else None

        # Parse: "Hostname: 9efb2e697ae4"
        hostname_match = re.search(r'Hostname: (\S+)', block)
        if hostname_match:
            neighbor['hostname'] = hostname_match.group(1)

        if neighbor:
            neighbors.append(neighbor)

    return neighbors


def parse_bgp_routes_from_dump_frr(dump_frr_path: Path) -> Tuple[List[Dict], List[str]]:
    """
    Extract BGP routes from dump_frr and identify issues.

    Returns: (routes, issues)
    """
    routes = {'ipv4': [], 'ipv6': [], 'ipv4_vrf_id': None, 'ipv6_vrf_id': None, 'ipv4_vrf_name': 'default', 'ipv6_vrf_name': 'default'}
    issues = []

    try:
        with open(dump_frr_path, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"Warning: Failed to read {dump_frr_path}: {e}", file=sys.stderr)
        return routes, issues

    # Parse IPv4 routes
    ipv4_section = re.search(r'###### show bgp ipv4\n(.*?)(?:\n######|$)', content, re.DOTALL)
    if ipv4_section:
        section_text = ipv4_section.group(1)

        # Extract VRF ID from header: "BGP table version is 1, local router ID is 192.168.221.22, vrf id 0"
        vrf_id_match = re.search(r'vrf id (\d+)', section_text)
        if vrf_id_match:
            routes['ipv4_vrf_id'] = int(vrf_id_match.group(1))
            # VRF ID 0 is always the default VRF
            routes['ipv4_vrf_name'] = 'default' if routes['ipv4_vrf_id'] == 0 else f'vrf-{routes["ipv4_vrf_id"]}'

        route_lines = section_text.split('\n')
        for line in route_lines:
            # Match route lines: " *>  10.129.0.0/23    0.0.0.0    0         32768 i"
            # Format: <status> <network> <nexthop> <metric> <locprf> <weight> <path> <origin>
            # Status codes can be: *, >, r, s, d, i, S, R, and combinations
            # Network must look like an IPv4 address/CIDR (starts with digit)
            match = re.match(r'\s+([*>rsdiSR= ]+)\s+(\d+\.\S+)\s+(\S+)\s+(.*)', line)
            if match:
                status = match.group(1)
                network = match.group(2)
                nexthop = match.group(3)
                rest_fields = match.group(4).split()

                # Parse remaining fields: Metric LocPrf Weight Path Origin
                # Fields may vary, but typically: metric locprf weight [path...] origin_code
                weight = None
                origin_code = None
                as_path = []

                if len(rest_fields) >= 3:
                    # Typical format: metric locprf weight [path...] origin
                    # Origin code is always last (single char: i, e, ?)
                    if rest_fields[-1] in ['i', 'e', '?']:
                        origin_code = rest_fields[-1]
                        rest_fields = rest_fields[:-1]

                    # Weight is typically the 3rd field (0-based index 2)
                    if len(rest_fields) >= 3:
                        try:
                            weight = int(rest_fields[2])
                        except ValueError:
                            pass

                    # AS path is everything after weight (if present)
                    if len(rest_fields) > 3:
                        as_path = rest_fields[3:]

                # Determine if route is locally originated
                is_local = (
                    (nexthop == '0.0.0.0' or nexthop == '::') and
                    (weight == 32768 or not as_path) and
                    origin_code == 'i'
                )

                route = {
                    'network': network,
                    'nexthop': nexthop,
                    'status': status.strip(),
                    'valid': '*' in status,
                    'best': '>' in status,
                    'rib_failure': 'r' in status,
                    'stale': 'S' in status,
                    'removed': 'R' in status,
                    'weight': weight,
                    'origin_code': origin_code,
                    'as_path': ' '.join(as_path) if as_path else '',
                    'local': is_local
                }
                routes['ipv4'].append(route)

                # Flag issues (priority order)
                if not route['valid']:
                    issues.append(f"❌ CRITICAL: IPv4 route {network} is INVALID (missing *)")
                elif route['rib_failure']:
                    issues.append(f"❌ IPv4 route {network} has RIB-failure")
                elif route['removed']:
                    issues.append(f"⚠️  IPv4 route {network} is marked as Removed")
                elif route['stale']:
                    issues.append(f"⚠️  IPv4 route {network} is Stale")
                elif not route['best']:
                    issues.append(f"⚠️  IPv4 route {network} valid but no best path selected")

    # Parse IPv6 routes
    ipv6_section = re.search(r'###### show bgp ipv6\n(.*?)(?:\n######|$)', content, re.DOTALL)
    if ipv6_section:
        section_text = ipv6_section.group(1)

        # Extract VRF ID from header
        vrf_id_match = re.search(r'vrf id (\d+)', section_text)
        if vrf_id_match:
            routes['ipv6_vrf_id'] = int(vrf_id_match.group(1))
            # VRF ID 0 is always the default VRF
            routes['ipv6_vrf_name'] = 'default' if routes['ipv6_vrf_id'] == 0 else f'vrf-{routes["ipv6_vrf_id"]}'

        route_lines = section_text.split('\n')
        i = 0
        while i < len(route_lines):
            line = route_lines[i]
            # Match route lines: " *>  fd01:0:0:2::/64  ::  0  32768 i"
            # Format: <status> <network> <nexthop> <metric> <locprf> <weight> <path> <origin>
            # Network must look like an IPv6 address/CIDR (contains colons)
            match = re.match(r'\s+([*>rsdiSR= ]+)\s+([0-9a-fA-F:]+/\d+)\s+(\S+)\s*(.*)', line)
            if match:
                status = match.group(1)
                network = match.group(2)
                nexthop = match.group(3)
                rest_fields = match.group(4).split() if match.group(4) else []

                # IPv6 routes may span multiple lines - if rest_fields is empty or incomplete,
                # check the next line for continuation (metric, locprf, weight, path, origin)
                if len(rest_fields) < 3 and i + 1 < len(route_lines):
                    next_line = route_lines[i + 1]
                    # Check if next line is a continuation (starts with whitespace, no status/network)
                    continuation_match = re.match(r'\s+(\d+\s+\d+\s+\d+.*)', next_line)
                    if continuation_match:
                        rest_fields = continuation_match.group(1).split()
                        i += 1  # Skip the continuation line in next iteration

                # Parse remaining fields: Metric LocPrf Weight Path Origin
                weight = None
                origin_code = None
                as_path = []

                if len(rest_fields) >= 3:
                    # Origin code is always last (single char: i, e, ?)
                    if rest_fields[-1] in ['i', 'e', '?']:
                        origin_code = rest_fields[-1]
                        rest_fields = rest_fields[:-1]

                    # Weight is typically the 3rd field (0-based index 2)
                    if len(rest_fields) >= 3:
                        try:
                            weight = int(rest_fields[2])
                        except ValueError:
                            pass

                    # AS path is everything after weight (if present)
                    if len(rest_fields) > 3:
                        as_path = rest_fields[3:]

                # Determine if route is locally originated
                is_local = (
                    (nexthop == '0.0.0.0' or nexthop == '::') and
                    (weight == 32768 or not as_path) and
                    origin_code == 'i'
                )

                route = {
                    'network': network,
                    'nexthop': nexthop,
                    'status': status.strip(),
                    'valid': '*' in status,
                    'best': '>' in status,
                    'rib_failure': 'r' in status,
                    'stale': 'S' in status,
                    'removed': 'R' in status,
                    'weight': weight,
                    'origin_code': origin_code,
                    'as_path': ' '.join(as_path) if as_path else '',
                    'local': is_local
                }
                routes['ipv6'].append(route)

                # Flag issues (priority order)
                if not route['valid']:
                    issues.append(f"❌ CRITICAL: IPv6 route {network} is INVALID (missing *)")
                elif route['rib_failure']:
                    issues.append(f"❌ IPv6 route {network} has RIB-failure")
                elif route['removed']:
                    issues.append(f"⚠️  IPv6 route {network} is marked as Removed")
                elif route['stale']:
                    issues.append(f"⚠️  IPv6 route {network} is Stale")
                elif not route['best']:
                    issues.append(f"⚠️  IPv6 route {network} valid but no best path selected")

            i += 1  # Move to next line

    return routes, issues


def parse_frr_node_state(nodestate_path: Path) -> Dict[str, Any]:
    """Parse FRRNodeState CRD."""
    state = parse_yaml_file(nodestate_path)
    if not state:
        return {}

    return {
        'name': state['metadata']['name'],
        'running_config': state.get('status', {}).get('runningConfig', ''),
        'last_reload_result': state.get('status', {}).get('lastReloadResult', ''),
        'last_conversion_result': state.get('status', {}).get('lastConversionResult', '')
    }


def compare_running_configs(dump_frr_config: str, nodestate_config: str) -> Dict[str, Any]:
    """Compare authoritative dump_frr vs FRRNodeState - flag discrepancies."""
    # Normalize whitespace for comparison
    dump_normalized = '\n'.join(line.strip() for line in dump_frr_config.split('\n') if line.strip())
    node_normalized = '\n'.join(line.strip() for line in nodestate_config.split('\n') if line.strip())

    if dump_normalized != node_normalized:
        return {
            'synced': False,
            'issue': 'FRRNodeState out of sync with actual FRR configuration'
        }

    return {'synced': True}


def parse_frr_configurations(must_gather_path: Path) -> Tuple[List[Dict], List[str]]:
    """
    Light parsing of FRRConfiguration CRDs.
    Detect issues, inventory configs, but don't attempt deep mapping.

    Returns: (configs, issues)
    """
    configs = []
    issues = []

    patterns = [
        "namespaces/openshift-frr-k8s/frrk8s.metallb.io/frrconfigurations/*.yaml",
        "*/namespaces/openshift-frr-k8s/frrk8s.metallb.io/frrconfigurations/*.yaml",
    ]

    for pattern in patterns:
        for config_file in must_gather_path.glob(pattern):
            config = parse_yaml_file(config_file)
            if not config:
                continue

            name = config['metadata']['name']
            spec = config.get('spec', {})

            # Check for raw config (UNSUPPORTED)
            has_raw_config = 'raw' in spec and spec['raw'].get('rawConfig')
            if has_raw_config:
                issues.append(f"⚠️  UNSUPPORTED: Raw config in use ({name})")

            # Extract basic info
            bgp_spec = spec.get('bgp', {})
            routers = bgp_spec.get('routers', [])
            bfd_profiles = bgp_spec.get('bfdProfiles', [])
            node_selector = spec.get('nodeSelector', {})

            # Build neighbor list for search purposes
            neighbors = []
            for router in routers:
                for neighbor in router.get('neighbors', []):
                    neighbors.append({
                        'address': neighbor.get('address'),
                        'asn': neighbor.get('asn'),
                        'vrf': router.get('vrf', 'default')
                    })

            configs.append({
                'name': name,
                'has_raw_config': has_raw_config,
                'node_selector': node_selector,
                'router_count': len(routers),
                'neighbor_count': len(neighbors),
                'neighbors': neighbors,
                'bfd_profiles': [p['name'] for p in bfd_profiles]
            })

            # Check for missing BFD profile references
            referenced_profiles = set()
            defined_profiles = set(p['name'] for p in bfd_profiles)

            for router in routers:
                for neighbor in router.get('neighbors', []):
                    bfd_profile = neighbor.get('bfdProfile')
                    if bfd_profile:
                        referenced_profiles.add(bfd_profile)

            missing_profiles = referenced_profiles - defined_profiles
            for profile in missing_profiles:
                issues.append(f"⚠️  BFD profile '{profile}' referenced but not defined in {name}")

    return configs, issues


def find_configs_for_neighbor(neighbor_address: str, configs: List[Dict]) -> List[str]:
    """Find which FRRConfigurations define a specific neighbor (best effort hint)."""
    config_names = []

    for config in configs:
        for neighbor in config['neighbors']:
            if neighbor['address'] == neighbor_address:
                config_names.append(config['name'])
                break

    return config_names


def parse_frr_pod_status(must_gather_path: Path) -> Dict[str, Any]:
    """Parse FRR pod status."""
    pods = {}

    patterns = [
        "namespaces/openshift-frr-k8s/pods/frr-k8s-*/frr-k8s-*.yaml",
        "*/namespaces/openshift-frr-k8s/pods/frr-k8s-*/frr-k8s-*.yaml",
    ]

    for pattern in patterns:
        for pod_file in must_gather_path.glob(pattern):
            # Skip webhook server
            if 'webhook-server' in str(pod_file):
                continue

            pod = parse_yaml_file(pod_file)
            if not pod:
                continue

            name = pod['metadata']['name']
            status = pod.get('status', {})
            spec = pod.get('spec', {})

            # Get node name
            node_name = spec.get('nodeName', 'unknown')

            # Get pod phase and container statuses
            phase = status.get('phase', 'Unknown')
            container_statuses = status.get('containerStatuses', [])

            restarts = 0
            for container in container_statuses:
                restarts += container.get('restartCount', 0)

            pods[name] = {
                'node': node_name,
                'phase': phase,
                'restarts': restarts
            }

    return pods


def analyze_node_bgp(must_gather_path: Path, node_name: str,
                     configs: List[Dict]) -> Dict[str, Any]:
    """Analyze BGP for a specific node."""

    result = {
        'node_name': node_name,
        'routers': [],
        'neighbors': [],
        'routes': {'ipv4': [], 'ipv6': []},
        'issues': [],
        'sync_status': None
    }

    # Find dump_frr file for this node
    dump_frr_patterns = [
        "namespaces/openshift-frr-k8s/pods/*/frr/frr/logs/dump_frr",
        "*/namespaces/openshift-frr-k8s/pods/*/frr/frr/logs/dump_frr",
    ]

    dump_frr_path = None
    for pattern in dump_frr_patterns:
        for path in must_gather_path.glob(pattern):
            # Check if this dump_frr is from a pod on this node
            # We need to read the pod yaml to determine node assignment
            # Path is: pods/frr-k8s-*/frr/frr/logs/dump_frr
            # So pod dir is 4 levels up
            pod_dir = path.parent.parent.parent.parent
            pod_yaml_files = list(pod_dir.glob("*.yaml"))
            if pod_yaml_files:
                pod = parse_yaml_file(pod_yaml_files[0])
                if pod and pod.get('spec', {}).get('nodeName') == node_name:
                    dump_frr_path = path
                    break
        if dump_frr_path:
            break

    if not dump_frr_path:
        result['issues'].append(f"⚠️  FRR runtime state not found in must-gather for node {node_name}")
        return result

    # Parse running config from dump_frr (AUTHORITATIVE)
    running_config = parse_dump_frr_running_config(dump_frr_path)
    if running_config:
        result['routers'] = parse_bgp_routers_from_config(running_config)

    # Parse neighbors from dump_frr
    result['neighbors'] = parse_bgp_neighbors_from_dump_frr(dump_frr_path)

    # Parse routes from dump_frr
    routes, route_issues = parse_bgp_routes_from_dump_frr(dump_frr_path)
    result['routes'] = routes
    result['issues'].extend(route_issues)

    # Check if multiple VRFs are configured but only default VRF routes are shown
    configured_vrfs = [r['vrf'] for r in result['routers']]
    if len(configured_vrfs) > 1:
        # Check if routes are only from default VRF (vrf id 0)
        ipv4_vrf_id = routes.get('ipv4_vrf_id')
        ipv6_vrf_id = routes.get('ipv6_vrf_id')

        if (ipv4_vrf_id == 0 or ipv6_vrf_id == 0):
            vrf_list = ', '.join(sorted(set(configured_vrfs)))
            result['issues'].append(
                f"⚠️  Multiple VRFs configured ({vrf_list}) but only default VRF routes available in must-gather"
            )

    # Check neighbor states and relate to configs
    for neighbor in result['neighbors']:
        if neighbor.get('state') != 'Established':
            config_names = find_configs_for_neighbor(neighbor['address'], configs)
            config_hint = f" (configured in: {', '.join(config_names)})" if config_names else ""
            result['issues'].append(
                f"❌ BGP neighbor {neighbor['address']} in {neighbor.get('state', 'Unknown')} state{config_hint}"
            )

    # Check if neighbors are configured to receive routes but no routes are being received
    if running_config:
        neighbor_configs = parse_neighbor_config_from_running_config(running_config)
        ipv4_received = sum(1 for r in routes.get('ipv4', []) if not r.get('local'))
        ipv6_received = sum(1 for r in routes.get('ipv6', []) if not r.get('local'))

        # Check each neighbor that is configured with inbound route-maps
        for neighbor_ip, config in neighbor_configs.items():
            # Find if this neighbor is established
            neighbor_state = next((n for n in result['neighbors'] if n.get('address') == neighbor_ip), None)

            if neighbor_state and neighbor_state.get('state') == 'Established':
                # Check IPv4
                if config['ipv4_activated'] and config['ipv4_route_map_in'] and ipv4_received == 0:
                    result['issues'].append(
                        f"⚠️  Neighbor {neighbor_ip} configured to receive IPv4 routes (route-map: {config['ipv4_route_map_in']}) "
                        f"but no IPv4 routes received - verify peer is advertising routes"
                    )
                # Check IPv6
                if config['ipv6_activated'] and config['ipv6_route_map_in'] and ipv6_received == 0:
                    result['issues'].append(
                        f"⚠️  Neighbor {neighbor_ip} configured to receive IPv6 routes (route-map: {config['ipv6_route_map_in']}) "
                        f"but no IPv6 routes received - verify peer is advertising routes"
                    )

    # Compare dump_frr with FRRNodeState
    nodestate_patterns = [
        f"cluster-scoped-resources/frrk8s.metallb.io/frrnodestates/{node_name}.yaml",
        f"*/cluster-scoped-resources/frrk8s.metallb.io/frrnodestates/{node_name}.yaml",
    ]

    for pattern in nodestate_patterns:
        for nodestate_path in must_gather_path.glob(pattern):
            nodestate = parse_frr_node_state(nodestate_path)
            if nodestate and running_config:
                sync = compare_running_configs(running_config, nodestate.get('running_config', ''))
                result['sync_status'] = sync

                if not sync.get('synced'):
                    # Check if raw config is in use
                    has_raw = any(c['has_raw_config'] for c in configs)
                    issue_msg = sync['issue']
                    if has_raw:
                        issue_msg += " (likely due to raw config usage - unsupported)"
                    result['issues'].append(f"❌ CRITICAL: {issue_msg}")

                # Check reload result
                reload_result = nodestate.get('last_reload_result', '')
                if reload_result and 'Error' in reload_result or 'Traceback' in reload_result:
                    result['issues'].append(f"⚠️  FRR reload errors detected")
            break

    return result


def format_output(analysis_results: Dict[str, Any], verbose: bool = False) -> str:
    """Format analysis results for display."""

    lines = []
    lines.append("=" * 80)
    lines.append("BGP ANALYSIS SUMMARY")
    lines.append("=" * 80)

    install = analysis_results['installation']
    if not install['installed']:
        lines.append("FRR-K8s Status:    Not Installed")
        lines.append("")
        lines.append("No FRR-K8s installation detected in this must-gather.")
        lines.append("FRR-K8s is used for advanced BGP routing in OpenShift clusters.")
        lines.append("If you expected FRR-K8s to be present, check:")
        lines.append("- CNO configuration (spec.defaultNetwork.ovnKubernetesConfig.additionalRoutingCapabilities)")
        lines.append("- openshift-frr-k8s namespace should exist")
        lines.append("=" * 80)
        return '\n'.join(lines)

    lines.append(f"FRR-K8s Status:    Installed")
    lines.append(f"Namespace:         {install['namespace']}")

    pod_status = analysis_results.get('pod_status', {})
    running_pods = sum(1 for p in pod_status.values() if p['phase'] == 'Running')
    total_pods = len(pod_status)
    lines.append(f"FRR Pods:          {running_pods}/{total_pods} Running")

    configs = analysis_results.get('configs', [])
    lines.append(f"Configurations:    {len(configs)} FRRConfiguration resources found")
    lines.append("")

    # Per-node status
    lines.append("PER-NODE BGP STATUS (from actual running config):")
    lines.append("")

    for node_data in analysis_results.get('nodes', []):
        node_name = node_data['node_name']
        lines.append(f"NODE: {node_name}")
        lines.append("─" * 65)

        # Routers
        if node_data['routers']:
            lines.append("BGP ROUTERS:")
            lines.append(f"{'VRF':<15} {'ASN':<10}")
            for router in node_data['routers']:
                lines.append(f"{router['vrf']:<15} {router['asn']:<10}")
            lines.append("")

        # Neighbors
        if node_data['neighbors']:
            lines.append("NEIGHBORS:")
            lines.append(f"{'PEER ADDRESS':<40} {'ASN':<10} {'STATE':<20} {'UPTIME':<10}")
            for neighbor in node_data['neighbors']:
                address = neighbor.get('address', 'unknown')
                asn = neighbor.get('remote_asn', 'unknown')
                raw_state = neighbor.get('state', 'Unknown')
                # Format state as "Up (Established)" or "Down (state)"
                if raw_state == 'Established':
                    state = 'Up (Established)'
                else:
                    state = f'Down ({raw_state})'
                uptime = neighbor.get('uptime') or '-'
                lines.append(f"{address:<40} {asn:<10} {state:<20} {uptime:<10}")
            lines.append("")

        # Routes summary
        ipv4_routes = node_data['routes'].get('ipv4', [])
        ipv6_routes = node_data['routes'].get('ipv6', [])
        ipv4_vrf_name = node_data['routes'].get('ipv4_vrf_name', 'default')
        ipv4_vrf_id = node_data['routes'].get('ipv4_vrf_id')
        ipv6_vrf_name = node_data['routes'].get('ipv6_vrf_name', 'default')
        ipv6_vrf_id = node_data['routes'].get('ipv6_vrf_id')

        if ipv4_routes:
            ipv4_best = sum(1 for r in ipv4_routes if r['best'])
            ipv4_local = sum(1 for r in ipv4_routes if r.get('local'))
            ipv4_received = len(ipv4_routes) - ipv4_local
            vrf_label = f" [VRF: {ipv4_vrf_name}]"
            lines.append(f"ROUTES (IPv4){vrf_label}: {len(ipv4_routes)} total, {ipv4_best} best ({ipv4_local} local, {ipv4_received} received)")
            if verbose:
                for route in ipv4_routes[:5]:  # Show first 5
                    origin = "local" if route.get('local') else "received"
                    lines.append(f"  {route['status']:<5} {route['network']:<20} via {route['nexthop']:<40} ({origin})")

        if ipv6_routes:
            ipv6_best = sum(1 for r in ipv6_routes if r['best'])
            ipv6_local = sum(1 for r in ipv6_routes if r.get('local'))
            ipv6_received = len(ipv6_routes) - ipv6_local
            vrf_label = f" [VRF: {ipv6_vrf_name}]"
            lines.append(f"ROUTES (IPv6){vrf_label}: {len(ipv6_routes)} total, {ipv6_best} best ({ipv6_local} local, {ipv6_received} received)")
            if verbose:
                for route in ipv6_routes[:5]:  # Show first 5
                    origin = "local" if route.get('local') else "received"
                    lines.append(f"  {route['status']:<5} {route['network']:<20} via {route['nexthop']:<40} ({origin})")

        lines.append("")

    # Issues section
    lines.append("=" * 80)
    lines.append("ISSUES DETECTED")
    lines.append("=" * 80)
    lines.append("")

    # Collect all issues
    critical_issues = []
    warnings = []
    config_issues = analysis_results.get('config_issues', [])

    for node_data in analysis_results.get('nodes', []):
        for issue in node_data['issues']:
            if '❌ CRITICAL' in issue:
                critical_issues.append(f"{node_data['node_name']}: {issue}")
            elif '❌' in issue:
                critical_issues.append(f"{node_data['node_name']}: {issue}")
            else:
                warnings.append(f"{node_data['node_name']}: {issue}")

    # Display critical issues
    if critical_issues:
        lines.append("CRITICAL ISSUES:")
        for issue in critical_issues:
            lines.append(issue)
        lines.append("")
    else:
        lines.append("CRITICAL ISSUES:")
        lines.append("✅ No critical issues detected")
        lines.append("")

    # Display warnings
    if warnings or config_issues:
        lines.append("WARNINGS:")
        for warning in warnings:
            lines.append(warning)
        for warning in config_issues:
            lines.append(warning)
        lines.append("")

    # Recommendations (grouped by issue type)
    if critical_issues or warnings or config_issues:
        lines.append("RECOMMENDATIONS:")
        lines.append("")
        all_issues = critical_issues + warnings + config_issues

        # Check for raw config
        has_raw = any(c['has_raw_config'] for c in configs)
        if has_raw:
            lines.append("Issue: Raw BGP configuration in use")
            lines.append("→ Remove raw config from FRRConfigurations (unsupported, can cause sync issues)")
            lines.append("")

        # Check for neighbor connectivity issues (not Established)
        if any('neighbor' in str(i).lower() and any(state in str(i).lower() for state in ['idle', 'active', 'connect', 'opensent', 'openconfirm']) for i in all_issues):
            lines.append("Issue: BGP neighbors not in Established state")
            lines.append("→ Check network connectivity to BGP peers")
            lines.append("→ Verify firewall rules allow BGP port 179")
            lines.append("→ Review FRR container logs for session establishment errors")
            lines.append("")

        # Check for configured to receive routes but not receiving
        if any('configured to receive' in str(i) and 'but no' in str(i) and 'routes received' in str(i) for i in all_issues):
            lines.append("Issue: Neighbors configured to receive routes but not receiving any")
            lines.append("→ Verify BGP peers are advertising expected routes")
            lines.append("→ Check for route-map filters that may be blocking incoming routes")
            lines.append("→ Review BGP policies on peer side")
            lines.append("")

        # Check for VRF route collection issues
        if any('Multiple VRFs configured' in str(i) and 'only default VRF routes available' in str(i) for i in all_issues):
            lines.append("Issue: Multiple VRFs configured but only default VRF routes available")
            lines.append("→ VRF-specific routes not collected in must-gather")
            lines.append("→ Only default VRF route data is available for analysis")
            lines.append("→ To collect all VRF routes, enhance must-gather collection to include VRF-specific route tables")
            lines.append("")

        # Check for invalid routes
        if any('invalid' in str(i).lower() and 'route' in str(i).lower() for i in all_issues):
            lines.append("Issue: Routes marked as invalid")
            lines.append("→ Check route-map policies and prefix filters")
            lines.append("→ Verify next-hop reachability")
            lines.append("")

        # Check for RIB failures
        if any('rib-failure' in str(i).lower() for i in all_issues):
            lines.append("Issue: Routes with RIB-failure")
            lines.append("→ Check for conflicting static routes")
            lines.append("→ Review administrative distance settings")
            lines.append("")

        # Check for stale routes
        if any('stale' in str(i).lower() and 'route' in str(i).lower() for i in all_issues):
            lines.append("Issue: Stale routes detected")
            lines.append("→ Check BGP graceful restart configuration")
            lines.append("→ Verify peer session stability")
            lines.append("")

        # Check for sync issues
        if any('sync' in str(i).lower() or 'out of sync' in str(i).lower() for i in all_issues):
            lines.append("Issue: FRR configuration out of sync")
            lines.append("→ Investigate FRR-K8s controller logs for sync errors")
            lines.append("→ Check for manual FRR configuration changes outside of FRR-K8s")
            lines.append("")

        # Check for pod issues
        if any('pod not' in str(i).lower() or 'not running' in str(i).lower() or 'runtime state not found' in str(i).lower() for i in all_issues):
            lines.append("Issue: FRR pods not running or runtime state unavailable")
            lines.append("→ Check FRR pod status and events for crash/restart reasons")
            lines.append("→ Review pod logs for errors")
            lines.append("")

    lines.append("=" * 80)

    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_bgp.py <must-gather-path> [--verbose] [--node <node-name>]")
        print("")
        print("Analyze FRR-K8s BGP configuration and state from must-gather data.")
        print("")
        print("Options:")
        print("  --verbose           Show detailed output")
        print("  --node <node-name>  Analyze specific node only")
        sys.exit(1)

    must_gather_path = Path(sys.argv[1])
    verbose = '--verbose' in sys.argv

    # Parse node filter
    node_filter = None
    if '--node' in sys.argv:
        node_idx = sys.argv.index('--node')
        if node_idx + 1 < len(sys.argv):
            node_filter = sys.argv[node_idx + 1]

    if not must_gather_path.exists():
        print(f"Error: Must-gather path does not exist: {must_gather_path}", file=sys.stderr)
        sys.exit(1)

    # Detect FRR-K8s installation
    installation = detect_frrk8s_installation(must_gather_path)

    analysis_results = {
        'installation': installation,
        'nodes': [],
        'configs': [],
        'config_issues': [],
        'pod_status': {}
    }

    if not installation['installed']:
        print(format_output(analysis_results, verbose))
        return

    # Parse FRRConfigurations (light parsing)
    configs, config_issues = parse_frr_configurations(must_gather_path)
    analysis_results['configs'] = configs
    analysis_results['config_issues'] = config_issues

    # Parse pod status
    pod_status = parse_frr_pod_status(must_gather_path)
    analysis_results['pod_status'] = pod_status

    # Find all nodes with FRRNodeState
    nodestate_patterns = [
        "cluster-scoped-resources/frrk8s.metallb.io/frrnodestates/*.yaml",
        "*/cluster-scoped-resources/frrk8s.metallb.io/frrnodestates/*.yaml",
    ]

    nodes = set()
    for pattern in nodestate_patterns:
        for nodestate_file in must_gather_path.glob(pattern):
            nodestate = parse_yaml_file(nodestate_file)
            if nodestate:
                node_name = nodestate['metadata']['name']
                nodes.add(node_name)

    # Analyze each node
    for node_name in sorted(nodes):
        if node_filter and node_filter not in node_name:
            continue

        node_analysis = analyze_node_bgp(must_gather_path, node_name, configs)
        analysis_results['nodes'].append(node_analysis)

    # Format and print output
    output = format_output(analysis_results, verbose)
    print(output)


if __name__ == '__main__':
    main()
