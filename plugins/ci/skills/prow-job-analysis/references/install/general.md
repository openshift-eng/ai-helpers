# Install Failure Analysis — General

**Use when** a CI job fails an `install should succeed` test, or when an upgrade job fails during
its initial install phase (before the upgrade begins). Definitive workflow for OpenShift install
failures on **all** platforms: classify the failure, locate artifacts, identify the failed stage,
diagnose root cause.

For bare metal jobs (name contains "metal" or "baremetal"), you must read [metal.md](metal.md)
(dev-scripts, Ironic, libvirt console logs).

---

## Quick-Start Investigation Workflow

Follow this sequence for every install failure:

1. **Parse the job name** → Identify platform, job type, and special modes (§ Job Type Identification)
2. **Download and parse `junit_install.xml`** → Determine the failure stage (§ Failure Stage Classification)
3. **Check symptom labels** → Collect machine-detected environmental context (§ Symptom Labels)
4. **Download installer logs** → `.openshift_install*.log`, excluding deprovision (§ Installer Logs)
5. **Download the log bundle** → find the `log-bundle-*` directory (recent jobs store it exploded) or the `log-bundle-*.tar`, then pull its full contents (§ Log Bundle Analysis)
6. **Analyze based on failure stage** → Route to the correct diagnostic section (§ Stage-Specific Analysis)
7. **Check must-gather availability** → For cluster creation / operator stability failures (§ Must-Gather)
8. **Synthesize root cause** → Combine evidence from all sources (§ Root Cause Determination)

---

## Job Type Identification

Job names encode the test environment. Parse these patterns to know what to expect.

### Platform Detection

| Pattern in Name | Platform | Notes |
|-----------------|----------|-------|
| `aws` | Amazon Web Services | Most common platform |
| `gcp` | Google Cloud Platform | |
| `azure` | Microsoft Azure | |
| `vsphere` | VMware vSphere | |
| `openstack` | Red Hat OpenStack | |
| `metal`, `baremetal` | Bare metal | Route to [metal.md](metal.md) for metal-specific analysis |
| `ovirt` | oVirt/RHV | |
| `nutanix` | Nutanix | |
| `ibmcloud` | IBM Cloud | |
| `powervs` | IBM Power VS | |
| `none` | Platform-agnostic | No platform-specific infrastructure provisioning |

### Installation Type Detection

| Pattern in Name | Install Type | Key Characteristics |
|-----------------|-------------|---------------------|
| (default — no special pattern) | IPI (Installer-Provisioned Infrastructure) | Installer manages all cloud resources |
| `upi` | UPI (User-Provisioned Infrastructure) | External infra provisioning, installer configures cluster |
| `assisted` | Assisted Installer | Agent-based installation workflow |
| `single-node`, `sno` | Single-Node OpenShift | All workloads on one node; prone to resource exhaustion |
| `compact` | Compact cluster | 3-node cluster with schedulable control plane |
| `microshift` | MicroShift | Minimal single-node OpenShift variant |

### Special Mode Detection

| Pattern in Name | Mode | Implications for Analysis |
|-----------------|------|---------------------------|
| `upgrade` | Upgrade job | Performs a **fresh install first**, then upgrades. Installation failures are still install failures — the upgrade never started |
| `upgrade-from-stable-4.X` | Minor upgrade | Installs previous minor version (e.g., 4.20 for a 4.21 job), then upgrades |
| `upgrade` without `upgrade-from-stable` | Micro upgrade | Installs earlier payload in same stream, then upgrades to newer |
| `fips` | FIPS mode | Watch for crypto library errors, TLS/SSL handshake failures, certificate validation issues, hash algorithm incompatibilities |
| `ipv6` | IPv6 networking | Usually **disconnected** (no internet), uses local mirror registry |
| `dualstack` | Dual-stack IPv4/IPv6 | May be disconnected |
| `techpreview` | TechPreview feature gates | Enables additional feature gates not active in Default clusters. Bootstrap failures may be in TechPreview-gated code paths (e.g., on-cluster layering, OS image management) that won't reproduce in Default clusters |
| `proxy` | HTTP proxy environment | Cluster traffic routed through proxy |
| `rt` | Real-time kernel | Uses real-time RHCOS kernel |
| `ovn` | OVN-Kubernetes networking | Standard CNI plugin |
| `sdn` | OpenShift SDN | Legacy CNI plugin |

### Upgrade Jobs and Installation Failures

Jobs with "upgrade" in the name perform a **fresh install first**, then upgrade. If the install
fails, the upgrade never begins — analyze it as a pure **installation failure**. The installed
version is:

- **Major upgrade** (e.g. 4→5): the newest release of the previous major (a 5.0 job installs the latest 4.x first)
- **Minor upgrade** (`upgrade-from-stable-4.X`): the *previous* minor release (a 4.21 job installs 4.20 first)
- **Micro upgrade** (no `upgrade-from-stable`): an earlier build of the same minor release

---

## Failure Stage Classification

### Locating junit_install.xml

`junit_install.xml` is the authoritative source for the failure stage. Location varies by job
config — always search for it:

```bash
# Search recursively for junit_install.xml
gcloud storage ls -r "gs://test-platform-results/{bucket-path}/artifacts/" 2>&1 \
  | grep "junit_install.xml"
```

**`{bucket-path}` is the *specific job run's* path** (e.g. `logs/{job-name}/{build-id}` for
periodics, `pr-logs/pull/{org}_{repo}/{pr}/{job-name}/{build-id}` for presubmits). Always scope
every `gcloud storage` command to this single run — go up a level and you enumerate tens of
thousands of unrelated jobs.

`install-status.txt` holds only the installer's exit code (a single number); `junit_install.xml`
translates it into a human-readable failure mode. **Always prefer `junit_install.xml`.**

### Failure Modes

The JUnit file contains `install should succeed: <stage>` test cases. Failed cases indicate the
failure mode:

| JUnit Failure Mode | Installation Stage | What Failed | Primary Logs |
|-------------------|-------------------|-------------|--------------|
| `configuration` | Pre-installation | Failed to create install-config.yaml. Extremely rare — validation errors or missing fields | Installer log only (no log bundle exists) |
| `infrastructure` | Infrastructure creation | Failed before creating all cloud resources. Often cloud quota, rate limiting, or API outages | Installer log — cloud API errors (log bundle may be partial or absent) |
| `cluster bootstrap` | Bootstrap phase | Failed to bootstrap the cluster. Bootstrap is typically an ephemeral VM running a temporary kube-apiserver | Log bundle: bootkube.log, etcd.log, kube-apiserver.log |
| `cluster creation` | Operator initialization | One or more operators was unable to stabilize after bootstrap completed | gather-must-gather (if available), installer log |
| `cluster operator stability` | Operator stabilization | Operators never reached stable state (available=True, progressing=False, degraded=False) | Operator-specific logs in must-gather (if available) |
| `other` | Unknown | Unknown install failure — could be any of the above or something novel | Full log analysis of all available artifacts required |

### Installation Stages in Detail

The full lifecycle, to target analysis:

1. **Pre-installation** (Failure mode: `configuration`)
   - Validation of `install-config.yaml`
   - Credential checks
   - Image resolution
   - **Common failures**: Invalid install-config, missing required fields, validation errors

2. **Infrastructure Creation** (Failure mode: `infrastructure`)
   - Creating cloud resources (VMs, networks, load balancers, DNS records, storage)
   - **Provisioning methods** vary by OpenShift version:
     - **Newer versions**: Use **Cluster API (CAPI)** — look for Machine/MachineSet/MachineDeployment errors
     - **Older versions**: Use **Terraform** — look for terraform state/apply errors in installer log
   - **Common failures**: Quota exceeded, rate limiting, API outages, permission/credential errors

3. **Bootstrap** (Failure mode: `cluster bootstrap`)
   - Bootstrap node boots with temporary control plane
   - Bootstrap etcd and kube-apiserver start
   - Bootstrap creates master nodes via machine-API or CAPI
   - **Common failures**: etcd won't start, API server won't start, bootkube errors, network issues

4. **Master Node Bootstrap**
   - Master nodes boot and join bootstrap etcd cluster
   - Masters form permanent control plane
   - Bootstrap control plane transfers to masters
   - **Common failures**: Masters can't reach bootstrap, network/DNS issues, ignition failures

5. **Bootstrap Complete**
   - Bootstrap node is decommissioned
   - Masters run permanent control plane
   - Cluster operators begin initialization
   - **Common failures**: Control plane not transferring, master nodes not ready

6. **Cluster Operator Initialization** (Failure mode: `cluster creation`)
   - Core cluster operators start deploying
   - Operators create their managed workloads
   - Initial operator stabilization begins
   - **Common failures**: Operators can't deploy, resource conflicts, dependency issues

7. **Cluster Operator Stabilization** (Failure mode: `cluster operator stability`)
   - Operators reach stable state: `available=True`, `progressing=False`, `degraded=False`
   - Worker nodes join the cluster
   - **Common failures**: Operators stuck progressing, degraded state, availability issues

8. **Install Complete**
   - All cluster operators are available and stable
   - Cluster is fully functional
   - Installation succeeded

---

## Key Artifact Paths

### Installer Logs

`.openshift_install.log` is the single most important artifact — it records every installer step.

```bash
# Find installer logs (IMPORTANT: exclude deprovision logs)
gcloud storage ls -r "gs://test-platform-results/{bucket-path}/artifacts/" 2>&1 \
  | grep -E "\.openshift_install.*\.log$" | grep -v "deprovision"
```

- **Format**: structured log with timestamp, level, message
  ```text
  time="2025-03-15T10:23:45Z" level=info msg="Creating infrastructure resources..."
  time="2025-03-15T10:24:12Z" level=error msg="Failed to create VPC: QuotaExceeded"
  ```
- **Log levels**: `info`, `warning`, `error`, `fatal`
- Deprovision logs (cluster teardown) are NOT relevant to install failures — always exclude them
- Multiple logs may exist (retries, multiple install phases) — download all non-deprovision logs

### Log Bundle

The log bundle contains node-level diagnostics collected during or after the install attempt. For
cloud IPI jobs the installer collects it (via the `gather-bootstrap` step); search recursively:

```bash
# Find log bundles (prefer non-deprovision) — matches the exploded dir and the legacy tarball
gcloud storage ls -r "gs://test-platform-results/{bucket-path}/artifacts/" 2>&1 \
  | grep "log-bundle"
```

GCS stores artifacts **decompressed** — CI gunzips everything to sweep for secrets, so bundles are
`log-bundle-*.tar` (never `.tar.gz`). Recent jobs go further and upload the bundle **exploded** as a
`log-bundle-*/` directory instead of a tarball; locate that directory and download its full
contents with `gcloud storage cp -r`. Prefer non-deprovision bundles — they capture the failure
state during installation.

### Log Bundle Structure

```text
log-bundle-{timestamp}/
├── bootstrap/
│   ├── journals/
│   │   ├── bootkube.log          # Bootstrap control plane initialization (CRITICAL)
│   │   ├── kubelet.log           # Bootstrap kubelet
│   │   ├── crio.log              # Container runtime
│   │   ├── ironic.log            # (Metal only) Ironic provisioning
│   │   ├── metal3-baremetal-operator.log  # (Metal only)
│   │   └── journal.log.gz        # Complete system journal (gzipped)
│   └── network/
│       ├── ip-addr.txt           # IP addresses
│       ├── ip-route.txt          # Routing table
│       └── hostname.txt          # Hostname
├── serial/
│   ├── {cluster}-bootstrap-serial.log    # Bootstrap node console
│   └── {cluster}-master-N-serial.log     # Master node consoles
├── clusterapi/
│   ├── etcd.log                  # etcd cluster logs (CRITICAL)
│   ├── kube-apiserver.log        # API server logs (CRITICAL)
│   └── *.yaml                    # Kubernetes resource definitions
├── control-plane/
│   └── {node-ip}/
│       └── containers/           # Control plane container logs
├── failed-units.txt              # Failed systemd units (STRONG indicator)
└── gather.log                    # Log bundle collection process log
```

### Other Important Artifacts

| Artifact | Path Pattern | Purpose |
|----------|-------------|---------|
| `prowjob.json` | `{build-id}/prowjob.json` | Job metadata (target, timing, refs, state) |
| `build-log.txt` | `{build-id}/build-log.txt` | ci-operator orchestration log |
| `metadata.json` | `artifacts/{target}/ipi-install-install/artifacts/metadata.json` | Cluster metadata (cluster ID, infra ID) |
| Ignition configs | `artifacts/{target}/ipi-install-install/artifacts/*.ign` | Machine ignition configurations |
| Symptom labels | `artifacts/job_labels/*.json` | Machine-detected symptom patterns |
| `install-status.txt` | `artifacts/{target}/.../install-status.txt` | Installer exit code (prefer junit_install.xml) |
| Must-gather | `artifacts/{target}/gather-must-gather/artifacts/must-gather.tar` | Cluster state diagnostic archive |

---

## Reading the Installer Log Effectively

### CRITICAL: Eventual Consistency Behavior

The single most important concept: installs exhibit **eventual consistency**. Components report
errors while waiting for dependencies to become ready (e.g. ingress waits on networking, which
waits on DNS, which waits on the API server). These intermediate errors are **expected and
normal**, and **early errors often resolve themselves — they are NOT the root cause.**

### Error Analysis Strategy: Work Backwards

**Always start at the END of the installer log and work backwards:**

1. **Read the LAST error/fatal messages** — the most important; they show what was still broken
   when the install timed out.
2. **Find the final "Still waiting for..." message** — identifies which component(s) failed to
   stabilize (e.g. `"Cluster operators X, Y, Z are not available"`).
3. **Read 10-20 lines of context** around the final errors for the immediate circumstances.
4. **Trace backwards** to the earliest persistent error for the component from step 1.
5. **Ignore early errors that disappeared** — an error at minute 5 not recurring after minute 10
   was transient startup noise, not the root cause.

**Example**: install fails at 40 min with "kube-apiserver not available"; a "ingress operator
degraded" error at 5 min is likely irrelevant. Focus on what was still broken at the 40-min mark.

### Key Log Patterns

#### Final/Fatal Errors
```text
level=fatal msg="Install failed: ..."
level=error msg="Cluster operator authentication Degraded is True..."
level=error msg="context deadline exceeded"
```

#### Timeout / Waiting Messages
```text
level=info msg="Still waiting for the cluster to initialize..."
level=info msg="Cluster operators authentication, console, monitoring still initializing"
level=warning msg="Cluster operator X has not yet been available"
```

#### Infrastructure Provisioning Errors
```text
level=error msg="Failed to create ...": cloud API errors
level=error msg="Error creating vpc": quota/rate limit
level=error msg="terraform apply"  # older versions
level=error msg="clusterapi"  # newer versions
```

#### Bootstrap Phase Errors
```text
level=info msg="Waiting up to 20m0s for the Kubernetes API..."
level=error msg="Failed waiting for Kubernetes API"
level=info msg="Waiting up to 30m0s for bootstrapping to complete..."
level=error msg="Failed to wait for bootstrapping to complete"
```

#### Cluster Operator Status Messages
```text
level=info msg="Cluster operator console Available is False..."
level=error msg="Cluster operators dns, ingress, monitoring are not available"
level=warning msg="Cluster operator X conditions: ..."
```

### Timestamp Correlation

The installer log uses ISO 8601 timestamps (`time="2025-03-15T10:23:45Z"`). Use them to:
- Build an event timeline
- Correlate installer log entries with log bundle entries
- Measure how long components were failing before the timeout
- Determine which error appeared first in a failure chain

---

## Stage-Specific Analysis

### Configuration Failures

**Failure mode**: `configuration` in junit_install.xml

**Extremely rare** — the installer fails to create or validate `install-config.yaml`.

**What to check** (installer log only — no log bundle exists):
- Validation errors: missing required fields, invalid values
- Credential format errors
- Image resolution failures

**Common patterns**:
```text
level=fatal msg="failed to fetch Install Config: ..."
level=error msg="invalid install-config.yaml: ..."
```

### Infrastructure Failures

**Failure mode**: `infrastructure` in junit_install.xml

Occurs before the cluster is created — the installer cannot provision the required cloud resources.

**What to check**:
- **Primary**: installer log — search for cloud provider API errors
- Log bundle is usually absent or incomplete

**Common causes by platform**:

| Platform | Common Errors | Log Pattern |
|----------|--------------|-------------|
| AWS | Quota exceeded, rate limiting, capacity | `RequestLimitExceeded`, `InsufficientInstanceCapacity`, `VcpuLimitExceeded` |
| GCP | Quota exceeded, rate limiting | `QUOTA_EXCEEDED`, `rateLimitExceeded` |
| Azure | Quota exceeded, operation not allowed | `QuotaExceeded`, `OperationNotAllowed` |
| vSphere | Connection timeouts, resource pool | `context deadline exceeded`, connection refused |
| OpenStack | Quota, floating IP exhaustion | `No more IP addresses`, quota errors |

**Provisioning method** (varies by OpenShift version):
- **Newer**: **Cluster API (CAPI)** — search installer log for `clusterapi`/`machine-api` and
  Machine/MachineSet/MachineDeployment errors
- **Older**: **Terraform** — search for `terraform apply` failures and terraform state errors

**Distinguish from product bugs**: most infra failures are transient (quota, rate limiting, cloud
outages), not product bugs. If the same job succeeds on retry, it was likely transient infra.

### Bootstrap Failures

**Failure mode**: `cluster bootstrap` in junit_install.xml

The most complex failure mode. The bootstrap node is an ephemeral VM running a temporary control
plane (kube-apiserver, etcd) to orchestrate creating the permanent control plane on masters.

**CRITICAL**: You MUST thoroughly examine the log bundle. Do not guess from a single error —
build a complete timeline.

**Analysis procedure**:

1. **Read `bootstrap/journals/bootkube.log` thoroughly** — the most important file. Identify
   every process that started, crashed, or errored; note timestamps for a chronological
   sequence. For any crashed process (non-zero exit, `ContainerDied`), read its stderr/stdout
   in surrounding lines.
2. **For crashed processes**: exit codes tell you *that* it crashed; error output tells you
   *why*. Validate the termination reason — check for OOM kills, host restarts, kill-by-signal,
   resource limits (consult surrounding logs and infra signals like dmesg/journal entries and
   resource utilization). Distinguish software defects from infra/resource-induced terminations.
3. **Pursue errors**: read context, follow references to other components' logs, trace causation
   back to the originating failure. The first error is often a symptom, not the cause.
4. **Check supporting logs** (cross-reference timestamps with `bootkube.log`):
   - `clusterapi/kube-apiserver.log` — API server startup and errors
   - `clusterapi/etcd.log` — etcd cluster formation and member health
   - `bootstrap/journals/kubelet.log` — kubelet container management
5. **Check serial console logs**: `serial/{cluster-name}-bootstrap-serial.log` — look for kernel
   panics, ignition failures, disk errors, network configuration issues.
6. **Check `failed-units.txt`** — failed systemd units; strong indicator of specific service failures.

**Common bootstrap failure patterns**:

| Pattern | Symptom | Root Cause Investigation |
|---------|---------|------------------------|
| etcd won't start | `bootkube.log`: etcd container crashes or restarts | Check `clusterapi/etcd.log`, bootstrap network config, disk performance |
| API server won't start | `bootkube.log`: kube-apiserver crash loops | Check `clusterapi/kube-apiserver.log`, etcd health, certificate issues |
| Masters can't join bootstrap | Masters never appear in etcd member list | Check master serial logs, network connectivity, DNS resolution |
| Bootstrap VM network issues | DHCP failures, unreachable addresses | Check `bootstrap/network/`, serial console log |
| Ignition failure | Bootstrap or master fails to provision | Check serial logs for ignition errors |
| Certificate issues | TLS handshake errors, cert validation fails | Check time sync, cert generation in bootkube.log |
| Disk pressure | Components killed or evicted | Check for OOM, disk full in journal/serial logs |

### Cluster Creation Failures

**Failure mode**: `cluster creation` in junit_install.xml

The cluster bootstrapped, but one or more operators failed to deploy and stabilize.

**What to check**:

1. **Installer log** — the final "Cluster operators X, Y, Z are not available" message
   identifies which operators failed.
2. **Must-gather availability** — check if `must-gather*.tar` exists:
   ```bash
   gcloud storage ls "gs://test-platform-results/{bucket-path}/artifacts/{target}/gather-must-gather/artifacts/" 2>&1 \
     | grep "must-gather.*\.tar"
   ```
   - **Yes**: extract and examine operator-specific logs.
   - **No**: cluster was too unstable to collect diagnostics — rely on installer log and log
     bundle only. **Do NOT suggest downloading must-gather if the .tar file doesn't exist.**
3. **Operator logs in must-gather** (if available): degraded operators and their conditions,
   operator-specific logs for the failing operators, resource conflicts or dependency issues.
4. **Log bundle** — may add context on operator deployment.

### Cluster Operator Stability Failures

**Failure mode**: `cluster operator stability` in junit_install.xml

Like cluster creation, but operators reached a partially running state and couldn't fully stabilize.

**What to check**:
- Operators with `available=False`, `progressing=True`, or `degraded=True`
- Operator logs for stuck operations
- Time-series of operator status changes; operators flipping between states
- Must-gather availability before suggesting to review it (same as cluster creation)

**Common operator stability failure patterns**:

| Operator | Common Issues | Where to Look |
|----------|--------------|---------------|
| `authentication` | OAuth server issues, identity provider config | OAuth pods, authentication operator logs |
| `console` | Console deployment fails, route issues | Console namespace pods |
| `ingress` | Router pods not ready, DNS issues | Ingress controller logs, DNS operator |
| `monitoring` | Prometheus/alertmanager startup | Monitoring namespace, PVC issues |
| `network` | OVN/SDN initialization | Network operator, ovnkube pods |
| `dns` | CoreDNS pods not ready | DNS operator logs |
| `image-registry` | Storage backend issues | Image registry operator, PVC |
| `kube-apiserver` | API server rollout issues | Kube-apiserver operator logs |
| `etcd` | Member health, quorum | etcd operator, etcd pod logs |

### Other / Unknown Failures

**Failure mode**: `other` in junit_install.xml

Catch-all for failures that don't match a known pattern.

**What to check**:
- Comprehensive analysis of ALL available logs
- Installer log for any error/fatal messages
- Log bundle if available
- Unusual patterns or timeout messages
- Whether the failure matches a known pattern but was misclassified

---

## Common Install Failure Categories

### API Server Not Coming Up

**Symptoms**: `"Waiting for Kubernetes API"` timeout, kube-apiserver crash loops in bootkube.log

**Investigation**:
- Check `clusterapi/kube-apiserver.log` for startup errors
- Check etcd health — API server depends on etcd
- Verify certificates and TLS configuration
- Check bootstrap network connectivity
- Look for resource exhaustion (OOM kills)

### etcd Bootstrap Failures

**Symptoms**: etcd container crashes in bootkube.log, "etcd cluster unhealthy" messages

**Investigation**:
- Check `clusterapi/etcd.log` for member formation errors
- Verify network connectivity between bootstrap and master nodes
- Check disk I/O performance (etcd is latency-sensitive)
- Look for DNS resolution failures preventing member discovery

### Machine Provisioning Failures

**Symptoms**: "machine has not yet been provisioned", machine stuck in provisioning state

**Investigation**:
- Installer log for CAPI/machine-api errors
- Cloud provider API errors (quota, capacity)
- For metal: Ironic provisioning logs (see [metal.md](metal.md))
- Security group / network configuration issues

### Certificate Issues

**Symptoms**: TLS handshake errors, x509 certificate verification failures, "certificate has expired"

**Investigation**:
- Check time synchronization between nodes
- Look for cert generation errors in bootkube.log
- Check if FIPS mode is affecting certificate handling
- Review cert-manager or cert rotation operator logs

### DNS Resolution Failures

**Symptoms**: "no such host", "DNS lookup failed", unresolved service names

**Investigation**:
- Check CoreDNS pod status
- Verify DNS operator health
- Check `bootstrap/network/` for DNS configuration
- For disconnected environments: verify local DNS resolver setup
- For IPv6: check AAAA record availability

### Network Connectivity Issues

**Symptoms**: "connection refused", "connection timed out", "no route to host"

**Investigation**:
- Check `bootstrap/network/ip-addr.txt` and `ip-route.txt`
- Verify security group / firewall rules on cloud platform
- Check for MTU mismatches (especially with overlay networks)
- For IPv6/dualstack: verify IPv6 addressing and routing
- For proxy environments: check proxy configuration

### Cloud Credential Issues

**Symptoms**: "AccessDenied", "AuthFailure", "Forbidden", IAM errors

**Investigation**:
- Check installer log for cloud API authentication errors
- Verify service account / IAM role configuration
- Check if credentials expired during long-running installation
- See [cloud-provider-errors.md](../cloud-provider-errors.md) for platform-specific patterns

### Image Pull Failures During Install

**Symptoms**: `ImagePullBackOff`, `ErrImagePull`, "failed to pull image"

**Investigation**:
- Check if the image repository is accessible
- For disconnected environments: verify mirror registry configuration
- Check for image tag resolution failures
- Verify pull secrets are correctly configured
- Check registry certificate trust

### Operator Timeout During Install

**Symptoms**: "context deadline exceeded", operators not reaching available=True

**Investigation**:
- Identify which specific operators failed (from installer log final messages)
- Check operator-specific logs in must-gather (if available)
- Look for dependency chains: operator A waiting on operator B
- Check for resource exhaustion preventing pod scheduling
- Verify all required images are pullable

---

## Symptom Labels

The CI system may attach **symptom labels** — machine-detected patterns stored as JSON artifacts
in `job_labels/` that provide environmental context.

### Locating Symptom Labels

Download the `job_labels/*.json` files with the commands in the
[`job_labels/` section of artifacts.md](../artifacts.md#job_labels--symptom-labels).

### Using Symptom Labels

Each JSON file describes a detected symptom with a summary and explanation.

**IMPORTANT**: symptoms are **environmental observations**, NOT definitive root causes. They
inform your investigation but you must still do thorough root cause analysis. For example, "test
failures during high CPU events" means CPU pressure was detected during the failure window — it
could explain the failure absent another root cause, but is not proof of causation.

Include symptom labels in the "Known Symptoms Seen" section of your report.

---

## Must-Gather Analysis for Install Failures

Must-gather provides cluster-state diagnostics captured after the install attempt. It is only
relevant to `cluster creation` and `cluster operator stability` failures, where the cluster came
up far enough to be partially operational; for `configuration`, `infrastructure`, and `cluster
bootstrap` failures it is normally absent. If no `must-gather*.tar` exists, collection failed
because the cluster was too unstable — say so rather than suggesting a download.

For locating, downloading, and extracting must-gather, and what to look for inside it, use the
must-gather reference: [artifacts.md § Must-Gather Archives](../artifacts.md#must-gather-archives).

---

## Log Bundle Analysis Workflow

### When Log Bundles Are Available

Log bundles are produced once the install reaches the bootstrap phase or later. **Not available**
for `configuration` or early `infrastructure` failures.

| Failure Mode | Log Bundle Available? |
|--------------|----------------------|
| `configuration` | No |
| `infrastructure` | Partial or No |
| `cluster bootstrap` | Yes (primary diagnostic source) |
| `cluster creation` | Yes |
| `cluster operator stability` | Yes |
| `other` | Varies |

### Downloading and Extracting the Log Bundle

```bash
# Exploded form (recent jobs): copy the whole log-bundle-*/ directory — no extraction needed
gcloud storage cp -r "{gcs-path-to-log-bundle-dir}" \
  .work/prow-job-analysis/{build_id}/logs/ --no-user-output-enabled

# Legacy tarball form: download, then extract (GCS stores it decompressed as .tar)
gcloud storage cp {gcs-path-to-log-bundle} \
  .work/prow-job-analysis/{build_id}/logs/ --no-user-output-enabled
tar -xf .work/prow-job-analysis/{build_id}/logs/log-bundle-*.tar \
  -C .work/prow-job-analysis/{build_id}/logs/
```

### Analysis by Failure Mode

Per-mode procedures live in [§ Stage-Specific Analysis](#stage-specific-analysis). The one
log-bundle-specific step: for **`cluster bootstrap`**, read `bootkube.log` and build a timeline,
cross-reference `etcd.log` / `kube-apiserver.log` / `kubelet.log`, check serial consoles for
kernel panics / Ignition failures, and check `failed-units.txt`.

---

## Distinguishing Install Failure from Test Failure

Distinguish "installation failed" from "installation succeeded but tests failed":

| Signal | Installation Failed | Installation Succeeded, Tests Failed |
|--------|--------------------|------------------------------------|
| JUnit XML | `install should succeed: <stage>` test is **failed** | `install should succeed` test is **passed** (or absent) |
| Build log | "Install failed" or fatal installer error | Install completes, test steps execute and fail |
| Installer log | Contains `level=fatal` | Contains `level=info msg="Install complete!"` |
| CI step | Failure in `ipi-install-install` or similar install step | Failure in `openshift-e2e-test` or similar test step |

If installation **succeeded** but tests failed, use the test failure analysis workflow instead
(see this skill's test failure references, e.g. `test-extension-binaries.md`).

---

## Routing to Metal-Specific Analysis

When the job name contains `metal` or `baremetal`, consult [metal.md](metal.md), which covers:

- **OFCIR host acquisition** — whether a bare metal host was acquired
- **Dev-scripts logs** — setup before OpenShift install (dev-scripts invoke the installer, so
  installer logs appear in devscripts directories)
- **Ironic/Metal3 provisioning** — BMC communication, node registration, power management
  - Bootstrap Ironic logs (master provisioning): `bootstrap/journals/ironic.log`
  - Control-plane Ironic logs (worker provisioning): `control-plane/{ip}/containers/metal3-ironic-*.log`
- **libvirt console logs** — VM boot sequence, kernel panics, ignition failures
- **sosreport** — hypervisor-level system diagnostics
- **squid proxy logs** — CI inbound access to the cluster (NOT outbound cluster access)

**Disconnected metal network architecture**: the hypervisor (dev-scripts host) HAS full internet
access; only the cluster VMs/nodes are disconnected. If downloads fail during dev-scripts setup,
check whether the remote service is down — it's not a network restriction.

This document still applies to metal jobs for the cluster-level failure; metal.md adds the
infrastructure layer below the installer.

---

## Root Cause Determination

### Synthesizing Evidence

Combine all sources to determine the root cause:

1. **Installer log** — what the installer saw and reported
2. **Log bundle** — node-level detail of what happened during bootstrap
3. **Must-gather** — cluster state after partial install (if available)
4. **Symptom labels** — environmental context (informational, not causal)
5. **JUnit XML** — the classified failure stage

### Prioritizing Evidence

- **Final errors are most important** — what was still broken at timeout
- **Persistent errors matter** — errors appearing throughout the log
- **Transient early errors usually don't matter** — eventual consistency
- **Infrastructure errors are usually not product bugs** — quota, rate limiting, outages
- **Operator dependency chains** — trace from symptomatic operator to root-cause operator

### Common Root Cause Patterns

| Observation | Likely Root Cause | Verification |
|-------------|-------------------|-------------|
| Cloud API errors in installer log | Quota/capacity/outage | Check cloud provider status, retry the job |
| etcd won't form cluster | Network issues between nodes | Check bootstrap network config, DNS |
| Multiple operators degraded | Upstream dependency failed | Find the root operator in the dependency chain |
| Image pull failures | Registry unreachable or image missing | Check pull secret, registry connectivity |
| Pods evicted or OOMKilled | Resource exhaustion | Check node resource utilization |
| TLS/cert errors in FIPS job | FIPS crypto incompatibility | Check FIPS-specific code paths |
| Bootstrap timeout, no errors | Possible network/DNS issue | Check serial logs, network config |
| Single operator degraded | Operator-specific bug or config | Check operator logs, recent code changes |

---

## Analysis Report Template

Use this structure when generating install failure analysis reports:

```text
OpenShift Installation Failure Analysis
========================================

Job: {job-name}
Build ID: {build_id}
Platform: {aws/gcp/azure/etc.}
Job Type: {IPI/UPI/SNO/etc.}
Prow URL: {original-url}

Failure Stage: {stage from junit_install.xml}

Known Symptoms Seen
---------------------
(Only include if symptom labels were found — omit section entirely if none)
- {symptom summary}: {symptom explanation}
Note: Symptoms are machine-detected environmental observations, not
definitive causes.

Summary
-------
{High-level summary of the failure — 2-3 sentences}

Installer Log Analysis
----------------------
{Key findings from installer log}

Final Error:
{Last error/fatal message with timestamp}

Last Waiting Message:
{Final "Still waiting for..." or "Cluster operators X, Y, Z are not available"}

Context:
{10-20 lines surrounding the final error}

Log Bundle Analysis
-------------------
{Findings from log bundle analysis}

Failed Units:
{List from failed-units.txt, if any}

Key Journal Errors:
{Important errors from bootkube.log, etcd.log, kube-apiserver.log}

Root Cause
----------
{The identified root cause with supporting evidence}

Recommended Next Steps
----------------------
{Actionable debugging steps based on failure mode}

Artifacts Location
------------------
All artifacts downloaded to:
.work/prow-job-analysis/{build_id}/logs/

- Installer logs: .openshift_install*.log
- Log bundle: log-bundle-*/
- Must-gather: must-gather/ (if available)
```

---

## Tips and Best Practices

### Critical Rules

1. **ALWAYS work backwards from the end of the installer log** — not forwards. Early errors are
   usually transient (eventual consistency).
2. **Never suggest downloading must-gather unless you verified the .tar file exists.** If absent,
   the cluster was too unstable to collect diagnostics.
3. **Bootstrap failures REQUIRE log bundle analysis** — the installer log alone is insufficient.
4. **Distinguish infrastructure failures from product bugs.** Quota, rate limiting, and API
   outages are transient. If the same job succeeds on retry, it was likely infrastructure.
5. **Separate install failures from test failures.** If the `install should succeed` case passed,
   the install succeeded and the failure is in the test phase.

### Investigation Efficiency

- **Start with `junit_install.xml`** to identify the failure stage — it guides which logs to prioritize
- **Use grep liberally** on large logs — don't read multi-thousand-line logs sequentially
- **Cache artifacts** in `.work/prow-job-analysis/{build_id}/` for re-analysis
- **Exclude deprovision logs/bundles** — they're from teardown, not install
- **Check `failed-units.txt`** — a strong, quick indicator of what went wrong

### Job Name Clues

- **FIPS**: check crypto-related errors first
- **IPv6/disconnected**: check mirror registry accessibility, DNS resolution
- **Single-node (SNO)**: check resource exhaustion (all workloads on one node)
- **TechPreview**: bootstrap failures may be in TechPreview-gated code paths that won't reproduce
  in Default clusters
- **Upgrade**: if install fails, the upgrade never started — analyze as a pure install failure

### File Format Notes

| File Type | Format | Notes |
|-----------|--------|-------|
| Installer log | Structured text (`time=... level=... msg=...`) | Primary analysis source |
| Journal logs | systemd journal format (plain text export) | From log bundle `bootstrap/journals/` |
| Serial logs | Raw console output | Boot sequence, kernel messages |
| YAML files | Kubernetes resource definitions | From `clusterapi/` in log bundle |
| `.gz` files | gzip compressed | Some journal logs are gzipped |
| `.tar` files | tar archive (NOT gzip) | Log bundles are `.tar`, not `.tar.gz` |

---

## Failure Mode Quick Reference

| JUnit Failure Mode | Installation Stage | Where to Look First | Log Bundle? | Must-Gather? |
|-------------------|-------------------|---------------------|-------------|-------------|
| `configuration` | Pre-installation | Installer log only | No | No |
| `infrastructure` | Infrastructure creation | Installer log — cloud API errors | Partial/No | No |
| `cluster bootstrap` | Bootstrap | Log bundle — bootkube, etcd, kube-apiserver | Yes (primary) | No |
| `cluster creation` | Operator initialization | Must-gather (if available), installer log | Yes | Maybe |
| `cluster operator stability` | Operator stabilization | Must-gather (if available), operator logs | Yes | Maybe |
| `other` | Unknown | All available logs | Varies | Varies |
