# Compliance Scoring Rubric

This rubric defines how blueprint compliance is scored (0-100). Weights are configurable — update this file when the standards add new mandatory sections.

## Overall Score Composition

| Category | Weight | Description |
|----------|--------|-------------|
| Section Presence | 35% | Are all mandatory sections present? |
| Content Completeness | 30% | Are sections substantive (not just placeholders)? |
| RDS Alignment | 20% | Are deviations documented? Are SUPPORTEX tickets linked? |
| Tables and Data Quality | 15% | Are S-BOM, H-BOM, and other tables complete with specific values? |

## Section Presence Scoring (35 points)

Each mandatory section contributes equally. Missing a section scores 0 for that item.

| Section | Points | Required Elements |
|---------|--------|-------------------|
| Document Metadata | 5 | Title, version history, NDA notice, contacts |
| Introduction and Architectural Overview | 5 | Purpose, workload, architecture diagram, deployment scenarios |
| Software and Configuration | 5 | S-BOM, operators, configuration baseline, support exceptions, deviations |
| Hardware and Node Configuration | 5 | H-BOM, node types, labels/taints, resource partitioning, kernel/BIOS |
| Networking | 5 | Network overview, primary CNI, secondary networks, IP addressing |
| Operations and Management | 5 | LCM, backup/restore, observability, security, user management |
| Certification | 5 | CNF certification, hardware certification |

## Content Completeness Scoring (30 points)

Sections must contain substantive content, not just headers or TODO placeholders. Strategic descriptions and aspirational text score 0 — content must be specific and actionable.

| Criterion | Points | How to Assess |
|-----------|--------|---------------|
| S-BOM has specific versions (not "latest" or "TBD") | 6 | Check each row has concrete version numbers. OCP and RHCOS versions must be stated explicitly, not inferred from operator versions. Score is proportional: (valid_rows / total_rows) × 6 points, rounded to the nearest integer. |
| H-BOM has specific hardware models and specs | 6 | Check server vendor, model, CPU arch/model, memory type/capacity, storage, NIC model, SR-IOV config. Each node type must be documented separately. |
| Architecture diagram is present and renderable | 4 | The diagram must be viewable in the Markdown document itself (inline image or linked file). Pandoc artifact comments or references to external documents score 0. Text descriptions without a renderable diagram score 1 at most. |
| Deployment scenarios are enumerated | 4 | Check for specific scenario types (5G Core, D-RAN, C-RAN, SNO, multi-node). If only one scenario applies, it must be explicitly stated. |
| Operations procedures are actionable | 5 | LCM must include specific upgrade paths (z-stream, EUS-to-EUS), backup must describe what is backed up and how, monitoring must name the stack and alert targets. Strategic text ("we plan to use ACM") without procedures scores 0. |
| Networking has specific configurations | 5 | CNI type must be named (e.g., OVNKubernetes), NADs must have parameters, IP ranges must be documented. PTP details alone are insufficient — core networking config is required. |

## RDS Alignment Scoring (20 points)

| Criterion | Points | How to Assess |
|-----------|--------|---------------|
| RDS baseline is identified | 4 | Must specify exact profile (RAN-DU, Core, or Hub), OCP version, and link to the RDS document. Vague references ("aligned with RDS") score 1 at most. |
| Deviations are itemized | 6 | Each deviation listed separately with explanation. The scorer must also check for undocumented deviations by analyzing the blueprint content (see Undocumented Deviation Detection below). |
| SUPPORTEX tickets are linked | 5 | SUPPORTEX-XXXXX format with active links. Each deviation must have a corresponding ticket. |
| Deviation impact is assessed | 5 | Each deviation explains why it exists, what the impact is on platform stability and support coverage, and what mitigations are in place. |

### Undocumented Deviation Detection

During scoring, the validator must scan the blueprint for deviations that exist but are not documented. Refer to the deviation detection patterns in the `deviation-tracking` skill, which organizes signals by RDS profile (RAN-DU, Core, Hub, Shared). For multi-profile blueprints, evaluate each profile independently — a configuration baseline for one profile may be a deviation for another.

Each detected undocumented deviation must be flagged in the compliance report as a gap requiring documentation and a SUPPORTEX ticket.

## Tables and Data Quality Scoring (15 points)

| Criterion | Points | How to Assess |
|-----------|--------|---------------|
| S-BOM table is well-formed | 4 | Has columns: Component, Version, Patch Level |
| Operators table is complete | 3 | Has columns: Name, Version, Channel, Role |
| Support Exceptions table is present | 4 | Has columns: SUPPORTEX ID, Required For, Status |
| Network Attachment Definitions table exists | 4 | Has columns: NAD Name, Type, Parameters |

## Score Interpretation

| Score Range | Rating | Action |
|-------------|--------|--------|
| 90-100 | Excellent | Ready for review |
| 75-89 | Good | Minor gaps — fix recommended |
| 50-74 | Needs Work | Significant gaps — fix required before review |
| 25-49 | Incomplete | Major sections missing — substantial work needed |
| 0-24 | Draft | Early stage — use `generate` command to build out sections |

## Updating This Rubric

When `telcoeng-blueprint-standards` adds new mandatory sections:

1. Add the section to the Section Presence table
2. Adjust point distribution to maintain 35-point total by reducing points evenly across existing sections (rounding to maintain integer values)
3. Add content completeness criteria if the section requires specific data
4. Bump the plugin version (PATCH for weight adjustments, MINOR for new sections)
