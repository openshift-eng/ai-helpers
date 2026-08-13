# k8s-rebase: Step Isolation and Version-Agnostic Generality

**STATUS: IMPLEMENTED.** This plan was executed — the orchestrator,
boot loader, step files, companion scripts, and hooks all exist.
Kept as an architectural decision record (ADR).

LLMs skip steps because they are satisficers, not optimizers. This
plan replaces a 981-line prompt with a state machine that gives each
step a fresh context and gates advancement on deterministic evidence.

## 1. Problem

The k8s-rebase skill works for 5 smaller repos (90%+) but fails on
ovn-kubernetes (26% true pass rate, 16/62). Of 89 total failures:

| Layer | Failures | % | Root cause | Fix |
|-------|----------|---|------------|-----|
| Agent skipping | 35 | 39% | Agent skips Steps 3-4, jumps to Step 5 | Orchestrator enforces step ordering |
| Gate flakiness | 44 | 49% | 31/33 gates are pure AI judgment, 94% flaky | Companion scripts for deterministic fast-path |
| Infrastructure | 8 | 9% | Stale branch, crashes, harness bugs | Retry + harness fixes |
| Court rejection | 2 | 2% | Real quality regressions | Investigate |

The "onion": 64% raw → 66% (infra fixed) → 78% (no skipping) →
94% (no gate flake) → 99% (only real quality issues).

**LLMs are satisficers.** Step-skipping is the dominant strategy of a
satisficing agent facing a long procedure — attentional pull toward
"done," not economic reasoning. The fix: less scope per decision,
more structure between decisions. Two clusters:
N=26 (11 failures, 100% spec=all — agent skips at step 2→3 boundary)
and N=15 (7 failures, both spec modes, 6/7 ovnk — agent skips before
step 4). Sessions used 14-50% of 1M context. 60% of "missing" land on
exact step boundaries. The Stop hook addresses 32 of 35 (91%).
Transcript evidence: *"Given the significant amount of work
remaining... let me proceed directly to Step 5."*

**spec=none vs spec=all:** No significant difference for ovnk (p=0.53).
But across all repos, spec=all significantly outperforms spec=none
(70% vs 46%, p=0.002). Non-ovnk repos are at 60-76% already.

**Gate flakiness is non-deterministic AI judgment.** Same repo+version
passes in other runs for 94% of gate failures. Only 2 of 33 gates
have companion scripts with deterministic checks.

### Glossary

- **spec=all/none**: Test modes. spec=all disables autofix+patterns
  (AI solves independently). spec=none enables all recipes (production).
- **Gates**: 33 `.md` files under `gates/step{1-4}*/` producing
  `.report` files (PASS/FAIL + rationale) via `write-gate-report.sh`.
- **N=X**: X gates missing. N=26 = stopped after step2 (7 of 33 done).

## 2. Design Principles

1. **Migrate complexity from probabilistic to deterministic.** A
   deterministic check is correct every time or wrong every time —
   test once, trust forever. An AI judgment check is correct ~94% but
   wrong unpredictably. Can it be a for-loop? Deterministic. Does it
   require reading code and judgment? Agentic. Four roles: scripts =
   what always happens, hooks = what must never happen, gates = what
   must be verified, AI prompts = what requires thinking.

2. **Clarity over cleverness.** Architecture readable from `tree`.

3. **Modern Claude Code patterns.** `${CLAUDE_PLUGIN_ROOT}`, hooks
   for enforcement, Agent delegation for step isolation.

4. **Teachability.** Code reads as a tutorial for multi-step AI
   automation with quality gates.

## 3. Architecture

### Current (monolithic, 981-line SKILL.md)

```
claude --bg session (single 1M context)
└── SKILL.md (981 lines) orchestrates Steps 1-5 via prose
    ├── Step 3: autofix + 11 gates           ← SKIPPED
    ├── Step 4: lint/test/review + 15 gates  ← SKIPPED
    └── Step 5: PR command                   ← JUMPED TO
```

### Target (orchestrator + boot loader + step agents)

```
claude --bg session
└── SKILL.md (~42 lines, boot loader)
    ├── orchestrator.sh init
    ├── orchestrator.sh status → current step
    ├── Read steps/<current-step>.md
    ├── Agent(step file + rules.md)  ← fresh context per step
    │   └── orchestrator.sh gates → fast-path PASS or launch subagents
    ├── orchestrator.sh advance → next step or BLOCKED
    └── repeat until done
```

Skip-to-Step-5 is eliminated by **defense in depth** — the orchestrator
only advances when all gates for the current step have fresh PASS
reports, and the agent never sees other steps' instructions. Not
information-theoretic isolation (the agent could still skip within a
step), but eliminates the dominant failure mode.

### Directory layout

```
plugins/k8s-rebase/
  # Runtime:
├── skills/k8s-rebase/SKILL.md        # Boot loader (~42 lines)
├── steps/                             # Step instructions
│   ├── rules.md                       # Shared rules (module safety, etc.)
│   └── step{1-5}*.md                  # One file per step
├── gates/                             # 33 gate files + companion scripts
│   ├── step1-rebase/                  # 1 gate
│   ├── step2-compilation/             # 6 gates
│   ├── step3-autofix/                 # 11 gates (+ 2 existing .sh)
│   └── step4-verification/            # 15 gates
├── scripts/
│   ├── k8s-rebase.sh                  # Deterministic dep bump
│   ├── k8s-rebase-validate.sh         # Build/vet/lint/test runner
│   ├── k8s-rebase-autofix.sh          # Scripted fix patterns
│   ├── k8s-rebase-orchestrator.sh     # NEW: state machine + gate runner
│   ├── write-gate-report.sh           # Gate report writer
│   └── gate-script-lib.sh             # NEW: companion script boilerplate
├── hooks/
│   ├── block-push.md                  # Existing (PreToolUse)
│   ├── block-module-ops.md            # NEW: blocks go mod tidy/get/etc.
│   ├── block-vendor-edit.md           # NEW: blocks /vendor/ edits
│   └── hooks.json + stop-hook.sh      # NEW: orchestrator-based Stop hook
├── docs/k8s-rebase-patterns.md
├── plans/
└── test/
```

## 4. Components to Build

### 4.1 k8s-rebase-orchestrator.sh (~250-350 lines)

Unified bash script. Single source of truth for step ordering, gate
counting, and companion script execution. Replaces the 33-gate
checkpoint, the standalone Stop hook logic, and the gate runner.

**`init <repo> <version>`** — if no state.json exists: fresh start
(create `.rebase-tmp/state.json`, gates directory, `.session-active`
sentinel, clear any stale reports). If state.json exists and is valid:
resume at the recorded step without clearing reports. Logs which path.

**`gates <step>`** — iterate gate .md files for this step's directory.
For gates WITH companion `.sh`: run the script. If PASS
(`NEW_ISSUES=0`), call `write-gate-report.sh` directly — no subagent.
Output: RESOLVED list (fast-path PASS, zero-flake deterministic
verdict) and PENDING list (need subagents for AI judgment).

**`advance`** — check all gate reports for current step:
- Every report must exist and contain PASS or FAIL verdict
- Stale detection: modify `write-gate-report.sh` to store HEAD SHA
  (currently not written). Report SHA ≠ current HEAD = stale
- Contract: commit all fixes THEN gates THEN advance (never reverse)
- All present + fresh → bump step, update timestamps
- Missing/stale/failing → exit 1 with specific gate names + paths
- After 3 failed advances → force-advance with warning

**`status`** — compact table: per-step gates expected/actual/PASS/FAIL,
elapsed time. Consumed by Stop hook, test harness, and `cmd_watch`.
Must work WITHOUT state.json (reconstruct by scanning .report files
and finding the first step with incomplete gates). state.json is a
cache for timestamps, not the source of truth.

**Exit code contract:** 0=success, 1=blocked (normal — gates not met),
2=usage error, 3+=internal error. The boot loader should stop on ≥2
and include the error in its response.

**Worktree awareness (CRITICAL):** The orchestrator must accept the
repo path as an argument (from the agent's `cwd`, which is the
worktree). Gate counting uses PLUGIN_ROOT derived from `$0`. Sessions
run in `.claude/worktrees/<branch>/`, not the repo root.

### 4.2 SKILL.md rewrite (~42 lines)

Boot loader pattern. SKILL.md is loaded statically (full text at
invocation), so it must be short — no step-specific instructions.

Content: frontmatter, 1-paragraph purpose, bash block to run
`orchestrator.sh status`, instruction to Read the matching step file
via Read tool, instruction to run `orchestrator.sh advance` after
completing work, recovery instructions (`orchestrator.sh status`
shows where to resume).

Absorbs baseline fixes: "current branch" (not "default branch"),
remove master-checkout recovery, `${CLAUDE_PLUGIN_ROOT}` for paths.

Preamble reframe: "Steps 3-4 are where you add unique value — the
quality gates that prevent CI rejection."

**Subagent prompt template** (for Agent() calls to step agents):
Include: repo path, k8s version, `${CLAUDE_PLUGIN_ROOT}` (resolved
at load time), "Read rules.md first", step file path, gate directory
path, structured return format (STEP_VERDICT, GATES_PASSED, COMMITS).

**Progress markers** in each step file heading: "PROGRESS: 20%
complete" (step 1), "40%" (step 2), "60%" (step 3), "80%" (step 4),
"95%" (step 5). Counters agent's "I've done enough" bias.

**Agent delegation details:**
- Hooks fire for subagents at depth 1 (session-level registration).
  Depth-2 behavior needs empirical verification — keep critical
  rules in prompt text as defense-in-depth alongside command hooks.
- Subagent crashes don't kill the session. Parent gets notified and
  can retry. Orchestrator's `advance` shows the step as incomplete.
- Parameters pass via prompt text (repo path, version, PLUGIN_ROOT).
  `${CLAUDE_PLUGIN_ROOT}` resolves at skill load time (text-sub).
- Token budget is shared across all subagents — companion scripts
  reduce budget consumption by resolving gates deterministically.

### 4.3 Step files (steps/*.md, ~150-200 lines each)

Extract from current 981-line SKILL.md into 6 files:
- `rules.md` — shared rules (module safety, commit discipline, scope,
  container commands, gate-fix loop protocol, nesting cap)
- `step1-rebase.md` — run rebase script, 1 gate
- `step2-compilation.md` — fix loop with validate.sh, 6 gates
- `step3-autofix.md` — run autofix, discovery checklist, 11 gates
- `step4-verification.md` — lint/test/review, 15 gates (~240 lines
  in current SKILL.md — extract `--bump-tools` to separate file and
  move test-splitting RAM examples to docs to fit under 200 lines)
- `step5-pr.md` — PR command generation, cleanup

Each step file starts with "Read rules.md first." Each ends with
"Run orchestrator.sh advance."

**Extraction challenges:**
- Lines 192-246 (steps 2-5 shared preamble with subagent rules,
  container commands) → rules.md, not step-specific files
- OCP version mapping (lines 882-890 in Step 5) needed by Step 2 →
  hoist to rules.md or docs/ocp-mapping.md to avoid duplication
- Gate-fix loop has per-step variations (Step 1 "stop", Steps 2-3
  "proceed", Step 4 "re-validate --no-test") → canonical pattern in
  rules.md with per-step override notes in each step file

Autofix signal cleanup lives in step3:
- autofix.sh: `RESULT: FAIL` → `RESULT: ITEMS_REMAINING`, `exit 1` → `exit 0`
- Move "FAIL is normal" before the bash block
- Add "Regardless of output, proceed to gates"
- Fix line 520 contradiction ("cat" → "let subagent Read")

See `plans/autofix-patterns-redesign.md` for the autofix function
disposition (18 kept, 9 removed) and patterns doc trimming.

**Robustness improvements** (in rules.md or step files):
- Oscillation detection: stop gate-fix loop if a previously-passed
  gate regresses after fixing a different gate
- Dirty-tree check: `git status --porcelain` at start of each
  gate-fix loop iteration
- go.mod broadening: use `find` for go.mod (catches multi-module repos)
- Checkpoint tightening: orchestrator's `advance` handles this
  (detects "not PASS" instead of just "is FAIL")

### 4.4 Companion scripts (4 priority + library)

**Primary value: reliability, not cost savings.** Replacing flaky AI
judgment with zero-flake deterministic evidence. The net subagent
count may not drop (forcing continuation adds back skipped gates),
but each gate's verdict becomes reproducible. The orchestrator's
`gates` subcommand runs these; no separate mechanism needed.

**4 priority scripts** (following crd-validation.sh pattern):
1. `build-vet.sh` — `go build && go vet`, diff vs base branch.
   Shared by step2/build-vet + step4/build-vet-recheck.
2. `version-consistency.sh` — parse go.mod, check k8s.io/* versions.
3. `go-version-check.sh` — compare `go` directive across files.
4. `major-version-imports.sh` — grep for bare `k8s.io/klog`.

**gate-script-lib.sh** — shared boilerplate: BASE merge-base
computation (with master→main fallback), cd to repo, exit-on-empty,
NEW_ISSUES counter, self-imposed timeout watchdog (`timeout 300`,
configurable via `GATE_TIMEOUT`), trap that writes FAIL report on
unexpected exit (crash/OOM still produces a report, not limbo).
Always `set -euo pipefail`. Exit 0 for "nothing to check." Exit 1
only for genuine infrastructure failures. Quote all variable
expansions in loops (paths with spaces).

**Gate .md integration pattern** (from crd-validation.sh):
Each gate .md with a companion script has a `MANDATORY FIRST STEP`
block that locates and runs the script. RULE 1: `NEW_ISSUES=0` →
fast-path PASS (write report, no AI analysis). RULE 2: AI only
evaluates items the script flagged as new/changed.

**Gate script discovery:** Convention-based — companion `.sh` has same
basename as the gate `.md` (e.g., `build-vet.md` → `build-vet.sh`).
The orchestrator checks `[[ -x "${gate_md%.md}.sh" ]]`. Simpler than
YAML frontmatter; add frontmatter later if metadata needs grow.

**Three-tier gate architecture** (33 total):
- **Tier 1: Fully deterministic** (~19) — companion script produces
  verdict. Includes 8 informational (always PASS) + 11 with machine-
  checkable predicates. Zero flakiness.
- **Tier 2: Evidence + interpretation** (~8) — script gathers
  deterministic evidence (run staticcheck, diff vs base branch), AI
  judges only flagged items. Highest-value engineering target for
  expanding companion scripts after the initial 4.
- **Tier 3: Fully agentic** (~6) — AI reads code, traces data flow,
  makes semantic judgments. Always launch subagent. Inherently
  non-deterministic.

Gate files retain inline rule copies (module safety, etc.) as
defense-in-depth until depth-2 hook firing is empirically verified.

### 4.5 Stop hook (~10 lines + hooks.json)

Simplified by the orchestrator. The hook reads `cwd` from stdin JSON,
runs `orchestrator.sh status "$CWD"`, and if state ≠ done, outputs
`{"decision": "block", "reason": <status output>}`. The orchestrator
handles all complexity (gate counting, stale detection, iteration
tracking, INCOMPLETE markers).

INCOMPLETE handling: test harness records as third verdict. Production:
Step 5 degrades to `--draft` PR with WARNING. Court skipped.

`stop_hook_active` check: exit 0 if another hook already blocked
(multi-hook safety). PLUGIN_ROOT from `$0` dirname.

### 4.6 Enforcement hooks (2 new .md files)

- **block-module-ops.md** — PreToolUse on Bash. Block `go mod tidy`,
  `go get`, `go mod vendor`, `go mod edit`, `go generate`, `go run`.
  #1 most-violated prohibition, most destructive (MVS corrupts pins).
  Safe: PreToolUse sees top-level command only, not subprocess execution
  inside scripts — so `bash k8s-rebase.sh` (which runs go mod tidy
  internally) is NOT blocked. Add `.session-active` check so hook
  doesn't interfere with non-rebase sessions.
- **block-vendor-edit.md** — PreToolUse on Edit/Write. Block paths
  containing `/vendor/`. #2 most-violated, wastes hours.

### 4.7 Observability

**results.tsv: 4 new columns** (model, gates_tally, duration_s,
diff_hunks). Already computed in `_do_record_one`, just not persisted.
Also add `fail_code` column for failure taxonomy.

**events.jsonl:** `_telem()` bash function (~3 lines) emits 8 event
types (step-enter, step-end, gate-verdict, fix-commit, script-done,
autofix-result, subagent-spawn, build-result). ~20 instrumentation
points. Enhanced `cmd_watch` shows current activity. Post-mortem:
`jq 'select(.verdict=="FAIL")' events.jsonl`.

**Failure taxonomy** (7 codes, 3 layers):
- INFRA-STALE, INFRA-CRASH, INFRA-NOGATE → retry
- SKIP-BOUNDARY, SKIP-EFFORT, SKIP-PARTIAL → orchestrator
- GATE-FLAKE, COURT-FAIL → companion scripts / investigate

**Self-improving loop:** Harvest skill-improvement gate suggestions
into `suggestions.jsonl` during `auto_record()`. `make suggestions`
aggregates (count≥3 = automation candidate). `make improve` templates
new autofix functions. No LLM in the improvement loop.

## 5. Commit Sequence

7 commits. Old SKILL.md keeps working until commit 6 (the switchover).

1. **Companion scripts** (gate-script-lib.sh + 4 .sh) — zero risk
2. **Enforcement hooks** (block-module-ops.md, block-vendor-edit.md)
3. **Orchestrator** (k8s-rebase-orchestrator.sh) — linchpin, depends on 1
4. **Step files** (rules.md + 5 step files) — depends on 3
5. **Stop hook** (stop-hook.sh + hooks.json) — depends on 3
6. **SKILL.md boot loader** — **THE SWITCHOVER**, depends on 3-5
7. **Observability + court fix** (results.tsv, events.jsonl, force
   juror tool use) — independent of 6

## 6. Success Criteria

**End state:** ovnk spec=all pass rate 60-80%+ (from 26% baseline).
Per-version floor 55%. Non-ovnk repos: no drop >15pp. Zero
step-skipping failures. Companion-scripted gates flaky rate <10%.

**Validation:** 15+ ovnk runs (5 per version), ~2 days compute,
$250-900. Rollback if any per-version rate drops >10pp vs baseline.
Gate PASS is minimum bar; court PASS is quality confirmation.
Strengthen court: force juror tool use (~5 lines in test-skill.sh
juror prompt — currently 0/15 jurors use their git show/diff/Read
tools, rubber-stamping without verification).

| Metric | Pessimistic | Optimistic |
|--------|-------------|------------|
| After orchestrator + hooks | 45% | 65% |
| After companion scripts | 55% | 75% |
| Ceiling (all layers addressed) | 84%+ | 94%+ |

## 7. Risks and Caveats

| Risk | Severity | Mitigation |
|------|----------|------------|
| Model-version coupling | Critical | Log model ID per run. Continuous regression testing. |
| Goodhart's Law | High | Companion scripts with deterministic evidence. Provenance validation. |
| Unbounded runtime | Medium | `--max-turns` / `--max-budget-usd`. CLI 8-block cap. |
| Depth-2 nesting untested | High | Test on CNCC first. Keep inline rule copies. |
| PLUGIN_ROOT not shell env | High | Gates keep `find`. Steps get literal paths via text-sub. |

**Data caveats:**
- Baseline includes 42% false-positive passes. True rate: 26% (16/62).
- Per-version: 1.34.1=37%, **1.35.3=12%** (blocker), 1.36.2=35%.
- "missing → pass" is the weakest assumption (balloon squeeze).
- spec=all vs spec=none: p=0.087 when time-controlled (temporal confound).

**Architectural assumptions:**
- SKILL.md is static (loaded in full) — true isolation needs Agent delegation.
- Depth-2 hook firing unverified — keep inline rule copies.
- 112 "no-token" sessions: 76% harness artifacts, ~7% real infra failures.

## 8. Not In Scope

- Discovery procedures replacing version-specific recipes (future)
- Multi-repo coordinator (library-go → ovnk → CNO sequencing)
- 2-of-3 voting for AI-judgment gates (too expensive: 9 invocations)
- Gate consolidation (33 → ~28)
- Fix maintainer-review.md contradiction (FAIL vs always PASS)
- CI integration (draft PRs for Prow feedback)
- Decision provenance: record WHY each fix was chosen in rebase report
- Blocked dependency detection: check upstream deps before starting
  (concrete first step toward multi-repo coordinator)
- Autofix A/B test: controlled experiment to resolve the p=0.002
  temporal confound (determines whether discovery procedures are needed)
- Close the CI loop: create draft PR, monitor CI, investigate failures,
  iterate (Step 5 could suggest `/loop 5m check CI, explore failures`)
- Downstream handling: openshift/ovn-kubernetes Dockerfiles, OTE tests,
  release branches — none of the 33 gates check downstream concerns
- Starter template for other teams
