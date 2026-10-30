---
name: rebase
description: "Rebase an OpenShift downstream fork onto an upstream release, including carry analysis, conflict adaptation, and validation. Use when asked to rebase an upstream release or execute a delegated rebase-manager stage."
---

# Rebase an OpenShift fork

Use this as the shared procedure behind `/openshift:rebase` and callers such as
`nid-team:rebase-manager`. The agent performs the work; a slash command is not a
shell executable. Follow the repository's rebase instructions and commit policy.
The baseline convention is documented in
[OpenShift Kubernetes's rebase guide](https://github.com/openshift/kubernetes/blob/master/REBASE.openshift.md).

## Invocation and boundaries

- **Interactive:** `[tag]` selects an upstream release, or discover the greatest
  stable release allowed by the repository's release policy. Run planning,
  application, validation, and reporting, then prepare the PR for user editing.
- **Delegated:** a caller supplies exactly one `--stage plan|apply|validate|report`
  and an absolute `--state-dir`. Read the
  [artifact contract](references/artifacts.md). Run only that stage and return its
  artifacts, unresolved issues, and actual outcome. Delegated stages never push,
  create/update a PR, reply to reviewers, or mark work ready.

Keep artifacts outside the target checkout. Reuse a caller's directory; otherwise
create a temporary directory and report its location. Do not change `.gitignore`
to accommodate workflow state. Resolve this skill from the installed OpenShift
plugin; a caller must report a missing dependency instead of substituting its own
Git rebase implementation.

## Plan

1. Inspect remotes and repository guidance. Resolve the upstream project,
   downstream project/branch, and publishing fork from URLs, not remote names
   alone. The customary names are `upstream`, `openshift`, and `origin`; document
   alternate mappings rather than confusing the upstream and downstream projects.
   Fetch the required refs and tags. Record full commit SHAs for the selected
   upstream tag, downstream tip, and previous upstream base. A caller's supplied
   target is authoritative. Uncertain previous-base detection is a blocker. If
   the selected upstream revision is already the current upstream base, report
   that no release rebase is needed and return without creating a candidate.
2. Inventory downstream commits since the previous upstream base and compare
   that base's tree with the downstream tree. Include unmarked commits, merge
   resolutions, additions, deletions, and old persistent differences. Commit
   subjects and an arbitrary recent date window cannot establish completeness.
   Assign every tree difference a disposition or leave it explicitly unresolved.
3. Analyze carries in their dependency order. Use full source SHAs and stable
   IDs; duplicate subjects do not identify duplicate changes. Treat labels as
   policy hints:
   - `<carry>` normally persists; inspect its purpose and present implementation.
   - `<drop>` normally represents branch-specific or generated work; explain
     whether its effect is obsolete or will be regenerated.
   - An upstream PR number requires evidence that the relevant change is in the
     selected upstream revision. Merged status alone is insufficient; squash
     merges, partial backports, and reverts may require tree/behavior inspection.
   - `squash` names a compatible target carry. Preserve application dependencies;
     consolidate only after the resulting changes have been reviewed. Keep
     generated changes separate where the repository requires it.
4. Record the repository's actual generation/build/test commands, required CI
   checks, and behavior that the carries must preserve. Distinguish checks that
   can run locally from checks requiring CI. Write `plan.json` and
   `release-report.md`, including upstream changelog links, major changes,
   compatibility concerns, carry rationale, and unresolved questions. A plan can
   contain `undecided` entries; application cannot.

The plan stage ends here. A manager decides when the selected plan may proceed.
Interactive requests to perform a rebase already authorize its local execution;
ask only for material decisions that remain unresolved.

## Apply

Read the pinned plan. Verify that the selected source refs still resolve to the
recorded SHAs and all carry/tree decisions are resolved. Require a clean checkout
when starting a new candidate. For an interrupted candidate, inspect the recorded
progress and Git operation before deciding whether its uncommitted changes belong
to the operation being resumed.
If a source moved, report the changed input and return for replanning. Never
silently retarget an active run to a newer release.

Create the planned branch at the pinned upstream SHA. Establish downstream
ancestry with an `ours` strategy merge of the pinned downstream SHA, following
the repository's history convention. Verify that this merge preserves the
upstream tree; preserving history does not preserve downstream content.

Record each carry's start and completed outcome in `apply-progress.json`, with
the plan digest, branch, pre-operation head, and source/result identities. Apply
carries in the planned dependency order. Examine conflicts and explain
resolutions in terms of upstream changes and carry intent. Do not blanket-select
`ours` or `theirs`. Rebuild generated files with the project's generator and
toolchain. Use `go mod tidy`/`go mod vendor` only when appropriate to that project's
dependency policy. In particular, do not amend arbitrary source repairs and
generated dependencies into an unrelated OpenShift-files carry.

On an existing planned branch, inspect its tip, operation state, and recorded
progress before continuing. An in-flight cherry-pick may have expected conflict
edits: verify `CHERRY_PICK_HEAD` against the recorded source and distinguish those
edits from unrelated work before continuing that operation. Reconcile recorded
carry IDs with source/result SHAs;
never infer completion from a subject substring. An uncertain partial operation
returns a blocker with the exact Git state. Preserve unrelated changes and human
edits; rebuilding a branch requires an explicit plan to retain accepted work.

Write `result.json` with the plan digest, final head, every carry's disposition
and resulting commit, plus any adaptations. Keep the plan immutable. A required
decision change returns to planning and invalidates earlier validation. Leave the
candidate committed and clean before returning success. Consolidation that
rewrites commits changes the candidate head and requires new evidence.

## Validate

Use the plan, result, and actual current tree. Return failure or inconclusive
evidence for any check that could not be completed; do not convert missing tools,
unavailable reviewers, or exhausted retries into a pass.

- **Carry accounting:** every planned carry has an explained outcome. Inspect
  changed behavior, obsolete patches, conflict adaptations, and source-to-result
  mappings rather than accepting a successful cherry-pick alone.
- **Tree accounting:** reconcile the final upstream-to-candidate tree difference
  with the planned downstream inventory. Explain both disappeared downstream
  differences and newly introduced differences. Check required files, deletions,
  generated output, and ignored-but-required build inputs.
- **Configured validation:** run the planned commands in the intended toolchain.
  Save the command, exit status, revision, and output. Distinguish product failures
  from environment limitations using evidence. Required CI checks that have not
  run remain inconclusive; a draft may clearly expose them for CI execution.
- **Independent review:** when a separate agent/reviewer is available, give it
  the pinned plan and candidate diff and request a correctness review. Record
  findings and disposition. If unavailable, return `INCONCLUSIVE` and identify
  the outstanding review; do not fabricate approval.

Emit one gate artifact per required check using the shared contract. Evidence
applies only to its recorded plan and head. After a fix, rerun affected checks
and refresh all readiness evidence for the new head, explaining any reused
results rather than presenting an old check as a fresh run.

## Report and interactive PR preparation

Render `release-report.md` and `pr-body.md` from the current plan, result, and
evidence. Include upstream changelogs, significant changes, carry decisions,
conflict adaptations, tests with failures/pending checks, previous rebase, and
diff to upstream. Follow the target PR template. Mark stale results clearly and
identify the actual tested head; never retain a success claim from an earlier
candidate. The report can also serve as the rebase review meeting agenda.

Delegated report mode returns these files without publishing. In interactive
mode, stop on unresolved code/build/test failures and present the evidence.
Otherwise prepare the branch for the user's fork and use
`gh pr create --web --repo <downstream-owner>/<repo>` so the user can edit the
submission. Derive the OCP version from repository context before using the title
`Rebase to <tag> for OCP <version>`. Preserve existing authorization for publishing;
if it has not been given, present the concrete branch and PR body for approval.

## Design sources

This extracts the existing OpenShift rebase command into a reusable skill.
Revision-bound evidence and separate stage workers are informed by
[Kubernetes dependency-rebase PR #617](https://github.com/openshift-eng/ai-helpers/pull/617)
and its
[orchestrator at the inspected revision](https://github.com/dfarrell07/ai-helpers/blob/1a33dafe05981ceebfaf8fe780b0c448a6310b2d/plugins/k8s-rebase/scripts/k8s-rebase-orchestrator.sh).
Those are design references, not a runtime dependency or a claim that this
workflow has passed their evaluations.
