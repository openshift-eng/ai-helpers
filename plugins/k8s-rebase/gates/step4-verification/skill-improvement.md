Read the branch diff (git diff of merge-base..HEAD). Identify
manual fix commits — those that do NOT have "Applied:" in the
commit body AND are not known autofix infrastructure commits
(license regeneration, post-vet cleanup, import reordering).
Autofix commits contain "Applied:" trailers; commits matching
script-generated subjects (deps:, codegen:, ci:, test:, docs:)
from the rebase or autofix scripts are also not manual work.

For each manual fix commit, classify the change:
- ONE-OFF: affects a unique code path unlikely to recur
- SYSTEMATIC: same transformation repeated across files, or a
  pattern likely to appear in other Go+k8s repos

For each SYSTEMATIC fix, describe:
1. Pattern name (short kebab-case slug)
2. Detection: grep/find command that finds affected code
3. Fix: sed/awk command or transformation description
4. Scope: generic (any Go+k8s repo) or repo-specific

Also check: did any manual fix address something the patterns
doc already describes? If yes, the autofix script may be missing
a fix function for that pattern.

Report each candidate with its classification, detection
command, and fix description. If no systematic fixes were
found, report "No new patterns discovered."

Rules: report specific findings, not "looks good." You are
read-only — do not edit files. Cite file:line for any issues.
