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
repos, and cached roster data. Use this to reclaim disk space or to satisfy
data purge requirements (DATA-05).

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--older-than N` | 30 | Only remove triage directories older than N days |
| `--dry-run` | off | Show what would be removed without deleting |

## Implementation

### 1. Discover artifacts

Scan for these locations relative to the current working directory and home:

| Location | Contents |
|----------|----------|
| `.work/node-cve/repos/` | Shallow repo clones |
| `.work/node-cve/triage-YYYY-MM-DD/` | Triage reports and analysis |
| `~/.node-assistant/` | Cached team roster JSON files |

For each location that exists, compute the size with `du -sh`.

### 2. Filter by age

For `.work/node-cve/triage-*/` directories, parse the date from the directory
name and skip directories newer than `--older-than` days. The `repos/` and
`~/.node-assistant/` directories are always included (no age filter).

### 3. Show summary

Use `$PWD` for `.work/` paths and `$HOME` for home directory paths so
the user sees resolved locations. Print a table:

```text
Location                                          Size    Age
$PWD/.work/node-cve/repos/                        1.2G    -
$PWD/.work/node-cve/triage-2026-05-01/            45M     59 days
$PWD/.work/node-cve/triage-2026-06-15/            52M     14 days (skipped, < 30 days)
$HOME/.node-assistant/                            128K    -

Total to remove: 1.25G
```

### 4. Delete

If `--dry-run` is set, stop after the summary.

Otherwise, ask the user for confirmation ("Remove these artifacts? [y/N]"),
then delete with `rm -rf`. Report each deletion:

```text
Removed $PWD/.work/node-cve/repos/ (1.2G)
Removed $PWD/.work/node-cve/triage-2026-05-01/ (45M)
Removed $HOME/.node-assistant/ (128K)
Done. Freed 1.25G.
```

## Notes

- This command never deletes source code repositories or plugin files
- Re-running `/node-cve:triage` recreates `.work/` artifacts automatically
- Roster cache is re-synced on the next `/node-team:overview` run
