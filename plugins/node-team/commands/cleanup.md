---
description: Purge cached artifacts and local data produced by Node team plugins
argument-hint: "[--older-than N] [--dry-run]"
---

## Name
node-team:cleanup

## Synopsis
```text
/node-team:cleanup [--older-than N] [--dry-run]
```

## Description

Removes local artifacts created by Node team plugins: triage reports, cloned
repos, dist-git clones, Vagrant VMs, and cached roster data. Use this to
reclaim disk space or to satisfy data purge requirements (DATA-05).

Caches are removed after one confirmation. User state and audit records
(onboarding progress, the node-cve posting audit log) are listed separately
and only removed after their own explicit confirmation.

## Implementation

### 1. Discover artifacts

Scan for these locations relative to the current working directory and home:

| Location | Contents | Class |
|----------|----------|-------|
| `.work/node-cve/repos/` | Shallow repo clones | cache |
| `.work/node-cve/triage-YYYY-MM-DD/` | CVE triage reports and analysis | cache (age filtered) |
| `.work/node-cve/trackers*.tsv`, `.work/node-cve/node-components.txt`, `.work/node-cve/current-run`, `.work/node-cve/reanalyze-consumed.txt` | Tracker query results (summaries, assignee names), component list, run pointer and the list of already honored `[reanalyze]` tags | cache |
| `.work/node-cve/posting-history.log` | Append-only record of every Jira and Slack post, across all runs | audit record |
| `.work/node-bug/triage-YYYY-MM-DD/` | Bug triage reports | cache (age filtered) |
| `.work/node-rpm/` | Dist-git clones and Vagrant VM | cache |
| `~/.node-assistant/team-roster-*.json` | Cached team roster JSON files | cache |
| `~/.node-assistant/onboarding-progress.json` | Progress of `/node-onboarding:checklist` | user state |

For each location that exists, compute the size with `du -sh`.

Never remove the `~/.node-assistant/` directory itself or any file in it that
is not listed above.

### 2. Filter by age

For `.work/node-cve/triage-*/` and `.work/node-bug/triage-*/` directories,
parse the date from the directory name and skip directories newer than
`--older-than` days. The `repos/`, the node-cve query files, `.work/node-rpm/`, and roster cache
locations are always included (no age filter).

### 3. Show summary

Use `$PWD` for `.work/` paths and `$HOME` for home directory paths so
the user sees resolved locations. Print a table:

```text
Location                                          Size    Age
$PWD/.work/node-cve/repos/                        1.2G    -
$PWD/.work/node-cve/triage-2026-05-01/            45M     59 days
$PWD/.work/node-cve/triage-2026-06-15/            52M     14 days (skipped, < 30 days)
$PWD/.work/node-bug/triage-2026-05-01/            12M     59 days
$PWD/.work/node-rpm/                              380M    -
$HOME/.node-assistant/team-roster-*.json          12K     -

Total to remove: 1.64G

Kept unless confirmed separately:
$PWD/.work/node-cve/posting-history.log                   4K   audit record
$HOME/.node-assistant/onboarding-progress.json            4K   user state
```

### 4. Delete

If `--dry-run` is set, stop after the summary.

Otherwise, ask the user for confirmation ("Remove these artifacts? [y/N]").
Then ask one more question per kept item that exists, for example "Also
delete the onboarding progress of `/node-onboarding:checklist`? [y/N]" and
"Also delete the record of posted Jira and Slack comments? [y/N]". Default to
no.

The per-run `posting-audit.log` inside a triage directory is removed together
with that directory. Nothing is lost: the node-cve helper mirrors every line
to `.work/node-cve/posting-history.log`, which is the audit record.

For `.work/node-rpm/`, release the libvirt VM before removing the directory,
and record whether removal is safe:

```bash
RPM_DIR=.work/node-rpm
REMOVE_RPM_DIR=yes
if [ -f "$RPM_DIR/Vagrantfile" ]; then
  if ! command -v vagrant >/dev/null 2>&1; then
    echo "SKIP: $RPM_DIR has a Vagrantfile but vagrant is not installed; keeping it to avoid orphaning the libvirt domain"
    REMOVE_RPM_DIR=no
  elif ! (cd "$RPM_DIR" && vagrant destroy -f); then
    echo "SKIP: vagrant destroy failed; keeping $RPM_DIR to avoid orphaning the libvirt domain"
    REMOVE_RPM_DIR=no
  fi
fi
[ "$REMOVE_RPM_DIR" = yes ] && rm -rf -- "$RPM_DIR"
```

Remove `.work/node-rpm/` only when `REMOVE_RPM_DIR` is still `yes`. Run the
check and the removal in the same Bash invocation, because shell variables do
not persist between Bash tool calls.

Delete the roster cache with `rm -f -- "$HOME"/.node-assistant/team-roster-*.json`
and the remaining confirmed locations with `rm -rf --` on the exact paths from
the summary. Never pass an empty or unquoted variable to `rm -rf`. Report each
deletion:

```text
Removed $PWD/.work/node-cve/repos/ (1.2G)
Removed $PWD/.work/node-cve/triage-2026-05-01/ (45M)
Removed $PWD/.work/node-bug/triage-2026-05-01/ (12M)
Removed $PWD/.work/node-rpm/ (380M)
Removed $HOME/.node-assistant/team-roster-*.json (12K)
Kept $HOME/.node-assistant/onboarding-progress.json
Done. Freed 1.64G.
```

## Return Value

- Summary table of discovered artifacts with size and age
- With `--dry-run`: nothing is deleted
- Otherwise: one line per removed, kept or skipped location and the total
  space freed

## Examples

1. **Preview what would be removed**:
   ```text
   /node-team:cleanup --dry-run
   ```

2. **Remove caches and triage output older than 30 days**:
   ```text
   /node-team:cleanup
   ```

3. **Remove triage output older than a week**:
   ```text
   /node-team:cleanup --older-than 7
   ```

## Arguments

- `--older-than N`: Only remove triage directories older than N days.
  Optional; default 30.
- `--dry-run`: Show what would be removed without deleting. Optional.

## Notes

- This command never deletes source code repositories or plugin files
- Re-running `/node-cve:triage` or `/node-bug:triage` recreates `.work/` artifacts automatically
- Re-running `/node-rpm:bump` recreates dist-git clones; the Vagrant VM must be reprovisioned with `vagrant up`
- The roster cache is re-synced on the next `/node-team:overview` run
