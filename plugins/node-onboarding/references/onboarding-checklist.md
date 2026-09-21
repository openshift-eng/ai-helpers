# Node Team Onboarding Checklist

Structured checklist for the `/node-onboarding:checklist` command. Each
section maps to a phase in the onboarding process. Items marked with a
check command can be validated automatically; others require manual
confirmation.

This file is the single source for checklist items, check commands and
manual actions. The command file only describes how to walk through it.

Source: Node Team Onboarding Guide (Google Doc, all tabs).

Channels, groups and team links that are not onboarding steps live in the
node-team plugin:
[shared/team-info.md](../../node-team/skills/node/references/shared/team-info.md).
When the plugin is installed that relative link does not resolve; read the
file from `"${CLAUDE_PLUGIN_ROOT}"/../../node-team/*/skills/node/references/`
(glob the version directory) or invoke the `node-team:node` skill and read
from its base directory.

## Jira check helper

The Jira checks below use `jira_status <url>`. Define it in the same Bash
invocation as the check, because shell variables and functions do not persist
between Bash tool calls. The token is passed to curl through a config on
stdin, never as a command-line argument:

```bash
JIRA_API_TOKEN="${JIRA_API_TOKEN:-$(security find-generic-password -s "JIRA_API_TOKEN" -w 2>/dev/null || secret-tool lookup service redhat key JIRA_API_TOKEN 2>/dev/null)}"
JIRA_USER="${JIRA_USER:-${JIRA_EMAIL:-$(security find-generic-password -s "JIRA_API_TOKEN" -g 2>&1 | grep acct | sed 's/.*="//;s/"//')}}"
JIRA_USER="${JIRA_USER:-$(git config user.email)}"
case "$JIRA_USER" in ""|*@*) ;; *) JIRA_USER="${JIRA_USER}@redhat.com" ;; esac
jira_status() {
  [ -n "$JIRA_API_TOKEN" ] && [ -n "$JIRA_USER" ] || { echo "missing JIRA_API_TOKEN or JIRA_USER/JIRA_EMAIL"; return 1; }
  printf 'user = "%s:%s"\n' "$JIRA_USER" "$JIRA_API_TOKEN" |
    curl -s -K - -o /dev/null -w '%{http_code}' "$1"
}
```

If the token or user is missing, the check fails; point the user to the
Authentication section of
[jira.md](../../node-team/skills/node/references/jira.md) and to
`/node-team:preflight`.

## Section: Prerequisites

Track: both

| Item | Key | Check Command | Manual Action |
|------|-----|---------------|---------------|
| Spin-up Buddy assigned | spinup_buddy | None | Ask your manager to assign a Spin-up Buddy before starting |
| VPN connectivity | vpn | `curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://brewweb.engineering.redhat.com/brew/` (expect 200) | Connect to the Red Hat VPN |
| Jira access | jira | `jira_status https://redhat.atlassian.net/rest/api/3/myself` (expect 200) | Set up `JIRA_API_TOKEN` and `JIRA_USER` or `JIRA_EMAIL` per jira.md |
| ServiceNow portal | servicenow | `curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://redhat.service-now.com/help` (expect 200) | Verify access to https://redhat.service-now.com/help?id=rh_requests |

## Section: Access and Permissions

Track: both

| Item | Key | URL |
|------|-----|-----|
| LDAP: openshift-node-team | ldap_node_team | https://rover.redhat.com/groups/group/openshift-node-team |
| LDAP: openshift-dev-node-team | ldap_dev_node_team | https://rover.redhat.com/groups/group/openshift-dev-node-team |
| Google Group: aos-node | google_aos_node | https://groups.google.com/a/redhat.com/g/aos-node |
| Google Group: aos-announce | google_aos_announce | https://groups.google.com/a/redhat.com/g/aos-announce |
| Slack: team-node (private) | slack_team_node | Request manager to add you |
| Slack: forum-ocp-node (public) | slack_forum_node | Join directly |
| Slack: @node-team user group | slack_node_handle | Request TL to add you |
| Calendar: OpenShift Main Calendar | cal_openshift | https://calendar.google.com/calendar/embed?src=redhat.com_2v3jc3smo4hr9r8dkv5phed66g%40group.calendar.google.com |
| Calendar: team PTO | cal_pto | Add the shared team leave calendar |

For the LDAP and Google groups, the manager or TL adds the user. The full
list of Slack channels and user groups is in team-info.md.

Verify LDAP membership:
```bash
ldapsearch -x -H ldaps://ldap.corp.redhat.com -b dc=redhat,dc=com -s sub 'uid=<your-uid>'
```

## Section: GCP Access

Track: both

| Item | Key | URL |
|------|-----|-----|
| Request openshift-gce-devel access | gcp_access | https://devservices.dpp.openshift.com/support/gcp_access_request/ |

Verify: https://console.cloud.google.com/welcome?project=openshift-gce-devel

Processing time: ~2 business days.

## Section: IDE License

Track: both

| Item | Key | URL |
|------|-----|-----|
| GoLand license | goland_license | https://source.redhat.com/groups/public/openshift/openshift_wiki/jetbrains_product_licenses |

File a DPP ticket in Jira. IntelliJ licenses are not available.

## Section: GitHub Setup

Track: both

| Item | Key | Check Command | Manual Action |
|------|-----|---------------|---------------|
| GitHub CLI authenticated | gh_auth | `gh auth status` (expect success) | Install `gh` and run `gh auth login` |
| OpenShift org member | gh_openshift_org | `gh api orgs/openshift/memberships/<github-handle> --jq '.state'` (expect "active") | Follow the setup guide below |

Ask the user for their GitHub handle and substitute it in the membership
check.

Setup guide:
https://source.redhat.com/groups/public/openshift/openshift_wiki/openshift_onboarding_checklist_for_github

## Section: Jira Dashboard

Track: both

| Item | Key | Check Command |
|------|-----|---------------|
| Node Components filter access | jira_filter | `jira_status https://redhat.atlassian.net/rest/api/3/filter/91645` (expect 200) |
| Node Bugs filter visible | jira_dashboard | None (manual: check https://redhat.atlassian.net/issues/?filter=83963) |

Request dashboard access:
https://redhat.atlassian.net/servicedesk/customer/portal/2

## Section: Development Environment

Track: both

| Item | Key | Check Command | Manual Action |
|------|-----|---------------|---------------|
| Go installed | go_installed | `which go && go version` | Install from https://go.dev/doc/install |
| kubectl installed | kubectl_installed | `which kubectl` | `brew install kubectl` (macOS) or distro package |
| oc CLI installed | oc_installed | `which oc` | Download from https://console.redhat.com/openshift/downloads |

`GOPATH` does not need to be set; Go modules work without it.

After these checks pass, use `/node-team:setup` to clone repos and create
worktrees. See
[SETUP.md](../../node-team/skills/node/references/SETUP.md).

For kubelet/CRI-O development, you can run a local single-node cluster
via `local-up-cluster.sh` from the Kubernetes repo:
```bash
CGROUP_DRIVER=systemd CONTAINER_RUNTIME_ENDPOINT=unix:///var/run/crio/crio.sock hack/local-up-cluster.sh
```

## Section: Cluster Creation

Track: both

| Item | Key | Instructions |
|------|-----|-------------|
| First cluster via ClusterBot | cluster_bot | DM "Cluster Bot" on Slack, type `launch <latest GA version> gcp` (the current GA release per the "stable channel" lookup in node-team `shared/version-map.md`, major.minor only, not the newest release branch; `help` lists the accepted version forms), wait ~30 min |
| AWS access (optional) | aws_access | For longer-lived clusters. Request openshift-dev AWS access via https://devservices.dpp.openshift.com/support (VPN required) |
| GCP cluster (optional) | gcp_cluster | Requires the openshift-gce-devel access from the GCP Access section. See the internal cluster creation guide |

ClusterBot is the recommended path for a first cluster. Its clusters expire
after ~2 hours. Use `export KUBECONFIG=<file>` and `kubectl get nodes` to
verify.

## Section: Customer Support Readiness

Track: both

| Item | Key | Check Command |
|------|-----|---------------|
| SupportShell access | supportshell | `ssh -o ConnectTimeout=5 -o BatchMode=yes supportshell-1.sush-001.prod.us-west-2.aws.redhat.com exit` (expect success) |
| omc tool | omc_installed | `which omc` (local; install omc for must-gather analysis if missing) |
| yank tool | yank_installed | `ssh -o ConnectTimeout=5 -o BatchMode=yes supportshell-1.sush-001.prod.us-west-2.aws.redhat.com 'command -v yank'` (expect success) |

`yank` is preinstalled on SupportShell and is not needed locally, so its
check runs over SSH and depends on SupportShell access.

Setup: https://source.redhat.com/groups/public/customerplatform/customerplatform_wiki/how_to_access_supportshell

Workflow: `yank -y <case_id>` to download case data, `omc use <file>` to
load, then `omc get nodes`, `omc get mc`, etc.

## Section: QE-Specific

Track: qe

| Item | Key | URL |
|------|-----|-----|
| QE onboarding guide | qe_guide | https://source.redhat.com/groups/public/openshiftqe/workflows/openshift_qe_workflow_wiki/openshift_qe_new_hire_guide |
| Clone openshift-tests-private (manual action: `git clone` this repository) | qe_tests_repo | https://github.com/openshift/openshift-tests-private |
| Polarion access | qe_polarion | https://polarion.engineering.redhat.com/polarion/#/project/OSE/mypolarion |
| Learn Ginkgo framework | qe_ginkgo | Study https://onsi.github.io/ginkgo/ |
