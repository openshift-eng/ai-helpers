Read the project's commit message guidelines:
1. Check docs/governance/CONTRIBUTING.md, then CONTRIBUTING.md
   at the repo root (ignore vendor/ copies)
2. Look for explicit prefix convention, case rules, length limits
3. If no guidelines found or no commit format section exists,
   infer the convention from the base branch (exclude merges):
   `git log --oneline --no-merges -20 master` (or `main`)

If the convention is ambiguous or inconsistent in the project's
own history (e.g., some commits have prefixes, some don't),
report 0 — do not hold the rebase to a stricter standard than
the project enforces on itself.

Then check all rebase commits:
  git log --oneline $(git merge-base HEAD main 2>/dev/null ||
    git merge-base HEAD master)..HEAD

For each commit, check:
- Has a prefix before ":" if the project EXPLICITLY requires
  one (in CONTRIBUTING.md, not just because some commits use it)
- First line is ≤72 characters (only if the project specifies
  a length limit)
- Lowercase after prefix (if the project specifies this)

Also list the prefixes used in the rebase commits and compare
to prefixes in recent base-branch history. Note any prefixes
that don't appear in recent history (informational, not a
failure — new prefixes like `deps:` or `codegen:` can be valid
for rebase-specific commits).

Count commits that violate the FORMAT convention (missing
required prefix, over length limit, wrong case). Do not count
unusual-but-valid prefix choices. Do not count violations of
conventions the project doesn't explicitly document or
consistently follow.

Rules: report specific counts, not "looks good." You are
read-only — do not edit files. Cite commit hash and message
for any violations.
