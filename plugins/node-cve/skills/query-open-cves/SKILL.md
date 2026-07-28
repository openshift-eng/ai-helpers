---
name: query-open-cves
description: Query and deduplicate open CVE vulnerability issues from OCPBUGS for Node team components
---

## When to Use

Use this skill when Phase 1 of the `node-cve:triage` command needs to fetch all open CVE trackers from Jira and deduplicate them into a list of unique CVEs.

## Prerequisites

- `jira` CLI configured with valid credentials
- Environment variables: `JIRA_API_TOKEN`
- Network access to Jira instance

## Implementation Steps

### Step 1: Load Node team components

Read the CVE-tracked component list from the [node-team shared components reference](../../../node-team/skills/node/references/shared/components.md). Use the full "Jira Components (OCPBUGS)" list plus the additional CVE triage components (Driver Toolkit, Machine Config Operator).

**Default behavior (no `--component` flag): include ALL Node team components, and ONLY Node team components.** "No flag" does not mean "no filter" — it means "the full Node component list." Never construct a query that omits the component filter entirely, even when no `--component` value was given.

If `--component` was specified, use only that single component instead of the full list. The value must match an entry in the shared reference exactly; if it does not, print an error listing the valid component names and exit rather than silently falling back to an unfiltered query.

The Jira saved filter "Node Components" (ID 91645) does not include Driver Toolkit and Machine Config Operator, so the explicit list from the shared reference is used for CVE queries to ensure completeness.

**CRITICAL SAFEGUARD:** This component filter is what scopes every downstream step (analysis, reporting, and — critically — Jira comment posting in Phase 3) to Node team trackers only. Many CVEs (especially Go stdlib or vendored-dependency vulnerabilities) have 50-200+ tracker issues across dozens of OpenShift teams. Omitting or bypassing this filter — for example by later re-querying Jira with only a CVE ID and no component constraint — is what caused the 2026-07-15 incident where Node-specific analysis was posted to ~200 non-Node trackers (HyperShift, Storage, Networking, Installer, etc.). See the [report-findings](../report-findings/SKILL.md) "Node Team Component Safeguard" section for the posting-time re-validation this feeds into.

### Step 2: Query Jira

Build and execute the JQL query. The `component in (...)` clause is mandatory in every invocation of this query, whether or not `--component` was passed:

```bash
jira issue list -q "project = OCPBUGS AND type = Vulnerability AND component in (<components from shared reference, or the single --component value>) AND status not in (Closed, Done, Verified)" --plain --no-headers --columns KEY,SUMMARY,COMPONENT,STATUS,ASSIGNEE,LABELS
```

If `--days N` was specified, add `AND updated >= -${N}d` to the JQL.

Handle pagination: the `jira` CLI returns up to 100 results by default (format: `--paginate <from>:<limit>`). If the result count equals 100, paginate by re-running with `--paginate 100:100`, `--paginate 200:100`, etc. until fewer than 100 results are returned.

**Sanity check:** After fetching results, verify that every returned `COMPONENT` value is actually in the Node team component list (or, when `--component` was given, equals that value). If any row has an unexpected component, this indicates a JQL construction bug — log a warning with the offending tracker key and component, and exclude that row rather than propagating it downstream.

### Step 3: Parse results

For each row in the output:
1. Extract the issue key (e.g., `OCPBUGS-85948`)
2. Extract the CVE ID from the summary using regex: `CVE-[0-9]{4}-[0-9]+`
3. Extract the OCP version from the summary brackets: `\[openshift-([^\]]+)\]`
4. Extract component name
5. Extract status and assignee
6. Extract labels (preserve `pscomponent:*` labels for Phase 2 repo mapping)

### Step 4: Deduplicate by CVE ID

Group all tracker issues by CVE ID. For each unique CVE, build a record:

```json
{
  "cve_id": "CVE-2026-32281",
  "summary": "Go crypto/x509: Denial of Service via inefficient certificate chain validation",
  "components": ["Node / CRI-O"],
  "status": "New",
  "assignee": "ocp-sustaining-blocked-trackers",
  "tracker_keys": ["OCPBUGS-85948", "OCPBUGS-85932", "OCPBUGS-85914", "..."],
  "affected_versions": ["4.12.z", "4.13.z", "4.14.z", "4.15.z", "4.16.z", "4.17", "4.18", "4.19"],
  "labels": ["pscomponent:cri-o", "SecurityTracking"]
}
```

A single CVE may span multiple components (e.g., both "Node / CRI-O" and "Machine Config Operator"), so `components` is an array collecting all distinct component values across tracker issues for that CVE.

Use the highest version tracker for the "primary" assignee and status (issues on newer versions are typically more actively managed).

### Step 5: Identify unassigned CVEs

Flag CVEs where:
- Assignee is a bot account (e.g., "ocp-sustaining-blocked-trackers") or empty
- Status is "New" (not yet picked up)


## Return Value

```json
{
  "skill": "query-open-cves",
  "status": "success",
  "total_trackers": 45,
  "unique_cves": 6,
  "cves": [
    {
      "cve_id": "CVE-2026-32281",
      "summary": "...",
      "components": ["Node / CRI-O"],
      "status": "New",
      "assignee": "ocp-sustaining-blocked-trackers",
      "is_unassigned": true,
      "tracker_keys": ["OCPBUGS-85948", "..."],
      "affected_versions": ["4.12.z", "..."],
      "labels": ["pscomponent:cri-o"]
    }
  ]
}
```

## Error Handling

- If `jira` CLI returns an error, print the error and exit. Common causes: expired API token, network issues, invalid JQL.
- If the query returns 0 results, return an empty list (not an error).
- If a CVE ID cannot be extracted from a summary, log a warning and skip that tracker.
