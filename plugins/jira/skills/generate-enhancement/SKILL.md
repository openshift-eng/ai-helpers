---
name: Generate Enhancement from Jira Epic or Feature
description: Generate OpenShift enhancement proposal markdown from Jira epic or feature content
---

# Generate Enhancement from Jira Epic or Feature

This skill provides implementation guidance for generating OpenShift enhancement proposal markdown files based on Jira epic or feature issues.

## When to Use This Skill

This skill is automatically invoked by the `/jira:generate-enhancement` command to guide the enhancement generation process from Jira epics or features.

## Prerequisites

- MCP Jira server configured and accessible (or direct API access)
- User has permissions to view the target epic or feature
- Epic or Feature issue exists and has substantive content
- Understanding of OpenShift enhancement process

**Reference Documentation:**
- [OpenShift Enhancement Template](https://github.com/openshift/enhancements/blob/master/guidelines/enhancement_template.md)
- [Enhancement Guidelines](https://github.com/openshift/enhancements/tree/master/guidelines)
- [MCP Tools Reference](../../reference/mcp-tools.md)

## What is an OpenShift Enhancement?

An OpenShift enhancement proposal is:
- A **design document** that describes significant changes to OpenShift
- A **communication tool** for building consensus among stakeholders
- An **architectural record** for future reference
- A **mandatory process** for all enhancements (starting with release 4.3)

### Enhancement Template Structure

The enhancement proposal uses YAML frontmatter metadata and structured markdown sections:

```markdown
---
title: neat-enhancement-idea
authors:
  - "@github-username"
reviewers:
  - "@reviewer1"
  - "@reviewer2"
approvers:
  - "@approver"
api-approvers:
  - None  # Or "@api-approver" if API changes
creation-date: yyyy-mm-dd
last-updated: yyyy-mm-dd
status: provisional
tracking-link:
  - https://issues.redhat.com/browse/FEATURE-123
---

# Enhancement Title

## Summary
## Motivation
### User Stories
### Goals
### Non-Goals
## Proposal
### Workflow Description
### API Extensions
### Topology Considerations
#### Hypershift / Hosted Control Planes
#### Standalone Clusters
#### Single-node Deployments or MicroShift
#### OpenShift Kubernetes Engine
### Implementation Details/Notes/Constraints
### Risks and Mitigations
### Drawbacks
## Alternatives (Not Implemented)
## Open Questions [optional]
## Test Plan
## Graduation Criteria
### Dev Preview -> Tech Preview
### Tech Preview -> GA
### Removing a deprecated feature
## Upgrade / Downgrade Strategy
## Version Skew Strategy
## Operational Aspects of API Extensions
## Support Procedures
## Infrastructure Needed [optional]
```

## Workflow: Generate Enhancement from Epic or Feature

### Step 0: Process Additional Context Links (Optional)

When `--additional-links` is provided, fetch and analyze additional context before generating the enhancement:

```python
def process_additional_links(links):
    """Process additional context links provided by the user."""
    
    context = {
        'github_prs': [],
        'jira_issues': [],
        'enhancements': [],
        'documentation': []
    }
    
    for link in links.split(','):
        link = link.strip()
        
        # GitHub PR
        if 'github.com' in link and '/pull/' in link:
            pr_info = fetch_github_pr(link)
            context['github_prs'].append(pr_info)
        
        # Jira issue
        elif 'issues.redhat.com' in link or 'jira.' in link:
            issue_key = extract_jira_key(link)
            issue_info = fetch_jira_issue(issue_key)
            context['jira_issues'].append(issue_info)
        
        # Enhancement proposal
        elif 'enhancements' in link and link.endswith('.md'):
            enhancement_content = fetch_url_content(link)
            context['enhancements'].append({
                'url': link,
                'content': enhancement_content
            })
        
        # Documentation
        elif 'docs.openshift.com' in link or '.md' in link:
            doc_content = fetch_url_content(link)
            context['documentation'].append({
                'url': link,
                'content': doc_content
            })
    
    return context

def fetch_github_pr(pr_url):
    """Fetch PR details from GitHub."""
    match = re.match(r'https://github.com/([^/]+)/([^/]+)/pull/(\d+)', pr_url)
    org, repo, pr_number = match.groups()
    
    # Fetch via GitHub API or gh CLI
    pr_data = gh_api_get(f'/repos/{org}/{repo}/pulls/{pr_number}')
    
    return {
        'url': pr_url,
        'number': int(pr_number),
        'repo': f'{org}/{repo}',
        'title': pr_data['title'],
        'body': pr_data['body'],
        'files': fetch_pr_files(org, repo, pr_number),
        'state': pr_data['state']
    }

def fetch_jira_issue(issue_key):
    """Fetch Jira issue details."""
    # Use MCP or direct API
    issue = mcp__atlassian__jira_get_issue(issue_key)
    
    return {
        'key': issue_key,
        'type': issue['fields']['issuetype']['name'],
        'summary': issue['fields']['summary'],
        'description': issue['fields']['description'],
        'status': issue['fields']['status']['name']
    }
```

**Use additional context when generating sections:**

- **API Extensions**: Extract API changes from GitHub PRs
- **Implementation Details**: Reference related Jira issues and their solutions
- **Risks and Mitigations**: Learn from issues documented in related bugs
- **Test Plan**: Extract test patterns from related PRs
- **Motivation**: Reference similar enhancements for context
- **User Stories**: Extract patterns from related feature requests

**Example usage:**
```text
Processing additional context links:
  ✓ GitHub PR: openshift/api#1234 (merged) - Add DedicatedHost field
  ✓ Jira Issue: OCPBUGS-5678 - Bug related to host placement
  ✓ Enhancement: cluster-api-integration.md - Related enhancement
  
Using additional context for:
  - API Extensions (from openshift/api#1234)
  - Risks and Mitigations (from OCPBUGS-5678)
  - Related Enhancements (cluster-api-integration.md)
```

### Step 1: Fetch Epic or Feature from Jira

Use direct API calls or MCP tools to retrieve the issue:

```bash
# Direct API (used in OCPSTRAT-1596 example)
curl -u "$USERNAME:$API_TOKEN" \
  "https://redhat.atlassian.net/rest/api/3/issue/<ISSUE-KEY>"
```

**Extract key information:**
- Summary (becomes enhancement title)
- Description (contains problem statement, goals, acceptance criteria)
- Components (determines topology considerations)
- Target version (informs graduation criteria)
- Child issues (epics, stories, tasks - become implementation details)
- Creation date (metadata)
- Issue type (Epic or Feature)

**Validation checks:**
- ✅ Issue type is "Epic" or "Feature"
- ✅ Issue has description content
- ✅ Issue summary is meaningful
- ⚠️  Warn if missing: detailed description, acceptance criteria, child issues

### Step 2: Parse Epic or Feature Description

**For Features created via `/jira:create feature`:**

Features follow this structure:

```text
<Brief overview>

h2. Market Problem
<Problem description>

h2. Proposed Solution
<Solution description>

h2. Strategic Value
h3. Customer Value
* <benefits>

h3. Business Impact
* <impacts>

h2. Success Criteria
h3. Adoption
* <metrics>

h2. Scope
h3. Epics (Planned)
* Epic 1: <name>
* Epic 2: <name>

h3. Out of Scope
* <items>

h2. Timeline
* Target: <release>
* Milestones: <dates>
```

**Parse sections into variables:**
- `overview` - First paragraph
- `market_problem` - Content under "Market Problem"
- `solution` - Content under "Proposed Solution"
- `customer_value` - Items under "Customer Value"
- `success_criteria` - All success criteria sections
- `epics_planned` - Epic list
- `out_of_scope` - Out of scope items
- `timeline` - Timeline information

**For Epics:**

Epics typically have simpler structure (as seen in HIVE-2589, OCPSTRAT-1596):

```text
<Epic summary>

h3. Feature Overview (aka. Goal Summary)
<Brief description>

h3. Goals (aka. expected user outcomes)
<What should be achieved>

h3. Requirements (aka. Acceptance Criteria)
<What must be delivered>

[Deployment considerations table]

h3. Questions to Answer (Optional)
<Open questions>

h3. Background
<Context and motivation>

h3. Documentation Considerations
<Docs needed>

h3. Interoperability Considerations
<Integration points>
```

**Parse epic sections into variables:**
- `overview` - Feature Overview / Goal Summary
- `goals` - Goals section
- `acceptance_criteria` - Requirements / Acceptance Criteria
- `deployment_considerations` - Table of deployment scenarios
- `background` - Background section (use as motivation)
- `questions` - Open questions
- `docs_considerations` - Documentation needs
- `interop_considerations` - Interoperability needs

**For both types, also fetch child issues:**
```bash
# Get child stories/tasks/epics
curl -u "$USERNAME:$API_TOKEN" \
  "https://redhat.atlassian.net/rest/api/3/search" \
  --data-urlencode "jql=parent = <ISSUE-KEY>"
```

### Step 3: Generate Enhancement Metadata

```yaml
---
title: <generated-from-summary>
authors:
  - "@<jira-reporter-github-username>"  # Prompt if unknown
reviewers:
  - TBD  # Prompt for reviewers
approvers:
  - TBD  # Prompt for approver (typically team lead)
api-approvers:
  - None  # Or prompt if API changes detected
creation-date: <feature-creation-date>
last-updated: <current-date>
status: provisional
tracking-link:
  - <jira-feature-url>
see-also:
  - # Related enhancements (optional, auto-populated from --additional-links)
replaces:
  - # If replacing existing enhancement (optional)
superseded-by:
  - # Leave empty
---
```

**Title generation:**
- Convert summary to lowercase
- Replace spaces with hyphens
- Remove special characters
- Example: "Advanced HCP Observability" → "advanced-hcp-observability"

**Detect API changes:**
- Search description for: "API", "CRD", "Custom Resource", "field", "endpoint"
- If detected, prompt: "This feature mentions API changes. Who should review API changes?"
- If additional GitHub PRs are provided and contain API changes, auto-detect from PR files

**Populate see-also from additional links:**
```python
def populate_see_also(additional_context):
    """Extract related enhancements from additional links."""
    
    see_also = []
    
    # Add related enhancement proposals
    for enhancement in additional_context.get('enhancements', []):
        # Extract path relative to enhancements directory
        if 'enhancements/' in enhancement['url']:
            path = enhancement['url'].split('enhancements/')[-1]
            see_also.append(f"/enhancements/{path}")
    
    return see_also
```

**Example with additional links:**
```yaml
see-also:
  - "/enhancements/cluster-api/cluster-api-integration.md"
  - "/enhancements/machine-api/dedicated-instances.md"
```

### Step 4: Map Content to Enhancement Sections

#### Summary
Use the feature overview (first paragraph) as the enhancement summary.

**Example:**
```markdown
## Summary

Deliver unified observability capabilities for ROSA and ARO hosted control planes,
enabling enterprise customers to manage large cluster fleets with centralized
monitoring, alerting, and compliance reporting.
```

#### Motivation
Map from the **Market Problem** section:

```markdown
## Motivation

<Content from "Market Problem" section>

This addresses the critical need for <summarize problem impact>.
```

#### User Stories
Two approaches:

**Approach 1: Extract from feature if present**
Some features include user stories in the description.

**Approach 2: Generate from customer value**
Convert customer value bullet points into user story format:

```markdown
### User Stories

#### Story 1: Fleet-wide Visibility
As a platform administrator managing 50+ ROSA HCP clusters, I want to view
aggregated health metrics across all clusters in a single dashboard, so that
I can quickly identify issues without navigating between separate UIs.

#### Story 2: Faster Incident Response
As an SRE, I want to receive alerts based on cross-cluster conditions, so that
I can detect and respond to incidents 80% faster than with per-cluster monitoring.
```

**Prompt if needed:**
```text
The feature doesn't include explicit user stories. I can:
1. Generate user stories from the customer value section
2. Prompt you to provide user stories

Which would you prefer?
```

#### Goals
Map from **Strategic Value** and **Proposed Solution**:

```markdown
### Goals

* Deliver centralized metrics aggregation across all customer clusters
* Provide unified dashboards for cluster health, performance, and capacity
* Enable fleet-wide alerting with intelligent cross-cluster correlation
* Support compliance and audit reporting across cluster fleet
* <Additional goals from strategic value>
```

#### Non-Goals
Map from **Out of Scope** section:

```markdown
### Non-Goals

* Log aggregation (separate feature planned for 2026)
* AI-powered predictive analytics (follow-on feature)
* Support for standalone OpenShift clusters (not HCP)
* Cost optimization recommendations (different feature)
```

If not present, prompt:
```text
What is explicitly OUT of scope for this enhancement?

This helps prevent scope creep and sets clear boundaries.
```

#### Proposal - Workflow Description
Generate from **Proposed Solution**:

```markdown
### Workflow Description

**Platform Administrator:**
1. Accesses unified observability dashboard
2. Views aggregated metrics across all managed clusters
3. Configures fleet-wide alert rules
4. Generates compliance reports for audit purposes

**SRE:**
1. Receives cross-cluster alert notification
2. Uses dashboard to identify affected clusters
3. Drills down into specific cluster metrics
4. Takes remediation action with API/CLI
```

Prompt if details missing:
```text
Please describe the typical workflow for using this feature:
- What does the user do first?
- What are the key interactions?
- What is the end result?
```

#### Proposal - API Extensions
Prompt for API changes:

```text
Does this feature introduce or modify APIs? (yes/no)

If yes, describe:
- New CRDs or API resources
- New fields in existing resources
- API endpoints
- Validation webhooks
```

**If additional GitHub PRs are provided via `--additional-links`:**

Extract API changes from the PRs:

```python
def extract_api_from_additional_links(context):
    """Extract API definitions from additional GitHub PRs."""
    
    api_changes = []
    
    for pr in context['github_prs']:
        # Look for PRs in openshift/api repo or API-related files
        if pr['repo'] == 'openshift/api' or any('types.go' in f['filename'] for f in pr['files']):
            for file in pr['files']:
                if file['filename'].endswith('types.go'):
                    # Extract Go struct definitions from patch
                    structs = extract_go_structs(file['patch'])
                    api_changes.extend(structs)
    
    return api_changes
```

**Example with additional context:**
````markdown
### API Extensions

Based on implementation in [openshift/api#1234](https://github.com/openshift/api/pull/1234):

#### AWSMachineProviderConfig API

```yaml
apiVersion: machine.openshift.io/v1beta1
kind: AWSMachineProviderConfig
spec:
  placement:
    dedicatedHost:
      id: h-0123456789abcdef0
      resourceGroupArn: arn:aws:ec2:...
    tenancy: host
```

The `placement.dedicatedHost` field was added to support EC2 Dedicated Hosts configuration.
````

**If no API changes:**
```markdown
### API Extensions

This enhancement does not introduce new API extensions.
```

#### Proposal - Topology Considerations
Auto-detect from feature components and prompt:

```python
# Detect from components
hypershift_detected = "HyperShift" in components or "ROSA" in components or "ARO" in components
standalone_detected = "Standalone" in description or not hypershift_detected
```

**For each topology, generate section:**

```markdown
#### Hypershift / Hosted Control Planes

This enhancement is designed specifically for Hypershift hosted control planes
(ROSA HCP and ARO HCP). It provides fleet-level observability by aggregating
metrics from control planes running in the management cluster.

**Considerations:**
* Metrics are collected from hosted control plane namespaces
* Aggregation service runs in the management cluster
* Supports multi-tenant isolation of metrics data
```

**Prompt if unclear:**
```text
Which OpenShift topologies does this enhancement support?

1. Hypershift / Hosted Control Planes (ROSA HCP, ARO HCP)
2. Standalone Clusters
3. Single-node Deployments or MicroShift
4. OpenShift Kubernetes Engine (OKE)

Select all that apply (comma-separated): 1,2
```

#### Proposal - Implementation Details
Map from **Epics (Planned)** section:

```markdown
### Implementation Details/Notes/Constraints

This enhancement will be delivered through the following epics:

1. **Multi-cluster metrics aggregation infrastructure** ([EPIC-1])
   - Build centralized metrics collection service
   - Implement storage backend for aggregated metrics
   - Establish secure communication from clusters to aggregator

2. **Unified observability dashboard and visualization** ([EPIC-2])
   - Develop dashboard UI components
   - Integrate with metrics aggregation API
   - Support customizable views and filters

3. **Fleet-wide alerting and intelligent correlation** ([EPIC-3])
   - Implement alert rule engine for cross-cluster conditions
   - Build notification integration (email, Slack, PagerDuty)
   - Add intelligent deduplication and correlation

<Continue for all epics>

**Technical Constraints:**
* Must support 500+ clusters without performance degradation
* Metrics retention: 30 days
* Query latency: <1s for 95th percentile
```

**Fetch linked epics if available:**
```python
# Get linked epics from feature
epics = mcp__atlassian__jira_search_issues(
    jql=f'parent = {feature_key} AND type = Epic'
)

# Include epic summaries and keys in implementation details
```

#### Risks and Mitigations
Map from **Risks and Mitigation** section in feature (if present), or prompt.

**If additional Jira issues are provided via `--additional-links`:**

Extract risks from related bugs or issues:

```python
def extract_risks_from_additional_links(context):
    """Extract risks from related Jira bugs."""
    
    risks = []
    
    for issue in context['jira_issues']:
        # Look for bugs or issues that highlight potential risks
        if issue['type'] in ['Bug', 'Task'] and issue['status'] != 'Closed':
            risks.append({
                'source': issue['key'],
                'description': issue['summary'],
                'details': issue['description']
            })
    
    return risks
```

**Example with additional context:**
```markdown
### Risks and Mitigations

**Risk 1: Performance degradation with >500 clusters**
* **Impact:** High - Could prevent enterprise adoption
* **Likelihood:** Medium
* **Mitigation:**
  - Performance benchmarking sprint in Epic 1
  - Horizontal scaling architecture from day 1
  - Load testing with 1000+ simulated clusters

**Risk 2: Integration complexity with third-party monitoring tools**
* **Impact:** Medium - Affects customer adoption
* **Likelihood:** Medium
* **Mitigation:**
  - Partner early with Datadog/Splunk on integration design
  - Provide standardized export formats (Prometheus, OpenMetrics)
  - Comprehensive integration documentation

**Risk 3: Host placement failures with incompatible instance types** (from [OCPBUGS-5678])
* **Impact:** Medium - Customer deployments could fail
* **Likelihood:** Low
* **Mitigation:**
  - Pre-validation of instance type compatibility (implemented in openshift/api#1234)
  - Clear error messages when unsupported configuration is detected
  - Documentation of supported instance type combinations
```

**If no additional context is available**, prompt:
```text
What are the main risks for this enhancement?

For each risk, provide:
- Description of the risk
- Potential impact
- Mitigation strategy
```

#### Test Plan
Prompt for test strategy:

```text
What testing is planned for this enhancement?

Consider:
- Unit tests
- Integration tests
- E2E tests
- Performance/scale tests
- Upgrade tests
```

```markdown
## Test Plan

### Unit Tests
* Metrics collection service: 85%+ coverage
* Aggregation logic: 90%+ coverage
* API endpoints: 100% coverage

### Integration Tests
* Multi-cluster metrics collection end-to-end
* Alert rule evaluation and notification delivery
* Dashboard data rendering with live metrics

### E2E Tests
* Deploy observability stack to test cluster
* Simulate 100 managed clusters
* Verify metrics aggregation, alerting, and dashboard functionality
* Test upgrade scenario from previous version

### Performance/Scale Tests
* Baseline: 500 clusters, 10K metrics/second
* Target: <1s query latency (p95), <5% CPU overhead per cluster
```

#### Graduation Criteria
Map from **Success Criteria** and **Timeline**:

```markdown
## Graduation Criteria

### Dev Preview -> Tech Preview

* Feature complete for MVP use cases (Epic 1-2)
* Basic E2E tests passing
* Documentation available
* Successfully tested with 10+ early adopter customers
* Known limitations documented

**Success signals:**
* 5+ customers using in non-production
* No critical bugs in 30 days

### Tech Preview -> GA

* All planned epics complete (Epic 1-7)
* Full E2E and scale testing complete (500+ clusters)
* Performance targets met (<1s query latency p95)
* Customer documentation complete
* Support procedures documented
* 30+ customers using in production

**Success signals:**
* Adoption: 50% of customers with 10+ clusters
* Customer satisfaction: CSAT >8.0
* Stability: <5 P1 bugs in 60 days

### Removing a deprecated feature

Not applicable - this is a new feature.
```

### Step 5: Prompt for Missing Sections

Some sections cannot be derived from the feature and require prompts:

**Drawbacks:**
```text
What are the drawbacks or downsides of this approach?

Consider:
- Added complexity
- Maintenance burden
- Performance impact
- Operational overhead
```

**Alternatives:**
```text
What alternative approaches were considered but not implemented?

For each alternative:
- Brief description
- Why it was rejected
```

**Upgrade/Downgrade Strategy:**
```text
How will upgrades and downgrades be handled?

Consider:
- Data migration requirements
- Backward compatibility
- Rollback procedures
- Version skew during upgrades
```

**Support Procedures:**
```text
What procedures should support teams use to diagnose and resolve issues?

Include:
- Common failure modes
- Diagnostic steps
- Recovery procedures
- Required access/permissions
```

### Step 6: Generate Filename and Write File

**Filename generation:**
```python
def generate_filename(summary: str, component: str = None) -> str:
    # Convert summary to kebab-case
    filename = summary.lower()
    filename = filename.replace(" ", "-")
    filename = re.sub(r'[^a-z0-9-]', '', filename)

    # Add .md extension
    return f"{filename}.md"

# Examples:
# "Advanced HCP Observability" → "advanced-hcp-observability.md"
# "Multi-cluster Metrics" → "multi-cluster-metrics.md"
```

**Directory selection:**
Suggest directory based on component:

| Component | Directory |
|-----------|-----------|
| HyperShift, ROSA, ARO | `enhancements/hypershift/` |
| Networking | `enhancements/network/` |
| Storage | `enhancements/storage/` |
| Authentication | `enhancements/authentication/` |
| Other | `enhancements/` (root) |

Prompt:
```text
Suggested directory: enhancements/hypershift/
Suggested filename: advanced-hcp-observability.md

Accept? (yes/no/edit)
```

**Write file:**
```python
# Create directory if needed
os.makedirs(output_dir, exist_ok=True)

# Write enhancement file
with open(filepath, 'w') as f:
    f.write(enhancement_content)
```

### Step 7: Report Results

```text
Created enhancement proposal:
  File: .work/enhancements/hypershift/advanced-hcp-observability.md
  Tracking: https://issues.redhat.com/browse/CNTRLPLANE-100

Additional context used:
  ✓ 2 GitHub PRs (openshift/api#1234, openshift/installer#5678)
  ✓ 1 Related Bug (OCPBUGS-5678)
  ✓ 1 Related Enhancement (cluster-api-integration.md)

Sections auto-populated from additional context:
  ✓ API Extensions (from openshift/api#1234)
  ✓ Risks and Mitigations (from OCPBUGS-5678)
  ✓ See Also (from cluster-api-integration.md)

Next steps:
1. Review and refine technical details
2. Add reviewers and approvers to metadata
3. Complete any sections marked [TODO]
4. Share with stakeholders for feedback
5. Submit PR to openshift/enhancements repository

Sections requiring attention:
- [ ] Test Plan - Add specific test scenarios
- [ ] Support Procedures - Define diagnostic steps
- [ ] Operational Aspects - Add SLI details
```

### Step 8: Verify and Sync with PRs (Optional)

When `--verify` or `--sync-from-prs` flags are provided, analyze linked PRs to compare or update the enhancement.

#### Fetch Linked PRs

Discover PRs from multiple sources:

```python
def fetch_linked_prs(issue_key, repos=None):
    """Fetch all PRs linked to an epic/feature."""

    if repos is None:
        repos = [
            'openshift/api',
            'openshift/installer',
            'openshift/machine-api-operator',
            'openshift/cluster-api-provider-aws',
            'openshift/hive'
        ]

    all_prs = []

    # 1. From Jira issue links (issuelinks field)
    issue = fetch_issue(issue_key)
    for link in issue.get('fields', {}).get('issuelinks', []):
        if 'github.com' in str(link) and '/pull/' in str(link):
            all_prs.append(extract_pr_info(link))

    # 2. From Jira comments (GitHub bot comments)
    for comment in issue.get('fields', {}).get('comment', {}).get('comments', []):
        pr_links = extract_github_pr_links(comment['body'])
        all_prs.extend(pr_links)

    # 3. From child issues (stories, tasks, sub-epics)
    child_issues = fetch_child_issues(issue_key)
    for child in child_issues:
        child_prs = fetch_linked_prs(child['key'], repos)
        all_prs.extend(child_prs)

    # 4. Search GitHub for PRs mentioning the issue key
    for repo in repos:
        search_query = f'repo:{repo} "{issue_key}" in:body type:pr'
        github_prs = search_github(search_query)
        all_prs.extend(github_prs)

    # Deduplicate by PR URL
    return deduplicate_prs(all_prs)

def extract_pr_info(pr_url):
    """Fetch PR details from GitHub API."""
    # Extract org, repo, pr_number from URL
    # https://github.com/openshift/api/pull/1234
    match = re.match(r'https://github.com/([^/]+)/([^/]+)/pull/(\d+)', pr_url)
    if not match:
        return None

    org, repo, pr_number = match.groups()

    # Fetch PR via GitHub API
    pr_data = github_api_get(f'/repos/{org}/{repo}/pulls/{pr_number}')

    return {
        'url': pr_url,
        'number': int(pr_number),
        'repo': f'{org}/{repo}',
        'title': pr_data['title'],
        'body': pr_data['body'],
        'state': pr_data['state'],
        'merged': pr_data.get('merged', False),
        'files': fetch_pr_files(org, repo, pr_number),
        'commits': fetch_pr_commits(org, repo, pr_number)
    }
```

#### Verification Mode (`--verify`)

Compare enhancement sections against actual PR implementation:

```python
def verify_enhancement(enhancement_path, prs):
    """Generate verification report."""

    enhancement = read_enhancement(enhancement_path)
    report = {
        'matches': [],
        'deviations': [],
        'incomplete': []
    }

    # Verify API Extensions
    api_result = verify_api_extensions(enhancement, prs)
    if api_result['status'] == 'MATCHES':
        report['matches'].append(api_result)
    elif api_result['status'] == 'DEVIATION':
        report['deviations'].append(api_result)
    else:
        report['incomplete'].append(api_result)

    # Verify Implementation Details
    impl_result = verify_implementation_approach(enhancement, prs)
    if impl_result['has_deviations']:
        report['deviations'].append(impl_result)
    else:
        report['matches'].append(impl_result)

    # Verify Topology Support
    topology_result = verify_topology_support(enhancement, prs)
    report['incomplete'].extend(topology_result['missing'])

    # Verify Test Coverage
    test_result = verify_test_plan(enhancement, prs)
    if test_result['has_missing_tests']:
        report['incomplete'].append(test_result)
    else:
        report['matches'].append(test_result)

    return report

def verify_api_extensions(enhancement, prs):
    """Verify API changes match enhancement."""

    # Extract expected APIs from enhancement
    api_section = extract_section(enhancement, "API Extensions")
    expected_apis = parse_api_definitions(api_section)

    # Extract actual APIs from PRs (look in openshift/api repo)
    api_prs = [pr for pr in prs if pr['repo'] == 'openshift/api']
    actual_apis = []

    for pr in api_prs:
        # Look for Go struct definitions in changed files
        for file in pr['files']:
            if file['filename'].endswith('.go'):
                apis = extract_api_structs(file['patch'])
                actual_apis.extend(apis)

    # Compare
    matches = []
    missing = []
    extra = []

    for expected in expected_apis:
        if find_matching_api(expected, actual_apis):
            matches.append(expected)
        else:
            missing.append(expected)

    for actual in actual_apis:
        if not find_matching_api(actual, expected_apis):
            extra.append(actual)

    if missing or extra:
        return {
            'section': 'API Extensions',
            'status': 'DEVIATION',
            'expected': expected_apis,
            'actual': actual_apis,
            'missing': missing,
            'extra': extra,
            'prs': [pr['url'] for pr in api_prs]
        }
    else:
        return {
            'section': 'API Extensions',
            'status': 'MATCHES',
            'prs': [pr['url'] for pr in api_prs]
        }

def verify_test_plan(enhancement, prs):
    """Verify test coverage matches enhancement."""

    test_section = extract_section(enhancement, "Test Plan")
    expected_tests = parse_test_requirements(test_section)

    # Find test files in PRs
    test_files = []
    for pr in prs:
        for file in pr['files']:
            if '_test.go' in file['filename'] or 'test_' in file['filename']:
                test_files.append({
                    'file': file['filename'],
                    'pr': pr['url'],
                    'type': classify_test_type(file['filename'])
                })

    # Check for missing test types
    missing = []
    if 'unit' in expected_tests and not any(t['type'] == 'unit' for t in test_files):
        missing.append('Unit tests')
    if 'integration' in expected_tests and not any(t['type'] == 'integration' for t in test_files):
        missing.append('Integration tests')
    if 'e2e' in expected_tests and not any(t['type'] == 'e2e' for t in test_files):
        missing.append('E2E tests')

    return {
        'section': 'Test Plan',
        'status': 'INCOMPLETE' if missing else 'MATCHES',
        'expected': expected_tests,
        'actual': test_files,
        'missing': missing,
        'has_missing_tests': bool(missing)
    }
```

**Verification Report Format:**

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VERIFICATION REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Enhancement: ec2-dedicated-hosts-on-aws.md
Tracking: OCPSTRAT-1596
PRs analyzed: 12

✅ API Extensions (2 PRs)
  Expected: AWSMachineProviderConfig.placement.dedicatedHost
  Actual: Matches in openshift/api#1234
  Status: MATCHES

⚠️ Topology Support (3 PRs)
  Expected: HCP and Standalone
  Actual: HCP only (openshift/installer#5678)
  Deferred: Standalone support (planned for 4.23)
  Status: DEVIATION

❌ Test Coverage (4 PRs)
  Expected: Unit, Integration, E2E
  Actual: Unit tests only
  Missing: Integration tests, E2E tests
  Status: INCOMPLETE

✅ Implementation Approach (5 PRs)
  Expected: MAPI shim + CAPI conversion
  Actual: CAPI-only in cluster-api-provider-aws#789
  Note: Approach changed based on upstream decision
  Status: DEVIATION (documented in PR)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Matches: 2
⚠️ Deviations: 2 (approach changed, standalone deferred)
❌ Incomplete: 1 (test coverage)

Recommendation: UPDATE ENHANCEMENT
The enhancement should be updated to reflect the CAPI-only approach
and document that standalone support is deferred to 4.23.

Run: /jira:generate-enhancement OCPSTRAT-1596 --sync-from-prs
```

#### Sync Mode (`--sync-from-prs`)

Update enhancement based on actual PR implementation:

```python
def sync_enhancement_from_prs(enhancement_path, prs, interactive=False):
    """Update enhancement with actual implementation."""

    enhancement = read_enhancement(enhancement_path)
    updates = []

    # Analyze PRs for implementation details
    api_changes = extract_api_changes(prs)
    implementation_approach = analyze_implementation_approach(prs)
    test_coverage = analyze_test_coverage(prs)
    topology_support = analyze_topology_support(prs)

    # Update API Extensions section
    if not is_manual_section(enhancement, "API Extensions"):
        new_api_section = generate_api_section_from_prs(api_changes)
        updates.append({
            'section': 'API Extensions',
            'old': extract_section(enhancement, 'API Extensions'),
            'new': new_api_section
        })

    # Update Implementation Details
    if not is_manual_section(enhancement, "Implementation Details"):
        new_impl_section = generate_implementation_section(implementation_approach)
        updates.append({
            'section': 'Implementation Details',
            'old': extract_section(enhancement, 'Implementation Details'),
            'new': new_impl_section
        })

    # Update Test Plan
    if not is_manual_section(enhancement, "Test Plan"):
        new_test_section = generate_test_section_from_prs(test_coverage)
        updates.append({
            'section': 'Test Plan',
            'old': extract_section(enhancement, 'Test Plan'),
            'new': new_test_section
        })

    # Update Topology Considerations
    if not is_manual_section(enhancement, "Topology Considerations"):
        new_topology_section = generate_topology_section(topology_support)
        updates.append({
            'section': 'Topology Considerations',
            'old': extract_section(enhancement, 'Topology Considerations'),
            'new': new_topology_section
        })

    # Add Implementation Notes section for deviations
    deviations = find_deviations(enhancement, prs)
    if deviations and not is_manual_section(enhancement, "Implementation Notes"):
        impl_notes = generate_implementation_notes(deviations)
        updates.append({
            'section': 'Implementation Notes (NEW)',
            'old': None,
            'new': impl_notes
        })

    # Apply updates (with interactive prompts if requested)
    for update in updates:
        if interactive:
            print(f"\n{'='*60}")
            print(f"Section: {update['section']}")
            print(f"{'='*60}")
            print(f"\n--- OLD ---\n{update['old'][:500]}...")
            print(f"\n--- NEW ---\n{update['new'][:500]}...")

            response = input("\nApply this change? (y/n/diff): ")
            if response == 'diff':
                show_unified_diff(update['old'], update['new'])
                response = input("Apply? (y/n): ")

            if response != 'y':
                continue

        enhancement = replace_section(enhancement, update['section'], update['new'])

    # Update metadata
    enhancement = update_frontmatter(enhancement, {
        'last-updated': datetime.now().strftime('%Y-%m-%d'),
        'last-synced': datetime.now().strftime('%Y-%m-%d'),
        'prs-analyzed': len(prs)
    })

    # Write updated enhancement
    write_enhancement(enhancement_path, enhancement)

    return {
        'updated_sections': [u['section'] for u in updates],
        'prs_analyzed': len(prs)
    }

def is_manual_section(enhancement, section_name):
    """Check if section is marked as manual (via comment or frontmatter)."""
    # Check for <!-- MANUAL --> comment in section content
    section = extract_section(enhancement, section_name)
    if section and '<!-- MANUAL' in section:
        return True

    # Check for sync-exclude in frontmatter
    frontmatter = extract_frontmatter(enhancement)
    if frontmatter:
        sync_exclude = frontmatter.get('sync-exclude', [])
        if section_name in sync_exclude:
            return True

    return False

def extract_frontmatter(enhancement):
    """Extract YAML frontmatter from enhancement."""
    import re
    import yaml

    match = re.match(r'^---\n(.*?)\n---', enhancement, re.DOTALL)
    if match:
        try:
            return yaml.safe_load(match.group(1))
        except:
            return None
    return None

def generate_implementation_notes(deviations):
    """Generate Implementation Notes section."""

    notes = ["## Implementation Notes\n\n"]
    notes.append("This section documents deviations from the original enhancement proposal based on actual implementation.\n\n")

    for deviation in deviations:
        notes.append(f"### {deviation['title']}\n\n")
        notes.append(f"**Original Proposal:** {deviation['expected']}\n\n")
        notes.append(f"**Actual Implementation:** {deviation['actual']}\n\n")
        notes.append(f"**Reason:** {deviation['reason']}\n\n")
        notes.append(f"**PRs:** {', '.join(deviation['prs'])}\n\n")

    return ''.join(notes)
```

**Interactive Sync Example:**

`````text
Syncing enhancement from PRs...

Found 12 PRs:
  openshift/api: 2 PRs
  openshift/installer: 3 PRs
  openshift/cluster-api-provider-aws: 4 PRs
  openshift/machine-api-operator: 2 PRs
  openshift/hive: 1 PR

============================================================
Section: API Extensions
============================================================

--- OLD ---
### API Extensions

Add new fields to the `AWSMachineProviderConfig` spec:

```yaml
placement:
  dedicatedHost:
    hostId: h-0123456789abcdef0
```

--- NEW ---
### API Extensions

#### AWSMachineProviderConfig API

Based on implementation in openshift/api#1234:

```yaml
apiVersion: machine.openshift.io/v1beta1
kind: AWSMachineProviderConfig
spec:
  placement:
    dedicatedHost:
      id: h-0123456789abcdef0
      resourceGroupArn: arn:aws:ec2:...
    tenancy: host
```

Apply this change? (y/n/diff): diff

[Shows unified diff]

Apply? (y/n): y

✓ Updated API Extensions

============================================================
Section: Implementation Notes (NEW)
============================================================

--- OLD ---
[Section does not exist]

--- NEW ---
## Implementation Notes

### MAPI Shim Approach Abandoned

**Original Proposal:** Add shim fields to MAPI, convert to CAPI
**Actual Implementation:** CAPI-only approach
**Reason:** Upstream CAPA added native dedicated host support
**PRs:** openshift/cluster-api-provider-aws#789

Apply this change? (y/n/diff): y

✓ Added Implementation Notes section

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sync complete!
Updated sections: 4
PRs analyzed: 12

Enhancement updated: ec2-dedicated-hosts-on-aws.md
`````

#### Manual Edit Protection

Users can mark sections to prevent sync from overwriting:

**Comment-based:**
```markdown
## Motivation

<!-- MANUAL: Strategic rationale - do not sync -->

Enterprise customers deploying ROSA...
[manually written content]
```

**Frontmatter-based:**
```yaml
---
title: ec2-dedicated-hosts-on-aws
sync-exclude:
  - Motivation
  - User Stories
  - Drawbacks
---
```

The sync process will skip these sections and report:

```text
Preserved manual sections:
  - Motivation (marked <!-- MANUAL -->)
  - User Stories (in sync-exclude)
```

## Content Mapping Reference

### Jira Feature → Enhancement Mapping

| Jira Section | Enhancement Section | Transformation |
|--------------|---------------------|----------------|
| Summary | Title (metadata) | Convert to kebab-case |
| Overview | Summary | Direct copy |
| Market Problem | Motivation | Direct copy + context |
| Customer Value | User Stories | Convert to "As a... I want... So that..." |
| Strategic Value | Goals | Extract objectives |
| Out of Scope | Non-Goals | Direct copy |
| Proposed Solution | Workflow Description | Expand into step-by-step |
| Epics (Planned) | Implementation Details | List epics with details |
| Success Criteria | Graduation Criteria | Map adoption/outcomes to GA criteria |
| Timeline | Graduation Criteria | Map milestones to Dev Preview/Tech Preview/GA |
| Risks | Risks and Mitigations | Direct copy + expand |

### Additional Links → Enhancement Mapping

When `--additional-links` is provided, use additional context to enrich sections:

| Additional Link Type | Enhancement Section | Usage |
|----------------------|---------------------|--------|
| GitHub PR (openshift/api) | API Extensions | Extract CRD definitions, API field changes |
| GitHub PR (with tests) | Test Plan | Extract test patterns, coverage examples |
| Jira Bug | Risks and Mitigations | Identify known issues and mitigations |
| Related Enhancement | Motivation, See Also | Reference related work, avoid duplication |
| Documentation URL | Motivation, Background | Provide context and requirements |
| GitHub PR (implementation) | Implementation Details | Extract actual approach and patterns |

**Example workflow with additional links:**

```python
def enrich_enhancement_with_context(enhancement_sections, additional_context):
    """Enrich enhancement sections with additional context."""
    
    # Enrich API Extensions with PR data
    if additional_context['github_prs']:
        api_prs = [pr for pr in additional_context['github_prs'] 
                   if pr['repo'] == 'openshift/api']
        if api_prs:
            enhancement_sections['api_extensions'] = generate_api_section_from_prs(api_prs)
    
    # Enrich Risks with bug data
    if additional_context['jira_issues']:
        bugs = [issue for issue in additional_context['jira_issues']
                if issue['type'] == 'Bug']
        if bugs:
            enhancement_sections['risks'] = enrich_risks_with_bugs(
                enhancement_sections.get('risks', ''), bugs
            )
    
    # Add related enhancements to See Also
    if additional_context['enhancements']:
        enhancement_sections['see_also'] = generate_see_also(
            additional_context['enhancements']
        )
    
    return enhancement_sections
```

## Enhancement Template Placeholders

For sections that cannot be derived from the feature, use informative placeholders:

```markdown
## Alternatives (Not Implemented)

**TODO:** Describe alternative approaches that were considered but not selected.

For each alternative:
- Brief description of the approach
- Pros and cons compared to the chosen solution
- Why it was rejected

Example alternatives to consider:
- Different architectural patterns
- Alternative technologies or frameworks
- Simpler approaches that were insufficient
```

## Validation Checks

Before writing the file, validate:

**Required sections present:**
- ✅ Summary (from epic/feature overview)
- ✅ Motivation (from background or market problem)
- ✅ Goals (from goals section or strategic value)
- ✅ Proposal (from child issues or solution)
- ⚠️  User Stories (generated or prompted)
- ⚠️  Test Plan (prompted)
- ⚠️  Graduation Criteria (from acceptance criteria or success criteria)

**Metadata complete:**
- ✅ Title generated
- ✅ Creation date from epic/feature
- ✅ Tracking link to epic/feature
- ⚠️  Authors (prompt if needed)
- ⚠️  Reviewers (prompt)
- ⚠️  Approvers (prompt)

**Quality checks:**
- ✅ No [TODO] markers without explanation
- ✅ No Jira wiki markup (h2., *, etc.) in final markdown
- ✅ All internal links valid
- ✅ Consistent terminology

## Jira Wiki Markup Conversion

Epics and features often use Jira wiki markup which must be converted to standard markdown:

| Jira Wiki | Markdown |
|-----------|----------|
| `h2. Heading` | `## Heading` |
| `h3. Heading` | `### Heading` |
| `* bullet` | `* bullet` (same) |
| `# numbered` | `1. numbered` |
| `[PROJ-123]` | `[PROJ-123](https://issues.redhat.com/browse/PROJ-123)` |
| `{{code}}` | `` `code` `` |

```python
def convert_jira_to_markdown(jira_text: str) -> str:
    # Convert headings
    text = re.sub(r'^h2\.\s+(.+)$', r'## \1', jira_text, flags=re.MULTILINE)
    text = re.sub(r'^h3\.\s+(.+)$', r'### \1', text, flags=re.MULTILINE)

    # Convert Jira links
    text = re.sub(r'\[([A-Z]+-\d+)\]',
                  r'[\1](https://issues.redhat.com/browse/\1)', text)

    # Convert inline code
    text = re.sub(r'{{(.+?)}}', r'`\1`', text)

    return text
```

## Error Handling

### Wrong Issue Type

**Scenario:** Issue is not type "Epic" or "Feature"

**Action:**
```text
CNTRLPLANE-123 is a Story, not an Epic or Feature.

This command requires an Epic or Feature issue type.

To create an enhancement from a Story, consider:
1. Convert the Story to an Epic or Feature first
2. Manually create the enhancement using the template
```

### Empty Description

**Scenario:** Epic or Feature has no description or minimal content

**Action:**
```text
Issue CNTRLPLANE-100 has minimal content.

Enhancement proposals require substantial detail. Please:
1. Complete the epic/feature description in Jira
2. Run /jira:generate-enhancement again

Or continue with interactive prompts to fill in details? (yes/no)
```

### Cannot Determine Component

**Scenario:** Cannot auto-detect component/directory from epic/feature

**Action:**
```text
Cannot determine the appropriate directory for this enhancement.

Please select:
1. enhancements/ (root - for broad-impact enhancements)
2. enhancements/hypershift/ (HyperShift/ROSA/ARO)
3. enhancements/network/ (Networking)
4. enhancements/storage/ (Storage)
5. enhancements/authentication/ (Auth/Identity)
6. Other (specify)

Selection:
```

## Best Practices

1. **Complete epic/feature first**: Ensure Jira epic or feature has comprehensive content before generation
2. **Review AI-generated content**: Enhancement is a starting point, not final document
3. **Add technical depth**: Expand implementation details with architecture diagrams, API specs
4. **Iterate with reviewers**: Share draft early for feedback
5. **Keep Jira updated**: Update epic/feature as enhancement evolves, or regenerate enhancement from updated Jira content
6. **Link bidirectionally**: Add enhancement PR link to epic/feature, epic/feature link in enhancement metadata

## Example Enhancement Generation

**Input Feature: CNTRLPLANE-100**
```text
Summary: Advanced observability for hosted control planes

Description:
Deliver unified observability capabilities for ROSA and ARO hosted control planes.

h2. Market Problem
Enterprise customers with 50+ clusters face significant operational challenges...

h2. Proposed Solution
Build a comprehensive observability platform...

h2. Strategic Value
h3. Customer Value
* 60% reduction in cluster management time
* 80% faster incident detection

h2. Scope
h3. Epics (Planned)
* Epic 1: Multi-cluster metrics aggregation
* Epic 2: Unified dashboard
* Epic 3: Fleet-wide alerting

h2. Timeline
* Target: Q3 2025 (4.23 GA)
```

**Generated Enhancement:**
```markdown
---
title: advanced-observability-for-hosted-control-planes
authors:
  - "@jdoe"
reviewers:
  - "@reviewer1"
  - "@reviewer2"
approvers:
  - "@team-lead"
api-approvers:
  - None
creation-date: 2025-01-15
last-updated: 2025-03-31
status: provisional
tracking-link:
  - https://issues.redhat.com/browse/CNTRLPLANE-100
---

# Advanced Observability for Hosted Control Planes

## Summary

Deliver unified observability capabilities for ROSA and ARO hosted control planes,
enabling enterprise customers to manage large cluster fleets with centralized
monitoring, alerting, and compliance reporting.

## Motivation

Enterprise customers managing multiple ROSA HCP clusters (50+) face significant
operational challenges...

[Full enhancement content continues...]
```

## See Also

- `/jira:generate-feature-doc` - Generate feature documentation
- `/jira:create` - Create Jira issues
- OpenShift Enhancement Process: https://github.com/openshift/enhancements
