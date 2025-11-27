#!/usr/bin/env python3
"""
OpenShift SOS Report Collector
Automates the collection of SOS reports from OpenShift nodes and downloads them locally.
"""

import subprocess
import sys
import time
import re
import argparse
from pathlib import Path
from datetime import datetime


class SOSReportCollector:
    def __init__(self, node_name, download_dir=".work/sos-reports", case_id=None, namespace="default", plugin_timeout=900):
        """
        Initialize the SOS Report Collector

        Args:
            node_name: OpenShift node name (e.g., worker-0.example.com)
            download_dir: Local directory to store downloaded reports
            case_id: Optional Red Hat case ID
            namespace: Namespace for debug pod (default: default)
            plugin_timeout: Timeout for each plugin in seconds (default: 900)
        """
        self.node_name = node_name
        self.download_dir = Path(download_dir)
        self.case_id = case_id

        # Validate and sanitize namespace to prevent shell injection
        # Kubernetes namespace must be a valid DNS label (alphanumeric, hyphens, max 63 chars)
        if not re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', namespace) or len(namespace) > 63:
            raise ValueError(f"Invalid namespace: {namespace}. Must be a valid Kubernetes namespace name.")
        self.namespace = namespace

        self.plugin_timeout = plugin_timeout
        self.debug_pod_name = None
        self.sos_report_path = None

        # Create download directory if it doesn't exist
        self.download_dir.mkdir(parents=True, exist_ok=True)
    
    def run_command(self, cmd, timeout=None, check=True, stream_output=False):
        """Execute a shell command and return output"""
        print(f"\n[CMD] {cmd}")
        try:
            if stream_output:
                # Stream output in real-time for long-running commands
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                output_lines = []
                for line in process.stdout:
                    print(line, end='')
                    output_lines.append(line)
                
                process.wait(timeout=timeout)
                stdout = ''.join(output_lines)
                stderr = ''
                returncode = process.returncode
            else:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=check
                )
                stdout = result.stdout
                stderr = result.stderr
                returncode = result.returncode
            
            return stdout, stderr, returncode
        except subprocess.TimeoutExpired:
            print(f"[ERROR] Command timed out after {timeout} seconds")
            raise
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Command failed with exit code {e.returncode}")
            print(f"[ERROR] stderr: {e.stderr}")
            raise
    
    def get_debug_pod_name(self):
        """Get the debug pod name for a node"""
        # Extract short node name
        short_name = self.node_name.split('.')[0]

        # Use oc get with field selector instead of grep to avoid shell injection
        # Get all pods and filter in Python instead of using shell pipes
        try:
            result = subprocess.run(
                ["oc", "get", "pods", "-n", self.namespace, "-o", "wide", "--no-headers"],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                # Filter for pods containing short node name, "debug", and "Running"
                for line in result.stdout.strip().split('\n'):
                    if line and short_name in line and 'debug' in line and 'Running' in line:
                        # Extract pod name from first column
                        pod_name = line.strip().split()[0]
                        return pod_name
        except Exception:
            pass

        return None
    
    def start_debug_pod(self):
        """Start an oc debug pod on the target node"""
        print(f"\n{'='*60}")
        print(f"Starting debug pod on node: {self.node_name}")
        print(f"{'='*60}")
        
        # Check if debug pod already exists
        existing_pod = self.get_debug_pod_name()
        if existing_pod:
            print(f"[INFO] Debug pod already exists: {existing_pod}")
            print(f"[INFO] Use this pod or delete it first with: oc delete pod -n {self.namespace} {existing_pod}")
            self.debug_pod_name = existing_pod
            return existing_pod
        
        # Start new debug pod
        # Note: We need to run this in the background, so we use Popen with nohup/background handling
        subprocess.Popen(
            ["oc", "debug", f"node/{self.node_name}", f"--to-namespace={self.namespace}", "--", "sleep", "3600"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True  # Detach from parent session (equivalent to & in shell)
        )
        
        # Wait for pod to start
        print("[INFO] Waiting for debug pod to start...")
        for i in range(30):
            time.sleep(2)
            pod_name = self.get_debug_pod_name()
            if pod_name:
                self.debug_pod_name = pod_name
                print(f"[SUCCESS] Debug pod started: {self.debug_pod_name}")
                return self.debug_pod_name
            print(".", end="", flush=True)
        
        raise RuntimeError("Failed to start debug pod within timeout")
    
    def collect_sos_report(self):
        """Execute SOS report collection inside the debug pod"""
        print(f"\n{'='*60}")
        print(f"Collecting SOS report...")
        print(f"{'='*60}")
        
        if not self.debug_pod_name:
            self.debug_pod_name = self.get_debug_pod_name()
            if not self.debug_pod_name:
                print("[ERROR] No debug pod found. Run with 'collect' command first.")
                return None
        
        # Build the sos report command
        # Based on the document, the working command structure is:
        # chroot /host -> toolbox -> sos report
        sos_cmd = "sos report -e openshift -e openshift_ovn -e openvswitch -e podman -e crio "
        sos_cmd += "-k crio.all=on -k crio.logs=on -k podman.all=on -k podman.logs=on "
        sos_cmd += "-k networking.ethtool-namespaces=off --all-logs "
        sos_cmd += f"--plugin-timeout={self.plugin_timeout} --batch"
        
        # Add case ID if provided
        if self.case_id:
            sos_cmd += f" --case-id={self.case_id}"
        
        # Build the full command with proper escaping
        # The command runs: chroot -> enters toolbox container -> runs sos report
        full_sos_cmd = f'chroot /host toolbox {sos_cmd}'
        
        # Execute sos report command
        exec_cmd = f"oc exec -n {self.namespace} {self.debug_pod_name} -- {full_sos_cmd}"
        
        print("[INFO] This may take several minutes (up to 30 minutes)...")
        print("[INFO] Collecting diagnostic data from the node...")
        print(f"[INFO] Plugin timeout set to: {self.plugin_timeout} seconds (15 minutes)")
        print("[INFO] Note: Some plugins (networking, networkmanager) may timeout - this is normal")
        print("[INFO] Streaming output:\n")
        
        try:
            stdout, stderr, returncode = self.run_command(
                exec_cmd,
                timeout=1200,  # 20 minutes timeout
                check=False,
                stream_output=True
            )
            
            if returncode != 0:
                print(f"\n[WARNING] SOS report command returned code {returncode}")
                print("[INFO] This may be due to plugin timeouts, which is often acceptable")
            
            # Parse output to find the report path
            output = stdout + stderr
            
            # Look for various patterns of the sosreport path
            patterns = [
                r'Your sosreport has been generated and saved in:\s+(/var/tmp/sosreport-[^\s]+\.tar\.xz)',
                r'(/var/tmp/sosreport-[^\s]+\.tar\.xz)',
                r'/host(/var/tmp/sosreport-[^\s]+\.tar\.xz)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, output)
                if match:
                    self.sos_report_path = match.group(1)
                    # Remove /host prefix if present
                    if self.sos_report_path.startswith('/host'):
                        self.sos_report_path = self.sos_report_path[5:]
                    print(f"\n[SUCCESS] SOS report created: {self.sos_report_path}")
                    return self.sos_report_path
            
            # If no match found, try to list the /var/tmp directory
            print("\n[WARNING] Could not parse SOS report path from output")
            print("[INFO] Attempting to find report in /var/tmp...")
            
            list_cmd = f"oc exec -n {self.namespace} {self.debug_pod_name} -- chroot /host ls -lt /var/tmp/sosreport-*.tar.xz 2>/dev/null | head -1"
            stdout, stderr, returncode = self.run_command(list_cmd, check=False)
            
            if returncode == 0 and stdout.strip():
                # Extract filename from ls output
                filename = stdout.strip().split()[-1]
                self.sos_report_path = f"/var/tmp/{filename}"
                print(f"[SUCCESS] Found SOS report: {self.sos_report_path}")
                return self.sos_report_path
            
            print("[ERROR] Could not find SOS report")
            return None
            
        except subprocess.TimeoutExpired:
            print("\n[ERROR] SOS report collection timed out")
            return None
        except Exception as e:
            print(f"\n[ERROR] Failed to collect SOS report: {e}")
            return None
    
    def list_sos_reports(self):
        """List available SOS reports in the debug pod"""
        print(f"\n{'='*60}")
        print(f"Listing SOS reports...")
        print(f"{'='*60}")
        
        if not self.debug_pod_name:
            self.debug_pod_name = self.get_debug_pod_name()
            if not self.debug_pod_name:
                print("[ERROR] No debug pod found")
                return []
        
        cmd = f"oc exec -n {self.namespace} {self.debug_pod_name} -- chroot /host ls -lh /var/tmp/sosreport-*.tar.xz 2>/dev/null"
        stdout, stderr, returncode = self.run_command(cmd, check=False)
        
        if returncode != 0 or not stdout.strip():
            print("[INFO] No SOS reports found in /var/tmp/")
            return []
        
        print("\nAvailable SOS reports:")
        print(stdout)
        
        # Extract filenames
        reports = []
        for line in stdout.strip().split('\n'):
            if 'sosreport-' in line:
                filename = line.split()[-1]
                reports.append(filename)
        
        return reports
    
    def download_report(self, report_path=None):
        """Download the SOS report from the debug pod with enhanced error handling and fallback methods"""
        if report_path:
            self.sos_report_path = report_path

        if not self.sos_report_path:
            # Try to find the latest report
            reports = self.list_sos_reports()
            if not reports:
                print("[ERROR] No SOS reports found to download")
                return None

            # Use the first (latest) report
            self.sos_report_path = f"/var/tmp/{reports[0]}"
            print(f"[INFO] Using latest report: {self.sos_report_path}")

        print(f"\n{'='*60}")
        print(f"Downloading SOS report...")
        print(f"{'='*60}")

        if not self.debug_pod_name:
            self.debug_pod_name = self.get_debug_pod_name()
            if not self.debug_pod_name:
                print("[ERROR] No debug pod found")
                return None

        # Extract filename from path
        filename = Path(self.sos_report_path).name
        local_path = self.download_dir / filename

        # The path in the pod includes /host prefix
        pod_path = f"/host{self.sos_report_path}"

        print(f"[INFO] Downloading {filename}...")
        print(f"[INFO] Source: {self.debug_pod_name}:{pod_path}")
        print(f"[INFO] Destination: {local_path}")

        # Method 1: Try oc cp first (standard method)
        print("\n[INFO] Attempting download using oc cp (method 1/3)...")
        success = self._download_via_oc_cp(pod_path, local_path)
        if success:
            return str(local_path)

        # Method 2: Try cat with redirect (fallback for large files that timeout with oc cp)
        print("\n[INFO] oc cp failed, trying cat with redirect (method 2/3)...")
        success = self._download_via_cat(pod_path, local_path)
        if success:
            return str(local_path)

        # Method 3: Try tar streaming (fallback for EOF errors)
        print("\n[INFO] cat redirect failed, trying tar streaming (method 3/3)...")
        success = self._download_via_tar(pod_path, local_path)
        if success:
            return str(local_path)

        print("\n[ERROR] All download methods failed")
        return None

    def _download_via_oc_cp(self, pod_path, local_path, max_retries=3):
        """Download using oc cp command with retry logic"""
        for attempt in range(1, max_retries + 1):
            try:
                print(f"[INFO] Attempt {attempt}/{max_retries}...")
                cp_cmd = f"oc cp -n {self.namespace} {self.debug_pod_name}:{pod_path} {local_path}"
                stdout, stderr, returncode = self.run_command(cp_cmd, timeout=600, check=False)

                if returncode == 0 and local_path.exists() and local_path.stat().st_size > 0:
                    size_mb = local_path.stat().st_size / (1024 * 1024)
                    print(f"[SUCCESS] Downloaded via oc cp: {local_path} ({size_mb:.2f} MB)")
                    return True
                else:
                    error_msg = stderr if stderr else stdout
                    print(f"[WARNING] Attempt {attempt} failed: {error_msg}")
                    if attempt < max_retries:
                        print(f"[INFO] Retrying in 2 seconds...")
                        time.sleep(2)
            except Exception as e:
                print(f"[WARNING] Attempt {attempt} failed with exception: {e}")
                if attempt < max_retries:
                    print(f"[INFO] Retrying in 2 seconds...")
                    time.sleep(2)

        return False

    def _download_via_cat(self, pod_path, local_path):
        """Download using cat with redirect (works better for large files)"""
        try:
            cat_cmd = f"oc exec -n {self.namespace} {self.debug_pod_name} -- cat {pod_path} > {local_path}"
            stdout, stderr, returncode = self.run_command(cat_cmd, timeout=600, check=False)

            if local_path.exists() and local_path.stat().st_size > 0:
                size_mb = local_path.stat().st_size / (1024 * 1024)
                print(f"[SUCCESS] Downloaded via cat redirect: {local_path} ({size_mb:.2f} MB)")
                return True
            else:
                print(f"[WARNING] cat redirect failed or produced empty file")
                return False
        except Exception as e:
            print(f"[WARNING] cat redirect failed with exception: {e}")
            return False

    def _download_via_tar(self, pod_path, local_path):
        """Download using tar streaming (most reliable for large files)"""
        try:
            # Get the directory and filename
            pod_dir = str(Path(pod_path).parent)
            filename = Path(pod_path).name

            # Use tar to stream the file
            tar_cmd = f"oc exec -n {self.namespace} {self.debug_pod_name} -- tar -C {pod_dir} -cf - {filename} | tar -xOf - > {local_path}"
            print(f"[INFO] Using tar streaming from {pod_dir}/{filename}")
            stdout, stderr, returncode = self.run_command(tar_cmd, timeout=600, check=False)

            if local_path.exists() and local_path.stat().st_size > 0:
                size_mb = local_path.stat().st_size / (1024 * 1024)
                print(f"[SUCCESS] Downloaded via tar streaming: {local_path} ({size_mb:.2f} MB)")
                return True
            else:
                print(f"[WARNING] tar streaming failed or produced empty file")
                return False
        except Exception as e:
            print(f"[WARNING] tar streaming failed with exception: {e}")
            return False
    
    def cleanup(self, force=False):
        """Clean up the debug pod"""
        if not self.debug_pod_name:
            self.debug_pod_name = self.get_debug_pod_name()
            if not self.debug_pod_name:
                print("[INFO] No debug pod found to clean up")
                return
        
        print(f"\n{'='*60}")
        print(f"Cleaning up debug pod: {self.debug_pod_name}")
        print(f"{'='*60}")
        
        if not force:
            response = input("Are you sure you want to delete the debug pod? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("[INFO] Cleanup cancelled")
                return
        
        cmd = f"oc delete pod -n {self.namespace} {self.debug_pod_name} --grace-period=0 --force"
        try:
            self.run_command(cmd, timeout=30, check=False)
            print(f"[SUCCESS] Debug pod deleted: {self.debug_pod_name}")
        except Exception as e:
            print(f"[WARNING] Failed to delete debug pod: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Collect and download SOS reports from OpenShift nodes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  start      Start a debug pod on the node
  collect    Collect SOS report (requires debug pod)
  download   Download SOS report from debug pod
  list       List available SOS reports in debug pod
  cleanup    Delete the debug pod
  all        Execute all steps: start -> collect -> download

Examples:
  # Full workflow (start + collect + download)
  %(prog)s all worker-0.example.com
  
  # Step by step workflow
  %(prog)s start worker-0.example.com
  %(prog)s collect worker-0.example.com
  %(prog)s download worker-0.example.com
  %(prog)s cleanup worker-0.example.com
  
  # List available reports
  %(prog)s list worker-0.example.com
  
  # Download specific report
  %(prog)s download worker-0.example.com --report-path /var/tmp/sosreport-xxx.tar.xz
  
  # With Red Hat case ID
  %(prog)s collect worker-0.example.com -c 12345678
        """
    )
    
    parser.add_argument(
        'command',
        choices=['start', 'collect', 'download', 'list', 'cleanup', 'all'],
        help='Command to execute'
    )
    parser.add_argument(
        'node',
        help='OpenShift node name (e.g., worker-0.example.com)'
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
        help='Namespace for debug pod (default: default)'
    )
    parser.add_argument(
        '-r', '--report-path',
        help='Specific report path to download (e.g., /var/tmp/sosreport-xxx.tar.xz)'
    )
    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help='Force cleanup without confirmation'
    )
    parser.add_argument(
        '-t', '--plugin-timeout',
        type=int,
        default=900,
        help='Timeout for each plugin in seconds (default: 900)'
    )
    
    args = parser.parse_args()
    
    # Create collector
    collector = SOSReportCollector(
        node_name=args.node,
        download_dir=args.download_dir,
        case_id=args.case_id,
        namespace=args.namespace,
        plugin_timeout=args.plugin_timeout
    )
    
    start_time = datetime.now()
    success = False
    
    try:
        if args.command == 'start':
            print(f"\n{'#'*60}")
            print(f"# Starting Debug Pod")
            print(f"# Node: {args.node}")
            print(f"{'#'*60}")
            collector.start_debug_pod()
            success = True
            
        elif args.command == 'collect':
            print(f"\n{'#'*60}")
            print(f"# Collecting SOS Report")
            print(f"# Node: {args.node}")
            print(f"{'#'*60}")
            report_path = collector.collect_sos_report()
            success = report_path is not None
            
        elif args.command == 'download':
            print(f"\n{'#'*60}")
            print(f"# Downloading SOS Report")
            print(f"# Node: {args.node}")
            print(f"{'#'*60}")
            local_file = collector.download_report(args.report_path)
            success = local_file is not None
            
        elif args.command == 'list':
            print(f"\n{'#'*60}")
            print(f"# Listing SOS Reports")
            print(f"# Node: {args.node}")
            print(f"{'#'*60}")
            collector.list_sos_reports()  # Output is printed inside the method
            success = True
            
        elif args.command == 'cleanup':
            collector.cleanup(force=args.force)
            success = True
            
        elif args.command == 'all':
            print(f"\n{'#'*60}")
            print(f"# Full SOS Report Collection Workflow")
            print(f"# Node: {args.node}")
            print(f"# Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'#'*60}")
            
            # Step 1: Start debug pod
            collector.start_debug_pod()
            
            # Step 2: Collect SOS report
            report_path = collector.collect_sos_report()
            if not report_path:
                print("\n[ERROR] Failed to collect SOS report")
                sys.exit(1)
            
            # Step 3: Download report
            local_file = collector.download_report()
            if not local_file:
                print("\n[ERROR] Failed to download SOS report")
                sys.exit(1)
            
            # Success summary
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"\n{'#'*60}")
            print(f"# SUCCESS - SOS Report Collection Complete")
            print(f"# Duration: {duration:.0f} seconds ({duration/60:.1f} minutes)")
            print(f"# Report: {local_file}")
            print(f"{'#'*60}\n")
            
            success = True
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n[WARNING] Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()