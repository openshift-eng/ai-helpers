# Node CVE Plugin

CVE triage for OpenShift Node team components. Queries open vulnerability issues from OCPBUGS, runs reachability analysis against affected repositories, and reports findings to Jira and Slack.

Part of the [node-team plugin family](../node-team/).

## Installation

```bash
/plugin install node-cve@ai-helpers
```

Requires the `node-team` plugin (installed automatically as a dependency).

## Command

### `/node-cve:triage [--component <name>] [--notify-jira] [--notify-slack] [--days N]`

Triage all open CVEs for Node team components with automated reachability analysis.

**Example:**
```text
/node-cve:triage --notify-jira --notify-slack
```

**What it does:**

1. Queries OCPBUGS for open Vulnerability issues across all Node team components (CRI-O, Kubelet, MCO, etc.)
2. Deduplicates by CVE ID (each CVE has multiple version trackers)
3. Filters to the latest OCP version (auto-detected as the highest numeric version from query results, e.g., `5.0`). Older versions are owned by the sustaining team.
4. Clones affected repositories at the latest version's release branch and analyzes source code for reachability
5. Classifies each CVE: Reachable, Present but not exploitable, Present but not reachable, Unaffected, or Uncertain
6. Generates a triage report with confidence levels and recommended actions
7. Posts analysis comments to Jira tracker issues (with `--notify-jira`)
8. Sends a threaded summary to Slack (with `--notify-slack`)

**Arguments:**
- `--component <name>`: Filter to a single specific component (e.g., "Node / CRI-O"). If omitted, ALL Node team components are included — and only Node team components, never all OCPBUGS components.
- `--notify-jira`: Post analysis results as comments on Jira tracker issues (also enables cross-run caching)
- `--notify-slack`: Send summary to Slack (API token for threading, or webhook for simple messages)
- `--days N`: Only include CVEs updated in the last N days (default: all open)

**Output:**
- Summary table printed to stdout
- Full report at `.work/node-cve/triage-YYYY-MM-DD/report.md`
- Structured data at `.work/node-cve/triage-YYYY-MM-DD/cves.json`
- Per-CVE analysis files in `.work/node-cve/triage-YYYY-MM-DD/`

## Prerequisites

```bash
# Jira CLI
# See https://github.com/ankitpokhrel/jira-cli

# git (for cloning repos)
# curl (for --notify-slack)
```

**Environment variables:**
- `JIRA_API_TOKEN` - Jira API token (required)
- `SLACK_API_TOKEN` - Slack bot token (preferred for `--notify-slack`, enables threaded messages)
- `SLACK_CHANNEL` - Slack channel ID (required with `SLACK_API_TOKEN`). Default: `GK6BJJ1J5` (`#team-node`)
- `SLACK_WEBHOOK` - Slack incoming webhook URL (alternative for `--notify-slack`, no threading)

## Headless Execution

The `ai-helpers` image ships the plugins under `/opt/ai-helpers`, but its
default settings neither enable `node-cve` nor allow any tools. Headless runs
need their own `settings.json`. With `dontAsk`, every tool call that is not
allowed below is refused; Claude Code's built-in read-only commands (`ls`,
`cat`, `echo`, `head`, `tail`, `grep`, `find`, `wc` and similar) always run.
The `Read` deny rules only cover Claude Code's file tools, so `cat` or any
allowed command could still read the credential mounts. The Bash sandbox
closes that gap: `sandbox.credentials` blocks both mounts for every Bash
command at the OS level. Keep this file in sync with the
[capabilities inventory](../node-team/docs/compliance/capabilities-inventory.md#headless-tool-allowlist):

```json
{
  "extraKnownMarketplaces": {
    "ai-helpers": { "source": { "source": "directory", "path": "/opt/ai-helpers" } }
  },
  "enabledPlugins": {
    "node-team@ai-helpers": true,
    "node-cve@ai-helpers": true
  },
  "permissions": {
    "defaultMode": "dontAsk",
    "allow": [
      "Skill(node-cve:*)",
      "Bash(jira issue list:*)",
      "Bash(jira issue view:*)",
      "Bash(jira issue comment add:*)",
      "Bash(git clone:*github.com/*)",
      "Bash(curl:*redhat.atlassian.net/*)",
      "Bash(curl:*hooks.slack.com/*)",
      "Bash(date:*)",
      "Bash(sleep:*)",
      "Bash(mkdir -p .work/node-cve/*)",
      "Bash(tee -a .work/node-cve/*)",
      "Edit(.work/node-cve/**)",
      "WebSearch",
      "WebFetch(domain:nvd.nist.gov)",
      "WebFetch(domain:access.redhat.com)",
      "WebFetch(domain:github.com)",
      "WebFetch(domain:pkg.go.dev)"
    ],
    "deny": [
      "Read(//var/run/secrets/**)",
      "Read(//etc/node-cve-triage/**)",
      "Read(//proc/**)"
    ]
  },
  "sandbox": {
    "enabled": true,
    "failIfUnavailable": true,
    "autoAllowBashIfSandboxed": false,
    "enableWeakerNestedSandbox": true,
    "credentials": {
      "files": [
        { "path": "/var/run/secrets", "mode": "deny" },
        { "path": "/etc/node-cve-triage", "mode": "deny" }
      ]
    },
    "network": {
      "allowedDomains": ["redhat.atlassian.net", "hooks.slack.com", "github.com"],
      "strictAllowlist": true
    }
  }
}
```

The sandbox settings:

- `failIfUnavailable` makes the run fail instead of running unsandboxed.
- `autoAllowBashIfSandboxed: false` keeps the allowlist above in charge of
  which commands run.
- `enableWeakerNestedSandbox` is needed in an unprivileged pod, which cannot
  mount a fresh `/proc`. The pod is the outer isolation boundary.
- Bash commands only reach the listed hosts.

The Claude Code process itself is not sandboxed, so it still reads the
Vertex AI credentials. The sandbox needs `bubblewrap` and `socat`, which the
`ai-helpers` image does not ship yet, and a pod that may create user
namespaces. Check both with a first run: without them Claude Code refuses to
start. The environment variables (`JIRA_API_TOKEN`, `SLACK_WEBHOOK`) stay
readable, see the
[security boundary](../node-team/docs/compliance/capabilities-inventory.md#security-boundary).

The `jira` CLI needs a config file for the account it runs as (server, login,
auth type), not only `JIRA_API_TOKEN`. Generate it once with `jira init` and
point `JIRA_CONFIG_FILE` at it. The `curl` calls for Jira comment edits take
the account from `JIRA_EMAIL`.

Run locally with the ai-helpers container:

```bash
podman run -it \
  -e CLAUDE_CODE_USE_VERTEX=1 \
  -e ANTHROPIC_VERTEX_PROJECT_ID=your-project \
  -e CLOUD_ML_REGION=your-region \
  -e JIRA_API_TOKEN=... \
  -e JIRA_EMAIL=... \
  -e JIRA_CONFIG_FILE=/home/claude/.jira.yml \
  -e SLACK_WEBHOOK=... \
  -v ./settings.json:/home/claude/.claude/settings.json:ro \
  -v ./jira.yml:/home/claude/.jira.yml:ro \
  -v ~/.config/gcloud:/home/claude/.config/gcloud:ro \
  ai-helpers --print "/node-cve:triage --notify-jira --notify-slack"
```

### OpenShift CronJob

Headless runs use a Jira service account and `SLACK_WEBHOOK`, see the
[compliance data flow](../node-team/docs/compliance/dataflow.md#deployment-modes).
The pod must run with an egress policy that only allows Jira, Slack, GitHub,
the public advisory sites and Vertex AI (see
[prompt injection](../node-team/docs/compliance/dataflow.md#prompt-injection)).

The `node-cve-triage-config` ConfigMap holds the `settings.json` above, the
`jira` CLI config and the Workload Identity Federation credential config for
Vertex AI (no key; it points at the projected token). The pod is discarded
after each run, so the session transcript (`--output-format stream-json`)
goes to stdout and `posting-audit.log` is streamed to stderr. Cluster
logging captures both.

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: node-cve-triage
  namespace: node-team
spec:
  schedule: "3 8 * * 1-5"
  timeZone: Etc/UTC        # requires K8s 1.27+ / OCP 4.14+
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 7
  failedJobsHistoryLimit: 7
  jobTemplate:
    metadata:
      labels:
        app: node-cve-triage
    spec:
      backoffLimit: 0             # never retry a run that may have posted already
      activeDeadlineSeconds: 3600 # kill runaway runs (monitoring plan threshold)
      template:
        metadata:
          labels:
            app: node-cve-triage
        spec:
          restartPolicy: Never
          serviceAccountName: node-cve-triage
          automountServiceAccountToken: false # no Kubernetes API token in the pod
          containers:
          - name: triage
            image: <ai-helpers image, pinned by digest>
            command: ["/bin/bash", "-c"]
            args:
            - |
              audit=.work/node-cve/triage-$(date +%Y-%m-%d)/posting-audit.log
              mkdir -p "$(dirname "$audit")" && touch "$audit"
              tail -f "$audit" >&2 &
              tail_pid=$!
              claude --print --output-format stream-json --verbose \
                "/node-cve:triage --notify-jira --notify-slack"
              rc=$?
              sleep 1; kill $tail_pid 2>/dev/null; wait $tail_pid 2>/dev/null
              exit $rc
            env:
            - name: CLAUDE_CODE_USE_VERTEX
              value: "1"
            - name: ANTHROPIC_VERTEX_PROJECT_ID
              value: <vertex project>
            - name: CLOUD_ML_REGION
              value: <vertex region>
            - name: JIRA_CONFIG_FILE
              value: /etc/node-cve-triage/jira.yml
            - name: GOOGLE_APPLICATION_CREDENTIALS
              value: /etc/node-cve-triage/gcp-credentials.json
            envFrom:
            - secretRef:
                name: cve-triage-secrets # JIRA_API_TOKEN, JIRA_EMAIL, SLACK_WEBHOOK
            resources:
              requests:
                cpu: "1"
                memory: 2Gi
                ephemeral-storage: 4Gi
              limits:
                memory: 4Gi
                ephemeral-storage: 8Gi
            volumeMounts:
            - name: config
              mountPath: /home/claude/.claude/settings.json
              subPath: settings.json
            - name: config
              mountPath: /etc/node-cve-triage
            - name: gcp-token
              mountPath: /var/run/secrets/gcp
              readOnly: true
            - name: workspace
              mountPath: /workspace # repo clones and reports
          volumes:
          - name: config
            configMap:
              name: node-cve-triage-config # settings.json, jira.yml, gcp-credentials.json
          - name: gcp-token
            projected:
              sources:
              - serviceAccountToken:
                  audience: <workload identity pool provider audience>
                  expirationSeconds: 3600
                  path: token
          - name: workspace
            emptyDir:
              sizeLimit: 5Gi
```

If the GCP organization does not allow Workload Identity Federation for the
cluster, mount a service account key from a Secret instead and rotate it at
least quarterly.

Only the namespace admins (see
[RBAC Enforcement](../node-team/docs/compliance/user-guide.md#rbac-enforcement))
can trigger or stop runs. A manual run bypasses `concurrencyPolicy`, so
suspend the CronJob first and wait until no Job is active before creating it:

```bash
oc patch cronjob node-cve-triage -p '{"spec":{"suspend":true}}'
oc get jobs -l app=node-cve-triage # wait until every job has a completion time
oc create job --from=cronjob/node-cve-triage node-cve-triage-manual-$(date +%s)
# resume the schedule once the manual job has finished
oc patch cronjob node-cve-triage -p '{"spec":{"suspend":false}}'

# stop: suspend future runs, then delete only the active job
oc patch cronjob node-cve-triage -p '{"spec":{"suspend":true}}'
oc delete job <active job name>
```

## Safeguards

The plugin implements two safeguards, each with query-time and posting-time validation, to ensure triage analysis is only posted where it belongs:

### Component safeguard (cross-team protection)

Many CVEs (especially Go stdlib or vendored-dependency vulnerabilities) have tracker issues across dozens of OpenShift teams — not just Node. Posting Node-specific reachability analysis to another team's tracker is confusing and erodes trust in the automation.

1. **Component filter at query time (Phase 1):** Every Jira query — whether or not `--component` is passed — is scoped with `component in (...)` to the Node team component list from the [shared components reference](../node-team/skills/node/references/shared/components.md). "No `--component` flag" means "all Node team components," never "no filter."
2. **Component re-validation at posting time (Phase 3):** Immediately before posting any `--notify-jira` comment, each tracker's component is re-checked against the Node team list, independent of Phase 1's filtering. Trackers that don't match are skipped and recorded in `posting-audit.log` instead of being commented on.

This design follows an incident (2026-07-15) where a CVE with 200+ multi-team trackers had Node-specific analysis posted to non-Node trackers because a downstream step re-searched Jira by CVE ID alone without a component filter.

### Version safeguard (cross-version protection)

Each CVE has tracker issues for every affected OCP version (e.g., 4.12.z through 5.0). The OCP sustaining team owns triage for all versions except the latest in-development release. The Node team should only triage the latest version.

1. **Version filter at query time (Phase 1):** After deduplication, trackers are filtered to the auto-detected latest OCP version (the highest numeric `major.minor` from query results). Only trackers matching that version are retained.
2. **Version re-validation at posting time (Phase 3):** Immediately before posting, each tracker's OCP version (from its summary) is re-checked against the auto-detected version. Trackers that don't match are skipped and recorded in `posting-audit.log`.

See [report-findings](skills/report-findings/SKILL.md) for the full validation logic (including `.z` suffix handling), and never construct a CVE-ID-only Jira search as a shortcut for finding trackers to comment on — always reuse the already-filtered tracker list from Phase 1.

## Node Team Components

The plugin covers all CVE-tracked OCPBUGS components owned by the Node team.
See the [node-team shared components reference](../node-team/skills/node/references/shared/components.md)
for the full mapping including downstream forks, branch patterns, languages,
and `pscomponent:` label mappings. See the
[node-team shared version map](../node-team/skills/node/references/shared/version-map.md)
for OCP-to-K8s/CRI-O version mappings.

## Reachability Classification

| Classification | Meaning | Summary Group |
|---------------|---------|---------------|
| Reachable | Vulnerable code path is reachable from entry points with attacker-controlled input | 🔴 Reachable |
| Present but not exploitable | Vulnerable function is called, but only with trusted/internal data | 🟡 Present |
| Present but not reachable | Vulnerable package is a dependency but the specific vulnerable functions are not called | 🟡 Present |
| Unaffected | Vulnerable package is not in the dependency tree | 🟢 Unaffected |
| Uncertain | Analysis could not determine (repo too large, CVE details insufficient, etc.) | ⚠️ Uncertain |

Each classification includes a confidence level (high/medium/low) based on the depth of source code analysis performed. The summary output groups "Present but not exploitable" and "Present but not reachable" together since both mean no urgent action is needed. The detailed report and Jira comments preserve the specific classification.
