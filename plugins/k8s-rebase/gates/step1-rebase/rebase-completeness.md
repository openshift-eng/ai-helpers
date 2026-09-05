EVIDENCE (read before judging): if `.rebase-tmp/gates/step1-rebase-completeness.evidence` exists,
run `git rev-parse HEAD` and compare it to the file's `HEAD:` line.
- Match: Read the file first and treat its `SUMMARY:`/facts as ground truth for this gate.
  `CHECK1_RESULT_FILE`, `CHECK2_UNCOMMITTED_COUNT`, and `CHECK5_CONFLICT_COUNT` are
  definitive counts — do not re-run those checks. For check 3 (commits), use the
  `CHECK3_LOG` lines and `CHECK3_*` fields as ground truth; apply the codegen exception
  logic below. For check 4 (dep versions), use `CHECK4_DEP` lines as ground truth;
  apply the replace/indirect exception logic below. `NEW_ISSUES` reflects checks 1, 2,
  and 5 only — checks 3 and 4 require your judgment.
- Differ or file absent: evidence is stale/missing — judge from scratch using the checks
  below. Do NOT PASS on the strength of absent or stale evidence.

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
3. Rebase commits: check `git log --oneline "$BASE"..HEAD` (where
   $BASE is from `git merge-base HEAD master 2>/dev/null || git merge-base HEAD main`).
   Count MISSING expected commits:
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
   minor version. Count any NOT at the target minor version (older or newer).
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
- Check 3 (missing commits): check step1.log for errors in that
  module's processing. If the module has k8s.io deps and no
  commit exists, manually run in that module's directory:
  `go get k8s.io/<dep>@$(cat .rebase-tmp/target-k8s-api-version.txt) && go mod tidy && go mod vendor`
  then commit with `-s`. If the module has no k8s.io deps,
  count 0 (no commit expected).
- Check 4 (version mismatch): report this fix for the main
  agent to apply (exact version from
  `.rebase-tmp/target-k8s-api-version.txt`):
  `go get k8s.io/<mod>@$(cat .rebase-tmp/target-k8s-api-version.txt)`
- Check 5 (conflict markers): for each file reported by the
  Check 5 grep, open it, resolve every `<<<<<<<`/`=======`/
  `>>>>>>>` block manually, then `git add <file>` and commit
  with `-s`. Unresolved conflicts block all subsequent steps.

VERDICT:
- If all counts are 0: PASS.
- If Check 1 is 1 but Checks 2-5 are ALL 0: PASS. The result
  file is missing but all work was completed. Note it in summary.
- Otherwise: FAIL.

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
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step1-rebase-completeness PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
