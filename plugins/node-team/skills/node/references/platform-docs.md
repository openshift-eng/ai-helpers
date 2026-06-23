# Platform Documentation Lookup

Prefer retrieval over pre-training for Kubernetes and OpenShift specifics, docs change across versions. Use `gh api` to fetch raw content.

## Kubernetes

- Repo: `kubernetes/website`, path: `content/en/docs/`
- Versioning: git branches named `release-X.Y` — discover latest by listing branches, grep `^release-`, version-sort (`sort -V`), take last
- No index file — navigate by listing directories
- Hugo shortcodes (`{{< ... >}}`) appear in content — ignore them
- Always include `?ref=$VERSION` in API calls

## OpenShift

- Repo: `openshift/openshift-docs`, path: varies by topic area
- Format: AsciiDoc (`.adoc`); fetch/read raw `.adoc` content for OpenShift pages
- Versioning: git branches named `enterprise-X.Y` (e.g. `enterprise-4.18`). Discover latest by listing branches, grep `^enterprise-`, version-sort, take last
- Topic map files (`_topic_map.yml`) list all pages per section

## Common

- Always use `-H "Accept: application/vnd.github.raw+json"` for raw file content
- Discover versions dynamically — never hardcode
- Read-only
