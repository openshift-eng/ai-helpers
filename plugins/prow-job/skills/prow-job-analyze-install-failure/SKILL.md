---
name: Prow Job Analyze Install Failure
description: Analyze OpenShift installation failures in Prow CI jobs by examining installer logs, log bundles, and sosreports. Use when CI job fails "install should succeed" tests at bootstrap, cluster creation or other stages.
---

# Prow Job Analyze Install Failure

This skill helps debug OpenShift installation failures in CI jobs by downloading and analyzing installer logs, log bundles, and sosreports from Google Cloud Storage.

## When to Use This Skill

Use this skill when:
- A CI job fails with "install should succeed" test failure
- You need to debug installation failures at specific stages (bootstrap, install-complete, etc.)
- You need to analyze installer logs and log bundles from failed CI jobs

## Prerequisites

Before starting, verify these prerequisites:

1. **gcloud CLI Installation**
   - Check if installed: `which gcloud`
   - If not installed, provide instructions for the user's platform
   - Installation guide: https://cloud.google.com/sdk/docs/install

2. **gcloud Authentication (Optional)**
   - The `test-platform-results` bucket is publicly accessible
   - No authentication is required for read access
   - Skip authentication checks

## Input Format

The user will provide:
1. **Prow job URL** - URL to the failed CI job
   - Example: `https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.21-e2e-aws-ovn-techpreview/1983307151598161920`
   - The URL should contain `test-platform-results/`

## Understanding Job Types from Names

Job names contain important clues about the test environment and what to look for:

1. **Upgrade Jobs** (names containing "upgrade")
   - These jobs perform a **fresh installation first**, then upgrade
   - **Minor upgrade jobs**: Contain "upgrade-from-stable-4.X" in the name - upgrade from previous minor version (e.g., 4.21 job installs 4.20, then upgrades to 4.21)
     - Example: `periodic-ci-openshift-release-master-ci-4.21-upgrade-from-stable-4.20-e2e-gcp-ovn-rt-upgrade`
   - **Micro upgrade jobs**: Have "upgrade" in the name but NO "upgrade-from-stable" - upgrade within the same minor version (e.g., earlier 4.21 to newer 4.21)
     - Example: `periodic-ci-openshift-release-master-nightly-4.21-e2e-aws-ovn-upgrade-fips`
     - Example: `periodic-ci-openshift-release-master-ci-4.21-e2e-azure-ovn-upgrade`
   - If installation fails, the upgrade never happens
   - **Key point**: Installation failures in upgrade jobs are still installation failures, not upgrade failures

2. **FIPS Jobs** (names containing "fips")
   - FIPS mode enabled for cryptographic operations
   - Pay special attention to errors related to:
     - Cryptography libraries
     - TLS/SSL handshakes
     - Certificate validation
     - Hash algorithms

3. **IPv6 and Dualstack Jobs** (names containing "ipv6" or "dualstack")
   - Using IPv6 or dual IPv4/IPv6 networking stack
   - Most IPv6 jobs are **disconnected** (no internet access)
   - Use a locally-hosted mirror registry for images
   - Pay attention to:
     - Network connectivity errors
     - DNS resolution issues
     - Mirror registry logs
     - IPv6 address configuration

4. **Metal Jobs with IPv6** (names containing "metal" and "ipv6")
   - Disconnected environment with additional complexity
   - The metal install failure skill will analyze squid proxy logs and disconnected environment configuration

5. **Single-Node Jobs** (names containing "single-node")
   - All control plane and compute workloads on one node
   - More prone to resource exhaustion
   - Pay attention to CPU, memory, and disk pressure

6. **Platform-Specific Indicators**
   - `aws`, `gcp`, `azure`: Cloud platform used
   - `metal`, `baremetal`: Bare metal environment (uses specialized metal install failure skill)
   - `ovn`: OVN-Kubernetes networking (standard)

## Implementation Steps

### Step 1: Parse and Validate URL

1. **Extract bucket path**
   - Find `test-platform-results/` in URL
   - Extract everything after it as the GCS bucket relative path
   - If not found, error: "URL must contain 'test-platform-results/'"

2. **Extract build_id**
   - Search for pattern `/(\d{10,})/` in the bucket path
   - build_id must be at least 10 consecutive decimal digits
   - Handle URLs with or without trailing slash
   - If not found, error: "Could not find build ID (10+ digits) in URL"

3. **Determine job type**
   - Check if job name contains "metal" (case-insensitive)
   - Metal jobs: Set `is_metal_job = true`
   - Other jobs: Set `is_metal_job = false`

4. **Construct GCS paths**
   - Bucket: `test-platform-results`
   - Base GCS path: `gs://test-platform-results/{bucket-path}/`
   - Ensure path ends with `/`

### Step 2: Create Working Directory

1. **Create directory structure**
   ```bash
   mkdir -p .work/prow-job-analyze-install-failure/{build_id}/logs
   mkdir -p .work/prow-job-analyze-install-failure/{build_id}/analysis
   ```
   - Use `.work/prow-job-analyze-install-failure/` as the base directory (already in .gitignore)
   - Use build_id as subdirectory name
   - Create `logs/` subdirectory for all downloads
   - Create `analysis/` subdirectory for analysis files
   - Working directory: `.work/prow-job-analyze-install-failure/{build_id}/`

### Step 3: Download prowjob.json and Identify Target

1. **Download prowjob.json**
   ```bash
   gcloud storage cp gs://test-platform-results/{bucket-path}/prowjob.json .work/prow-job-analyze-install-failure/{build_id}/logs/prowjob.json --no-user-output-enabled
   ```

2. **Parse and validate**
   - Read `.work/prow-job-analyze-install-failure/{build_id}/logs/prowjob.json`
   - Search for pattern: `--target=([a-zA-Z0-9-]+)`
   - If not found:
     - Display: "This is not a ci-operator job. The prowjob cannot be analyzed by this skill."
     - Explain: ci-operator jobs have a --target argument specifying the test target
     - Exit skill

3. **Extract target name**
   - Capture the target value (e.g., `e2e-aws-ovn-techpreview`)
   - Store for constructing artifact paths

### Step 4: Download JUnit XML to Identify Failure Stage

**Note on install-status.txt**: You may see an `install-status.txt` file in the artifacts. This file contains only the installer's exit code (a single number). The junit_install.xml file translates this exit code into a human-readable failure mode, so always prefer junit_install.xml for determining the failure stage.

1. **Find junit_install.xml**
   - Use recursive listing to find the file anywhere in the job artifacts:
   ```bash
   gcloud storage ls -r gs://test-platform-results/{bucket-path}/artifacts/ 2>&1 | grep "junit_install.xml"
   ```
   - The file location varies by job configuration - don't assume any specific path

2. **Download junit_install.xml**
   - Download from the discovered location:
   ```bash
   # Download from wherever it was found
   gcloud storage cp {full-gcs-path-to-junit_install.xml} .work/prow-job-analyze-install-failure/{build_id}/logs/junit_install.xml --no-user-output-enabled
   ```
   - If file not found, continue anyway (older jobs or early failures may not have this file)

3. **Parse junit_install.xml to find failure stage**
   - Look for failed test cases with pattern `install should succeed: <stage>`
   - Installation failure modes:
     - **`cluster bootstrap`** - Early install failure where we failed to bootstrap the cluster. Bootstrap is typically an ephemeral VM that runs a temporary kube apiserver. Check bootkube logs in the bundle.
     - **`infrastructure`** - Early failure before we're able to create all cloud resources. Often but not always due to cloud quota, rate limiting, or outages. Check installer log for cloud API errors.
     - **`cluster creation`** - Usually means one or more operators was unable to stabilize. Check operator logs in gather-must-gather artifacts.
     - **`configuration`** - Extremely rare failure mode where we failed to create the install-config.yaml for one reason or another. Check installer log for validation errors.
     - **`cluster operator stability`** - Operators never stabilized (available=True, progressing=False, degraded=False). Check specific operator logs to determine why they didn't reach stable state.
     - **`other`** - Unknown install failure, could be for one of the previously declared reasons, or an unknown one. Requires full log analysis.
   - Extract the failure stage for targeted log analysis
   - Use the failure mode to guide which logs to prioritize

### Step 5: Locate and Download Installer Logs

1. **List all artifacts to find installer logs**
   - Installer logs follow the pattern `.openshift_install*.log`
   - **IMPORTANT**: Exclude deprovision logs - they are from cluster teardown, not installation
   - Use recursive listing to find all installer logs:
   ```bash
   gcloud storage ls -r gs://test-platform-results/{bucket-path}/artifacts/ 2>&1 | grep -E "\.openshift_install.*\.log$" | grep -v "deprovision"
   ```
   - This will find installer logs regardless of which CI step created them

2. **Download all installer logs found**
   ```bash
   # For each installer log found in the listing (excluding deprovision)
   gcloud storage cp {full-gcs-path-to-installer-log} .work/prow-job-analyze-install-failure/{build_id}/logs/ --no-user-output-enabled
   ```
   - Download all installer logs found that are NOT from deprovision steps
   - If multiple installer logs exist, download all of them (they may be from different install phases)
   - Deprovision logs are from cluster cleanup and not relevant for installation failures

### Step 6: Locate and Download Log Bundle

1. **List all artifacts to find log bundle**
   - Log bundles are `.tar` files (NOT `.tar.gz`) starting with `log-bundle-`
   - **IMPORTANT**: Prefer non-deprovision log bundles over deprovision ones
   - Use recursive listing to find all log bundles:
   ```bash
   # Find all log bundles, preferring non-deprovision
   gcloud storage ls -r gs://test-platform-results/{bucket-path}/artifacts/ 2>&1 | grep -E "log-bundle.*\.tar$"
   ```
   - This will find log bundles regardless of which CI step created them

2. **Download log bundle**
   ```bash
   # If non-deprovision log bundles exist, download one of those (prefer most recent by timestamp)
   # Otherwise, download deprovision log bundle if that's the only one available
   gcloud storage cp {full-gcs-path-to-log-bundle} .work/prow-job-analyze-install-failure/{build_id}/logs/ --no-user-output-enabled
   ```
   - Prefer log bundles NOT from deprovision steps (they capture the failure state during installation)
   - Deprovision log bundles may also contain useful info if no other bundle exists
   - If multiple log bundles exist, prefer the one from a non-deprovision step
   - If no log bundle found, continue with installer log analysis only (early failures may not produce log bundles)

3. **Extract log bundle**
   ```bash
   tar -xf .work/prow-job-analyze-install-failure/{build_id}/logs/log-bundle-{timestamp}.tar -C .work/prow-job-analyze-install-failure/{build_id}/logs/
   ```

### Step 7: Invoke Metal Install Failure Skill (Metal Jobs Only)

**IMPORTANT: Only perform this step if `is_metal_job = true`**

Metal IPI jobs use **dev-scripts** with **Metal3** and **Ironic** to install OpenShift on bare metal. These require specialized analysis.

1. **Invoke the metal install failure skill**
   - Use the Skill tool to invoke: `prow-job:prow-job-analyze-metal-install-failure`
   - Pass the following information:
     - Build ID: `{build_id}`
     - Bucket path: `{bucket-path}`
     - Target name: `{target}`
     - Working directory already created: `.work/prow-job-analyze-install-failure/{build_id}/`

2. **The metal skill will**:
   - Download and analyze dev-scripts logs (setup process before OpenShift installation)
   - Download and analyze libvirt console logs (VM/node boot sequence)
   - Download and analyze optional artifacts (sosreport, squid logs)
   - Determine if failure was in dev-scripts setup or cluster installation
   - Generate metal-specific analysis report

3. **Continue with standard analysis**:
   - After metal skill completes, continue with Step 8 (Analyze Installer Logs)
   - The metal skill provides additional context about dev-scripts and console logs
   - Standard installer log analysis is still relevant for understanding cluster creation failures

### Step 8: Analyze Installer Logs

**CRITICAL: Understanding OpenShift's Eventual Consistency**

OpenShift installations exhibit "eventual consistency" behavior, which means:
- Components may report errors while waiting for dependencies to become ready
- Example: Ingress operator may error waiting for networking, which errors waiting for other components
- These intermediate errors are **expected and normal** during installation
- Early errors in the log often resolve themselves and are NOT the root cause

**Error Analysis Strategy**:
1. **Start with the NEWEST/FINAL errors** - Work backwards in time
2. Focus on errors that persisted until installation timeout
3. Track backwards from final errors to identify the dependency chain
4. Early errors are only relevant if they directly relate to the final failure state
5. Don't chase errors that occurred early and then disappeared - they likely resolved

**Example**: If installation fails at 40 minutes with "kube-apiserver not available", an error at 5 minutes saying "ingress operator degraded" is likely irrelevant because it probably resolved. Focus on what was still broken when the timeout occurred.

1. **Read installer log**
   - The installer log is a sequential log file with timestamp, log level, and message
   - Format: `time="YYYY-MM-DDTHH:MM:SSZ" level=<level> msg="<message>"`

2. **Identify key failure indicators (WORK BACKWARDS FROM END)**
   - **Start at the end of the log** - Look at final error/fatal messages
   - **Error messages**: Lines with `level=error` or `level=fatal` near the end of the log
   - **Last status messages**: The final "Still waiting for" or "Cluster operators X, Y, Z are not available" messages
   - **Warning messages**: Lines with `level=warning` near the failure time that may indicate problems
   - **Then work backwards** to find when the failing component first started having issues
   - Ignore errors from early in the log unless they persist to the end

3. **Extract relevant log sections (prioritize recent errors)**
   - For bootstrap failures:
     - Search for: "bootstrap", "bootkube", "kube-apiserver", "etcd" in the **last 20% of the log**
   - For install-complete failures:
     - Search for: "Cluster operators", "clusteroperator", "degraded", "available" in the **final messages**
   - For timeout failures:
     - Search for: "context deadline exceeded", "timeout", "timed out"
     - Look at what component was being waited for when timeout occurred

4. **Create installer log summary**
   - Extract **final/last** error or fatal message (most important)
   - Extract the last "Still waiting for..." message showing what didn't stabilize
   - Extract surrounding context (10-20 lines before and after final errors)
   - Optionally note early errors only if they relate to the final failure
   - Save to: `.work/prow-job-analyze-install-failure/{build_id}/analysis/installer-summary.txt`

### Step 9: Analyze Log Bundle

**Skip this step if no log bundle was downloaded**

1. **Understand log bundle structure**
   - `log-bundle-{timestamp}/`
     - `bootstrap/journals/` - Journal logs from bootstrap node
       - `bootkube.log` - Bootkube service that starts initial control plane
       - `kubelet.log` - Kubelet service logs
       - `crio.log` - Container runtime logs
       - `journal.log.gz` - Complete system journal (gzipped)
     - `bootstrap/network/` - Network configuration
       - `ip-addr.txt` - IP addresses
       - `ip-route.txt` - Routing table
       - `hostname.txt` - Hostname
     - `serial/` - Serial console logs from all nodes
       - `{cluster-name}-bootstrap-serial.log` - Bootstrap node console
       - `{cluster-name}-master-N-serial.log` - Master node consoles
     - `clusterapi/` - Cluster API resources
       - `*.yaml` - Kubernetes resource definitions
       - `etcd.log` - etcd logs
       - `kube-apiserver.log` - API server logs
     - `failed-units.txt` - List of systemd units that failed
     - `gather.log` - Log bundle collection process log

2. **Analyze based on failure mode from junit_install.xml**

   **For "cluster bootstrap" failures:**
   - Check `bootstrap/journals/bootkube.log` for bootkube errors
   - Check `bootstrap/journals/kubelet.log` for kubelet issues
   - Check `clusterapi/kube-apiserver.log` for API server startup issues
   - Check `clusterapi/etcd.log` for etcd cluster formation issues
   - Check `serial/{cluster-name}-bootstrap-serial.log` for bootstrap VM boot issues
   - Look for temporary control plane startup problems
   - This is an early failure - focus on bootstrap node and initial control plane

   **For "infrastructure" failures:**
   - Primary focus on installer log, not log bundle (failure happens before bootstrap)
   - Search installer log for cloud provider API errors
   - Look for quota exceeded messages (e.g., "QuotaExceeded", "LimitExceeded")
   - Look for rate limiting errors (e.g., "RequestLimitExceeded", "Throttling")
   - Check for authentication/permission errors
   - **Infrastructure provisioning methods** (varies by OpenShift version):
     - **Newer versions**: Use **Cluster API (CAPI)** to provision infrastructure
       - Look for errors in ClusterAPI-related logs and resources
       - Check for Machine/MachineSet/MachineDeployment errors
       - Search for "clusterapi" or "machine-api" related errors
     - **Older versions**: Use **Terraform** to provision infrastructure
       - Look for "terraform" in log entries
       - Check for terraform state errors or apply failures
       - Search for terraform-related error messages
   - Log bundle may not exist or be incomplete for this failure mode

   **For "cluster creation" failures:**
   - Check if must-gather was successfully collected:
     - Look for `must-gather*.tar` files in the gather-must-gather step directory
     - If NO .tar file exists, must-gather collection failed (cluster was too unstable)
     - Do NOT suggest downloading must-gather if the .tar file doesn't exist
   - If must-gather exists, check for operator logs
   - Look for degraded cluster operators
   - Check operator-specific logs to see why they couldn't stabilize
   - Review cluster operator status conditions
   - This indicates cluster bootstrapped but operators failed to deploy

   **For "configuration" failures:**
   - Focus entirely on installer log
   - Look for install-config.yaml validation errors
   - Check for missing required fields or invalid values
   - This is a very early failure before any infrastructure is created
   - Log bundle will not exist for this failure mode

   **For "cluster operator stability" failures:**
   - Similar to "cluster creation" but operators are stuck in unstable state
   - Check if must-gather was successfully collected (look for `must-gather*.tar` files)
   - If must-gather doesn't exist, rely on installer log and log bundle only
   - Check for operators with available=False, progressing=True, or degraded=True
   - Review operator logs in gather-must-gather (if it exists)
   - Check for resource conflicts or dependency issues
   - Look at time-series of operator status changes

   **For "other" failures:**
   - Perform comprehensive analysis of all available logs
   - Check installer log for any errors or fatal messages
   - Review log bundle if available
   - Look for unusual patterns or timeout messages

3. **Extract key information**
   - If `failed-units.txt` exists, read it to find failed services
   - For each failed service, find corresponding journal log
   - Extract error messages from journal logs
   - Save findings to: `.work/prow-job-analyze-install-failure/{build_id}/analysis/log-bundle-summary.txt`

### Step 10: Generate Analysis Report

1. **Create comprehensive analysis report**
   - Combine findings from all sources:
     - Installer log analysis
     - Log bundle analysis
     - sosreport analysis (if applicable)

2. **Report structure**
   ```
   OpenShift Installation Failure Analysis
   ========================================

   Job: {job-name}
   Build ID: {build_id}
   Job Type: {metal/cloud}
   Prow URL: {original-url}

   Failure Stage: {stage from junit_install.xml}

   Summary
   -------
   {High-level summary of the failure}

   Installer Log Analysis
   ----------------------
   {Key findings from installer log}

   First Error:
   {First error message with timestamp}

   Context:
   {Surrounding log lines}

   Log Bundle Analysis
   -------------------
   {Findings from log bundle}

   Failed Units:
   {List from failed-units.txt}

   Key Journal Errors:
   {Important errors from journal logs}

   Metal Installation Analysis (Metal Jobs Only)
   -----------------------------------------
   {Summary from metal install failure skill}
   - Dev-scripts setup status
   - Console log findings
   - Key metal-specific errors

   See detailed metal analysis: .work/prow-job-analyze-install-failure/{build_id}/analysis/metal-analysis.txt

   Recommended Next Steps
   ----------------------
   {Actionable debugging steps based on failure mode:

   For "configuration" failures:
   - Review install-config.yaml validation errors
   - Check for missing required fields
   - Verify credential format and availability

   For "infrastructure" failures:
   - Check cloud provider quota and limits
   - Review cloud provider service status for outages
   - Verify API credentials and permissions
   - Check for rate limiting in cloud API calls

   For "cluster bootstrap" failures:
   - Review bootkube logs for control plane startup issues
   - Check etcd cluster formation in etcd.log
   - Examine kube-apiserver startup in kube-apiserver.log
   - Review bootstrap VM serial console for boot issues

   For "cluster creation" failures:
   - Identify which operators failed to deploy
   - Check if must-gather was collected (look for must-gather*.tar files)
   - If must-gather exists: Review specific operator logs in gather-must-gather
   - If must-gather doesn't exist: Cluster was too unstable to collect diagnostics; rely on installer log and log bundle
   - Check for resource conflicts or missing dependencies

   For "cluster operator stability" failures:
   - Identify operators not reaching stable state
   - Check operator conditions (available, progressing, degraded)
   - Check if must-gather exists before suggesting to review it
   - Review operator logs for stuck operations (if must-gather available)
   - Look for time-series of operator status changes

   For "other" failures:
   - Perform comprehensive log review
   - Look for timeout or unusual error patterns
   - Check all available artifacts systematically
   }

   Artifacts Location
   ------------------
   All artifacts downloaded to:
   .work/prow-job-analyze-install-failure/{build_id}/logs/

   - Installer logs: .openshift_install*.log
   - Log bundle: log-bundle-*/
   - sosreport: sosreport-*/ (metal jobs only)
   ```

3. **Save report**
   - Save to: `.work/prow-job-analyze-install-failure/{build_id}/analysis/report.txt`

### Step 11: Present Results to User

1. **Display summary**
   - Show the analysis report to the user
   - Highlight the most critical findings
   - Provide file paths for further investigation

2. **Offer next steps**
   - Based on the failure type, suggest specific debugging actions:
     - For bootstrap failures: Check API server and etcd logs
     - For install-complete failures: Check cluster operator status
     - For network issues: Review network configuration
     - For metal job failures: Examine VM console logs
   - **IMPORTANT**: Only suggest reviewing must-gather if you verified the .tar file exists
     - Don't suggest downloading must-gather if no .tar file was found
     - If must-gather doesn't exist, note that the cluster was too unstable to collect it

3. **Provide artifact locations**
   - List all downloaded files with their paths
   - Note whether must-gather was successfully collected or not
   - Explain how to explore the logs further
   - Mention that artifacts are cached for faster re-analysis

## Installation Stages Reference

Understanding the installation stages helps target analysis:

1. **Pre-installation** (Failure mode: "configuration")
   - Validation of install-config.yaml
   - Credential checks
   - Image resolution
   - **Common failures**: Invalid install-config.yaml, missing required fields, validation errors

2. **Infrastructure Creation** (Failure mode: "infrastructure")
   - Creating cloud resources (VMs, networks, storage)
   - For metal: VM provisioning on hypervisor
   - **Common failures**: Cloud quota exceeded, rate limiting, API outages, permission errors

3. **Bootstrap** (Failure mode: "cluster bootstrap")
   - Bootstrap node boots with temporary control plane
   - Bootstrap API server and etcd start
   - Bootstrap creates master nodes
   - **Common failures**: API server won't start, etcd formation issues, bootkube errors

4. **Master Node Bootstrap**
   - Master nodes boot and join bootstrap etcd
   - Masters form permanent control plane
   - Bootstrap control plane transfers to masters
   - **Common failures**: Masters can't reach bootstrap, network issues, ignition failures

5. **Bootstrap Complete**
   - Bootstrap node is no longer needed
   - Masters are running permanent control plane
   - Cluster operators begin initialization
   - **Common failures**: Control plane not transferring, master nodes not ready

6. **Cluster Operators Initialization** (Failure mode: "cluster creation")
   - Core cluster operators start
   - Operators begin deployment
   - Initial operator stabilization
   - **Common failures**: Operators can't deploy, resource conflicts, dependency issues

7. **Cluster Operators Stabilization** (Failure mode: "cluster operator stability")
   - Operators reach stable state (available=True, progressing=False, degraded=False)
   - Worker nodes can join
   - **Common failures**: Operators stuck progressing, degraded state, availability issues

8. **Install Complete**
   - All cluster operators are available and stable
   - Cluster is fully functional
   - Installation successful

## Failure Mode Mapping

| JUnit Failure Mode | Installation Stage | Where to Look | Artifacts Available |
|-------------------|-------------------|---------------|-------------------|
| `configuration` | Pre-installation | Installer log only | No log bundle |
| `infrastructure` | Infrastructure Creation | Installer log, cloud API errors | Partial or no log bundle |
| `cluster bootstrap` | Bootstrap | Log bundle (bootkube, etcd, kube-apiserver) | Full log bundle |
| `cluster creation` | Operators Initialization | gather-must-gather, operator logs | Full artifacts |
| `cluster operator stability` | Operators Stabilization | gather-must-gather, operator status | Full artifacts |
| `other` | Unknown | All available logs | Varies |

## Key Files Reference

### Installer Logs
- **Location**: `.openshift_install-{timestamp}.log`
- **Format**: Structured log with timestamp, level, message
- **Key patterns**:
  - `level=error` - Error messages
  - `level=fatal` - Fatal errors that stop installation
  - `waiting for` - Timeout/waiting messages

### Log Bundle Structure
- **bootstrap/journals/bootkube.log**: Bootstrap control plane initialization
- **bootstrap/journals/kubelet.log**: Bootstrap kubelet (container orchestration)
- **clusterapi/kube-apiserver.log**: API server logs
- **clusterapi/etcd.log**: etcd cluster logs
- **serial/*.log**: Node console output
- **failed-units.txt**: systemd services that failed

### Metal Job Artifacts

Metal installations are handled by the `prow-job-analyze-metal-install-failure` skill.
See that skill's documentation for details on dev-scripts, libvirt logs, sosreport, and squid logs.

## Tips

- **CRITICAL**: Work backwards from the end of the installer log, not forwards from the beginning
- Early errors often resolve themselves due to eventual consistency - focus on final errors
- Always start by checking the installer log for the **LAST** error, not the first
- The log bundle provides detailed node-level diagnostics
- Serial console logs show the actual boot sequence and can reveal kernel panics
- Failed systemd units in failed-units.txt are strong indicators of the problem
- Bootstrap failures are often etcd or API server related
- Install-complete failures are usually cluster operator issues
- Metal jobs use a specialized skill for analysis (prow-job-analyze-metal-install-failure)
- Cache artifacts in `.work/prow-job-analyze-install-failure/{build_id}/` for re-analysis
- Use grep with relevant keywords to filter large log files
- Timeline of events from installer log helps correlate issues across logs
- Pay attention to job name clues: fips, ipv6, dualstack, metal, single-node, upgrade
- IPv6 jobs are often disconnected and use mirror registries
- Only suggest must-gather if the .tar file exists; if not, cluster was too unstable

## Important Notes

1. **Eventual Consistency Behavior**
   - OpenShift installations exhibit eventual consistency
   - Components report errors while waiting for dependencies
   - Early errors are EXPECTED and usually resolve automatically
   - **Always analyze backwards from the final timeout, not forwards from the start**
   - Only errors that persist until failure are relevant root causes

2. **Upgrade Jobs and Installation**
   - Jobs with "upgrade" in the name perform installation FIRST, then upgrade
   - If you're analyzing an installation failure in an upgrade job, it never got to the upgrade phase
   - "minor" upgrade: Installs 4.n-1 version (e.g., 4.20 for a 4.21 upgrade job)
   - "micro" upgrade: Installs earlier payload in same stream

3. **Log Bundle Availability**
   - Not all jobs produce log bundles
   - Older jobs may not have this feature
   - Installation must reach a certain point to generate log bundle

4. **Must-Gather Availability**
   - Must-gather only exists if a `must-gather*.tar` file is present
   - If no .tar file exists, the cluster was too unstable to collect diagnostics
   - **Never suggest downloading must-gather unless you verified the .tar file exists**

5. **Metal Job Specifics**
   - Metal jobs are analyzed using the specialized `prow-job-analyze-metal-install-failure` skill
   - That skill handles dev-scripts, libvirt console logs, sosreport, and squid logs
   - See the metal skill documentation for details

6. **Debugging Workflow**
   - Start with installer log to find **LAST** error (not first)
   - Use failure stage to guide which logs to examine
   - Log bundle provides node-level details
   - For metal jobs, invoke the metal-specific skill for additional analysis
   - Work backwards in time to trace dependency chains

7. **Common Failure Patterns**
   - **Bootstrap etcd not starting**: Check etcd.log and bootkube.log
   - **API server not responding**: Check kube-apiserver.log
   - **Masters not joining**: Check master serial logs
   - **Operators degraded**: Check specific operator logs in must-gather (if it exists)
   - **Network issues**: Check network configuration in bootstrap/network/

8. **File Formats**
   - Installer log: Plain text, structured format
   - Journal logs: systemd journal format (plain text export)
   - Serial logs: Raw console output
   - YAML files: Kubernetes resource definitions
   - Compressed files: .gz (gzip), .xz (xz)
