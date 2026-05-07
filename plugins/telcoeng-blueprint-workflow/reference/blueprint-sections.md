# Blueprint Section Reference

This file is a **pointer** to the canonical source of truth: the `telcoeng-blueprint-standards` repository. Do NOT duplicate the standards here — always read the live document at runtime.

## Standards Document Location

The standards document is maintained at:

- **Internal GitLab**: `gitlab.cee.redhat.com/telcoeng/telcoeng-blueprint-standards`
- **Local clone** (if available): Look for `telcoeng-blueprint-standards/README.md` relative to the current workspace or in sibling directories

To locate the standards at runtime, search in this order:

1. `../telcoeng-blueprint-standards/README.md` (sibling directory)
2. `../../telcoeng-blueprint-standards/README.md` (parent sibling)
3. Search workspace for any directory named `telcoeng-blueprint-standards`

## Required Section Hierarchy

The following section hierarchy is extracted from the standards. **Always re-read the live document** to pick up changes — this list is for quick reference only.

### Top-Level Sections (Mandatory)

1. **Blueprint Document Metadata** — Title, Version History, NDA Notice, Contacts/Approvers
2. **Authorship** — Collaborative authorship statement
3. **Introduction and Architectural Overview** — Purpose, Workload, Solution Architecture, Deployment Scenarios, Infrastructure Components, Untested Features
4. **Technical Deep Dive** — Core technical specifications
   - Software and Configuration (S-BOM, Operators, Configuration Baseline, Support Exceptions, RDS Deviations)
   - Hardware and Node Configuration (H-BOM, Node Types, Labels/Taints, Resource Partitioning, Kernel/BIOS)
   - Compute
   - Storage
   - Networking (Network Overview, Primary CNI, Secondary Networks, IP Addressing, Load Balancing)
5. **Operations and Management** — LCM, Backup/Restore, Observability, Security, User Management
6. **Certification** — CNF Certification, Hardware Certification
7. **Appendix** — Terminology, Configuration Examples, Diagrams, References

### Critical Tables (Must Be Present and Complete)

- **S-BOM Table**: Software component | Version | Minimum patch level
- **Operators Table**: Operator name | Version | Channel (stable/eus) | Role
- **Support Exceptions Table**: SUPPORTEX ID | Required for | Status/Comments
- **RDS Deviations List**: Itemized deviations with explanation and tracking
- **H-BOM Table**: Server model | CPU | Memory | Storage | NICs
- **Network Attachment Definitions Table**: NAD name | Type | Parameters

## Persona Requirements

The standards define 7 target personas. Each blueprint section must satisfy:

| Persona | Primary Need |
|---------|-------------|
| Platform/Operations/Workload Pillar Teams | Technical depth, RDS alignment, deviation tracking |
| Verification Pillar Engineers | Precise configs, exact versions (S-BOM), specific hardware (H-BOM), YAML manifests |
| Red Hat Field Teams | Executive architecture + technical depth for pre-sales |
| NPSS Team | Compliance determines SLA eligibility; deviations affect support scope |
| Partner Engineering Teams | Clear structure, RDS alignment guidance, production baselines |
| CSP Architects | High-level architecture and operational considerations |
| System Integrators | Tested baseline vs experimental features; deployment guidance |
