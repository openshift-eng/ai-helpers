# Testing and evals

How each layer of the plugin is tested, and what to build next.

## Layers

- **Scripts** (`scripts/`, `subagents/*.sh`) decide versions, commits,
  ignores and gates. `test/test-lib.sh` covers them with about 2,300
  hermetic checks.
- **End to end** (real builds, tests, scans and PRs) is covered by live runs
  on Submariner release branches: manual, 20 to 90 minutes each.
- **The skill** (`SKILL.md`) turns a finished run into the cause, evidence,
  action and owner for each finding. Nothing measures it.

Live-run failures feed the faster layers: a script bug gets a hermetic
regression test (as every release-0.24 bug did), and a skill mistake gets an
eval case. No case is written speculatively.

## 1. Run the suite in CI

`make test` runs every plugin's `test_*.py`, this suite included. It only
skipped because its wrapper demanded Go 1.26; the suite passes on Go 1.24
(1.22 fails four packed-binary checks), and GitHub's `ubuntu-24.04` runners
put Go 1.24 on `PATH`. With the floor at 1.24, the existing Test job runs it.

That adds about 3 minutes (measured locally) to a job that takes under 1
today, on every PR. If maintainers object, move the suite to a Prow job with
`run_if_changed: ^plugins/fix-go-cves/` rather than add diff logic to the
wrapper.

## 2. Evaluate the skill

On release-0.24 the skill found a default-branch fix to backport for a
license failure (lighthouse) and traced stdlib findings to the build image.
It also passed on two wrong verdicts from `review.sh`'s model review without
checking them: an invented x/crypto policy boundary, and "team input" for
three subctl bumps that a leftover `bin/lichen` binary had blocked.
(`scripts/review-prompt.md` forces every open reason into "team input"; see
[Correctness](README.md#correctness).) `SKILL.md` asks the skill to
investigate each flagged line, so a case may require it to reject such a
verdict.

### Phase 1

The repository's convention, agent-eval-harness (`eval-fix-go-cves.yaml`),
run locally on the `claude-code` runner. It reports cost, tokens and model
per case, which a maintainer asked for in the review of the k8s-rebase
plugin.

**A case replays a recorded run.** No build, scan or Docker daemon runs, so
a trial takes minutes and costs well under $1. `workspace.sh prepare`, the
harness's `before_each` hook, builds a workspace holding:

- the case repository at pinned base and default-branch commits, on the
  branch the run started from;
- untracked files the run saw, as stubs dated before the log starts (for
  subctl, an empty `bin/lichen`);
- report directories the log names, where the run kept them;
- remotes pointing at local bare repositories, and a `gh` shim that only
  logs its arguments.

The plugin is loaded from a replay copy, built outside the repository by a
`before_all` hook: the current plugin without `evals/`, `plans/` or `test/`,
with `scripts/fix-all.sh` replaced. The replacement records its arguments,
applies the case's `result.bundle` (a git bundle of just the run's commits)
to create the fix branch, prints the recorded log and exits with the
recorded code. Nothing else from the case reaches the agent.

The harness invokes the skill with the case's arguments (`mode: case`, as in
the repository's other evals), with `CLAUDE_CONFIG_DIR` pointing at an empty
directory so user instructions and memory stay out. `GH_CONFIG_DIR` is empty
and `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1` and
`GIT_TERMINAL_PROMPT=0` drop host git and `gh` credentials. The runner is
still not a sandbox.

**Checks** live in `checks.py`. The deterministic ones gate at a 1.0 pass
rate:

1. **State.** After the run: on the fix branch at the recorded result, a
   clean worktree, untracked and ignored files unchanged, bare remotes
   unchanged, an empty `gh` log, and no attempted or denied push, `gh`,
   stash or clean in the transcript. The harness's own files are excluded.
2. **One run.** The script ran once, for the requested branch.
3. **PR command.** If the log printed one, a code block in the reply holds
   the same command; otherwise none holds `gh pr create`.
4. **Commits.** Commits the case names appear in the reply.

The judged facts gate at 0.8, as in the repository's code-review eval:
binary criteria per case that need reasoning the log does not hand over,
such as "the x/net and grpc bumps were skipped because the scan was blocked,
and need no team decision". `checks.py calibrate` must pass each reference
reply and fail each recorded wrong reply before any agent is scored; rerun
it when criteria or the judge model change. Reference replies follow
`SKILL.md`: a Go directive raise the build image supports is not a team
decision.

**Cases** (`cases/fix-go-cves/case-NNN`, indexed in `evals/README.md`):

| Case | Run | Decision |
| --- | --- | --- |
| 001 | lighthouse: license | Backports devel's cdc3003 |
| 002 | submariner: partial | Relays the PR; names the image owner |
| 003 | cloud-prepare: clean | Flagged lines need no action |
| 004 | subctl: `bin/lichen` | Blames the leftover, not the bumps |
| 005 | admiral: govet | Backports devel's 8234df0 |
| 006 | lighthouse: x/crypto | Rejects the unsupported boundary |

Each case holds `input.yaml` (repository, commits, arguments, files),
`annotations.yaml` (criteria, PR command), `result.bundle`, the whole log
gzipped, `reply.md` and, where one exists, `wrong-reply.md`. Files are
copied by allowlist: agent transcripts stay out, because their first
record lists the recording user's connectors, plugins and memory paths.
Hermetic tests fail on a transcript, a `/home/` or `/run/user/` path under
`evals/cases/`, or a log missing what `SKILL.md` reads, which happens when
`fix-all.sh` output changes and the case needs re-recording. The
release-0.24 sources are kept in `.work/fix-go-cves-evals/source/` until
then.

**Running.** Three runs per case before a `SKILL.md`, review-prompt or model
change. Read failing transcripts before changing anything, since a case can
be wrong too, and rerun a failing case with the old `SKILL.md` before
blaming the change.

### Later

- **CI.** An optional `eval-fix-go-cves` Prow job on the shared
  `openshift-claude-agent-eval` workflow, started by hand with `/test` after
  a maintainer reads the PR's `evals/` and `scripts/` diff, because that
  code runs beside CI's credentials. Before then, the shared workflow needs
  issues filed: it clones the harness at `main`, mounts a GitHub token
  evals do not use, and passes on the agent's exit rather than the
  thresholds. Its `EVAL_CHANGED_ONLY` option skips every case, since the
  image has no `.git`.
- **Isolated and cross-agent runs.** Inspect AI with Inspect SWE runs Claude
  Code, Codex, Gemini CLI and others in a networkless container, with model
  credentials kept on the host. Vertex works. It is the runner for
  untrusted changes and agent comparisons. (Harbor was rejected: no Vertex
  support for Claude Code, and credentials inside the sandbox.)
- **`review.sh` cases**, if a review mistake appears that replay cases
  cannot catch.

## 3. Optional: live canary

Run `scripts/report.sh` weekly on one fast repository (Shipyard `devel`) on
a runner with Docker. It needs no model and fails only on `INCOMPLETE` or
`ERROR`, never on findings. It catches drift no recorded case can: Grype
schema or database changes, new Go releases, builder-image changes. Several
release-0.24 failures were drift of this kind.

## Not planned

- Evals that run the full fix: they take hours and need Docker, and the
  canary and live runs cover end-to-end behavior.
- A with/without-skill comparison: without the skill, nothing runs the
  scripts.
- An eval of the LLM verification layer: the recorded runs already settle
  it (see [Decisions](README.md#decisions)).
