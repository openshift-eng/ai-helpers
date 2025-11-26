---
description: |
  Assist with openshift/origin PRs that add or modify Two Node (Fencing or Arbiter)
  tests under test/extended/two_node/. Dynamically discover the changed tests,
  review their logic and structure, suggest reuse of existing Origin and Kubernetes
  utilities, recommend suite and Serial annotations, propose CI lane coverage, and
  generate ready-to-paste text for both the Origin PR and the corresponding
  openshift/release CI lane PR.
---

## Name

`/origin:two-node-origin-pr-helper` — Expert helper for Origin Two Node test PRs.

## Synopsis

Analyze an `openshift/origin` PR that adds or modifies Two Node (Fencing or Arbiter)
tests under `test/extended/two_node/`, then:

- discover changed tests,
- review their design and correctness,
- suggest helper/utility reuse,
- recommend suite and `[Serial]` annotations,
- propose CI lane coverage,
- and generate ready-to-paste PR text for both Origin and Release.

Typical usage:

> /origin:two-node-origin-pr-helper  
> Repo: openshift/origin  
> PR: https://github.com/openshift/origin/pull/30510  

## Description

Use this command when you have an `openshift/origin` PR that modifies or adds Two Node
(Fencing or Arbiter) tests under `test/extended/two_node/` and you need an expert,
end-to-end review for them.

The goal is to provide a **single, structured response** that:

1. Summarizes what the PR changes for Two Node tests.
2. Reviews the tests’ logic, structure, and correctness.
3. Suggests reuse of existing Origin and Kubernetes utilities instead of duplicating logic.
4. Recommends appropriate suite tags and `[Serial]` annotations.
5. Proposes which CI lane(s) in `openshift/release` should cover these tests.
6. Generates short, ready-to-paste PR description text for both Origin and Release.

This helper is scoped to **Two Node OpenShift topologies** (Fencing and Arbiter) and
should reason based on what the code actually does, not on a hard-coded list of
function names or helpers.

## Implementation

The command should behave as follows.

1. **Automatically discover relevant changes**
   - Identify all changed files under `test/extended/two_node/`.
   - From those files, dynamically extract:
     - new or modified `Describe` / `It` blocks,
     - suite tags (e.g. `[Suite:...]`),
     - Serial markers,
     - imports and helper usage.

2. **Review test design and correctness**
   - Check whether the tests’ logic matches their stated intent (names, comments).
   - For Two Node Fencing / Arbiter scenarios, reason about:
     - degraded vs non-degraded behavior,
     - fencing / failover intent,
     - arbiter / quorum intent,
     - correctness of expectations and assertions.
   - Do **not** assume specific helper or function names exist; instead, use the
     actual code and imports in the PR to understand what the tests are doing.

3. **Suggest reuse of existing utilities and helpers**
   - Look for patterns where the PR re-implements generic behaviors that are already
     available in imported Origin or Kubernetes utilities.
   - Typical examples include, but are not limited to:
     - Origin test utilities such as:
       - `exutil "github.com/openshift/origin/test/extended/util"`
       - image helpers under `github.com/openshift/origin/test/extended/util/...`
     - Kubernetes utilities from the broader `k8s.io/...` ecosystem, for example:
       - client libraries under `k8s.io/client-go/...`
       - generic helpers under `k8s.io/apimachinery/pkg/util/...` (wait, retry, intstr, sets, etc.)
       - pointer and type helpers under `k8s.io/utils/...`
   - If you see manual polling loops, ad-hoc resource creation, or repeated patterns
     that look similar to existing helpers in the repo:
     - point out where a helper could be reused,
     - or suggest that a new helper be extracted and placed in an appropriate
       shared location (for example, a shared Two Node utility file).
   - Do this **based on the actual imports and surrounding code in the PR**, not on
     a fixed list of helper names.

4. **Evaluate structure and readability**
   - Review Ginkgo structure:
     - `Describe` / `Context` / `It` organization,
     - naming clarity,
     - use of `By` steps (if present),
     - quality of assertion messages.
   - Suggest improvements where they would make the tests easier to understand,
     debug, and maintain.

5. **Recommend suite and Serial annotations**
   - Decide, based on what the tests do, which suite is appropriate (for example
     `[Suite:openshift/two-node]` for Two Node–specific behavior).
   - Recommend which tests should be `[Serial]` vs safe to run in parallel:
     - tests that heavily modify cluster-scoped state, reboot control-plane nodes,
       or put the cluster into unusual states are more likely to require `[Serial]`;
     - tests that are fully namespaced, use isolated resources, and leave the
       cluster in a clean state are more likely to be parallel-safe.
   - Base these recommendations on the observed behavior and impact of the tests,
     not on hard-coded rules.

6. **Propose CI lane coverage**
   - Given the tests and their suite/tagging, reason about:
     - whether existing CI lanes already cover these tests,
     - or whether a new lane / suite configuration is needed.
   - When recommending CI changes in `openshift/release`, provide:
     - the suite or `TEST_SUITE` that should be used,
     - a rough lane naming suggestion (if helpful),
     - any notable environment flags or feature gates that the tests assume
       (for example, if they rely on a specific Two Node topology or feature set).
   - Keep this guidance general enough that it remains valid as suites and
     lane names evolve.

7. **Generate ready-to-paste text**
   - For the `openshift/origin` PR description:
     - Concisely describe what the new Two Node tests cover,
     - Mention any important suite/tagging and Serial decisions,
     - Summarize key design and behavior points.
   - For the `openshift/release` PR:
     - Explain what kind of Two Node behavior the lane validates,
     - Note which suite or tags it focuses on,
     - Describe how it complements existing lanes (for example, “Two Node–specific
       degraded behavior” vs “generic conformance”).

The command is purely **static**: it should not require cluster access, kubeconfig,
or secrets. It operates on the local Git checkout and PR diff only.

---

## Expected input

From the user, you primarily expect:

- The **PR link** (or repo + PR number), e.g.:
  - `https://github.com/openshift/origin/pull/30510`

You should assume the command is run within a local checkout of the repo on the
PR branch. Where possible, **inspect the diff directly**, for example by reading:

- `git diff --name-only` to discover changed files,
- the contents of changed Go files under `test/extended/two_node/`.

Optionally, the user may also provide:

- A short summary of what the PR is trying to validate (for context).
- Any specific questions (e.g. “Should this be Serial?”, “Is this using exutil correctly?”).

Do **not** require the user to manually paste all tests; instead, discover them
from the actual code in the PR wherever possible.

---

## What you should extract and reason about

When reviewing the PR, dynamically derive:

1. **Changed test files**
   - All Go files under `test/extended/two_node/` that were added or modified.

2. **Test metadata**
   - New or modified Ginkgo `Describe` / `It` blocks.
   - Suite tags such as `[Suite:...]`.
   - Serial tags such as `[Serial]` if present.
   - Any feature-gate or topology hints in the test names, descriptions, or comments.

3. **Behavior and intent**
   - From names, comments, and logic:
     - infer whether the tests are about Two Node Fencing, Arbiter, degraded mode,
       failover, quorum, or general conformance.
   - Check whether the implementation appears consistent with that intent:
     - e.g. if the description talks about degraded behavior, does the test
       actually set up and verify a degraded scenario?

4. **Use and reuse of utilities**
   - Inspect imports and helper calls to see which utilities are already in use,
     including but not limited to:
     - Origin utilities (for example, `exutil` and related helpers),
     - image helpers,
     - common Kubernetes utility packages.
   - Look for places where:
     - the PR re-implements logic that appears similar to helpers already in
       the repo,
     - or where logic is complex enough that extracting a helper would improve
       readability and reuse.
   - Suggest concrete refactor opportunities but phrase them in terms of patterns
     (“this polling loop looks like it could use a shared wait helper”) rather
     than hard-coding specific function names.

5. **Safety, cleanup, and determinism**
   - Check that tests:
     - clean up resources they create, where appropriate,
     - avoid leaving the cluster in a confusing state for subsequent tests,
     - use reasonable timeouts and retries,
     - avoid brittle sleeps where a condition-based wait would be better.

6. **Suite and Serial recommendations**
   - Based on the above, recommend:
     - suite tagging (`[Suite:openshift/two-node]` or others if appropriate),
     - whether each test should be `[Serial]` or parallel-safe, with reasoning.

7. **CI lane recommendations**
   - Suggest a high-level CI plan:
     - whether existing lanes likely cover these tests,
     - whether a dedicated Two Node lane is appropriate,
     - and roughly how it should be configured (suite, topology assumptions, etc.).
   - Avoid relying on specific hard-coded lane names; instead, describe the
     characteristics a lane should have.

---

## Output structure

Always respond in four sections:

1. **Summary of changes**
   - 2–5 bullet points summarizing:
     - which Two Node test files were touched,
     - in very broad terms, what scenarios they cover.

2. **Review of tests (design, logic, reuse)**
   - Bullet points or short paragraphs covering:
     - logic correctness and alignment with intent,
     - opportunities to reuse existing utilities or extract helpers,
     - improvements to Ginkgo structure and assertions,
     - cleanup and determinism.

3. **Suite, Serial, and CI recommendations**
   - Suite tags you recommend and why.
   - Serial vs parallel recommendations and why.
   - A concise CI coverage suggestion:
     - whether existing lanes are probably enough,
     - or what kind of lane configuration should run these tests.

4. **Ready-to-paste PR text**
   - A short paragraph for the Origin PR description that:
     - explains new tests and why they exist,
     - mentions suite and any special considerations.
   - A short paragraph for the Release PR (if needed) that:
     - explains what the CI lane validates,
     - and how it fits into the broader Two Node testing story.

Keep the tone technical, concise, and practical.

---

## Example 1 — Degraded Two Node Fencing tests

**User prompt**

> /origin:two-node-origin-pr-helper  
>  
> Repo: openshift/origin  
> PR: https://github.com/openshift/origin/pull/30510  
>  
> This PR adds degraded Two Node tests under test/extended/two_node/.
> Please review the tests, suggest reuse of existing helpers/utilities,
> and recommend suite, Serial tagging, and CI coverage. Also generate
> suggested PR descriptions for origin + release.

---

## Example 2 — Two Node Arbiter recovery tests

**User prompt**

> /origin:two-node-origin-pr-helper  
>  
> Repo: openshift/origin  
> PR: <link>  
>  
> This PR adds recovery tests for Two Node + Arbiter under test/extended/two_node/.
> Please review structure, logic correctness, helper reuse, suite/Serial decisions,
> and suggest CI coverage + PR description text.
