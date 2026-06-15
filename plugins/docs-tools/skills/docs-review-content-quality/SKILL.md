---
context: fork
name: docs-review-content-quality
description: Review documentation for content quality — logical flow, user journey alignment, scannability, conciseness, fluff removal, and customer focus. Use this skill whenever someone asks to check if docs are well-organized, too wordy, have unnecessary content, lack logical flow, or need tightening. Also use for content quality peer reviews, minimalism checks, or when asked to "cut the fluff" or "make it more concise."
---

# Content quality review skill

Review documentation for content quality: logical flow, user journey alignment, scannability, conciseness, and customer focus.

This skill covers review dimensions that are unique to content quality assessment. It does not duplicate language, grammar, style, formatting, or accessibility checks, which are covered by the IBM Style Guide and Red Hat Supplementary Style Guide skills.

## Checklist

### Logical flow of information

- [ ] Information is presented in logical order
- [ ] Prerequisites come before procedures
- [ ] Context is provided before details
- [ ] Cross-references are used appropriately
- [ ] Procedures, code examples, and lists are introduced with a lead-in sentence that explains their purpose

### User journey alignment

- [ ] The user goal is clear
- [ ] Tasks reflect the intended goal of the user
- [ ] Troubleshooting steps are included where appropriate
- [ ] Error recognition and recovery is addressed

### Content organization

- [ ] Related information is grouped together
- [ ] Assembly structure reflects user workflow
- [ ] Table of contents makes sense for the user journey
- [ ] Information is provided at the right pace

### Customer focus and action orientation

- [ ] Content focuses on actions and customer tasks
- [ ] Features are explained in terms of what users can do with them
- [ ] Content answers "how do I...?" not "what is...?"

### Scannability and findability

- [ ] Content is easy to scan
- [ ] Information is easy to find
- [ ] Bulleted lists break up dense paragraphs
- [ ] Tables present comparative or reference information
- [ ] Headings describe the content that follows

### Conciseness (no fluff)

- [ ] Text does not include unnecessary information
- [ ] Obvious statements are removed ("As you know...", "It is important to note that...")
- [ ] Self-referential text is removed ("This section describes...", "This topic explains...", "This guide shows...")
- [ ] Redundant phrases are eliminated:
  - "in order to" -> "to"
  - "at this point in time" -> "now"
  - "due to the fact that" -> "because"
- [ ] Each sentence adds value
- [ ] Screenshots are used only when text cannot suffice
- [ ] Diagrams add value that text alone cannot provide
- [ ] Content is clear, precise, and unambiguous

## Key principles

**Good content quality means:**
- Writing only what users need to know
- Organizing information in a task-oriented way
- Focusing on tasks, not features
- Getting users to their goal quickly
- Providing information when users need it
- Removing redundant or obvious information

**Ask yourself:**
- Does this sentence help the user complete their task?
- Can this be said in fewer words?
- Would removing this change the user's understanding?
- Is this information in the right place in the user's journey?

## How to use

1. Review only changed content and necessary context
2. Check that information flows logically
3. Look for content that can be shortened or removed
4. Verify the user journey makes sense
5. Mark issues as **required** (unclear/missing content) or **[SUGGESTION]** (could be shorter or better organized)

## Example invocations

- "Review this file for content quality"
- "Check the logical flow and conciseness of this procedure"
- "Do a content quality review on the assembly"
- "Look for fluff and flow issues in this module"

## References

For detailed guidance, consult:
- Red Hat Modular Documentation Guide: https://redhat-documentation.github.io/modular-docs/
- Red Hat Minimalism Guidelines
- IBM Style Guide
