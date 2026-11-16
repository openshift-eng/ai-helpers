---
name: understanding-openshift-prs
description: Use when managing or shepherding open OpenShift pull requests — explains what a PR needs to merge (lgtm, approved, verified, Jira labels), pre-merge verification with /verified, why e2e jobs have not started (pipeline controller, /lgtm, /pipeline required), Chai bot test selection, Jira label failures, backports with /cherry-pick, and how to prove a fix worked from presubmit artifacts and draft a /verified comment for human approval.
---

# Understanding OpenShift Pull Requests

Most repos in the `openshift` GitHub org share a merge process that is not obvious from the PR page: a `verified` label is usually required, expensive e2e jobs often wait for `/lgtm`, and in some repos a bot chooses which e2e jobs run at all. This skill explains those mechanics so you can tell a user why a PR is stuck and what to do next, and walks through verifying a fix from presubmit results.

## When to Use This Skill

- A user is working through a list of open PRs and wants to know what each one needs to merge.
- A PR's e2e jobs never started, or only a few of them ran.
- A user wants to confirm a fix worked using the PR's presubmit jobs, then mark it verified.

## Posting Rule: Human Approval Required

Slash commands on a PR change its merge state and are visible to the whole team. **Never post a PR comment, including `/verified`, `/lgtm`, `/approve`, `/pipeline ...`, `/cherry-pick`, `/jira refresh`, `/test` or `/retest`, without the user's explicit approval for that specific comment on that specific PR.** Draft the exact comment text, show it, and wait. Approval for one PR does not extend to the next.

## What a PR Needs to Merge

Tide merges a PR once its required labels are present, no forbidden labels are present, and required jobs pass. The requirements differ by repo and branch, so check rather than assume. Use the `fetch-tide-pr-status` skill: it reads Tide's queries and lists each PR's missing labels and failing or pending required jobs.

Typical requirements in OpenShift repos:

| Label | Set by | Notes |
|-------|--------|-------|
| `lgtm` | Reviewer comments `/lgtm` | Removed when new commits are pushed (including a rebase) |
| `approved` | An OWNERS approver comments `/approve` | |
| `verified` | A repo collaborator comments `/verified ...` | Required by about half of `openshift` repos, see below |
| `jira/valid-reference` | Jira automation | PR title starts with a Jira key, e.g. `OCPBUGS-123: ...` |
| `jira/valid-bug` | Jira automation | Bug passes validation; required on release branches and some repos' main. See below |
| `backport-risk-assessed` | Repo owners authorized for backports | Release branches only; records that the backport was judged safe to accept. See [Backports](#backports-cherry-pick) |

Forbidden labels include `do-not-merge/hold`, `do-not-merge/work-in-progress`, `needs-rebase` and `jira/invalid-bug`.

### Jira Label Failures

The most common Jira failure is a **missing or wrong Target Version** on the bug. Each branch expects a specific target version: main expects the release in development, and `release-X.Y` expects `X.Y.z`. A mismatch sets `jira/invalid-bug` and withholds `jira/valid-bug`. Backport bugs also fail when the matching bug on the next-newer branch is not yet VERIFIED. The automation's PR comment lists each validation it ran and which one failed. Fix the bug in Jira, then comment `/jira refresh` (with user approval) to re-run validation.

### Risk Labels: `chai-risk-assessment/*`

Chai labels many PRs with a risk tier for the latest commit, used for risk-based review. For now these labels are informational and Tide does not require them, but they may soon affect merge requirements. Check `fetch-tide-pr-status` rather than assuming they are still optional.

| Label | Meaning |
|-------|---------|
| `chai-risk-assessment/low` | No product behavior change, e.g. docs, tests, dependency bumps |
| `chai-risk-assessment/moderate` | May change product behavior, but not disruptively |
| `chai-risk-assessment/critical` | May disrupt clusters or workloads if the change is wrong |

Use the tier to decide how much review and verification a PR needs. A `critical` PR deserves evidence from a job matching the affected platform or topology before `/verified by`; a `low` tier alone does not justify `/verified bypass`, since dependency bumps are `low` but still change what ships. The tiers and how they are assigned are defined in the `openshift-developer:pr-risk-assessment` skill, which you can also run for a second opinion on any PR.

## Pre-merge Verification: `/verified`

Many repos require the `verified` label to merge. It records how the change was tested, and it drives the linked Jira bug's state after merge. Reference: [Jira integration docs](https://docs.ci.openshift.org/docs/architecture/jira/#premerge-verification).

| Command | Meaning | Jira effect after merge |
|---------|---------|-------------------------|
| `/verified by <reason>` | Pre-merge testing done. `<reason>` is a comma-separated list of test or job names and/or GitHub `@usernames` who tested it | Bug moves to VERIFIED automatically |
| `/verified later @user` | Post-merge testing will be done by the named user(s) | Bug moves to ON_QA; someone must verify by hand |
| `/verified bypass` | The change is non-functional and needs no testing | Treated as pre-merge verified |
| `/verified remove` | Removes the label so it can be set again | |

Key behaviors:

- **Only repo collaborators** can use these commands; others get a rejection comment.
- **Any new commit removes `verified`** (and `verified-later`). After a rebase or fixup, verification must be redone against the new head.
- The command must start its own line: `/verified by` takes the rest of that line as the reason. Explanation can follow on later lines of the same comment.
- If several PRs fix one bug, the bug only moves to VERIFIED when all of them are merged and pre-merge verified.
- Do not suggest `/verified bypass` for changes that alter behavior, such as a manifest value, code path or dependency bump. Bypass is for docs, comments, test-only cleanups and similar.

## Backports: `/cherry-pick`

The preferred way to backport a fix from main is a `/cherry-pick <branch>` comment on the main PR (`/cherrypick` also works). For example, while main is 5.1, comment `/cherry-pick release-5.0`. After the PR merges, the automation:

1. Opens a cherry-pick PR against the target branch and assigns it to the commenter.
2. Clones the Jira bug with the correct Target Version for that branch, marks the clone as dependent on the original, and retitles the PR to reference the clone.

Fixes move back **one release at a time**. The bug must be VERIFIED on the newer branch before the backport to the next-older branch is valid, and each branch's PR merges in sequence. This ensures every fix exists in all newer releases, so upgrading a cluster never brings back a fixed bug. It also prevents pulling changes into older branches out of order. To request several releases at once, list them newest first, e.g. `/cherry-pick release-5.0 release-4.22`. The automation opens the next cherry-pick only after the previous one merges.

Backport PRs also need `backport-risk-assessed`, set by repo owners authorized for backports. The `openshift-developer:backport` skill is Chai's playbook for the same flow (it requires Chai's `ocp_backport_*` tools) and explains the Jira clone chain in more detail.

## Why E2E Jobs Have Not Run: The Pipeline Controller

Many repos split presubmits into two stages. First-stage jobs (unit, verify, images) run on every push. Second-stage jobs, usually the expensive e2e ones, are triggered by the [pipeline controller](https://docs.ci.openshift.org/how-tos/creating-a-pipeline/). On enrolled repos it posts a "Pipeline controller notification" comment when the PR opens. In each repo's ci-operator config, second-stage jobs are `always_run: false`, and some carry `pipeline_run_if_changed` / `pipeline_skip_if_only_changed` annotations that limit them to relevant file changes.

Each enrolled repo uses one of three trigger modes, configured in `openshift/release` under `core-services/pipeline-controller/`:

| Mode | Config file | Second stage starts when |
|------|-------------|--------------------------|
| LGTM | `lgtm-config.yaml` (most enrolled `openshift` repos) | The `lgtm` label is added |
| Automatic | `config.yaml` with `trigger: auto`, or no `mode.trigger` (the default) | All first-stage jobs pass |
| Manual | `config.yaml` with explicit `trigger: manual` | Someone comments `/pipeline required` or `/test <job>` |

Consequences to explain to users:

- **In LGTM mode, no e2e results exist until someone adds `/lgtm`.** A PR with pending e2e contexts and no `lgtm` is waiting on review, not on CI.
- **A push or rebase removes `lgtm`**, so in LGTM mode the second stage waits again for the new head. The bot's auto-rebase is a common cause of "everything went back to pending".
- `/pipeline required` starts the full second-stage set now, without waiting for `lgtm` or first-stage success. It re-fires jobs that are already running.
- `/pipeline remaining` starts only the second-stage jobs that have no run at the current head. Prefer it when some jobs already ran.
- While Chai owns test selection (see below), the controller rejects `/pipeline required` and `/pipeline remaining`; they start nothing.
- `/test ?` lists available jobs; `/pipeline help` lists pipeline commands.
- A `ci/pipeline-gate` check stays pending until the second stage is dispatched. It goes green on dispatch, not when the tests pass.

## Chai Test Selection (Agentic Mode)

In a few enrolled repos the pipeline controller hands second-stage selection to `redhat-chai-bot`. These are the entries with `agentic: {mode: chai}` in the pipeline-controller configs; `origin`, `ci-tools`, `api` and `installer` are examples, but check the configs since enrollment is a closed beta and changes.

- Chai reads the diff and posts a comment titled "Chai test selection for `<sha>` → `<branch>`", listing the jobs it chose, its reasoning, and a `/test` line that dispatches them.
- **Only the jobs Chai selected run.** A missing e2e result is often by design, not a stuck job. Read Chai's reasoning before assuming something is broken.
- Chai is triggered once per head SHA. A new push re-triggers it; `/pipeline required` and `/pipeline remaining` are rejected while Chai owns selection.
- If Chai does not respond within its timeout, the controller falls back to normal selection for that revision.
- `/pipeline skip-agentic-mode` opts a PR out of Chai (persists across pushes); `/pipeline agentic-mode` opts back in.
- If Chai responded but dispatch stalled, propose `/pipeline skip-agentic-mode` for user approval, then repeat `/pipeline remaining` (or `/pipeline required`) after the opt-out. Running tests are not cancelled.

When verifying a fix in a Chai repo, check whether the jobs that would show the fix were selected. If not, propose a `/test <job>` comment for user approval rather than concluding the evidence does not exist.

## Verifying a Fix From Presubmit Results

Goal: concrete evidence that the change does what the linked bug asks, from a completed run on the PR's **current** head.

1. **Define "fixed".** Read the PR description and linked Jira bug. Turn the expected outcome into something observable: a test that should now pass, a value that should appear in an artifact, a log line or metric that should change.
2. **Get the current head SHA** (`gh pr view <n> -R openshift/<repo> --json headRefOid`). Evidence from an older head does not count, because `verified` is tied to the current head.
3. **Pick a completed run on that head** that would actually exercise the change. Map job names to what they test before searching artifacts. For example, an artifact written by the `openshift-e2e-test` step will not exist in HyperShift or operator-only jobs that do not run that step. Prefer the job whose platform and topology match the bug.
4. **Find the evidence.** Use the `prow-job-analysis` skill or the GCS artifact browser (`https://gcs.ci.openshift.org/gcs/test-platform-results-public/pr-logs/pull/<org>_<repo>/<pr>/<full-job-name>/<run-id>/artifacts/`). Record the run URL and the exact observed value or result.
5. **If the evidence is missing,** say so plainly. Name the run and path you checked, and offer the next step: another job, `/test <job>`, `/pipeline remaining`, or `/verified later @user` if pre-merge testing is impractical. Do not stretch a passing job into proof it does not provide; a green e2e run alone does not show a specific fix.
6. **Draft the comment** and show it to the user for approval (see the posting rule above):

```text
/verified by e2e-aws-ovn

Checked https://prow.ci.openshift.org/view/gs/test-platform-results-public/pr-logs/pull/openshift_<repo>/<pr>/<full-job-name>/<run-id> (head <short-sha>):
<artifact path or test name> shows <observed value>, matching the expected <expected value> from OCPBUGS-NNNNN.
```

Put the job or test name in the reason, not a vague "CI". Keep the evidence specific enough that a reviewer can re-check it in one click.

## Working Through Many PRs

For each PR, summarize in one line: what blocks merge (from `fetch-tide-pr-status`), whether second-stage jobs ran on the current head, and the single next action, each marked as needing a human or something you can do. Typical next actions:

- Needs review → `/lgtm` from a reviewer, which also starts e2e in LGTM mode.
- E2e done, fix confirmed → draft `/verified by ...` for approval.
- Infra failure (pod eviction, cluster install or lease failures unrelated to the diff) → propose `/retest` or `/test <job>`.
- Real failure → investigate with `prow-job-analysis`.
- New commits since verification → verification must be redone.
- `jira/invalid-bug` → check the bug's Target Version against the branch (and, for backports, that the newer branch's bug is VERIFIED), then `/jira refresh`.
- Merged fix that needs a backport → propose `/cherry-pick release-X.Y` for the next-older branch only.

## Related Skills

- `fetch-tide-pr-status` — merge blockers and required job states for one or many PRs
- `prow-job-analysis` — debugging a failed Prow job and browsing its artifacts
- `fetch-prowjob-json` — job metadata for a run URL
- `openshift-developer:pr-risk-assessment` — the tier behind `chai-risk-assessment/*` labels, or a second opinion on a PR's risk
- `openshift-developer:backport` — Chai's backport playbook: Jira clone chain and per-branch cherry-pick PRs
