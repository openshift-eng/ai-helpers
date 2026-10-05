# Known Disruption Issues (Step 8)

Skip this step if `--skip-jira` was passed. This step searches Jira for existing cards that
may already track the disruption pattern identified in the analysis, and offers to file a new
bug if none are found.

## 8.1: Search for Known Disruption Cards

Extract the base backend names from the analysis (e.g., `openshift-api`, `kube-api`, `oauth-api`
— strip `cache-` prefix and `-new-connections`/`-reused-connections` suffixes to get the base name).

Run two JQL queries using `searchJiraIssuesUsingJql` (cloudId: `redhat.atlassian.net`) —
one for open cards, one for closed. Combine all backend names into a single query to avoid
excessive API calls:

**Query 1 — Open cards:**

```jql
project in (TRT, OCPBUGS) AND status != Closed AND (labels = "disruption" OR text ~ "disruption") AND (text ~ "{backend_name_1}" OR text ~ "{backend_name_2}") ORDER BY updated DESC
```

**Query 2 — Closed cards (prior investigations):**

```jql
project in (TRT, OCPBUGS) AND status = Closed AND (labels = "disruption" OR text ~ "disruption") AND (text ~ "{backend_name_1}" OR text ~ "{backend_name_2}") ORDER BY updated DESC
```

Use `maxResults: 10` and `fields: ["summary", "status", "labels", "assignee", "updated", "priority", "resolution"]`
for each query. Deduplicate results across queries by issue key.

Closed cards are valuable — they may document a prior investigation into the same disruption
pattern that provides context (root cause, fix applied, affected versions).

## 8.1.1: Search by Root Cause Signals

The backend-name queries above find bugs filed about the symptom (which backend was disrupted).
Many bugs are filed about the root cause mechanism instead (CPU exhaustion, OVS stalls, etcd
pressure). Build additional JQL queries from the root cause signals identified during analysis.

Check the `concurrent_events` and `key_signals` from the parsed data. For each signal category
present, run one additional open-card query:

**If OVS stalls were detected** (`OVSVswitchdLog` in concurrent events with `max_poll_interval_ms > 500`):

```jql
project in (TRT, OCPBUGS) AND status != Closed AND (summary ~ "OVS" OR summary ~ "vswitchd" OR summary ~ "ovs-vswitchd" OR text ~ "vswitchd stall") ORDER BY updated DESC
```

**If CPU pressure was detected** (`CPUMonitor` in concurrent events):

```jql
project in (TRT, OCPBUGS) AND status != Closed AND (summary ~ "CPU exhaustion" OR summary ~ "ExtremelyHigh" OR text ~ "ExtremelyHighIndividualControlPlaneCPU" OR summary ~ "high CPU") ORDER BY updated DESC
```

**If etcd pressure was detected** (`EtcdLog` in concurrent events with count > 0):

```jql
project in (TRT, OCPBUGS) AND status != Closed AND (summary ~ "etcd leader" OR summary ~ "etcd slow" OR text ~ "took too long" OR summary ~ "etcd pressure") ORDER BY updated DESC
```

Use the same `maxResults: 10` and field list. Deduplicate all results across all queries
(backend queries + signal queries) by issue key before presenting.

## 8.2: Present Results and Offer Actions

**If matching cards are found:**

Add a "Known Disruption Issues" section to the report. Group results into open and closed,
with open cards listed first (most actionable), then closed cards (useful for context):

```markdown
## Known Disruption Issues

### Open
| Key | Summary | Status | Labels | Assignee | Updated |
|-----|---------|--------|--------|----------|---------|
| [OCPBUGS-1234](url) | openshift-api disruption on AWS | In Progress | disruption | @engineer | 2026-07-28 |

### Previously Resolved
| Key | Summary | Resolution | Labels | Updated |
|-----|---------|------------|--------|---------|
| [OCPBUGS-999](url) | openshift-api disruption on Azure | Done - Errata | disruption | 2026-03-15 |
```

For each card missing the "disruption" label, note it:

```text
> OCPBUGS-5678 does not have the "disruption" label. Consider adding it for tracking.
```

Ask the user:
1. Whether any of the found cards match this specific disruption
2. Whether to add the "disruption" label to any unlabeled cards that match — use `editJiraIssue`
   to append `"disruption"` to the existing labels array

**If no matching cards are found:**

Add to the report:

```markdown
## Known Disruption Issues

No existing Jira cards were found tracking this disruption pattern.
```

Then ask:

```text
No existing Jira cards were found tracking this disruption pattern.

Would you like to file a disruption bug? (yes/no)
```

If yes, proceed to Step 8.3.

## 8.3: File a Disruption Bug (Interactive)

Use the `jira:create` skill to file a bug. Propose the following details for the user to review
and edit before creation:

- **Project**: `OCPBUGS` (default; ask user if TRT is more appropriate)
- **Type**: Bug
- **Summary**: Derived from the analysis — e.g., `"{backend_name} disruption in {job_name} on {platform}"`
- **Description**: Populated from the analysis report including:
  - Root cause hypothesis
  - Affected backends and their types (cache/non-cache)
  - Job run links (Prow and Sippy Intervals)
  - Key evidence (timeline data links, etcd signals, OVS stalls, CPU metrics)
  - Disruption counts and durations
- **Labels**: `["disruption", "ai-generated-jira"]`

Present the proposed summary and description to the user. Allow them to confirm, edit, or cancel
before creating. Follow the `jira:create` skill's interactive workflow and project conventions
(load `jira:jira-conventions` for the target project).

After creation, update the report's "Known Disruption Issues" section with the new bug's key and URL.
