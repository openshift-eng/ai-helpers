---
name: Markdown for Jira Reference
description: Markdown formatting guide for Jira issue descriptions via MCP tools
---

# Markdown for Jira Reference

When using MCP tools (e.g., `jira_create_issue`, `jira_update_issue`, `jira_add_comment`) to create or update Jira issues, write descriptions and comments in **Markdown format**. The MCP tool automatically converts Markdown to Jira wiki markup before sending it to Jira.

This means you do **not** need to use Jira wiki markup syntax directly. Write standard Markdown and the conversion is handled for you.

## Syntax Mapping

The table below shows the Markdown syntax to use and how it renders in Jira after conversion.

| Element | Markdown Syntax | Jira Rendering |
|---|---|---|
| Heading 1 | `# Heading` | h1. Heading |
| Heading 2 | `## Heading` | h2. Heading |
| Heading 3 | `### Heading` | h3. Heading |
| Bold | `**bold text**` | **bold text** |
| Italic | `*italic text*` | _italic text_ |
| Bold + Italic | `***bold italic***` | Bold italic text |
| Bullet list | `- item` | Bulleted list item |
| Nested bullet | `- nested item` (indented two spaces) | Nested bulleted item |
| Numbered list | `1. item` | Numbered list item |
| Inline code | `` `code` `` | Monospace text |
| Code block | ` ```lang...``` ` | {code:lang}...{code} |
| Link | `[text](url)` | Clickable link |
| Blockquote | `> quoted text` | Blockquote |
| Horizontal rule | `---` | Horizontal separator |
| Table | Standard Markdown table | Jira table |

## Detailed Examples

### Headings

```markdown
# Heading 1
## Heading 2
### Heading 3
#### Heading 4
```

### Text Formatting

```markdown
**bold text**
*italic text*
***bold and italic***
`inline code`
~~strikethrough~~
```

### Bullet Lists

```markdown
- First item
- Second item
  - Nested item
  - Another nested item
- Third item
```

### Numbered Lists

```markdown
1. First step
2. Second step
3. Third step
```

### Code Blocks

Use triple backticks with an optional language identifier:

````markdown
```go
func main() {
    fmt.Println("Hello, World!")
}
```
````

### Links

```markdown
[OpenShift Documentation](https://docs.openshift.com)
```

### Tables

```markdown
| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |
```

### Blockquotes

```markdown
> This is a blockquote.
> It can span multiple lines.
```

## Auto-Linking

Jira issue keys (e.g., `PROJ-123`, `OCPBUGS-456`) are automatically linked by Jira regardless of formatting. Simply type the issue key in plain text and Jira will render it as a clickable link to that issue.

## Example Templates

### User Story

```markdown
As a `cluster admin`, I want to `configure autoscaling`, so that `I can handle traffic spikes`.

## Acceptance Criteria

- Test that node pools scale up when CPU exceeds 80%
- Test that node pools scale down when CPU drops below 30%
- Test that scaling respects configured min/max node limits

## Additional Context

This feature integrates with the existing monitoring infrastructure introduced in PROJ-100.

### Dependencies

- PROJ-99 - Monitoring infrastructure
- Coordination with Platform team for API access

### Out of Scope

- Custom metrics-based scaling (future story)
```

### Bug Report

````markdown
## Description

The `API server` returns a `500 error` when creating namespaces with `special characters` in the name.

## Steps to Reproduce

1. Create a namespace with special characters: `kubectl create namespace test-@-ns`
2. Observe the API server response
3. Check the API server logs for details

## Actual Result

`HTTP 500 Internal Server Error` returned. API logs show `panic: regex compilation failed`.

## Expected Result

Namespace should be created successfully, or a `400 Bad Request` should be returned with a clear validation error message.

## Additional Info

- OpenShift Version: 4.21
- Affected Component: `Kubernetes API Server`
- First reported in: Version 4.20

```
Error from server (InternalError): error when creating "manifest.yaml": Internal error occurred: failed to validate object against schema: regex compilation failed
```
````

### Epic Description

```markdown
## Use Case / Context

Implement comprehensive monitoring and observability for `GCP-hosted control planes` across multiple `GKE clusters`, enabling operators to detect and respond to issues proactively.

## Current State

- Limited visibility into control plane metrics
- Manual troubleshooting process
- Slow mean time to resolution (MTTR)

## Desired State

- Real-time metrics collection from control plane pods
- Centralized metrics aggregation and storage
- Pre-built dashboards for cluster health monitoring
- Alerting framework for critical metrics

## Scope

**This Epic covers:**
- Metrics collection from control plane pods
- Central metrics aggregation and storage
- Dashboards for monitoring cluster health
- Alerting framework for critical metrics
- Log aggregation and analysis

**Out of Scope:**
- Custom application metrics (separate Epic)
- Alert routing to external systems (future)

## Acceptance Criteria

- Test that metrics are collected from all control plane pods
- Test that metrics are available within 30 seconds of generation
- Test that dashboards accurately reflect cluster state
- Test that alerts fire within 2 minutes of anomaly detection
```

### Task Description

````markdown
## Objective

Add Prometheus scrape annotations to all control plane pod deployments in the `hypershift-operator` namespace.

## Details

Update the following deployments to include Prometheus annotations:
- `kube-apiserver`
- `kube-controller-manager`
- `etcd`

### Required Annotations

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8443"
  prometheus.io/scheme: "https"
```

## Definition of Done

- All listed deployments have correct Prometheus annotations
- Metrics endpoint is reachable from the monitoring namespace
- Unit tests validate annotation presence
- Documentation updated in PROJ-200
````
