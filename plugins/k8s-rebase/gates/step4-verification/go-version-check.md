The rebase bumped the Go version. Verify consistency across
the repo and check for implications.

1. go directive: are all go.mod files at the same Go version?
   git diff $(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)..HEAD -- '*/go.mod' 'go.mod' | grep '^[+-]go '

2. toolchain directive: was it added, removed, or changed?
   git diff $(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)..HEAD -- '*/go.mod' 'go.mod' | grep '^[+-]toolchain'

3. Makefiles: do all GO_VERSION / GOLANG_VERSION vars match?
   grep -rn 'GO_VERSION.*=\|GOLANG_VERSION.*=' --include='Makefile*' . | grep -v vendor

4. Dockerfiles: do all golang: image tags match?
   grep -rn 'golang:' --include='Dockerfile*' . | grep -v vendor

5. CI workflows: do they use go-version-file (dynamic) or
   hardcoded versions?
   grep -rn 'go-version' --include='*.yml' --include='*.yaml' .github/ | head -10

6. x/ package opportunities: does the repo still import any
   golang.org/x/ packages that the new Go version promoted
   to stdlib?
   grep -rn '"golang.org/x/exp/\|"golang.org/x/slices"\|"golang.org/x/maps"' --include='*.go' . | grep -v vendor | head -10

Report any mismatches or migration opportunities.

Rules: you are read-only — do not edit files.
