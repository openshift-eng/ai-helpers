Read ALL fix commits (autofix + agent). For each function modified
in the diff, trace data flow. Prioritize by risk tier:
- Tier 1 (full trace required): type conversions, struct field mappings,
  type assertions — data loss here is silent and hard to catch later
- Tier 1 (full trace required): map key format changes — if a modified file
  changes HOW keys are stored in a map (e.g. adds a namespace prefix, changes
  field used as key), grep ALL lookup sites across the module
  (`grep -rn 'mapName\[' --include='*.go' . | grep -v vendor/`) and verify
  every lookup produces the same key format. A mismatch causes silent runtime
  failure with no compile error or panic. CRITICAL: this cross-file check
  must cover files NOT modified by the rebase — the reader and writer are
  often in different files. Find the map variable name, then grep for BOTH
  write sites (`mapName[`) and read sites (`mapName[`) across ALL .go files.
  If any read site uses a key format that differs from the new write format,
  flag FAIL with the specific file:line of each mismatched lookup.
- Tier 2 (full trace required): error paths and error propagation —
  a missed error return causes runtime failures
- Tier 3 (pattern check): all other modifications — scan for obvious
  set-but-not-read, unused assignments, incomplete patterns
State the tier for each function. Depth matters more than breadth.

Before flagging anything FAIL: run `git show $BASE:<file>` where
`BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)`.
If the issue exists at BASE, it is pre-existing — report INFO, not FAIL.

Also check: if CRD/API schema files (manifests/*.yaml, *crd*.yaml) were modified,
compare their `description:` default values against the corresponding Go constants
in the same repo. Mismatches (CRD says X, runtime constant is Y) are false API
contracts — flag as FAIL regardless of which side was touched. Use
`grep -rn '<constant-name>' --include='*.go' .` to find the Go definition.

Flag:
- Struct copies that drop fields (FAIL)
- Error values checked in one path but ignored in another (FAIL)
- Fields set but never read — verify usage across the full module
  (`grep -rn '<field>' --include='*.go' . | grep -v vendor/`)
  before flagging. Only FAIL if truly unused repo-wide. (FAIL)
- Fields compared in one code path but not another (FAIL)
- Incomplete transformations: if a fix commit changed a pattern
  in some places but the same pattern remains elsewhere in the
  modified files, grep for the old pattern and flag each instance
  with file:line. Any single remaining instance is a finding. (FAIL)
- Variables assigned but never used (INFO — compiler catches these, do not count toward FAIL)

Scope: flag issues WITHIN modified functions or files — not
unrelated code. Code removed in the diff may reflect upstream
changes — check the current file state, not just the diff.

The autofix applies documented patterns that are intentionally
targeted changes. Do not flag autofix patterns as incomplete
unless the autofix demonstrably missed instances in files it
touched.

List EVERY function you checked and your finding for each. Do
not just say "no issues" — show what you traced. This is the
primary correctness gate — thoroughness matters more than speed.

For each finding, check the base branch:
  `BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)`
  `git show $BASE:<file> 2>/dev/null | grep -c '<pattern>'`
If the same issue exists on the base branch, it is pre-existing —
report as INFO but do NOT count toward FAIL. Only issues
introduced by the rebase trigger FAIL.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. For each issue, state the specific
fix needed. Cite file:line.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step4-logical-consistency PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
