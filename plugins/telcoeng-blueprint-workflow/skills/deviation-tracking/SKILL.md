---
name: Deviation Tracking
description: Documents RDS deviations, manages SUPPORTEX ticket references, and creates ECOPS JIRA tickets for blueprint compliance issues
---

# Deviation Tracking

This skill handles the documentation and tracking of deviations from Red Hat Reference Design Specifications (RDS) in partner blueprints. It manages SUPPORTEX ticket references and integrates with JIRA to create ECOPS tickets for unresolved deviations.

## When to Use This Skill

Use this skill when:

- The `validate` command checks RDS deviation documentation completeness
- The `generate` command needs to produce a deviations section
- The `fix` command needs to create JIRA tickets for undocumented deviations
- A user needs to document a new deviation or update an existing one

## Prerequisites

- Understanding of which RDS profile the blueprint aligns with (RAN-DU, Core, or Hub)
- Access to JIRA for SUPPORTEX and ECOPS ticket queries (via the `jira` plugin)
- See `reference/mcp-tools.md` for JIRA integration patterns

## Key Concepts

### RDS Profiles

Red Hat maintains Reference Design Specifications for different deployment types:

- **RAN-DU**: Single Node OpenShift for Distributed Unit workloads
- **Core**: Multi-node OpenShift for 5G Core workloads
- **Hub**: Management cluster running ACM (OCP 4.19+)

A blueprint may cover **multiple profiles** (e.g., Hub + Core when a partner documents both management and workload clusters in a single document). When multiple profiles apply:

- Deviations must be evaluated against **each applicable RDS** independently
- Each deviation must be tagged with its applicable profile (Hub, Core, RAN-DU, or Shared)
- A SUPPORTEX table should include a **Profile** column indicating which cluster type the exception applies to
- Scoring must account for both profiles — a configuration that is baseline for Core (e.g., non-RT kernel) may be a deviation for RAN-DU

Each blueprint must identify which RDS profile(s) it aligns with and document all deviations per profile.

### Deviation Types

Common categories of deviations from RDS:

1. **Workload specification** — Pod count, container count, traffic patterns
2. **Exec probes** — Count and frequency exceeding RDS limits
3. **ConfigMaps** — Usage patterns differing from RDS
4. **Kernel arguments** — Additional kernel args not in RDS
5. **Kernel modules** — Additional modules not validated in RDS
6. **Sysctls** — Custom sysctl configurations
7. **Cluster capabilities** — Enabling capabilities disabled in RDS
8. **etcd encryption** — Enabling encryption not in baseline RDS

### SUPPORTEX Tickets

Formal support exceptions filed in JIRA under the SUPPORTEX project. Required when a deviation needs explicit Red Hat support approval.

Format: `SUPPORTEX-XXXXX`
Link: `https://issues.redhat.com/browse/SUPPORTEX-XXXXX`

### ECOPS Tickets

Operational compliance tickets filed in the ECOPS JIRA project. Used for tracking deviation analysis and resolution.

Format: `ECOPS-XXXX`
Link: `https://issues.redhat.com/browse/ECOPS-XXXX`

## Implementation Steps

### Step 1: Identify RDS Baseline

From the blueprint, determine which RDS profile(s) the solution aligns with:

1. Search for "Reference Design Specification" or "RDS" mentions
2. Extract the OCP version and deployment type
3. Detect profile signals to classify the blueprint:

| Signal | Profile |
|--------|---------|
| DU workload, FlexRAN, Aerial SDK, RT kernel, SNO | RAN-DU |
| 5G Core CNFs, multi-node MNO, CWL/CMWL clusters | Core |
| ACM, GitOps, Quay, cluster management, Hub cluster | Hub |

4. If both Hub and Core/RAN-DU signals are present, classify as **multi-profile** (e.g., Hub + Core)
5. For multi-profile blueprints, identify which sections apply to which profile:
   - Hub-specific: ACM configuration, GitOps, Quay registry, Hub operators, Hub georedundancy
   - Core/RAN-specific: Workload CNFs, performance profiles, SR-IOV, worker node tuning
   - Shared: S-BOM, cluster capabilities, security, monitoring, backup

### Step 2: Extract Existing Deviations

Parse the blueprint's deviations section (if present) and build an inventory:

1. Find the "Deviations from the Reference Design Specifications" section
2. Parse each deviation item (bullet points or numbered list)
3. For each deviation, extract:
   - Description of the deviation
   - Reason/rationale
   - Impact assessment (if provided)
   - SUPPORTEX ticket reference (if linked)
   - ECOPS ticket reference (if linked)

### Step 3: Validate Deviation Documentation

For each deviation, check:

1. **Description is specific**: Not vague — names exact config, component, or parameter
2. **Rationale is provided**: Explains WHY the deviation exists (partner requirement, architecture constraint)
3. **Impact is assessed**: States the expected impact on platform resources or support scope
4. **Ticket is linked**: SUPPORTEX or ECOPS ticket reference exists
5. **Ticket status is current**: If possible, verify ticket status via JIRA (Approved, Pending, etc.)

### Step 4: Identify Undocumented Deviations

Scan the blueprint content itself for signals that indicate deviations exist but are not documented. This does not require kube-compare — it works from the blueprint text alone.

**Content-based detection patterns:**

| Signal in Blueprint | Likely Deviation | RDS Expectation |
|---------------------|-----------------|-----------------|
| `aarch64` or `ARM` CPU architecture | Non-x86 worker nodes | x86_64 |
| `realTimeKernel.enabled: false` on RAN workload | Non-RT kernel | RT kernel for RAN-DU |
| GPU references (NVIDIA, CUDA, Aerial, H100, GH200) | GPU-accelerated workloads | Not in standard RDS |
| Kernel args not in RDS baseline (e.g., `iommu.passthrough`, `module_blacklist`, `preempt=full`) | Custom kernel parameters | RDS-validated set only |
| Custom scheduler groups (e.g., `ice-ptp`, `ice-gnss`) | Non-standard thread scheduling | Not in RDS |
| KVM/VM-based control plane | Virtualized masters | Bare metal |
| BlueField/DPU NIC references | SmartNIC/DPU | Standard SR-IOV NICs |
| Pod counts exceeding RDS limits | Workload exceeds spec | 15 pods / 30 containers (RAN-DU) |
| HugePages sizes not in RDS (e.g., 512M instead of 1G) | Non-standard memory config | 1G HugePages |
| `etcd` encryption enabled | Non-default security config | Not in RDS baseline |
| Cluster capabilities enabled beyond RDS (Build, CSISnapshot) | Additional capabilities | Disabled in RDS |

For each detected signal:
1. Check if a corresponding deviation is documented in the deviations section
2. If not documented, flag as an undocumented deviation in the compliance report
3. Include the signal source (section, line) and the expected RDS behavior

**kube-compare cross-reference** (when available):

If kube-compare-mcp results are available, also cross-reference:

1. Compare kube-compare cluster diff output against documented deviations
2. Flag any deviations found by kube-compare that are NOT documented in the blueprint
3. These are compliance gaps requiring either documentation or remediation

### Step 5: Create JIRA Tickets (Optional)

For undocumented or unresolved deviations, offer to create ECOPS tickets:

1. Use the `jira` plugin's create command
2. Set project to ECOPS
3. Format the ticket:
   - Summary: `[Blueprint] <partner-name> - <deviation-description>`
   - Description: Include the deviation details, which RDS section it deviates from, and recommended action
   - Labels: `blueprint`, `compliance`, `<partner-name>`

Always ask for user confirmation before creating tickets.

## Return Value

- List of documented deviations with completeness status
- List of undocumented deviations (gaps)
- SUPPORTEX ticket references and their status
- ECOPS ticket references and their status
- Recommendations for improving deviation documentation

## Error Handling

- **No deviations section found**: Flag as a major compliance gap (6 points in the rubric)
- **JIRA unavailable**: Document deviations locally, note that tickets need to be created manually
- **Unknown RDS profile**: Ask user to specify which RDS the blueprint targets
- **kube-compare results unavailable**: Skip cross-reference check, note in the report
