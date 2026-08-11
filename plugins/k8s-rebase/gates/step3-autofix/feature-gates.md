EVIDENCE (read before judging): if `.rebase-tmp/gates/step3-feature-gates.evidence` exists,
run `git rev-parse HEAD` and compare it to the file's `HEAD:` line.
- Match: Read the file first and treat its `SUMMARY:`/facts as ground truth for this gate.
  `WIRED_GATES` lists every gate found wired in the repo. `VENDOR_MISSING` lines identify
  gates wired in source but absent from vendor (likely stale). `VENDOR_UNKNOWN` lines
  identify gates where vendor/k8s.io/*/features/known_features.go is absent — vendor
  coverage is unverifiable; judge from manual check below. `LAYER*_MISSING` lines
  identify specific wiring gaps. Gates not mentioned as MISSING or UNKNOWN were
  confirmed covered — do not re-grep them. `NEW_ISSUES=0` means all wired gates are
  current and fully covered.
  `SUITE_NO_SETFROMMAP` lists *_suite_test.go files with RegisterFailHandler but no
  SetFromMap. In k8s 1.35+, pkg/features.init() can override DefaultMutableFeatureGate
  and defeat the env-var-based gate disable. To find which files the human rebase
  actually modified, run:
    git log --oneline | grep -iE 'feature.gate|WatchListClient|SetFromMap|disable.*gate'
  then `git show <that-commit> -- <file>` for each flagged file. Copy the exact pattern
  from the human commit (import alias, gate names, and map keys all vary by repo and
  k8s version). Add SetFromMap ONLY to the files the human modified — not all flagged
  files. This is a quality concern, not a compile/vet failure. PASS if NEW_ISSUES=0;
  addressing the affected suites improves robustness but is not required for PASS.
  If evidence shows `SKIP`: no feature gate wiring exists in this repo — verdict PASS.
- Differ or file absent: evidence is stale/missing — judge from scratch using the checks
  below. Do NOT PASS on the strength of absent or stale evidence.

Run this applicability check first:
```bash
REPO="<the repo path from the first line of your prompt>"
FG_REFS=$(grep -rn 'KUBE_FEATURE_\|SetFromMap' "$REPO" --include='*.sh' --include='Makefile*' --include='*.go' 2>/dev/null | grep -v vendor/ | head -20)
if [ -z "$FG_REFS" ]; then
  echo "No feature gate references found"
fi
```
If the applicability check finds no SetFromMap or KUBE_FEATURE_
references, the gate does not apply to this repo — write a SKIP
report and stop.

If references ARE found: check if feature gates referenced in
test files (SetFromMap calls, os.Setenv/t.Setenv with
KUBE_FEATURE_ vars, shell script exports) still exist in
vendor/k8s.io/ (grep for the quoted gate name). Report any
gates that are referenced but missing from vendor.

Search the entire repo for KUBE_FEATURE_ references:
  `grep -rn 'KUBE_FEATURE_' --include='*.sh' --include='Makefile*' --include='*.go' "$REPO" | grep -v vendor/`
This covers shell exports, Makefile variables, AND Go code
(os.Setenv, t.Setenv, SetFromMap calls). Report count of
files with missing or stale gates.

MANDATORY pre-existing check — run for EVERY finding:

```bash
BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
# For each gate <gate_name> referenced in source but missing from current vendor:
base_in_vendor=$(git grep -l "$gate_name" "$BASE" -- 'vendor/k8s.io/' 2>/dev/null | wc -l)
# base_in_vendor > 0 → gate WAS in vendor before rebase, now removed → NEW
# base_in_vendor == 0 → gate was also missing from base vendor → PRE-EXISTING
```

The correct target is vendor, not the source file. A gate name
appearing in the source on base says nothing about whether it was
valid at that time — check whether it existed in the BASE vendor.
If ALL findings are pre-existing (base_in_vendor == 0 for each),
verdict MUST be PASS.

Also check export completeness in scripts modified by the rebase:

```bash
_BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)
# For each .sh or Makefile* that the rebase touched:
for script in $(git diff --name-only "$_BASE"..HEAD -- '*.sh' 'Makefile*'); do
  # Was a new KUBE_FEATURE_*=false export added to this script?
  if git diff "$_BASE"..HEAD -- "$script" | grep -q '^\+.*export KUBE_FEATURE_.*=false'; then
    # Check that all sudo calls in this script pass env vars through
    if grep -q 'sudo ' "$script" && \
       ! grep -q 'sudo -E\|sudo --preserve-env' "$script"; then
      echo "FAIL: $script has new KUBE_FEATURE_*=false export but bare sudo (env dropped)"
    fi
  fi
done
```

If any script has a newly-added `export KUBE_FEATURE_*=false` AND bare `sudo`
(not `sudo -E` or `sudo --preserve-env`), FAIL — the env var is silently
dropped when the test binary runs as root. Fix: `sudo -E binary`.
If no scripts are modified by the rebase, skip this check entirely.

VERDICT: FAIL if count of files with missing or stale feature
gates > 0 (excluding pre-existing), OR if any newly-exported
KUBE_FEATURE_ flag is silently dropped at a sudo boundary.
PASS if all feature gates are current and all exports reach
their intended test invocations.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: report specific counts, not "looks good." You are
read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line for any issues. For each missing gate, report the gate name and the fix needed.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
SCRIPT=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)
if [ -n "$SCRIPT" ]; then
  bash "$SCRIPT" "$REPO" step3-feature-gates PASS 0 "your one-line summary" \
    "detail line 1" "detail line 2"
else
  mkdir -p "$REPO/.rebase-tmp/gates"
  printf 'VERDICT: PASS\nISSUES: 0\nSUMMARY: your one-line summary\nDETAILS:\ndetail line 1\ndetail line 2\n' \
    > "$REPO/.rebase-tmp/gates/step3-feature-gates.report"
fi
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
