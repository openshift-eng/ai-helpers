---
context: fork
name: rh-ssg-release-notes
description: 'Review Red Hat release notes for SSG compliance — tense rules (present default, past for "before this update"), informative headings (sentence case, no gerunds, under 120 chars), Jira references on known/fixed issues, AsciiDoc formatting (description lists, + attachment), and release note types: new features, enhancements, rebases (X.Y.Z format), Technology Preview entries, deprecated features, removed features, known issues (Cause > Consequence > Workaround > Result), and fixed issues (CCFR pattern). Use this skill whenever reviewing, writing, or checking release notes for any Red Hat product.'
---

# Red Hat SSG: Release Notes review skill

Review release notes for compliance with the Red Hat Supplementary Style Guide.

## Checklist

### General style

- [ ] Focus on impact to the user; omit overly technical details
- [ ] Avoid passive voice, modal verbs, and ambiguous language ("Should XY happen" > "If XY happens")
- [ ] No infinitive statements from changelogs ("Remove deprecated macros" > "Deprecated macros are removed")
- [ ] Unfamiliar terms (utilities, packages, commands) are defined on first mention outside headings
- [ ] Abbreviations are expanded in descriptions (not in headings)
- [ ] Sentences do not start with a lowercase word — repeat the definition if needed
- [ ] Admonitions are minimal; release notes do not begin with admonitions

### Tenses

- [ ] Simple present tense is the default
- [ ] No future tenses, "should," or "might" for post-update state
- [ ] Simple past tense describes the situation before the current update
- [ ] "Now" is not used to refer to the post-update state
- [ ] Fixed issues follow CCFR tense logic (Cause-Consequence-Fix-Result)
- [ ] "Before this update" is used instead of "previously"

### Headings

- [ ] Each release note has an informative heading summarizing the note
- [ ] Headings use sentence-style capitalization (not title case)
- [ ] Headings are under 120 characters
- [ ] Headings do not start with a gerund (release note headings should be descriptive, not task-oriented)
- [ ] Headings mention the component when it might not be obvious
- [ ] Headings are specific, not overly generic ("Program no longer crashes" is too vague)
- [ ] Abbreviations in headings are not expanded (expanded in the text below)

### Jira references

- [ ] All Known issues and Fixed issues include Jira ticket references
- [ ] Jira references are on the line directly after the entry (not in parentheses or brackets)
- [ ] If tickets require login, introductory text states: "Some linked Jira tickets are accessible only with Red Hat credentials."

### AsciiDoc formatting

- [ ] Each release note is a description list item (not nested headings)
- [ ] Additional paragraphs after the first line are attached with `+` on a separate line
- [ ] Lists within a release note are attached with `+`, and a `+` follows the list before the next paragraph
- [ ] Open blocks (`--`) are attached with `+` before and after

### New features and enhancements

- [ ] Describes **what** the feature/enhancement is, **why** it benefits the customer, and the **result**
- [ ] Links to product documentation if available
- [ ] When TP becomes fully supported, this is clearly stated

### Rebases

- [ ] Version uses X.Y.Z format only (not `+1-A.elN`)
- [ ] Includes a parallel list of highlights
- [ ] No blank rebase descriptions — include details if the component is important
- [ ] Zeroth minor versions (e.g., 10.0): "provided in version X.Y.Z" not "rebased to"

### Technology Preview features

- [ ] Heading ends with "(Technology Preview)"
- [ ] Description mentions the feature is a Technology Preview
- [ ] Technology Preview admonition is NOT used in release notes (would be repetitive)
- [ ] TP release notes are repeated in subsequent releases until GA or removal

### Deprecated features

- [ ] Describes the feature, states it is deprecated, and provides the alternative
- [ ] Does not use "Recommended" — per SSG glossary
- [ ] Does not repeat the definition of "deprecated" from the section intro
- [ ] Does not predict future feature statuses: "will be deprecated next release"

### Removed features

- [ ] Feature was documented as deprecated in a preceding release
- [ ] Describes the feature, states it is removed, and provides the alternative
- [ ] Small part removals are treated as feature changes, not removed features

### Known issues

- [ ] Follows: Cause > Consequence > Workaround > Result structure
- [ ] Workaround is in a separate paragraph: "To work around this problem, ..."
- [ ] If no workaround exists: "No known workaround exists."
- [ ] Uses present tense
- [ ] Never promises future fixes

### Fixed issues (bug fixes)

- [ ] Follows CCFR: "Before this update, <cause>. As a consequence, <consequence>. With this release, <fix>. As a result, <result>."
- [ ] Cause and consequence in past tense; fix and result in present tense
- [ ] Uses "before this update" not "previously"

## How to use

1. Review only changed content and necessary context
2. For each issue found, cite the relevant SSG section and release note type
3. Mark issues as **required** (wrong tense, missing Jira reference, missing heading) or **[SUGGESTION]** (style improvements)

## Example invocations

- "Review these release notes for SSG compliance"
- "Check the known issues section in release-notes.adoc"
- "Do an SSG release notes review on the 4.17 release notes"

## References

For detailed guidance, consult:
- [Red Hat Supplementary Style Guide: Release notes](https://redhat-documentation.github.io/supplementary-style-guide/#release-notes)
