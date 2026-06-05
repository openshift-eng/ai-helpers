---
name: create-prow-agent
description: Interactive guide to design, configure, and deploy a new Prow-based AI agent in OpenShift CI. Walks through brainstorming the agent's purpose, then generates step registry refs, commands scripts, and ci-operator configs with a prerequisites checklist for credentials the developer needs to fill in.
user-invocable: true
---

# Create a Prow-Based AI Agent

This skill guides you through building a new autonomous AI agent that runs in OpenShift CI (Prow). It covers the full lifecycle: designing what the agent does, then generating all the CI artifacts (with a prerequisites checklist for credentials) so the developer can get a PR up to `openshift/release` right away while collecting secrets in parallel.

## When to Use This Skill

Use this skill when someone wants to:

- Create a new periodic, presubmit, or ad-hoc AI agent job in Prow
- Automate a workflow that requires AI analysis, code generation, or triage
- Understand what's needed to run Claude Code autonomously in OpenShift CI

## Background: Existing Agents

Three production agents in the [openshift/release](https://github.com/openshift/release) repository define the patterns this skill follows. All live under `ci-operator/step-registry/` in that repo:

1. **Payload Agent** ([`openshift/claude/payload/`](https://github.com/openshift/release/tree/main/ci-operator/step-registry/openshift/claude/payload)) — Triggers on release payloads. Polls blocking CI jobs, analyzes failures with Claude, generates HTML reports, and hands off to Chai Bot for autonomous remediation — a multi-agent system.

2. **HyperShift Jira Agent** ([`hypershift/jira-agent/`](https://github.com/openshift/release/tree/main/ci-operator/step-registry/hypershift/jira-agent)) — Runs on a cron schedule. Queries Jira for issues labeled `issue-for-agent`, processes each through a four-phase pipeline (solve → code review → fix → PR creation), tracks state via Jira labels, and uses GitHub App tokens with separate fork/upstream installations.

3. **HyperShift Review Agent** ([`hypershift/review-agent/`](https://github.com/openshift/release/tree/main/ci-operator/step-registry/hypershift/review-agent)) — Runs periodically on weekdays. Finds agent-created PRs with unresolved review threads, rebases stale branches, addresses reviewer feedback via Claude, and fixes failing CI checks. Uses a comment analyzer to prevent duplicate bot responses.

## Implementation Steps

### Prerequisites Check (Important)

Before starting, verify the user's environment. This check is critical — without these tools, later steps will be blocked or require manual workarounds.

#### Chai Bot MCP

Check if the Chai Bot MCP server is configured:

```bash
grep -q "chai" ~/.claude.json 2>/dev/null || grep -q "chai" .claude/settings.json 2>/dev/null
```

If Chai Bot is **not enabled**, strongly recommend it:

> **Recommended:** Enable the Chai Bot MCP server before continuing. Chai Bot can provide guidance on any of the prerequisites you'll need to set up — GitHub App configuration, vault secrets, GCP service accounts, and more. You can ask it questions like "How do I get a GitHub App set up?" or "How do I add a secret to the CI vault?" as we work through this guide.

#### openshift/release Clone

Check if a local clone of `openshift/release` exists:

```bash
ls ~/git/release 2>/dev/null || ls /tmp/release 2>/dev/null
```

If a clone is available, use it. If not, offer to fork and clone it for them:

> I don't see a local clone of `openshift/release`. I can fork it to your GitHub account and clone it — would you like me to do that?

If they agree, fork via `gh repo fork openshift/release --clone --remote` into a working directory.

#### GitHub CLI (`gh`)

Check if `gh` is installed and authenticated:

```bash
gh auth status
```

If `gh` is set up, you can create PRs to `openshift/release` automatically at the end. If not, let the user know:

> The `gh` CLI isn't configured. I can still generate all the files, but you'll need to push and open the PR manually. You can set it up with `gh auth login` if you'd like automated PR creation.

### Phase 1: Brainstorm and Design

This phase is interactive. Ask the user questions to understand their agent, then produce a design summary.

#### Step 1.1: Understand the Problem

Ask the user:

> What problem should this agent solve? Describe the workflow you want to automate — what does a human do today that the agent should handle?

Listen for:
- The domain (CI failures, Jira issues, PRs, tests, docs, dependencies, etc.)
- Whether the task is read-only analysis or produces artifacts (PRs, comments, reports)
- How much autonomy the agent should have (fully autonomous vs. human-in-the-loop)

#### Step 1.2: Determine the Trigger

Ask the user:

> How should this agent be triggered?
>
> - **Periodic (cron)** — runs on a schedule (e.g., daily, weekly). Best for batch processing like "process all new Jira issues" or "check for stale PRs."
> - **Presubmit** — runs on PRs, either automatically on matching PRs or on-demand via `/test <job-name>`. Best for PR-scoped analysis like code review or test gap detection.
> - **Payload verification** — runs when a release payload is assembled. Best for release-scoped analysis.
> - **Ad-hoc (Gangway API)** — a periodic job triggered on demand with parameter overrides. Best for one-off tasks like "analyze this specific Jira issue."

Help them choose. If they want ad-hoc triggering, explain that this is implemented as a periodic job with `@yearly` cron plus Gangway API overrides using `MULTISTAGE_PARAM_OVERRIDE_*` environment variables. The `ci:trigger-periodic` command can trigger these.

#### Step 1.3: Identify Data Sources and Actions

Ask the user:

> What data does the agent need to read, and what actions should it take?

Build a table of data sources and actions. Common ones:

| Data Source | Access Method | Credentials Needed |
|-------------|--------------|-------------------|
| Jira issues | REST API (`redhat.atlassian.net`) | Jira email + API token (Basic Auth) |
| GitHub PRs/code | `gh` CLI + git | GitHub App token |
| CI job results | Prow/GCS artifacts | None (public) |
| Sippy test data | Sippy API | None (public) |
| Release payloads | Release controller API | None (public) |

| Action | Tool | Credentials Needed |
|--------|------|-------------------|
| Open/update PRs | `gh pr create` | GitHub App (upstream installation) |
| Push branches | `git push` | GitHub App (fork installation) |
| Comment on Jira | REST API | Jira email + API token |
| Post to Slack | Webhook | Slack webhook URL |
| Generate reports | HTML to `${ARTIFACT_DIR}` | None |

#### Step 1.4: Audit Existing Skills

Search the ai-helpers plugins directory for skills and commands the agent could reuse:

```bash
find plugins -name "*.md" -path "*/commands/*" | while read f; do
  name=$(basename "$f" .md)
  plugin=$(echo "$f" | grep -oP 'plugins/\K[^/]+')
  desc=$(grep -m1 '^description:' "$f" | sed 's/^description: //')
  echo "  /${plugin}:${name} — ${desc}"
done
```

Present the relevant matches to the user. Common reusable skills:

- `/jira:solve` — Analyze a Jira issue and create a PR to solve it
- `/code-review:pre-commit-review` — Review code changes before committing
- `/utils:address-reviews` — Address reviewer feedback on a PR
- `/ci:analyze-prow-job-test-failure` — Analyze a specific Prow job test failure
- `/ci:analyze-prow-job-install-failure` — Analyze install failures
- `/ci:payload-analysis` — Full payload analysis with HTML report

If the user needs functionality not covered by existing skills, note what custom skills they'll need to write. Help them design the skill interface (inputs, outputs, what Claude should do).

#### Step 1.5: Design the Pipeline

Based on the answers above, design the agent's pipeline. Most agents follow a multi-phase pattern. Propose a pipeline and confirm with the user.

Common patterns:

**Single-phase (analysis only):**
```
1. Gather data → 2. Analyze with Claude → 3. Report results
```

**Multi-phase (code changes):**
```
1. Query work items → 2. Solve each item → 3. Code review → 4. Fix review findings → 5. Create PR → 6. Notify
```

**Multi-phase (with polling):**
```
1. Poll until data ready → 2. Snapshot data → 3. Analyze → 4. Report → 5. Notify
```

Write a design summary capturing:
- Agent name and purpose
- Trigger type and schedule
- Pipeline phases
- Data sources and credentials needed
- Existing skills to reuse
- Custom skills to write
- Target repository (where the agent operates)

Confirm the design with the user before proceeding to Phase 2.

### Phase 2: Generate CI Artifacts and Prerequisites Checklist

#### Step 2.1: Explore Existing Agent Patterns in openshift/release

Before writing any files, explore the `openshift/release` clone to understand current patterns for AI-based agents. Read the step registry refs, commands scripts, and workflow YAMLs of existing agents:

```bash
# Find all AI agent step registry entries
find ci-operator/step-registry -name "*-commands.sh" | xargs grep -l "claude" 2>/dev/null
find ci-operator/step-registry -name "*-ref.yaml" | xargs grep -l "claude-ai-helpers" 2>/dev/null
```

Read through at least two of the existing agents to understand:
- How they structure their workflow YAML (pre/test/post phases)
- How they configure env vars and credentials in the ref YAML
- How the commands script invokes Claude (flags, output parsing, error handling)
- How they handle GitHub App token generation and credential loading
- How they track token usage and generate reports

Use these real, up-to-date patterns as the template for the new agent — not just the examples in this skill. The existing agents may have evolved since this skill was written.

#### Step 2.2: Set Up Branch and Choose a Step Registry Path

Create a feature branch in the `openshift/release` clone:

```bash
cd {release-repo-path}
git checkout -b add-{agent-name}
```

Generate a prerequisites checklist the developer works through in parallel. When done, open a PR to `openshift/release` — rehearsals will validate the step registry structure even before secrets are wired up.

The step registry path determines the job's identity.

Use the `openshift/release` clone identified in the prerequisites check. Create a feature branch:

```bash
cd {release-repo-path}
git checkout -b add-{agent-name}
```

The step registry path determines the job's identity. Convention: `{team-or-component}/{agent-name}/`. For example:

- `hypershift/jira-agent/`
- `openshift/claude/payload/`
- `myteam/my-agent/`

Ask the user for their preferred path. The full directory structure will be:

```
ci-operator/step-registry/{path}/
├── {agent-name}-workflow.yaml
├── setup/
│   ├── {agent-name}-setup-ref.yaml
│   └── {agent-name}-setup-commands.sh
├── process/
│   ├── {agent-name}-process-ref.yaml
│   └── {agent-name}-process-commands.sh
└── report/                              (optional)
    ├── {agent-name}-report-ref.yaml
    └── {agent-name}-report-commands.sh
```

#### Step 2.3: Write the Workflow YAML

Generate the workflow YAML. A typical three-phase workflow:

```yaml
workflow:
  as: {agent-name}
  steps:
    pre:
      - ref: {agent-name}-setup
    test:
      - ref: {agent-name}-process
    post:
      - ref: {agent-name}-report
  documentation: |-
    {Description of what the workflow does}
```

If the agent is simple (single phase, no reporting), a single ref without a workflow may suffice.

#### Step 2.4: Write the Setup Step

The setup step verifies the environment is ready. Minimal example:

**Ref YAML** (`setup/{agent-name}-setup-ref.yaml`):
```yaml
ref:
  as: {agent-name}-setup
  from: claude-ai-helpers
  commands: {agent-name}-setup-commands.sh
  env:
  - name: CLAUDE_CODE_USE_VERTEX
    default: "1"
  - name: CLOUD_ML_REGION
    default: "global"
  - name: ANTHROPIC_VERTEX_PROJECT_ID
    default: "YOUR_GCP_PROJECT_ID"
    documentation: |-
      TODO: Replace with your GCP project ID from the Vertex AI service account.
  - name: GOOGLE_APPLICATION_CREDENTIALS
    default: "/var/run/claude-code-service-account/YOUR_KEY_FILENAME"
    documentation: |-
      TODO: Replace YOUR_KEY_FILENAME with the vault key name for your GCP SA JSON.
  resources:
    requests:
      cpu: 100m
      memory: 200Mi
  credentials:
  - namespace: test-credentials
    name: YOUR_VAULT_SECRET_NAME
    mount_path: /var/run/claude-code-service-account
  documentation: |-
    Setup step: verifies Claude Code CLI is available.
```

**Commands** (`setup/{agent-name}-setup-commands.sh`):
```bash
#!/bin/bash
set -euo pipefail
echo "=== {Agent Name} Setup ==="
claude --version
echo "Claude Code CLI verified"
```

#### Step 2.5: Write the Process Step

This is the main step. Generate the ref YAML and commands script based on the design.

**Ref YAML** (`process/{agent-name}-process-ref.yaml`):

Include all env vars from the design:
- Vertex AI vars (always required)
- Agent-specific config vars (e.g., `MAX_ISSUES`, issue key overrides)
- `CLAUDE_MODEL` (default: `claude-sonnet-4-6` for cost efficiency, `claude-opus-4-6` for complex reasoning)
- Gangway override vars if ad-hoc triggering is needed

Set appropriate resource requests:
- CPU: `500m` (typical for AI agents)
- Memory: `1Gi` (typical)

Set a timeout appropriate to the workload (1-12 hours).

**Commands script** (`process/{agent-name}-process-commands.sh`):

The commands script follows this structure. Include only the sections relevant to the design:

```bash
#!/bin/bash
set -euo pipefail

echo "=== {Agent Name} Process ==="

# --- Gangway API overrides (if ad-hoc triggering) ---
if [[ -n "${MULTISTAGE_PARAM_OVERRIDE_MY_PARAM:-}" ]]; then
  export MY_PARAM="${MULTISTAGE_PARAM_OVERRIDE_MY_PARAM}"
fi

# --- State file for report step ---
STATE_FILE="${SHARED_DIR}/processed-items.txt"

# --- Clone repos (if agent operates on a codebase) ---
git clone https://github.com/{org}/{repo} /tmp/{repo}
cd /tmp/{repo}
git config user.name "OpenShift CI Bot"
git config user.email "ci-bot@redhat.com"

# --- GitHub App token generation (if pushing/creating PRs) ---
# The function below generates installation tokens from a GitHub App.
# Requires vault keys: app-id, private-key, installation-id
GITHUB_APP_CREDS_DIR="/var/run/claude-code-service-account"

generate_github_token() {
  local INSTALL_ID=$1
  local NOW=$(date +%s)
  local IAT=$((NOW - 60))
  local EXP=$((NOW + 600))
  local HEADER=$(echo -n '{"alg":"RS256","typ":"JWT"}' | base64 | tr -d '=' | tr '/+' '_-' | tr -d '\n')
  local PAYLOAD=$(echo -n "{\"iat\":${IAT},\"exp\":${EXP},\"iss\":\"$(cat ${GITHUB_APP_CREDS_DIR}/app-id)\"}" | base64 | tr -d '=' | tr '/+' '_-' | tr -d '\n')
  local SIGNATURE=$(echo -n "${HEADER}.${PAYLOAD}" | openssl dgst -sha256 -sign "${GITHUB_APP_CREDS_DIR}/private-key" | base64 | tr -d '=' | tr '/+' '_-' | tr -d '\n')
  curl -s -X POST \
    -H "Authorization: Bearer ${HEADER}.${PAYLOAD}.${SIGNATURE}" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/app/installations/${INSTALL_ID}/access_tokens" \
    | jq -r '.token'
}

# --- Load Jira credentials (if using Jira) ---
JIRA_TOKEN_FILE="${GITHUB_APP_CREDS_DIR}/jira-pat"
JIRA_EMAIL_FILE="${GITHUB_APP_CREDS_DIR}/jira-email"
if [ -f "$JIRA_TOKEN_FILE" ] && [ -f "$JIRA_EMAIL_FILE" ]; then
  JIRA_AUTH=$(echo -n "$(cat $JIRA_EMAIL_FILE):$(cat $JIRA_TOKEN_FILE)" | base64 | tr -d '\n')
fi

# --- Load Slack webhook (if posting notifications) ---
set +x  # protect credential
SLACK_WEBHOOK_FILE="${GITHUB_APP_CREDS_DIR}/slack-webhook-url"
if [ -f "$SLACK_WEBHOOK_FILE" ]; then
  SLACK_WEBHOOK_URL=$(cat "$SLACK_WEBHOOK_FILE")
fi

# --- Query for work items ---
# ... (Jira JQL query, GitHub API, etc.)

# --- Process each work item ---
while IFS= read -r item; do
  # Phase 1: Core task
  set +e
  claude -p "{prompt or /skill:command}" \
    --allowedTools "Bash Read Write Edit Grep Glob WebFetch" \
    --max-turns 100 \
    --model "$CLAUDE_MODEL" \
    --output-format stream-json \
    2> "/tmp/claude-${ITEM_ID}-output.log" \
    | tee "/tmp/claude-${ITEM_ID}-output.json"
  EXIT_CODE=$?
  set -e

  # Extract token usage for cost tracking
  grep '"type":"result"' "/tmp/claude-${ITEM_ID}-output.json" \
    | head -1 \
    | jq '{
        total_cost_usd: (.total_cost_usd // 0),
        duration_ms: (.duration_ms // 0),
        num_turns: (.num_turns // 0),
        input_tokens: (.usage.input_tokens // 0),
        output_tokens: (.usage.output_tokens // 0),
        cache_read_input_tokens: (.usage.cache_read_input_tokens // 0),
        cache_creation_input_tokens: (.usage.cache_creation_input_tokens // 0)
      }' > "${SHARED_DIR}/claude-${ITEM_ID}-tokens.json"

  # Record state for reporting
  echo "${ITEM_ID} $(date -u +%Y-%m-%dT%H:%M:%SZ) ${STATUS}" >> "$STATE_FILE"

  # Rate limiting between items
  sleep 60
done <<< "$ITEMS"
```

Key principles for the commands script:
- Always use `set +e` around Claude invocations so a single failure doesn't abort the whole run
- Always extract token usage from `stream-json` output for cost tracking
- Use `--allowedTools` to restrict to the minimum needed tools
- Use `--output-format stream-json` for structured output parsing
- Cap turns with `--max-turns` to prevent runaway token consumption
- Record state to `${SHARED_DIR}` for the report step
- Use rate limiting (60s) between processing items
- Never expose credentials in logs (disable tracing with `set +x` around sensitive operations)
- For multi-phase pipelines, refresh GitHub App tokens between phases (they expire after 1 hour)

#### Step 2.6: Write the Report Step (Optional)

If the agent processes multiple items or the user wants HTML reporting:

Generate an HTML report from the state file and token usage JSONs. The report should include:
- Summary table (item, timestamp, status, PR URL if applicable, cost)
- Per-item detail sections with phase output and tool call summaries
- Token usage breakdown by model
- Grand totals

Write the report to `${ARTIFACT_DIR}/{agent-name}-report.html`.

Follow the pattern from the HyperShift jira-agent report step.

#### Step 2.7: Write the CI-Operator Config

Generate the ci-operator config that defines the job. This goes in the target repository's ci-operator config file (e.g., `ci-operator/config/{org}/{repo}/{org}-{repo}-{branch}.yaml`).

**For a periodic job:**
```yaml
- as: {job-name}
  steps:
    workflow: {agent-name}
  cron: "{cron-expression}"
```

**For a presubmit job:**
```yaml
- as: {job-name}
  steps:
    workflow: {agent-name}
  run_if_changed: "{file-pattern}"
  # Or for optional jobs triggered via /test:
  always_run: false
  optional: true
```

**For ad-hoc via Gangway:**
```yaml
- as: {job-name}
  steps:
    workflow: {agent-name}
  cron: "@yearly"
```

#### Step 2.8: Write Custom Skills (If Needed)

If the design identified gaps in existing ai-helpers skills, help the user write custom skills. Each skill needs:

- A `SKILL.md` file following the standard format (frontmatter with name/description, implementation steps)
- Placement in the appropriate plugin directory

If the skill is general-purpose, add it to an existing ai-helpers plugin. If it's team-specific, it can live in the target repo's `.claude/` directory.

#### Step 2.9: Write the Target Repo CLAUDE.md (If Needed)

If the agent operates on a specific repository, the repo should have a `CLAUDE.md` that helps Claude understand the codebase. This is especially important for code generation agents.

The `CLAUDE.md` should include:
- Build and test commands
- Architecture overview
- Coding conventions
- Key directories and their purposes

#### Step 2.10: Generate Prerequisites Checklist

Present the developer with a prerequisites checklist — the blanks they need to fill in. Include only the items relevant to their design:

**Always required:**
- [ ] **Vertex AI service account** — Either reuse the existing `sa-claude-openshift-ci` secret (if your use case is covered by the [existing AIA](https://docs.google.com/document/d/1bppZgkklo4ECLDJEWb6j6TEqxMeIri5XxseLiZTqwkI/edit?tab=t.0): reading public Jira, editing code, examining CI results, opening human-reviewed PRs) or request a new one:
  1. File an [AIA](https://source.redhat.com/departments/strategy_and_operations/it/it_information_security/data_privacy/data_privacy) for novel use cases
  2. Request a GCP service account via [ServiceNow](https://redhathub.service-now.com/hub?id=emp_taxonomy_topic&topic_id=0394f0b38788bed08b5bc88d0ebb35c8)
  3. Store in the [CI self-service vault](https://docs.ci.openshift.org/how-tos/adding-a-new-secret-to-ci/)
  4. Replace `YOUR_GCP_PROJECT_ID` and `YOUR_KEY_FILENAME` in the ref YAMLs

**If the agent pushes branches or creates PRs:**
- [ ] **GitHub App** — Request via [PCO DevServices](https://devservices.dpp.openshift.com/support/) with minimum permissions: Contents (R&W), Pull requests (R&W). No admin permissions.
  - Configure the app and install on the fork org (for pushing) and upstream org (for PR creation)
  - Store the app's `private-key` and `installation-id` (one per org) in your vault secret, along with a generated token for authentication
  - The commands script generates JWT tokens at runtime using RS256 signing and maintains separate tokens for fork push and upstream PR operations

**If the agent reads or writes Jira:**
- [ ] **Jira API token** — Create at https://id.atlassian.com/manage-profile/security/api-tokens
  - Store `jira-pat` (API token) and `jira-email` (associated email) in your vault secret
  - Used for Basic Auth: `base64(email:token)`

**If the agent posts Slack notifications:**
- [ ] **Slack webhook** — Create an incoming webhook for your channel
  - Store as `slack-webhook-url` in your vault secret
  - Optionally add a `gh-to-slack-ids` JSON mapping file for reviewer pings

**Vault secret setup:**
- [ ] Create a vault secret (e.g., `my-team-claude-prow`) in the [CI self-service vault](https://docs.ci.openshift.org/how-tos/adding-a-new-secret-to-ci/) with all credential keys above
- [ ] Replace `YOUR_VAULT_SECRET_NAME` in the ref YAMLs with your secret name

Include a secrets mapping table:

| Vault Key | Mount Path | Used For | Status |
|-----------|-----------|----------|--------|
| `gcp-sa-key` | `/var/run/claude-code-service-account/gcp-sa-key` | Vertex AI auth | TODO |
| `app-id` | `/var/run/claude-code-service-account/app-id` | GitHub App JWT | TODO |
| ... | ... | ... | ... |

#### Step 2.11: Review and Open PR

Commit all generated files in the `/tmp/release` clone and open a PR to `openshift/release`. Ask the user for their GitHub fork to push to, then create the PR using `gh pr create`.

Present the user with a summary of:

1. **The PR to `openshift/release`** — step registry refs, workflow, ci-operator config. Rehearsals will validate the structure even before secrets are wired up.
2. **Files for the target repo** (if any) — CLAUDE.md, custom skills
3. **Prerequisites checklist** — the blanks to fill in, which can be done while the PR is in review

Remind them:
- AI-generated PRs must have human review before merge and must not be configured to auto-merge
- AI-generated content should be marked with: `Generated with [Claude Code](https://claude.com/claude-code)`
- The agent should follow the principle of least privilege — restrict `--allowedTools` to the minimum needed
- Set `--max-turns` and step timeouts to prevent runaway execution

## Notes

- The `claude-ai-helpers` container image is built from `openshift-eng/ai-helpers` and includes all plugins, the `gh` CLI, Go, Python, and common utilities.
- The image is referenced as `from: claude-ai-helpers` in step registry refs (resolved to `ci/claude-ai-helpers:latest`).
- Vertex AI authentication uses the `global` region endpoint by default, which routes to the nearest available region.
- GitHub App tokens expire after 1 hour. For long-running agents, regenerate tokens between phases.
- All generated files are written directly in a clone of `openshift/release` and submitted as a PR.

## References

- [Autonomous AI Usage in OpenShift CI](https://docs.google.com/document/d/1s_u8gU57ALgvXFODCIzjXlEXUkIKBvt2SJEtyLhgmJI/edit?tab=t.0#heading=h.smmuwphj1oay) — Covers authentication, running Claude Code autonomously, principle of least privilege, and examples of existing agents.
- [HyperShift AI-Assisted CI Jobs](https://hypershift.pages.dev/how-to/ci/ai-assisted-ci-jobs/) — HyperShift team's documentation on their Jira agent and review agent, including setup and operational details.
