# Eval Improvement Backlog

Future work for the k8s-rebase eval suite. Items are ordered by
implementation priority.

---

## 1. ✓ DONE — Expand to full repo×version matrix (16 total cases)

16 cases across 1.34.1 (4 repos), 1.35.3 (6 repos), 1.36.2 (6 repos).
See `evals/README.md` for the case table. SHAs from `test/config-1.3{4,5,6}.yaml`.

---

## 2. ✓ DONE — Add `go_mod_version_correct` deterministic judge

**Gap:** `go_mod_and_vendor_modified` confirms go.mod changed but not
*what it changed to*. A skill that bumped to 1.35 when asked for 1.36
passes all current judges.

go.mod is not in `COURT_EXCLUDES`, so the hunk appears in `diff.patch`
directly — no new output file needed.

**Judge logic:**

```python
import json, re
all_f = {**outputs.get("files", {}), **outputs.get("modified_files", {})}
# ... standard infra_error exclusion block ...
diff_files = {k: v for k, v in all_f.items() if k.endswith("diff.patch")}
kg_files = {k: v for k, v in all_f.items() if k.endswith("known-good.patch")}
if not diff_files:
    return (False, "No diff.patch found")
diff = list(diff_files.values())[0]
_anchors = ["k8s.io/api ", "k8s.io/client-go "]
diff_minor = None
for _anchor in _anchors:
    _m = re.search(
        r'^\+\s+' + re.escape(_anchor) + r'v0\.(\d+)\.', diff, re.MULTILINE)
    if _m:
        diff_minor = int(_m.group(1))
        break
if diff_minor is None:
    return (True, "No k8s.io/api or k8s.io/client-go anchor in diff.patch — skip")
kg_minor = None
if kg_files:
    kg_text = list(kg_files.values())[0]
    for _anchor in _anchors:
        _m = re.search(
            r'^\+\s+' + re.escape(_anchor) + r'v0\.(\d+)\.', kg_text, re.MULTILINE)
        if _m:
            kg_minor = int(_m.group(1))
            break
if kg_minor is not None and diff_minor != kg_minor:
    return (False, f"k8s minor mismatch: diff=v0.{diff_minor}.x, known-good=v0.{kg_minor}.x")
if kg_minor is None:
    _removed = re.search(
        r'^-\s+k8s\.io/(?:api|client-go)\s+v0\.(\d+)\.', diff, re.MULTILINE)
    if _removed and int(_removed.group(1)) >= diff_minor:
        return (False,
                f"k8s minor not increased: was v0.{_removed.group(1)}.x, now v0.{diff_minor}.x")
return (True, f"k8s bumped to v0.{diff_minor}.x")
```

**Design notes:**

- Returns True (skip) when neither anchor found — avoids false failures
  on unusual repos.

- Brand-new dependency (no removal line): direction check skipped,
  returns True — `go_mod_and_vendor_modified` already confirms changes.

**Threshold:** `go_mod_version_correct: {min_pass_rate: 1.0}`

---

## 3. ✓ DONE — Add `step5_pr_command_printed` deterministic judge

**Gap:** `pr_command_never_attempted_or_blocked` checks the command was
not *executed*. It does not verify it was *presented* to the user. A
skill that skips step5-pr.md entirely still passes.

**Implementation:** Add before line 192 in `run-rebase.sh` (where
`session-output.json` is deleted):

```bash
jq -rs '[.[] | select(.type=="assistant")
             | .message.content[]?
             | select(.type=="text")
             | .text] | join("\n")' \
  "$OUTPUT_DIR/session-output.json" \
  > "$OUTPUT_DIR/pr-command.txt" 2>/dev/null || true
```

**Judge:**

```python
pr_files = {k: v for k, v in all_f.items() if k.endswith("pr-command.txt")}
if not pr_files:
    return (False, "No pr-command.txt found (run-rebase.sh update needed)")
content = list(pr_files.values())[0]
lines = content.splitlines()
cmd_idx = next((i for i, l in enumerate(lines) if "gh pr create" in l), None)
if cmd_idx is None:
    return (False, "No 'gh pr create' found in assistant text")
# In practice: gh pr create --title "..." --body "$(cat <<'EOF'
# 4-line window handles any variant where flags split across lines.
title_window = lines[cmd_idx:cmd_idx + 4]
if not any("--title" in l for l in title_window):
    return (False, "'--title' not found within 4 lines of 'gh pr create'")
body_window = lines[cmd_idx:cmd_idx + 5]
if not any("--body" in l for l in body_window):
    return (False, "'--body' not found within 5 lines of 'gh pr create'")
return (True, "gh pr create command with --title and --body found")
```

**Threshold:** `step5_pr_command_printed: {min_pass_rate: 1.0}`

---

## 4. ✓ DONE — Add `rebase_gap_analysis` LLM judge

**Gap:** `rebase_correctness` is holistic — a judge that hallucinates
"looks fine" passes with no adversarial check. A gap-analysis judge
forces explicit enumeration of MISSING and EXTRA files before scoring,
changing what the model attends to first.

LLM judges have no tool access — diff-only evidence only.

**Prompt structure:**

```text
You are reviewing a Kubernetes dependency rebase for correctness gaps.
Work in two phases before scoring:

If known-good.patch is empty, skip Phase 1 and score on Phase 2 only.
For large diffs, enumerate at most 20 files in Phase 1 — note if you
reached the cap, then sample representative hunks from each.

PHASE 1 — MISSING: List files changed in known-good.patch that have no
counterpart change in diff.patch (stop at 20 files). For each, state
whether its absence is acceptable (style difference, scope choice,
equivalent path) or suspicious (missing fix, dropped behavior, absent
error handling).

PHASE 2 — EXTRA: List every file changed in diff.patch that has no
counterpart change in known-good.patch. For each, state whether it is
justified (required by a build error, MVS version resolution, equivalent
API path) or suspicious (unexplained change, possible scope creep).

[same diff sections as rebase_correctness]

Score 1: Unexplained MISSING items LIKELY to break compilation or
         runtime based on diff evidence, or EXTRA items that introduce
         regressions. (Score 1 only when diff evidence is strongly
         indicative — compilation cannot be verified without tooling.)
Score 2: Suspicious gaps with weak justification.
Score 3: All gaps explained, but explanations are vague or unverifiable.
Score 4: All gaps explained with specific, plausible justification.
Score 5: No unexplained gaps; differences are all acceptable variance.
```

**Note on 20-file cap:** Best-effort instruction only — the LLM cannot
enforce it mechanically. If context explosion becomes a problem on
large diffs, apply the cap runner-side by truncating known-good.patch
to the first N file hunks before passing to the judge.

**Threshold:** `rebase_gap_analysis: {min_mean: 2.5}`

**Calibrate before merging threshold.** Run on case-002 to establish
expected score range — this judge may be stricter than `rebase_correctness`.

---

## 5. ✓ DONE — Fix stop-hook turn-burn during step1 background script

**Gap:** The stop hook fired on every agent yield while the step1 rebase
script ran in the background (go mod vendor on large repos: 5–30 min).
Each block consumed a turn. Repos with large vendor trees (multus-cni:
2086 files) exhausted the turn budget before the script finished.

**Fix:** Stop hook now checks `step1.pid` liveness and `step1-result.txt`
existence. If the PID is alive and result file not yet written, it yields
instead of blocking. Once the script finishes (result written or PID gone),
normal gate enforcement resumes.

Also strengthened `step1-rebase.md`: single 30-min background wait instead
of repeated short polls.

**Validated:** case-013 (multus-cni @ 1.35.3) went from 20 turns / DONE:false
to 9 turns / DONE:true after the fix.

---

## 6. ✓ DONE — Fix runner leaving stale bump branches in cached clone

**Gap:** Cached eval repo clones accumulated stale `bump*` branches from
prior runs. The rebase script warned "on bump1.36, not default branch main"
and the agent mis-diagnosed the repo as already at 1.36, refusing to proceed.

**Fix:** `run-rebase.sh` now detaches HEAD then deletes all `bump*` branches
before invoking claude, so every run starts clean.

---

## 7. Add negative test case

**Gap:** All cases are "skill succeeds." LLM judges are never tested
against a deliberately bad diff.

**Harness limitation:** No `max_mean` threshold type — a negative case
cannot be automatically asserted to score below a ceiling. Implement
manually at calibration time; automate when `max_mean` is supported.

**Design:** Separate eval YAML (`eval-k8s-rebase-negative.yaml`) with
`cases/negative/` dataset and its own runner. Runner plants pre-baked
bad artifacts without invoking the skill. `$CASE_DIR` is not
harness-provided for cli runners — resolve fixtures via `$AI_HELPERS_DIR`:

```bash
FIXTURES_DIR="$AI_HELPERS_DIR/plugins/k8s-rebase/evals/cases/negative/${1}/fixtures"
mkdir -p output
cp "$FIXTURES_DIR/"* output/
echo '{"status":"completed","reason":""}' > output/run-status.json
echo '{"token_usage":{"input":0,"output":0},"cost_usd":0,"num_turns":0,"model":"synthetic"}' \
  > output/metrics.json
```

Synthetic diff: plausible but wrong rebase — correct go.mod bump, but
scope-creep changes and one silently dropped API fix from known-good.
Deterministic judges seeded with PASS fixtures intentionally — negative
case tests LLM judges only.

---

## 8. ✓ DONE — Fix orchestrator rejecting SKIP verdict as non-passing

**Gap (found 2026-09-14 via case-012 live run):** `report_has_pass` in
`k8s-rebase-orchestrator.sh` only matched `VERDICT: PASS`. Any gate that
correctly wrote `VERDICT: SKIP` (e.g. `step2-type-conversions` when the
rebase has no type conversion changes) was treated as FAILING. The
orchestrator blocked 3 times then force-advanced, wasting turns and
writing `FORCE_ADVANCE` to `force-advance.log`.

**Fix:** `report_has_pass` now matches `VERDICT: (PASS|SKIP)`.

**Evidence:** `eval judge all_gates_resolved` already accepted SKIP (correct);
only the orchestrator gate check was wrong. Single-line fix, no test needed
beyond the next eval run.

---

## 9. ✓ DONE — Fix openshift/client-go @latest pulling wrong k8s minor

**Gap (found 2026-09-14 via case-012 live run):** When the Go proxy
returned empty for `release-4.22.info` (or the branch info was unavailable),
`k8s-rebase.sh` fell back to bare `go get github.com/openshift/client-go`
(`@latest`). The `@latest` version at run time was
`v0.0.0-20260810202730-ddca5e0b7146`, which requires `k8s.io/api v0.36.2`.
MVS upgraded `k8s.io/api` to v0.36.2, conflicting with `k8s.io/kubectl
v0.35.3` (which imports `scheduling/v1alpha1` removed in k8s 1.36). The
`go mod tidy` retry loop only handles `unknown revision v0.0.0` errors, so
the conflict was fatal and the rebase script exited 1.

**Root cause:** The `@latest` fallback for k8s-version-locked packages
(`client-go`, `api`) is unsafe. These packages use timestamp pseudoversions
across multiple OCP branches; `@latest` picks the newest commit regardless
of which k8s minor it targets.

**Fix (two parts):**

1. `_validate_openshift_k8s_minor` — after resolving the branch version,
   fetches the package's `go.mod` from the proxy and checks that its
   `k8s.io/api` requirement matches the target minor. Rejects versions that
   pin a different minor; falls back to the `@latest`-skip path below.

2. In `derive_go_gets` Rule 2b: when `_os_ver` is empty for `client-go` or
   `api` (either proxy lookup failed or the validated version was rejected),
   skip the `go get` entirely rather than emitting bare `go get`. `go mod
   tidy` retains the existing version, which is safer than @latest pulling
   the wrong k8s minor. `library-go` and `build-machinery-go` do not pin
   k8s directly and continue to use bare `go get` when unresolved.

---

## 10. ✓ DONE — Fix run-rebase.sh failing on cached clone with uncommitted changes

**Gap (found 2026-09-15 via case-004 re-run):** When the skill leaves
modified files in a cached eval clone (e.g. a partial rebase that changed
Go source files but didn't commit them), the subsequent run's
`git checkout --detach <sha>` fails: "Your local changes would be overwritten
by checkout." The ERR trap fires and the entire run records `infra_error`
before the skill is even invoked.

**Fix:** Added `git restore . 2>/dev/null || git checkout -- . 2>/dev/null || true`
plus an early `git clean -fdx` immediately after restoring `origin`'s fetch URL
and before `git fetch`. This discards any working-tree debris from a prior run
before the checkout that might reject them.

**Evidence:** case-004 re-run logged "error: Your local changes to the following
files would be overwritten" for `pkg/bpf-mgr/lib-bpfman.go` and 5 other files.

---

## Latent risks

**LLM judge `outputs.files` only:** `prompt:` judges iterate
`outputs.files.items()` only. `check:` judges defensively merge both
`files` and `modified_files`. If the harness places output files in
`modified_files`, LLM judges receive empty diffs and score silently on
nothing. Fix if empty diffs appear: use
`{% for path, content in (outputs.files | combine(outputs.modified_files | default({}))).items() %}`.

**`--case` flag unsupported:** `claude plugin eval --case <name>` does not
work with cli runner dataset mode. Use `run-rebase.sh` directly for single
case runs (see `evals/README.md`).

**Turn budget on gate-heavy repos:** case-012 hit the 200-turn limit during
step 3/4 gate reviews. Root cause: the force-advance bug (now fixed in item 8)
consumed extra turns. Verify the 200-turn budget is sufficient after the fix.
If light cases still hit the limit, investigate whether step 3/4 gate counts
can be reduced or batched more efficiently.
