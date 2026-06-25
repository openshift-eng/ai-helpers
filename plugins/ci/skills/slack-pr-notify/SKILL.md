---
name: slack-pr-notify
description: Slack PR review notification with reviewer polling for CI
disable-model-invocation: true
---

# Slack PR Review Notification

Shell library that posts a Slack message when a CI job creates a PR. Polls for assigned reviewers (up to 2 minutes), maps GitHub usernames to Slack IDs, and mentions them. Safe to call unconditionally — skips silently when no webhook is configured, never fails the job. This skill exists only as a distribution mechanism — it is sourced by CI process scripts, not invoked by Claude.

## Prerequisites

- `gh` CLI authenticated against the upstream repo
- `curl`, `jq` available on the runner

## Usage

Source the script, set the required variables, and call `send_slack_notification`:

```bash
source /tmp/ai-helpers/plugins/ci/skills/slack-pr-notify/slack-pr-notify.sh

send_slack_notification "$PR_URL" "$PR_NUM"
```

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `SLACK_WEBHOOK_URL` | yes | — | Incoming webhook URL (empty to skip) |
| `JIRA_AGENT_UPSTREAM_REPO` | yes | — | Repo slug for `gh pr view` (e.g. `openshift/hypershift`) |
| `GITHUB_SLACK_MAP` | yes | — | JSON: `{"gh-user": "USLACKID", "backup-user": "UFALLBACK"}` |
| `SLACK_EMOJI` | no | `:robot:` | Message prefix emoji |
