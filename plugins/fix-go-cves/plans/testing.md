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

On release-0.24 the skill found a default-branch fix to backport for a license
failure (lighthouse) and traced stdlib findings to the build image. In subctl
it found the leftover `bin/lichen` binary that had blocked the scan and cleared
the x/net bump for a rerun, but still sent the grpc and otel/sdk bumps to the
team, repeating `review.sh`'s "team input" verdict for bumps the blocked scan
had skipped (`scripts/review-prompt.md` forces every open reason into "team
input"; see [Correctness](README.md#correctness)). In an earlier lighthouse run
it missed the backport, suggesting the license be allowed instead, and blamed
that run's x/crypto "policy boundary" flag on the Go 1.26 raise; the flag was
spurious, a side effect of ignoring GO-2026-5932, which has no fix (see
[Correctness](README.md#correctness)). `SKILL.md` asks the skill to investigate
each flagged line, so a case may require it to reject or explain such a
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
| 004 | subctl: `bin/lichen` | No team decision for the blocked bumps |
| 005 | admiral: govet | Backports devel's 8234df0 |
| 006 | lighthouse: x/crypto | Flag is spurious; backports cdc3003 |

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

Files are copied by allowlist. Agent transcripts stay out: their first record
lists the recording user's connectors, plugins and memory paths. Hermetic tests
fail on a transcript, a `/home/` or `/run/user/` path anywhere under
`evals/cases/fix-go-cves/`, which must hold at least one case (decompressing
`.gz` files first), a `plugin.tar.gz` holding `plans/` or any case's answer
strings, a `plugin.tar.gz` holding anything but regular files and directories
under `.claude-plugin/`, `skills/`, `scripts/`, `subagents/` and `README.md`
(no links, absolute or `..` names), a manifest with keys beyond `name`,
`version`, `description` and `author` (a plugin can also declare unsandboxed
hooks, monitors and language servers), or a log missing what `SKILL.md` reads.
Checks that need the case repositories' history (each bundle's commits scanned
on top of its base, and a prepared workspace reaching nothing outside itself)
run as `checks.py lint`, which needs the clone cache or network access: run it
before committing a case, and `run.sh` runs it first. The bundles and PR
commands keep the recording author's name and fork. Three bundles (004, 005,
006) hold commits that were never pushed, but they contain only `go.mod`,
`go.sum` and `.grype.yaml` edits by the same author, so publishing them adds
nothing sensitive. Until the cases are committed, the release-0.24 sources stay
in `.work/fix-go-cves-evals/source/`.

**Checks** live in `checks.py`. The deterministic ones gate at a 1.0 pass
rate:

1. **State.** After the trial, in the container: on the fix branch at the
   recorded result, a clean worktree, untracked and ignored files unchanged,
   bare remotes unchanged, an empty `gh` log, no `subagents/` or
   `input.yaml` planted, and no attempted or denied push, `gh`, stash or
   clean in the transcript. The harness's own files are excluded.
2. **One run.** The script ran once, for the requested branch.
3. **PR command.** If the log printed one, a code block in the reply holds
   the same command, compared as shell-parsed tokens with continuations
   joined, since logs escape the title and replies quote it; otherwise no
   block holds `gh pr create`.
4. **Commits.** Commits in `annotations.yaml` appear in the reply, matched
   by a prefix of at least seven characters.

The judged facts are binary criteria per case that need reasoning the log does
not hand over, such as "the x/net, grpc and otel/sdk bumps were skipped because
the scan was blocked, and need no team decision". A pooled threshold would let
one case fail every trial while the rest pass, so `checks.py summarize` reads
the three rounds and requires every case to pass its deterministic checks in
all three and its facts in at least two.

**Calibration.** `checks.py calibrate` runs the harness's own judges (`score.py
judges`) on synthetic trials whose final result is a stored reply, so the
scoring prompt is the one calibrated. It must pass each `reply.md` and fail
each negative before any agent is scored, including, per case, a wrong reply
that also tells the judge to pass it; rerun it when criteria or the judge model
change. References for 004 and 006 are written by hand, since their recorded
replies are wrong, and 005's is edited to drop its claim that the Go 1.26 raise
is the team's call, since criteria stay neutral on that. 006 is a separate,
earlier lighthouse run that hit the same license failure, so it carries 001's
backport criterion, which its recorded reply fails. Its own criterion passes a
reply that shows the x/crypto "policy boundary" flag is spurious (it follows
the GO-2026-5932 ignore, and the scan has no x/crypto finding) and that
x/crypto needs no action, and fails one that sends the flag to the team or
blames the Go raise; the recorded reply and a constructed team-input negative
cover both. Criteria stay neutral on whether a Go directive raise needs the
team: the plugin and the repositories' own workflow notes disagree (see
[Decisions](README.md#decisions)).

**Running.** Three rounds to accept a `SKILL.md` or model change. A change to
`scripts/review-prompt.md` or to `fix-all.sh` output is not exercised by
replay: it means re-recording the cases whose logs it changes; for the review
prompt, every case whose log has `UNRESOLVED:` lines (001, 002, 004 and 006).
Read failing transcripts before changing anything, since a case can be wrong
too, and rerun a failing case with the old `SKILL.md` before blaming the
change.

**Workspace.** The harness invokes the skill with the case's arguments
(`mode: case`, as in the repository's other evals) in a case workspace,
which `workspace.sh prepare`, the `before_each` hook (timeout 900 seconds,
for a cold clone), turns into the case repository:

- **Replace the harness scaffolding.** The harness makes the workspace a git
  repository whose first commit holds `input.yaml`, and links ai-helpers'
  `CLAUDE.md`, `scripts/` and every `.claude/` subdirectory into it, which
  would collide with the case repository and expose ai-helpers. Prepare
  removes that `.git` and every link, and deletes `input.yaml` once the
  harness has read the arguments. It keeps `.claude/settings.json`, which
  the agent reads at launch.
- **Build the repository.** Prepare fetches only the pinned commits, with
  no tags, from a clone cache under ai-helpers' `.work/` (warmed by
  `before_all`) into a fresh repository and fresh bare remotes, so no later
  history (such as the merged CVE PRs, which contain the backports cases
  001 and 005 look for) is reachable. It checks out the branch the
  recording started from and points every remote at a bare remote.
  `checks.py lint` checks that every ref and object is reachable from the
  pinned commits or the bundle. `annotations.yaml` never reaches the
  workspace.
- **Restore what the recording saw.** Untracked files as stubs (for subctl,
  an empty `bin/lichen`; `go version` on it disagrees with the log, so
  criteria rely on the log, not the file), and the case's `reports/`, at
  the paths the preamble writes into the log, outside the case repository.
- **Stage the plugin.** Prepare unpacks the case's `plugin.tar.gz`, with
  Python's `tarfile` and `filter="data"`, into
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
  itself), which it fills with a directory beside the workspace. The log's
  own `exit=` line is dropped, since `SKILL.md` appends one.

**Isolation: the agent runs in a throwaway container.** The harness stays on
the host, so its `claude-code` runner still reports cost, tokens and model,
and its judges keep the host's credentials. The agent does not. The harness
launches `claude` by name, so `run.sh` puts a `claude` wrapper first on the
harness's `PATH`; for each trial the wrapper:

- starts a container from a pinned image (Claude Code at the host's
  version, git, jq, Go, Python and socat, plus the `gh` shim that only logs
  its arguments) with `--network none`, a fresh `HOME`, no host mounts
  except one Unix socket, and the trial's name;
- copies in the prepared workspace and the bare remotes at the same paths,
  since the runner passes `--plugin-dir` and `--settings` as workspace
  paths, and runs `claude` there with the runner's arguments, stdin and
  stdout passed through (answering the runner's `claude --version` too);
- reaches Vertex through a proxy on the host that lives for the trial and
  listens only on that socket, which socat in the container turns back into
  a local port. The proxy adds the bearer token from the host's credentials,
  forwards only the Anthropic model paths for the configured project, and
  caps requests and bytes, since the agent could call it directly. The
  container runs Claude Code with `CLAUDE_CODE_SKIP_VERTEX_AUTH=1` and
  `ANTHROPIC_VERTEX_BASE_URL` pointing at that port: both are on the
  runner's allowlist for this purpose (agentic-ci uses the same proxy
  pattern), and cost is still reported as the runner's own.

No credential, host path, other trial, case answer or network route exists
inside the container, and nothing the agent writes reaches the host. The
`after_each` hook commits the container, runs the state check from that
image (also without network or mounts), copies the resulting JSON to the
case's declared `outputs:` path, and removes the container with
`podman rm -f`. That also stops any process the agent left running: the
runner's timeout kills only the wrapper. The state check runs git with
`-c core.fsmonitor=false -c core.hooksPath=/dev/null` and system and global
configuration off, and hashes the bare remotes instead of running git in
them. The reply is the `result` field of the last `{"type":"result"}` object
in the trial's `stdout.log`, extracted to its own output file by a
`before_scoring` hook: the harness's events omit that text, a resumed session
emits one result per segment, and the conversation it otherwise hands judges
includes interim narration and the log itself. `checks.py calibrate` writes
its synthetic trials in the same form, and `checks.py` reads case arguments
only from the dataset.

The eval file's `permissions.deny`, which the harness writes into the
workspace settings, blocks `Bash(git push:*)`, `Bash(gh:*)`, MCP tools, web
tools and subagents, so check 1 has denials to find. The entries stay plain
tool patterns and the eval uses no provider plan: either would make the
runner write a settings overlay into the workspace, one form of which holds
the inference key. `run.sh` starts the harness with an explicit environment
(`env -i`), so stray host keys such as `ANTHROPIC_API_KEY` reach neither the
harness nor the wrapper.

**To confirm when building:** that Claude Code in Vertex mode works through
`ANTHROPIC_VERTEX_BASE_URL` and the proxy; that the wrapper passes the
runner's stream-json through unchanged, including for resumed sessions; that
rootless podman runs the container on the target hosts; that prepare fits its
900-second hook timeout from a cold cache; and the cost of one trial, to set
the per-case budget.

### Later

- **CI.** An optional `eval-fix-go-cves` Prow job on the shared
  `openshift-claude-agent-eval` workflow, started by hand with `/test` after a
  maintainer reads the PR's whole `plugins/fix-go-cves/` diff (`SKILL.md`, the
  plugin manifest and the case tarballs run there too, beside CI's credentials)
  and checks the head commit just before posting. Before then, the shared
  workflow needs issues filed: it clones the harness at `main`, mounts a GitHub
  token evals do not use, and passes on the agent's exit rather than the
  thresholds. Its `EVAL_CHANGED_ONLY` option skips every case, since the image
  has no `.git`.
- **Cross-agent runs.** Inspect AI with Inspect SWE runs Codex, Gemini CLI and
  others the same way (in a networkless container, model credentials kept on
  the host behind a proxy), for comparing agents. (Harbor was rejected: its
  Podman backend can reach Vertex only by mounting a service-account key into
  the container where the agent's Bash runs, its network setting is all or
  nothing, and its judges run inside the trial container beside the answers.)
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
