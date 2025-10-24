---
argument-hint: <tag>
description: Rebase OpenShift fork of an upstream repository to a new upstream release.
---

## Name
openshift:rebase

## Synopsis
```
/openshift:rebase [tag]
```

## Description

The `/openshift:rebase` command rebases git repository in the current working directory
to a new upstream release specified by `[tag]`. If no `[tag]` is specified, the command
tries to find the latest stable upstream release.

The repository must follow rules described in https://github.com/openshift/kubernetes/blob/master/REBASE.openshift.md,
namely all OpenShift-specific commits must have prefix `UPSTREAM:`.

## Workflow

### Pre-requisites
Three local remote repositories should be tracked from a local machine: `origin`
tracking the user's fork of this repository, `openshift` tracking this
repository and `upstream` tracking the upstream repository.

To verify the correct setup, use
```bash
git remote -v
```

Fail, if there is no `upstream`, `origin` or `openshift` remote.

### Rebase to the new upstream version

1. Fetch all the remote repositories including tags
    ```bash
    git fetch --all
    ```

2. Find the main branch of the repository. It's either `master` or `main`. In the following steps, we will use `master`, but replace it with the main branch.

3. If user did not specify an upstream tag to rebase to as `<tag>`, find the greatest upstream tag that is not alpha, beta or rc.

4. Create a new branch based on the newest tag $1 of the upstream
    repository. Name it after the tag.
    ```bash
    git checkout -b rebase-<tag> <tag>
    ```

5. Merge `openshift/master` branch into the `rebase-$1` branch with merge strategy `ours`:
    ```bash
    git merge -s ours openshift/master
    ```

6. Find the last rebase that has been done to `openshift/master`. We will use the upstream tag used for this rebase as `$previous_tag`.

7. Find the merge base of the `openshift/master` and `$previous_tag` by running `git merge-base openshift/master $previous_tag`. We will use this merge base as `$mergebase`.

8. Prepare `commits.tsv` tab-separated values file containing the set of carry
    commits in the openshift/master branch that need to be considered for picking:

    Create the commits file:
    ```
    echo -e 'Sha\tMessage\tDecision' > commits.tsv
    git log ${mergebase}..openshift/master --ancestry-path --reverse --no-merges --pretty="tformat:%h%x09%s%x09" | grep "UPSTREAM:" > commits.tsv
    ```

9. Go through the commits in the `commits.tsv` file and for each of them decide
    whether to pick, drop or squash it. Commits carried on rebase branches have commit
    messages prefixed as follows:

    * `UPSTREAM: <carry>: Add OpenShift files`:
        ALWAYS carry this commit and mark it as "cherry-pick".
        This is a persistent carry that contains all OpenShift-specific files and should be present in every rebase.

    * Other `UPSTREAM: <carry>` commit:
        A persistent carry that needs to be considered for squashing.
        Examine what files it modifies using `git show --stat <commit-sha>`.
        If it modifies ONLY OpenShift-specific files (Dockerfile, OWNERS, .ci-operator.yaml, .snyk, etc.), mark it as "squash",
        otherwise mark is as "cherry-pick".

    * `UPSTREAM: <drop>`:
        A carry that should probably not be picked for the subsequent rebase branch.
        In general, these commits are used to maintain the codebase in ways that are branch-specific,
        like the update of generated files or dependencies.
        Mark such commit as "drop".

    * `UPSTREAM: (upstream PR number)`:
        The number identifies a PR in upstream repository (e.g. https://github.com/<upstream project>/<upstrem repository>/pull/<pr id>).
        A commit with this message should only be picked into the subsequent rebase branch if the commits
        of the referenced PR are not included in the upstream branch. To check if a given commit is included
        in the upstream branch, open the referenced upstream PR and check any of its commits for the release tag.

    For each commit:
    - Print the decision you made and why.
    - Update commits.tsv with the decision ("cherry-pick", "drop", or "squash").

10. Cherry-pick all commits marked as "cherry-pick" in commits.tsv.
    Then squash ALL commits marked as "squash" into a single commit named "UPSTREAM: <carry>: Add OpenShift files"
    to keep the number of <carry> commits as low as possible.

    Use `git reset --soft` to squash multiple commits together, then create a single commit with all the changes.
    The commit message should list what was included (e.g., "Additional changes: remove .github files, add .snyk file, update Dockerfile and .ci-operator.yaml").

11. If the upstream repository DOES NOT include `vendor/` directory and the OpenShift fork DOES, then update the vendor directory with `go mod tidy` and `go mod vendor`.
    Amend these vendor updates into the "UPSTREAM: <carry>: Add OpenShift files" commit using `git commit --amend --no-edit`.

12. As a verification step, see the last rebase and ensure that all changes made in the last rebase are present in the current one.
    Either as a cherry pick or were part of the rebase.
    Verify all changes were applied during the rebase. Either as a cherry-picked patch or they were included in the new upstream tag.
    List all these commits, together with checks you made and their result.

13. Verify the changes by running `make` and `make test` (or a similar command like like `go build ./...` and `go test ./...`).
    Stop here if there are compilation errors or test failures that indicate real code issues.
    If you make any new commits to fix compilation or tests, let user review these changes and then squash them into the commit "UPSTREAM: <carry>: Add OpenShift files" too.

14. Find links to upstream changelogs between `$previous_tag` and $1.
    Make sure they are links to changelogs, not tags.
    Print list of the links.

15. Create a github pull request against the OpenShift github repository (openshift/<repo-name>).
    IMPORTANT: Use `--repo openshift/<repo-name>` to ensure the PR is created against the correct OpenShift repository, not the upstream.
    The PR title should be "Rebase to $1 for OCP <current OCP version>".
    Follow the repository .github/PULL_REQUEST_TEMPLATE.md, if it exists.
    Description of the PR must look like:
    ```
    ## Upstream changelogs
    <List links to all upstream changelogs, as composed in the previous step.>

    ## Summary of changes
    <List all new major features and breaking changes that happened between $previous_tag and $1.
    Do not list upstream commits or PRs, make a human readable summary of them.
    Do not include small bug fixes, small updates, or dependency bumps.>

    ## Carried commits
    <List of commits from commits.tsv. For each commit print a decision you made - either "drop", "cherry-pick", or "squash".>

    Diff to upstream: <link to a diff between the upstream project/upstream repository/tag $1 and this PR (i.e. my personal fork with branch `rebase-$1`>

    Previous rebase: <link to the previous rebase PR on github>
    ```
    When opening the PR, ALWAYS use `gh pr create --web --repo openshift/<repo-name>` to allow user edit the PR before creation.
