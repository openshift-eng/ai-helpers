---
context: fork
name: ibm-sg-legal-information
description: Review documentation for IBM Style Guide legal issues — unsubstantiated claims, superlatives, trademarks (™/® usage), copyright notices, personal information (PII in examples), and republishing/attribution of external content. Use this skill when checking for legal risks, trademark compliance, PII exposure in examples, unsupported marketing claims, or content attribution issues. For Red Hat docs, the rh-ssg-legal-and-support skill takes precedence on Technology Preview and Developer Preview.
---

# IBM Style Guide: Legal Information review skill

Review documentation for legal issues: claims and recommendations, company names, trademarks, copyright notices, personal information, and republishing.

**Precedence**: For Red Hat documentation, the Red Hat Supplementary Style Guide (SSG) takes precedence over IBM Style Guide rules. Where guidance conflicts, follow the RH SSG skill for that topic (e.g., `rh-ssg-legal-and-support` for Technology Preview and Developer Preview).

## Checklist

### Claims and recommendations

- [ ] No unsubstantiated claims; assertions are backed by evidence or data
- [ ] Superlatives are avoided: "best," "fastest," "most secure," "only," "first"
- [ ] Outcomes are not guaranteed: "ensures," "guarantees," "will always" > "helps," "is designed to," "can"
- [ ] No comparative claims against competitors (unless legally reviewed)
- [ ] Performance claims are qualified with context: "up to 50% faster in internal benchmarks using X"
- [ ] No implied third-party endorsement without authorization
- [ ] Forward-looking statements about unannounced features are avoided
- [ ] "Can" is used instead of "will" for capability statements

### Company names

- [ ] Full legal company name is used on first reference in formal documents
- [ ] Official capitalization and spacing are followed: "Red Hat" not "Redhat"
- [ ] Required trademark attributions are included where legally necessary

### Trademarks

- [ ] Trademark symbols (™, ®) appear on first prominent use only
- [ ] Trademark symbols are not in headings, code examples, or every instance
- [ ] Trademarks are used as adjectives, not nouns or verbs:
  - Correct: "a Docker container," "Kubernetes orchestration"
  - Wrong: "use a Docker," "Kubernetes the deployment"
- [ ] Trademarks are not modified: no pluralizing, abbreviating, or changing capitalization

### Copyright notices

- [ ] Copyright notices are included as required by the legal team
- [ ] Format follows: "Copyright © [year] [company]. All rights reserved."
- [ ] Year is updated when content is substantially revised

### Personal information

- [ ] No real personal information is used in examples
- [ ] Fictional names, addresses, phone numbers, and emails are used
- [ ] Employee names, emails, and internal IDs are not in published content
- [ ] No real SSNs, credit card numbers, or PII — even in examples
- [ ] Screenshots with personal data are redacted before publishing

### Republishing existing content

- [ ] External content is not copied without permission and attribution
- [ ] Content is paraphrased rather than quoted at length; sources are cited
- [ ] Open-source documentation licenses are verified for intended use
- [ ] Proprietary vendor documentation is not reproduced verbatim
- [ ] External content is linked to the canonical source rather than reproduced
- [ ] Creative Commons and open-content license requirements are respected

## How to use

1. Review only changed content and necessary context
2. For each issue found, cite the relevant IBM Style Guide section
3. Mark issues as **required** (trademark violations, PII exposure, unsubstantiated claims) or **[SUGGESTION]** (improvements)

## Example invocations

- "Review this file for legal and compliance issues"
- "Check trademarks and claims in the marketing page"
- "Do an IBM legal review on modules/overview.adoc"

## References

For detailed guidance, consult:
- IBM Style Guide: Legal information sections
- Your organization's legal and trademark guidelines
