# Feature

Type-specific guidance for creating Jira features representing strategic objectives.

## Market Problem

Every feature must clearly state:
- **What** customer/business problem does this solve?
- **Who** is affected?
- **Why** is solving this important now?
- **What happens** if we don't solve it?

## Strategic Value

Explain why this feature matters:
- **Business impact:** Revenue, cost reduction, market differentiation
- **Customer value:** What do customers gain?
- **Competitive advantage:** How does this position us?
- **Strategic alignment:** How does this support product strategy?

## Success Criteria

Define measurable success (not just completion):
- **Adoption:** How many customers will use this?
- **Usage:** How will it be used?
- **Outcomes:** What improves as a result?
- **Business:** Revenue, cost, satisfaction impact

## Interactive Workflow

### 1. Market Problem

**Prompt:** "What customer or market problem does this solve? Who is affected and why does it matter?"

### 2. Proposed Solution

**Prompt:** "How will this feature solve the problem? What capability will be delivered?"

### 3. Strategic Value

**Prompt:** "Why is this strategically important? What business value does it deliver?"

### 4. Success Criteria

**Prompt:** "How will you measure success? What metrics will tell you this achieved its goals?"

Categories: adoption, usage, outcomes, business metrics.

### 5. Scope and Epics

**Prompt:** "What are the major components or epics within this feature?"

Identify 3-8 major work streams.

### 6. Timeline and Milestones

**Prompt:** "What is the timeline? What are key milestones?"

## Size Validation

- **Too small** (single epic, 1-2 months) → suggest creating as Epic instead
- **Right size:** 3-8 epics, spans 1-3 releases (6-12 months), addresses strategic market problem

## Description Template

```markdown
<Brief feature overview>

## Market Problem

<Customer/business problem, who is affected, impact>

## Proposed Solution

<Capability being delivered>

## Strategic Value

### Customer Value
- <Benefit>

### Business Impact
- <Impact>

### Strategic Alignment
<How this supports strategy>

## Success Criteria

### Adoption
- <Metrics>

### Outcomes
- <Metrics>

## Scope

### Epics (Planned)
- Epic 1: <name>
- Epic 2: <name>

### Out of Scope
- <Related work NOT in this feature>

## Timeline

- Total duration: <timeframe>
- Target GA: <date/release>
```

For formatting reference, see [Markdown for Jira](markdown-for-jira.md).

## Anti-Patterns

- Feature is actually an epic (single capability) → create as Epic
- No strategic context ("Build monitoring system") → must explain market problem and business value
- Vague success criteria ("customers like it") → use measurable metrics
- Technical implementation as feature ("Migrate to K8s operator") → features describe customer-facing value
