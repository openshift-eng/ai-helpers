# Claude/Codex Compatibility Plan

## Scope and current status

Make the existing Kubernetes rebase workflow usable by Codex while preserving
Claude behavior. Limit changes to invocation/instruction compatibility,
independent-review handoff, existing hook input formats, documentation, and
focused validation. The user also approved the narrow shared finalization
corrections below. Keep one plugin package, one skill, and the shared scripts,
steps, gates, and reports.

**2026-09-17: offline checks and both hosts' finalization artifact checks pass.
Codex's current finalization account is accurate; Claude retains native reporting
and failure-handling qualification gaps. Not end-to-end qualified.**
Frozen candidate: `69cd6519` plus the audit fixes below, version 0.0.1.
Package manifest SHA-256:
`f1312236c0bb2d9d32f64e717c2e8fb4b6eb163f34dddedb1f87a37980b32ced`
(a content snapshot, not a Git commit). All 122 package files and executable
bits match both isolated CLI installs. Codex loaded its cache; Claude's local
marketplace loader used the identical frozen marketplace source. Only plan/README
updates follow that freeze. The normal user installation remains `1073dc17`;
these isolated tests did not refresh it or the current app session.

Implemented: shared path/argument handling, host-specific review routing,
checked Codex prompt preparation, vendor-patch hook support, and exact gate
summaries. Existing tests also cover the separate shared-workflow corrections:
PASS/SKIP advancement, checked OpenShift version selection and failure-hook
restoration, isolated lint baseline checks, and bounded lint retry/triage.
Keep shared-workflow fixes distinct from host compatibility; focused checks
are not full-rebase qualification.

This is the canonical current plan. Keep raw fixtures under
`.work/claude-codex-compatibility/`; superseded narratives remain in Git
history, not another planning document.

## Design to preserve

### Package and invocation

- Reuse the existing marketplace, manifest, and Claude frontmatter. The tested
  Codex loader accepts them; generic-validator rejection of Claude fields is
  not a reason to remove them. Metadata does not grant tools or permissions.
  Installation and both namespaced invocations are in [README](../README.md).
- Derive `PLUGIN_ROOT` from the actual loaded skill path, resolving aliases
  and symlinks; verify the orchestrator and skill directory. Derive the target
  `REPO_ROOT` separately. Never search for an arbitrary installed copy.
- Require the agent's session cwd to be the physical target checkout root
  before initialization. A command-level cwd override cannot repair the hook
  activation path. Use separate clones for concurrent rebases; worktrees
  share Git hooks.
- Accept exactly one `1.Y` or `1.Y.Z` version and optional `--bump-tools`;
  normalize `1.Y` to `1.Y.0`. Reject invalid/missing/extra arguments before
  `init`. A question about the skill does not authorize a rebase.
- Bind absolute paths and arguments in each shell call and worker handoff.
  Use quoted argv, not `eval`, persistent shell exports, `$ARGUMENTS`, or
  hook-only environment variables. Preserve the tools flag through Steps 1
  and 4d.
- Keep the current parent's host runtime in task context, not persisted state
  or a provider flag. Workers inherit it; cross-agent resumes use the new
  host. Do not infer it from model vendor, installed CLIs, or plugin paths.
- Before resume initialization, reconcile the requested version with valid
  existing state. Recover the unrecorded tools flag from context or ask.
  Conflicting/malformed state, or missing state with interrupted artifacts,
  requires recovery without overwriting evidence. `status` reconstruction
  is advisory and does not restore `state.json`.

### Execution, gates, and advancement

Use native workers when available and authorized; ordinary steps, tests,
investigations, and gates may run inline otherwise. Gate reviewers may write
only their own reports; the implementing agent handles source fixes. Only one
session may mutate a rebase, and source mutations must finish before concurrent
evidence collection or review. HEAD checks do not detect uncommitted changes.

Keep the existing protocol, with these non-interchangeable outcomes:

| Signal | Meaning |
| --- | --- |
| Step 1 process exit | 0: no-op, stop; 2: success; 1: error requiring recovery/triage |
| `gates` exit 1 with normal PENDING output | Judgments remain; unexpected errors with the same exit code instead stop the caller |
| `gates` exit 0 | No pending work, not necessarily passing verdicts |
| Fresh PASS / justified SKIP | Acceptable for advancement; retain SKIP and its reason |
| FAIL / INCONCLUSIVE / missing or malformed report | Unresolved or unverified, never inferred success |
| Successful / forced advancement | State already moved; do not advance the same handoff twice |
| Orchestrator DONE | Gated steps traversed; Step 5 still runs, without `advance` |

- Use the returned `STEP_FILE` relative to `skills/k8s-rebase/` verbatim.
  Handle completed state before resolving a step file.
- Wait for actual long-running process completion. Step 1's early result
  marker is not terminal status. Inspect the recorded process and logs before
  recovery; do not relaunch surviving work or infer success from a dead PID.
- Run companions through `gates`, then review pending evidence at the current
  HEAD. Inspect cached verdicts too. Write reports with
  `scripts/write-gate-report.sh`, confirming the reviewed HEAD is unchanged.
- After fix commits, perform the step's required validation and refresh
  **all** stale current-step reports, including earlier PASS reports.
  Same-HEAD invalidation must precede regeneration; never delete a newly
  regenerated companion report or a prior-step report.
- The parent alone calls `advance`. Workers return outcomes, unresolved
  findings, and consumed repair iterations. Share the step's three-iteration
  budget across parent and workers; do not restart it at handoff.
  Repair iterations and blocked advancement attempts are distinct.
- Step 1 structural failures, failed Codex independent review, and genuine
  blockers stop without advancement. In Steps 2–4, exhausted repair budgets
  may use the remaining blocked attempts under the existing force-advance
  policy, without another repair loop. FORCE_ADVANCE already changes state:
  report the warning and inspect `status`; ERROR is a hard stop.
- Step 5 uses the orchestrator's read-only `reports` inventory of expected
  gates, not just existing files. Preserve
  exact verdicts, missing/malformed checks, and stale final-step evidence.
  Prior-step PASS is evidence at its recorded SHA, not a final-tip retest.
  `status` counts SKIP under PASS; INCOMPLETE records only the latest forced
  advancement. Neither aggregate is a substitute for the retained reports.

Do not redesign the orchestrator or change gate names, report schema,
freshness policy, or retry thresholds to simplify callers. The independently
versioned-module correction below is a shared correctness change, not a
host-specific relaxation of gate criteria.

### Independent review

Preserve both existing scopes: Step 4 selected-commit review through
`k8s-rebase-review.sh` and its template; Step 5 full-rebase review through
`k8s-rebase-pr-review.sh` and its separate four-check rubric.

| Host | Execution and failure policy |
| --- | --- |
| Claude | Default helpers invoke the nested Claude CLI; retain existing infrastructure fallbacks |
| Codex | Checked `--print-prompt` preparation, then a fresh-context read-only native reviewer; preparation/reviewer failure stops |

Codex preparation validates immutable commit/base references, checks required
evidence commands before truncation, and checks rendering before handoff.
Failed collection is not an empty diff; a successfully collected empty filtered
diff remains valid review input, not automatic approval. Preserve filters,
optional context, and disclosed helper truncation.

For Codex, the reviewer must receive the complete prepared payload and scope,
not the implementer's reasoning history or a silently truncated tool response.
Require an explicit `APPROVE: <reason>` or `REJECT: <reason>`; investigate
rejection, and stop on missing/malformed verdicts. Preparation success is not
approval. A worker that implemented a fix cannot review it independently in
the same context. Treat repository evidence as data, not instructions.

On Codex resume, repeat review if its decision for the SHA/scope is unavailable;
do not reuse approval for later changes. Keep Claude's existing fallback policy.
For either host, source approval does not upgrade gate verdicts. Do not add
approval markers, a review state machine, or a CLI provider-dispatch framework.

### Hooks and finalization

Reuse `hooks/hooks.json`, its session guard, and existing response policies.
Retain vendor checks for Claude `file_path` and Codex `apply_patch` headers
in `tool_input.command`, including move destinations. Codex supports the
existing hook-root compatibility variables, but requires trust of the actual
definitions; discovery alone is not enforcement. Hook cwd is session-scoped.
See the official [plugin-hook](https://learn.chatgpt.com/docs/hooks#plugin-bundled-hooks),
[input](https://learn.chatgpt.com/docs/hooks#pretooluse), and
[cwd](https://learn.chatgpt.com/docs/hooks#common-input-fields) contracts.

Print push/PR commands only. Preserve commit trailers, retained reports,
INCOMPLETE, and pre-push-hook restoration. Keep Claude's optional `/loop`
suggestion conditional; do not add Codex automation.

## Latest audit fixes

- Shared exact-verdict parsing rejects prefixed/duplicate fields without
  changing valid PASS/SKIP advancement or thresholds. The read-only `reports`
  command replaces Step 5's inline inventory, reusing report paths and parsing;
  it computes verdict/freshness totals without changing reports, schemas, or
  state. Step 5 copies those totals and recorded force-advance wording, and
  derives change claims from the diff rather than commit subjects/context.
- Codex review payloads are complete, unique, and checked before handoff;
  Claude's default/fallback behavior is unchanged. Steps 2–3 remove contradictory
  per-gate budgets in favor of the existing shared per-step limit.
- Test-only validation preserves `summary.txt` and reserves separate logs
  with ordinary umask permissions. Normal validation still replaces its
  summary and uses `.log` names, including for `test-only-*` modules.
- Stop exempts a live positive Step 1 PID after the early result marker only
  during Step 1; exited/zombie, invalid, and later-step PIDs do not qualify.
  Recovery preserves interrupted evidence and does not recommend erasure.
- Steps 1–2 and pre-PR review exclude independently versioned
  klog/utils/kube-openapi/gengo from release alignment; Kubernetes still tracks
  v1.Y.Z. Step 2 parses actual requirements with Go's read-only parser, not
  excludes/replaces. Missing target/modules or parsing failure cannot certify
  zero issues. Existing replace/indirect exceptions, exact target matching,
  and dependency-upgrade logic are preserved.
- The push guard no longer mistakes `pre-push` filenames for commands;
  ordinary, flagged, quoted, and compound push denials remain. Cleanup checks
  hook reads, restores backups directly with executable mode preserved,
  removes only listed scratch, and removes the marker last. Failures stop
  without disabling guards or changing access; verify resulting artifacts.
- The eval branch-fetch fallback keeps the configured known-good commit,
  not the newer fetched branch tip. Local-fetch tests do not launch the runner.

These changes stay in existing files/tests. Unique scratch names use portable
trailing-X templates. No provider framework, extra package, new dependency,
or shared-workflow redesign is needed.

## Validation and qualification

### Preparation and offline checks

Reuse matching evidence at its recorded revision and scope. Start with the
smallest reproducer; stop escalation on failure. Freeze candidate source and
install from tracked files through the existing marketplace route, excluding
scratch data and nested checkouts. Verify actual loaded paths, file contents,
and executable bits; do not edit the installed cache. Follow repository
version/sync rules when applicable, without a separate cachebuster scheme.

Record source/installed revisions, CLI/model versions, hook trust mode,
reviewed SHAs/scopes, and actual tool outcomes. Give evaluating agents the
skill and raw fixture state, not expected answers. Inspect exact hooks before
invocation-only trust; do not change persistent trust settings for fixtures.
For Codex CLI 0.154.0 isolated-config fixtures, the verified selector is
`-c 'plugins.k8s-rebase@ai-helpers.enabled=true'`; embedded quotes around the
plugin ID prevented discovery. Verify the catalog and loaded path regardless.

From the repository root:

```bash
git diff --check
make -C plugins/k8s-rebase test-compatibility
make -C plugins/k8s-rebase test-version-selection
make -C plugins/k8s-rebase assert-evidence-paths
make lint
make site-build
```

Run Bash syntax and ShellCheck for changed scripts/examples. The local strict
site build uses the existing
`plugins/k8s-rebase/.work/claude-codex-compatibility/site-venv/bin` on PATH.
Repository lint and actual runtime loading take precedence over the
generic skill validator's rejection of unchanged Claude-specific metadata.

### Remaining installed-runtime coverage

Resolve the native qualification gaps below before escalation. Git-hook
restoration needs authorized target-metadata writes; approved narrower file
operations do not authorize changing access policy or disabling guards.

- **Invocation/hooks:** Separate disposable target repos; repeated shell calls,
  quoted paths, missing/invalid/extra arguments, question-only requests, and
  tools-flag forwarding. A subdirectory-started session must stop before init
  despite command cwd overrides; root sessions retain guards during
  module-local commands. Verify active/inactive guards and actual denials for
  vendor edits, module operations, push/PR, prior-report deletion, and Stop.
  Use harmless stubs without publishing access; an agent declining a command
  is not a hook denial.
- **Gates/handoffs:** Inline fallback, PENDING versus command errors, cached
  FAIL, exact SKIP, stale evidence, all-current-step refresh, same-HEAD
  invalidation before companion regeneration, shared repair budgets, and
  one-parent advancement. Check completed-state entry into Step 5 and
  FORCE_ADVANCE without a second advancement. Cover successful committed
  handoffs in both host directions; existing blocked Step 1 handoffs do not
  establish this.
- **Recovery/interruption:** Both installed hosts preserve artifacts on a
  version mismatch. Still cover malformed/missing state. Interrupt a delayed
  Step 1 stand-in after its early marker;
  resume with a surviving child and with a terminated/failed child. Verify
  no duplicate launch or premature dependent work, preserve failure artifacts,
  and check hook lifecycle. Unknown outcomes must stop for recovery.
- **Independent review:** Installed selected-commit rejection and pre-PR
  approval now exercise both routes. Still cover repaired-commit re-review,
  large pre-PR payloads, missing verdicts, and actual
  native-tool absence (not just prohibited delegation or feature flags).
  Retain checks for invalid references, collection/rendering failures,
  valid empty diffs, and missing, directory, or disappearing templates.
  Preserve immutable evidence and Claude
  default/fallback parity. Verify large-prompt delivery and mutually exclusive
  host routing in actual tool traces.
- **Finalization:** Compare every PR verification claim with expected reports,
  including prior-step unresolved/missing checks and stale final-step evidence.
  Claude must retain required failure stops in adapted cleanup operations,
  particularly before marker removal on scratch failure. Successful cleanup
  and an unreadable-hook refusal do not establish this case.
  Failed Codex preparation/review must not trigger PR generation or cleanup.

### Bounded end-to-end pair

Use the existing `openshift/multus-cni` case in
[config-1.36.yaml](../test/config-1.36.yaml): baseline
`b4ec7d8239ce4bd3ed949bce9816a013377b44c7`, target **1.36.2**,
`--bump-tools` **false**.

Use separate clean clones, matching Go/tooling environments, and the same
frozen candidate. Start detached at the baseline and pin the local default
branch there for review-base discovery; a default-branch start can
fast-forward away from the intended baseline.

Obtain approved wall-time/cost caps before launching. Run Codex first, then
Claude after it passes; a targeted diagnostic comparison is an exception.
Preserve blocked runs rather than switching repos to obtain a pass. Run the
installed skill through all four gated steps and Step 5 with real companions
and independent reviews. In each host's run, pause at a committed boundary with no child
running, then resume in a new session. Keep cross-host checks in the focused
fixtures.

Qualification requires both hosts to finish with applicable gates passing,
legitimate inapplicable gates recorded as SKIP, real independent approvals,
accurate final claims, retained reports, original hook restoration, and no
compatibility-related manual rescue. Different valid fixes are acceptable.
Claude fallback remains supported behavior but does not count as real review.
Force-advanced traversal alone is not an all-gates-passing rebase. Do not push
or create a PR. The full multi-repository eval matrix is not required.

## Current evidence and limits

Current working-tree checks: **47 compatibility tests, 12 version-selection
tests, 46 repository unit tests, and 8 companion/template pairs** pass.
Two legacy Claude helper invocation/fallback parity checks pass. Of the 32
gate criteria/safety bodies compared with `69ff8893`, 30 are unchanged after
reviewed path substitutions; Steps 1–2 have the explicit version-check
corrections above. All gate safety/report-write boundaries remain unchanged.
Repository lint, strict site build,
and Bash syntax pass; changed scripts introduce no new ShellCheck diagnostics.
Pre-existing findings remain in the validator, eval runner, and version companion.

Additional offline evidence: 14 exact-shell-block checks cover Step 1 child
exit/wait/argv and review preparation/cleanup. Tracked tests cover allocation,
log-permission, inventory, and cleanup-command failures without stale reuse or
lost recovery artifacts. These do not establish native interruption behavior.

Native Codex source reviews (2026-09-16) rejected a regression beyond byte
98,000 in both scopes (`f3b338cc`), then approved a separately repaired commit
(`7380869a`) with a fresh reviewer. Prohibited delegation stopped without
self-review. These are handoff tests, not installed or full-rebase qualification.

Latest installed fixtures used Codex CLI **0.154.0 / gpt-5.6-sol (medium)**
and Claude CLI **2.1.274 / claude-sonnet-4-6**. Claude's helper retains its
separate default model selection. Each session has a five-minute process-group
cap; Claude's outer $2 budget does not cap the nested helper's separate call.
Exit 0 means the session finished, not a passing test. The reported network
interruption did not prevent these model calls completing.

Both profiles were isolated with a read-only system mount and writable fixture,
profile, and temporary directories. Codex used invocation-only trust after all
hook definitions/scripts were reviewed; persistent user trust was unchanged.
Current Codex finalization fixtures allow target Git-metadata writes inside
that outer isolation. Host policy rejects the example shell removal but permits
narrower file operations; no guard or access policy was changed for completion.

The current snapshot's finalization and unreadable-hook cleanup runs are under
`.work/claude-codex-compatibility/finalization-current-20260917.HlkRPc/`.

- Both real independent pre-PR routes approve the final SHA. Both hosts retain
  HEAD, state, INCOMPLETE, and all 31 reports; remove only intended scratch;
  and restore the original hook bytes with mode 0751. Codex's checked cleanup
  removes the marker last. No source changes, gate executions, or publishing occur.
- Both copy the computed inventory correctly: 32 expected gates, 27 PASS,
  one each SKIP/FAIL/INCONCLUSIVE, two unverified, with PASS split into
  13 current, 13 historical prior-step, and one stale final-step report.
  Dependency changes and every unresolved/unverified check are identified.
- Claude still falsely says all reports share one summary, adds a redundant
  recap, and drops a scratch-cleanup failure stop before marker removal.
  Correct artifacts on the successful path do not qualify that failure path.
  The source already requires exact reporting and stopping on cleanup failure;
  retain these model-following failures without expanding the workflow.
- Both unreadable-hook runs stop without changing hook/backup metadata, HEAD,
  state, reports, scratch, or the marker. Claude's refusal still recommends a
  permission change and treats the backup as proof of hook ownership; neither
  is established authority to proceed. No permissions were changed. This tests
  hook-read failure, not scratch-removal failure or every recovery suggestion.

Retained earlier installed evidence remains useful at its recorded scope:

- `installed-candidate-20260917.XzHBcH/` (`2ba91582…`): both selected-commit
  reviewers reject the lost-field regression. Codex uses `fork_turns: none`
  and reads all 956 prompt lines, including the defect beyond byte 98,000;
  Claude uses the default nested CLI. Codex renderer failure stops before
  delegation, mutation, or cleanup. Version-conflict recovery preserves state
  on both hosts, but Claude's initial erasure advice was unsafe.
- `finalization-fixes-20260917.Ygn4gR/` (`a46a2049…`): Claude's recovery rerun
  preserves artifacts and no longer recommends erasing them. Later finalization
  reruns corrected the push collision, scratch removal, malformed-verdict counts,
  and freshness arithmetic. Failed prose/ordering iterations remain in their
  `finalization-*` traces; successful artifacts alone do not qualify them.
- Discovery located both installed packages without mutation. Claude's false
  missing-gates claim came from assigning zsh's special `path` variable; the
  guided diagnostic is not a fresh passing discovery test. Earlier blocked
  Step 1 handoffs, wrong-package runs, and ineffective reviewer-disabling
  probes do not qualify successful handoffs or native-tool absence.

Each fixture directory retains its manifest/patch, installation records,
prompts, traces, and artifact audits. Synthetic reports are not actual gate
executions or a migration. No builds, rebases, pushes, or PR creation ran;
temporary credential copies are removed after testing. Earlier source-review
and offline evidence remains under the same scratch parent; superseded scratch
expectations do not replace tracked tests.

The separate root `output/` Claude run has DONE and 32 reports (29 PASS,
3 SKIP), but says 31 gates and lacks retained package provenance/full lint
baseline comparison. Leave it untouched as partial evidence, not qualification.

## Existing limitations outside compatibility scope

- Module-safety rules permit tidy/vendor in some repair cases while the hook
  blocks direct calls. Do not erase exceptions, conceal commands, or bypass
  the guard to obtain a passing run.
- Feature-gate companion/manual paths differ on PASS versus SKIP when no
  wiring applies. Both can advance; preserve the actual reported verdict.
- A vet timeout can coexist with fresh “0 build/vet errors” evidence and
  mislead the unchanged rubric. Evidence-schema checks alone do not validate
  that judgment. Step 2's unchanged `go mod verify` check verifies the module
  cache, not vendor contents, and can miss failures outside its text filters.
- Selected-commit review's root-vendor exclusion is imperfect. Existing hooks
  remain heuristic guardrails, not complete enforcement; the demonstrated
  pre-push filename collision is fixed without adding a shell parser.

Do not redesign Kubernetes/OCP migration logic, fix patterns, gate policies,
commit attribution, monitoring, or the eval harness. No duplicated packages,
provider configuration/persistence, or new hook system. If an out-of-scope
issue prevents qualification, retain the evidence and seek separate direction.
