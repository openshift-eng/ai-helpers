---
context: fork
name: ibm-sg-language-and-grammar
description: Review documentation for IBM Style Guide language and grammar — abbreviations/acronyms, capitalization, active voice, inclusive language (master/slave, blacklist/whitelist, gendered pronouns), contractions, anthropomorphism, and preferred terminology (avoid "utilize," "leverage," "via," "in order to," "please"). Use this skill when checking grammar, word choice, inclusive language, or terminology compliance. For Red Hat docs, the rh-ssg-grammar-and-language skill takes precedence on conscious language and contractions.
---

# IBM Style Guide: Language and Grammar review skill

Review documentation for language and grammar issues: abbreviations, capitalization, active voice, inclusive language, pronouns, contractions, and preferred terminology.

**Precedence**: For Red Hat documentation, the Red Hat Supplementary Style Guide (SSG) takes precedence over IBM Style Guide rules. Where guidance conflicts, follow the RH SSG skill for that topic (e.g., `rh-ssg-grammar-and-language` for conscious language and contractions).

## Checklist

### Abbreviations and acronyms

- [ ] Abbreviations are spelled out on first use: "command-line interface (CLI)"
- [ ] Well-known abbreviations (API, URL, HTML, PDF) are not unnecessarily spelled out
- [ ] No periods in abbreviations: US, UK, PhD, CEO
- [ ] Plural abbreviations have no apostrophe: APIs, URLs (not API's)
- [ ] Articles match the sound: "an SQL query," "a URL"
- [ ] Do NOT flag command names, utility names, tool names, or executable names as undefined acronyms — these are proper nouns or literal strings, not abbreviations (for example, `db2trc`, `ULOAD`, `SETUP`, `oc`, `kubectl`, `podman`)

### Capitalization

- [ ] Sentence case is used for headings, titles, labels, and buttons
- [ ] Generic technology terms are lowercase: cloud, server, database, container
- [ ] Product names follow official capitalization: GitHub, macOS, PostgreSQL, npm
- [ ] ALL CAPS is not used for emphasis

### Active voice and verbs

- [ ] Active voice is the default: "The system logs the event" not "The event is logged"
- [ ] Present tense is used: "creates" not "will create"
- [ ] Simple verb forms are preferred: "use" not "utilize," "start" not "initiate"
- [ ] Imperative mood is used for instructions
- [ ] Subjunctive mood is avoided ("should you want to..." > "if you want to...")

### Inclusive language

- [ ] "master/slave" is replaced with "primary/replica," "main/secondary," "leader/follower"
- [ ] "blacklist/whitelist" is replaced with "blocklist/allowlist"
- [ ] "sanity check" is replaced with "validity check," "confidence check"
- [ ] "guys," "manpower," "man-hours" are replaced with "team," "workforce," "person-hours"
- [ ] Gendered pronouns are not used for generic users; "they" or rewording is used
- [ ] Ableist language is avoided: "blind to," "cripple," "lame," "dumb"
- [ ] Person-first language is used: "people with disabilities" not "the disabled"

### Pronouns

- [ ] Second person "you" addresses the reader
- [ ] "They/them" is used as singular gender-neutral pronoun (not "he/she" or "s/he")
- [ ] "One" as a pronoun is avoided

### Contractions

- [ ] Contractions are used appropriately for the content type (informal: yes; formal: no)
- [ ] Informal contractions are never used: ain't, gonna, wanna

### Anthropomorphism

- [ ] Software is not given human qualities: "thinks," "wants," "knows," "believes"
- [ ] Software actions are described factually: "detects," "reports," "returns"

### Key terminology (preferred vs. avoid)

- [ ] "abort" > use "end," "cancel," "stop"
- [ ] "above/below" > use "previous/preceding," "following/later"
- [ ] "backend" > use "back end" (noun), "back-end" (adj)
- [ ] "click on" > use "click"
- [ ] "e.g." > use "for example"
- [ ] "etc." > use "and so on"
- [ ] "i.e." > use "that is"
- [ ] "impact" (verb) > use "affect"
- [ ] "in order to" > use "to"
- [ ] "leverage" (verb) > use "use"
- [ ] "may" > use "can" (ability) or "might" (possibility)
- [ ] "please" > omit in instructions
- [ ] "should" > use "must" (requirement) or "can" (suggestion)
- [ ] "simple/simply" > omit
- [ ] "utilize" > use "use"
- [ ] "via" > use "through," "by using"
- [ ] "whether or not" > use "whether"

## How to use

1. Review only changed content and necessary context
2. For each issue found, cite the relevant IBM Style Guide section
3. Mark issues as **required** (inclusive language, incorrect terminology) or **[SUGGESTION]** (wording preferences)

## Example invocations

- "Review this file for IBM language and grammar issues"
- "Check terminology and inclusive language in modules/"
- "Do an IBM language review on the changed files"

## References

For detailed guidance, consult:
- IBM Style Guide: Language and grammar sections
- IBM Style Guide: Word usage appendix
