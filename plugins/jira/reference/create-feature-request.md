# Feature Request

Type-specific guidance for creating Feature Requests in the RFE project.

## What is a Feature Request?

A customer-driven request for new functionality, submitted to the **RFE** project. Captures business requirements and customer justification, links affected components and teams.

| Type | Purpose | Project |
|------|---------|---------|
| **Feature Request (RFE)** | Customer request for capability | RFE |
| Feature | Strategic product objective | CNTRLPLANE, etc. |
| Story | Single user-facing functionality | Any |

## MCP Creation Details

- `projectKey`: `"RFE"`
- `issueTypeName`: `"Feature Request"`
- Use `getJiraIssueTypeMetaWithFields` to discover custom field IDs for the RFE project

## Title Best Practices

Clear, concise (50-80 characters), customer-focused, specific:

- Good: "Support custom SSL certificates for ROSA HCP managed control planes"
- Bad: "Better security" (too vague)

## Interactive 4-Question Workflow

### 1. Proposed Title

**Prompt:** "What is the proposed title? Make it clear, specific, and customer-focused (50-80 characters)."

### 2. Nature and Description

**Prompt:** "Describe:
- What capability is being requested
- Current limitations
- Desired behavior
- Use case"

### 3. Business Requirements

**Prompt:** "Why does the customer need this?
- Customer impact and affected segment
- Regulatory/compliance drivers
- Business justification
- What happens without this capability"

### 4. Affected Packages and Components

**Prompt:** "What teams, operators, or components are affected?"

**Component mapping guidance:**
- HyperShift, ROSA, ARO mentioned → Component: "HyperShift"
- Networking, Ingress mentioned → Component: "Networking"
- OCM, Console mentioned → Component: "OCM"
- Multi-cluster, Observability mentioned → Component: "Observability"
- If unclear, ask user

## Description Template

```markdown
<Brief overview>

## Nature and Description of Request

<What is being requested>

### Current Limitation
<What doesn't work today>

### Desired Behavior
<What should work>

### Use Case
<How customers will use this>

## Business Requirements

### Customer Impact
- <Affected segment>
- <Number of requests>
- <Deal impacts>

### Regulatory/Compliance Requirements
- <Requirement 1>

### Business Justification
<Why this matters, impact of not having it>

### Competitive Context (optional)
<Competitor capabilities, market gaps>

## Affected Packages and Components

### Teams
- <Team>: <Responsibility>

### Technical Components
- <Component/operator>

### Jira Component
**Component**: <component name>
```

For formatting reference, see [Markdown for Jira](markdown-for-jira.md).

## Anti-Patterns

- Vague title ("Better security") → use specific capability
- No business justification ("Customers want this") → provide specifics: customer count, blocked deals, compliance requirements
- Technical implementation details ("Implement TLS 1.3 in ingress-operator") → focus on customer need
- No component information ("Someone should look at this") → identify affected teams
