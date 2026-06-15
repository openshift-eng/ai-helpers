---
context: fork
name: rh-ssg-accessibility
description: Review Red Hat documentation for accessibility compliance (WCAG) — alt text for images/icons, color not as sole information carrier, no directional language ("left"/"right"/"above"), descriptive link text (no "click here"), table structure (no irregular headers, no blank header cells), and correct heading nesting. Use this skill whenever checking Red Hat docs for accessibility, screen reader compatibility, alt text, link text, or WCAG compliance. This skill takes precedence over ibm-sg-audience-and-medium for accessibility checks on Red Hat content.
---

# Red Hat SSG: Accessibility review skill

Review documentation for accessibility compliance with the Red Hat Supplementary Style Guide and WCAG guidelines.

## Checklist

### Colors and visual information

- [ ] Color is not the only means of conveying information
- [ ] Instructions do not rely solely on sensory characteristics (shape, size, visual location, orientation)
- [ ] No directional indicators for navigation: "left," "right," "above," "below" have no meaning to screen readers
- [ ] Information conveyed by color differences is also provided in text form
- [ ] Images and diagrams have sufficient contrast between foreground and background

### Images

- [ ] All icons, images, diagrams, and non-text elements have meaningful alt text
- [ ] Icon alt text describes function, not appearance: alt text for `+` icon is "Add" not "Plus Sign"
- [ ] No images of text — use actual text to convey information
- [ ] Screen captures of informational tables are replaced with actual tables

### Links and hypertext

- [ ] Link purpose is clear from the link text alone (or link text with context)
- [ ] No generic link text: "click here," "here," "this page"
- [ ] Links within a document show the section title
- [ ] External links provide the site name or target page title
- [ ] All links point to correct and valid destinations

### Tables

- [ ] Tables have a simple, logical reading order: left to right, top to bottom
- [ ] No tables with irregular headers (multi-level headers, spanned rows/cells)
- [ ] No blank header cells — add text to each header cell
- [ ] All tables have descriptive titles/captions

### Well-formed HTML and meaningful sequence

- [ ] Headings are correctly nested: H1 > H2 > H3 (no skipped levels)
- [ ] Content is presented in a meaningful order
- [ ] Correct AsciiDoc tags produce the intended HTML output

## How to use

1. Review only changed content and necessary context
2. For each issue found, cite the relevant SSG or WCAG section
3. Mark issues as **required** (missing alt text, images of text, blank header cells, skipped heading levels) or **[SUGGESTION]** (improvements)

## Example invocations

- "Review this file for accessibility issues"
- "Check images and tables for accessibility in assembly_overview.adoc"
- "Do an SSG accessibility review on the changed modules"

## References

For detailed guidance, consult:
- [Red Hat Supplementary Style Guide: Accessibility](https://redhat-documentation.github.io/supplementary-style-guide/#accessibility)
- [Getting started with accessibility for writers](https://redhat-documentation.github.io/accessibility-guide/)
- [WCAG 2.1 Guidelines](https://www.w3.org/TR/WCAG21/)
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
