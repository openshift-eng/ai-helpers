# Operating System Changes Reference

Use when no other failure mode explains the cause and you suspect an operating system
level problem — kernel, cri-o, NetworkManager, systemd, SELinux, rpm-ostree, or bootloader
changes. The node OS is RHCOS (Red Hat CoreOS), the immutable OS every OpenShift node boots. A
single RHCOS bump inside a payload swaps the kernel, cri-o, systemd, NetworkManager, and SELinux
policy across the whole cluster at once, so it breaks many unrelated jobs with no product-code PR
to blame.
Route here when:

- Containers fail to start or die at runtime (`cri-o`, `crun`, `runc`, OCI/cgroup errors)
- Node networking breaks after boot (NetworkManager, host interface/route/DNS)
- A node kernel-panics, hangs, or never returns Ready after a reboot
- Nodes fail Ignition/first-boot, or `rpm-ostree`/boot fails to apply an OS update
- A failure appears **only** on one RHCOS variant (RHCOS 10 but not RHCOS 9, or the reverse)
- SELinux denials, failed systemd units, or filesystem errors surface in node journals

**Use a different reference for:**

- MCO **drain/reboot stalls** and MachineConfigPool mechanics →
  [upgrade.md](upgrade.md#mco-drain-failures--the-1-upgrade-problem) (owns the drain cascade)
- In-cluster **networking** (OVN-Kubernetes/SDN, DNS, ingress, IP exhaustion) →
  [networking.md](networking.md)
- **OOM / node pressure / disk / PID** exhaustion → [resource-exhaustion.md](resource-exhaustion.md)
- CPU-starvation / OVS-stall **disruption** interpretation → [disruption.md](disruption.md)
- OS problems **during install** (bootstrap, Ignition, serial console) →
  [install/general.md](install/general.md); metal console/sosreport →
  [install/metal.md](install/metal.md)
- Full artifact tree → [artifacts.md](artifacts.md)

## What RHCOS Is

RHCOS is an immutable, `rpm-ostree`-managed RHEL image shipped **as a component of the release
payload** (image-stream tags `rhel-coreos` and `rhel-coreos-10`), not installed per node. Nodes
never `yum install`; the entire OS is a versioned tree that the MCO deploys and the node boots
into. Two variants ship today:

| Variant | Base | Job-name fragment | `rhcos_version` values |
|---------|------|-------------------|------------------------|
| RHCOS 9 | RHEL 9 | none (4.x default) or `rhcos9` | `rhcos9`, `rhcos9-default` |
| RHCOS 10 | RHEL 10 | `rhcos10` | `rhcos10`, `rhcos10-default` |
| Heterogeneous | both | `rhcos9_10` | `rhcos9_10` |

RHCOS 10 carries a **different kernel, systemd, SELinux policy, and package set** than RHCOS 9.
When both exist in a payload, a bug can be confined to one variant — see
[Variant Isolation](#variant-isolation-the-strongest-signal).

## How an RHCOS Change Reaches a Node

```text
payload bumps rhel-coreos image  →  machine-config-operator renders a new MachineConfig
  →  machine-config-daemon (one pod per node) picks it up
    →  cordon → drain → rpm-ostree deploy new OS tree → reboot into it → uncordon
      →  repeats one node at a time per MachineConfigPool (master pool, then worker pool)
```

An OS change and a config change travel the **same MCO path**, which splits the debugging:

- The **drain/reboot** half (PDBs, stuck nodes, MCP `Degraded`) is the #1 upgrade failure and is
  owned by [upgrade.md](upgrade.md#mco-drain-failures--the-1-upgrade-problem).
- The **OS-content** half — what changed inside the booted tree (kernel, cri-o, NetworkManager,
  systemd) — is this reference.

## When to Suspect the OS Layer

Work top-down; the first two are the highest-signal.

### Variant Isolation (the strongest signal)

A failure that hits RHCOS 10 jobs and **zero** RHCOS 9 jobs (or the reverse) is almost certainly
an OS-variant difference — kernel, systemd, SELinux, or a package that differs between RHEL 9 and
RHEL 10. Heterogeneous (`rhcos9_10`) jobs count toward both variants; when only their RHCOS-10
nodes fail, treat it as RHCOS-10-isolated. This narrows the search at once and points at the
platform/RHCOS team, not the product PR under test.

### Payload-Boundary, Cross-Job Blast Radius

An RHCOS bump lands at a **payload boundary** and affects every job that consumes that payload.
Signature: a class of failures that begins on one nightly/CI payload, spans unrelated components,
and matches no product PR. Confirm the onset aligns with a payload on
[search.ci](https://search.ci.openshift.org/) or [Sippy](https://sippy.dptools.openshift.org/),
then compare the RHCOS RPM diff for that payload ([next section](#comparing-rhcos-between-payloads)).

### Host-Level Symptom

The failing component runs on the host, below Kubernetes: cri-o/crun/runc, the kernel,
NetworkManager, systemd, SELinux, or the filesystem/bootloader. These speak in **node journals
and serial consoles**, not in operator pod logs — see [Failure Patterns](#failure-patterns) and
[Artifact Locations](#artifact-locations).

## Comparing RHCOS Between Payloads

For payload debugging, the release controller and the payload snapshot expose a **deep RPM-level
changelog** between an RHCOS version and its predecessor — the fastest way to see what actually
changed in the OS.

- **Release-controller changelog** — the payload diff (`changelog.json`) carries a top-level
  `nodeImageStreams` block: per-variant RPM diffs (added/removed/changed packages) between this
  payload and the previous one.
- **Payload snapshot** ([payload-snapshot](../../payload-snapshot/SKILL.md)) persists this as
  `summary.json` → `payloads[].rhcos_changes[]` (per-variant `rpmDiff`, keyed by tag
  `rhel-coreos` / `rhel-coreos-10`) and extracts the full RPM database to
  `rpmdb/<variant>/rpmdb.sqlite`:

  ```bash
  # every RPM in a variant, at exact NEVRA
  rpm -qa --dbpath "$(pwd)/payload/<version>/<stream>/<tag>/rpmdb/rhel-coreos-10"
  ```

- Map the failing job to its variant (`rhcos_version` in the snapshot's job entry), then read
  that variant's `rpmDiff` for the job's originating payload. Overlap between the diff and the
  failure's subsystem (kernel / systemd / cri-o / NetworkManager / SELinux) is the correlation.

**RHCOS RPM changes are not revert candidates** — they cannot be pulled out of a payload like a
PR. Surface them as **RHCOS RPM suspects** for the RHCOS/platform team, with the variant, the
package NEVRA delta, and a rationale. Full suspect-scoring workflow:
[payload-analysis](../../payload-analysis/SKILL.md).

## Identifying the RHCOS Version on a Node

From gathered cluster state (no live cluster needed):

- `gather-extra/artifacts/oc_cmds/nodes` — the node `OSImage` (e.g.
  `Red Hat Enterprise Linux CoreOS 9.x`) plus `KernelVersion` and `ContainerRuntimeVersion` under
  `.status.nodeInfo`.
- must-gather `cluster-scoped-resources/core/nodes/*.yaml` — the same fields per node.

The `OSImage` string is the quickest confirmation of which RHEL base (9 vs 10) a node booted.

## Failure Patterns

| Symptom / log string | OS subsystem | Where to look |
|----------------------|--------------|---------------|
| `CreateContainerError`, `RunContainerError`, `failed to create OCI runtime`, `error reserving ctr name`, crun/runc errors | cri-o / crun / runc | crio journal + `crio_service.log`; pod events |
| Runtime ↔ kubelet mismatch after a bump, `CRI-O` version errors, cgroup v1/v2 errors | cri-o / kubelet | `crio_service.log`, `kubelet_service.log`, journal |
| Node loses connectivity **after boot**, missing IP/route, `NetworkManager-wait-online` unit fails | NetworkManager | node journal (`NetworkManager` unit), serial console |
| `Kernel panic - not syncing`, `BUG:`, `Oops`, `soft lockup`, `Call Trace:`; node never returns Ready after reboot | kernel | serial console; journal (previous boot) |
| systemd unit `failed` / `start-limit-hit`; degraded first boot | systemd | `failed-units.txt`, journal, serial console |
| `avc:  denied`, `SELinux is preventing` after an OS bump | SELinux policy | node journal (`audit` / `setroubleshoot`) |
| `read-only file system`, xfs/ext4 errors, mount or `rpm-ostree` deploy failures | storage / rpm-ostree | journal, serial console |
| Ignition first-boot failure (fresh install) | ignition / afterburn | serial console, log bundle → [install/general.md](install/general.md) |

Container-start and NetworkManager issues dominate day-to-day OS debugging; kernel panics and
Ignition failures usually keep a node from ever becoming Ready — check the serial console first.

## Artifact Locations

| Artifact | Path | OS signal |
|----------|------|-----------|
| Node journals | `gather-extra/artifacts/journal_logs/` | kernel, NetworkManager, crio, kubelet, systemd per node |
| crio/kubelet host logs | must-gather `host_service_logs/masters/{crio,kubelet}_service.log` | runtime & kubelet decisions at the host level |
| Failed units | log bundle / must-gather `failed-units.txt` | which systemd units failed (fast first look) |
| Serial console | `log-bundle-*/serial/*-serial.log`; metal `libvirt-logs.tar` | kernel panic, boot hang, Ignition — the only place a pre-Ready node speaks |
| Node OS/kernel/runtime | `gather-extra/artifacts/oc_cmds/nodes` (`.status.nodeInfo`) | `OSImage`, `KernelVersion`, `ContainerRuntimeVersion` |
| MCO / MCD logs | `gather-extra/artifacts/pods/openshift-machine-config-operator/` | which OS/config version a node is on; rollout errors |
| MachineConfig(Pool) | `oc_cmds/machineconfigpool`, `oc_cmds/machineconfig` | rendered config, per-pool update/degraded state |

```bash
# kernel panics / OOM / NetworkManager / SELinux across every node journal
grep -rEi "kernel panic|BUG:|Oops|Call Trace|out of memory|NetworkManager|avc: +denied" \
  gather-extra/artifacts/journal_logs/
```

Journals and serial consoles are the OS layer's primary evidence; operator pod logs sit above it
and show only the downstream symptom.

## Quick Triage Checklist

1. **Variant?** Read `rhcos_version` (snapshot) or `OSImage` (`oc_cmds/nodes`). Failure on only
   one variant → OS-variant-specific; go straight to the RPM diff.
2. **Payload boundary?** Did the failure class start on a specific payload across unrelated jobs
   with no product PR? → compare `rhcos_changes[]` / `nodeImageStreams` RPM diff.
3. **Which subsystem?** Match the symptom in [Failure Patterns](#failure-patterns) to
   cri-o / kernel / NetworkManager / systemd / SELinux / storage.
4. **Read host evidence.** Node journal + `host_service_logs` for runtime/NM/systemd; serial
   console for kernel panic / boot / Ignition; `failed-units.txt` for a fast unit list.
5. **Correlate.** Overlap between the RPM diff and the failing subsystem = RHCOS suspect (not a
   revert). Record variant, package NEVRA delta, and rationale for the platform team.
6. **Drain vs content.** A node that will not drain/reboot is an MCO **rollout** problem
   ([upgrade.md](upgrade.md#mco-drain-failures--the-1-upgrade-problem)); a node that boots the new
   OS and then misbehaves is an OS-**content** problem (this reference).

## See Also

- [upgrade.md](upgrade.md) — MCO drain/reboot cascade, MachineConfigPool status, version skew
- [networking.md](networking.md) — in-cluster OVN/DNS/ingress (vs host NetworkManager here)
- [resource-exhaustion.md](resource-exhaustion.md) — OOM, node pressure, kernel OOM killer
- [disruption.md](disruption.md) — OVS stalls, CPU starvation, interval interpretation
- [install/general.md](install/general.md) · [install/metal.md](install/metal.md) — Ignition, serial console, sosreport at install time
- [artifacts.md](artifacts.md) — full artifact tree (journals, serial, must-gather, log bundle)
- [payload-snapshot](../../payload-snapshot/SKILL.md) · [payload-analysis](../../payload-analysis/SKILL.md) — RHCOS RPM diffs, rpmdb, suspect scoring
