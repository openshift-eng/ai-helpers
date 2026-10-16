# Testing and evals

How each layer of the plugin is tested, and the gaps worth closing, in
build order.

## Layers

- **Scripts** (`scripts/`, `subagents/*.sh`) decide versions, commits,
  ignores and gates. `test/test-lib.sh` covers them with about 2,300
  hermetic checks.
- **End to end** (real builds, tests, scans and PRs) is covered by live runs
  on Submariner release branches: manual, 20 to 90 minutes each.
- **The LLM layers** decide what the scripts cannot: `review.sh` settles
  open packages, and the skill (`SKILL.md`) turns a finished run into the
  cause, evidence, action and owner for each finding. Nothing measures
  them.

Live-run failures feed the faster layers: a script bug gets a hermetic
regression test (as every release-0.24 bug did), and an LLM-layer mistake
gets an eval case. No case is written speculatively.

## 1. Run the existing suite in CI

`make test` already runs every plugin's `test_*.py`, this suite included.
It skipped only because its wrapper demanded Go 1.26. The suite passes on
Go 1.24 (1.22 fails four packed-binary checks), so the floor is now 1.24,
and GitHub's `ubuntu-24.04` runners already put Go 1.24 on `PATH`. The
suite therefore runs in the existing Test job with no workflow change.

That has a cost: the suite takes about 3 minutes locally, and the whole
Test job takes under 1 minute today. So the wrapper must skip in a pull
request that does not touch `plugins/fix-go-cves/`, and that skip has to
land in the same PR as the lower floor. It fetches the base commit named in
`$GITHUB_EVENT_PATH` (the checkout is shallow) and diffs against it; pushes
to main always run the suite.

If maintainers prefer scoping in CI configuration, the repository's own
pattern is a Prow job with `run_if_changed: ^plugins/fix-go-cves/` in
openshift/release. Adding `setup-go` to `.github/workflows/test.yml` is not
needed.

## 2. Evaluate the LLM layers

Two LLM steps sit on top of the scripts. `review.sh` asks a model to decide
packages the scripts left open, and its verdicts land in the run log. The
skill then reads that log and reports cause, evidence, action and owner.
Release-0.24 showed both at work. The skill found a default-branch backport
for a license failure (lighthouse) and traced stdlib findings to the build
image. `review.sh` invented a policy boundary for x/crypto and sent three
subctl bumps to "team input" when a leftover `bin/lichen` had blocked the
scan, and the skill relayed both instead of checking them.

So two case groups share one design: `replay` cases test the skill on a
recorded log, and `review` cases test `review.sh` on recorded inputs.
`SKILL.md` asks the skill to investigate each flagged line, so a replay
case may require it to reject a `review.sh` verdict that the evidence
contradicts.

### Case: replay a recorded run

A case is a recorded run, not a new one: no build, scan or Docker daemon
runs, so a trial takes minutes and costs well under $1.

`workspace.sh prepare` builds the case workspace as the run found it:

- The case repository at pinned base and default-branch commits, checked
  out on the branch the run started from. The default branch serves
  backport searches.
- Untracked files the recorded run saw, listed in `input.yaml`, with
  timestamps from before the log starts: for subctl, a `bin/lichen` built
  with `GOTOOLCHAIN=go1.26.8 GOEXPERIMENT=nodwarf5` at the lichen version
  `input.yaml` names, so its compiler marker (`go1.26.8-X:nodwarf5`) matches
  the log. Prepare therefore needs Go and module proxy access, with the
  default checksum database left on.
- Report directories the log names, restored where the run kept them, so
  the agent can read the same evidence. Criteria use only facts the agent
  can find in the workspace.
- Remotes pointing at local bare repositories, and a `gh` shim that only
  logs its arguments.
- A replay plugin: the current plugin with only `scripts/fix-all.sh`
  replaced, and without `evals/`, `plans/` or `test/`. The replacement
  records its arguments, applies the case's `result.bundle` and checks out
  the fix branch as the real script would, prints the recorded log and
  exits with the recorded code. Each runner below says how the agent finds
  it.
- An agent configuration with only this skill installed: no user plugins,
  instructions or memory, which would change which skill is picked (a
  Submariner `cve-fix` skill competes for the same request) and how it
  behaves. Agent directories go in `.git/info/exclude`, so they do not
  count as edits.

The agent gets a plain request, "Fix the CVEs in release-0.24 of this
repository", that names no command, so every agent gets the same prompt and
the case also tests that the skill is selected. Its final message is the
reply. `workspace.sh snapshot` then records the state for the checks.

### Case: review a recorded decision

A `review` case runs `review.sh` on the inputs a live run gave it (the
report directory and state it read) and checks each `RESOLVED` or
`UNRESOLVED` verdict against the case's expected one. The first comes from
the preserved subctl run, where the correct verdict is that the bumps were
skipped because the scan was blocked, not that the team must decide. That
case fails today: `scripts/review-prompt.md` requires every `UNRESOLVED`
reason to end in "(need team input)", even for an environment failure (see
[Correctness](README.md#correctness)). Live runs keep their report
directories from now on, so the group grows like the replay group.

### Checks

`checks.py` holds the deterministic checks and the judge prompt. Any failed
deterministic check scores the trial 0.

1. **Skill used.** The transcript shows this skill loaded, not another.
2. **State.** After the run, the repository is on the fix branch at the
   recorded result, the worktree is clean, ignored and untracked files are
   unchanged (by hash), the bare remotes are unchanged and the `gh` log is
   empty. The transcript has no attempted or denied push, `gh` call, stash
   or clean: a denied command never reaches the shim.
3. **One run.** The script ran exactly once, for the requested branch, as
   `SKILL.md` requires: no unrequested rerun, no other branch, and no
   answer given without running it.
4. **PR command.** Commands are read from fenced code blocks, with
   backslash-newline continuations joined before `shlex` splits them. If the
   log printed a PR command, one block holds the same argv; otherwise no
   block holds `gh pr create`.
5. **Named commits.** Commits a case requires, such as cdc3003, appear in the
   reply.
6. **Facts.** Binary criteria for each case, graded by a pinned judge model.
   Each needs reasoning the log does not hand over, for example "explains
   that the x/net and grpc bumps were skipped because the scan was blocked,
   and need no team decision". Binary criteria score more clearly and
   stably than a 1-to-5 rubric.

Unit tests in the hermetic suite cover checks 1 to 5. `checks.py calibrate`
validates the judge on stored replies: the reference reply, the recorded
wrong reply where one exists, and for each criterion a copy of the
reference with that one fact removed or changed. Each verdict must be the
same in five judge runs. Run it whenever criteria or the judge model
change, before scoring any agent. Reference replies follow `SKILL.md`'s
rules, edited from the recorded replies where those disagree: a Go
directive raise the build image supports is not a team decision, even where
a repository's older workflow note says to revert it.

### Cases

| Case | Run | Decision |
| --- | --- | --- |
| replay/001 | lighthouse: license | Finds backport cdc3003 |
| replay/002 | submariner: partial | Relays the PR; names the image owner |
| replay/003 | cloud-prepare: clean | Flagged lines need no action |
| replay/004 | subctl: `bin/lichen` | Blames the leftover, not the bumps |
| replay/005 | admiral: govet | Finds backport 8234df0 |
| replay/006 | lighthouse: x/crypto | Rejects the unsupported boundary |
| review/001 | subctl: blocked scan | Skipped bumps need no team decision |

Where stdlib findings remain, a case also requires naming Go 1.26.9 in the
build image and who updates it.

### Data and history

- **Case inputs are self-contained.** `input.yaml` pins the upstream base
  and default-branch commits, and `result.bundle`, a thin git bundle of
  only the run's commits (under 12 KB each), carries the result. A case
  depends on no fork branch or PR ref; subctl's result was never pushed,
  and PR heads carry later manual commits. Logs are stored whole and
  gzipped; trimming would need its own logic and could drop evidence the
  agent reads. The release-0.24 sources are kept under
  `.work/fix-go-cves-evals/source/` with a manifest and checksums until the
  cases are committed.
- **Only listed files are committed.** A case gets exactly the files in the
  layout below, copied by allowlist. Agent transcripts stay out: their
  first record lists the recording user's connectors, plugins, memory
  paths and session IDs. Home and runtime paths are replaced with
  placeholders in every committed text file, so logs, replies and report
  directories stay consistent. A hermetic test fails on any `*.jsonl` or
  transcript file, or any `/home/` or `/run/user/` path, under
  `evals/cases/`.
- **Format drift fails loudly.** `input.yaml` records the plugin commit that
  produced the log, and a hermetic test checks that every log still has
  what `SKILL.md` reads (the summary block, the `exit=` line, the flagged
  lines). When `fix-all.sh` output changes, the test names the cases to
  re-record.
- **Every trial is identified.** `workspace.sh snapshot` records the
  ai-helpers commit, a hash of `SKILL.md`, the agent CLI and its version,
  and the agent and judge models, so a change in pass rate can be traced to
  the skill, the agent or the model.
- **Adding a case.** From a live run, copy the log and the agent's reply,
  bundle the result commits, write the criteria and the reference reply,
  run `checks.py calibrate`, and register the case in `evals/README.md`.
- **History uses existing systems.** CI eval jobs keep each run's report,
  `summary.yaml` and `run_result.json` as Prow artifacts, with per-case
  results in `summary.yaml`; the JUnit file holds one result per config. The
  autodl export loads cost, tokens and model into BigQuery. Local runs keep
  harness results or Inspect logs under `.work/`. The thresholds in
  `eval-fix-go-cves.yaml` are the regression line; change them
  deliberately, saying why in the commit.

### Runners

Both runners share the cases, `workspace.sh` and `checks.py`, so they score
a trial the same way. Neither exposes the answers: the replay plugin
leaves out `evals/`, `plans/` and `test/`, and only `input.yaml`,
`run.log.gz` and `result.bundle` reach a workspace.

**agent-eval-harness** (`eval-fix-go-cves.yaml`) is the marketplace
convention, which a maintainer asked for in the k8s-rebase review, and
reports cost, tokens and model for each case.

- **Prompt mode**, so the agent gets the plain request rather than a skill
  invocation, on the `claude-code` runner.
- **Hooks.** `before_all` builds the replay plugin outside the repository,
  and `plugin_dirs` loads it, so `CLAUDE_PLUGIN_ROOT` names it.
  `before_each` (with `timeout: 900`) and `after_each` call `workspace.sh`.
  `workspace.files` lists only the three inputs above.
- **Isolation.** `runner.env` sets `CLAUDE_CONFIG_DIR` to an empty
  directory, so user instructions and memory stay out; the harness already
  leaves user plugins out. It also cuts off host credentials the agent
  could otherwise reach through `HOME`: `GH_CONFIG_DIR` points at an empty
  directory, and `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1` and
  `GIT_TERMINAL_PROMPT=0` drop git credential helpers. Its permissions deny
  `git push` and `gh` too, but prefix rules are easy to bypass: this runner
  is not a sandbox, and changes that should not be trusted run under
  Inspect.
  The harness writes its own files into the workspace (`.staged-plugins/`,
  `.claude/`, `output/` and others); `prepare` excludes them, and the state
  check ignores them.
- **Judges** call `checks.py` through `module:`/`function:`. Each judge has
  `min_pass_rate: 1.0`, so any failing case fails the run.
- **Review cases** use a second definition, `eval-fix-go-cves-review.yaml`,
  with the `cli` runner, because `review.sh` is a script that calls the
  agent itself. It always gets the recorded scan, so Grype never runs, and
  writes `metrics.json` for cost.
- Build this runner first: it answers the review and needs nothing new
  installed. Codex runs locally only, because CI has no OpenAI credentials.

**Inspect AI with Inspect SWE** (`task.py`) runs the same replay cases
isolated, for comparing agents and for changes that should not touch the
host. [Inspect AI](https://inspect.aisi.org.uk/) is maintained by the UK AI
Security Institute. [Inspect SWE](https://meridianlabs-ai.github.io/inspect_swe/),
from the same core team, runs Claude Code, Codex CLI, Gemini CLI, OpenCode
and Google's Antigravity SDK agent in a container:

- Model calls go through a loopback proxy to Inspect on the host, so no API
  key or Vertex credential enters the sandbox. Anthropic on Vertex works
  (`anthropic/vertex/...`), and the agent and model are chosen separately:
  Codex can run on a Vertex Claude model.
- The sandbox has no network (`network_mode: none`), and the agent binary is
  copied in from the host.
- The image holds only the repository state `workspace.sh prepare` builds.
  Each sample copies in the replay plugin at start and sets
  `CLAUDE_PLUGIN_ROOT` through the agent's `env` option; skills installed
  with the `skills` option land under the working directory, where
  `SKILL.md`'s fallback path would not find the scripts. A cached image so
  never tests a stale plugin.
- Three epochs with an `at_least` reducer give the per-case all-attempts
  result directly. `inspect score` re-scores saved logs after a judge
  change, and `inspect view` shows transcripts.

Inspect AI and Inspect SWE publish with PyPI Trusted Publishing and send no
telemetry; they are pre-1.0 and release often, so `evals/requirements.txt`
pins them with hashes. Pin the harness by git commit: the PyPI package
named `agent-eval-harness` is an unrelated project. Pin agent CLI versions
with Inspect SWE's `version` option. Keep all of it out of
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
  README.md                       case index
  eval-fix-go-cves.yaml           agent-eval-harness, replay cases
  eval-fix-go-cves-review.yaml    agent-eval-harness, review cases
  task.py                         Inspect task, replay cases
  checks.py                       deterministic checks and judge prompt
  workspace.sh                    build the replay plugin; prepare and
                                  snapshot a case workspace
  Dockerfile                      Inspect sandbox (base pinned by digest)
  requirements.txt                pinned, hashed eval dependencies
  cases/replay/case-NNN/          input.yaml (repo, commits, files,
                                  request), annotations.yaml (criteria,
                                  PR command), result.bundle,
                                  run.log.gz, reply.md, wrong-reply.md
  cases/review/case-NNN/          input.yaml, annotations.yaml
                                  (verdicts), report directory
```

### Running

- Run three attempts per case and report passes out of three for each case:
  three harness run IDs, or three Inspect epochs. Three attempts flag noise
  too: a case that passes 90% of single attempts passes all three only 73%
  of the time. Before calling a failure a regression, rerun that case about
  ten times with the old and the new `SKILL.md` on the same model.
- Read failing transcripts (`/eval-review` or `inspect view`) before
  changing `SKILL.md`. A failure can be the case's fault as easily as the
  skill's.
- In CI, use the repository's existing Prow eval workflow,
  `openshift-claude-agent-eval`, which brings CI's Vertex credentials and
  the `claude-ai-helpers` image. Add an optional `eval-fix-go-cves` job with
  `always_run: false`, started only with `/test eval-fix-go-cves`, after a
  maintainer has read the PR's `evals/` and `scripts/` diff. Those files run
  in the job beside the credentials, and after one `/ok-to-test` a
  `run_if_changed` trigger would rerun every later push unreviewed.
- Three changes to the shared workflow, in openshift/release:
  - a variant that does not mount the GitHub bot token, which the eval
    never uses;
  - the harness pinned by commit (an `EVAL_HARNESS_REF` with a SHA
    default) instead of cloned at `main`;
  - a final step that runs that checkout's `score.py regression` and fails
    on its exit code, or when `run_result.json` is missing. The workflow
    otherwise passes or fails on the agent's exit, not on the thresholds.
- Run the whole config, not `EVAL_CHANGED_ONLY`: that option diffs with
  `.git`, which the image leaves out, so it skips every case and still
  reports success.
- Run it before changing `SKILL.md`, `scripts/review-prompt.md` or the
  default model.

### To confirm when building

- `workspace.sh prepare` fits in the hook timeout on CI's one CPU, and the
  image has `jq`, `git` and module proxy access.
- A full Inspect trial completes with the sandbox network off.
- The cost of one trial, to set the per-case budget.

## 3. Optional: live canary

Run `scripts/report.sh` weekly on one fast repository (Shipyard `devel`)
on a runner with Docker; as a Prow periodic, its history would land in
Sippy with the rest. It needs no model and fails only on `INCOMPLETE` or
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
