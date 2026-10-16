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

### Format: Harbor tasks

Use the [Harbor](https://github.com/laude-institute/harbor) task format,
the Terminal-Bench successor: a container environment, an instruction, a
verifier and an oracle solution per task.

- **Any agent.** Harbor injects job-supplied skills into each agent's native
  location and ships integrations for Claude Code, Codex, Antigravity, Gemini
  CLI, Cursor and others, so one task set covers every agent:
  `harbor run -p .work/evals/tasks -a codex --skill skills/fix-go-cves -k 3`.
- **Isolation.** Each trial gets a fresh container, so the agent cannot touch
  the host, a real fork or another trial.
- **Verifier checks.** The `oracle` agent must score 1 and `nop` must score
  0 before results count.
- **Regrade.** A separate verifier grades only collected artifacts, so
  changing a judge reruns no agents.

The other plugins' evals here use agent-eval-harness, which runs on the host
and has no oracle or regrade step. Harbor fits a skill whose correctness
depends on repository state better.

### Task: replay a recorded run

A task is a recorded run, not a new one. It needs no build, scan or Docker
daemon, so a trial takes minutes and costs well under $1.

- **Environment.** The image clones the case repository and checks out its
  fix branch at the recorded result (the upstream `refs/pull/N/head`). It
  keeps the base and default branches for backport searches, points every
  remote at a local bare repository, and puts a `gh` shim on `PATH` that only
  logs its arguments. `CLAUDE_PLUGIN_ROOT`, which `SKILL.md` already honors,
  names a plugin copy whose `scripts/fix-all.sh` prints the recorded log and
  exits with the recorded code. The skill under test is the real one,
  supplied with `--skill`.
- **Instruction.** The real request (`/fix-go-cves:fix-go-cves 0.24`, or
  "fix the CVEs in release-0.24"), plus one line saying to save the final
  reply to `/logs/artifacts/reply.md`.
- **Artifacts.** The reply, the repository and the `gh` log.

### Verifier

The deterministic checks gate the result: if any fails, the reward is 0.
Facts are then scored by an LLM judge.

1. **State.** The fix branch and HEAD are unchanged, the worktree is clean,
   the bare remotes are unchanged and the `gh` log is empty. This catches
   pushes, PRs and hand edits by outcome, whatever tools the agent used.
2. **PR command.** If the log printed one, the reply contains a command with
   the same argv, compared with `shlex`, so quoting differences pass.
   Otherwise the reply contains none.
3. **Facts.** Binary criteria for each case, graded with Harbor rewardkit's
   judge criteria, for example "recommends backporting cdc3003, the
   `.lichen.yaml` override, from devel". Binary criteria give clearer and
   more stable scores than a 1-to-5 rubric.

The oracle's `solve.sh` writes the reference reply, so every criterion is
proven satisfiable. Where a run produced a wrong reply, that reply is kept as
the case's negative example and must fail.

### Cases

Each case comes from a release-0.24 run and tests one decision:

| Case | Run | Decision |
| --- | --- | --- |
| case-001 | lighthouse: license, stdlib | Finds backport cdc3003 |
| case-002 | submariner: partial fix | Relays the PR, does not run it |
| case-003 | cloud-prepare: exit 0 | Invents no review items |
| case-004 | subctl: leftover `bin/lichen` | Removes it, reruns |
| case-005 | admiral: govet failure | Finds backport 8234df0 |

Every case where stdlib findings remain also requires naming Go 1.26.9 in
the build image. Add a case whenever a live run shows a new skill-layer
mistake. Do not write speculative cases.

### Layout

Following Harbor's adapter pattern, the cases are data and one template
renders them:

```text
evals/
  README.md            case index (required by the repository lint)
  template/            task.toml, Dockerfile, replayer, gh shim, verifier
  cases/case-NNN/      case.yaml (repo, refs, exit code, criteria),
                       run.log (trimmed, home paths replaced),
                       reply.md (reference), wrong-reply.md (optional)
  render.py            writes Harbor tasks to .work/evals/tasks/
```

The verifier's deterministic part gets unit tests in the hermetic suite, so
`make test` covers the grader too.

### Running

- `make eval agent=claude-code|codex|antigravity-cli case=NNN` renders the
  tasks, verifies them with `oracle` and `nop`, then runs three attempts.
  Report the pass rate and pass^3 (every attempt passes), because a skill
  that is right two times in three is not dependable.
- Not in CI: it needs model credentials and spends money. Run it before
  changing `SKILL.md`, the review prompts or the default model.

### Optional case: the LLM verification layer

Replay the same evidence through the LLM verification layer. If its
verdicts never change an outcome that the deterministic evidence has not
already decided, that settles the decision in the
[plans index](README.md#decisions) to drop the layer.

## 3. Optional: live canary

Run `scripts/report.sh` weekly on one fast repository (Shipyard `devel`, on
a runner with Docker). It needs no model and catches drift that no recorded
case can: Grype schema or database changes, new Go releases, builder-image
changes. Several release-0.24 failures were drift of this kind.

## Not planned

- Evals that run the full fix, which take hours and need Docker. The canary
  and manual live runs cover end-to-end behavior.
- A with/without-skill ablation: the skill owns the script entry point, so a
  run without it measures nothing useful.
- Trigger or description evals.
- A second suite in the `claude plugin eval` layout, whose graders cannot
  check repository state.
