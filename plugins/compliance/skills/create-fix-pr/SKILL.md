---
name: create-fix-pr
description: After a CVE fix is applied and verified locally, create (or update) a GitHub pull request and optionally post the PR URL back to the source Jira ticket
---

# Create Fix PR

Opens a GitHub pull request for the CVE fix already applied in `REPO_DIR` (Phase 5). Never commits, pushes, or opens a PR without **explicit approval** — interactive, or `AUTO_APPROVE=yes` recorded once upfront (see [Autonomous Mode](../../commands/analyze-cve.md#autonomous-mode---auto-approveyesno)). Direct CVE mode (no `--jira=`/`--jql=`) still creates the PR; it just omits Jira `Fixes:` links and the Jira follow-up comment.

Called from **Phase 6** of `/compliance:analyze-cve` after Phase 5 verification succeeds.

---

## When to Use This Skill

Use this skill when:

- Phase 5 applied a fix in `REPO_DIR` and verification passed
- The user approved creating a GitHub PR
- `embargo_status` is not `True`

Do **not** use this skill to apply the fix itself (that is Phase 5) or to post the analysis report (that is `report-to-jira` in Phase 4).

---

## Required Inputs

From the parent command:

| Input | Source | Required |
|---|---|---|
| `REPO_DIR` | Phase 0.7 | Yes |
| `GIT_BRANCH` | Phase 0.7 (mapped release branch, e.g. `release-4.17`) | Yes |
| `REPO_URL` | Phase 0.7 | Yes |
| `CVE_ID` | Phase 0.5 / direct CVE mode | Yes |
| `SOURCE_TICKET` | `--jira=` / `--jql=` | No |
| `AUTO_APPROVE` | Phase 0 (`--auto-approve`, default `no`) | Yes |
| `FORK_ORG` | Caller environment (e.g. CI/RWS runner) | No — enables [Fork Mode](#fork-mode-fork_org-set) when set |
| `PHASE5_FILES` | Phase 5 allowlist (incl. untracked) | Yes |
| Module path, old version, new version | Phase 4 / 5 | Yes if a dependency bump |
| Short CVE description | Phase 1 | Recommended |
| Phase 5 change summary | Phase 5 "Document Changes" | Yes |

---

## Prerequisites

Hard requirements **for this skill**. Phase 0 does **not** treat `gh` as required (warn-only). This skill must not assume either tool is present — re-check both, then **fail** if either is missing. Do not create a PR another way.

```bash
which git 2>/dev/null || echo "MISSING: git"
which gh 2>/dev/null || echo "MISSING: gh"
gh auth status 2>/dev/null || echo "MISSING: gh auth"
```

- IF `git` is missing → print install instructions and return `status: failed` (`git_missing`). Stop. Do not commit or push.
- IF `gh` is missing → print install instructions (`https://cli.github.com/`) and return `status: failed` (`gh_missing`). Stop. Do not commit or push.
- IF `gh auth status` fails → print `gh auth login` instructions and return `status: failed` (`gh_unauthenticated`). Stop. Do not commit or push.
- Do not print token or login output that contains credentials.

> **Credential rule:** Never print, echo, or log tokens, PATs, or `gh` auth output that contains credentials. Reference credentials only via environment variable names.

---

## Fork Mode (`FORK_ORG` set)

By default (no `FORK_ORG`) this skill pushes the fix branch directly to the cloned repo's own `origin` and opens a same-repo branch→base PR. That requires the authenticated `gh`/`git` identity to have **direct write access** to every upstream repo `image-repo-mapping` might resolve to (e.g. `openshift/cert-manager-operator`, `openshift/cert-manager`, `openshift/secrets-store-csi-driver-operator`, ...). In an unattended CI/RWS runner that isn't a collaborator on all of those repos, that's the wrong default.

**IF the environment variable `FORK_ORG` is set** (e.g. a bot-owned org), push to a fork under that org instead and open a cross-repo PR — mirrors the fork/upstream model used elsewhere for automated OpenShift PRs. This section only changes **where the branch is pushed** and **how the PR's `--head` is specified**; Step 0 (safety gates), Step 1 (org/repo/base-branch resolution from `origin`), Step 2 (conflicting-PR detection), and Step 3b (commit, allowlist validation) are unchanged and still operate against `REPO_DIR`/`ORG`/`REPO`/`BASE_BRANCH` resolved from `origin`.

### Resolve the fork repo

```bash
FORK_REPO="${FORK_ORG}/${REPO}"   # REPO = repo name parsed from origin in Step 1, e.g. "cert-manager-operator"
```

### Ensure the fork exists and is actually a fork of this repo

Never assume a repo at `${FORK_REPO}` is the right push target just because the name matches — verify its fork lineage first. Reusing an unrelated (or unexpectedly renamed/transferred) repo that happens to occupy that name would push the fix branch and open a PR from somewhere unintended.

```bash
if FORK_JSON=$(gh repo view "${FORK_REPO}" --json isFork,parent 2>/dev/null); then
  IS_FORK=$(echo "$FORK_JSON" | jq -r '.isFork')
  PARENT_FULL_NAME=$(echo "$FORK_JSON" | jq -r '.parent.fullName // empty')
else
  IS_FORK=""
  PARENT_FULL_NAME=""
fi
```

- IF `${FORK_REPO}` exists (the `gh repo view` above succeeded) **and** (`IS_FORK` is not exactly `true` **or** `PARENT_FULL_NAME` is not exactly `${ORG}/${REPO}`) → **stop immediately**, do not add the `fork` remote or push anything, and return `status: failed` (`fork_wrong_lineage`).
- IF `${FORK_REPO}` exists and lineage matches → skip fork creation below, continue to Step 3a.
- IF `${FORK_REPO}` does not exist → create it:

```bash
gh repo fork "${ORG}/${REPO}" --org "${FORK_ORG}" --remote=false --clone=false --default-branch-only=false
FORK_CREATE_EXIT=$?
```

- IF `FORK_CREATE_EXIT` is non-zero → **stop immediately** and return `status: failed` (`fork_create_failed`). Do not poll, do not add the `fork` remote, do not push — the create call already reported failure, so there is nothing to wait for.
- IF `FORK_CREATE_EXIT` is `0` → the fork was accepted; poll briefly, since GitHub creates forks asynchronously:

```bash
for i in $(seq 1 10); do
  gh repo view "${FORK_REPO}" >/dev/null 2>&1 && break
  sleep 3
done
```

- IF the fork still doesn't exist after polling → return `status: failed` (`fork_create_failed`). Do not fall back to pushing to `origin` — that would silently switch to requiring direct upstream write access, which is exactly what `FORK_ORG` was set to avoid.

### 3a (fork mode). Branch — same as default mode

Branch creation/naming is identical to the non-fork case below (`BRANCH_NAME` derived from `CVE_ID`/`SOURCE_TICKET`, checked out from `BASE_BRANCH`).

### 3c (fork mode). Push to the fork, not `origin`

```bash
git -C "${REPO_DIR}" remote add fork "https://github.com/${FORK_REPO}.git" 2>/dev/null \
  || git -C "${REPO_DIR}" remote set-url fork "https://github.com/${FORK_REPO}.git"

# Keep the fork in sync with the upstream base branch before pushing a branch built on top of it,
# so the PR diff is just this fix — not a stale-fork drift diff.
git -C "${REPO_DIR}" fetch origin "${BASE_BRANCH}"
git -C "${REPO_DIR}" push fork "refs/remotes/origin/${BASE_BRANCH}:refs/heads/${BASE_BRANCH}" --force-with-lease 2>/dev/null || true

git -C "${REPO_DIR}" push -u fork "${BRANCH_NAME}"
```

Never force-push `${BASE_BRANCH}` on `origin` (the upstream repo) — the force-with-lease sync above only ever targets the `fork` remote's copy of that branch name, never `origin`.

### Step 4 (fork mode). Create the PR across fork → upstream

**Do not use `gh pr create --head "${FORK_ORG}:${BRANCH_NAME}"`.** `gh pr create --head` only supports a **user**-owned head repo via the `owner:branch` syntax — per `gh pr create --help`: "Using an organization as the owner is currently not supported" (tracked at [cli/cli#10093](https://github.com/cli/cli/issues/10093)). Since `FORK_ORG` may be a GitHub organization, use the REST API's `head_repo` parameter instead (via `gh api`), which unambiguously names the head repository regardless of whether `FORK_ORG` is a user or an org:

```bash
printf '%s' "${PR_BODY}" > "${WORK_CVE}/pr-body.md"

PR_URL=$(gh api \
  "repos/${ORG}/${REPO}/pulls" \
  -f head_repo="${FORK_REPO}" \
  -f head="${BRANCH_NAME}" \
  -f base="${BASE_BRANCH}" \
  -f title="${PR_TITLE}" \
  -F body=@"${WORK_CVE}/pr-body.md" \
  --jq '.html_url')
```

`head` is the **bare branch name** here (no `owner:` prefix) — disambiguation comes entirely from the separate `head_repo` field, so this works whether `FORK_ORG`/`FORK_REPO` is user- or org-owned. Everything else (title/body construction, stacked-PR update path) is unchanged; `PR_URL` is captured directly from the API response instead of `gh pr create`'s output.

### Auth note

`gh auth status` in Prerequisites must reflect a token with `public_repo` (classic PAT) or equivalent fork/push/PR scope on `${FORK_ORG}` and PR-creation scope against the upstream repo — this is set up by the caller before this skill runs (not part of this skill). Never echo the token itself.

---

## Step 0: Safety Gates

1. IF `embargo_status = True` → **abort immediately**. Do not commit, push, create a PR, or mention ticket contents.
2. IF Phase 5 did not complete successfully → return `status: skipped` (`phase5_incomplete`).
3. Confirm there are local changes to commit:

   ```bash
   git -C "${REPO_DIR}" status --porcelain
   git -C "${REPO_DIR}" diff --stat
   ```

   - IF working tree is clean **and** HEAD is already on a fix branch with the Phase 5 remediation committed (dependency bump, source, or config) → **validate that branch's changes against `PHASE5_FILES`** (see the check in Step 3b) before skipping to Step 4. A clean worktree only means nothing is *uncommitted*; it does not prove the existing commit(s) contain only Phase 5 paths. IF the branch diff vs `${BASE_BRANCH}` contains paths outside `PHASE5_FILES` → **always return `status: failed` (`phase5_files_mismatch`) immediately. Never gated by `AUTO_APPROVE` and never prompt.**
   - IF working tree is clean and HEAD is still `${GIT_BRANCH}` with no Phase 5 commit → return `status: skipped` (`no_local_changes`).
4. IF `AUTO_APPROVE=no` (and the parent hasn't already recorded a yes) → Ask:

   ```
   Phase 5 applied the fix locally. Create a GitHub PR against <GIT_BRANCH>?
   ```

   - IF no → return `status: skipped` (`user_declined`). Leave the working tree as-is.
   - IF yes → continue. Still do not commit until Step 3.

   IF `AUTO_APPROVE=yes` → treat as yes, skip the prompt, continue. Still do not commit until Step 3.

---

## Step 1: Resolve GitHub Repo and Base Branch

```bash
git -C "${REPO_DIR}" remote get-url origin
```

Parse `ORG/REPO` from the origin URL (`github.com/openshift/hypershift.git` → `openshift/hypershift`). If origin is SSH (`git@github.com:org/repo.git`), parse the same way.

`BASE_BRANCH` = `GIT_BRANCH` from Phase 0.7 (the mapped release branch the clone is on). Do **not** open the PR against `main` unless that is actually `GIT_BRANCH`.

---

## Step 2: Detect Conflicting Open PRs

**Title match only.** Do not inspect PR files, body, module versions, or `go.mod` diffs.

```bash
gh pr list --repo "${ORG}/${REPO}" --state open --base "${BASE_BRANCH}" \
  --json number,title,url,headRefName,author
```

A PR is a **match** if its **title** contains (case-insensitive) either this `CVE_ID`, or `SOURCE_TICKET` (when set).

IF none → continue to Step 3 with strategy `new`.

IF any match:

- **`AUTO_APPROVE=no`** → present the list and wait for the user:

  ```text
  Open PR(s) on <ORG/REPO> base <BASE_BRANCH> already have this CVE/Jira in the title:

    #<N>  <title>  <url>  head=<branch>

  How should I proceed?
    1. stack     — check out that PR branch, commit this fix on top, push (PR updates)
    2. wait      — stop; do not open a competing PR
    3. independent — new branch from <BASE_BRANCH> (may need rebase later)
  ```

  | Choice | Action |
  | --- | --- |
  | `stack` | `git fetch origin <headRefName> && git checkout <headRefName> && git pull`. Re-apply leftover Phase 5 changes if they are not already on that branch (same method as Phase 5 — bump, patch, or config edit). Strategy = `stack`. |
  | `wait` | Return `status: skipped` (`user_wait_for_pr`) including the existing PR URL. |
  | `independent` | Warn that a second PR on the same base may need rebase later. If `go.mod` is in this diff, mention possible module-file conflicts. Strategy = `new`. |
  | No answer | **Do not guess.** Ask again. |

- **`AUTO_APPROVE=yes`** → **always `wait`**, automatically, with no exceptions: return `status: skipped` (`user_wait_for_pr_auto`) including the existing PR URL. Never auto-choose `stack` (that pushes commits onto a branch nobody reviewed for this run) or `independent` (that opens a second, possibly duplicate/conflicting PR) unattended. Log clearly that this run stopped because of the existing PR, so a human can revisit with `--auto-approve=no` if a different resolution is actually wanted.

---

## Step 3: Branch, Commit, Push

Work only inside `REPO_DIR`.

**Vendor:** Phase 5 already ran `go mod vendor`/`make vendor` (if applicable) and included any resulting paths in `PHASE5_FILES` before verification. Do **not** run vendor sync here — doing so after `PHASE5_FILES` was written would generate paths that never make it into the allowlist and get silently dropped from the commit. IF a dependency bump is present in `PHASE5_FILES` but `vendor/` looks out of sync (e.g. `go mod vendor` reports diffs) → stop and tell the user to re-run Phase 5, rather than fixing it here.

### 3a. Branch

**New PR (`strategy = new`):**

```bash
git -C "${REPO_DIR}" fetch origin "${BASE_BRANCH}"
git -C "${REPO_DIR}" checkout "${BASE_BRANCH}"
git -C "${REPO_DIR}" pull --ff-only origin "${BASE_BRANCH}"

SLUG="$(echo "${CVE_ID}" | tr '[:upper:]' '[:lower:]')"
if [ -n "${SOURCE_TICKET}" ]; then
  BRANCH_NAME="fix/${SLUG}-$(echo "${SOURCE_TICKET}" | tr '[:upper:]' '[:lower:]')"
else
  BRANCH_NAME="fix/${SLUG}"
fi

git -C "${REPO_DIR}" checkout -b "${BRANCH_NAME}"
```

Re-apply the Phase 5 changes on this branch if checking out `BASE_BRANCH` discarded uncommitted work. Prefer not discarding: stash before checkout if the working tree is dirty, then stash pop onto `BRANCH_NAME`.

**Stack (`strategy = stack`):** already on the existing PR branch. Set `BRANCH_NAME` to that head ref. Do not create a new branch.

### 3b. Commit

Stage **only `PHASE5_FILES`**, not the whole worktree. That allowlist is written in Phase 5 (`phase5-files.txt`) and includes new untracked files. `go.mod`, `go.sum`, `go.work`, and `vendor/` are common for **dependency version bumps**, but other CVE remediations may only touch source, config, Dockerfiles, or scripts.

`WORK_CVE` is in the **command's own workspace** (`.work/`), not inside `REPO_DIR`. Paths in the allowlist are relative to `REPO_DIR`.

```bash
WORK_CVE="${AI_HELPERS_WORKSPACE:-.}/.work/compliance/analyze-cve/${CVE_ID}"
PHASE5_FILES="${WORK_CVE}/phase5-files.txt"
```

IF `phase5-files.txt` is missing or empty → rebuild it from Phase 5 "Document Changes" (and `phase5-before.status` if present). IF the allowlist still cannot be determined → **always return `status: failed` (`phase5_files_missing`) immediately. Never gated by `AUTO_APPROVE` and never prompt.** Do **not** fall back to whole-worktree `git diff` / `git add -A` / `git add .` in any case.

```bash
# inspect current tree for sanity, but do not use it as the stage set
git -C "${REPO_DIR}" status --porcelain

while IFS= read -r f; do
  [ -n "${f}" ] || continue
  git -C "${REPO_DIR}" add -- "${f}"
done < "${PHASE5_FILES}"
```

`git add -- <path>` stages modifications, deletions, and untracked files. Examples of what belongs on the allowlist:

- Dependency bump: `go.mod`, `go.sum`, and `go.work` / `vendor/` only if Phase 5 changed them
- Code/config fix: the source or config files Phase 5 added or edited
- Mixed: the union of those paths

Do **not** add `.work/`, analysis reports, or credentials. Do **not** add pre-existing dirty files that are absent from `PHASE5_FILES`. Do **not** `git add` `go.mod` / `vendor/` unless they are on the allowlist.

**Validate the staged set exactly matches the allowlist.** The loop above only *adds* allowlisted paths — it does not prove the index is free of anything else (e.g. leftover pre-existing staged files). Diff the two sets and reject extras instead of committing them silently:

```bash
git -C "${REPO_DIR}" diff --cached --name-only > "${WORK_CVE}/staged-files.txt"

EXTRA="$(comm -23 <(sort "${WORK_CVE}/staged-files.txt") <(sort "${PHASE5_FILES}"))"
if [ -n "${EXTRA}" ]; then
  echo "Unstaging paths not in PHASE5_FILES:"
  echo "${EXTRA}"
  while IFS= read -r x; do
    [ -n "${x}" ] || continue
    git -C "${REPO_DIR}" restore --staged -- "${x}"
  done <<< "${EXTRA}"
fi
```

IF any path was rejected → tell the user which paths were unstaged and why before continuing. Re-run the diff after unstaging to confirm the index now matches `PHASE5_FILES` exactly (accounting for deletions).

**On a `stack` branch, or when Step 0 skipped ahead because a Phase 5 commit already existed,** run the equivalent check against the branch, not just the index:

```bash
git -C "${REPO_DIR}" diff --name-only "${BASE_BRANCH}...HEAD" > "${WORK_CVE}/branch-files.txt"
comm -23 <(sort "${WORK_CVE}/branch-files.txt") <(sort "${PHASE5_FILES}")
```

IF that reports any path outside `PHASE5_FILES` → stop; do not push or open/update the PR. **Always return `status: failed` (`phase5_files_mismatch`) immediately, for manual follow-up. Never gated by `AUTO_APPROVE` and never prompt.**

**Commit message.** Match the **actual** Phase 5 change, not a canned module bump. Use the repo's own convention when detectable — e.g. many OpenShift repos expect `UPSTREAM: <upstream-pr-or-carry>: <subject>`:

```bash
git -C "${REPO_DIR}" log --oneline -20
```

If the recent history shows the `UPSTREAM:` convention and a dependency bump with a known upstream fix PR number (from the Phase 4 remediation plan):
```
UPSTREAM: <upstream-pr>: Bump <module> to <new> for <CVE_ID>
```

If a dependency bump that is downstream-only / fork / carry (no tracked upstream PR, but repo uses `UPSTREAM:` convention):
```
UPSTREAM: <carry>: Bump <module> to <new> for <CVE_ID>
```

If the repo does not use the `UPSTREAM:` convention, use a plain subject. Dependency bump:
```
Bump <module> to <new> for <CVE_ID>
```

If the fix is **not** a version bump (code, config, workaround), regardless of convention:
```
Fix <CVE_ID>: <short description of the change>
```

Body: one or two sentences describing what changed and why. Include `Fixes: <SOURCE_TICKET>` in Jira mode; omit that line in direct CVE mode. For a bump, include old → new versions. Do not claim a module bump if Phase 5 did not bump a module.

```bash
git -C "${REPO_DIR}" commit --signoff -m "${COMMIT_SUBJECT}" -m "${COMMIT_BODY}"
```

Sign off (DCO) by default — most upstream/downstream OpenShift-style repos require it and a missing sign-off is a common, avoidable PR-check failure. Never use `--no-verify` or skip hooks unless the user explicitly asks.

### 3c. Push

```bash
git -C "${REPO_DIR}" push -u origin "${BRANCH_NAME}"
```

Default is a normal push. Amending an existing commit and force-pushing is never authorized by `AUTO_APPROVE`; it always requires an interactive user (moot in practice, since `AUTO_APPROVE=yes` never selects `stack` — see Step 2).

---

## Step 4: Create or Update the GitHub PR

### Title

Dependency bump:
```
<CVE_ID>: bump <module-short> to <new> [<SOURCE_TICKET>]
```
Omit `[<SOURCE_TICKET>]` in direct CVE mode. Example: `CVE-2026-33186: bump google.golang.org/grpc to v1.79.3 [OCPBUGS-80452]`

Non-bump fix:
```
<CVE_ID>: <short description> [<SOURCE_TICKET>]
```

### Body

Read the repo's PR template if one exists (`cat "${REPO_DIR}/.github/PULL_REQUEST_TEMPLATE.md" 2>/dev/null`) and structure the body around it. Otherwise use:

**Jira mode** — every Jira key must be a markdown link. Use a `Fixes:` line (do not use a bare key):

```markdown
## Summary

Fixes: [<SOURCE_TICKET>](<JIRA_BASE_URL>/browse/<SOURCE_TICKET>)

<What Phase 5 changed and why — e.g. bump `<module>` from `<old>` to `<new>`, or a code/config workaround.>

<2–3 sentence CVE description from Phase 1>

## Changes

- <file- or behavior-level bullets from the Phase 5 diff>

## Verification

- `make verify` / `go mod verify` (if modules changed)
- `make build` / `go build ./...`
- `govulncheck ./...`

---
Always review AI generated responses prior to use.
AI-assisted change via compliance plugin (`/compliance:analyze-cve`)
```

**Direct CVE mode** — same body **without** the `Fixes:` line and without Jira URLs.

Do not include hostnames, cluster names, routes, usernames, passwords, or tokens in the title, body, or comments.

### Create vs update

**New PR (default mode — no `FORK_ORG`):**

```bash
gh pr create \
  --repo "${ORG}/${REPO}" \
  --base "${BASE_BRANCH}" \
  --head "${BRANCH_NAME}" \
  --title "${PR_TITLE}" \
  --body "${PR_BODY}"
```

**New PR (fork mode — `FORK_ORG` set):** use the [Fork Mode](#fork-mode-fork_org-set) Step 4 variant (`gh api repos/.../pulls -f head_repo=...`) instead of the `gh pr create` call above.

**Stacked on existing PR:** push is enough (to `origin` by default, or `fork` in Fork Mode). Optionally:

```bash
gh pr comment "${EXISTING_PR}" --repo "${ORG}/${REPO}" \
  --body "Added <CVE_ID> fix: <what Phase 5 changed>."
```

And `gh pr edit` to append the CVE / Jira key to title and the `Fixes:` line if missing.

Capture `PR_URL` from `gh pr create` output or `gh pr view --json url` (default mode), or from the `gh api` response (Fork Mode).

IF create fails (permissions, fork needed) → show the exact `gh` error (no secrets). If the error indicates missing write access and `FORK_ORG` is not set, suggest re-running with `FORK_ORG` configured (see [Fork Mode](#fork-mode-fork_org-set)) rather than guessing at a fork target. Otherwise give the user the title/body to paste, return `status: failed` (`pr_create_failed`). Do not retry more than once.

---

## Step 5: Post PR URL to Jira (Jira mode only)

**Skip this step** if `SOURCE_TICKET` is unset (direct CVE mode) → still `status: success` for the GitHub PR.

Use the [report-to-jira](../report-to-jira/SKILL.md) skill's **Follow-up: PR URL comment** section. Do not edit or replace the Phase 4 analysis comment. Do not add/remove labels here.

IF posting fails → display the comment in session for manual paste. The GitHub PR is still a success (`jira_followup: failed`).

---

## Return Value

**Success:**

```json
{
  "skill": "create-fix-pr",
  "status": "success",
  "action": "created | updated",
  "pr_url": "https://github.com/<org>/<repo>/pull/<n>",
  "pr_number": 123,
  "branch": "fix/cve-yyyy-nnnnn-ocpbugs-12345",
  "base_branch": "release-4.17",
  "cve_id": "CVE-YYYY-NNNNN",
  "source_ticket": "OCPBUGS-12345 or null",
  "jira_followup": "posted | skipped | failed"
}
```

**Skipped:**

```json
{
  "skill": "create-fix-pr",
  "status": "skipped",
  "reason": "user_declined | no_local_changes | phase5_incomplete | user_wait_for_pr | user_wait_for_pr_auto | embargo"
}
```

**Failed:**

```json
{
  "skill": "create-fix-pr",
  "status": "failed",
  "reason": "git_missing | gh_missing | gh_unauthenticated | pr_create_failed | commit_failed | phase5_files_missing | phase5_files_mismatch | fork_wrong_lineage | fork_create_failed",
  "error": "<message without secrets>"
}
```

---

## Integration with Parent Command

Called from **Phase 6** of `/compliance:analyze-cve` after Phase 5 verification succeeds. Runs after the [Repo Guard](../../commands/analyze-cve.md#repo-guard--re-clone-if-missing) has confirmed `REPO_DIR` still exists.

---

## Guardrails

- Never commit, push, or open a PR without explicit approval — interactive, or `AUTO_APPROVE=yes` recorded once upfront
- Never force-push to `BASE_BRANCH` / `main` / `master` / `release-*`
- Never skip git hooks unless the user asks
- Never stage paths outside `PHASE5_FILES`; never `git add -A` or `git add .`
- Never commit/push/PR without validating the staged (and, for `stack`, the branch) path set against `PHASE5_FILES` and rejecting extras
- Never run vendor sync in Phase 6 — it happens in Phase 5, before `PHASE5_FILES` is written
- Never push to, or open a PR from, a `FORK_ORG` repo without first verifying its fork lineage (`isFork` + `parent.fullName` match) — never reuse a same-named repo that isn't actually a fork of the target
- Never let `AUTO_APPROVE=yes` auto-select `stack` or `independent` on a PR-title conflict — always `wait` unattended
- Never let `AUTO_APPROVE=yes` skip a hard-fail case (missing/mismatched `PHASE5_FILES`, ambiguous conflict resolution) — those always require a human, flag or not
- Never include secrets in commit messages, PR text, or Jira comments
- Stop immediately on embargo
- Direct CVE mode must still produce a PR
