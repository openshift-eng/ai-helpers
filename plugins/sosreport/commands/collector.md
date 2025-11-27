---
description: Collect SOS reports from one or more OpenShift nodes and download them locally
argument-hint: <command> <node-name(s)> [options]
---

## Name
sosreport:collector

## Synopsis

**Single-node mode:**
```
/sosreport:collector <command> <node-name> [--download-dir <path>] [--case-id <id>] [--namespace <ns>] [--plugin-timeout <seconds>] [--report-path <path>] [--force]
```

**Multi-node mode:**
```
/sosreport:collector multi <node1> <node2> [<node3> ...] [--download-dir <path>] [--case-id <id>] [--namespace <ns>] [--plugin-timeout <seconds>] [--max-parallel <num>] [--cleanup]
```

**Single-node Commands:**

- **`start`**: Start a debug pod on the target node
- **`collect`**: Collect SOS report from the node (requires debug pod)
- **`download`**: Download SOS report from debug pod to local machine
- **`list`**: List available SOS reports in the debug pod
- **`cleanup`**: Delete the debug pod
- **`all`**: Execute complete workflow (start → collect → download)

**Multi-node Command:**

- **`multi`**: Collect SOS reports from multiple nodes in parallel

## Description

The `sosreport:collector` command automates the collection of SOS reports from OpenShift nodes. It supports both single-node and multi-node collection modes.

**Single-node mode** creates a debug pod on the target node, executes the SOS report collection inside the node's environment using a toolbox container, and downloads the generated report to your local machine. This mode provides fine-grained control with separate commands for each step.

**Multi-node mode** collects SOS reports from multiple nodes in parallel, significantly reducing the total time required for cluster-wide diagnostics. Collections run simultaneously (up to a configurable limit), with independent error handling per node.

This command is particularly useful for collecting diagnostic data from OpenShift cluster nodes for troubleshooting purposes. The collected SOS reports can then be analyzed using `/sosreport:analyze`.

The command uses the OpenShift debug pod mechanism to access the node's host filesystem and execute the `sos report` command with appropriate plugins and options for OpenShift environments.

## Arguments

### Single-Node Mode Arguments

- `$1` (required): Command to execute - one of: `start`, `collect`, `download`, `list`, `cleanup`, `all`
- `$2` (required): OpenShift node name (e.g., `worker-0.example.com`)
- `--download-dir <path>` (optional): Directory to store downloaded reports (default: `.work/sos-reports`)
- `--case-id <id>` (optional): Red Hat case ID to associate with the SOS report
- `--namespace <ns>` (optional): Namespace for debug pod (default: `default`)
- `--plugin-timeout <seconds>` (optional): Timeout for each SOS plugin in seconds (default: 900)
- `--report-path <path>` (optional): Specific report path to download (for `download` command)
- `--force` (optional): Force cleanup without confirmation (for `cleanup` command)

### Multi-Node Mode Arguments

- `$1` (required): Must be `multi`
- `$2..$N` (required): Space-separated list of OpenShift node names (minimum 2 nodes)
- `--download-dir <path>` (optional): Directory to store downloaded reports (default: `.work/sos-reports`)
- `--case-id <id>` (optional): Red Hat case ID to associate with all SOS reports
- `--namespace <ns>` (optional): Namespace for debug pods (default: `default`)
- `--plugin-timeout <seconds>` (optional): Timeout for each SOS plugin in seconds (default: 900)
- `--max-parallel <num>` (optional): Maximum number of nodes to process in parallel (default: 5)
- `--cleanup` (optional): Automatically cleanup debug pods after collection completes

## Implementation

The implementation uses two Python helper scripts:
- **Single-node**: `plugins/sosreport/skills/scripts/sosreport-single-collector.py`
- **Multi-node**: `plugins/sosreport/skills/scripts/sosreport-multi-collector.py`

### 0. Route to Appropriate Mode

1. **Check first argument**
   - If `$1` is `multi`: Route to multi-node mode (Section 2)
   - Otherwise: Route to single-node mode (Section 1)

---

## Single-Node Mode Implementation

### 1. Parse Command-Line Arguments

1. **Extract and validate command**
   - Validate command is one of: `start`, `collect`, `download`, `list`, `cleanup`, `all`
   - If invalid command, display usage and valid commands

2. **Extract node name**
   - Second argument is the OpenShift node name (required)
   - Example: `worker-0.example.com`
   - If missing, return error with usage instructions

3. **Parse optional arguments**
   - `--download-dir`: Target directory for downloaded reports (default: `.work/sos-reports`)
   - `--case-id`: Red Hat case ID to tag the SOS report
   - `--namespace`: Kubernetes namespace for debug pod (default: `default`)
   - `--plugin-timeout`: Timeout per plugin in seconds (default: 900 seconds = 15 minutes)
   - `--report-path`: Specific report path for download command
   - `--force`: Skip confirmation for cleanup command

4. **Validate prerequisites**
   - Check if `oc` CLI is installed and available: `which oc`
   - Verify user is logged in to OpenShift cluster: `oc whoami`
   - If not logged in, provide instructions to login: `oc login`

### 2. Execute Single-Node Workflow

Call the Python helper script with the appropriate arguments:

```bash
python3 plugins/sosreport/skills/scripts/sosreport-single-collector.py \
  <command> <node-name> \
  [--download-dir <path>] \
  [--case-id <id>] \
  [--namespace <ns>] \
  [--plugin-timeout <seconds>] \
  [--report-path <path>] \
  [--force]
```

The helper script implements the following command workflows:

#### Command: `start`

1. **Check for existing debug pod**
   - Search for running debug pods for the node: `oc get pods -n <namespace> -o wide | grep <node-short-name> | grep debug | grep Running`
   - If found, inform user and provide option to use existing pod or delete it first

2. **Start new debug pod**
   - Launch debug pod: `oc debug node/<node-name> --to-namespace=<namespace> -- sleep 3600 &`
   - The pod runs `sleep 3600` to keep it alive for subsequent operations

3. **Wait for pod to be ready**
   - Poll for pod status every 2 seconds (max 30 attempts = 60 seconds)
   - Check if pod is in Running state
   - Display progress dots while waiting
   - Store pod name for subsequent commands

4. **Output**
   - Success: Display debug pod name
   - Failure: Exit with error if pod doesn't start within timeout

#### Command: `collect`

1. **Verify debug pod exists**
   - Get debug pod name: `oc get pods -n <namespace> -o wide | grep <node-short-name> | grep debug | grep Running`
   - If not found, inform user to run `start` command first

2. **Build SOS report command**
   - Base command: `sos report`
   - Enable OpenShift plugins: `-e openshift -e openshift_ovn -e openvswitch -e podman -e crio`
   - Enable detailed options: `-k crio.all=on -k crio.logs=on -k podman.all=on -k podman.logs=on`
   - Disable problematic options: `-k networking.ethtool-namespaces=off`
   - Add all logs: `--all-logs`
   - Set plugin timeout: `--plugin-timeout=<seconds>` (default: 900)
   - Non-interactive mode: `--batch`
   - Optionally add case ID: `--case-id=<case-id>`

3. **Execute SOS report collection**
   - Full command structure: `oc exec -n <namespace> <pod-name> -- chroot /host toolbox <sos-command>`
   - The command uses `chroot /host` to access the node's filesystem
   - Then enters `toolbox` container which has `sos` installed
   - Stream output in real-time to show progress
   - Set timeout: 1200 seconds (20 minutes)
   - Note: Some plugins (networking, networkmanager) may timeout - this is normal

4. **Parse output to find report path**
   - Look for patterns in output:
     - `Your sosreport has been generated and saved in: /var/tmp/sosreport-*.tar.xz`
     - `/var/tmp/sosreport-*.tar.xz`
     - `/host/var/tmp/sosreport-*.tar.xz`
   - If not found in output, list directory: `oc exec <pod> -- chroot /host ls -lt /var/tmp/sosreport-*.tar.xz | head -1`
   - Extract filename from listing
   - Store report path for download command

5. **Handle collection issues**
   - Warning on non-zero exit codes (often due to plugin timeouts, which is acceptable)
   - Inform user that some plugin timeouts are normal
   - Ensure report was created even if some plugins timed out

6. **Output**
   - Success: Display report path
   - Failure: Exit with error and diagnostics

#### Command: `download`

1. **Determine report to download**
   - If `--report-path` provided, use that path
   - Otherwise, list available reports and use the latest one
   - List command: `oc exec <pod> -- chroot /host ls -lh /var/tmp/sosreport-*.tar.xz`

2. **Ensure download directory exists**
   - Create download directory if it doesn't exist: `mkdir -p <download-dir>`

3. **Download the report with automatic fallback**

   The download uses a **3-tier fallback strategy** for maximum reliability:

   **Method 1: oc cp (standard method)**
   - Command: `oc cp -n <namespace> <pod-name>:/host<report-path> <local-path>`
   - Retry logic: 3 attempts with 2-second delays between retries
   - Timeout: 600 seconds (10 minutes) per attempt
   - Best for: Normal files, fastest method
   - Common issues: May fail with EOF errors on large files (>50MB) or network timeouts

   **Method 2: cat with redirect (fallback)**
   - Command: `oc exec <pod> -- cat /host<report-path> > <local-path>`
   - Timeout: 600 seconds (10 minutes)
   - Best for: Large files that timeout with oc cp
   - Advantages: Streams file content directly, handles large files better

   **Method 3: tar streaming (most robust)**
   - Command: `oc exec <pod> -- tar -C /host/var/tmp -cf - <filename> | tar -xOf - > <local-path>`
   - Timeout: 600 seconds (10 minutes)
   - Best for: Problematic files with corrupted transfers or persistent EOF errors
   - Advantages: Most reliable method, handles various failure scenarios

   The script automatically tries each method in sequence until one succeeds.

4. **Verify download**
   - Check if file exists locally
   - Validate file size is non-zero
   - Display file size in MB
   - Output full local path

5. **Output**
   - Success: Display download method used, local file path, and size
   - Failure: Exit with error if all 3 methods fail

6. **Progress indication**
   - Displays which download method is being attempted (1/3, 2/3, 3/3)
   - Shows retry attempts for Method 1 (oc cp)
   - Reports success or failure for each method
   - Clear indication of which method succeeded

#### Command: `list`

1. **Verify debug pod exists**
   - Get debug pod name
   - If not found, inform user

2. **List SOS reports in pod**
   - Execute: `oc exec <pod> -- chroot /host ls -lh /var/tmp/sosreport-*.tar.xz`
   - Display full listing with file sizes and timestamps
   - Extract filenames for reference

3. **Output**
   - Display table of available reports with sizes
   - If no reports found, inform user

#### Command: `cleanup`

1. **Verify debug pod exists**
   - Get debug pod name
   - If not found, inform user no cleanup needed

2. **Confirm deletion (unless --force)**
   - If `--force` not provided, ask user: "Are you sure you want to delete the debug pod? (yes/no):"
   - Wait for user confirmation
   - If not confirmed, cancel cleanup

3. **Delete debug pod**
   - Execute: `oc delete pod -n <namespace> <pod-name> --grace-period=0 --force`
   - Set timeout: 30 seconds

4. **Output**
   - Success: Confirm pod deleted
   - Warning: If deletion fails

#### Command: `all`

This command executes the complete workflow in sequence:

1. **Start debug pod** (see `start` command workflow)

2. **Collect SOS report** (see `collect` command workflow)
   - If collection fails, exit with error
   - Do not proceed to download

3. **Download report** (see `download` command workflow)
   - If download fails, exit with error
   - Debug pod remains active for troubleshooting

4. **Display success summary**
   ```
   ############################################################
   # SUCCESS - SOS Report Collection Complete
   # Duration: X seconds (Y minutes)
   # Report: /path/to/local/report.tar.xz
   ############################################################
   ```

5. **Output**
   - Total execution time
   - Local report path
   - Success status

### 3. Error Handling

1. **Command validation errors**
   - Invalid command: Display valid commands
   - Missing node name: Display usage

2. **Prerequisites errors**
   - `oc` not found: "Error: oc CLI not found. Please install OpenShift CLI"
   - Not logged in: "Error: Not logged in to OpenShift. Run: oc login <cluster-url>"
   - Node not found: "Error: Node '<node-name>' not found in cluster"

3. **Debug pod errors**
   - Pod failed to start: "Error: Debug pod failed to start within timeout"
   - Pod not found for collect/download: "Error: No debug pod found. Run 'start' command first"

4. **Collection errors**
   - SOS report timeout: "Warning: Collection timed out. Some plugins may not have completed"
   - SOS report not found: "Error: Could not locate SOS report. Check pod logs"

5. **Download errors**
   - No reports available: "Error: No SOS reports found to download"
   - Copy failed: "Error: Failed to download report. Check pod status and network"
   - File not found after copy: "Error: Download completed but file not found locally"

6. **General errors**
   - Network errors: Display error and suggest checking cluster connectivity
   - Permission errors: Display error and suggest checking RBAC permissions
   - Unexpected errors: Display full error message and traceback

### 4. Progress Indication

Provide clear progress indicators for long-running operations:

1. **Debug pod startup**: Display dots while waiting for pod
2. **SOS report collection**: Stream real-time output from sos command
3. **Download**: Display "Downloading..." message
4. **Cleanup**: Confirm action before execution (unless --force)

---

## Multi-Node Mode Implementation

### 1. Parse Command-Line Arguments

1. **Extract node names**
   - Parse all positional arguments after `multi` as node names
   - Minimum 2 nodes required
   - Remove duplicates if any
   - Example: `multi worker-0.example.com worker-1.example.com worker-2.example.com`

2. **Parse optional arguments**
   - `--download-dir`: Target directory for downloaded reports (default: `.work/sos-reports`)
   - `--case-id`: Red Hat case ID to tag all SOS reports
   - `--namespace`: Kubernetes namespace for debug pods (default: `default`)
   - `--plugin-timeout`: Timeout per plugin in seconds (default: 900)
   - `--max-parallel`: Maximum concurrent collections (default: 5)
   - `--cleanup`: Auto-cleanup debug pods flag

3. **Validate prerequisites**
   - Check if `oc` CLI is installed: `which oc`
   - Verify user is logged in: `oc whoami`
   - Verify all nodes exist: `oc get node <node-name>` for each
   - Create download directory if needed

4. **Display collection plan**
   - Show list of nodes to process
   - Display configuration (case ID, timeout, max parallel, cleanup)
   - Ask for user confirmation to proceed

### 2. Execute Multi-Node Workflow

Call the Python helper script:

```bash
python3 plugins/sosreport/skills/scripts/sosreport-multi-collector.py \
  <node1> <node2> [<node3> ...] \
  [--download-dir <path>] \
  [--case-id <id>] \
  [--namespace <ns>] \
  [--plugin-timeout <seconds>] \
  [--max-parallel <num>] \
  [--cleanup]
```

The script uses `concurrent.futures.ThreadPoolExecutor` for parallel execution across four phases:

#### Phase 1: Start Debug Pods (Parallel)

1. **Create thread pool** with `max_workers=max_parallel`
2. **Start debug pods in parallel**
   - For each node: `oc debug node/<node> --to-namespace=<namespace> -- sleep 3600 &`
   - Wait for each pod to reach Running state (60s timeout per pod)
   - Track success/failure for each node
3. **Report phase results**
   - Display which pods started successfully
   - Display which failed
   - Continue only with successful pods

#### Phase 2: Collect SOS Reports (Parallel)

1. **Collect reports in parallel** from all running debug pods
   - Command: `oc exec <pod> -- chroot /host toolbox sos report ...`
   - Stream output to per-node log files
   - Parse output to find report paths
2. **Monitor progress**
   - Display progress: X/Y nodes completed
   - Show which nodes are currently collecting
3. **Report phase results**
   - Display successful collections
   - Display failed/timed-out collections

#### Phase 3: Download Reports (Parallel)

1. **Download in parallel** all successful collections
   - Command: `oc cp <pod>:/host<report-path> <local-path>`
   - Verify downloads completed
2. **Report phase results**
   - Display downloaded files with sizes
   - Display failed downloads

#### Phase 4: Cleanup (Optional, Parallel)

If `--cleanup` flag provided:

1. **Delete debug pods in parallel**
   - `oc delete pod <pod> --grace-period=0 --force`
2. **Report cleanup results**

### 3. Final Summary Report

Display comprehensive summary:

```
============================================================
Multi-Node SOS Report Collection Summary
============================================================
Total Nodes: 10
Total Duration: 25 minutes

Status:
  ✓ Successful: 8 nodes
  ✗ Failed: 2 nodes

Successful Collections:
  worker-0 → .work/sos-reports/sosreport-worker-0-*.tar.xz (245 MB)
  ...

Failed Collections:
  worker-8 → Debug pod failed to start
  ...

Next Steps:
  • Analyze collected reports
  • Retry failed nodes
  • Cleanup remaining pods
============================================================
```

### 4. Error Handling

1. **Each node's collection is independent** - failures don't stop others
2. **All errors tracked and reported** in final summary
3. **Prerequisites errors** - exit early if oc not found or not logged in
4. **Resource constraints** - respect `--max-parallel` limit

### 5. Progress Indication

1. **Phase headers** - clear indication of current phase
2. **Progress bars** - show X/Y nodes completed
3. **Per-node logs** - saved to `.work/sos-reports/logs/<node>.log`
4. **Summary tables** - tabular output showing status per node

## Return Value

### Single-Node Mode

- **Format**: Command output displayed in terminal with progress indicators and status messages
- **Exit code**:
  - 0 if command executes successfully
  - 1 if command fails

**Outputs by command:**
- `download` and `all`: Local file path `<download-dir>/sosreport-<hostname>-<timestamp>.tar.xz`
- `list`: List of available reports with sizes and timestamps
- `start`: Debug pod name
- `collect`: Report path in pod `/var/tmp/sosreport-<hostname>-<timestamp>.tar.xz`

### Multi-Node Mode

- **Format**: Detailed progress output followed by comprehensive summary table
- **Exit code**:
  - 0 if at least one collection succeeds
  - 1 if all collections fail
  - 2 if prerequisites check fails

**Outputs:**
- Downloaded reports: `<download-dir>/sosreport-<hostname>-<timestamp>.tar.xz` for each successful collection
- Log files: `<download-dir>/logs/<node-name>.log` for each node
- Summary report on stdout showing success/failure status

## Examples

### Single-Node Examples

1. **Full workflow - collect and download in one command**:
   ```bash
   /sosreport:collector all worker-0.example.com
   ```
   
   This is the most common use case. It starts a debug pod, collects the SOS report, and downloads it to `.work/sos-reports/`.

2. **Full workflow with Red Hat case ID**:
   ```bash
   /sosreport:collector all worker-0.example.com --case-id 12345678
   ```
   
   Tags the SOS report with a Red Hat support case ID for easier tracking.

3. **Full workflow with custom download directory**:
   ```bash
   /sosreport:collector all worker-0.example.com --download-dir /tmp/sos-collection
   ```
   
   Downloads the report to a custom directory instead of the default `.work/sos-reports/`.

4. **Step-by-step workflow - start debug pod**:
   ```bash
   /sosreport:collector start worker-0.example.com
   ```
   
   Only starts the debug pod. Useful when you want to perform multiple collections or need to inspect the pod before collection.

5. **Step-by-step workflow - collect SOS report**:
   ```bash
   /sosreport:collector collect worker-0.example.com --case-id 12345678
   ```
   
   Collects SOS report from an already running debug pod. Useful when the pod was started earlier or collection was interrupted.

6. **Step-by-step workflow - download report**:
   ```bash
   /sosreport:collector download worker-0.example.com
   ```
   
   Downloads the latest available SOS report from the debug pod. Useful when collection completed but download was interrupted.

7. **List available reports**:
   ```bash
   /sosreport:collector list worker-0.example.com
   ```
   
   Lists all SOS reports available in the debug pod. Useful when multiple reports exist and you want to see what's available.

8. **Download specific report**:
   ```bash
   /sosreport:collector download worker-0.example.com --report-path /var/tmp/sosreport-xxx-2024-01-15.tar.xz
   ```
   
   Downloads a specific report by path. Useful when multiple reports exist and you want a specific one.

9. **Clean up debug pod**:
   ```bash
   /sosreport:collector cleanup worker-0.example.com
   ```
   
   Deletes the debug pod after collection is complete. Prompts for confirmation.

10. **Force cleanup without confirmation**:
    ```bash
    /sosreport:collector cleanup worker-0.example.com --force
    ```
    
    Deletes the debug pod without prompting for confirmation. Useful in automated workflows.

11. **Custom plugin timeout for slow nodes**:
    ```bash
    /sosreport:collector all worker-0.example.com --plugin-timeout 1800
    ```
    
    Increases plugin timeout to 30 minutes (1800 seconds) for nodes with slow I/O or many containers.

12. **Collect from node in specific namespace**:
    ```bash
    /sosreport:collector all worker-0.example.com --namespace openshift-debug
    ```
    
    Creates debug pod in a custom namespace instead of `default`.

13. **Complete workflow with all options**:
    ```bash
    /sosreport:collector all worker-0.example.com \
      --download-dir /data/sos-reports \
      --case-id 12345678 \
      --namespace openshift-debug \
      --plugin-timeout 1800
    ```
    
    Full collection with custom directory, case ID, namespace, and plugin timeout.

14. **Workflow with analysis**:
    ```bash
    # Collect the report
    /sosreport:collector all worker-0.example.com

    # Analyze the downloaded report
    /sosreport:analyze .work/sos-reports/sosreport-*.tar.xz
    ```

    Complete workflow: collect SOS report from node and immediately analyze it.

### Multi-Node Examples

1. **Collect from multiple worker nodes**:
   ```bash
   /sosreport:collector multi worker-0.example.com worker-1.example.com worker-2.example.com
   ```

   Collects SOS reports from 3 worker nodes in parallel with default settings.

2. **Full cluster collection with case ID and auto-cleanup**:
   ```bash
   /sosreport:collector multi \
     master-{0..2}.example.com \
     worker-{0..9}.example.com \
     --case-id 12345678 \
     --cleanup
   ```

   Collects from all cluster nodes (3 masters + 10 workers) and automatically cleans up debug pods.

3. **Limited parallel collections**:
   ```bash
   /sosreport:collector multi worker-{0..19}.example.com --max-parallel 3
   ```

   Collects from 20 nodes but only runs 3 collections simultaneously to avoid overwhelming the cluster.

4. **Custom timeout for slow nodes**:
   ```bash
   /sosreport:collector multi worker-0.example.com worker-1.example.com --plugin-timeout 1800
   ```

   Increases plugin timeout to 30 minutes for nodes with many containers or slow I/O.

5. **Custom namespace**:
   ```bash
   /sosreport:collector multi master-0.example.com master-1.example.com master-2.example.com \
     --namespace openshift-debug
   ```

   Creates debug pods in a custom namespace instead of `default`.

6. **Multi-node with analysis**:
   ```bash
   # Collect from multiple nodes
   /sosreport:collector multi worker-0.example.com worker-1.example.com worker-2.example.com --cleanup

   # Analyze specific node
   /sosreport:analyze .work/sos-reports/sosreport-worker-1-*.tar.xz --only logs

   # Ask comparative questions
   # "Compare memory usage across all three worker nodes"
   # "Which node has the most OOM killer events?"
   ```

   Complete workflow: collect from multiple nodes and perform comparative analysis.

7. **Using node list from command**:
   ```bash
   # Get all NotReady nodes
   /sosreport:collector multi $(oc get nodes -o name --no-headers | grep worker | sed 's/node\///') \
     --case-id 12345678
   ```

   Dynamically collect from nodes matching specific criteria.

## Notes

### General (All Modes)

- **Collection time**: SOS report collection typically takes 10-30 minutes per node depending on node size and number of containers
- **Plugin timeouts**: Some plugins (networking, networkmanager) commonly timeout - this is normal and the report is still useful
- **Storage**: SOS reports can be large (100MB - 2GB+). Ensure sufficient disk space in download directory
- **OpenShift plugins**: Automatically enables relevant OpenShift plugins (openshift, openshift_ovn, openvswitch, podman, crio)
- **Container logs**: Collects container logs with `-k crio.logs=on -k podman.logs=on`
- **All logs**: Uses `--all-logs` to capture complete log history
- **Case ID**: Optional but recommended for Red Hat support cases
- **Batch mode**: Always uses `--batch` for non-interactive execution

### Single-Node Mode Specific

- **Debug pod persistence**: The debug pod remains running between commands to allow multiple operations (collect, list, download) without recreating the pod each time
- **First time collection**: Use `all` command for simplicity
- **Multiple collections**: Use `start` once, then multiple `collect` commands, then `cleanup`
- **Network issues**: Use step-by-step workflow to retry individual steps on failure

### Node Access

- **RBAC permissions**: User must have permissions to:
  - Create debug pods in the target namespace
  - Execute commands in pods
  - Copy files from pods
- **Node selection**: Use full node name from `oc get nodes`
- **Node status**: Works with nodes in any status (Ready, NotReady, SchedulingDisabled)

### Multi-Node Mode Specific

- **Parallel execution**: Collections run simultaneously up to `--max-parallel` limit (default: 5)
- **Time savings**: With 5 parallel collections, collecting from 10 nodes takes ~2x the time of 1 node instead of 10x
- **Independent processing**: Each node's collection is independent - failures don't stop other collections
- **Resource usage**: Each collection uses memory/CPU on both local machine and cluster
- **Max parallel recommendations**:
  - 3-5 for typical clusters
  - 1-2 for small/constrained clusters
  - Reduce if failures occur
- **Disk space**: Ensure at least 2GB free per node being collected
- **Per-node logs**: Detailed logs saved to `.work/sos-reports/logs/<node-name>.log`
- **Auto-cleanup**: Use `--cleanup` flag to automatically remove debug pods after collection

### Troubleshooting

**Single-Node Mode:**
- **Pod startup fails**: Check node status with `oc get node <node-name>` and verify RBAC permissions
- **Collection hangs**: Increase `--plugin-timeout` for slow nodes or those with many containers
- **Download fails with EOF error**: The script automatically tries 3 download methods (oc cp → cat → tar). If oc cp fails with "unexpected EOF", it will automatically retry with cat or tar streaming. No manual intervention needed.
- **All download methods fail**: Verify pod is still running with `oc get pod -n <namespace> <pod-name>`. The download includes retry logic and automatic fallback, so if all methods fail, the issue is likely pod termination or file corruption.
- **Report not found**: Check pod logs with `oc logs -n <namespace> <pod-name>`

**Multi-Node Mode:**
- **Many failures**: Reduce `--max-parallel` to 2-3
- **Timeout issues**: Increase `--plugin-timeout` to 1800 (30 minutes)
- **Download failures**: The enhanced download automatically tries 3 methods per node. Check `.work/sos-reports/logs/<node-name>-download.log` to see which methods were attempted.
- **Out of resources**: Reduce `--max-parallel` or collect in batches
- **Check logs**: Review `.work/sos-reports/logs/<node-name>.log` for detailed errors

**All Modes:**
- **Permission denied**: Verify you have cluster-admin or equivalent permissions for debug pods

**Download Method Selection:**
- **Method 1 (oc cp)**: Fastest but may fail with EOF on large files (>50MB)
- **Method 2 (cat)**: Automatic fallback, handles large files well
- **Method 3 (tar)**: Most robust, used as last resort for problematic transfers
- The script automatically selects the best method that works for your file

## Prerequisites

1. **OpenShift CLI (oc)**
   - Check: `which oc`
   - Install: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html
   - Verify version: `oc version`

2. **Cluster access**
   - Must be logged in to OpenShift cluster: `oc whoami`
   - Login if needed: `oc login <cluster-api-url>`
   - Verify cluster connectivity: `oc cluster-info`

3. **Python 3**
   - Check: `which python3`
   - Required for helper script
   - Usually pre-installed on Linux/macOS

4. **Permissions**
   - Ability to create debug pods (usually requires cluster-admin or equivalent)
   - Verify: `oc auth can-i create pods --as-namespace=<namespace>`
   - Verify: `oc auth can-i debug node/<node-name>`

5. **Disk space**
   - Local: At least 2GB free for downloaded reports
   - Check: `df -h <download-dir>`

## See Also

### Related Commands
- **sosreport:analyze**: Analyze downloaded SOS reports - `plugins/sosreport/commands/analyze.md`

### Helper Scripts
- **Single-Node Collector**: Python implementation - `plugins/sosreport/skills/scripts/sosreport-single-collector.py`
- **Multi-Node Collector**: Python parallel implementation - `plugins/sosreport/skills/scripts/sosreport-multi-collector.py`

### External Resources
- **sosreport documentation**: https://github.com/sosreport/sos
- **OpenShift debug documentation**: https://docs.openshift.com/container-platform/latest/support/troubleshooting/investigating-pod-issues.html#debugging-node-issues
- **Red Hat sosreport guide**: https://access.redhat.com/solutions/3592
- **OpenShift CLI reference**: https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/developer-cli-commands.html

### Complete Workflow Example

```bash
# 1. Collect SOS report from node
/sosreport:collector all worker-0.example.com --case-id 12345678

# Output: Downloaded to .work/sos-reports/sosreport-worker-0-2024-01-15.tar.xz

# 2. Analyze the collected report
/sosreport:analyze .work/sos-reports/sosreport-worker-0-2024-01-15.tar.xz

# Output: Interactive analysis showing issues, resource usage, errors, etc.

# 3. Ask follow-up questions
# "Show me more details about the memory issues"
# "What caused the kubelet service to fail?"
# "Analyze the network timeouts"

# 4. Clean up (if debug pod still running)
/sosreport:collector cleanup worker-0.example.com
```

