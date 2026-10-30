---
description: Plan, execute, and resume a manually operated downstream rebase with revision-bound evidence and draft PR feedback
argument-hint: "[--tag <tag>] [--stage plan|apply|validate|draft|review|status] [--state-dir <path>]"
---

## Name

nid-team:rebase-manager

## Synopsis

```text
/nid-team:rebase-manager [--tag <tag>] [--stage plan|apply|validate|draft|review|status] [--state-dir <path>]
```

## Description

Manage a downstream fork rebase from an upstream release through a reviewable
plan, local candidate, validation evidence, and a draft PR. Resume from explicit
state and PR identity. The agent analyzes carry intent, adapts conflicts, checks
behavior, and addresses feedback; the helper records decisions and checks whether
evidence belongs to the current candidate.

This is a manually invoked workflow. A new invocation with no stage produces a
plan for review; a request to complete a rebase may continue through the stages
already authorized. It does not schedule future runs or merge PRs.

## Implementation

Read and follow the [rebase-manager skill](../skills/rebase-manager/SKILL.md).
Resolve that file relative to this installed plugin. It delegates rebase mechanics
to the installed `openshift:rebase` skill; install the OpenShift plugin if that
skill is unavailable. Neither slash command is a shell executable.

The Python helper is only the state and evidence recorder. Running it alone does
not analyze a repository, execute a rebase, run tests, or address feedback.

## Return Value

Report the state directory, pinned target, candidate revision when present, actual
validation results, pending decisions or feedback, and draft PR URL if published.

## Examples

```text
/nid-team:rebase-manager --tag v1.13.2 --stage plan
/nid-team:rebase-manager --state-dir /work/rebase-state/coredns-v1.13.2 --stage apply
/nid-team:rebase-manager --state-dir /work/rebase-state/coredns-v1.13.2 --stage review
```
