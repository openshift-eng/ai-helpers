---
description: Analyze PR review comments to propose CodeRabbit rules for a repository
argument-hint: "<repo> [--count N]"
---

## Name

teams:coderabbit-rules-from-pr-reviews

## Synopsis

```
/teams:coderabbit-rules-from-pr-reviews openshift/origin
/teams:coderabbit-rules-from-pr-reviews https://github.com/openshift/origin
/teams:coderabbit-rules-from-pr-reviews openshift/origin --count 50
```

## Description

The `teams:coderabbit-rules-from-pr-reviews` command analyzes human review comments on recent merged PRs in a GitHub repository to identify recurring review feedback patterns that could be codified as CodeRabbit review rules in the repo's `.coderabbit.yaml` file.

The command fetches the most recent N merged PRs (default: 30), collects all human review comments (excluding comments from `coderabbitai[bot]` and other bots), and uses AI analysis to identify patterns that appear across multiple PRs. Only patterns that are likely to recur in future PRs are proposed as rules -- obscure, one-off, or minor issues are ignored.

After analysis, the command offers to open a PR against the repo that adds or updates the `.coderabbit.yaml` with the proposed rules. It also checks for a `CONTRIBUTING.md` and adds a reference to the CodeRabbit review rules if one is missing. The command is designed to be re-run periodically -- it compares proposed rules against existing rules and only adds net-new ones.

## Arguments

- `<repo>` (required): The GitHub repository to analyze. Accepts either:
  - Full URL: `https://github.com/openshift/origin`
  - Short form: `openshift/origin`
- `--count N` (optional): Number of recent merged PRs to analyze. Default: 30. Higher values give better pattern detection but take longer.

## Implementation

### Prerequisites

- **GitHub CLI (`gh`)**: Must be installed and authenticated with access to the target repo.
- **Python 3**: Python 3.6 or later.

  ```bash
  gh auth status
  python3 --version
  ```

### Steps

1. **Parse the repo argument**: Extract `owner/repo` from the argument. If a full GitHub URL is provided, strip the `https://github.com/` prefix. Validate the format is `owner/repo`.

2. **Fetch and filter PR review comments**: Run the Python script from the `teams:coderabbit-rules-from-pr-reviews` skill to collect human review comments:

   ```bash
   python3 plugins/teams/skills/coderabbit-rules-from-pr-reviews/fetch_pr_comments.py <owner/repo> --count <N>
   ```

   The script handles all GitHub API calls, bot filtering, noise removal, and rate limiting. It outputs JSON to stdout with all filtered human review comments. See the skill documentation for output format details.

   Save the JSON output for analysis in the next step.

3. **Analyze comments for patterns**: Parse the JSON output from the script. Analyze the collected human review comments to identify:

   - **Recurring patterns**: Issues or feedback that appears in 3+ different PRs, or from 2+ different reviewers on similar topics
   - **Categories to look for**:
     - Code style and formatting issues (naming conventions, import ordering, etc.)
     - Error handling patterns (missing error checks, swallowed errors, etc.)
     - Testing gaps (missing tests for edge cases, missing negative tests, etc.)
     - API/interface misuse (deprecated APIs, incorrect usage patterns, etc.)
     - Documentation gaps (missing godoc, unclear comments, etc.)
     - Security concerns (hardcoded values, missing input validation, etc.)
     - Performance issues (unnecessary allocations, missing context propagation, etc.)
     - Go-specific patterns (if applicable): nil checks, goroutine leaks, defer misuse, etc.
     - Kubernetes/OpenShift patterns (if applicable): label conventions, finalizer handling, status update patterns, etc.

   **What to ignore**:
   - One-off issues specific to a single PR's logic
   - Minor nitpicks that wouldn't meaningfully improve code quality
   - Subjective style preferences from a single reviewer
   - Comments that are questions or discussions rather than actionable feedback
   - Merge conflict or rebase-related comments

4. **Check existing CodeRabbit config**: Fetch the repo's current `.coderabbit.yaml` (or `.coderabbit.yml`) if it exists:

   ```bash
   gh api repos/<owner/repo>/contents/.coderabbit.yaml --jq '.content' 2>/dev/null | base64 -d
   ```

   If a config exists, parse all existing `path_instructions` rules and compare them against the proposed rules. **De-duplicate**: drop any proposed rule whose intent is already covered by an existing rule (same path pattern with overlapping instruction content). Only present net-new rules in the report. This ensures the command can be re-run periodically without creating redundant rules.

5. **Format the output as a report**: Present findings as a structured report:

   ```
   ## CodeRabbit Rules from PR Reviews: <owner/repo>

   **PRs analyzed**: <count>
   **Review comments collected**: <total_human_comments>
   **Reviewers represented**: <unique_reviewer_count>

   ### Proposed New Rules

   For each identified pattern (only rules not already in existing config):

   #### Rule <N>: <Short descriptive title>

   **Pattern**: <Description of what reviewers are catching>
   **Evidence**: Found in <X> PRs by <Y> different reviewers
   **Example PRs**: #123, #456, #789
   **Example comments**:
   > <quoted reviewer comment from PR #123>
   > <quoted reviewer comment from PR #456>

   **Proposed `.coderabbit.yaml` rule**:
   ```yaml
   reviews:
     path_instructions:
       - path: "<glob pattern>"
         instructions: |
           <instruction text>
   ```

   ### Already Covered by Existing Rules

   <List any patterns found in reviews that are already addressed by existing .coderabbit.yaml rules, with brief explanation of which existing rule covers it>

   ### Summary

   - Total patterns identified: <N>
   - Already covered by existing rules: <N>
   - Net-new rules proposed: <N>

   ### Existing Config

   <Show current .coderabbit.yaml contents if present, or note that none exists>
   ```

6. **Offer to open a PR**: After presenting the report, ask the user:

   > Would you like me to open a PR to add these rules to the repo's `.coderabbit.yaml`?

   If the user declines, stop here. If the user accepts, proceed with steps 7-12.

7. **Fork and clone the repo**: Use a temporary working directory. Fork the repo (idempotent) and clone it:

   ```bash
   REPO="<owner/repo>"
   REPO_NAME="${REPO##*/}"
   GH_USER=$(gh api user --jq '.login')
   WORKDIR="/tmp/cr-rules-workdir/${REPO_NAME}"
   BRANCH_NAME="coderabbit-rules-from-reviews"
   UPSTREAM_DEFAULT=$(gh repo view "${REPO}" --json defaultBranchRef --jq '.defaultBranchRef.name')

   # Fork (idempotent)
   gh repo fork "${REPO}" --clone=false 2>&1 || true
   sleep 2

   # The fork's default branch may differ from upstream (e.g., fork uses "master"
   # while upstream uses "main"). Detect the fork's actual default branch.
   FORK_DEFAULT=$(gh repo view "${GH_USER}/${REPO_NAME}" --json defaultBranchRef --jq '.defaultBranchRef.name')

   # Sync fork's default branch with upstream's default branch
   gh repo sync "${GH_USER}/${REPO_NAME}" --source "${REPO}" --branch "${FORK_DEFAULT}" 2>&1

   # Delete stale branch from previous runs
   gh api -X DELETE "repos/${GH_USER}/${REPO_NAME}/git/refs/heads/${BRANCH_NAME}" 2>/dev/null || true
   sleep 1

   # Clone using the fork's default branch, then create a working branch
   rm -rf "${WORKDIR}"
   gh repo clone "${GH_USER}/${REPO_NAME}" "${WORKDIR}" -- -b "${FORK_DEFAULT}" --depth 1
   cd "${WORKDIR}"
   git checkout -b "${BRANCH_NAME}"
   ```

   **Important**: Use `UPSTREAM_DEFAULT` (not `FORK_DEFAULT`) as the PR base branch in step 11, since
   the PR targets the upstream repo.

8. **Create or update `.coderabbit.yaml`**: In the cloned repo:

   - **If no `.coderabbit.yaml` exists**: Create a new file with `inheritance: true` at the top (so org-wide rules are preserved) followed by the proposed `path_instructions` rules:
     ```yaml
     inheritance: true
     reviews:
       path_instructions:
         - path: "<glob>"
           instructions: |
             <instruction>
     ```

   - **If `.coderabbit.yaml` already exists**: Parse the existing file and merge in the new rules. Append new `path_instructions` entries after existing ones. Do not modify or remove any existing content. Preserve `inheritance: true` if present; add it if missing. Preserve all existing YAML structure, comments, and formatting as much as possible.

9. **Check and update `CONTRIBUTING.md`**: Look for `CONTRIBUTING.md` or `CONTRIBUTING` (case-insensitive) in the repo root:

    ```bash
    ls -1 "${WORKDIR}" | grep -i '^contributing'
    ```

    - **If a contributing file exists**: Check if it already references `.coderabbit.yaml` or CodeRabbit review rules (case-insensitive search). If not, append a section:
      ```markdown

      ## Automated Code Review

      This repository uses [CodeRabbit](https://coderabbit.ai) for automated code review.
      Review rules are defined in [`.coderabbit.yaml`](.coderabbit.yaml) and encode
      common patterns identified from past PR reviews. Please review these rules when
      contributing to understand the standards enforced during automated review.
      ```

    - **If no contributing file exists**: Do nothing -- do not create a CONTRIBUTING.md from scratch, as the repo may intentionally not have one.

10. **Commit the changes**: Create a single commit with all changes:

    ```bash
    git add .coderabbit.yaml
    # Only add CONTRIBUTING.md if it was modified
    git diff --name-only | grep -i contributing && git add CONTRIBUTING.md CONTRIBUTING contributing.md 2>/dev/null || true

    git commit -m "$(cat <<'COMMITEOF'
    Add CodeRabbit review rules derived from PR review patterns

    Analyzed recent merged PRs to identify recurring review feedback patterns
    and codified them as CodeRabbit path_instructions rules. These rules help
    catch common issues automatically during code review.

    Generated by teams:coderabbit-rules-from-pr-reviews
    COMMITEOF
    )"
    ```

11. **Push and open PR**:

    ```bash
    git push origin "${BRANCH_NAME}"

    gh pr create \
      --repo "${REPO}" \
      --head "${GH_USER}:${BRANCH_NAME}" \
      --base "${UPSTREAM_DEFAULT}" \
      --title "Add CodeRabbit review rules from PR review patterns" \
      --body "$(cat <<'BODYEOF'
    ## Summary

    This PR adds CodeRabbit review rules to `.coderabbit.yaml` based on patterns
    identified from analyzing recent merged PR review comments. These rules encode
    recurring feedback from human reviewers so that CodeRabbit can catch the same
    issues automatically in future PRs.

    ### Rules added

    <list each rule title and a one-line description>

    ### How these were identified

    Analyzed the most recent <N> merged PRs and collected human review comments
    (excluding bots, approvals, and prow commands). Patterns appearing in 3+ PRs
    or from 2+ different reviewers were proposed as rules.

    ### Re-running

    This command can be re-run periodically to identify new patterns:
    ```
    /teams:coderabbit-rules-from-pr-reviews <owner/repo>
    ```
    It compares against existing rules and only proposes net-new additions.

    Generated by `teams:coderabbit-rules-from-pr-reviews`
    BODYEOF
    )"
    ```

    **Important**: Customize the PR body before creating it. Replace the `<list each rule title...>` placeholder with the actual rules being added, and replace `<N>` with the actual PR count analyzed.

12. **Report the result**: Display the PR URL to the user. Clean up by noting the temp directory path but do not delete it (in case the user wants to inspect it).

## Skills Used

This command delegates to the following skill:

- `teams:coderabbit-rules-from-pr-reviews` - Fetch and filter human review comments from recent merged PRs

## Return Value

- **Markdown report**: Identified patterns, evidence, and proposed CodeRabbit rules
- **YAML snippets**: Ready-to-use `.coderabbit.yaml` rule definitions
- **PR URL**: Link to the opened PR (if user accepted)

## Examples

1. **Analyze default number of PRs**:
   ```
   /teams:coderabbit-rules-from-pr-reviews openshift/origin
   ```

2. **Analyze more PRs for better pattern detection**:
   ```
   /teams:coderabbit-rules-from-pr-reviews openshift/origin --count 50
   ```

3. **Using full URL**:
   ```
   /teams:coderabbit-rules-from-pr-reviews https://github.com/openshift/cluster-kube-apiserver-operator
   ```

## Notes

- **Idempotent / re-runnable**: The command compares proposed rules against the repo's existing `.coderabbit.yaml` and only proposes net-new rules. This makes it safe to re-run periodically to keep rules up to date as new review patterns emerge.
- **Fork-based PRs**: PRs are always opened from the authenticated user's fork, never by pushing directly to the upstream repo. The fork is created automatically if it doesn't exist.
- **Stale branch cleanup**: If the branch `coderabbit-rules-from-reviews` already exists on the fork (from a previous run), it is deleted before pushing to ensure a clean state.
- **CONTRIBUTING.md**: If the repo has a `CONTRIBUTING.md`, the command adds a reference to `.coderabbit.yaml` so contributors know about the automated review rules. It does not create a `CONTRIBUTING.md` if one doesn't exist.
- **Bot filtering**: The Python script excludes comments from `coderabbitai[bot]` and other known bots automatically.
- **Rate limiting**: The script adds 0.5s sleeps between API calls with retry logic for rate limit errors. Analyzing 30 PRs typically takes 1-2 minutes.
- **Comment quality**: Short comments (<20 chars), pure approvals, and Prow commands are filtered out by the script.
- **Pattern threshold**: Only patterns appearing in 3+ PRs or from 2+ different reviewers are proposed as rules. This ensures rules target genuinely recurring issues, not one-off problems.
- **CodeRabbit rule format**: Proposed rules use the `path_instructions` format which associates review instructions with file path glob patterns. See [CodeRabbit docs](https://docs.coderabbit.ai/guides/review-instructions) for the full rule specification.
- **Inheritance preserved**: When creating or updating `.coderabbit.yaml`, the command ensures `inheritance: true` is set so org-wide rules from [openshift/coderabbit](https://github.com/openshift/coderabbit) continue to apply.
- The command works with any GitHub repository accessible to the authenticated `gh` user, not just OpenShift repos.

## See Also

- Related Command: `/teams:coderabbit-inheritance-scanner` - Scan repos for CodeRabbit config inheritance
- Related Command: `/teams:coderabbit-adoption-report` - Report on CodeRabbit adoption
- Global CodeRabbit config: https://github.com/openshift/coderabbit
- CodeRabbit review instructions docs: https://docs.coderabbit.ai/guides/review-instructions
