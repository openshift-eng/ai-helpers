---
description: Sync downstream fork with upstream while preserving downstream-specific files
argument-hint: [--dry-run]
---

## Name
git:sync-downstream

## Synopsis
```
/git:sync-downstream [--dry-run]
```

## Description

The `git:sync-downstream` command automates the workflow of syncing a downstream fork with upstream changes while preserving downstream-specific configuration files. This is commonly used in OpenShift and other projects that maintain forks of upstream repositories with custom configurations.

The command:
- Creates a `sync-downstream` branch from upstream/main
- Merges downstream/main using the `-s ours` strategy (no conflicts)
- Selectively restores downstream-specific files from downstream/main
- Updates vendored dependencies (for Go projects)
- Creates a single commit with all changes

**Downstream files to preserve** are read from a `.downstream-preserve` file in the repository root. If this file doesn't exist, the command will fail with instructions to create it.

This workflow is especially useful for:
- OpenShift forks of upstream Kubernetes projects
- Projects with CI/CD configurations specific to downstream
- Maintaining custom build processes while staying current with upstream

## Implementation

### Prerequisites

1. **Git remotes must exist:**
   ```bash
   git remote -v | grep -E '(upstream|downstream)'
   ```
   - `upstream` remote: Points to the original upstream repository
   - `downstream` remote: Points to your downstream fork

2. **Configuration file must exist:**
   Create a `.downstream-preserve` file in repository root listing files/directories to preserve from downstream:
   ```
   # Example .downstream-preserve
   .ci-operator.yaml
   .tekton/
   Dockerfile.ci
   OWNERS
   renovate.json
   ```

3. **Clean working directory** (recommended but not required):
   ```bash
   git status --porcelain
   ```

### Execution Steps

1. **Start from detached HEAD** (ensures clean state):
   ```bash
   git checkout --detach
   ```

2. **Remove old sync branch** if it exists:
   ```bash
   git branch -D sync-downstream 2>/dev/null || true
   ```

3. **Fetch latest changes:**
   ```bash
   git fetch downstream
   git fetch upstream
   ```

4. **Create sync branch from upstream:**
   ```bash
   git checkout -b sync-downstream upstream/main
   ```

5. **Merge with ours strategy** (preserves upstream, no conflicts):
   ```bash
   git merge -s ours --no-commit downstream/main
   ```

6. **Restore downstream files:**
   Read `.downstream-preserve` line by line and restore each file/directory:
   ```bash
   while IFS= read -r file; do
     [[ "$file" =~ ^#.*$ || -z "$file" ]] && continue  # Skip comments and empty lines
     git checkout downstream/main -- "$file"
   done < .downstream-preserve
   ```

7. **Update Go dependencies** (if go.mod exists):
   ```bash
   if [ -f go.mod ]; then
     go mod tidy
     go mod vendor
     git add vendor/
   fi
   ```

8. **Commit everything in one commit:**
   ```bash
   git commit -am "sync: merge upstream main with downstream config"
   ```

### Output

After successful execution, show:
- ✅ Commit hash and message
- 📊 Summary of changes: `git diff --stat downstream/main..HEAD | tail -1`
- 📝 Next steps:
  ```
  # Push the branch
  git push origin sync-downstream

  # Create pull request
  gh pr create --base downstream/main --title "Sync with upstream main"
  ```

### Dry Run Mode

If `--dry-run` is specified:
- Execute all steps through merge
- Show which files would be restored
- Show diff summary
- **Do NOT commit or create branch**
- Leave repository in detached HEAD state for review

### Error Handling

- **Missing remotes:** Show error with instructions to add `git remote add upstream <url>`
- **Missing .downstream-preserve:** Show error with example file content
- **Merge conflicts:** Should not happen with `-s ours`, but if they do, show conflict and exit
- **Failed commands:** Stop immediately and display error, leave state for manual investigation
- **No changes:** If diff is empty, notify user that downstream is already up to date

## Arguments

- **--dry-run** (optional): Preview changes without committing or creating branch

## Examples

### Example 1: Basic Usage

```bash
/git:sync-downstream
```

**Output:**
```
✅ Created sync-downstream branch from upstream/main
✅ Merged downstream/main with -s ours strategy
✅ Restored 9 downstream files from .downstream-preserve
✅ Updated Go dependencies (vendor/)
✅ Committed: abc1234 "sync: merge upstream main with downstream config"

📊 Changes: 45 files changed, 892 insertions(+), 234 deletions(-)

📝 Next steps:
  git push origin sync-downstream
  gh pr create --base downstream/main --title "Sync with upstream main"
```

### Example 2: Dry Run

```bash
/git:sync-downstream --dry-run
```

**Output:**
```
🔍 DRY RUN MODE - No changes will be committed

✅ Fetched upstream and downstream
✅ Would create sync-downstream branch from upstream/main
✅ Would restore these downstream files:
   - .ci-operator.yaml
   - .tekton/
   - Dockerfile.ci
   - OWNERS
   - renovate.json

📊 Would change: 45 files changed, 892 insertions(+), 234 deletions(-)

Use /git:sync-downstream (without --dry-run) to apply these changes.
```

### Example 3: First Time Setup

```bash
# First, create the downstream preserve file
cat > .downstream-preserve << 'EOF'
# Downstream-specific CI/CD files
.ci-operator.yaml
.tekton/
Dockerfile.ci

# Downstream ownership and governance
OWNERS

# Downstream dependency management
renovate.json
mcp_config.toml
EOF

# Add it to git
git add .downstream-preserve
git commit -m "Add downstream file preservation config"

# Now run the sync
/git:sync-downstream
```

## Related Commands

- `/git:cherry-pick-by-patch` - Cherry-pick specific commits between branches
- `/git:branch-cleanup` - Clean up old sync branches
- `/git:commit-suggest` - Generate conventional commit messages

## Configuration File Format

The `.downstream-preserve` file supports:
- **One file or directory per line**
- **Comments** starting with `#`
- **Empty lines** (ignored)
- **Directory paths** with trailing `/` (optional but recommended for clarity)
- **Glob patterns** are NOT supported - list files explicitly

**Example:**
```
# CI/CD configurations
.ci-operator.yaml
.snyk
.tekton/

# Build files
Dockerfile.ci
Dockerfile.ocp
Makefile-ocp.mk

# Governance
OWNERS

# Configuration
mcp_config.toml
renovate.json
```

## Common Workflows

### Weekly Upstream Sync

```bash
# 1. Review what's new in upstream
git fetch upstream
git log HEAD..upstream/main --oneline

# 2. Run sync (dry-run first)
/git:sync-downstream --dry-run

# 3. If looks good, run for real
/git:sync-downstream

# 4. Push and create PR
git push origin sync-downstream
gh pr create --base downstream/main
```

### Adding New Downstream Files

```bash
# 1. Edit .downstream-preserve
echo "new-downstream-file.yaml" >> .downstream-preserve

# 2. Commit the config change
git add .downstream-preserve
git commit -m "Preserve new downstream config file"

# 3. Future syncs will preserve this file automatically
/git:sync-downstream
```

## Notes

- This command is designed for **OpenShift and similar fork workflows**
- The `-s ours` strategy means upstream changes take precedence, then downstream files are overlaid
- For Go projects, `go mod vendor` is automatically run if `go.mod` exists
- The `.downstream-preserve` file should be committed to downstream/main
- Branch name is always `sync-downstream` - delete old branches before running
- This is a **one-way sync** from upstream to downstream
