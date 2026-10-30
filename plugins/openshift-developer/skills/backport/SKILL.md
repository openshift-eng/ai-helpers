---
name: backport
description: Use when someone asks to backport or cherry-pick a PR to release branches of an openshift/* repository. Drives the full OpenShift backport flow — Jira clone chain, one cherry-pick PR per branch, chain progression — using the deterministic ocp_backport_* tools.
---

## Name
openshift-developer:backport

## Synopsis
```text
/openshift-developer:backport <PR> <branches...>
```

# OpenShift backport (coordinator playbook)

Use when someone asks to backport or cherry-pick a PR to `release-*`
branches of a `github.com/openshift/*` repository, in Slack or in a GitHub
mention on the PR.

## What the process is (so you can explain it)

1. One bug per release. The fix's OCPBUGS bug is cloned once per target
   branch; each clone is **blocked by** the clone for the next-newer branch
   (`Blocks` links), so a `release-4.20` PR is only valid once the
   `release-4.21` bug is VERIFIED. The jira-lifecycle-plugin validates PRs
   against this chain and labels them `jira/valid-bug` / `jira/invalid-bug`.
2. One PR per branch, cherry-picked from the parent PR's commits with
   `git cherry-pick -x`, titled `[release-4.20] OCPBUGS-<clone>: …`, body
   starting `This is an automated cherry-pick of #N`.
3. Merge needs, per Tide on release branches: `lgtm`, `approved`,
   `jira/valid-bug`, `backport-risk-assessed` (a z-stream approver's risk
   sign-off) and `verified` (QE or a collaborator's `/verified by`). The bot
   never applies any of these.
4. A multi-branch request is a **set**: all PRs open together (when the
   parent merges, or immediately if asked), never chained one-after-another.

## Steps

1. `ocp_backport_plan(pr, branches)` — blockers stop you; a chain gap means
   offering the completed branch list. Show the `summary`; confirm (Slack
   reply / GitHub comment).
2. `priv_ocp_backport_ensure_clones(host, repo, pr_number, branches)` — the
   Jira chain. Report created vs reused clones. Parent not merged → wait for
   the merge turn.
3. Per branch, newest first, one pod (`rws_pod_create` named after the
   campaign): `ocp_backport_brief` → `rws_new_agent` → `rws_goal_task` running
   `/openshift-developer:cherry-pick` with the brief → on success
   `priv_scm_ensure_fork` + `priv_scm_create_change_request` with the brief's
   title/body unchanged → `ocp_backport_record_pr`. Conflicts park the branch
   (`report_progress(kind="concern")`, tell the requester which files).
4. Then monitor: PR-activity turns (reviews, CI) and `[BACKPORT UPDATE]`
   turns from the watcher. `ocp_backport_status` gives each branch's
   `next_action`; `ocp_zstream_approvers(repo)` names who can sign off.

## Exceptions you recognize, humans decide

- `jlp-no-clone` on the bug, a disallowed security level, a non-bug project
  in the title, `red-hat-storage`/DFBUGS: the plan blocks; explain.
- Code that no longer exists in master: the campaign can start from the
  newest affected branch; newer releases still get "presence" bugs.
- Releases that already contain the fix: clones still exist for QE to
  verify; moving them to ON_QA is a human ask you may relay only when told.
- Maintenance / EOL / EUS releases: the plan's lifecycle phase warning is the
  cue to point at engineering management + PM (or Sustaining Engineering).
