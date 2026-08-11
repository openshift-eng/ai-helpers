Verify the deterministic rebase script completed correctly.
Report a count for each check:

1. Result file: does `.rebase-tmp/step1-result.txt` exist
   and contain "EXIT 2"? (EXIT 2 = rebase script's success
   code, meaning deps were bumped. EXIT 0 = already at target.)
   (0 = yes, 1 = missing or wrong)
2. Uncommitted changes: count from `git status --short`
   (exclude untracked files with `?`). Any staged-but-
   uncommitted go.mod, vendor, or generated files indicate
   the script's commit step failed.
3. Rebase commits: check `git log --oneline` on the current
   branch. Count MISSING expected commits:
   - "Rebase" commits (at least 1 per go.mod with k8s.io deps,
     excluding vendor/)
   - Codegen commit (expected if hack/update-codegen.sh or
     Makefile generate/manifests/codegen targets exist —
     search all directories containing go.mod files).
     EXCEPTION: if `.rebase-tmp/codegen.log` exists (codegen
     ran) AND `.rebase-tmp/summary.txt` does NOT contain
     "## CODEGEN FAILURE" (it succeeded) AND there is no
     codegen commit in git log — then codegen produced no
     diff and a codegen commit is NOT expected (count 0).
   - Version refs commit
4. Dependency versions: check all go.mod files (excluding
   vendor/) for k8s.io/* deps. All should be at the same
   minor version. Count any at an older minor version.
   EXCEPTION — do NOT count a version mismatch if EITHER:
   (a) the module has a `replace` directive in this go.mod,
       and that same replace (same module, same target) also
       exists on the base branch; OR
   (b) the module is an `// indirect` require, and it
       appears at the same version in this go.mod on the
       base branch.
   To check the base-branch version of any go.mod:
   `git show $(git merge-base HEAD master 2>/dev/null ||
   git merge-base HEAD main):<path>` — substitute the
   relative path of the go.mod being checked (e.g. go.mod,
   go-controller/go.mod).
   Direct (non-indirect) requires without a `replace` are
   never excepted — the rebase script must bump those.

5. Conflict markers: scan all non-vendor source files:
   `grep -rn '<<<<<<<\|>>>>>>>' --include='*.go' --include='*.yaml' --include='*.json' . | grep -v vendor/`
   Count any merge conflict markers. These mean the rebase
   or a cherry-pick left unresolved conflicts.

Report all 5 counts. Count 0 means that check passed.

Fix hints for non-zero counts:
- Check 1 (result file): if Checks 2-5 all pass, the script
  likely crashed after completing — proceed. Otherwise, check
  `.rebase-tmp/step1.log` for the error and address it.
- Check 2 (uncommitted): `git add` and commit, or investigate
  why the script's commit step failed
- Check 3 (missing commits): re-run the rebase for the missing
  module, or check if that module has no k8s.io deps
- Check 4 (version mismatch): report this fix for the main
  agent to apply: `go get k8s.io/<mod>@v0.<target>.0`

VERDICT:
- If all counts are 0: PASS.
- If Check 1 is 1 but Checks 2-5 are ALL 0: PASS. The result
  file is missing but all work was completed. Note it in summary.
- Otherwise: FAIL.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
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
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step1-rebase-completeness PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
