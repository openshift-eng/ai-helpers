---
name: report-findings
description: Generate triage reports and post findings to Jira and Slack
---

## When to Use

Use this skill when Phase 3 of the `node-cve:triage` command needs to generate the triage report, post comments to Jira tracker issues, and send Slack notifications.

## Prerequisites

- `bash`, `curl` and `jq`
- Environment variables: `JIRA_API_TOKEN` (for `--notify-jira`), and `JIRA_USER` (or `JIRA_EMAIL`) with the Jira login. Set it explicitly in containers, where the `git config user.email` fallback does not exist.
- For `--notify-slack`: either `SLACK_API_TOKEN` (channel from `SLACK_CHANNEL`, default `GK6BJJ1J5`, `#team-node`; enables threading) or `SLACK_WEBHOOK` (single message, no threading). If both are set, the API token is used.
- The `node-team` plugin (shared component list)

## Helper script

All Jira and Slack calls go through [scripts/node-cve-lib.sh](scripts/node-cve-lib.sh), invoked as one command per step:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" help
```

It exists for four reasons:

- **One allowlistable command.** Headless runs use a strict Bash allowlist, where every part of a compound command must be allowed. Do not write ad-hoc `curl` or `jira` commands, and do not chain commands with `&&`, `;`, pipes or redirects. Each subcommand takes file paths as arguments and writes its own files. Use the Read and Write tools for the files.
- **Secrets stay off the command line.** Credentials reach `curl` through a config on stdin (`curl -K -`). Never write `curl -u user:token` or `-H "Authorization: Bearer ..."`, which expose the token in the process list. The webhook URL is handled the same way.
- **Shell state does not persist between Bash tool calls.** Each subcommand is self-contained. State that must survive (validated trackers, the posting gate) lives in files in the triage directory.
- **Errors are not silent, and safeguards are enforced in code.** The helper retries on HTTP 429 using `Retry-After`, checks Slack's `ok` field, exits non-zero on failure, refuses to comment on a tracker that did not pass validation in this run, and refuses all comments once the tracker threshold is exceeded. It never reads from a terminal, so it cannot hang headless.

Paths written as `.work/node-cve/triage-YYYY-MM-DD/` stand for the run directory that `init` printed as `TRIAGE_DIR=`. Use that path as is, also after midnight; the helper keeps using it for the whole run.

| Subcommand | Purpose |
|---|---|
| `validate [--max-trackers N] [--trackers ROWS] VERSION FILE` | Re-validate component and OCP version of every tracker key in FILE. Writes `validated-trackers.txt`, logs skips, opens or closes the posting gate. `--trackers` checks against the caller's rows instead of Jira (handoff mode only) |
| `find-comment KEY` | Newest existing `node-cve:triage` comment as JSON (`id`, `created`, `updated`, `author`, `own`, `own_id`, `body`), or nothing. Exits non-zero when the lookup fails |
| `post-comment [--dry-run] KEY BODYFILE [COMMENT_ID]` | Add a comment, or update the account's own existing one in place. Repeats the lookup itself and skips the tracker when it fails |
| `slack [--dry-run] --header TEXT --summary FILE --details FILE` | Post to Slack (API with thread reply, or webhook) |
| `jql-url JQL` | URL-encoded Jira search link |
| `plan-comment KEY BODYFILE` | Handoff mode: add the comment to `posting-plan.json` instead of posting it. Same validation and gate checks as `post-comment` |
| `plan-slack --header TEXT --summary FILE --details FILE` | Handoff mode: add the Slack texts to `posting-plan.json` |
| `plan-show VERSION [--dry-run]` | Handoff mode: finish `posting-plan.json` and print it |
| `audit LINE` | Append a timestamped line to `posting-audit.log` and `posting-history.log` |
| `audit-summary VERSION SOURCE MODE` | Append the totals to `posting-audit.log` and print the whole log |

## Locating shared data

The link to the `node-team` components file below resolves in a repository checkout and on the docs site. When the plugins are installed it does not resolve, because every plugin lives in its own versioned cache directory. The helper's `init` subcommand resolves the real directory and extracts the component names into `.work/node-cve/node-components.txt`, which the validation below reads. If that file is missing, run `init` again instead of writing it by hand. If the list cannot be obtained, do not post anything. The helper fails closed in that case.

## Node Team Component Safeguard (CRITICAL)

**This skill may ONLY post comments to trackers whose component is a Node team component.** Many CVEs (especially Go stdlib and vendored-dependency vulnerabilities) span 50-200+ tracker issues across dozens of OpenShift teams (HyperShift, Storage, Networking, Installer, Monitoring, Cloud providers, etc.). Node-specific reachability analysis is meaningless and confusing on another team's tracker.

The canonical Node team component list lives in the [node-team shared components reference](../../../node-team/skills/node/references/shared/components.md) ("Jira Components (OCPBUGS)" section, plus Driver Toolkit and Machine Config Operator). **Do not hardcode or duplicate that list here or anywhere else.** Always read it from the shared reference so it stays in sync as Node team components change. Note: the shared reference also documents `pscomponent:` label mappings, but those are for Phase 2 repo mapping only. The posting-time validation in Step 2 below checks the tracker's component field exclusively (see Step 2 for why).

**Never do this (this is exactly what caused the 2026-07-15 incident where analysis was posted to ~200 non-Node trackers):**
- Do NOT run an ad-hoc/one-off Jira search scoped only by CVE ID (e.g. `summary ~ "CVE-XXXX-XXXXX"`) to find trackers to comment on. A CVE ID alone is not enough to scope a search. It returns trackers for every team affected by that CVE.
- Do NOT write a separate "batch posting script" that re-queries Jira outside of the `tracker_keys` produced by the `query-open-cves` skill in Phase 1.
- Do NOT assume that because Phase 1 already filtered by component, it is safe to skip validation here. Always re-validate at posting time (defense in depth). Phase 1's `tracker_keys` may have been supplemented, cached from a stale run, or copy-pasted into a manual follow-up.

**Only post to tracker keys that are:**
1. Present in the `tracker_keys` list of the CVE record produced by `query-open-cves` (Phase 1), AND
2. Re-validated against the Node team component list immediately before posting (see Step 2 below), AND
3. Re-validated against the active OCP version filter (see "OCP Version Safeguard" below and Step 2).

## OCP Version Safeguard

**This skill may ONLY post comments to trackers whose OCP version matches `version_filter` from Phase 1** (auto-detected from an un-narrowed query, or given with `--ocp-version`). The OCP sustaining team owns triage and remediation for all versions except the latest in-development release. Posting Node-team reachability analysis to older-version trackers creates noise for the sustaining team and duplicates their work.

The `query-open-cves` skill (Phase 1) selects the OCP version and filters trackers to it, but this skill re-validates at posting time as defense in depth, the same principle as the component safeguard above. The version is passed through from Phase 1 via the `version_filter` field in the CVE query results.

**At posting time, re-validate each tracker's OCP version** (extracted from the tracker summary via regex `\[openshift-([^\]]+)\]`) against `version_filter`. If the tracker's version does not match (after stripping `.z` suffixes from both sides for comparison), skip it and log the reason in the posting audit log.

If you ever find yourself constructing a new JQL query or Jira search specifically to find trackers to comment on, STOP. That is the anti-pattern that caused this incident. Reuse the already-filtered tracker list from Phase 1 instead.

## Implementation Steps

### Step 1: Generate markdown report

Write the report to `.work/node-cve/triage-YYYY-MM-DD/report.md`:

```markdown
# Node CVE Triage Report - YYYY-MM-DD

**Version scope:** OCP <version> (<auto-detected | from --ocp-version>)

## Summary

| Metric | Count |
|--------|-------|
| Total unique CVEs | N |
| Reachable | N |
| Present | N |
| Unaffected | N |
| Uncertain | N |

## Action Required

<list of CVEs that are Reachable or Uncertain and unassigned; write "None" if there are none>

## Detailed Findings

### CVE-XXXX-XXXXX: <short description>

| Field | Value |
|-------|-------|
| Component | Node / CRI-O |
| Repository | openshift/cri-o |
| Overall classification | Reachable / Present but not exploitable / Present but not reachable / Unaffected / Uncertain |
| Overall confidence | High / Medium / Low |
| Assignee | <name or Unassigned> |
| OCP version | 5.0 |
| Tracker issues | [OCPBUGS-XXXXX](https://redhat.atlassian.net/browse/OCPBUGS-XXXXX) |

**Analysis result:**

| Branch | Commit | OCP Version | Classification | Confidence |
|--------|--------|-------------|----------------|------------|
| release-5.0 | abc1234 | 5.0 | Reachable | High |

**Evidence:**
<source code analysis summary>
<call path if found>

**Recommended action:** <specific action>

---
```

This is the only copy of the report template. The `node-cve:triage` command refers to it. Repeat the "### CVE-..." block for each CVE. Version numbers and branch names in the template are examples: use the actual `version_filter` and branch. Use the classification labels from the [analyze-cve-repos](../analyze-cve-repos/SKILL.md) Step 6 table in the report, and the enum values in JSON.

### Handoff mode

In a run started with `init --handoff` (`--handoff` on the triage command), the helper refuses `post-comment` and `slack`, and `validate` needs `--trackers`. Steps 2a, 2c and the comment and Slack texts of Steps 3 and 4 stay the same. Steps 2b, 2d and 2e do not apply: every validated tracker goes into the plan with `plan-comment`, the Slack texts with `plan-slack`, and `plan-show` finishes the plan. The caller deduplicates against the tracker's existing comments and posts. See the triage command's "Handoff mode" section for the call sequence.

### Step 2: Posting gate (if --notify-jira, --notify-slack, or --dry-run)

Nothing is posted until this gate has passed. The gate has five parts: validate, deduplicate, threshold, dry run, confirm.

**2a. Validate every tracker (MANDATORY).** For each unique CVE, take its `tracker_keys` list from Phase 1 (`query-open-cves`) and re-validate every tracker against both the component list and the version filter. Do not trust cached or upstream filtering alone. Write all tracker keys, one per line, to `.work/node-cve/triage-YYYY-MM-DD/candidate-trackers.txt` with the Write tool, then run:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" validate --max-trackers 50 5.0 .work/node-cve/triage-YYYY-MM-DD/candidate-trackers.txt
```

Use the real `version_filter`, date and `--max-trackers` value. The helper looks up each tracker (1 second apart), writes the keys that pass to `validated-trackers.txt` in the triage directory, and logs every skip to `posting-audit.log` as `SKIP-COMPONENT`, `SKIP-VERSION` or `SKIP-ERROR`.

**Component validation:** every component on the tracker must match an entry in `.work/node-cve/node-components.txt` (the "Jira Components (OCPBUGS)" list plus Driver Toolkit and Machine Config Operator from the shared components reference). **Only the component field counts. A `pscomponent:` label is not an alternative pass condition.** `pscomponent:` labels are used in Phase 2 for repo mapping, not for determining tracker ownership. A non-Node tracker (for example component "Security") could carry a `pscomponent:cri-o` label, and accepting that would reintroduce the cross-team contamination this safeguard exists to prevent.

**Version validation:** the tracker's OCP version is extracted from its summary (`[openshift-X.Y]`) and must equal `version_filter` after stripping `.z` suffixes from both sides.

If a tracker fails either check, or the lookup fails, it is skipped and logged. Never post "just in case". Both checks run even when `--component` was passed and even though Phase 1 already filtered, since this is the last line of defense before an irreversible write. `post-comment` enforces the result: it refuses any key that is not in `validated-trackers.txt`.

**2b. Decide the action per validated tracker (deduplication).** For each validated tracker, look for an existing analysis comment (reuse the result from the Phase 1.5 cache check when that already fetched it):

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" find-comment OCPBUGS-XXXXX
```

Read the `Classification` and `Branch` rows from the `body` field and compare them with the new result:

- No existing comment: action `ADD`.
- Existing comment with the same classification and branch: action `SKIP-UNCHANGED` (avoids spam). Exception: when this CVE was re-analyzed because of a trusted `[reanalyze]` tag, do not skip. Use `UPDATE <own_id>` (or `ADD` when `own_id` is null) and add the line `Re-analyzed on <date> on request, result unchanged.` above the footer. The refreshed comment is newer than the tag, which is what marks the tag as handled. Without it a headless run, which keeps no local state, would re-analyze the CVE on every run.
- Existing comment with a different classification, branch, or materially different evidence: action `UPDATE <own_id>` when your account already has a triage comment on the tracker (`own_id` is not null, even if someone else's comment is newer). It is edited in place, no second comment is added. When only other accounts have posted one (`own_id: null`, for example an interactive run by a team member), the action is `ADD`, because Jira only lets an account edit its own comments.
- Lookup failed (non-zero exit): action `SKIP-ERROR`. Do not post to that tracker, since posting without a working deduplication check would duplicate the comment on every run. Log it in the summary and continue.

The helper matches the wiki markup footer `[node-cve:triage|` and any link to `plugins/node-cve`. `post-comment` repeats this lookup and enforces the same rules, so a wrong decision here cannot produce a duplicate or an edit of someone else's comment.

**2c. Threshold (hard abort).** If more trackers pass validation than `--max-trackers` (default 50), `validate` exits with code 5, records `ABORTED jira posting` in the audit log, and closes the posting gate: every later `post-comment` in this run is refused. Report it in the summary. One OCP version across the Node components normally yields far fewer trackers, so a larger number indicates a scoping bug like the one behind the 2026-07-15 incident. `--yes` does not bypass this. Only an explicit higher `--max-trackers` does. Slack and the report are still produced.

**2d. Dry run.** With `--dry-run`, pass `--dry-run` to every `post-comment` and `slack` call. The helper then sends nothing and writes `WOULD-POST` lines to `posting-audit.log`. Run Steps 3 and 4 normally so the log shows exactly what would happen, then say clearly in the summary that nothing was posted. `--dry-run` wins over `--yes`.

**2e. Confirmation.** With `--yes`, continue. Without `--yes` and without `--dry-run`, show the plan and ask the user once before the first post:

```text
About to post (OCP <version>):
  Jira:  N new comments, M updates, K unchanged (skipped)
         OCPBUGS-XXXXX (CVE-XXXX-XXXXX, Reachable, ADD)
         ...
  Slack: channel <SLACK_CHANNEL> via API (summary + thread reply)   [or: incoming webhook, single message]
Skipped by validation: S trackers (see posting-audit.log)
Proceed? (yes / no / dry-run)
```

Post only on an explicit "yes". On "no", post nothing. On "dry-run", continue as in 2d. Ask in the conversation, not through a shell prompt. If the user cannot be asked because the run is headless (`claude --print`), abort before posting: record it with the `audit` subcommand (`ABORTED: posting needs --yes in a headless run`), post nothing, and continue with Step 5. Never wait for input in a headless run.

### Step 3: Post Jira comments (if --notify-jira)

For each unique CVE, post to every validated tracker with action `ADD` or `UPDATE`. Each tracker receives the analysis result for the selected OCP version. Comments use Atlassian wiki markup (not Markdown) and therefore go through the Jira REST API v2 comment endpoints (`POST /rest/api/2/issue/{key}/comment`, `PUT /rest/api/2/issue/{key}/comment/{id}`). API v3 would require Atlassian Document Format instead.

Write the comment body to `.work/node-cve/triage-YYYY-MM-DD/<CVE-ID>-comment.txt` with the Write tool:

```text
h3. Automated CVE Reachability Analysis

||Field||Value||
|CVE|CVE-XXXX-XXXXX|
|Repository|[openshift/cri-o|https://github.com/openshift/cri-o]|
|Branch|release-5.0|
|OCP Version|5.0|
|Classification|Reachable|
|Confidence|High|

h4. Evidence
{noformat}
<source code analysis summary>
{noformat}

h4. Recommended Action
<specific next step>

----
_AI-generated analysis by [node-cve:triage|https://github.com/openshift-eng/ai-helpers/tree/main/plugins/node-cve]. Always review prior to use._
```

Then post it, one call per tracker. The first form adds a comment, the second updates the existing comment with that id. Add `--dry-run` directly after `post-comment` for a dry run:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" post-comment OCPBUGS-XXXXX .work/node-cve/triage-YYYY-MM-DD/CVE-XXXX-XXXXX-comment.txt
```

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" post-comment OCPBUGS-YYYYY .work/node-cve/triage-YYYY-MM-DD/CVE-XXXX-XXXXX-comment.txt 12345678
```

Fill in real values. "Classification" is exactly one label from the [analyze-cve-repos](../analyze-cve-repos/SKILL.md) Step 6 table (Reachable, Present but not exploitable, Present but not reachable, Unaffected, Uncertain), "Confidence" one of High, Medium, Low. The evidence must not contain the text `{noformat}`.

Use the footer line exactly as shown. The "AI-generated" label and review notice are required by Red Hat's medium-risk AI agent controls (TR-01, HU-01). The `[node-cve:triage|` link in it is also the marker that deduplication and the cache check search for. Do not append a date. The Jira comment timestamp already covers that.

**Important:**
- `post-comment` refuses keys that are not in `validated-trackers.txt` and refuses everything when the gate is closed. Do not work around a refusal.
- It waits 1 second after each call and retries on HTTP 429 with the `Retry-After` delay.
- If commenting fails on a specific issue (for example permissions), the helper logs `FAILED` to the audit log and exits non-zero. Continue with the next tracker.

**Audit log (MANDATORY whenever Step 2 ran):** every `SKIP-*`, `POSTED`, `WOULD-POST`, `FAILED`, `REFUSED` and `ABORTED` event is appended to `.work/node-cve/triage-YYYY-MM-DD/posting-audit.log` by the helper, and mirrored to `.work/node-cve/posting-history.log`, which survives the age-based purge of `triage-*` directories by `/node-team:cleanup`. After Step 4, finish with:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" audit-summary 5.0 auto-detected live
```

The arguments are the version filter, its source (`auto-detected` or `argument`) and the mode (`live`, `dry-run` or `aborted`). The subcommand appends the totals and prints the whole log to stdout, so headless runs in ephemeral pods keep the record in their job log.

If any trackers were skipped, print a visible warning in the command summary output (Phase 4) so the operator notices immediately, for example "⚠️ Skipped N trackers during posting (K non-Node-component, J wrong version), see posting-audit.log". A non-zero skip count is expected and healthy. For component skips it means the cross-team safeguard is working as intended, and for version skips it means other-version trackers are being left to the sustaining team as required.

### Step 4: Send Slack notification (if --notify-slack)

Two modes are supported. The helper picks one per run:

- **Slack API** when `$SLACK_API_TOKEN` is set. The channel is `$SLACK_CHANNEL`, default `GK6BJJ1J5` (`#team-node`). Posts a summary and a threaded reply with the details.
- **Webhook** when only `$SLACK_WEBHOOK` is set. Posts a single message with summary and details. No threading.

The helper builds the Block Kit payloads with `jq` (a quoted heredoc with `$SLACK_CHANNEL` inside would be sent literally), keeps the token and the webhook URL off the command line, retries on HTTP 429, and checks the `ok` field of the response, because the Slack API reports failures as HTTP 200 with `"ok": false`. It appends the required footer (":robot_face: AI-generated by node-cve:triage. Always review prior to use.") to every message.

**Building the texts.** Collect tracker keys per classification group and build the links with the helper:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" jql-url 'key in (OCPBUGS-XXXXX, OCPBUGS-YYYYY)'
```

- Unassigned link: the same with ` AND (assignee is EMPTY OR assignee in ("ocp-sustaining-blocked-trackers", "Node Team Bot Account"))` appended. The same rule defines the "M unassigned" count everywhere (summary, Slack, report).
- Slack link syntax is `<url|text>`. Omit the "(M unassigned)" part when M is 0. Omit classification lines and sections with a count of 0.
- Header on a first run: "Node CVE Triage (N CVEs analyzed, OCP <version>)". With cached results: "Node CVE Triage (N CVEs, M new, OCP <version>)", plus ", K updated" if classifications changed.

Summary text, one line per non-empty group. Write it to `slack-summary.txt` in the triage directory:

```text
:red_circle: Reachable: <url|N> (<url|M> unassigned)
:large_yellow_circle: Present: <url|N> (<url|M> unassigned)
:large_green_circle: Unaffected: <url|N>
:grey_question: Uncertain: <url|N> (<url|M> unassigned)
```

Details text, one section per non-empty group. Each CVE ID links to a JQL filter showing all its trackers (or directly to the tracker when there is only one). Write it to `slack-details.txt`:

```text
*Reachable (action required):*
• <url|CVE-XXXX-XXXXX> - <short description>. (CRI-O, high confidence, N trackers[, M unassigned])

*Present (no action needed):*
• ...

*Unaffected:*
• ...

*Uncertain (needs manual investigation):*
• ...
```

A Slack text block is limited to 3000 characters. Keep each file below that. If the details are longer, truncate the list with "... and N more. See full report."

Then post (add `--dry-run` directly after `slack` for a dry run):

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/report-findings/scripts/node-cve-lib.sh" slack --header "Node CVE Triage (6 CVEs analyzed, OCP 5.0)" --summary .work/node-cve/triage-YYYY-MM-DD/slack-summary.txt --details .work/node-cve/triage-YYYY-MM-DD/slack-details.txt
```

A Slack failure is reported as a warning and recorded in the audit log, but does not fail the command.

### Step 5: Save structured data

Write `cves.json` to `.work/node-cve/triage-YYYY-MM-DD/cves.json` containing the full analysis results in machine-readable format:

```json
{
  "date": "YYYY-MM-DD",
  "version_filter": "5.0",
  "version_source": "auto-detected",
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
      "affected_versions": ["5.0"],
      "branch": "release-5.0",
      "commit": "abc1234",
      "ocp_version": "5.0",
      "evidence_summary": "...",
      "recommended_action": "..."
    }
  ]
}
```

`overall_classification` is one of `REACHABLE`, `PRESENT_NOT_EXPLOITABLE`, `PRESENT_NOT_REACHABLE`, `UNAFFECTED`, `UNCERTAIN`. `overall_confidence` is one of `HIGH`, `MEDIUM`, `LOW`. Both are defined in [analyze-cve-repos](../analyze-cve-repos/SKILL.md) Step 6. Human-readable output (report, Jira, Slack) uses the matching labels, and the summary groups both `PRESENT_*` values under "Present".

### Step 6: Verify artifacts

Ensure all generated files exist under `.work/node-cve/triage-YYYY-MM-DD/`:
- `report.md` - full report
- `cves.json` - structured CVE data (for programmatic consumption)
- `posting-audit.log` - only when `--notify-jira`, `--notify-slack`, or `--dry-run` was used (see Steps 2 and 3). Do not expect this file otherwise.
- `<CVE-ID>-<branch>-analysis.md` - per-CVE per-branch source code analysis (from Phase 2)

## Return Value

```json
{
  "skill": "report-findings",
  "status": "success",
  "version_filter": "5.0",
  "report_path": ".work/node-cve/triage-YYYY-MM-DD/report.md",
  "dry_run": false,
  "jira_comments_posted": 4,
  "jira_comments_updated": 1,
  "jira_comments_unchanged": 1,
  "jira_comments_failed": 0,
  "jira_posting_aborted_by_threshold": false,
  "jira_trackers_skipped_non_node_component": 0,
  "jira_trackers_skipped_version_mismatch": 0,
  "slack_notified": true,
  "artifacts": [
    ".work/node-cve/triage-YYYY-MM-DD/report.md",
    ".work/node-cve/triage-YYYY-MM-DD/cves.json",
    ".work/node-cve/triage-YYYY-MM-DD/posting-audit.log"
  ]
}
```

`posting-audit.log` is only produced when the posting gate ran (`--notify-jira`, `--notify-slack`, or `--dry-run`). When present, add it to the `artifacts` list. Omit it on other runs rather than reporting a file that was never written. With `dry_run: true`, the posted and updated counts are what would have been posted.

## Error Handling

- Non-Node-team component detected on a tracker: skip that tracker and log it in the audit log (see Step 2). Never post to it. Do not fail the entire command. Other trackers for the same CVE may still be valid Node team trackers.
- OCP version mismatch detected on a tracker: skip that tracker and log it in the audit log (see Step 2). The sustaining team owns the other versions. Do not fail the entire command.
- Tracker lookup failed during validation: skip that tracker (fail closed) and log it.
- More trackers than `--max-trackers`: abort all Jira posting for this run (Step 2c). The report and Slack summary are still produced.
- No confirmation in an interactive run: post nothing. Headless run without `--yes`: abort before posting, never wait for input.
- Jira comment failures: logged by the helper. Continue with the next tracker. Do not fail the entire command because one tracker issue is inaccessible.
- HTTP 429 from Jira or Slack: the helpers wait for `Retry-After` (or 5, 10, ... seconds) and retry up to 5 times.
- Slack failure: log a warning. Slack API errors arrive as HTTP 200 with `"ok": false` and an `error` field (`channel_not_found`, `not_in_channel`, `invalid_auth`, `msg_too_long`), which the helper records in the audit log.
- If the Slack payload exceeds the character limit, split or truncate the CVE list and add "... and N more. See full report."
- File write failures: these are critical. Exit with error if the work directory is not writable.
