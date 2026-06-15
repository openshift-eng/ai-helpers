# docs-tools

!!! tip

    Always run Claude Code from a terminal in the root of the documentation repository you are working on. The docs-tools commands and agents operate on the current working directory, they read local files, check git branches, and write output relative to the repo root.

## Prerequisites

- Install the [Red Hat Docs Agent Tools marketplace](https://aireilly.gitlab.cee.redhat.com/redhat-docs-agent-tools/install/)

- Install [software dependencies](https://aireilly.gitlab.cee.redhat.com/redhat-docs-agent-tools/install/#software-dependencies)

- Create an `.env` file with your tokens. You can use either location:

    - **`~/.env`** — global defaults, shared across all projects
    - **`.env`** in the project root — project-specific overrides (takes precedence over `~/.env`)

    ```bash
    JIRA_API_TOKEN=your_jira_api_token
    # JIRA_AUTH_TOKEN is also accepted as a backward-compatible alias
    # Required for Atlassian Cloud authentication
    JIRA_EMAIL=you@redhat.com
    # Optional: defaults to https://redhat.atlassian.net if not set
    JIRA_URL=https://redhat.atlassian.net
    # Required scopes: "repo" for private repos, "public_repo" for public repos
    GITHUB_TOKEN=your_github_pat
    # Required scope: "api"
    GITLAB_TOKEN=your_gitlab_pat
    ```

    All scripts load both files automatically (global first, then local overrides). You can also add the following to `~/.bashrc` (Linux) or `~/.zshrc` (macOS) to export them into your shell:
    
    ```bash
    if [ -f ~/.env ]; then
        set -a
        source ~/.env
        set +a
    fi
    ```

    Restart your terminal and Claude Code for changes to take effect.

## Customizing the docs workflow

The docs orchestrator (`/docs-orchestrator`) runs a YAML-defined step list. You can customize it per-repo without modifying the plugin.

### Override the workflow steps

The orchestrator looks for workflow YAML in this order:

1. `.agent_workspace/docs-<name>.yaml` — if `--workflow <name>` is passed
2. Matching plugin default — `skills/docs-orchestrator/defaults/docs-<name>.yaml` if that project-level file is absent
3. `.agent_workspace/docs-workflow.yaml` — project-level default (when no `--workflow` is specified)
4. Plugin default — `skills/docs-orchestrator/defaults/docs-workflow.yaml`

To customize, download the default into your docs repo and edit it:

```bash
mkdir -p .agent_workspace
curl -sL https://gitlab.cee.redhat.com/aireilly/redhat-docs-agent-tools/-/raw/main/plugins/docs-tools/skills/docs-orchestrator/defaults/docs-workflow.yaml \
   -o .agent_workspace/docs-workflow.yaml
```

Then modify `.agent_workspace/docs-workflow.yaml` to add, remove, or reorder steps:

```yaml
workflow:
  name: docs-workflow
  steps:
    - name: requirements
      skill: docs-workflow-requirements
      description: Analyze documentation requirements

    - name: planning
      skill: docs-workflow-planning
      inputs: [requirements]

    # Add a custom step using a local skill
    - name: sme-review
      skill: my-review-skill
      description: Domain-specific review by SME checklist
      inputs: [writing]

    # Remove or skip steps by deleting them from the list
```

### Supplement with local skills

You can reference local standalone skills (from `.claude/skills/`) alongside plugin skills in your workflow YAML. Create a local skill in your docs repo:

```
.claude/skills/my-review-skill/SKILL.md
```

Then reference it by its standalone name in the step list:

```yaml
- name: sme-review
  skill: my-review-skill
  description: Run team-specific review checklist
  inputs: [writing]
```

Local standalone skills use short names (e.g., `my-review-skill`), while plugin skills use fully qualified names (e.g., `docs-workflow-writing`). Both can coexist in the same workflow YAML.

### Conditional steps

Use the `when` field to make steps run only when a CLI flag is passed:

```yaml
- name: create-merge-request
  skill: docs-tools:docs-workflow-create-merge-request
  when: create_merge_request
  inputs: [writing, style-review, technical-review]
```

This step only runs when `--create-merge-request` is passed to the orchestrator.

### Multiple workflow variants

Use `--workflow <name>` to maintain different workflows for different purposes:

```bash
# Uses .agent_workspace/docs-quick.yaml
/docs-orchestrator PROJ-123 --workflow quick

# Uses .agent_workspace/docs-full.yaml
/docs-orchestrator PROJ-123 --workflow full
```

### Merge request creation

The default workflow includes a **create-merge-request** step that is off by default. Pass `--create-merge-request` to activate it. When enabled, the step creates a feature branch (if needed), commits the written files, pushes to the remote, and opens a merge request (GitLab) or pull request (GitHub).

```bash
/docs-orchestrator PROJ-123 --create-merge-request
```

Without the flag, the workflow ends at style-review and leaves the files as uncommitted changes in the repo, so you can create your own branch and MR manually.

### Code-analysis workflow

The `workflow-code-analysis` variant adds code-learner analysis steps to the standard pipeline: **code-analysis** (runs learn-code to produce structured analysis of the source repository — module registry, per-module summaries, cross-module relationships) and optionally **pr-analysis** (analyzes PR changes against the module registry). This workflow requires a source code repository — the orchestrator fails at load time if neither `--source-code-repo` nor `--pr` is provided.

```bash
/docs-orchestrator PROJ-123 \
  --workflow workflow-code-analysis \
  --source-code-repo https://github.com/org/operator
```

### Multi-repo evidence retrieval

1. **requirements** — analyze documentation requirements from the JIRA ticket
2. **code-analysis** — run learn-code to produce ONBOARDING.md, module registry, per-module summaries, and cross-module relationship data
3. **pr-analysis** _(conditional, runs when a PR URL is available)_ — analyze PR changes against the module registry
4. **planning** — create the documentation plan, scoping modules based on onboarding priority (read-first, read-second, skip)
5. **writing** — write documentation grounded in the code-learner analysis
6. **technical-review** — verify technical accuracy with claim validation against code-learner analysis
7. **style-review** — check style guide compliance
8. **create-merge-request** _(optional, pass `--create-merge-request` to enable)_ — create a branch (if needed), commit, push, and open a merge request or pull request

Compared to the default workflow, the code-analysis variant produces documentation with fewer technical review issues because the writer has structured code understanding (module APIs, data flows, dependencies) to work from, rather than generating from the JIRA description alone.

Maximum 3 secondary repos per run (configurable with `--max-secondary-repos`). Repos are ranked by the number of associated requirements.

```bash
# Auto-discover secondary repos without prompting (CI mode)
/docs-orchestrator PROJ-123 --auto-discover-repos

# Limit to 2 secondary repos with custom weight
/docs-orchestrator PROJ-123 --max-secondary-repos 2 --secondary-weight 0.7
```

## Starting a docs workflow

The easiest way to start a documentation workflow is with `/docs-workflow-start`. This skill provides a guided, interactive experience that builds the right orchestrator command for you — no need to remember CLI flags.

### Why docs-workflow-start exists

The docs orchestrator (`/docs-orchestrator`) is powerful but has many flags: `--repo`, `--pr`, `--mkdocs`, `--create-jira`, `--workflow`, and more. For users who run workflows interactively in Claude Code, remembering the right combination of flags for each situation is unnecessary friction. `/docs-workflow-start` solves this by asking a short series of questions and assembling the orchestrator invocation automatically.

### Basic usage

Invoke the skill from the Claude Code prompt with a JIRA ticket ID:

```bash
/docs-workflow-start PROJ-123
```

If you already know the flags you want, pass them directly and the skill skips the questionnaire entirely:

```bash
/docs-workflow-start PROJ-123 --repo https://github.com/org/repo --mkdocs
```

When invoked without flags, the skill walks you through five steps:

1. **Ticket ID** — confirms or asks for the JIRA ticket
2. **Action** — full workflow, specific steps, or resume a previous run
3. **Configuration** — output format (AsciiDoc or MkDocs), source code repo, file placement, JIRA ticket creation
4. **Additional context** — PR URLs, repo paths, or other details
5. **Execute** — assembles the CLI flags and hands off to `docs-orchestrator`

### Running specific steps

When you choose "specific steps" in step 2, the skill shows you the available workflow steps and lets you pick which ones to run. It automatically resolves dependencies — if you choose `writing`, the skill detects that `requirements` and `planning` are prerequisites and includes them. If those prerequisites have already been completed in a previous run, it offers to reuse the existing artifacts or re-run them.

### When to use docs-workflow-start vs. docs-orchestrator

| Scenario | Use |
|----------|-----|
| Interactive session, unsure which flags to use | `/docs-workflow-start` |
| Running a single step with its prerequisites | `/docs-workflow-start` (specific steps mode) |
| CI/CD pipelines or scripted automation | `/docs-orchestrator` directly |
| You already know the exact flags | Either — `/docs-workflow-start` passes through to the orchestrator when flags are provided |

## Using the docs orchestrator locally

Run the docs orchestrator from a Claude Code command prompt in the root of your documentation repository or from the chat panel in Agent mode in Cursor. The orchestrator reads a JIRA ticket, analyzes requirements, plans the documentation structure, writes modules, and runs technical and style reviews.

### Basic usage

To write files directly into your repo (update-in-place mode), run as follows:

```bash
/docs-orchestrator PROJ-123
```

In update-in-place mode, the orchestrator detects your repo's documentation framework (Antora, ccutil, etc.) and writes files to the correct locations as uncommitted changes. To also create a branch, commit, push, and open a merge request, add `--create-merge-request`.

### Grounding documentation in source code

When documenting a feature that lives in a source code repository, pass `--repo` to provide the code repository. The orchestrator clones the repo, runs code-learner analysis (tree-sitter AST parsing + fan-out agents), and produces structured understanding of the codebase — module registry, per-module summaries, cross-module relationships, and an ONBOARDING.md guide. The writer then uses this analysis to ground its output in actual module APIs, data flows, and dependencies — rather than generating from the JIRA description alone.

```bash
/docs-orchestrator PROJ-123 --repo https://github.com/org/repo
```

The code-analysis step runs automatically when `--repo` is provided. It:

1. Clones the repository (or uses it if it's a local path)
2. Detects modules using tree-sitter AST parsing and language-specific heuristics
3. Builds a module registry with onboarding priorities (read-first, read-second, skip)
4. Runs per-module deep analysis agents in parallel
5. Analyzes cross-module relationships
6. Produces `ONBOARDING.md`, `registry.json`, per-module summaries, and relationship data

Without `--repo`, the code-analysis step is skipped and the writer works from the JIRA ticket and documentation plan only.

!!! tip

    Code analysis is most effective when the JIRA ticket has a detailed description. A well-described ticket combined with structured code analysis produces documentation with significantly fewer technical review issues.

### Including PR context

If the feature has associated pull requests, pass their URLs to include the code changes in the requirements analysis:

```bash
/docs-orchestrator PROJ-123 --pr https://github.com/org/repo/pull/456
```

Multiple `--pr` flags can be passed. The requirements analyst will read the PR diff, comments, and description alongside the JIRA ticket.

### Other options

| Flag | Description |
|------|-------------|
| `--repo <url-or-path>` | Source code repository for code-learner analysis |
| `--pr <url>` | PR/MR URL to include in requirements analysis (repeatable) |
| `--no-source-repo` | Skip source resolution and all source-dependent steps |
| `--auto-discover-repos` | Skip confirmation when secondary repos are discovered |
| `--max-secondary-repos <N>` | Maximum secondary repos to clone (default: 3) |
| `--secondary-weight <float>` | Relevance multiplier for secondary repo results (default: 0.8) |
| `--mkdocs` | Generate Material for MkDocs Markdown instead of AsciiDoc |
| `--repo-path <path>` | Write files to a specific repo path (e.g., an external clone) |
| `--create-jira <PROJECT>` | Create a linked JIRA ticket in the specified project |
| `--workflow <name>` | Use `.agent_workspace/docs-<name>.yaml` instead of the default workflow |

### Resuming a workflow

The orchestrator saves progress to `.agent_workspace/<ticket>/workflow/<workflow-type>_<ticket>.json`. If a run is interrupted or fails, start the orchestrator again with the same ticket and workflow and it will resume from where it left off:

```bash
/docs-orchestrator PROJ-123
```

Completed steps are skipped automatically. You can add flags on resume (e.g., add `--create-jira` to a run that didn't originally include it).

## Using the docs orchestrator in CI/CD

The docs orchestrator can run in GitHub Actions or GitLab CI using [Claude Code in the CLI](https://code.claude.com/docs/en/cli-reference). This lets you automate documentation workflows — for example, generating draft docs from a JIRA ticket when a PR is opened, or running style and technical reviews on documentation changes.

### Prerequisites

Your CI environment needs:

- **Claude Code** installed (`npm install -g @anthropic-ai/claude-code`)
- **API key** set as `ANTHROPIC_API_KEY` secret
- **JIRA token** set as `JIRA_API_TOKEN` secret (and `JIRA_EMAIL` for Atlassian Cloud)
- **Python 3** with required packages (see [Prerequisites](#prerequisites))
- The docs-tools plugin installed or available in the runner

### How it works

The CI pattern has two phases:

1. **Phase 1 — JIRA ready check**: The `docs-workflow-jira-ready` skill queries JIRA for tickets matching a JQL filter, excludes tickets that already have a workflow progress file or tracking label, and returns a JSON list of actionable ticket IDs.
2. **Phase 2 — Orchestrator loop**: For each ready ticket, run the `docs-orchestrator` skill to execute the full documentation workflow.

All invocations go through `claude -p` (headless mode) so the plugin system resolves script paths via `CLAUDE_PLUGIN_ROOT`. No local checkout of the tools repo is needed — only the plugin installed in Claude Code.

### GitHub Actions example

```yaml
name: Docs Workflow
on:
  schedule:
    - cron: '0 8 * * 1-5'  # Weekdays at 8am
  workflow_dispatch: {}

env:
  DOCS_JQL: "project=PROJ AND labels=docs-needed AND labels != docs-workflow-started"

jobs:
  check:
    runs-on: ubuntu-latest
    outputs:
      tickets: ${{ steps.check.outputs.tickets }}
    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: |
          npm install -g @anthropic-ai/claude-code
          python3 -m pip install PyGithub python-gitlab jira pyyaml ratelimit requests beautifulsoup4 html2text

      - name: Check for ready tickets
        id: check
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          JIRA_API_TOKEN: ${{ secrets.JIRA_API_TOKEN }}
          JIRA_EMAIL: ${{ secrets.JIRA_EMAIL }}
        run: |
          RESULT=$(claude -p "Skill: docs-workflow-jira-ready, args: \"--jql '${{ env.DOCS_JQL }}' --add-label\"")
          echo "tickets=$(echo "$RESULT" | jq -c '.ready')" >> "$GITHUB_OUTPUT"

  run-workflow:
    needs: check
    if: needs.check.outputs.tickets != '[]'
    runs-on: ubuntu-latest
    strategy:
      matrix:
        ticket: ${{ fromJson(needs.check.outputs.tickets) }}
      max-parallel: 2
    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: |
          npm install -g @anthropic-ai/claude-code
          python3 -m pip install python-pptx PyGithub python-gitlab jira pyyaml ratelimit requests beautifulsoup4 html2text

      - name: Run docs orchestrator
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          JIRA_API_TOKEN: ${{ secrets.JIRA_API_TOKEN }}
          JIRA_EMAIL: ${{ secrets.JIRA_EMAIL }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          claude -p "Skill: docs-orchestrator, args: \"${{ matrix.ticket }} --draft\""

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: docs-${{ matrix.ticket }}
          path: artifacts/
```

This uses a matrix strategy to parallelize orchestrator runs across tickets. The `check` job queries JIRA and passes ready ticket IDs to `run-workflow` via `fromJson`.

### GitLab CI example

```yaml
docs-check-tickets:
  stage: docs
  image: node:20
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
    - when: manual
  before_script:
    - npm install -g @anthropic-ai/claude-code
    - apt-get update && apt-get install -y python3 python3-pip jq
    - python3 -m pip install PyGithub python-gitlab jira pyyaml ratelimit requests beautifulsoup4 html2text
  script:
    - |
      RESULT=$(claude -p "Skill: docs-workflow-jira-ready, args: \"--jql 'project=PROJ AND labels=docs-needed' --add-label\"")
      TICKETS=$(echo "$RESULT" | jq -r '.ready[]' 2>/dev/null || true)
      if [ -z "$TICKETS" ]; then
        echo "No tickets ready for docs workflow."
        exit 0
      fi
      for TICKET in $TICKETS; do
        echo "=== Starting workflow for $TICKET ==="
        claude -p "Skill: docs-orchestrator, args: \"$TICKET --draft\"" \
          2>&1 | tee -a .work/cron-runs/$(date +%Y%m%d-%H%M%S)-${TICKET}.log
      done
  artifacts:
    paths:
      - artifacts/
      - .work/cron-runs/
    expire_in: 1 week
```

Set `ANTHROPIC_API_KEY`, `JIRA_API_TOKEN`, `JIRA_EMAIL`, and any Git platform tokens as CI/CD variables (masked/protected).

### Tips for CI usage

- Use `--draft` to write output to `artifacts/` staging area instead of modifying repo files directly
- Use `--add-label` in the JIRA ready check to prevent re-processing tickets on the next run
- Use `--workflow` to select a CI-specific workflow variant (e.g., a lighter review-only pipeline)
- Collect the `artifacts/` directory as an artifact for downstream review or PR creation
- The orchestrator writes a progress JSON file, so failed runs can be resumed in a subsequent job if the artifact is restored
- For PR-triggered workflows, pass `--pr $CI_MERGE_REQUEST_URL` or `--pr $GITHUB_PR_URL` to include the PR context in requirements analysis
