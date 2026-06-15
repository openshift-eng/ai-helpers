---
context: fork
name: ibm-sg-structure-and-format
description: Review documentation for IBM Style Guide structure and format — headings (sentence case, no gerunds), lists (parallel structure, lead-in sentences), procedures (imperative verbs, one action per step, max 9 steps), tables (headers, alignment, captions), notes/warnings/tips, bold/monospace/italic formatting, and figures with alt text. Use this skill when checking doc structure, heading style, list formatting, procedure steps, table layout, or emphasis conventions. For Red Hat docs, the rh-ssg-structure and rh-ssg-formatting skills take precedence.
---

# IBM Style Guide: Structure and Format review skill

Review documentation for structure and format issues: headings, lists, procedures, paragraphs, tables, notes, emphasis, figures, and examples.

**Precedence**: For Red Hat documentation, the Red Hat Supplementary Style Guide (SSG) takes precedence over IBM Style Guide rules. Where guidance conflicts, follow the RH SSG skill for that topic (e.g., `rh-ssg-formatting`, `rh-ssg-structure`).

## Checklist

### Headings

- [ ] Sentence case is used: "Configure the database connection" (not Title Case)
- [ ] Heading levels are not skipped: H1 > H2 > H3
- [ ] Headings are concise (under 8 words ideally)
- [ ] Headings are descriptive and specific: "Install the CLI on Linux" not "Installation"
- [ ] Task headings start with a verb: "Create," "Configure," "Deploy"
- [ ] Gerunds (-ing) are not used in task headings: "Create a cluster" not "Creating a cluster"
- [ ] Headings do not end with periods or colons
- [ ] Code formatting in headings is avoided unless necessary

### Lists

- [ ] Ordered lists are used for sequential steps; unordered lists for non-sequential items
- [ ] Parallel structure is used: all items start the same way (all verbs, all nouns)
- [ ] First word of each list item is capitalized
- [ ] Punctuation is consistent: all periods or no periods within a list
- [ ] Lists have more than one item
- [ ] Nesting does not exceed two levels
- [ ] Lists are introduced with a complete lead-in sentence ending in a colon
- [ ] "Following" is not used without a noun: "the following items:" not "the following:"

### Procedures

- [ ] Numbered lists are used for sequential steps
- [ ] Each step starts with an imperative verb: "Click," "Enter," "Select"
- [ ] One action per step; multiple actions are not combined
- [ ] Expected results or output are stated after the action when helpful
- [ ] Procedures do not exceed 9 steps; longer procedures are broken into sub-tasks
- [ ] Prerequisites are listed before the procedure, not within it
- [ ] Optional steps begin with "Optional:"

### Paragraphs

- [ ] Main point leads the paragraph
- [ ] Paragraphs are short: 3-5 sentences maximum
- [ ] One idea per paragraph

### Tables

- [ ] Tables are used for data, not layout
- [ ] Header rows with clear column labels are present
- [ ] Text is left-aligned; numbers are right-aligned
- [ ] Cell content is brief
- [ ] Every table has a caption or introductory sentence
- [ ] Empty cells use "N/A," "None," or a dash
- [ ] Rows are sorted logically

### Notes, tips, and warnings

- [ ] "Note:" is used for supplementary, non-critical information
- [ ] "Important:" is used for must-not-miss information
- [ ] "Warning:" is used for data loss or system damage risks
- [ ] Admonitions are not overused
- [ ] Warnings are placed before the action, not after

### Highlighting and emphasis

- [ ] **Bold** is used for UI elements: **Save**, **File > New**
- [ ] `Monospace` is used for code, commands, file names, and paths
- [ ] *Italic* is used for introducing new terms on first use only
- [ ] Underline is not used for emphasis
- [ ] ALL CAPS is not used for emphasis
- [ ] Multiple emphasis styles are not combined (bold italic, bold underline)

### Figures and images

- [ ] Every image has a figure number and descriptive caption
- [ ] Figures are referenced in text before they appear
- [ ] Alt text is provided for every image
- [ ] Images are not the sole means of conveying critical information

### Examples

- [ ] Examples use realistic values, not "foo," "bar," or "Lorem ipsum"
- [ ] Example domains use RFC 2606: example.com, example.org
- [ ] Example IPs use RFC 5737: 192.0.2.x, 198.51.100.x, 203.0.113.x
- [ ] Examples use clearly fake names and data, never real personal information

## How to use

1. Review only changed content and necessary context
2. For each issue found, cite the relevant IBM Style Guide section
3. Mark issues as **required** (broken structure, missing headings) or **[SUGGESTION]** (formatting improvements)

## Example invocations

- "Review this file for structure and format issues"
- "Check headings and lists in this procedure module"
- "Do an IBM structure review on the assembly"

## References

For detailed guidance, consult:
- IBM Style Guide: Structure and format sections
