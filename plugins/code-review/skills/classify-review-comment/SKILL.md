---
name: "classify-review-comment"
description: "Classify GitHub PR review comments by severity and topic. Use when the user wants to categorize, analyze, or understand patterns in code review feedback — whether for a single comment, a comment URL, or an entire pull request. Triggers on requests like 'classify this comment', 'categorize PR feedback', 'what kind of review comments does this PR have', or 'break down comments by severity'."
---

# Classify Review Comments

Classify GitHub pull request review comments into severity and topic categories. Works with a single comment (text), a GitHub comment URL, or an entire PR (classifies all comments).

This enables tracking review feedback patterns: what kinds of issues reviewers catch, how severe they are, and where AI-generated code needs the most improvement.

## Input Modes

### 1. Single Comment (text)

Classify a comment provided directly as text.

**Input:** The raw comment body.
**Output:** A single classification object.

### 2. Comment URL

Fetch a specific comment by its GitHub URL and classify it.

**URL formats supported:**
- `https://github.com/{owner}/{repo}/pull/{number}#issuecomment-{id}`
- `https://github.com/{owner}/{repo}/pull/{number}#discussion_r{id}`

**Fetch with:**
```bash
# Issue comment
gh api repos/{owner}/{repo}/issues/comments/{id} --jq '{author: .user.login, body: .body}'

# Review comment (discussion)
gh api repos/{owner}/{repo}/pulls/comments/{id} --jq '{author: .user.login, body: .body}'
```

### 3. Full PR

Fetch all comments on a PR, filter out noise, and classify each one.

**URL format:** `https://github.com/{owner}/{repo}/pull/{number}`

**Fetch with:**
```bash
# Issue-level conversation comments
gh api repos/{owner}/{repo}/issues/{number}/comments --paginate --jq '.[] | {id: .id, author: .user.login, body: .body}'

# Inline review comments
gh api repos/{owner}/{repo}/pulls/{number}/comments --paginate --jq '.[] | {id: .id, author: .user.login, body: .body}'
```

**Before classifying, filter out noise comments** (these carry no review signal):
- Pure slash commands: body starts with `/` followed by a command word (e.g., `/lgtm`, `/test e2e-aws`, `/approve`, `/retest`, `/cc`)
- CI bot notifications: authors like `openshift-ci-robot`, `openshift-ci[bot]`, `cwbotbot`, or any `*[bot]` author except `coderabbitai[bot]`
- CodeRabbit noise: "No actionable comments were generated", "Skipped: comment is from another GitHub bot"
- Auto-CC commands: `/auto-cc`

**Do classify** comments from:
- Human reviewers (all comments, including those directing bots)
- `coderabbitai[bot]` (substantive review comments and walkthrough summaries)
- `hypershift-jira-solve-ci[bot]` responding to review feedback (these show how the AI addressed the review)

## Severity Categories

Severity captures how urgent or blocking the feedback is.

| Severity | Description | Signal |
|----------|-------------|--------|
| `nitpick` | Cosmetic or stylistic preference — take it or leave it | "nit:", "minor:", optional wording |
| `suggestion` | Worth considering but not blocking merge | "consider", "might want to", "could" |
| `required_change` | Must be addressed before merge | "this will break", "bug", "needs to be fixed" |
| `question` | Reviewer is asking for clarification | "why", "what does", "can you explain" |
| `unclassified` | Meta-comments, acknowledgments, or doesn't fit above | "looks good", "thanks", process comments |

## Topic Categories

Topic captures what area of concern the comment addresses.

| Topic | Description | Examples |
|-------|-------------|---------|
| `style` | Code formatting, naming, organization, idioms | "rename `cnt` to `count`", "move vars to `var ()` block" |
| `logic_bug` | Incorrect logic, potential bugs, edge cases, panics | "this will panic if nil", "off-by-one", "case mismatch" |
| `test_gap` | Missing tests, test quality, coverage issues | "add a test for empty input", "test doesn't validate X" |
| `api_design` | API surface, interfaces, abstractions, contracts | "why is this exported?", "consider a different signature" |
| `documentation` | Missing docs, comments, READMEs, godoc | "missing godoc", "add a comment explaining why" |
| `ci` | CI triggers, test results, overrides, retests | "/test e2e-aws", "e2e failed on Teardown", CI status |
| `bot_instruction` | Directing a bot/AI to take action | "fix the unit tests", "rebase the PR", "push the changes" |
| `approval` | Approvals, LGTMs, sign-offs, acknowledgments | "/lgtm", "no changes requested", "LGTM" |
| `process` | Jira refs, duplicates, PR status, meta-discussion | "dup of #7727", Jira validation notices |
| `unclassified` | Doesn't fit other categories | Catch-all |

## Classification Approach

For each comment, determine severity and topic by reading the comment body and considering:

1. **The language used** — imperative ("fix this") vs suggestive ("consider") vs interrogative ("why?")
2. **The content focus** — what aspect of the code is being discussed?
3. **The author context** — a bot responding to feedback vs a human reviewing code
4. **Slash commands mixed with text** — if a comment has substantive text before a slash command (e.g., "good analysis\n/override ci/prow/e2e"), classify based on the substantive text, not the slash command

When a comment could fit multiple topics, pick the primary one — what is the reviewer's main concern?

## Output Format

### Single comment
```json
{
  "severity": "nitpick",
  "topic": "style",
  "rationale": "Brief one-line explanation of why this classification was chosen"
}
```

### Full PR
```json
{
  "pr": "https://github.com/openshift/hypershift/pull/7620",
  "total_comments": 15,
  "classified": 5,
  "filtered_noise": 10,
  "comments": [
    {
      "id": 2871360513,
      "author": "jparrill",
      "body_preview": "small nit: I would move the vars...",
      "severity": "nitpick",
      "topic": "style",
      "rationale": "Reviewer suggests moving variable declarations for consistency"
    }
  ],
  "summary": {
    "by_severity": {"nitpick": 1, "suggestion": 1, "required_change": 2, "question": 1},
    "by_topic": {"style": 1, "api_design": 1, "logic_bug": 2, "bot_instruction": 1}
  }
}
```

## Real-World Examples

These are from actual PRs in openshift/hypershift:

**Comment:** "small nit: I would move the vars `key`, `log` and `cloudName` to `var (` section just to be consistent."
```json
{"severity": "nitpick", "topic": "style", "rationale": "Reviewer suggests grouping variables for consistency — cosmetic, not functional"}
```

**Comment:** "Why not use NewARMClientOptions here for the clientOptions?"
```json
{"severity": "question", "topic": "api_design", "rationale": "Reviewer asks about API choice for client options construction"}
```

**Comment:** "This will panic if `items` is nil — needs a nil check before the loop"
```json
{"severity": "required_change", "topic": "logic_bug", "rationale": "Nil pointer dereference would cause runtime panic"}
```

**Comment:** "failing during `hypershift install`\n```\nClusterRoleBinding is invalid: roleRef.kind: Unsupported value\n```"
```json
{"severity": "required_change", "topic": "logic_bug", "rationale": "Installation fails due to missing required roleRef fields"}
```

**Comment:** "hypershift-jira-solve-ci - the unit test job is failing and needs fixed"
```json
{"severity": "required_change", "topic": "bot_instruction", "rationale": "Human directing AI bot to fix failing unit tests"}
```

**Comment:** "hypershift-jira-solve-ci - rebase the PR to fix the konflux issues"
```json
{"severity": "suggestion", "topic": "bot_instruction", "rationale": "Human directing AI bot to rebase — a process action, not a code issue"}
```

**Comment:** "`e2e-aws-4-21` failed on `Teardown` but due to uncleaned cloud resources, not VPC endpoint blocking the finalizer\n/override ci/prow/e2e-aws-4-21"
```json
{"severity": "suggestion", "topic": "ci", "rationale": "Reviewer explains CI failure root cause and overrides — substantive analysis before the slash command"}
```

**Comment:** "Oh no that's ok. I missed that part. No changes requested."
```json
{"severity": "unclassified", "topic": "approval", "rationale": "Reviewer withdrawing their earlier question — acknowledgment"}
```

**Comment:** "dup of https://github.com/openshift/hypershift/pull/7727"
```json
{"severity": "unclassified", "topic": "process", "rationale": "Marking PR as duplicate of another — process meta-comment"}
```

**Comment:** "The root cause of the CI failure in this PR has been identified. The fix in `rejectVpcEndpointConnections` doesn't work because of a **case mismatch** between AWS API responses and SDK v2 enum constants."
```json
{"severity": "required_change", "topic": "logic_bug", "rationale": "Detailed root cause analysis identifying a case mismatch bug"}
```

**CodeRabbit walkthrough summary** (long HTML comment starting with `<!-- walkthrough_start -->`):
```json
{"severity": "unclassified", "topic": "documentation", "rationale": "Automated PR summary providing overview of changes — informational, not actionable feedback"}
```

**CodeRabbit issue flagged** (starting with `_Potential issue_ | _Critical_`):
```json
{"severity": "required_change", "topic": "logic_bug", "rationale": "CodeRabbit identified a critical code issue requiring attention"}
```
