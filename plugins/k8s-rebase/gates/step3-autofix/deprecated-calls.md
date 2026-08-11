<!-- markdownlint-disable MD013 -->
Detect deprecated function and type usage via static analysis.
This catches deprecated-but-compiling code that go build and
go vet miss — the most common cause of gate failures.

EVIDENCE (read before judging):
  `.rebase-tmp/gates/step3-deprecated-calls.evidence`
  The companion retains a Go AST inventory and its producer exit for each
  vendored module. Read the linked inventory files: they include full
  declaration comments, receiver methods, grouped declarations, fields,
  candidate consumer identifiers, and comments requiring manual resolution.
  Counts describe candidates, not deprecated uses or a gate verdict.
  Compare evidence HEAD, SCAN_HEAD and HEAD_AFTER with the actual reviewed
  revision. Changed revisions or incomplete collection require fresh evidence;
  do not accept a current end stamp for an inventory collected at another HEAD.
  A missing/failed inventory or a module without vendor requires collecting
  its dependency source separately; zero collected candidates is not coverage.
  SA1019 still needs its own completed execution and retained output.

Step 1 — Try staticcheck (most reliable):
  If `staticcheck` is available, run:
  `staticcheck -checks SA1019 ./... 2>&1`
  With vendor/, set Go's flags while preserving inherited flags:
  `GOFLAGS="${GOFLAGS:+$GOFLAGS }-mod=vendor" staticcheck -checks SA1019 ./... 2>&1`
  Do not pass `-mod=vendor` as a Staticcheck argument; it is a Go flag.
  SA1019 detects calls to functions/types marked `// Deprecated:`
  in their source. This catches standard Go deprecated API usage.
  Always run Step 2 regardless of staticcheck results — some projects
  use `// DEPRECATED` (no colon) which SA1019 misses.

  If staticcheck is not installed, try:
  `go install honnef.co/go/tools/cmd/staticcheck@latest 2>/dev/null`

Step 2 — Non-standard deprecation scan:
  Some projects (notably OpenShift API) use `// DEPRECATED`
  instead of the Go-standard `// Deprecated:` format. SA1019
  misses these. Use the companion's AST inventory to check all candidate
  file/name pairs and relevant unbound comments. Resolve matches to the actual
  imported declaration and receiver, reading its complete comment before
  assigning a deprecation. A same-named deprecated declaration in another
  dependency does not deprecate the imported one.
  Resolve package-level and type deprecations through constructor return
  types and receiver methods too: consumers can use a deprecated type without
  spelling its name. A constructor without its own deprecation marker does
  not exempt its deprecated result type. Record these uses and their baseline
  delta even when SA1019 is clean; zero net-new uses is not zero consumption.
  If the inventory could not run, collect equivalent complete evidence. This
  grep can help discovery, but cannot establish complete declaration coverage:
  `grep -rh -A2 '// Deprecated:\|// DEPRECATED' vendor/ --include='*.go' 2>/dev/null | grep -E '^\s*func |^\s*type |^\s*var |^\s*const ' | grep -oP '(?<!\w)(?:func|type|var|const)\s+\K\w+' | sort -u`
  This looks at two lines AFTER the deprecation comment and misses longer
  comment blocks, grouped specifications and receiver methods. Never use its
  count alone as the completed scan.
  Check every collected name in non-vendor source, retaining the full hits.
  Use explicit Bash and line iteration or arrays. In zsh, `for sym in $NAMES`
  does not split a multiline list; likewise a quoted multiline file list is
  one filename. A failed search is incomplete coverage, never zero uses.

  For an already collected newline-separated `NAMES` list, this Bash loop
  distinguishes no matches (rg exit 1) from an unsuccessful scan:

  ```bash
  checked=0
  while IFS= read -r symbol; do
    [[ -n "$symbol" ]] || continue
    printf 'SYMBOL: %s\n' "$symbol"
    rc=0
    rg -n -w -F --glob '*.go' --glob '!**/vendor/**' \
      --glob '!**/.cache/**' -- "$symbol" . || rc=$?
    [[ "$rc" -le 1 ]] || exit "$rc"
    checked=$((checked + 1))
  done <<< "$NAMES"
  printf 'CHECKED_SYMBOLS: %s\n' "$checked"
  ```

Step 3 — Fallback (if staticcheck unavailable and no vendor):
  Use `go vet ./...` as a minimal check. It won't catch
  deprecated APIs but will catch format string issues and
  other vet-detectable problems.

Find module directories:
  `find . -name go.mod -not -path '*/vendor/*' -exec dirname {} \;`

Run both scans in each module directory, using its own vendor or resolved
module-cache source. An absent repository-root vendor directory does not
mean nested modules have no dependencies. Retain complete diagnostics and
the analyzer's exit status before displaying excerpts; a truncated sample
does not establish coverage of the remaining findings or modules.

Report each deprecated call with file:line and what to replace
it with (if the deprecation comment says). A matching identifier is only
a candidate: resolve its import alias and receiver to the actual dependency
declaration before reporting a deprecated use. An identically named symbol
in another package does not establish that this call is deprecated.
FAIL if any NEW
deprecated calls exist. PASS if clean or only pre-existing.
If neither staticcheck nor Go is available, write INCONCLUSIVE with summary
"staticcheck and Go unavailable — deprecated call check not performed".
If only staticcheck is unavailable, say so in the summary: SA1019 coverage is
then limited to Step 2's scan.

MANDATORY pre-existing check — run for EVERY finding before
counting it:

```bash
BASE=$(bash "$PLUGIN_ROOT/scripts/resolve-rebase-base.sh" "$(git rev-parse --show-toplevel)") || exit 1
# For each finding at <file>:<line> with <symbol>:
base_count=$(git show "$BASE:<file>" 2>/dev/null | grep -c '<symbol>')
curr_count=$(grep -c '<symbol>' "<file>" 2>/dev/null)
net_new=$(( curr_count > base_count ? curr_count - base_count : 0 ))
# net_new > 0: that many calls are NEW and count toward FAIL
# net_new == 0: all calls are PRE-EXISTING — do NOT count
```

Count the delta: only `curr_count - base_count` net-new calls
count toward FAIL. Do NOT use "base_has > 0" as a simple binary —
a file with 2 deprecated calls on base and 4 on HEAD has 2 NEW ones.
If ALL findings net_new == 0, verdict MUST be PASS.

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
  "$REPO" step3-deprecated-calls PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Choose the verdict from this gate's criteria. Replace the example verdict,
issue count, summary, and details with your actual findings.
