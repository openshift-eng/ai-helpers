---
description: Interactive onboarding that guides new Node team members through access, tools, and environment setup
argument-hint: "[--track dev|qe] [--resume] [--check-only]"
---

## Name

node-onboarding:checklist

## Synopsis

```
/node-onboarding:checklist [--track dev|qe] [--resume] [--check-only]
```

## Description

Walks a new Node team member through the full onboarding process: access
requests, tool installation, environment setup, and first cluster creation.
The command runs automated checks to verify each step that can be tested
programmatically. For manual steps, it provides instructions and links,
then asks the user to confirm completion.

Progress is saved between sessions so the checklist can be resumed later.

## Implementation

### Phase 0: Setup and Argument Parsing

1. Parse arguments:
   - `--track dev|qe`: onboarding track (default: `dev`). The `qe` track
     adds QE-specific items after the common sections.
   - `--resume`: load prior progress from
     `~/.node-assistant/onboarding-progress.json` and skip completed sections.
   - `--check-only`: run only automated verification checks without
     interactive prompts. Print pass/fail for each checkable item.
2. If `--resume`, read `~/.node-assistant/onboarding-progress.json`. If the
   file does not exist, start fresh.
3. Read the checklist structure from
   [references/onboarding-checklist.md](../references/onboarding-checklist.md).

### Phase 1: Interactive Checklist

Walk through each section sequentially. For each item:
- If an automated check is defined, run it and report the result.
- If the check passes, mark the item complete automatically.
- If the check fails or no check exists, show instructions and ask the user
  to confirm when done (skip this prompt in `--check-only` mode).
- Save progress to `~/.node-assistant/onboarding-progress.json` after each
  section completes.

**Sections:**

#### 1. Prerequisites

Verify the user has completed New Hire Orientation and has basic access.

| Item | Automated Check | Manual Action |
|------|----------------|---------------|
| Spin-up Buddy assigned | None | Request your manager to assign a Spin-up Buddy before starting |
| VPN connectivity | `curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://brewweb.engineering.redhat.com/brew/` (expect 200) | Connect to Red Hat VPN |
| Jira access | `curl -s -o /dev/null -w "%{http_code}" -u "${JIRA_USER:-$(git config user.email)}:$JIRA_API_TOKEN" "https://redhat.atlassian.net/rest/api/3/myself"` (expect 200) | Set up `JIRA_API_TOKEN` per [jira.md](../../node-team/skills/node/references/jira.md) |
| ServiceNow portal | `curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://redhat.service-now.com/help` (expect 200) | Verify access to https://redhat.service-now.com/help?id=rh_requests |

#### 2. Access and Permissions

Guide through LDAP groups, Google Groups, Slack, and calendars.

| Item | Instruction |
|------|-------------|
| LDAP: openshift-node-team | Request manager to add you at https://rover.redhat.com/groups/group/openshift-node-team |
| LDAP: openshift-dev-node-team | Request manager to add you at https://rover.redhat.com/groups/group/openshift-dev-node-team |
| Google Group: aos-node | Ask manager or TL to add you to https://groups.google.com/a/redhat.com/g/aos-node |
| Google Group: aos-announce | Join https://groups.google.com/a/redhat.com/g/aos-announce |
| Slack: team-node | Request manager to add you (private channel) |
| Slack: forum-ocp-node | Join (public channel) |
| Slack: @node-team handle | Request TL to add you to the @node-team Slack user group |
| Calendar: OpenShift Main Calendar | Add https://calendar.google.com/calendar/embed?src=redhat.com_2v3jc3smo4hr9r8dkv5phed66g%40group.calendar.google.com |
| Calendar: team PTO | Add the shared team leave calendar |

Prompt the user to confirm each item. For LDAP groups, suggest verifying with:
```bash
ldapsearch -x -H ldaps://ldap.corp.redhat.com -b dc=redhat,dc=com -s sub 'uid=<your-uid>'
```

#### 3. GCP Access

| Item | Instruction |
|------|-------------|
| openshift-gce-devel | Request via https://devservices.dpp.openshift.com/support/gcp_access_request/ (VPN required). Verify at https://console.cloud.google.com/welcome?project=openshift-gce-devel |

#### 4. IDE License

| Item | Instruction |
|------|-------------|
| GoLand license | File a DPP ticket. See https://source.redhat.com/groups/public/openshift/openshift_wiki/jetbrains_product_licenses |

#### 5. GitHub Setup

| Item | Automated Check | Manual Action |
|------|----------------|---------------|
| GitHub account linked | `gh auth status` (expect success) | Install `gh` and run `gh auth login` |
| OpenShift org member | `gh api orgs/openshift/memberships/<github-handle> --jq '.state'` (expect `active`) | Follow https://source.redhat.com/groups/public/openshift/openshift_wiki/openshift_onboarding_checklist_for_github |

Ask the user for their GitHub handle and substitute it in the org membership check.

#### 6. Jira Dashboard

| Item | Automated Check | Manual Action |
|------|----------------|---------------|
| Node Components filter access | `curl -s -u "${JIRA_USER:-$(git config user.email)}:$JIRA_API_TOKEN" "https://redhat.atlassian.net/rest/api/3/filter/91645" -o /dev/null -w "%{http_code}"` (expect 200) | Request access at https://issues.redhat.com/servicedesk/customer/portal/2 if needed |
| Node Bugs filter | None | Verify you can open https://redhat.atlassian.net/issues/?filter=83963 |

#### 7. Development Environment

| Item | Automated Check | Manual Action |
|------|----------------|---------------|
| Go installed | `which go && go version` | Install from https://go.dev/doc/install |
| kubectl installed | `which kubectl` | `brew install kubectl` (macOS) or distro package |
| oc installed | `which oc` | Download from https://console.redhat.com/openshift/downloads |
| GOPATH set | `test -n "$GOPATH"` (expect success) | Add `export GOPATH=$HOME/go` to shell config |

After tool checks, suggest running `/node-team:setup` to clone repos and
set up worktrees. Reference
[SETUP.md](../../node-team/skills/node/references/SETUP.md) for the standard
workflow.

For kubelet/CRI-O development, mention the option to run a local
single-node cluster via `local-up-cluster.sh` from the Kubernetes repo.
Key environment variables:
- `CGROUP_DRIVER=systemd`
- `CONTAINER_RUNTIME_ENDPOINT=unix:///var/run/crio/crio.sock`

#### 8. Cluster Creation

Guide through creating a first test cluster. Present options:

1. **ClusterBot** (recommended for first cluster):
   - Open a DM with "Cluster Bot" on Slack
   - Type `launch 4.19 gcp`
   - Wait ~30 mins for kubeconfig
   - `export KUBECONFIG=<downloaded-file>`
   - `kubectl get nodes` to verify
   - Cluster auto-expires after ~2 hours

2. **AWS** (for longer-lived clusters):
   - Requires openshift-dev AWS access (account 269733383066)
   - Request via https://devservices.dpp.openshift.com/support (VPN required)
   - Reference: internal cluster creation guide

3. **GCP** (requires openshift-gce-devel access from step 3):
   - Reference: internal cluster creation guide

#### 9. Customer Support Readiness

| Item | Automated Check | Manual Action |
|------|----------------|---------------|
| SupportShell access | `ssh -o ConnectTimeout=5 -o BatchMode=yes supportshell-1.sush-001.prod.us-west-2.aws.redhat.com exit 2>&1` (expect success) | Follow https://source.redhat.com/groups/public/customerplatform/customerplatform_wiki/how_to_access_supportshell |
| omc installed | `which omc` | Install omc for must-gather analysis |
| yank installed | `which yank` | Available on SupportShell by default |

Explain the workflow: `yank -y <case_id>` to download, `omc use <file>` to
analyze, then standard `omc get nodes`, `omc get mc` commands.

#### 10. QE-Specific (only if `--track qe`)

Additional items for QE engineers:

| Item | Instruction |
|------|-------------|
| QE onboarding guide | Follow https://source.redhat.com/groups/public/openshiftqe/workflows/openshift_qe_workflow_wiki/openshift_qe_new_hire_guide |
| Clone openshift-tests-private | `git clone https://github.com/openshift/openshift-tests-private` |
| Polarion access | Access https://polarion.engineering.redhat.com/polarion/#/project/OSE/mypolarion with SSO |
| Learn Ginkgo | Study the Ginkgo testing framework (used for e2e tests) |

### Phase 2: Progress Summary

1. Calculate completion percentage: `completed_items / total_items * 100`
2. Print summary:
   - Sections complete vs. remaining
   - For incomplete items, list the specific action needed
   - If all items complete, print next steps:
     - Pick up your first Jira ticket
     - Submit your first PR
     - Update this onboarding doc for the next new team member
3. Save final progress to `~/.node-assistant/onboarding-progress.json`

### Progress File Format

```json
{
  "track": "dev",
  "started": "2026-06-30",
  "last_updated": "2026-06-30",
  "sections": {
    "prerequisites": {"status": "complete", "items": {"vpn": true, "jira": true}},
    "access": {"status": "in_progress", "items": {"ldap_node_team": true, "slack_team_node": false}}
  }
}
```

## Return Value

A completion summary showing which sections passed, which have remaining
items, and specific next steps for incomplete items.

## Examples

1. **Start fresh onboarding (dev track)**:
   ```bash
   /node-onboarding:checklist
   ```

2. **QE-specific onboarding**:
   ```bash
   /node-onboarding:checklist --track qe
   ```

3. **Resume after a break**:
   ```bash
   /node-onboarding:checklist --resume
   ```

4. **Just check what's done**:
   ```bash
   /node-onboarding:checklist --check-only
   ```

## Arguments

- **--track** *(optional)*
  Onboarding track. `dev` (default) covers the standard developer path.
  `qe` adds QE-specific items (Polarion, openshift-tests-private, Ginkgo).

- **--resume** *(optional)*
  Load progress from `~/.node-assistant/onboarding-progress.json` and skip
  completed sections.

- **--check-only** *(optional)*
  Run automated verification checks only. Do not prompt for manual
  confirmation. Useful for periodic re-validation.
