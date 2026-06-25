# Story

Type-specific guidance for creating Jira user stories.

## Summary vs Description: Critical Distinction

**Summary** (issue title): SHORT, concise (5-10 words). Action-oriented. Does NOT contain "As a... I want... So that...".

- Good: "Enable ImageTagMirrorSet configuration in HostedCluster CRs"
- Bad: "As a cluster admin, I want to configure ImageTagMirrorSet..." (belongs in description)

**Description** (issue body): Contains the FULL user story format, acceptance criteria, and additional context.

When collecting story information:
1. Collect the full user story (As a... I want... So that...)
2. Extract a concise summary title from that story
3. Summary → `summary` parameter, full story → `description`

## User Story Template

```plaintext
As a <User/Who>, I want to <Action/What>, so that <Purpose/Why>.
```

- **Who:** The person, device, or system that benefits (e.g., "cluster admin", "developer", "SRE")
- **What:** What they can do with the system
- **Why:** The value they gain

### The 3 Cs

1. **Card** — The story itself
2. **Conversation** — Discussion about implementation
3. **Confirmation** — Acceptance criteria defining "done"

## Acceptance Criteria Formats

### Test-Based
```plaintext
- Test that <criteria>
```

### Verification-Based
```plaintext
- Verify that when <a role> does <some action> they get <this result>
```

### Given-When-Then (BDD)
```plaintext
- Given <a context> when <this event occurs> then <this happens>
```

### How Much AC is Enough?

Enough when: you can size the story, testing approach is clear, story is independently testable. If >7-8 AC, consider splitting.

## Interactive Workflow

### 1. Collect User Story

Ask three questions:
1. **Who benefits?** (role or user type)
2. **What action?** (what they want to do)
3. **What value?** (why, what benefit)

Construct: "As a {1}, I want to {2}, so that {3}."

Present to user for confirmation.

### 2. Collect Acceptance Criteria

Offer format templates or free-form. Validate:
- At least 2-3 criteria
- Specific and testable
- Cover happy path and edge cases
- User-observable (not implementation details)

### 3. Collect Additional Context (Optional)

Background, dependencies, constraints, out of scope, references.

## Story Sizing and Splitting

A well-sized story completes in one sprint, can be demonstrated, delivers incremental value.

**Split when:** >1 sprint, too many AC, multiple distinct features, hard dependencies.

**Split by:** workflow steps, acceptance criteria groups, platform/component.

## Description Template

```markdown
As a <user>, I want to <action>, so that <value>.

## Acceptance Criteria

- Test that <criteria 1>
- Verify that <criteria 2>

## Additional Context

<optional context, dependencies, out of scope>
```

For formatting reference, see [Markdown for Jira](markdown-for-jira.md).

## Anti-Patterns

- Technical tasks as stories → use Task instead
- Multiple stories in one → split into separate stories
- Vague AC ("works correctly") → be specific with measurable criteria
- Implementation details in AC → focus on user-observable behavior
