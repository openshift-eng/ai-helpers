<!-- markdownlint-disable MD013 -->
Identify all non-k8s dependencies whose minor version changed in this rebase:
  `git diff $(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)..HEAD -- go.mod | grep '^[+-]' | grep -v 'k8s.io\|sigs.k8s.io\|^[+-][+-]' | sort`
For any dep where the minor version changed (e.g., v1.2→v1.4, not v1.2.3→v1.2.5),
read its release notes. Common examples: KIND, MetalLB, KubeVirt, golangci-lint,
controller-runtime — apply the same lookup to any dep found by the diff above.

Sources:

Sources by dep:

- KIND: gh api repos/kubernetes-sigs/kind/releases --paginate (has
  explicit "Breaking Changes" headings in .body)

- MetalLB: curl the in-repo release notes at
  raw.githubusercontent.com/metallb/metallb/main/website/content/release-notes/_index.md

- KubeVirt: gh api repos/kubevirt/kubevirt/releases --paginate
  (tagged by SIG — focus on SIG-network, Deprecation, API change)

- golangci-lint: curl CHANGELOG.md from the repo
  raw.githubusercontent.com/golangci/golangci-lint/main/CHANGELOG.md

- controller-runtime: gh api repos/kubernetes-sigs/controller-runtime/releases
  --paginate (focus on Breaking Changes in .0 minor releases; also
  check deprecations and removed APIs — e.g. breaking API changes)

Also check for other non-k8s ecosystem deps bumped by a minor
version or more. Find them with:
  `git diff $(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)..HEAD -- go.mod | grep '^[+-]' | grep -v 'k8s.io\|sigs.k8s.io\|^[+-][+-]' | sort`
For any dep where the minor version changed (e.g., v1.2→v1.4,
not v1.2.3→v1.2.5), search for its release notes on GitHub.

For each dep, extract entries between the old and new versions.
Focus on: breaking changes, deprecations, removed features,
default behavioral changes. Ignore: patch-level bug fixes,
documentation changes, features behind alpha gates.

For each concern found, check whether:

1. The autofix already addresses it (check the diff)
2. The repo actually uses the affected feature (grep source
   AND grep CI scripts like kind-common.sh for flags/defaults)

Report format per dep:
  [dep] old → new: BREAKING / DEPRECATION / none found

If release notes are unavailable (API failure, empty body),
note it and move on — do not block.

VERDICT: FAIL if any dependency release note documents a breaking
change that affects this repo and is not addressed in the rebase.
PASS if all relevant changes are addressed or no breaking changes
found.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, `go generate`,
`go run`, or any command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite specific
release note entries for any concerns.

After your analysis, write your report using the helper script.
Bind PLUGIN_ROOT to the verified absolute plugin path from your reviewer
context in this shell call. Confirm HEAD still matches the code reviewed;
then write through the helper (stop if it is unavailable):

```bash
REPO="<the absolute repo path from reviewer context>"
SCRIPT="$PLUGIN_ROOT/scripts/write-gate-report.sh"
bash "$SCRIPT" "$REPO" step3-dep-release-notes PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Choose the verdict from this gate's criteria. Replace the example verdict,
issue count, summary, and details with your actual findings.
