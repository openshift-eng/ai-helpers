---
name: address-review-precommit
description: Compatibility alias for applying pre-commit review findings through the implement skill. Use when an existing caller has not migrated to openshift-developer:implement.
---

## Name
openshift-developer:address-review-precommit

## Synopsis
```text
/openshift-developer:address-review-precommit
```

## Compatibility behavior

This skill is a temporary backward-compatible entry point. Delegate the complete request
to `/openshift-developer:implement` with the review findings from the current conversation
or preceding `/code-review:pre-commit-review` invocation.

- Preserve `--ci` or any caller prohibition on prompting, pushing, or creating a PR.
- Pass the Jira issue key and implementation plan when they are available.
- Use `--defer-commit` when a later review or `check-gates` step will commit the final
  result; otherwise allow `implement` to create or amend the appropriate commit.
- Return the result produced by `implement`.

Do not independently edit code, run a second verification workflow, push, or create a
pull request. New integrations should invoke `/openshift-developer:implement` directly.
