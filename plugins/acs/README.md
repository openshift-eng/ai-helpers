# acs

Skills and commands for Advanced Cluster Security (ACS / RHACS) workflows.

## Skills

### rox-backport

Drives the full ROX backport flow for cherry-picking a PR to
`release-X.Y` branches of the `stackrox/stackrox` repository.

Unlike the OpenShift backport process, ROX backports do NOT create Jira
clones. Instead, fix versions are added to the original ROX bug and
cherry-pick PRs reference it directly.

## Commands

### `/acs:rox-backport <PR> <branches...>`

Invokes the `rox-backport` skill to plan, execute, and monitor a ROX
backport campaign.
