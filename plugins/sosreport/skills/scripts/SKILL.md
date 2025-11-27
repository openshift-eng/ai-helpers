---
name: SOS Report Collector Scripts
description: Helper scripts for collecting SOS reports from OpenShift nodes (single and multi-node)
---

# SOS Report Collector Scripts

This directory contains helper scripts used by the sosreport plugin commands.

## Overview

The scripts in this directory provide automation for collecting diagnostic data from OpenShift cluster nodes. They are called by the `/sosreport:collector` command to handle the technical implementation of SOS report collection in both single-node and multi-node modes.

## Scripts

### sosreport-single-collector.py

A Python script that automates the collection of SOS reports from a single OpenShift node using debug pods.

**Purpose:**
- Creates and manages debug pods on OpenShift nodes
- Executes SOS report collection commands inside the node's environment
- Downloads collected reports to the local machine
- Handles the complete workflow lifecycle

**Features:**
- Multiple commands: `start`, `collect`, `download`, `list`, `cleanup`, `all`
- Supports Red Hat case ID tagging
- Configurable plugin timeouts
- Progress tracking and error handling
- Real-time output streaming during collection

**Usage:**

The script is invoked by the `/sosreport:collector` command for single-node operations. It can also be used standalone:

```bash
# Full workflow
python3 plugins/sosreport/skills/scripts/sosreport-single-collector.py \
  all worker-0.example.com \
  --case-id 12345678 \
  --download-dir .work/sos-reports

# Step-by-step workflow
python3 plugins/sosreport/skills/scripts/sosreport-single-collector.py \
  start worker-0.example.com

python3 plugins/sosreport/skills/scripts/sosreport-single-collector.py \
  collect worker-0.example.com \
  --case-id 12345678

python3 plugins/sosreport/skills/scripts/sosreport-single-collector.py \
  download worker-0.example.com

python3 plugins/sosreport/skills/scripts/sosreport-single-collector.py \
  cleanup worker-0.example.com
```

**Arguments:**

- `command` (positional, required): One of `start`, `collect`, `download`, `list`, `cleanup`, `all`
- `node` (positional, required): OpenShift node name
- `-d, --download-dir`: Directory for downloaded reports (default: `.work/sos-reports`)
- `-c, --case-id`: Red Hat case ID
- `-n, --namespace`: Namespace for debug pod (default: `default`)
- `-r, --report-path`: Specific report path to download
- `-f, --force`: Force cleanup without confirmation
- `-t, --plugin-timeout`: Timeout per plugin in seconds (default: 900)

**Implementation Details:**

The script uses the `SOSReportCollector` class which provides:

1. **Debug Pod Management**
   - `start_debug_pod()`: Creates debug pod with `oc debug node/<node> -- sleep 3600`
   - `get_debug_pod_name()`: Finds existing debug pod for a node
   - `cleanup()`: Deletes the debug pod

2. **SOS Report Collection**
   - `collect_sos_report()`: Executes `chroot /host toolbox sos report` with OpenShift plugins
   - Uses plugins: openshift, openshift_ovn, openvswitch, podman, crio
   - Enables detailed logging with `-k crio.logs=on -k podman.logs=on`
   - Collects all logs with `--all-logs`
   - Runs in batch mode (`--batch`) for non-interactive execution

3. **Report Management**
   - `list_sos_reports()`: Lists available reports in `/var/tmp/`
   - `download_report()`: Downloads report using `oc cp`
   - Handles `/host` prefix for pod filesystem paths

4. **Utility Functions**
   - `run_command()`: Executes shell commands with timeout and error handling
   - Supports real-time output streaming for long-running commands
   - Proper error handling and exit codes

**Command Workflows:**

- **start**: Creates debug pod and waits for it to be running (60 second timeout)
- **collect**: Executes SOS report collection (20 minute timeout), parses output to find report path
- **download**: Copies report from pod to local directory using `oc cp` (5 minute timeout)
- **list**: Shows available reports with sizes and timestamps
- **cleanup**: Deletes debug pod with optional force flag
- **all**: Executes start → collect → download in sequence with duration tracking

**Error Handling:**

- Validates prerequisites (oc CLI, cluster access)
- Checks for existing debug pods before creating new ones
- Handles collection timeouts gracefully (some plugins often timeout)
- Verifies downloaded files exist and reports file size
- Provides helpful error messages and troubleshooting guidance

**Exit Codes:**

- `0`: Success
- `1`: Failure (invalid arguments, pod errors, collection errors, download errors)

---

### sosreport-multi-collector.py

A Python script that automates the collection of SOS reports from multiple OpenShift nodes in parallel.

**Purpose:**
- Collects SOS reports from multiple nodes simultaneously
- Uses Python's `ThreadPoolExecutor` for parallel execution
- Independent per-node error handling
- Comprehensive summary reporting
- Optional automatic cleanup

**Features:**
- Parallel execution across 4 phases: start pods → collect → download → cleanup
- Configurable parallelism limit (default: 5 concurrent nodes)
- Per-node log files for detailed troubleshooting
- Real-time progress tracking with colored output
- Comprehensive final summary showing successes/failures

**Usage:**

The script is invoked by the `/sosreport:collector multi` command. It can also be used standalone:

```bash
# Basic multi-node collection
python3 plugins/sosreport/skills/scripts/sosreport-multi-collector.py \
  worker-0.example.com worker-1.example.com worker-2.example.com

# With options
python3 plugins/sosreport/skills/scripts/sosreport-multi-collector.py \
  worker-{0..9}.example.com \
  --case-id 12345678 \
  --max-parallel 3 \
  --cleanup \
  --download-dir .work/sos-reports
```

**Arguments:**

- `nodes` (positional, required): Space-separated list of OpenShift node names (minimum 2)
- `-d, --download-dir`: Directory for downloaded reports (default: `.work/sos-reports`)
- `-c, --case-id`: Red Hat case ID
- `-n, --namespace`: Namespace for debug pods (default: `default`)
- `-t, --plugin-timeout`: Timeout per plugin in seconds (default: 900)
- `-p, --max-parallel`: Maximum parallel collections (default: 5)
- `--cleanup`: Automatically cleanup debug pods after collection

**Implementation Details:**

The script uses the `MultiNodeCollector` class which provides:

1. **Prerequisites Validation**
   - Checks oc CLI, cluster login, node existence
   - Displays collection plan and asks for confirmation

2. **Phase 1: Start Debug Pods (Parallel)**
   - Creates thread pool with `max_workers=max_parallel`
   - Starts debug pods in parallel across all nodes
   - Tracks which pods started successfully

3. **Phase 2: Collect SOS Reports (Parallel)**
   - Executes `chroot /host toolbox sos report` in each pod
   - Streams output to per-node log files
   - Parses output to find report paths

4. **Phase 3: Download Reports (Parallel)**
   - Downloads all successful collections using `oc cp`
   - Verifies downloads and displays file sizes

5. **Phase 4: Cleanup (Optional, Parallel)**
   - If `--cleanup` flag provided, deletes all debug pods
   - Tracks cleanup successes/failures

6. **Final Summary**
   - Displays comprehensive table of results
   - Shows successes, failures, and next steps
   - Includes total duration and per-node status

**Error Handling:**

- Each node's collection is independent - failures don't stop others
- All errors tracked and reported in final summary
- Prerequisites errors exit early
- Resource constraints respected via `--max-parallel` limit
- Helpful next steps provided for failures

**Progress Indication:**

- Phase headers with clear current state
- Progress counters (X/Y nodes completed)
- Colored output (green=success, red=failure, yellow=warning)
- Per-node logs saved to `.work/sos-reports/logs/<node-name>-<phase>.log`

**Exit Codes:**

- `0`: At least one collection succeeded
- `1`: All collections failed
- `2`: Prerequisites check failed

---

## Prerequisites

- **Python 3**: Required to run the script
- **OpenShift CLI (oc)**: Must be installed and user must be logged in
- **Cluster permissions**: User must have permissions to create debug pods

## Integration with Plugin

These scripts are called by the `/sosreport:collector` command defined in `plugins/sosreport/commands/collector.md`. The command provides a user-friendly interface to the scripts' functionality.

**Command to Script Mapping:**

**Single-node mode:**
```
/sosreport:collector <cmd> <node> [opts]
    ↓
python3 plugins/sosreport/skills/scripts/sosreport-single-collector.py <cmd> <node> [opts]
```

**Multi-node mode:**
```
/sosreport:collector multi <node1> <node2> [...] [opts]
    ↓
python3 plugins/sosreport/skills/scripts/sosreport-multi-collector.py <node1> <node2> [...] [opts]
```

## See Also

- **Command Documentation**: `plugins/sosreport/commands/collector.md`
- **Plugin README**: `plugins/sosreport/README.md`
- **SOS Report Documentation**: https://github.com/sosreport/sos
- **OpenShift Debug Documentation**: https://docs.openshift.com/container-platform/latest/support/troubleshooting/investigating-pod-issues.html

## Contributing

When modifying this script:

1. Maintain backwards compatibility with existing command-line arguments
2. Update the command documentation in `collector.md` if behavior changes
3. Test all command workflows: start, collect, download, list, cleanup, all
4. Ensure proper error handling and helpful error messages
5. Update this SKILL.md if adding new scripts or changing functionality

