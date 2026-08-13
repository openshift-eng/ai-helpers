Step 3 already verified autofix patterns (deprecated APIs, CRD
validation, feature gates, e2e infra). Do NOT re-check those —
focus on CI-specific gaps that only matter at ship time:

1. Does any e2e test or CI config reference a hardcoded k8s
   version, KIND image tag, or container image that needs updating?
   Search the full repo (excluding vendor):
   `grep -rn 'kind.sigs.k8s.io/dl/v\|KIND_VERSION=v\|kindest/node:v' . --include="*.yml" --include="*.yaml" --include="*.sh" --include="Makefile" --include="kind-common" 2>/dev/null | grep -v vendor/`
2. Are there version-conditional test skips that should be added
   or removed for this k8s version? Search for them:
   `grep -rn 'Skip\|Skipf\|MinimumKubernetes\|MaximumKubernetes' --include='*.go' . | grep -v vendor/`
   Check each hit — if it references the previous k8s minor
   version, flag whether the condition is still correct.
3. Are there patterns in the doc that the agent should have fixed
   manually but didn't? Find the patterns doc:
   `find "$HOME/.claude" "$HOME" -maxdepth 7 -name "k8s-rebase-patterns.md" -path "*/k8s-rebase/*" 2>/dev/null | head -1`
   Read it and check the branch diff for each documented manual fix.
4. Would the KIND image tag actually exist? Search the web
   for "kindest/node <version>" to verify. Optionally run:
   `skopeo inspect --no-creds docker://docker.io/kindest/node:v<version> 2>/dev/null`
   If the tag doesn't exist yet, note as a warning (not a FAIL).

VERDICT criteria: FAIL if a CI config uses a different k8s MINOR
version (e.g., v1.35.x when targeting 1.36). PASS if configs use
the correct minor version, even if the patch differs because the
KIND image isn't published yet (note as INFO in details, not FAIL).
SKIP if the repo has no CI configuration files. Never use WARN —
only PASS, FAIL, or SKIP.

NEVER run `go mod tidy`, `go get`, `go mod vendor`, or any
command that modifies go.mod/go.sum/vendor. Allowed: `go build`,
`go vet`, `go test` (with `-mod=vendor` if vendor/ exists),
`go mod verify`, `go doc`, `go install <tool>@<version>`,
`go clean -cache`. Fix-hint commands in report text are fine.

Rules: you are read-only — do not edit repo files. Your sole
permitted write is your gate report file under .rebase-tmp/gates/.
Do not write anywhere else. Cite file:line
for any issues.

After your analysis, write your report using the helper script.
The repo path is the first line of your prompt:

```bash
REPO="<the repo path from the first line of your prompt>"
bash "$(find "$HOME/.claude" "$HOME" -maxdepth 7 -name "write-gate-report.sh" -path "*/k8s-rebase/scripts/*" 2>/dev/null | head -1)" \
  "$REPO" step4-ci-readiness PASS 0 "your one-line summary" \
  "detail line 1" "detail line 2"
```

Use PASS, FAIL, or SKIP as the verdict. Replace the summary and
details with your actual findings.
