---
name: jira-solve
description: Analyze a JIRA issue and create a pull request to solve it. Use when the user wants to implement a fix or feature described in a Jira issue, push a branch, and open a draft PR.
---

## Name
openshift-developer:jira-solve

## Synopsis
```text
/openshift-developer:jira-solve <jira-issue-id> [remote] [--ci]
```

## Description

Analyzes a JIRA issue, implements a solution in the current repository, and creates a comprehensive pull request with the necessary changes.

Takes a JIRA URL or issue key, fetches the issue description and requirements, analyzes the codebase to understand how to implement the solution, and produces a branch with well-structured commits.

## Implementation

### Step 1: Issue Analysis

Parse the JIRA issue and fetch details:

1. Use curl to fetch JIRA issue data:
   ```bash
   curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" "https://redhat.atlassian.net/rest/api/3/issue/{$1}"
   ```
2. Parse JSON response to extract:
   - Issue summary and description
   - From within the description expect the following sections:
     - Required: Context, Acceptance criteria
     - Optional: Steps to reproduce (for bugs), Expected vs actual behavior
3. If `--ci` flag (`$3`) is NOT set: Ask the user for further issue grooming if the required sections are missing
4. If `--ci` flag (`$3`) IS set: Proceed with available information, making reasonable assumptions where needed

### Step 2: Codebase Analysis

Search and analyze relevant code:

- Find related files and functions
- Understand current implementation
- Identify areas that need changes
- Use Grep and Glob tools to search for:
  - Related function names mentioned in JIRA
  - File patterns related to the component
  - Similar existing implementations
  - Test files that need updates

### Step 3: Solution Implementation

1. Think hard and create a detailed, step-by-step plan. Save it to `spec-$1.md` within the `.work/solve/` folder (e.g. `.work/solve/spec-OCPBUGS-12345.md`)
2. If `--ci` flag (`$3`) is NOT set: Ask the user to review the plan and give them the choice to modify it before starting
3. If `--ci` flag (`$3`) IS set: Proceed immediately without waiting for approval
4. Implement the plan:
   - Make necessary code changes using Edit/MultiEdit tools
   - Follow existing code patterns and conventions
   - Add or update tests when code behavior changes or new functions are introduced
   - Update documentation if needed within the `docs/` folder
   - If the problem is too complex consider delegating to one of the SME agents
   - Ensure godoc comments are generated for any newly created public functions
     - Use your best judgement if godoc comments are needed for private functions
     - A comment should not be generated for a simple function like `func add(int a, b) int { return a + b }`
   - Create unit tests for any newly created functions

### Step 4: Commit Creation

1. Create feature branch using the jira-key `$1` as the branch name (e.g. `git checkout -b fix-{jira-key}`)
2. Break commits into logical components based on the nature of the changes
3. Each commit must honor https://www.conventionalcommits.org/en/v1.0.0/ and always include a commit message body articulating the "why"
4. Use your judgment to organize commits in a way that makes them easy to review and understand
5. Common logical groupings (use as guidance, not rigid rules):
   - API changes: Changes in `api/` directory (types, CRDs)
     - Example: `git commit -m"feat(api): Update HostedCluster API for X" -m"Add new fields to support Y functionality"`
   - Vendor changes: Dependency updates in `vendor/` directory
     - Example: `git commit -m"chore(vendor): Update dependencies for X" -m"Required to pick up bug fixes in upstream library Y"`
   - Generated code: Auto-generated clients, informers, listers, and CRDs
     - Example: `git commit -m"chore(generated): Regenerate clients and CRDs" -m"Regenerate after API changes to ensure client code is in sync"`
   - CLI changes: User-facing command changes in `cmd/` directory
     - Example: `git commit -m"feat(cli): Add support for X flag" -m"This allows users to configure Y behavior at cluster creation time"`
   - Operator changes: Controller logic in `operator/` or `controllers/`
     - Example: `git commit -m"feat(operator): Implement X controller logic" -m"Without this the controller won't reconcile when Y condition occurs"`
   - Support/utilities: Shared code in `support/` directory
     - Example: `git commit -m"refactor(support): Extract common X utility" -m"Consolidate duplicated logic from multiple controllers into shared helper"`
   - Tests: Test additions or modifications
     - Example: `git commit -m"test: Add tests for X functionality" -m"Ensure the new behavior is covered by unit tests to prevent regressions"`
   - Documentation: Changes in `docs/` directory
     - Example: `git commit -m"docs: Document X feature" -m"Help users understand how to configure and use the new capability"`
6. Push the feature branch (the one created in step 1) with all commits to the remote specified in argument `$2` — unless the caller's context prohibits pushing (e.g. a "do not push" directive), in which case commit locally and skip the push. Only ever push that feature branch; never push to `main`/`master`, and never force-push.

### Step 5: PR Creation

By this point you have committed the fix and, unless pushing was prohibited, pushed the branch in Step 4. This step only decides whether to *also* open a pull request; do not open one if the branch was not pushed.

- If `--ci` flag (`$3`) IS set: **Do NOT open a pull request under any circumstances.** This overrides every other instruction in this skill about opening or drafting a PR — do not run `gh pr create` and do not open a PR by any other means. In CI, opening the PR is the responsibility of a later pipeline step, not this skill. Output: "Skipping PR creation in CI mode — PR will be created by the pipeline."
- If `--ci` flag (`$3`) is NOT set: open a pull request with:
  - Clear title referencing JIRA issue as a prefix (e.g. `OCPBUGS-12345: ...`)
  - The PR description should satisfy the template within `.github/PULL_REQUEST_TEMPLATE.md` if the file exists
  - Always include the following footer:
    ```text
    Always review AI generated responses prior to use.
    Generated with AI assistance via openshift-developer plugin
    ```
  - Create it as a draft PR
  - Create the PR using the branch you pushed to `$2` as the head — do not assume a remote named `origin`; for a fork, pass an owner-qualified head (e.g. `gh pr create --head <fork-owner>:<branch>`)
  - Use gh cli if you need to

### Step 6: PR Description Review

- If `--ci` flag (`$3`) IS set: Skip — no PR was created in CI mode.
- If `--ci` flag (`$3`) is NOT set:
  - After creating the PR, display the PR URL and description to the user
  - Ask the user: "Please review the PR description. Would you like me to update it? (yes/no)"
  - If the user says yes or requests changes:
    - Ask what changes they'd like to make
    - Update the PR description using `gh pr edit {PR_NUMBER} --body "{new_description}"`
    - Repeat this review step until the user is satisfied
  - If the user says no or is satisfied, acknowledge and provide next steps

## Arguments
- `$1` — The JIRA issue to solve (required)
- `$2` — The remote repository to push the branch (required)
- `$3` — Optional `--ci` flag for non-interactive CI automation mode. When set, skips all user prompts, proceeds automatically, and does NOT open a pull request (PR creation is left to the pipeline).

## Examples

1. **Solve a specific JIRA issue**:
   ```text
   /openshift-developer:jira-solve OCPBUGS-12345 origin
   ```

2. **Solve in CI mode (non-interactive, no PR — PR left to the pipeline)**:
   ```text
   /openshift-developer:jira-solve OCPBUGS-12345 origin --ci
   ```

## Guidelines

- Authentication uses Basic auth with `JIRA_USERNAME` and `JIRA_API_TOKEN` for Atlassian Cloud
- The command will provide progress updates and create a comprehensive solution addressing all requirements from the JIRA issue
