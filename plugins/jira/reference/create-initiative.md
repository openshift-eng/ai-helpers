# Initiative

Type-specific guidance for creating Jira initiatives representing internal capability and architectural work.

Initiatives are at the same hierarchy level as Features but are **not customer-facing**. They address architectural gaps, process improvements, and engineering enablement that deliver internal value. Use a Feature instead if customers will directly interact with the capability.

## Problem Statement

Every initiative must clearly state:
- **What internal gap or limitation** does this address?
- **Who** is affected (which teams, roles, workflows)?
- **What is the current impact** of not addressing this?
- **Why** is solving this important now?

## Internal Impact

Explain the value this initiative delivers internally:
- **Team efficiency:** Time savings, reduced manual effort, faster feedback
- **Reliability/stability:** Reduced incidents, faster detection, improved recovery
- **Scalability:** Supports growth without proportional effort increase
- **Developer experience:** Faster onboarding, better tooling, improved workflows

## Success Criteria

Define measurable success with internal metrics:
- **Efficiency:** Time savings, effort reduction, automation coverage
- **Reliability:** Incident reduction, MTTR improvement, regression detection rate
- **Capability:** What can you do now that you couldn't before?
- **Adoption:** How many teams/workflows use the new capability?

## Interactive Workflow

### 1. Problem Statement

**Prompt:** "What internal gap, architectural limitation, or process problem does this initiative address? Who is affected and what is the current impact?"

### 2. Proposed Approach

**Prompt:** "What is the high-level technical or architectural approach to solve this?"

### 3. Internal Impact

**Prompt:** "How will this initiative improve internal capabilities? Think about team efficiency, reliability, scalability, and developer experience."

### 4. Success Criteria

**Prompt:** "How will you measure success? What internal metrics will tell you this initiative achieved its goals?"

Categories: efficiency, reliability, capability, adoption.

### 5. Scope and Epics

**Prompt:** "What are the major components or epics within this initiative?"

Identify 3-8 major work streams.

### 6. Timeline and Milestones

**Prompt:** "What is the timeline? What are key milestones?"

## Size Validation

- **Too small** (single epic, 1-2 months) → suggest creating as Epic instead
- **Right size:** 3-8 epics, spans 1-3 releases (3-9 months), addresses a strategic internal gap
- **Customer-facing work** → redirect to Feature instead

## Description Template

```markdown
<Brief initiative overview>

## Problem Statement

<Internal gap or architectural limitation, who is affected, current impact>

## Proposed Approach

<Technical/architectural approach to solve this>

## Internal Impact

### Team Efficiency
- <Efficiency improvement>

### Reliability
- <Reliability improvement>

### Scalability
<How this enables scaling>

### Developer Experience
<How this improves workflows>

## Success Criteria

### Efficiency
- <Efficiency metrics>

### Reliability
- <Reliability metrics>

### Capability
- <Capability metrics>

### Adoption
- <Adoption metrics>

## Scope

### Epics (Planned)
- Epic 1: <name>
- Epic 2: <name>
- Epic 3: <name>

### Out of Scope
- <Related work NOT in this initiative>

## Timeline

- Total duration: <timeframe>
- Key milestones: <major deliverables>
```

For formatting reference, see [Markdown for Jira](markdown-for-jira.md).

## Anti-Patterns

- Initiative is actually an epic (single capability, 1-2 months) → create as Epic
- Customer-facing work framed as initiative → create as Feature instead
- No internal context ("Improve infrastructure") → must explain what internal gap exists and current impact
- Vague success criteria ("Initiative is successful when infrastructure is better") → use measurable internal metrics
