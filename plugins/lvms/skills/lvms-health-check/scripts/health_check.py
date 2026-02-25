#!/usr/bin/env python3
"""
LVMS Health Check Script

Lightweight health monitoring and capacity tracking for LVMS clusters.
Focuses on real-time live cluster monitoring.

Usage:
    python3 health_check.py [--format json|table] [--threshold-warning <percentage>] [--namespace <namespace>]

Arguments:
    --format: Output format (table|json)
    --threshold-warning: Warning threshold percentage for capacity (default: 80)
    --namespace: LVMS namespace (default: openshift-lvm-storage)
"""

import os
import sys
import json
import re
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


class HealthStatus:
    """Health status constants"""
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


def print_success(message: str):
    """Print success message with checkmark"""
    print(f"{Colors.GREEN}✓{Colors.END} {message}")


def print_warning(message: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠{Colors.END}  {message}")


def print_error(message: str):
    """Print error message"""
    print(f"{Colors.RED}❌{Colors.END} {message}")


def print_info(message: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ{Colors.END}  {message}")


class LVMSHealthChecker:
    """Main health checker class for LVMS"""

    def __init__(self, args):
        self.args = args
        self.output_format = args.format
        self.threshold_warning = args.threshold_warning
        self.custom_namespace = getattr(args, 'namespace', None)

        # LVMS namespace: default to openshift-lvm-storage or use custom namespace
        self.lvms_namespace = self.custom_namespace if self.custom_namespace else "openshift-lvm-storage"

        # Health data
        self.health_data = {
            'timestamp': None,
            'overall_status': HealthStatus.HEALTHY,
            'health_score': 100,
            'lvmcluster': {},
            'capacity': {},
            'volume_groups': [],
            'pvcs': {},
            'operator': {},
            'storage_classes': {},
            'csi_driver': {},
            'alerts': [],
            'recommendations': []
        }

        # Issue tracking
        self.issues = {
            'critical': [],
            'warning': [],
            'info': []
        }

    def validate_prerequisites(self) -> bool:
        """Validate prerequisites for live cluster mode"""
        # Check oc CLI
        try:
            result = subprocess.run(['oc', 'whoami'],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print_error("No active cluster connection")
                print_info("Please login: oc login <cluster-url>")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print_error("oc CLI not found or not responding")
            return False

        print_success(f"Connected to cluster")

        # Validate LVMS namespace exists
        try:
            result = subprocess.run(['oc', 'get', 'namespace', self.lvms_namespace],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                if self.custom_namespace:
                    print_success(f"Using custom LVMS namespace: {self.lvms_namespace}")
                else:
                    print_success(f"Using default LVMS namespace: {self.lvms_namespace}")
            else:
                print_error(f"LVMS namespace '{self.lvms_namespace}' not found")
                if not self.custom_namespace:
                    print_info("Try using --namespace <custom-namespace> if LVMS is in a different namespace")
                return False
        except subprocess.TimeoutExpired:
            print_error(f"Timeout checking namespace: {self.lvms_namespace}")
            return False

        # Check basic permissions
        permissions_ok = True
        for resource in ['lvmcluster', 'pvc', 'pods']:
            try:
                if resource == 'pvc':
                    cmd = ['oc', 'auth', 'can-i', 'get', resource, '--all-namespaces']
                else:
                    cmd = ['oc', 'auth', 'can-i', 'get', resource, '-n', self.lvms_namespace]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    print_warning(f"Limited permissions for {resource}")
                    permissions_ok = False
            except subprocess.TimeoutExpired:
                print_warning(f"Permission check timeout for {resource}")
                permissions_ok = False

        if permissions_ok:
            print_success("Required permissions verified")
        else:
            print_warning("Some permissions missing. Results may be incomplete.")

        return True

    def collect_health_data(self):
        """Collect health data from live cluster"""
        print_info("Collecting health data from live cluster...")

        # Collect LVMCluster status
        self._collect_lvmcluster_status()

        # Collect capacity data
        self._collect_vg_capacity()

        # Collect PVC data
        self._collect_pvc_data()

        # Collect operator health
        self._collect_operator_health()

        # Collect storage class data
        self._collect_storage_class_data()

        # Collect CSI driver data
        self._collect_csi_driver_data()

    def _collect_lvmcluster_status(self):
        """Collect LVMCluster resource status"""
        try:
            result = subprocess.run([
                'oc', 'get', 'lvmcluster', '-n', self.lvms_namespace, '-o', 'json'
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                clusters = data.get('items', [])

                total_clusters = len(clusters)
                ready_clusters = sum(1 for c in clusters if c.get('status', {}).get('ready', False))

                self.health_data['lvmcluster'] = {
                    'total': total_clusters,
                    'ready': ready_clusters,
                    'clusters': clusters
                }

                print_success(f"Collected {total_clusters} LVMCluster(s), {ready_clusters} ready")

                # Check for critical issues
                if ready_clusters < total_clusters:
                    self.issues['critical'].append(f"{total_clusters - ready_clusters} LVMCluster(s) not ready")

            else:
                print_warning("Failed to collect LVMCluster data")

        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            print_error(f"Error collecting LVMCluster status: {e}")

    def _collect_vg_capacity(self):
        """Collect volume group capacity data"""
        try:
            result = subprocess.run([
                'oc', 'get', 'lvmvolumegroupnodestatus', '-n', self.lvms_namespace, '-o', 'json'
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                vg_data = data.get('items', [])

                capacity_info = []
                total_capacity = 0
                total_used = 0

                for item in vg_data:
                    node_name = item.get('metadata', {}).get('name', 'unknown')
                    node_status_list = item.get('spec', {}).get('nodeStatus', [])

                    for node_status in node_status_list:
                        vg_name = node_status.get('name', 'unknown')
                        vg_status = node_status.get('status', 'Unknown')
                        devices = node_status.get('devices', [])

                        # Since lvmvolumegroupnodestatus doesn't contain capacity info,
                        # we'll report basic VG status and device info without capacity details
                        size_bytes = 0
                        used_bytes = 0
                        available_bytes = 0
                        usage_percent = 0

                        # Determine status based on VG readiness
                        status = "OK" if vg_status == "Ready" else "CRITICAL"

                        capacity_data = {
                            'node': node_name,
                            'vg_name': vg_name,
                            'vg_status': vg_status,
                            'devices': devices,
                            'device_count': len(devices),
                            'size_bytes': size_bytes,
                            'used_bytes': used_bytes,
                            'available_bytes': available_bytes,
                            'usage_percent': usage_percent,
                            'status': status,
                            'capacity_available': False  # Mark that we don't have capacity data
                        }

                        capacity_info.append(capacity_data)
                        total_capacity += size_bytes
                        total_used += used_bytes

                        # Track issues
                        if status == "CRITICAL":
                            if vg_status != "Ready":
                                self.issues['critical'].append(
                                    f"Volume group {vg_name} on {node_name} is not ready (status: {vg_status})"
                                )
                            else:
                                self.issues['critical'].append(
                                    f"Volume group {vg_name} on {node_name} at {usage_percent}% capacity (critical)"
                                )
                        elif status == "WARNING":
                            self.issues['warning'].append(
                                f"Volume group {vg_name} on {node_name} at {usage_percent}% capacity"
                            )

                overall_usage = 0
                if total_capacity > 0:
                    overall_usage = int((total_used * 100) / total_capacity)

                self.health_data['capacity'] = {
                    'total_bytes': total_capacity,
                    'used_bytes': total_used,
                    'available_bytes': total_capacity - total_used,
                    'usage_percentage': overall_usage
                }

                self.health_data['volume_groups'] = capacity_info

                print_success(f"Collected volume group data from {len(vg_data)} node(s)")

            else:
                print_warning("Failed to collect volume group capacity data")

        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            print_error(f"Error collecting VG capacity: {e}")

    def _collect_pvc_data(self):
        """Collect PVC data for LVMS storage classes"""
        try:
            result = subprocess.run([
                'oc', 'get', 'pvc', '-A', '-o', 'json'
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                all_pvcs = data.get('items', [])

                # Filter for LVMS storage classes
                lvms_pvcs = [
                    pvc for pvc in all_pvcs
                    if pvc.get('spec', {}).get('storageClassName', '').startswith('lvms-')
                ]

                # Count by status
                status_counts = defaultdict(int)
                for pvc in lvms_pvcs:
                    phase = pvc.get('status', {}).get('phase', 'Unknown')
                    status_counts[phase] += 1

                total_pvcs = len(lvms_pvcs)
                bound_pvcs = status_counts.get('Bound', 0)
                pending_pvcs = status_counts.get('Pending', 0)

                self.health_data['pvcs'] = {
                    'total': total_pvcs,
                    'bound': bound_pvcs,
                    'pending': pending_pvcs,
                    'failed': status_counts.get('Failed', 0),
                    'bind_rate': round((bound_pvcs / total_pvcs * 100), 1) if total_pvcs > 0 else 0
                }

                print_success(f"Found {total_pvcs} LVMS PVCs: {bound_pvcs} bound, {pending_pvcs} pending")

                # Check for issues
                if pending_pvcs > 0:
                    if pending_pvcs > total_pvcs * 0.05:  # More than 5% pending
                        self.issues['critical'].append(f"{pending_pvcs} PVCs stuck pending")
                    else:
                        self.issues['warning'].append(f"{pending_pvcs} PVCs pending")

            else:
                print_warning("Failed to collect PVC data")

        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            print_error(f"Error collecting PVC data: {e}")

    def _collect_operator_health(self):
        """Collect LVMS operator health data"""
        try:
            result = subprocess.run([
                'oc', 'get', 'pods', '-n', self.lvms_namespace, '-o', 'json'
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                pods = data.get('items', [])

                total_pods = len(pods)
                running_pods = sum(1 for p in pods if p.get('status', {}).get('phase') == 'Running')

                # Check for deployments and daemonsets
                deploy_result = subprocess.run([
                    'oc', 'get', 'deployments', '-n', self.lvms_namespace, '-o', 'json'
                ], capture_output=True, text=True, timeout=30)

                deployments_ready = 0
                if deploy_result.returncode == 0:
                    deploy_data = json.loads(deploy_result.stdout)
                    deployments = deploy_data.get('items', [])
                    deployments_ready = sum(
                        1 for d in deployments
                        if d.get('status', {}).get('readyReplicas', 0) == d.get('spec', {}).get('replicas', 0)
                    )

                ds_result = subprocess.run([
                    'oc', 'get', 'daemonsets', '-n', self.lvms_namespace, '-o', 'json'
                ], capture_output=True, text=True, timeout=30)

                daemonsets_ready = 0
                if ds_result.returncode == 0:
                    ds_data = json.loads(ds_result.stdout)
                    daemonsets = ds_data.get('items', [])
                    daemonsets_ready = sum(
                        1 for ds in daemonsets
                        if ds.get('status', {}).get('numberReady', 0) == ds.get('status', {}).get('desiredNumberScheduled', 0)
                    )

                self.health_data['operator'] = {
                    'pods_total': total_pods,
                    'pods_ready': running_pods,
                    'deployments_ready': deployments_ready,
                    'daemonsets_ready': daemonsets_ready
                }

                print_success(f"Operator health: {running_pods}/{total_pods} pods ready")

                # Check for issues
                if running_pods < total_pods:
                    self.issues['warning'].append(f"{total_pods - running_pods} operator pod(s) not running")

            else:
                print_warning("Failed to collect operator health data")

        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            print_error(f"Error collecting operator health: {e}")

    def _collect_storage_class_data(self):
        """Collect LVMS storage class data and validate against device classes"""
        print_info("Collecting LVMS storage class data...")

        try:
            result = subprocess.run([
                'oc', 'get', 'storageclass', '-o', 'json'
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                all_scs = data.get('items', [])

                # Filter for TopoLVM storage classes
                lvms_scs = [
                    sc for sc in all_scs
                    if sc.get('provisioner') == 'topolvm.io'
                ]

                total_scs = len(lvms_scs)
                storage_class_names = [sc.get('metadata', {}).get('name', '') for sc in lvms_scs]

                # Get device class names from LVMCluster for validation
                device_class_names = []
                lvmcluster_data = self.health_data.get('lvmcluster', {})
                clusters = lvmcluster_data.get('clusters', [])

                for cluster in clusters:
                    storage_spec = cluster.get('spec', {}).get('storage', {})
                    device_classes = storage_spec.get('deviceClasses', [])
                    for dc in device_classes:
                        device_class_names.append(dc.get('name', ''))

                # Check 1:1 mapping between device classes and storage classes
                # Handle potential "lvms-" prefix in storage class names
                normalized_sc_names = []
                for sc_name in storage_class_names:
                    if sc_name.startswith('lvms-'):
                        normalized_sc_names.append(sc_name[5:])  # Remove "lvms-" prefix
                    else:
                        normalized_sc_names.append(sc_name)

                matched_classes = set(normalized_sc_names) & set(device_class_names)
                missing_scs = set(device_class_names) - set(normalized_sc_names)
                orphaned_scs = set(normalized_sc_names) - set(device_class_names)

                # Map missing/orphaned back to original storage class names with prefixes
                missing_scs_with_prefix = []
                orphaned_scs_with_prefix = []

                # For missing: device classes without corresponding storage classes
                for missing in missing_scs:
                    # Look for expected storage class name (with or without prefix)
                    expected_names = [f"lvms-{missing}", missing]
                    found = False
                    for expected in expected_names:
                        if expected in storage_class_names:
                            found = True
                            break
                    if not found:
                        missing_scs_with_prefix.append(f"lvms-{missing} or {missing}")

                # For orphaned: storage classes without corresponding device classes
                for i, norm_name in enumerate(normalized_sc_names):
                    if norm_name in orphaned_scs:
                        orphaned_scs_with_prefix.append(storage_class_names[i])

                self.health_data['storage_classes'] = {
                    'total': total_scs,
                    'device_classes_total': len(device_class_names),
                    'matched_classes': len(matched_classes),
                    'missing_storage_classes': missing_scs_with_prefix,
                    'orphaned_storage_classes': orphaned_scs_with_prefix,
                    'storage_classes': lvms_scs,
                    'storage_class_names': storage_class_names,
                    'normalized_sc_names': normalized_sc_names,
                    'device_class_names': device_class_names
                }

                print_success(f"Found {total_scs} LVMS storage class(es) for {len(device_class_names)} device class(es)")

                # Check for issues - storage class mapping is CRITICAL for functionality
                if len(device_class_names) == 0:
                    self.issues['critical'].append("No device classes configured in LVMCluster - LVMS cannot provision storage")
                elif total_scs == 0:
                    self.issues['critical'].append("No LVMS storage classes found - storage provisioning impossible")
                elif len(missing_scs_with_prefix) > 0:
                    self.issues['critical'].append(f"CRITICAL: Missing storage classes for device classes: {', '.join(missing_scs_with_prefix)} - Cannot provision storage from these device classes")
                elif len(orphaned_scs_with_prefix) > 0:
                    self.issues['critical'].append(f"CRITICAL: Orphaned storage classes without device classes: {', '.join(orphaned_scs_with_prefix)} - These storage classes are non-functional")

            else:
                print_warning("Failed to collect storage class data")
                self.health_data['storage_classes'] = {
                    'total': 0,
                    'device_classes_total': 0,
                    'matched_classes': 0,
                    'missing_storage_classes': [],
                    'orphaned_storage_classes': [],
                    'storage_classes': [],
                    'storage_class_names': [],
                    'device_class_names': []
                }

        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            print_error(f"Error collecting storage class data: {e}")

    def _collect_csi_driver_data(self):
        """Collect CSI driver status data"""
        print_info("Collecting CSI driver status...")

        try:
            # Check CSIDriver resource registration
            csidriver_result = subprocess.run([
                'oc', 'get', 'csidriver', 'topolvm.io', '-o', 'json'
            ], capture_output=True, text=True, timeout=30)

            csidriver_exists = csidriver_result.returncode == 0

            # Check CSINode resources (should match number of nodes with TopoLVM driver)
            csinode_result = subprocess.run([
                'oc', 'get', 'csinode', '-o', 'json'
            ], capture_output=True, text=True, timeout=30)

            csinode_count = 0
            topolvm_nodes = 0
            if csinode_result.returncode == 0:
                csinode_data = json.loads(csinode_result.stdout)
                csinodes = csinode_data.get('items', [])
                csinode_count = len(csinodes)

                # Count nodes with TopoLVM driver
                for node in csinodes:
                    drivers = node.get('spec', {}).get('drivers', [])
                    if any(d.get('name') == 'topolvm.io' for d in drivers):
                        topolvm_nodes += 1

            # CSI functionality is integrated into LVMS operator pods, so we validate
            # through operator health and CSIDriver registration rather than separate CSI pods
            operator_data = self.health_data.get('operator', {})
            operator_pods_ready = operator_data.get('pods_ready', 0)
            operator_pods_total = operator_data.get('pods_total', 0)

            self.health_data['csi_driver'] = {
                'csidriver_registered': csidriver_exists,
                'operator_provides_csi': True,  # CSI is integrated into operator
                'csinode_total': csinode_count,
                'topolvm_nodes': topolvm_nodes
            }

            if csidriver_exists and operator_pods_ready > 0:
                print_success(f"CSI driver: registered via LVMS operator, {topolvm_nodes}/{csinode_count} nodes with TopoLVM")
            else:
                print_warning(f"CSI driver: issues detected")

            # Check for issues
            if not csidriver_exists:
                self.issues['critical'].append("TopoLVM CSIDriver not registered")

            if operator_pods_ready == 0:
                self.issues['critical'].append("No LVMS operator pods running (CSI functionality unavailable)")

            if csinode_count > 0 and topolvm_nodes < csinode_count:
                self.issues['warning'].append(f"TopoLVM driver not registered on {csinode_count - topolvm_nodes} node(s)")

        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            print_error(f"Error collecting CSI driver data: {e}")

    def calculate_health_score(self):
        """Calculate overall health score"""
        score = 100

        # LVMCluster readiness (25 points)
        cluster_data = self.health_data.get('lvmcluster', {})
        total_clusters = cluster_data.get('total', 0)
        ready_clusters = cluster_data.get('ready', 0)

        if total_clusters > 0:
            cluster_score = int((ready_clusters / total_clusters) * 25)
            score = score - 25 + cluster_score

        # Volume group health (25 points)
        vg_data = self.health_data.get('volume_groups', [])
        if vg_data:
            healthy_vgs = sum(1 for vg in vg_data if vg.get('status') == 'OK')
            total_vgs = len(vg_data)
            vg_score = int((healthy_vgs / total_vgs) * 25) if total_vgs > 0 else 25
            score = score - 25 + vg_score

        # PVC binding (15 points)
        pvc_data = self.health_data.get('pvcs', {})
        total_pvcs = pvc_data.get('total', 0)
        bound_pvcs = pvc_data.get('bound', 0)

        if total_pvcs > 0:
            pvc_score = int((bound_pvcs / total_pvcs) * 15)
            score = score - 15 + pvc_score

        # Operator health (10 points)
        operator_data = self.health_data.get('operator', {})
        total_pods = operator_data.get('pods_total', 0)
        ready_pods = operator_data.get('pods_ready', 0)

        if total_pods > 0:
            operator_score = int((ready_pods / total_pods) * 10)
            score = score - 10 + operator_score

        # Storage classes (15 points) - CRITICAL component for functionality
        sc_data = self.health_data.get('storage_classes', {})
        device_classes_total = sc_data.get('device_classes_total', 0)
        matched_classes = sc_data.get('matched_classes', 0)
        missing_scs = sc_data.get('missing_storage_classes', [])
        orphaned_scs = sc_data.get('orphaned_storage_classes', [])

        if device_classes_total == 0:
            sc_score = 0  # No points if no device classes - LVMS cannot function
        elif matched_classes == device_classes_total and len(missing_scs) == 0 and len(orphaned_scs) == 0:
            sc_score = 15  # Full points only for perfect 1:1 mapping
        else:
            sc_score = 0  # Zero points for any mismatch - storage provisioning is broken

        score = score - 15 + sc_score

        # CSI driver (10 points)
        csi_data = self.health_data.get('csi_driver', {})
        csi_driver_registered = csi_data.get('csidriver_registered', False)
        operator_data = self.health_data.get('operator', {})
        operator_pods_ready = operator_data.get('pods_ready', 0)

        csi_score = 0
        if csi_driver_registered:
            csi_score += 5  # 5 points for CSIDriver registration

        # 5 points for operator pods being ready (which provide CSI functionality)
        if operator_pods_ready > 0:
            csi_score += 5
        else:
            csi_score += 0  # No points if operator pods not ready

        score = score - 10 + csi_score

        self.health_data['health_score'] = max(0, score)

    def determine_overall_status(self):
        """Determine overall health status"""
        critical_issues = len(self.issues['critical'])
        warning_issues = len(self.issues['warning'])
        health_score = self.health_data['health_score']

        if critical_issues > 0:
            self.health_data['overall_status'] = HealthStatus.CRITICAL
        elif warning_issues > 0 or health_score < 80:
            self.health_data['overall_status'] = HealthStatus.WARNING
        else:
            self.health_data['overall_status'] = HealthStatus.HEALTHY

    def generate_alerts(self):
        """Generate alerts based on health data"""
        alerts = []

        # Generate alerts from issues
        for issue in self.issues['critical']:
            alerts.append({
                'level': 'CRITICAL',
                'component': 'cluster',
                'message': issue
            })

        for issue in self.issues['warning']:
            alerts.append({
                'level': 'WARNING',
                'component': 'cluster',
                'message': issue
            })

        # Capacity alerts
        for vg in self.health_data.get('volume_groups', []):
            if vg.get('status') in ['WARNING', 'CRITICAL']:
                alerts.append({
                    'level': vg['status'],
                    'component': 'volume_group',
                    'node': vg['node'],
                    'message': f"Volume group {vg['vg_name']} at {vg['usage_percent']}% capacity"
                })

        self.health_data['alerts'] = alerts

    def generate_recommendations(self):
        """Generate recommendations based on alerts"""
        recommendations = []
        alerts = self.health_data.get('alerts', [])

        # Capacity recommendations
        capacity_alerts = [a for a in alerts if 'capacity' in a.get('message', '')]
        if capacity_alerts:
            recommendations.append("Consider expanding storage or cleaning up unused volumes")
            recommendations.append("Monitor capacity trends regularly")

        # PVC recommendations
        pvc_issues = [i for i in self.issues['critical'] if 'PVC' in i]
        if pvc_issues:
            recommendations.append("Investigate volume group availability on nodes")
            recommendations.append("Check storage class configuration")

        # LVMCluster recommendations
        cluster_issues = [i for i in self.issues['critical'] if 'LVMCluster' in i]
        if cluster_issues:
            recommendations.append("Run /lvms:analyze for detailed troubleshooting")
            recommendations.append("Check device availability and configuration")

        self.health_data['recommendations'] = recommendations

    def generate_output(self):
        """Generate output based on format"""
        # Set timestamp
        from datetime import datetime
        self.health_data['timestamp'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        if self.output_format == 'json':
            print(json.dumps(self.health_data, indent=2))
        else:
            self._generate_table_output()

    def _generate_table_output(self):
        """Generate table format output"""
        health_score = self.health_data['health_score']
        overall_status = self.health_data['overall_status']

        # Header
        print("\n" + "=" * 79)
        print("LVMS HEALTH CHECK")
        print("=" * 79)
        print()

        # Overall status
        status_icons = {
            HealthStatus.HEALTHY: "✓",
            HealthStatus.WARNING: "⚠",
            HealthStatus.CRITICAL: "❌"
        }

        icon = status_icons.get(overall_status, "?")
        print(f"Overall Status: {overall_status} {icon}")
        print(f"Health Score: {health_score}/100")
        print()

        # Component status table
        self._print_component_table()
        print()

        # Capacity table
        if self.health_data.get('volume_groups'):
            self._print_capacity_table()
            print()

        # Alerts
        alerts = self.health_data.get('alerts', [])
        if alerts:
            print("=" * 79)
            print("ALERTS & RECOMMENDATIONS")
            print("=" * 79)
            print()

            for alert in alerts:
                level = alert['level']
                message = alert['message']
                if level == 'CRITICAL':
                    print_error(f"{message}")
                else:
                    print_warning(f"{message}")

            # Recommendations
            recommendations = self.health_data.get('recommendations', [])
            if recommendations:
                print()
                for rec in recommendations:
                    print_info(f"{rec}")

        # Quick actions
        print()
        print("=" * 79)
        print("QUICK ACTIONS")
        print("=" * 79)
        print()
        print("• Detailed analysis: /lvms:analyze --live")
        print("• Monitor trends: Set up regular /lvms:health-check execution")
        print("• Expand storage: See LVMS documentation for adding devices")

    def _print_component_table(self):
        """Print component status table"""
        print("┌─────────────────┬────────────────────────────────────────┐")
        print("│ Component       │ Status                                 │")
        print("├─────────────────┼────────────────────────────────────────┤")

        # Helper function to format status column (38 chars wide)
        def format_status(status_text):
            return f"{status_text:<38}"

        # LVMCluster
        cluster_data = self.health_data.get('lvmcluster', {})
        ready = cluster_data.get('ready', 0)
        total = cluster_data.get('total', 0)

        if ready == total and total > 0:
            print(f"│ LVMCluster      │ {format_status('✓ Ready')} │")
        else:
            print(f"│ LVMCluster      │ {format_status(f'❌ {ready}/{total} ready')} │")

        # Volume Groups
        vg_data = self.health_data.get('volume_groups', [])
        healthy_vgs = sum(1 for vg in vg_data if vg.get('status') == 'OK')
        total_vgs = len(vg_data)

        if healthy_vgs == total_vgs and total_vgs > 0:
            print(f"│ Volume Groups   │ {format_status(f'✓ {healthy_vgs}/{total_vgs} functional')} │")
        elif total_vgs > 0:
            print(f"│ Volume Groups   │ {format_status(f'⚠ {healthy_vgs}/{total_vgs} functional')} │")
        else:
            print(f"│ Volume Groups   │ {format_status('ℹ No volume groups found')} │")

        # PVC Binding
        pvc_data = self.health_data.get('pvcs', {})
        bound = pvc_data.get('bound', 0)
        total_pvcs = pvc_data.get('total', 0)
        bind_rate = pvc_data.get('bind_rate', 0)

        if total_pvcs == 0:
            print(f"│ PVC Binding     │ {format_status('ℹ No LVMS PVCs found')} │")
        elif bound == total_pvcs:
            print(f"│ PVC Binding     │ {format_status(f'✓ {bound}/{total_pvcs} bound ({bind_rate}%)')} │")
        else:
            print(f"│ PVC Binding     │ {format_status(f'⚠ {bound}/{total_pvcs} bound ({bind_rate}%)')} │")

        # Operator
        operator_data = self.health_data.get('operator', {})
        ready_pods = operator_data.get('pods_ready', 0)
        total_pods = operator_data.get('pods_total', 0)

        if ready_pods == total_pods and total_pods > 0:
            print(f"│ Operator        │ {format_status('✓ All pods ready')} │")
        elif total_pods > 0:
            print(f"│ Operator        │ {format_status(f'⚠ {ready_pods}/{total_pods} pods ready')} │")
        else:
            print(f"│ Operator        │ {format_status('ℹ No operator pods found')} │")

        # Storage Classes
        sc_data = self.health_data.get('storage_classes', {})
        total_scs = sc_data.get('total', 0)
        device_classes_total = sc_data.get('device_classes_total', 0)
        matched_classes = sc_data.get('matched_classes', 0)
        missing_scs = sc_data.get('missing_storage_classes', [])
        orphaned_scs = sc_data.get('orphaned_storage_classes', [])

        if device_classes_total == 0:
            print(f"│ Storage Classes │ {format_status('❌ No device classes - cannot provision')} │")
        elif total_scs == 0:
            print(f"│ Storage Classes │ {format_status('❌ No storage classes - provisioning broken')} │")
        elif len(missing_scs) > 0:
            print(f"│ Storage Classes │ {format_status(f'❌ CRITICAL: {len(missing_scs)} missing classes')} │")
        elif len(orphaned_scs) > 0:
            print(f"│ Storage Classes │ {format_status(f'❌ CRITICAL: {len(orphaned_scs)} orphaned classes')} │")
        elif matched_classes == device_classes_total:
            print(f"│ Storage Classes │ {format_status(f'✓ {matched_classes}/{device_classes_total} perfect mapping')} │")
        else:
            print(f"│ Storage Classes │ {format_status('❌ CRITICAL: mapping broken')} │")

        # CSI Driver
        csi_data = self.health_data.get('csi_driver', {})
        csi_registered = csi_data.get('csidriver_registered', False)
        operator_data = self.health_data.get('operator', {})
        operator_pods_ready = operator_data.get('pods_ready', 0)

        if csi_registered and operator_pods_ready > 0:
            print(f"│ CSI Driver      │ {format_status('✓ Registered via LVMS operator')} │")
        elif csi_registered and operator_pods_ready == 0:
            print(f"│ CSI Driver      │ {format_status('⚠ Registered but operator not ready')} │")
        elif not csi_registered and operator_pods_ready > 0:
            print(f"│ CSI Driver      │ {format_status('⚠ Operator ready but driver not registered')} │")
        else:
            print(f"│ CSI Driver      │ {format_status('❌ Not configured')} │")

        print("└─────────────────┴────────────────────────────────────────┘")

    def _print_capacity_table(self):
        """Print capacity/volume group overview table"""
        print("=" * 79)
        print("VOLUME GROUP OVERVIEW")
        print("=" * 79)
        print()

        vg_data = self.health_data.get('volume_groups', [])
        if not vg_data:
            print("No volume group data available")
            return

        # Check if we have capacity data
        has_capacity_data = any(vg.get('capacity_available', True) and vg.get('size_bytes', 0) > 0 for vg in vg_data)

        if has_capacity_data:
            print("┌──────────────┬───────────┬─────────────┬─────────┬────────┐")
            print("│ Volume Group │ Node      │ Total       │ Used    │ Usage  │")
            print("├──────────────┼───────────┼─────────────┼─────────┼────────┤")

            total_capacity = 0
            total_used = 0

            for vg in vg_data:
                vg_name = vg['vg_name']
                node = vg['node'][:9]  # Truncate node name
                size_bytes = vg['size_bytes']
                used_bytes = vg['used_bytes']
                usage_percent = vg['usage_percent']
                status = vg['status']

                size_display = self._format_bytes(size_bytes)
                used_display = self._format_bytes(used_bytes)
                usage_display = f"{usage_percent}%"

                if status == "CRITICAL":
                    usage_display += " ❌"
                elif status == "WARNING":
                    usage_display += " ⚠"

                print(f"│ {vg_name:<12} │ {node:<9} │ {size_display:<11} │ {used_display:<7} │ {usage_display:<6} │")

                total_capacity += size_bytes
                total_used += used_bytes
        else:
            # Show VG status and device info instead of capacity
            print("┌──────────────┬───────────┬─────────────┬─────────────────┐")
            print("│ Volume Group │ Node      │ Status      │ Devices         │")
            print("├──────────────┼───────────┼─────────────┼─────────────────┤")

            for vg in vg_data:
                vg_name = vg['vg_name']
                node = vg['node'][:9]  # Truncate node name
                vg_status = vg.get('vg_status', 'Unknown')
                device_count = vg.get('device_count', 0)
                status = vg['status']

                # Format status display
                if vg_status == "Ready":
                    status_display = "✓ Ready"
                else:
                    status_display = f"❌ {vg_status}"

                devices_display = f"{device_count} device(s)"
                if status == "CRITICAL":
                    devices_display += " ❌"

                print(f"│ {vg_name:<12} │ {node:<9} │ {status_display:<11} │ {devices_display:<15} │")

            total_capacity = 0
            total_used = 0

        # Totals (only for capacity data)
        if len(vg_data) > 1 and has_capacity_data:
            print("├──────────────┼───────────┼─────────────┼─────────┼────────┤")
            total_usage_percent = int((total_used * 100) / total_capacity) if total_capacity > 0 else 0
            total_cap_display = self._format_bytes(total_capacity)
            total_used_display = self._format_bytes(total_used)
            node_count = len(set(vg['node'] for vg in vg_data))

            print(f"│ {'TOTAL':<12} │ {f'{node_count} nodes':<9} │ {total_cap_display:<11} │ {total_used_display:<7} │ {total_usage_percent}%     │")

        # Close the table with appropriate border
        if has_capacity_data:
            print("└──────────────┴───────────┴─────────────┴─────────┴────────┘")
        else:
            print("└──────────────┴───────────┴─────────────┴─────────────────┘")

    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes for human readable display"""
        if bytes_val == 0:
            return "0 B"

        units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
        unit_index = 0
        size = bytes_val

        while size >= 1024 and unit_index < len(units) - 1:
            size //= 1024
            unit_index += 1

        return f"{size} {units[unit_index]}"

    def _parse_size(self, size_str: str) -> int:
        """Parse size string to bytes"""
        if not size_str or size_str == '0':
            return 0

        # Remove any whitespace
        size_str = size_str.strip()

        # Extract number and unit
        match = re.match(r'(\d+(?:\.\d+)?)\s*([KMGT]i?)?', size_str)
        if not match:
            return 0

        number = float(match.group(1))
        unit = match.group(2) or ''

        # Convert to bytes
        multipliers = {
            '': 1,
            'K': 1000, 'Ki': 1024,
            'M': 1000**2, 'Mi': 1024**2,
            'G': 1000**3, 'Gi': 1024**3,
            'T': 1000**4, 'Ti': 1024**4,
        }

        return int(number * multipliers.get(unit, 1))

    def run_health_check(self) -> int:
        """Run complete health check and return exit code"""
        # Validate prerequisites
        if not self.validate_prerequisites():
            return 3

        # Collect health data
        self.collect_health_data()

        # Calculate metrics
        self.calculate_health_score()
        self.determine_overall_status()

        # Generate alerts and recommendations
        self.generate_alerts()
        self.generate_recommendations()

        # Generate output
        self.generate_output()

        # Return exit code based on status
        status_to_exit = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.WARNING: 1,
            HealthStatus.CRITICAL: 2
        }

        return status_to_exit.get(self.health_data['overall_status'], 3)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='LVMS Health Check - Lightweight monitoring and capacity tracking',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--format',
        choices=['table', 'json'],
        default='table',
        help='Output format (default: table)'
    )

    parser.add_argument(
        '--threshold-warning',
        type=int,
        default=80,
        help='Warning threshold percentage for capacity (default: 80)'
    )

    parser.add_argument(
        '--namespace',
        type=str,
        help='LVMS namespace (default: openshift-lvm-storage)'
    )

    args = parser.parse_args()

    # Always use live mode
    args.live = True
    args.must_gather_path = None

    # Run health check
    checker = LVMSHealthChecker(args)
    exit_code = checker.run_health_check()

    sys.exit(exit_code)


if __name__ == '__main__':
    main()