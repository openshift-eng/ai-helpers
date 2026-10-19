---
name: fix-go-cves
description: Use when asked to fix the CVE/GHSA findings of a Go repository — scans every module with Grype, updates dependencies on a new branch, ignores only findings without a published fix, verifies with rebuild, tests and rescan, and relays any printed PR command. Also scans without changes when only a report is wanted. For one known CVE with a user-supplied fix version or fork, use golang:fix-cve instead.
argument-hint: "[repo] [branch] | all <branch>"
user-invocable: true
allowed-tools: Bash, Read
---

# Fix Go CVEs

Deterministic scripts own every mutation, rollback, and verification gate.
Your job is to run them, then explain what they could not decide.

## Locate the scripts

`PLUGIN_ROOT` is `${CLAUDE_PLUGIN_ROOT}` when set; otherwise resolve the
**actual loaded** `SKILL.md` path and use its directory's `../..`. Verify
`$PLUGIN_ROOT/scripts/fix-all.sh` exists. Never search home directories for
another installed copy. `fix-all.sh` checks its prerequisites and exits 1
naming anything missing.

## Run the scripts

Builds and tests can each take 30 minutes. Run every script in the background
with its output in a log file, and wait for it to exit; do not let a tool
timeout kill it (SIGKILL skips cleanup). Shell variables do not persist
between tool calls, so reuse the printed log path literally.
In Claude Code, set Bash `run_in_background: true` for the launch.
In Codex, use `exec_command` with a short `yield_time_ms` and poll its returned
session with `write_stdin`. Replace `ARGS` with the request's arguments, or delete it:

```bash
LOG=$(mktemp "${TMPDIR:-/tmp}/fix-go-cves.XXXXXX.log"); echo "LOG=$LOG"
CVE_FIX_AGENT=claude bash "$PLUGIN_ROOT/scripts/fix-all.sh" ARGS </dev/null >"$LOG" 2>&1; echo "exit=$?" >>"$LOG"
```

Before interpreting the outcome, read that actual log and confirm its terminal
`exit=N` line. Intermediate `FIXED` output and background-task notifications do
not establish completion. If the line is absent and the process lives, run
`sleep 30` before checking the log again; if it stopped, report completion as
unconfirmed. Do not substitute standalone scans, builds, tests, or another
script invocation while waiting.

Then read the outcome rather than the whole log:

```bash
tail -1 "$LOG"
grep -q '^--- Summary' "$LOG" && sed -n '/^--- Summary/,$p' "$LOG" || tail -40 "$LOG"
grep -nE '^(NEEDS_REVIEW|ERROR|TIMEOUT|STILL_VULNERABLE|NEW_FINDING|POLICY REVIEW)' "$LOG"
```

Set `CVE_FIX_AGENT` to the host runtime: `claude` in Claude Code, `codex` in
Codex. Codex needs network and container access (a full-access sandbox).

## Report only

When the user asks only to scan, check, or report, run `scripts/report.sh`
(optionally with a repository path) instead of `fix-all.sh`. It scans the
checked-out branch without creating a branch or commit; the build still runs.
Any non-zero exit means the scan is incomplete (an `INCOMPLETE:` line names
why); say so rather than reporting a clean result.

## Fix one repository

`ARGS` are an optional repository (an absolute path or a
[registry](../../README.md#repository-registry) name) and branch; `X.Y` means
`release-X.Y`. With neither, the current checkout and branch are used.

- `origin` must be the upstream repository: the fix branch starts from
  `origin/<branch>`, and the PR targets `origin`'s owner unless `upstream-org`
  is set. If the run cannot find `origin/<branch>`, ask for the base branch.
- The checkout must have no uncommitted or untracked files. If it does, ask;
  never stash, commit, or clean for the user.
- The script creates `fix-<version>-cves-<date>`, commits there, and leaves
  the checkout on it when commits were made.
- Run each repository once per request. A rerun creates another `-vN`
  branch; suggest one with the change that would alter the result, and rerun
  only when the user asks.

## Fix all registered repositories

For `all <branch>`, list the names, then run `fix-all.sh NAME BRANCH` for each,
one at a time with a new log; parallel builds contend for resources. No
output means no registry exists; tell the user to create one.

```bash
for r in "${CVE_FIX_REPOS:-}" "${XDG_CONFIG_HOME:-$HOME/.config}/cve-fix/repos.yaml" "$PLUGIN_ROOT/repos.yaml"; do
  [[ -f "$r" ]] && { python3 "$PLUGIN_ROOT/scripts/read-config.py" repos-list "$r"; break; }
done
```

## Interpret the result

After the script exits, investigate read-only and recommend next steps. Leave
repairs, reruns, and build, test, or cleanup commands for a new user request.

| Exit | Meaning |
| --- | --- |
| 0 | Every finding fixed or ignored, and all gates passed |
| 2 | Partial fix, unconfirmed result, or PR prerequisite failure |
| 1 | Setup or invocation error: quote the last `ERROR:` line (or the log tail) |
| 130, 143 | Interrupted; the fix branch was removed |

Include in the final report:

- Retained branch, all retained fix commit hashes, and how to return to the
  original branch. Label upstream/backport commits separately.
- The Summary's `Outstanding` count when present, including zero, and actual
  gate results; label unconfirmed results.
- Relay a push/PR command only if the script printed it. Otherwise state the
  log's reason and omit push/PR commands from the reply.
- For each flagged outcome: evidence (log line or `file:line`), cause or
  uncertainty, recommended action and owner. An upstream commit does not prove
  its tests passed; do not promise a backport or rerun will pass gates or print
  a PR command.

`IGNORED` lines need no action: no fix is published, and the ignore lapses
once Grype records one.

Investigate flagged outcomes using these checks:

- Breaking or incompatible update: read the target version's release notes
  and the repository's use of the changed API; estimate the migration.
- Kubernetes minor bump, or Go above the build image: name the team decision
  and what unblocks it (a newer builder, an approved bump).
- Test failure (already retried once): read the failing output and identify
  the evidence linking it to the update; say when causality is unproven.
  Compare dependencies from this run's actual base commit to its retained fix
  commit, including the Go directive. The current fix-branch dependencies alone
  are not baseline evidence.
  Pre-existing source does not prove a pre-existing failure; a changed Go
  directive can activate checks without changing tooling dependencies.
  Tests that need `sudo` or a prompt need a non-interactive test command.
- Test, lint, or license-check failure: if the default branch already fixed
  it (`git log origin/<default> -- <file>`, such as the failing code or the
  license config), recommend that backport.
  The repair must reach `origin/<branch>` before rerunning: the script starts
  each fix branch there.
- Transient network, timeout, or degraded scanner: recommend a rerun.
- Wrong build or test command: recommend `CVE_FIX_*` overrides for a rerun,
  or `.cve-fix.yaml` fields committed on the target branch
  ([configuration](../../README.md#configuration)).

Do not hand-edit `go.mod`, `go.sum`, vendor trees, or `.grype.yaml` to force a
clean result, and do not delete the fix branch. Never push or create the PR.
