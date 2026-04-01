---
name: "classify-review-comment"
description: "Classify GitHub PR review comments by severity and topic. Use when the user wants to categorize, analyze, or understand patterns in code review feedback — whether for a single comment, a comment URL, or an entire pull request. Triggers on requests like 'classify this comment', 'categorize PR feedback', 'what kind of review comments does this PR have', or 'break down comments by severity'."
---

# Classify Review Comments

Classify GitHub pull request review comments into severity and topic categories. Works with a single comment (text), a GitHub comment URL, or an entire PR (classifies all comments).

This enables tracking review feedback patterns: what kinds of issues reviewers catch, how severe they are, and where AI-generated code needs the most improvement.

## Labels

**Read the labels file before classifying any comments:**

```text
config.json (in the same directory as this skill)
```

The labels file defines the **exact** set of valid values for `severity` and `topic`. You MUST select from these values — do not invent new labels. Each label includes a description and signal words or examples to guide your selection.

**Classification rule:** For each comment, find the single best-matching `severity` and single best-matching `topic` from the labels file. Match based on the label's description, signals/examples, and the comment content. Use `unclassified` only when no other label fits.

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
- CI bot notifications: authors like `openshift-ci-robot`, `openshift-ci[bot]`, `cwbotbot`, or any `*[bot]` author **not listed** in the `allowed_bots` section of config.json
- Comments matching any pattern in the `noise_patterns` section of config.json
- Auto-CC commands: `/auto-cc`

**Do classify** comments from:
- Human reviewers (all comments, including those directing bots)
- Any bot listed in `allowed_bots` in config.json (classify their substantive review comments — code issues, suggestions, questions)

## Classification Approach

For each comment:

1. **Read config.json** to load the valid severity and topic values
2. **Scan the comment body** for signal words and patterns that match label descriptions
3. **Select exactly one severity** — match the comment's urgency/tone to the severity descriptions and signals
4. **Select exactly one topic** — match the comment's subject matter to the topic descriptions and examples
5. **When ambiguous**, prefer the more specific label over `unclassified`
6. **When a comment spans multiple topics**, pick the primary one — what is the reviewer's main concern?

Additional classification rules:
- **Slash commands mixed with text** — if a comment has substantive text before a slash command (e.g., "good analysis\n/override ci/prow/e2e"), classify based on the substantive text, not the slash command
- **Comments directed at bots/AI** — classify by the underlying problem, not the fact that the recipient is a bot. "Fix the unit tests" is about test failures (`test_gap`), "rebase the PR" is a CI/process issue (`ci`), "push the changes" is a process failure (`process`). The topic should answer "what went wrong?" not "who is being told to fix it?"

## Output Format

### Single comment
```json
{
  "severity": "<value from config.json severity list>",
  "topic": "<value from config.json topic list>",
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
      "severity": "<value from config.json>",
      "topic": "<value from config.json>",
      "rationale": "Reviewer suggests moving variable declarations for consistency"
    }
  ],
  "summary": {
    "by_severity": {"nitpick": 1, "suggestion": 1, "required_change": 2, "question": 1},
    "by_topic": {"style": 1, "api_design": 1, "logic_bug": 2, "test_gap": 1}
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
{"severity": "required_change", "topic": "test_gap", "rationale": "Unit tests are failing — the bot made code changes without ensuring tests pass"}
```

**Comment:** "hypershift-jira-solve-ci - rebase the PR to fix the konflux issues"
```json
{"severity": "suggestion", "topic": "ci", "rationale": "PR needs rebasing to resolve CI pipeline issues — classify by the problem (CI), not the recipient (bot)"}
```

**Comment:** "hypershift-jira-solve-ci - this still needs fixed since the code did not get pushed"
```json
{"severity": "required_change", "topic": "process", "rationale": "Code changes were not committed/pushed — a process failure, not a code issue"}
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

**CodeRabbit issue flagged** (starting with `_Potential issue_ | _Critical_`):
```json
{"severity": "required_change", "topic": "logic_bug", "rationale": "CodeRabbit identified a critical code issue requiring attention"}
```
