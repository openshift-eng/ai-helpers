---
description: Expert review tool for PRs that add or modify Two Node (Fencing or Arbiter) tests under test/extended/two_node/ in openshift/origin.
argument-hint: [--url PR_URL] [<pr>] [--depth quick|full]
---

## Name

/origin:two-node-origin-pr-helper — Review Two Node (Fencing/Arbiter) tests in openshift/origin.

## Synopsis
```
/origin:two-node-origin-pr-helper [--url PR_URL] [<pr>] [--depth quick|full]
```
## Description

The /origin:two-node-origin-pr-helper command is an expert review tool for PRs that add or modify
Two Node (Fencing or Arbiter) tests under test/extended/two_node/ in openshift/origin.

It:

- Discovers changed Two Node test files from the current branch.
- Analyzes Ginkgo Describe / Context / It blocks, suite tags, and [Serial] markers.
- Reviews test logic, structure, cleanup, and determinism.
- Suggests reuse of existing Origin and Kubernetes helpers instead of ad-hoc code.
- Recommends suite + [Serial] tagging and CI coverage.
- Generates ready-to-paste PR description text for the Origin PR.
- Suggests CI lane characteristics for openshift/release (without generating full PR text).

Use this command when creating or reviewing Origin PRs that touch the Two Node test suite and you
want a focused, reproducible review of test design, helper usage, and CI integration.

This is a specialized Origin review helper focused on Two Node tests and is intended as a building
block toward a future generic Origin review command.

## Implementation

The command should behave as follows.

### 1. Argument handling

Parse arguments from the invocation:

- --url:
  - Optional full PR URL (example: <https://github.com/openshift/origin/pull/30510>)
  - When provided, this takes precedence over any local git information.

- <pr> (optional positional):
  - Optional PR number (example: 30510)

- --depth:
  - quick: short, high-level summary
  - full: detailed four-section output (default)

Default behavior:

- If --url is provided, use that PR.
- Else if <pr> is provided, use that PR in the current repo.
- Else infer the PR from the current git repository remote and branch name.
- Fail with a clear error message if the PR cannot be determined.

### 2. Automatically discover relevant changes

Assume the command is run inside a local checkout of the repo.

- Determine changed files using git diff.
- Filter to Go files under test/extended/two_node/.
- Parse:
  - Ginkgo Describe / Context / It blocks
  - Suite tags
  - [Serial] markers
  - Helper imports

### 3. Review test design and correctness

For each test:

- Validate alignment between intent and implementation.
- Validate degraded vs non-degraded behavior.
- Validate fencing vs arbiter semantics.
- Validate quorum, failover, and recovery expectations.

Do not assume helper existence. Infer from imports and logic only.

### 4. Suggest reuse of utilities and helpers

Look for re-implemented logic where helpers already exist.

Examples:

- Origin utilities under github.com/openshift/origin/test/extended/util
- Kubernetes helpers under k8s.io/apimachinery and k8s.io/utils

Call out:

- Correct helper usage
- Missed reuse opportunities
- Duplication that should become shared Two Node helpers

### 5. Evaluate structure and readability

Review:

- Describe / Context / It hierarchy
- By(...) usage
- Assertion clarity
- Avoidance of time.Sleep in favor of polling

### 6. Recommend suite and Serial annotations

- Prefer [Suite:openshift/two-node] for Two Node tests.
- Recommend [Serial] for:
  - Cluster-scoped mutations
  - Reboots
  - Degradation or fencing actions

- Recommend parallel for isolated, namespaced tests.

Always explain why.

### 7. Propose CI lane coverage

- Determine if existing CI already covers the tests.
- If not, propose:
  - Topology
  - TEST_SUITE
  - Feature gates
  - Blocking vs periodic vs optional

Do not hard-code lane names.

### 8. Generate ready-to-paste text

Produce:

- Origin PR summary text
- Optional CI lane summary text (not a full release PR)

The command is static and requires no cluster access.

---

## Expected input

/origin:two-node-origin-pr-helper --depth full  
/origin:two-node-origin-pr-helper 30510 --depth full  
/origin:two-node-origin-pr-helper --url <https://github.com/openshift/origin/pull/30510> --depth quick  

---

## Output structure

Always respond in four sections:

1. Summary of changes  
2. Review of tests (design, logic, reuse)  
3. Suite, Serial, and CI recommendations  
4. Ready-to-paste text  

Respect --depth only:

- quick → compact output
- full → detailed output

---

## Example 1 — Degraded Two Node Fencing tests

/origin:two-node-origin-pr-helper 30510 --depth full

---

## Example 2 — Two Node Arbiter recovery tests

/origin:two-node-origin-pr-helper --url <https://github.com/openshift/origin/pull/XXXXX> --depth quick
