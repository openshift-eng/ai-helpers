# Manage Labels

Create, update, or delete Sippy job run Labels via the authenticated Sippy API.

## Overview

Sippy Symptoms are known-failure signatures for OpenShift CI. A symptom is a rule made of a file pattern (a glob over a CI job run's artifact files, e.g. `**/build-log.txt`) and a matcher (`string` = substring, `regex` = regular expression, `none` = file merely exists, `cel` = a compound CEL expression over other label names). When a symptom matches a job run's artifacts, Sippy applies one or more **Labels** — human-readable tags like `InfraFailure` — to that run. Labels appear in the Sippy UI and Spyglass and help everyone quickly recognize known failure modes without re-debugging them. You do not need any prior Sippy knowledge to use this skill.

Labels must exist before a symptom can reference them.

## Authentication

Writes go to `https://sippy-auth.dptools.openshift.org` and require a Bearer token. Log into the DPCR cluster (`https://api.cr.j7t7.p1.openshiftapps.com:6443`) with `oc login` and use the `oc-auth` skill to obtain the token. Prefer `export SIPPY_TOKEN=$(oc whoami -t --context="$CONTEXT")` over passing `--token` on the command line (argv is visible in process listings); `--token` still works and takes precedence.

## Usage

```bash
# Create a label
python3 plugins/ci/skills/manage-labels/manage_labels.py create --title "Cluster DNS Flake" \
  --explanation "DNS lookups inside the cluster intermittently time out."

# Update a label (only pass the fields to change; the script merges with the existing label)
python3 plugins/ci/skills/manage-labels/manage_labels.py update --id ClusterDNSFlake \
  --explanation "Updated explanation."

# Delete a label (confirm with the user first!)
python3 plugins/ci/skills/manage-labels/manage_labels.py delete --id ClusterDNSFlake
```

## See Also

- [SKILL.md](SKILL.md) - Complete implementation guide
- Related: `oc-auth` skill (authentication tokens)
- Related: `list-symptoms` skill (inspect labels, no auth needed)
- Related: `manage-symptoms` skill (symptoms that apply labels)
