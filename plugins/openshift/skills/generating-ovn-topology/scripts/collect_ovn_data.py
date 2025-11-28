#!/usr/bin/env python3
"""
collect_ovn_data.py - Collect OVN data from live cluster

Usage: collect_ovn_data.py <KUBECONFIG> <TMPDIR>

This script collects OVN data from a live Kubernetes cluster:
1. Collects pod information from cluster (including auto-discovery of ovnkube-node pods)
2. Queries each node's NBDB once for all needed data
3. Writes standardized detail files (switches/routers include UUIDs)

Outputs (all files written to TMPDIR):
  - ovn_switches_detail.txt - node|uuid|name|other_config
  - ovn_routers_detail.txt  - node|uuid|name|external_ids|options
  - ovn_lsps_detail.txt     - node|name|addresses|type|options
  - ovn_lrps_detail.txt     - node|name|mac|networks|options
  - ovn_pods_detail.txt     - namespace|name|ip|node

Exit codes:
  0 - Success (all nodes collected OR partial success with warnings)
  1 - Total failure (no data collected)

Note: This script must be run from the scripts/ directory or have the scripts/
      directory in PYTHONPATH for the ovn_utils import to work.

Requirements: Python 3.6+, kubectl in PATH
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import csv
from io import StringIO

# Import shared utilities (must be in same directory or in PYTHONPATH)
from ovn_utils import (
    detect_ovn_namespace,
    detect_ovsdb_container,
    safe_write_file,
    safe_append_file,
)

# Configuration constants (module-scoped, private)
_OVNKUBE_NODE_APP_LABEL = "ovnkube-node"
_OVNKUBE_NODE_NAME_LABEL = "ovnkube-node"
_OVNKUBE_NODE_PREFIX = "ovnkube-node-"

# OVN component types (module-scoped, private)
_COMPONENT_LOGICAL_SWITCH = "Logical_Switch"
_COMPONENT_LOGICAL_SWITCH_PORT = "Logical_Switch_Port"
_COMPONENT_LOGICAL_ROUTER = "Logical_Router"
_COMPONENT_LOGICAL_ROUTER_PORT = "Logical_Router_Port"

# File name constants (module-scoped, private)
_PODS_DETAIL_FILE = "ovn_pods_detail.txt"
_SWITCHES_DETAIL_FILE = "ovn_switches_detail.txt"
_ROUTERS_DETAIL_FILE = "ovn_routers_detail.txt"
_LSPS_DETAIL_FILE = "ovn_lsps_detail.txt"
_LRPS_DETAIL_FILE = "ovn_lrps_detail.txt"


@dataclass
class CollectionStats:
    """Track collection statistics and failures."""

    pods_collected: int = 0
    nodes_attempted: int = 0
    nodes_successful: int = 0
    nodes_failed: List[str] = field(default_factory=list)
    component_counts: Dict[str, int] = field(default_factory=dict)

    def add_component(self, component_type: str, count: int = 1):
        """Add to component count."""
        self.component_counts[component_type] = (
            self.component_counts.get(component_type, 0) + count
        )


class OVNDataCollector:
    """Collect OVN data from live cluster with graceful degradation."""

    def __init__(self, kubeconfig: str, tmpdir: str):
        """Initialize OVNDataCollector with a private temporary directory.

        Args:
            kubeconfig: Path to kubeconfig file
            tmpdir: Private temporary directory path.
        """

        self.kubeconfig = kubeconfig
        self.stats = CollectionStats()
        self.ovnkube_node_pods: List[str] = []  # Discovered ovnkube-node pods
        self.ovsdb_container: Optional[str] = None  # Will be detected later
        self.ovn_namespace: Optional[str] = None  # Will be detected in run()

        # Output files (detail files with UUIDs for switches/routers)
        self.pods_file = os.path.join(tmpdir, _PODS_DETAIL_FILE)
        self.switches_file = os.path.join(tmpdir, _SWITCHES_DETAIL_FILE)
        self.routers_file = os.path.join(tmpdir, _ROUTERS_DETAIL_FILE)
        self.lsps_file = os.path.join(tmpdir, _LSPS_DETAIL_FILE)
        self.lrps_file = os.path.join(tmpdir, _LRPS_DETAIL_FILE)

    def initialize_output_files(self):
        """Create/clear output files."""
        for filepath in [
            self.pods_file,
            self.switches_file,
            self.routers_file,
            self.lsps_file,
            self.lrps_file,
        ]:
            # Create empty file using safe write
            safe_write_file(filepath, "")

    def _is_ovnkube_node_pod(self, pod_item: dict) -> bool:
        """Check if a pod is an ovnkube-node pod.

        Uses multiple methods for compatibility:
        1. Label app=ovnkube-node
        2. Label name=ovnkube-node (older deployments)
        3. Name pattern ovnkube-node-*

        Args:
            pod_item: Pod object from kubectl JSON output

        Returns:
            True if this is an ovnkube-node pod, False otherwise
        """
        namespace = pod_item.get('metadata', {}).get('namespace', '')
        name = pod_item.get('metadata', {}).get('name', '')
        labels = pod_item.get('metadata', {}).get('labels', {})

        # Must be in ovn-kubernetes namespace
        if namespace != self.ovn_namespace:
            return False

        # Method 1: Check for app=ovnkube-node label
        if labels.get('app') == _OVNKUBE_NODE_APP_LABEL:
            return True

        # Method 2: Check for name=ovnkube-node label (older deployments)
        if labels.get('name') == _OVNKUBE_NODE_NAME_LABEL:
            return True

        # Method 3: Check name pattern
        if name.startswith(_OVNKUBE_NODE_PREFIX):
            return True

        return False

    def _parse_pod_json(self, data: dict) -> int:
        """Parse JSON pod data and write to file.

        Args:
            data: JSON pod list from kubectl get pods -o json

        Returns:
            Number of pods collected
        """
        count = 0
        content_lines = []
        for item in data.get('items', []):
            # Only running pods with IPs
            if (item.get('status', {}).get('phase') == 'Running' and
                    item.get('status', {}).get('podIP')):

                namespace = item['metadata']['namespace']
                name = item['metadata']['name']
                pod_ip = item['status']['podIP']
                node = item['spec'].get('nodeName', 'unknown')

                content_lines.append(f"{namespace}|{name}|{pod_ip}|{node}\n")
                count += 1

                # Auto-discover ovnkube-node pods
                if self._is_ovnkube_node_pod(item):
                    self.ovnkube_node_pods.append(name)

        if content_lines:
            safe_write_file(self.pods_file, "".join(content_lines))

        return count

    def collect_pods_info(self) -> bool:
        """Collect pod information from cluster and discover ovnkube-node pods.

        Writes to ovn_pods_detail.txt: namespace|pod_name|pod_ip|node_name
        Also populates self.ovnkube_node_pods with discovered ovnkube-node pods.

        Returns:
            True if successful, False otherwise.
        """
        print("=" * 50)
        print("COLLECTING POD INFORMATION")
        print("=" * 50)

        try:
            # Try JSON parsing first (more reliable)
            env = os.environ.copy()
            env["KUBECONFIG"] = self.kubeconfig
            result = subprocess.run(
                [
                    "kubectl", "--kubeconfig", self.kubeconfig,
                    "get", "pods", "-A", "-o", "json"
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )

            if result.returncode != 0:
                print(
                    "  ⚠️  kubectl get pods failed, trying fallback...",
                    file=sys.stderr,
                )
                return self._collect_pods_fallback()

            # Parse JSON
            try:
                data = json.loads(result.stdout)
                self.stats.pods_collected = self._parse_pod_json(data)

                print(f"  ✓ Collected {self.stats.pods_collected} running pods")
                print(f"  ✓ Discovered {len(self.ovnkube_node_pods)} ovnkube-node pods")
                return True

            except json.JSONDecodeError:
                print(
                    "  ⚠️  JSON parsing failed, trying fallback...",
                    file=sys.stderr,
                )
                return self._collect_pods_fallback()

        except subprocess.TimeoutExpired:
            print(
                "  ⚠️  kubectl timeout, trying fallback...",
                file=sys.stderr,
            )
            return self._collect_pods_fallback()
        except Exception as e:
            print(
                f"  ⚠️  Error: {e}, trying fallback...",
                file=sys.stderr,
            )
            return self._collect_pods_fallback()

    def _collect_pods_fallback(self) -> bool:
        """Fallback method using kubectl -o wide and auto-discover ovnkube-node pods."""
        try:
            env = os.environ.copy()
            env["KUBECONFIG"] = self.kubeconfig
            result = subprocess.run(
                [
                    "kubectl", "--kubeconfig", self.kubeconfig,
                    "get", "pods", "-A", "-o", "wide", "--no-headers"
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )

            if result.returncode != 0:
                return False

            content_lines = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split()
                if (len(parts) >= 8 and parts[3] == 'Running' and
                        parts[6] != '<none>'):
                    namespace = parts[0]
                    pod_name = parts[1]
                    pod_ip = parts[6]
                    node_name = parts[7]

                    # namespace|pod_name|pod_ip|node_name
                    content_lines.append(f"{namespace}|{pod_name}|{pod_ip}|{node_name}\n")
                    self.stats.pods_collected += 1

                    # Auto-discover ovnkube-node pods (simple pattern check for fallback)
                    if (namespace == self.ovn_namespace and
                            pod_name.startswith(_OVNKUBE_NODE_PREFIX)):
                        self.ovnkube_node_pods.append(pod_name)

            if content_lines:
                safe_write_file(self.pods_file, "".join(content_lines))

            print(
                f"  ✓ Collected {self.stats.pods_collected} running pods (fallback)"
            )
            print(f"  ✓ Discovered {len(self.ovnkube_node_pods)} ovnkube-node pods")
            return True

        except Exception as e:
            print(f"  ❌ Fallback also failed: {e}", file=sys.stderr)
            return False

    def get_node_name_for_pod(self, pod: str) -> Optional[str]:
        """Get node name for a given pod."""
        try:
            env = os.environ.copy()
            env["KUBECONFIG"] = self.kubeconfig
            result = subprocess.run(
                [
                    "kubectl", "--kubeconfig", self.kubeconfig,
                    "get", "pod", "-n", self.ovn_namespace, pod,
                    "-o", "jsonpath={.spec.nodeName}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None

        except Exception:
            return None

    def query_ovn_component(
        self, pod: str, node_name: str, component_type: str,
        columns: str, output_file: str
    ) -> Tuple[bool, int]:
        """Query OVN component data from a specific pod.

        Args:
            pod: Pod name to query
            node_name: Node name (for labeling output)
            component_type: OVN table name (e.g., "Logical_Switch")
            columns: Comma-separated column names
            output_file: File to append results to

        Returns:
            (success: bool, count: int) - Whether query succeeded and entry count

        Note:
            All exceptions (timeouts, subprocess errors) are caught and handled
            internally. Errors are logged to stderr and return (False, 0).
        """
        try:
            env = os.environ.copy()
            env["KUBECONFIG"] = self.kubeconfig
            result = subprocess.run(
                [
                    "kubectl", "--kubeconfig", self.kubeconfig,
                    "exec", "-n", self.ovn_namespace, pod, "-c", self.ovsdb_container,
                    "--",
                    "ovn-nbctl", "--no-leader-only", "--format=csv",
                    "--data=bare", "--no-headings",
                    f"--columns={columns}", "list", component_type,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )

            if result.returncode != 0:
                return False, 0

            lines = result.stdout.strip().split('\n')
            count = 0

            # Build content to append
            content_lines = []
            for line in lines:
                if not line:
                    continue
                # Parse CSV properly to handle quoted fields with commas
                reader = csv.reader(StringIO(line))
                for row in reader:
                    line_with_pipes = '|'.join(row)
                    content_lines.append(f"{node_name}|{line_with_pipes}\n")
                    count += 1

            if content_lines:
                safe_append_file(output_file, "".join(content_lines))

            return True, count

        except subprocess.TimeoutExpired:
            print(
                f"      ⚠️  Timeout querying {component_type}",
                file=sys.stderr,
            )
            return False, 0
        except Exception as e:
            print(
                f"      ⚠️  Error querying {component_type}: {e}",
                file=sys.stderr,
            )
            return False, 0

    def collect_node_data(self, pod: str, node_name: str) -> bool:
        """Collect all OVN data from a single node.

        This queries each component once with all needed columns including UUID.

        Args:
            pod: Pod name to query.
            node_name: Node name for labeling output.

        Returns:
            True if ANY data was collected successfully, False otherwise.
        """
        print(f"  Node: {node_name} (pod: {pod})")

        any_success = False

        # Collect Logical Switches (with UUID)
        # Output: node|uuid|name|other_config
        print("    Querying Logical_Switch...")
        success, count = self.query_ovn_component(
            pod, node_name, _COMPONENT_LOGICAL_SWITCH,
            "_uuid,name,other_config", self.switches_file
        )
        if success:
            self.stats.add_component("switches", count)
            print(f"      ✓ Collected {count} switches")
            any_success = True
        else:
            print(
                f"    ⚠️  Failed to query switches from {pod}",
                file=sys.stderr,
            )

        # Collect Logical Switch Ports (no UUID needed)
        # Output: node|name|addresses|type|options
        print("    Querying Logical_Switch_Port...")
        success, count = self.query_ovn_component(
            pod, node_name, _COMPONENT_LOGICAL_SWITCH_PORT,
            "name,addresses,type,options", self.lsps_file
        )
        if success:
            self.stats.add_component("lsps", count)
            print(f"      ✓ Collected {count} LSPs")
            any_success = True
        else:
            print(
                f"    ⚠️  Failed to query LSPs from {pod}",
                file=sys.stderr,
            )

        # Collect Logical Routers (with UUID)
        # Output: node|uuid|name|external_ids|options
        print("    Querying Logical_Router...")
        success, count = self.query_ovn_component(
            pod, node_name, _COMPONENT_LOGICAL_ROUTER,
            "_uuid,name,external_ids,options", self.routers_file
        )
        if success:
            self.stats.add_component("routers", count)
            print(f"      ✓ Collected {count} routers")
            any_success = True
        else:
            print(
                f"    ⚠️  Failed to query routers from {pod}",
                file=sys.stderr,
            )

        # Collect Logical Router Ports (no UUID needed)
        # Output: node|name|mac|networks|options
        print("    Querying Logical_Router_Port...")
        success, count = self.query_ovn_component(
            pod, node_name, _COMPONENT_LOGICAL_ROUTER_PORT,
            "name,mac,networks,options", self.lrps_file
        )
        if success:
            self.stats.add_component("lrps", count)
            print(f"      ✓ Collected {count} LRPs")
            any_success = True
        else:
            print(
                f"    ⚠️  Failed to query LRPs from {pod}",
                file=sys.stderr,
            )

        return any_success

    def collect_all_nodes(self):
        """Collect data from all nodes with graceful degradation."""
        print()
        print("=" * 50)
        print("COLLECTING OVN DATA FROM NODES")
        print("=" * 50)

        if not self.ovnkube_node_pods:
            print(
                "❌ No ovnkube-node pods discovered. Cannot collect OVN data.",
                file=sys.stderr,
            )
            return

        # Auto-detect OVSDB container name using first pod
        try:
            self.ovsdb_container = detect_ovsdb_container(
                self.kubeconfig, self.ovn_namespace, self.ovnkube_node_pods[0]
            )
        except RuntimeError as e:
            print(f"❌ Container detection failed: {e}", file=sys.stderr)
            return

        # Print architecture detection summary
        print()
        print("=" * 50)
        print("ARCHITECTURE DETECTION")
        print("=" * 50)
        platform = "OpenShift" if self.ovn_namespace == "openshift-ovn-kubernetes" else "Upstream OVN-Kubernetes"
        print(f"  Platform:       {platform}")
        print(f"  OVN Namespace:  {self.ovn_namespace}")
        print(f"  NBDB Container: {self.ovsdb_container}")
        print(f"  Nodes:          {len(self.ovnkube_node_pods)}")
        print()

        for pod in self.ovnkube_node_pods:
            self.stats.nodes_attempted += 1

            # Get node name
            node_name = self.get_node_name_for_pod(pod)
            if not node_name:
                print(
                    f"  ⚠️  Warning: Could not determine node for pod {pod}",
                    file=sys.stderr,
                )
                self.stats.nodes_failed.append(f"{pod} (unknown node)")
                continue

            # Try to collect data from this node
            try:
                success = self.collect_node_data(pod, node_name)
                if success:
                    self.stats.nodes_successful += 1
                else:
                    self.stats.nodes_failed.append(f"{node_name} ({pod})")
            except Exception as e:
                print(
                    f"  ❌ Error collecting from {node_name}: {e}",
                    file=sys.stderr,
                )
                self.stats.nodes_failed.append(
                    f"{node_name} ({pod}) - {str(e)}"
                )

    def is_collection_successful(self) -> bool:
        """Determine if collection was successful.

        Returns:
            True if any nodes were successfully queried (partial success OK)
            False if complete failure (no nodes could be queried)
        """
        return self.stats.nodes_successful > 0

    def print_summary(self):
        """Print collection summary."""
        print()
        print("=" * 50)
        print("COLLECTION SUMMARY")
        print("=" * 50)

        # Count lines in output files
        def count_lines(filepath):
            try:
                with open(filepath) as f:
                    return sum(1 for _ in f)
            except Exception:
                return 0

        print(f"Pods:     {self.stats.pods_collected}")
        print(f"Nodes attempted: {self.stats.nodes_attempted}")
        print(f"Nodes successful: {self.stats.nodes_successful}")

        print()
        print("Detail files (switches/routers include UUIDs):")
        print(f"  Pods:     {count_lines(self.pods_file)} → {self.pods_file}")
        print(f"  Switches: {count_lines(self.switches_file)} → {self.switches_file}")
        print(f"  Routers:  {count_lines(self.routers_file)} → {self.routers_file}")
        print(f"  LSPs:     {count_lines(self.lsps_file)} → {self.lsps_file}")
        print(f"  LRPs:     {count_lines(self.lrps_file)} → {self.lrps_file}")

        if self.stats.nodes_failed:
            print()
            print(f"Nodes failed: {len(self.stats.nodes_failed)}")
            print("⚠️  WARNING: Some nodes could not be queried:")
            for failed in self.stats.nodes_failed:
                print(f"  • {failed}")
            print()
            print("💡 TIP: Check these nodes with:")
            print(f"   kubectl get pods -n {self.ovn_namespace}")
            print(f"   kubectl describe pod -n {self.ovn_namespace} <pod-name>")
            print()

        # Print final status
        if self.is_collection_successful():
            if self.stats.nodes_failed:
                print("✅ Partial data collection successful")
                print(
                    f"   ({self.stats.nodes_successful}/"
                    f"{self.stats.nodes_attempted} nodes)"
                )
            else:
                print("✅ Complete data collection successful (all nodes)")
        else:
            print("❌ Complete failure - no nodes could be queried")

    def run(self) -> int:
        """Run the complete collection process.

        Returns:
            0 if successful (including partial success)
            1 if complete failure
        """
        # Detect OVN namespace after argument validation
        try:
            self.ovn_namespace = detect_ovn_namespace(self.kubeconfig)
        except Exception as exc:
            print(f"❌ Failed to detect OVN namespace: {exc}", file=sys.stderr)
            return 1

        # Initialize output files
        self.initialize_output_files()

        # Collect pod information
        if not self.collect_pods_info():
            print(
                "❌ Failed to collect pod information",
                file=sys.stderr,
            )
            # Continue anyway - we might still get OVN data

        # Collect OVN data from all nodes
        self.collect_all_nodes()

        # Verify we collected some data
        if not self.is_collection_successful():
            print("❌ No data collected from any node", file=sys.stderr)
            return 1

        # Print collection summary
        self.print_summary()

        return 0


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print(
            f"Usage: {sys.argv[0]} <KUBECONFIG> <TMPDIR>",
            file=sys.stderr,
        )
        return 1

    kubeconfig = sys.argv[1]
    tmpdir = sys.argv[2]

    if not os.path.exists(kubeconfig):
        print(
            f"❌ Error: Kubeconfig not found: {kubeconfig}",
            file=sys.stderr,
        )
        return 1

    if not os.path.isdir(tmpdir):
        print(
            f"❌ Error: TMPDIR is not a directory or does not exist: {tmpdir}",
            file=sys.stderr,
        )
        return 1

    collector = OVNDataCollector(kubeconfig, tmpdir)
    try:
        return collector.run()
    except OSError as exc:
        print(f"❌ Error writing output files: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
