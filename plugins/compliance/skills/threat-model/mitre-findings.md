# MITRE ATT&CK Findings Tracker

Cumulative security findings from PR threat analysis.

## Legend

**Severity**: Critical / High / Medium / Low / Info
**Status**: Open / Mitigated / Accepted / FalsePositive

---

## Findings by Technique

| Date | Repo | PR | Topology | Technique ID | Technique Name | Severity | Status | Notes |
|------|------|----|----------|--------------|----------------|----------|--------|-------|
| 2026-02-12 | cluster-etcd-operator | #1521 | TNF | T1562 | Impair Defenses | Medium | Accepted | CIB `force_new_cluster` attribute manipulation (matches PE-P7-T-2) |
| 2026-02-12 | cluster-etcd-operator | #1521 | TNF | T1485 | Data Destruction | Low | Accepted | `rm -rf` on etcd data dir during restore (intentional, backup exists) |
| 2026-02-12 | cluster-etcd-operator | #1521 | TNF | T1565 | Data Manipulation | Low | Accepted | Config files moved without integrity check (root-only, files regenerated) |

---

## Statistics

| Technique ID | Count | Last Seen |
|--------------|-------|-----------|
| T1562 | 1 | 2026-02-12 |
| T1485 | 1 | 2026-02-12 |
| T1565 | 1 | 2026-02-12 |

---

## Recent Analyses

<!-- New entries are appended below -->

### 2026-02-05 | resource-agents PR #2112

**Title**: podman-etcd: add -a option to crictl ps
**Author**: @fonta-rh
**Topology**: TNF
**Report**: [PR2112-THREAT-MODEL-resource-agents.md](../repos/two-node-toolbox/docs/PR2112-THREAT-MODEL-resource-agents.md)

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |

**Summary**: Clean PR - no security issues. Fixes race condition in etcd pod detection.

---

### 2026-02-12 | cluster-etcd-operator PR #1521

**Title**: OCPBUGS-60588: [TNF] support restore for pacemaker-managed etcd
**Author**: @clobrano
**Topology**: TNF
**Report**: [PR1521-THREAT-MODEL-cluster-etcd-operator.md](../repos/two-node-toolbox/docs/PR1521-THREAT-MODEL-cluster-etcd-operator.md)

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 2 |

**Summary**: Extends etcd restore to TNF clusters. Medium finding: `crm_attribute` sets `force_new_cluster` CIB attribute (matches existing PE-P7-T-2/PE-DS3-T-2 — root-only, `--lifetime reboot`). Low findings: `rm -rf` on etcd data dir (intentional, backup exists) and config files moved without integrity check. No credentials handled, no new privilege escalation vectors. ShellCheck clean on new scripts.

---
