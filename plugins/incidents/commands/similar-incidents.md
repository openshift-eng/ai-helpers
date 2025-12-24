---
description: Search past incidents to find similar patterns and what worked before
argument-hint: <description>
---

## Name
incidents:similar-incidents

## Synopsis
```
/incidents:similar-incidents <description>
```

## Description

The `incidents:similar-incidents` command searches through historical incident records to find similar patterns, previous resolutions, and lessons learned. This command helps prevent re-investigation of known issues by leveraging institutional knowledge and past incident data.

**Key Benefits:**
- **Faster incident resolution**: Quickly identify if a similar issue has been encountered before (saves hours of investigation)
- **Better learnings capture**: Surface relevant post-mortems and RCAs (Root Cause Analyses)
- **Prevent repeat incidents**: Identify recurring patterns that may indicate systemic issues
- **Improve team knowledge**: Share solutions across team members
- **Create institutional memory**: Build a searchable knowledge base of incident responses

**Search Strategy:**
This command follows a JIRA-first approach:
1. Search JIRA for similar incidents using extracted keywords
2. Extract linked GitHub PRs from matching JIRA tickets
3. Fetch PR details to understand the actual code fixes
4. Present a comprehensive view linking incidents to their resolutions

## Implementation

### Step 1: Create Working Directory

1. **Set up the working directory for this search session**:
   ```bash
   mkdir -p .work/incidents/similar-incidents/$(date +%Y%m%d-%H%M%S)
   ```
   - Use this directory to store intermediate results and the final report
   - The timestamp ensures each search session has its own workspace

### Step 2: Parse and Normalize the Description

The quality of search results depends heavily on extracting the right keywords from the user's description.

1. **Identify and extract key information categories**:

   | Category | What to Look For | Examples |
   |----------|------------------|----------|
   | Error Messages | Exact error strings, error codes | `"context deadline exceeded"`, `"connection refused"`, `E1234` |
   | Stack Traces | Function names, file paths, line numbers | `pkg/operator/controller.go:234`, `panic: runtime error` |
   | Components | OpenShift/Kubernetes component names | `etcd`, `kube-apiserver`, `ingress-controller`, `cluster-etcd-operator` |
   | Operators | Operator names and CRDs | `cluster-version-operator`, `machine-config-operator`, `HostedCluster` |
   | Symptoms | Observable behaviors | `crashlooping`, `OOMKilled`, `leader election`, `not ready` |
   | Versions | OpenShift/component versions | `4.15`, `4.14.5`, `v3.5.9` |
   | Platforms | Infrastructure platforms | `AWS`, `Azure`, `GCP`, `bare-metal`, `vSphere` |
   | Resource Types | Kubernetes resources | `Pod`, `Deployment`, `StatefulSet`, `Node` |

2. **Build keyword extraction logic**:
   ```
   Primary Keywords (high weight):
   - Exact error messages (quoted strings)
   - Component/operator names
   - Specific error codes
   
   Secondary Keywords (medium weight):
   - Symptom descriptions
   - Resource types affected
   - Version numbers
   
   Context Keywords (low weight):
   - Platform information
   - Environment details
   - Timeline indicators
   ```

3. **Normalize extracted keywords**:
   - Convert to lowercase for consistent matching
   - Remove common noise words: "the", "a", "an", "is", "was", "error", "issue", "problem"
   - Preserve exact error strings in quotes
   - Handle hyphenated component names (e.g., `cluster-etcd-operator` should also match `etcd`)

4. **Create multiple search query variants**:
   - **Strict query**: Uses exact phrases for error messages
   - **Broad query**: Uses individual keywords with OR operators
   - **Component-focused query**: Prioritizes component/operator names

### Step 3: Search JIRA for Similar Incidents

JIRA is the primary source of truth for incident records at Red Hat.

1. **Construct the JQL query**:

   **Primary query pattern**:
   ```
   project in (OCPBUGS, OCPSTRAT, ETCD, RHSTOR, CNV, MGMT, HOSTEDCP) 
   AND (
     summary ~ "{primary_keywords}" 
     OR description ~ "{primary_keywords}"
     OR text ~ "{exact_error_message}"
   ) 
   AND type in (Bug, Incident, Story) 
   AND status in (Closed, Resolved, Done, "In Progress")
   ORDER BY updated DESC
   ```

   **Component-specific query** (if component identified):
   ```
   project = OCPBUGS 
   AND component = "{component_name}"
   AND (summary ~ "{keywords}" OR description ~ "{keywords}")
   AND resolution is not EMPTY
   ORDER BY resolved DESC
   ```

2. **Execute the JIRA search**:
   ```bash
   # URL-encode the JQL query
   ENCODED_JQL=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${JQL_QUERY}'))")
   
   # Fetch results with relevant fields
   curl -s "https://issues.redhat.com/rest/api/2/search?jql=${ENCODED_JQL}&maxResults=20&fields=key,summary,status,resolution,description,components,labels,issuelinks,fixVersions,created,updated,resolutiondate,comment,customfield_12310220,customfield_12311140" | jq '.'
   ```

3. **Important JIRA fields to extract**:

   | Field | Purpose | How to Use |
   |-------|---------|------------|
   | `key` | Issue identifier | Primary reference (e.g., OCPBUGS-12345) |
   | `summary` | Issue title | Quick understanding of the issue |
   | `description` | Full issue details | Contains root cause, symptoms, and often GitHub links |
   | `status` | Current state | Prioritize Resolved/Closed issues |
   | `resolution` | How it was resolved | "Fixed", "Done", "Won't Fix", etc. |
   | `components` | Affected components | Match against user's component |
   | `labels` | Tags and categories | May include version, severity info |
   | `issuelinks` | Related JIRA issues | Find duplicates, related bugs |
   | `fixVersions` | Version where fixed | Helps identify if fix is in user's version |
   | `comment.comments` | Discussion thread | Often contains root cause analysis |
   | `customfield_12310220` | External links | **GitHub PR links are often here** |
   | `customfield_12311140` | Target Version | When fix is expected |

4. **Parse and score each JIRA result**:
   
   For each issue returned, calculate a relevance score:
   ```
   Score = 0
   
   # Exact error message match in summary or description
   if exact_error_found: Score += 50
   
   # Component match
   if component_matches: Score += 30
   
   # Multiple keyword matches
   Score += (keyword_match_count * 10)
   
   # Resolution status bonus
   if status in ["Resolved", "Closed"]: Score += 20
   
   # Recency bonus (issues from last 6 months)
   if updated_within_6_months: Score += 10
   
   # Has linked PR bonus
   if has_github_pr_link: Score += 25
   ```

5. **Extract GitHub PR links from each JIRA issue**:

   Search for GitHub URLs in these locations (in order of reliability):
   
   a. **External Links field** (`customfield_12310220`):
      ```python
      # Often contains structured link data
      external_links = issue['fields'].get('customfield_12310220', [])
      for link in external_links:
          if 'github.com' in link.get('url', ''):
              github_urls.append(link['url'])
      ```
   
   b. **Issue description**:
      ```bash
      # Extract GitHub PR URLs using regex
      echo "${description}" | grep -oE 'https://github\.com/[^/]+/[^/]+/pull/[0-9]+' | sort -u
      ```
   
   c. **Issue comments**:
      ```bash
      # Search through all comments for PR links
      echo "${comments}" | grep -oE 'https://github\.com/[^/]+/[^/]+/pull/[0-9]+' | sort -u
      ```
   
   d. **Commit links** (alternative pattern):
      ```bash
      echo "${description}" | grep -oE 'https://github\.com/[^/]+/[^/]+/commit/[a-f0-9]+' | sort -u
      ```

   **Common GitHub URL patterns to match**:
   - `https://github.com/{org}/{repo}/pull/{number}` - Pull requests
   - `https://github.com/{org}/{repo}/issues/{number}` - GitHub issues
   - `https://github.com/{org}/{repo}/commit/{sha}` - Direct commits
   - `https://github.com/{org}/{repo}/compare/{base}...{head}` - Comparisons

### Step 4: Fetch Linked GitHub PR Details

For each GitHub PR link found in JIRA, retrieve detailed information.

1. **Fetch PR metadata using gh CLI**:
   ```bash
   gh pr view {pr_number} --repo {org}/{repo} --json number,title,body,state,mergedAt,mergeCommit,files,additions,deletions,changedFiles,labels,author,reviews,comments,closingIssuesReferences
   ```

2. **Key PR fields to extract and analyze**:

   | Field | Purpose | What to Look For |
   |-------|---------|------------------|
   | `title` | PR summary | Often contains JIRA key and fix description |
   | `body` | Full PR description | Root cause explanation, testing details |
   | `state` | PR status | MERGED, OPEN, CLOSED |
   | `mergedAt` | When merged | Confirms fix is available |
   | `files` | Changed files | Shows exactly what was fixed |
   | `additions/deletions` | Change size | Indicates complexity of fix |
   | `labels` | PR labels | May include "backport", "bug", "critical" |
   | `reviews` | Review comments | May contain technical insights |
   | `closingIssuesReferences` | Linked issues | "Fixes #123" references |

3. **Analyze the files changed**:
   ```bash
   # Get list of files changed in the PR
   gh pr view {pr_number} --repo {org}/{repo} --json files --jq '.files[].path'
   ```
   
   Categorize changed files:
   - `*_test.go` - Test files (shows what behavior was tested)
   - `pkg/controller/*` - Controller logic (core fix location)
   - `pkg/api/*` - API changes (may require upgrade considerations)
   - `vendor/*` - Dependency updates
   - `docs/*` - Documentation changes
   - `Makefile`, `go.mod` - Build/dependency changes

4. **Extract the actual fix from PR diff** (for critical PRs):
   ```bash
   # Get the diff for key files (not vendor or generated)
   gh pr diff {pr_number} --repo {org}/{repo} | grep -A 20 "^diff --git a/pkg/"
   ```

5. **Check for backport PRs**:
   ```bash
   # Search for related backport PRs
   gh search prs "backport {pr_number}" --repo {org}/{repo} --limit 5
   gh search prs "{jira_key}" --repo {org}/{repo} --state merged --limit 10
   ```

6. **If no linked PRs found in JIRA, perform fallback search**:
   ```bash
   # Search for PRs mentioning the JIRA key
   gh search prs "{jira_key}" --repo openshift/origin --repo openshift/hypershift --repo openshift/cluster-etcd-operator --state merged --limit 10
   
   # Search for PRs with similar error messages (if specific enough)
   gh search prs "{exact_error_message}" --owner openshift --state merged --limit 5
   ```

### Step 5: Analyze Related JIRA Issues

Explore the issue link network for additional context.

1. **Follow JIRA issue links**:
   - **Duplicates**: `is duplicated by` / `duplicates` - Same issue reported multiple times
   - **Blocks/Blocked by**: Dependency relationships
   - **Clones**: Similar issues in different projects
   - **Relates to**: Related but distinct issues

2. **For each linked issue**, fetch:
   ```bash
   curl -s "https://issues.redhat.com/rest/api/2/issue/{linked_key}?fields=key,summary,status,resolution,description" | jq '.'
   ```

3. **Build an incident cluster**:
   - Group all related issues
   - Identify the "root" issue (usually the first reported or most detailed)
   - Track the fix propagation across linked issues

### Step 6: Enrich with Additional Sources (If Needed)

When JIRA and GitHub don't provide enough context:

1. **Search for related test failures in CI**:
   ```bash
   # Use the ci:ask-sippy command if available
   # Or search Prow job history for similar failures
   ```

2. **Check for post-mortem documents**:
   - Search team documentation repositories
   - Look for RCA documents referencing the JIRA keys found

3. **Search component-specific documentation**:
   - Check the component's GitHub repo for known issues in CHANGELOG or docs

### Step 7: Compile and Rank Results

1. **Create a ranked list of similar incidents**:

   **Final Scoring Formula**:
   ```
   FinalScore = JIRARelevanceScore + GitHubBonus + RecencyBonus + ResolutionBonus
   
   Where:
   - JIRARelevanceScore: Calculated in Step 3 (0-100)
   - GitHubBonus: +25 if has merged PR, +15 if has open PR, +10 if has commits
   - RecencyBonus: +15 if < 3 months old, +10 if < 6 months, +5 if < 12 months
   - ResolutionBonus: +20 if Resolved with fix, +10 if has workaround, +5 if has RCA
   ```

2. **Group related incidents**:
   - Cluster issues that share the same root cause
   - Identify if this is a recurring pattern
   - Note version-specific occurrences

3. **Extract actionable information for each top result**:
   - **Root Cause**: From JIRA description or PR body
   - **Fix Applied**: From merged PR details
   - **Files Changed**: Specific files and paths
   - **Workaround**: If mentioned in comments
   - **Prevention**: Any follow-up actions taken

### Step 8: Present Findings

Generate a comprehensive, actionable report.

1. **Create the structured report**:

   ```markdown
   # Similar Incidents Analysis Report
   
   **Generated**: {timestamp}
   **Search Query**: {original user description}
   
   ## Executive Summary
   
   - **Similar incidents found**: {count}
   - **Incidents with verified fixes**: {count_with_merged_prs}
   - **Recurring pattern detected**: {yes/no}
   - **Recommended action**: {brief recommendation}
   
   ---
   
   ## Keywords Extracted
   
   | Category | Keywords |
   |----------|----------|
   | Components | {component1}, {component2} |
   | Error Messages | "{exact_error}" |
   | Symptoms | {symptom1}, {symptom2} |
   | Versions | {version_info} |
   
   ---
   
   ## Top Similar Incidents
   
   ### 1. [{JIRA_KEY}] {Issue Title}
   
   **Similarity Score**: {score}% | **Status**: {status} | **Resolved**: {date}
   
   **JIRA Link**: https://issues.redhat.com/browse/{JIRA_KEY}
   
   **Component(s)**: {components}
   
   **Root Cause**:
   > {Brief root cause from JIRA description or PR body}
   
   **Symptoms Matched**:
   - {symptom1 that matched user's description}
   - {symptom2 that matched}
   
   #### Linked GitHub PRs
   
   | PR | Title | Status | Files Changed | Link |
   |----|-------|--------|---------------|------|
   | #{pr_number} | {title} | MERGED | {count} files | [View PR]({url}) |
   
   **Key Files Changed**:
   ```
   pkg/controller/foo/bar.go
   pkg/operator/observe_config.go
   ```
   
   **Fix Summary**:
   > {Brief description of what the PR changed to fix the issue}
   
   ---
   
   ### 2. [{JIRA_KEY}] {Issue Title}
   
   {... repeat format for each similar incident ...}
   
   ---
   
   ## Recurring Patterns
   
   {If patterns detected, describe them}
   
   | Pattern | Occurrences | Time Range | Root Cause |
   |---------|-------------|------------|------------|
   | {description} | {N} times | {date range} | {common cause} |
   
   ---
   
   ## Recommended Actions
   
   Based on the similar incidents found:
   
   1. **Immediate**: {action based on top match}
   2. **Verify**: {check if fix applies to current version}
   3. **Consider**: {additional steps based on patterns}
   
   ---
   
   ## Related Resources
   
   - **Post-mortems**: {links if found}
   - **Documentation**: {relevant docs}
   - **Related JIRA Issues**: {list of related keys}
   
   ---
   
   ## Next Steps
   
   - To apply a fix from the similar incidents, use: `/jira:solve {JIRA_KEY}`
   - To investigate a specific PR further, review the linked GitHub PR
   - To search with different keywords, run this command again with refined terms
   ```

2. **Save the report**:
   ```bash
   REPORT_DIR=".work/incidents/similar-incidents/$(date +%Y%m%d-%H%M%S)"
   mkdir -p "${REPORT_DIR}"
   # Save report to ${REPORT_DIR}/report.md
   ```

3. **Display summary to user**:
   - Show top 3-5 most similar incidents inline
   - Provide clear links to full report and resources
   - Offer follow-up actions

### Step 9: Interactive Follow-up

1. **Ask the user for next steps**:
   - "Would you like me to analyze any specific incident in more detail?"
   - "Should I search with different/refined keywords?"
   - "Would you like me to help apply the fix from incident X?"

2. **If no similar incidents found**:
   - Suggest broadening the search terms
   - Offer to create a new JIRA issue to document this incident
   - Recommend checking with SMEs or escalation paths

3. **If user wants to apply a fix**:
   - Suggest using `/jira:solve {JIRA_KEY}` for the matching issue
   - Offer to cherry-pick or adapt the fix from the linked PR

## Return Value

- **Format**: Markdown report with structured findings
- **Location**: Report saved to `.work/incidents/similar-incidents/{timestamp}/report.md`
- **Console Output**: Summary of top 5 most similar incidents with links and recommended actions

## Examples

1. **Search by error message**:
   ```
   /incidents:similar-incidents "etcd leader changed 5 times in last minute, cluster unstable"
   ```
   Searches for incidents related to etcd leader election issues. Will match JIRA issues mentioning "leader changed", "leader election", "etcd unstable" and find related PRs in cluster-etcd-operator.

2. **Search by symptoms**:
   ```
   /incidents:similar-incidents "API server returning 503 errors after node restart on AWS"
   ```
   Finds past incidents involving API server availability issues on AWS. Keywords extracted: "API server", "503", "node restart", "AWS".

3. **Search by component and behavior**:
   ```
   /incidents:similar-incidents "ingress controller pods crashlooping after upgrade to 4.15"
   ```
   Locates upgrade-related ingress issues specific to version 4.15. Will search with component filter for ingress-related issues.

4. **Search with stack trace**:
   ```
   /incidents:similar-incidents "panic: runtime error: invalid memory address or nil pointer dereference at pkg/operator/controller.go:234"
   ```
   Finds incidents with similar panic patterns in operator code. Will search for the exact error and file path.

5. **Search by operator behavior**:
   ```
   /incidents:similar-incidents "cluster-version-operator stuck in Progressing state after upgrade, reconciling message shows image pull failure"
   ```
   Identifies CVO-related issues with image pull problems during upgrades.

## Arguments

- `$1`: The incident description, error message, or symptoms to search for (required)
  - Can include: error messages, stack traces, component names, symptoms
  - Longer, more detailed descriptions yield better results
  - Quotes are recommended for multi-word descriptions
  - Include version numbers when relevant
  - Mentioning the specific component/operator helps narrow results

## Prerequisites

- `curl` - For JIRA REST API access
- `jq` - For JSON parsing (recommended)
- `gh` - GitHub CLI for PR details (required for GitHub enrichment)
- Network access to `issues.redhat.com` and `github.com`

## Notes

- **JIRA-first approach**: Always starts with JIRA as the source of truth, then enriches with GitHub
- **Linked PRs are key**: The most valuable information comes from PRs linked to resolved JIRA issues
- **Scoring prioritizes fixes**: Resolved issues with merged PRs score higher
- **Results ranked by relevance**: Not just recency - multiple factors contribute to ranking
- **Patterns matter**: Recurring issues are highlighted to prevent repeat incidents
- **Actionable output**: Each result includes clear next steps
- For best results, include specific error messages or codes when available
- Consider adding tags/labels to resolved incidents to improve future searchability
