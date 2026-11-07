<!-- markdownlint-disable MD013 -->
# Rebase Rules

Read this file at the start of every step.

## Runtime context

Use the absolute plugin root derived from the loaded skill, target repo root,
requested version, and tools flag supplied by the caller. Bind the variables
needed by each shell example in that command call; prior exports and cwd
changes are not a contract. Run repo-level commands at `REPO_ROOT`, and
module-local operations in their module. Keep the session itself rooted at
the checkout so the existing hook guards remain active.

Resolve the baseline with the shared helper, never a guessed `HEAD~N` or a
hardcoded branch name:

```bash
BASE=$(bash "$PLUGIN_ROOT/scripts/resolve-rebase-base.sh" "$REPO_ROOT") || exit 1
```

Step 1 records `.rebase-tmp/base-commit` before changing dependencies. The
helper validates that record against HEAD and supports release branches when
recovering older runs. Bind BASE again in each shell call that needs it.
If resolution fails, retain the error and report unresolved scope; never
substitute an arbitrary ancestor or claim a zero-issue diff.

## Scope

Every change must be required by the requested rebase: dependency alignment,
codegen, version references, or a fix the bump makes necessary. For any fix,
ask: would build, vet, lint, tests, or CI fail without it? If not, do not
make the change. Broader tooling updates require `--bump-tools`. Do not
refactor, add features, or fix unrelated debt. Fix ONLY the cited issue at
the cited location.

Preserve behavior: never replace label selectors with
`reflect.DeepEqual`, never change security flag defaults.
Preserve nil semantics: `*int32` nil means "server default",
`int32` zero means "set to 0" — use `ptr.To[int32](val)`.
Adapt type signatures without altering surrounding logic.
Verify the issue against base, including its dependencies and configuration;
unchanged source alone does not establish that a failure is pre-existing:
`BASE=$(bash "$PLUGIN_ROOT/scripts/resolve-rebase-base.sh" "$(git rev-parse --show-toplevel)") || exit 1; git show "$BASE:<file>"`

Do not add struct tags (like omitempty), merge functions, rename
interfaces, or restructure packages.

## Module Safety

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go mod edit`,
`go generate`, or `go run` directly: they can move Kubernetes pins through
MVS. Allowed: `go build`, `go vet`, `go test` (with `-mod=vendor` if vendor/
exists), `go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`.

Module repairs use `scripts/k8s-rebase-depfix.sh` in each affected module:
`<module>@<version>` bumps one dependency; `--sync` tidies (and vendors, when
vendor/ exists) after you add a `replace`. Both modes synchronize the module,
so do not repeat it. Verify Kubernetes pins afterward; the helper does not.

Prepend this rule to every gate subagent prompt. Suggested fix commands in
a gate report do not expand these permissions. The module-operation hook
enforces the direct-command ban; never disguise a command to bypass it.

## Never Push

NEVER run `git push` or `gh pr create`. Only print commands for
the user to copy-paste.

## Verdicts

Each gate report carries exactly one verdict:

| Verdict | Meaning | Normal advancement |
| --- | --- | --- |
| PASS | The check ran to completion and found no new issues | Accepted when fresh |
| SKIP | The check does not apply to this repo; the summary says why | Accepted when fresh |
| FAIL | The check found new issues | Blocks |
| INCONCLUSIVE | The check applies but could not be completed or attributed | Blocks |

A check that did not run is INCONCLUSIVE, never PASS or SKIP: missing
coverage is not a zero count. Pre-existing findings are INFO, not FAIL,
unless the gate's rubric says otherwise.
The informational commit-messages and skill-improvement gates always PASS
and carry their findings in DETAILS. Never relabel a SKIP as PASS.
Include this section in every gate reviewer's context.

## Gate-Fix Loop

1. Run `bash "$PLUGIN_ROOT/scripts/k8s-rebase-orchestrator.sh" gates "$REPO_ROOT" <step>`.
   It executes companions and identifies PENDING reviews. Exit 1 with normal
   PENDING output means judgments remain; unexpected errors stop the caller.
   Exit 0 means none pending, not all passed: inspect EXISTING and RESOLVED
   verdicts too. Read exact reports; the status table counts SKIP under PASS.
2. Read each pending prompt and its evidence. Check evidence HEAD against
   the current commit; missing/stale evidence after a companion crash is not
   usable. Gather fresh read-only evidence as that prompt permits, or report
   inability to judge. Use a native gate worker when available, otherwise
   review inline under the same read-only constraints only if no worker tool
   is exposed. Give each gate a separate bounded task; wait for its completion
   before starting the next worker. Pass the exact gate-file path, these rules,
   and raw evidence. Require reading the complete gate; a shortened task prompt
   must not replace its scope or criteria. Do not propose a verdict.
   A separate bounded ordinary gate task need not create a new agent thread.
   When native capacity is limited, reuse an idle ordinary worker through a
   bounded follow-up with the complete current gate, rules, revision, and raw
   evidence. Verify its earlier producers are finished first. Reserve fresh
   contexts for Steps 4–5 independent reviews; a reused ordinary worker cannot
   replace those reviewers. If fresh review capacity is unavailable, preserve
   state and stop at that boundary for a same-checkout continuation.
   Resource limits require sequential delegation, not
   replacing available workers with parent self-review.
3. Write reports through `scripts/write-gate-report.sh` at the known plugin
   root. Confirm HEAD has not changed during review before it stamps the
   report. Choose one actual verdict; `PASS|FAIL` is notation, not a
   shell pipeline. A missing helper is an error, not grounds to fabricate
   an unstamped report.
   Before accepting a report, compare its coverage with the gate prompt.
   A fresh stamp only establishes the reviewed SHA. Missing required source
   URLs/ranges, incomplete scans, or unexecuted applicable checks require
   further evidence or INCONCLUSIVE; they cannot support PASS.
   Verify file:line citations against the numbered retained source bytes,
   including external files. Do not reuse line numbers from another revision.
4. Triage findings against base under Scope. For INCONCLUSIVE, gather the
   missing evidence before deciding on an edit. An expected version or stream
   is not proof that its image exists: if registry access prevents verification,
   retain the existing reference and report the blocker. Changing it to the
   unverified candidate does not resolve the finding.
   Fix established in-scope issues and commit before refreshing evidence.
   Re-validate as the step requires (`--quick` in 2–3,
   `--no-test` in 4), then run `gates` again. Every current-step report at the
   old HEAD is stale, including PASS reports: complete all newly pending
   reviews, not just the previously failing ones.
   Leave prior-step reports at their actual reviewed SHAs. Later commits do
   not authorize restamping them; changing a prior report's HEAD requires
   recollecting its evidence and performing that review again.
5. For deliberate recollection at the **same HEAD**, or after a companion
   crash, first resolve the cause and have the parent run
   `bash "$PLUGIN_ROOT/scripts/k8s-rebase-orchestrator.sh" retry-gate "$REPO_ROOT" <gate-name>`.
   Use the short gate name in the current step, for example `autofix-result`
   in Step 3, not `step3-autofix-result` or a `.report`/`.md` filename.
   This retains the previous report/evidence/crash under `.rebase-tmp/gate-retries/`
   and clears that current gate's active report, evidence, and crash marker. Then rerun
   `gates` and review the new evidence within the existing retry budget.
   Do not invalidate a newly regenerated report or a prior-step report.

Use each gate's rubric for its verdict and issue count. Preserve out-of-scope
findings in report details; deciding not to fix them does not itself make a
failed check pass.

Repeat fixes/reviews up to 3 iterations, sharing this budget across workers
and parent; do not nest another retry loop at handoff. Preserve the step's
stop condition (Step 1 structural failure stops). The parent alone calls
`advance` and handles its retry/force-advance output as in SKILL.md. Workers
return verdicts, unresolved issues, and attempts already used. Never call a
gate passed until a fresh report says PASS, and never spend advances as
status polls.
For Steps 2–4 only, if the fix budget is exhausted, the parent may retry a
BLOCKED handoff to reach the existing force-advance threshold. Step 1
structural failures must not call `advance`, even to record the failure.
Do not add another fix loop, overwrite non-PASS findings, or retry after
state has already advanced.

## Never Add Test Skips

If a test fails, fix the root cause. Adding `t.Skip()` hides
real issues. If pre-existing, note in the commit message but
do not skip it.

## Commits and Git

- Body lines <= 72 chars.
- Each commit gets exactly one `Signed-off-by` and one `Assisted-by` trailer
  identifying the session's host: `Codex <noreply@openai.com>` or
  `Claude Code <noreply@anthropic.com>`. Bind and export `AI_TRAILER` to the
  complete matching trailer in each shell call that runs the rebase/autofix
  scripts; they preserve that value and default to Claude for existing callers.
  For your commits use `git commit -s --trailer "$AI_TRAILER"` after binding it.
  For multiline messages, write real newlines to a message file under
  `.rebase-tmp/`, then use `git commit -s --trailer "$AI_TRAILER" -F "$MESSAGE_FILE"`.
  Quoted literal `\n` sequences do not create message paragraphs.
  Attribution does not select the independent-review path; use host context.
- Do not amend — create new commits on top.
- No `org/repo#N` in commit messages.
- If adding a `replace` directive, add a TODO comment.
- One commit per distinct fix. Don't bundle unrelated changes.
- Each commit should compile independently (`go build ./...`).
- Read CONTRIBUTING.md for the project's commit prefix convention.
  Use specific sub-component names matching the code you changed
  (e.g., `e2e:`, `hybrid-overlay:`).

## Container Commands

Prefer `podman` with `--userns=keep-id --security-opt label=disable`.
Tell subagents to use `podman run --userns=keep-id` with the
golang container if they need Go tools.
Carry the user's CPU/memory limits into container arguments explicitly;
host `GOMAXPROCS`/`GOFLAGS` are not inherited automatically. When a repository
launcher does not forward them, use its supported runtime/options override
or reproduce its container invocation with explicit `-e` arguments. Retain
the actual invocation and report any limit that could not be enforced.
The validation helper accepts optional `K8S_REBASE_CONTAINER_MEMORY`,
`K8S_REBASE_CONTAINER_MEMORY_SWAP`, and `K8S_REBASE_CONTAINER_CPUS` bounds.
Memory-swap is the combined memory-plus-swap budget; setting it equal to
memory disables additional swap. Rootless Podman may use a separate scope:
verify that container's actual cgroup limits rather than inferring them from
its parent. A configured host `TMPDIR` must exist; the helper mounts that
same disk-backed directory at `/task-tmp` to leave room for Unix socket names.
This mapping changes the container path, not the scratch storage medium.

## Feature Gates

SetFromMap validates parent-dependent consistency. Disable each gate with
its dependents in every mechanism the repo uses: `KUBE_FEATURE_` exports,
`Setenv` calls, and SetFromMap. The autofix wires this; never remove gates
from its SetFromMap.

## Execution and reviewer roles

- Shell guards can reject harmless quoted documentation containing module or
  publish commands. Retain such text with the host's file-edit tool or pass it
  as native worker input; use the verified report helper for gate reports.
  Keep executable module operations in the authorized helpers, and present
  publish commands for the user without executing them.

- Report specific counts, not just "looks good."
- Judgment agents must cite the specific file:line or diff hunk
  for each concern — "no issues found" requires listing what was
  actually checked.

- Gate subagents are read-only — they must NOT edit repo files.
  They may write their report under `.rebase-tmp/gates/` and retain command
  evidence in a unique directory under `.rebase-tmp/gate-logs/`. Record argv,
  reviewed revision, scope and completed producer exit with the full output.
  This logging allowance also applies to gates whose boilerplate says
  "sole permitted write"; it does not permit source or other report edits.
  Never reuse an earlier command's log path. The main agent applies fixes.

- If ANY judgment agent flags a concern, the main agent MUST
  investigate and either fix it or explain why it's not an issue.

- Use native workers when available; ordinary steps, investigations, tests,
  type-conversion checks, and gates can run inline otherwise. The parent may
  read gate prompts. Independent review in Steps 4–5 is different: Codex
  needs a fresh-context read-only reviewer with rubric/evidence, not the
  parent's reasoning history. Stop at that boundary if none is available.
- Run only one worker, build, generator, test, scan, or validation command at
  a time by default. Wait for completion before starting the next. Parallel
  execution requires an explicit user request and separate writable logs/state.
- **Companion gate scripts:** Let `gates` run the adjacent `.sh` files;
  do not launch them directly. Current collectors write evidence, not
  verdicts. A successful collector exit still requires gate review.

- **Long-running commands:** Use the runtime's supported process/session
  mechanism and wait for actual completion before dependent work. Preserve
  logs and recovery information; a single "still running" check or an early
  result file does not establish completion. Do not launch the same work twice.
  The parent must verify completed producer exits at worker handoff; Codex
  native subagent finalization may not invoke the root session's Stop hook.
  Resume a worker that returned with a running producer, or retain a foreground
  wait in the parent, before collecting gates or advancing.
  Never end your turn while launched work runs: a headless session ends with
  its turn and no completion notice arrives. Wait in the foreground, in
  bounded calls that fit the command timeout, until the process exits.
  Keep the user informed while work runs; stop and report genuine blockers.
  Save complete output and capture the work command's exit status before
  displaying excerpts. In `command | tail`, `$?` is normally the filter's
  status; retain `PIPESTATUS` or use `pipefail` when logging through a pipeline.
  A successful output filter cannot turn a failed check into PASS.
  Never pipe a live producer to `head` or another early-exiting filter: it can
  kill the producer with SIGPIPE. A simple Bash pattern avoids both errors:

  ```bash
  rc=0
  command arg1 arg2 > "$REPO_ROOT/.rebase-tmp/check.log" 2>&1 || rc=$?
  printf 'EXIT_STATUS: %s\n' "$rc"
  tail -80 "$REPO_ROOT/.rebase-tmp/check.log"
  exit "$rc"
  ```

  Use a descriptive, unique log path for each actual command. Keep its argv,
  revision, scope, completed exit, and log path in the handoff; do not recreate
  a command from memory when drafting the PR.

## OpenShift dependency branches

Select the OpenShift dependency release branch for k8s 1.N as follows:

- k8s <= 1.35: OCP 4.(N-13) — e.g., 1.34 -> 4.21, 1.35 -> 4.22
- k8s >= 1.36: OCP 5.(N-36) — e.g., 1.36 -> 5.0, 1.37 -> 5.1

Use `release-5.X` branches for k8s >= 1.36.
Do NOT escalate to a newer release branch to fix
dependency conflicts — find newer commits on the CORRECT branch.
This mapping selects dependency branches; it does not require every Go builder
or OS base image to carry the same stream label. Select CI images by their
actual role, required toolchain, and the repository's target-branch CI evidence.
Apply the checks in
`${PLUGIN_ROOT}/gates/step4-verification/version-completeness.md` before
declaring that reference stale.
