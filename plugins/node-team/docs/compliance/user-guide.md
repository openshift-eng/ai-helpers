# Node Team AI Assistant - User Guide

Control ID: TR-02

## Overview

The Node team plugin suite is a set of Claude Code plugins that assist the
OpenShift Node team with development workflows, CVE vulnerability triage, and
component management. The suite consists of:

- **node-team**: umbrella plugin for development setup, team overview, debugging,
  and shared reference data
- **node-onboarding**: guided onboarding for new team members
- **node-cve**: automated CVE triage with source code reachability analysis
- **node-bug**: bug triage, sub-team routing, and assignment suggestions
- **node-rpm**: RPM build and dist-git management

### Quick Start

```bash
# Install the plugin family
/plugin install node-team@ai-helpers
/plugin install node-onboarding@ai-helpers
/plugin install node-cve@ai-helpers
/plugin install node-bug@ai-helpers
/plugin install node-rpm@ai-helpers

# Verify credentials are working
/node-team:preflight

# Run CVE triage
/node-cve:triage
```

## Limitations

- AI-generated analysis may produce false positives (flagging unreachable code
  as reachable) or false negatives (missing actual reachability paths).
  Classifications are probabilistic, not definitive.
- Reachability analysis depends on the quality of available source code. If a
  downstream fork is missing or a branch does not exist, the result is
  classified as "Uncertain."
- The agent cannot access private repositories or systems beyond what the
  configured API tokens allow.
- Jira queries are scoped to OCPBUGS/OCPNODE projects. Issues in other projects
  are not analyzed.
- The agent does not perform runtime testing or dynamic analysis. All analysis
  is static, based on source code inspection.

## Agent Persona and Purpose

The agent acts as a technical assistant for the Node team. Its role is to
surface information, perform analysis, and present findings for human review.
It does not make decisions autonomously: all write actions (Jira comments,
Slack notifications) require explicit opt-in via command flags.

## Capabilities and Inventory

See [capabilities-inventory.md](capabilities-inventory.md) for the full list
of tools, APIs, data sources, and guardrails. The `jira`, `git` and `curl`
CLIs run through Claude Code's Bash tool.

### Authorized Actions

- Query Jira for open CVE trackers and team issues (read)
- Clone public downstream OpenShift repository forks (read)
- Analyze source code for CVE reachability (read, local computation)
- Post analysis comments to Jira issues (write, opt-in via `--notify-jira`)
- Send summary notifications to Slack (write, opt-in via `--notify-slack`)
- Generate local reports in `.work/` (write, local only)
- Bump downstream RPM packages in dist-git and start Brew builds
  (`/node-rpm:bump`, interactive only, each push and build confirmed by the
  user)

### Prohibited Actions

- The agent must not create or close Jira issues
- The agent must not transition issue status (e.g., move to ASSIGNED or CLOSED)
- The agent must not create pull requests
- The agent must not commit code or modify repository contents, except
  user-confirmed dist-git changes through `/node-rpm:bump`
- The headless deployment is configured to run only `/node-cve:triage`; only
  the namespace admins can change the CronJob or create Jobs
- The agent must not access customer data, HR data, or financial data
- The agent must not send messages to external parties

## Best Practices

- Run `/node-team:preflight` before first use to verify all credentials
- Start without `--notify-jira`/`--notify-slack` to review output before posting
- For CVE triage, review the generated report at
  `.work/node-cve/triage-YYYY-MM-DD/report.md` before enabling notifications
- Use `--component <name>` to scope triage to a single component when debugging

## Human Review and Action

**Always review AI-generated output prior to use.**

All analysis results require human review before acting on them. The agent's
CVE classifications (Reachable, Present, Unaffected, Uncertain) are
suggestions, not authoritative determinations. Security decisions must be
made by qualified engineers.

Other existing code review and compliance processes still apply. The agent's
output does not replace manual security analysis.

## Rollback and Emergency Stop (Kill Switch)

### Interactive Mode
- Press `Ctrl-C` to stop any running command immediately.

### Headless / CronJob Mode
Run by the namespace admins:
- Suspend future runs: `oc patch cronjob node-cve-triage -p '{"spec":{"suspend":true}}'`
- Stop the active run: find it with `oc get jobs -l app=node-cve-triage`
  (the job without a completion time) and delete only that one with
  `oc delete job <name>`. Deleting a Job also deletes its pod and logs;
  cluster logging keeps its own copy.
- Delete the CronJob entirely: `oc delete cronjob node-cve-triage`
- Revoke the credentials to disable all external actions, independently of
  the cluster: the Jira service account token, the Slack webhook, and the
  Vertex AI access (remove the Workload Identity Federation binding, or
  delete the service account key)

### Reverting Actions
- Jira comments posted by the agent can be edited or deleted manually
- Slack messages can be deleted from the channel
- Local artifacts in `.work/` can be removed with `/node-team:cleanup`

## Data Handling

Do not add any personal information or customer information to the AI tool.

The agent processes only:
- Jira ticket metadata (summaries, components, assignees, labels, status)
- Low-sensitivity personal data (team member names, email addresses,
  GitHub handles from the team roster, treated as business contact
  information per Red Hat's data classification)
- Public source code from downstream OpenShift forks
- Public CVE advisory data

See [dataflow.md](dataflow.md) for the complete data flow diagram.

Refer to the "High-Risk Data Sensitivity" section of Red Hat's
[Risk Assessment Rubric](https://source.redhat.com/departments/strategy_and_operations/it/it_information_security/data_privacy/risk_assessment_rubric_)
for types of personal information and customer data that are out of scope.

## RBAC Enforcement

The agent inherits permissions from the configured API tokens:
- **Jira**: scoped by `JIRA_API_TOKEN`. The agent can only access projects and
  issues the token owner has permission to view/comment on.
- **Slack**: scoped by `SLACK_API_TOKEN` bot permissions. The bot can only post
  to channels it has been added to.
- **GitHub**: scoped by `gh` CLI authentication. Only public repos or repos the
  authenticated user can access.

Users can verify their access levels by running `/node-team:preflight`.

In headless mode the agent does not inherit a user's permissions. It runs
with a Jira service account limited to browsing OCPBUGS and OCPNODE and
adding and editing its own comments on OCPBUGS, and a Slack incoming webhook
bound to #team-node. Tool use is limited by the
[headless tool allowlist](capabilities-inventory.md#headless-tool-allowlist).

Namespace access has two levels, each backed by a Rover group:

| Group | Role | Can do |
|-------|------|--------|
| Node team members | Custom read-only Role: `get`, `list`, `watch` on `cronjobs`, `jobs`, `pods` and `pods/log` | See runs and read their logs |
| Admins (two or three maintainers) | `admin` | Change the CronJob and its config, trigger runs (`oc create job --from=cronjob/node-cve-triage <name>`, after checking that no run is active, since manual runs bypass `concurrencyPolicy`), suspend, manage secrets |

The namespace is provisioned with a Role for read-only viewers and a
RoleBinding for each level. Admins get the built-in `admin` ClusterRole
scoped to the namespace. Both bindings reference OCP groups synced from
Rover by the cluster's group-sync operator.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: node-cve-viewer
  namespace: node-team
rules:
- apiGroups: ["batch"]
  resources: ["cronjobs", "jobs"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: node-cve-viewers
  namespace: node-team
subjects:
- kind: Group
  name: node-cve-triage-viewers   # synced from Rover
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: node-cve-viewer
  apiGroup: rbac.authorization.k8s.io
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: node-cve-admins
  namespace: node-team
subjects:
- kind: Group
  name: node-cve-triage-admins    # synced from Rover
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: admin
  apiGroup: rbac.authorization.k8s.io
```

Anyone who can create Jobs or edit the CronJob can run any image with the
mounted secrets, and RBAC cannot restrict what a Job runs. That is why
triggers stay with the admins and team members get no write access or
secret access.

## Troubleshooting

Common issues and solutions:

| Issue | Solution |
|-------|----------|
| Jira API returns 401 | Token expired. Regenerate at https://id.atlassian.com/manage-profile/security/api-tokens |
| Jira API returns 429 | Rate limited. Wait and retry. The agent sleeps 1s between calls. |
| Slack notification fails | Verify `SLACK_API_TOKEN` and `SLACK_CHANNEL` (check bot is added to channel), or `SLACK_WEBHOOK`. |
| Git clone times out | Network issue or repo doesn't exist at that branch. Classification defaults to "Uncertain." |
| Empty triage results | Check Jira query. Run `/node-cve:triage --component "Node / CRI-O"` to test a single component. |

Run `/node-team:preflight --fix` for automated credential verification and
remediation guidance.

## Feedback

Report issues, suggest improvements, or provide feedback on analysis quality:
- GitHub: https://github.com/openshift-eng/ai-helpers/issues
- Tag issues with `plugin/node-cve` or `plugin/node-team`

## Point of Contact

- Team alias: aos-node@redhat.com
- Slack: #team-node (Red Hat internal)
