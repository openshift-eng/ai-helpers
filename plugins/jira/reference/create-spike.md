# Spike

Type-specific guidance for creating Jira spikes for research and investigation work.

Spikes are time-boxed investigations used to resolve uncertainty before committing to implementation. They answer a specific research question so the team can make an informed decision about next steps.

**Key properties:**
- Always time-boxed (1-2 days typical; never open-ended)
- Not story-pointed — effort is bounded by the time box
- Must produce a documented finding and at least one follow-up action (backlog item or decision record)
- If you already know what to build, use a Story or Task instead

## Research Question

Every spike must clearly state:
- **What specific uncertainty or question** does this spike address?
- **What decision does the answer inform?** (which implementation approach, whether to proceed, which tool to adopt)
- **What will you do with the findings?** (design doc, ADR, follow-up stories)

## Interactive Workflow

### 1. Research Question
**Prompt:** "What specific question or uncertainty does this spike address? What decision will the findings inform?"

The question should be answerable within the time box. If it isn't, split the spike or narrow the scope.

### 2. Context
**Prompt:** "Why is this investigation needed now? What is blocked or uncertain without it?"

### 3. Investigation Approach
**Prompt:** "How will you investigate? What methods, sources, or experiments will you use?"

Examples: proof-of-concept implementation, benchmark comparison, API exploration, reading upstream docs, vendor evaluation.

### 4. Time Box
**Prompt:** "How much time should be allocated? (Typical: 1-2 days maximum)"

If the user says more than 2 days, prompt them to narrow the research question or split into multiple spikes.

### 5. Success Criteria
**Prompt:** "What findings or decisions will mark this spike as complete?"

Success criteria for spikes are outcome-oriented, not implementation-oriented:
- "Decision documented: use approach A vs B, with rationale"
- "Proof-of-concept confirms feasibility; follow-up stories created"
- "Benchmark results show X metric meets SLO threshold"

### 6. Follow-up Actions
**Prompt:** "What backlog items will you create based on the findings?"

A spike with no planned follow-up actions is incomplete. At minimum, commit to creating one of: implementation story, decision record, or a second spike to narrow the scope.

## Description Template

```markdown
## Research Question

<What specific question or uncertainty does this spike address? What decision does it inform?>

## Context

<Why is this investigation needed? What is blocked or uncertain without it?>

## Investigation Approach

<Methods, sources, or experiments — e.g., proof-of-concept, benchmark, API exploration, vendor evaluation>

## Time Box

<Maximum time allocated — typically 1-2 days>

## Success Criteria

<What findings or decisions mark this spike as complete?>

## Findings Documentation

<Where findings will be recorded — e.g., PR comment, design doc, ADR, Confluence page>

## Follow-up Actions

- [ ] <Backlog item or decision record to create upon completion>
```

For formatting reference, see [Markdown for Jira](markdown-for-jira.md).

## Size Validation

- **Too broad** (research question can't be answered in 1-2 days) → narrow the question or split
- **Already decided** (you know what to implement) → use Story or Task instead
- **No follow-up planned** → prompt for at least one follow-up action before creating

## Anti-Patterns

- No clear research question ("Investigate GCP networking") → must state what specific decision or uncertainty the spike resolves
- No time box or open-ended time box → always set a maximum; prompt the user if missing
- Implementation work framed as spike ("Spike: implement monitoring") → if you already know what to build, use a Story or Task
- Spike with no follow-up actions → findings must result in backlog items or a documented decision
