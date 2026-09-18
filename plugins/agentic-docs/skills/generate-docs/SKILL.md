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
- `--cache-dir DIR`: shared review cache; default to a new run directory under
  `REPO_PATH/.work/agentic-docs/`.
- `--keep-cache`: keep the cache after a successful run instead of deleting it.
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

The first reviewer checks the full scope. Later reviewers check affected claims
against the last independent snapshot and reuse valid unchanged evidence.

Share immutable snapshots, source excerpts, verification records, and the diff.
Exclude the fixer's conversation and reasoning history. Cached fixer verdicts
are inputs, not independent verification: reviewers must assess the evidence.
Read [Claim cache](../review-docs/SKILL.md#claim-cache) before the first handoff.

The latest independent report determines completion. Stop when only the same
unresolved claims remain with no new evidence or actionable fix; report them.

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

3. **Prepare the independent baseline**
   - Resolve the review scope once from `REPO_PATH` using `review-docs`.
     Keep the cache outside that scope and out of published docs.
   - Set up the cache using `review-docs`' path and ownership rules. This workflow
     handles cleanup; reviewers leave the shared cache intact between passes.
     Before creating `.work`, ensure `/.work/` is listed in the target
     repository's local `.git/info/exclude`, then verify with `git check-ignore`
     that Git ignores the directory.
   - Record the repository revision and prompt version. Save any source evidence
     from generation as immutable cache records.
   - Let the first fresh reviewer perform the full review.
   - Record fixes and their sources; give reviewers the diff and source evidence.

4. **Verify independently**
   - Run the component validator at its resolved skill-local path with
     `REPO_PATH`. Include any resulting edits in the snapshot and diff.
   - Give a fresh reviewer `REPO_PATH`, the resolved `review-docs` skill path,
     cache directory, prompt version, scoped document paths, and snapshot/evidence
     IDs. After the first pass, also give the last independent baseline ID and diff.
   - Have the reviewer run `review-docs` Phases 1–5 and report findings. The main
     agent applies fixes in step 5, then starts a fresh reviewer to check them.
   - The first pass reads every scoped file, independently checks every extracted
     claim, and saves the baseline inventory and evidence. Cached excerpts can
     save retrieval.
   - Later passes read changed sections in context and update the inventory.
     Use the cache planner to select new or changed claims, dependent claims,
     and invalid evidence. Check all affected occurrences, summaries, and diagrams.
   - Verify selected cross-repository claims against authoritative sources,
     such as upstream GitHub sources or Chai Bot's configured CodeRAG. Use
     configured Slack and Jira knowledge for historical or cross-functional
     context when relevant.
   - Fully review any scope with missing, corrupt, or incomplete baseline coverage.
     An empty plan does not prove complete coverage.
   - Require the Phase 5 report: baseline/current snapshot IDs, pass number, and
     current, newly verified, reused, failed, and unresolved claim counts split
     by local/cross-repo. Findings need claim ID, location, incorrect claim,
     correction, severity, and evidence. List removed claims separately.
   - Assign the reviewer a report path: `CACHE_DIR/reports/pass-NNN.md`, using
     the next unused pass number (starting at `001`). The reviewer saves findings
     and inventory/evidence references there, then returns the path and a summary.
     Never overwrite a report. Each report counts as one iteration and supplies
     the next baseline; a fixer snapshot cannot.
   - After saving the self-contained report, run the claim cache's `compact`
     command for that snapshot. Remove detailed verified observations, retain
     failed and unresolved observations, and return the compaction counts.

5. **Fix and reassess**
   - The main agent reads the returned report and checks its evidence, then fixes
     confirmed issues everywhere, including summaries and diagrams. Do not
     auto-fix hedged or unverified claims.
     Append corrections and confirmed false positives with evidence to the cache.
   - Snapshot the edited docs and sources, update claims in changed sections,
     and follow their dependencies. Keep valid unchanged evidence under the cache
     rules, even when the document hash or repository commit changes.
   - Return to step 4 for changed claims, sources, policy, new evidence, or newly
     found coverage. Otherwise stop with the findings and unresolved claim IDs.
   - Stop at the pass limit. Fixes after the last pass await independent review;
     validation alone cannot certify them.

6. **Finalize**
   - Source-backup cleanup depends on successful component validation, not the
     independent-review verdict or cross-repository resource availability. If a validated run
     still has `"$REPO_PATH/ai-docs/_sources"`, run the component cleanup helper
     even when the completion gate does not pass.
   - After cleanup, verify that `"$REPO_PATH/ai-docs/_sources"` no longer exists.
   - Report the number of iterations, validator result, review coverage,
     corrections made, remaining findings, and cross-repository verification
     sources and status.
   - Once the report is ready and reviewers have returned, apply `review-docs`'
     cleanup rules: delete an owned cache when the gate passes unless `--keep-cache`.
     Retain failed, incomplete, or interrupted runs. Report cleanup status and any
     retained path and reason.

## Completion gate

The `VERIFIED CLEAN` verdict in the current fresh reviewer's returned report is
the completion signal. Do not search prior output or accept a verdict from an
earlier reviewer.

Report **verified clean** only when all of the following are true in the latest
pass:

- a fresh isolated reviewer produced the latest report;
- the component validator exits successfully;
- that reviewer reports zero critical issues and zero warnings;
- the snapshot matches the final docs and source scope;
- the inventory covers the full current scope;
- every local and cross-repo claim is verified in this pass or through valid
  reused independent evidence, with none failed or unresolved.

If independent review succeeds but cross-repository verification is
unavailable, report **locally verified; cross-repository claims unverified**,
not an unqualified verified-clean result.

At the pass limit or when no progress is possible, report remaining findings and
unresolved claim IDs. Report missing independent verification as incomplete.
Never invent a completion marker or discard failures.
