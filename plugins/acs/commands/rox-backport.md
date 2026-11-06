---
description: Backport a PR to stackrox release branches using the ROX non-clone workflow
argument-hint: "<PR> <branches...>"
---

## Name
acs:rox-backport

## Synopsis
```text
/acs:rox-backport <PR> <branches...>
```

## Description
The `acs:rox-backport` command drives the full ROX backport flow for a pull
request to one or more `release-X.Y` branches of the `stackrox/stackrox`
repository.

Unlike the OpenShift backport process, ROX backports do NOT create Jira
clones. Instead, the workflow adds fix versions to the ORIGINAL ROX bug and
opens cherry-pick PRs that reference it directly.

The command:
1. Plans the backport: discovers release branches, infers fix versions,
   validates the PR and its ROX bug.
2. Adds fix versions to the original bug's Fix Version/s field for each
   target branch.
3. Adds the `chai-backport` label to the original bug.
4. Cherry-picks the PR's commits to each target branch (one PR per branch).
5. Records each opened PR and monitors the campaign.

## Implementation
This command invokes the `rox-backport` skill, which orchestrates the
`rox_backport_*` coordinator tools and the cherry-pick worker. See the
skill at `plugins/acs/skills/rox-backport/SKILL.md` for the full playbook.

## Arguments
- `<PR>`: The parent pull request URL or `org/repo#N` reference.
- `<branches...>`: Target release branches, space- or comma-separated
  (e.g., `release-4.11 release-4.10` or `4.11,4.10`).

## Examples

1. **Backport to two release branches**:
   ```
   /acs:rox-backport stackrox/stackrox#12345 release-4.11 release-4.10
   ```

2. **Backport using short version syntax**:
   ```
   /acs:rox-backport https://github.com/stackrox/stackrox/pull/12345 4.11,4.10
   ```
