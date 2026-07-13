Run on the host, NOT in a container. Count:
1. Uncommitted tracked files: `git status --short | grep -v '^[?]' | wc -l`
2. Root-owned files outside .git and vendor:
   `find . -type f -not -path './.git/*' -not -path '*/vendor/*' -user root 2>/dev/null | wc -l`
3. .rebase-tmp files tracked by git: `git ls-files .rebase-tmp | wc -l`

Report all three counts.

Rules: report specific counts, not "looks good." You are
read-only — do not edit files. Cite file:line for any issues.
