---
description: Send reminder comments on stale high-priority assigned PRs
argument-hint: "[--dryrun] [--days 7] [--priority High,Urgent]"
---

## Name

nid-team:nudge-prs

## Synopsis

```bash
/nid-team:nudge-prs [--dryrun] [--days 7] [--priority High,Urgent]
```

## Description

Sends automated reminder comments on PRs that are assigned (Status=Assigned), high priority (PR Priority=High or Urgent), and have had no human activity for a configurable number of days. Determines whether the author or reviewer is blocking and @-mentions them in the comment.

## Implementation

Run the nudge script:

```bash
plugins/nid-team/scripts/pr-dashboard/nudge-prs.sh [--dryrun] [--days 7] [--priority High,Urgent]
```

### Arguments

| Argument | Default | Description |
|---|---|---|
| `--dryrun` | off | Print the comments without posting them |
| `--days` | 7 | Days of inactivity threshold |
| `--priority` | High,Urgent | Comma-separated PR Priority values to nudge |

### What counts as human activity

- Author pushed commits
- Human review comment (not CodeRabbit or bots)
- Human PR comment (not bots, not Prow commands like /assign /label /hold)

Bot comments and mechanical Prow commands do NOT reset the inactivity clock.

### What the comment includes

- How long the PR has been open
- Primary and Secondary Reviewer @-mentions
- Last human activity (who and when)
- Who is blocking (author or reviewer) and why
- needs-rebase and do-not-merge/hold warnings
- lgtm/approved label status

## Examples

```bash
# Dry run — see what would be posted
/nid-team:nudge-prs --dryrun

# Post reminders for High and Urgent PRs inactive 7+ days
/nid-team:nudge-prs

# Custom threshold — 14 days, all priorities
/nid-team:nudge-prs --days 14 --priority High,Urgent,Medium
```

## Notes

- Only nudges PRs with Status=Assigned on the dashboard
- Always use `--dryrun` first to review the comments before posting
- Does not nudge the same PR twice per run (idempotent within a run)
- Does not track previous nudges — running it again will post another comment
