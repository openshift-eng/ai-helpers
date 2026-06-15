---
context: fork
name: ibm-sg-numbers-and-measurement
description: Review documentation for IBM Style Guide number and measurement formatting — numerals vs. spelled-out numbers, commas in large numbers, currency codes (USD/EUR), date formats, 24-hour time, units of measurement (KB/MB/GB with spaces), IEC binary prefixes (KiB/MiB/GiB), and phone numbers. Use this skill when checking number formatting, date/time consistency, unit abbreviations, or measurement conventions in documentation.
---

# IBM Style Guide: Numbers and Measurement review skill

Review documentation for number and measurement issues: numerals vs. words, formatting, currency, dates, times, units, and phone numbers.

**Precedence**: For Red Hat documentation, the Red Hat Supplementary Style Guide (SSG) takes precedence over IBM Style Guide rules. Where guidance conflicts, follow the RH SSG skill for that topic (e.g., `rh-ssg-formatting` for date formats).

## Checklist

### Numerals vs. words

- [ ] Zero through nine are spelled out; numerals are used for 10 and above
- [ ] Numerals are used with units of measurement: "5 GB," "3 seconds"
- [ ] Numerals are used in technical contexts: version numbers, port numbers, step counts
- [ ] Sentences do not start with a numeral (spell out or rewrite)
- [ ] All numbers in a series use numerals if any number is 10+: "3, 7, and 12 servers"
- [ ] Ordinals one through nine are spelled out; 10th and above use numerals

### Number formatting

- [ ] Commas are used in numbers with four or more digits: 1,000 and 10,000
- [ ] A period is used for decimal points: 3.14
- [ ] Large round numbers use words: "2 million users" (not "2,000,000 users")
- [ ] Number ranges are consistent: "5 to 10" or "5-10," not "five to 10"

### Currency

- [ ] ISO currency codes are used for international audiences: USD 100, EUR 50
- [ ] Currency symbols are used for domestic audiences: $100, €50
- [ ] Unnecessary decimal places are avoided: "$100" not "$100.00"
- [ ] Currency symbol or code is placed before the number

### Dates and times

- [ ] Full date format is used for international clarity: "1 January 2025" or "January 1, 2025"
- [ ] All-numeric dates (01/02/25) are not used
- [ ] 24-hour clock is used for technical and international content: 14:00 (not 2:00 PM)
- [ ] Time zones are included when relevant: "14:00 UTC"
- [ ] ISO 8601 format is used in technical/data contexts: 2025-01-15T14:00:00Z

### Units of measurement

- [ ] Standard abbreviations are used: KB, MB, GB, TB, ms, sec, min
- [ ] A space separates the number and unit: "500 MB" (not "500MB")
- [ ] IEC binary prefixes are used for binary values: KiB, MiB, GiB
- [ ] Abbreviated units are not pluralized: "5 GB" not "5 GBs"

### Phone numbers

- [ ] International format with country code is used: +1 512 555 0100
- [ ] Parentheses around area codes are not used in international content

## How to use

1. Review only changed content and necessary context
2. For each issue found, cite the relevant IBM Style Guide section
3. Mark issues as **required** (inconsistent formats, ambiguous dates) or **[SUGGESTION]** (preferences)

## Example invocations

- "Review this file for number formatting issues"
- "Check dates and units in the release notes"
- "Do an IBM numbers review on modules/configuration.adoc"

## References

For detailed guidance, consult:
- IBM Style Guide: Numbers and measurement sections
