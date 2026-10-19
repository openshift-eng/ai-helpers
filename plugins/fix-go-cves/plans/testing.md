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
regression test, and a skill mistake gets an eval case.

## 1. Run the suite in CI

**Status:** done in this PR. `make test` runs the suite, requires Go 1.24 or
later, and fails rather than skips when `CI` is set. The workflow uses
`ubuntu-latest` without an explicit Go setup. The suite takes a few minutes;
if maintainers object, move it to a Prow job with
`run_if_changed: ^plugins/fix-go-cves/`.

## 2. Evaluate the skill

**Status:** six recordings in `.work/fix-go-cves-evals/source/`; case packaging
and corrected references remain unfinished. No eval runner or checks are built.
The rest of this section describes proposed work.

On release-0.24 the skill found a default-branch backport for a license
failure and traced stdlib findings to the build image, but it also relayed
or misread two verdicts from `review.sh`, and in one run missed the
backport. The cases cover each; two of the underlying script bugs are under
[Correctness](README.md#correctness).

### Design

- **Replay, not rerun.** A case replays a recorded `fix-all.sh` run in a
  workspace rebuilt to match it, avoiding the full build, scan and Docker run.
  Measure trial time and cost in the pilot.
- **The repository's harness.** agent-eval-harness on its `claude-code`
  runner reports cost, tokens and model per case, as a maintainer asked for
  in the k8s-rebase review. Files live in `plugins/fix-go-cves/evals/`,
  laid out like `plugins/ci/evals/`.
- **The recorded plugin, today's skill.** The agent gets the plugin as it
  was when the log was recorded; only `SKILL.md`, the thing under test,
  comes from the working tree. Today's scripts carry comments written after
  the recordings, one naming case 004's answer.
- **The stock runner.** Permissions and state checks limit or detect expected
  mistakes; they do not isolate host files or credentials. Use trusted code
  and inspect unexpected sessions. Strong isolation belongs in the shared
  harness rather than a custom runner for this plugin.

### Build first

Start with **005 (admiral)**: one recorded fix commit, no printed PR command,
and no binary-stub inconsistency. The default-branch pin contains backport
`8234df0`; correct the reference's rerun advice before using it.

Build one fixture, stock harness YAML and only the preparation, extraction and
checks it needs. Dry-run preparation and replay without models, builds or scans.
Then run one trial and the actual judges on the corrected reference and one
negative that misses the backport. Check loaded script hashes and skill, per-case
environment, exactly one replay, retained result state, final-reply extraction
and complete judge samples. Record harness revision, cost and time, including
whether a cold clone fits 900-second setup hooks (default 120).

A failed factual verdict can still prove the plumbing works: inspect and retain
that reply, rather than rerunning until it passes. Package more cases and apply
the three-round acceptance rule only after this pilot. Runtime correctness fixes
need their own regressions; this replay is not their prerequisite or validation.
The integration details below were checked
against [agent-eval-harness at `1a980e7`](https://github.com/opendatahub-io/agent-eval-harness/tree/1a980e7);
verify them at the harness revision used for the pilot.

### Cases

| Case | Recording | Decision |
| --- | --- | --- |
| 001 | lighthouse: license | Recommends devel's cdc3003 backport |
| 002 | submariner: partial | Relays the PR; names who decides the image |
| 003 | cloud-prepare: clean | Flagged lines need no action |
| 004 | subctl: `bin/lichen` | No team decision for the blocked bumps |
| 005 | admiral: govet | Recommends devel's 8234df0 backport |
| 006 | lighthouse: x/crypto | Flag is spurious; recommends cdc3003 backport |

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
- Write corrected references for 004 and 006. Also correct 001 and 005's
  fix-branch cherry-pick followed by rerun: reruns start at `origin/<branch>`,
  so the backport must reach the target branch before rerunning.

Each case directory holds `input.yaml` (repository, the base and default-branch
commits it starts from, called pins, arguments, and stubs: untracked files
the recording's checkout had), `annotations.yaml` (criteria, PR command,
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
  with its deterministic checks in three of three rounds (a round is one
  trial of every case) and its facts in at least two; a pooled rate would
  hide a case that always fails.
- A missing, skipped or errored verdict, or a failed or unrecorded harness
  stage (checks 1 to 4 raise when the state record is missing or
  malformed), is ERROR: rerun, never counted as a pass or a failure.
  Inspect sample counts and `stability.error_count`: the harness can report
  PASS from one surviving sample when the other two error, which
  `max_error_rate: 0` alone does not catch. Require all requested samples.
- Apply `min_pass_rate: 1.0` to deterministic checks and `max_error_rate: 0`
  to harness errors. Harness thresholds pool cases by judge; initially inspect
  saved results manually for the per-case, three-round fact rule above.
- Accept a `SKILL.md` or model change on three rounds. A case at exactly
  two of three on facts gets three more trials each on the old and new
  configuration, and the change is accepted only if the new one does no
  worse. Read failing sessions before blaming the change, since a case can
  be wrong too.
- The cases helped tune `SKILL.md` (its license wording came from 001 and
  006), so they guard against regressions, not prove the skill generalizes.

**Calibration.** Before trusting scores, run the actual judge prompts on
the corrected references and negatives. Each reference must pass and each
negative fail its named criterion, without sample errors. Include one-fact
edits, the recorded wrong replies and a reply that asks the judge to pass it.
Inspect the first baseline replies by hand. Automate repeated calibration only
after the pilot works; repeat it when criteria, judge model or fixtures change.

**Historical coverage.** Replay does not exercise today's scripts or review
prompt. Keep useful historical cases when those change; add current-output
recordings when a new interpretation failure warrants one. Revise an old case
only when its expected skill behavior changes or its evidence is wrong.
The live Grype database and build images are not pinned, so a new recording
need not reproduce an old failure. Recheck references, commits, PR command and
judge calibration whenever a fixture changes.

### Guards

**Workspace** (`workspace.sh prepare`, the `before_each` hook):

- fetches only the pinned commits, with no tags, into a fresh repository and
  fresh bare remotes, since later history holds the answers for 001 and
  005; remote paths end in `owner/repo.git` and `origin/<base>` and
  `origin/<default>` exist, since the skill checks both;
- removes the harness's `.git`, its links into ai-helpers and `input.yaml`,
  which would collide with the case repository;
- copies in nothing from the case directory but the plugin, bundle, log,
  stubs and reports, so `annotations.yaml`, `reply.md` and `negatives/`
  never reach the workspace;
- lists the harness's paths in `.git/info/exclude`, since `SKILL.md` stops
  on untracked files;
- prepopulates `.staged-plugins/fix-go-cves`, which the stock runner reuses,
  with the recorded plugin, today's `SKILL.md`, and a preamble in
  `fix-all.sh` that applies the bundle, prints the log with placeholders
  filled, and exits with the recorded code; the real script text stays
  below it for an agent that reads it;
- restores stubs in the replay checkout and reports outside `cases/`, which
  the harness scores directory by directory. Resolve subctl's empty `bin/lichen`
  contradicting its log before admitting the case; preserve enough captured
  evidence for the diagnosis without requiring a live build.

**Isolation:**

- `before_each` creates a fresh `TMPDIR` and `HOME` and supplies them through
  the harness's hook-output environment, plus a `gh` shim that logs its arguments.
  An environment set once by `run.sh` would be shared across cases. This avoids
  default discovery of user configuration; it does not block host-file access.
- `runner.env` sets `GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`,
  `GIT_ALLOW_PROTOCOL=file`, `GOPROXY=off` and `GOTOOLCHAIN=local` to disable
  ordinary git and Go network fetches; these are not an egress sandbox.
- The eval's `permissions.deny` blocks `git push`, `gh`, MCP, web tools and
  subagents, so check 1 has denials to find.
- Model credentials remain readable, and the stock runner grants project-root
  access. Check 1 also fails detected reads of the ai-helpers checkout, where
  the answers live; this detects leakage rather than enforcing file isolation.
- Judges get the reply only through `{{ outputs.files[...] }}` with no
  filters, which the harness fences as untrusted, never `llm_rubric` or
  `{{ conversation }}`. The global `before_scoring` hook iterates case outputs
  and parses each JSON event log for the final completed `result`, excluding
  progress commentary. Missing or errored final results are ERROR.

**Hermetic tests** (in `make test`) cover case-content, tarball and judge-template
rules without a trial. They also fail on no cases, an empty rendered reply,
a recorded log missing what `SKILL.md` reads,
and a plugin manifest with keys beyond `name`, `version`, `description` and
`author` (a plugin can declare unsandboxed hooks).

**Fixture checks** (before committing a case, and first in `run.sh`) prepare
each case, validate its refs and paths, and check that each criterion has a
judge. Add only checks needed to establish the replay contract above.

### Later

- **CI.** An optional Prow job on the shared `openshift-claude-agent-eval`
  workflow, started by hand after a maintainer reads the PR's whole plugin
  diff and checks the head commit just before posting, once issues are filed
  against that workflow (it clones the harness at `main`, mounts an unused
  GitHub token, and ignores thresholds).
- **Container isolation.** A per-trial networkless container whose model
  credentials stay on the host behind a proxy, for CI or untrusted changes;
  better added to agent-eval-harness than built here.
- **`review.sh` cases**, if a review mistake appears that replay cannot
  catch.

## 3. Optional: live canary

Run `scripts/report.sh` weekly on one fast repository (Shipyard `devel`) on
a runner with Docker, after fixing report validation and scanner deadlines
([Operations](README.md#operations)). It needs no model and should fail on
incomplete scans, never on findings. It can catch drift no recorded case can: Grype
schema or database changes, new Go releases, builder-image changes. Several
release-0.24 failures were drift of this kind.

## Not planned

- Evals that run the full fix: they take hours and need Docker, and the
  canary and live runs cover end-to-end behavior.
- A with/without-skill comparison: without the skill, nothing runs the
  scripts.
- An eval of the LLM verification layer: the recorded runs already settle
  it (see [Decisions](README.md#decisions)).
