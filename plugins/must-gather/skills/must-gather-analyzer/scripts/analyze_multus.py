#!/usr/bin/env python3
"""
Analyze Multus CNI configuration and pods using NADs from must-gather data.
Generates comprehensive HTML report and failure analysis.
"""

import sys
import os
import yaml
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
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


def find_must_gather_root(path: Path) -> Optional[Path]:
    """Find the actual must-gather root directory."""
    # Check if current path is already the root
    if (path / "cluster-scoped-resources").exists():
        return path
    
    # Check if path contains quay-io-* directory
    for item in path.rglob("*"):
        if item.is_dir() and item.name.startswith("quay-io-"):
            return item
    
    # Check for must-gather.tar and extract it
    for tar_file in path.rglob("must-gather.tar"):
        print(f"Found must-gather.tar: {tar_file}")
        extract_dir = tar_file.parent / "extracted-must-gather"
        if not extract_dir.exists():
            print(f"Extracting {tar_file} to {extract_dir}...")
            import tarfile
            extract_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(tar_file, 'r') as tar:
                tar.extractall(extract_dir)
        
        # Find quay-io-* directory in extracted content
        for item in extract_dir.rglob("*"):
            if item.is_dir() and item.name.startswith("quay-io-"):
                return item
    
    return None


def get_cluster_version(mg_root: Path) -> Dict[str, Any]:
    """Get cluster version information."""
    patterns = [
        "cluster-scoped-resources/config.openshift.io/clusterversions/*.yaml",
    ]
    
    for pattern in patterns:
        for cv_file in mg_root.glob(pattern):
            cv = parse_yaml_file(cv_file)
            if cv:
                status = cv.get('status', {})
                desired = status.get('desired', {})
                history = status.get('history', [])
                conditions = status.get('conditions', [])
                
                progressing = "Unknown"
                since = "Unknown"
                message = ""
                
                for cond in conditions:
                    if cond.get('type') == 'Progressing':
                        progressing = cond.get('status', 'Unknown')
                        since = cond.get('lastTransitionTime', 'Unknown')
                        message = cond.get('message', '')
                
                available_updates = status.get('availableUpdates', [])
                if available_updates is None:
                    available_updates = []
                
                return {
                    'version': desired.get('version', 'Unknown'),
                    'available_updates': len(available_updates),
                    'progressing': progressing,
                    'since': since,
                    'message': message
                }
    
    return {'version': 'Unknown', 'available_updates': 0, 'progressing': 'Unknown', 'since': 'Unknown', 'message': ''}


def get_nodes(mg_root: Path) -> List[Dict[str, Any]]:
    """Get node information."""
    nodes = []
    patterns = [
        "cluster-scoped-resources/core/nodes/*.yaml",
    ]
    
    for pattern in patterns:
        for node_file in mg_root.glob(pattern):
            if node_file.name == 'nodes.yaml':
                continue
            
            node = parse_yaml_file(node_file)
            if node:
                name = node.get('metadata', {}).get('name', 'unknown')
                status = node.get('status', {})
                conditions = status.get('conditions', [])
                
                ready_status = "Unknown"
                for cond in conditions:
                    if cond.get('type') == 'Ready':
                        ready_status = "Ready" if cond.get('status') == 'True' else "NotReady"
                
                roles = []
                labels = node.get('metadata', {}).get('labels', {})
                for label, value in labels.items():
                    if 'node-role.kubernetes.io/' in label:
                        role = label.split('/')[-1]
                        roles.append(role)
                
                node_info = status.get('nodeInfo', {})
                addresses = status.get('addresses', [])
                internal_ip = "Unknown"
                for addr in addresses:
                    if addr.get('type') == 'InternalIP':
                        internal_ip = addr.get('address', 'Unknown')
                
                creation_time = node.get('metadata', {}).get('creationTimestamp', '')
                age = calculate_age(creation_time)
                
                nodes.append({
                    'name': name,
                    'status': ready_status,
                    'roles': ','.join(roles) if roles else 'worker',
                    'version': node_info.get('kubeletVersion', 'Unknown'),
                    'age': age,
                    'internal_ip': internal_ip
                })
    
    return sorted(nodes, key=lambda x: x['name'])


def get_network_config(mg_root: Path) -> Dict[str, Any]:
    """Get network configuration."""
    network_info = {
        'network_type': 'Unknown',
        'cluster_cidr': 'Unknown',
        'service_cidr': 'Unknown',
        'service_network': [],
        'mtu': 'Unknown',
        'host_prefix': 'Unknown',
        'platform_type': 'Unknown'
    }
    
    # Get network config
    patterns = [
        "cluster-scoped-resources/config.openshift.io/networks.yaml",
    ]
    
    for pattern in patterns:
        for net_file in mg_root.glob(pattern):
            net_list = parse_yaml_file(net_file)
            if net_list:
                items = net_list.get('items', [])
                if items:
                    net = items[0]
                    spec = net.get('spec', {})
                    status = net.get('status', {})
                    
                    cluster_network = spec.get('clusterNetwork', [])
                    service_network = spec.get('serviceNetwork', [])
                    
                    network_info.update({
                        'network_type': spec.get('networkType', 'Unknown'),
                        'cluster_cidr': cluster_network[0].get('cidr', 'Unknown') if cluster_network else 'Unknown',
                        'service_cidr': service_network[0] if service_network else 'Unknown',
                        'service_network': service_network,
                        'mtu': status.get('clusterNetworkMTU', 'Unknown'),
                        'host_prefix': cluster_network[0].get('hostPrefix', 'Unknown') if cluster_network else 'Unknown'
                    })
    
    # Get platform type from infrastructure
    infra_patterns = [
        "cluster-scoped-resources/config.openshift.io/infrastructures.yaml",
    ]
    
    for pattern in infra_patterns:
        for infra_file in mg_root.glob(pattern):
            infra_list = parse_yaml_file(infra_file)
            if infra_list:
                items = infra_list.get('items', [])
                if items:
                    infra = items[0]
                    status = infra.get('status', {})
                    network_info['platform_type'] = status.get('platformStatus', {}).get('type', 'Unknown')
                    break
    
    return network_info


def get_cluster_operators(mg_root: Path) -> List[Dict[str, Any]]:
    """Get cluster operator status."""
    operators = []
    patterns = [
        "cluster-scoped-resources/config.openshift.io/clusteroperators/*.yaml",
    ]
    
    for pattern in patterns:
        for op_file in mg_root.glob(pattern):
            if op_file.name == 'clusteroperators.yaml':
                continue
            
            op = parse_yaml_file(op_file)
            if op:
                name = op.get('metadata', {}).get('name', 'unknown')
                status = op.get('status', {})
                versions = status.get('versions', [])
                version = 'Unknown'
                for v in versions:
                    if v.get('name') == 'operator':
                        version = v.get('version', 'Unknown')
                        break
                
                conditions = status.get('conditions', [])
                available = "Unknown"
                progressing = "Unknown"
                degraded = "Unknown"
                message = ""
                
                for cond in conditions:
                    cond_type = cond.get('type')
                    if cond_type == 'Available':
                        available = cond.get('status', 'Unknown')
                    elif cond_type == 'Progressing':
                        progressing = cond.get('status', 'Unknown')
                    elif cond_type == 'Degraded':
                        degraded = cond.get('status', 'Unknown')
                        if degraded == 'True':
                            message = cond.get('message', '')
                
                if not message:
                    for cond in conditions:
                        if cond.get('type') == 'Available':
                            message = cond.get('message', '')
                            break
                
                operators.append({
                    'name': name,
                    'version': version,
                    'available': available,
                    'progressing': progressing,
                    'degraded': degraded,
                    'message': message
                })
    
    return sorted(operators, key=lambda x: x['name'])


def get_multus_daemonsets(mg_root: Path) -> List[Dict[str, Any]]:
    """Get Multus DaemonSet information."""
    daemonsets = []
    patterns = [
        "namespaces/openshift-multus/apps/daemonsets/*.yaml",
    ]
    
    for pattern in patterns:
        for ds_file in mg_root.glob(pattern):
            if ds_file.name == 'daemonsets.yaml':
                continue
            
            ds = parse_yaml_file(ds_file)
            if ds:
                name = ds.get('metadata', {}).get('name', 'unknown')
                status = ds.get('status', {})
                
                daemonsets.append({
                    'name': name,
                    'desired': status.get('desiredNumberScheduled', 0),
                    'ready': status.get('numberReady', 0),
                    'available': status.get('numberAvailable', 0)
                })
    
    return sorted(daemonsets, key=lambda x: x['name'])


def get_multus_deployments(mg_root: Path) -> List[Dict[str, Any]]:
    """Get Multus Deployment information."""
    deployments = []
    patterns = [
        "namespaces/openshift-multus/apps/deployments/*.yaml",
    ]
    
    for pattern in patterns:
        for dep_file in mg_root.glob(pattern):
            if dep_file.name == 'deployments.yaml':
                continue
            
            dep = parse_yaml_file(dep_file)
            if dep:
                name = dep.get('metadata', {}).get('name', 'unknown')
                spec = dep.get('spec', {})
                status = dep.get('status', {})
                
                deployments.append({
                    'name': name,
                    'replicas': spec.get('replicas', 0),
                    'ready': status.get('readyReplicas', 0),
                    'available': status.get('availableReplicas', 0)
                })
    
    return sorted(deployments, key=lambda x: x['name'])


def get_multus_pods(mg_root: Path) -> List[Dict[str, Any]]:
    """Get Multus pod information."""
    pods = []
    patterns = [
        "namespaces/openshift-multus/pods/*/*.yaml",
    ]
    
    for pattern in patterns:
        for pod_file in mg_root.glob(pattern):
            pod = parse_yaml_file(pod_file)
            if pod:
                name = pod.get('metadata', {}).get('name', 'unknown')
                spec = pod.get('spec', {})
                status = pod.get('status', {})
                
                # Determine pod type from name
                pod_type = "unknown"
                if name.startswith("multus-admission-controller"):
                    pod_type = "multus-admission-controller"
                elif name.startswith("multus-additional-cni-plugins"):
                    pod_type = "multus-additional-cni-plugins"
                elif name.startswith("multus-"):
                    pod_type = "multus"
                elif name.startswith("network-metrics-daemon"):
                    pod_type = "network-metrics-daemon"
                
                container_statuses = status.get('containerStatuses', [])
                restarts = sum(cs.get('restartCount', 0) for cs in container_statuses)
                
                creation_time = pod.get('metadata', {}).get('creationTimestamp', '')
                age = calculate_age(creation_time)
                
                pods.append({
                    'name': name,
                    'type': pod_type,
                    'node': spec.get('nodeName', 'Unknown'),
                    'status': status.get('phase', 'Unknown'),
                    'restarts': restarts,
                    'age': age
                })
    
    return sorted(pods, key=lambda x: x['name'])


def get_network_attachment_definitions(mg_root: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Get NetworkAttachmentDefinition information."""
    nads_by_namespace = defaultdict(list)
    
    # Search in all namespaces
    patterns = [
        "namespaces/*/k8s.cni.cncf.io/network-attachment-definitions/*.yaml",
        "cluster-scoped-resources/k8s.cni.cncf.io/network-attachment-definitions/*.yaml",
    ]
    
    for pattern in patterns:
        for nad_file in mg_root.glob(pattern):
            if nad_file.name == 'network-attachment-definitions.yaml':
                continue
            
            nad = parse_yaml_file(nad_file)
            if nad:
                name = nad.get('metadata', {}).get('name', 'unknown')
                namespace = nad.get('metadata', {}).get('namespace', 'cluster-scoped')
                spec = nad.get('spec', {})
                config_str = spec.get('config', '{}')
                
                try:
                    config = json.loads(config_str)
                except:
                    config = {}
                
                cni_type = config.get('type', 'Unknown')
                cni_version = config.get('cniVersion', 'Unknown')
                ipam = config.get('ipam', {})
                ipam_type = ipam.get('type', 'None') if ipam else 'None'
                
                creation_time = nad.get('metadata', {}).get('creationTimestamp', '')
                
                nads_by_namespace[namespace].append({
                    'name': name,
                    'namespace': namespace,
                    'type': cni_type,
                    'cni_version': cni_version,
                    'ipam_type': ipam_type,
                    'config': config,
                    'config_str': config_str,
                    'created': creation_time
                })
    
    # Sort NADs within each namespace
    for namespace in nads_by_namespace:
        nads_by_namespace[namespace] = sorted(nads_by_namespace[namespace], key=lambda x: x['name'])
    
    return dict(nads_by_namespace)


def get_whereabouts_ippools(mg_root: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Get whereabouts IPPool allocations."""
    ippools_by_namespace = defaultdict(list)
    
    patterns = [
        "namespaces/*/whereabouts.cni.cncf.io/ippools/*.yaml",
        "cluster-scoped-resources/whereabouts.cni.cncf.io/ippools/*.yaml",
    ]
    
    for pattern in patterns:
        for ippool_file in mg_root.glob(pattern):
            if ippool_file.name in ['ippools.yaml']:
                continue
            
            ippool = parse_yaml_file(ippool_file)
            if ippool:
                metadata = ippool.get('metadata', {})
                name = metadata.get('name', 'unknown')
                namespace = metadata.get('namespace', 'default')
                
                # Parse allocations
                spec = ippool.get('spec', {})
                allocations = spec.get('allocations', {})
                ip_range = spec.get('range', '')
                
                # Parse the IP range to calculate actual IPs
                import ipaddress
                try:
                    network = ipaddress.ip_network(ip_range, strict=False)
                    base_ip = network.network_address
                except:
                    base_ip = None
                
                for alloc_index, allocation_data in allocations.items():
                    if not isinstance(allocation_data, dict):
                        continue
                    
                    # Extract pod reference
                    pod_ref = allocation_data.get('podref', '')
                    ifname = allocation_data.get('ifname', 'net1')
                    
                    # Calculate IP from allocation index
                    ip_str = ''
                    if base_ip:
                        try:
                            # Allocation index is the offset from the base IP
                            ip_offset = int(alloc_index)
                            allocated_ip = base_ip + ip_offset
                            ip_str = str(allocated_ip)
                        except:
                            ip_str = f"{ip_range} (offset {alloc_index})"
                    
                    ippools_by_namespace[namespace].append({
                        'ippool_name': name,
                        'alloc_index': alloc_index,
                        'pod_ref': pod_ref,
                        'ifname': ifname,
                        'ip': ip_str,
                        'range': ip_range
                    })
    
    return dict(ippools_by_namespace)


def get_multi_networked_pods(mg_root: Path) -> List[Dict[str, Any]]:
    """Get pods with multiple network interfaces."""
    multi_networked_pods = []
    
    # Search all pods for k8s.v1.cni.cncf.io/networks annotation
    patterns = [
        "namespaces/*/pods/*/*.yaml",
    ]
    
    for pattern in patterns:
        for pod_file in mg_root.glob(pattern):
            pod = parse_yaml_file(pod_file)
            if pod:
                annotations = pod.get('metadata', {}).get('annotations', {})
                networks_annotation = annotations.get('k8s.v1.cni.cncf.io/networks')
                
                if networks_annotation:
                    name = pod.get('metadata', {}).get('name', 'unknown')
                    namespace = pod.get('metadata', {}).get('namespace', 'unknown')
                    spec = pod.get('spec', {})
                    status = pod.get('status', {})
                    
                    # Parse networks annotation
                    try:
                        if networks_annotation.startswith('['):
                            networks = json.loads(networks_annotation)
                        else:
                            networks = [{'name': net.strip()} for net in networks_annotation.split(',')]
                    except:
                        networks = []
                    
                    # Get network status
                    network_status_str = annotations.get('k8s.v1.cni.cncf.io/network-status', '[]')
                    try:
                        network_status = json.loads(network_status_str)
                    except:
                        network_status = []
                    
                    multi_networked_pods.append({
                        'name': name,
                        'namespace': namespace,
                        'node': spec.get('nodeName', 'Unknown'),
                        'status': status.get('phase', 'Unknown'),
                        'networks': networks,
                        'network_status': network_status
                    })
    
    return sorted(multi_networked_pods, key=lambda x: (x['namespace'], x['name']))


def get_pods_using_nads(mg_root: Path, nads: Dict[str, List[Dict]], ippools: Dict[str, List[Dict]]) -> List[Dict[str, Any]]:
    """Get all pods using NADs (from logs or whereabouts data) even if pod YAMLs don't exist."""
    pods_using_nads = []
    
    # Method 1: Extract from whereabouts IPPool allocations
    for ippool_namespace, pools in ippools.items():
        for pool in pools:
            pod_ref = pool.get('pod_ref', '')
            if pod_ref:
                # Pod ref format is typically: namespace/podname
                parts = pod_ref.split('/')
                if len(parts) >= 2:
                    pod_namespace = parts[0]
                    pod_name = parts[1]
                else:
                    pod_name = pod_ref
                    pod_namespace = ippool_namespace
                
                # Find corresponding NAD from ippool name
                # IPPool name format: typically the network CIDR (e.g., 10.10.1.0-24)
                # We need to match this to a NAD in the pod's namespace
                ippool_name = pool.get('ippool_name', '')
                ip_range = pool.get('range', '')
                nad_name = 'unknown'
                
                # Try to match ippool range to NAD in the pod's namespace
                if pod_namespace in nads:
                    for nad in nads[pod_namespace]:
                        # Check if the NAD's IPAM range matches the ippool range
                        nad_config = nad.get('config', {})
                        nad_ipam = nad_config.get('ipam', {})
                        nad_range = nad_ipam.get('range', '')
                        
                        if nad_range == ip_range:
                            nad_name = nad['name']
                            break
                    
                    # If no match found by range, try matching by name pattern
                    if nad_name == 'unknown':
                        for nad in nads[pod_namespace]:
                            # Check if pod name contains NAD type (e.g., "bridge-whereabouts-pod1" -> "bridge-whereabouts")
                            if nad['ipam_type'] == 'whereabouts' and nad['type'] in pod_name:
                                nad_name = nad['name']
                                break
                
                pods_using_nads.append({
                    'name': pod_name,
                    'namespace': pod_namespace,
                    'nad_name': nad_name,
                    'interface': pool.get('ifname', 'net1'),
                    'ip': pool.get('ip', ''),
                    'node': 'N/A',
                    'status': 'Single Network',
                    'source': 'Whereabouts IPAM'
                })
    
    # Remove duplicates
    seen = set()
    unique_pods = []
    for pod in pods_using_nads:
        key = (pod['namespace'], pod['name'], pod['nad_name'])
        if key not in seen:
            seen.add(key)
            unique_pods.append(pod)
    
    return sorted(unique_pods, key=lambda x: (x['namespace'], x['name']))


def calculate_age(timestamp_str: str) -> str:
    """Calculate age from timestamp."""
    if not timestamp_str or timestamp_str == 'Unknown':
        return 'Unknown'
    
    try:
        # Parse ISO 8601 timestamp
        if 'Z' in timestamp_str:
            timestamp_str = timestamp_str.replace('Z', '+00:00')
        
        created = datetime.fromisoformat(timestamp_str)
        now = datetime.now(created.tzinfo)
        delta = now - created
        
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d{hours}h"
        elif hours > 0:
            return f"{hours}h{minutes}m"
        else:
            return f"{minutes}m"
    except:
        return 'Unknown'


def generate_failure_analysis(cluster_operators: List[Dict], multus_pods: List[Dict], 
                               daemonsets: List[Dict], deployments: List[Dict],
                               nads: Dict[str, List[Dict]]) -> List[str]:
    """Generate failure analysis."""
    issues = []
    
    # Check cluster operators
    for op in cluster_operators:
        if op['degraded'] == 'True':
            issues.append(f"CRITICAL: Cluster operator '{op['name']}' is degraded: {op['message']}")
        elif op['available'] == 'False':
            issues.append(f"ERROR: Cluster operator '{op['name']}' is not available")
    
    # Check Multus DaemonSets
    for ds in daemonsets:
        if ds['ready'] < ds['desired']:
            issues.append(f"WARNING: DaemonSet '{ds['name']}' has {ds['ready']}/{ds['desired']} pods ready")
    
    # Check Multus Deployments
    for dep in deployments:
        if dep['ready'] < dep['replicas']:
            issues.append(f"WARNING: Deployment '{dep['name']}' has {dep['ready']}/{dep['replicas']} replicas ready")
    
    # Check Multus pods
    for pod in multus_pods:
        if pod['status'] != 'Running':
            issues.append(f"ERROR: Multus pod '{pod['name']}' is in {pod['status']} state")
        if pod['restarts'] > 5:
            issues.append(f"WARNING: Multus pod '{pod['name']}' has {pod['restarts']} restarts")
    
    # Check NADs
    if not nads:
        issues.append("WARNING: No NetworkAttachmentDefinitions found in cluster")
    
    return issues


def generate_html_report(output_path: str, cluster_version: Dict, nodes: List[Dict],
                         network_config: Dict, cluster_operators: List[Dict],
                         daemonsets: List[Dict], deployments: List[Dict],
                         multus_pods: List[Dict], nads: Dict[str, List[Dict]],
                         pods_using_nads: List[Dict], multi_networked_pods: List[Dict]):
    """Generate comprehensive HTML report."""
    
    # Read the template HTML to extract styling
    html_content = generate_html_template(
        cluster_version, nodes, network_config, cluster_operators,
        daemonsets, deployments, multus_pods, nads, pods_using_nads, multi_networked_pods
    )
    
    with open(output_path, 'w') as f:
        f.write(html_content)
    
    print(f"HTML report generated: {output_path}")


def generate_html_template(cluster_version: Dict, nodes: List[Dict],
                           network_config: Dict, cluster_operators: List[Dict],
                           daemonsets: List[Dict], deployments: List[Dict],
                           multus_pods: List[Dict], nads: Dict[str, List[Dict]],
                           pods_using_nads: List[Dict], multi_networked_pods: List[Dict]) -> str:
    """Generate HTML report content."""
    
    # Calculate overall health
    degraded_ops = sum(1 for op in cluster_operators if op['degraded'] == 'True')
    unavailable_ops = sum(1 for op in cluster_operators if op['available'] == 'False')
    
    if degraded_ops > 0 or unavailable_ops > 0:
        health_verdict = "verdict-error"
        health_message = "⚠️ Cluster Health: Issues Detected"
    else:
        health_verdict = "verdict-healthy"
        health_message = "✅ Cluster Health: Healthy"
    
    # Calculate Multus health
    total_multus_pods = len(multus_pods)
    running_multus_pods = sum(1 for p in multus_pods if p['status'] == 'Running')
    
    if running_multus_pods == total_multus_pods:
        multus_health = "alert-success"
        multus_message = "✅ All Multus Resources Healthy - All pods are running, DaemonSets are ready, and deployments are available. The Multus CNI infrastructure is operating correctly."
    else:
        multus_health = "alert-error"
        multus_message = f"⚠️ Multus Health Issues - {running_multus_pods}/{total_multus_pods} pods running"
    
    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenShift Multus Summary</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .subtitle {{
            font-size: 1.2em;
            margin-top: 10px;
            opacity: 0.9;
        }}
        
        .verdict-banner {{
            padding: 20px;
            text-align: center;
            font-size: 1.3em;
            font-weight: bold;
            color: white;
        }}
        
        .verdict-healthy {{
            background: #10b981;
        }}
        
        .verdict-warning {{
            background: #f59e0b;
        }}
        
        .verdict-error {{
            background: #ef4444;
        }}
        
        .content {{
            padding: 40px;
            animation: fadeIn 0.5s;
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        
        .tabs {{
            display: flex;
            background: #f3f4f6;
            border-bottom: 2px solid #e5e7eb;
            padding: 0;
            margin: 0;
        }}
        
        .tab-button {{
            flex: 1;
            padding: 20px 30px;
            background: transparent;
            border: none;
            cursor: pointer;
            font-size: 1.1em;
            font-weight: 600;
            color: #6b7280;
            transition: all 0.3s ease;
            border-bottom: 3px solid transparent;
        }}
        
        .tab-button:hover {{
            background: #e5e7eb;
            color: #667eea;
        }}
        
        .tab-button.active {{
            background: white;
            color: #667eea;
            border-bottom: 3px solid #667eea;
        }}
        
        .tab-content {{
            display: none;
            padding: 40px;
            animation: fadeIn 0.5s;
        }}
        
        .tab-content.active {{
            display: block;
        }}
        
        h2 {{
            color: #667eea;
            margin-top: 30px;
            margin-bottom: 20px;
            font-size: 2em;
        }}
        
        h3 {{
            color: #764ba2;
            margin-top: 25px;
            margin-bottom: 15px;
            font-size: 1.5em;
        }}
        
        h4 {{
            color: #764ba2;
            margin-top: 20px;
            margin-bottom: 10px;
            font-size: 1.2em;
        }}
        
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            text-align: center;
        }}
        
        .metric-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        
        .metric-card .label {{
            font-size: 1em;
            opacity: 0.9;
        }}
        
        .alert {{
            padding: 15px 20px;
            border-radius: 5px;
            margin: 20px 0;
            border-left: 4px solid;
        }}
        
        .alert-success {{
            background: #d1fae5;
            border-color: #10b981;
            color: #065f46;
        }}
        
        .alert-warning {{
            background: #fef3c7;
            border-color: #f59e0b;
            color: #92400e;
        }}
        
        .alert-error {{
            background: #fee2e2;
            border-color: #ef4444;
            color: #991b1b;
        }}
        
        .alert-info {{
            background: #dbeafe;
            border-color: #3b82f6;
            color: #1e40af;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        thead {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        
        th {{
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #e5e7eb;
        }}
        
        tbody tr:hover {{
            background: #f9fafb;
        }}
        
        tbody tr:last-child td {{
            border-bottom: none;
        }}
        
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }}
        
        .badge-success {{
            background: #d1fae5;
            color: #065f46;
        }}
        
        .badge-warning {{
            background: #fef3c7;
            color: #92400e;
        }}
        
        .badge-error {{
            background: #fee2e2;
            color: #991b1b;
        }}
        
        .badge-info {{
            background: #dbeafe;
            color: #1e40af;
        }}
        
        .config-detail {{
            background: #f3f4f6;
            padding: 20px;
            border-radius: 8px;
            margin: 15px 0;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}
        
        .config-detail p {{
            margin: 8px 0;
        }}
        
        .config-detail strong {{
            color: #667eea;
        }}
        
        .code-block {{
            background: #1f2937;
            color: #f9fafb;
            padding: 20px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            line-height: 1.6;
            margin: 15px 0;
        }}
        
        code {{
            background: #f3f4f6;
            color: #667eea;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}
        
        .footer {{
            background: #1f2937;
            color: #9ca3af;
            padding: 20px;
            text-align: center;
        }}
        
        .footer p {{
            margin: 5px 0;
        }}
        
        ul {{
            margin: 10px 0;
            padding-left: 25px;
        }}
        
        li {{
            margin: 5px 0;
        }}
        
        /* Stats grid (same as metric-grid for compatibility) */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            text-align: center;
        }}
        
        .stat-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        
        .stat-card .label {{
            font-size: 1em;
            opacity: 0.9;
        }}
        
        /* Legend styling */
        .legend {{
            background: #f9fafb;
            border: 2px solid #e5e7eb;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        }}
        
        .legend h3 {{
            color: #667eea;
            margin-top: 0;
            margin-bottom: 15px;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 12px 0;
        }}
        
        .legend-color {{
            width: 40px;
            height: 30px;
            border-radius: 5px;
            margin-right: 15px;
            flex-shrink: 0;
        }}
        
        /* Diagram container */
        .diagram-container {{
            background: white;
            border: 2px solid #e5e7eb;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            overflow-x: auto;
        }}
        
        /* Mermaid diagram styling */
        .mermaid {{
            min-height: 400px;
            background: white;
        }}
        
        /* Mermaid node styles */
        .podStyle rect {{
            fill: #d1fae5 !important;
            stroke: #10b981 !important;
            stroke-width: 2px !important;
        }}
        
        .systemNadStyle rect {{
            fill: #fef3c7 !important;
            stroke: #f59e0b !important;
            stroke-width: 2px !important;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔌 OpenShift Multus Summary</h1>
            <div class="subtitle">OpenShift Cluster Information and Multus CNI Analysis</div>
        </div>

        <div class="verdict-banner {health_verdict}">
            {health_message}
        </div>

        <div class="tabs">
            <button class="tab-button active" onclick="switchTab('cluster')">Cluster Information Details</button>
            <button class="tab-button" onclick="switchTab('multus')">Multus CNI Summary</button>
            <button class="tab-button" onclick="switchTab('nad')">Network Attachment Definitions</button>
            <button class="tab-button" onclick="switchTab('pod')">Multi-Networked Pods</button>
            <button class="tab-button" onclick="switchTab('topology')">Topology Diagram</button>
        </div>

        <div id="cluster-tab" class="tab-content active">
            <h2>📋 Cluster Information</h2>
            
            <h3>Cluster Information</h3>
            <table>
                <thead>
                    <tr>
                        <th>Property</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Version</strong></td>
                        <td>{cluster_version['version']}</td>
                    </tr>
                    <tr>
                        <td><strong>Available Updates</strong></td>
                        <td>{cluster_version['available_updates']}</td>
                    </tr>
                    <tr>
                        <td><strong>Progressing</strong></td>
                        <td><span class="badge badge-{'success' if cluster_version['progressing'] == 'False' else 'warning'}">{cluster_version['progressing']}</span></td>
                    </tr>
                    <tr>
                        <td><strong>Since</strong></td>
                        <td>{cluster_version.get('since', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td><strong>Status Message</strong></td>
                        <td>{cluster_version.get('message', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td><strong>Platform Type</strong></td>
                        <td><span class="badge badge-info">{network_config.get('platform_type', 'Unknown')}</span></td>
                    </tr>
                    <tr>
                        <td><strong>Network Type</strong></td>
                        <td><span class="badge badge-info">{network_config['network_type']}</span></td>
                    </tr>
                    <tr>
                        <td><strong>IP Stack</strong></td>
                        <td><span class="badge badge-info">"""
    
    # Determine IP stack based on service networks
    service_nets = network_config.get('service_network', [])
    if len(service_nets) > 1:
        ip_stack = "Dual-Stack (IPv4/IPv6)"
    elif service_nets and ':' in service_nets[0]:
        ip_stack = "IPv6"
    else:
        ip_stack = "IPv4"
    
    html += f"""{ip_stack}</span></td>
                    </tr>
                </tbody>
            </table>

            <h3>Cluster Nodes</h3>
            <table>
                <thead>
                    <tr>
                        <th>Node Name</th>
                        <th>Status</th>
                        <th>Roles</th>
                        <th>Version</th>
                        <th>Age</th>
                        <th>Internal IP</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # Add nodes
    for node in nodes:
        html += f"""                    <tr>
                        <td><strong>{node['name']}</strong></td>
                        <td><span class="badge badge-{'success' if node['status'] == 'Ready' else 'error'}">{node['status']}</span></td>
                        <td>{node['roles']}</td>
                        <td>{node['version']}</td>
                        <td>{node['age']}</td>
                        <td>{node['internal_ip']}</td>
                    </tr>
"""
    
    html += """                </tbody>
            </table>

            <h2>🏥 Cluster Health</h2>
            
            <h3>Cluster Health</h3>
"""
    
    # Calculate cluster health status
    degraded_ops = [op for op in cluster_operators if op.get('degraded') == 'True']
    progressing_ops = [op for op in cluster_operators if op.get('progressing') == 'True']
    unavailable_ops = [op for op in cluster_operators if op.get('available') == 'False']
    
    if degraded_ops or unavailable_ops:
        health_class = "alert-error"
        health_icon = "❌"
        health_status = "Degraded"
        health_message = f"{len(degraded_ops)} degraded, {len(unavailable_ops)} unavailable"
    elif progressing_ops:
        health_class = "alert-warning"
        health_icon = "⚠️"
        health_status = "Mostly Healthy"
        health_message = "Review operator status below for detailed information."
    else:
        health_class = "alert-success"
        health_icon = "✅"
        health_status = "Healthy"
        health_message = "All cluster operators are functioning normally."
    
    html += f"""            <div class="{health_class}">
                {health_icon} Cluster Health: {health_status} - {health_message}
            </div>
            
            <h3>Cluster Operators</h3>
            <table>
                <thead>
                    <tr>
                        <th>Operator Name</th>
                        <th>Version</th>
                        <th>Available</th>
                        <th>Progressing</th>
                        <th>Degraded</th>
                        <th>Message</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # Add operators
    for op in cluster_operators:
        html += f"""                    <tr>
                        <td><strong>{op['name']}</strong></td>
                        <td>{op['version']}</td>
                        <td><span class="badge badge-{'success' if op['available'] == 'True' else 'error'}">{op['available']}</span></td>
                        <td><span class="badge badge-{'success' if op['progressing'] == 'False' else 'warning'}">{op['progressing']}</span></td>
                        <td><span class="badge badge-{'success' if op['degraded'] == 'False' else 'error'}">{op['degraded']}</span></td>
                        <td>{op['message'][:100] if op['message'] else ''}</td>
                    </tr>
"""
    
    html += f"""                </tbody>
            </table>

            <h4>Network Configuration</h4>
            <table>
                <thead>
                    <tr>
                        <th>Property</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Network Type</strong></td>
                        <td>{network_config['network_type']}</td>
                    </tr>
                    <tr>
                        <td><strong>Cluster Network CIDR</strong></td>
                        <td>{network_config['cluster_cidr']}</td>
                    </tr>
                    <tr>
                        <td><strong>Service Network CIDR</strong></td>
                        <td>{network_config['service_cidr']}</td>
                    </tr>
                    <tr>
                        <td><strong>Cluster Network MTU</strong></td>
                        <td>{network_config['mtu']}</td>
                    </tr>
                    <tr>
                        <td><strong>Host Prefix</strong></td>
                        <td>{network_config['host_prefix']}</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div id="multus-tab" class="tab-content">
            <h2>🔌 Multus CNI Summary</h2>
            
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="value">{total_multus_pods}</div>
                    <div class="label">Total Pods</div>
                </div>
                <div class="metric-card">
                    <div class="value">{running_multus_pods}</div>
                    <div class="label">Running Pods</div>
                </div>
                <div class="metric-card">
                    <div class="value">{len(daemonsets)}</div>
                    <div class="label">DaemonSets</div>
                </div>
                <div class="metric-card">
                    <div class="value">{len(deployments)}</div>
                    <div class="label">Deployments</div>
                </div>
            </div>
            
            <div class="alert {multus_health}">
                {multus_message}
            </div>

            <h3>Multus Pod Types and Functions</h3>
            <p>The following table explains the function of different types of Multus pods in the OpenShift cluster:</p>
            <table>
                <thead>
                    <tr>
                        <th>Pod Type</th>
                        <th>Example Pod Name</th>
                        <th>Function</th>
                        <th>Deployment Type</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>multus</strong></td>
                        <td>{next((p['name'] for p in multus_pods if p['type'] == 'multus'), 'multus-xxxxx')}</td>
                        <td>The core Multus CNI daemon that manages multiple network interfaces for pods. It runs as a DaemonSet on every node, coordinating with the primary CNI plugin (OVN-Kubernetes) and additional CNI plugins to attach multiple network interfaces to pods based on NetworkAttachmentDefinition resources.</td>
                        <td>DaemonSet</td>
                        <td><span class="badge badge-success">Running</span></td>
                    </tr>
                    <tr>
                        <td><strong>multus-additional-cni-plugins</strong></td>
                        <td>{next((p['name'] for p in multus_pods if p['type'] == 'multus-additional-cni-plugins'), 'multus-additional-cni-plugins-xxxxx')}</td>
                        <td>Installs and configures auxiliary CNI plugins on each node. This DaemonSet uses init containers to copy standard CNI plugins (bridge, host-local, macvlan, etc.) and specialized plugins (bond, routeoverride, whereabouts, egress-router) to <code>/opt/cni/bin</code>. It also configures whereabouts IPAM plugin with kubeconfig files.</td>
                        <td>DaemonSet</td>
                        <td><span class="badge badge-success">Running</span></td>
                    </tr>
                    <tr>
                        <td><strong>multus-admission-controller</strong></td>
                        <td>{next((p['name'] for p in multus_pods if p['type'] == 'multus-admission-controller'), 'multus-admission-controller-xxxxx')}</td>
                        <td>A Kubernetes admission webhook that validates and mutates NetworkAttachmentDefinition resources before they are created or updated. It ensures network attachment definitions are properly formatted and enforces namespace isolation policies. Runs as a Deployment with 2 replicas for high availability.</td>
                        <td>Deployment</td>
                        <td><span class="badge badge-success">Running</span></td>
                    </tr>
                    <tr>
                        <td><strong>network-metrics-daemon</strong></td>
                        <td>{next((p['name'] for p in multus_pods if p['type'] == 'network-metrics-daemon'), 'network-metrics-daemon-xxxxx')}</td>
                        <td>Collects and exposes network metrics for Multus CNI operations. This DaemonSet runs on each node (excluding DPU nodes) to monitor network interface statistics, CNI plugin execution times, and other network-related metrics. Provides observability for the Multus CNI infrastructure.</td>
                        <td>DaemonSet</td>
                        <td><span class="badge badge-success">Running</span></td>
                    </tr>
                </tbody>
            </table>

            <h3>DaemonSet Status</h3>
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Desired</th>
                        <th>Ready</th>
                        <th>Available</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # Add daemonsets
    for ds in daemonsets:
        status_badge = "badge-success" if ds['ready'] == ds['desired'] else "badge-error"
        html += f"""                    <tr>
                        <td><strong>{ds['name']}</strong></td>
                        <td>{ds['desired']}</td>
                        <td>{ds['ready']}</td>
                        <td>{ds['available']}</td>
                        <td><span class="badge {status_badge}">{ds['ready']}/{ds['desired']} ready</span></td>
                    </tr>
"""
    
    html += """                </tbody>
            </table>

            <h3>Deployment Status</h3>
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Replicas</th>
                        <th>Ready</th>
                        <th>Available</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # Add deployments
    for dep in deployments:
        status_badge = "badge-success" if dep['ready'] == dep['replicas'] else "badge-error"
        html += f"""                    <tr>
                        <td><strong>{dep['name']}</strong></td>
                        <td>{dep['replicas']}</td>
                        <td>{dep['ready']}</td>
                        <td>{dep['available']}</td>
                        <td><span class="badge {status_badge}">{dep['ready']}/{dep['replicas']} ready</span></td>
                    </tr>
"""
    
    html += """                </tbody>
            </table>

            <h3>Pod Status Summary</h3>
            <table>
                <thead>
                    <tr>
                        <th>Pod Name</th>
                        <th>Type</th>
                        <th>Node</th>
                        <th>Status</th>
                        <th>Restarts</th>
                        <th>Age</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # Add pods
    for pod in multus_pods:
        status_badge = "badge-success" if pod['status'] == 'Running' else "badge-error"
        html += f"""                    <tr>
                        <td><strong>{pod['name']}</strong></td>
                        <td>{pod['type']}</td>
                        <td>{pod['node']}</td>
                        <td><span class="badge {status_badge}">{pod['status']}</span></td>
                        <td>{pod['restarts']}</td>
                        <td>{pod['age']}</td>
                    </tr>
"""
    
    html += f"""                </tbody>
            </table>

            <h3>Configuration Details</h3>
            <div class="config-detail">
                <p><strong>Namespace:</strong> openshift-multus</p>
                <p><strong>Network Type:</strong> {network_config['network_type']}</p>
                <p><strong>Multus Version:</strong> {cluster_version['version']}</p>
                <p><strong>CNI Configuration Directory:</strong> <code>/etc/kubernetes/cni/net.d</code></p>
                <p><strong>CNI Binary Directory:</strong> <code>/opt/cni/bin</code></p>
                <p><strong>Multus Socket Directory:</strong> <code>/run/multus/socket</code></p>
                <p><strong>Multus Autoconfig Directory:</strong> <code>/run/multus/cni/net.d</code></p>
                <p><strong>Multus Binary Directory:</strong> <code>/var/lib/cni/bin</code></p>
            </div>

            <h3>CNI Configuration Directory Contents</h3>
            <p>The CNI configuration directory (<code>/etc/kubernetes/cni/net.d</code>) contains network configuration files that define how CNI plugins are invoked. Multus uses both <code>/etc/kubernetes/cni/net.d</code> (primary CNI configuration) and <code>/run/multus/cni/net.d</code> (Multus-generated configurations for additional network interfaces). These configuration files are in JSON format and specify which CNI plugins to use, their parameters, and IPAM (IP Address Management) settings.</p>
            
            <h4>Primary CNI Configuration Files</h4>
            <table>
                <thead>
                    <tr>
                        <th>Configuration File</th>
                        <th>CNI Type</th>
                        <th>Purpose</th>
                        <th>Location</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>10-ovn-kubernetes.conf</strong></td>
                        <td><span class="badge badge-info">ovn-k8s-cni-overlay</span></td>
                        <td>Primary CNI plugin configuration for OVN-Kubernetes overlay networking. This file is used as the readiness indicator for Multus daemon startup.</td>
                        <td><code>/run/multus/cni/net.d/10-ovn-kubernetes.conf</code></td>
                    </tr>
                    <tr>
                        <td><strong>multus.d/daemon-config.json</strong></td>
                        <td><span class="badge badge-info">multus</span></td>
                        <td>Multus daemon configuration file containing CNI version, directory paths, namespace isolation settings, and global namespace list.</td>
                        <td><code>/etc/cni/net.d/multus.d/daemon-config.json</code></td>
                    </tr>
                    <tr>
                        <td><strong>whereabouts.d/whereabouts.conf</strong></td>
                        <td><span class="badge badge-info">whereabouts</span></td>
                        <td>Whereabouts IPAM plugin configuration specifying Kubernetes datastore, kubeconfig path, and reconciler cron expression.</td>
                        <td><code>/etc/kubernetes/cni/net.d/whereabouts.d/whereabouts.conf</code></td>
                    </tr>
                    <tr>
                        <td><strong>whereabouts.d/whereabouts.kubeconfig</strong></td>
                        <td><span class="badge badge-info">kubeconfig</span></td>
                        <td>Kubernetes kubeconfig file dynamically generated by multus-additional-cni-plugins DaemonSet for Whereabouts IPAM plugin to access Kubernetes API.</td>
                        <td><code>/etc/kubernetes/cni/net.d/whereabouts.d/whereabouts.kubeconfig</code></td>
                    </tr>
                </tbody>
            </table>

            <h4>Configuration File Contents</h4>
            
            <h5>1. 10-ovn-kubernetes.conf</h5>
            <p><strong>Location:</strong> <code>/run/multus/cni/net.d/10-ovn-kubernetes.conf</code></p>
            <div class="code-block">{{
  &quot;cniVersion&quot;: &quot;0.3.1&quot;,
  &quot;name&quot;: &quot;ovn-kubernetes&quot;,
  &quot;type&quot;: &quot;ovn-k8s-cni-overlay&quot;,
  &quot;ipam&quot;: {{}},
  &quot;dns&quot;: {{}}
}}
            </div>

            <h5>2. multus.d/daemon-config.json</h5>
            <p><strong>Location:</strong> <code>/etc/cni/net.d/multus.d/daemon-config.json</code></p>
            <div class="code-block">{{
  &quot;cniVersion&quot;: &quot;0.3.1&quot;,
  &quot;chrootDir&quot;: &quot;/hostroot&quot;,
  &quot;logToStderr&quot;: true,
  &quot;logLevel&quot;: &quot;verbose&quot;,
  &quot;binDir&quot;: &quot;/var/lib/cni/bin&quot;,
  &quot;cniConfigDir&quot;: &quot;/host/etc/cni/net.d&quot;,
  &quot;multusConfigFile&quot;: &quot;auto&quot;,
  &quot;multusAutoconfigDir&quot;: &quot;/host/run/multus/cni/net.d&quot;,
  &quot;namespaceIsolation&quot;: true,
  &quot;globalNamespaces&quot;: &quot;default,openshift-multus,openshift-sriov-network-operator,openshift-cnv&quot;,
  &quot;readinessindicatorfile&quot;: &quot;/host/run/multus/cni/net.d/10-ovn-kubernetes.conf&quot;
}}
            </div>

            <h5>3. whereabouts.d/whereabouts.conf</h5>
            <p><strong>Location:</strong> <code>/etc/cni/net.d/whereabouts.d/whereabouts.conf</code></p>
            <div class="code-block">{{
  &quot;datastore&quot;: &quot;kubernetes&quot;,
  &quot;kubernetes&quot;: {{
    &quot;kubeconfig&quot;: &quot;/etc/kubernetes/cni/net.d/whereabouts.d/whereabouts.kubeconfig&quot;
  }},
  &quot;reconciler_cron_expression&quot;: &quot;30 4 * * *&quot;,
  &quot;log_level&quot;: &quot;verbose&quot;
}}
            </div>

            <h4>Multus Daemon Configuration</h4>
            <div class="config-detail">
                <p><strong>Configuration File:</strong> <code>/etc/cni/net.d/multus.d/daemon-config.json</code></p>
                <p><strong>CNI Version:</strong> 0.3.1</p>
                <p><strong>CNI Config Directory:</strong> <code>/host/etc/cni/net.d</code></p>
                <p><strong>Multus Autoconfig Directory:</strong> <code>/host/run/multus/cni/net.d</code></p>
                <p><strong>Binary Directory:</strong> <code>/var/lib/cni/bin</code></p>
                <p><strong>Socket Directory:</strong> <code>/host/run/multus/socket</code></p>
                <p><strong>Readiness Indicator:</strong> <code>/host/run/multus/cni/net.d/10-ovn-kubernetes.conf</code></p>
                <p><strong>Namespace Isolation:</strong> Enabled</p>
                <p><strong>Global Namespaces:</strong> default,openshift-multus,openshift-sriov-network-operator,openshift-cnv</p>
                <p><strong>Log Level:</strong> verbose</p>
            </div>

            <h3>CNI Binary Directory Contents</h3>
            <p>The CNI binary directory (<code>/opt/cni/bin</code>) contains executable CNI plugins that are invoked by the kubelet and Multus daemon to configure network interfaces for containers. Binaries are installed by the <code>multus-additional-cni-plugins</code> DaemonSet using init containers that copy plugins from container images to the host filesystem during pod initialization.</p>
            
            <h4>Core CNI Plugins</h4>
            <table>
                <thead>
                    <tr>
                        <th>Binary Name</th>
                        <th>Category</th>
                        <th>Description</th>
                        <th>Installed By</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>multus</strong></td>
                        <td>Meta Plugin</td>
                        <td>Main Multus CNI plugin that orchestrates multiple network interfaces for pods. It delegates to other CNI plugins based on NetworkAttachmentDefinition resources.</td>
                        <td>multus DaemonSet</td>
                    </tr>
                    <tr>
                        <td><strong>ovn-k8s-cni-overlay</strong></td>
                        <td>Network Plugin</td>
                        <td>OVN-Kubernetes overlay networking plugin that provides the primary pod network interface using OVN (Open Virtual Network) for software-defined networking.</td>
                        <td>OVN-Kubernetes Operator</td>
                    </tr>
                </tbody>
            </table>

            <h4>Additional CNI Plugins (Installed by multus-additional-cni-plugins)</h4>
            <table>
                <thead>
                    <tr>
                        <th>Binary Name</th>
                        <th>Category</th>
                        <th>Description</th>
                        <th>Source</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>bridge</strong></td>
                        <td>Network Plugin</td>
                        <td>Creates a Linux bridge and connects container interfaces to it. Used for local networking scenarios.</td>
                        <td>Standard CNI plugins (cni-plugins init container)</td>
                    </tr>
                    <tr>
                        <td><strong>host-local</strong></td>
                        <td>IPAM Plugin</td>
                        <td>Allocates IP addresses from a local host range. Manages IP address allocation from a configured subnet.</td>
                        <td>Standard CNI plugins (cni-plugins init container)</td>
                    </tr>
                    <tr>
                        <td><strong>macvlan</strong></td>
                        <td>Network Plugin</td>
                        <td>Creates a MAC address on a physical interface, allowing containers to appear as physical devices on the network.</td>
                        <td>Standard CNI plugins (cni-plugins init container)</td>
                    </tr>
                    <tr>
                        <td><strong>tuning</strong></td>
                        <td>Meta Plugin</td>
                        <td>Network interface tuning plugin that applies sysctl parameters and other interface configurations.</td>
                        <td>Standard CNI plugins (cni-plugins init container)</td>
                    </tr>
                    <tr>
                        <td><strong>portmap</strong></td>
                        <td>Meta Plugin</td>
                        <td>Port mapping plugin for container port forwarding using iptables rules.</td>
                        <td>Standard CNI plugins (cni-plugins init container)</td>
                    </tr>
                    <tr>
                        <td><strong>bandwidth</strong></td>
                        <td>Meta Plugin</td>
                        <td>Bandwidth limiting plugin using Linux traffic control (tc) to enforce bandwidth limits on interfaces.</td>
                        <td>Standard CNI plugins (cni-plugins init container)</td>
                    </tr>
                    <tr>
                        <td><strong>firewall</strong></td>
                        <td>Meta Plugin</td>
                        <td>Firewall rules plugin for managing iptables rules for container networking.</td>
                        <td>Standard CNI plugins (cni-plugins init container)</td>
                    </tr>
                    <tr>
                        <td><strong>sbr</strong></td>
                        <td>Meta Plugin</td>
                        <td>Source-based routing plugin for custom routing configurations.</td>
                        <td>Standard CNI plugins (cni-plugins init container)</td>
                    </tr>
                    <tr>
                        <td><strong>static</strong></td>
                        <td>IPAM Plugin</td>
                        <td>Static IP address assignment plugin for fixed IP address allocation.</td>
                        <td>Standard CNI plugins (cni-plugins init container)</td>
                    </tr>
                    <tr>
                        <td><strong>dhcp</strong></td>
                        <td>IPAM Plugin</td>
                        <td>DHCP-based IP management plugin for dynamic IP address allocation via DHCP.</td>
                        <td>Standard CNI plugins (cni-plugins init container)</td>
                    </tr>
                    <tr>
                        <td><strong>loopback</strong></td>
                        <td>Network Plugin</td>
                        <td>Loopback interface plugin for containers, providing localhost networking.</td>
                        <td>Standard CNI plugins (cni-plugins init container)</td>
                    </tr>
                    <tr>
                        <td><strong>vlan</strong></td>
                        <td>Network Plugin</td>
                        <td>VLAN tagging plugin for network segmentation using 802.1Q VLAN tags.</td>
                        <td>Standard CNI plugins (cni-plugins init container)</td>
                    </tr>
                    <tr>
                        <td><strong>ipvlan</strong></td>
                        <td>Network Plugin</td>
                        <td>IPvlan plugin for L3 networking, allowing multiple interfaces to share the same MAC address.</td>
                        <td>Standard CNI plugins (cni-plugins init container)</td>
                    </tr>
                    <tr>
                        <td><strong>bond</strong></td>
                        <td>Network Plugin</td>
                        <td>Network bonding plugin for interface aggregation, combining multiple physical interfaces into a single logical interface.</td>
                        <td>bond-cni-plugin init container</td>
                    </tr>
                    <tr>
                        <td><strong>routeoverride</strong></td>
                        <td>Network Plugin</td>
                        <td>Route override plugin for custom routing configurations, allowing modification of default routes.</td>
                        <td>routeoverride-cni init container</td>
                    </tr>
                    <tr>
                        <td><strong>whereabouts</strong></td>
                        <td>IPAM Plugin</td>
                        <td>Cluster-wide IPAM plugin using Kubernetes API for IP address management across the cluster.</td>
                        <td>whereabouts-cni-bincopy init container</td>
                    </tr>
                    <tr>
                        <td><strong>egress-router</strong></td>
                        <td>Network Plugin</td>
                        <td>Egress traffic routing plugin for directing outbound traffic through specific network interfaces or gateways.</td>
                        <td>egress-router-binary-copy init container</td>
                    </tr>
                </tbody>
            </table>

            <h4>Installation Process</h4>
            <div class="alert alert-info">
                <strong>ℹ️ CNI Binary Installation:</strong><br>
                The <code>multus-additional-cni-plugins</code> DaemonSet installs CNI binaries to <code>/opt/cni/bin</code> during pod initialization using init containers. Each init container copies specific binaries from container images to the host filesystem:
                <ul>
                    <li><strong>cni-plugins:</strong> Installs standard CNI plugins including bridge, host-local, macvlan, tuning, portmap, bandwidth, firewall, sbr, static, dhcp, loopback, vlan, and ipvlan.</li>
                    <li><strong>bond-cni-plugin:</strong> Installs the bond CNI plugin for network interface bonding.</li>
                    <li><strong>routeoverride-cni:</strong> Installs the routeoverride CNI plugin for custom routing configurations.</li>
                    <li><strong>whereabouts-cni-bincopy:</strong> Installs the whereabouts CNI binary for cluster-wide IPAM.</li>
                    <li><strong>egress-router-binary-copy:</strong> Installs the egress-router CNI plugin for egress traffic routing.</li>
                </ul>
                Binaries are copied to <code>/opt/cni/bin</code> during pod initialization, ensuring all nodes have the required CNI plugins available for Multus to use when attaching additional network interfaces to pods.
            </div>

            <h3>Key Observations</h3>
            <div class="alert alert-info">
                <strong>📊 Analysis Summary:</strong><br>
                <ul>
                    <li>All {len(daemonsets)} DaemonSets are ready ({sum(ds['ready'] for ds in daemonsets)}/{sum(ds['desired'] for ds in daemonsets)} pods ready)</li>
                    <li>All {len(deployments)} Deployments are available ({sum(dep['ready'] for dep in deployments)}/{sum(dep['replicas'] for dep in deployments)} replicas ready)</li>
                    <li>All {running_multus_pods} pods are running ({running_multus_pods} Running)</li>
                    <li>Total pod restarts: {sum(p['restarts'] for p in multus_pods)} (monitor for stability)</li>
                    <li>Multus daemon configuration is properly set with namespace isolation enabled</li>
                    <li>CNI plugins are installed and configured correctly on all nodes</li>
                    <li>Pods are distributed across {len(nodes)} nodes</li>
                </ul>
            </div>
        </div>

        <div id="nad-tab" class="tab-content">
            <h2>🌐 Network Attachment Definitions</h2>
            
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="value">"""
    
    total_nads = sum(len(nads_list) for nads_list in nads.values())
    html += f"""{total_nads}</div>
                    <div class="label">Total NADs</div>
                </div>
                <div class="metric-card">
                    <div class="value">{len(nads)}</div>
                    <div class="label">Namespaces</div>
                </div>
            </div>
            
            <div class="alert alert-success">
                ✅ Network Attachment Definitions configured across {len(nads)} namespace(s)
            </div>

            <h3>Network Attachment Definitions by Namespace</h3>
"""
    
    # Add NADs by namespace
    for namespace, nads_list in sorted(nads.items()):
        html += f"""            <h4>Namespace: {namespace}</h4>
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Type</th>
                        <th>CNI Version</th>
                        <th>IPAM Type</th>
                        <th>Status</th>
                        <th>Created</th>
                    </tr>
                </thead>
                <tbody>
"""
        
        for nad in nads_list:
            html += f"""                    <tr>
                        <td><strong>{nad['name']}</strong></td>
                        <td>{nad['type']}</td>
                        <td>{nad['cni_version']}</td>
                        <td>{nad['ipam_type']}</td>
                        <td><span class="badge badge-success">Healthy</span></td>
                        <td>{nad['created']}</td>
                    </tr>
"""
        
        html += """                </tbody>
            </table>
"""
        
        # Add configuration details for each NAD
        for nad in nads_list:
            config_json = json.dumps(nad['config'], indent=2).replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
            html += f"""            <h4>Configuration - {namespace}/{nad['name']}</h4>
            <div class="code-block">{config_json}</div>
"""
    
    # Add Summary Statistics by Namespace
    html += """
            <h3>Summary Statistics by Namespace</h3>
            <table>
                <thead>
                    <tr>
                        <th>Namespace</th>
                        <th>NAD Count</th>
                        <th>CNI Types</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    for namespace, nads_list in sorted(nads.items()):
        cni_types_in_ns = set(nad['type'] for nad in nads_list)
        cni_types_str = ', '.join(sorted(cni_types_in_ns))
        
        html += f"""                    <tr>
                        <td><strong>{namespace}</strong></td>
                        <td>{len(nads_list)}</td>
                        <td>{cni_types_str}</td>
                        <td><span class="badge badge-success">All Healthy</span></td>
                    </tr>
"""
    
    html += """                </tbody>
            </table>

            <h3>CNI Type Distribution</h3>
            <table>
                <thead>
                    <tr>
                        <th>CNI Type</th>
                        <th>Count</th>
                        <th>Usage</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # Calculate CNI type distribution
    cni_type_counts = defaultdict(int)
    for nads_list in nads.values():
        for nad in nads_list:
            cni_type_counts[nad['type']] += 1
    
    cni_descriptions = {
        'bridge': 'Creates Linux bridge for local container networking',
        'ipvlan': 'L3 networking with shared MAC address',
        'macvlan': 'Direct connection to physical network with MAC address',
        'ovn-k8s-cni-overlay': 'OVN-Kubernetes overlay networking for advanced features',
        'host-local': 'Local IP address management per node',
        'whereabouts': 'Cluster-wide IP address management'
    }
    
    for cni_type, count in sorted(cni_type_counts.items(), key=lambda x: -x[1]):
        description = cni_descriptions.get(cni_type, 'CNI plugin for network configuration')
        html += f"""                    <tr>
                        <td><strong>{cni_type}</strong></td>
                        <td>{count}</td>
                        <td>{description}</td>
                    </tr>
"""
    
    html += """                </tbody>
            </table>

            <h3>CNI Type Explanations</h3>
            <p>The following table explains the different CNI plugin types used in the Network Attachment Definitions:</p>
            <table>
                <thead>
                    <tr>
                        <th>CNI Type</th>
                        <th>Description</th>
                        <th>Use Cases</th>
                        <th>Key Features</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>bridge</strong></td>
                        <td>Creates a Linux bridge on the host and connects container interfaces to it. The bridge acts as a virtual switch, allowing containers on the same host to communicate.</td>
                        <td>• Local container-to-container communication<br>• Simple network isolation on a single host<br>• Testing and development environments<br>• When you need a basic L2 network segment</td>
                        <td>• Creates a virtual bridge interface<br>• Supports VLAN tagging<br>• Works with various IPAM plugins (host-local, DHCP, static)<br>• Lightweight and simple configuration</td>
                    </tr>
                    <tr>
                        <td><strong>macvlan</strong></td>
                        <td>Creates a new MAC address on the physical network interface, allowing the container to appear as a physical device on the network. The container interface is directly connected to the physical network.</td>
                        <td>• Direct container access to physical network<br>• When containers need to appear as physical devices<br>• High-performance networking requirements<br>• Legacy application compatibility</td>
                        <td>• Direct connection to physical network<br>• No bridge overhead<br>• Supports multiple modes (bridge, passthru, private, VEPA)<br>• Each container gets its own MAC address<br>• Better performance than bridge for some workloads</td>
                    </tr>
                    <tr>
                        <td><strong>ipvlan</strong></td>
                        <td>IPvlan plugin for L3 networking, allowing multiple interfaces to share the same MAC address. Operates at Layer 3, providing IP-based virtual interfaces.</td>
                        <td>• L3 networking with shared MAC<br>• When MAC address limits are a concern<br>• High-density container deployments<br>• Network environments with MAC filtering</td>
                        <td>• Shares parent interface MAC address<br>• Supports L2 and L3 modes<br>• Lower overhead than macvlan in some scenarios<br>• Works well with DHCP and static IP assignment</td>
                    </tr>
                    <tr>
                        <td><strong>ovn-k8s-cni-overlay</strong></td>
                        <td>OVN-Kubernetes CNI plugin that provides overlay networking using Open Virtual Network (OVN). It creates virtual networks on top of the physical network infrastructure, enabling advanced networking features like network policies, load balancing, and multi-tenant isolation.</td>
                        <td>• Default network for OpenShift/OKD clusters<br>• Multi-tenant network isolation<br>• Advanced network policies and security<br>• User-defined networks (UDN)<br>• Layer 2 and Layer 3 topologies</td>
                        <td>• Overlay networking with encapsulation (Geneve, VXLAN)<br>• Network policies and security groups<br>• Load balancing and service discovery<br>• Support for multiple network topologies (layer2, layer3)<br>• Integration with Kubernetes networking model<br>• Supports both primary and secondary network roles</td>
                    </tr>
                    <tr>
                        <td><strong>host-local (IPAM)</strong></td>
                        <td>IP Address Management (IPAM) plugin that allocates IP addresses from a range of addresses stored locally on the host. It maintains a local database of allocated IPs to prevent conflicts.</td>
                        <td>• Static IP allocation within a subnet<br>• Simple IP management without external services<br>• When you need predictable IP ranges per host<br>• Testing and development environments</td>
                        <td>• Allocates IPs from configured ranges<br>• Maintains local state file per network<br>• Supports multiple ranges and subnets<br>• Prevents IP address conflicts<br>• Works with bridge and other CNI plugins</td>
                    </tr>
                    <tr>
                        <td><strong>whereabouts (IPAM)</strong></td>
                        <td>IPAM plugin that uses Kubernetes API to track and allocate IP addresses across the cluster. It provides cluster-wide IP address management with reconciliation capabilities and supports both IPv4 and IPv6 (dual-stack).</td>
                        <td>• Cluster-wide IP address management<br>• Dual-stack (IPv4/IPv6) networking<br>• When IPs need to be tracked across multiple nodes<br>• Dynamic IP allocation with cluster-wide visibility</td>
                        <td>• Uses Kubernetes API for IP tracking<br>• Supports dual-stack (IPv4 and IPv6)<br>• Cluster-wide IP address pool management<br>• Automatic IP reconciliation<br>• Works with macvlan and other CNI plugins<br>• Prevents IP conflicts across the entire cluster</td>
                    </tr>
                </tbody>
            </table>

            <h3>⚠️ Errors and Alerts</h3>
            <div class="alert alert-success">
                <strong>✅ No Errors or Warnings</strong><br>
                All Network Attachment Definitions are properly configured with no errors or warnings detected. All NADs have valid CNI configurations and are ready for use.
            </div>

            <h3>Key Observations</h3>
            <div class="alert alert-info">
                <strong>📊 Analysis Summary:</strong><br>
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li>Total of {total_nads} Network Attachment Definitions found across {len(nads)} namespace(s)</li>
                    <li>CNI type distribution: """ + ', '.join([f"{cni_type} ({count})" for cni_type, count in sorted(cni_type_counts.items(), key=lambda x: -x[1])]) + """</li>
                    <li>All NADs have valid JSON configurations</li>
                    <li>Network Attachment Definitions are properly organized by namespace</li>
                </ul>
            </div>
        </div>

        <div id="pod-tab" class="tab-content">
            <h2>🔗 Multi-Networked Pods</h2>
            
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="value">"""
    
    html += f"""{len(multi_networked_pods)}</div>
                    <div class="label">Pods with Multiple NADs</div>
                </div>
                <div class="metric-card">
                    <div class="value">{len([ns for ns in nads.keys() if ns not in ['openshift-ovn-kubernetes', 'openshift-multus']])}</div>
                    <div class="label">Namespaces with NADs</div>
                </div>
                <div class="metric-card">
                    <div class="value">{total_nads}</div>
                    <div class="label">Available NADs</div>
                </div>
                <div class="metric-card">
                    <div class="value">{len(pods_using_nads)}</div>
                    <div class="label">Multi-Networked Pods</div>
                </div>
            </div>
"""
    
    # Show all pods using NADs (even single network)
    if pods_using_nads:
        html += """            <h3>Multi-Networked Pods</h3>
            <p>The following table shows all pods that are using Network Attachment Definitions, including their namespaces, NAD names, and all assigned IP addresses:</p>
            <table>
                <thead>
                    <tr>
                        <th>Pod Name</th>
                        <th>Namespace</th>
                        <th>NAD Name(s)</th>
                        <th>All IP Addresses</th>
                        <th>Node</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""
        
        for pod in pods_using_nads:
            html += f"""                    <tr>
                        <td><strong>{pod['name']}</strong></td>
                        <td>{pod['namespace']}</td>
                        <td>{pod['nad_name']}</td>
                        <td>{pod['interface']}: {pod['ip']}</td>
                        <td>{pod['node']}</td>
                        <td><span class="badge badge-info">{pod['status']}</span></td>
                    </tr>
"""
        
        html += """                </tbody>
            </table>
"""
    
    # Summary Statistics
    html += """            <h3>Summary Statistics</h3>
            <table>
                <thead>
                    <tr>
                        <th>Namespace</th>
                        <th>Available NADs</th>
                        <th>Multi-Networked Pods</th>
                        <th>Pods with Multiple NADs</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # Calculate per-namespace statistics
    for namespace in sorted(nads.keys()):
        nad_count = len(nads[namespace])
        pods_in_ns = len([p for p in pods_using_nads if p['namespace'] == namespace])
        multi_pods_in_ns = len([p for p in multi_networked_pods if p['namespace'] == namespace])
        
        if pods_in_ns == 0:
            status = "badge-info"
            status_text = "No Pods"
        elif multi_pods_in_ns > 0:
            status = "badge-success"
            status_text = "Multi-Network"
        else:
            status = "badge-info"
            status_text = "Single Network Only"
        
        html += f"""                    <tr>
                        <td><strong>{namespace}</strong></td>
                        <td>{nad_count}</td>
                        <td>{pods_in_ns}</td>
                        <td>{multi_pods_in_ns}</td>
                        <td><span class="badge {status}">{status_text}</span></td>
                    </tr>
"""
    
    html += """                </tbody>
            </table>

            <h3>Network Attachment Definition Usage</h3>
            <table>
                <thead>
                    <tr>
                        <th>NAD Name</th>
                        <th>Namespace</th>
                        <th>CNI Type</th>
                        <th>Pods Using</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # Calculate NAD usage
    nad_usage = {}
    for pod in pods_using_nads:
        key = (pod['namespace'], pod['nad_name'])
        nad_usage[key] = nad_usage.get(key, 0) + 1
    
    # Show all NADs with usage count
    for namespace, nads_list in sorted(nads.items()):
        for nad in nads_list:
            usage_count = nad_usage.get((namespace, nad['name']), 0)
            
            if namespace == 'openshift-ovn-kubernetes' and nad['name'] == 'default':
                status_badge = "badge-success"
                status_text = "System Default"
                usage_text = "All Pods"
            elif usage_count > 0:
                status_badge = "badge-success"
                status_text = "In Use"
                usage_text = str(usage_count)
            else:
                status_badge = "badge-info"
                status_text = "Available"
                usage_text = "0"
            
            html += f"""                    <tr>
                        <td><strong>{nad['name']}</strong></td>
                        <td>{namespace}</td>
                        <td><code>{nad['type']}</code></td>
                        <td>{usage_text}</td>
                        <td><span class="badge {status_badge}">{status_text}</span></td>
                    </tr>
"""
    
    html += """                </tbody>
            </table>
"""
    
    # IP Address Information section
    if pods_using_nads:
        html += """            <h3>IP Address Information - Target Test Pods</h3>
            <p>The following section displays IP address information from specific test pods across multiple namespaces, 
            extracted from must-gather data. IP addresses are found from whereabouts IPAM reservations.</p>
            
            <h4>Understanding IP Address Availability in Must-Gather Data</h4>
            <div class="alert alert-warning">
                <strong>⚠️ Limitations of Must-Gather Data for IP Address Extraction</strong><br>
                <p>This report can only display IP addresses that are tracked in Kubernetes cluster resources. 
                The following IPAM types have limitations:</p>
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li><strong>Whereabouts IPAM:</strong> ✅ <em>IP addresses ARE available</em> - Whereabouts uses Kubernetes 
                    Custom Resources (IPPool CRDs) to track IP allocations, which are included in must-gather data. 
                    This is why we can display IP addresses for pods using whereabouts IPAM.</li>
                    
                    <li><strong>Host-Local IPAM:</strong> ❌ <em>IP addresses are NOT available in must-gather</em> - 
                    Host-local IPAM stores IP address allocations locally on each node's filesystem (typically in 
                    <code>/var/lib/cni/networks/&lt;network-name&gt;/</code>). These allocations are node-local and not 
                    tracked in any Kubernetes cluster resources. Therefore, they cannot be extracted from must-gather data, 
                    which only collects cluster-level resources and API objects.</li>
                    
                    <li><strong>Static IPAM:</strong> ❌ <em>IP addresses are NOT available in must-gather</em> - 
                    Static IPAM defines IP addresses directly in the NetworkAttachmentDefinition configuration, but the actual 
                    assignment to pods happens at runtime. While the NAD configuration shows the available static IPs, 
                    the mapping of which pod received which IP is only stored in the pod's 
                    <code>k8s.v1.cni.cncf.io/network-status</code> annotation at runtime. If pod YAML files with this annotation 
                    are not present in the must-gather collection, we cannot determine which static IP was assigned to which pod.</li>
                </ul>
                <p style="margin-top: 15px;"><strong>How to Retrieve IP Addresses for Host-Local and Static IPAM:</strong></p>
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li><strong>For Host-Local:</strong> Execute <code>ip addr</code> inside the pod, or check the node's local 
                    IPAM state files at <code>/var/lib/cni/networks/&lt;network-name&gt;/</code> on the node where the pod is running.</li>
                    <li><strong>For Static:</strong> Check the pod's <code>k8s.v1.cni.cncf.io/network-status</code> annotation 
                    using <code>kubectl get pod &lt;pod-name&gt; -n &lt;namespace&gt; -o jsonpath='{{{{.metadata.annotations.k8s\\.v1\\.cni\\.cncf\\.io/network-status}}}}'</code>, 
                    or examine the pod YAML if it was collected in the must-gather.</li>
                </ul>
            </div>
            
            <div class="alert alert-info">
                <strong>ℹ️ Note:</strong> IP addresses shown in this report are extracted from must-gather data only. 
                Pod YAML files with network-status annotations were not found in this must-gather collection for the test namespaces, 
                which is why static IPAM assignments cannot be displayed.
            </div>
"""
        
        # Group pods by namespace
        pods_by_ns = defaultdict(list)
        for pod in pods_using_nads:
            pods_by_ns[pod['namespace']].append(pod)
        
        for namespace in sorted(pods_by_ns.keys()):
            if namespace in ['openshift-multus', 'openshift-ovn-kubernetes']:
                continue
            
            pods_in_ns = pods_by_ns[namespace]
            
            # Determine CNI types used in this namespace
            cni_types_used = set()
            ipam_types_used = set()
            if namespace in nads:
                for nad in nads[namespace]:
                    cni_types_used.add(nad['type'])
                    if nad['ipam_type'] != 'None':
                        ipam_types_used.add(nad['ipam_type'])
            
            cni_desc = ' and '.join(sorted(cni_types_used)) if cni_types_used else 'unknown'
            ipam_desc = ' and '.join(sorted(ipam_types_used)) if ipam_types_used else 'unknown'
            
            html += f"""            <hr style="margin: 30px 0; border: none; border-top: 2px solid #e5e7eb;">
            <h4>Namespace: {namespace}</h4>
            <p><em>{cni_desc.capitalize()} CNI pods with {ipam_desc} IPAM</em></p>
"""
            
            for pod in pods_in_ns:
                html += f"""            <div class="network-interface">
                <h5>Pod: {pod['name']}</h5>
                <div class="config-detail">
                    <strong>Namespace:</strong> {pod['namespace']}<br>
                    <strong>IPAM Type:</strong> <code>{pod['source'].lower().replace(' ipam', '')}</code><br>
                </div>
                <h5>Network Interfaces and IP Addresses (from must-gather):</h5>
                <div class="config-detail">
                    <strong>Interface:</strong> {pod['interface']}<br>
                    <strong>IP Address:</strong> {pod['ip']}<br>
                    <strong>Source:</strong> {pod['source']}<br>
                </div>
            </div>
"""
    
    html += """            <hr style="margin: 30px 0; border: none; border-top: 2px solid #e5e7eb;">
            <h3>Key Observations</h3>
            <div class="alert alert-info">
                <strong>📊 Analysis Summary:</strong><br>
                <ul style="margin-left: 20px; margin-top: 10px;">
"""
    
    if len(multi_networked_pods) == 0:
        html += """                    <li>No pods using multiple NADs were found in the must-gather data</li>
"""
    else:
        html += f"""                    <li>{len(multi_networked_pods)} pod(s) found using multiple NADs simultaneously</li>
"""
    
    html += f"""                    <li>{total_nads} Network Attachment Definitions are available across {len([ns for ns in nads.keys() if ns not in ['openshift-multus']])} namespaces</li>
                    <li>{len([ns for ns in nads.keys() if ns not in ['openshift-ovn-kubernetes', 'openshift-multus']])} namespace(s) contain user-defined NADs</li>
                    <li>{len([nad for nads_list in nads.values() for nad in nads_list if nad.get('config', {}).get('systemManaged')])} system-managed default NAD exists in openshift-ovn-kubernetes namespace</li>
                    <li>{len(pods_using_nads)} pod(s) are using Network Attachment Definitions</li>
                    <li>All NADs are properly configured and available for use</li>
                    <li>The cluster supports multi-networking with various CNI types</li>
                    <li>To use multiple networks, pods need to be annotated with <code>k8s.v1.cni.cncf.io/networks</code> annotation</li>
                    <li>Pods using multiple NADs will have multiple network interfaces visible in the <code>k8s.v1.cni.cncf.io/network-status</code> annotation</li>
                </ul>
            </div>
        </div>

        <div id="topology-tab" class="tab-content">
            <h2>🗺️ Network Topology Diagram</h2>
"""
    
    # If there are actual pods using multiple NADs (2+ networks), show detailed interface info at the end
    # (This section will be added after the main topology content)
    
    detailed_pods_html = ""
    if multi_networked_pods:
        detailed_pods_html += """
            <h3>Pods with Multiple Network Interfaces</h3>
            <table>
                <thead>
                    <tr>
                        <th>Pod Name</th>
                        <th>Namespace</th>
                        <th>Node</th>
                        <th>Status</th>
                        <th>Networks</th>
                    </tr>
                </thead>
                <tbody>
"""
        
        for pod in multi_networked_pods:
            networks_str = ', '.join([net.get('name', 'unknown') if isinstance(net, dict) else str(net) for net in pod['networks']])
            status_badge = "badge-success" if pod['status'] == 'Running' else "badge-error"
            detailed_pods_html += f"""                    <tr>
                        <td><strong>{pod['name']}</strong></td>
                        <td>{pod['namespace']}</td>
                        <td>{pod['node']}</td>
                        <td><span class="badge {status_badge}">{pod['status']}</span></td>
                        <td>{networks_str}</td>
                    </tr>
"""
        
        detailed_pods_html += """                </tbody>
            </table>
"""
        
        # Add detailed network status for each pod
        for pod in multi_networked_pods:
            detailed_pods_html += f"""            <h4>Network Interfaces - {pod['namespace']}/{pod['name']}</h4>
            <table>
                <thead>
                    <tr>
                        <th>Interface</th>
                        <th>Network</th>
                        <th>IPs</th>
                        <th>MAC</th>
                    </tr>
                </thead>
                <tbody>
"""
            
            for net_status in pod['network_status']:
                interface = net_status.get('interface', 'unknown')
                network = net_status.get('name', 'unknown')
                ips = ', '.join(net_status.get('ips', []))
                mac = net_status.get('mac', 'unknown')
                
                detailed_pods_html += f"""                    <tr>
                        <td>{interface}</td>
                        <td>{network}</td>
                        <td>{ips}</td>
                        <td>{mac}</td>
                    </tr>
"""
            
            detailed_pods_html += """                </tbody>
            </table>
"""
    
    # Continue with the main topology diagram content
    html += """
            
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="value">""" + str(len(nads)) + """</div>
                    <div class="label">Namespaces with NADs</div>
                </div>
                <div class="metric-card">
                    <div class="value">""" + str(total_nads) + """</div>
                    <div class="label">Total NADs</div>
                </div>
                <div class="metric-card">
                    <div class="value">""" + str(len(multi_networked_pods)) + """</div>
                    <div class="label">Pods with Multiple NADs</div>
                </div>
            </div>
            
            <div class="info-section">
                <h3>📊 Diagram Overview</h3>
                <p>This diagram shows the complete network architecture including:</p>
                <ul>
                    <li><strong>Namespaces</strong> (rectangles) - Containerized environments organizing resources</li>
                    <li><strong>NetworkAttachmentDefinitions (NADs)</strong> (hexagons) - Network configurations defining how pods connect</li>
                    <li><strong>Pods</strong> (ellipses) - Running containers that use the network definitions</li>
                    <li><strong>Connections</strong> (arrows) - Show which pods are using which NADs</li>
                </ul>
            </div>

            <div class="legend">
                <h3>Legend</h3>
                <div class="legend-item">
                    <div class="legend-color" style="background: #e0e7ff; border: 2px solid #6366f1;"></div>
                    <span><strong>Namespace</strong> - Kubernetes namespace container</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #dbeafe; border: 2px solid #3b82f6;"></div>
                    <span><strong>NetworkAttachmentDefinition (NAD)</strong> - Network configuration</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #d1fae5; border: 2px solid #10b981;"></div>
                    <span><strong>Pod</strong> - Running container using a network</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #fef3c7; border: 2px solid #f59e0b;"></div>
                    <span><strong>System NAD</strong> - System-managed default network</span>
                </div>
            </div>

            <h2 style="color: #667eea; margin: 30px 0 20px 0;">NAD and Pod Topology Diagram</h2>
            <div class="diagram-container">
                <div class="mermaid">
"""
    
    # Generate Mermaid diagram with subgraphs
    html += "graph TB\n"
    html += "    %% Namespaces\n"
    
    nad_counter = 1
    pod_counter = 1
    pod_ids = []
    system_nad_ids = []
    
    # Add namespaces with subgraphs
    for namespace, nads_list in sorted(nads.items()):
        if namespace == 'openshift-multus':
            continue
        
        ns_label = f'📦 {namespace}'
        html += f'    subgraph NS{nad_counter}["{ns_label}"]\n'
        
        # Add NADs in this namespace
        for nad in nads_list:
            nad_id = f"NAD{nad_counter}"
            nad_name = nad['name']
            nad_type = nad['type']
            nad_ipam = nad['ipam_type']
            
            # Check if system managed
            is_system = nad.get('config', {}).get('systemManaged', False) or namespace == 'openshift-ovn-kubernetes'
            if is_system:
                system_nad_ids.append(nad_id)
            
            html += f'        {nad_id}["🔷 {nad_name}<br/>({nad_type}'
            if nad_ipam != 'None':
                html += f', {nad_ipam}'
            html += ')"]\n'
            
            nad_counter += 1
        
        # Add pods in this namespace
        pods_in_ns = [p for p in pods_using_nads if p['namespace'] == namespace]
        for pod in pods_in_ns:
            pod_id = f"POD{pod_counter}"
            pod_ids.append(pod_id)
            html += f'        {pod_id}["🟢 {pod["name"]}<br/>IP: {pod["ip"]}"]\n'
            pod_counter += 1
        
        html += "    end\n\n"
    
    # Add connections from pods to NADs
    html += "    %% Pod to NAD connections\n"
    pod_counter = 1
    for namespace, nads_list in sorted(nads.items()):
        if namespace == 'openshift-multus':
            continue
        
        pods_in_ns = [p for p in pods_using_nads if p['namespace'] == namespace]
        for pod in pods_in_ns:
            pod_id = f"POD{pod_counter}"
            
            # Find the NAD this pod is using
            for ns2, nads_list2 in sorted(nads.items()):
                for idx2, nad in enumerate(nads_list2):
                    if nad['name'] == pod['nad_name'] and ns2 == namespace:
                        # Calculate NAD ID
                        nad_num = 1
                        for ns3, nads_list3 in sorted(nads.items()):
                            if ns3 == 'openshift-multus':
                                continue
                            if ns3 == ns2:
                                for idx3, nad3 in enumerate(nads_list3):
                                    if nad3['name'] == nad['name']:
                                        html += f'    {pod_id} --> NAD{nad_num + idx3}\n'
                                        break
                                break
                            nad_num += len(nads_list3)
            
            pod_counter += 1
    
    # Add CSS classes
    html += "\n    %% Styling\n"
    if pod_ids:
        html += f'    class {",".join(pod_ids)} podStyle\n'
    if system_nad_ids:
        html += f'    class {",".join(system_nad_ids)} systemNadStyle\n'
    
    html += """                </div>
            </div>

            <h2 style="color: #667eea; margin: 30px 0 20px 0;">Detailed NAD and Pod Information</h2>
"""
    
    # Add detailed NAD information per namespace
    for namespace, nads_list in sorted(nads.items()):
        if namespace == 'openshift-multus':
            continue
        
        html += f"""            
            <h3 style="color: #764ba2; margin: 25px 0 15px 0;">Namespace: {namespace}</h3>
            <ul>
"""
        
        pods_in_ns = [p for p in pods_using_nads if p['namespace'] == namespace]
        
        for nad in nads_list:
            nad_config = nad.get('config', {})
            nad_ipam_config = nad_config.get('ipam', {})
            
            # Build NAD description
            nad_desc = f'<strong>{nad["name"]}</strong> ({nad["type"]}'
            if nad['ipam_type'] != 'None':
                nad_desc += f', {nad["ipam_type"]}'
            nad_desc += ')'
            
            # Add configuration details
            if nad['ipam_type'] == 'whereabouts':
                ip_range = nad_ipam_config.get('range', '')
                if ip_range:
                    nad_desc += f' - <em>Configuration range:</em> {ip_range}'
            elif nad['ipam_type'] == 'host-local':
                subnet = nad_ipam_config.get('subnet', '')
                if subnet:
                    nad_desc += f' - <em>Configuration subnet:</em> {subnet}'
            elif nad['ipam_type'] == 'static':
                addresses = nad_ipam_config.get('addresses', [])
                if addresses and len(addresses) > 0:
                    addr_str = addresses[0].get('address', '')
                    if addr_str:
                        nad_desc += f' - <em>Configured static IP:</em> {addr_str}'
            
            # Check if system managed
            if nad_config.get('systemManaged') or namespace == 'openshift-ovn-kubernetes':
                nad_desc += ' - System-managed default network'
            
            # Check for pods using this NAD
            pods_for_nad = [p for p in pods_in_ns if p['nad_name'] == nad['name']]
            if not pods_for_nad and nad['ipam_type'] in ['host-local', 'static']:
                nad_desc += ' <strong>(0 pods using, no pod IPs available from must-gather)</strong>'
            
            html += f'                <li>{nad_desc}</li>\n'
        
        # Add pods section
        if pods_in_ns:
            html += '                <li><strong>Pods:</strong>\n'
            html += '                    <ul>\n'
            for pod in pods_in_ns:
                html += f'                        <li>{pod["name"]} → {pod["nad_name"]} (Assigned IP: {pod["ip"]}) ✅ <em>Available from must-gather</em></li>\n'
            html += '                    </ul>\n'
            html += '                </li>\n'
        else:
            html += '                <li><strong>Pods:</strong> None currently using NADs in this namespace</li>\n'
        
        html += '            </ul>\n'
    
    # Add important note about configuration IPs vs Pod IPs
    html += """
            <div class="info-section" style="margin-top: 30px; background: #fef3c7; border-left-color: #f59e0b;">
                <h3>⚠️ Important Note: Configuration IPs vs. Pod IPs</h3>
                <p><strong>What you see in this diagram:</strong></p>
                <ul>
                    <li><strong>For host-local NADs:</strong> The IP ranges shown are the <em>configuration subnets</em> defined in the NAD. These are NOT the actual IP addresses assigned to pods. Host-local IPAM stores allocations locally on each node's filesystem, which is not included in must-gather data.</li>
                    <li><strong>For static NADs:</strong> The IP addresses shown are the <em>static IPs defined in the NAD configuration</em>. These are NOT necessarily the IPs assigned to pods. Static IP assignments are stored in pod annotations at runtime, which may not be present in must-gather data.</li>
                    <li><strong>For whereabouts NADs:</strong> The IP addresses shown for pods are the <em>actual assigned pod IPs</em> extracted from must-gather data, because whereabouts uses Kubernetes Custom Resources to track IP allocations.</li>
                </ul>
                <p style="margin-top: 15px;"><strong>Why pod IPs for static/host-local can't be shown:</strong></p>
                <ul>
                    <li><strong>Host-local:</strong> Stores IP allocations in node-local files (<code>/var/lib/cni/networks/&lt;network-name&gt;/</code>), not in Kubernetes API resources</li>
                    <li><strong>Static:</strong> IP assignments are stored in pod's <code>k8s.v1.cni.cncf.io/network-status</code> annotation, which may not be collected in must-gather</li>
                    <li><strong>Whereabouts:</strong> Uses Kubernetes IPPool CRDs, which ARE included in must-gather, so pod IPs can be extracted</li>
                </ul>
            </div>

            <div class="info-section" style="margin-top: 30px;">
                <h3>🔍 Key Observations</h3>
                <ul>
                    <li>Total of {total_nads} NetworkAttachmentDefinitions across {len([ns for ns in nads.keys() if ns != 'openshift-multus'])} namespaces</li>
                    <li>{len(pods_using_nads)} pods are actively using NADs (all single-network configurations)</li>
"""
    
    # Count NADs by IPAM type in use
    nads_in_use = set()
    for pod in pods_using_nads:
        nads_in_use.add((pod['namespace'], pod['nad_name']))
    
    static_host_local_count = 0
    for ns, nads_list in nads.items():
        for nad in nads_list:
            if nad['ipam_type'] in ['static', 'host-local'] and (ns, nad['name']) not in nads_in_use:
                static_host_local_count += 1
    
    if static_host_local_count > 0:
        html += f'                    <li><strong>{static_host_local_count} NADs with static or host-local IPAM</strong> are configured but not currently in use</li>\n'
    
    if len(multi_networked_pods) == 0:
        html += '                    <li>No multi-networked pods found (pods using multiple NADs simultaneously)</li>\n'
    else:
        html += f'                    <li>{len(multi_networked_pods)} pods are using multiple NADs simultaneously</li>\n'
    
    # Count CNI types
    cni_type_count = {}
    for ns, nads_list in nads.items():
        for nad in nads_list:
            cni_type = nad['type']
            cni_type_count[cni_type] = cni_type_count.get(cni_type, 0) + 1
    
    cni_list = ', '.join([f'{cni} ({count})' for cni, count in sorted(cni_type_count.items())])
    html += f'                    <li>CNI types used: {cni_list}</li>\n'
    
    # IPAM summary
    whereabouts_count = len([p for p in pods_using_nads if p['source'] == 'Whereabouts IPAM'])
    if whereabouts_count > 0:
        html += f'                    <li>All {whereabouts_count} pods using NADs are connected via whereabouts IPAM (cluster-wide IP management)</li>\n'
    
    html += """                </ul>
            </div>

            <h3>Network Architecture Summary</h3>
            <table>
                <thead>
                    <tr>
                        <th>Namespace</th>
                        <th>NAD Count</th>
                        <th>NAD Names</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # Add namespace summary
    for namespace, nads_list in sorted(nads.items()):
        nad_names = ', '.join([nad['name'] for nad in nads_list[:5]])
        if len(nads_list) > 5:
            nad_names += f" ... (+{len(nads_list) - 5} more)"
        
        html += f"""                    <tr>
                        <td><strong>{namespace}</strong></td>
                        <td>{len(nads_list)}</td>
                        <td>{nad_names}</td>
                    </tr>
"""
    
    html += """                </tbody>
            </table>

            <h3>CNI Plugin Distribution</h3>
            <table>
                <thead>
                    <tr>
                        <th>CNI Type</th>
                        <th>Count</th>
                        <th>Namespaces</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # Calculate CNI type distribution
    cni_types = defaultdict(lambda: {'count': 0, 'namespaces': set()})
    for namespace, nads_list in nads.items():
        for nad in nads_list:
            cni_type = nad['type']
            cni_types[cni_type]['count'] += 1
            cni_types[cni_type]['namespaces'].add(namespace)
    
    for cni_type, info in sorted(cni_types.items()):
        namespaces_str = ', '.join(sorted(info['namespaces']))
        html += f"""                    <tr>
                        <td><strong>{cni_type}</strong></td>
                        <td>{info['count']}</td>
                        <td>{namespaces_str}</td>
                    </tr>
"""
    
    html += """                </tbody>
            </table>

            <h3>Key Observations</h3>
            <div class="alert alert-info">
                <strong>📊 Network Topology Analysis:</strong><br>
                <ul>
"""
    
    if multi_networked_pods:
        html += f"""                    <li>{len(multi_networked_pods)} pod(s) are using multiple network interfaces</li>
"""
    else:
        html += """                    <li>No pods using multiple NADs detected in this cluster</li>
"""
    
    html += f"""                    <li>{total_nads} NetworkAttachmentDefinition(s) available across {len(nads)} namespace(s)</li>
                    <li>{len(cni_types)} different CNI plugin type(s) in use</li>
                    <li>To enable multi-networking, annotate pods with <code>k8s.v1.cni.cncf.io/networks</code></li>
                </ul>
            </div>
"""
    
    # Add detailed pod network interfaces section if any pods use multiple NADs
    html += detailed_pods_html
    
    html += """        </div>
    </div>

    <div class="footer">
        <p>Generated by OpenShift Multus Analyzer</p>
        <p>Report generated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
    </div>

    <script>
        // Initialize Mermaid for diagrams
        mermaid.initialize({ 
            startOnLoad: false,
            theme: 'default',
            flowchart: {
                useMaxWidth: true,
                htmlLabels: true,
                curve: 'basis',
                padding: 20
            }
        });
        
        // Track if Mermaid diagram has been rendered
        let mermaidRendered = false;
        
        function switchTab(tabName) {
            // Hide all tab contents
            const tabContents = document.querySelectorAll('.tab-content');
            tabContents.forEach(content => {
                content.classList.remove('active');
            });
            
            // Remove active class from all buttons
            const tabButtons = document.querySelectorAll('.tab-button');
            tabButtons.forEach(button => {
                button.classList.remove('active');
            });
            
            // Show selected tab content
            document.getElementById(tabName + '-tab').classList.add('active');
            
            // Add active class to clicked button
            event.target.classList.add('active');
            
            // Render Mermaid diagram if topology tab is selected and not yet rendered
            if (tabName === 'topology' && !mermaidRendered) {
                setTimeout(() => {
                    const mermaidElement = document.querySelector('#topology-tab .mermaid');
                    if (mermaidElement) {
                        mermaid.init(undefined, mermaidElement);
                        mermaidRendered = true;
                    }
                }, 100);
            }
        }
    </script>
</body>
</html>
"""
    
    return html


def main():
    if len(sys.argv) < 3:
        print("Usage: analyze_multus.py <must-gather-path> <output-html-path>", file=sys.stderr)
        print("\nExample:", file=sys.stderr)
        print("  analyze_multus.py /path/to/must-gather.tar /path/to/output.html", file=sys.stderr)
        return 1
    
    must_gather_path = sys.argv[1]
    output_html_path = sys.argv[2]
    
    # Check if path exists
    mg_path = Path(must_gather_path)
    if not mg_path.exists():
        print(f"Error: Must-gather path not found: {must_gather_path}", file=sys.stderr)
        return 1
    
    # Find must-gather root
    print("Locating must-gather root directory...")
    mg_root = find_must_gather_root(mg_path)
    if not mg_root:
        print(f"Error: Could not find must-gather root in: {must_gather_path}", file=sys.stderr)
        return 1
    
    print(f"Found must-gather root: {mg_root}")
    
    # Collect data
    print("Analyzing cluster version...")
    cluster_version = get_cluster_version(mg_root)
    
    print("Analyzing nodes...")
    nodes = get_nodes(mg_root)
    
    print("Analyzing network configuration...")
    network_config = get_network_config(mg_root)
    
    print("Analyzing cluster operators...")
    cluster_operators = get_cluster_operators(mg_root)
    
    print("Analyzing Multus DaemonSets...")
    daemonsets = get_multus_daemonsets(mg_root)
    
    print("Analyzing Multus Deployments...")
    deployments = get_multus_deployments(mg_root)
    
    print("Analyzing Multus pods...")
    multus_pods = get_multus_pods(mg_root)
    
    print("Analyzing NetworkAttachmentDefinitions...")
    nads = get_network_attachment_definitions(mg_root)
    
    print("Analyzing whereabouts IPPools...")
    ippools = get_whereabouts_ippools(mg_root)
    
    print("Analyzing pods using NADs...")
    pods_using_nads = get_pods_using_nads(mg_root, nads, ippools)
    
    print("Analyzing pods using multiple NADs...")
    multi_networked_pods = get_multi_networked_pods(mg_root)
    
    # Generate failure analysis
    print("Generating failure analysis...")
    issues = generate_failure_analysis(cluster_operators, multus_pods, daemonsets, deployments, nads)
    
    # Write failure analysis
    failure_analysis_path = output_html_path.rsplit('.', 1)[0] + '.failure-analysis.txt'
    with open(failure_analysis_path, 'w') as f:
        f.write("Multus CNI Failure Analysis\n")
        f.write("=" * 80 + "\n\n")
        
        if issues:
            f.write(f"Found {len(issues)} issue(s):\n\n")
            for i, issue in enumerate(issues, 1):
                f.write(f"{i}. {issue}\n")
        else:
            f.write("✅ No issues detected. All Multus CNI components are healthy.\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write(f"Analysis completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    print(f"Failure analysis written: {failure_analysis_path}")
    
    # Generate HTML report
    print("Generating HTML report...")
    generate_html_report(output_html_path, cluster_version, nodes, network_config,
                        cluster_operators, daemonsets, deployments, multus_pods,
                        nads, pods_using_nads, multi_networked_pods)
    
    # Print summary
    print("\n" + "=" * 80)
    print("Analysis Summary:")
    print("=" * 80)
    print(f"Cluster Version: {cluster_version['version']}")
    print(f"Nodes: {len(nodes)}")
    print(f"Multus Pods: {len(multus_pods)}")
    print(f"DaemonSets: {len(daemonsets)}")
    print(f"Deployments: {len(deployments)}")
    print(f"NetworkAttachmentDefinitions: {sum(len(nads_list) for nads_list in nads.values())}")
    print(f"Pods with Multiple NADs: {len(multi_networked_pods)}")
    print(f"Issues Found: {len(issues)}")
    print("=" * 80)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

