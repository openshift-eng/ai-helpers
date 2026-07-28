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

## Node Team Component Safeguard (CRITICAL)

**This skill may ONLY post comments to trackers whose component is a Node team component.** Many CVEs (especially Go stdlib and vendored-dependency vulnerabilities) span 50-200+ tracker issues across dozens of OpenShift teams (HyperShift, Storage, Networking, Installer, Monitoring, Cloud providers, etc.). Node-specific reachability analysis is meaningless — and confusing — on another team's tracker.

The canonical Node team component list lives in the [node-team shared components reference](../../../node-team/skills/node/references/shared/components.md) ("Jira Components (OCPBUGS)" section, plus Driver Toolkit and Machine Config Operator). **Do not hardcode or duplicate that list here or anywhere else** — always read it from the shared reference so it stays in sync as Node team components change. Note: the shared reference also documents `pscomponent:` label mappings, but those are for Phase 1 CVE discovery and Phase 2 repo mapping only — the posting-time validation in Step 2 below checks the tracker's COMPONENT field exclusively (see Step 2 for why).

**Never do this (this is exactly what caused the 2026-07-15 incident where analysis was posted to ~200 non-Node trackers):**
- Do NOT run an ad-hoc/one-off Jira search scoped only by CVE ID (e.g. `summary ~ "CVE-XXXX-XXXXX"`) to find trackers to comment on. A CVE ID alone is not enough to scope a search — it will return trackers for every team affected by that CVE.
- Do NOT write a separate "batch posting script" that re-queries Jira outside of the `tracker_keys` produced by the `query-open-cves` skill in Phase 1.
- Do NOT assume that because Phase 1 already filtered by component, it is safe to skip validation here. Always re-validate at posting time (defense in depth) — Phase 1's `tracker_keys` may have been supplemented, cached from a stale run, or copy-pasted into a manual follow-up.

**Only post to tracker keys that are:**
1. Present in the `tracker_keys` list of the CVE record produced by `query-open-cves` (Phase 1), AND
2. Re-validated against the Node team component list immediately before posting (see Step 2 below).

If you ever find yourself constructing a new JQL query or Jira search specifically to find trackers to comment on, STOP — that is the anti-pattern that caused this incident. Reuse the already-filtered tracker list from Phase 1 instead.

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

**VALIDATION (MANDATORY, before posting anything):** For each unique CVE, take its `tracker_keys` list from Phase 1 (`query-open-cves`) and re-validate every tracker's component immediately before posting — do not trust cached or upstream filtering alone:

```bash
# component_is_node_team() checks the tracker's COMPONENT field against the
# canonical Node team component list from the shared components reference
# (link above), NOT a hardcoded list.
for tracker_key in $TRACKER_KEYS; do
  component=$(jira issue view "$tracker_key" --plain --no-headers --columns COMPONENT | tail -1)

  if ! component_is_node_team "$component"; then
    echo "⚠️  SKIPPING $tracker_key: component '$component' is not a Node team component" | tee -a "$SKIPPED_LOG"
    sleep 1
    continue
  fi

  # Component validated — proceed with posting for $tracker_key
  sleep 1
done
```

A component is considered a Node team component only if it matches an entry in the "Jira Components (OCPBUGS)" list (plus Driver Toolkit, Machine Config Operator) in the shared components reference. **Check the COMPONENT field only — do not treat a `pscomponent:` label as an alternative pass condition.** `pscomponent:` labels are used in Phase 1/Phase 2 for CVE discovery and repo mapping, not for determining tracker ownership; a non-Node tracker (e.g. component "Security") could incidentally carry a `pscomponent:cri-o` label, and accepting that as a pass would silently reintroduce the exact cross-team contamination this safeguard exists to prevent. If a tracker's component cannot be confidently classified as Node team, **skip it and log the reason** — never post "just in case." This check must run even when `--component` was passed, and even if Phase 1 already filtered by component, since this is the last line of defense before an irreversible write to another team's tracker. Rate limit: sleep 1 second between validation calls, same as the posting calls below, since a CVE with N trackers makes N validation calls before posting even starts.

For each unique CVE, post a comment on every **validated** tracker issue. Each tracker issue receives the analysis result for its specific OCP version/branch (not a blanket result). Use Atlassian wiki markup (not Markdown):

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
- Post to ALL **validated** tracker issues for a CVE (all version trackers), each with its version-specific result
- If commenting fails on a specific issue (e.g., permissions), log a warning and continue

**POST-POSTING AUDIT (MANDATORY when --notify-jira is used):** Write an audit log to `.work/node-cve/triage-$(date +%Y-%m-%d)/posting-audit.log` summarizing what was posted and what was skipped, so cross-team contamination is caught immediately instead of discovered days later:

```bash
{
  echo "=== Node CVE Triage Posting Audit — $(date +%Y-%m-%d) ==="
  echo "CVEs processed: $CVE_COUNT"
  echo "Trackers commented: $POSTED_COUNT"
  echo "Trackers skipped (non-Node component): $SKIPPED_COUNT"
  echo ""
  echo "Skipped trackers (tracker, component, reason):"
  cat "$SKIPPED_LOG"
} > ".work/node-cve/triage-$(date +%Y-%m-%d)/posting-audit.log"
```

If `$SKIPPED_COUNT` is greater than zero, print a visible warning in the command summary output (Phase 4) so the operator notices immediately, e.g. "⚠️ Skipped N non-Node-component trackers — see posting-audit.log". A non-zero skip count is expected and healthy for multi-team CVEs; it means the safeguard is working. A skip count that is unexpectedly large relative to Phase 1's tracker count may indicate a bug and should be investigated before re-running.

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
- `posting-audit.log` - only when `--notify-jira` was used (see Step 2); do not expect this file otherwise
- `<CVE-ID>-<branch>-analysis.md` - per-CVE per-branch source code analysis (from Phase 2)

## Return Value

```json
{
  "skill": "report-findings",
  "status": "success",
  "report_path": ".work/node-cve/triage-2026-05-20/report.md",
  "jira_comments_posted": 45,
  "jira_comments_failed": 0,
  "jira_trackers_skipped_non_node_component": 0,
  "slack_notified": true,
  "artifacts": [
    ".work/node-cve/triage-2026-05-20/report.md",
    ".work/node-cve/triage-2026-05-20/cves.json"
  ]
}
```

`posting-audit.log` is only produced when `--notify-jira` is used (see Step 2). When present, add it to the `artifacts` list; omit it entirely on runs without `--notify-jira` rather than reporting a file that was never written.

## Error Handling

- Non-Node-team component detected on a tracker: skip that tracker and log it in the audit log (see Step 2). Never post to it. Do not fail the entire command — other trackers for the same CVE may still be valid Node team trackers.
- Jira comment failures: log and continue. Do not fail the entire command because one tracker issue is inaccessible.
- Slack failure: log warning. Common causes: invalid token/webhook URL, missing channel permissions, network issues, payload too large (Slack limit: 3000 chars per text block).
- If the Slack payload exceeds the character limit, truncate the CVE list and add "... and N more. See full report."
- File write failures: these are critical. Exit with error if the work directory is not writable.
