#!/usr/bin/env python3
"""
OpenShift Multi-Node SOS Report Collector
Automates parallel collection of SOS reports from multiple OpenShift nodes.
"""

import subprocess
import sys
import time
import re
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import threading

# Import the single-node collector class
import importlib.util
spec = importlib.util.spec_from_file_location(
    "sosreport_single_collector",
    Path(__file__).parent / "sosreport-single-collector.py"
)
sosreport_single_collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sosreport_single_collector)
SOSReportCollector = sosreport_single_collector.SOSReportCollector


class Colors:
    """ANSI color codes for terminal output"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"


class MultiNodeCollector:
    def __init__(self, nodes, download_dir=".work/sos-reports", case_id=None,
                 namespace="default", plugin_timeout=900, max_parallel=5, auto_cleanup=False):
        """
        Initialize Multi-Node SOS Report Collector

        Args:
            nodes: List of OpenShift node names
            download_dir: Local directory to store downloaded reports
            case_id: Optional Red Hat case ID
            namespace: Namespace for debug pods
            plugin_timeout: Timeout for each plugin in seconds
            max_parallel: Maximum number of parallel collections
            auto_cleanup: Automatically cleanup debug pods after collection
        """
        self.nodes = list(set(nodes))  # Remove duplicates
        self.download_dir = Path(download_dir)
        self.case_id = case_id

        # Validate and sanitize namespace to prevent shell injection
        # Kubernetes namespace must be a valid DNS label (alphanumeric, hyphens, max 63 chars)
        if not re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', namespace) or len(namespace) > 63:
            raise ValueError(f"Invalid namespace: {namespace}. Must be a valid Kubernetes namespace name.")
        self.namespace = namespace

        self.plugin_timeout = plugin_timeout
        self.max_parallel = max_parallel
        self.auto_cleanup = auto_cleanup

        # Create directories
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir = self.download_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Track results
        self.results = {
            'debug_pods': {},      # node -> pod_name or error
            'collections': {},     # node -> report_path or error
            'downloads': {},       # node -> local_path or error
            'cleanups': {},        # node -> success/error
        }

        # Thread-safe printing
        self.print_lock = threading.Lock()

    def safe_print(self, message):
        """Thread-safe printing with closed stdout handling"""
        with self.print_lock:
            try:
                print(message, flush=True)
            except (ValueError, OSError):
                # stdout is closed (e.g., from piped input), skip printing
                pass

    def validate_prerequisites(self):
        """Validate prerequisites before starting"""
        self.safe_print(f"\n{Colors.BOLD}Validating prerequisites...{Colors.RESET}")

        # Check oc CLI
        try:
            subprocess.run(["which", "oc"], check=True,
                          capture_output=True)
        except subprocess.CalledProcessError:
            self.safe_print(f"{Colors.RED}[ERROR] oc CLI not found. Please install OpenShift CLI{Colors.RESET}")
            return False

        # Check login
        try:
            subprocess.run(["oc", "whoami"], check=True,
                          capture_output=True)
        except subprocess.CalledProcessError:
            self.safe_print(f"{Colors.RED}[ERROR] Not logged in to OpenShift. Run: oc login{Colors.RESET}")
            return False

        # Validate nodes exist
        valid_nodes = []
        for node in self.nodes:
            try:
                subprocess.run(["oc", "get", "node", node], check=True,
                             capture_output=True, timeout=10)
                valid_nodes.append(node)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                self.safe_print(f"{Colors.YELLOW}[WARNING] Node not found or unreachable: {node}{Colors.RESET}")

        if not valid_nodes:
            self.safe_print(f"{Colors.RED}[ERROR] No valid nodes found{Colors.RESET}")
            return False

        if len(valid_nodes) < len(self.nodes):
            self.safe_print(f"{Colors.YELLOW}[WARNING] Continuing with {len(valid_nodes)}/{len(self.nodes)} valid nodes{Colors.RESET}")
            self.nodes = valid_nodes

        return True

    def display_plan(self):
        """Display collection plan and get user confirmation"""
        self.safe_print(f"\n{Colors.BOLD}{'='*60}")
        self.safe_print("Multi-Node SOS Report Collection Plan")
        self.safe_print(f"{'='*60}{Colors.RESET}")
        self.safe_print(f"\n{Colors.CYAN}Nodes to collect ({len(self.nodes)}):{Colors.RESET}")
        for i, node in enumerate(self.nodes, 1):
            self.safe_print(f"  {i}. {node}")

        self.safe_print(f"\n{Colors.CYAN}Configuration:{Colors.RESET}")
        self.safe_print(f"  Download directory: {self.download_dir}")
        self.safe_print(f"  Case ID: {self.case_id or 'None'}")
        self.safe_print(f"  Namespace: {self.namespace}")
        self.safe_print(f"  Plugin timeout: {self.plugin_timeout}s")
        self.safe_print(f"  Max parallel: {self.max_parallel}")
        self.safe_print(f"  Auto cleanup: {self.auto_cleanup}")

        # Estimate time
        estimated_time = (len(self.nodes) / self.max_parallel) * 25  # ~25 min per batch
        self.safe_print(f"\n{Colors.CYAN}Estimated time: {estimated_time:.0f} minutes{Colors.RESET}")

        self.safe_print(f"\n{Colors.YELLOW}Note: Each node collection typically takes 10-30 minutes{Colors.RESET}")
        self.safe_print(f"{Colors.YELLOW}      Collections run in parallel (up to {self.max_parallel} at a time){Colors.RESET}")

        # Confirmation
        try:
            response = input(f"\n{Colors.BOLD}Proceed with collection? (yes/no): {Colors.RESET}")
            return response.lower() in ['yes', 'y']
        except EOFError:
            # stdin is closed (from pipe), auto-confirm
            return True

    def start_debug_pod_for_node(self, node):
        """Start debug pod for a single node"""
        log_file = self.logs_dir / f"{node.split('.')[0]}-start.log"
        try:
            collector = SOSReportCollector(
                node_name=node,
                download_dir=str(self.download_dir),
                case_id=self.case_id,
                namespace=self.namespace,
                plugin_timeout=self.plugin_timeout
            )

            # Start debug pod (output goes to stdout and log file)
            try:
                pod_name = collector.start_debug_pod()
                with open(log_file, 'w') as log:
                    log.write(f"Starting debug pod for {node}\n")
                    log.write(f"Debug pod started: {pod_name}\n")
                return node, pod_name, None
            except Exception as e:
                with open(log_file, 'w') as log:
                    log.write(f"Error: {str(e)}\n")
                return node, None, str(e)

        except Exception as e:
            with open(log_file, 'w') as log:
                log.write(f"Outer error: {str(e)}\n")
            return node, None, str(e)

    def collect_report_for_node(self, node, pod_name):
        """Collect SOS report for a single node"""
        log_file = self.logs_dir / f"{node.split('.')[0]}-collect.log"
        try:
            collector = SOSReportCollector(
                node_name=node,
                download_dir=str(self.download_dir),
                case_id=self.case_id,
                namespace=self.namespace,
                plugin_timeout=self.plugin_timeout
            )
            collector.debug_pod_name = pod_name

            # Collect SOS report (output goes to stdout and log file)
            try:
                report_path = collector.collect_sos_report()
                with open(log_file, 'w') as log:
                    log.write(f"Collecting SOS report from {node}\n")
                    log.write(f"SOS report collected: {report_path}\n")
                return node, report_path, None
            except Exception as e:
                with open(log_file, 'w') as log:
                    log.write(f"Error: {str(e)}\n")
                return node, None, str(e)

        except Exception as e:
            with open(log_file, 'w') as log:
                log.write(f"Outer error: {str(e)}\n")
            return node, None, str(e)

    def download_report_for_node(self, node, pod_name, report_path):
        """Download SOS report for a single node"""
        log_file = self.logs_dir / f"{node.split('.')[0]}-download.log"
        try:
            collector = SOSReportCollector(
                node_name=node,
                download_dir=str(self.download_dir),
                case_id=self.case_id,
                namespace=self.namespace,
                plugin_timeout=self.plugin_timeout
            )
            collector.debug_pod_name = pod_name

            # Download report (output goes to stdout and log file)
            try:
                local_path = collector.download_report(report_path=report_path)
                with open(log_file, 'w') as log:
                    log.write(f"Downloading SOS report from {node}\n")
                    log.write(f"Report path: {report_path}\n")
                    log.write(f"Downloaded to: {local_path}\n")
                return node, local_path, None
            except Exception as e:
                with open(log_file, 'w') as log:
                    log.write(f"Error: {str(e)}\n")
                return node, None, str(e)

        except Exception as e:
            with open(log_file, 'w') as log:
                log.write(f"Outer error: {str(e)}\n")
            return node, None, str(e)

    def cleanup_node(self, node, pod_name):
        """Cleanup debug pod for a single node"""
        log_file = self.logs_dir / f"{node.split('.')[0]}-cleanup.log"
        try:
            collector = SOSReportCollector(
                node_name=node,
                download_dir=str(self.download_dir),
                namespace=self.namespace
            )
            collector.debug_pod_name = pod_name

            # Log to file
            with open(log_file, 'w') as log:
                log.write(f"Cleaning up debug pod for {node}\n")
                log.flush()
                try:
                    collector.cleanup(force=True)
                    log.write(f"Debug pod cleaned up\n")
                    return node, True, None
                except Exception as e:
                    log.write(f"Error: {str(e)}\n")
                    return node, False, str(e)

        except Exception as e:
            with open(log_file, 'w') as log:
                log.write(f"Outer error: {str(e)}\n")
            return node, False, str(e)

    def run_phase(self, phase_name, task_func, nodes_data, show_progress=True):
        """
        Run a phase of collection in parallel

        Args:
            phase_name: Name of the phase for display
            task_func: Function to execute for each node
            nodes_data: Dictionary mapping node to task arguments
            show_progress: Whether to show progress updates

        Returns:
            Dictionary mapping node to (result, error)
        """
        self.safe_print(f"\n{Colors.BOLD}{'='*60}")
        self.safe_print(f"{phase_name}")
        self.safe_print(f"{'='*60}{Colors.RESET}")

        results = {}
        completed = 0
        total = len(nodes_data)

        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            # Submit all tasks
            future_to_node = {
                executor.submit(task_func, node, *args): node
                for node, args in nodes_data.items()
            }

            # Process completions
            for future in as_completed(future_to_node):
                node = future_to_node[future]
                try:
                    node_result, result, error = future.result()
                    results[node_result] = (result, error)

                    completed += 1

                    if show_progress:
                        if error:
                            self.safe_print(
                                f"{Colors.RED}[{completed}/{total}] ✗ {node}: {error}{Colors.RESET}"
                            )
                        else:
                            self.safe_print(
                                f"{Colors.GREEN}[{completed}/{total}] ✓ {node}{Colors.RESET}"
                            )

                except Exception as e:
                    results[node] = (None, str(e))
                    completed += 1
                    self.safe_print(
                        f"{Colors.RED}[{completed}/{total}] ✗ {node}: {str(e)}{Colors.RESET}"
                    )

        # Summary
        successes = sum(1 for r, e in results.values() if not e)
        failures = total - successes

        self.safe_print(f"\n{Colors.CYAN}Phase complete: {successes} succeeded, {failures} failed{Colors.RESET}")

        return results

    def run_collection(self):
        """Execute the complete multi-node collection workflow"""
        start_time = datetime.now()

        # Phase 1: Start debug pods
        self.results['debug_pods'] = self.run_phase(
            "Phase 1: Starting Debug Pods",
            self.start_debug_pod_for_node,
            {node: () for node in self.nodes}
        )

        # Filter nodes with successful debug pods
        nodes_with_pods = {
            node: (pod,)
            for node, (pod, error) in self.results['debug_pods'].items()
            if not error and pod
        }

        if not nodes_with_pods:
            self.safe_print(f"\n{Colors.RED}[ERROR] No debug pods started successfully. Exiting.{Colors.RESET}")
            return False

        # Phase 2: Collect SOS reports
        self.results['collections'] = self.run_phase(
            "Phase 2: Collecting SOS Reports",
            self.collect_report_for_node,
            nodes_with_pods
        )

        # Filter nodes with successful collections
        nodes_with_reports = {
            node: (nodes_with_pods[node][0], report)
            for node, (report, error) in self.results['collections'].items()
            if not error and report
        }

        if not nodes_with_reports:
            self.safe_print(f"\n{Colors.RED}[ERROR] No SOS reports collected successfully. Exiting.{Colors.RESET}")
            return False

        # Phase 3: Download reports
        self.results['downloads'] = self.run_phase(
            "Phase 3: Downloading Reports",
            self.download_report_for_node,
            nodes_with_reports
        )

        # Phase 4: Cleanup (if requested)
        if self.auto_cleanup:
            cleanup_nodes = {
                node: (pod,)
                for node, (pod,) in nodes_with_pods.items()
            }
            self.results['cleanups'] = self.run_phase(
                "Phase 4: Cleaning Up Debug Pods",
                self.cleanup_node,
                cleanup_nodes
            )

        # Display final summary
        self.display_summary(start_time)

        # Return success if at least one download succeeded
        successes = sum(
            1 for path, error in self.results['downloads'].values()
            if not error and path
        )
        return successes > 0

    def display_summary(self, start_time):
        """Display comprehensive summary report"""
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        self.safe_print(f"\n{Colors.BOLD}{'='*60}")
        self.safe_print("Multi-Node SOS Report Collection Summary")
        self.safe_print(f"{'='*60}{Colors.RESET}")

        self.safe_print(f"\n{Colors.CYAN}Total Nodes:{Colors.RESET} {len(self.nodes)}")
        self.safe_print(f"{Colors.CYAN}Total Duration:{Colors.RESET} {duration/60:.1f} minutes")

        # Count successes and failures
        downloads = self.results['downloads']
        successes = sum(1 for p, e in downloads.values() if not e and p)
        failures = len(self.nodes) - successes

        self.safe_print(f"\n{Colors.BOLD}Status:{Colors.RESET}")
        self.safe_print(f"  {Colors.GREEN}✓ Successful:{Colors.RESET} {successes} nodes")
        self.safe_print(f"  {Colors.RED}✗ Failed:{Colors.RESET} {failures} nodes")

        # Download status and locations
        if successes > 0:
            self.safe_print(f"\n{Colors.BOLD}{Colors.GREEN}Downloaded Reports:{Colors.RESET}")
            total_size = 0
            for node, (path, error) in downloads.items():
                if not error and path:
                    # Get file size (with defensive check)
                    file_path = Path(path)
                    if file_path.exists():
                        size_mb = file_path.stat().st_size / (1024 * 1024)
                    else:
                        size_mb = 0.0  # File may have been moved                    
                    total_size += size_mb
                    short_node = node.split('.')[0]
                    self.safe_print(f"  {Colors.GREEN}✓{Colors.RESET} {short_node:20s} → {path}")
                    self.safe_print(f"    {Colors.CYAN}Size:{Colors.RESET} {size_mb:.1f} MB")

            self.safe_print(f"\n  {Colors.BOLD}Total Downloaded:{Colors.RESET} {total_size:.1f} MB across {successes} nodes")
            self.safe_print(f"  {Colors.BOLD}Download Directory:{Colors.RESET} {self.download_dir}")

        # Failed collections
        if failures > 0:
            self.safe_print(f"\n{Colors.BOLD}{Colors.RED}Failed Collections:{Colors.RESET}")

            # Collect all nodes and their failure reasons
            failed_nodes = {}

            # Check debug pod failures
            for node, (pod, error) in self.results['debug_pods'].items():
                if error or not pod:
                    failed_nodes[node] = "Debug pod failed to start"

            # Check collection failures
            for node, (report, error) in self.results['collections'].items():
                if node not in failed_nodes and (error or not report):
                    failed_nodes[node] = error or "Collection failed"

            # Check download failures
            for node, (path, error) in downloads.items():
                if node not in failed_nodes and (error or not path):
                    failed_nodes[node] = error or "Download failed"

            for node, reason in failed_nodes.items():
                short_node = node.split('.')[0]
                self.safe_print(f"  {Colors.RED}✗{Colors.RESET} {short_node:20s} → {reason}")

        # Debug pods status
        if self.auto_cleanup:
            cleanup_results = self.results.get('cleanups', {})
            cleaned = sum(1 for success, _ in cleanup_results.values() if success)
            self.safe_print(f"\n{Colors.BOLD}Debug Pods:{Colors.RESET}")
            self.safe_print(f"  {Colors.GREEN}✓ Cleaned up:{Colors.RESET} {cleaned} pods (--cleanup flag was provided)")

            still_running = len(self.results['debug_pods']) - cleaned
            if still_running > 0:
                self.safe_print(f"  {Colors.YELLOW}⚠ Still running:{Colors.RESET} {still_running} pods (cleanup failed)")
        else:
            pods_created = sum(
                1 for pod, error in self.results['debug_pods'].values()
                if not error and pod
            )
            if pods_created > 0:
                self.safe_print(f"\n{Colors.BOLD}Debug Pods:{Colors.RESET}")
                self.safe_print(f"  {Colors.YELLOW}⚠ Still running:{Colors.RESET} {pods_created} pods (manual cleanup required)")

        # Next steps
        self.safe_print(f"\n{Colors.BOLD}Next Steps:{Colors.RESET}")

        if successes > 0:
            self.safe_print(f"  • Analyze collected reports:")
            self.safe_print(f"    /sosreport:analyze {self.download_dir}/sosreport-*.tar.xz")

        if failures > 0:
            self.safe_print(f"  • Check logs for failures:")
            self.safe_print(f"    cat {self.logs_dir}/<node-name>-*.log")
            self.safe_print(f"  • Retry failed nodes individually:")
            for node in list(failed_nodes.keys())[:2]:  # Show first 2
                short_node = node.split('.')[0]
                self.safe_print(f"    /sosreport:collector all {node}")

        # Only show cleanup guidance if we didn't auto-cleanup
        if not self.auto_cleanup:
            pods_created = sum(
                1 for pod, error in self.results['debug_pods'].values()
                if not error and pod
            )
            if pods_created > 0:
                self.safe_print(f"  • Cleanup debug pods:")
                for node, (pod, error) in list(self.results['debug_pods'].items())[:2]:
                    if not error and pod:
                        self.safe_print(f"    /sosreport:collector cleanup {node}")            

        self.safe_print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}\n")

def main():
    parser = argparse.ArgumentParser(
        description='Collect SOS reports from multiple OpenShift nodes in parallel',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect from multiple nodes
  %(prog)s worker-0.example.com worker-1.example.com worker-2.example.com

  # With case ID and auto-cleanup
  %(prog)s worker-{0..9}.example.com --case-id 12345678 --cleanup

  # Limit parallel collections
  %(prog)s worker-{0..19}.example.com --max-parallel 3

  # Custom namespace and timeout
  %(prog)s master-0.example.com master-1.example.com \\
    --namespace openshift-debug --plugin-timeout 1800
        """
    )

    parser.add_argument(
        'nodes',
        nargs='+',
        help='OpenShift node names (space-separated)'
    )
    parser.add_argument(
        '-d', '--download-dir',
        default='.work/sos-reports',
        help='Directory to store downloaded reports (default: .work/sos-reports)'
    )
    parser.add_argument(
        '-c', '--case-id',
        help='Red Hat case ID'
    )
    parser.add_argument(
        '-n', '--namespace',
        default='default',
        help='Namespace for debug pods (default: default)'
    )
    parser.add_argument(
        '-t', '--plugin-timeout',
        type=int,
        default=900,
        help='Timeout for each plugin in seconds (default: 900)'
    )
    parser.add_argument(
        '-p', '--max-parallel',
        type=int,
        default=5,
        help='Maximum number of parallel collections (default: 5)'
    )
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Automatically cleanup debug pods after collection'
    )

    args = parser.parse_args()

    # Validate minimum nodes
    if len(args.nodes) < 2:
        try:
            print(f"{Colors.YELLOW}[INFO] For single node collection, use /sosreport:collector instead{Colors.RESET}")
        except (ValueError, OSError):
            pass
        sys.exit(1)

    # Create collector
    collector = MultiNodeCollector(
        nodes=args.nodes,
        download_dir=args.download_dir,
        case_id=args.case_id,
        namespace=args.namespace,
        plugin_timeout=args.plugin_timeout,
        max_parallel=args.max_parallel,
        auto_cleanup=args.cleanup
    )

    # Validate prerequisites
    if not collector.validate_prerequisites():
        sys.exit(2)

    # Display plan and get confirmation
    if not collector.display_plan():
        try:
            print(f"\n{Colors.YELLOW}[INFO] Collection cancelled by user{Colors.RESET}")
        except (ValueError, OSError):
            pass
        sys.exit(0)

    # Run collection
    try:
        success = collector.run_collection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        try:
            print(f"\n{Colors.YELLOW}[WARNING] Interrupted by user{Colors.RESET}")
            print(f"{Colors.YELLOW}[WARNING] Debug pods may still be running{Colors.RESET}")
        except (ValueError, OSError):
            pass
        sys.exit(1)
    except Exception as e:
        try:
            print(f"\n{Colors.RED}[ERROR] Unexpected error: {e}{Colors.RESET}")
            import traceback
            traceback.print_exc()
        except (ValueError, OSError):
            pass
        sys.exit(1)


if __name__ == '__main__':
    main()
