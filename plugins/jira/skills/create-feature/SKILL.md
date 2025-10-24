---
name: Create Jira Feature
description: Implementation guide for creating Jira features representing strategic objectives and market problems
---

# Create Jira Feature

This skill provides implementation guidance for creating Jira features, which represent high-level strategic objectives and solutions to market problems.

## When to Use This Skill

This skill is automatically invoked by the `/jira:create feature` command to guide the feature creation process.

## Prerequisites

- MCP Jira server configured and accessible
- User has permissions to create issues in the target project
- Understanding of the strategic objective and market problem
- Product/business context for the feature

## What is a Feature?

A feature is:
- A **strategic objective** that addresses a market problem or customer need
- **Broader than an epic** - typically contains multiple epics
- A **product capability** that delivers business value
- Aligned with **product roadmap** and business goals
- Typically spans **one or more releases**

### Feature vs Epic vs Story

| Level | Scope | Duration | Example |
|-------|-------|----------|---------|
| **Feature** | Strategic objective, market problem | 1-3 releases (3-9 months) | "Advanced hosted control plane observability" |
| Epic | Specific capability within feature | 1 quarter/release | "Multi-cluster metrics aggregation" |
| Story | Single user-facing functionality | 1 sprint | "View aggregated cluster metrics in dashboard" |

### Feature Characteristics

Features should:
- Address a **specific market problem** or customer need
- Be **more strategic** than implementation details
- Contain **multiple epics** (typically 3-8 epics)
- Deliver **measurable business value**
- Align with **product strategy** and roadmap
- Have clear **success criteria** (not just completion criteria)

## Feature Description Best Practices

### Market Problem

Every feature should clearly state:
- **What customer/business problem** does this solve?
- **Who** is affected by this problem?
- **Why** is solving this problem important now?
- **What happens** if we don't solve it?

**Good example:**
```
h2. Market Problem

Enterprise customers managing multiple ROSA HCP clusters (10+) struggle with operational visibility and control. They must navigate between separate dashboards for each cluster, making it difficult to:
- Identify issues across their cluster fleet
- Track resource utilization trends
- Respond quickly to incidents
- Optimize costs across clusters

This leads to increased operational overhead, slower incident response, and higher support costs. Without a unified observability solution, customers face scalability challenges as their cluster count grows.
```

**Bad example:**
```
We need better observability.
```

### Strategic Value

Explain why this feature matters to the business:
- **Business impact:** Revenue, cost reduction, market differentiation
- **Customer value:** What do customers gain?
- **Competitive advantage:** How does this position us vs competitors?
- **Strategic alignment:** How does this support company/product strategy?

**Example:**
```
h2. Strategic Value

h3. Customer Value
- 60% reduction in time spent on cluster management
- Faster incident detection and response (10min → 2min)
- Better resource optimization across cluster fleet
- Improved operational confidence at scale

h3. Business Impact
- Supports enterprise expansion (critical for deals >100 clusters)
- Reduces support burden (fewer escalations, faster resolution)
- Competitive differentiator (no competitor offers unified HCP observability)
- Enables upsell opportunities (advanced monitoring add-ons)

h3. Strategic Alignment
- Aligns with "Enterprise-First" product strategy for FY2025
- Prerequisite for multi-cluster management capabilities in roadmap
- Supports OpenShift Hybrid Cloud Platform vision
```

### Success Criteria

Define how you'll measure success (not just completion):
- **Adoption metrics:** How many customers will use this?
- **Usage metrics:** How will it be used?
- **Outcome metrics:** What improves as a result?
- **Business metrics:** Revenue, cost, satisfaction impact

**Example:**
```
h2. Success Criteria

h3. Adoption
- 50% of customers with 10+ clusters adopt within 6 months of GA
- Feature enabled by default for new cluster deployments

h3. Usage
- Average of 5 dashboard views per day per customer
- Alert configuration adoption >30% of customers
- API usage growing 20% month-over-month

h3. Outcomes
- 40% reduction in time-to-detect incidents (measured via support metrics)
- Customer satisfaction (CSAT) improvement from 7.2 to 8.5 for multi-cluster users
- 25% reduction in cluster management support tickets

h3. Business
- Closes 10+ enterprise deals blocked by observability gap
- Reduces support costs by $200K annually
- Enables $500K in advanced monitoring upsell revenue
```

## Interactive Feature Collection Workflow

When creating a feature, guide the user through strategic thinking:

### 1. Market Problem

**Prompt:** "What customer or market problem does this feature solve? Be specific about who is affected and why it matters."

**Probing questions:**
- Who has this problem? (customer segment, user type)
- What pain do they experience today?
- What is the impact of not solving this?
- Why is solving this important now?

**Example response:**
```
Enterprise customers with large ROSA HCP deployments (50+ clusters) struggle with operational visibility. They must manage each cluster separately, leading to slow incident response, difficulty tracking compliance, and high operational overhead. This is blocking large enterprise deals and causing customer escalations.
```

### 2. Proposed Solution

**Prompt:** "How will this feature solve the problem? What capability will be delivered?"

**Example response:**
```
Deliver a unified observability platform for ROSA HCP that aggregates metrics, logs, and events across all clusters in a customer's fleet. Provide centralized dashboards, fleet-wide alerting, and compliance reporting.
```

### 3. Strategic Value

**Prompt:** "Why is this strategically important? What business value does it deliver?"

**Helpful questions:**
- What business impact will this have? (revenue, cost, market position)
- How does this align with product strategy?
- What competitive advantage does this provide?
- What customer value is delivered?

**Example response:**
```
Customer value: 50% reduction in cluster management time
Business impact: Unblocks $5M in enterprise deals, reduces support costs
Competitive advantage: No competitor offers unified HCP observability
Strategic alignment: Critical for enterprise market expansion
```

### 4. Success Criteria

**Prompt:** "How will you measure success? What metrics will tell you this feature achieved its goals?"

**Categories to consider:**
- Adoption (who/how many use it)
- Usage (how they use it)
- Outcomes (what improves)
- Business (revenue, cost, satisfaction)

**Example response:**
```
Adoption: 50% of enterprise customers within 6 months
Usage: Daily active usage by SREs in 80% of adopting customers
Outcomes: 40% faster incident detection
Business: Closes 15+ blocked enterprise deals
```

### 5. Scope and Epics

**Prompt:** "What are the major components or epics within this feature?"

**Identify 3-8 major work streams:**

**Example response:**
```
1. Multi-cluster metrics aggregation
2. Unified observability dashboard
3. Fleet-wide alerting and automation
4. Compliance and audit reporting
5. API and CLI for programmatic access
6. Documentation and enablement
```

### 6. Timeline and Milestones

**Prompt:** "What is the timeline? What are key milestones?"

**Example response:**
```
Timeline: 9 months (3 releases)
Milestones:
- Q1 2025: MVP metrics aggregation (Epic 1)
- Q2 2025: Dashboard and alerting (Epics 2-3)
- Q3 2025: Compliance, API, GA (Epics 4-6)
```

## Field Validation

Before submitting the feature, validate:

### Required Fields
- ✅ Summary clearly states the strategic objective
- ✅ Description includes market problem
- ✅ Strategic value articulated
- ✅ Success criteria defined (measurable)
- ✅ Component is specified (if required by project)
- ✅ Target version/release is set (if required)

### Feature Quality
- ✅ Addresses a real market problem
- ✅ Strategic value is clear
- ✅ Success criteria are measurable
- ✅ Scope is larger than an epic (multi-epic)
- ✅ Timeline is realistic (1-3 releases)
- ✅ Aligns with product strategy

### Security
- ✅ No credentials, API keys, or secrets in any field
- ✅ No confidential business information (if public project)

## MCP Tool Parameters

### Basic Feature Creation

```python
mcp__atlassian__jira_create_issue(
    project_key="<PROJECT_KEY>",
    summary="<feature summary>",
    issue_type="Feature",
    description="""
<Brief overview of the feature>

h2. Market Problem

<Describe the customer/business problem this solves>

h2. Proposed Solution

<Describe the capability/solution being delivered>

h2. Strategic Value

h3. Customer Value
* <Customer benefit 1>
* <Customer benefit 2>

h3. Business Impact
* <Business impact 1>
* <Business impact 2>

h3. Strategic Alignment
<How this aligns with product strategy>

h2. Success Criteria

h3. Adoption
* <Adoption metric 1>

h3. Outcomes
* <Outcome metric 1>

h3. Business
* <Business metric 1>

h2. Scope

h3. Epics (Planned)
* Epic 1: <epic name>
* Epic 2: <epic name>
* Epic 3: <epic name>

h2. Timeline

* Target: <release/timeframe>
* Key milestones: <major deliverables>
    """,
    components="<component name>",  # if required
    additional_fields={
        # Add project-specific fields
    }
)
```

### With Project-Specific Fields (e.g., CNTRLPLANE)

```python
mcp__atlassian__jira_create_issue(
    project_key="CNTRLPLANE",
    summary="Advanced observability for hosted control planes",
    issue_type="Feature",
    description="""
Deliver unified observability capabilities for ROSA and ARO hosted control planes, enabling enterprise customers to manage large cluster fleets with centralized monitoring, alerting, and compliance reporting.

h2. Market Problem

Enterprise customers managing multiple ROSA HCP clusters (50+) face significant operational challenges:

* Must navigate separate dashboards for each cluster (time-consuming, error-prone)
* Cannot track compliance posture across cluster fleet
* Slow incident detection and response (10-30 minutes to identify cross-cluster issues)
* Difficulty optimizing resources and costs across clusters
* High operational overhead preventing scaling to larger deployments

This problem affects our largest customers and is blocking expansion into enterprise segments. Competitors are beginning to offer fleet management capabilities, creating competitive pressure.

h2. Proposed Solution

Build a comprehensive observability platform for hosted control planes that provides:

* Centralized metrics aggregation across all customer clusters
* Unified dashboards for cluster health, performance, and capacity
* Fleet-wide alerting with intelligent cross-cluster correlation
* Compliance and audit reporting across cluster fleet
* APIs and CLI for programmatic access and automation
* Integration with existing customer monitoring tools

h2. Strategic Value

h3. Customer Value
* 60% reduction in time spent on cluster operational tasks
* 80% faster incident detection and response (30min → 6min)
* Improved compliance posture with automated reporting
* Confidence to scale to 100+ clusters
* Better resource optimization (20% cost savings through right-sizing)

h3. Business Impact
* Unblocks $5M in enterprise pipeline (15+ deals require this capability)
* Reduces support escalations by 40% (better self-service visibility)
* Competitive differentiator (no competitor offers unified HCP observability at this level)
* Enables $500K annual upsell revenue (advanced monitoring add-ons)
* Improves customer retention (reducing churn in enterprise segment)

h3. Competitive Advantage
* First-to-market with truly unified HCP observability
* Deep integration with OpenShift ecosystem
* AI-powered insights (future capability)

h3. Strategic Alignment
* Aligns with "Enterprise-First" product strategy for FY2025
* Supports "Hybrid Cloud Platform" vision
* Prerequisite for future multi-cluster management capabilities on roadmap
* Enables shift to "fleet management" business model

h2. Success Criteria

h3. Adoption
* 50% of customers with 10+ clusters adopt within 6 months of GA
* Feature enabled by default for all new ROSA HCP deployments
* 30% adoption in ARO HCP customer base within 9 months

h3. Usage
* Daily active usage by SREs in 80% of adopting customers
* Average 10+ dashboard views per customer per day
* Alert configuration adoption >40% of customers
* API usage growing 25% month-over-month

h3. Outcomes
* 40% reduction in time-to-detect incidents (measured via support metrics)
* 50% reduction in time-to-resolve incidents (via support ticket analysis)
* Customer satisfaction (CSAT) improvement from 7.2 to 8.5 for multi-cluster customers
* 30% reduction in cluster management support tickets

h3. Business Metrics
* Close 15 blocked enterprise deals ($5M+ in ARR)
* Reduce support costs by $250K annually
* Generate $500K in upsell revenue (advanced monitoring)
* Improve enterprise customer retention by 15%

h2. Scope

h3. Epics (Planned)
* Epic 1: Multi-cluster metrics aggregation infrastructure
* Epic 2: Unified observability dashboard and visualization
* Epic 3: Fleet-wide alerting and intelligent correlation
* Epic 4: Compliance and audit reporting
* Epic 5: API and CLI for programmatic access
* Epic 6: Customer monitoring tool integrations (Datadog, Splunk)
* Epic 7: Documentation, training, and customer enablement

h3. Out of Scope (Future Considerations)
* Log aggregation (separate feature planned for 2026)
* AI-powered predictive analytics (follow-on feature)
* Support for standalone OpenShift clusters (not HCP)
* Cost optimization recommendations (different feature)

h2. Timeline

* Total duration: 9 months (3 releases)
* Target GA: Q3 2025 (OpenShift 4.23)

h3. Milestones
* Q1 2025 (4.21): MVP metrics aggregation, basic dashboard (Epics 1-2)
* Q2 2025 (4.22): Alerting, compliance reporting (Epics 3-4)
* Q3 2025 (4.23): API, integrations, GA (Epics 5-7)

h2. Dependencies

* Centralized metrics storage infrastructure ([CNTRLPLANE-50])
* Cluster registration and inventory service ([CNTRLPLANE-75])
* Identity and access management for multi-cluster ([CNTRLPLANE-120])

h2. Risks and Mitigation

h3. Risks
* Performance degradation with >500 clusters (scalability testing needed)
* Integration complexity with third-party monitoring tools
* Customer adoption if migration from existing tools is complex

h3. Mitigation
* Performance benchmarking sprint in Epic 1
* Partner early with Datadog/Splunk on integration design
* Provide migration tools and dedicated customer success support
    """,
    components="HyperShift",
    additional_fields={
        "customfield_12319940": "openshift-4.21",  # target version (initial)
        "labels": ["ai-generated-jira", "observability", "enterprise"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

## Jira Description Formatting

Use Jira's native formatting (Wiki markup):

### Feature Template Format

```
<Brief feature overview>

h2. Market Problem

<Detailed description of customer/business problem>
<Who is affected, what pain they experience, impact of not solving>

h2. Proposed Solution

<Description of the capability/solution being delivered>

h2. Strategic Value

h3. Customer Value
* <Benefit 1>
* <Benefit 2>

h3. Business Impact
* <Impact 1>
* <Impact 2>

h3. Competitive Advantage
<How this differentiates us>

h3. Strategic Alignment
<How this supports product/company strategy>

h2. Success Criteria

h3. Adoption
* <Adoption metrics>

h3. Usage
* <Usage metrics>

h3. Outcomes
* <Customer outcome metrics>

h3. Business Metrics
* <Revenue, cost, satisfaction metrics>

h2. Scope

h3. Epics (Planned)
* Epic 1: <name>
* Epic 2: <name>
* Epic 3: <name>

h3. Out of Scope
* <Related work NOT in this feature>

h2. Timeline

* Total duration: <timeframe>
* Target GA: <date/release>

h3. Milestones
* <Quarter/Release>: <deliverable>
* <Quarter/Release>: <deliverable>

h2. Dependencies (if any)

* [PROJ-XXX] - <dependency description>

h2. Risks and Mitigation (optional)

h3. Risks
* <Risk 1>
* <Risk 2>

h3. Mitigation
* <Mitigation strategy 1>
* <Mitigation strategy 2>
```

## Error Handling

### Feature Too Small

**Scenario:** Feature could be accomplished as a single epic.

**Action:**
1. Suggest creating as Epic instead
2. Explain feature should be multi-epic effort

**Example:**
```
This feature seems small enough to be a single Epic (1-2 months, single capability).

Features should typically:
- Contain 3-8 epics
- Span multiple releases (6-12 months)
- Address strategic market problem

Would you like to create this as an Epic instead? (yes/no)
```

### Missing Strategic Context

**Scenario:** User doesn't provide market problem or strategic value.

**Action:**
1. Explain importance of strategic framing
2. Ask probing questions
3. Help articulate business case

**Example:**
```
For a feature, we need to understand the strategic context:

1. What market problem does this solve?
2. Why is this strategically important to the business?
3. What value do customers get?

These help stakeholders understand why we're investing in this feature.

Let's start with: What customer problem does this solve?
```

### Vague Success Criteria

**Scenario:** Success criteria are vague or not measurable.

**Action:**
1. Identify vague criteria
2. Ask for specific metrics
3. Suggest measurable alternatives

**Example:**
```
Success criteria should be measurable. "Feature is successful" is too vague.

Instead, consider metrics like:
- Adoption: "50% of enterprise customers within 6 months"
- Usage: "10+ daily dashboard views per customer"
- Outcomes: "40% faster incident response time"
- Business: "Close 10 blocked deals worth $3M"

What specific metrics would indicate success for this feature?
```

### No Epic Breakdown

**Scenario:** User doesn't identify component epics.

**Action:**
1. Explain features are delivered through epics
2. Help identify major work streams
3. Suggest 3-8 epic areas

**Example:**
```
Features are typically delivered through 3-8 epics. What are the major components or work streams?

For observability, typical epics might be:
1. Metrics collection infrastructure
2. Dashboard and visualization
3. Alerting system
4. Reporting capabilities
5. API development
6. Documentation

What would be the major components for your feature?
```

### Security Validation Failure

**Scenario:** Sensitive data detected in feature content.

**Action:**
1. STOP submission
2. Inform user what type of data was detected
3. Ask for redaction

**Example:**
```
I detected confidential business information (customer names, revenue figures).

If this is a public Jira project, please sanitize:
- Use "Enterprise Customer A" instead of actual customer names
- Use ranges ($1-5M) instead of exact revenue figures
```

### MCP Tool Error

**Scenario:** MCP tool returns an error when creating the feature.

**Action:**
1. Parse error message
2. Provide user-friendly explanation
3. Suggest corrective action

**Common errors:**
- **"Issue type 'Feature' not available"** → Check if project supports Features
- **"Field 'customfield_xyz' does not exist"** → Remove unsupported custom field

## Examples

### Example 1: Complete Feature

**Input:**
```bash
/jira:create feature CNTRLPLANE "Advanced hosted control plane observability"
```

**Interactive prompts collect:**
- Market problem (enterprise customer pain)
- Strategic value (business impact, customer value)
- Success criteria (measurable metrics)
- Epic breakdown (7 major components)
- Timeline (9 months, 3 releases)

**Result:**
- Complete feature with strategic framing
- All CNTRLPLANE conventions applied
- Ready for epic planning

### Example 2: Feature with Component Detection

**Input:**
```bash
/jira:create feature CNTRLPLANE "Multi-cloud cost optimization for ROSA and ARO HCP"
```

**Auto-detected:**
- Component: HyperShift (affects both ROSA and ARO)
- Target version: openshift-4.21

**Result:**
- Feature with appropriate component
- Multi-platform scope

## Best Practices Summary

1. **Strategic framing:** Always articulate market problem and business value
2. **Measurable success:** Define specific metrics for adoption, usage, outcomes, business
3. **Multi-epic scope:** Feature should contain 3-8 epics
4. **Customer-focused:** Describe value from customer perspective
5. **Business case:** Clear ROI or strategic justification
6. **Realistic timeline:** 1-3 releases (6-12 months typical)
7. **Risk awareness:** Identify and mitigate known risks

## Anti-Patterns to Avoid

❌ **Feature is actually an epic**
```
"Multi-cluster dashboard" (single capability, 1 epic)
```
✅ Too small, create as Epic

❌ **No strategic context**
```
"Build monitoring system"
```
✅ Must explain market problem and business value

❌ **Vague success criteria**
```
"Feature is successful when customers like it"
```
✅ Use measurable metrics: "50% adoption, 8.5 CSAT score, $2M revenue"

❌ **Technical implementation as feature**
```
"Migrate to Kubernetes operator pattern"
```
✅ Technical work should be epic/task. Features describe customer-facing value.

## Workflow Summary

1. ✅ Parse command arguments (project, summary)
2. 🔍 Auto-detect component from summary keywords
3. ⚙️ Apply project-specific defaults
4. 💬 Interactively collect market problem
5. 💬 Interactively collect strategic value
6. 💬 Interactively collect success criteria
7. 💬 Collect epic breakdown and timeline
8. 🔒 Scan for sensitive data
9. ✅ Validate feature quality and scope
10. 📝 Format description with Jira markup
11. ✅ Create feature via MCP tool
12. 📤 Return issue key and URL

## See Also

- `/jira:create` - Main command that invokes this skill
- `create-epic` skill - For epics within features
- `cntrlplane` skill - CNTRLPLANE specific conventions
- Product management and roadmap planning resources
