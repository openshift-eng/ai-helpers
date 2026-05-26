# Activity Type Classification Guidance

This is the Red Hat HCM/HCP Sankey capacity allocation guidance adapted for Activity Type classification. Categories are listed in order of "what would put us out of business the fastest if ignored."

## Proactive vs. Reactive Groupings

- **Proactive**: Associate Wellness & Development, Future Sustainability, Product / Portfolio Work
- **Reactive**: Incidents & Support, Security & Compliance, Quality / Stability / Reliability

## Category Definitions

### 1. Associate Wellness & Development

Onboarding, team growth, training, AI learning activities, conference attendance, associate experience, taking care of ourselves and ensuring the long-term health of everyone on the team.

Not all aspects of this category are tracked in Jira (e.g., PTO/leave). Teams can use their own judgment to determine if a ticket is desired.

**Indicators**: training, onboarding, mentoring, team building, conference, hackathon, learning, wellness, career development

### 2. Incidents & Support

Immediate, business-critical work that directly impacts customers and/or has contractual implications, including regularly-scheduled on-call shifts. All incidents and support escalations are top priority for triage. The severity of the situation dictates required capacity allocation. Support is our core business.

**Indicators**: incident, outage, escalation, customer impact, paging, on-call, SLA breach, emergency fix, production issue, hotfix

### 3. Security & Compliance

As we offer more managed services, compliance like FedRAMP is increasingly important. Security includes processes and tooling that ensure safe patterns when interacting with Red Hat resources.

**Subcategories**:
- **Vulnerabilities (CVEs)**: Common vulnerabilities and exposures with mandatory remediation timelines. Must be evaluated and delivered quickly, on or prior to the due date.
- **Weaknesses**: Potential risks identified by Prodsec that could result in systems being vulnerable to attack if left unaddressed.

**Indicators**: CVE, vulnerability, weakness, FedRAMP, compliance, security review, audit, security tooling, FIPS, SOC2, penetration test, security scanning, certificate rotation, OIDC key rotation

### 4. Quality / Stability / Reliability

Work to solve or address immediate technical situations impacting quality, stability, or reliability.

**Subcategories**:
- **Bugs / SLOs**: Correct problems found with actual vs. expected functionality
- **Chores**: Tasks that ensure build, CI, and other infrastructure are up to date and meet Red Hat standards
- **Tech debt**: Tasks resulting from technical costs incurred after taking shortcuts to prioritize delivery speed over a more optimal solution
- **Toil reduction**: Tasks ensuring build, CI, infrastructure, processes, and related data are up to date and meet applicable standards
- **PMR Action Items**: Tasks resulting from reviews of past incidents aimed at preventing recurrence

**Indicators**: bug, fix, SLO, CI/CD, flaky test, regression, reliability, stability, tech debt, toil, cleanup, infrastructure maintenance, PMR action item, post-mortem

### 5. Future Sustainability

Work that helps set us up for success in the future by preventing problems (reactive work) from occurring and/or actively increasing productivity and effectiveness.

**Subcategories**:
- **Enablement to the Right**: Actions enabling more tightly-coupled delivery activities across roles, reducing hand-offs and waiting
- **Proactive Architecture**: Initiatives addressing long-term technical scenarios, preventing or eliminating technical debt
- **Productivity Improvements & Effectiveness**: Actions improving efficiency and productivity, including investigative work, proposals, proof-of-concepts (Jira Spikes), process automation, eliminating unnecessary steps
- **Team Improvements**: Actions improving team processes and delivery patterns
- **Upstream**: Work establishing relationships with and/or contributing to the upstream community

**Indicators**: refactor (proactive), automation, process improvement, upstream contribution, architecture proposal, spike, investigation, prototype, developer experience, self-service, tooling improvement, documentation improvement

### 6. Product / Portfolio Work

Work that delivers new and/or enhanced functionality and services to customers ("Customer Value"). Typically all work requested by Product Management.

**Subcategories**:
- **Architectural Decisions / Proof of Concept**: Investigatory work establishing a potential path for product/service architecture (often Spikes in Jira)
- **BU Features / BU Product Work**: Features part of product and component roadmaps
- **Strategic Product Work**: Features directly connected to larger product goals (Outcomes in OCPSTRAT) and product revenue targets
- **Strategic Portfolio Work**: Work connected via Jira hierarchy to Strategic Goals (HATSTRAT) and company revenue targets

**Indicators**: feature, enhancement, new capability, customer request, product roadmap, RFE, epic (feature-related), user story, GA, release, product requirement, PRD

## Edge Cases and Disambiguation

- **Refactoring**: If driven by product needs → Product / Portfolio Work. If proactive cleanup → Future Sustainability. If fixing existing instability → Quality / Stability / Reliability.
- **Spikes**: If investigating product direction → Product / Portfolio Work. If investigating process improvement → Future Sustainability.
- **CVE remediation**: Always Security & Compliance, even if it involves code changes that look like bug fixes.
- **Test infrastructure**: If fixing flaky tests → Quality / Stability / Reliability. If building new test frameworks proactively → Future Sustainability.
- **Documentation**: If documenting a new feature → Product / Portfolio Work. If improving existing docs proactively → Future Sustainability.
