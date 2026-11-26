Scan the go.mod diff (all modules, excluding vendor) between
the branch and its merge-base. Classify each changed dependency:

1. Direct deps with minor-version jumps:
   - `k8s.io/*` and `sigs.k8s.io/*`: label "expected rebase" (skip)
   - Third-party (everything else): flag for review
2. Deps that moved from a released version to a pseudo-version
   (e.g., vX.Y.Z → vX.Y.Z-0.2026...): flag as "pinned to
   unreleased commit"
3. Deps added or removed entirely — especially direct deps
   removed (may indicate stdlib promotion or API consolidation)
4. Pre-release direct deps (alpha, beta, rc, v0.0.0-timestamp)
   that have a newer stable release available
5. The `go` directive change (e.g., 1.25 → 1.26): note stdlib
   and language implications

Report findings for all categories above. Count third-party
minor-version jumps, pseudo-version pins, added/removed deps,
and pre-release direct deps separately.

VERDICT criteria: FAIL if any non-k8s direct dependency has an
unexpected major-version jump, or if a direct dep moved to a
pseudo-version without a corresponding k8s.io/* dependency
requiring it (check require/replace chains). PASS otherwise — flagged
items in categories 3-5 are informational, not blockers.

"Unexpected" for a major-version jump: the jump is NOT traceable to
a `k8s.io/*` transitive requirement. To verify: check whether any
`k8s.io/*` dependency in go.mod requires the new major version (via
require/replace chains). If no k8s dep requires it, the jump is
independent scope creep and should FAIL. If a k8s dep requires it,
the jump is forced and expected.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite the specific
go.mod line for any flagged dependency.

After your analysis, write your report using the helper script.
Bind PLUGIN_ROOT to the verified absolute plugin path from your reviewer
context in this shell call. Confirm HEAD still matches the code reviewed;
then write through the helper (stop if it is unavailable):

```bash
REPO="<the absolute repo path from reviewer context>"
bash "${PLUGIN_ROOT}/scripts/write-gate-report.sh" \
  "$REPO" step4-gomod-diff-analysis PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Choose the verdict from this gate's criteria. Replace the example verdict,
issue count, summary, and details with your actual findings.
