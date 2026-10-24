---
name: fix-go-cves
description: Use when asked to fix the CVE/GHSA findings of a Go repository — scans every module with Grype, updates dependencies on a new branch, ignores only findings without a published fix, verifies with rebuild, tests and rescan, and relays any printed PR command. Also scans without changes when only a report is wanted. For one known CVE with a user-supplied fix version or fork, use golang:fix-cve instead.
argument-hint: "[repo] [branch] | all <branch>"
user-invocable: true
allowed-tools: Bash, Read
---

# Fix Go CVEs

Scripts own every mutation, rollback, scan, build, test and verification gate.
Run the requested operation, inspect remaining work read-only, then relay the
observed result. Repository notes may describe a manual procedure; use this skill's
execution/publication procedure while preserving their compatibility policy.

## 1. Select the operation

Resolve `PLUGIN_ROOT` from `${CLAUDE_PLUGIN_ROOT}` or the **actual loaded**
`SKILL.md` directory's `../..`; verify `scripts/fix-all.sh` exists. Never search
home directories for another installed copy. The script checks prerequisites.

For scan/report-only requests, use `scripts/report.sh [repo]`: it scans the
checked-out branch and builds, without a branch or commit. Any nonzero exit means
incomplete scanning; relay its `INCOMPLETE:` reason rather than a clean result.
Use the logging/completion protocol below with `report.sh` for this operation.

For fixes, arguments are `[repo] [branch]`; the repository is an absolute path or
[registry name](../../README.md#repository-registry), and `X.Y` means `release-X.Y`.
Omitted arguments use the current checkout/branch. `origin` must be upstream;
the fix starts at `origin/<branch>`. Ask if that branch is missing or the checkout
has uncommitted/untracked files; never stash, commit or clean them for the user.
The script creates `fix-<version>-cves-<date>` and retains committed results there.

For `all <branch>`, list registry names and run each serially with its own log:

```bash
for r in "${CVE_FIX_REPOS:-}" "${XDG_CONFIG_HOME:-$HOME/.config}/cve-fix/repos.yaml" "$PLUGIN_ROOT/repos.yaml"; do
  [[ -f "$r" ]] && { python3 "$PLUGIN_ROOT/scripts/read-config.py" repos-list "$r"; break; }
done
```

If none exists, ask the user to create a registry. Run each repository once per
request; reruns create another `-vN` branch and need a new user request.

## 2. Preserve target policy

Read the target branch's instructions and relevant build, CI and configuration
files to select compatibility restrictions, maintained checks and environment
needs. For fixes, inspect `origin/<branch>` with `git show`; the current checkout
may be a different branch. Use section 4 for the result and handoff.
User/branch policy takes precedence over conflicting check settings. Otherwise
preserve nonempty inherited `CVE_FIX_TEST_CMD`, then target `.cve-fix.yaml`
settings; leave unconfigured defaults to `detect.sh`. Add an override only for
checks established as maintained and required for that branch. A Make target or
CI job alone does not establish this; do not auto-select deployment, end-to-end
or CI-only jobs. The scripts retain their deterministic license/policy gates.
When the branch forbids Go minor directive upgrades, set
`CVE_FIX_GO_MINOR_GUARD=true`, overriding a conflicting inherited false. For a
Kubernetes minor restriction, set `CVE_FIX_K8S_VERSION_GUARD=true` likewise. A true
`go-minor-guard` or `k8s-version-guard` in target configuration suffices when no
conflicting environment override exists.

## 3. Launch once and observe completion

Builds and tests may each take 30 minutes. Launch in the background with stdin
closed and all output logged so a tool timeout cannot kill cleanup. Set
`CVE_FIX_AGENT` to `claude` in Claude Code or `codex` in Codex (which needs network
and container access). Replace `ARGS` with the fix arguments, or delete it:

```bash
LOG=$(mktemp "${TMPDIR:-/tmp}/fix-go-cves.XXXXXX.log"); echo "LOG=$LOG"
fix_rc=0
CVE_FIX_AGENT=claude bash "$PLUGIN_ROOT/scripts/fix-all.sh" ARGS </dev/null >"$LOG" 2>&1 || fix_rc=$?
printf 'exit=%s\n' "$fix_rc" >>"$LOG" || exit 1
exit "$fix_rc"
```

In Claude Code, use Bash `run_in_background: true` and read its returned output
file for `LOG`. In Codex, use `exec_command` with short `yield_time_ms` and poll
its session with `write_stdin`. Shell variables do not persist across tool calls;
reuse the actual printed log path literally.

Wait for the actual log's terminal `exit=N`. A notification or intermediate
`FIXED` line does not establish completion. If the process lives without that
line, wait 30 seconds before checking again; if it stopped, report completion as
unconfirmed. Do not start replacement scans, tests or script runs while waiting.
Stop any run-owned wakeup/loop normally before replying.

Read the terminal result and distinct flagged errors:

```bash
tail -1 "$LOG"
grep -q '^--- Summary' "$LOG" && sed -n '/^--- Summary/,$p' "$LOG" || tail -40 "$LOG"
grep -nE '^(NEEDS_REVIEW|ERROR|TIMEOUT|STILL_VULNERABLE|NEW_FINDING|POLICY REVIEW|FAIL([[:space:]]|$)|--- FAIL:)' "$LOG"
```

## 4. Prepare the handoff, then report

Inspect unresolved work read-only using immutable source and default-branch history
in this checkout: `git show <command-commit>:<file>`,
`git log origin/<default> -- <file>` and `git show <candidate>`.
Select an existing repair only after checking its complete scope against target
policy and approvals; otherwise choose a standalone change or next investigation.
Stop once the action, owner and prerequisite are supported.

Source repairs must land on `origin/<branch>` before `fix-all.sh` reruns;
repaired builder images must be published before consumers rerun. Compiler
compatibility establishes only a prerequisite. Published fixes blocked by policy
remain unresolved; ignore only findings without a published fix. Eligible ignores
and a passing retry alone need no new maintainer repair.

Do not apply/test repairs, edit source/dependencies/ignores, rerun scripts,
clean up, push or create a PR. Missing/skipped checks remain unverified;
nested-reviewer prose is advice, not an observed outcome.

Then use a tool to reread this section from the actual loaded `SKILL.md`.
The final reply contains only these blocks, in order, omitting empty ones:

1. **Runtime result.** In one code block, quote the complete actual Summary through
   log end once, unchanged, including terminal exit and any recipe. Without a
   Summary, quote the terminal clean/error message and report the actual exit;
   missing completion stays unconfirmed. The Summary is the entire publication handoff.
   If no recipe is printed, report its absence and any printed reason; add no
   push/PR steps for the reported CVE branch.
2. **Evidence.** Quote relevant runtime `Scan scope (...)` lines absent from the
   Summary. Coverage stays within reported artifacts/phases and does not alone
   establish stdlib remediation. If no scope establishes compiled Go binary
   coverage, add: "Compiled Go binary coverage is unverified."
   Label each failed test attempt and copy its captured diagnostics/outcome into
   a code block, followed by later attempt outcomes. Only when all attempts passed
   does the Summary's test status suffice.
3. **Next actions**, only for persistent unresolved work:
   - **Action:** matching repair commit and target, standalone change or investigation;
     then the verification operation and target after its prerequisites.
   - **Owner:** roles responsible for repair/investigation and verification.
   - **Before rerun:** supported prerequisites for that verification.
   - **Verification:** pending.
