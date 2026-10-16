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

**Status:** done in this PR.

`make test` runs every plugin's `test_*.py`, this suite included. Its wrapper
used to skip below Go 1.26; the suite passes on Go 1.24 (1.22 fails four
packed-binary checks), so the floor is now 1.24, and GitHub's `ubuntu-24.04`
runners put Go 1.24 on `PATH` (the Test job uses `ubuntu-latest`, currently
24.04). When `CI` is set, the wrapper fails instead of skipping, so a runner
image without Go cannot silently drop the suite.

That adds about 3 minutes (measured locally) to a job that takes under 1
today, on every PR. If maintainers object, move the suite to a Prow job with
`run_if_changed: ^plugins/fix-go-cves/` rather than add diff logic to the
wrapper.

## 2. Evaluate the skill

**Status:** cases recorded, in `.work/fix-go-cves-evals/source/` until they
are committed; nothing else built.

On release-0.24 the skill found a default-branch backport for a license
failure and traced stdlib findings to the build image, but it also relayed
or misread two verdicts from `review.sh`, and in one run missed the backport.
The cases below cover each; two of the underlying script bugs are under
[Correctness](README.md#correctness).

### Design at a glance

- **Replay, not rerun.** A case replays a recorded `fix-all.sh` run in a
  workspace rebuilt to match it: no build, scan or Docker daemon, so a trial
  takes minutes and costs well under $1.
- **The repository's harness.** agent-eval-harness on its `claude-code`
  runner, run locally, reports cost, tokens and model per case, as a
  maintainer asked for in the review of the k8s-rebase plugin.
- **The recorded plugin, today's skill.** The agent gets the plugin as it
  was when the log was produced; only `SKILL.md`, the thing under test,
  comes from the working tree.
- **A throwaway container for the agent.** The harness and judges stay on
  the host; the agent runs in a per-trial container with no network,
  credentials or host paths, and reaches Vertex through a per-trial proxy.
- **The proxy's log is the record.** The reply, tool calls and cost come
  from the proxy's log of model traffic, which the agent cannot forge.
- **Per-case scoring.** Deterministic checks gate every trial; judged facts
  are binary criteria; every case must pass across three rounds.
- **A calibrated judge.** The scoring prompt must pass each reference reply
  and fail each negative before any agent is scored.
- **A two-tier threat model.** Hard boundaries hold against a hostile agent;
  within its own trial, only opportunistic gaming is guarded against.

### Terms

- **Recording:** the release-0.24 `fix-all.sh` run a case is built from.
- **Recorded log:** that run's log, stored as `run.log.gz`.
- **Trial:** one harness invocation on one case. **Round:** one trial of
  every case.
- **Session:** a trial's conversation, rebuilt from the proxy's log.
- **Preamble:** the replay code placed at the top of the staged
  `fix-all.sh`.
- **Sibling directory:** `<run workspace>/fgc/<case-id>/`, outside the
  harness's `cases/` (whose every directory it scores as a case); it holds
  run state, reports, the log's other home paths and the bare remotes.
  Prepare's baseline hashes and the copy-out archive sit beside it, in
  `fgc/<case-id>.baseline.json` and `fgc/<case-id>.out.tar`, outside the
  copy list.
- **Copy list:** the paths prepare writes for the wrapper to copy into the
  container.
- **Copied-out tree:** the container's volumes, copied out after the trial
  as one tar archive and unpacked only inside the checker container.

Everything lives under `plugins/fix-go-cves/evals/`, laid out like
`plugins/ci/evals/`: `eval-fix-go-cves.yaml`, a `README.md` that indexes the
cases (the repository lint requires it), `run.sh`, `checks.py`,
`workspace.sh`, and `cases/fix-go-cves/case-NNN/`.

### Cases

| Case | Recording | Decision |
| --- | --- | --- |
| 001 | lighthouse: license | Backports devel's cdc3003 |
| 002 | submariner: partial | Relays the PR; names the image owner |
| 003 | cloud-prepare: clean | Flagged lines need no action |
| 004 | subctl: `bin/lichen` | No team decision for the blocked bumps |
| 005 | admiral: govet | Backports devel's 8234df0 |
| 006 | lighthouse: x/crypto | Flag is spurious; backports cdc3003 |

Notes on the cases:

- **004:** the recorded reply found the leftover `bin/lichen` that blocked
  the scan and cleared x/net for a rerun, but still sent grpc and otel/sdk
  to the team, repeating `review.sh`'s "team input". The criterion covers
  all three bumps; the reference reply is written by hand.
- **005:** the recorded reply calls the Go 1.26 raise the team's call; the
  reference drops that claim (see Calibration).
- **006:** a separate, earlier lighthouse run with the same license failure, so
  it also carries 001's backport criterion. Its x/crypto "policy boundary" flag
  was spurious: it followed the ignore of GO-2026-5932, which has no fix, and
  the scan has no x/crypto finding. The criterion passes a reply that says so
  and that x/crypto needs no action, and fails one that blames the Go raise
  (the recorded reply) or sends the flag to the team (a constructed negative).
  The reference reply is written by hand.

Each case directory holds:

- `input.yaml`: repository, pinned commits (base, default branch, and the
  ai-helpers commit that produced the log, for provenance), arguments and
  stub files;
- `annotations.yaml`: criteria, the PR command, commits the reply must
  name;
- `result.bundle`: a git bundle of just the recording's commits;
- `run.log.gz`: the recorded log;
- `reply.md`: the reference reply;
- `negatives/`: the recorded wrong reply, where one exists, one-fact edits
  of the reference, case-specific constructed wrong replies (006's send the
  flag to the team, or blame the Go raise while keeping the backport, since
  the recorded reply also misses the backport), and a wrong reply that tells
  the judge to pass it; each names the criterion it must fail;
- `reports/`: report directories the log names (subctl's);
- `plugin.tar.gz`: the plugin at the recording's commit, limited to
  `.claude-plugin/`, `skills/`, `scripts/`, `subagents/` and `README.md`
  (about 110 KB), since `plans/` would name the answers and the commits live
  only on the PR branch, which a rebase or squash would rewrite.

Files are copied in by allowlist, with home paths stored as placeholders.
Agent transcripts from the recordings stay out: their first record lists the
recording user's connectors, plugins and memory paths.

**Hermetic tests** (in `make test`) fail on:

- no case under `evals/cases/fix-go-cves/`;
- a transcript, or a `/home/` or `/run/user/` path, anywhere there
  (decompressing `.gz` files first);
- a `plugin.tar.gz` holding `plans/`, any case's answer strings, or anything
  but regular files and directories under the five allowed paths (no links,
  absolute or `..` names);
- a plugin manifest (`plugin.json`) with keys beyond `name`, `version`,
  `description` and `author`, since a plugin can declare unsandboxed hooks,
  monitors and language servers;
- a judge defined with `llm_rubric`, or a judge template naming anything
  but the fenced reply file and `{{ annotations }}` (see Builder
  checklist);
- a recorded log missing what `SKILL.md` reads;
- a prepared `.claude/settings.json` with keys beyond `permissions.allow`
  and `permissions.deny`;
- a proxy that forwards a request with a server-side tool, `mcp_servers`,
  `container`, a content `source` other than `base64` or `text`, a beta
  header off its allowlist, or a path or project other
  than the configured model ones;
- a rendered judge prompt whose reply is empty (the harness renders a
  missing key as an empty string);
- an `eval-fix-go-cves.yaml` whose `permissions` hold a path-based rule, or
  that sets a provider plan (the runner would write a settings overlay into
  the workspace at launch, after prepare).

**`checks.py lint`** needs the case repositories' history, from the clone
cache or the network. Run it before committing a case; `run.sh` runs it
first. It runs `workspace.sh prepare` for every case into a scratch run
workspace and checks:

- each bundle's commits, on top of its base, for home paths;
- that every ref and object in a prepared workspace is reachable from the
  pinned commits or the bundle;
- that a prepared workspace has no path outside itself and its sibling
  directory.

**Publication.** The bundles and PR commands keep the recording author's
name and fork. Three bundles (004, 005 and 006) hold commits that were never
pushed, but they contain only `go.mod`, `go.sum` and `.grype.yaml` edits by
the same author, so publishing them adds nothing sensitive.

### Checks and scoring

`checks.py` holds the deterministic checks, which gate at a 1.0 pass rate:

1. **State.** In the copied-out tree: on the fix branch at the recorded
   result, a clean worktree, untracked and ignored files unchanged, bare
   remotes unchanged, an empty `gh` log, no `subagents/` or `input.yaml`
   planted, and no attempted or denied push, `gh`, stash or clean in the
   session. The harness's own files, the paths prepare excludes, are left
   out, and `hooks/` must stay absent.
2. **One run.** The script ran once, for the requested branch.
3. **PR command.** If the recorded log printed one, a code block in the
   reply holds the same command, compared as shell-parsed tokens with
   continuations joined, since logs escape the title and replies quote it;
   otherwise no block holds `gh pr create`.
4. **Commits.** Commits in `annotations.yaml` appear in the reply, matched
   by a prefix of at least seven characters.

The judged facts are binary criteria per case that need reasoning the
recorded log does not hand over, such as "the x/net, grpc and otel/sdk bumps
were skipped because the scan was blocked, and need no team decision". A
pooled threshold would let one case fail every trial while the rest pass, so
`checks.py summarize` requires every case to pass its deterministic checks
in all three rounds and its facts in at least two. `checks.py` reads case
arguments only from the dataset, never from a workspace file the agent could
have written.

### Calibration

`checks.py calibrate` runs the harness's own judges (`score.py judges`) on
synthetic trials whose reply file holds a stored reply, laid out as
`collect.py` lays out a real trial, so the prompt calibrated is the prompt
that scores. It must pass each `reply.md` and fail
each negative on the criterion it names before any agent is scored. The harness
finds criteria by the trial directory's name, so each stored reply is its own
run, under `cases/<case-id>/`, scored with a config holding only the criteria
judges; `calibrate` reads the verdicts from each run's `summary.yaml` and
ignores the exit code, which negatives always fail. Rerun it when criteria or
the judge model change. Criteria stay neutral on whether a Go directive raise
needs the team, because the plugin and the repositories' own workflow notes
disagree (see [Decisions](README.md#decisions)).

### Running

Accept a `SKILL.md` or model change on three rounds. Read failing sessions
before changing anything, since a case can be wrong too, and rerun a failing
case with the old `SKILL.md` before blaming the change. A change to
`scripts/review-prompt.md` or to `fix-all.sh` output is not exercised by
replay: it means re-recording the cases whose logs it changes; for the
review prompt, every case whose log has `UNRESOLVED:` lines (001, 002, 004
and 006).

### Threat model

Two tiers. The host, its credentials and network, other trials and the data
later committed must stay out of reach even of a hostile agent, so the agent
runs in a container that holds none of them. Within its own trial the agent
could still try to game its score: cheap structural guards (state from
checker-owned tooling, the reply and cost from the proxy's record) stop
opportunistic gaming, and reading failing and surprising sessions catches
the rest. A deliberately forged pass on one trial is an accepted risk for a
six-case regression eval of a skill we own.

### Workspace

The harness invokes the skill with the case's arguments (`mode: case`, as in
the repository's other evals) in a case workspace. `workspace.sh prepare`,
the `before_each` hook, turns it into the case repository:

- **Replace the harness scaffolding.** The harness makes the workspace a git
  repository whose first commit holds `input.yaml`, and links ai-helpers'
  `CLAUDE.md`, `scripts/` and every `.claude/` subdirectory into it, which
  would collide with the case repository and expose ai-helpers. Prepare
  removes that `.git`, every link and the subagent hook's `hooks/`
  directory, and deletes `input.yaml` once the harness has read the
  arguments. It rewrites `.claude/settings.json`, which the agent reads at
  launch, keeping only `permissions.allow` and `permissions.deny`: the
  harness also writes the subagent hook (subagents are denied),
  `permissions.additionalDirectories` (the ai-helpers checkout), an `env`
  block resolved from its own environment, tracing variables, carried-over
  hooks and the operator's `enabledPlugins`.
- **Build the repository.** Prepare fetches only the pinned commits, with no
  tags, from a clone cache under ai-helpers' `.work/` (warmed by
  `before_all`) into a fresh repository and fresh bare remotes, so no later
  history is reachable (the merged CVE PRs contain the backports cases 001
  and 005 look for). It checks out the branch the recording started from and
  points every remote at a bare remote whose path ends in the remote's own
  `owner/repo.git`, since the skill checks that `origin` is upstream. It
  creates `origin/<base>` and `origin/<default>` at their pins, which the
  skill and the preamble's tracking branch need. It lists the harness's paths
  (`.claude/`, `.staged-plugins/`, `.hook-outputs.*`) in `.git/info/exclude`,
  since `SKILL.md` stops and asks when the checkout has untracked files.
  `annotations.yaml` never reaches the workspace.
- **Restore what the recording saw.** Untracked files as stubs (for subctl, an
  empty `bin/lichen`; `go version` on it disagrees with the recorded log, so
  criteria rely on the log, not the file), and the case's `reports/` in the
  sibling directory, with the same two placeholders filled as in the log (see
  the next item).
- **Stage the plugin.** Prepare unpacks the case's `plugin.tar.gz`, whose
  entries are the plugin's root, into `.staged-plugins/fix-go-cves`, where
  the runner reuses an existing copy, replaces its `SKILL.md` with the
  working tree's, and adds the recorded log and `result.bundle`. Today's
  scripts carry comments written after the recordings, one of which names
  case 004's answer. `scripts/fix-all.sh`
  keeps its real text behind the preamble, which records its arguments,
  applies the bundle to create the fix branch, prints the recorded log and
  exits with the recorded code, so an agent reading the script still finds
  the gate logic it is investigating. The recorded log stores home paths as
  two placeholders, which the preamble fills: the recording's repository
  root becomes the workspace, and every other home path the sibling
  directory. The log's own `exit=` line is dropped, since `SKILL.md`
  appends one.
- **Record the baseline and the copy list.** Prepare hashes the bare
  remotes and the untracked and ignored files into
  `fgc/<case-id>.baseline.json`, and lists the workspace and the sibling
  directory (which holds the bare remotes) for the wrapper.

### Isolation

- **The agent runs in a throwaway container.** The harness launches
  `claude` by name, so `run.sh` puts a `claude` wrapper first on its `PATH`.
  The wrapper runs the CLI in a per-trial container with no network, no host
  mounts but the proxy's socket, a read-only root filesystem and a non-root
  user, holding only the paths in the copy list. No credential, host path,
  other trial, case answer or network route exists inside it.
- **One way out: the proxy.** A per-trial proxy on the host holds the Vertex
  token, forwards only the Anthropic model paths for the configured project,
  caps tokens per trial (the agent could call it directly), and logs every
  request and response. It rejects, and fails the trial on, a body with a
  server-side tool (web search, web fetch, code execution), `mcp_servers`,
  `container`, a content block whose `source` is a URL or file reference
  (anything but `base64` or `text`), or a beta header off its allowlist,
  since Anthropic's servers would fetch for the agent despite
  `--network none`.
- **No host environment crosses over.** The wrapper sets the container's
  environment from a fixed list, and `run.sh` starts the harness with an
  explicit one, so stray host keys reach neither; the in-container Vertex
  settings stay out of the harness's environment, where they would redirect
  the judges.
- **The copied-out tree is data.** After the trial, the container's volumes
  are copied out as one tar archive, never unpacked on the host, and checked
  in a fresh container from the pinned image,
  with checker-owned git: the agent's git configuration, whose filters and
  diff drivers can run commands, is never used. The host validates the
  result and fails the trial if it is missing or malformed. Nothing the
  agent writes reaches the host any other way.
- **The session comes from the proxy.** The agent shares a user with Claude
  Code inside the container, so it could forge the CLI's output stream. The
  main conversation is the chain of requests in which each request's
  messages extend the previous request's messages and logged response,
  compared after dropping `cache_control` and other per-request annotations
  (role, block type, text, tool-use id, name and input, and tool-result
  content must match): the
  reply is all of the chain's assistant text after the `fix-all.sh` result
  (the replay can finish before the agent's turn ends, so the report and a
  closing message may be separate), and the tool calls and any
  denials the model was told about are its tool turns. A request that fits
  neither the chain nor a known side-call shape (Claude Code's small-model
  helper calls), or arrives after the chain ends, fails the trial. The cost
  reported per case is the proxy's token usage, priced on the host; a large
  gap from the runner's own figure fails the trial.
- **Judges see only the reply.** They read the reply file and the case's
  criteria (`{{ annotations }}`, from the dataset) and nothing else:
  with trace events off, the harness fills `{{ conversation }}` from the raw
  stream, and `llm_rubric` judges append it automatically.

### Builder checklist

- **`run.sh`:** starts the harness under `env -i` with an explicit variable
  list (the runner forwards host keys such as `ANTHROPIC_API_KEY`,
  `GOOGLE_APPLICATION_CREDENTIALS` and `HOME` to the agent); puts the
  wrapper first on `PATH`; runs `checks.py lint` first.
- **Wrapper:** creates per-trial volumes (`podman volume create`) for the
  workspace, sibling directory and `HOME`; `podman create`s
  the container on them from a pinned image (Claude Code at the host's
  version, git, jq, Go, Python, socat and the `gh` shim that only logs its
  arguments) with `--network none`, `--read-only` except those volumes and
  `/tmp`, `--userns=keep-id` (so the user can reach the socket), one Unix
  socket mount, `--http-proxy=false` (podman otherwise copies its own proxy
  variables in), `--interactive` (the runner writes the prompt to stdin), the
  trial's name and a `--timeout` below the runner's; copies in the copy list
  at the same paths, since the runner passes `--plugin-dir` and `--settings`
  as workspace paths; then `exec`s `podman start --attach --interactive`, so
  the runner's pipes close when the agent stops. Answers the runner's
  `claude --version`.
- **Proxy:** started with `setsid`, its output to its own log,
  `fgc/<case-id>.proxy.log`, so it never holds the runner's pipes; listens
  only on the per-trial socket, which socat in the container turns back into a
  local port. Inside the container Claude Code gets
  `CLAUDE_CODE_SKIP_VERTEX_AUTH=1` and `ANTHROPIC_VERTEX_BASE_URL` pointing at
  that port, a pattern the runner already supports for agentic-ci.
- **`after_each`:** timeout of 600 seconds; kills the container and the proxy
  (the runner's timeout kills only the wrapper), streams the volumes out with
  `podman cp <ctr>:<path> -` into `fgc/<case-id>.out.tar`, never unpacked on
  the host (host git, a shell prompt or an editor in an agent-written tree
  could run its configuration), runs the state check in a fresh container from
  the pinned image, with the archive and the baseline mounted read-only, the
  archive unpacked inside it, its result written to a separate fresh mount,
  and no network, writes the validated result (including the preamble's record
  of its arguments), and from the proxy log the session's reply, its tool
  calls and denials, and its token usage, into declared `outputs:` directories
  (`collect.py` treats a declared path as a directory, so the reply is
  `fgc-out/reply.md` both in the trial and as the judges' key), outside the
  `output/` directory where the harness drops `stdout.log`, and removes the
  container, volumes and archive.
- **State check:** builds a fresh `.git` from the copied objects, refs and
  `HEAD`, with a configuration it writes itself and no attributes; runs git
  with `-c core.fsmonitor=false -c core.hooksPath=/dev/null` and system and
  global configuration off; compares the worktree to HEAD by hashing files
  without filters; compares the bare remotes and untracked and ignored
  files with prepare's baseline hashes.
- **Judges:** defined with `prompt` or `prompt_file`, never `llm_rubric`;
  templates name the reply only as `{{ outputs.files['fgc-out/reply.md'] }}`,
  which the harness fences as untrusted, with no filters (a string filter
  drops the fence), plus `{{ annotations }}`; never `*_content`,
  `outputs[...]`, `{{ conversation }}`, `{{ tool_trace }}` or
  `{{ reasoning }}`.
- **Eval `permissions.deny`:** plain tool patterns blocking
  `Bash(git push:*)`, `Bash(gh:*)`, MCP tools, web tools and subagents, so
  check 1 has denials to find; no provider plan. Either path-based rules or
  a plan would make the runner write a settings overlay, one form of which
  holds the inference key, into the workspace.
- **Prepare:** `before_all` (which warms the clone cache) and `before_each`
  timeouts of 900 seconds, for a cold clone, since hooks default to 120;
  unpacks with Python's `tarfile` and `filter="data"`.

### To confirm when building

- Claude Code in Vertex mode works through `ANTHROPIC_VERTEX_BASE_URL` and
  the proxy.
- The wrapper passes the runner's prompt through on stdin and its
  stream-json back unchanged, including for resumed sessions.
- The reply and tool calls can be read back from the proxy's log of
  streamed responses, and one real recorded session links into a single
  chain under the normalised comparison.
- Rootless podman runs the container on the target hosts, and the container
  user can connect to the proxy socket under `--userns=keep-id`.
- `before_all` fits its 900-second timeout from a cold cache.
- The cost of one trial, to set the per-case budget.

### Later

- **CI.** An optional `eval-fix-go-cves` Prow job on the shared
  `openshift-claude-agent-eval` workflow, started by hand with `/test` after
  a maintainer reads the PR's whole `plugins/fix-go-cves/` diff (`SKILL.md`,
  the plugin manifest and the case tarballs run there too, beside CI's
  credentials) and checks the head commit just before posting. Before then,
  the shared workflow needs issues filed: it clones the harness at `main`,
  mounts a GitHub token evals do not use, and passes on the agent's exit
  rather than the thresholds. Its `EVAL_CHANGED_ONLY` option skips every
  case, since the image has no `.git`.
- **Cross-agent runs.** Inspect AI with Inspect SWE runs Codex, Gemini CLI
  and others the same way (in a networkless container, model credentials
  kept on the host behind a proxy), for comparing agents. Harbor was
  rejected: its Podman backend reaches Vertex only by mounting a
  service-account key into the container where the agent's Bash runs, its
  network setting is all or nothing, and its judges run inside the trial
  container beside the answers.
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
