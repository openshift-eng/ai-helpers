Review the branch as a maintainer would. Does every change serve the k8s
version bump, or are there unrelated cleanups, style changes, or logic alterations?

Step 1 — read the commit history (subjects AND bodies — both are required):
  git log --format="%H%n%s%n%b%n---END---" $(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)..HEAD

  Use the commit bodies to verify: are commit messages accurate? Do they match the diff?
  Individual commits map changes to SHAs — needed for citing evidence in any FAIL finding.

Step 2 — read the aggregate diff:
  git diff $(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)..HEAD

Check:
- Are commits well-scoped (one concern per commit)?
- Are commit messages accurate?
- Is there any scope creep (changes beyond what the rebase needs)?
  Examples of scope creep: dependency bumps unrelated to k8s.io/*,
  reformatting unchanged code, logic changes not required by
  type/API changes, new features.
- Are any expected changes missing (e.g., version refs not
  updated, type conversions incomplete)?

Note: the autofix script applies deterministic rebase patterns
that ARE required — these are NOT scope creep. Changes from the
autofix are expected, even if they touch e2e infrastructure,
version references, or test configuration. Do not flag
patch-level version mismatches as scope creep — the autofix
picks the latest available patch releases. DO flag minor-version
mismatches (versions from a different minor release than the
target).

Lint-suppression check — any `//nolint:` annotation that duplicates
coverage already in `.golangci.yml` is unnecessary noise in the diff.
FAIL if the diff adds `//nolint:` comments for linters that are also
suppressed via `.golangci.yml` (exclude-functions, exclude-rules, or
linter settings). The config is the right place; inline annotations are
for rare, targeted, one-off exceptions that can't be expressed in config.
Check:
  `git diff $(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)..HEAD | grep '^\+.*//nolint:'`
For each hit, verify the suppressed linter is NOT already covered by
`.golangci.yml`. If it is — FAIL. If the annotation is genuinely
site-specific with no config equivalent — INFO only.

Deprecated-API suppression check — if the diff adds `//nolint:staticcheck`
to suppress a deprecated call, check whether a non-deprecated replacement
exists. If vendor/ does not exist in the repo, run
`go doc <import-path>.<Symbol>` to check for a replacement: if go doc
confirms a replacement exists — FAIL; if go doc is inconclusive or the
package is unavailable, note the check as unverifiable in DETAILS and do
not FAIL. If vendor/ exists, use these steps:
  1. Find the new nolint lines: `git diff $(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)..HEAD | grep '^\+.*//nolint:staticcheck'`
  2. For each, look at the suppressed call on the same or adjacent line.
  3. Identify the package: find the import path in the file's import block.
  4. Locate the deprecation notice: `grep -rn 'Deprecated' vendor/<import-path>/`
  5. The deprecation notice names the replacement function.
  6. Confirm replacement exists: `grep -rn 'func <Replacement>' vendor/<import-path>/`
  7. If the replacement exists in vendor — FAIL. The correct fix is to
     use the new API, not suppress the warning with nolint.
This pattern is a real regression because future k8s versions may remove
the deprecated function, causing compile failures after the next rebase.

VERDICT: FAIL if scope creep or inaccurate commit messages are
CONFIRMED from the diff — demonstrably present, not merely suspected.
PASS if all changes serve the rebase. Only flag what you can point
to with a specific commit SHA and file:line. If you are uncertain
whether a change is required, note it as INFO and lean toward PASS.
False FAILs block legitimate rebases; false PASSes are caught by
human review. Cite your evidence precisely.

List your findings with specific commit SHAs and file:line refs.
Do not just say "would approve" — explain what you checked.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
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

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and details with
your actual findings. Cite specific commit SHAs and file:line for
every FAIL finding — no citations means no FAIL.
