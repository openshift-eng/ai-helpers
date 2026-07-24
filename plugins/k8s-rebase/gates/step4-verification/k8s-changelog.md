Read the Kubernetes changelog for the target minor version:
  curl -sL "https://raw.githubusercontent.com/kubernetes/kubernetes/master/CHANGELOG/CHANGELOG-1.${K8S_MINOR}.md"

If the changelog is too large, focus on these sections only:
- "Urgent Upgrade Notes"
- "Deprecation"
- "API Change"

Filter for entries tagged [SIG Network], [SIG API Machinery],
or [SIG Node]. Ignore entries about DRA, scheduling, storage,
windows, auth unless they mention networking, CNI, or pods.

For each relevant entry, check whether the rebase addresses it:
- grep the repo source (excluding vendor) for affected symbols
- check the branch diff for related fix commits

Report per entry:
  [section] summary: ADDRESSED / N/A / NOT ADDRESSED

Also fetch the client-go Go API changelog:
  curl -sL "https://raw.githubusercontent.com/kubernetes/client-go/master/CHANGELOG.md"

Ignore entries below the "Changes for Kubernetes <= ..." cutoff
line — those are from older releases. For each remaining entry:
- Extract the changed/removed/added symbols from the code block
- grep the repo source (excluding vendor) for each symbol
- If a removed or changed symbol is used, verify the rebase
  addresses it (check the branch diff for a fix commit)
- If the symbol is not used in the repo, mark N/A

Report per entry:
  [client-go] summary: ADDRESSED / N/A / NOT ADDRESSED

If either changelog is unavailable, note it and move on.

Determine the target k8s minor version from go.mod:
  grep 'k8s.io/api ' go.mod (or go-controller/go.mod)
  Extract the minor version from v0.XX.Y

Rules: you are read-only — do not edit files. Cite commit
hashes or file:line for ADDRESSED items.
