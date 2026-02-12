# TNA DFD Element Reference

> **Topology**: TNA (Two-Node with Arbiter) only. For TNF elements, see dfd-elements-tnf.md.

Quick reference for mapping PR changes to Data Flow Diagram elements defined in
`repos/two-node-toolbox/docs/TNA-THREAT-MODEL.md`.

## Processes

| ID | Name | Code Reference | STRIDE |
|----|------|---------------|--------|
| P1 | Installer (arbiter topology) | `installer/pkg/asset/machines/arbiter.go`, `installer/pkg/types/installconfig.go` | S, T, R, I, D, E |
| P3 | MCO (arbiter config) | `machine-config-operator/manifests/arbiter.machineconfigpool.yaml` | S, T, R, I, D, E |
| P4 | CEO (standard etcd) | `cluster-etcd-operator/pkg/operator/ceohelpers/control_plane_topology.go` | S, T, R, I, D, E |
| P5 | Worker Kubelet (optional, OCP 4.22+) | Worker node kubelet | S, T, R, I, D, E |

## Data Stores

| ID | Name | Location | STRIDE |
|----|------|----------|--------|
| DS5 | etcd Data | etcd pods on 2 masters + arbiter | T, I, D |
| DS6 | Worker Ignition / Credentials | Worker ignition endpoint | T, I, D |

## External Entities

| ID | Name | Protocol | STRIDE |
|----|------|----------|--------|
| EE1 | User / Cluster Admin | oc/kubectl | S, R |

## Trust Boundaries

| ID | Boundary | Elements Inside |
|----|----------|----------------|
| TB1 | Admin Network | EE1 |
| TB2 | Kubernetes API | P1, P3, P4, DS5 |
| TB3 | Worker Compute (optional) | P5, DS6 |

---

## High-Risk Elements

Elements with the most significant threats (from TNA-THREAT-MODEL.md):

| Element | Key Risks | Related Threats |
|---------|-----------|-----------------|
| P3 (MCO) | Arbiter taint removal -> workload scheduling -> quorum loss | T-2, D-1 |
| DS5 (etcd Data) | Node compromise exposes all K8s secrets | I-1, T-1 |
| P5 (Worker Kubelet) | Lateral movement from worker to control plane | E-2 |

---

## TNA Does NOT Have

TNA uses standard Kubernetes etcd (3-member quorum via arbiter) and does **not** include any RHEL-HA / Pacemaker components. The following TNF elements have **no equivalent** in TNA:

- No Pacemaker / Corosync / STONITH / fencing
- No BMC credentials or fencing-credentials secrets
- No podman-etcd OCF agent
- No PCSD authentication
- No privileged TNF setup jobs (P2, P3, P4, P5 from TNF DFD)
- No CIB (Cluster Information Base)
- No fence_redfish
- No Corosync network (UDP 5404-5406)
- No BMC network trust boundary

Any PR analysis mentioning these components is **not applicable** to TNA topology.
