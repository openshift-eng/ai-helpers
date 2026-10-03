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

## Scope

Every change must be directly required by the k8s version bump.
Does build, vet, or lint fail without it? If not, do not make the
change. Do not refactor, add features, or touch files that compile
cleanly. Fix ONLY the cited issue at the cited location.

Preserve behavior: never replace label selectors with
`reflect.DeepEqual`, never change security flag defaults.
Preserve nil semantics: `*int32` nil means "server default",
`int32` zero means "set to 0" — use `ptr.To[int32](val)`.
Adapt type signatures without altering surrounding logic.
Verify against base before flagging issues:
`git show $(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main):<file>`

Do not add struct tags (like omitempty), merge functions, rename
interfaces, or restructure packages.

## Module Safety

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go mod edit`,
`go generate`, or `go run`. Allowed: `go build`, `go vet`,
`go test` (with `-mod=vendor` if vendor/ exists), `go mod verify`,
`go doc`, `go install <tool>@<version>`, `go clean -cache`.

**Exception:** When adding a `replace` directive or when
`k8s-rebase-depfix.sh` bumps a dependency, run `go mod tidy` and
`go mod vendor` in each affected module directory to keep vendor/ in
sync. These are the only contexts where `go mod tidy` and
`go mod vendor` are permitted. Do not run them speculatively.

Prepend this rule to every gate subagent prompt.

The existing module-operation hook blocks direct tidy/vendor even in these
documented exception cases. If it blocks a required repair, report that
conflict; do not disable the hook or disguise the command to bypass it.

## Never Push

NEVER run `git push` or `gh pr create`. Only print commands for
the user to copy-paste.

## Gate-Fix Loop

1. Run `bash "$PLUGIN_ROOT/scripts/k8s-rebase-orchestrator.sh" gates "$REPO_ROOT" <step>`.
   It executes companions and identifies PENDING reviews. Exit 1 with normal
   PENDING output means judgments remain; unexpected errors stop the caller.
   Exit 0 means none pending, not all passed: inspect EXISTING and RESOLVED
   verdicts too. Fresh PASS and justified SKIP satisfy advancement; do not
   retry an accepted SKIP or relabel it PASS. FAIL and INCONCLUSIVE remain
   unresolved. Read exact reports: the status table counts SKIP under PASS.
2. Read each pending prompt and its evidence. Check evidence HEAD against
   the current commit; missing/stale evidence after a companion crash is not
   usable. Gather fresh read-only evidence as that prompt permits, or report
   inability to judge. Use a native gate worker when available, otherwise
   review inline under the same read-only constraints.
3. Write reports through `scripts/write-gate-report.sh` at the known plugin
   root. Confirm HEAD has not changed during review before it stamps the
   report. Choose one actual verdict; `PASS|FAIL|SKIP` is notation, not a
   shell pipeline. A missing helper is an error, not grounds to fabricate
   an unstamped report.
4. Triage findings against base, fix new issues, and commit all fixes before
   refreshing evidence. Re-validate as the step requires (`--quick` in 2–3,
   `--no-test` in 4), then run `gates` again. Every current-step report at the
   old HEAD is stale, including PASS reports: complete all newly pending
   reviews, not just the previously failing ones.
5. If a cached report needs deliberate invalidation at the **same HEAD**,
   remove only that current-step report **before** rerunning `gates`.
   Never delete a newly regenerated companion report or prior-step reports.

Repeat fixes/reviews up to 3 iterations, sharing this budget across workers
and parent; do not nest another retry loop at handoff. Preserve the step's
stop condition (Step 1 structural failure stops). The parent alone calls
`advance` and handles its retry/force-advance output as in SKILL.md. Workers
return verdicts, unresolved issues, and attempts already used. Never call a
gate passed until a fresh report says PASS or spend advances as status polls.
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
- Each commit gets exactly one `Signed-off-by` and one
  `Assisted-by: Claude Code <noreply@anthropic.com>` trailer
  (scripts add automatically).

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

## Feature Gates

SetFromMap validates parent-dep consistency. ALL gates must go in
SetFromMap AND env vars. The autofix script handles this; do not
remove gates from its SetFromMap.

## Execution and reviewer roles

- Report specific counts, not just "looks good."
- Judgment agents must cite the specific file:line or diff hunk
  for each concern — "no issues found" requires listing what was
  actually checked.

- Gate subagents are read-only — they must NOT edit repo files.
  Their sole permitted write is their gate report file under
  `.rebase-tmp/gates/`. The main agent applies fixes.

- If ANY judgment agent flags a concern, the main agent MUST
  investigate and either fix it or explain why it's not an issue.

- Use native workers when available; ordinary steps, investigations, tests,
  type-conversion checks, and gates can run inline otherwise. The parent may
  read gate prompts. Independent review in Steps 4–5 is different: Codex
  needs a fresh-context read-only reviewer with rubric/evidence, not the
  parent's reasoning history. Stop at that boundary if none is available.
- **Companion gate scripts:** Some gates have `.sh` files alongside
  the `.md` prompt. The orchestrator's `gates` command runs them
  automatically and marks the gate RESOLVED if the companion passes,
  or PENDING if it needs a subagent. Do NOT run companion `.sh`
  scripts manually — the orchestrator has already handled them.
  Launch gate workers only for PENDING gates, or review those gates inline.

- **Long-running commands:** Use the runtime's supported process/session
  mechanism and wait for actual completion before dependent work. Preserve
  logs and recovery information; a single "still running" check or an early
  result file does not establish completion. Do not launch the same work twice.
  Keep the user informed while work runs; stop and report genuine blockers.

## OCP Version Mapping

k8s 1.N maps to OCP as follows:

- k8s <= 1.35: OCP 4.(N-13) — e.g., 1.34 -> 4.21, 1.35 -> 4.22
- k8s >= 1.36: OCP 5.(N-36) — e.g., 1.36 -> 5.0, 1.37 -> 5.1

Use `release-5.X` branches and `openshift-5.X` in CI image refs
for k8s >= 1.36. Do NOT escalate to a newer release branch to fix
dependency conflicts — find newer commits on the CORRECT branch.
Read the OCP version from `.ci-operator.yaml` or Dockerfiles to
confirm (`grep -rn 'openshift-[0-9]' .`).
