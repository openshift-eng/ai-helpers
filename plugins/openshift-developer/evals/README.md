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

## jira-refine (`cases/jira-refine`)

Whether jira-refine reaches the right disposition and applies its Jira writes
correctly. Each case freezes an issue in `jira-fixture.json`, served by the
`jira-stub` MCP server (`stubs/jira_stub_mcp.py`) with the Atlassian MCP
`jira_*` tool names. Writes stay in the stub and are logged to
`output/jira-calls.jsonl` and `output/jira-state.json` for the judges.
`stubs/jira_guard.py` blocks real Jira hosts and Atlassian MCP servers, because
live issues are readable anonymously and would leak the answer. A fixture can
also block material published after its snapshot, such as a fix pull request:
`blocked_research` lists regexes, and `blocked_research_sha256` lists SHA-256
digests of lowercase tokens (PR number, fork owner, branch) so the workspace
does not reveal them. The guard blocks network calls that match either.

| Case | JIRA | Description |
|------|------|-------------|
| case-001 | OCPBUGS-99760 | Repeat run on a misdiagnosed CAPA capacity bug; expected CLOSE (Not a Bug) |
| case-002 | OCPBUGS-99759 | Misdiagnosed scale-from-zero incident; expected CLOSE with version-scoped evidence and reopening conditions |
| case-003 | OCPBUGS-132796 | CPO sends AWS Local Zone subnets to VPC endpoint create/modify; expected SOLVE with a CPO zone filter that needs no new IAM permission, 4.22.z evidence from the stack trace, and the ignition symptom kept separate |
| case-004 | OCPBUGS-129314 | Hosted CVO ignores management proxy environment after guest-proxy isolation; expected NEED_HUMAN_ANALYSIS for coordinated CVO transport and HyperShift injection changes |

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
