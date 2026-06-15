# Platform Documentation Lookup

Prefer retrieval over pre-training for Kubernetes and OpenShift specifics — docs change across versions. Use `gh api` to fetch raw markdown.

## Kubernetes

- Repo: `kubernetes/website`, path: `content/en/docs/`
- Versioning: git branches named `release-X.Y` — discover latest by listing branches, grep `^release-`, version-sort (`sort -V`), take last
- No index file — navigate by listing directories
- Hugo shortcodes (`{{< ... >}}`) appear in content — ignore them
- Always include `?ref=$VERSION` in API calls

## OpenShift

- Repo: `harche/openshift-docs-md`, path: `docs/{version}/`
- Versions are directories (e.g. `4.22`) — discover latest by listing `docs/`, filter numeric names, take highest by version (`sort -V`, not lexicographic — e.g. 4.10 > 4.9)
- Each version has an **`AGENTS.md`** index mapping topics to doc files — always start here

## Common

- Always use `-H "Accept: application/vnd.github.raw+json"` for raw file content
- Discover versions dynamically — never hardcode
- Read-only
