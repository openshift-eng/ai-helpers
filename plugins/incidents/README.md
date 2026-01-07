# Incidents Plugin

Incident management and historical analysis tools for faster incident resolution. This plugin helps teams leverage institutional knowledge by searching past incidents, finding similar patterns, and surfacing what worked before.

## Commands

### `/incidents:similar-incidents <description>`

Search past incidents to find similar patterns and resolutions using a JIRA-first, GitHub-enriched approach.

**Usage:**
```bash
# Search by error message
/incidents:similar-incidents "etcd leader changed 5 times in last minute"

# Search by symptoms
/incidents:similar-incidents "API server returning 503 errors after node restart"

# Search by component behavior
/incidents:similar-incidents "ingress controller pods crashlooping after upgrade to 4.15"

# Search with stack trace
/incidents:similar-incidents "panic: runtime error: invalid memory address at pkg/operator/controller.go:234"
```

## How It Works

The command follows a **JIRA-first approach**:

### Step 1: Parse & Extract Keywords
- Extracts error messages, component names, symptoms, versions from your description
- Builds optimized search queries with primary, secondary, and context keywords
- Handles multiple keyword variants for broader matching

### Step 2: Search JIRA
- Queries Red Hat JIRA (OCPBUGS, OCPSTRAT, ETCD, RHSTOR, CNV, etc.)
- Fetches issue details including descriptions, comments, and external links
- Parses GitHub PR links from JIRA tickets

### Step 3: Fetch Linked GitHub PRs
- For each GitHub PR found in JIRA, retrieves full PR details
- Extracts: title, description, files changed, merge status, reviews
- Shows exactly what code was changed to fix the issue

### Step 4: Analyze & Rank
- Scores each result by relevance (keyword match, component match, recency)
- Bonus points for resolved issues with merged PRs
- Groups related incidents to identify recurring patterns

### Step 5: Present Findings
- Generates comprehensive report with actionable recommendations
- Shows JIRA issues linked to their fixing PRs
- Highlights recurring patterns and prevention measures

## Output Example

```
# Similar Incidents Analysis Report

**Generated**: 2024-12-24 10:30:00
**Search Query**: etcd leader election instability

## Executive Summary

- **Similar incidents found**: 5
- **Incidents with verified fixes**: 3
- **Recurring pattern detected**: Yes
- **Recommended action**: Review PR #4521 for heartbeat configuration fix

---

## Top Similar Incidents

### 1. [OCPBUGS-12345] etcd leader election storms during high load

**Similarity Score**: 95% | **Status**: Resolved | **Resolved**: 2024-11-15

**JIRA Link**: https://issues.redhat.com/browse/OCPBUGS-12345

**Component(s)**: etcd, cluster-etcd-operator

**Root Cause**:
> Network latency spikes were causing heartbeat timeouts, triggering
> frequent leader elections under load.

**Symptoms Matched**:
- Leader changed multiple times in short period
- Cluster instability during peak usage

#### Linked GitHub PRs

| PR | Title | Status | Files Changed | Link |
|----|-------|--------|---------------|------|
| #4521 | Fix etcd heartbeat interval configuration | MERGED | 3 files | [View PR](https://github.com/openshift/cluster-etcd-operator/pull/4521) |

**Key Files Changed**:
```
pkg/operator/configobservation/etcd/observe_etcd.go
pkg/operator/etcdcli/etcd_client.go
```

**Fix Summary**:
> Adjusted heartbeat-interval and election-timeout values to be more
> tolerant of network latency variations.

---

## Recurring Patterns

| Pattern | Occurrences | Time Range | Root Cause |
|---------|-------------|------------|------------|
| etcd leader instability | 12 times | Last 6 months | Disk I/O or network latency |

---

## Recommended Actions

1. **Immediate**: Check disk I/O latency on control plane nodes
2. **Verify**: Confirm your version includes the fix from PR #4521
3. **Consider**: Review etcd metrics for slow commits
```

## Value Proposition

| Benefit | Impact |
|---------|--------|
| **Faster incident resolution** | Saves hours of investigation time by finding similar past issues |
| **Better learnings capture** | Surfaces relevant post-mortems and RCAs automatically |
| **Prevent repeat incidents** | Identifies recurring patterns that indicate systemic issues |
| **Improve team knowledge** | Shares solutions across team members |
| **Create institutional memory** | Builds searchable knowledge base of incident responses |

## Prerequisites

- `curl` - For JIRA REST API access
- `jq` - For JSON parsing (recommended)
- `gh` - GitHub CLI for fetching PR details
- Network access to `issues.redhat.com` and `github.com`

## Tips for Better Search Results

1. **Include specific error messages** - Exact error text provides the best matches
2. **Mention affected components** - Component names help narrow results (e.g., "cluster-etcd-operator")
3. **Include version information** - Version-specific issues are common (e.g., "after upgrade to 4.15")
4. **Describe observable symptoms** - What you see helps match against past incidents
5. **Include stack traces** - Function names and file paths are highly searchable

## Keyword Extraction

The command automatically extracts and categorizes keywords:

| Category | Examples |
|----------|----------|
| **Components** | etcd, kube-apiserver, ingress-controller, cluster-version-operator |
| **Error Messages** | "context deadline exceeded", "connection refused" |
| **Symptoms** | crashlooping, OOMKilled, not ready, leader election |
| **Versions** | 4.15, 4.14.5, v3.5.9 |
| **Platforms** | AWS, Azure, GCP, bare-metal, vSphere |

## Integration with Other Commands

- **After finding a match**: Use `/jira:solve {JIRA_KEY}` to apply a similar fix
- **For CI failures**: Results may link to `/prow-job:analyze-test-failure` for deeper analysis
- **For component health**: Check `/component-health:analyze` for ongoing issues

## Contributing

To improve incident searchability for future users:
- Tag resolved incidents with clear component labels in JIRA
- Include specific error messages in JIRA descriptions
- Link GitHub PRs to JIRA issues when fixing bugs
- Document root causes and resolutions thoroughly
- Create post-mortems for significant incidents
