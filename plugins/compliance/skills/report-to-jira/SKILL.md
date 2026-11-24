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
- `AUTO_APPROVE` (`yes`/`no`, default `no`) — governs the Step 3b visibility-downgrade fallback prompt

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

> **Credential rule:** Never print, echo, or log any token, key, or password value. Reference credentials only via environment variable names. Never interpolate a credential value into a logged string.

CVE analysis reports contain security-sensitive findings. Prefer restricted (internal-only) visibility when the Jira instance supports it.

Write the Step 2 comment to a private temporary file once, before any posting path — every method below reads this file. Write the report with a file-writing tool, not a shell heredoc, so report text is never interpreted as shell source:

```bash
COMMENT_FILE=$(mktemp /tmp/cve-report-comment.XXXXXX)
chmod 600 "${COMMENT_FILE}"
```

Keep the file for the whole posting workflow and remove it in the cleanup step at the end of Step 3.

### Step 3a: Direct REST API with restricted visibility (attempt first, if credentials are configured)

If a token is available in the environment, try the REST API directly — it remains the preferred restricted-visibility path. The Step 3b MCP fallback can carry the same restriction via `commentVisibility`, so a REST failure no longer forces an unrestricted comment. Try **both** auth schemes and let the HTTP response decide which one worked — credentials may be exposed differently depending on the runtime (a local shell with a bare token vs. a CI/RWS runner with a mounted service-account email+token pair):

1. **Basic auth (email + API token)** — the scheme most Jira Cloud instances actually expect for API tokens. Used when both `JIRA_EMAIL` and a token are available.
2. **Bearer token only** — fallback for runtimes that expose only a bare token env var with no associated email.

```bash
JIRA_API_TOKEN="${JIRA_API_TOKEN:-${JIRA_TOKEN:-${ATLASSIAN_API_TOKEN:-}}}"
JIRA_BASE_URL="${JIRA_URL:-}"
JIRA_EMAIL="${JIRA_EMAIL:-}"

if [ -n "${JIRA_API_TOKEN}" ] && [ -n "${JIRA_BASE_URL}" ]; then
  case "${JIRA_BASE_URL}" in
    https://*) ;;
    *) echo "ERROR: JIRA_BASE_URL must use HTTPS (got: ${JIRA_BASE_URL})"; rm -f "${COMMENT_FILE:-}"; exit 1 ;;
  esac

  COMMENT_BODY=$(cat "${COMMENT_FILE}")
  RESPONSE_FILE=$(mktemp /tmp/jira-post-response.XXXXXX)
  chmod 600 "${RESPONSE_FILE}"
  COMMENT_JSON_BODY=$(echo "${COMMENT_BODY}" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))")

  post_comment() {
    # $1 = auth mode: "basic" (email+token) or "bearer" (token only)
    # Build the Authorization header inside this function after set +x so
    # credentials never appear in traced argv when post_comment is invoked.
    local auth_mode="$1" curl_cfg http_code auth_header
    curl_cfg=$(mktemp)
    chmod 600 "${curl_cfg}"
    trap 'rm -f "${curl_cfg}"' RETURN EXIT INT TERM
    [[ $- == *x* ]] && local _was_tracing=true || local _was_tracing=false
    set +x
    if [ "${auth_mode}" = "basic" ]; then
      auth_header="Basic $(printf '%s:%s' "${JIRA_EMAIL}" "${JIRA_API_TOKEN}" | base64 | tr -d '\n')"
    else
      auth_header="Bearer ${JIRA_API_TOKEN}"
    fi
    printf 'header = "Authorization: %s"\n' "${auth_header}" > "${curl_cfg}"
    unset auth_header
    $_was_tracing && set -x || true

    http_code=$(curl -s -o "${RESPONSE_FILE}" -w "%{http_code}" \
      --connect-timeout 15 \
      --max-time 60 \
      -X POST \
      -K "${curl_cfg}" \
      "${JIRA_BASE_URL}/rest/api/2/issue/${SOURCE_TICKET}/comment" \
      -H "Content-Type: application/json" \
      --data-binary @- << EOF
{
  "body": ${COMMENT_JSON_BODY},
  "visibility": {
    "type": "group",
    "value": "Red Hat Employee"
  }
}
EOF
)
    echo "${http_code}"
  }

  HTTP_STATUS=""
  if [ -n "${JIRA_EMAIL}" ] && [ -n "${JIRA_API_TOKEN}" ]; then
    echo "Attempting REST post with Basic auth (email + token)..."
    HTTP_STATUS=$(post_comment basic)
  fi

  # Only retry with the other auth scheme when Basic wasn't attempted at all
  # (no JIRA_EMAIL) or came back with an actual auth failure (401/403). This
  # POST is not idempotent: retrying it for every other status (400, 429,
  # 5xx, or curl's own "000") risks creating a duplicate comment if the first
  # request was actually accepted server-side but the response was lost or
  # malformed. Any other failure goes straight to Step 3b instead of retrying.
  if { [ -z "${HTTP_STATUS}" ] || [ "${HTTP_STATUS}" = "401" ] || [ "${HTTP_STATUS}" = "403" ]; } && [ -n "${JIRA_API_TOKEN}" ]; then
    echo "Attempting REST post with Bearer auth..."
    HTTP_STATUS=$(post_comment bearer)
  fi

  echo "Jira API HTTP status: ${HTTP_STATUS:-none attempted}"
  if [ "${HTTP_STATUS}" = "201" ]; then
    echo "✓ Comment posted with restricted visibility"
  else
    echo "✗ REST API failed (HTTP ${HTTP_STATUS:-n/a}) — will fall back to MCP tool"
    cat "${RESPONSE_FILE}" 2>/dev/null || true
  fi
fi
```

> The `visibility` object above targets `redhat.atlassian.net`. On other Jira Cloud instances, adjust `type`/`value` to match an equivalent internal-only group. If no equivalent internal group exists, skip the REST post and continue to Step 3b — do not post unrestricted from here.

- IF HTTP 201 (either scheme) → done. Skip Step 3b.
- IF credentials are not configured → continue to Step 3b.
- IF HTTP 401/403 on both schemes (or Basic wasn't attempted and Bearer also fails) → credentials not available or insufficient permissions; continue to Step 3b.
- IF the final REST attempt (either scheme) returns any other status (400, 429, 5xx, curl error `000`) → do **not** retry with the other scheme (the POST is not idempotent) — go directly to Step 3b.
- Never print `JIRA_API_TOKEN`, `JIRA_EMAIL`, the computed `BASIC_AUTH` value, or the contents of `${curl_cfg}` — only the HTTP status code and response body (which contains no credentials).

5xx and curl `000` leave the write's outcome unknown. Before posting via MCP, check for an existing comment: call `listJiraIssueComments`, paginating with `startAt` until `isLast` is true, and compare each body against the exact Step 2 comment — a match means the report is already on the ticket, so do not repost. A failed or incomplete read, or a restricted comment this account cannot see, is also an unknown outcome: take the Step 4 failure path instead of reposting.

---

### Step 3b: MCP tool (default / fallback)

```python
addOrEditJiraIssueComment(
    issueIdOrKey=SOURCE_TICKET,
    commentBody="<constructed comment from Step 2>",
    contentFormat="markdown",
    commentVisibility={"type": "group", "value": "Red Hat Employee"}
)
```

> The MCP tool supports restricted visibility via `commentVisibility` (`{"type": "group"|"role", "value": "<name>"}`). Pass the same internal group Step 3a uses — `Red Hat Employee` on `redhat.atlassian.net`; on other instances pick an equivalent group per the note above.

Any post without the internal-only restriction is gated by `AUTO_APPROVE`, regardless of whether Step 3a was attempted:

- Equivalent internal group exists → post via MCP with `commentVisibility`; no approval needed.
- No equivalent group → the comment is visible to everyone with ticket access:
  - `AUTO_APPROVE=no` → **ask the user**:
    ```
    ⚠️ No equivalent internal group exists on this instance for `commentVisibility`. The comment will be visible to everyone with ticket access. Proceed?
    ```
    If the user declines → display the comment body for manual posting.
  - `AUTO_APPROVE=yes` → post and **clearly log** that the comment went out unrestricted.
- MCP rejects the post → only a **confirmed visibility-related rejection** (the error names `commentVisibility` or an invalid group/role, and no comment was created) may fall back to an unrestricted post, under the same `AUTO_APPROVE` rules. Rate limits, server errors, timeouts, and ambiguous failures are plain errors: take the Step 4 failure path, keep `commentVisibility` on any retry, and retry only when the original write is known not to have succeeded. Do not switch to jira-cli to bypass this rule.

**Fallback — jira-cli** (if MCP is also unavailable):

```bash
jira issue comment add "${SOURCE_TICKET}" \
  --body "$(cat "${COMMENT_FILE}")" \
  --no-input
```

> `jira-cli` posts with no visibility restriction. Apply the unrestricted-post rule above before **every** `jira-cli` post: ask under `AUTO_APPROVE=no`, proceed and log under `AUTO_APPROVE=yes`.

**Cleanup** — when the posting workflow finishes, on success or failure, remove the temporary files:

```bash
rm -f "${COMMENT_FILE}" "${RESPONSE_FILE:-}"
```

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
  "method": "rest | mcp | jira-cli"
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

**Input:** complete report content, CVE ID, risk level, `SOURCE_TICKET` (from Phase 0.5), `AUTO_APPROVE`
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

Use the same procedure as Step 3 (REST with restricted visibility first if configured, MCP/jira-cli fallback otherwise).

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
