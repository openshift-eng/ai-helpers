Determine K8S_MINOR from go.mod — check api, apimachinery, or client-go
(use whichever is a direct dependency):
  `K8S_MINOR=$(grep -E 'k8s\.io/(api|apimachinery|client-go) ' go.mod | grep -v '=>' | head -1 | grep -oE 'v0\.[0-9]+' | sed 's/v0\.//')`
If K8S_MINOR is empty after this, the repo may use indirect k8s deps only —
try: `grep -E 'k8s\.io/(api|apimachinery|client-go) ' go.sum | head -1 | grep -oE 'v0\.[0-9]+' | sed 's/v0\.//'`
If still empty, write PASS with summary "could not determine K8S_MINOR — verify changelog manually."

Read the Kubernetes changelog for the target minor version.
Try the tag-based URL first (more reliable), fall back to master:
  curl -sfL "https://raw.githubusercontent.com/kubernetes/kubernetes/refs/tags/v1.${K8S_MINOR}.0/CHANGELOG/CHANGELOG-1.${K8S_MINOR}.md"
If that returns 404:
  curl -sfL "https://raw.githubusercontent.com/kubernetes/kubernetes/master/CHANGELOG/CHANGELOG-1.${K8S_MINOR}.md"

If the changelog is too large, focus on these sections only:
- "Urgent Upgrade Notes"
- "Deprecation"
- "API Change"

Filter for entries most relevant to this repo's component. For
network-focused repos, prioritize [SIG Network], [SIG API Machinery],
[SIG Node]. Adjust based on what the repo implements — a storage CSI
driver should focus on [SIG Storage], a scheduler plugin on
[SIG Scheduling]. Ignore SIGs unrelated to this repo's scope unless
they mention components this repo depends on directly.

For each relevant entry, check whether the rebase addresses it:
- grep the repo source (excluding vendor) for affected symbols
- check the branch diff for related fix commits

Report per entry:
  [section] summary: ADDRESSED / N/A / NOT ADDRESSED

Also fetch the client-go Go API changelog.
Try the tag-based URL first, fall back to master:
  curl -sfL "https://raw.githubusercontent.com/kubernetes/client-go/refs/tags/v0.${K8S_MINOR}.0/CHANGELOG.md"
If that returns 404:
  curl -sfL "https://raw.githubusercontent.com/kubernetes/client-go/master/CHANGELOG.md"

For each entry:
- Extract the changed/removed/added symbols from the code block
- grep the repo source (excluding vendor) for each symbol
- If a removed or changed symbol is used, verify the rebase
  addresses it (check the branch diff for a fix commit)
- If the symbol is not used in the repo, mark N/A

Report per entry:
  [client-go] summary: ADDRESSED / N/A / NOT ADDRESSED

If either changelog is unavailable, note it and move on.

VERDICT criteria: FAIL if any NOT ADDRESSED entry is in
"Urgent Upgrade Notes" or "API Change" and affects symbols
used by this repo. PASS if all relevant entries are ADDRESSED
or N/A. If the changelog is unavailable, write SKIP with summary
"changelog unavailable — verify k8s upgrade notes manually before
merging." PASS hides the gap; SKIP makes the court show a coverage
gap without falsely asserting the check passed.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. For NOT ADDRESSED entries, describe the code change needed. Cite commit
hashes or file:line for ADDRESSED items.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step4-k8s-changelog PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
