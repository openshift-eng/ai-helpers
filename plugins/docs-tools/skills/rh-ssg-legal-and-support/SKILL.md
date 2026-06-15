---
context: fork
name: rh-ssg-legal-and-support
description: Review Red Hat documentation for SSG legal and support compliance — no cost/pricing references, no future release promises, Developer Preview requirements (IMPORTANT admonition, no "supported"), and Technology Preview requirements (IMPORTANT admonition, never "Tech Preview" or "Technical Preview", no "supported as a Technology Preview"). Use this skill when checking Red Hat docs for Technology Preview, Developer Preview, TP/DP admonitions, cost language, future release statements, or support scope compliance. Takes precedence over ibm-sg-legal-information for Red Hat content.
---

# Red Hat SSG: Legal and Support review skill

Review documentation for legal and support compliance with the Red Hat Supplementary Style Guide.

## Checklist

### Cost references

- [ ] No references to costs or charges of Red Hat products
- [ ] No use of "free," "at no initial cost," or similar cost language
- [ ] Cost information is left to marketing materials

### Future releases or plans

- [ ] No promises that a feature or fix will be included in a specific future release
- [ ] No references to specific future release numbers or dates
- [ ] Future plans use words like "anticipate," "expect," or "plan"
- [ ] Exception: deprecation/removal notices may specify a future release

### Developer Preview

- [ ] "Developer Preview" uses initial uppercase capitalization
- [ ] IMPORTANT admonition with required template text is included at the beginning of Developer Preview content
- [ ] The phrase "supported as a Developer Preview" is never used
- [ ] The word "support" is avoided in Developer Preview descriptions — use "available," "provide," "capability" instead
- [ ] When feature becomes GA, the IMPORTANT admonition is removed

### Technology Preview

- [ ] "Technology Preview" uses initial uppercase capitalization — never "Tech Preview" or "Technical Preview"
- [ ] IMPORTANT admonition with required template text is included at the beginning of Technology Preview content
- [ ] The phrase "supported as a Technology Preview" is never used
- [ ] The word "support" is avoided — use "available," "provide," "capability," "functionality," "enable" instead
- [ ] For hardware: "recognize" is the correct term (components recognize devices)
- [ ] When feature becomes GA, the IMPORTANT admonition is removed
- [ ] Brief description is included in the release notes

## How to use

1. Review only changed content and necessary context
2. For each issue found, cite the relevant SSG section
3. Mark issues as **required** (missing TP/DP admonitions, cost references, future release promises) or **[SUGGESTION]** (wording improvements)

## Example invocations

- "Review this file for legal and support compliance"
- "Check Technology Preview and Developer Preview admonitions"
- "Do an SSG legal review on the release notes"

## References

For detailed guidance, consult:
- [Red Hat Supplementary Style Guide: Legal](https://redhat-documentation.github.io/supplementary-style-guide/#legal)
- [Red Hat Supplementary Style Guide: Support](https://redhat-documentation.github.io/supplementary-style-guide/#support)
- [Developer Preview Support Scope](https://access.redhat.com/support/offerings/devpreview/)
- [Technology Preview Features Support Scope](https://access.redhat.com/support/offerings/techpreview/)
