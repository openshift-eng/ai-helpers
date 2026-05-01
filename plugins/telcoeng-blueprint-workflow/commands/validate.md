---
description: Score a blueprint against telcoeng-blueprint-standards (0-100) with section-by-section compliance report
argument-hint: <blueprint-path> [--partner <name>] [--cluster <kubeconfig>] [--jira]
---

## Name

telcoeng-blueprint-workflow:validate

## Synopsis

```text
/telcoeng-blueprint-workflow:validate <blueprint-path> [--partner <name>] [--cluster <kubeconfig>] [--jira]
```

## Description

The `validate` command is the Blueprint Advisor — it reads a blueprint document and the `telcoeng-blueprint-standards`, then produces a compliance score (0-100) with a detailed section-by-section breakdown.

This implements WOW #2 (Automated Compliance Checking & Validation) from the prioritization matrix. It combines RAG-style analysis (standards + blueprint) with optional cluster-level validation via kube-compare-mcp.

### Key Features

- Scores compliance across 4 weighted categories (presence, completeness, RDS alignment, data quality)
- Reads the standards document dynamically — adapts when standards change
- Optionally validates against a live cluster using kube-compare-mcp
- Creates ECOPS JIRA tickets for non-compliant findings (optional, via `--jira` flag)
- Generates a detailed compliance report with actionable recommendations

## Implementation

### Phase 1: Load Scoring Framework

1. Invoke the `compliance-scoring` skill using the Skill tool to load the weighted rubric from `reference/compliance-rubric.md`
2. Load the four scoring categories and their point allocations

### Phase 2: Load Standards Structure

1. Invoke the `blueprint-structure` skill using the Skill tool
2. Read the current `telcoeng-blueprint-standards/README.md` to extract the required section hierarchy
3. Build the list of mandatory sections, required elements, and table schemas

### Phase 3: Read the Blueprint

1. Read the blueprint document at `<blueprint-path>`
2. If the file is not Markdown, inform the user to run `ingest` first
3. Parse the document structure: headings, sections, tables, bullet lists
4. Determine the partner name from `--partner` flag, document title, or prompt

### Phase 4: Score Section Presence (35 points)

For each mandatory section from the standards:

1. Search for the section heading in the blueprint (fuzzy match)
2. Score: present with content = full points, present but empty = half points, absent = 0
3. Record findings for the report

### Phase 5: Score Content Completeness (30 points)

For each present section, evaluate substantive content per the rubric criteria. Apply these strict rules:

1. Check S-BOM for specific version numbers — OCP and RHCOS versions must be stated explicitly, not inferred from operator versions. Blank version fields score 0 for that row.
2. Check H-BOM for specific hardware models and specs — each node type must be documented separately with vendor, model, CPU, memory, storage, NIC.
3. Check architecture diagram is **renderable** in the Markdown — pandoc artifact comments or references to the source Word/PDF document do not count. Text descriptions without a renderable diagram score 1 at most.
4. Check deployment scenarios are enumerated — if only one scenario applies, it must be explicitly stated.
5. Check operations procedures are **actionable**, not strategic — "we plan to use ACM" without procedures scores 0. LCM must include specific upgrade paths, backup must describe what and how, monitoring must name the stack.
6. Check networking has specific configurations — PTP details alone are insufficient, core networking config (CNI type, NADs, IP ranges) is required.
7. Score each criterion per the rubric.

### Phase 6: Score RDS Alignment (20 points)

1. Invoke the `deviation-tracking` skill using the Skill tool
2. **Detect RDS profile(s)**: Determine whether the blueprint covers a single profile (RAN-DU, Core, or Hub) or multiple profiles (e.g., Hub + Core). Use profile detection signals from the deviation-tracking skill:
   - Hub signals: ACM, GitOps, Quay, Hub cluster, cluster management
   - Core signals: 5G Core CNFs, multi-node MNO, CWL/CMWL workload clusters
   - RAN-DU signals: DU workload, RT kernel, FlexRAN, Aerial SDK, SNO
3. Check for explicit RDS baseline identification — must specify exact profile(s), OCP version, and link to the RDS document. For multi-profile blueprints, each profile must be named with its own RDS link. Vague references score 1 at most.
4. Verify deviations are itemized with individual explanations. For multi-profile blueprints, each deviation must indicate which profile it applies to (Hub, Core, RAN-DU, or Shared).
5. Verify SUPPORTEX tickets are linked (search for `SUPPORTEX-` pattern). For multi-profile blueprints, the SUPPORTEX table should include a Profile column.
6. Verify deviation impact is assessed for each item
7. **Profile-aware scoring**: A configuration that is baseline for one profile may be a deviation for another. For example, `realTimeKernel.enabled: false` is baseline for Core but a deviation for RAN-DU. For multi-profile blueprints, evaluate each profile independently and deduct points only for deviations not documented for the affected profile.

### Phase 7: Detect Undocumented Deviations

Scan the blueprint content for signals that indicate deviations exist but are not documented in the deviations section. Refer to the deviation detection patterns in the `deviation-tracking` skill, organized by RDS profile (RAN-DU, Core, Hub, Shared).

For each detected undocumented deviation, add it to the compliance report as a gap. Undocumented deviations do not directly reduce the total score, but they may indirectly affect the "Deviations itemized" criterion (6 points) if the documented deviations list is incomplete relative to what exists in the blueprint. They are surfaced as actionable findings to guide the `fix` and `generate` commands.

### Phase 8: Score Tables and Data Quality (15 points)

1. Validate S-BOM table structure (Component | Version | Patch Level columns)
2. Validate Operators table (Name | Version | Channel | Role)
3. Validate Support Exceptions table (SUPPORTEX ID | Required For | Status)
4. Validate Network Attachment Definitions table (NAD Name | Type | Parameters)

### Phase 9: Cluster Validation (Optional)

If `--cluster <kubeconfig>` is provided:

1. Invoke the `kube-compare-integration` skill using the Skill tool
2. Run cluster comparison against the appropriate RDS profile
3. Cross-reference cluster deviations with documented blueprint deviations
4. Flag undocumented deviations as additional compliance gaps
5. Include cluster validation results in the report as a supplementary section

### Phase 10: Generate Compliance Report

1. Calculate total score (sum of all categories)
2. Determine rating (Excellent/Good/Needs Work/Incomplete/Draft)
3. Generate the full compliance report with:
   - Overall score and rating
   - Section-by-section breakdown with points and findings
   - RDS alignment details
   - Table quality assessment
   - Cluster validation results (if performed)
   - Prioritized recommendations (ordered by point impact)
4. Save to `.work/blueprints/<partner-name>/compliance-report.md`

### Phase 11: JIRA Integration (Optional)

If `--jira` flag is provided:

1. For each finding rated as "Missing" or "Fail", offer to create an ECOPS ticket
2. Use the `jira` plugin's create command with:
   - Project: ECOPS
   - Summary: `[Blueprint] <partner-name> - <finding-description>`
   - Labels: blueprint, compliance, <partner-name>
3. Always ask for user confirmation before creating tickets
4. Add ticket references to the compliance report

## Return Value

- **Overall score** (0-100)
- **Rating** (Excellent/Good/Needs Work/Incomplete/Draft)
- **Report file path**: `.work/blueprints/<partner-name>/compliance-report.md`
- **Missing sections** count
- **Top 3 recommendations**
- **JIRA tickets created** (if `--jira` was used)

## Examples

1. **Basic validation**:
   ```text
   /telcoeng-blueprint-workflow:validate .work/blueprints/acme-telecom/blueprint.md
   ```
   Output:
   ```text
   Compliance Score: 72/100 — Needs Work

   Section Presence:   28/35 (missing: Certification, Compute)
   Content Completeness: 22/30 (S-BOM has TBD versions)
   RDS Alignment:      12/20 (deviations not linked to SUPPORTEX)
   Data Quality:       10/15 (NAD table missing)

   Top recommendations:
   1. Add Certification section with CNF and hardware certification status
   2. Replace TBD versions in S-BOM with specific version numbers
   3. Link each RDS deviation to a SUPPORTEX ticket

   Report: .work/blueprints/acme-telecom/compliance-report.md
   ```

2. **Validation with cluster check**:
   ```text
   /telcoeng-blueprint-workflow:validate ./blueprint.md --cluster ~/.kube/config --partner samsung
   ```

3. **Validation with JIRA ticket creation**:
   ```text
   /telcoeng-blueprint-workflow:validate ./blueprint.md --partner softbank --jira
   ```

## Arguments

- `$1` (`<blueprint-path>`): Path to the blueprint Markdown file to validate.
- `--partner <name>`: Partner name for report naming and JIRA labels.
- `--cluster <kubeconfig>`: Path to kubeconfig for cluster-level validation via kube-compare-mcp. Optional.
- `--jira`: Enable JIRA ticket creation for non-compliant findings. Optional. Requires user confirmation per ticket.

## Error Handling

- **Blueprint not found**: Display error with path, suggest running `ingest` if the source is Word/PDF
- **Blueprint not in Markdown**: Inform user to run `ingest` command first
- **Standards not found**: Fall back to `reference/blueprint-sections.md`, warn about potentially stale data
- **kube-compare-mcp not available**: Skip cluster validation, note in report, proceed with document-only scoring
- **JIRA not configured**: Skip ticket creation, note in report, provide manual ticket creation guidance
- **Empty blueprint**: Score 0/100 with rating "Draft", recommend using `generate` to scaffold content
- **Skill invocation failure**: If a required skill (`compliance-scoring`, `blueprint-structure`, `deviation-tracking`) fails to load, fall back to built-in defaults (e.g., rubric weights 35/30/20/15) and warn the user that scoring may be incomplete
