# Documentation plan template

Template and instructions for producing documentation plans. Used by the docs-planner agent.

## Output structure

The planner produces two outputs from the same research: a full documentation plan (saved as an attachment) and an abbreviated JIRA ticket description (posted to the ticket). Both are populated from your research and analysis — **you MUST replace every `[REPLACE: ...]` marker** with actual content. Never output bracket instructions, placeholder text, or the persona reference list.

### Full documentation plan (attachment)

Save the fully populated template below to the output path specified in the workflow prompt. When invoked by the orchestrator, this is `<base-path>/planning/plan.md`; when invoked by the legacy command, save to `artifacts/plans/plan_<project>_<yyyymmdd>.md`. This is the comprehensive planning artifact with all sections completed.

### JIRA ticket description

Post **only these sections** from the full plan to the JIRA ticket description:

- `## What is the main JTBD? What user goal is being accomplished? What pain point is being avoided?`
- `## How does the JTBD(s) relate to the overall real-world workflow for the user?`
- `## Who can provide information and answer questions?`
- `## New Docs`
- `## Updated Docs`

Copy these five sections verbatim from the completed full plan. Do not add sections that are not in this list to the JIRA ticket description. The full plan attachment contains the remaining detail.

## Template

**Critical rules for template population:**
- **Replace ALL `[REPLACE: ...]` text** with real content derived from your research — never output the bracket instructions themselves
- **Personas**: Select 1-3 personas from the persona reference list below. Output ONLY the selected personas with a brief relevance note. Do NOT include the full persona reference list in the output
- **New Docs / Updated Docs**: Replace the example entries with actual module names, types, and content outlines from your planning. The entries shown (e.g., "Actual Module Title (Concept)") are structural examples, not headings to keep
- **JTBD statement**: Replace `[actual circumstance]`, `[actual motivation]`, etc. with the real job statement from your analysis

~~~markdown
# Documentation Plan

**Project**: [REPLACE: Project name from JIRA ticket]
**Date**: [REPLACE: Current date in YYYY-MM-DD format]
**Ticket**: [REPLACE: JIRA ticket ID and URL]

## What is the support status of the feature(s) being used to complete the user's JTBD (Job To Be Done)?

[REPLACE: Choose one of Dev Preview / Tech Preview / General Availability based on JIRA ticket metadata]

## Why is this content important?

[REPLACE: Summarize why the user needs this content, derived from your JTBD analysis]

## Who is the target persona(s)?

[REPLACE: List 1-3 selected personas with brief relevance notes. Example output:]
[* Developer: Primary user creating containerized applications]
[* SysAdmin: Manages the platform where containers are deployed]

## What is the main JTBD? What user goal is being accomplished? What pain point is being avoided?

[REPLACE: Write the completed job statement using your research findings]
When [actual circumstance], I want to [actual motivation], so that I can [actual goal] while avoiding [actual pain point].

## How does the JTBD(s) relate to the overall real-world workflow for the user?

[REPLACE: Explain how the JTBD fits into the user's broader end-to-end workflow]

## What high-level steps does the user need to take to accomplish the goal?

[REPLACE: Provide the actual steps and prerequisites identified during your planning]

## Is there a demo available or can one be created?

[REPLACE: No / Yes — include link if available]

## Are there special considerations for disconnected environments?

[REPLACE: No / Yes — describe considerations if applicable]

## Who can provide information and answer questions?

[REPLACE: Extract PM / Technical SME / UX contacts from the parent JIRA ticket]

## Release Note needed?

[REPLACE: No / Yes]

Draft release note: [REPLACE: Draft a release note based on the user-facing change, or N/A]

## Links to existing content

[REPLACE: Add actual links discovered during research as bullets]

## New Docs

[REPLACE: List actual new modules to create based on your gap analysis and module planning. Follow this structure for each:]

* Actual Module Title (Concept/Procedure/Reference)
    Actual content outline derived from your research

## Updated Docs

[REPLACE: List actual existing modules that need updates based on your gap analysis. Follow this structure for each:]

* actual-existing-filename.adoc
    Specific updates required based on your findings
~~~

## Persona reference list

Select 1-3 personas from this list when populating the "Who is the target persona(s)?" section. Do NOT include this list in the output.

| Persona | Description |
|---------|-------------|
| C-Suite IT | The ultimate budget owner and final decision-maker for technology purchases, focused on cloud migration, cost efficiency, and finding established vendors with strong reputations. |
| C-Suite Non-IT | Holds significant budget influence and focuses on ROI and digital transformation, but relies on IT to vet the technical integration and security capabilities of new solutions. |
| AppDev ITDM | Typically owns the budget for application and cloud infrastructure, prioritizing innovation in cloud-native development and automation to improve customer and employee experiences. |
| Enterprise Architect | A technical influencer rather than a budget owner, they focus on how new automation and cloud solutions will integrate with and support the existing infrastructure. |
| IT Operations Leader | Owns the budget for IT infrastructure and operations, prioritizing security, virtualization, and cloud migration to ensure system stability and end-user satisfaction. |
| Line of Business (LOB) | Budget owners for specific business units (like Marketing or Sales) who focus on customer satisfaction and operational efficiency, often requiring proof of successful implementation. |
| SysAdmin | Influences purchasing by recommending specific solutions to modernize infrastructure, focusing heavily on automation and virtualization even though they do not own the budget. |
| Procurement | A budget owner or influencer who researches vendors to ensure cost savings and compliance, requiring detailed support information to justify recommendations to internal business units. |
| Developer | Focused on creating solutions using tools like APIs and Kubernetes, they act as influencers who value technical specs and community support rather than managing budgets or making final decisions. |
| Data Scientist | Influences purchases for data and development platforms, driven by a passion for AI/ML and big data analytics to drive innovation and strategic decision-making. |
| IT Security Practitioner / Compliance & Auditor | Often a budget owner involved throughout the process, prioritizing data protection, risk mitigation, and identity management to prevent security breaches. |
| Automation Architect | A budget owner or influencer for Engineering and IT, motivated by creative problem-solving and focused on implementing automation, big data, and cloud computing technologies. |
| Network Architect (Telco) | A budget owner involved in the entire purchase process, deeply focused on migrating to 5G, automation, and cloud technologies to stay ahead in a changing market. |
| Network Admin/Ops (Telco) | Recommends vendors and defines capabilities with a focus on automating network operations and resolving customer issues quickly, though rarely the final decision-maker. |
| Head of Product Line (FinServ) | Sets strategy for their specific line of business and is open to pioneering technologies that innovate the business, despite operating in a culture often resistant to change. |

## How to populate the template

- **Support status**: Determine from JIRA ticket labels, fix version, or parent epic metadata. If not explicitly stated, flag for confirmation.
- **Why important**: Derive from the JTBD analysis — explain the user value, not the feature description.
- **Target personas**: Select from the persona reference list above based on who the JTBD applies to. Limit to 3 personas maximum per the self-review verification checklist.
- **JTBD statement**: Use the job statement from your JTBD analysis. Must follow the "When... I want to... so that I can..." format with all placeholders replaced.
- **High-level steps**: Extract from your procedure module planning. Include prerequisites identified during gap analysis.
- **Contacts**: Extract PM, SME, and UX contacts from the parent JIRA ticket fields (assignee, reporter, watchers, or custom fields).
- **Release note**: Check the JIRA ticket for release note fields or labels. Draft a release note based on the user-facing change.
- **Links to existing content**: Include links to existing documentation, upstream docs, and related JIRA tickets discovered during research.
- **New Docs / Updated Docs**: Map directly from your recommended modules and gap analysis sections. Use actual module names and real content outlines — not the example entries from the template.
