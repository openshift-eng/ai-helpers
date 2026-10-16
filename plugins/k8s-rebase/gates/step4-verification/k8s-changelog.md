<!-- markdownlint-disable MD013 -->
Determine K8S_MINOR from Step 1's target record:
  `K8S_MINOR=$(grep -oE '^v0\.[0-9]+' .rebase-tmp/target-k8s-api-version.txt | cut -d. -f2)`
If that file is unavailable, read `k8s.io/api`, `k8s.io/apimachinery`, or
`k8s.io/client-go` from the primary go.mod — the first non-vendor go.mod that
requires one, which may be nested (for example `go-controller/go.mod`).
If K8S_MINOR is still empty, write INCONCLUSIVE with summary
"could not determine K8S_MINOR".

Read the Kubernetes changelog for the target minor and requested patch.
Derive the exact target from the same target record or primary go.mod above
(for example v0.37.1 means v1.37.1). Fetch that Kubernetes tag's
`CHANGELOG/CHANGELOG-1.${K8S_MINOR}.md`. Check that its headings include the
requested stable release: a successful HTTP response may contain stale notes.
If the tag file is missing or lacks the target heading, fetch the
`release-1.${K8S_MINOR}` branch file, then the exact GitHub release body as
needed. Report the actual URL and reviewed headings. Do not silently use
`.0` notes as verification of a later patch, or include a newer patch as if
it were part of the requested target.

For example, the release branch source is:
  `https://raw.githubusercontent.com/kubernetes/kubernetes/release-1.${K8S_MINOR}/CHANGELOG/CHANGELOG-1.${K8S_MINOR}.md`

If the changelog is too large, focus on these sections only:

- "Urgent Upgrade Notes"
- "Deprecation"
- "API Change"

Read these sections across the target minor's development and stable release
entries, plus changes through the requested patch. A truncated web response
is incomplete evidence, even when it summarizes other sections. Retrieve
the omitted sections using bounded raw-source reads; if that cannot be
completed, list the missing sections and report INCONCLUSIVE. Never infer
"no relevant urgent notes" from missing text.
Build a release-heading/section coverage list from the raw file before
analysis, including sections absent from an entry. A generated web summary
does not establish the headings or complete section coverage. Keep raw
line ranges so the final reviewer can check each coverage claim.

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

If the client-go changelog is unavailable, note it in DETAILS and continue.
Include the source URLs, release ranges/sections actually read, affected
symbols checked, and any missing coverage in the report.

VERDICT criteria: FAIL if any NOT ADDRESSED entry is in
"Urgent Upgrade Notes" or "API Change" and affects symbols
used by this repo. PASS if all relevant entries are ADDRESSED
or N/A and the required Kubernetes sections were read completely. If the
Kubernetes changelog is unavailable or relevant sections remain unread, write
INCONCLUSIVE with summary "Kubernetes changelog unavailable — upgrade
notes not checked".

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
Bind PLUGIN_ROOT to the verified absolute plugin path from your reviewer
context in this shell call. Confirm HEAD still matches the code reviewed;
then write through the helper (stop if it is unavailable):

```bash
REPO="<the absolute repo path from reviewer context>"
bash "${PLUGIN_ROOT}/scripts/write-gate-report.sh" \
  "$REPO" step4-k8s-changelog PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Choose the verdict from this gate's criteria. Replace the example verdict,
issue count, summary, and details with your actual findings.
