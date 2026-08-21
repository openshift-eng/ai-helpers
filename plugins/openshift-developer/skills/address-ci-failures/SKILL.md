---
name: address-ci-failures
description: Triage and fix PR CI failures caused by the PR's own changes. Use when has-review-work detects new failing checks, when a PR has CI regressions to investigate, or when deciding whether to fix vs report a CI failure.
---

## Name
openshift-developer:address-ci-failures

## Synopsis
```text
/openshift-developer:address-ci-failures [PR number] [owner/repo] [--failing-checks JSON] [--ci]
```

## Description
Investigates failing CI checks on a pull request, classifies each failure, and only fixes failures that are a direct consequence of the PR's changes. Pre-existing, infrastructure, flake, and fleet-wide failures are reported on the PR instead of "fixed" with out-of-scope repo-wide changes.

When `--ci` is passed: NEVER ask interactive questions or wait for user input. Make autonomous decisions. When uncertain whether a failure is PR-caused, do not fix — report instead.

## Implementation

### Step 0: Resolve PR and failing checks

Resolve PR number and repository into named variables before any shell commands. Quote those variables in every `gh` and `git` invocation — never pass raw `$1` or `$2` to commands.

1. **PR number**: If argument `$1` is provided, set `PR_NUMBER="$1"`. Otherwise:

   ```sh
   PR_NUMBER=$(gh pr view --json number -q .number)
   ```

2. **Repository**: If argument `$2` is provided (`owner/repo`), set `REPO="$2"`. Otherwise:

   ```sh
   REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
   ```

3. **Failing checks**: Each check object uses `{name, state, bucket, link}` — the same shape `has-review-work` emits in `FAILING_CHECKS`.

   - If `--failing-checks` is provided, parse it as a JSON array of those objects.
   - If any object omits `link`, merge links from:

     ```sh
     gh pr checks "$PR_NUMBER" --repo "$REPO" --json name,state,bucket,link
     ```

   - Otherwise fetch failing checks directly:

     ```sh
     gh pr checks "$PR_NUMBER" --repo "$REPO" --json name,state,bucket,link
     ```

   Keep checks where `bucket == "fail"`. Ignore `tide`.

4. If no failing checks remain, report that and stop.

5. **PR diff context** (required for triage; fail closed if unavailable):

   Discover the repository's configured remote — do not assume `origin`. Prefer the current branch's tracking remote, then `upstream`, then `origin`, then the first configured remote:

   ```sh
   BASE_BRANCH=$(gh pr view "$PR_NUMBER" --repo "$REPO" --json baseRefName -q .baseRefName)

   TRACKING_REMOTE=$(git config "branch.$(git rev-parse --abbrev-ref HEAD).remote" 2>/dev/null)
   if [ -z "$TRACKING_REMOTE" ]; then
     TRACKING_REMOTE=$(git remote | grep -m1 '^upstream$')
   fi
   if [ -z "$TRACKING_REMOTE" ]; then
     TRACKING_REMOTE=$(git remote | grep -m1 '^origin$')
   fi
   if [ -z "$TRACKING_REMOTE" ]; then
     TRACKING_REMOTE=$(git remote | head -1)
   fi
   if [ -z "$TRACKING_REMOTE" ]; then
     echo "ERROR: no git remote configured" >&2
     exit 1
   fi

   git fetch "$TRACKING_REMOTE" "${BASE_BRANCH}" || exit 1
   git diff "${TRACKING_REMOTE}/${BASE_BRANCH}" --stat || exit 1
   git diff "${TRACKING_REMOTE}/${BASE_BRANCH}" --name-only || exit 1
   ```

   Do not continue triage if fetch or either diff command fails.

### Step 1: Triage each failing check (mandatory before any code change)

For each failing check, gather evidence and classify. Use `ci:prow-job-analysis` for Prow/OpenShift CI jobs and the flaky-test-identification reference for classification signals.

1. **Get the job URL** from the check object's `link` field (populated in Step 0). Skip checks with no Prow URL (e.g. GitHub Actions-only) — triage from available logs/output instead.

2. **Analyze the failure** using `ci:prow-job-analysis` with the Prow URL. Identify:
   - Failed step or test name
   - Error message
   - ci-operator failure reason (if any)
   - Whether the failure touches files or packages changed in this PR

3. **Classify** each failure into exactly one category:

   | Classification | Fix? | Signals |
   |----------------|------|---------|
   | **pr_caused** | Yes | Error in files/packages the PR changed; compile/lint/test failure directly tied to the diff; new test or code path introduced by this PR |
   | **infrastructure** | No | ci-operator reasons (`pod_pending`, `acquiring_lease`, `acquiring_cluster_claim`, `importing_release`, `building_image`, `resolving_step`); cloud quota/API errors; Boskos lease failures |
   | **pre_existing** | No | Same check fails on base branch or unrelated PRs; CVE/dependency issue on unchanged deps affecting all PRs; failure predates this PR |
   | **flake** | No | Sippy pass rate in 80–99% band; in-run fail+pass JUnit twin; same error across 3+ unrelated jobs at once; passes on retry with no code change |
   | **out_of_scope** | No | Fix would require repo-wide CI config, audit/lint threshold changes, or policy changes unrelated to the Jira issue scope |

   Consult [flaky-test-identification](../../../ci/skills/prow-job-analysis/references/flaky-test-identification.md) for the full decision methodology.

4. **Default when uncertain**: classify as **pre_existing** or **out_of_scope** and report — do not fix.

5. **Document triage** for each check: classification, key evidence, and whether a fix is planned.

### Step 2: Act on classification

#### PR-caused failures

1. Implement the **minimal fix** in the PR's changed code or tests — do not broaden scope.
2. Run the repo's verification commands before committing (same detection as `address-review-pr` Step 3.5).
3. Commit locally with a conventional commit message referencing the failing check.
4. Maximum **3 fix attempts** per root cause. After 3 failures, stop and report what was tried.
5. In `--ci` mode: commit locally only — do not `git push` (the pipeline pushes after you finish).

#### Not PR-caused failures

1. Do **not** change application code, CI configuration, generated files, or repo-wide tooling policy.
2. Post a **PR conversation comment** (not inline) for each non-actionable failure. Build the report body as data in a safely quoted variable (or a temp file), then pass it through `gh api` — do not interpolate report text directly into shell source or unquoted command arguments:

   ```sh
   OWNER="${REPO%%/*}"
   REPO_NAME="${REPO#*/}"

   REPORT_BODY='**CI failure (not fixing):** ci/prow/lint

   **Classification:** pre_existing

   **Evidence:** ...

   **Action needed:** Human or infra follow-up required — not addressed in this PR.

   ---
   *AI-assisted response via Claude Code*'

   jq -n --arg body "$REPORT_BODY" '{body: $body}' |
     gh api "repos/${OWNER}/${REPO_NAME}/issues/${PR_NUMBER}/comments" --input -
   ```

   Report template:

   ```text
   **CI failure (not fixing):** {check name}

   **Classification:** {infrastructure|pre_existing|flake|out_of_scope}

   **Evidence:** {1-3 sentences with job URL, error summary, and why this is not caused by this PR's changes}

   **Action needed:** Human or infra follow-up required — not addressed in this PR.

   ---
   *AI-assisted response via Claude Code*
   ```

3. Do not `/retest`, retrigger jobs, or weaken lint/audit/security thresholds.

### Step 3: Summary

Report for each failing check:

| Check | Classification | Action |
|-------|----------------|--------|
| ... | pr_caused / infra / ... | fixed / reported / skipped |

Include commit hashes for fixes and comment URLs for reports.

## Explicit prohibitions

- Do not modify CI configuration (`.prow.yaml`, `Makefile` CI targets, workflow files) to green the PR unless the PR's Jira scope explicitly requires it.
- Do not weaken lint, audit, or security thresholds (e.g. `--audit-level=high`) to bypass fleet-wide CVE findings.
- Do not change generated files to silence failures.
- Do not fix failures classified as infrastructure, pre-existing, flake, or out-of-scope.
- Do not `/retest` or trigger CI jobs — report only.

## Arguments
- `$1`: PR number (optional — current branch if omitted)
- `$2`: `owner/repo` (optional — current repo if omitted)
- `--failing-checks`: JSON array of `{name, state, bucket, link}` objects from `has-review-work`
- `--ci`: Non-interactive CI automation mode; no push; when uncertain, report instead of fix

## Examples

1. **Triage and fix PR-caused failures on current branch**:
   ```text
   /openshift-developer:address-ci-failures
   ```

2. **Process checks from has-review-work gate output**:
   ```text
   /openshift-developer:address-ci-failures 3816 openshift/sippy --failing-checks '[{"name":"ci/prow/lint","state":"FAILURE","bucket":"fail","link":"https://prow.ci.openshift.org/view/..."}]' --ci
   ```

3. **Investigate a specific PR interactively**:
   ```text
   /openshift-developer:address-ci-failures 1234 openshift/origin
   ```

## See Also
- `has-review-work` — read-only gate that detects new CI failures
- `address-review-pr` — handles reviewer comments (not CI failures)
- `ci:prow-job-analysis` — analyze Prow job logs and artifacts
- `github:check-pr-ci-status` — CI status helper with previous-failure tracking
