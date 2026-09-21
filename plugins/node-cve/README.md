# Node CVE Plugin

CVE triage for OpenShift Node team components. Queries open vulnerability issues from OCPBUGS, runs reachability analysis against affected repositories, and reports findings to Jira and Slack.

Part of the [node-team plugin family](../node-team/).

## Installation

```bash
/plugin install node-cve@ai-helpers
```

Requires the `node-team` plugin (installed automatically as a dependency).

## Command

### `/node-cve:triage [--component <name>] [--ocp-version X.Y] [--days N] [--notify-jira] [--notify-slack] [--dry-run] [--yes] [--max-trackers N] [--handoff --trackers FILE]`

Triage all open CVEs for Node team components with automated reachability analysis.

**Examples:**
```text
/node-cve:triage
/node-cve:triage --notify-jira --notify-slack --dry-run
/node-cve:triage --notify-jira --notify-slack
```

Without notify flags the command only analyzes and writes a local report. With them it shows what it is about to post and asks for confirmation first.

**What it does:**

1. Queries OCPBUGS for open Vulnerability issues across all Node team components (CRI-O, Kubelet, MCO, etc.)
2. Deduplicates by CVE ID (each CVE has multiple version trackers)
3. Filters to one OCP version: the latest in-development release, auto-detected as the highest numeric version across all open Node trackers (never from a result set narrowed by `--days` or `--component`), or set with `--ocp-version`. Other versions are owned by the sustaining team.
4. Clones affected downstream forks at that version's release branch and analyzes source code for reachability, including Go standard library CVEs (checked against the Go builder version, not `go.mod`)
5. Classifies each CVE: Reachable, Present but not exploitable, Present but not reachable, Unaffected, or Uncertain
6. Generates a triage report with confidence levels and recommended actions
7. Re-validates every tracker, enforces the `--max-trackers` threshold, and asks for confirmation (or requires `--yes` when headless)
8. Posts analysis comments to Jira tracker issues (with `--notify-jira`), updating an existing comment in place when the classification changed
9. Sends a summary to Slack (with `--notify-slack`)

**Arguments:**
- `--component <name>`: Filter to a single specific component (e.g., "Node / CRI-O"). If omitted, ALL Node team components are included, and only Node team components, never all OCPBUGS components.
- `--ocp-version X.Y`: OCP version to triage. Default: auto-detected. Use it when several in-development versions have open trackers.
- `--days N`: Only include CVEs updated in the last N days (default: all open)
- `--notify-jira`: Post analysis results as comments on Jira tracker issues (also enables cross-run caching)
- `--notify-slack`: Send summary to Slack (API token for threading, or webhook for a single message)
- `--dry-run`: Do everything except posting. Records what would be posted in `posting-audit.log`.
- `--yes`: Skip the confirmation. Required for headless posting: a headless run without it aborts before posting.
- `--max-trackers N`: Refuse all Jira posting if more than N trackers pass validation (default: 50). Not bypassed by `--yes`.
- `--handoff`: Make no Jira or Slack calls. The caller supplies the tracker rows with `--trackers FILE` and posts from `posting-plan.json`. See [Chai RWS](#chai-rws).
- `--trackers FILE`: Tracker rows from the caller's Jira search (only with `--handoff`).

**Output:**
- Summary table printed to stdout
- Full report at `.work/node-cve/triage-YYYY-MM-DD/report.md`
- Structured data at `.work/node-cve/triage-YYYY-MM-DD/cves.json`
- Per-CVE analysis files in `.work/node-cve/triage-YYYY-MM-DD/`
- `posting-audit.log` in the same directory whenever posting or `--dry-run` was requested, also printed to stdout at the end of the run. Every post is mirrored to `.work/node-cve/posting-history.log`.

## Prerequisites

- `bash`, `curl`, `jq` and `git`

All Jira access uses the Jira REST API through the plugin's helper script ([node-cve-lib.sh](skills/report-findings/scripts/node-cve-lib.sh)), which is the only shell command the plugin runs. The `jira` CLI is not required: it cannot list or edit comments, has no component column, and its pagination offset is ignored on Jira Cloud. Tokens are passed to `curl` on stdin, never on a command line.

**Environment variables:**
- `JIRA_API_TOKEN` - Jira API token (required)
- `JIRA_USER` (or `JIRA_EMAIL`) - Jira login for the token. Falls back to `git config user.email`. Set it explicitly for service accounts and in containers.
- `SLACK_API_TOKEN` - Slack bot token (preferred for `--notify-slack`, enables threaded messages)
- `SLACK_CHANNEL` - Slack channel ID, used with `SLACK_API_TOKEN`. Optional, default: `GK6BJJ1J5` (`#team-node`)
- `SLACK_WEBHOOK` - Slack incoming webhook URL (alternative for `--notify-slack`, no threading). Used only when `SLACK_API_TOKEN` is not set.

Run `/node-team:preflight` to check credentials before the first use.

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
      "Bash(bash /home/claude/.claude/plugins/cache/ai-helpers/node-cve/*/skills/report-findings/scripts/node-cve-lib.sh *)",
      "Edit(.work/node-cve/**)",
      "Read(//home/claude/.claude/plugins/cache/ai-helpers/node-cve/**)",
      "Read(//home/claude/.claude/plugins/cache/ai-helpers/node-team/**)",
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

The helper script is the only shell command the plugin runs. It makes all
Jira REST calls, the Slack post and the shallow clones, so no `jira` CLI and
no `jira` config file are needed. It takes the Jira account from `JIRA_EMAIL`
(or `JIRA_USER`) and the token from `JIRA_API_TOKEN`. The Bash rule must match
the path the plugin is installed to (`${CLAUDE_PLUGIN_ROOT}`). Check it with a
`--dry-run` run first: a wrong path shows up as refused tool calls in the
transcript. Keep the rule pointed at a directory the agent cannot write to.

Posting needs `--yes` in headless runs. Without it the command stops before
the first Jira or Slack post, because nobody can confirm. `--yes` does not
bypass the `--max-trackers` threshold (default 50), and `--dry-run` wins over
`--yes`.

Run locally with the ai-helpers container:

```bash
podman run -it \
  -e CLAUDE_CODE_USE_VERTEX=1 \
  -e ANTHROPIC_VERTEX_PROJECT_ID=your-project \
  -e CLOUD_ML_REGION=your-region \
  -e JIRA_API_TOKEN \
  -e JIRA_EMAIL \
  -e SLACK_WEBHOOK \
  -v ./settings.json:/home/claude/.claude/settings.json:ro \
  -v ~/.config/gcloud:/home/claude/.config/gcloud:ro \
  ai-helpers --print "/node-cve:triage --notify-jira --notify-slack --dry-run"
```

`-e NAME` without a value passes the variable through from the calling shell,
so the secrets do not end up in the shell history or the process list. Drop
`--dry-run` and add `--yes` once the audit log shows the expected posts.

### Chai RWS

On Chai RWS the worker that runs Claude Code gets no credentials: the
trusted manager sidecar holds them, and the coordinator makes the Jira and
Slack calls with its own tools. The worker has a git proxy for the clones.
The command therefore runs with `--handoff`, and the coordinator does the
Jira and Slack part. The worker checks the rows it gets against the
component list, the version filter and `--max-trackers`, and returns
`posting-plan.json`; the coordinator re-checks each tracker live before it
posts. The scheduled task tells the coordinator to:

1. Search Jira with `query_jira` for the JQL that
   `node-cve-lib.sh jql` prints (all Node components, no `--days`), following
   every page. Keep that JQL in the task config. Each run prints it again, so
   a change of the node-team component list shows up in the run output.
2. Start the worker with `rws_query`: write the rows to
   `.work/node-cve/trackers.tsv` (tab-separated: key, summary, components
   `;`-separated, status, assignee, labels `,`-separated), then run
   `/node-cve:triage --handoff --trackers .work/node-cve/trackers.tsv --notify-jira --notify-slack`.
3. Take the plan from the end of the worker output. Post nothing to Jira if
   `dry_run` is true or `posting_gate` is not `open`, and never post to a key
   that is not in `jira`.
4. For each `jira` entry, fetch the tracker with `get_jira_issue` and skip it
   (and report the skip) unless its components still equal `components` and
   its summary still contains `[openshift-<version_filter>]`. Skip it as
   unchanged when its newest comment containing `marker` has the same
   `Classification` and `Branch` rows as the entry. Otherwise post `body`
   unchanged with `comment_on_jira_issue`. The body is Jira wiki markup and
   ends with the AI-generated footer, which must stay.
5. Send the `slack` texts (header, summary, details, footer) in the report.

Chai's Jira tools cannot edit a comment, so a changed classification adds a
new comment instead of updating the old one in place, and a trusted
`[reanalyze]` tag is not honored. The Jira comment cache is not available
either, so every run analyzes all CVEs again. The Jira account behind the
coordinator's tools needs to browse OCPBUGS and add comments there.

### OpenShift CronJob

Headless runs use a Jira service account and `SLACK_WEBHOOK`, see the
[compliance data flow](../node-team/docs/compliance/dataflow.md#deployment-modes).
The pod must run with an egress policy that only allows Jira, Slack, GitHub,
the public advisory sites and Vertex AI (see
[prompt injection](../node-team/docs/compliance/dataflow.md#prompt-injection)).

The `node-cve-triage-config` ConfigMap holds the `settings.json` above and
the Workload Identity Federation credential config for Vertex AI (no key; it
points at the projected token). The pod is discarded after each run, so the
session transcript (`--output-format stream-json`) goes to stdout and every
audit event is streamed from `posting-history.log` to stderr as it is
written. Cluster logging captures both.

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
              audit=.work/node-cve/posting-history.log
              mkdir -p .work/node-cve && touch "$audit"
              tail -f "$audit" >&2 &
              tail_pid=$!
              claude --print --output-format stream-json --verbose \
                "/node-cve:triage --notify-jira --notify-slack --yes"
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
              name: node-cve-triage-config # settings.json, gcp-credentials.json
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

Many CVEs (especially Go stdlib or vendored-dependency vulnerabilities) have tracker issues across dozens of OpenShift teams, not just Node. Posting Node-specific reachability analysis to another team's tracker is confusing and erodes trust in the automation.

1. **Component filter at query time (Phase 1):** Every Jira query, whether or not `--component` is passed, is scoped with `component in (...)` to the Node team component list from the [shared components reference](../node-team/skills/node/references/shared/components.md). "No `--component` flag" means "all Node team components," never "no filter."
2. **Component re-validation at posting time (Phase 3):** Immediately before posting any `--notify-jira` comment, each tracker's component is re-checked against the Node team list, independent of Phase 1's filtering. Trackers that do not match are skipped and recorded in `posting-audit.log` instead of being commented on. The helper script refuses to comment on any tracker that did not pass this validation in the current run.

This design follows an incident (2026-07-15) where a CVE with 200+ multi-team trackers had Node-specific analysis posted to non-Node trackers because a downstream step re-searched Jira by CVE ID alone without a component filter.

### Version safeguard (cross-version protection)

Each CVE has tracker issues for every affected OCP version (e.g., 4.12.z through 5.0). The OCP sustaining team owns triage for all versions except the latest in-development release. The Node team should only triage the latest version.

1. **Version filter at query time (Phase 1):** After deduplication, trackers are filtered to one OCP version: the highest numeric `major.minor` across all open Node trackers (detected from an un-narrowed query and sanity-checked against the shared version map), or the `--ocp-version` value. Only trackers matching that version are retained.
2. **Version re-validation at posting time (Phase 3):** Immediately before posting, each tracker's OCP version (from its summary) is re-checked against the selected version. Trackers that do not match are skipped and recorded in `posting-audit.log`.

### Posting safeguard (outward-facing actions)

Jira comments and Slack messages are hard to take back, so posting is gated:

1. **Dry run:** `--dry-run` runs the full pipeline and records what would be posted, without posting.
2. **Confirmation:** an interactive run shows the plan (tracker count, keys, Slack target) and asks once. A headless run must pass `--yes`. Without it, the run aborts before posting instead of waiting for input.
3. **Threshold:** if more trackers pass validation than `--max-trackers` (default 50), no Jira comment is posted at all. `--yes` does not bypass this.
4. **Audit:** every post, would-post, skip, refusal and failure is written to `posting-audit.log`, mirrored to `.work/node-cve/posting-history.log`, and printed at the end of the run.

See [report-findings](skills/report-findings/SKILL.md) for the full validation logic (including `.z` suffix handling). Never construct a CVE-ID-only Jira search as a shortcut for finding trackers to comment on. Always reuse the already-filtered tracker list from Phase 1.

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
| Unaffected | Vulnerable package is not in the dependency tree, or the dependency / Go builder version already contains the fix | 🟢 Unaffected |
| Uncertain | Analysis could not determine (repo too large, CVE details insufficient, fork or branch missing, clone failed) | ⚠️ Uncertain |

Each classification includes a confidence level (high/medium/low) based on the depth of source code analysis performed. The summary output groups "Present but not exploitable" and "Present but not reachable" together since both mean no urgent action is needed. The detailed report and Jira comments preserve the specific classification. `cves.json` uses the enum values `REACHABLE`, `PRESENT_NOT_EXPLOITABLE`, `PRESENT_NOT_REACHABLE`, `UNAFFECTED` and `UNCERTAIN`.
