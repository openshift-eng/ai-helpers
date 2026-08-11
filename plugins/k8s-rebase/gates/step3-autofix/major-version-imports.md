EVIDENCE (read before judging): if `.rebase-tmp/gates/step3-major-version-imports.evidence` exists,
run `git rev-parse HEAD` and compare it to the file's `HEAD:` line.
- Match: Read the file first and treat its `SUMMARY:`/facts as ground truth for this gate.
- Differ or file absent: evidence is stale/missing — judge from scratch using the checks
  below. Do NOT PASS on the strength of absent or stale evidence.

Read the evidence. If SUMMARY shows 0 stale imports, verdict is PASS.
When NEW_ISSUES > 0: analyze all detail lines in the evidence —
the script excludes pre-existing imports at collection time so every
detail line is a new finding. There are no "PRE-EXISTING" lines in
the evidence file.

If evidence is stale or absent, fall back to manual checks:

Check for stale major-version Go module imports. These are
entire module path changes where v1 is abandoned in favor of
v2+ — NOT deprecated symbols (those are caught by other gates).

MANDATORY first action — run these before any analysis:
  `grep -rn '"k8s.io/klog"' --include='*.go' . | grep -v vendor/ | grep -v .cache/ | grep -v '/v2'`
Collect the results. Apply the pre-existing check below before
counting any as FAIL — klog bare imports may be pre-existing.

Step 1 — Discover major-version modules from go.mod:
  `grep -E '/v[0-9]+' go.mod | grep -v '^//' | sed 's|.*\([a-z].*\/v[0-9]*\).*|\1|' | sort -u`
  For each versioned module path (e.g., k8s.io/klog/v2), check
  if non-vendor code still imports the unversioned path:
  `grep -rn '"k8s.io/klog"' --include='*.go' . | grep -v vendor/ | grep -v .cache/ | grep -v '/v2'`

Step 2 — Check go.mod require lines:
  `grep -E 'require' go.mod`
  Look for any direct dependency that uses a pre-v2 path when
  a v2+ version is available. Cross-reference with vendor/:
  `find vendor/ -type d -regex '.*/v[0-9]+$' | sort`

Report each stale import with file:line AND the correct
versioned path (e.g., k8s.io/klog -> k8s.io/klog/v2).

For each finding, check the base branch — use count delta:
  `BASE=$(git merge-base HEAD master 2>/dev/null || git merge-base HEAD main)`
  `base_count=$(git show "$BASE:<file>" 2>/dev/null | grep -c '<bare-import>')`
  `curr_count=$(grep -c '<bare-import>' "<file>" 2>/dev/null)`
  `net_new=$(( curr_count > base_count ? curr_count - base_count : 0 ))`
Only net_new > 0 occurrences are NEW and count toward FAIL.
A file with 3 pre-existing bare imports and 5 on HEAD has 2 NEW ones.
Do NOT use "base_has > 0" as a simple binary — that marks all as pre-existing.

FAIL if any NEW stale imports remain. PASS if clean or
only pre-existing. If no major-version deps, PASS.

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
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
SCRIPT=$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)
if [ -n "$SCRIPT" ]; then
  bash "$SCRIPT" "$REPO" step3-major-version-imports PASS 0 "your one-line summary" \
    "detail line 1" "detail line 2"
else
  mkdir -p "$REPO/.rebase-tmp/gates"
  printf 'VERDICT: PASS\nISSUES: 0\nSUMMARY: your one-line summary\nDETAILS:\ndetail line 1\ndetail line 2\n' \
    > "$REPO/.rebase-tmp/gates/step3-major-version-imports.report"
fi
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
