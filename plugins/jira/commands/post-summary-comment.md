---
description: Post a PR summary or a plain note as a comment on a Jira ticket
argument-hint: <jira-ticket> [<pr-url>] [--format standup|detailed] [additional-context]
---

## Name
jira:post-summary-comment

## Synopsis
```
/jira:post-summary-comment <jira-ticket> [<pr-url>] [--format standup|detailed] [additional-context]
/jira:post-summary-comment <jira-ticket> "<note>"
/jira:post-summary-comment <jira-ticket> --note <text>
```

## Description

The `jira:post-summary-comment` command posts a comment to a Jira ticket. It has two modes:

**PR summary mode** — when a GitHub PR URL is provided, the command summarizes the PR
and posts that summary as a structured Jira comment.

**Note mode** — when no PR URL is provided, the remaining text is posted verbatim as a plain comment. Useful for quick status updates, blockers, or freeform notes.

**Local-first approach (PR mode):** if the PR's branch is already present in the local
git repository, all diff and commit data is read directly from git — no GitHub API calls
needed for that data. Only PR metadata that exists exclusively on GitHub (title, body,
review state) is fetched remotely. This makes the command fast and offline-friendly.

This command is useful for:
- Keeping Jira tickets updated with progress from linked PRs without manual copy-paste
- Dropping a quick status note or blocker comment on a ticket without linking a PR
- Providing stakeholders with a readable summary of code changes directly in Jira

Authentication uses the `JIRA_API_TOKEN` environment variable (Atlassian API token).
If the Atlassian MCP server is configured, it is preferred; otherwise the command falls
back to the Jira REST API via `curl`.

**Summary formats (PR mode only):**

| Format | When to use | What's included |
|--------|-------------|-----------------|
| `standup` | Most day-to-day updates *(default)* | Status line + what/why paragraph |
| `detailed` | Complex PRs, post-mortems, full audit trail | Description, key changes, diff highlights |

Default is `standup` when `--format` is omitted.

**Usage Examples:**

1. **PR summary — standup (default):**
   ```
   /jira:post-summary-comment OCPBUGS-12345 https://github.com/openshift/ci-tools/pull/4321
   ```

2. **PR summary — detailed breakdown:**
   ```
   /jira:post-summary-comment OCPBUGS-12345 https://github.com/openshift/ci-tools/pull/4321 --format detailed
   ```

3. **PR summary with extra context:**
   ```
   /jira:post-summary-comment DPTP-1234 https://github.com/openshift/ci-tools/pull/4321 "Fixes the flaky test introduced in 4.15 branch"
   ```

4. **Plain note — no PR needed (implicit):**
   ```
   /jira:post-summary-comment DPTP-1234 "Blocked on cluster provisioning, resuming tomorrow"
   ```


## Implementation

### 🔍 Phase 1: Validate Inputs and Detect Mode

1. **Check required argument**:
   - `$1` (jira-ticket): must match pattern `[A-Z]+-[0-9]+`
   - If missing or malformed, print usage and exit

2. **Detect mode** by inspecting arguments:
   - If `--note <text>` flag is present anywhere → **note mode** using the flag value (skips Phases 3-PR and 4)
   - Else if `$2` matches `https://github.com/{org}/{repo}/pull/{number}` → **PR summary mode**
     - Parse `ORG`, `REPO`, `PR_NUMBER` from the URL
     - Remaining arguments are `--format` flag and/or `additional-context`
   - Else if `$2` is absent or is plain text (not a URL) → **note mode**
     - Treat all remaining arguments (everything after `$1`) as the note text
   - In note mode: skip Phases 3 and 4 entirely

3. **Check `gh` CLI availability** *(PR mode only)*:
   ```bash
   command -v gh >/dev/null 2>&1 || { echo "gh CLI not found. Install from https://cli.github.com/"; exit 1; }
   gh auth status >/dev/null 2>&1 || { echo "gh CLI not authenticated. Run: gh auth login"; exit 1; }
   ```

4. **Check Jira authentication**:
   - Prefer MCP tool `mcp__atlassian__jira_get_issue` — if available use MCP path throughout
   - Otherwise require `JIRA_API_TOKEN` env var (and optionally `JIRA_USERNAME`)
   - If neither available, print:
     ```
     Jira authentication not configured.
     Set JIRA_API_TOKEN (and optionally JIRA_USERNAME) or configure the Atlassian MCP server.
     ```
   - Exit if no auth method found

### 📋 Phase 2: Fetch Jira Issue

Confirm the ticket exists and retrieve its summary to include in the comment header.

**MCP path:**
```python
issue = mcp__atlassian__jira_get_issue(issue_key="<jira-ticket>")
issue_summary = issue["fields"]["summary"]
issue_status  = issue["fields"]["status"]["name"]
```

**curl fallback:**
```bash
curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
  "https://redhat.atlassian.net/rest/api/2/issue/$1?fields=summary,status"
```

If the ticket is not found (404), exit with:
```
Jira ticket $1 not found. Verify the issue key and your credentials.
```

### 📝 Phase 3 (note mode): Build Comment

Skip to Phase 5 with the note text as the comment body. Post it as plain text — no Jira
wiki markup headers or structure added. Preserve the user's text exactly as written.

```
<note text verbatim>
```

---

### 🐙 Phase 3 (PR mode): Fetch PR Details (local-first)

Use local git data whenever the branch is present; fall back to the GitHub API only for
what git cannot provide.

#### 3a. Detect local branch

Parse `$2` to extract `HEAD_BRANCH` (the PR's source branch). Common patterns in the PR URL
do not contain the branch name, so attempt detection in this order:

1. **Remote-tracking ref** — fetch silently and check:
   ```bash
   git fetch origin pull/$PR_NUMBER/head:pr-$PR_NUMBER --quiet 2>/dev/null
   LOCAL_REF="pr-$PR_NUMBER"
   ```
   Where `origin` (or `upstream`) is the remote pointing to `$ORG/$REPO`
   (e.g., `https://github.com/$ORG/$REPO.git`). Identify the correct remote
   with `git remote -v` if needed.

2. **Already-checked-out branch** — if current `HEAD` or any local branch matches a recent
   push that introduced commits not on the base:
   ```bash
   git branch --list | grep -q "pr-$PR_NUMBER" && LOCAL_REF="pr-$PR_NUMBER"
   ```

3. **Explicit branch name from `gh`** — if steps 1–2 fail, fetch only the branch name
   (single lightweight API call):
   ```bash
   HEAD_BRANCH=$(gh pr view $PR_NUMBER --repo $ORG/$REPO --json headRefName -q .headRefName)
   git fetch origin $HEAD_BRANCH:$HEAD_BRANCH --quiet 2>/dev/null && LOCAL_REF="$HEAD_BRANCH"
   ```

Set `LOCAL_AVAILABLE=true` if `LOCAL_REF` was resolved, `false` otherwise.

#### 3b. Determine base ref

```bash
BASE_REF=$(git merge-base origin/main $LOCAL_REF 2>/dev/null \
           || git merge-base origin/master $LOCAL_REF 2>/dev/null)
```

If `LOCAL_AVAILABLE=false`, derive base from GitHub metadata (step 3d).

#### 3c. Local git data (used when `LOCAL_AVAILABLE=true`)

All of the following are read from local git — no API calls:

1. **Commit list:**
   ```bash
   git log --oneline $BASE_REF..$LOCAL_REF
   ```

2. **Diff stats (files changed, additions, deletions):**
   ```bash
   git diff --stat $BASE_REF..$LOCAL_REF
   ```

3. **Full diff (abridged to first 200 lines for analysis):**
   ```bash
   git diff $BASE_REF..$LOCAL_REF | head -200
   ```

4. **Author and timestamps:**
   ```bash
   git log $BASE_REF..$LOCAL_REF --format="%an <%ae>" | sort -u
   ```

#### 3d. GitHub metadata (always fetched — not in git)

The following exist only on GitHub and require one `gh` call regardless of local availability:

```bash
gh pr view $PR_NUMBER --repo $ORG/$REPO \
  --json number,title,state,author,body,url,baseRefName,reviewDecision,labels
```

Fields used:
- `title` — PR headline for the comment header
- `body` — PR description (the "why"); supplements commit messages
- `state` — Open / Merged / Closed
- `reviewDecision` — APPROVED / CHANGES_REQUESTED / REVIEW_REQUIRED
- `labels` — e.g. `do-not-merge`, `approved`

If `LOCAL_AVAILABLE=false` also fetch diff and commits via:
```bash
gh pr view $PR_NUMBER --repo $ORG/$REPO --json commits,additions,deletions,changedFiles
gh pr diff $PR_NUMBER --repo $ORG/$REPO | head -200
```

### 🤖 Phase 4: Generate PR Summary

Parse `--format` flag from arguments (default: `standup`). Produce Jira wiki markup so the
comment renders correctly. Apply format rules below.

**Quality rules (all formats):**
- Language factual and neutral — no filler phrases
- Technical terms, file paths, identifiers must be exact
- Code references use Jira `{{monospace}}` formatting
- If PR body is empty, derive context from commits and diff only

#### Format: `standup` *(default)*

Concise update covering the what and why. No commit list, no diff details, no file breakdown.

```
h3. PR [#<number> <title>|<PR URL>]

*Status:* <Open|Merged|Closed> · *Author:* <author> · *Review:* <decision>
*Changes:* +<additions>/-<deletions> across <N> file(s)

<2–3 sentence plain-language description of purpose and approach,
 derived from PR body and commit messages. Focus on the "why".
 Do not reproduce PR body verbatim.>

<If additional-context provided:>
*Context:* <additional-context>

----
```

---

#### Format: `detailed`

Full audit trail. Use for complex PRs, post-mortems, or when reviewers need the complete
picture without opening GitHub.

```
h2. PR Summary: [#<number> <title>|<PR URL>]

*Status:* <Open|Merged|Closed> · *Branch:* {{<head>}} → {{<base>}}
*Author:* <author> · *Review:* <decision> · *Labels:* <labels or none>
*Changes:* +<additions>/-<deletions> across <changedFiles> file(s)

----

h3. What this PR does

<3–5 sentence description covering purpose, approach, and key technical decisions.
 Synthesised from PR body, commit messages, and diff. Do not quote PR body verbatim.>

h3. Key changes

<File-by-file or area-by-area breakdown. Group related changes.
 Maximum 10 bullets. For each: path in monospace + what changed and why.>
* {{cmd/pod-scaler/main.go}} — added {{--dry-run}} flag; skips GCS writes when set
* {{pkg/controller/reconciler.go}} — nil-guard on lease before status update
* {{test/e2e/pod_scaler_test.go}} — integration test covering the new flag

h3. Diff highlights

<Notable patterns from the diff: error handling additions, API surface changes,
 new test assertions, config flag wiring. 3–6 bullets max. Skip if diff is trivial.>
* Added {{if hcp == nil \{ return \}}} guard in three controller methods
* New E2E assertion verifies GCS write count is 0 under {{--dry-run}}

<If additional-context provided:>
h3. Additional context

<additional-context verbatim>

----
```

### 🔒 Phase 5: Security Scan

Before posting, scan the generated comment text for credentials or secrets:
- API tokens, keys, passwords (patterns: `sk_`, `ghp_`, `AKIA`, `-----BEGIN`)
- kubeconfig or certificate PEM blocks
- Base64-encoded blobs longer than 64 chars

If found: stop, report the pattern type (not the value), and ask the user to sanitize.

### 💬 Phase 6: Post Comment to Jira

**MCP path (preferred):**
```python
mcp__atlassian__jira_add_comment(
    issue_key="<jira-ticket>",
    comment_body="<generated comment>"
)
```

**curl fallback:**
```bash
PAYLOAD=$(jq -n --arg body "$COMMENT" '{"body": $body}')
curl -s -X POST \
  -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  "https://redhat.atlassian.net/rest/api/2/issue/$1/comment"
```

### 📤 Phase 7: Display Confirmation

On success, print:

**PR mode:**
```
✓ Comment posted to $1

  Ticket : <issue summary>
  PR     : <PR title> (#<number>)
  URL    : https://redhat.atlassian.net/browse/$1
```

**Note mode:**
```
✓ Note posted to $1

  Ticket : <issue summary>
  URL    : https://redhat.atlassian.net/browse/$1
```

## Arguments

- **$1 – jira-ticket** *(required)*
  Jira issue key (e.g., `OCPBUGS-12345`, `DPTP-1234`).

- **$2 – pr-url** *(optional)*
  Full GitHub pull request URL (e.g., `https://github.com/openshift/ci-tools/pull/4321`).
  When omitted, the command runs in **note mode** and posts the remaining text as a plain
  comment without generating a PR summary.

- **--format** *(optional, default: `standup`, PR mode only)*
  Controls comment verbosity. Accepted values:
  - `standup` — status line + concise what/why paragraph *(default)*
  - `detailed` — full breakdown: description, key changes, diff highlights

- **--note \<text\>** *(optional; forces note mode)*
  Provide the note text explicitly via flag. When present, the command enters **note mode**
  immediately (Phases 3-PR and 4 are skipped) regardless of other arguments.
  Example: `/jira:post-summary-comment DPTP-1234 --note "Blocked on cluster provisioning, resuming tomorrow"`

- **additional-context / note** *(optional in PR mode, the comment body in note mode)*
  - PR mode: free-text appended to the generated summary
  - Note mode: the entire comment posted verbatim to Jira

## Return Value

- **Comment URL**: `https://redhat.atlassian.net/browse/<jira-ticket>` — navigate to see
  the posted comment
- **PR title**: Confirmed PR title used in the comment header
- **Character count**: Length of the posted comment (Jira has a ~32 KB limit)

## Error Handling

### Missing or malformed arguments

```
Usage:
  /jira:post-summary-comment <jira-ticket> <pr-url> [--format standup|detailed] [context]
  /jira:post-summary-comment <jira-ticket> "<note>"

  jira-ticket   Required. Format: PROJECT-NUMBER (e.g., OCPBUGS-12345)
  pr-url        Optional. https://github.com/{org}/{repo}/pull/{number}
                If omitted, posts the remaining text as a plain note.
  --format      Optional (PR mode only). standup (default) | detailed
  context       Optional in PR mode. Plain text appended to the summary.

Examples:
  /jira:post-summary-comment OCPBUGS-12345 https://github.com/openshift/ci-tools/pull/4321
  /jira:post-summary-comment OCPBUGS-12345 https://github.com/openshift/ci-tools/pull/4321 --format detailed
  /jira:post-summary-comment DPTP-1234 https://github.com/openshift/ci-tools/pull/4321 "extra context"
  /jira:post-summary-comment DPTP-1234 "Blocked on cluster provisioning, resuming tomorrow"
  /jira:post-summary-comment DPTP-1234 --note "Blocked on cluster provisioning, resuming tomorrow"
```

### Jira ticket not found

```
Jira ticket OCPBUGS-99999 not found.
Verify the issue key exists at https://redhat.atlassian.net/browse/OCPBUGS-99999
and that your JIRA_API_TOKEN has read access.
```

### PR not accessible

```
Unable to fetch PR https://github.com/openshift/ci-tools/pull/4321.
Verify the PR exists and that gh CLI is authenticated with read access to openshift/ci-tools.
Run: gh auth status
```

### Comment too large

If the generated comment exceeds 30,000 characters:
1. Truncate the diff section first
2. If still too large, truncate commits to 5
3. If still too large, shorten the "Key changes" and "What this PR does" sections
4. Add a note at the bottom: `_Comment truncated to fit Jira's size limit._`

### Post failure

```
Failed to post comment to $1.
HTTP status: <status>

The generated comment is shown below so you can post it manually:
---
<comment text>
---
```

## Prerequisites

- **`git`** — always required; used for local diff/commit data when the branch is present
- **`gh` CLI** — installed and authenticated (`gh auth login`); required only for:
  - PR metadata (title, description, review state) — always one call
  - Diff + commits — only when the branch is **not** available locally
- **Jira authentication**: one of:
  - Atlassian MCP server configured (preferred)
  - `JIRA_API_TOKEN` environment variable set (Atlassian Cloud API token)
  - Optionally `JIRA_USERNAME` (email) if using Basic auth

**Offline / no-GitHub scenario:** if you have the branch locally and skip `gh` entirely,
the command will still generate a full diff + commit summary. Only the PR title and review
state will be missing from the comment — everything else comes from git.

## See Also

- `jira:create-release-note` — Generate and post a structured release note from a bug and its PRs
- `jira:solve` — Analyze a Jira issue and create a PR to solve it
- `git:commit-suggest` — Generate a conventional commit message from staged changes
- `code-review:pr` — Review a PR for quality and security issues
