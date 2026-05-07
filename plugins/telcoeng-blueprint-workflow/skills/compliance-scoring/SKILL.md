---
name: Compliance Scoring
description: Scores a blueprint against telcoeng-blueprint-standards using a weighted rubric (0-100)
---

# Compliance Scoring

This skill implements the compliance scoring engine that evaluates a blueprint document against the `telcoeng-blueprint-standards`. It produces a section-by-section compliance report with a total score from 0 to 100.

## When to Use This Skill

Use this skill when:

- The `validate` command needs to score a blueprint
- The `fix` command needs to identify which sections need improvement
- A user asks about blueprint compliance or readiness for review

## Prerequisites

- The blueprint document must be in Markdown format (use `ingest` command first if in Word/PDF)
- The `blueprint-structure` skill must be invoked first to load the current section hierarchy
- Read `reference/compliance-rubric.md` for the scoring weights and criteria

## Implementation Steps

### Step 1: Load Scoring Rubric

Read `reference/compliance-rubric.md` to load the four scoring categories and their weights:

1. Section Presence (35%)
2. Content Completeness (30%)
3. RDS Alignment (20%)
4. Tables and Data Quality (15%)

### Step 2: Score Section Presence (35 points)

For each mandatory section from the blueprint-structure skill output, check if the section exists in the blueprint:

1. Search for the section heading (## or ### level) in the document
2. Allow minor heading variations (case-insensitive, synonyms like "SW BOM" for "S-BOM")
3. Score: present = full points, absent = 0 points
4. Record which sections are missing for the report

### Step 3: Score Content Completeness (30 points)

For each present section, evaluate whether it contains substantive content:

1. **S-BOM check**: Does the table have rows with specific version numbers? Flag "TBD", "latest", or empty cells
2. **H-BOM check**: Does the table have specific server models, CPU specs, memory amounts?
3. **Architecture diagram**: Is there an image reference or diagram description?
4. **Deployment scenarios**: Are specific scenarios enumerated (5G Core, D-RAN, C-RAN)?
5. **Operations procedures**: Are LCM steps, backup procedures, monitoring setup described?
6. **Networking configs**: Are CNI type, MTU, NAD parameters, IP ranges specified?

Score each criterion per the rubric point values.

### Step 4: Score RDS Alignment (20 points)

Evaluate how well the blueprint documents its relationship to the Reference Design Specifications:

1. **RDS baseline identified** (4 pts): Search for explicit RDS reference (e.g., "Telco 5G RAN 4.x RDS", "Reference Design Specification")
2. **Deviations itemized** (6 pts): Check for a deviations section with individual bullet points or numbered items
3. **SUPPORTEX tickets linked** (5 pts): Search for `SUPPORTEX-` pattern with issue tracker links
4. **Deviation impact assessed** (5 pts): Each deviation should explain its rationale and impact

### Step 5: Score Tables and Data Quality (15 points)

Check the structure and completeness of required tables:

1. **S-BOM table** (4 pts): Has columns for Component, Version, Patch Level
2. **Operators table** (3 pts): Has columns for Name, Version, Channel, Role
3. **Support Exceptions table** (4 pts): Has columns for SUPPORTEX ID, Required For, Status
4. **Network Attachment Definitions** (4 pts): Has columns for NAD Name, Type, Parameters

### Step 6: Calculate Total Score

Sum all category scores. Apply the interpretation scale from the rubric:

- 90-100: Excellent — ready for review
- 75-89: Good — minor gaps
- 50-74: Needs Work — significant gaps
- 25-49: Incomplete — major sections missing
- 0-24: Draft — early stage

### Step 7: Generate Compliance Report

Produce a structured report with:

```text
# Compliance Report: <blueprint-name>

## Overall Score: XX/100 — <Rating>

## Section Presence (XX/35)
| Section | Status | Points |
|---------|--------|--------|
| ... | Present/Missing | X/5 |

## Content Completeness (XX/30)
| Criterion | Status | Points | Findings |
|-----------|--------|--------|----------|
| ... | Pass/Fail/Partial | X/Y | <details> |

## RDS Alignment (XX/20)
| Criterion | Status | Points | Findings |
|-----------|--------|--------|----------|
| ... | Pass/Fail | X/Y | <details> |

## Tables and Data Quality (XX/15)
| Table | Status | Points | Findings |
|-------|--------|--------|----------|
| ... | Well-formed/Missing/Incomplete | X/Y | <details> |

## Recommendations
1. <highest-impact recommendation>
2. <second recommendation>
...
```

Save the report to `.work/blueprints/<partner-name>/compliance-report.md`.

## Return Value

- **Total score** (0-100)
- **Rating** (Excellent/Good/Needs Work/Incomplete/Draft)
- **Category breakdown** (4 category scores)
- **Missing sections** list
- **Top recommendations** (ordered by impact)
- **Report file path**

## Error Handling

- **Blueprint not in Markdown**: Inform user to run `ingest` command first
- **Empty blueprint**: Score 0, recommend using `generate` command to scaffold
- **Ambiguous section headings**: Use fuzzy matching, flag uncertain matches in the report
- **Rubric file not found**: Fall back to hardcoded default weights (35/30/20/15) and warn user
