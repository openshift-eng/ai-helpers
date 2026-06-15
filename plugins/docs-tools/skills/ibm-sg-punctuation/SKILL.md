---
context: fork
name: ibm-sg-punctuation
description: Review documentation for IBM Style Guide punctuation — serial/Oxford commas, colons before lists, em dashes vs. en dashes vs. hyphens, compound adjective hyphenation, quotation marks (US style), semicolon avoidance, ellipses, exclamation points, parentheses, slashes ("and/or"), and period consistency in lists. Use this skill when checking punctuation, hyphenation, comma usage, dash types, or list punctuation consistency.
---

# IBM Style Guide: Punctuation review skill

Review documentation for punctuation issues: colons, commas, dashes, hyphens, parentheses, periods, quotation marks, semicolons, and slashes.

**Precedence**: For Red Hat documentation, the Red Hat Supplementary Style Guide (SSG) takes precedence over IBM Style Guide rules where guidance conflicts.

## Checklist

### Colons

- [ ] Colons introduce lists only after a complete sentence
  - Correct: "The tool supports three languages: Python, Go, and Java."
  - Wrong: "The tool supports: Python, Go, and Java."
- [ ] Text after a colon is not capitalized unless it begins a complete sentence or proper noun

### Commas

- [ ] Serial (Oxford) comma is used before "and"/"or" in lists of three or more
- [ ] Commas follow introductory phrases
- [ ] No comma before "that" in restrictive clauses
- [ ] Comma used before "which" in nonrestrictive clauses

### Dashes

- [ ] Em dashes (—) are used for emphasis or asides, with no spaces around them
- [ ] En dashes (–) are used for ranges: "pages 10–15"
- [ ] Hyphens (-) are not used where em dashes or en dashes belong
- [ ] No more than one pair of em dashes per sentence

### Ellipses

- [ ] Ellipses are not used to trail off or imply something
- [ ] Ellipses indicate omitted text in quotations or "more input needed" in UI only

### Exclamation points

- [ ] Exclamation points are not used in technical documentation
- [ ] Multiple exclamation points ("!!!") are never used

### Hyphens

- [ ] Compound adjectives are hyphenated before a noun: "command-line interface"
- [ ] Compound adjectives are not hyphenated after a noun: "the interface is command line"
- [ ] Adverb-adjective compounds with "-ly" are not hyphenated: "newly created file"
- [ ] Prefixes before proper nouns or numbers are hyphenated: "pre-2020," "non-IBM"
- [ ] Common prefixes are not hyphenated: reuse, coexist, noncompliant, preinstall, multicloud

### Parentheses

- [ ] Parentheses are used sparingly; important content is integrated into the sentence
- [ ] Parentheses are not nested
- [ ] Punctuation is placed outside parentheses (unless the entire sentence is parenthetical)

### Periods

- [ ] One space follows a period (not two)
- [ ] Periods end complete sentences in lists
- [ ] Periods are not used in headings, subheadings, or button labels
- [ ] List items are consistent: all periods or no periods, not mixed

### Quotation marks

- [ ] Double quotation marks are used for direct quotes and titles
- [ ] Commas and periods are placed inside quotation marks (US style)
- [ ] Colons and semicolons are placed outside quotation marks
- [ ] Quotation marks are not used for emphasis (use bold or italic)
- [ ] Code terms use monospace formatting, not quotation marks

### Semicolons

- [ ] Semicolons are avoided; sentences are split instead
- [ ] Semicolons are used only in complex lists where items contain commas

### Slashes

- [ ] Slashes for "or" are avoided; "or" is written out: "Linux or macOS" not "Linux/macOS"
- [ ] "and/or" is not used; "and," "or," or rephrasing is preferred
- [ ] Slashes are acceptable in established terms: "client/server," "TCP/IP," "I/O"

## How to use

1. Review only changed content and necessary context
2. For each issue found, cite the relevant IBM Style Guide section
3. Mark issues as **required** (incorrect punctuation) or **[SUGGESTION]** (style preferences)

## Example invocations

- "Review this file for punctuation issues"
- "Check comma and hyphen usage in this module"
- "Do an IBM punctuation review on the changed files"

## References

For detailed guidance, consult:
- IBM Style Guide: Punctuation sections
