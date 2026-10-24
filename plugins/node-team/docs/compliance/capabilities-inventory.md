# Node Team AI Assistant - Capabilities Inventory

Control ID: GLC-08

## Tools

All tools are command-line programs run through Claude Code's Bash tool. There
are no separate "direct" integrations for `jira` or `git`.

| Tool | Purpose | Plugin |
|------|---------|--------|
| `bash` helper script | `node-cve-lib.sh`: the single entry point for all Jira REST, Slack and `git` access of `/node-cve:triage` | node-cve |
| `git` | Clone repositories; create branches, worktrees and local commits in the user's checkouts; commit and push to dist-git (node-rpm, interactive only, after user confirmation) | node-cve, node-team, node-rpm |
| `curl` | Jira REST API, Slack API, Red Hat SSO / KB / support case API calls | node-bug, node-cve, node-team, node-onboarding |
| `jq` | JSON processing | all |
| `gh` | GitHub CLI: auth check, PR and repo reads | node-team |
| `oc` / `kubectl` | Cluster inspection; debug-binary deployment (cordon, drain, bastion, helper pod) on development clusters | node-team |
| `ssh` / `scp` | Reach RHCOS nodes through the SSH bastion for debug-binary deployment | node-team |
| `docker` / `podman` | Cross-compile debug binaries in containers | node-team |
| `promtool` | Query Prometheus / Thanos | node-team |
| `security` / `secret-tool` | Read tokens from the macOS Keychain / Linux secret service | node-team, node-bug |
| `vagrant`, `rhpkg`, `brew` | RPM build environment, dist-git clone, source upload, Brew builds | node-rpm (interactive only) |
| `du`, `rm` | Size and purge local artifacts (`/node-team:cleanup`, after confirmation) | node-team |
| `claude plugin install` | Install the plugin into a worktree (`/node-team:setup`) | node-team |

## APIs

### Jira REST API (https://redhat.atlassian.net)

| Endpoint | Method | Action | Plugin |
|----------|--------|--------|--------|
| `/rest/api/3/search/jql` | POST | Query CVE trackers | node-cve |
| `/rest/api/3/search/jql` | POST | Query team bugs, epics and sprint work | node-bug, node-team |
| `/rest/api/3/issue/{key}` | GET | Fetch issue details | node-cve, node-team |
| `/rest/api/3/issue` | POST | Create issue (interactive, after user confirmation) | node-team |
| `/rest/api/3/issue/{key}` | PUT | Update fields (interactive, after user confirmation) | node-team |
| `/rest/api/3/issue/{key}/assignee` | PUT | Assign (interactive, after user confirmation) | node-team |
| `/rest/api/3/issue/{key}/transitions` | GET, POST | List and perform transitions (POST after user confirmation) | node-team |
| `/rest/api/3/issue/{key}/remotelink` | POST | Add link (interactive, after user confirmation) | node-team |
| `/rest/api/3/user/search` | GET | Resolve users | node-team |
| `/rest/api/3/myself` | GET | Credential check (`/node-team:preflight`) | node-team |
| `/rest/api/2/myself` | GET | Account id for the comment ownership check | node-cve |
| `/rest/agile/1.0/sprint/{id}/issue` | GET, POST | Sprint issues; move to sprint (POST after user confirmation) | node-team |
| `/rest/api/2/issue/{key}/comment` | GET | List comments (cache check, deduplication); v2 because comment bodies are wiki markup | node-cve |
| `/rest/api/2/issue/{key}/comment` | POST | Add analysis comment | node-cve |
| `/rest/api/2/issue/{key}/comment/{id}` | PUT | Edit the account's own existing comment | node-cve |
| `/rest/agile/1.0/board/11478/sprint` | GET | List active sprints | node-team |
| `/rest/api/3/issue/OCPNODE-4230` | GET | Fetch team roster attachments (issue overridable with `NODE_ASSISTANT_CONFIG_ISSUE`) | node-team |

Authentication: HTTP Basic Auth with `JIRA_USER` (or `JIRA_EMAIL`) and
`JIRA_API_TOKEN`. Credentials are passed to curl on stdin (`curl -K -`), not on
the command line.

### Red Hat SSO, Knowledge Base and Support Case APIs

| Endpoint | Method | Action | Plugin |
|----------|--------|--------|--------|
| `sso.redhat.com/.../openid-connect/token` | POST | Exchange `RH_API_OFFLINE_TOKEN` for a short-lived access token | node-team |
| `access.redhat.com/hydra/rest/search/kcs` | GET | Search KB solutions and articles | node-team |
| `api.access.redhat.com/support/v1/cases/{caseNumber}` | GET | Read a support case, its comments and attachment list | node-team |
| `api.access.redhat.com/support/v1/cases/filter` | POST | Search cases (only on explicit user request) | node-team |

Authentication: Bearer access token. Read only. Support cases are customer
data; see the handling rules in `skills/node/references/support.md` and the
Data Handling section of the [user guide](user-guide.md).

### OpenShift / Kubernetes clusters

Used interactively by the `node-team:node` skill against a cluster the user
is logged in to (`oc`), with the user's own RBAC: inspection, Prometheus
queries through the Thanos route, and debug-binary deployment (bastion, cordon,
drain, service restart) on development clusters.

### Slack API (https://slack.com/api)

| Endpoint | Method | Action | Plugin |
|----------|--------|--------|--------|
| `chat.postMessage` | POST | Send summary and threaded replies | node-cve |

Authentication: Bearer token via `SLACK_API_TOKEN`.

Alternative: `SLACK_WEBHOOK` (incoming webhook, POST only, no threading).
Headless runs use `SLACK_WEBHOOK` only: the Slack app holds just the
`incoming-webhook` scope and can post to a single channel.

### GitHub

| Action | Method | Plugin |
|--------|--------|--------|
| Clone downstream forks for analysis | `git clone --depth 1` | node-cve |
| Clone repos for development | `git clone` (full history), `git fetch pull/N/head` | node-team |
| Auth check, PR reads | `gh auth status`, `gh api`, `gh pr view` | node-team |

Authentication: `gh` CLI auth or unauthenticated for public repos.

## Data Sources

| Source | Type | Data Accessed | Plugin |
|--------|------|---------------|--------|
| OCPBUGS (Jira) | Read | Issue summaries, components, assignees, labels, status, custom fields | node-cve, node-bug |
| OCPNODE, OCPBUGS and related projects (Jira) | Read; write after user confirmation | Issues, sprints, epics; team config issue (OCPNODE-4230) with roster attachments | node-team |
| Red Hat KB and support cases | Read | KB solutions; support case metadata, comments, attachment lists (customer data) | node-team |
| Development clusters | Read/Write | Node state, metrics, debug binaries | node-team |
| Downstream forks (GitHub) | Read | Source code at release branches (shallow clone) | node-cve |
| NVD / public advisories | Read | CVE descriptions, affected packages, fixed versions | node-cve |
| `~/.node-assistant/team-roster-*.json` | Read/Write | Cached team rosters (display names and GitHub handles). Written only by `/node-team:overview` | node-team (write), node-bug (read) |
| `~/.node-assistant/onboarding-progress.json` | Read/Write | Onboarding checklist progress | node-onboarding |

## Write Actions and Guardrails

### Jira Comments (node-cve)

This table covers the automated `node-cve` flow only. The authoritative
description is in the node-cve plugin (`commands/triage.md` and the
`report-findings` skill).

| Guardrail | Implementation |
|-----------|----------------|
| Opt-in only | Requires `--notify-jira` flag |
| Deduplication | Checks for existing `node-cve:triage` comments before posting; edits if classification changed, skips if unchanged |
| Rate limiting | 1-second sleep between API calls |
| Attribution | Footer: `_AI-generated analysis by [node-cve:triage\|...]. Always review prior to use._` |
| Scope | node-cve: comments only; no issue creation, status transitions, or assignment changes |
| Error handling | Failed comments are logged and skipped; does not fail the entire run |

### Interactive Jira Writes (node-team)

The `node-team:node` skill documents the Jira endpoints for creating and
updating issues, assigning, transitioning, linking and moving issues between
sprints. These are never automated or scheduled.

| Guardrail | Implementation |
|-----------|----------------|
| User-initiated | Only when the user asks for the change in an interactive session |
| Confirmation | `jira.md`: "Always confirm with the user before any write operation (create, edit, comment, transition)" |
| Permissions | Bounded by the user's own Jira permissions (personal API token) |
| Visibility | Every call is a Bash tool call the user can see and deny |

### Slack Messages (node-cve)

| Guardrail | Implementation |
|-----------|----------------|
| Opt-in only | Requires `--notify-slack` flag |
| Channel scope | Posts to configured `SLACK_CHANNEL` only (default: #team-node) |
| Attribution | Context block: "AI-generated by node-cve:triage. Always review prior to use." |
| Size limits | Truncates to Slack's 3000-char block limit with "... and N more" |
| Error handling | Failed sends are logged as warnings; non-fatal |

### Local Artifacts

| Guardrail | Implementation |
|-----------|----------------|
| Isolation | All artifacts written to `.work/` (gitignored) |
| Purge | `/node-team:cleanup` removes caches after confirmation; onboarding progress and the posting audit log only after a separate confirmation |
| Code changes stay local | node-cve clones are read-only analysis copies. `/node-team:setup` and the worktree workflow create branches, worktrees and (on request) local commits in the user's own checkouts. The plugins never push or open pull requests on their own, except the user-confirmed node-rpm dist-git pushes below; changes reach a shared repository only through the user's normal PR review flow |

### Dist-git and Brew (node-rpm, interactive only)

`/node-rpm:bump` updates a spec file in dist-git, pushes the change and
starts a Brew build. It is never run headless.

| Guardrail | Implementation |
|-----------|----------------|
| Human approval | The diff and the source checksum are reviewed before the lookaside upload; the push and the build each require their own explicit user confirmation |
| Credentials | User's own Kerberos ticket and dist-git permissions; no service account |
| Scope | Only packages listed in `rpm-workflow.md`; `--scratch` builds from the working tree without upload, commit or push |
| Reversibility | Dist-git commits can be reverted by a follow-up commit; official Brew builds cannot be deleted, but do not ship outside the regular release process |
| Headless | Not part of the CronJob deployment; the container image has no `rhpkg` or Kerberos credentials |

### Cluster Changes (node-team)

| Guardrail | Implementation |
|-----------|----------------|
| Development clusters only | Debug-binary deployment is documented for debug and POC clusters |
| Safety rules | Preflight test, cordon and drain first, one node at a time, rollback known before deploy (`deployment/debug-binary.md`) |
| Pinned third-party script | The SSH bastion deploy script is pinned to a commit, downloaded, reviewed and run only after user confirmation |
| Confirmation | Service account creation for Prometheus access requires user confirmation and is cleaned up afterwards |

## Tool Access Model

Every tool in the Tools table, including `git` and `curl`, runs through
Claude Code's Bash tool. Claude Code has no separate integration for them.

The `allowed-tools: Bash(curl:*)` frontmatter of the `node-team:node` skill
**pre-approves** curl calls so they do not prompt each time. It does not
restrict the agent to curl. Compound commands (for example the auth block in
`jira.md`, which resolves credentials and then calls curl) do not match
`Bash(curl:*)` and go through the normal permission prompt.

- **Interactive:** Claude Code asks the user before each tool call that is not
  already allowed in the user's settings.
- **Headless:** no one is there to approve. The `dontAsk` permission mode
  refuses every tool call outside the allowlist below.

### Headless Tool Allowlist

The CronJob mounts a `settings.json` that enables only the `node-team` and
`node-cve` plugins (full file in the
[node-cve README](../../../node-cve/README.md#headless-execution)):

| Rule | Purpose |
|------|---------|
| `Skill(node-cve:*)` | Load the node-cve skills |
| `Bash(bash <node-cve plugin root>/skills/report-findings/scripts/node-cve-lib.sh *)` | The only shell command of `/node-cve:triage`. The helper script makes all Jira REST calls (search, tracker validation, comment lookup, add and edit), the Slack webhook post and the shallow `git` clones. The plugin root is outside the working directory and not writable through the allowed tools |
| `Edit(.work/node-cve/**)` | Reports, comment bodies and the component list the helper reads |
| `Read` on the installed `node-team` and `node-cve` plugin directories | Shared component and version data, skill references |
| `WebSearch`, `WebFetch` (nvd.nist.gov, access.redhat.com, github.com, pkg.go.dev) | Public CVE intelligence |
| Deny `Read` on `/var/run/secrets/**`, `/etc/node-cve-triage/**`, `/proc/**` | Keep credentials and the projected token out of Claude Code's file tools |
| Sandbox: deny `/var/run/secrets` and `/etc/node-cve-triage` in `sandbox.credentials`, network limited to Jira, Slack and GitHub | Keep the same files out of every Bash command, including the built-in read-only ones; fail the run if the sandbox cannot start |

In addition, Claude Code always allows its built-in read-only commands (`ls`,
`cat`, `echo`, `head`, `tail`, `grep`, `find`, `wc`, `which` and similar),
reads inside the working directory, and nothing else. Source code analysis
uses the Read, Grep and Glob tools on the clones in the working directory.
The `Read` deny rules do not apply to Bash commands; the sandbox does.

The helper enforces the posting rules in code, independent of the prompt:
`post-comment` refuses trackers that did not pass component and version
validation in the same run, refuses everything once more trackers validated
than `--max-trackers` (default 50), skips a tracker when the comment lookup
fails, and only edits comments owned by the invoking account. Without `--yes`
a headless run stops before posting, and `--dry-run` records what would be
posted without sending anything.

On Chai RWS the command runs with `--handoff`: the helper refuses every Jira
and Slack call, `validate` checks the coordinator's tracker rows offline, and
`plan-comment` applies the same gate checks as `post-comment` before it adds a
comment to `posting-plan.json`. The coordinator re-checks each tracker with
its own Jira tools before posting (see the
[node-cve README](../../../node-cve/README.md#chai-rws)).

### Security Boundary

The allowlist limits what the agent does by default; it is not a security
boundary. Claude Code's own documentation says so for Bash rules. The helper
script narrows the surface compared to free-form `curl` and `git clone` rules
(it only talks to the configured Jira site, Slack and the clone URL it is
given, and never prints credentials). Its `clone` subcommand accepts only
plain `https://` URLs and ref names made of safe characters, which rules out
`ext::` transports and option injection, but it still takes a URL argument,
and the credentials are environment variables of the pod.
The agent reads untrusted text (Jira descriptions, advisory pages, cloned
source code), so a prompt injection could try to use these paths.

The actual boundary is the pod:

- **Egress policy (required):** only Jira, Slack, GitHub, the public advisory
  sites and Vertex AI are reachable
- **Least-privilege credentials:** the Jira service account can only browse
  and comment, the Slack webhook posts to one channel, the Vertex identity
  can only call Vertex AI, and there is no Kubernetes API token
- **Ephemeral pod:** nothing persists between runs
- **Bash sandbox:** Bash commands cannot read the Vertex AI token or the
  mounted config and only reach Jira, Slack and GitHub. The environment
  variables stay readable, and a comment or Slack post can still carry data
  out, so the credentials above must stay least privilege
- **Audit:** every tool call is in the session transcript in the pod logs

Any change to the allowlist must update this table.
