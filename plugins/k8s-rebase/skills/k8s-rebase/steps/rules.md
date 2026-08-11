# Rebase Rules

Read this file at the start of every step.

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
`go test` (`-mod=vendor` if vendor/ exists), `go mod verify`,
`go doc`, `go install <tool>@<version>`, `go clean -cache`.
Prepend this rule to every gate subagent prompt.

## Never Push

NEVER run `git push` or `gh pr create`. Only print commands for
the user to copy-paste.

## Gate-Fix Loop

When a gate reports FAIL:
1. **Triage** — verify real, not pre-existing on base branch.
2. **Fix** and commit.
3. **Delete** old report (`rm .rebase-tmp/gates/<report>`).
4. **Re-run** gate with a fresh prompt.

Commit ALL fixes before re-launching ANY gates. Gates read the
branch tip at launch — uncommitted fixes cause false FAILs.
Pattern: read all FAIL reports, fix all issues, commit, then
re-run all failed gates in one parallel wave.
Repeat up to 3 iterations. Never skip the re-run — a gate is
not passed until a fresh run reports PASS.

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

## Subagent Rules

- Report specific counts, not just "looks good."
- Judgment agents must cite the specific file:line or diff hunk
  for each concern — "no issues found" requires listing what was
  actually checked.
- Gate subagents are read-only — they must NOT edit repo files.
  Their sole permitted write is their gate report file under
  `.rebase-tmp/gates/`. The main agent applies fixes.
- If ANY judgment agent flags a concern, the main agent MUST
  investigate and either fix it or explain why it's not an issue.
- If you cannot launch subagents, run the gate checks inline.
- **Companion gate scripts:** Some gates have `.sh` files alongside
  the `.md` prompt. Run the `.sh` script FIRST — it provides
  mechanical check results. Include the script output in the
  subagent prompt so it uses the results instead of re-running.
- **Context budget:** Never burn main-agent context on build
  monitoring. Use `run_in_background: true` for long commands,
  or launch builds in subagents. NEVER use `sleep` to poll.
- **Stay active:** NEVER produce a text-only response while
  work remains. Every response must include at least one tool
  call (Bash, Read, or Agent). If waiting for background tasks,
  check status or start the next piece of work — never emit
  prose like "Waiting for X" without a tool call alongside it.

## OCP Version Mapping

k8s 1.N maps to OCP as follows:
- k8s <= 1.35: OCP 4.(N-13) — e.g., 1.34 -> 4.21, 1.35 -> 4.22
- k8s >= 1.36: OCP 5.(N-36) — e.g., 1.36 -> 5.0, 1.37 -> 5.1

Use `release-5.X` branches and `openshift-5.X` in CI image refs
for k8s >= 1.36. Do NOT escalate to a newer release branch to fix
dependency conflicts — find newer commits on the CORRECT branch.
Read the OCP version from `.ci-operator.yaml` or Dockerfiles to
confirm (`grep -rn 'openshift-[0-9]' .`).
