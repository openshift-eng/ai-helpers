---
name: Prow Job Analyze Metal Install Failure
description: Analyze OpenShift bare metal installation failures in Prow CI jobs using dev-scripts artifacts. Use for jobs with "metal" in name, for debugging Metal3/Ironic provisioning, installation, or dev-scripts setup failures. You may also use the prow-job-analyze-install-failure skill with this one.
---

# Prow Job Analyze Metal Install Failure

This skill helps debug OpenShift bare metal installation failures in CI jobs by analyzing dev-scripts logs, libvirt console logs, sosreports, and other metal-specific artifacts.

## When to Use This Skill

Use this skill when:
- A bare metal CI job fails with "install should succeed" test failure
- The job name contains "metal" or "baremetal"
- You need to debug Metal3/Ironic provisioning issues
- You need to analyze dev-scripts setup failures

This skill is invoked by the main `prow-job-analyze-install-failure` skill when it detects a metal job.

## Metal Installation Overview

Metal IPI jobs use **dev-scripts** (https://github.com/openshift-metal3/dev-scripts) with **Metal3** and **Ironic** to install OpenShift:
- **dev-scripts**: Framework for setting up and installing OpenShift on bare metal
- **Metal3**: Kubernetes-native interface to Ironic
- **Ironic**: Bare metal provisioning service

The installation process has multiple layers:
1. **dev-scripts setup**: Configures hypervisor, sets up Ironic/Metal3, builds installer
2. **Ironic provisioning**: Provisions bare metal nodes (or VMs acting as bare metal)
3. **OpenShift installation**: Standard installer runs on provisioned nodes

Failures can occur at any layer, so analysis must check all of them.

## Network Architecture (CRITICAL for Understanding IPv6/Disconnected Jobs)

**IMPORTANT**: The term "disconnected" refers to the cluster nodes, NOT the hypervisor.

### Hypervisor (dev-scripts host)
- **HAS** full internet access
- Downloads packages, container images, and dependencies from the public internet
- Runs dev-scripts Ansible playbooks that download tools (Go, installer, etc.)
- Hosts a local mirror registry to serve the cluster

### Cluster VMs/Nodes
- Run in a **private IPv6-only network** (when IP_STACK=v6)
- **NO** direct internet access (truly disconnected)
- Pull container images from the hypervisor's local mirror registry
- Access to hypervisor services only (registry, DNS, etc.)

### Common Misconception
When analyzing failures in "metal-ipi-ovn-ipv6" jobs:
- ❌ WRONG: "The hypervisor cannot access the internet, so downloads fail"
- ✅ CORRECT: "The hypervisor has internet access. If downloads fail, it's likely due to the remote service being unavailable, not network restrictions"

### Implications for Failure Analysis
1. **Dev-scripts failures** (steps 01-05): If external downloads fail, check if the remote service/URL is down or has removed the resource
2. **Installation failures** (step 06+): If cluster nodes cannot pull images, check the local mirror registry on the hypervisor
3. **HTTP 403/404 errors during dev-scripts**: Usually means the resource was removed from the upstream source, not that the network is restricted

## Prerequisites

1. **gcloud CLI Installation**
   - Check if installed: `which gcloud`
   - If not installed, provide instructions for the user's platform
   - Installation guide: https://cloud.google.com/sdk/docs/install

2. **gcloud Authentication (Optional)**
   - The `test-platform-results` bucket is publicly accessible
   - No authentication is required for read access

## Input Format

The user will provide:
1. **Build ID** - Extracted by the main skill
2. **Bucket path** - Extracted by the main skill
3. **Target name** - Extracted by the main skill
4. **Working directory** - Already created by main skill

## Metal-Specific Artifacts

Metal jobs produce several diagnostic archives:

### OFCIR Acquisition Logs
- **Location**: `{target}/ofcir-acquire/`
- **Purpose**: Shows the OFCIR host acquisition process
- **Contains**:
  - `build-log.txt`: Log showing pool, provider, and host details
  - `artifacts/junit_metal_setup.xml`: JUnit with test `[sig-metal] should get working host from infra provider`
- **Critical for**: Determining if the job failed to acquire a host before installation started
- **Key information**:
  - Pool name (e.g., "cipool-ironic-cluster-el9", "cipool-ibmcloud")
  - Provider (e.g., "ironic", "equinix", "aws", "ibmcloud")
  - Host name and details

### Dev-scripts Logs
- **Location**: `{target}/baremetalds-devscripts-setup/artifacts/root/dev-scripts/logs/`
- **Purpose**: Shows installation setup process and cluster installation
- **Contains**: Numbered log files showing each setup step (requirements, host config, Ironic setup, installer build, cluster creation). **Note**: dev-scripts invokes the installer, so installer logs (`.openshift_install*.log`) will also be present in the devscripts folders.
- **Critical for**: Early failures before cluster creation, Ironic/Metal3 setup issues, installation failures

### libvirt-logs.tar
- **Location**: `{target}/baremetalds-devscripts-gather/artifacts/`
- **Purpose**: VM/node console logs showing boot sequence
- **Contains**: Console output from bootstrap and master VMs/nodes
- **Critical for**: Boot failures, Ignition errors, kernel panics, network configuration issues

### log-bundle-*.tar (from gather or post-installation)
- **Location**: `{target}/baremetalds-devscripts-gather/artifacts/`
- **Purpose**: Cluster-level diagnostics including Ironic/Metal3 logs
- **Contains**:
  - **Bootstrap Ironic logs**: Located at `bootstrap/journals/ironic.log` and `bootstrap/journals/metal3-baremetal-operator.log`
    - Shows master node provisioning during bootstrap phase
    - Contains Redfish/IPMI BMC communication for masters
  - **Control-plane Ironic logs**: Located at `control-plane/{node-ip}/containers/metal3-ironic-*.log` and `control-plane/{node-ip}/containers/metal3-baremetal-operator-*.log`
    - Shows worker node provisioning
  - Bootstrap node journals (bootkube, kubelet, crio)
  - Control plane container logs
  - Cluster API resources
- **Critical for**: BareMetalHost registration failures, BMC connectivity issues (IPMI/Redfish), provisioning state problems, power management errors
- **Key Ironic errors to look for**:
  - BMC (IPMI, Redfish) errors
  - Node registration failures in Ironic
  - Power state query failures
  - Provisioning state transitions stuck
- **IMPORTANT**:
  - Bootstrap Ironic logs only show master provisioning
  - Control-plane Ironic logs show worker provisioning
  - Always check control-plane logs when investigating worker issues

### sosreport
- **Location**: `{target}/baremetalds-devscripts-gather/artifacts/`
- **Purpose**: Hypervisor system diagnostics
- **Contains**: Hypervisor logs, system configuration, diagnostic command output
- **Useful for**: Hypervisor-level issues, not typically needed for VM boot problems

### squid-logs.tar
- **Location**: `{target}/baremetalds-devscripts-gather/artifacts/`
- **Purpose**: Squid proxy logs for inbound CI access to the cluster
- **Contains**: Logs showing CI system's inbound connections to the cluster under test. **Note**: The squid proxy runs on the hypervisor for INBOUND access (CI → cluster), NOT for outbound access (cluster → registry).
- **Critical for**: Debugging CI access issues to the cluster, particularly in IPv6/disconnected environments

## Implementation Steps

### Step 1: Check OFCIR Acquisition

1. **Download OFCIR logs**
   ```bash
   gcloud storage cp gs://test-platform-results/{bucket-path}/artifacts/{target}/ofcir-acquire/build-log.txt .work/prow-job-analyze-install-failure/{build_id}/logs/ofcir-build-log.txt --no-user-output-enabled 2>&1 || echo "OFCIR build log not found"
   gcloud storage cp gs://test-platform-results/{bucket-path}/artifacts/{target}/ofcir-acquire/artifacts/junit_metal_setup.xml .work/prow-job-analyze-install-failure/{build_id}/logs/junit_metal_setup.xml --no-user-output-enabled 2>&1 || echo "OFCIR JUnit not found"
   ```

2. **Check junit_metal_setup.xml for acquisition failure**
   - Read the JUnit file
   - Look for test case: `[sig-metal] should get working host from infra provider`
   - If the test failed, OFCIR failed to acquire a host
   - This means installation never started - the failure is in host acquisition

3. **Extract OFCIR details from build-log.txt**
   - Parse the JSON in the build log to extract:
     - `pool`: The OFCIR pool name
     - `provider`: The infrastructure provider
     - `name`: The host name allocated
   - Save these for the final report

4. **If OFCIR acquisition failed**
   - Stop analysis - installation never started
   - Report: "OFCIR host acquisition failed"
   - Include pool and provider information
   - Suggest: Check OFCIR pool availability and provider status

### Step 2: Download Dev-Scripts Logs

1. **Download dev-scripts logs directory**
   ```bash
   gcloud storage cp -r gs://test-platform-results/{bucket-path}/artifacts/{target}/baremetalds-devscripts-setup/artifacts/root/dev-scripts/logs/ .work/prow-job-analyze-install-failure/{build_id}/logs/devscripts/ --no-user-output-enabled
   ```

2. **Handle missing dev-scripts logs gracefully**
   - Some metal jobs may not have dev-scripts artifacts
   - If missing, note this in the analysis and proceed with other artifacts

### Step 2: Download libvirt Console Logs

1. **Find and download libvirt-logs.tar**
   ```bash
   gcloud storage ls -r gs://test-platform-results/{bucket-path}/artifacts/ 2>&1 | grep "libvirt-logs\.tar$"
   gcloud storage cp {full-gcs-path-to-libvirt-logs.tar} .work/prow-job-analyze-install-failure/{build_id}/logs/ --no-user-output-enabled
   ```

2. **Extract libvirt logs**
   ```bash
   tar -xf .work/prow-job-analyze-install-failure/{build_id}/logs/libvirt-logs.tar -C .work/prow-job-analyze-install-failure/{build_id}/logs/
   ```

### Step 3: Download Optional Artifacts

1. **Download sosreport (optional)**
   ```bash
   gcloud storage ls -r gs://test-platform-results/{bucket-path}/artifacts/ 2>&1 | grep "sosreport.*\.tar\.xz$"
   gcloud storage cp {full-gcs-path-to-sosreport} .work/prow-job-analyze-install-failure/{build_id}/logs/ --no-user-output-enabled
   tar -xf .work/prow-job-analyze-install-failure/{build_id}/logs/sosreport-{name}.tar.xz -C .work/prow-job-analyze-install-failure/{build_id}/logs/
   ```

2. **Download squid-logs (optional, for IPv6/disconnected jobs)**
   ```bash
   gcloud storage ls -r gs://test-platform-results/{bucket-path}/artifacts/ 2>&1 | grep "squid-logs.*\.tar$"
   gcloud storage cp {full-gcs-path-to-squid-logs} .work/prow-job-analyze-install-failure/{build_id}/logs/ --no-user-output-enabled
   tar -xf .work/prow-job-analyze-install-failure/{build_id}/logs/squid-logs-{name}.tar -C .work/prow-job-analyze-install-failure/{build_id}/logs/
   ```

### Step 4: Analyze Dev-Scripts Logs

**Check dev-scripts logs FIRST** - they show what happened during setup and installation.

1. **Read dev-scripts logs in order**
   - Logs are numbered sequentially showing setup steps
   - **Note**: dev-scripts invokes the installer, so you'll find `.openshift_install*.log` files in the devscripts directories
   - Look for the first error or failure

2. **Key errors to look for**:
   - **Host configuration failures**: Networking, DNS, storage setup issues
   - **Ironic/Metal3 setup issues**: BMC connectivity, provisioning network, node registration failures
   - **Installer build failures**: Problems building the OpenShift installer binary
   - **Install-config validation errors**: Invalid configuration before cluster creation
   - **Installation failures**: Check installer logs (`.openshift_install*.log`) present in devscripts folders

3. **Important distinction**:
   - If failure is in dev-scripts setup logs (01-05), the problem is in the setup process
   - If failure is in installer logs or 06_create_cluster, the problem is in the cluster installation (also analyzed by main skill)

4. **Save dev-scripts analysis**:
   - Save findings to: `.work/prow-job-analyze-install-failure/{build_id}/analysis/devscripts-summary.txt`

### Step 5: Analyze Ironic Logs (from log-bundle)

**CRITICAL: Check the RIGHT Ironic logs based on what failed**

The log bundle contains TWO sets of Ironic logs in different locations:
- **Bootstrap Ironic logs**: For master node provisioning
- **Control-plane Ironic logs**: For worker node provisioning

**Which logs to check:**
- Masters failed to provision → Check `bootstrap/journals/ironic.log`
- Workers failed to provision → Check `control-plane/{ip}/containers/metal3-ironic-*.log`
- Unsure which failed → Check all

1. **Download and extract log bundle**
   ```bash
   gcloud storage ls -r gs://test-platform-results/{bucket-path}/artifacts/ 2>&1 | grep "log-bundle.*\.tar$"
   gcloud storage cp {full-gcs-path-to-log-bundle.tar} .work/prow-job-analyze-install-failure/{build_id}/logs/ --no-user-output-enabled
   tar -xf .work/prow-job-analyze-install-failure/{build_id}/logs/log-bundle-*.tar -C .work/prow-job-analyze-install-failure/{build_id}/logs/
   ```

2. **Find ALL Ironic logs**
   ```bash
   # Bootstrap Ironic (master provisioning)
   find .work/prow-job-analyze-install-failure/{build_id}/logs/ -path "*/bootstrap/journals/ironic.log"
   find .work/prow-job-analyze-install-failure/{build_id}/logs/ -path "*/bootstrap/journals/metal3-baremetal-operator.log"

   # Control-plane Ironic (worker provisioning) - CRITICAL for worker failures
   find .work/prow-job-analyze-install-failure/{build_id}/logs/ -path "*/control-plane/*/containers/metal3-ironic-*.log"
   find .work/prow-job-analyze-install-failure/{build_id}/logs/ -path "*/control-plane/*/containers/metal3-baremetal-operator-*.log"
   ```

3. **Analyze the Ironic logs**:

   **For Master Provisioning Issues** (check bootstrap logs):
   - Location: `bootstrap/journals/ironic.log` and `bootstrap/journals/metal3-baremetal-operator.log`
   - What to search: Master node UUIDs, master BareMetalHost names

   **For Worker Provisioning Issues** (check control-plane logs):
   - Location: `control-plane/{node-ip}/containers/metal3-ironic-*.log`
   - What to search: Worker node UUIDs, worker BareMetalHost names

4. **Map node UUIDs to BareMetalHost names**:
   - Ironic logs use node UUIDs (e.g., `b7fa5b83-91d0-46ee-acd2-e4b33e9ac983`)
   - Find the corresponding BareMetalHost name from installer logs or must-gather
   - This helps identify which specific worker or master failed

5. **Save Ironic analysis**:
   - Save findings to: `.work/prow-job-analyze-install-failure/{build_id}/analysis/ironic-summary.txt`
   - Include:
     - Which Ironic logs were checked (bootstrap vs control-plane)
     - Node UUIDs with errors
     - Specific error messages (SSL, BMC connection, etc.)
     - Whether masters or workers were affected

### Step 6: Analyze libvirt Console Logs

**Console logs are CRITICAL for metal failures during cluster creation.**

1. **Find console logs**
   ```bash
   find .work/prow-job-analyze-install-failure/{build_id}/logs/ -name "*console*.log"
   ```
   - Look for patterns like `{cluster-name}-bootstrap_console.log`, `{cluster-name}-master-{N}_console.log`

2. **Analyze console logs for boot/provisioning issues**:
   - **Kernel boot failures or panics**: Look for "panic", "kernel", "oops"
   - **Ignition failures**: Look for "ignition", "config fetch failed", "Ignition failed"
   - **Network configuration issues**: Look for "dhcp", "network unreachable", "DNS", "timeout"
   - **Disk mounting failures**: Look for "mount", "disk", "filesystem"
   - **Service startup failures**: Look for systemd errors, service failures

3. **Console logs show the complete boot sequence**:
   - As if you were watching a physical console
   - Shows kernel messages, Ignition provisioning, CoreOS startup
   - Critical for understanding what happened before the system was fully booted

4. **Save console log analysis**:
   - Save findings to: `.work/prow-job-analyze-install-failure/{build_id}/analysis/console-summary.txt`

### Step 7: Analyze sosreport

**Only needed for hypervisor-level issues.**

1. **Check sosreport for hypervisor diagnostics**:
   - `var/log/messages` - Hypervisor system log
   - `sos_commands/` - Output of diagnostic commands
   - `etc/libvirt/` - Libvirt configuration

2. **Look for hypervisor-level issues**:
   - Libvirt errors
   - Network configuration problems on hypervisor
   - Resource constraints (CPU, memory, disk)

### Step 8: Analyze squid-logs (If Downloaded)

**Important for debugging CI access to the cluster.**

1. **Check squid proxy logs**:
   - Look for failed connections from CI to the cluster
   - Look for HTTP errors or blocked requests
   - Check patterns of CI test framework access issues

2. **Common issues**:
   - CI unable to connect to cluster API
   - Proxy configuration errors blocking CI access
   - Network routing issues between CI and cluster
   - **Note**: These logs are for INBOUND access (CI → cluster), not for cluster's outbound access to registries

### Step 9: Generate Metal-Specific Analysis Report

1. **Create comprehensive metal analysis report**:
   ```
   Metal Installation Failure Analysis
   ====================================

   Job: {job-name}
   Build ID: {build_id}
   Prow URL: {original-url}

   Installation Method: dev-scripts + Metal3 + Ironic

   OFCIR Host Acquisition
   ----------------------
   Pool: {pool name from OFCIR build log}
   Provider: {provider from OFCIR build log}
   Host: {host name from OFCIR build log}
   Status: {Success or Failure}

   {If OFCIR acquisition failed, note that installation never started}

   Dev-Scripts Analysis
   --------------------
   {Summary of dev-scripts logs}

   Key Findings:
   - {First error in dev-scripts setup}
   - {Related errors}

   If dev-scripts failed: The problem is in the setup process (host config, Ironic, installer build)
   If dev-scripts succeeded: The problem is in cluster installation (see main analysis)

   Console Logs Analysis
   ---------------------
   {Summary of VM/node console logs}

   Bootstrap Node:
   - {Boot sequence status}
   - {Ignition status}
   - {Network configuration}
   - {Key errors}

   Master Nodes:
   - {Status for each master}
   - {Key errors}

   Hypervisor Diagnostics (sosreport)
   -----------------------------------
   {Summary of sosreport findings, if applicable}

   Proxy Logs (squid)
   ------------------
   {Summary of proxy logs, if applicable}
   Note: Squid logs show CI access to the cluster, not cluster's registry access

   Metal-Specific Recommended Steps
   ---------------------------------
   Based on the failure:

   For dev-scripts setup failures:
   - Review host configuration (networking, DNS, storage)
   - Check Ironic/Metal3 setup logs for BMC/provisioning issues
   - Verify installer build completed successfully
   - Check installer logs in devscripts folders

   For console boot failures:
   - Check Ignition configuration and network connectivity
   - Review kernel boot messages for hardware issues
   - Verify network configuration (DHCP, DNS, routing)

   For CI access issues:
   - Check squid proxy logs for failed CI connections to cluster
   - Verify network routing between CI and cluster
   - Check proxy configuration

   Artifacts Location
   ------------------
   Dev-scripts logs: .work/prow-job-analyze-install-failure/{build_id}/logs/devscripts/
   Console logs: .work/prow-job-analyze-install-failure/{build_id}/logs/
   sosreport: .work/prow-job-analyze-install-failure/{build_id}/logs/sosreport-*/
   squid logs: .work/prow-job-analyze-install-failure/{build_id}/logs/squid-logs-*/
   ```

2. **Save report**:
   - Save to: `.work/prow-job-analyze-install-failure/{build_id}/analysis/metal-analysis.txt`

### Step 10: Return Metal Analysis to Main Skill

1. **Provide summary to main skill**:
   - Brief summary of metal-specific findings
   - Indication of whether failure was in dev-scripts setup or cluster installation
   - Key error messages and recommended actions

## Common Metal Failure Patterns

| Issue | Symptoms | Where to Look |
|-------|----------|---------------|
| **Dev-scripts host config** | Early failure before cluster creation | Dev-scripts logs (host configuration step) |
| **Ironic/Metal3 setup** | Provisioning failures, BMC errors | Dev-scripts logs (Ironic setup) |
| **BMC communication** | BareMetalHost stuck registering, power state failures | Ironic logs (in log-bundle), BareMetalHost status |
| **Node boot failure** | VMs/nodes won't boot | Console logs (kernel, boot sequence) |
| **Ignition failure** | Nodes boot but don't provision | Console logs (Ignition messages) |
| **Network config** | DHCP failures, DNS issues | Console logs (network messages), dev-scripts host config |
| **CI access issues** | Tests can't connect to cluster | squid logs (proxy logs for CI → cluster access) |
| **Hypervisor issues** | Resource constraints, libvirt errors | sosreport (system logs, libvirt config) |

## Tips

- **Check dev-scripts logs FIRST**: They show setup and installation (dev-scripts invokes the installer)
- **Installer logs in devscripts**: Look for `.openshift_install*.log` files in devscripts directories
- **Check Ironic logs for BMC issues**: BareMetalHost provisioning failures usually show detailed errors in Ironic logs
- **Console logs are critical**: They show the actual boot sequence like a physical console
- **Ironic/Metal3 setup errors** often appear in dev-scripts setup logs
- **BMC communication errors** appear in Ironic container logs in the log-bundle
- **Squid logs are for CI access**: They show inbound CI → cluster access, not outbound cluster → registry
- **Boot vs. provisioning**: Boot failures appear in console logs, provisioning failures in Ironic logs
- **Layer distinction**: Separate dev-scripts setup from Ironic provisioning from OpenShift installation
