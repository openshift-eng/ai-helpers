# Example Accomplishment Bullets

These examples demonstrate the correct format for quarterly accomplishment bullets using Red Hat Engineering Competencies **v10.6**.

## Format Pattern

```
[Action verb] [deliverable] [readable links] via [RESPONSIBILITY] and [SKILL] to [impact], [how/details].
```

**Key requirement:** Use 1 RESPONSIBILITY + 1 SKILL from v10.6 framework

## Good Examples

### Strategic Planning
```
Led strategic communication [Strategy Doc] via Own and Deliver Business Impact and Leadership to achieve cross-company alignment on delivery timeline, analyzing risks, alternatives, and mitigation plan.
```

**Why this works:**
- ✅ Direct action verb: "Led"
- ✅ Explicit v10.6 competencies: "Own and Deliver Business Impact and Leadership"
- ✅ Clear impact: "achieve cross-company alignment"
- ✅ Quantified details: No unnecessary adjectives, just facts
- ✅ No adverbs: No "successfully", "effectively", etc.

### Technical Work
```
Fixed job controller startup [PR#1500] via Apply and Advance Technical Practices and Technical Acumen to prevent false degraded states, implementing exponential backoff to retry TNF setup for 10 minutes before degrading.
```

**Why this works:**
- ✅ Direct action: "Fixed"
- ✅ Explicit v10.6 competencies: "Apply and Advance Technical Practices and Technical Acumen"
- ✅ Clear impact: "prevent false degraded states"
- ✅ Quantified: "10 minutes"
- ✅ Technical details at end: "implementing exponential backoff..."

### Team Enablement
```
Created testing library [PR#30332, OCPEDGE-2207] via Apply and Advance Technical Practices and Leadership to enable 3 test authors to develop TNF recovery tests in parallel without code duplication.
```

**Why this works:**
- ✅ Explicit v10.6 competencies: "Apply and Advance Technical Practices and Leadership"
- ✅ Quantified impact: "3 test authors", "in parallel"
- ✅ Clear value: "without code duplication"

### Cross-Functional Collaboration
```
Advanced PacemakerCluster API design [OCPEDGE-2215] via Internal and External Collaboration and System Design to define pacemaker health monitoring in TNF operator conditions, working with API maintainers.
```

**Why this works:**
- ✅ Explicit v10.6 competencies: "Internal and External Collaboration and System Design"
- ✅ Specific partnership: "working with API maintainers"
- ✅ Clear deliverable: "define pacemaker health monitoring"

### Product Delivery / CI Work
```
Fixed CEO presubmits [PR#69895] via SDLC and Continuous Learning to reduce timeout failures, adding sharding to e2e-aws-ovn-serial for 4.16+.
```

**Why this works:**
- ✅ Explicit v10.6 competencies: "SDLC and Continuous Learning"
- ✅ Clear impact: "reduce timeout failures"
- ✅ Quantified scope: "4.16+"
- ✅ Technical approach: "adding sharding"

### Quality / Testing Work
```
Designed test automation framework [PR#2100] via Ensure Software Quality and Reliability and Quality Management to enable regression testing across 5 network configurations, implementing parallel execution with 60% runtime reduction.
```

**Why this works:**
- ✅ Uses v10.6 quality-specific competencies: "Ensure Software Quality and Reliability and Quality Management"
- ✅ Quantified impact: "5 network configurations", "60% runtime reduction"
- ✅ Clear technical approach: "parallel execution"

### Mentoring
```
Mentored 4 engineers on etcd debugging techniques [Mentoring Guide] via Mentor and Develop Engineering Talent and Leadership to reduce incident resolution time from 3 days to 8 hours, establishing troubleshooting runbooks.
```

**Why this works:**
- ✅ Uses v10.6 mentoring competencies: "Mentor and Develop Engineering Talent and Leadership"
- ✅ Quantified impact: "4 engineers", "3 days to 8 hours"
- ✅ Concrete deliverable: "troubleshooting runbooks"

---

## Bad Examples (and how to fix them)

### ❌ Generic Competencies
```
Fixed job controller via debugging to improve reliability.
```

**Problems:**
- "via debugging" - too generic, not a Red Hat v10.6 competency
- "improve reliability" - vague impact
- No link references
- No details/quantification

**✅ Fixed version (v10.6):**
```
Fixed job controller startup [PR#1500] via Apply and Advance Technical Practices and Technical Acumen to prevent false degraded states, implementing exponential backoff to retry TNF setup for 10 minutes before degrading.
```

### ❌ Unnecessary Adverbs
```
Successfully created a comprehensive testing library [PR#30332] using extensive collaboration to effectively enable developers to efficiently write tests.
```

**Problems:**
- "Successfully" - unnecessary adverb
- "comprehensive" - unnecessary adjective
- "extensive collaboration" - not explicit v10.6 competency
- "effectively", "efficiently" - unnecessary adverbs

**✅ Fixed version (v10.6):**
```
Created testing library [PR#30332, OCPEDGE-2207] via Apply and Advance Technical Practices and Leadership to enable 3 test authors to develop TNF recovery tests in parallel without code duplication.
```

### ❌ Missing Impact
```
Led strategic communication [Strategy Doc] via Own and Deliver Business Impact, analyzing timeline risks and alternatives.
```

**Problems:**
- No clear impact statement ("to achieve...")
- Details given but outcome missing
- Missing second competency (only Responsibility, no Skill)

**✅ Fixed version (v10.6):**
```
Led strategic communication [Strategy Doc] via Own and Deliver Business Impact and Leadership to achieve cross-company alignment on delivery timeline, analyzing risks, alternatives, and mitigation plan.
```

### ❌ Using Old v9.0 Keywords
```
Fixed etcd quorum detection [PR#1483] via technical innovation and business impact to eliminate false alerts.
```

**Problems:**
- "technical innovation" and "business impact" are v9.0 terms (outdated)
- Should use v10.6 Responsibilities + Skills

**✅ Fixed version (v10.6):**
```
Fixed etcd quorum detection [PR#1483] via Apply and Advance Technical Practices and Technical Acumen to eliminate false quorum-lost alerts during fencing operations.
```

---

## Competency Keyword Reference (v10.6)

### Responsibilities (What You DO) - 8 Total

**Use EXACTLY these terms as the first competency:**
1. Technical Impact
2. Ensure Software Quality and Reliability
3. Internal and External Collaboration
4. Mentor and Develop Engineering Talent
5. Own and Deliver Business Impact
6. Apply and Advance Technical Practices
7. Leverage and Utilize AI Tools *(NEW in v10.6)*
8. SDLC

### Job Skills (Capabilities You HAVE) - 10 Total

**Use EXACTLY these terms as the second competency:**
1. Technical Acumen
2. Quality Management
3. System Design
4. Communication
5. Collaboration
6. Leadership
7. Business impact *(note lowercase)*
8. Continuous Learning
9. Influence
10. Knowledge Sharing

### Common Responsibility + Skill Combinations

**Technical work:**
- Technical Impact + Technical Acumen

**Quality/Testing:**
- Ensure Software Quality and Reliability + Quality Management

**Cross-team projects:**
- Internal and External Collaboration + Collaboration

**Mentoring:**
- Mentor and Develop Engineering Talent + Leadership

**Bug fixes:**
- Own and Deliver Business Impact + Business impact

**Process improvements:**
- Apply and Advance Technical Practices + Continuous Learning

**CI/CD work:**
- SDLC + Quality Management

**Strategic planning:**
- Own and Deliver Business Impact + Leadership

**Upstream contributions:**
- Internal and External Collaboration + Knowledge Sharing

**AI/Automation:**
- Leverage and Utilize AI Tools + Technical Acumen

### DON'T Use v9.0 Terms (Outdated)

- ❌ "technical innovation" → ✅ "Apply and Advance Technical Practices"
- ❌ "business impact" (v9.0) → ✅ "Own and Deliver Business Impact" (Responsibility) or "Business impact" (Skill)
- ❌ "cross-functional collaboration" → ✅ "Internal and External Collaboration" (Responsibility) or "Collaboration" (Skill)
- ❌ "functional area leadership" → ✅ "Own and Deliver Business Impact and Leadership"
- ❌ "continuous improvement" → ✅ "Apply and Advance Technical Practices and Continuous Learning"
- ❌ "product delivery lifecycle management" → ✅ "SDLC and Quality Management"
- ❌ "team enablement" → ✅ "Mentor and Develop Engineering Talent and Leadership"
- ❌ "technical knowledge" → ✅ "Technical Impact and Technical Acumen"

### DON'T Use Generic Terms

- ❌ "collaboration" alone → ✅ "Internal and External Collaboration and Collaboration"
- ❌ "innovation" alone → ✅ "Apply and Advance Technical Practices and Technical Acumen"
- ❌ "leadership" alone → ✅ Use specific Responsibility + Leadership skill
- ❌ "debugging" alone → ✅ "Technical Impact and Technical Acumen"
- ❌ "working with team" → ✅ "Internal and External Collaboration and Collaboration"

**Always use TWO keywords:** 1 Responsibility + 1 Skill (order doesn't matter, but Responsibility first is conventional)

---

## HTML Format Example

When outputting to HTML, use this format:

```html
<ul>
<li>Fixed job controller startup [<a href="https://github.com/openshift/cluster-etcd-operator/pull/1500">PR#1500</a>] via Apply and Advance Technical Practices and Technical Acumen to prevent false degraded states, implementing exponential backoff to retry TNF setup for 10 minutes before degrading.</li>
</ul>
```

This renders as clickable links when pasted into Workday.

---

## Migration Notes

If you have existing bullets using v9.0 keywords, simply replace the competency keywords with v10.6 equivalents. The format pattern remains identical - only the competency vocabulary changed.

**Example migration:**
- **v9.0:** "via technical innovation and business impact"
- **v10.6:** "via Apply and Advance Technical Practices and Technical Acumen"

See `red-hat-competencies.md` for complete v9.0 → v10.6 mapping table.
