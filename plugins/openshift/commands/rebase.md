---
argument-hint: "[tag] [--stage plan|apply|validate|report --state-dir PATH]"
description: Rebase an OpenShift fork onto an upstream release using the shared rebase skill.
---

## Name
openshift:rebase

## Synopsis
```text
/openshift:rebase [tag]
/openshift:rebase [tag] --stage plan|apply|validate|report --state-dir PATH
```

## Description

Analyze downstream carries, adapt them to an upstream release, validate the
candidate, and prepare a reviewable PR. With no tag, discover the latest stable
release allowed by the repository's policy. Delegated stages allow a rebase
manager to reuse this procedure while owning publication and review progress.

## Implementation

Read and follow the [OpenShift rebase skill](../skills/rebase/SKILL.md), passing
through the supplied target and stage arguments. Resolve the skill relative to
this command's installed plugin directory. The agent executes its instructions;
do not attempt to run a slash command as a shell subprocess.
The skill is the sole procedure for stage boundaries, artifacts, validation,
authorization, and PR preparation; do not maintain a second implementation here.

## Return Value

Pinned release/carry plan, application results, revision-specific validation,
and a release report/PR body. Report unfinished work and actual test failures.

## Examples

```text
/openshift:rebase v1.2.3
/openshift:rebase v1.2.3 --stage plan --state-dir /tmp/rebase-plan
```

## Arguments

- `tag`: Optional upstream release tag.
- `--stage`: Run one of `plan`, `apply`, `validate`, or `report` for a caller.
- `--state-dir`: Absolute artifact directory required in delegated mode.
