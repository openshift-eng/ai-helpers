Check the autofix results by examining git log for the autofix
commits. Look for commits matching patterns like "Migrate x/exp
imports", "Disable new default-true feature gates", "Update KIND
image", "Update version references and lint". Count how many
autofix commits were created. If zero, the autofix may not have
run. Ignore stale vendor in gitignored directories
(`git check-ignore -q <dir>/vendor`) — these are expected and
not maintained by the rebase. Do NOT escalate gitignored vendor
staleness as a blocker.

Report total issues.

Rules: report specific counts, not "looks good." You are
read-only — do not edit files. Cite file:line for any issues.
