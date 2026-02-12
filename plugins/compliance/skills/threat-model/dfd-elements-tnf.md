# TNF DFD Element Reference

> **Topology**: TNF (Two-Node with Fencing) only. For TNA elements, see dfd-elements-tna.md.

Quick reference for mapping PR changes to Data Flow Diagram elements defined in
`repos/two-node-toolbox/docs/TNF-THREAT-MODEL.md`.

## Processes

| ID | Name | Code Reference | STRIDE |
|----|------|---------------|--------|
| P1 | Installer / Assisted Service | `assisted-service/internal/installcfg/builder/builder.go` | S, T, R, I, D, E |
| P2 | CEO TNF Controller | `cluster-etcd-operator/pkg/tnf/operator/starter.go` | S, T, R, I, D, E |
| P3 | TNF Auth Job | `cluster-etcd-operator/pkg/tnf/auth/runner.go` | S, T, R, I, D, E |
| P4 | TNF Setup Job | `cluster-etcd-operator/pkg/tnf/setup/runner.go` | S, T, R, I, D, E |
| P5 | TNF Fencing Job | `cluster-etcd-operator/pkg/tnf/fencing/runner.go` | S, T, R, I, D, E |
| P6 | Pacemaker fenced | `pacemaker/daemons/fenced/` | S, T, R, I, D, E |
| P7 | podman-etcd OCF Agent | `resource-agents/heartbeat/podman-etcd` | S, T, R, I, D, E |
| P8 | fence_redfish | `/usr/sbin/fence_redfish` (RPM) | S, T, R, I, D, E |

## Data Stores

| ID | Name | Location | STRIDE |
|----|------|----------|--------|
| DS1 | install-config.yaml | Installer host filesystem | T, I, D |
| DS2 | K8s Secrets | `openshift-etcd` namespace | T, I, D |
| DS3 | Pacemaker CIB | `/var/lib/pacemaker/cib/cib.xml` | T, I, D |
| DS4 | PCSD Token | `/var/lib/pcsd/token` | T, I, D |
| DS5 | etcd Data | etcd containers / persistent storage | T, I, D |

## Data Flows

| ID | From | To | Data | STRIDE |
|----|------|----|------|--------|
| DF1 | EE1 | P1 | BMC credentials | T, I, D |
| DF2 | P1 | DS1 | Credentials in install-config | T, I, D |
| DF3 | P1 | DS2 | Credentials as K8s Secrets | T, I, D |
| DF4 | DS2 | P5 | Secret read by fencing job | T, I, D |
| DF5 | P3 | DS4 | ClusterID as PCSD token | T, I, D |
| DF6 | P4 | DS3 | Cluster + etcd config to CIB | T, I, D |
| DF7 | P4/P5 | DS3 | STONITH credentials to CIB | T, I, D |
| DF8 | DS3 | P6 | Credentials read for fencing | T, I, D |
| DF9 | P6 | P8 | Credentials as CLI args | T, I, D |
| DF10 | P8 | EE2 | HTTPS Basic Auth to BMC | T, I, D |
| DF11 | P7 | DS5 | etcd container lifecycle | T, I, D |
| DF12 | EE3 | P4/P6 | Membership + CIB replication | T, I, D |

## External Entities

| ID | Name | Protocol | STRIDE |
|----|------|----------|--------|
| EE1 | User / Cluster Admin | REST API / YAML | S, R |
| EE2 | BMC Controllers | Redfish HTTPS | S, R |
| EE3 | Corosync Network | UDP 5404-5406 | S, R |

## Trust Boundaries

| ID | Boundary | Elements Inside |
|----|----------|----------------|
| TB1 | External Network | EE1, EE2 |
| TB2 | Kubernetes API | P1, P2, DS2 |
| TB3 | Privileged Container (nsenter) | P3, P4, P5 |
| TB4 | Host / Pacemaker | P6, P7, P8, DS3, DS4, DS5 |
| TB5 | BMC Network | EE2 |
| TB6 | Inter-Node (Corosync) | EE3 |

---

## High-Risk Elements

Elements with the most existing per-element threats (from TNF-THREAT-MODEL.md):

| Element | Threat Count | Key Risks | Related VULNs |
|---------|-------------|-----------|---------------|
| P5 (Fencing Job) | 4 | Credential exposure, shell injection, privilege | VULN-1, VULN-3 |
| P4 (Setup Job) | 4 | CIB tampering, credential storage, privilege | VULN-3, VULN-4 |
| P8 (fence_redfish) | 4 | MITM, credential exposure, BMC spoofing | VULN-1, VULN-2 |
| DS3 (CIB) | 3 | Plaintext credentials, fencing disable, corruption | VULN-4 |
| P6 (fenced) | 4 | Spoofed requests, credential relay, malicious fencing | VULN-1 |
| P3 (Auth Job) | 3 | Predictable token, privilege escalation | VULN-3, VULN-5 |
| DF9 (P6→P8) | 2 | Credentials in /proc/cmdline | VULN-1 |
| DF10 (P8→EE2) | 3 | MITM, credential interception | VULN-2 |

---

## Credential Flow Path

The full path credentials take through the system (highest-risk data flow):

```text
EE1 (Admin) --DF1--> P1 (Installer) --DF2--> DS1 (install-config) [plaintext on disk]
                                      --DF3--> DS2 (K8s Secret)    [base64 in etcd]
                                                    |
                                                   DF4
                                                    |
                                                    v
                                               P5 (Fencing Job)
                                                    |
                                                   DF7
                                                    |
                                                    v
                                               DS3 (CIB)          [plaintext XML]
                                                    |
                                                   DF8
                                                    |
                                                    v
                                               P6 (fenced)
                                                    |
                                                   DF9
                                                    |
                                                    v
                                               P8 (fence_redfish)  [CLI args visible]
                                                    |
                                                  DF10
                                                    |
                                                    v
                                               EE2 (BMC)           [HTTPS Basic Auth]
```

Any PR touching code along this path requires careful credential handling review.
