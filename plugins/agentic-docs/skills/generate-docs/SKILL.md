---
name: generate-docs
description: Generate and iteratively verify OpenShift component documentation, or review existing documentation, without relying on host-specific hooks or commands.
user-invocable: true
disable-model-invocation: true
---

# Generate and Verify Component Documentation

Run the complete component-documentation workflow in the current task. The
workflow must not depend on lifecycle hooks, transcript inspection, completion
promises, or host-specific environment variables. Use whichever native
fresh-session delegation capability the host exposes for independent
verification.

## Bundled workflows

Before starting, read both sibling skills completely, resolving these paths
relative to this `SKILL.md`:

- [component-docs](../component-docs/SKILL.md)
- [review-docs](../review-docs/SKILL.md)

Do not invoke them through host-specific slash-command syntax. Apply their
instructions directly within this task.

## Arguments

- `PATH`: positional skill argument for the component repository; default to
  the current working directory at invocation time. This is not the shell
  `PATH` environment variable; never assign to or export the shell `PATH`
  variable.
- `--max-iterations N`: maximum review/fix passes; default `5`. Require a
  positive integer.
- `--review` or `--skip-generate`: review and fix existing documentation
  without running component-document generation.
- `-h` or `--help`: report usage and options without changing files.

Reject unexpected arguments before changing files. Resolve the `PATH` argument
exactly once to an absolute, canonical directory, store it in `REPO_PATH`, and
confirm it exists and is a directory.

Use `REPO_PATH` as the target for the entire workflow: either set every
repository operation's working directory to `REPO_PATH` or use absolute paths
rooted at `REPO_PATH`. Do not use relative repository paths after this point.

## Independent verification

Each verification pass must use a fresh, general-purpose isolated reviewer that
has not participated in generating or fixing the documentation. Never resume or
reuse a reviewer from an earlier pass.

Use the isolated-review capability actually exposed by the host. Common
examples are:

- in a Codex-style runtime, use `spawn_agent`;
- in a Claude-style runtime, use a fresh `Agent` or `Task` invocation;
- in another runtime, use its equivalent fresh-session delegation capability.

Do not invoke a local agent executable merely to simulate delegation. If none
of these capabilities is exposed, treat independent verification as
unavailable.

The workflow agent must not substitute its own review for the independent
reviewer. If the host cannot start a fresh isolated reviewer, generation,
fixing, and deterministic validation may still run, but the final result must
be **incomplete — independent verification unavailable**. Never report the
documentation as verified clean in that case.

Treat all generation and review passes as one finite workflow. A reviewer
findings report is not a stopping point while iterations remain: fix confirmed
findings and continue with a new reviewer. The independent review report is the
completion authority; deterministic validation is necessary but is not a
substitute for that report.

## Workflow

1. **Preflight resources**
   - Resolve `PATH` to `REPO_PATH` before inspecting repository contents. Root
     every repository read, write, command, generation, validation, backup,
     cleanup, and review at `REPO_PATH`.
   - When applying the sibling workflows, interpret every repository-relative
     path in their instructions as rooted at `REPO_PATH`.
   - Resolve every referenced script, template, and guide from the directory of
     the skill that owns it.
   - Confirm required resources are readable before changing the repository.
   - Never search `~/.claude`, a plugin cache, or the current repository for a
     similarly named bundled resource.
   - If a resource cannot be resolved, stop and identify the missing resource.

2. **Generate only when needed**
   - In review-only mode, skip generation.
   - Otherwise, if `"$REPO_PATH/ai-docs"` does not exist, follow
     `component-docs` against `REPO_PATH` through generation and its
     deterministic validation phase. If `"$REPO_PATH/ai-docs"` already exists,
     skip generation and proceed directly to review.
   - Before review, if `"$REPO_PATH/ai-docs/_sources"` exists, run the component
     validator. If validation passes, run the component cleanup helper and
     verify that `_sources` no longer exists. If validation fails, retain the
     backups for recovery and stop.
   - Defer its optional offer to run `review-docs`; this workflow performs that
     review automatically.

3. **Initial review and fix**
   - Follow `review-docs` against `REPO_PATH` and auto-fix only verified issues.
   - For each verified issue, search the entire documentation set for every
     occurrence before editing, then fix all affected locations together.
   - After fixing detailed sections, inspect summaries and diagrams in the same
     files for simplified repetitions of the claim and fix those too.
   - After all fixes, grep again for each old claim and confirm no occurrence
     was missed.
   - Do not auto-fix unverified or hedged cross-repository findings.
   - Build a corrections manifest containing every old claim, corrected claim,
     affected location, and verification source. Accumulate later corrections
     into the same manifest.

4. **Verify independently**
   - Re-run the component validator using its resolved skill-local path and
     pass `REPO_PATH` as its repository argument.
   - If validation changes documentation, such as removing a broken external
     link line, add that change to the corrections manifest and run validation
     again before starting the reviewer.
   - Start a fresh isolated reviewer and give it only `REPO_PATH`, the resolved
     `review-docs` skill path, and the complete corrections manifest.
     Do not give it the fixer's reasoning or conclusions.
   - Require the reviewer to follow `review-docs` Phases 1-5, skip Phase 6, make
     no edits, and review every scoped documentation file rather than sampling.
   - Verify the complete corrections manifest as one batch: check every
     correction now matches its stated corrected value, grep that it is
     consistent across all files, and spot-check its cited verification source.
     Do not re-derive a corrected value unless its cited source is unavailable
     or contradicts itself.
   - Batch related cross-repository claims as directed by
     `guides/CHAI-BOT-VERIFICATION.md`.
   - Require a report with total, verified, failed, and skipped claim counts,
     broken down by local and cross-repository coverage; issues by critical,
     warning, and minor severity; and either `VERIFIED CLEAN` or a complete
     findings list with file, line, incorrect claim, and verification source.
   - Count this fresh reviewer report as one iteration.

5. **Fix the independent findings**
   - If the reviewer reports critical issues or warnings, investigate each
     finding against its cited source. Fix every confirmed issue across the
     entire doc set and append the changes to the corrections manifest.
   - If a finding is a confirmed false positive, record the evidence in the
     manifest so the next reviewer can check it.
   - Return to step 4 with a new isolated reviewer. Never resume the previous
     reviewer. Stop after the configured maximum number of reviewer passes.

6. **Finalize**
   - Source-backup cleanup depends on successful component validation, not the
     independent-review verdict or Chai Bot availability. If a validated run
     still has `"$REPO_PATH/ai-docs/_sources"`, run the component cleanup helper
     even when the completion gate does not pass.
   - After cleanup, verify that `"$REPO_PATH/ai-docs/_sources"` no longer exists.
   - Report the number of iterations, validator result, review coverage,
     corrections made, remaining findings, and Chai Bot verification status.

## Completion gate

The `VERIFIED CLEAN` verdict in the current fresh reviewer's returned report is
the completion signal. Do not search prior output or accept a verdict from an
earlier reviewer.

Report **verified clean** only when all of the following are true in the latest
pass:

- a fresh isolated reviewer produced the latest report;
- the component validator exits successfully;
- that reviewer reports zero critical issues and zero warnings;
- every local claim has a `verified` status, with zero failed and zero skipped local claims;
- every cross-repository claim is verified.

If independent review succeeds but cross-repository verification is
unavailable, report **locally verified; cross-repository claims unverified**,
not an unqualified verified-clean result.

If the iteration limit is reached, stop normally and report the remaining
findings. If independent verification is unavailable, report that limitation
as incomplete. Never manufacture a completion marker or silently discard
failures.
