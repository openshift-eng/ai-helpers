# Node CVE Plugin

CVE triage for OpenShift Node team components. Queries open vulnerability issues from OCPBUGS, runs reachability analysis against affected repositories, and reports findings to Jira and Slack.

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
3. Clones affected repositories at all version-specific release branches and analyzes source code for reachability
4. Classifies each CVE: Reachable, Present but not exploitable, Present but not reachable, Unaffected, or Uncertain
5. Generates a triage report with confidence levels and recommended actions
6. Posts analysis comments to Jira tracker issues (with `--notify-jira`)
7. Sends a threaded summary to Slack (with `--notify-slack`)

**Arguments:**
- `--component <name>`: Filter to a specific component (e.g., "Node / CRI-O")
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

Run as a scheduled job using the ai-helpers container:

```bash
podman run -it \
  -e CLAUDE_CODE_USE_VERTEX=1 \
  -e ANTHROPIC_VERTEX_PROJECT_ID=your-project \
  -e JIRA_API_TOKEN=... \
  -e SLACK_API_TOKEN=xoxb-... \
  -e SLACK_CHANNEL=GK6BJJ1J5 \
  -v ~/.config/gcloud:/home/claude/.config/gcloud:ro \
  ai-helpers --print "/node-cve:triage --notify-jira --notify-slack"
```

### OpenShift CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: node-cve-triage
  namespace: node-team
spec:
  schedule: "3 8 * * 1-5"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: triage
            image: ai-helpers:latest
            args: ["--print", "/node-cve:triage --notify-jira --notify-slack"]
            envFrom:
            - secretRef:
                name: cve-triage-secrets
          restartPolicy: OnFailure
```

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
