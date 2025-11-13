---
name: Create Jira Feature Request
description: Implementation guide for creating Feature Requests in the RFE project
---

# Create Jira Feature Request

This skill provides implementation guidance for creating Feature Requests in the RFE Jira project, which captures customer-driven enhancement requests.

## When to Use This Skill

This skill is automatically invoked by the `/jira:create feature-request RFE` command to guide the feature request creation process.

## Prerequisites

- MCP Jira server configured and accessible
- User has permissions to create issues in the RFE project
- Understanding of the customer need and business justification
- Knowledge of affected components/teams

## What is a Feature Request?

A Feature Request (RFE) is:
- A **customer-driven request** for new functionality or enhancement
- Submitted to the **RFE project** in Jira
- Captures **business requirements** and customer justification
- Links specific **components and teams** that need to implement the request
- Focuses on **what** is needed rather than **how** to implement it

### Feature Request vs Feature vs Story

| Type | Purpose | Project | Example |
|------|---------|---------|---------|
| **Feature Request (RFE)** | Customer request for capability | RFE | "Support for Foo in ProductA managed control planes" |
| Feature | Strategic product objective | CNTRLPLANE, etc. | "Advanced hosted control plane security" |
| Story | Single user-facing functionality | Any | "User can upload custom SSL certificate via console" |

### Feature Request Characteristics

Feature Requests should:
- Clearly state the **customer need** or problem
- Provide **business justification** for the request
- Identify **affected components** and teams
- Be **customer-focused** (what they need, not how to build it)
- Include enough detail for engineering teams to **understand and estimate**

## Feature Request Description Best Practices

### Title

The title should be:
- **Clear and concise** (50-80 characters)
- **Customer-focused** (describes the capability needed)
- **Specific** (not vague or overly broad)

**Good examples:**
```
Support Foo for ProductA managed control planes
Enable pod autoscaling based on custom metrics
Multi-cluster backup and restore for ProductB
```

**Bad examples:**
```
Better security (too vague)
SSL stuff (not specific)
Make autoscaling work better (not clear)
```

### Nature and Description

Clearly describe:
- **What** is being requested (the capability or enhancement)
- **Current limitations** or gaps (what doesn't work today)
- **Desired behavior** (what should happen)
- **Use case** (how customers will use this)

**Good example:**
```
h2. Nature and Description of Request

Customers need the ability to use Foo for ProductA managed control plane endpoints, rather than relying on vendor-provided defaults.

h3. Current Limitation
Today, ProductA clusters use vendor-managed configuration for the API server endpoint. Customers cannot provide their own configuration, which creates issues for:
- Corporate security policies requiring organization-specific settings
- Integration with existing enterprise infrastructure
- Compliance requirements (SOC2, ISO 27001)

h3. Desired Behavior
Customers should be able to:
- Upload their own configuration during cluster creation
- Rotate configuration after cluster creation
- Validate configuration before cluster becomes active
- Receive alerts when configuration changes are needed

h3. Use Case
Enterprise customers with strict security policies need all infrastructure to use internally-managed configuration. This blocks ProductA adoption in regulated industries (finance, healthcare, government) where configuration management is a compliance requirement.
```

**Bad example:**
```
We need better SSL support.
```

### Business Requirements

Explain **why** the customer needs this:
- **Business impact** (what happens without this)
- **Customer segment** affected (who needs this)
- **Regulatory/compliance** drivers (if applicable)
- **Competitive** context (if relevant)
- **Priority** indicators (blocking deals, customer escalations)

**Good example:**
```
h2. Business Requirements

h3. Customer Impact
- **Primary segment**: Enterprise customers in regulated industries (finance, healthcare, government)
- **Affected customers**: 10+ customers have requested this capability
- **Deal blockers**: Multiple active deals blocked by this limitation
- **Escalations**: Several P1 customer escalations due to compliance failures

h3. Regulatory Requirements
- SOC2 Type II compliance requires organization-specific configuration
- ISO 27001 mandates lifecycle management
- Financial services regulations (PCI-DSS) require integration with enterprise infrastructure
- Government contracts require validated configuration chains

h3. Business Justification
Without this capability:
- Cannot close enterprise deals in regulated industries
- Risk losing existing customers to competitors during renewals
- Increasing support burden from compliance audit failures
- Limiting market expansion into high-value segments

h3. Competitive Context
Major competitors (CompetitorA, CompetitorB, CompetitorC) all support this capability for managed Kubernetes control planes. This is a gap that affects product competitive positioning.
```

**Bad example:**
```
Customers need this for security.
```

### Affected Packages and Components

Identify:
- **Teams** that need to implement this (use team names like "HyperShift", "ROSA SRE")
- **Operators** or controllers affected (e.g., "cluster-ingress-operator")
- **Components** in Jira (this will be set as the Component field)
- **Related services** (APIs, CLIs, consoles)

**Good example:**
```
h2. Affected Packages and Components

h3. Teams
- **HyperShift Team**: Control plane infrastructure, configuration management
- **ROSA SRE Team**: Operational validation, configuration rotation
- **OCM Team**: Console and API for configuration upload
- **Networking Team**: Networking and configuration distribution

h3. Technical Components
- **cluster-ingress-operator**: Configuration provisioning and installation
- **hypershift-operator**: Control plane configuration
- **openshift-console**: UI for configuration upload and management
- **rosa CLI**: CLI support for configuration operations

h3. Jira Component
Based on the primary team and technical area, this should be filed under:
**Component**: HyperShift / ProductA

h3. Related Services
- Product API (configuration upload endpoint)
- Configuration management service (validation, storage)
- Control plane API server (configuration installation)
```

**Note:** The "Jira Component" will be used to set the `components` field when creating the issue.

## Interactive Feature Request Collection Workflow

When creating a feature request, guide the user through these specific questions:

### 1. Proposed Title

**Prompt:** "What is the proposed title for this feature request? Make it clear, specific, and customer-focused (50-80 characters)."

**Validation:**
- Not too vague ("Better performance")
- Not too technical ("Implement TLS 1.3 in ingress controller")
- Customer-facing capability

**Example response:**
```
Support Foo for ProductA managed control planes
```

### 2. Nature and Description

**Prompt:** "What is the nature and description of the request? Describe:
- What capability is being requested
- Current limitations
- Desired behavior
- Use case"

**Probing questions if needed:**
- What doesn't work today that should?
- What would you like to be able to do?
- How would customers use this capability?

**Example response:**
```
Customers need to use Foo for ProductA API endpoints instead of vendor-provided defaults.

Current limitation: ProductA only supports vendor-managed configuration, blocking customers with corporate requirements.

Desired behavior: Customers can upload, validate, and rotate custom configuration for the control plane API.

Use case: Enterprise customers in regulated industries (finance, healthcare) need organization-specific configuration for compliance.
```

### 3. Business Requirements

**Prompt:** "Why does the customer need this? List the business requirements, including:
- Customer impact and affected segment
- Regulatory/compliance drivers
- Business justification
- What happens without this capability"

**Helpful questions:**
- Who is asking for this? (customer segment)
- Why is this blocking them? (compliance, policy, competitive)
- What is the business impact? (deals, escalations, churn risk)
- Are there regulatory requirements?

**Example response:**
```
Customer impact:
- 10+ enterprise customers have requested this
- Multiple active deals blocked
- Several P1 escalations from compliance failures

Regulatory requirements:
- SOC2, ISO 27001, PCI-DSS require organization-specific configuration
- Government contracts require validated configuration chains

Business justification:
- Cannot close deals in regulated industries (finance, healthcare, government)
- Competitive gap (CompetitorA, CompetitorB, CompetitorC all support this capability)
- Risk of customer churn during renewals
```

### 4. Affected Packages and Components

**Prompt:** "What packages, components, teams, or operators are affected? This helps route the request to the right teams.

Provide details like:
- Team names (e.g., 'HyperShift', 'Networking', 'OCM')
- Operators (e.g., 'cluster-ingress-operator')
- Technical areas (e.g., 'control plane', 'API server')
- Services (e.g., 'OCM console', 'rosa CLI')"

**Follow-up:** After collecting this information, help the user determine the appropriate **Jira Component** value.

**Component mapping guidance:**
- If **HyperShift**, **ProductA**, or **ProductB** mentioned → Component: "HyperShift"
- If **Networking**, **Ingress** mentioned → Component: "Networking"
- If **OCM**, **Console** mentioned → Component: "OCM"
- If **Multi-cluster**, **Observability** mentioned → Component: "Observability"
- If unclear, ask: "Based on the teams and technical areas mentioned, which component should this be filed under?"

**Example response:**
```
Teams affected:
- HyperShift Team (primary - control plane configuration management)
- ROSA SRE Team (configuration rotation, operations)
- OCM Team (console UI for configuration upload)
- Networking Team (networking configuration distribution)

Operators/components:
- cluster-ingress-operator
- hypershift-operator
- openshift-console

Suggested Jira Component: HyperShift
```

## Field Validation

Before submitting the feature request, validate:

### Required Fields
- ✅ Title is clear, specific, and customer-focused
- ✅ Nature and description explains what is requested
- ✅ Business requirements justify why this is needed
- ✅ Affected components and teams are identified
- ✅ Jira Component is set appropriately
- ✅ Project is set to "RFE"
- ✅ Issue type is "Feature Request"

### Content Quality
- ✅ Describes customer need (not implementation details)
- ✅ Business justification is clear
- ✅ Enough detail for engineering teams to understand
- ✅ No vague statements ("better performance", "more secure")
- ✅ Use case is explained

### Security
- ✅ No credentials, API keys, or secrets in any field
- ✅ No confidential customer information (use anonymized references if needed)

## MCP Tool Parameters

### Basic Feature Request Creation

```python
mcp__atlassian__jira_create_issue(
    project_key="RFE",
    summary="<title of feature request>",
    issue_type="Feature Request",
    description="""
<Brief overview of the request>

h2. Nature and Description of Request

<What is being requested - capability, current limitations, desired behavior, use case>

h2. Business Requirements

h3. Customer Impact
* <Customer segment affected>
* <Number of customers requesting>
* <Deals blocked or escalations>

h3. Regulatory/Compliance Requirements (if applicable)
* <Compliance driver 1>
* <Compliance driver 2>

h3. Business Justification
<Why this is important, what happens without it>

h3. Competitive Context (if applicable)
<How competitors handle this, gaps>

h2. Affected Packages and Components

h3. Teams
* <Team 1>: <Responsibility>
* <Team 2>: <Responsibility>

h3. Technical Components
* <Operator/component 1>
* <Operator/component 2>

h3. Related Services
* <Service 1>
* <Service 2>
    """,
    components="<component name>",  # Based on affected teams/areas
    additional_fields={
        # NOTE: Custom field IDs need to be discovered for RFE project
        # Placeholder examples below - replace with actual field IDs
        # "customfield_12345": "<customer name>",  # If RFE has customer field
        # "customfield_67890": "<priority level>",  # If RFE has priority field
        "labels": ["ai-generated-jira"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

### Example: Foo Feature Request

```python
mcp__atlassian__jira_create_issue(
    project_key="RFE",
    summary="Support Foo for ProductA managed control planes",
    issue_type="Feature Request",
    description="""
Enable customers to use Foo for ProductA managed control plane API server endpoints, replacing the current vendor-managed approach.

h2. Nature and Description of Request

Customers need the ability to use Foo for ProductA API endpoints rather than relying on vendor-provided defaults.

h3. Current Limitation
ProductA clusters currently use vendor-managed configuration for the API server endpoint. Customers cannot provide their own configuration, which creates issues for:
* Corporate security policies requiring organization-specific settings
* Integration with existing enterprise infrastructure
* Compliance requirements (SOC2, ISO 27001, PCI-DSS)

h3. Desired Behavior
Customers should be able to:
* Upload their own configuration during cluster creation
* Rotate custom configuration after cluster creation without cluster downtime
* Validate configuration before cluster becomes active
* Receive proactive alerts when configuration updates are needed (30 days, 7 days)
* View configuration details in product console

h3. Use Case
Enterprise customers with strict security policies need all infrastructure components to use internally-managed configuration. This capability is required for ProductA adoption in regulated industries (finance, healthcare, government) where configuration management is a compliance requirement and external configuration violates security policies.

h2. Business Requirements

h3. Customer Impact
* **Primary segment**: Enterprise customers in regulated industries (finance, healthcare, government, defense)
* **Affected customers**: 10+ enterprise customers have explicitly requested this capability
* **Deal blockers**: Multiple active enterprise deals are currently blocked by this limitation
* **Escalations**: Several Priority 1 customer escalations due to failed compliance audits

h3. Regulatory/Compliance Requirements
* SOC2 Type II compliance requires use of organization-specific configuration with documented lifecycle management
* ISO 27001 certification mandates configuration lifecycle management and infrastructure integration
* PCI-DSS (Payment Card Industry) requires configuration from approved infrastructure
* Government contracts (FedRAMP, DoD) require validated configuration chains
* Industry-specific regulations (HIPAA, GDPR) require organizational control of configuration

h3. Business Justification
Without this capability:
* Cannot close enterprise deals in regulated industries (blocking market expansion)
* Risk losing existing customers to competitors during renewal periods
* Increasing support burden from compliance audit failures and customer escalations
* Limiting addressable market to non-regulated segments
* Missing revenue opportunity in high-value enterprise segments

h3. Competitive Context
All major competitors support this capability for managed Kubernetes control planes:
* CompetitorA: Supports custom configuration via service manager
* CompetitorB: Allows bring-your-own configuration for API server
* CompetitorC: Supports custom configuration for control plane endpoints

This is a competitive gap affecting ProductA positioning in enterprise sales cycles.

h2. Affected Packages and Components

h3. Teams
* **HyperShift Team**: Primary owner - control plane infrastructure, configuration management, rotation logic
* **ROSA SRE Team**: Operational validation, configuration rotation procedures, monitoring and alerting
* **OCM Team**: Console UI for configuration upload, validation, and lifecycle management
* **Networking Team**: Networking configuration, configuration distribution to load balancers
* **Security Team**: Configuration validation, security review, key management

h3. Technical Components
* **hypershift-operator**: Control plane configuration and installation
* **cluster-ingress-operator**: Configuration provisioning for API server
* **openshift-console**: UI components for configuration upload and management
* **rosa CLI**: CLI commands for configuration operations (upload, rotate, view)
* **control-plane-operator**: API server configuration mounting

h3. Related Services
* OCM API: New endpoints for configuration upload, validation, and management
* Configuration storage service: Secure storage for sensitive data (encryption at rest)
* Control plane API server: Configuration installation and serving
* Monitoring and alerting: Configuration monitoring and proactive alerts

h2. Jira Component
**Component**: HyperShift

(Primary team is HyperShift, primary technical area is control plane infrastructure)
    """,
    components="HyperShift",
    additional_fields={
        # TODO: Discover actual custom field IDs for RFE project
        # These are placeholders - need to query Jira API to get correct field IDs
        # Common RFE fields might include:
        #   - Customer name (customfield_XXXXX)
        #   - Request priority (customfield_XXXXX)
        #   - Target release (customfield_XXXXX)
        "labels": ["ai-generated-jira", "security", "compliance", "product-a"],
        "security": {"name": "Red Hat Employee"}
    }
)
```

## Jira Description Formatting

Use Jira's native formatting (Wiki markup):

### Feature Request Template Format

```
<Brief overview>

h2. Nature and Description of Request

<What is being requested>

h3. Current Limitation
<What doesn't work today>

h3. Desired Behavior
<What should work>

h3. Use Case
<How customers will use this>

h2. Business Requirements

h3. Customer Impact
* <Affected segment>
* <Number of requests>
* <Deal impacts>

h3. Regulatory/Compliance Requirements
* <Requirement 1>
* <Requirement 2>

h3. Business Justification
<Why this matters, impact of not having it>

h3. Competitive Context (optional)
<Competitor capabilities, market gaps>

h2. Affected Packages and Components

h3. Teams
* <Team>: <Responsibility>

h3. Technical Components
* <Component/operator>

h3. Related Services
* <Service>

h2. Jira Component
**Component**: <component name>
```

## Error Handling

### Missing Business Justification

**Scenario:** User provides feature request without clear business justification.

**Action:**
1. Explain importance of business requirements
2. Ask probing questions about customer impact
3. Help articulate business case

**Example:**
```
For a Feature Request to be prioritized, we need to understand the business impact.

Can you provide:
1. Who is requesting this? (customer segment, specific customers)
2. Why is it blocking them? (compliance, policy, competitive)
3. What is the business impact? (deals blocked, escalations, churn risk)
4. Are there regulatory requirements driving this?

This helps product management and engineering teams understand priority and urgency.
```

### Vague Description

**Scenario:** Description lacks specifics about what is needed.

**Action:**
1. Identify vague areas
2. Ask clarifying questions
3. Help user be more specific

**Example:**
```
The description "better security" is too vague. Let's be more specific:

1. What security capability is needed? (authentication, encryption, access control)
2. What doesn't work today? (specific limitation or gap)
3. What should work? (desired behavior)
4. How would customers use this? (use case)

For example: "Support custom SSL certificates" is specific and actionable.
```

### Missing Component Information

**Scenario:** User doesn't know which teams or components are affected.

**Action:**
1. Ask about technical area or keywords
2. Provide component mapping guidance
3. Suggest likely component based on description

**Example:**
```
To route this Feature Request correctly, we need to identify the component.

Based on your description mentioning "ProductA control plane" and "configuration", this likely affects:
- **HyperShift Team** (control plane infrastructure)
- **Networking Team** (networking and configuration)

I recommend setting the Jira Component to: **HyperShift**

Does this seem correct based on your understanding?
```

### Security Validation Failure

**Scenario:** Sensitive data detected in feature request content.

**Action:**
1. STOP submission
2. Inform user what type of data was detected
3. Ask for sanitization

**Example:**
```
I detected potentially confidential information (customer names, specific revenue figures).

If this is a public Jira project, please anonymize:
- Use "Enterprise Customer A" instead of actual customer names
- Use ranges ($1-5M) instead of exact revenue figures
- Remove any confidential business information

Would you like to revise the content?
```

### MCP Tool Error

**Scenario:** MCP tool returns an error when creating the feature request.

**Action:**
1. Parse error message
2. Provide user-friendly explanation
3. Suggest corrective action

**Common errors:**
- **"Issue type 'Feature Request' not available"** → Verify RFE project configuration, may need to use "Story" or "Enhancement" instead
- **"Component 'X' does not exist"** → List valid components for RFE project
- **"Field 'customfield_xyz' does not exist"** → Remove custom field, update placeholder in skill

## Examples

### Example 1: Enterprise Customer Request

**Input:**
```bash
/jira:create feature-request RFE "Support Foo for ProductA"
```

**Interactive prompts collect:**
- Title: "Support Foo for ProductA managed control planes"
- Nature: Current limitation with vendor defaults, need for custom configuration, use case for regulated industries
- Business requirements: 10+ customers, multiple blocked deals, compliance drivers
- Components: HyperShift team, cluster-ingress-operator, hypershift-operator

**Result:**
- Complete Feature Request with business justification
- Component: HyperShift
- Routed to appropriate teams for review

### Example 2: Compliance-Driven Request

**Input:**
```bash
/jira:create feature-request RFE "Multi-cluster backup and restore for ProductB"
```

**Auto-detected:**
- Component: HyperShift (ProductB keyword)
- Compliance: GDPR data residency, disaster recovery requirements

**Result:**
- Feature Request with regulatory justification
- Clear business impact (compliance blocking deals)

## Best Practices Summary

1. **Customer-focused:** Describe what customers need, not how to implement it
2. **Business justification:** Always include customer impact, deals, escalations, compliance drivers
3. **Specific and actionable:** Avoid vague descriptions like "better performance" or "more secure"
4. **Component routing:** Identify affected teams and set appropriate Jira component
5. **Regulatory context:** Include compliance requirements if applicable (SOC2, ISO, PCI, HIPAA, etc.)
6. **Competitive awareness:** Note if competitors have this capability
7. **No implementation details:** Focus on "what" is needed, not "how" to build it

## Anti-Patterns to Avoid

❌ **Vague title**
```
"Better security"
```
✅ Use specific capability: "Support Foo for ProductA managed control planes"

❌ **No business justification**
```
"Customers want this"
```
✅ Provide specifics: "10+ customers requested, multiple blocked deals, SOC2 compliance requirement"

❌ **Technical implementation details**
```
"Implement TLS 1.3 in ingress-operator using new controller"
```
✅ Focus on customer need: "Support Foo with modern security standards"

❌ **No component information**
```
"Someone should look at this"
```
✅ Identify teams: "HyperShift team (control plane), Networking team (ingress)"

## Workflow Summary

1. ✅ Parse command arguments (project=RFE, summary)
2. 💬 Interactively collect: Proposed title
3. 💬 Interactively collect: Nature and description of request
4. 💬 Interactively collect: Business requirements (why customer needs this)
5. 💬 Interactively collect: Affected packages and components
6. 🔍 Determine appropriate Jira Component from team/operator information
7. 🔒 Scan for sensitive data (credentials, confidential customer info)
8. ✅ Validate feature request quality and completeness
9. 📝 Format description with Jira Wiki markup
10. ✅ Create Feature Request via MCP tool
11. 📤 Return issue key and URL

## See Also

- `/jira:create` - Main command that invokes this skill
- `create-feature` skill - For strategic product features
- `create-epic` skill - For implementation epics
- RFE project documentation (if available)

## Notes

### Custom Field Discovery

This skill uses placeholder comments for custom fields because the actual field IDs for the RFE project need to be discovered. To find the correct field IDs:

1. **Query Jira API for RFE project metadata:**
   ```bash
   curl -X GET "https://issues.redhat.com/rest/api/2/issue/createmeta?projectKeys=RFE&expand=projects.issuetypes.fields"
   ```

2. **Look for custom fields** like:
   - Customer name
   - Request priority
   - Target release/version
   - Business impact

3. **Update `additional_fields` dictionary** with actual field IDs

**TODO:** Once field IDs are discovered, update the MCP tool examples with real field mappings.
