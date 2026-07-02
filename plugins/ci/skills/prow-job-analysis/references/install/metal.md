# Install Failure Analysis — Metal (Bare Metal)

Metal-specific supplement to [general.md](general.md), covering bare metal install failures that use dev-scripts, Metal3, and Ironic. Use **both** files for metal jobs: [general.md](general.md) owns the standard installer workflow (reading installer logs, log-bundle analysis, failure-stage identification); this file owns the metal layers on top.

## When to Use This Reference

Use when ANY of these are true:
- Job name contains `metal`, `baremetal`, `baremetalds`, or `sno` (single-node on metal)
- Job uses dev-scripts with Metal3/Ironic for provisioning
- Debugging OFCIR host acquisition, Ironic provisioning, or dev-scripts setup
- Console logs or sosreport analysis is needed

If the job name has no metal keyword, use [general.md](general.md) only.

---

## Metal Installation Stack

Metal IPI (Installer-Provisioned Infrastructure) jobs have distinct layers; failures can occur at any of them. Identifying which layer failed is the first step in analysis.

```text
┌─────────────────────────────────────────────────────┐
│  Layer 3: OpenShift Installation                    │
│  Standard installer runs on provisioned nodes       │
│  → Use general.md techniques for this layer         │
├─────────────────────────────────────────────────────┤
│  Layer 2: Ironic / Metal3 Provisioning              │
│  Provisions bare metal nodes (or VMs acting as BM)  │
│  → Ironic logs, BareMetalHost resources             │
├─────────────────────────────────────────────────────┤
│  Layer 1: dev-scripts Setup                         │
│  Configures hypervisor, networking, Ironic, builds  │
│  the installer binary                               │
│  → Dev-scripts numbered logs (01-05)                │
├─────────────────────────────────────────────────────┤
│  Layer 0: OFCIR Host Acquisition                    │
│  Acquires a physical or virtual host from the CI    │
│  resource pool before anything else runs            │
│  → OFCIR build-log.txt, junit_metal_setup.xml       │
└─────────────────────────────────────────────────────┘
```

### Key Components

- **dev-scripts** ([openshift-metal3/dev-scripts](https://github.com/openshift-metal3/dev-scripts)):
  Framework for setting up and installing OpenShift on bare metal. Configures the
  hypervisor, sets up networking, starts Ironic/Metal3 services, builds the installer,
  and orchestrates the install.

- **Metal3**: Kubernetes-native interface to Ironic. Manages `BareMetalHost` custom
  resources representing physical or virtual machines.

- **Ironic**: OpenStack bare metal provisioning service. Handles node enrollment,
  inspection, and deployment lifecycle.

- **OFCIR** (OpenShift Fleeting CI Resources): Acquires baremetal hosts from
  infrastructure provider pools for CI jobs.

---

## Metal CI Job Identification

### Job Naming Patterns

| Pattern in Job Name | Meaning |
|---------------------|---------|
| `metal` | Generic bare metal job |
| `baremetal` | Bare metal job (synonym) |
| `baremetalds` | Bare metal using dev-scripts |
| `metal-ipi` | Metal Installer-Provisioned Infrastructure |
| `metal-ipi-ovn-ipv6` | Metal IPI with IPv6-only networking (disconnected) |
| `metal-ipi-ovn-dualstack` | Metal IPI with dual-stack networking |
| `sno` | Single-Node OpenShift (often on metal) |
| `metal-assisted` | Metal using Assisted Installer |
| `metal-ipi-serial` | Metal IPI with serial console capture |

### Examples

```text
periodic-ci-openshift-release-master-ci-4.19-e2e-metal-ipi-ovn-ipv6
periodic-ci-openshift-release-master-nightly-4.19-e2e-metal-ipi-ovn-dualstack
periodic-ci-openshift-release-master-ci-4.19-e2e-metal-ipi-serial-ovn-ipv6
```

---

## Network Architecture

**CRITICAL**: "disconnected" in metal CI jobs refers to the **cluster nodes**, NOT the
hypervisor. This is the single most common misunderstanding in metal failure analysis.

### Hypervisor (dev-scripts host)

- **HAS** full internet access
- Downloads packages, container images, and dependencies from the public internet
- Runs dev-scripts Ansible playbooks that download tools (Go, installer, etc.)
- Hosts a local mirror registry to serve images to cluster nodes
- Runs the Squid proxy for inbound CI access to the cluster

### Cluster VMs/Nodes

- Run in a **private network** (often IPv6-only when `IP_STACK=v6`)
- **NO** direct internet access (truly disconnected)
- Pull container images from the hypervisor's local mirror registry
- Access to hypervisor services only (registry, DNS, DHCP, etc.)

### Network Topology Diagram

```text
┌──────────────────────────────────────────────────────────────┐
│  CI Infrastructure (Prow)                                    │
│                                                              │
│  ┌──────────┐     Squid Proxy      ┌──────────────────────┐ │
│  │ CI Tests ├──────(inbound)──────►│ Cluster API          │ │
│  └──────────┘                      │ (on cluster nodes)   │ │
│                                    └──────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Hypervisor (dev-scripts host)                         │  │
│  │  ✅ Full internet access                               │  │
│  │                                                        │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │  │
│  │  │ Mirror       │  │ Ironic       │  │ dnsmasq     │  │  │
│  │  │ Registry     │  │ Services     │  │ (DHCP/DNS)  │  │  │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘  │  │
│  │         │                 │                  │         │  │
│  │  ═══════╪═════════════════╪══════════════════╪═══════  │  │
│  │         │    Provisioning Network            │         │  │
│  │  ═══════╪═════════════════╪══════════════════╪═══════  │  │
│  │         │    Baremetal Network                │         │  │
│  │         │                 │                  │         │  │
│  │  ┌──────┴──┐  ┌──────────┴──┐  ┌───────────┴──┐      │  │
│  │  │Bootstrap│  │  Master-0   │  │  Master-1    │      │  │
│  │  │  Node   │  │             │  │              │      │  │
│  │  └─────────┘  └─────────────┘  └──────────────┘      │  │
│  │  ❌ No internet (disconnected)                        │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Common Misconception — AVOID

- ❌ **WRONG**: "The hypervisor cannot access the internet, so downloads fail"
- ✅ **CORRECT**: "The hypervisor has internet access. If downloads fail, it's likely
  the remote service is unavailable, not network restrictions."

### Implications for Failure Analysis

| Failure Location | What's Happening | Root Cause Direction |
|------------------|-----------------|---------------------|
| Dev-scripts (steps 01-05), download failures | Hypervisor can't download from internet | Remote service/URL is down or resource removed upstream |
| Dev-scripts, HTTP 403/404 | External resource not found | Resource removed from upstream source (not network restriction) |
| Installation (step 06+), image pull failures | Cluster nodes can't pull images | Check local mirror registry on hypervisor |
| Cluster nodes, DNS failures | Nodes can't resolve names | Check dnsmasq on hypervisor, not internet DNS |

---

## OFCIR (OpenShift Fleeting CI Resources)

OFCIR manages the pool of bare metal hosts for CI jobs. Before installation begins, the
job must acquire a host from an OFCIR pool.

### How OFCIR Works

1. Job requests a host from a specific pool (e.g., `cipool-ironic-cluster-el9`)
2. OFCIR checks pool availability and allocates a host
3. Host details (name, provider, IP) are returned to the job
4. Dev-scripts then provisions OpenShift on the acquired host

### OFCIR Artifact Locations

```text
{target}/ofcir-acquire/
├── build-log.txt                          # JSON with pool, provider, host details
└── artifacts/
    └── junit_metal_setup.xml              # JUnit test result for host acquisition
```

### Checking OFCIR Acquisition

```bash
# Download OFCIR logs
gcloud storage cp \
  "gs://test-platform-results/{bucket-path}/artifacts/{target}/ofcir-acquire/build-log.txt" \
  ./ofcir-build-log.txt --no-user-output-enabled 2>&1

# Download JUnit result
gcloud storage cp \
  "gs://test-platform-results/{bucket-path}/artifacts/{target}/ofcir-acquire/artifacts/junit_metal_setup.xml" \
  ./junit_metal_setup.xml --no-user-output-enabled 2>&1
```

### Interpreting OFCIR Results

**Check `junit_metal_setup.xml` first** — look for the test case:
```text
[sig-metal] should get working host from infra provider
```

If this test **failed**, OFCIR could not acquire a host and **installation never
started**. Stop here — the failure is purely infrastructure acquisition.

**Parse `build-log.txt`** for JSON fields:
```json
{
  "pool": "cipool-ironic-cluster-el9",
  "provider": "ironic",
  "name": "host-ci-1234"
}
```

Key fields:
- `pool`: OFCIR pool name (e.g., `cipool-ironic-cluster-el9`, `cipool-ibmcloud`)
- `provider`: Infrastructure provider (`ironic`, `equinix`, `aws`, `ibmcloud`)
- `name`: Specific host allocated

### Common OFCIR Failure Patterns

| Pattern | Symptoms | Likely Cause |
|---------|----------|-------------|
| Pool exhaustion | `junit_metal_setup.xml` fails, no host allocated | All hosts in pool are busy or unhealthy |
| Host acquisition timeout | Test fails after waiting | Pool capacity issue or OFCIR service problem |
| Stale host | Host acquired but immediately unusable | Previous job's deprovision left the host dirty/unusable |
| Provider error | Provider-specific error in build log | Infrastructure provider issue (e.g., Equinix API down) |

**If OFCIR fails**: Report that installation never started. Include pool name and
provider. Suggest checking OFCIR pool health and provider status.

---

## Dev-Scripts Environment

### What dev-scripts Does

Dev-scripts sets up the entire bare metal environment as a series of numbered steps on
the hypervisor:

| Step | Script | Purpose |
|------|--------|---------|
| 01 | `01_install_requirements.sh` | Install packages, dependencies |
| 02 | `02_configure_host.sh` | Configure hypervisor networking, storage, libvirt |
| 03 | `03_setup_ironic.sh` | Start Ironic/Metal3 services, configure BMC |
| 04 | `04_build_installer.sh` | Build or download the OpenShift installer binary |
| 05 | `05_create_install_config.sh` | Generate install-config.yaml |
| 06 | `06_create_cluster.sh` | Run the installer to create the cluster |

**Critical distinction**:
- Failures in steps **01-05** = dev-scripts setup problem (not an OpenShift install failure)
- Failures in step **06** = actual cluster installation failure (analyze with
  [general.md](general.md) techniques plus metal-specific artifacts)

### Dev-Scripts Log Location

```text
{target}/baremetalds-devscripts-setup/artifacts/root/dev-scripts/logs/
```

One log file per step. **Dev-scripts invokes the installer**, so `.openshift_install*.log`
files also appear in this directory tree.

### How to Download Dev-Scripts Logs

```bash
gcloud storage cp -r \
  "gs://test-platform-results/{bucket-path}/artifacts/{target}/baremetalds-devscripts-setup/artifacts/root/dev-scripts/logs/" \
  ./devscripts-logs/ --no-user-output-enabled
```

### Dev-Scripts Setup Failure Patterns

| Step | Common Failures | What to Look For |
|------|----------------|------------------|
| 01 (requirements) | Package install failures, dependency conflicts | `yum`/`dnf` errors, missing repos |
| 02 (host config) | Network bridge setup, libvirt configuration | Bridge errors, IP conflicts, libvirt XML errors |
| 03 (Ironic setup) | BMC connectivity, Ironic container startup | Container pull failures, port conflicts, cert errors |
| 04 (build installer) | Go build errors, download failures | Compiler errors, HTTP 404/403 on downloads |
| 05 (install-config) | Validation errors, missing credentials | Config validation messages |
| 06 (create cluster) | Full installation failure | See installer log analysis ([general.md](general.md)) |

### VM-Based Metal Simulation

In CI, "bare metal" nodes are actually **VMs managed by libvirt/QEMU** on the
hypervisor:

- **libvirt** manages VM lifecycle (create, start, stop, destroy)
- **QEMU** provides hardware emulation
- **Virtual BMC (vBMC)** simulates IPMI/Redfish BMC for each VM
- VMs are given virtual disks, NICs, and console output

Some failures originate in this simulation layer, not in OpenShift or Ironic. See
[Hardware Simulation Issues](#hardware-simulation-issues) below.

### Network Architecture in Dev-Scripts

Dev-scripts configures two networks on the hypervisor:

1. **Provisioning network** (`provisioning` bridge):
   - Used by Ironic for PXE boot and node inspection
   - dnsmasq provides DHCP and TFTP on this network
   - Nodes PXE boot from this network during initial provisioning

2. **Baremetal network** (`baremetal` bridge):
   - Primary cluster network
   - Used for all cluster communication after provisioning
   - dnsmasq provides DHCP and DNS on this network
   - External bridge for cluster connectivity

3. **External bridge** (optional):
   - Connects the baremetal network to the hypervisor's external network
   - Enables inbound CI access to the cluster

### Squid Proxy

Dev-scripts runs a Squid proxy on the hypervisor for **inbound** CI access — the CI test
framework connecting to the cluster API through the proxy.

**Important**: Squid is for **inbound** access (CI → cluster), NOT outbound
(cluster → registry). Cluster nodes access the mirror registry directly on the
hypervisor's internal network.

---

## Ironic and Metal3 Provisioning

### Ironic Service Architecture

Ironic runs as a set of containers on the bootstrap node (for master provisioning)
and later on the control plane (for worker provisioning):

| Service | Role |
|---------|------|
| `ironic` | Main provisioning service — manages node lifecycle |
| `ironic-inspector` | Hardware inspection service — discovers node hardware |
| `ironic-httpd` | HTTP server for serving boot images and configs |
| `dnsmasq` | DHCP/TFTP server for PXE boot on provisioning network |
| `metal3-baremetal-operator` | Kubernetes operator managing BareMetalHost resources |

### BareMetalHost Provisioning Lifecycle

Ironic manages nodes through a state machine. These states pinpoint where provisioning
stalled:

```text
enroll → manageable → inspecting → available → provisioning → deploying → active
  │          │             │            │            │             │
  │          │             │            │            │             └─ Node is running
  │          │             │            │            └─ Writing image to disk
  │          │             │            └─ Ready for deployment
  │          │             └─ Discovering hardware (CPU, RAM, disks, NICs)
  │          └─ BMC credentials verified, node is manageable
  └─ Initial registration with Ironic
```

**Failure transitions** (any state can go to):
```text
→ inspect failed   (inspection couldn't complete)
→ deploy failed    (image write or boot failed)
→ clean failed     (disk cleaning failed)
→ error            (generic error state)
```

### Where to Find Ironic Logs

**CRITICAL**: There are TWO sets of Ironic logs in different locations. Check the right
set based on what failed.

#### Bootstrap Ironic Logs (Master Provisioning)

During bootstrap, Ironic runs on the bootstrap node and provisions the masters.

```text
log-bundle-*/bootstrap/journals/ironic.log
log-bundle-*/bootstrap/journals/metal3-baremetal-operator.log
```

**Check these when**: Master nodes failed to provision, bootstrap phase failures.

#### Control-Plane Ironic Logs (Worker Provisioning)

After bootstrap, Ironic moves to the control plane and provisions workers.

```text
log-bundle-*/control-plane/{node-ip}/containers/metal3-ironic-*.log
log-bundle-*/control-plane/{node-ip}/containers/metal3-baremetal-operator-*.log
```

**Check these when**: Worker nodes failed to provision, post-bootstrap failures.

#### Decision Matrix

| What Failed | Which Ironic Logs to Check |
|-------------|---------------------------|
| Masters failed to provision | `bootstrap/journals/ironic.log` |
| Workers failed to provision | `control-plane/{ip}/containers/metal3-ironic-*.log` |
| Unsure which failed | Check ALL Ironic logs |
| Bootstrap timeout with no masters | `bootstrap/journals/ironic.log` first |

### How to Find and Read Ironic Logs

```bash
# Download and extract log bundle
gcloud storage ls -r "gs://test-platform-results/{bucket-path}/artifacts/" 2>&1 \
  | grep "log-bundle.*\.tar$"
gcloud storage cp {log-bundle-path} ./log-bundle.tar --no-user-output-enabled
tar -xf ./log-bundle.tar

# Find bootstrap Ironic logs (master provisioning)
find . -path "*/bootstrap/journals/ironic.log"
find . -path "*/bootstrap/journals/metal3-baremetal-operator.log"

# Find control-plane Ironic logs (worker provisioning)
find . -path "*/control-plane/*/containers/metal3-ironic-*.log"
find . -path "*/control-plane/*/containers/metal3-baremetal-operator-*.log"
```

### Mapping Node UUIDs to BareMetalHost Names

Ironic logs reference nodes by UUID (e.g., `b7fa5b83-91d0-46ee-acd2-e4b33e9ac983`),
but operators and kubectl output use BareMetalHost names. Correlate them:

```bash
# Search installer log for UUID-to-name mapping
grep -E "uuid|BareMetalHost" .openshift_install*.log

# Search Ironic logs for node registration
grep "Registering" ironic.log | head -20

# Look for mapping in must-gather BareMetalHost YAML
grep -r "uid:" baremetalhosts/
```

### Common Ironic Failure Patterns

| Pattern | Log Message | Cause |
|---------|------------|-------|
| BMC connection failure | `IPMI Error`, `Redfish connection refused` | BMC unreachable or wrong credentials |
| Inspection timeout | `Timeout waiting for node inspection` | Node didn't respond during hardware discovery |
| Deploy failure | `Deploy failed`, `Image write error` | Disk image couldn't be written to node |
| Power management error | `Failed to get power state`, `Power action failed` | Virtual BMC or IPMI issue |
| SSL/TLS error | `SSL: CERTIFICATE_VERIFY_FAILED` | Certificate mismatch between Ironic components |
| Node stuck registering | `BareMetalHost stuck in registering` | BMC communication failure during registration |
| Provisioning state stuck | `Node {uuid} stuck in {state}` | State machine transition blocked |

### Key Ironic Log Patterns to Search

```bash
# BMC errors
grep -i "ipmi\|redfish\|bmc" ironic.log | grep -i "error\|fail\|timeout"

# Provisioning state changes
grep "provision_state" ironic.log

# Node registration
grep -i "register\|enroll" ironic.log

# Deploy operations
grep -i "deploy\|provision" ironic.log | grep -i "error\|fail"

# SSL/TLS issues
grep -i "ssl\|certificate\|tls" ironic.log | grep -i "error\|fail"

# Power management
grep -i "power" ironic.log | grep -i "error\|fail"
```

---

## DHCP, PXE Boot, and Network Boot

### Boot Sequence

Metal nodes boot through a network boot sequence managed by dnsmasq on the
provisioning network:

```text
1. Node powers on (via IPMI/Redfish from Ironic)
2. Node PXE boots from provisioning network
3. dnsmasq provides DHCP lease + TFTP boot file
4. Node downloads and boots iPXE/GRUB
5. iPXE fetches RHCOS kernel + initramfs from Ironic's httpd
6. RHCOS boots and runs Ignition
7. Ignition configures the node (networking, services, etc.)
8. Node joins the cluster
```

### dnsmasq Configuration

dnsmasq serves dual duty in dev-scripts:

- **On provisioning network**: DHCP + TFTP for PXE boot
- **On baremetal network**: DHCP + DNS for cluster networking

### PXE Boot Failure Patterns

| Failure Point | Symptoms | Diagnosis |
|---------------|----------|-----------|
| DHCP timeout | Node never gets an IP | Check dnsmasq logs, provisioning network bridge |
| TFTP error | Node gets IP but can't download boot files | Check dnsmasq TFTP config, boot file paths |
| Boot image download | iPXE starts but fails to fetch kernel | Check Ironic httpd logs, image URLs |
| Wrong boot order | Node boots from disk instead of network | Check VM/node boot configuration |

### Where to Find Network Boot Logs

```bash
# dnsmasq logs (in sosreport or dev-scripts logs)
grep -i "dnsmasq" sosreport-*/var/log/messages
grep -i "dhcp\|tftp\|pxe" sosreport-*/var/log/messages

# Ironic httpd logs (image serving)
grep -i "httpd\|GET\|404\|500" ironic.log
```

---

## Serial Console Logs

Serial console logs capture the complete boot output from each VM/node as if watching a
physical serial console. They are **invaluable** for failures that occur before the node
is fully operational.

### Location and Extraction

```text
{target}/baremetalds-devscripts-gather/artifacts/libvirt-logs.tar
```

```bash
# Download and extract
gcloud storage cp \
  "gs://test-platform-results/{bucket-path}/artifacts/{target}/baremetalds-devscripts-gather/artifacts/libvirt-logs.tar" \
  ./libvirt-logs.tar --no-user-output-enabled
tar -xf ./libvirt-logs.tar

# Find console logs
find . -name "*console*.log"
# Typical names:
#   {cluster-name}-bootstrap_console.log
#   {cluster-name}-master-0_console.log
#   {cluster-name}-master-1_console.log
#   {cluster-name}-master-2_console.log
```

### What Console Logs Reveal

The complete boot sequence, as the node would display it on a physical serial port:

1. **BIOS/UEFI boot** — Hardware initialization
2. **PXE/iPXE boot** — Network boot sequence
3. **Kernel boot** — Linux kernel initialization
4. **initramfs** — Early userspace
5. **Ignition** — CoreOS configuration
6. **systemd services** — Service startup
7. **kubelet/crio** — Container runtime and kubelet startup

### Key Patterns to Search in Console Logs

```bash
# Kernel panics and oops
grep -i "panic\|kernel.*oops\|BUG:" *console*.log

# Ignition failures (critical for provisioning)
grep -i "ignition\|config fetch failed\|Ignition failed" *console*.log

# Network issues during boot
grep -i "dhcp\|network unreachable\|DNS\|timeout\|no carrier" *console*.log

# Disk and filesystem errors
grep -i "mount\|disk\|filesystem\|I/O error\|readonly" *console*.log

# systemd service failures
grep -i "Failed to start\|service.*failed\|Unit.*failed" *console*.log

# Memory issues
grep -i "Out of memory\|oom\|Cannot allocate" *console*.log

# Hardware errors
grep -i "hardware error\|MCE\|machine check" *console*.log

# SSH key and authentication
grep -i "authorized_keys\|sshd\|authentication" *console*.log
```

### Console Log vs. Other Logs

| Scenario | Best Log Source |
|----------|---------------|
| Node never boots at all | Console log — will show where boot stopped |
| Node boots but Ignition fails | Console log — Ignition messages appear here |
| Node boots but doesn't join cluster | Console log + Ironic log + installer log |
| Node joins but operator fails | Installer log + must-gather (not console) |
| Kernel panic during boot | Console log — the only place this appears |

---

## Assisted Installer on Metal

Some metal CI jobs use the **Assisted Installer** (agent-based installation) instead of
the traditional IPI flow.

### Agent-Based Installation

- Uses a **Discovery ISO** booted on target nodes
- An **agent** on each node reports hardware inventory
- The **Assisted Service** validates hosts and orchestrates installation
- Job names may contain `metal-assisted` or `agent`

### Host Validation Failures

The Assisted Installer validates each host before installation proceeds:
- Sufficient CPU, memory, and disk
- Network connectivity between hosts
- DNS resolution
- NTP synchronization
- Compatible hardware

Look for validation errors in the Assisted Service logs or the agent logs on each node.

### Discovery ISO Issues

- ISO download failures (check image cache)
- Boot from ISO failures (check console logs)
- Agent registration failures (check agent logs)

---

## Image-Related Issues

### RHCOS Image Download Failures

During provisioning, Ironic downloads the RHCOS (Red Hat CoreOS) disk image and writes
it to each node's disk. Failures here block provisioning.

```bash
# Check for image download errors in Ironic logs
grep -i "image\|download\|rhcos" ironic.log | grep -i "error\|fail\|timeout"

# Check Ironic httpd for image serving errors
grep -i "GET.*rhcos\|404\|500" ironic-httpd.log
```

**Common causes**:
- Image URL changed or was removed upstream
- Image cache on hypervisor is corrupted or full
- Network timeout during large image download
- Disk space exhaustion on hypervisor preventing image caching

### Image Caching

Dev-scripts caches RHCOS images on the hypervisor to avoid repeated downloads. If the
cache is corrupted or stale:

```bash
# Check image cache in dev-scripts logs
grep -i "cache\|image.*download\|pulling" devscripts-logs/*
```

### Disk Image Writing Failures

After download, Ironic writes the image to the node's virtual disk:

```bash
# Check for write failures in Ironic logs
grep -i "write\|deploy.*fail\|disk" ironic.log | grep -i "error\|fail"
```

**Common causes**:
- Insufficient disk space on target node
- Disk I/O errors (especially in VM environments)
- Image corruption during transfer
- qcow2/raw format mismatch

---

## Hardware Simulation Issues

Since CI metal jobs use VMs to simulate bare metal, failures can originate in the
virtualization layer.

### Virtual BMC (vBMC) Failures

Virtual BMC provides IPMI/Redfish endpoints for each VM, letting Ironic manage them as
physical machines.

```bash
# Check for vBMC errors
grep -i "vbmc\|virtualbmc\|virtual.*bmc" devscripts-logs/*
grep -i "ipmi\|redfish" ironic.log | grep -i "connect\|refuse\|timeout"
```

**Common vBMC issues**:
- vBMC service didn't start for one or more VMs
- Port conflicts preventing vBMC from listening
- vBMC crashed or became unresponsive

### libvirt/QEMU Issues

```bash
# Check libvirt errors in sosreport
grep -i "libvirt\|qemu\|kvm" sosreport-*/var/log/messages
grep -i "error\|fail\|refuse" sosreport-*/var/log/libvirt/*.log

# Check VM definitions
ls sosreport-*/etc/libvirt/qemu/
```

**Common libvirt issues**:
- VM failed to create (insufficient resources)
- VM crashed during boot (QEMU errors)
- Storage pool issues (disk space, permissions)
- CPU model incompatibilities

### Virtual Disk/Network Device Problems

```bash
# Disk issues
grep -i "virtio.*disk\|vda\|sda\|I/O error" *console*.log

# Network device issues
grep -i "virtio.*net\|eth0\|ens\|no carrier\|link.*down" *console*.log
```

---

## Network-Specific Metal Failures

### Bridge Configuration Issues

Dev-scripts creates network bridges (`provisioning`, `baremetal`) on the hypervisor.
Misconfiguration prevents nodes from communicating.

```bash
# Check bridge configuration in sosreport
grep -i "bridge\|brctl" sosreport-*/sos_commands/networking/*
cat sosreport-*/sos_commands/networking/ip_-d_link 2>/dev/null

# Check dev-scripts network setup logs
grep -i "bridge\|network\|interface" devscripts-logs/02_*
```

### VLAN/Bond Failures

Some metal jobs test advanced networking configurations:

```bash
# Check for VLAN errors
grep -i "vlan\|802.1q" *console*.log devscripts-logs/*

# Check for bond errors
grep -i "bond\|lacp\|aggregat" *console*.log devscripts-logs/*
```

### IPv6 SLAAC/DHCPv6 Issues

IPv6-only metal jobs are particularly prone to addressing issues:

```bash
# Check IPv6 address configuration
grep -i "ipv6\|slaac\|dhcpv6\|router.*advert\|fe80\|fd00" *console*.log

# Check for IPv6 connectivity issues
grep -i "network unreachable\|no route\|icmpv6" *console*.log

# Check dnsmasq DHCPv6 configuration
grep -i "dhcpv6\|ra-param\|enable-ra" devscripts-logs/*
```

**Common IPv6 issues on metal**:
- Router advertisements not reaching nodes
- DHCPv6 lease not obtained
- SLAAC address conflicts
- DNS resolution failures over IPv6
- NDP (Neighbor Discovery Protocol) issues

---

## Metal-Specific Artifact Reference

### Complete Artifact Map

```text
artifacts/{target}/
├── ofcir-acquire/
│   ├── build-log.txt                              # OFCIR host acquisition log
│   └── artifacts/
│       └── junit_metal_setup.xml                   # Host acquisition JUnit result
│
├── baremetalds-devscripts-setup/
│   └── artifacts/root/dev-scripts/logs/            # Dev-scripts setup logs
│       ├── 01_install_requirements.log
│       ├── 02_configure_host.log
│       ├── 03_setup_ironic.log
│       ├── 04_build_installer.log
│       ├── 05_create_install_config.log
│       ├── 06_create_cluster.log
│       ├── .openshift_install.log                  # Installer log (dev-scripts invokes installer)
│       └── .openshift_install_state.json
│
├── baremetalds-devscripts-gather/
│   └── artifacts/
│       ├── libvirt-logs.tar                        # VM console logs
│       │   └── {cluster}-bootstrap_console.log
│       │   └── {cluster}-master-0_console.log
│       │   └── {cluster}-master-1_console.log
│       │   └── {cluster}-master-2_console.log
│       ├── log-bundle-*.tar                        # Log bundle with Ironic logs
│       │   └── bootstrap/journals/
│       │   │   ├── ironic.log                      # Master provisioning
│       │   │   ├── metal3-baremetal-operator.log
│       │   │   ├── bootkube.log
│       │   │   └── kubelet.log
│       │   └── control-plane/{node-ip}/containers/
│       │       ├── metal3-ironic-*.log              # Worker provisioning
│       │       └── metal3-baremetal-operator-*.log
│       ├── sosreport-*.tar.xz                      # Hypervisor diagnostics
│       └── squid-logs-*.tar                        # CI access proxy logs
```

### Downloading All Metal Artifacts

```bash
# OFCIR logs
gcloud storage cp \
  "gs://test-platform-results/{bucket-path}/artifacts/{target}/ofcir-acquire/build-log.txt" \
  ./ofcir-build-log.txt --no-user-output-enabled 2>&1 || echo "Not found"

# Dev-scripts logs
gcloud storage cp -r \
  "gs://test-platform-results/{bucket-path}/artifacts/{target}/baremetalds-devscripts-setup/artifacts/root/dev-scripts/logs/" \
  ./devscripts-logs/ --no-user-output-enabled

# Console logs
gcloud storage ls -r \
  "gs://test-platform-results/{bucket-path}/artifacts/" 2>&1 | grep "libvirt-logs\.tar$"
# Then: gcloud storage cp {path} ./libvirt-logs.tar --no-user-output-enabled
# Then: tar -xf ./libvirt-logs.tar

# Log bundle (with Ironic logs)
gcloud storage ls -r \
  "gs://test-platform-results/{bucket-path}/artifacts/" 2>&1 | grep "log-bundle.*\.tar$"
# Then: gcloud storage cp {path} ./log-bundle.tar --no-user-output-enabled
# Then: tar -xf ./log-bundle.tar

# sosreport (optional)
gcloud storage ls -r \
  "gs://test-platform-results/{bucket-path}/artifacts/" 2>&1 | grep "sosreport.*\.tar\.xz$"
# Then: gcloud storage cp {path} ./sosreport.tar.xz --no-user-output-enabled
# Then: tar -xf ./sosreport.tar.xz

# Squid proxy logs (optional, for IPv6/disconnected)
gcloud storage ls -r \
  "gs://test-platform-results/{bucket-path}/artifacts/" 2>&1 | grep "squid-logs.*\.tar$"
# Then: gcloud storage cp {path} ./squid-logs.tar --no-user-output-enabled
# Then: tar -xf ./squid-logs.tar
```

---

## sosreport Analysis

The sosreport captures hypervisor-level diagnostics. Use it when the failure appears to
be in the hypervisor itself rather than in OpenShift.

### Key sosreport Contents

```text
sosreport-{hostname}-*/
├── var/log/
│   ├── messages                        # System log — libvirt, kernel, service errors
│   └── libvirt/                        # Libvirt-specific logs
├── etc/
│   └── libvirt/
│       └── qemu/                       # VM definitions (XML)
├── sos_commands/
│   ├── networking/                     # Network configuration dumps
│   │   ├── ip_-d_link                  # Interface details
│   │   ├── ip_-d_addr                  # IP addresses
│   │   ├── ip_route_show_table_all     # Routing tables
│   │   └── bridge_-t_-s_vlan_show     # Bridge/VLAN info
│   ├── libvirt/                        # Libvirt diagnostic output
│   ├── process/                        # Process lists
│   └── memory/                         # Memory diagnostics
```

### When to Use sosreport

- Hypervisor resource exhaustion (CPU, memory, disk)
- libvirt/QEMU crashes or errors
- Network bridge or interface problems on the hypervisor
- Kernel errors or panics on the hypervisor itself
- Storage pool issues

### Key sosreport Searches

```bash
# Resource exhaustion
grep -i "out of memory\|oom\|no space left\|disk full" sosreport-*/var/log/messages

# libvirt errors
grep -i "libvirt\|qemu" sosreport-*/var/log/messages | grep -i "error\|fail"

# Network issues on hypervisor
grep -i "bridge\|bond\|link.*down\|no carrier" sosreport-*/var/log/messages

# Kernel errors
grep -i "kernel.*error\|BUG\|oops\|panic" sosreport-*/var/log/messages
```

---

## Squid Proxy Log Analysis

The Squid proxy runs on the hypervisor to provide **inbound** access from CI
infrastructure to the cluster under test, especially in IPv6/disconnected environments.

### What Squid Logs Show

- CI test runner connections to the cluster API
- HTTP status codes for CI-to-cluster requests
- Connection timeouts or refusals
- Proxy configuration issues

### Location

```text
{target}/baremetalds-devscripts-gather/artifacts/squid-logs-*.tar
```

### Key Squid Log Patterns

```bash
# Failed connections
grep -i "TCP_DENIED\|ERR_CONNECT\|TIMEOUT\|503\|502" squid-logs-*/access.log

# Connection patterns
grep -i "CONNECT\|api\|oauth" squid-logs-*/access.log | tail -20

# Configuration errors
grep -i "error\|fail\|denied" squid-logs-*/cache.log
```

### Common Squid Issues

| Pattern | Meaning |
|---------|---------|
| `TCP_DENIED` | Proxy blocked the connection (ACL issue) |
| `ERR_CONNECT_FAIL` | Target unreachable (cluster API down) |
| `TIMEOUT` | Connection timed out (network issue or cluster unresponsive) |
| Many 503s | Cluster API not ready or overloaded |

Squid logs show CI → cluster access. If cluster nodes can't reach the mirror registry,
that's a different issue (check dnsmasq and network config, not Squid).

---

## Metal Analysis Workflow — Step by Step

### Step 1: Check OFCIR Acquisition

Did the job get a host? If `junit_metal_setup.xml` shows a failure, stop here.
Report: "OFCIR host acquisition failed — installation never started."

### Step 2: Read Dev-Scripts Logs

Read the numbered logs in order. Identify the **first step that failed**.
- Steps 01-05 failed → dev-scripts setup issue (not an OpenShift bug)
- Step 06 failed → proceed to installation analysis

### Step 3: Check Console Logs (if available)

Extract and read `libvirt-logs.tar`. Look for:
- Kernel panics
- Ignition failures
- Network configuration problems during boot
- Disk/filesystem errors

### Step 4: Check Ironic Logs (from log bundle)

Determine whether masters or workers failed, then check the matching Ironic logs:
- Bootstrap Ironic → master provisioning issues
- Control-plane Ironic → worker provisioning issues

Map node UUIDs to BareMetalHost names to identify specific failing nodes.

### Step 5: Analyze Installer Logs

Use the techniques from [general.md](general.md): work backwards from the end of the log,
focus on final errors (not early transient ones), and track dependency chains.

### Step 6: Check Optional Artifacts

If the root cause is still unidentified:
- **sosreport**: hypervisor-level issues
- **Squid logs**: CI access problems (IPv6/disconnected jobs)

---

## Common Metal Failure Patterns — Quick Reference

| Issue | Symptoms | Primary Artifact | Resolution Hints |
|-------|----------|------------------|-----------------|
| **OFCIR pool exhaustion** | No host acquired | `junit_metal_setup.xml` | Wait for pool capacity; check pool health |
| **Dev-scripts package failure** | Step 01 fails | Dev-scripts log 01 | Check package repos, dependencies |
| **Network bridge failure** | Step 02 fails, no connectivity | Dev-scripts log 02 | Check libvirt network config |
| **Ironic container failure** | Step 03 fails | Dev-scripts log 03 | Check container image availability |
| **Installer build failure** | Step 04 fails | Dev-scripts log 04 | Check Go toolchain, source availability |
| **Install-config error** | Step 05 fails | Dev-scripts log 05 | Check config template, credentials |
| **BMC connection refused** | Nodes stuck registering | Ironic log | Check vBMC, IPMI port availability |
| **Inspection timeout** | Nodes stuck inspecting | Ironic log | Check provisioning network DHCP |
| **Deploy failure** | Nodes stuck deploying | Ironic log | Check RHCOS image, disk space |
| **Kernel panic** | Node crash during boot | Console log | Check hardware/VM configuration |
| **Ignition failure** | Node boots but misconfigured | Console log | Check Ignition config URL, MCS access |
| **DHCP timeout** | No IP address obtained | Console log + dnsmasq | Check provisioning network, dnsmasq |
| **Mirror registry down** | Image pull failures | Dev-scripts log, installer log | Check registry pod on hypervisor |
| **CI access failure** | Tests can't reach cluster | Squid logs | Check proxy config, network routing |
| **Hypervisor OOM** | Random VM crashes | sosreport | Check hypervisor memory allocation |
| **Disk space exhaustion** | Image downloads fail | sosreport, dev-scripts log | Check hypervisor disk usage |

---

## Tips and Best Practices

- **Check dev-scripts logs FIRST** — they show setup AND installation (dev-scripts
  invokes the installer). Most information-dense starting point.

- **Installer logs live in devscripts directories** — `.openshift_install*.log` files
  are inside the dev-scripts log directory, not just the standard location.

- **Console logs are irreplaceable** — for any boot-level or pre-OS failure, they are
  the only source of truth for kernel panics, Ignition errors, and network boot issues.

- **Check the RIGHT Ironic logs** — bootstrap Ironic covers master provisioning;
  control-plane Ironic covers worker provisioning.

- **Separate the layers** — identify which layer (OFCIR, dev-scripts, Ironic, OpenShift)
  failed first. Chasing an OpenShift issue when dev-scripts setup failed wastes time.

- **Squid is for inbound access** — CI → cluster, NOT cluster → registry.

- **"Disconnected" means the nodes** — the hypervisor always has internet. Don't
  attribute hypervisor download failures to disconnected networking.

- **Boot vs. provisioning** — boot failures appear in console logs; provisioning
  failures appear in Ironic logs.

- **Map UUIDs to names** — Ironic logs use node UUIDs; map them to BareMetalHost names
  for clear reporting.

- **IPv6 adds complexity** — IPv6-only environments have extra failure modes around
  SLAAC, DHCPv6, and NDP. Check these explicitly in IPv6 jobs.
