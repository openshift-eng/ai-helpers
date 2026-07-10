# Epic

Type-specific guidance for creating Jira epics.

## Epic Name Field Requirement

**IMPORTANT:** The Epic Name field (`customfield_10011`) must be set and must match the summary. This is a separate required field — if missing, epic creation fails.

## Parent Link

Epic → Feature uses `{"parent": {"key": "FEATURE-KEY"}}` in `additional_fields`.

## Epic Description Best Practices

Include:
- **Objective:** Overall goal or capability delivered
- **Value:** Who benefits and how
- **Scope:** What's included and explicitly excluded
- **Acceptance criteria:** High-level outcomes (3-6, broader than story AC)
- **Timeframe:** Target quarter/release, estimated sprints

## Interactive Workflow

### 1. Epic Objective

**Prompt:** "What is the main objective? What capability will it deliver?"

### 2. Epic Scope

**Prompt:** "What is included? What is explicitly out of scope?"

### 3. Acceptance Criteria

**Prompt:** "What high-level outcomes define this epic as complete?"

Focus on capabilities, measurable/demonstrable, 3-6 criteria.

### 4. Timeframe

**Prompt:** "Target timeframe? (quarter, release, estimated sprints)"

### 5. Parent Feature (Optional)

**Prompt:** "Is this epic part of a larger feature? If yes, provide the feature key."

Validate parent exists and is a Feature (not another Epic).

## Size Validation

- **Too small** (completable in 1 sprint) → suggest creating as Story instead
- **Too large** (>1 quarter, 50+ stories) → suggest creating as Feature with child Epics
- **Right size:** 2-8 sprints, contains multiple stories, delivers a cohesive capability

## Description Template

```markdown
<Epic objective - what capability will be delivered and why>

## Epic Acceptance Criteria

- <High-level outcome 1>
- <High-level outcome 2>
- <High-level outcome 3>

## Scope

### In Scope
- <Functionality included>

### Out of Scope
- <Related work NOT in this epic>

## Timeline

- Target: <quarter or release>
- Estimated: <sprints>

## Target Users

- <User group>

## Parent Feature (if applicable)

This epic is part of [PROJ-YYY] and addresses <contribution>.
```

For formatting reference, see [Markdown for Jira](markdown-for-jira.md).

## Anti-Patterns

- Epic is actually a story (too small) → create as Story
- Epic is actually a feature (too large, 12+ months) → create as Feature
- Vague AC ("done when everything works") → be specific with measurable outcomes
- No scope definition → always define what's included and excluded
