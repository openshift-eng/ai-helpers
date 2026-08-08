Review the full branch diff as a maintainer would. Does every
change serve the k8s version bump, or are there unrelated
cleanups, style changes, or logic alterations? Would a
maintainer approve this diff as-is?

Check:
- Are commits well-scoped (one concern per commit)?
- Are commit messages accurate?
- Is there any scope creep (changes beyond what the rebase needs)?
  Examples of scope creep: dependency bumps unrelated to k8s.io/*,
  reformatting unchanged code, logic changes not required by
  type/API changes, new features.
- Are any expected changes missing (e.g., version refs not
  updated, type conversions incomplete)?

Note: the autofix script applies known rebase patterns that ARE
required — these are NOT scope creep. To identify them, run:
  `PATTERNS=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "k8s-rebase-patterns.md" -path "*/k8s-rebase/docs/*" 2>/dev/null | head -1)`
  `[ -n "$PATTERNS" ] && cat "$PATTERNS"`
Any change that matches a documented pattern is expected, even
if it touches e2e infrastructure, version references, or test
configuration. Do not flag patch-level mismatches within the same minor
version as a concern — the autofix picks the latest available
patch releases. DO flag minor-version mismatches (versions
from a different minor release than the target).

VERDICT: FAIL if scope creep or inaccurate commit messages
found. PASS if all changes serve the rebase and commits are
well-scoped.

List your findings with specific commit SHAs and file:line refs.
Do not just say "would approve" — explain what you checked.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line
for any issues.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step4-maintainer-review PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

This is an INFORMATIONAL gate — always use PASS. Report scope
concerns for human review but do not FAIL. Scope discipline is
enforced by the SKILL.md instructions, not by this gate.
Replace the summary and details with your actual findings.
