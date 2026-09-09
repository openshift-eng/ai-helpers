---
name: check-gates
description: Repeatedly validate and fix a Jira implementation until tests, lint, builds, requirements, production readiness, and repository cleanliness all pass. Use as the final quality gate before delivery.
---

## Name
openshift-developer:check-gates

## Synopsis
```text
/openshift-developer:check-gates <ISSUE_KEY> [--ci]
```

## Success condition

Do not report success until all of these are true for `%ISSUE_KEY%`:

- Tests pass.
- Linting and repository verification are clean.
- Builds succeed.
- Every implementation requirement is satisfied.
- The changes are production-ready.
- `git status --short` is empty.

If any gate fails, diagnose it, fix in-scope failures, and re-run every gate affected by
the fix. Continue until the complete success condition holds. A previous successful run
does not remain valid after another edit.

## Workflow

1. Resolve the Jira issue and build an explicit acceptance checklist from its description,
   acceptance criteria, reproduction details, and later clarifications. Inspect the
   current diff and commit history against that checklist.
2. Discover repository-prescribed validation commands from `AGENTS.md`, contributor
   documentation, CI configuration, and the Makefile. At minimum, run applicable:
   - Unit and integration tests for changed behavior, followed by the repository test
     target when one exists.
   - Formatting, lint, generated-file, and verification targets.
   - Build targets covering affected binaries, images, or packages.
3. Review the implementation for production readiness: error paths, upgrade and rollback
   behavior where relevant, concurrency/idempotency, security boundaries, observability,
   compatibility, tests, and documentation. Apply these checks proportionally to the
   change; do not invent unrelated work.
4. For each failure:
   - Determine whether it is caused by the implementation, pre-existing, environmental,
     or outside the issue scope.
   - Fix implementation-caused and in-scope failures, using `implement` when substantive
     coding is needed.
   - Re-run the failed gate and any gate invalidated by the edit.
   - Never weaken a check, delete a legitimate test, or hide a failure to obtain a pass.
5. Run `git diff --check` and inspect `git status --short`. Commit all in-scope source,
   test, documentation, and generated changes in logical conventional commits. Do not
   discard, overwrite, or commit unrelated user changes.
6. Perform one final complete pass of the acceptance checklist and all applicable gates
   after the last commit. Confirm `git status --short` produces no output.

## Blocking conditions

The normal stopping condition is complete success. If an external dependency,
unavailable required environment, contradictory acceptance criterion, or unrelated dirty
worktree makes success impossible, do not claim the gates passed. Exhaust safe in-scope
alternatives, then report the exact blocker and the remaining unsatisfied gates. Under
`--ci`, do not prompt, push, create a PR, or mutate external systems.

## Return value

Report each gate and its final command/evidence, the acceptance checklist result, final
commit hashes, and confirmation that the working tree is clean.
