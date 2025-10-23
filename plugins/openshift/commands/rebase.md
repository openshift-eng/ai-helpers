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
    echo -e 'Comment Sha\tMessage' > commits.tsv
    git log ${mergebase}..openshift/master --ancestry-path --reverse --no-merges --pretty="tformat:%h%x09%s" | grep "UPSTREAM:" > commits.tsv
    ```

9. Go through the commits in the `commits.tsv` file and for each of them decide
    whether to pick, drop or squash it. Commits carried on rebase branches have commit
    messages prefixed as follows:

    * `UPSTREAM: <carry>`:
        A persistent carry that should probably be picked for the subsequent rebase branch.

    * `UPSTREAM: <drop>`:
        A carry that should probably not be picked for the subsequent rebase branch.
        In general, these commits are used to maintain the codebase in ways that are branch-specific,
        like the update of generated files or dependencies.

    * `UPSTREAM: (upstream PR number)`:
        The number identifies a PR in upstream repository (e.g. https://github.com/<upstream project>/<upstrem repository>/pull/<pr id>).
        A commit with this message should only be picked into the subsequent rebase branch if the commits
        of the referenced PR are not included in the upstream branch. To check if a given commit is included
        in the upstream branch, open the referenced upstream PR and check any of its commits for the release tag.

        For each commit print the decission you made and why.

10. Squash any cherry-picked commits that modify only OpenShift specific files into a single commit named "UPSTREAM: <carry>: Add OpenShift files"
    to keep the number of <carry> commits as low as possible.
    OpenShift specific files are files that bring OpenShift-specific changes, such as Dockerfiles, OWNERS, various files necessary to build an OpenShift image etc.
    For each cherry-picked commit print the decission you made about squashing it and describe why.

11. As a verification step, find all differences between `$previous_tag` and `openshift/master`.
    Verify each commit that all commit changes were applied during the rebase. Either as a cherry-picked patch or they were included in the new upstream tag.
    list all these commits, together with checks you made and their result.

12. Verify the changes by running `make` and `make test` (or a similar unit-test).
    Stop here if these commands fail. Summarize the errors, suggest a fix. Do not continue with following steps.

13. Find links to upstream changelogs between `$previous_tag` and $1.
    Make sure they are links to changelogs, not tags.
    Print list of the links.

14. Create a github pull request against the OpenShift github repository.
    The PR title should be "Rebase to $1 for OCP <current OCP version>".
    Decription of the PR must look like:
    ```
    ## Upstream changelogs
    <List links to all upstream changelogs, as composed in the previous step.>

    ## Summary of changes
    <List all new features and major updates that happened between $previous_tag and $1. Do not list upstream commits or PRs, make a human readable summary of them.>

    ## Carried commits
    <List of commits from commits.tsv. For each commit print a decission you made - either "drop", "carry", or "squash".>

    Diff to upstream: <link to a diff between the upstream project/upstream repository/tag $1 and this PR (i.e. my personal fork with branch `rebase-$1`>
    ```
    When opening the PR, ALWAYS use `gc pr create --web` to allow user edit the PR before creation.
