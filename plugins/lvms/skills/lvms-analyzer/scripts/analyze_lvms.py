#!/usr/bin/env python3
"""
LVMS Must-Gather Analyzer

Analyzes LVMS (Logical Volume Manager Storage) must-gather data to identify
and diagnose storage issues including LVMCluster health, volume groups,
PVC/PV problems, operator issues, and TopoLVM CSI driver status.

Usage:
    python3 analyze_lvms.py <must-gather-path> [--component <component>]

Arguments:
    must-gather-path: Path to the extracted must-gather directory
    --component: Optional filter for specific component analysis
                 (storage, operator, volumes, all)
"""

import os
import sys
import json
import yaml
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_section(title: str):
    """Print a formatted section header"""
    separator = "=" * 79
    print(f"\n{separator}")
    print(f"{Colors.BOLD}{title}{Colors.END}")
    print(f"{separator}\n")


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


def load_yaml_file(file_path: Path) -> Optional[Any]:
    """Load and parse a YAML file"""
    try:
        with open(file_path, 'r') as f:
            # Handle multiple YAML documents in one file
            docs = list(yaml.safe_load_all(f))
            return docs[0] if len(docs) == 1 else docs
    except Exception as e:
        print_error(f"Failed to load {file_path}: {e}")
        return None


def find_files(base_path: Path, pattern: str) -> List[Path]:
    """Recursively find files matching a pattern"""
    return list(base_path.rglob(pattern))


class LVMSAnalyzer:
    """Main analyzer class for LVMS must-gather data"""

    def __init__(self, must_gather_path: str):
        self.base_path = Path(must_gather_path)
        # LVMS namespace changed from openshift-storage to openshift-lvm-storage
        # Support both for backward compatibility with older must-gathers
        self.lvms_namespace = None
        self.possible_namespaces = ["openshift-lvm-storage", "openshift-storage"]

        # Data storage
        self.lvmclusters = []
        self.lvmvolumegroups = []
        self.lvmvolumegroupnodestatus = []
        self.pods = []
        self.events = []
        self.pvcs = []
        self.pvs = []
        self.storage_classes = []
        self.deployments = []
        self.daemonsets = []

        # Issue tracking
        self.issues = {
            'critical': [],
            'warning': [],
            'info': []
        }

        # Pod logs
        self.pod_logs = []

    def validate_must_gather(self) -> bool:
        """Validate that the must-gather path is correct and detect LVMS namespace"""
        # Try to detect which namespace is used in this must-gather
        for namespace in self.possible_namespaces:
            lvms_ns_path = self.base_path / "namespaces" / namespace
            if lvms_ns_path.exists():
                self.lvms_namespace = namespace
                if namespace == "openshift-storage":
                    print_info(f"Detected older LVMS installation using namespace: {namespace}")
                    print_info("(Newer LVMS versions use openshift-lvm-storage namespace)")
                else:
                    print_info(f"Detected LVMS namespace: {namespace}")
                return True

        # If neither namespace found, try to help find the correct path
        print_error(f"LVMS namespace directory not found in: {self.base_path}")
        print_info(f"Looking for must-gather structure at: {self.base_path}")

        # Try to find the correct subdirectory
        for namespace in self.possible_namespaces:
            possible_paths = list(self.base_path.glob(f"*/namespaces/{namespace}"))
            if possible_paths:
                print_info(f"Found LVMS namespace '{namespace}' at: {possible_paths[0].parent.parent}")
                print_info("Please use the correct subdirectory path")
                return False

        print_error("Could not find openshift-lvm-storage or openshift-storage namespace")
        print_info("This may not be an LVMS must-gather")
        return False

    def load_resources(self):
        """Load all LVMS-related resources from must-gather"""
        print_info("Loading LVMS resources from must-gather...")

        # LVMS must-gathers store resources in oc_output directory
        oc_output_dir = self.base_path / "namespaces" / self.lvms_namespace / "oc_output"

        # Load LVMCluster resources from oc_output/lvmcluster.yaml
        lvmcluster_file = oc_output_dir / "lvmcluster.yaml"
        if lvmcluster_file.exists():
            data = load_yaml_file(lvmcluster_file)
            if data:
                if isinstance(data, list):
                    self.lvmclusters.extend([item for item in data if item])
                elif isinstance(data, dict) and data.get('items'):
                    self.lvmclusters.extend(data['items'])
                elif isinstance(data, dict) and data.get('kind') == 'LVMCluster':
                    self.lvmclusters.append(data)
        else:
            # Fallback: try finding in API group directories (newer structure)
            lvmcluster_files = find_files(
                self.base_path / "namespaces" / self.lvms_namespace,
                "lvmclusters.yaml"
            )
            for file in lvmcluster_files:
                data = load_yaml_file(file)
                if data:
                    if isinstance(data, list):
                        self.lvmclusters.extend([item for item in data if item])
                    elif isinstance(data, dict) and data.get('items'):
                        self.lvmclusters.extend(data['items'])
                    elif isinstance(data, dict):
                        self.lvmclusters.append(data)

        # Note: LVMVolumeGroup and LVMVolumeGroupNodeStatus are often in text format in oc_output
        # We'll extract info from LVMCluster status which contains node-level VG status
        # For detailed VG info, check oc_output/lvmvolumegroup and lvmvolumegroupnodestatus text files

        # Load pods from pods directory
        pods_dir = self.base_path / "namespaces" / self.lvms_namespace / "pods"
        if pods_dir.exists():
            for pod_dir in pods_dir.iterdir():
                if pod_dir.is_dir():
                    # Look for {pod-name}.yaml in the pod directory
                    pod_yaml = pod_dir / f"{pod_dir.name}.yaml"
                    if pod_yaml.exists():
                        data = load_yaml_file(pod_yaml)
                        if data and isinstance(data, dict) and data.get('kind') == 'Pod':
                            self.pods.append(data)

        # Load events from oc_output or core directory
        events_file = oc_output_dir / "events"
        if not events_file.exists():
            # Try alternate location
            events_files = find_files(
                self.base_path / "namespaces" / self.lvms_namespace / "core",
                "events.yaml"
            )
            for file in events_files:
                data = load_yaml_file(file)
                if data:
                    if isinstance(data, dict) and data.get('items'):
                        self.events.extend(data['items'])
                    elif isinstance(data, list):
                        self.events.extend([item for item in data if item])

        # Load PVCs (all namespaces, filter for LVMS storage classes)
        pvc_files = find_files(self.base_path / "namespaces", "persistentvolumeclaims.yaml")
        for file in pvc_files:
            data = load_yaml_file(file)
            if data:
                if isinstance(data, dict) and data.get('items'):
                    self.pvcs.extend(data['items'])
                elif isinstance(data, list):
                    self.pvcs.extend([item for item in data if item])

        # Filter PVCs for LVMS storage classes
        self.pvcs = [
            pvc for pvc in self.pvcs
            if pvc.get('spec', {}).get('storageClassName', '').startswith('lvms-')
        ]

        # Load PVs
        pv_files = find_files(
            self.base_path / "cluster-scoped-resources" / "core",
            "persistentvolumes.yaml"
        )
        for file in pv_files:
            data = load_yaml_file(file)
            if data:
                if isinstance(data, dict) and data.get('items'):
                    pvs = data['items']
                elif isinstance(data, list):
                    pvs = data
                else:
                    pvs = [data] if data else []

                # Filter for TopoLVM provisioned volumes
                self.pvs.extend([
                    pv for pv in pvs
                    if pv.get('spec', {}).get('csi', {}).get('driver') == 'topolvm.io'
                ])

        # Load storage classes
        sc_files = find_files(
            self.base_path / "cluster-scoped-resources" / "storage.k8s.io",
            "storageclasses.yaml"
        )
        for file in sc_files:
            data = load_yaml_file(file)
            if data:
                if isinstance(data, dict) and data.get('items'):
                    scs = data['items']
                elif isinstance(data, list):
                    scs = data
                else:
                    scs = [data] if data else []

                # Filter for TopoLVM storage classes
                self.storage_classes.extend([
                    sc for sc in scs
                    if sc.get('provisioner') == 'topolvm.io'
                ])

        # Load deployments and daemonsets
        # Try apps directory first, then look in oc_output
        apps_dir = self.base_path / "namespaces" / self.lvms_namespace / "apps"

        deploy_files = find_files(apps_dir, "deployments.yaml") if apps_dir.exists() else []
        for file in deploy_files:
            data = load_yaml_file(file)
            if data:
                if isinstance(data, dict) and data.get('items'):
                    self.deployments.extend(data['items'])
                elif isinstance(data, list):
                    self.deployments.extend([item for item in data if item])
                elif isinstance(data, dict) and data.get('kind') == 'Deployment':
                    self.deployments.append(data)

        ds_files = find_files(apps_dir, "daemonsets.yaml") if apps_dir.exists() else []
        for file in ds_files:
            data = load_yaml_file(file)
            if data:
                if isinstance(data, dict) and data.get('items'):
                    self.daemonsets.extend(data['items'])
                elif isinstance(data, list):
                    self.daemonsets.extend([item for item in data if item])
                elif isinstance(data, dict) and data.get('kind') == 'DaemonSet':
                    self.daemonsets.append(data)

        print_success(f"Loaded {len(self.lvmclusters)} LVMCluster(s)")
        print_success(f"Loaded {len(self.pods)} pod(s)")
        print_success(f"Loaded {len(self.pvcs)} LVMS PVC(s)")
        print_success(f"Loaded {len(self.pvs)} LVMS PV(s)")
        print_success(f"Loaded {len(self.deployments)} deployment(s)")
        print_success(f"Loaded {len(self.daemonsets)} daemonset(s)")

    def load_pod_logs(self):
        """Load and parse pod logs from must-gather"""
        print_info("Loading pod logs...")

        pods_dir = self.base_path / "namespaces" / self.lvms_namespace / "pods"
        if not pods_dir.exists():
            return

        log_entries = []

        for pod_dir in pods_dir.iterdir():
            if not pod_dir.is_dir():
                continue

            pod_name = pod_dir.name

            # Find log files in pod directory
            # Structure: pods/{pod-name}/{container}/{container}/logs/current.log
            for container_dir in pod_dir.iterdir():
                if not container_dir.is_dir():
                    continue

                # Navigate to nested container directory
                nested_container_dir = container_dir / container_dir.name / "logs"
                if nested_container_dir.exists():
                    log_file = nested_container_dir / "current.log"
                    if log_file.exists():
                        container_name = container_dir.name
                        entries = self._parse_log_file(log_file, pod_name, container_name)
                        log_entries.extend(entries)

        # Deduplicate log entries by error message
        unique_errors = {}
        for entry in log_entries:
            error_key = entry['msg']
            if error_key not in unique_errors:
                unique_errors[error_key] = entry
            else:
                # Keep the earliest occurrence
                if entry['ts'] < unique_errors[error_key]['ts']:
                    unique_errors[error_key] = entry

        self.pod_logs = list(unique_errors.values())
        print_success(f"Loaded {len(self.pod_logs)} unique error/warning messages from pod logs")

    def _parse_log_file(self, log_file: Path, pod_name: str, container_name: str) -> List[Dict[str, Any]]:
        """Parse a JSON-formatted log file and extract error/warning entries"""
        entries = []

        try:
            with open(log_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        # Log format: "TIMESTAMP JSON"
                        # Split on first space to separate timestamp from JSON
                        parts = line.split(' ', 1)
                        if len(parts) < 2:
                            continue

                        json_part = parts[1]
                        log_entry = json.loads(json_part)

                        # Extract error and warning level logs
                        level = log_entry.get('level', '').lower()
                        if level in ['error', 'warning']:
                            entries.append({
                                'pod': pod_name,
                                'container': container_name,
                                'level': level,
                                'ts': log_entry.get('ts', ''),
                                'msg': log_entry.get('msg', ''),
                                'error': log_entry.get('error', ''),
                                'controller': log_entry.get('controller', ''),
                                'raw': log_entry
                            })
                    except (json.JSONDecodeError, IndexError):
                        # Skip non-JSON lines or malformed lines
                        continue
        except Exception as e:
            print_error(f"Failed to parse log file {log_file}: {e}")

        return entries

    def analyze_lvmcluster(self):
        """Analyze LVMCluster resource health"""
        print_section("LVMCLUSTER STATUS")

        if not self.lvmclusters:
            print_warning("No LVMCluster resources found")
            self.issues['critical'].append("No LVMCluster configured")
            return

        for cluster in self.lvmclusters:
            name = cluster.get('metadata', {}).get('name', 'unknown')
            status = cluster.get('status', {})

            print(f"\n{Colors.BOLD}LVMCluster:{Colors.END} {name}")

            # Check state
            state = status.get('state', 'Unknown')
            ready = status.get('ready', False)

            if state == 'Ready' and ready:
                print_success(f"State: {state}")
                print_success(f"Ready: {ready}")
            elif state == 'Progressing':
                print_warning(f"State: {state}")
                print_warning(f"Ready: {ready}")
                self.issues['warning'].append(f"LVMCluster {name} in Progressing state")
            else:
                print_error(f"State: {state}")
                print_error(f"Ready: {ready}")
                self.issues['critical'].append(f"LVMCluster {name} not Ready (state: {state})")

            # Check conditions
            conditions = status.get('conditions', [])
            if conditions:
                print(f"\n{Colors.BOLD}Conditions:{Colors.END}")
                for cond in conditions:
                    cond_type = cond.get('type', 'Unknown')
                    cond_status = cond.get('status', 'Unknown')
                    reason = cond.get('reason', '')
                    message = cond.get('message', '')

                    if cond_status == 'True':
                        print_success(f"{cond_type}: {cond_status}")
                        if reason:
                            print(f"  Reason: {reason}")
                    else:
                        print_error(f"{cond_type}: {cond_status}")
                        if reason:
                            print(f"  Reason: {reason}")
                        if message:
                            print(f"  Message: {message}")

                        self.issues['critical'].append(
                            f"LVMCluster {name} condition {cond_type}: {message or reason}"
                        )

            # Check device class statuses
            device_class_statuses = status.get('deviceClassStatuses', [])
            if device_class_statuses:
                print(f"\n{Colors.BOLD}Device Classes:{Colors.END}")
                for dc_status in device_class_statuses:
                    dc_name = dc_status.get('name', 'unknown')
                    node_status = dc_status.get('nodeStatus', [])

                    total_nodes = len(node_status)
                    ready_nodes = sum(1 for ns in node_status if ns.get('status') == 'Ready')

                    print(f"\n  Device Class: {dc_name}")
                    if ready_nodes == total_nodes and total_nodes > 0:
                        print_success(f"  Nodes: {ready_nodes}/{total_nodes} Ready")
                    elif ready_nodes > 0:
                        print_warning(f"  Nodes: {ready_nodes}/{total_nodes} Ready")
                        self.issues['warning'].append(
                            f"Device class {dc_name}: only {ready_nodes}/{total_nodes} nodes ready"
                        )
                    else:
                        print_error(f"  Nodes: {ready_nodes}/{total_nodes} Ready")
                        self.issues['critical'].append(
                            f"Device class {dc_name}: no nodes ready"
                        )

                    # Show failed nodes
                    failed_nodes = [ns.get('node') for ns in node_status if ns.get('status') != 'Ready']
                    if failed_nodes:
                        print(f"  Failed nodes: {', '.join(failed_nodes)}")

    def analyze_volume_groups(self):
        """Analyze volume group status from LVMCluster deviceClassStatuses"""
        print_section("VOLUME GROUP STATUS")

        if not self.lvmclusters:
            print_warning("No LVMCluster resources found")
            return

        # Extract VG info from LVMCluster status
        for cluster in self.lvmclusters:
            status = cluster.get('status', {})
            device_class_statuses = status.get('deviceClassStatuses', [])

            if not device_class_statuses:
                print_warning("No device class status information found in LVMCluster")
                return

            for dc_status in device_class_statuses:
                vg_name = dc_status.get('name', 'unknown')
                node_statuses = dc_status.get('nodeStatus', [])

                print(f"\n{Colors.BOLD}Volume Group/Device Class:{Colors.END} {vg_name}")
                print(f"Nodes: {len(node_statuses)}")

                for node_status in node_statuses:
                    node_name = node_status.get('node', 'unknown')
                    status_state = node_status.get('status', 'Unknown')
                    devices = node_status.get('devices', [])
                    reason = node_status.get('reason', '')

                    print(f"\n  {Colors.BOLD}Node:{Colors.END} {node_name}")

                    # Check status
                    if status_state == 'Ready':
                        print_success(f"  Status: {status_state}")
                    elif status_state == 'Progressing':
                        print_warning(f"  Status: {status_state}")
                        self.issues['warning'].append(f"VG {vg_name} on {node_name}: Progressing")
                    else:
                        print_error(f"  Status: {status_state}")
                        self.issues['critical'].append(f"VG {vg_name} on {node_name}: {status_state}")

                    # Show reason if failed/degraded
                    if reason:
                        print(f"\n  {Colors.BOLD}Reason:{Colors.END}")
                        # Print first few lines of reason
                        for line in reason.split('\n')[:5]:
                            print(f"  {line}")
                        if len(reason.split('\n')) > 5:
                            print(f"  ... (truncated, see LVMCluster status for full details)")
                        self.issues['critical'].append(f"VG {vg_name} on {node_name}: {reason[:200]}")

                    # Check devices
                    if devices:
                        valid_devices = [d for d in devices if d != '[unknown]']
                        if valid_devices:
                            print(f"\n  {Colors.BOLD}Devices:{Colors.END} {', '.join(valid_devices)}")
                        else:
                            print_warning(f"  Devices: No valid devices (unknown)")
                    else:
                        print_warning(f"  No devices configured")

                    # Show excluded devices summary
                    excluded = node_status.get('excluded', [])
                    if excluded:
                        print(f"\n  {Colors.BOLD}Excluded devices:{Colors.END} {len(excluded)} device(s)")
                        # Show first few exclusion reasons
                        for i, excl in enumerate(excluded[:3]):
                            name = excl.get('name', 'unknown')
                            reasons = excl.get('reasons', [])
                            if reasons:
                                print(f"    - {name}: {reasons[0]}")
                        if len(excluded) > 3:
                            print(f"    ... and {len(excluded) - 3} more excluded devices")

    def analyze_pvcs(self):
        """Analyze PVC status for LVMS volumes"""
        print_section("STORAGE (PVC/PV) STATUS")

        if not self.pvcs:
            print_info("No PVCs using LVMS storage classes found")
            return

        # Count by status
        status_counts = defaultdict(int)
        pending_pvcs = []

        for pvc in self.pvcs:
            phase = pvc.get('status', {}).get('phase', 'Unknown')
            status_counts[phase] += 1

            if phase != 'Bound':
                pending_pvcs.append(pvc)

        print(f"Total LVMS PVCs: {len(self.pvcs)}")
        for phase, count in sorted(status_counts.items()):
            if phase == 'Bound':
                print_success(f"{phase}: {count}")
            else:
                print_error(f"{phase}: {count}")

        # Analyze pending PVCs
        if pending_pvcs:
            print(f"\n{Colors.BOLD}Pending/Failed PVCs:{Colors.END}\n")

            for pvc in pending_pvcs:
                name = pvc.get('metadata', {}).get('name', 'unknown')
                namespace = pvc.get('metadata', {}).get('namespace', 'unknown')
                phase = pvc.get('status', {}).get('phase', 'Unknown')
                storage_class = pvc.get('spec', {}).get('storageClassName', 'unknown')
                requested_size = pvc.get('spec', {}).get('resources', {}).get('requests', {}).get('storage', 'unknown')

                print(f"{Colors.BOLD}{namespace}/{name}{Colors.END}")
                print_error(f"  Status: {phase}")
                print(f"  Storage Class: {storage_class}")
                print(f"  Requested: {requested_size}")

                # Check for related events
                related_events = [
                    e for e in self.events
                    if e.get('involvedObject', {}).get('name') == name
                    and e.get('involvedObject', {}).get('namespace') == namespace
                ]

                if related_events:
                    print(f"\n  {Colors.BOLD}Recent Events:{Colors.END}")
                    for event in related_events[-3:]:  # Last 3 events
                        event_type = event.get('type', 'Normal')
                        reason = event.get('reason', '')
                        message = event.get('message', '')

                        if event_type == 'Warning':
                            print_warning(f"  {reason}: {message}")
                        else:
                            print_info(f"  {reason}: {message}")

                self.issues['critical'].append(f"PVC {namespace}/{name} in {phase} state")
                print()

    def analyze_operator_health(self):
        """Analyze LVMS operator and component pod health"""
        print_section("OPERATOR HEALTH")

        # Analyze deployments
        if self.deployments:
            print(f"{Colors.BOLD}Deployments:{Colors.END}\n")
            for deploy in self.deployments:
                name = deploy.get('metadata', {}).get('name', 'unknown')
                spec = deploy.get('spec', {})
                status = deploy.get('status', {})

                desired = spec.get('replicas', 0)
                ready = status.get('readyReplicas', 0)

                if ready == desired and desired > 0:
                    print_success(f"{name}: {ready}/{desired} replicas ready")
                else:
                    print_error(f"{name}: {ready}/{desired} replicas ready")
                    self.issues['critical'].append(f"Deployment {name}: only {ready}/{desired} replicas ready")

        # Analyze daemonsets
        if self.daemonsets:
            print(f"\n{Colors.BOLD}DaemonSets:{Colors.END}\n")
            for ds in self.daemonsets:
                name = ds.get('metadata', {}).get('name', 'unknown')
                status = ds.get('status', {})

                desired = status.get('desiredNumberScheduled', 0)
                ready = status.get('numberReady', 0)

                if ready == desired and desired > 0:
                    print_success(f"{name}: {ready}/{desired} nodes ready")
                else:
                    print_warning(f"{name}: {ready}/{desired} nodes ready")
                    self.issues['warning'].append(f"DaemonSet {name}: only {ready}/{desired} nodes ready")

        # Analyze pod status
        if self.pods:
            problematic_pods = [
                pod for pod in self.pods
                if pod.get('status', {}).get('phase') not in ['Running', 'Succeeded']
            ]

            if problematic_pods:
                print(f"\n{Colors.BOLD}Problematic Pods:{Colors.END}\n")

                for pod in problematic_pods:
                    name = pod.get('metadata', {}).get('name', 'unknown')
                    phase = pod.get('status', {}).get('phase', 'Unknown')

                    print_error(f"{name}: {phase}")

                    # Check container statuses
                    container_statuses = pod.get('status', {}).get('containerStatuses', [])
                    for cs in container_statuses:
                        container_name = cs.get('name', 'unknown')
                        restart_count = cs.get('restartCount', 0)

                        if restart_count > 0:
                            print(f"  {container_name}: {restart_count} restarts")

                        # Check waiting/terminated states
                        if cs.get('state', {}).get('waiting'):
                            reason = cs['state']['waiting'].get('reason', '')
                            message = cs['state']['waiting'].get('message', '')
                            print_warning(f"  Waiting: {reason}")
                            if message:
                                print(f"  Message: {message}")

                        if cs.get('state', {}).get('terminated'):
                            reason = cs['state']['terminated'].get('reason', '')
                            message = cs['state']['terminated'].get('message', '')
                            exit_code = cs['state']['terminated'].get('exitCode', 0)
                            print_error(f"  Terminated: {reason} (exit code: {exit_code})")
                            if message:
                                print(f"  Message: {message}")

                    self.issues['critical'].append(f"Pod {name} in {phase} state")
                    print()

    def analyze_storage_classes(self):
        """Analyze TopoLVM storage class configuration"""
        print_section("TOPOLVM CSI DRIVER")

        if not self.storage_classes:
            print_warning("No TopoLVM storage classes found")
            self.issues['warning'].append("No TopoLVM storage classes configured")
            return

        print(f"{Colors.BOLD}Storage Classes:{Colors.END}\n")

        for sc in self.storage_classes:
            name = sc.get('metadata', {}).get('name', 'unknown')
            provisioner = sc.get('provisioner', 'unknown')
            binding_mode = sc.get('volumeBindingMode', 'Immediate')
            parameters = sc.get('parameters', {})

            print_success(f"{name}")
            print(f"  Provisioner: {provisioner}")
            print(f"  Binding Mode: {binding_mode}")

            if parameters:
                print(f"  Parameters:")
                for key, value in parameters.items():
                    print(f"    {key}: {value}")
            print()

    def analyze_pod_logs(self):
        """Analyze pod logs for errors and warnings"""
        print_section("POD LOGS ANALYSIS")

        if not self.pod_logs:
            print_info("No error or warning messages found in pod logs")
            return

        # Group logs by pod
        logs_by_pod = defaultdict(list)
        for log_entry in self.pod_logs:
            logs_by_pod[log_entry['pod']].append(log_entry)

        for pod_name, entries in sorted(logs_by_pod.items()):
            print(f"\n{Colors.BOLD}Pod:{Colors.END} {pod_name}")
            print(f"Unique errors/warnings: {len(entries)}\n")

            for entry in sorted(entries, key=lambda x: x['ts']):
                level = entry['level']
                timestamp = entry['ts']
                msg = entry['msg']
                error = entry['error']
                controller = entry['controller']

                if level == 'error':
                    print_error(f"{timestamp}: {msg}")
                else:
                    print_warning(f"{timestamp}: {msg}")

                if controller:
                    print(f"  Controller: {controller}")

                if error:
                    # Split multi-line errors for better readability
                    error_lines = error.split('\n')
                    if len(error_lines) > 1:
                        print(f"  {Colors.BOLD}Error Details:{Colors.END}")
                        for i, line in enumerate(error_lines[:10]):  # Show first 10 lines
                            if line.strip():
                                print(f"    {line}")
                        if len(error_lines) > 10:
                            print(f"    ... ({len(error_lines) - 10} more lines)")
                    else:
                        print(f"  Error: {error}")

                    # Track critical issues from logs
                    if level == 'error':
                        self.issues['critical'].append(f"Pod {pod_name}: {msg}")
                    else:
                        self.issues['warning'].append(f"Pod {pod_name}: {msg}")

                print()

    def generate_summary(self):
        """Generate final summary and recommendations"""
        print_section("LVMS ANALYSIS SUMMARY")

        critical_count = len(self.issues['critical'])
        warning_count = len(self.issues['warning'])
        info_count = len(self.issues['info'])

        if critical_count == 0 and warning_count == 0:
            print_success(f"No critical issues or warnings found")
            print_info("LVMS appears to be healthy")
        else:
            if critical_count > 0:
                print_error(f"CRITICAL ISSUES: {critical_count}")
                for issue in self.issues['critical']:
                    print(f"  - {issue}")
                print()

            if warning_count > 0:
                print_warning(f"WARNINGS: {warning_count}")
                for issue in self.issues['warning']:
                    print(f"  - {issue}")
                print()

        # Recommendations
        if critical_count > 0 or warning_count > 0:
            print_section("RECOMMENDATIONS")

            if critical_count > 0:
                print(f"{Colors.BOLD}CRITICAL (Fix Immediately):{Colors.END}\n")

                # Check for common patterns
                if any('PVC' in issue and 'Pending' in issue for issue in self.issues['critical']):
                    print("1. Investigate pending PVCs:")
                    print("   - Check volume group status on nodes")
                    print("   - Verify sufficient free space in volume groups")
                    print("   - Check vg-manager pods are running")
                    print("   - Review events for provisioning errors")
                    print()

                if any('not Ready' in issue or 'not ready' in issue for issue in self.issues['critical']):
                    print("2. Fix LVMCluster/VG readiness:")
                    print("   - Check node device availability")
                    print("   - Verify devices are not in use by other systems")
                    print("   - Review vg-manager pod logs")
                    print("   - Ensure devices match deviceSelector criteria")
                    print()

                if any('Pod' in issue for issue in self.issues['critical']):
                    print("3. Fix failing pods:")
                    print("   - Review pod logs in must-gather")
                    print("   - Check for image pull errors")
                    print("   - Verify node resources available")
                    print()

            if warning_count > 0:
                print(f"\n{Colors.BOLD}WARNINGS (Address Soon):{Colors.END}\n")

                if any('DaemonSet' in issue for issue in self.issues['warning']):
                    print("- Investigate DaemonSet node coverage")
                    print("  Check node taints and tolerations")
                    print()

    def run_analysis(self, component: str = 'all'):
        """Run the complete analysis"""
        if not self.validate_must_gather():
            return 1

        self.load_resources()
        self.load_pod_logs()

        if component in ['all', 'operator']:
            self.analyze_lvmcluster()

        if component in ['all', 'volumes', 'vg']:
            self.analyze_volume_groups()

        if component in ['all', 'storage', 'pvc']:
            self.analyze_pvcs()

        if component in ['all', 'operator', 'pods']:
            self.analyze_operator_health()

        if component in ['all', 'storage']:
            self.analyze_storage_classes()

        if component in ['all', 'operator', 'pods', 'logs']:
            self.analyze_pod_logs()

        self.generate_summary()

        # Return exit code based on issues
        return 1 if self.issues['critical'] else 0


def main():
    parser = argparse.ArgumentParser(
        description='Analyze LVMS must-gather data',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'must_gather_path',
        help='Path to the LVMS must-gather directory'
    )
    parser.add_argument(
        '--component',
        choices=['all', 'storage', 'operator', 'volumes', 'vg', 'pvc', 'pods', 'logs'],
        default='all',
        help='Component to analyze (default: all)'
    )

    args = parser.parse_args()

    analyzer = LVMSAnalyzer(args.must_gather_path)
    exit_code = analyzer.run_analysis(args.component)

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
