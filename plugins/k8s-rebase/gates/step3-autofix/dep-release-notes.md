<!-- markdownlint-disable MD013 -->
Identify non-Kubernetes-release dependencies whose major or minor version
changed. Inspect every non-vendor module, including nested modules:

```bash
BASE=$(bash "$PLUGIN_ROOT/scripts/resolve-rebase-base.sh" "$(git rev-parse --show-toplevel)") || exit 1
git diff "$BASE"..HEAD -- ':(glob)**/go.mod' ':(exclude,glob)**/vendor/**'
```

Pair removed and added versions. Include independently versioned ecosystem
modules such as `sigs.k8s.io/controller-runtime`; do not exclude all `sigs.k8s.io/`
paths. Kubernetes release notes are covered by the k8s-changelog gate.

Also inspect changed tool pins in Makefiles, scripts, and CI configuration.
KIND, MetalLB, KubeVirt, and golangci-lint may be pinned there rather than in
go.mod. Read each dependency's upstream release notes or changelog for the
old → new version range; a module-only search misses these changes.

Sources for common dependencies:

- KIND: `gh api repos/kubernetes-sigs/kind/releases --paginate`
  (explicit "Breaking Changes" headings in `.body`)
- MetalLB: in-repo notes at
  `raw.githubusercontent.com/metallb/metallb/main/website/content/release-notes/_index.md`
- KubeVirt: `gh api repos/kubevirt/kubevirt/releases --paginate`
  (tagged by SIG; focus on SIG-network, Deprecation, API change)
- golangci-lint: `raw.githubusercontent.com/golangci/golangci-lint/main/CHANGELOG.md`
- controller-runtime: `gh api repos/kubernetes-sigs/controller-runtime/releases --paginate`
  (Breaking Changes in `.0` minor releases, deprecations, removed APIs)

For other dependencies, search their GitHub releases or changelog.

For each dep, extract entries between the old and new versions.
Use the raw source's release headings and their complete relevant text;
a generated web summary can misattribute entries to neighboring releases.
Record the exact headings, including multi-module release mappings, before
assessing applicability. Retain or cite those raw sections for final review.
Focus on: breaking changes, deprecations, removed features,
default behavioral changes. Ignore: patch-level bug fixes,
documentation changes, features behind alpha gates.

For each concern found, check whether:

1. The autofix already addresses it (check the diff)
2. The repo actually uses the affected feature (grep source
   AND grep CI scripts like kind-common.sh for flags/defaults)

For indirect dependencies, trace production consumers through vendor or the
resolved source. No direct import does not establish that changed defaults
are unused; distinguish client-side and server-side paths where relevant.

Account for every in-scope dependency and tool pin in a coverage list:
  [dep] old → new: source URL + reviewed release range + BREAKING / DEPRECATION / none found / UNVERIFIED

Fetch and read the source; compilation, an indirect requirement, a minor
version bump, or a module's API shape cannot substitute for release notes
about changed behavior. Record inaccessible/missing sources individually.
If a response is truncated, retrieve the omitted relevant sections before
claiming coverage. Do not label an unfetched source "none found".

If a dependency's release notes are unavailable, list it as
unverified in DETAILS and continue. Modules that publish no release
notes (for example `golang.org/x/*`) are listed the same way and do not
by themselves make this gate inconclusive. An unattempted check, inaccessible
published notes, or an unread relevant release range leaves this gate
INCONCLUSIVE. List completed and missing coverage separately.
The no-notes exception applies to a dependency that publishes no release
notes, not to missing portions of an otherwise published history. If a
crossed major/minor release has no available notes, retain INCONCLUSIVE
and name that gap; do not infer compatibility from a 404 or nearby patch notes.

VERDICT: FAIL if any dependency release note documents a breaking
change that affects this repo and is not addressed in the rebase.
PASS only when the coverage list is complete and all reviewed relevant
changes are addressed or no breaking changes were found. Explicit absence
of published notes remains a named coverage limitation.

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
