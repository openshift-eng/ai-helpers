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
| `.work/node-cve/triage-YYYY-MM-DD/` | CVE triage reports and analysis |
| `.work/node-bug/triage-YYYY-MM-DD/` | Bug triage reports |
| `.work/node-rpm/` | Dist-git clones and Vagrant VM |
| `~/.node-assistant/` | Cached team roster JSON files |

For each location that exists, compute the size with `du -sh`.

### 2. Filter by age

For `.work/node-cve/triage-*/` and `.work/node-bug/triage-*/` directories,
parse the date from the directory name and skip directories newer than
`--older-than` days. The `repos/`, `.work/node-rpm/`, and `~/.node-assistant/`
directories are always included (no age filter).

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
$HOME/.node-assistant/                            128K    -

Total to remove: 1.64G
```

### 4. Delete

If `--dry-run` is set, stop after the summary.

Otherwise, ask the user for confirmation ("Remove these artifacts? [y/N]"),
then delete each location. For `.work/node-rpm/`, run `vagrant destroy -f`
first to release libvirt VMs before removing the directory:

```bash
if command -v vagrant &>/dev/null && [ -f .work/node-rpm/Vagrantfile ]; then
  (cd .work/node-rpm && vagrant destroy -f) || echo "WARNING: vagrant destroy failed; skipping .work/node-rpm/ removal to avoid orphaning libvirt domains"
fi
```

Only remove `.work/node-rpm/` if `vagrant destroy` succeeded (or no Vagrantfile was present). Delete all other locations with `rm -rf`. Report each deletion:

```text
Removed $PWD/.work/node-cve/repos/ (1.2G)
Removed $PWD/.work/node-cve/triage-2026-05-01/ (45M)
Removed $PWD/.work/node-bug/triage-2026-05-01/ (12M)
Removed $PWD/.work/node-rpm/ (380M)
Removed $HOME/.node-assistant/ (128K)
Done. Freed 1.64G.
```

## Notes

- This command never deletes source code repositories or plugin files
- Re-running `/node-cve:triage` or `/node-bug:triage` recreates `.work/` artifacts automatically
- Re-running `/node-rpm:bump` recreates dist-git clones; the Vagrant VM must be reprovisioned with `vagrant up`. The cleanup command runs `vagrant destroy -f` before removing `.work/node-rpm/` to avoid orphaning libvirt domains.
- Roster cache is re-synced on the next `/node-team:overview` run
