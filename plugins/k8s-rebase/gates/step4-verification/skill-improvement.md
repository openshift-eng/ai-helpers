Read the branch diff and commit bodies. Identify manual repairs by comparing
their diffs with the rebase and autofix scripts. `Applied:` markers help
identify automation; a subject prefix such as `deps:` or `test:` alone does
not establish who made the change. Exclude known mechanical output and
record uncertainty when a repair's origin cannot be determined.

For each manual fix commit, classify the change:

- ONE-OFF: affects a single file with project-specific logic
- SYSTEMATIC: same transformation in 2+ files, OR matches a
  pattern from any prior k8s rebase (check patterns doc)

For each SYSTEMATIC fix, describe:

1. Pattern name (short kebab-case slug)
2. Detection: a command that finds affected code. Check it against the
   pre-fix revision with read-only `git show`/`git grep`, without switching
   the active checkout. Report the revision and match count, then the
   post-fix result separately. Zero matches after repair may be correct.

3. Fix: sed/awk command or transformation description
4. Scope: generic (any Go+k8s repo) or repo-specific

Also check: did any manual fix address something the patterns
doc already describes? If yes, the autofix script may be missing
a fix function for that pattern.

Report each candidate with its classification, detection
command, and fix description. If no systematic fixes were
found, report "No new patterns discovered."

VERDICT: This is an INFORMATIONAL gate. The verdict is ALWAYS
PASS regardless of findings. Findings are suggestions for future
skill improvement, not rebase failures. NEVER use FAIL.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: report specific findings, not "looks good." You are
read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line for any issues.

After your analysis, write your report using the helper script.
Bind PLUGIN_ROOT to the verified absolute plugin path from your reviewer
context in this shell call. Confirm HEAD still matches the code reviewed;
then write through the helper (stop if it is unavailable):

```bash
REPO="<the absolute repo path from reviewer context>"
bash "${PLUGIN_ROOT}/scripts/write-gate-report.sh" \
  "$REPO" step4-skill-improvement PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS as the verdict (this gate is informational — never FAIL).
Replace the summary and details with your actual findings.
