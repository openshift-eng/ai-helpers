---
name: report-findings
description: Generate triage reports and post findings to Jira and Slack
---

## When to Use

Use this skill when Phase 3 of the `node-cve:triage` command needs to generate the triage report, post comments to Jira tracker issues, and send Slack notifications.

## Prerequisites

- `jira` CLI (for `--notify-jira`)
- `curl` (for `--notify-slack`)
- Environment variables: `JIRA_API_TOKEN` (for Jira)
- For Slack: either `SLACK_API_TOKEN` + `SLACK_CHANNEL` (preferred, enables threading) or `SLACK_WEBHOOK` (simpler, no threading)

## Implementation Steps

### Step 1: Generate markdown report

Write the report to `.work/node-cve/triage-YYYY-MM-DD/report.md`:

```markdown
# Node CVE Triage Report - YYYY-MM-DD

## Summary

| Metric | Count |
|--------|-------|
| Total unique CVEs | N |
| Reachable | N |
| Present | N |
| Unaffected | N |
| Uncertain | N |

## Action Required

List CVEs that are Reachable or Uncertain with unassigned owners. These need immediate attention.

## Detailed Findings

### CVE-XXXX-XXXXX: <short description>

| Field | Value |
|-------|-------|
| Component | Node / CRI-O |
| Repository | openshift/cri-o |
| Overall classification | Reachable / Present but not exploitable / Present but not reachable / Unaffected / Uncertain |
| Overall confidence | High / Medium / Low |
| Assignee | <name or Unassigned> |
| Affected versions | 4.12.z - 4.19 |
| Tracker issues | [OCPBUGS-XXXXX](https://redhat.atlassian.net/browse/OCPBUGS-XXXXX), [OCPBUGS-XXXXX](https://redhat.atlassian.net/browse/OCPBUGS-XXXXX), ... |

**Per-branch results:**

| Branch | OCP Version | Classification | Confidence |
|--------|-------------|----------------|------------|
| release-1.28 | 4.15 | Reachable | High |
| release-1.29 | 4.16 | Reachable | High |
| release-1.30 | 4.17 | Unaffected | High |
| ... | ... | ... | ... |

**Evidence (worst-case branch):**
<source code analysis summary>
<call path if found>

**Recommended action:** <specific action>

---
(repeat for each CVE)
```

### Step 2: Post Jira comments (if --notify-jira)

For each unique CVE, post a comment on ALL its tracker issues. Each tracker issue receives the analysis result for its specific OCP version/branch (not a blanket result). Use Atlassian wiki markup (not Markdown):

```bash
jira issue comment add OCPBUGS-XXXXX "$(cat <<'COMMENT'
h3. Automated CVE Reachability Analysis

||Field||Value||
|CVE|CVE-XXXX-XXXXX|
|Repository|[openshift/cri-o|https://github.com/openshift/cri-o]|
|Branch|release-1.31|
|Classification|Reachable / Present but not exploitable / Present but not reachable / Unaffected / Uncertain|
|Confidence|High / Medium / Low|

h4. Results across all analyzed branches
||Branch||OCP Version||Classification||Confidence||
|release-1.28|4.15|Reachable|High|
|release-1.29|4.16|Reachable|High|
|release-1.30|4.17|Unaffected|High|

h4. Evidence
{noformat}
<source code analysis summary for this tracker's specific branch>
{noformat}

h4. Recommended Action
<specific next step>

----
_AI-generated analysis by [node-cve:triage|https://github.com/openshift-eng/ai-helpers/tree/main/plugins/node-cve]. Always review prior to use._
COMMENT
)"
```

Use the footer line exactly as shown. The "AI-generated" label and review notice are required by Red Hat's medium-risk AI agent controls (TR-01, HU-01). Do not append a date; the Jira comment timestamp already covers that.

**Deduplication:** Before posting a comment, check for existing `node-cve:triage` comments on the issue:

```bash
jira issue comment list OCPBUGS-XXXXX --plain --no-headers
```

Search the output for comments containing `[node-cve:triage|`. This pattern anchors on the Jira wiki-markup link syntax and matches both the current and legacy footer formats. If a prior comment exists:
- If the classification or evidence has changed, edit the existing comment rather than adding a new one
- If the result is unchanged, skip posting to avoid spam

**Important:**
- Rate limit: sleep 1 second between Jira API calls to avoid HTTP 429 throttling
- Post to ALL tracker issues for a CVE (all version trackers), each with its version-specific result
- If commenting fails on a specific issue (e.g., permissions), log a warning and continue

### Step 3: Send Slack notification (if --notify-slack)

Two modes are supported depending on which credentials are available:

**Mode A: Slack API (`$SLACK_API_TOKEN` + `$SLACK_CHANNEL`)** - enables threaded messages.

**Step 3a: Post summary (main message)**

```bash
RESPONSE=$(curl -s -X POST "https://slack.com/api/chat.postMessage" \
  -H "Authorization: Bearer $SLACK_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(cat <<'SLACK'
{
  "channel": "$SLACK_CHANNEL",
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "Node CVE Triage (N CVEs analyzed)"
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": ":red_circle: Reachable: <https://redhat.atlassian.net/issues/?jql=key%20in%20(OCPBUGS-XXXXX)|N> (<https://redhat.atlassian.net/issues/?jql=key%20in%20(OCPBUGS-XXXXX)%20AND%20assignee%20is%20EMPTY|M> unassigned)\n:large_yellow_circle: Present: <https://redhat.atlassian.net/issues/?jql=key%20in%20(OCPBUGS-XXXXX)|N> (<https://redhat.atlassian.net/issues/?jql=key%20in%20(OCPBUGS-XXXXX)%20AND%20assignee%20is%20EMPTY|M> unassigned)\n:large_green_circle: Unaffected: <https://redhat.atlassian.net/issues/?jql=key%20in%20(OCPBUGS-XXXXX)|N>\n:grey_question: Uncertain: <https://redhat.atlassian.net/issues/?jql=key%20in%20(OCPBUGS-XXXXX)|N>"
      }
    },
    {
      "type": "context",
      "elements": [
        {
          "type": "mrkdwn",
          "text": ":robot_face: AI-generated by node-cve:triage. Always review prior to use."
        }
      ]
    }
  ]
}
SLACK
)"
```

Build the JQL URLs by collecting all tracker keys per classification group. Use `key in (OCPBUGS-XXXXX, OCPBUGS-YYYYY, ...)` as the filter. For the unassigned link, add `AND (assignee is EMPTY OR assignee = "ocp-sustaining-blocked-trackers")` to also count placeholder assignees as unassigned. URL-encode the JQL query. Omit the "(M unassigned)" part when M is 0. Omit empty classification lines.

On subsequent runs with cached results, change the header to "Node CVE Triage (N CVEs, M new)" or "Node CVE Triage (N CVEs, M new, K updated)".

Extract `ts` from the JSON response (`jq -r '.ts'`) to use as `thread_ts` for the reply.

**Step 3b: Post detailed findings (thread reply)**

```bash
curl -s -X POST "https://slack.com/api/chat.postMessage" \
  -H "Authorization: Bearer $SLACK_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(cat <<'SLACK'
{
  "channel": "$SLACK_CHANNEL",
  "thread_ts": "<ts-from-step-3a>",
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Reachable (action required):*\n• <https://redhat.atlassian.net/issues/?jql=key%20in%20(OCPBUGS-XXXXX%2COCPBUGS-YYYYY)|CVE-XXXX-XXXXX> - <short description>. (CRI-O, high confidence, N trackers[, M unassigned])\n\n*Present (no action needed):*\n• <https://redhat.atlassian.net/browse/OCPBUGS-XXXXX|CVE-XXXX-XXXXX> - <short description>. (kubernetes, high confidence, 1 tracker)\n\n*Unaffected:*\n• ...\n\n*Uncertain:*\n• ..."
      }
    },
    {
      "type": "context",
      "elements": [
        {
          "type": "mrkdwn",
          "text": ":robot_face: AI-generated by node-cve:triage. Always review prior to use."
        }
      ]
    }
  ]
}
SLACK
)"
```

**Mode B: Webhook (`$SLACK_WEBHOOK`)** - simpler setup, no threading.

Post a single message containing both summary and detailed findings:

```bash
curl -s -X POST "$SLACK_WEBHOOK" \
  -H "Content-Type: application/json" \
  -d "$(cat <<'SLACK'
{
  "blocks": [
    {
      "type": "header",
      "text": {
        "type": "plain_text",
        "text": "Node CVE Triage (N CVEs analyzed)"
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": ":red_circle: Reachable: <https://redhat.atlassian.net/issues/?jql=key%20in%20(OCPBUGS-XXXXX)|N> (<https://redhat.atlassian.net/issues/?jql=key%20in%20(OCPBUGS-XXXXX)%20AND%20assignee%20is%20EMPTY|M> unassigned)\n:large_yellow_circle: Present: <https://redhat.atlassian.net/issues/?jql=key%20in%20(OCPBUGS-XXXXX)|N>\n:large_green_circle: Unaffected: <https://redhat.atlassian.net/issues/?jql=key%20in%20(OCPBUGS-XXXXX)|N>"
      }
    },
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Reachable (action required):*\n• <https://redhat.atlassian.net/issues/?jql=key%20in%20(OCPBUGS-XXXXX%2COCPBUGS-YYYYY)|CVE-XXXX-XXXXX> - <short description>. (CRI-O, high confidence, N trackers[, M unassigned])\n\n*Present (no action needed):*\n• ...\n\n*Unaffected:*\n• ..."
      }
    },
    {
      "type": "context",
      "elements": [
        {
          "type": "mrkdwn",
          "text": ":robot_face: AI-generated by node-cve:triage. Always review prior to use."
        }
      ]
    }
  ]
}
SLACK
)"
```

**Both modes:** Omit empty classification sections. If the total text exceeds the Slack character limit (3000 chars per text block), split across multiple blocks or truncate with "... and N more. See full report." If Slack returns a non-200 status, log a warning but do not fail the command.

### Step 4: Save structured data

Write `cves.json` to `.work/node-cve/triage-YYYY-MM-DD/cves.json` containing the full analysis results in machine-readable format:

```json
{
  "date": "YYYY-MM-DD",
  "total_cves": 6,
  "cves": [
    {
      "cve_id": "CVE-XXXX-XXXXX",
      "summary": "...",
      "components": ["Node / CRI-O"],
      "repo": "https://github.com/openshift/cri-o",
      "overall_classification": "REACHABLE",
      "overall_confidence": "HIGH",
      "assignee": "...",
      "tracker_keys": ["OCPBUGS-XXXXX"],
      "affected_versions": ["4.12.z", "4.19"],
      "per_branch_results": [
        {
          "branch": "release-1.28",
          "ocp_version": "4.15",
          "classification": "REACHABLE",
          "confidence": "HIGH",
          "evidence_summary": "..."
        },
        {
          "branch": "release-1.30",
          "ocp_version": "4.17",
          "classification": "NOT_AFFECTED",
          "confidence": "HIGH",
          "evidence_summary": "..."
        }
      ],
      "recommended_action": "..."
    }
  ]
}
```

### Step 5: Verify artifacts

Ensure all generated files exist under `.work/node-cve/triage-YYYY-MM-DD/`:
- `report.md` - full report
- `cves.json` - structured CVE data (for programmatic consumption)
- `<CVE-ID>-<branch>-analysis.md` - per-CVE per-branch source code analysis (from Phase 2)

## Return Value

```json
{
  "skill": "report-findings",
  "status": "success",
  "report_path": ".work/node-cve/triage-2026-05-20/report.md",
  "jira_comments_posted": 45,
  "jira_comments_failed": 0,
  "slack_notified": true,
  "artifacts": [
    ".work/node-cve/triage-2026-05-20/report.md",
    ".work/node-cve/triage-2026-05-20/cves.json"
  ]
}
```

## Error Handling

- Jira comment failures: log and continue. Do not fail the entire command because one tracker issue is inaccessible.
- Slack failure: log warning. Common causes: invalid token/webhook URL, missing channel permissions, network issues, payload too large (Slack limit: 3000 chars per text block).
- If the Slack payload exceeds the character limit, truncate the CVE list and add "... and N more. See full report."
- File write failures: these are critical. Exit with error if the work directory is not writable.
