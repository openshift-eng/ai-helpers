---
context: fork
name: rh-ssg-formatting
description: Review Red Hat documentation for SSG formatting compliance — code blocks (one command per step, bold via subs="+quotes", separate input/output), user-replaced values (angle brackets, italics, underscores), sentence-style capitalization in titles, product name/version attributes (not hard-coded), date formats ("3 October 2019"), single-step procedures (bullet not number), non-breaking spaces in "Red Hat", and man page references. Use this skill when checking Red Hat docs for code block formatting, placeholder values, title capitalization, product name attributes, or date formats.
---

# Red Hat SSG: Formatting review skill

Review documentation for formatting compliance with the Red Hat Supplementary Style Guide.

## Checklist

### Commands in code blocks

- [ ] Each code block contains only one command per procedure step
- [ ] Command input and example output are in separate code blocks
- [ ] Commands in code blocks use bold formatting (via `subs="+quotes"`)
- [ ] Bold formatting is applied consistently, even when no output is shown
- [ ] Callouts are not used — use definition lists or bulleted lists after the code block instead

### Explanation of commands and variables

- [ ] Single command/variable explanations use a simple sentence after the code block
- [ ] Multiple variables are explained with a definition list introduced by "where:"
- [ ] Each variable description begins with "Specifies"
- [ ] Parameters are listed in the order they appear in the code block
- [ ] YAML structure explanations use a bulleted list

### User-replaced values

- [ ] User-replaced values use angle brackets: `<value_name>`
- [ ] Multi-word values use underscores: `<cluster_name>`
- [ ] Values are lowercase (unless surrounding text is uppercase)
- [ ] Values are italicized in running text
- [ ] In code blocks, `subs="+quotes"` is used to enable italics
- [ ] For XML code blocks, format is `${value_name}` (not angle brackets)

### Titles and headings

- [ ] All titles and headings use sentence-style capitalization (not headline-style)
- [ ] Guide titles, Knowledgebase article titles all follow this rule

### Product names and version references

- [ ] Product names use AsciiDoc attributes, not hard-coded names
- [ ] Product versions use attributes, not hard-coded version numbers
- [ ] Hard-coded versions are used only for versions that never change (e.g., "introduced in RHEL 8.4")
- [ ] Attribute file is included in `master.adoc`

### Date formats

- [ ] Dates use "day Month year" format: "3 October 2019" (preferred)
- [ ] "Month day, year" format ("October 3, 2019") is acceptable if the preferred format causes clarity issues

### Single-step procedures

- [ ] Procedures with only one step use an unnumbered bullet, not a numbered list

### Non-breaking spaces

- [ ] Non-breaking space (`&nbsp;`) is used between "Red" and "Hat" to prevent line breaks splitting the company name

### Man page references

- [ ] Man pages referenced as: `_command_(section)` man page on your system
- [ ] No external links to man page websites

## How to use

1. Review only changed content and necessary context
2. For each issue found, cite the relevant SSG section
3. Mark issues as **required** (incorrect user-replaced values, missing bold in code blocks) or **[SUGGESTION]** (improvements)

## Example invocations

- "Review formatting in this procedure module"
- "Check code blocks and user-replaced values in proc_installing.adoc"
- "Do an SSG formatting review on the changed files"

## References

For detailed guidance, consult:
- [Red Hat Supplementary Style Guide: Formatting](https://redhat-documentation.github.io/supplementary-style-guide/#formatting)
