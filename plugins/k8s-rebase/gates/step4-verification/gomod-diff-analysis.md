Scan the go.mod diff (all modules, excluding vendor) between
the branch and its merge-base. Classify each changed dependency:

1. Direct deps with minor-version jumps:
   - k8s.io/* and sigs.k8s.io/*: label "expected rebase" (skip)
   - Third-party (everything else): flag for review
2. Deps that moved from a released version to a pseudo-version
   (e.g., v1.36.11 → v1.36.12-0.20260120...): flag as
   "pinned to unreleased commit"
3. Deps added or removed entirely — especially direct deps
   removed (may indicate stdlib promotion or API consolidation)
4. Pre-release direct deps (alpha, beta, rc, v0.0.0-timestamp)
   that have a newer stable release available
5. The `go` directive change (e.g., 1.25 → 1.26): note stdlib
   and language implications

Report findings for all categories above. Count third-party
minor-version jumps, pseudo-version pins, added/removed deps,
and pre-release direct deps separately.

Rules: you are read-only — do not edit files. Cite the specific
go.mod line for any flagged dependency.
