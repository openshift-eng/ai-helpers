# Testing and evals

How each layer of the plugin is tested, and the gaps worth closing, most
valuable first.

## Layers

- **Scripts** (`scripts/`, `subagents/*.sh`) decide versions, commits,
  ignores and gates. `test/test-lib.sh` covers them with about 2,300
  hermetic checks.
- **End to end** (real builds, tests, scans and PRs) is covered by live runs
  on Submariner release branches: manual, 20 to 90 minutes each.
- **The skill** (`SKILL.md`) turns a finished run into the cause, evidence,
  action and owner for each finding. Nothing measures it.

Failures found in live runs feed back into the faster layers. A script bug
gets a hermetic regression test (as for every release-0.24 bug), and a
skill-layer mistake gets an eval case. No case is written speculatively.

## 1. Run the existing suite in CI

`make test` skips the suite on GitHub runners because they lack Go 1.26, so
none of the 2,300 checks gate a PR today. Adding `actions/setup-go` to
`.github/workflows/test.yml` closes the largest gap without new tests.

## 2. Evaluate the skill layer

The skill layer is where release-0.24 showed both value and errors. It found
a default-branch backport for a license failure (lighthouse) and traced
stdlib findings to the build image. It also invented a policy boundary for
x/crypto, and asked for "team input" on two bumps when a leftover
`bin/lichen` was blocking the scan (subctl).

### Tooling: one case set, two runners

The cases, the workspace setup (`prepare.sh`) and the deterministic checks
(`checks.py`) are shared. Each runner is a thin definition over them, so the
two always score a trial the same way.

**agent-eval-harness** (`eval-fix-go-cves.yaml`) follows the marketplace
convention, which a maintainer asked for in the k8s-rebase review. It
reports cost, tokens and model for each case. A `cli` runner calls
`prepare.sh` and then the agent (Claude Code or Codex). Its judges call
`checks.py` through `module:`/`function:`, plus one LLM judge for the facts.
It runs on the host, so its permissions deny `git push` and `gh`, and every
remote in the workspace is a local bare repository; even an allowed push
stays local.

**Inspect AI with Inspect SWE** (`task.py`) runs the same cases isolated.
[Inspect AI](https://inspect.aisi.org.uk/) is maintained by the UK AI
Security Institute, and [Inspect SWE](https://meridianlabs-ai.github.io/inspect_swe/),
from the same core team, runs real agents (Claude Code, Codex CLI, Gemini
CLI, OpenCode and Google's Antigravity SDK agent) in a sandbox. Use it to
compare agents and to try changes without host access:

- **Credentials stay on the host.** The agent runs in a container and talks
  to a loopback proxy that relays its model calls to Inspect; Claude Code
  gets only a placeholder token. No API key or Vertex credential enters the
  sandbox. Any Inspect provider works, including
  Anthropic on Vertex (`anthropic/vertex/...`). The proxy also withholds
  provider-side tools such as web search by default.
- **No network.** Inspect sandboxes default to `network_mode: none`, and
  Inspect SWE copies the agent binary in from the host. The agent cannot
  push, open a PR or fetch anything, whatever it tries.
- **Supply chain.** Both packages are published to PyPI with Trusted
  Publishing provenance and have no telemetry. Both are pre-1.0 and release
  often, so pin them and the agent CLI versions with hashes in
  `evals/requirements.txt`, and upgrade deliberately. Keep them out of
  `requirements-dev.txt` so `make test` stays light.
- **Built-in scoring.** Epochs with an `at_least` reducer, re-scoring of
  saved logs with `inspect score` (no agent rerun after a judge change), and
  a transcript viewer (`inspect view`).

Considered and rejected:

- **Harbor.** The Terminal-Bench harness has the widest agent list, but its
  Claude Code integration has no Vertex support, it places agent and judge
  credentials inside the sandbox, publishes without provenance, and enables
  telemetry by default.
- **`claude plugin eval`.** It runs one agent, and its graders cannot inspect
  repository state.

### Sample: replay a recorded run

A sample is a recorded run, not a new one. It needs no build, scan or Docker
daemon inside the sandbox, so a trial takes minutes and costs well under $1.

- **Workspace.** `prepare.sh` builds it from the case's pinned commits:
  in the case workspace for agent-eval-harness, and at image build time for
  Inspect. The run's result is checked out as the fix branch, and
  the base and default branches are kept as they were, for backport
  searches. Pin the result commit itself, not the PR head, which can carry
  later manual commits. Remotes point at local bare repositories and a `gh`
  shim only logs its arguments. The Inspect image runs as a non-root user,
  which Claude Code requires for unattended permissions.
- **Agent.** An Inspect SWE agent with the real skill passed through its
  `skills` option. Its `env` option sets `CLAUDE_PLUGIN_ROOT`, which
  `SKILL.md` already honors, to a plugin copy whose `scripts/fix-all.sh`
  replays the recorded log, records each invocation, and exits with the
  recorded code. Inspect SWE installs skills and agent configuration under
  the working directory (`.claude/`, `.codex/`), so the image lists those in
  `.git/info/exclude` to keep the state check meaningful.
- **Input.** A plain request, "Fix the CVEs in release-0.24 of this
  repository", that names no command. Every agent gets the same prompt, and
  the case also tests that the skill is selected. The agent's final message
  is the reply; nothing extra is asked of it.

### Scorers

Scorers run on the host, after the agent. The deterministic ones gate the
result: if any fails, the sample scores 0.

1. **State.** Read in the sandbox: the fix branch and HEAD are unchanged,
   the worktree is clean, the bare remotes are unchanged and the `gh` log is
   empty. Hand edits are caught by outcome, whatever tools the agent used.
2. **One run.** The script ran exactly once, as `SKILL.md` requires: no
   unrequested rerun, and no answer given without running it.
3. **PR command.** If the log printed one, the reply contains a command with
   the same argv, compared with `shlex`, so quoting differences pass.
   Otherwise the reply contains none.
4. **Facts.** Binary criteria for each case, graded by a pinned judge model,
   for example "recommends backporting cdc3003, the `.lichen.yaml`
   override, from devel". Binary criteria give clearer and more stable
   scores than a 1-to-5 rubric.

Two stand-in solvers check the scorers before any agent is scored:

- `oracle` replies with the reference reply and must score 1, which proves
  every criterion can be satisfied.
- `wrong` replies with the case's recorded wrong reply, where one exists
  (the lighthouse x/crypto boundary, the subctl "team input"), and must
  score 0.

### Cases

Each case comes from a release-0.24 run and tests one decision:

| Case | Run | Decision |
| --- | --- | --- |
| case-001 | lighthouse: license, stdlib | Finds backport cdc3003 |
| case-002 | submariner: partial fix | Relays the PR, does not run it |
| case-003 | cloud-prepare: exit 0 | Invents no review items |
| case-004 | subctl: leftover `bin/lichen` | Recommends removal and a rerun |
| case-005 | admiral: govet failure | Finds backport 8234df0 |

Every case where stdlib findings remain also requires naming Go 1.26.9 in
the build image. Logs are stored whole, gzipped (under 1 MB for all five),
with home paths replaced: trimming would need its own logic and could drop
evidence the agent reads.

### Layout

The repository lint requires opaque `case-NNN` names in a group directory,
each registered in the README:

```text
evals/
  README.md                case index
  eval-fix-go-cves.yaml    agent-eval-harness definition
  task.py                  Inspect task
  checks.py                shared deterministic checks and judge prompt
  prepare.sh               builds a case workspace (both runners)
  Dockerfile               Inspect sandbox; runs prepare.sh at build time
  requirements.txt         pinned, hashed Inspect AI and Inspect SWE
  cases/replay/case-NNN/   input.yaml (repo, commits, exit code, request),
                           annotations.yaml (criteria, PR command),
                           run.log.gz, reply.md, wrong-reply.md (optional)
```

`checks.py` gets unit tests in the hermetic suite, so `make test` covers
the grader too.

### Running

- `make eval runner=harness|inspect agent=... model=... case=NNN` runs
  three attempts. Report the mean and whether every attempt passed,
  because a skill that is right two times in three is not dependable. The
  harness run adds cost and tokens per case.
- Under Inspect, the `oracle` and `wrong` checks run first. The agent
  scaffold and the model are independent there, so Codex can be scored on a
  Vertex Claude model without an OpenAI key.
- Read failing transcripts (the harness's `/eval-review`, or
  `inspect view`) before changing `SKILL.md`. A failure can be the case's
  fault as easily as the skill's.
- Not in CI: it needs model credentials and spends money. Run it before
  changing `SKILL.md`, the review prompts or the default model.

### Optional case: the LLM verification layer

Replay the same evidence through the LLM verification layer. If its
verdicts never change an outcome that the deterministic evidence has not
already decided, that settles the decision in the
[plans index](README.md#decisions) to drop the layer.

## 3. Optional: live canary

Run `scripts/report.sh` weekly on one fast repository (Shipyard `devel`, on
a runner with Docker). It needs no model and fails only on `INCOMPLETE` or
`ERROR`, never on findings. It catches drift that no recorded case can:
Grype schema or database changes, new Go releases, builder-image changes.
Several release-0.24 failures were drift of this kind.

## Not planned

- Evals that run the full fix, which take hours and need Docker. The canary
  and manual live runs cover end-to-end behavior.
- A with/without-skill ablation: the skill owns the script entry point, so a
  run without it measures nothing useful.
- Separate trigger evals: the plain-language input already tests that the
  skill is selected.
