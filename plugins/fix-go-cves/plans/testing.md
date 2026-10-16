# Testing and evals

How each layer of the plugin is tested, and the gaps worth closing, in
build order.

## Layers

- **Scripts** (`scripts/`, `subagents/*.sh`) decide versions, commits,
  ignores and gates. `test/test-lib.sh` covers them with about 2,300
  hermetic checks.
- **End to end** (real builds, tests, scans and PRs) is covered by live runs
  on Submariner release branches: manual, 20 to 90 minutes each.
- **The skill** (`SKILL.md`) turns a finished run into the cause, evidence,
  action and owner for each finding. Nothing measures it.

Live-run failures feed the faster layers: a script bug gets a hermetic
regression test (as every release-0.24 bug did), and a skill-layer mistake
gets an eval case. No case is written speculatively.

## 1. Run the existing suite in CI

`make test` skips the suite on GitHub runners because they lack Go 1.26, so
none of the 2,300 checks gate a PR today. Adding `actions/setup-go` to
`.github/workflows/test.yml` closes the largest gap without new tests. It
belongs in its own PR, since `.github` needs admin approval.

## 2. Evaluate the skill layer

Release-0.24 showed the skill layer's value and its errors. It found a
default-branch backport for a license failure (lighthouse) and traced stdlib
findings to the build image. It also invented a policy boundary for
x/crypto, and asked for "team input" on two bumps when a leftover
`bin/lichen` was blocking the scan (subctl).

### Case: replay a recorded run

A case is a recorded run, not a new one: no build, scan or Docker daemon
runs, so a trial takes minutes and costs well under $1.

`workspace.sh prepare` builds the case workspace:

- The case repository at pinned commits: the run's result checked out as
  the fix branch (the result commit itself, not a PR head that may carry
  later manual commits), and the base and default branches as they were,
  for backport searches.
- Untracked files the recorded run saw, when `input.yaml` lists them: for
  subctl, a `bin/lichen` built with `GOEXPERIMENT=nodwarf5`, so its
  compiler marker matches the log.
- Remotes pointing at local bare repositories, and a `gh` shim that only
  logs its arguments. A push or PR attempt stays local and is recorded.
- A replay plugin whose `scripts/fix-all.sh` prints the recorded log,
  records each invocation and exits with the recorded code, named by
  `CLAUDE_PLUGIN_ROOT`, which `SKILL.md` already honors.
- The current `SKILL.md`, installed where each agent finds project skills
  (`.claude/skills/`, `.agents/skills/`). Agent directories go in
  `.git/info/exclude`, so they do not count as edits.

The agent gets a plain request, "Fix the CVEs in release-0.24 of this
repository", that names no command, so every agent gets the same prompt and
the case also tests that the skill is selected. Its final message is the
reply. `workspace.sh snapshot` then records the state for the checks.

### Checks

`checks.py` holds the deterministic checks and the judge prompt. Any failed
deterministic check scores the trial 0.

1. **State.** The fix branch and HEAD are unchanged, the worktree is clean,
   the bare remotes are unchanged and the `gh` log is empty. Hand edits are
   caught by outcome, whatever tools the agent used.
2. **One run.** The script ran exactly once, as `SKILL.md` requires: no
   unrequested rerun, and no answer given without running it.
3. **PR command.** If the log printed one, the reply contains a command with
   the same argv, compared with `shlex`, so quoting differences pass.
   Otherwise the reply contains none.
4. **Facts.** Binary criteria for each case, graded by a pinned judge model,
   for example "recommends backporting cdc3003, the `.lichen.yaml`
   override, from devel". Binary criteria score more clearly and stably
   than a 1-to-5 rubric.

Unit tests in the hermetic suite cover checks 1 to 3. Before any agent is
scored, the judge must pass each case's reference reply and fail its
recorded wrong reply, where one exists (the lighthouse x/crypto boundary,
the subctl "team input").

### Cases

| Case | Run | Decision |
| --- | --- | --- |
| case-001 | lighthouse: license, stdlib | Finds backport cdc3003 |
| case-002 | submariner: partial fix | Relays the PR, does not run it |
| case-003 | cloud-prepare: exit 0 | Invents no review items |
| case-004 | subctl: leftover `bin/lichen` | Recommends removal and a rerun |
| case-005 | admiral: govet failure | Finds backport 8234df0 |

Where stdlib findings remain, a case also requires naming Go 1.26.9 in the
build image. Logs are stored whole, gzipped (under 1 MB for all five), with
home paths replaced; trimming would need its own logic and could drop
evidence the agent reads.

### Runners

Both runners share the cases, `workspace.sh` and `checks.py`, so they score
a trial the same way.

**agent-eval-harness** (`eval-fix-go-cves.yaml`) is the marketplace
convention, which a maintainer asked for in the k8s-rebase review, and
reports cost, tokens and model for each case. It runs in prompt mode, so
the agent gets the plain request rather than a skill invocation, with its
`claude-code` or `codex` runner; `before_each` and `after_each` hooks call
`workspace.sh`; judges call `checks.py` through `module:`/`function:`. It
runs on the host, as the skill does in real use, so its permissions also
deny `git push` and `gh`. Build it first: it answers the review and needs
nothing new installed.

**Inspect AI with Inspect SWE** (`task.py`) runs the same cases isolated,
for comparing agents and for changes that should not touch the host.
[Inspect AI](https://inspect.aisi.org.uk/) is maintained by the UK AI
Security Institute. [Inspect SWE](https://meridianlabs-ai.github.io/inspect_swe/),
from the same core team, runs Claude Code, Codex CLI, Gemini CLI, OpenCode
and Google's Antigravity SDK agent in a container:

- Model calls go through a loopback proxy to Inspect on the host, so no API
  key or Vertex credential enters the sandbox. Anthropic on Vertex works
  (`anthropic/vertex/...`), and the agent and model are chosen separately:
  Codex can run on a Vertex Claude model.
- The sandbox has no network (`network_mode: none`), and the agent binary is
  copied in from the host.
- `workspace.sh prepare` runs at image build time, as a non-root user, which
  Claude Code needs for unattended permissions. The skill is passed with
  Inspect SWE's `skills` option rather than baked in, so a cached image
  never tests a stale `SKILL.md`.
- Epochs with an `at_least` reducer, `inspect score` to re-score saved logs
  after a judge change, and `inspect view` for transcripts are built in.

Both packages publish with PyPI Trusted Publishing and send no telemetry.
They are pre-1.0 and release often, so `evals/requirements.txt` pins them,
the harness and the agent CLIs with hashes. Keep them out of
`requirements-dev.txt` so `make test` stays light.

Considered and rejected:

- **Harbor.** The Terminal-Bench harness has the widest agent list, but its
  Claude Code integration has no Vertex support, it places agent and judge
  credentials inside the sandbox, publishes without provenance, and enables
  telemetry by default.
- **`claude plugin eval`.** It runs one agent, and its graders cannot inspect
  repository state.

### Layout

The repository lint requires opaque `case-NNN` names in a group directory,
each registered in the README:

```text
evals/
  README.md                case index
  eval-fix-go-cves.yaml    agent-eval-harness definition
  task.py                  Inspect task
  checks.py                deterministic checks and judge prompt
  workspace.sh             prepare and snapshot a case workspace
  Dockerfile               Inspect sandbox
  requirements.txt         pinned, hashed eval dependencies
  cases/replay/case-NNN/   input.yaml (repo, commits, exit code, request),
                           annotations.yaml (criteria, PR command),
                           run.log.gz, reply.md, wrong-reply.md (optional)
```

### Running

- Run three attempts per case and report the mean and whether every attempt
  passed: a skill that is right two times in three is not dependable.
- Read failing transcripts (`/eval-review` or `inspect view`) before
  changing `SKILL.md`. A failure can be the case's fault as easily as the
  skill's.
- Not in CI: it needs model credentials and spends money. Run it before
  changing `SKILL.md`, the review prompts or the default model.

### To confirm when building

- Codex discovers project skills in `.agents/skills/` in prompt mode.
- A full Inspect trial completes with the sandbox network off.
- The cost of one trial, to set the per-case budget.

## 3. Optional: live canary

Run `scripts/report.sh` weekly on one fast repository (Shipyard `devel`, on
a runner with Docker). It needs no model and fails only on `INCOMPLETE` or
`ERROR`, never on findings. It catches drift no recorded case can: Grype
schema or database changes, new Go releases, builder-image changes. Several
release-0.24 failures were drift of this kind.

## Not planned

- Evals that run the full fix, which take hours and need Docker. The canary
  and manual live runs cover end-to-end behavior.
- A with/without-skill ablation: the skill owns the script entry point, so a
  run without it measures nothing useful.
- Separate trigger evals: the plain-language request already tests that the
  skill is selected.
- An eval of the LLM verification layer: the recorded runs already settle
  it (see [Decisions](README.md#decisions)).
