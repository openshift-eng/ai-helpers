---
description: Expert review tool for PRs that add or modify Two Node (Fencing or Arbiter) tests under test/extended/two_node/ in openshift/origin.
argument-hint: <pr> [--repo owner/repo] [--focus tests|ci|helpers|all] [--depth quick|full]
---

## Name

origin:two-node-origin-pr-helper

## Synopsis
```
/origin:two-node-origin-pr-helper <pr> [--repo owner/repo] [--focus tests|ci|helpers|all] [--depth quick|full]
```

## Description

The `/origin:two-node-origin-pr-helper` command is an expert review tool for PRs that add or modify
Two Node (Fencing or Arbiter) tests under `test/extended/two_node/` in `openshift/origin`.

It:

- Discovers changed Two Node test files from the current branch.
- Analyzes Ginkgo `Describe` / `It` blocks, suite tags, and `[Serial]` markers.
- Reviews test logic, structure, cleanup, and determinism.
- Suggests reuse of existing Origin and Kubernetes helpers instead of ad-hoc code.
- Recommends suite + `[Serial]` tagging and CI coverage.
- Generates ready-to-paste PR description text for both Origin and Release repos.

Use this command when creating or reviewing Origin PRs that touch the Two Node test suite and you
want a focused, reproducible review of test design, helper usage, and CI integration.

## Implementation

The command should behave as follows.

### 1. Argument handling

Parse arguments from the invocation:

- `<pr>`:
  - Accept either a PR number (e.g. `30510`) or full URL
    (`https://github.com/openshift/origin/pull/30510`).
- `--repo owner/repo`:
  - Default: `openshift/origin` if omitted.
- `--focus`:
  - `tests`   → emphasize test logic, structure, determinism.
  - `ci`      → emphasize suite tags, `[Serial]`, CI lane coverage.
  - `helpers` → emphasize helper/utility reuse and refactor suggestions.
  - `all`     → cover all aspects (default if omitted).
- `--depth`:
  - `quick` → short, high-level summary in each section.
  - `full`  → detailed 4-section output (default if omitted).

The internal behavior (what to inspect and how to reason) is the same; `--focus` changes emphasis
and the level of detail per topic, and `--depth` controls how verbose the final answer is.

### 2. Automatically discover relevant changes

Assume the command is run inside a local checkout of the repo on the PR branch.

- Determine which files have changed:
  - Use `git diff --name-only` for the PR range, or an equivalent mechanism that Claude has access to.
- Filter to Two Node tests:
  - Consider Go files under `test/extended/two_node/` that were added or modified.
- For each such file:
  - Parse the contents enough to identify:
    - new or modified Ginkgo `Describe` / `Context` / `It` blocks,
    - suite tags (e.g. `[Suite:openshift/two-node]`),
    - `[Serial]` markers,
    - imports and the key helpers/utilities being used.

### 3. Review test design and correctness

For each relevant test:

- Check whether names, comments, and assertions are consistent with the stated intent:
  - degraded vs non-degraded behavior,
  - Two Node Fencing vs Two Node Arbiter focus,
  - quorum / failover / recovery semantics,
  - etc.
- Pay particular attention to:
  - How the cluster state is set up (e.g. degraded TNF mode, arbiter behavior),
  - Which conditions are asserted (e.g. PDB behavior, reboot-block, quorum changes),
  - Whether the expectations match typical Two Node semantics in Origin.

Do **not** assume specific helper or function names exist. Infer behavior from the actual code,
imports, and test logic present in the PR.

### 4. Suggest reuse of existing utilities and helpers

Look for patterns where the PR re-implements behavior that is likely covered by existing helpers.

Examples (non-exhaustive, pattern-based):

- Origin test utilities such as:
  - `exutil "github.com/openshift/origin/test/extended/util"`
  - image helpers under `github.com/openshift/origin/test/extended/util/...`
- Kubernetes helper packages, for example:
  - `k8s.io/client-go/...` client usage patterns,
  - `k8s.io/apimachinery/pkg/util/...` (wait, retry, intstr, sets, etc.),
  - `k8s.io/utils/...` pointer / type helpers.

If you see:

- Hand-rolled polling loops,
- Custom resource creation logic that looks similar across tests,
- Repeated boilerplate for waiting on pods/nodes/MCPs,

then:

- Call out where an existing helper is already being used correctly,
- Suggest where existing helpers could replace ad-hoc code,
- Or propose that new shared helpers be extracted into a common Two Node utility file when
  patterns are repeated in multiple tests.

Importantly, base these suggestions on the **actual imports and code** in the PR, not a hard-coded
list of function names.

### 5. Evaluate structure and readability

Review the Ginkgo test structure:

- `Describe` / `Context` / `It` hierarchy:
  - Are scopes and groupings clear?
  - Do names convey behavior and expectations?
- Use of `By(...)` steps (if present) to narrate critical phases.
- Assertion quality:
  - Are failure messages informative?
  - Are conditions checked via proper waits/conditions rather than brittle sleeps?

Suggest improvements where they would materially help future readers/debugging, especially for
complex Two Node scenarios where debugging can be painful.

### 6. Recommend suite and Serial annotations

Based on what each test does:

- Suite tagging:
  - For Two Node–specific behavior, prefer something like
    `[Suite:openshift/two-node]` (or whatever suite tagging is used in the file).
  - If another suite is clearly more appropriate and consistent with the surrounding tests,
    call that out explicitly.
- `[Serial]` vs parallel:
  - Tests that:
    - modify cluster-scoped state,
    - reboot control-plane nodes,
    - intentionally degrade or fence nodes,
    - or otherwise put the cluster into unusual states
    are strong candidates for `[Serial]`.
  - Tests that:
    - are fully namespaced,
    - use isolated resources,
    - clean up after themselves,
    - and don’t disrupt cluster-wide behavior
    are more likely to be parallel-safe.
- Provide reasoning:
  - Explain *why* a given test should or should not be `[Serial]`, referencing its behavior.

### 7. Propose CI lane coverage

Using the tests, suite tags, and Serial decisions:

- Determine whether existing CI lanes are likely to cover these tests:
  - e.g. lanes already running `[Suite:openshift/two-node]` on a Two Node topology.
- If coverage looks insufficient, propose what kind of CI lane is appropriate:
  - Topology: Two Node Fencing vs Two Node + Arbiter vs generic Two Node.
  - Suite / `TEST_SUITE`: e.g. Two Node suite vs generic conformance.
  - Feature gates / environment flags:
    - e.g. if tests assume DualReplica / degraded behavior, etc.
  - Whether the lane should be:
    - periodic vs blocking vs optional (if the user provides context).

Avoid hard-coding specific lane names; instead, describe the lane characteristics and how it fits
into the existing Two Node CI story.

### 8. Generate ready-to-paste text

Produce short, practical text snippets:

- For the `openshift/origin` PR:
  - Summarize what the new Two Node tests cover.
  - Mention suite tags and any `[Serial]` decisions.
  - Highlight key behavioral checks (e.g. degraded TNF behavior, arbiter recovery).
- For a potential `openshift/release` PR:
  - Describe what the CI lane validates (e.g. degraded Two Node Fencing behavior, arbiter quorum).
  - Note which suite/tags it runs.
  - Explain how it complements existing lanes (e.g. Two Node degraded behavior vs generic e2e).

The command is purely **static**: it should not require cluster access, kubeconfig, secrets, or
live API calls. It operates on the local Git checkout and PR diff only.

---

## Expected input

Typical invocation:

/origin:two-node-origin-pr-helper <pr> [--repo owner/repo] [--focus tests|ci|helpers|all] [--depth quick|full]

Where:

- `<pr>`: PR number or full PR URL.
- `--repo`: Optional, defaults to `openshift/origin`.
- `--focus`: Optional, defaults to `all`.
- `--depth`: Optional, defaults to `full`.

Assume the command is run:

- Inside a local checkout of the target repo,
- On the branch that corresponds to the PR (or with the PR’s diff available).

The tool should:

- Use the PR reference to orient itself (repo + PR number/URL),
- Inspect the local diff and files under `test/extended/two_node/`,
- Ask the user for clarifications only when absolutely necessary (e.g. ambiguous topology).

---

## What you should extract and reason about

When reviewing the PR, dynamically derive:

1. **Changed test files**
   - All Go files under `test/extended/two_node/` that were added or modified.

2. **Test metadata**
   - New or modified Ginkgo `Describe` / `Context` / `It` blocks.
   - Suite tags such as `[Suite:...]`.
   - Serial tags such as `[Serial]` if present.
   - Any feature-gate or topology hints in test names, descriptions, or comments.

3. **Behavior and intent**
   - From names, comments, and logic, infer whether tests cover:
     - Two Node Fencing vs Two Node Arbiter,
     - degraded mode vs normal operation,
     - failover, fencing, or recovery flows,
     - quorum behavior, etc.
   - Check that implementation matches intent:
     - e.g. a “degraded” test actually sets up and asserts degraded behavior.

4. **Use and reuse of utilities**
   - Inspect imports and helper calls to see which utilities are already in use:
     - Origin utilities (`exutil`, image helpers, etc.),
     - Common Kubernetes utility packages.
   - Identify:
     - duplicated logic that could use existing helpers,
     - complex blocks that would benefit from extraction into shared helpers.
   - Phrase suggestions as patterns, not hard-coded function names.

5. **Safety, cleanup, and determinism**
   - Verify that tests:
     - clean up resources where appropriate,
     - leave the cluster in a reasonable state,
     - use condition-based waits instead of arbitrary sleeps,
     - have sensible timeouts and error messages.

6. **Suite and Serial recommendations**
   - Recommend suite tags and `[Serial]` where appropriate, with justification.

7. **CI lane recommendations**
   - Suggest:
     - whether existing lanes likely run these tests,
     - whether a new/dedicated lane is needed,
     - what topology/suite/flags that lane should have.

---

## Output structure

Always respond in **four sections**:

1. **Summary of changes**
   - 2–5 bullet points summarizing:
     - which Two Node test files were touched,
     - what scenarios they cover at a high level.

2. **Review of tests (design, logic, reuse)**
   - Bullet points or short paragraphs covering:
     - logic correctness and alignment with intent,
     - opportunities to reuse utilities or extract helpers,
     - Ginkgo structure and assertion quality,
     - cleanup and determinism.

3. **Suite, Serial, and CI recommendations**
   - Recommended suite tags and why.
   - `[Serial]` vs parallel recommendations and why.
   - Concise CI coverage plan:
     - existing lanes vs new lane,
     - topology and suite characteristics.

4. **Ready-to-paste PR text**
   - For the Origin PR description:
     - explains new tests and motivation,
     - mentions suite/tagging and special considerations.
   - For a Release PR (if needed):
     - explains what the CI lane validates,
     - and how it fits into the broader Two Node testing story.

Respect `--focus` and `--depth`:

- For `--focus tests`, put most detail into section 2.
- For `--focus ci`, emphasize section 3.
- For `--focus helpers`, emphasize reuse/refactor parts of section 2.
- For `--depth quick`, produce shorter bullets and more compact text in each section.

---

## Example 1 — Degraded Two Node Fencing tests

**User command**

/origin:two-node-origin-pr-helper 30510 --repo openshift/origin --focus all --depth full

Context (for illustration):

- PR 30510 adds degraded Two Node Fencing tests under `test/extended/two_node/`.
- The user wants:
  - Review of test design and helper usage,
  - Suite + `[Serial]` recommendations,
  - CI coverage suggestions,
  - Ready-to-paste PR description snippets.

The command should respond with:

- A 4-section analysis as described above,
- Explicit notes on degraded TNF behavior and MCO/PDB semantics (based on actual code),
- Suggested Two Node suite configuration for CI.

---

## Example 2 — Two Node Arbiter recovery tests

**User command**

/origin:two-node-origin-pr-helper https://github.com/openshift/origin/pull/XXXXX --focus tests --depth quick

Context (for illustration):

- The PR adds recovery tests for Two Node + Arbiter under `test/extended/two_node/`.
- The user is mainly interested in:
  - Test structure and logic correctness,
  - Helper reuse suggestions.

The command should respond with:

- A 4-section output, but with:
  - Shorter bullets overall (`--depth quick`),
  - More detail in section 2 (`--focus tests`),
  - Brief CI and PR-text suggestions.
