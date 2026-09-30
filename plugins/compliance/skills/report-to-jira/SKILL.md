---
name: report-to-jira
description: Use when posting a completed CVE analysis report or PR follow-up as a Jira comment on the source ticket from `/compliance:analyze-cve`.
---

# Report to Jira

Posts the completed CVE analysis report as a comment on the **source Jira ticket** — the same ticket the CVE details were read from (`SOURCE_TICKET`, set in Phase 0.5 from `--jira=`/`--jql=`). Always called as the last step of Phase 4, after the report has been generated. Also reused by `create-fix-pr` (Phase 6) for a short follow-up comment containing the PR URL.

If no Jira ticket was involved (direct `<CVE-ID>` mode), this skill is skipped entirely — there is nothing to post to.

---

## Step 1: Confirm Report is Ready

Before posting, verify the following are available from the parent command:

- Final report content (full markdown from Phase 3)
- CVE ID (e.g. `CVE-2024-45338`)
- **`SOURCE_TICKET`** — the Jira ticket key from `--jira=`/`--jql=` (e.g. `OCPBUGS-12345`). This is the only ticket this skill writes to.
- **`jira_context`** — label snapshot from Phase 0.5 (`jira_context["labels"]`); used as a hint only — Step 4.5 re-fetches current labels before writing
- Risk level (`HIGH` / `MEDIUM` / `LOW` / `NEEDS_REVIEW`)

**If `SOURCE_TICKET` is not available** (direct CVE mode): return `status: skipped` with reason `"no_source_ticket"`.

If the report is incomplete or Phase 3 did not finish, return `status: skipped` with reason.

---

## Step 2: Build the Comment Body

Read `${AI_HELPERS_WORKSPACE:-.}/.work/compliance/analyze-cve/${CVE_ID}/report.md` from Phase 3 and post it **in full**. The Jira comment is the report — do **not** pre-emptively shorten it or write a separate `jira-comment.md`.

Write standard Markdown — Jira Cloud renders Markdown natively when posted with `contentFormat: "markdown"` (see [markdown-for-jira reference](../../../jira/reference/markdown-for-jira.md) if that plugin is installed; the syntax is standard CommonMark either way). No wiki-markup conversion is needed.

**Default body = attribution header + entire `report.md`.** If Phase 4 produced a remediation plan not already under `## Remediation` in the report, append it as `## Remediation Plan (Phase 4)`.

Prepend the following attribution header before the report:

```markdown
> ⚠️ **This analysis was performed automatically by `/compliance:analyze-cve`.**
> Results should be reviewed by a human before acting on remediation steps.

---

```

### Size limit handling

Jira comment bodies are capped at **32,767 characters**. Apply these steps **in order** — only move to the next step if the comment is still over 32,000 chars:

1. **Post in full** (≤ 32,000 chars) — no changes.
2. **Trim raw tool dumps only** (> 32,000 chars) — inside fenced code blocks, replace full `govulncheck` scrollback, call-graph DOT, or megabyte grep output with a one-line pointer:
   ```
   _(Full output truncated — see `${AI_HELPERS_WORKSPACE:-.}/.work/compliance/analyze-cve/<CVE_ID>/govulncheck-source.txt`)_
   ```
   Keep executive summary, CVE context, evidence interpretations, call-graph **results table**, risk assessment, and remediation in full. Re-measure.
3. **Shortened summary (last resort only)** — if still > 32,000 chars after step 2, replace the body with a condensed summary derived from `report.md`. Retain: risk level, repository/branch/commit, dependency versions, govulncheck conclusion, four-algorithm call-graph table, manual verification findings, recommendation, and artifact paths. Omit repeated narrative and any remaining large code blocks. Note at the top:
   ```
   _(Full report exceeded Jira comment limit — summary below. See `${AI_HELPERS_WORKSPACE:-.}/.work/compliance/analyze-cve/<CVE_ID>/report.md`.)_
   ```
   Do **not** use a shortened summary unless steps 1–2 are insufficient.

### Stripping rules (apply regardless of size)

- Remove internal email addresses — replace with the display name only.
- Do not include embargoed content — if somehow reached here with `embargo_status: True`, abort immediately.

---

## Step 3: Post the Comment

The comment is posted publicly (visible to everyone with access to the ticket) — no visibility restriction is applied or needed.

### Step 3a: MCP tool (default)

```python
addCommentToJiraIssue(
    issue_key=SOURCE_TICKET,
    comment_body="<constructed comment from Step 2>",
    contentFormat="markdown"
)
```

### Step 3b: Fallbacks (if the MCP tool is unavailable)

**jira-cli:**

```bash
jira issue comment add "${SOURCE_TICKET}" \
  --body "$(cat /tmp/cve-report-comment.txt)" \
  --no-input
```

**Direct REST API** (headless environments with `JIRA_API_TOKEN`/`JIRA_URL` set but no MCP tool or jira-cli):

> **Credential rule:** Never print, echo, or log any token, key, or password value. Reference credentials only via environment variable names. Never interpolate a credential value into a logged string.

```bash
JIRA_API_TOKEN="${JIRA_API_TOKEN:-${JIRA_TOKEN:-${ATLASSIAN_API_TOKEN:-}}}"
JIRA_BASE_URL="${JIRA_URL:-}"
JIRA_EMAIL="${JIRA_EMAIL:-}"

if [ -n "${JIRA_API_TOKEN}" ] && [ -n "${JIRA_BASE_URL}" ]; then
  case "${JIRA_BASE_URL}" in
    https://*) ;;
    *) echo "ERROR: JIRA_BASE_URL must use HTTPS (got: ${JIRA_BASE_URL})"; exit 1 ;;
  esac

  COMMENT_JSON_BODY=$(python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))" < /tmp/cve-report-comment.txt)
  if [ -n "${JIRA_EMAIL}" ]; then
    auth_header="Basic $(printf '%s:%s' "${JIRA_EMAIL}" "${JIRA_API_TOKEN}" | base64 | tr -d '\n')"
  else
    auth_header="Bearer ${JIRA_API_TOKEN}"
  fi
  curl_cfg=$(mktemp) && chmod 600 "${curl_cfg}"
  trap 'rm -f "${curl_cfg}"' RETURN EXIT INT TERM
  printf 'header = "Authorization: %s"\n' "${auth_header}" > "${curl_cfg}"
  unset auth_header

  HTTP_STATUS=$(curl -s -o /tmp/jira-post-response.txt -w "%{http_code}" \
    --connect-timeout 15 --max-time 60 -X POST -K "${curl_cfg}" \
    "${JIRA_BASE_URL}/rest/api/2/issue/${SOURCE_TICKET}/comment" \
    -H "Content-Type: application/json" \
    --data-binary "{\"body\": ${COMMENT_JSON_BODY}}")

  echo "Jira API HTTP status: ${HTTP_STATUS}"
  [ "${HTTP_STATUS}" != "201" ] && cat /tmp/jira-post-response.txt 2>/dev/null
fi
```

- IF HTTP 201 → posted successfully.
- Never print `JIRA_API_TOKEN`, `JIRA_EMAIL`, the computed auth header, or the contents of `${curl_cfg}` — only the HTTP status code and response body.

On failure of every available method, display the full comment body in the session so the user can post it manually. Do not retry more than once.

---

## Step 4: Confirm and Report

After posting, output to the session:

```
✅ Report posted to <SOURCE_TICKET>
   <JIRA_BASE_URL>/browse/<SOURCE_TICKET>

   CVE:        <CVE_ID>
   Risk level: <level>
```

If the post fails:

```
❌ Failed to post report to <SOURCE_TICKET>
   Error: <error message>

   The full report has been displayed above. Please copy and paste it
   into <SOURCE_TICKET> manually.
```

Do not retry more than once. On failure, display the comment body in the session so the user can post it manually.

---

## Step 4.5: Mark Source Ticket as Processed

Add the label **`ai-cve-analyzed`** to `SOURCE_TICKET` to prevent redundant re-processing on future runs.

**Only run this step if Step 3 succeeded.** If Step 3 failed for any reason, **skip this step entirely** — do not add the label to a ticket that did not receive the comment.

### ⚠️ CRITICAL: Existing labels MUST be preserved

Jira's update API **replaces** the entire label list — it does not append. Sending only `["ai-cve-analyzed"]` will **delete all existing labels** on the ticket. This is a destructive operation and must never happen.

**Before writing, always:**
1. Re-fetch the ticket's current labels (do not trust the Phase 0.5 snapshot alone — labels may have changed while analysis ran):
   ```python
   fresh = getJiraIssue(issue_key=SOURCE_TICKET)
   current_labels = fresh["fields"]["labels"]   # never start from an empty list
   ```
   Use `jira_context["labels"]` only as a fallback if the re-fetch fails.
2. Append `ai-cve-analyzed` to `current_labels`
3. Write the combined list back

```python
# current_labels comes from the mandatory re-fetch above (Step 4.5)

if "ai-cve-analyzed" not in current_labels:
    new_labels = current_labels + ["ai-cve-analyzed"]
else:
    new_labels = current_labels   # already marked — nothing to write

editJiraIssue(
    issue_key=SOURCE_TICKET,
    fields={"labels": new_labels}
)
```

**Fallback — jira-cli** (appends without replacing — safe to use directly):

```bash
jira issue edit "${SOURCE_TICKET}" --label "ai-cve-analyzed" --no-input
```

### Verification (mandatory when using the MCP/REST label-replace path)

After the update call, re-fetch the ticket labels and confirm:

```python
updated = getJiraIssue(issue_key=SOURCE_TICKET)
updated_labels = updated["fields"]["labels"]

assert "ai-cve-analyzed" in updated_labels, "New label missing"
for label in current_labels:
    assert label in updated_labels, f"LABEL LOST: {label}"
```

**If the new label is missing:** log a non-fatal warning — the report is already posted:
```
⚠️ Could not add 'ai-cve-analyzed' label to <SOURCE_TICKET>. Add it manually to prevent re-processing.
```

**If an existing label was lost:** this is a data integrity error — log it and output the original label list so the user can restore it:
```
❌ LABEL INTEGRITY ERROR on <SOURCE_TICKET>
   The following labels were present before the update but are now missing:
   <list of lost labels>

   Original full label list (restore manually):
   <current_labels>
```

**If both checks pass:**
```
✅ Label 'ai-cve-analyzed' added to <SOURCE_TICKET>. Labels verified intact.
```

---

## Return Value

**Success:**
```json
{
  "skill": "report-to-jira",
  "status": "success",
  "source_ticket": "<SOURCE_TICKET>",
  "cve_id": "<CVE_ID>",
  "risk_level": "<HIGH|MEDIUM|LOW|NEEDS_REVIEW>",
  "method": "mcp | jira-cli | rest"
}
```

**Skipped:**
```json
{
  "skill": "report-to-jira",
  "status": "skipped",
  "reason": "<no_source_ticket | report incomplete | phase 3 did not finish>"
}
```

**Failed:**
```json
{
  "skill": "report-to-jira",
  "status": "failed",
  "source_ticket": "<SOURCE_TICKET>",
  "error": "<error message>",
  "fallback": "comment body displayed in session for manual posting"
}
```

---

## Integration with analyze-cve

Called from **Phase 4** of the [analyze-cve](../analyze-cve/SKILL.md) skill as the final step, after the report has been fully generated.

**Input:** complete report content, CVE ID, risk level, `SOURCE_TICKET` (from Phase 0.5)
**Output:** confirmation of comment and label posted to `SOURCE_TICKET`, or `status: skipped`/`failed` per above

Also called from **Phase 6** (`create-fix-pr`) for a short follow-up comment containing only the GitHub PR URL. That path uses the section below and must not replace this analysis comment or change labels.

---

## Follow-up: PR URL comment (Phase 6)

Post a **new** comment on `SOURCE_TICKET` after a remediation PR is opened. Invoked by [create-fix-pr](../create-fix-pr/SKILL.md).

**Do not run this path unless** `SOURCE_TICKET` is set, Phase 6 produced a `PR_URL`, and the user approved opening the PR.

**Do not:**
- Edit or delete the Phase 4 analysis comment
- Add or remove labels (`ai-cve-analyzed` stays as Phase 4 left it)
- Re-post the full analysis report
- Mention embargoed content (if `embargo_status = True`, abort)

### Comment body

```markdown
### Remediation PR opened

A pull request is open for this CVE.

- **PR:** [<PR_URL>](<PR_URL>)
- **CVE:** <CVE_ID>
- **Change:** <what Phase 5 changed — `<module>` <old> → <new> only for a dependency bump; otherwise a short source/config summary>
- **Base branch:** <BASE_BRANCH>
```

### Posting

Use the same procedure as Step 3 (MCP tool, then jira-cli/REST fallback).

On failure, print the comment in the session for manual paste. Do not treat a Jira follow-up failure as a GitHub PR failure — the PR itself is still a success.

**Return:**
```json
{
  "skill": "report-to-jira",
  "status": "success | skipped | failed",
  "mode": "pr_followup",
  "source_ticket": "<SOURCE_TICKET>",
  "pr_url": "<PR_URL>"
}
```
