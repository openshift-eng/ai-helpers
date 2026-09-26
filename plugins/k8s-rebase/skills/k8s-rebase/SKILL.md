---
name: k8s-rebase
description: Use when rebasing a Go project to a new Kubernetes version — bumps all k8s.io/* dependencies, runs codegen, updates version references, fixes build breakage with antagonistic review, and presents a gh pr create command.
argument-hint: "[--bump-tools] <version> (e.g., 1.36.0 or --bump-tools 1.36.0)"
user-invocable: true
allowed-tools: Bash, Read, Agent
---

# Kubernetes Rebase

Automates k8s dependency rebases for Go projects. Steps 3-4 are where
you add unique value — the quality gates that prevent CI rejection. A
rebase that skips them will fail CI. **The rebase is NOT finished until
you present a `gh pr create` command to the user in Step 5.**

**Arguments:** one Kubernetes version (`1.Y` or `1.Y.Z`) and optional
`--bump-tools`, taken directly from the user's rebase request. Reject missing,
extra, or invalid arguments before initialization. Normalize `1.Y` to `1.Y.0`.
Selecting this skill to ask a question does not authorize starting a rebase.

**NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go mod edit`,
`go generate`, or `go run`.** These corrupt k8s version pins via MVS.

**NEVER run `git push` or `gh pr create`.** Only print commands for
the user.

## Bootstrap

Run from your working branch (typically main or master). Step 1 creates a
rebase branch automatically — do not create or switch branches manually
before running bootstrap.

Resolve the **actual loaded** `skills/k8s-rebase/SKILL.md` path (including
runtime aliases and symlinks). Its directory's `../..` is `PLUGIN_ROOT`.
Verify `scripts/k8s-rebase-orchestrator.sh` and the skill directory exist
there. Never search home directories for an arbitrary installed copy.

Resolve `REPO_ROOT` independently with `git rev-parse --show-toplevel` in the
target checkout. Before `init`, compare its physical path with the runtime's
**session cwd**, not a shell command's overridden workdir. If they differ,
stop and ask for a session started at the checkout root: hooks locate the
session guard there. A shell `cd` cannot repair the hook session cwd.
Use separate clones for concurrent rebases; worktrees share Git hooks.

Carry these values in task context: absolute `PLUGIN_ROOT`, `REPO_ROOT`,
normalized `VERSION`, and `BUMP_TOOLS` (`true` only when requested).
Also identify the current session's **host runtime**: Claude Code or Codex.
Steps 4–5 have mutually exclusive review paths: Claude Code uses the default
helper's nested CLI review and existing infrastructure fallback; Codex uses
`--print-prompt` and a fresh-context native reviewer, stopping if preparation
or independent review fails. Do not choose by model vendor, tool names,
installed CLIs, or plugin path. Delegated workers inherit the parent's host;
on cross-agent resume, use the new session's host. Keep this in task context,
not a new shell flag, configuration setting, or persisted state field.

Bind needed variables explicitly in **each shell call** and use Bash for the
examples below. Exports and cwd changes do not persist between tool calls.
Do not depend on `$ARGUMENTS`, manifest-injected variables, or hook-root
variables in ordinary shell commands. Pass quoted argv; never use `eval`.

Before initializing, inspect `.rebase-tmp/state.json` if present. Its version
must agree with the request (normalizing `X.Y` to `X.Y.0` for comparison);
`init` does not validate a changed version on resume. If it differs or the
state is malformed, stop and report the conflict. Recover `BUMP_TOOLS` from
the previous invocation, or ask if unknown; it is not persisted in state.
If state is missing but interrupted artifacts remain in `.rebase-tmp/`,
stop for recovery rather than fresh-initializing over them.
Preserve the interrupted state, reports, and logs; recovery advice must not
recommend clearing `.rebase-tmp/`. Resolve the intended target first.

With those checks satisfied, run:

```bash
# Bind PLUGIN_ROOT, REPO_ROOT, VERSION from the verified context in this call.
bash "$PLUGIN_ROOT/scripts/k8s-rebase-orchestrator.sh" init "$REPO_ROOT" "$VERSION"
```

Nonzero exit means initialization failed: stop. Both FRESH and RESUME
continue at the returned `STEP`. If `STEP` is 5, go directly to Step 5;
the completed state's empty step filename is not a file to load.

## Execute Current Step

1. Read `${PLUGIN_ROOT}/skills/k8s-rebase/steps/rules.md` —
   these rules apply to ALL steps. Internalize them.

2. Read `${PLUGIN_ROOT}/skills/k8s-rebase/${STEP_FILE}` using the
   orchestrator's returned `STEP_FILE` verbatim: it already includes
   `steps/` and `.md`.

3. Use a native step worker when available; otherwise execute ordinary
   step work inline. Supply the absolute repo/plugin paths, version,
   tools flag, parent's host runtime and matching review branch, rules,
   step file, and gate directory. Workers return results;
   **only the parent calls `advance`**. Independent reviews in Steps 4–5
   follow that host's branch; ordinary worker delegation does not change it.

4. When step work completes, run the following unless it reports a stop
   condition (Step 1 structural failure/no-op, a failed Codex independent-review
   path, or another genuine blocker). Those conditions must not be advanced;
   Claude's documented review infrastructure fallback is not such a blocker:

   ```bash
   bash "$PLUGIN_ROOT/scripts/k8s-rebase-orchestrator.sh" advance "$REPO_ROOT"
   ```

   - Exit 0 → read the next step file and continue
   - Exit 1 → shared gate-fix loop in rules.md; keep its retry budget
     across worker/parent handoffs, not another nested fix loop. If that
     budget is exhausted in Steps 2–4, report unresolved gates and submit
     remaining blocked advancement attempts to the existing force-advance policy,
     without starting another fix cycle. These are deliberate retries,
     not status polls; stop retrying as soon as state advances. Step 1
     structural failures stop; never submit them to force-advance.
   - Exit 2 with FORCE_ADVANCE in output → force-advance: read and report the
     WARNING output and .rebase-tmp/status/INCOMPLETE, then run `status` to
     find the new step or completion. State has already advanced.
   - Exit 2 with ERROR in output → hard error: stop and include the error in your response

5. Repeat until `advance` prints `DONE: all steps complete` or `status`
   reports `DONE: true`. Never use `advance` as a status poll or call it
   again after a successful/forced advancement for the same handoff.

6. After DONE: read and execute
   `${PLUGIN_ROOT}/skills/k8s-rebase/steps/step5-pr.md`
   (PR command generation + cleanup). Step 5 has no gates — it runs
   after the orchestrator confirms all gated steps are complete. DONE
   does not certify every gate passed. Preserve unresolved findings in
   the final summary; INCOMPLETE records only the latest force-advance.

## Recovery

If resuming a crashed or interrupted session, bind the same verified paths
and inspect status before any mutation:

```bash
bash "$PLUGIN_ROOT/scripts/k8s-rebase-orchestrator.sh" status "$REPO_ROOT"
```

Follow the Bootstrap resume checks, then continue from the recorded step.
Status reconstruction without state.json is advisory; it does not restore
state or authorize fresh initialization. Do not infer a completed process
from a result marker alone; use Step 1's recovery checks.
