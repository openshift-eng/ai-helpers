---
context: fork
name: ibm-sg-audience-and-medium
description: Review documentation for IBM Style Guide audience and medium issues — accessibility (alt text, color, headings), global audience readiness (idioms, date formats, cultural references), tone (active voice, no "please" or "simply"), AI assistant style, marketing claims, and mobile/video content. Use this skill when reviewing docs for accessibility, internationalization, tone problems, or audience appropriateness. For Red Hat docs, prefer the rh-ssg-accessibility skill for accessibility-specific checks.
---

# IBM Style Guide: Audience and Medium review skill

Review documentation for audience and medium issues: accessibility, global audiences, tone, AI assistant style, mobile, marketing, and video content.

**Precedence**: For Red Hat documentation, the Red Hat Supplementary Style Guide (SSG) takes precedence over IBM Style Guide rules. Where guidance conflicts, follow the RH SSG skill for that topic (e.g., `rh-ssg-accessibility` for accessibility).

## Checklist

### Accessibility

- [ ] Every image has alt text that describes function, not appearance
- [ ] Color is not the sole means of conveying meaning
- [ ] Link text is descriptive (no "click here" or "see below")
- [ ] Headings use semantic levels in order (H1 > H2 > H3); no skipped levels
- [ ] Directional language is avoided ("the panel on the right"); use labels or names
- [ ] Text equivalents are provided for video and audio content
- [ ] Tables are used for data only, not for layout; header rows and captions are present

### Global audiences

- [ ] Idioms, slang, colloquialisms, and culture-specific references are avoided
- [ ] Sentence structures are simple: subject-verb-object
- [ ] Humor, puns, and wordplay are avoided
- [ ] Latin abbreviations (e.g., i.e., etc.) are written out ("for example," "that is," "and so on")
- [ ] Phrasal verbs are replaced with single-word alternatives ("remove" not "take out")
- [ ] Date formats are unambiguous (1 January 2025, not 1/1/25)
- [ ] Country-specific examples include context for international readers
- [ ] "Domestic," "foreign," "overseas" are replaced with specific country or region names

### Tone

- [ ] Active voice and present tense are used as defaults
- [ ] The reader is addressed as "you"
- [ ] "Please" is not used in instructions
- [ ] "Simply," "just," "easy," "straightforward" are not used
- [ ] Content states what to do, not what not to do
- [ ] Hedging is avoided ("You might want to consider possibly...")

### AI assistant and conversational style

- [ ] "I" is used for the assistant and "you" for the user
- [ ] Responses lead with the answer, then explain
- [ ] Filler phrases are avoided ("I think," "It seems like," "I'm happy to help")
- [ ] The AI is not anthropomorphized (no feelings, opinions, or consciousness claims)
- [ ] Errors are acknowledged plainly, not with casual language ("Oops!")

### Marketing content

- [ ] Superlatives are avoided ("best," "fastest") unless backed by evidence
- [ ] No unsubstantiated claims or guarantees
- [ ] Competitive comparisons do not disparage competitors
- [ ] Concrete benefits are used over vague buzzwords

### Mobile

- [ ] Content is concise for small screens
- [ ] Important information is front-loaded in headings and paragraphs
- [ ] "Tap" is used instead of "click" for mobile interfaces

### Videos

- [ ] Scripts use a conversational, spoken style with short sentences
- [ ] Closed captions and transcripts are provided
- [ ] Visuals are introduced before being shown

## How to use

1. Review only changed content and necessary context
2. For each issue found, cite the relevant IBM Style Guide section
3. Mark issues as **required** (accessibility violations, misleading tone) or **[SUGGESTION]** (style improvements)

## Example invocations

- "Review this file for audience and accessibility issues"
- "Check this tutorial for global audience readiness"
- "Do an IBM audience and medium review on modules/getting-started.adoc"

## References

For detailed guidance, consult:
- IBM Style Guide: Audience and medium sections
- WCAG 2.1 Guidelines
