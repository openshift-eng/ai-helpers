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
put Go 1.24 on `PATH` (the Test job uses `ubuntu-latest`, currently 24.04).
With the floor at 1.24, the existing Test job runs it. When `CI` is set, the
wrapper fails instead of skipping, so a runner image without Go cannot
silently drop the suite.

That adds about 3 minutes (measured locally) to a job that takes under 1
today, on every PR. If maintainers object, move the suite to a Prow job with
`run_if_changed: ^plugins/fix-go-cves/` rather than add diff logic to the
wrapper.

## 2. Evaluate the skill

On release-0.24 the skill found a default-branch fix to backport for a
license failure (lighthouse) and traced stdlib findings to the build image.
It also relayed two wrong verdicts from `review.sh`'s model review
unchecked: an invented x/crypto policy boundary, and "team input" for three
subctl bumps that a leftover `bin/lichen` binary had blocked.
(`scripts/review-prompt.md` forces every open reason into "team input"; see
[Correctness](README.md#correctness).) `SKILL.md` asks the skill to
investigate each flagged line, so a case may require it to reject such a
verdict.

Terms: a **recording** is the release-0.24 `fix-all.sh` run a case is built
from; a **trial** is one harness invocation on one case; a **round** is one
trial of every case, and a score uses three rounds.

### Phase 1

Each case replays a recording with the repository's convention,
agent-eval-harness, run locally on the
`claude-code` runner, which reports cost, tokens and model per case, as a
maintainer asked for in the review of the k8s-rebase plugin. The skill
reads the recorded log in a workspace rebuilt to match the recording, so no
build, scan or Docker daemon runs, and a trial takes minutes and costs well
under $1.

Everything lives under `plugins/fix-go-cves/evals/`, laid out like
`plugins/ci/evals/`: `eval-fix-go-cves.yaml`, a `README.md` that indexes
the cases (the repository lint requires it), `run.sh`, `checks.py`,
`workspace.sh`, and `cases/fix-go-cves/case-NNN/`.

**Cases:**

| Case | Recording | Decision |
| --- | --- | --- |
| 001 | lighthouse: license | Backports devel's cdc3003 |
| 002 | submariner: partial | Relays the PR; names the image owner |
| 003 | cloud-prepare: clean | Flagged lines need no action |
| 004 | subctl: `bin/lichen` | Blames the leftover, not the bumps |
| 005 | admiral: govet | Backports devel's 8234df0 |
| 006 | lighthouse: x/crypto | Rejects the unsupported boundary |

Each case directory holds:

- `input.yaml`: repository, pinned commits (base, default branch, and the
  ai-helpers commit that produced the log, for provenance), arguments and
  stub files;
- `annotations.yaml`: criteria, the PR command, commits the reply must
  name;
- `result.bundle`: a git bundle of just the recording's commits;
- `run.log.gz`: the whole log, gzipped;
- `reply.md`: the reference reply;
- `negatives/`: the recorded wrong reply, where one exists, and one-fact
  edits of the reference;
- `reports/`: report directories the log names, where the recording kept
  them (subctl's), with home paths stored as placeholders;
- `plugin.tar.gz`: the plugin as it was at that commit, limited to
  `.claude-plugin/`, `skills/`, `scripts/`, `subagents/` and `README.md`
  (about 110 KB); `plans/` would name the answers. The commits live only on
  the PR branch, which a rebase or squash would rewrite.

Files are copied by allowlist. Agent transcripts stay out: their first
record lists the recording user's connectors, plugins and memory paths.
Hermetic tests fail on a transcript, a `/home/` or `/run/user/` path
anywhere under `evals/fix-go-cves/cases/` (decompressing `.gz` files
first), a `plugin.tar.gz` holding `plans/` or any case's answer strings, or
a log missing what `SKILL.md` reads. Checks that need the case repositories'
history (each bundle's commits scanned on top of its base, and a prepared
workspace reaching nothing outside itself) run as `checks.py lint`, which
needs the clone cache or network access: run it before committing a case,
and `run.sh` runs it first. The bundles and PR commands keep the
recording author's name and fork. Three bundles (004, 005, 006) hold
commits that were never pushed, but they contain only `go.mod`, `go.sum`
and `.grype.yaml` edits by the same author, so publishing them adds nothing
sensitive. Until the cases are committed, the release-0.24 sources stay in
`.work/fix-go-cves-evals/source/`.

**Checks** live in `checks.py`. The deterministic ones gate at a 1.0 pass
rate:

1. **State.** After the trial: on the fix branch at the recorded result, a
   clean worktree, untracked and ignored files unchanged, bare remotes
   unchanged, an empty `gh` log, and no attempted or denied push, `gh`,
   stash or clean in the transcript. The harness's own files are excluded.
   A tool input that names a protected root voids the trial, since it may
   have reached an answer: an absolute path token, read after dropping
   shell defaults such as the `/tmp` in `${TMPDIR:-/tmp}`, that resolves
   under `/home`, `/tmp`, `/var/tmp` or `/run/user` outside the trial's own
   directory. A calibration fixture holding `SKILL.md`'s exact commands
   must pass.
2. **One run.** The script ran once, for the requested branch.
3. **PR command.** If the log printed one, a code block in the reply holds
   the same command, compared as shell-parsed tokens with continuations
   joined, since logs escape the title and replies quote it; otherwise no
   block holds `gh pr create`.
4. **Commits.** Commits in `annotations.yaml` appear in the reply, matched
   by a prefix of at least seven characters.

The judged facts are binary criteria per case that need reasoning the log
does not hand over, such as "the x/net and grpc bumps were skipped because
the scan was blocked, and need no team decision". A pooled threshold would
let one case fail every trial while the rest pass, so `checks.py summarize`
reads the three rounds and requires every case to pass its deterministic
checks in all three and its facts in at least two.

**Calibration.** `checks.py calibrate` runs the harness's own judges (`score.py
judges`) on synthetic trials whose final result is a stored reply, so the
scoring prompt is the one calibrated. It must pass each `reply.md` and fail
each negative before any agent is scored; rerun it when criteria or the judge
model change. References for 004 and 006 are written by hand, since their
recorded replies are the wrong ones, and 005's is edited. 006 is a separate,
earlier lighthouse run that hit the same license failure, so it also carries
001's backport criterion, which its recorded reply fails by suggesting the
license be allowed instead. Criteria stay neutral on whether a Go directive
raise needs the team: the plugin and the repositories' own workflow notes
disagree (see [Decisions](README.md#decisions)).

**Running.** Three rounds to accept a `SKILL.md` or model change. A change
to `scripts/review-prompt.md` or to `fix-all.sh` output is not exercised by
replay: it means re-recording the cases whose logs it changes (004 and 006
for the review prompt). Read failing transcripts before changing anything,
since a case can be wrong too, and rerun a failing case with the old
`SKILL.md` before blaming the change.

**Workspace.** The harness invokes the skill with the case's arguments
(`mode: case`, as in the repository's other evals) in a case workspace,
which `workspace.sh prepare`, the `before_each` hook (timeout 900 seconds,
for a cold clone), turns into the case repository:

- **Replace the harness scaffolding.** The harness makes the workspace a git
  repository whose first commit holds `input.yaml`, and links ai-helpers'
  `CLAUDE.md`, `scripts/` and every `.claude/` subdirectory into it, which
  would collide with the case repository and expose ai-helpers. Prepare
  removes that `.git` and every link. It keeps `.claude/settings.json`,
  which the agent reads at launch, after `before_each`, but deletes its
  `permissions.additionalDirectories`, which grants read access to the
  directory the harness runs from.
- **Build the repository.** Prepare fetches only the pinned commits, with
  no tags, from a clone cache under ai-helpers' `.work/` (warmed by
  `before_all`, and inside a path the sandbox denies, since it holds the
  full history) into a fresh repository and fresh bare remotes, so no later
  history (such as the merged CVE PRs, which contain the backports cases
  001 and 005 look for) is reachable. It checks out the branch the
  recording started from and points every remote at a bare remote. A
  `checks.py lint` checks that every ref and object is reachable from the
  pinned commits or the bundle. Harness paths go in
  `.git/info/exclude`. Prepare then deletes `input.yaml`, which the harness
  has already read for the arguments; `annotations.yaml` never reaches the
  workspace.
- **Restore what the recording saw.** Untracked files as stubs (for subctl,
  an empty `bin/lichen`; `go version` on it disagrees with the log, so
  criteria rely on the log, not the file), and the case's `reports/`,
  unpacked in the trial's own space at the paths the preamble writes into
  the log, outside the case repository.
- **Stage the plugin.** Prepare unpacks the case's `plugin.tar.gz` into
  `.staged-plugins/fix-go-cves`, where the runner reuses an existing copy.
  It is the plugin that produced the log, not today's: current scripts
  carry comments written after a recording, and one names case 004's
  answer. Only `SKILL.md`, the thing under test, comes from the working
  tree, and the case's log and `result.bundle` are added.
  `scripts/fix-all.sh` keeps its real text behind a short preamble that
  records its arguments, applies the bundle to create the fix branch,
  prints the recorded log and exits with the recorded code, so an agent
  reading the script still finds the gate logic it is investigating. Logs
  and report directories store home-directory paths as two placeholders:
  the recording's repository root, which the preamble fills with the case
  workspace, and every other home path (run state, reports, the log
  itself), which it fills with a directory in the trial's own space. The
  log's own `exit=` line is dropped, since `SKILL.md` appends one.

An `after_each` hook writes the repository state (status including ignored
files, refs, the bare remotes and the `gh` log) to a declared `outputs:`
path in the workspace, which the harness collects for the checks. The reply
is the `result` field of the last `{"type":"result"}` object in the trial's
`stdout.log`, extracted to its own output file by a `before_scoring` hook;
the harness's events omit that text, a resumed session emits one result per
segment, and the conversation it otherwise hands judges includes interim
narration and the log itself. `checks.py calibrate` writes its synthetic
trials in the same form.

**Isolation.** `run.sh` invokes the harness once per trial, each time in a
fresh trial directory under a dedicated root outside `/home` and `/tmp` (for
example `/var/tmp/fix-go-cves-evals/`), which holds the trial's `TMPDIR` (where
the harness puts workspaces, with no `CLAUDE.md` above it), its `HOME` and its
other files. `PATH` is the `gh` shim, which only logs its arguments, followed
by system directories only: the host's own `PATH` can point under `/home`
(`~/.local/bin`, Homebrew), which the sandbox below denies. `run.sh` deletes
the trial directory after collecting results. The claude-code runner passes the
agent only `runner.env` and a short host allowlist that includes `HOME`, `PATH`
and `GOOGLE_APPLICATION_CREDENTIALS` but not `TMPDIR`, so `runner.env` carries
`TMPDIR: "$TMPDIR"` and `CLAUDE_CODE_TMPDIR: "$TMPDIR"`, which the harness
resolves from `run.sh`'s environment; the second keeps Claude Code's own
temporary files, including background-task output the skill reads, inside the
trial directory. That keeps the user's `CLAUDE.md`, memory, plugins and
credentials out of the agent's default view, but environment variables do not
stop a command from reading an absolute path, and a developer host holds copies
of the answers in many places: the case sources, the clone cache, the recording
repositories, stray clones and dumps under `/tmp`, earlier trials and `~/.ssh`.
`runner.settings` therefore enables Claude Code's sandbox, with no unsandboxed
fallback, denying reads of `/home`, `/tmp`, `/var/tmp` and `/run/user` except
the trial's own directory; check 1 voids any trial that names one anyway. If
the sandbox cannot express that exception, the trial runs as a dedicated Unix
user with a private `/tmp` instead.

`runner.env` also sets `GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0` and
`GIT_ALLOW_PROTOCOL=file`, so git cannot fetch a newer upstream than the
pinned one, `GOPROXY=off` with `GOTOOLCHAIN=local` for Go, and an empty
`AGENT_EVAL_RUNS_DIR`, so the agent is not told where results go. Claude
Code itself reads the Vertex key file, outside the sandbox; the file stays
under a denied root, so the agent's commands cannot read it.

The eval file's `permissions.deny`, which the harness writes into the workspace
settings, blocks `Bash(git push:*)`, `Bash(gh:*)`, MCP tools, web tools and
subagents, so check 1 has denials to find.

**To confirm when building:** that Claude Code's sandbox read rules stop Bash,
not only the Read tool, from reading the denied paths on Linux (a trial must
fail to read a canary file seeded in `/tmp`); that a trial's sandboxed
`$TMPDIR` and background-task output both resolve inside the trial directory;
that a trial can run `git`, `jq`, `python3` and `go version` with the
restricted `PATH`; that prepare fits its 900-second hook timeout from a cold
cache; and the cost of one trial, to set the per-case budget.

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
