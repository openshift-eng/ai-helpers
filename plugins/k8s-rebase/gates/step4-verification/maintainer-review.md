Review the full branch diff as a maintainer would. Does every
change serve the k8s version bump, or are there unrelated
cleanups, style changes, or logic alterations? Would a
maintainer approve this diff as-is?

Check:
- Are commits well-scoped (one concern per commit)?
- Are commit messages accurate?
- Is there any scope creep (changes beyond what the rebase needs)?

Note: the autofix script applies known rebase patterns that ARE
required — these are NOT scope creep. Read the patterns doc
(find k8s-rebase-patterns.md in the plugin directory) for the
full list. Any change that matches a documented pattern is
expected, even if it touches e2e infrastructure, version
references, or test configuration. K8S_VERSION patch-level
differences (e.g., v1.36.2 in go.mod vs v1.36.1 for KIND) are
expected — the autofix picks the latest available kindest/node
tag. Do not flag this as a concern.

List your findings with specific commit SHAs and file:line refs.
Do not just say "would approve" — explain what you checked.

Rules: you are read-only — do not edit files. Cite file:line
for any issues.
