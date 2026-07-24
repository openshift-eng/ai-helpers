Count stale version refs from the PREVIOUS k8s version only
(e.g., if rebasing to 1.36, look for leftover 1.35 refs).
Check yml/yaml/sh/Makefile/Dockerfile files. Exclude:
- K8S_VERSION if the kindest/node image isn't published yet
- Historical/documentation references ("introduced in k8s 1.X",
  comments explaining old behavior, changelogs)
- References inside vendor/ directories
- Ancient versions (1.16, 1.20, etc.) — those are pre-existing
  documentation debt, not rebase issues

Report count of genuinely stale previous-version references.

Rules: report specific counts, not "looks good." You are
read-only — do not edit files. Cite file:line for any issues.
