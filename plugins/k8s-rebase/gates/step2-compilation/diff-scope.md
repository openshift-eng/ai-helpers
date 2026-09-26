Identify fix commits (after the rebase, not part of the
mechanical dependency bump):
  `git log --oneline $(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)..HEAD`
Skip commits that only touch go.mod/go.sum/vendor (rebase
infrastructure). Review the remaining commits' diffs.

Count files that are not in expected categories for a k8s rebase:
Go source (.go, _test.go), module files (go.mod, go.sum), docs (.md),
CI configs (.yml/.yaml), build files (Makefile, Dockerfile, .sh, .j2),
protobuf definitions (.proto, generated .pb.go), or managed directories
(`vendor/`, `LICENSES/`, `_output/`, `third_party/`).
Adapt this list for the repo — a CSI driver legitimately modifies .proto
files; a pure controller likely does not.
Unexpected file types suggest a fix leaked beyond its intended scope.

Report count of unexpected files changed. When the legitimacy of a
file type is uncertain for this repo (e.g., a .tf file in an operator,
or a .json schema in a CSI driver), report as INFO in DETAILS and do
NOT count toward FAIL — context matters. FAIL only for files that are
clearly unrelated to the k8s dependency bump. PASS if all changed
files are in expected or plausibly-required categories.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: report specific counts, not "looks good." You are
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
  "$REPO" step2-diff-scope PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Choose the verdict from this gate's criteria. Replace the example verdict,
issue count, summary, and details with your actual findings.
