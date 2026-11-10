# OpenShift Developer Plugin Evals

Index of what each opaque `case-NNN` directory tests.

## preassessment (`cases/preassessment`)

End-to-end evaluation of the preassessment skill against real Jira issues and
repositories. Each case clones the target repo at a pinned commit and lets the
skill explore code to inform its planning-level decision.

| Case | JIRA | Description |
|------|------|-------------|
| case-001 | TRT-2755 | Mechanical context.Context threading is implementation-ready |
| case-002 | TRT-2688 | Assumed-context agentic infra story needs clarification |
| case-003 | TRT-2575 | Paging for test queries requires planning for API contract decisions |
| case-004 | TRT-2296 | Aggressive new-test retesting needs decomposition into independent pieces |

## address-reviews (`cases/address-reviews`)

Whether the address-reviews flow deduplicates bot replies, categorizes review
comments correctly, prioritizes, and formats replies.

| Case | Description |
|------|-------------|
| case-001 | Duplicate bot reply |
| case-002 | Duplicate — extreme |
| case-003 | Categorize — question |
| case-004 | Categorize — question (variant 2) |
| case-005 | Categorize — change request |
| case-006 | Categorize — dead code |
| case-007 | Categorize — suggestion |
| case-008 | Categorize — action instruction |
| case-009 | Prioritize — mixed |
| case-010 | Filter — CodeRabbit comment kept |
| case-011 | Reply format |
| case-012 | CI push override |
| case-013 | Response — question, no change |
| case-014 | Response — imperative change |

## address-ci-failures (`cases/address-ci-failures`)

Whether the address-ci-failures skill correctly classifies CI failures and
decides fix vs report per TRT-2831 guardrails.

| Case | Description |
|------|-------------|
| case-001 | Pre-existing npm audit CVE on unchanged deps (TRT-2831 canonical) |
| case-002 | PR-caused unit test failure in modified file |
| case-003 | Infrastructure failure (pod_pending) |
| case-004 | Optional job — do not fix without slam-dunk PR-caused evidence |

## solve (`cases/solve`)

Direct end-to-end evaluation of the jira-solve orchestrator against the
immutable commit immediately before a known-good PR. The eval initializes the
case workspace as the target repository and lets jira-solve select its own
skill chain.

| Case | JIRA | Description |
|------|------|-------------|
| case-001 | OCPBUGS-34662 | HyperShift jira-solve pipeline (known-good PR #7538) |
| case-002 | OCPBUGS-120802 | Preserve webhook certificates on transient API errors (PR #9507) |
| case-003 | OCPBUGS-119976 | Include unavailable components in KAS load-balancer status (PR #9502) |
| case-004 | OCPBUGS-100141 | Propagate proxy configuration to AWS cloud-controller-manager (PR #9156) |
| case-005 | OCPBUGS-85182 | Remove obsolete MutatingAdmissionPolicy runtime configuration (PR #9350) |

## pr-risk-assessment (`cases/pr-risk-assessment`)

Whether pr-risk-assessment assigns the verified risk tier to real HyperShift
pull requests, and reads the repository's AGENTS.md. Each case
freezes in `input.json` the evidence chai-bot's `prepare_pr_risk_assessment`
tool hands the skill (title, description, changed files with patches;
vendored and generated patches omitted; a 300,000-character patch budget),
made with `scripts/snapshot_pr_evidence.py`. Labels, comments, and authors are
left out and people's names removed, because the live pull requests carry
their tier labels.

| Case | PR | Expected | Description |
|------|----|----------|-------------|
| case-001 | openshift/hypershift#9958 | Critical | GCP default ingress: DNS record cleanup and new credentials for existing clusters |
| case-002 | openshift/hypershift#9818 | Critical | NodePool rollout hashes and token secrets, for every NodePool at HO upgrade |
| case-003 | openshift/hypershift#10213 | Moderate | Karpenter finalizer removal during deletion when AWS credentials are invalid |
| case-004 | openshift/hypershift#10224 | Critical | Default guest capabilities, which the HCCO reconciles into existing guests |
| case-005 | openshift/hypershift#8656 | Critical (Moderate also accepted) | Deterministic mirror order in a control plane environment variable the HO renders for every hosted cluster with registry overrides |
| case-006 | openshift/hypershift#10223 | Low | CI workflow and documentation only |

The subject and LLM judges run on Claude Code with `claude-opus-5-5`. The run
may read the repository at `base_sha` to trace callers, and nothing else of
the pull request. `stubs/pr_evidence_guard.py` holds that policy once. Staged
next to `input.json`, it is the `PreToolUse` hook in `runner.settings`: it
blocks reads of pull requests, issues, searches, and this directory, and reads
of the repository at any other commit or branch (a partial clone fetches a
named commit on demand, so any other full SHA is blocked too). Imported from
the repository root, it is the `pull_request_not_read` judge: it applies the
policy again to every call the hook let through and fails a run whose tool
output carries a `chai-risk-assessment/` label or this eval's answers, however
the read was spelled. `agents_md_read` passes when a tool output holds the
case's `agents_md_marker`, a line only the root `AGENTS.md` has.
`python3 plugins/openshift-developer/evals/stubs/test_pr_evidence_guard.py`
tests the policy. From the repository root:

```text
/eval-run --config plugins/openshift-developer/evals/eval-pr-risk-assessment.yaml --model claude-opus-5-5
```

To add a case, freeze the evidence with
`python3 plugins/openshift-developer/evals/scripts/snapshot_pr_evidence.py <PR_URL> <case-dir>`,
remove people's names from the description, and write `annotations.yaml` with
the verified tier, the reasoning behind it, and an `agents_md_marker` line
from the root `AGENTS.md` at the case's `base_sha`.

## jira-refine (`cases/jira-refine`)

Whether jira-refine reaches the right disposition and applies its Jira writes
correctly. Each case freezes an issue in `jira-fixture.json`, served by the
`jira-stub` MCP server (`stubs/jira_stub_mcp.py`) with the Atlassian MCP
`jira_*` tool names. Writes stay in the stub and are logged to
`output/jira-calls.jsonl` and `output/jira-state.json` for the judges.
`stubs/jira_guard.py` blocks real Jira hosts and Atlassian MCP servers, because
live issues are readable anonymously and would leak the answer.

| Case | JIRA | Description |
|------|------|-------------|
| case-001 | OCPBUGS-99760 | Repeat run on a misdiagnosed CAPA capacity bug; expected CLOSE (Not a Bug) |
| case-002 | OCPBUGS-99759 | Misdiagnosed scale-from-zero incident; expected CLOSE with version-scoped evidence and reopening conditions |

The default subject and LLM judges use the harness's native `codex` runner
with `gpt-6.1-sol` and `high` reasoning. The harness stages the plugin skills
and invokes `codex exec`; no custom model loop is needed.

Install Codex CLI with MCP and PreToolUse hook support, authenticate it for
Sol 6.1, and install Agent Eval Harness. The evaluated harness revision is
`1a980e7`. From the repository root, use its `eval-run` workflow:

```text
/eval-run --config plugins/openshift-developer/evals/eval-jira-refine.yaml --model gpt-6.1-sol --effort high
```

`runner.settings` registers the workspace-local Jira stub as a required stdio
MCP server and enables the Jira guard as a native `PreToolUse` hook. Subject
runs fail at startup if the stub cannot initialize. Guard
results are recorded in `output/jira-guard-events.jsonl`. Research shell
commands exclude OpenAI API credentials, and hosted web search is disabled so
research goes through the guarded shell. Prompt-only judges use native Codex
through `models.judge: runner:/gpt-6.1-sol`.

For the scoring step, use `eval-jira-refine-judges.yaml` as the config passed
to the harness's `score.py judges` command. It inherits the same cases and
judges, but disables skill staging, the Jira stub, and hooks for prompt-only
judges, whose temporary workspaces contain no Jira fixture. Keep
`eval-jira-refine.yaml` for subject execution so the stub remains mandatory.

Codex requires non-managed hooks to be reviewed and trusted before they run.
Review the configured guard using `/hooks` before an unattended evaluation;
a skipped guard does not provide an isolated Jira evaluation. See the
[Codex hooks documentation](https://learn.chatgpt.com/docs/hooks) for hook
trust and the [MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
for stdio configuration.
