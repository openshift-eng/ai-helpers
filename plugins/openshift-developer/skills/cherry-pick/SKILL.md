---
name: cherry-pick
description: Use when the coordinator dispatches a BACKPORT BRIEF for a single branch. Cherry-picks the named commits onto an OpenShift release branch, resolves conflicts conservatively, runs the repository's checks, and pushes the branch to the bot's fork. Never opens a PR.
---

## Name
openshift-developer:cherry-pick

## Synopsis
```text
/openshift-developer:cherry-pick <brief>
```

# /openshift-developer:cherry-pick <brief>

The brief is authoritative: repository, target branch, source commits (in
order), head branch name, and the fork remote are all decided by the
coordinator's tools. Do not rename, retitle or reorder anything.

## Steps

1. `git fetch upstream <target_branch>` (add `upstream` for the upstream
   repository if the clone's `origin` is the fork) and
   `git checkout -b <head_branch> upstream/<target_branch>`.
2. Fetch the source commits (`git fetch upstream pull/<N>/head` covers PR
   commits; a squash/merge commit sha is on the base branch). For
   `source_mode: rebase`, find each PR commit's rebased twin on the base
   branch by `git patch-id` and pick those.
3. `git cherry-pick -x <sha>` for each source commit, in order. Keep the
   original authorship and message; the `-x` trailer is the only addition.
4. On a conflict: resolve minimally, preserving the upstream change's
   intent on this branch's code. Regenerate `vendor/`, `go.sum`, lockfiles
   with the project's own commands, never by hand. Never drop or weaken a
   test. Consult the `conflict_hints` PRs (already-resolved newer backports)
   for how the same hunk was resolved — but never pick from them. If a
   conflict is not mechanically resolvable, stop: push what applies cleanly
   in order, `report_setback("cherry_pick_conflict", <files and why>)`, and
   end with `GOAL_VERDICT: blocked`.
5. Run the proportional checks the repository defines (`make build`,
   `make test`/`make verify`, or the language's equivalents). Fix only what
   the cherry-pick introduced.
6. `git push origin <head_branch>`. Do NOT open a PR — the coordinator does,
   with the brief's title and body.
7. Report: the pushed branch, the commit shas on it, per-file conflict
   notes (file, what conflicted, how you resolved it), test evidence, and a
   closing `GOAL_VERDICT: achieved|blocked|failed` line.
