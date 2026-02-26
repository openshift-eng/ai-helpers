---
description: Revert a merged PR that is breaking CI or nightly payloads
argument-hint: <pr-url> <jira-ticket>
---

## Name

ci:revert-pr

## Synopsis

```
/ci:revert-pr <pr-url> <jira-ticket>
```

## Description

The `ci:revert-pr` command reverts a merged pull request that is breaking CI or nightly payloads. It follows the [OpenShift quick-revert policy](https://github.com/openshift/enhancements/blob/master/enhancements/release/improving-ci-signal.md#quick-revert) to restore CI signal.

This command:

- Extracts the original PR details (title, author, merge commit SHA, base branch)
- Ensures the user has a fork of the repository
- Creates a revert branch and performs `git revert -m1` of the merge commit
- Pushes the revert branch to the user's fork
- Creates a revert PR using the [Revertomatic](https://github.com/stbenjam/revertomatic) template format
- Generates CI override commands (`/override`) for jobs that need to be bypassed on the revert PR

This command is useful when:

- A merged PR is causing CI job failures
- Nightly payloads are blocked by a breaking change
- Quick reversion is needed to restore CI signal while the original author fixes the issue

## Implementation

1. **Parse Arguments**: Extract the PR URL and JIRA ticket

   - PR URL format: `https://github.com/{owner}/{repo}/pull/{number}`
   - JIRA ticket: e.g., `TRT-1234` or `OCPBUGS-56789`
   - If the user provides additional context about why the revert is needed, capture it for the PR body
   - If the user provides verification details (jobs to run before unrevert), capture those too

2. **Gather Context**: Use the JIRA ticket to automatically determine what broke and what needs verification

   - **Look up the JIRA ticket** using the `fetch-jira-issue` skill (`plugins/ci/skills/fetch-jira-issue/fetch_jira_issue.py`) with `--format json`
   - **Extract context from the JIRA issue**: Use the issue summary, description, and comments to determine:
     - **What broke**: Which CI jobs or payloads are failing (e.g., "e2e-aws jobs failing on 4.18 nightly payload")
     - **Verification jobs**: Which jobs should pass before the original change can be re-landed (e.g., "e2e-aws, e2e-gcp")
   - **Compose the context** for the revert PR body from the JIRA issue details. Include links to failing jobs or payloads if mentioned in the ticket.
   - **Fall back to asking the user** only if:
     - The JIRA lookup fails (token not set, network error, ticket not found)
     - The JIRA issue doesn't contain enough information to determine what broke or which jobs to verify
   - If the user provided additional context as inline arguments, combine it with the JIRA-derived context

3. **Perform the Revert**: Use the `revert-pr` skill

   Follow the complete workflow in `plugins/ci/skills/revert-pr/SKILL.md`, which covers:
   - Extracting PR information (title, author, merge SHA, base branch) via `gh`
   - Validating the PR is in MERGED state
   - Ensuring the user has a fork of the repository
   - Detecting commit message conventions (e.g., `UPSTREAM: <carry>:` prefix)
   - Cloning or using an existing local repository
   - Creating the revert branch and performing `git revert -m1`
   - Handling merge conflicts: resolving simple ones directly, or reverting dependent commits for complex ones
   - Pushing to the user's fork
   - Generating CI override commands (filtering out unoverridable jobs)
   - Creating the revert PR with the Revertomatic template (adapting title format for UPSTREAM carry repos)
   - Optionally posting override commands as a PR comment

4. **Report Results**: Display the revert PR URL and next steps

   - Link to the revert PR
   - List of override commands generated
   - Instructions for the original author to unrevert

## Return Value

- **Revert PR URL**: Link to the newly created revert pull request
- **Override Commands**: List of `/override` commands for CI jobs
- **Summary**: Brief description of what was reverted and why

## Examples

1. **Basic revert with context provided inline**:
   ```
   /ci:revert-pr https://github.com/openshift/kubernetes/pull/1703 TRT-9999
   ```
   The command will ask for context and verification details interactively.

2. **Revert with full context**:
   ```
   /ci:revert-pr https://github.com/openshift/cluster-network-operator/pull/2037 OCPBUGS-12345
   This PR broke all e2e-aws jobs on the 4.18 nightly. Verification: run e2e-aws and e2e-gcp.
   ```

## Arguments

- `$1` (required): GitHub PR URL to revert
  - Format: `https://github.com/{owner}/{repo}/pull/{number}`
  - The PR must be in MERGED state
- `$2` (required): JIRA ticket tracking the revert
  - Format: JIRA key (e.g., `TRT-1234`, `OCPBUGS-56789`)
- Additional text (optional): Context explaining why the revert is needed and verification details

## Prerequisites

1. **GitHub CLI (`gh`)**: Must be installed and authenticated
   - Check: `gh auth status`
   - Install: https://cli.github.com/

2. **Git**: Must be installed
   - Check: `which git`

3. **GitHub Token**: The `gh` CLI must have `repo` and `read:org` permissions

## Notes

- This command follows the [Revertomatic](https://github.com/stbenjam/revertomatic) PR template format for consistency
- The original PR author is CC'd in the revert PR body
- To unrevert, the original author should revert the revert PR and layer a fix commit on top
- For repos using `UPSTREAM: <tag>:` commit conventions (e.g., openshift/kubernetes and other repos carrying upstream patches), the commit message and PR title adapt automatically
- Merge conflicts are handled automatically when possible: trivial conflicts are resolved directly, non-trivial ones trigger reverting dependent commits

## See Also

- Related Skill: `revert-pr` - Detailed git revert workflow and PR template (`plugins/ci/skills/revert-pr/SKILL.md`)
- OpenShift Quick Revert Policy: https://github.com/openshift/enhancements/blob/master/enhancements/release/improving-ci-signal.md#quick-revert
- Revertomatic: https://github.com/stbenjam/revertomatic
