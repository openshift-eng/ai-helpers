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

**Status:** done in this PR. `make test` runs the suite on Go 1.24 or later
(GitHub's `ubuntu-24.04` runners have it) and fails rather than skips when
`CI` is set. It adds about 3 minutes per PR; if maintainers object, move it
to a Prow job with `run_if_changed: ^plugins/fix-go-cves/`.

## 2. Evaluate the skill

**Status:** six cases recorded, in `.work/fix-go-cves-evals/source/` until
committed; nothing else built.

On release-0.24 the skill found a default-branch backport for a license
failure and traced stdlib findings to the build image, but it also relayed
or misread two verdicts from `review.sh`, and in one run missed the
backport. The cases cover each; two of the underlying script bugs are under
[Correctness](README.md#correctness).

### Design

- **Replay, not rerun.** A case replays a recorded `fix-all.sh` run in a
  workspace rebuilt to match it: no build, scan or Docker, so a trial takes
  minutes and costs well under $1.
- **The repository's harness.** agent-eval-harness on its `claude-code`
  runner reports cost, tokens and model per case, as a maintainer asked for
  in the k8s-rebase review. Files live in `plugins/fix-go-cves/evals/`,
  laid out like `plugins/ci/evals/`.
- **The recorded plugin, today's skill.** The agent gets the plugin as it
  was when the log was recorded; only `SKILL.md`, the thing under test,
  comes from the working tree. Today's scripts carry comments written after
  the recordings, one naming case 004's answer.
- **The agent in a throwaway container.** The harness and judges stay on the
  host. The agent runs in a per-trial container with no network,
  credentials or host paths, and reaches Vertex only through a per-trial
  host proxy that holds the token.
- **Two-tier threat model.** Hard boundaries (the host, its credentials and
  network, other trials, the committed answers) hold against a hostile
  agent. Within its own trial, checker-owned state checks stop
  opportunistic gaming and reading surprising sessions catches the rest; a
  deliberately forged pass on one trial is an accepted risk for a six-case
  regression eval of a skill we own.
- **Per-case scoring, calibrated judges.** Deterministic checks gate every
  trial, binary judged criteria cover the decisions, and every case must
  pass on its own. The judges must pass each reference reply and fail each
  negative before any agent is scored.

### Build first

Run one case end to end before building the rest; each unknown here could
change the isolation design:

- Claude Code in Vertex mode works through `ANTHROPIC_VERTEX_BASE_URL`
  (with `CLAUDE_CODE_SKIP_VERTEX_AUTH=1`, as the runner supports for
  agentic-ci) and the proxy;
- the wrapper passes the runner's stdin prompt in and its stream-json out
  unchanged, including for resumed sessions;
- rootless podman runs the container, and its user reaches the proxy
  socket under `--userns=keep-id`;
- a cold clone fits the hook timeout;
- the cost of one trial, to set the per-case budget.

### Cases

| Case | Recording | Decision |
| --- | --- | --- |
| 001 | lighthouse: license | Backports devel's cdc3003 |
| 002 | submariner: partial | Relays the PR; names who decides the image |
| 003 | cloud-prepare: clean | Flagged lines need no action |
| 004 | subctl: `bin/lichen` | No team decision for the blocked bumps |
| 005 | admiral: govet | Backports devel's 8234df0 |
| 006 | lighthouse: x/crypto | Flag is spurious; backports cdc3003 |

- **004:** the recorded reply found the leftover `bin/lichen` that blocked
  the scan and cleared x/net for a rerun, but still sent grpc and otel/sdk
  to the team, repeating `review.sh`. The criterion covers all three bumps.
- **005:** the recorded reply calls the Go 1.26 raise the team's call; the
  reference drops that claim.
- **006:** an earlier lighthouse run with the same license failure, so it
  also carries 001's backport criterion. Its x/crypto "policy boundary"
  followed the ignore of GO-2026-5932, which has no fix, and the scan has no
  x/crypto finding: the criterion passes a reply that says x/crypto needs no
  action, and fails one that blames the Go raise or sends it to the team.
- References for 004 and 006 are hand-written, since their recorded replies
  are the wrong ones.

Each case directory holds `input.yaml` (repository, pinned base and default
commits, arguments, stubs), `annotations.yaml` (criteria, PR command,
commits to name, flagged items), `result.bundle` (the recording's commits),
`run.log.gz`, `reply.md` (the reference), `negatives/` (each naming the
criterion it must fail), `reports/`, and `plugin.tar.gz` (the recorded
plugin, limited to `.claude-plugin/`, `skills/`, `scripts/`, `subagents/`
and `README.md`, since `plans/` names the answers). Home paths are stored as
placeholders. Recording transcripts stay out: their first record lists the
recording user's connectors, plugins and memory paths. The bundles keep the
recording author's name and fork; the three never pushed (004, 005, 006)
hold only `go.mod`, `go.sum` and `.grype.yaml` edits.

### Scoring

Deterministic checks (`checks.py`) gate every trial:

1. **State.** On the fix branch at the recorded result, a clean worktree,
   bare-remote refs at their pins, untracked and ignored files equal to the
   case's stubs plus the harness's excluded paths, an empty `gh` log, and
   no attempted or denied push, `gh`, stash or clean.
2. **One run.** The script ran once, for the requested branch.
3. **PR command.** If the log printed one, a code block in the reply holds
   the same command, compared as shell tokens (logs escape the title,
   replies quote it); otherwise no block holds `gh pr create`.
4. **Commits.** The annotated commits appear in the reply, by a prefix of at
   least seven characters.

Judged facts are binary criteria needing reasoning the log does not hand
over, such as "the x/net, grpc and otel/sdk bumps were skipped because the
scan was blocked, and need no team decision". One more per case requires
every flagged item to get an action and an owner, so a reply cannot pass on
its headline alone. Criteria stay neutral on whether a Go directive raise
needs the team, since the plugin and the repositories' workflow notes
disagree (see [Decisions](README.md#decisions)).

- One boolean judge per criterion (`feedback_type: bool`, `samples: 3`,
  majority vote), reading only the fenced reply and `{{ annotations }}`.
- A trial passes its facts only if every criterion passes. A case passes
  with its deterministic checks in three of three rounds and its facts in
  at least two; a pooled rate would hide a case that always fails.
- A missing, skipped or errored verdict, or a failed harness stage
  (recorded by `after_each`), is ERROR: rerun, never counted as a pass or a
  failure. Harness thresholds pair `min_pass_rate: 1.0` with
  `max_error_rate: 0`, since the pass rate leaves errored trials out.
- Accept a `SKILL.md` or model change on three rounds. Rerun a case at two
  of three three more times, and read failing sessions before blaming the
  change, since a case can be wrong too.
- The cases helped tune `SKILL.md` (its license wording came from 001 and
  006), so they guard against regressions, not prove the skill generalizes.

**Calibration.** `checks.py calibrate` runs the harness's own judges on
synthetic trials holding each stored reply, laid out as real trials, so the
prompt calibrated is the prompt that scores. Every reference must pass and
every negative fail on its named criterion, with stable verdicts across
samples. The negatives include one-fact edits of each reference, the
recorded wrong replies, and a reply that tells the judge to pass it. The
first baseline round's replies are labelled by hand and the correct ones
added as positives. Rerun calibration when criteria, the judge model or a
recording change.

**Re-recording.** Replay does not exercise `scripts/review-prompt.md` or
`fix-all.sh` output; changing either means re-recording the affected cases
(for the review prompt, those with `UNRESOLVED:` lines: 001, 002, 004,
006). The Grype database, build image and the bugs a case depends on are
not pinned, so a new recording replaces a case only if it reproduces the
case's decision; then regenerate its commits, PR command, reference and
negatives, and recalibrate.

### Guards

**Workspace** (`workspace.sh prepare`, the `before_each` hook):

- fetches only the pinned commits, with no tags, into a fresh repository and
  fresh bare remotes, since later history holds the answers for 001 and
  005; remote paths end in `owner/repo.git` and `origin/<base>` and
  `origin/<default>` exist, since the skill checks both;
- removes the harness's `.git`, links into ai-helpers, `hooks/` and
  `input.yaml`, and rewrites `.claude/settings.json` to keep only
  `permissions` (the harness also writes host paths, env and the
  operator's plugin list there);
- lists the harness's paths in `.git/info/exclude`, since `SKILL.md` stops
  on untracked files;
- stages the recorded plugin with today's `SKILL.md`, and a preamble in
  `fix-all.sh` that applies the bundle, prints the log with placeholders
  filled, and exits with the recorded code; the real script text stays
  below it for an agent that reads it;
- restores stubs (subctl's empty `bin/lichen`, which contradicts the log,
  so criteria rely on the log) and reports outside `cases/`, which the
  harness scores directory by directory.

**Isolation:**

- `run.sh` starts the harness under `env -i` and puts a `claude` wrapper
  first on `PATH`; the wrapper builds the container's environment from a
  fixed list, so no host key (the runner forwards `HOME`,
  `GOOGLE_APPLICATION_CREDENTIALS`, `ANTHROPIC_API_KEY`) crosses over.
- The container runs from a pinned image with `--network none`,
  `--read-only` but its volumes, a non-root user, `--http-proxy=false`, and
  no mount but the proxy socket. Only the wrapper's final `exec` touches the
  runner's pipes.
- The proxy forwards only the configured project's main model and one
  pinned small model, caps tokens, logs usage, and rejects server-side
  tools, `mcp_servers`, `container`, URL or file content sources and
  unlisted betas, since Anthropic's servers would fetch for the agent.
  Reported cost is the proxy's usage, priced on the host.
- The runner's timeout kills only the wrapper, so `after_each` stops the
  container and proxy, then runs the state check in a fresh container that
  mounts the trial's volumes read-only and uses checker-owned git (no agent
  configuration, hooks, fsmonitor or filters). No agent-written file is
  unpacked on the host. Leftovers are labelled and swept by `before_all`.
- The eval's `permissions.deny` blocks `git push`, `gh`, MCP, web tools and
  subagents with plain patterns and no provider plan; either would make the
  runner write a settings overlay holding the inference key into the
  workspace.
- Judges get the reply only through `{{ outputs.files[...] }}` with no
  filters, which the harness fences as untrusted, never `llm_rubric` or
  `{{ conversation }}`. A `before_scoring` hook extracts the reply (all
  assistant text after the `fix-all.sh` result) from `stdout.log`.
- Hooks default to a 120-second timeout; `before_all` and `before_each` get
  900 for a cold clone, `after_each` 600.

**Hermetic tests** (in `make test`) fail on: no cases; a transcript or a
`/home/` or `/run/user/` path in a case, `.gz` included; a plugin tarball
holding `plans/`, answer strings, links or paths outside the five allowed;
a plugin manifest with keys beyond `name`, `version`, `description` and
`author` (a plugin can declare unsandboxed hooks); a judge using
`llm_rubric`, `condition` instead of `if`, a non-bool criterion, or a
template naming anything but the fenced reply and `{{ annotations }}`; an
empty rendered reply; a recorded log missing what `SKILL.md` reads; a
prepared `settings.json` with keys beyond `permissions`; an eval with
path-based permissions or a provider plan; and a proxy that forwards any
request it must reject.

**`checks.py lint`** (before committing a case, and first in `run.sh`)
prepares every case and checks that bundles hold no home paths, every ref
and object is reachable from the pins or the bundle, nothing points outside
the workspace and its run state, and every criterion has a judge.

### Later

- **CI.** An optional Prow job on the shared `openshift-claude-agent-eval`
  workflow, started by hand after a maintainer reads the PR's whole plugin
  diff, once issues are filed against that workflow (it clones the harness
  at `main`, mounts an unused GitHub token, and ignores thresholds).
- **Cross-agent runs.** Inspect AI with Inspect SWE runs Codex, Gemini CLI
  and others in the same networkless, proxied shape. Harbor was rejected:
  its Podman backend mounts a service-account key where the agent runs.
- **`review.sh` cases**, if a review mistake appears that replay cannot
  catch.

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
