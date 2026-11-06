---
name: rox-backport
description: Use when someone asks to backport or cherry-pick a PR to release branches of a stackrox/* repository. Drives the full ROX backport flow — fix-version consolidation on the original bug (no Jira clones), one cherry-pick PR per branch, campaign monitoring — using the deterministic rox_backport_* tools.
---

## Name
acs:rox-backport

## Synopsis
```text
/acs:rox-backport <PR> <branches...>
```

# ROX backport (coordinator playbook)

Use when someone asks to backport or cherry-pick a PR to `release-*`
branches of a `github.com/stackrox/*` repository, in Slack or in a GitHub
mention on the PR.

## What the process is (so you can explain it)

1. **No Jira clones.** Unlike the OpenShift backport process, ROX backports
   reference the ORIGINAL ROX bug throughout. The appropriate `X.Y.Z` fix
   version is added to the original bug's Fix Version/s field for each
   target branch (preserving existing values, no duplicates).
2. **One PR per branch**, cherry-picked from the parent PR's commits with
   `git cherry-pick -x`, titled `[release-X.Y] ROX-NNN: …`, body starting
   `This is an automated cherry-pick of #N` and referencing the original
   ROX bug key.
3. **`chai-backport` label** is added to the original bug when starting a
   campaign.
4. **Dynamic branch discovery.** Supported `release-X.Y` branches are
   discovered from the `stackrox/stackrox` repository, and the next
   unreleased Jira version per stream is inferred automatically.
5. A multi-branch request is a **set**: all PRs open together (or when the
   parent merges), never chained one-after-another. There are no
   clone-chain dependencies.

## Steps

### Phase 0 — plan and confirm (no writes)

1. `rox_backport_plan(pr, branches)` — blockers stop you. Show the
   `summary` (branches, fix versions, existing PRs, notes) and confirm
   with the requester (Slack reply / GitHub comment).
2. If `warnings` say the requester's Rover profile links several GitHub
   accounts (or none), ask which account the PRs should `/assign` and pass
   `requester_github_login=` to the plan and to the fix-version operation
   from then on.

### Phase 1 — fix versions and label

`priv_rox_backport_add_fix_versions(host, repo, pr_number, branches)` — run
`check_proposal` first as usual. It records the campaign, then:
- Adds the appropriate `X.Y.Z` fix version to the original bug's Fix
  Version/s for each target branch.
- Adds the `chai-backport` label to the original bug.
- Returns `campaign_id` and `next`.

Report the results (added / already present per branch) and `warnings`.
If it returns `campaign_store_unavailable`, stop: nothing was written.
`campaign_exists`: another thread owns it; point the requester there.

### Phase 2 — per branch, one cherry-pick PR each

One pod per campaign (`rws_pod_create`, logical name = the campaign id,
environment `general_dev`); one background task at a time.

```
rox_backport_brief(campaign_id, branch)            # deterministic brief
rws_new_agent("<campaign_id>", "Cherry-pick for <branch> of <org/repo>#<N>; Jira <bug_key>.")
rws_goal_task("<campaign_id>",
  "Cherry-pick with this brief:\n<brief verbatim>\n"
  "Proof: git log of the pushed branch, per-file conflict notes, test evidence, GOAL_VERDICT.")
# → [RWS GOAL COMPLETE]
#   conflict / blocked verdict → phase stays `conflict`: report_progress(kind="concern"),
#     tell the requester which files, keep the pushed partial branch; do NOT open a PR
#   achieved →
priv_scm_ensure_fork(host, repo)
priv_scm_create_change_request(host, repo, source_branch=<head_branch>, target_branch=<branch>,
                               title=<pr_title>, description=<pr_body>, head_repo=<fork_repo>)
rox_backport_record_pr(campaign_id, branch, <new PR>)   # binds and flags monitoring
# next branch: rws_new_agent, then repeat
```

Rules:
- Pass `pr_title` and `pr_body` unchanged — they reference the original ROX
  bug key, never a clone key.
- Never open a PR for a branch whose brief errored.
- A conflict on one branch never stops the others.
- Do not open drafts.
- Never create Jira clones or post `/jira backport` or `/cherrypick`.

### Phase 3 — monitoring (autonomous turns)

- **`[GITHUB PR UPDATE]`** on a backport PR: the normal PR-response rules
  apply (trust tags, 5-minute settling, batch fixes). Fixes run on the
  same logical pod (`rws_goal_task`; recreate the pod under the same name
  if it expired). One turn may carry several PRs of the campaign; handle
  them together.
- **`[ROX BACKPORT UPDATE]`** from the watcher: read CHANGES and DIGEST.
  "every branch is merged" → final report. "closed without merging" → a
  person decided; never reopen.
- **`rox_backport_status`** answers "where is this?" — per branch
  `next_action`: `add_fix_versions`, `open_pr`, `await_merge`, `done`,
  `needs_human`.

## Handling cherry-pick conflicts

When `rws_goal_task` reports a conflict:
1. Set the branch phase to `conflict` (the brief does this implicitly).
2. Report to the requester which files conflict and why (the worker's
   per-file notes).
3. Keep the pushed partial branch — do NOT delete it.
4. Do NOT open a PR for a conflicted branch.
5. The requester resolves the conflict manually and re-runs the backport
   for that branch, or opens their own PR.

## Handling CI failures

When a cherry-pick PR fails CI:
1. Read the CI failure logs from the PR checks.
2. If the failure is related to the cherry-pick (test changes, build
   breakage): attempt a fix on the same pod, push to the same branch.
3. If the failure is pre-existing (flaky test, infrastructure issue):
   report it to the requester and suggest a `/retest` — but at most a
   few times per PR per day.
4. Never force-merge a PR with failing required checks.

## Handling review feedback

When a reviewer comments on a backport PR:
1. Address the review comments on the same pod if they are mechanical
   (style, minor fixes).
2. For substantive changes that alter the fix: report to the requester
   for their decision.
3. Batch all fixes and push once — do not push after each individual
   comment.

## Exceptions you recognize, humans decide

- A non-ROX project key in the PR title: the plan blocks; explain that
  OCPBUGS bugs use the `openshift_backport` workflow instead.
- Code that no longer exists on the target branch: the campaign can
  start from the newest affected branch; report the gap.
- Releases that already contain the fix: the fix version may already be
  present; the plan shows this as "already present" and continues.
- The requester asks to skip a branch: use `rox_backport_cancel` for the
  whole campaign only if all branches should be dropped; otherwise just
  do not process the skipped branch.

## Ending turns

Slack thread: `send_response` with what happened and what a person must do
next. Autonomous turns with nothing to add: `no_action_required`. Campaign
state is durable (Firestore); a pod restart loses nothing — re-run
`rox_backport_status` and continue.
