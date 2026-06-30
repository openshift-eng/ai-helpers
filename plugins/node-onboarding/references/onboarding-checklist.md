# Node Team Onboarding Checklist

Structured checklist for the `/node-onboarding:checklist` command. Each
section maps to a phase in the onboarding process. Items marked with a
check command can be validated automatically; others require manual
confirmation.

Source: Node Team Onboarding Guide (Google Doc, all tabs).

## Section: Prerequisites

Track: both

| Item | Key | Check Command |
|------|-----|---------------|
| Spin-up Buddy assigned | spinup_buddy | None (manual: ask manager) |
| VPN connectivity | vpn | `curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://brewweb.engineering.redhat.com/brew/` (expect 200) |
| Jira access | jira | `curl -s -o /dev/null -w "%{http_code}" -u "${JIRA_USER:-$(git config user.email)}:$JIRA_API_TOKEN" "https://redhat.atlassian.net/rest/api/3/myself"` (expect 200) |
| ServiceNow portal | servicenow | `curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 https://redhat.service-now.com/help` (expect 200) |

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

| Item | Key | Check Command |
|------|-----|---------------|
| GitHub CLI authenticated | gh_auth | `gh auth status` (expect success) |
| OpenShift org member | gh_openshift_org | `gh api orgs/openshift/memberships/<github-handle> --jq '.state'` (expect "active") |

Setup guide:
https://source.redhat.com/groups/public/openshift/openshift_wiki/openshift_onboarding_checklist_for_github

## Section: Jira Dashboard

Track: both

| Item | Key | Check Command |
|------|-----|---------------|
| Node Components filter access | jira_filter | `curl -s -u "${JIRA_USER:-$(git config user.email)}:$JIRA_API_TOKEN" "https://redhat.atlassian.net/rest/api/3/filter/91645" -o /dev/null -w "%{http_code}"` (expect 200) |
| Node Bugs filter visible | jira_dashboard | None (manual: check https://redhat.atlassian.net/issues/?filter=83963) |

Request dashboard access:
https://issues.redhat.com/servicedesk/customer/portal/2

## Section: Development Environment

Track: both

| Item | Key | Check Command |
|------|-----|---------------|
| Go installed | go_installed | `which go && go version` |
| kubectl installed | kubectl_installed | `which kubectl` |
| oc CLI installed | oc_installed | `which oc` |
| GOPATH configured | gopath_set | `test -n "$GOPATH"` |

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
| First cluster via ClusterBot | cluster_bot | DM "Cluster Bot" on Slack, type `launch 4.19 gcp`, wait ~30 min |
| AWS access (optional) | aws_access | Request via https://devservices.dpp.openshift.com/support (account 269733383066) |

ClusterBot clusters expire after ~2 hours. Use `export KUBECONFIG=<file>`
and `kubectl get nodes` to verify.

## Section: Customer Support Readiness

Track: both

| Item | Key | Check Command |
|------|-----|---------------|
| SupportShell access | supportshell | `ssh -o ConnectTimeout=5 -o BatchMode=yes supportshell-1.sush-001.prod.us-west-2.aws.redhat.com exit` (expect success) |
| omc tool | omc_installed | `which omc` |
| yank tool | yank_installed | `which yank` |

Setup: https://source.redhat.com/groups/public/customerplatform/customerplatform_wiki/how_to_access_supportshell

Workflow: `yank -y <case_id>` to download case data, `omc use <file>` to
load, then `omc get nodes`, `omc get mc`, etc.

## Section: QE-Specific

Track: qe

| Item | Key | URL |
|------|-----|-----|
| QE onboarding guide | qe_guide | https://source.redhat.com/groups/public/openshiftqe/workflows/openshift_qe_workflow_wiki/openshift_qe_new_hire_guide |
| Clone openshift-tests-private | qe_tests_repo | https://github.com/openshift/openshift-tests-private |
| Polarion access | qe_polarion | https://polarion.engineering.redhat.com/polarion/#/project/OSE/mypolarion |
| Learn Ginkgo framework | qe_ginkgo | Study https://onsi.github.io/ginkgo/ |
