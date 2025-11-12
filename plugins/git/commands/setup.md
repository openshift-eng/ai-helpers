---
description: Set up a git repository with upstream and downstream remotes for forked development workflows
argument-hint: [--upstream-only | --downstream-only]
---

## Name
git:setup

## Synopsis
```
/git:setup [--upstream-only | --downstream-only]
```

## Description
The `git:setup` command helps set up a git repository following the OpenShift/Red Hat development workflow where:
- **Upstream**: The original repository (e.g., kubernetes on GitHub)
- **Downstream**: The Red Hat/OpenShift fork (e.g., openshift/kubernetes)
- **Origin**: Your personal fork for development

This command handles:
- Creating personal forks from upstream repositories
- Cloning repositories to the local filesystem
- Setting up git remotes (origin, upstream, downstream)
- Creating and syncing branches across remotes
- Managing existing local repositories

## Implementation

### Welcome Message

When the tool starts, display the following message:

```
The git setup tool helps you fork git repositories and clone them. Also helps keep the cloned repo in sync with the upstream or downstream repo. You can also create branches in git that will have the correct changes from upstream repos.

IMPORTANT: To rebase openshift/kubernetes use the "/openshift:rebase" command. This command is for generalized git repository setup and management.
```

### Initial Setup Flow

1. **Ask for Local Code Repository Base Path**

   First, ask the user where they keep all their code repositories:

   ```
   Where do you keep your code repositories?
   Example: $HOME/go/src
   Default: $HOME/go/src
   ```

   Once the user provides the path:
   - Validate that the directory exists
   - If the directory doesn't exist, ask if they want to create it
   - Change to that directory: `cd <code-base-path>`
   - Store this path as `<code-base-path>` for later use in constructing the full clone path

   Example implementation:
   ```bash
   # Get the code base path from user (default: $HOME/go/src)
   code_base_path="${user_input:-$HOME/go/src}"

   # Expand ~ to full home path if needed
   code_base_path="${code_base_path/#\~/$HOME}"

   # Check if directory exists
   if [ ! -d "$code_base_path" ]; then
     echo "Directory $code_base_path does not exist."
     read -p "Would you like to create it? (y/n): " create_dir
     if [ "$create_dir" = "y" ]; then
       mkdir -p "$code_base_path"
       echo "✓ Created directory $code_base_path"
     else
       echo "Please provide an existing directory path."
       exit 1
     fi
   fi

   # Change to the code base directory
   cd "$code_base_path"
   echo "✓ Changed to directory $code_base_path"
   ```

2. **Ask About Repository Type**

   **Note**: The AskUserQuestion tool has a maximum of 4 options. To accommodate all 5 workflow options, use one of these approaches:

   **Approach A - Two-step question (Recommended)**:

   First question:
   ```
   Do you want to set up:
   1. Upstream repository only (no downstream fork)
   2. Upstream with downstream fork (Red Hat/OpenShift workflow)
   3. Downstream repository only (e.g., OpenShift projects without upstream)
   4. Work with existing repository (create/rebase branches)
   ```

   If option 4 is selected, ask a follow-up question:
   ```
   What would you like to do with your existing repository?
   1. Create a new branch synced with upstream/downstream branch
   2. Rebase an existing branch with latest code from remote
   ```

   **Approach B - Direct text output (Alternative)**:

   Instead of using AskUserQuestion, output the options as text and ask the user to respond:
   ```
   Do you want to set up:
   1. Upstream repository only (no downstream fork)
   2. Upstream with downstream fork (Red Hat/OpenShift workflow)
   3. Downstream repository only (e.g., OpenShift projects without upstream)
   4. Create a branch in personal forked repository synced with upstream/downstream branch (for existing repos)
   5. Rebase an existing branch with latest code from remote (for existing repos)

   Please respond with the option number (1-5):
   ```

   If `--upstream-only` flag is provided, skip to upstream-only flow.
   If `--downstream-only` flag is provided, skip to downstream-only flow.

   If **Option 4** is selected, skip to "Create Branch in Existing Repository" flow.
   If **Option 5** is selected, skip to "Rebase Existing Branch with Remote" flow.

3. **Get Repository URL**

   For **Option 1** (Upstream only) or **Option 2** (Upstream with downstream):
   ```
   What is the upstream repository URL?
   Example: https://github.com/kubernetes/kubernetes
   ```

   Validate the URL is a valid GitHub repository.
   Parse to extract: `<upstream-org>/<upstream-repo>`

   For **Option 3** (Downstream only):
   ```
   What is the downstream repository URL?
   Example: https://github.com/openshift/machine-config-operator
   ```

   Validate the URL is a valid GitHub repository.
   Parse to extract: `<downstream-org>/<downstream-repo>`

4. **Personal Fork Setup**

   For **Option 1** (Upstream only) or **Option 2** (Upstream with downstream):
   ```
   Do you want to create a personal fork from upstream? (y/n)
   ```

   If yes:
   - Use GitHub CLI to create fork: `gh repo fork <upstream-org>/<upstream-repo> --clone=false`
   - This creates fork under authenticated user's account

   If no or fork already exists:
   ```
   What is your personal fork name?
   Hint: Format is usually <github-username>/<repo-name>
   Example: <username>/kubernetes
   ```

   For **Option 3** (Downstream only):
   ```
   Do you want to create a personal fork from downstream? (y/n)
   ```

   If yes:
   - Use GitHub CLI to create fork: `gh repo fork <downstream-org>/<downstream-repo> --clone=false`
   - This creates fork under authenticated user's account

   If no or fork already exists:
   ```
   What is your personal fork name?
   Hint: Format is usually <github-username>/<repo-name>
   Example: <username>/machine-config-operator
   ```

5. **Personal Fork Branch (Optional)**
   ```
   Do you have a specific branch in your personal fork you want to work with? (y/n)
   ```

   If yes:
   ```
   What is the branch name?
   ```

6. **Downstream Repository (for Option 2 only - Upstream with downstream)**
   ```
   What is the downstream repository?
   Hint: For OpenShift projects, this is usually openshift/<repo-name>
   Example: openshift/kubernetes
   Default: openshift/<repo-name>
   ```

   Skip this step for **Option 1** (Upstream only) and **Option 3** (Downstream only).

7. **Downstream Remote Name (for Option 2 and Option 3)**

   For **Option 2** (Upstream with downstream):
   ```
   What should the downstream remote be named?
   Recommended: "openshift" (for OpenShift projects)
   Default: openshift
   ```

   For **Option 3** (Downstream only):
   The downstream repository becomes the primary remote alongside origin.
   ```
   What should the downstream remote be named?
   Recommended: "openshift" (for OpenShift projects)
   Default: openshift
   ```

   Skip this step for **Option 1** (Upstream only).

8. **Local Clone Path**

   Use the `<code-base-path>` from step 1 to construct the full clone path.

   For **Option 1** (Upstream only) or **Option 2** (Upstream with downstream):
   ```
   Where do you want to clone the repository?
   Recommended format: <code-base-path>/github.com/<org>/<repo>
   Example: $HOME/go/src/github.com/kubernetes/kubernetes
   Default: <code-base-path>/github.com/<upstream-org>/<upstream-repo>
   ```

   For **Option 3** (Downstream only):
   ```
   Where do you want to clone the repository?
   Recommended format: <code-base-path>/github.com/<org>/<repo>
   Example: $HOME/go/src/github.com/openshift/machine-config-operator
   Default: <code-base-path>/github.com/<downstream-org>/<downstream-repo>
   ```

9. **Check if Local Directory Exists**

   If the directory does NOT exist:

   For **Option 1** (Upstream only):
   - Clone from personal fork: `git clone git@github.com:<personal-fork>.git <local-path>`
   - If personal fork branch was specified: `git clone -b <branch> git@github.com:<personal-fork>.git <local-path>`
   - Change to the directory: `cd <local-path>`
   - Add upstream remote: `git remote add upstream git@github.com:<upstream-org>/<upstream-repo>.git`
   - Fetch all remotes: `git fetch --all`

   For **Option 2** (Upstream with downstream):
   - Clone from personal fork: `git clone git@github.com:<personal-fork>.git <local-path>`
   - If personal fork branch was specified: `git clone -b <branch> git@github.com:<personal-fork>.git <local-path>`
   - Change to the directory: `cd <local-path>`
   - Add upstream remote: `git remote add upstream git@github.com:<upstream-org>/<upstream-repo>.git`
   - Add downstream remote: `git remote add <downstream-name> git@github.com:<downstream-repo>.git`
   - Fetch all remotes: `git fetch --all`

   For **Option 3** (Downstream only):
   - Clone from personal fork: `git clone git@github.com:<personal-fork>.git <local-path>`
   - If personal fork branch was specified: `git clone -b <branch> git@github.com:<personal-fork>.git <local-path>`
   - Change to the directory: `cd <local-path>`
   - Add downstream remote: `git remote add <downstream-name> git@github.com:<downstream-org>/<downstream-repo>.git`
   - Fetch all remotes: `git fetch --all`

   If the directory DOES exist:
   - Proceed to "Managing Existing Repository" flow

### Create Branch in Existing Repository (Option 4)

When **Option 4** is selected from step 2, follow this flow to create a branch in the personal fork that syncs with an upstream/downstream branch:

1. **Ask for Existing Local Repository Path**
   ```
   What is the local path to your existing repository?
   Example: $HOME/go/src/github.com/kubernetes/kubernetes
   ```

   Validate that the directory exists and is a git repository:
   ```bash
   if [ ! -d "$local_path" ]; then
     echo "Error: Directory does not exist"
     exit 1
   fi

   if [ ! -d "$local_path/.git" ]; then
     echo "Error: Not a git repository"
     exit 1
   fi

   cd "$local_path"
   ```

2. **List Available Remotes**

   Get all remotes and display them to the user:
   ```bash
   cd "$local_path"
   git remote -v
   ```

   If there are multiple remotes (more than just 'origin'), ask the user to select one:
   ```
   Which remote do you want to sync with?
   Available remotes: origin, upstream, openshift
   ```

   If there's only one remote, use it automatically.

3. **Ask for Branch Name in Selected Remote**
   ```
   Which branch from <selected-remote> do you want to sync with?
   Example: main, master, release-4.18
   Default: main
   ```

4. **Ask for New Branch Name**
   ```
   What should the new branch be named in your personal fork?
   Example: feature/my-feature, sync-upstream-main
   ```

5. **Create and Push Branch**

   Implementation:
   ```bash
   cd "$local_path"

   # Fetch the selected remote
   git fetch "$selected_remote"

   # Create new branch from remote branch
   git checkout -b "$new_branch_name" "$selected_remote/$remote_branch"

   # Push to origin (personal fork)
   git push -u origin "$new_branch_name"

   echo "✓ Created branch '$new_branch_name' from $selected_remote/$remote_branch"
   echo "✓ Pushed to origin/$new_branch_name"
   ```

6. **Display Final Summary**
   ```
   ✓ Branch Creation Complete

   Local path: <local-path>
   New branch: <new_branch_name>
   Synced with: <selected-remote>/<remote_branch>

   To verify the setup, run:
     git remote -v
   ```

### Rebase Existing Branch with Remote (Option 5)

When **Option 5** is selected from step 2, follow this flow to rebase an existing branch with the latest code from a remote:

1. **Ask for Existing Local Repository Path**
   ```
   What is the local path to your existing repository?
   Example: $HOME/go/src/github.com/kubernetes/kubernetes
   ```

   Validate that the directory exists and is a git repository:
   ```bash
   if [ ! -d "$local_path" ]; then
     echo "Error: Directory does not exist"
     exit 1
   fi

   if [ ! -d "$local_path/.git" ]; then
     echo "Error: Not a git repository"
     exit 1
   fi

   cd "$local_path"
   ```

2. **Ask for Branch to Rebase**
   ```
   Which branch do you want to rebase?
   Example: feature/my-feature, bugfix/fix-123
   ```

   Validate that the branch exists:
   ```bash
   if ! git rev-parse --verify "$branch_name" >/dev/null 2>&1; then
     echo "Error: Branch '$branch_name' does not exist"
     exit 1
   fi
   ```

3. **Determine Current Remote Tracking Branch**

   Check if the branch has a remote tracking branch:
   ```bash
   cd "$local_path"

   # Get the upstream tracking branch for the specified branch
   tracking_branch=$(git rev-parse --abbrev-ref "$branch_name@{upstream}" 2>/dev/null)

   if [ -n "$tracking_branch" ]; then
     echo "Current tracking branch: $tracking_branch"
     # Parse remote and branch name
     remote_name=$(echo "$tracking_branch" | cut -d'/' -f1)
     remote_branch=$(echo "$tracking_branch" | cut -d'/' -f2-)
   else
     echo "This branch is not tracking any remote branch"
     remote_name=""
     remote_branch=""
   fi
   ```

4. **List Available Remotes and Ask for Remote**

   Get all remotes and display them to the user:
   ```bash
   cd "$local_path"
   git remote -v
   ```

   Ask the user which remote to sync with:
   ```
   Which remote do you want to rebase with?
   Available remotes: origin, upstream, openshift
   Current tracking remote: <remote_name> (if exists)
   Default: <remote_name> (if exists, otherwise no default)
   ```

5. **Ask for Branch Name in Selected Remote**
   ```
   Which branch from <selected-remote> do you want to rebase with?
   Current tracking branch: <remote_branch> (if exists)
   Example: main, master, release-4.18
   Default: <remote_branch> (if exists, otherwise main)
   ```

6. **Perform Rebase**

   Implementation:
   ```bash
   cd "$local_path"

   # Check for uncommitted changes
   if ! git diff-index --quiet HEAD --; then
     echo "Warning: You have uncommitted changes."
     read -p "Do you want to stash them? (y/n): " stash_changes
     if [ "$stash_changes" = "y" ]; then
       git stash save "Auto-stash before rebase"
       stashed=true
     else
       echo "Please commit or stash your changes before rebasing."
       exit 1
     fi
   fi

   # Fetch the selected remote
   git fetch "$selected_remote"

   # Checkout the branch
   git checkout "$branch_name"

   # Perform rebase
   echo "Rebasing $branch_name with $selected_remote/$remote_branch..."
   if git rebase "$selected_remote/$remote_branch"; then
     echo "✓ Rebase completed successfully"

     # Pop stash if we stashed changes
     if [ "$stashed" = "true" ]; then
       echo "Restoring stashed changes..."
       git stash pop
     fi

     # Ask about force push
     read -p "Do you want to force push to origin/$branch_name? (y/n): " force_push
     if [ "$force_push" = "y" ]; then
       git push -f origin "$branch_name"
       echo "✓ Force pushed to origin/$branch_name"
     else
       echo "You can force push later with: git push -f origin $branch_name"
     fi
   else
     echo "✗ Rebase failed. Please resolve conflicts manually."
     echo "After resolving conflicts, run: git rebase --continue"
     echo "To abort the rebase, run: git rebase --abort"

     # If stashed, remind user
     if [ "$stashed" = "true" ]; then
       echo "Note: Your changes were stashed. Run 'git stash pop' after completing the rebase."
     fi
     exit 1
   fi
   ```

7. **Display Final Summary**
   ```
   ✓ Rebase Complete

   Local path: <local-path>
   Branch: <branch_name>
   Rebased with: <selected-remote>/<remote_branch>

   To verify the rebase, run:
     git log --oneline -10
   ```

### Managing Existing Repository

When the local directory already exists, present options:

```
The directory <local-path> already exists.
What would you like to do?

1. Create a branch synced with upstream
2. Create a branch synced with downstream
3. Sync an existing personal fork branch with upstream
4. Just setup/verify remotes
5. Cancel
```

#### Option 1: Create Branch Synced with Upstream

```
Which upstream branch do you want to sync with?
Default: main
```

Implementation:
```bash
cd <local-path>

# Verify/add upstream remote if not exists
git remote | grep -q "^upstream$" || git remote add upstream git@github.com:<upstream-org>/<upstream-repo>.git

# Fetch upstream
git fetch upstream

# Get upstream branch (default: main)
upstream_branch="${user_input:-main}"

# Create new local branch
read -p "Name for the new local branch: " local_branch
git checkout -b "$local_branch" "upstream/$upstream_branch"

# Push to personal fork
git push -u origin "$local_branch"
```

#### Option 2: Create Branch Synced with Downstream

```
What is the downstream remote name?
Default: openshift
```

```
Which downstream branch do you want to sync with?
Default: master
```

Implementation:
```bash
cd <local-path>

# Verify/add downstream remote if not exists
downstream_name="${user_input:-openshift}"
git remote | grep -q "^$downstream_name$" || {
  read -p "Downstream repository (e.g., openshift/kubernetes): " downstream_repo
  git remote add "$downstream_name" "git@github.com:$downstream_repo.git"
}

# Fetch downstream
git fetch "$downstream_name"

# Get downstream branch
downstream_branch="${user_input:-master}"

# Create new local branch
read -p "Name for the new local branch: " local_branch
git checkout -b "$local_branch" "$downstream_name/$downstream_branch"

# Push to personal fork
git push -u origin "$local_branch"
```

#### Option 3: Sync Personal Fork Branch with Upstream

```
Which branch in your personal fork do you want to sync?
```

```
Which upstream branch should it sync with?
Default: main
```

Implementation:
```bash
cd <local-path>

# Verify remotes
git remote | grep -q "^upstream$" || git remote add upstream git@github.com:<upstream-org>/<upstream-repo>.git

# Fetch all
git fetch --all

# Checkout the personal fork branch
git checkout "$personal_branch"

# Rebase or merge with upstream
read -p "Sync method (rebase/merge)? Default: rebase: " sync_method
sync_method="${sync_method:-rebase}"

upstream_branch="${user_input:-main}"

if [ "$sync_method" = "rebase" ]; then
  git rebase "upstream/$upstream_branch"
else
  git merge "upstream/$upstream_branch"
fi

# Push to personal fork (may need force push if rebased)
if [ "$sync_method" = "rebase" ]; then
  echo "Rebase complete. You may need to force push: git push -f origin $personal_branch"
  read -p "Force push now? (y/n): " force_push
  [ "$force_push" = "y" ] && git push -f origin "$personal_branch"
else
  git push origin "$personal_branch"
fi
```

#### Option 4: Setup/Verify Remotes

Implementation:
```bash
cd <local-path>

# Show current remotes
echo "Current remotes:"
git remote -v

# Check and add missing remotes
echo ""
echo "Verifying remotes..."

# Check origin
if ! git remote | grep -q "^origin$"; then
  read -p "Origin remote not found. Enter origin URL (your personal fork): " origin_url
  git remote add origin "$origin_url"
  echo "✓ Added origin remote"
else
  echo "✓ Origin remote exists"
fi

# Check upstream
if ! git remote | grep -q "^upstream$"; then
  read -p "Upstream remote not found. Enter upstream URL: " upstream_url
  git remote add upstream "$upstream_url"
  echo "✓ Added upstream remote"
else
  echo "✓ Upstream remote exists"
fi

# Check downstream (optional)
read -p "Do you need a downstream remote (e.g., OpenShift fork)? (y/n): " need_downstream
if [ "$need_downstream" = "y" ]; then
  read -p "Downstream remote name (default: openshift): " downstream_name
  downstream_name="${downstream_name:-openshift}"

  if ! git remote | grep -q "^$downstream_name$"; then
    read -p "Downstream repository (e.g., openshift/kubernetes): " downstream_repo
    git remote add "$downstream_name" "git@github.com:$downstream_repo.git"
    echo "✓ Added $downstream_name remote"
  else
    echo "✓ $downstream_name remote exists"
  fi
fi

# Fetch all remotes
echo ""
echo "Fetching all remotes..."
git fetch --all
echo "✓ All remotes fetched"

# Show final configuration
echo ""
echo "Final remote configuration:"
git remote -v
```

### Validation Steps

Throughout the process:

1. **Validate GitHub Repository URLs**
   - Use `gh repo view <org>/<repo>` to verify repository exists
   - Handle both HTTPS and SSH URL formats

2. **Verify GitHub Authentication**
   - Check if `gh auth status` shows authenticated
   - If not authenticated, prompt: `gh auth login`

3. **Check Git Configuration**
   - Verify git user.name and user.email are set
   - If not: prompt user to configure with `git config --global user.name` and `git config --global user.email`

4. **Verify SSH Keys**
   - When using SSH URLs (git@github.com:...), verify SSH key is configured
   - Test with: `ssh -T git@github.com`

5. **Handle Errors Gracefully**
   - If fork creation fails (already exists), continue with existing fork
   - If clone fails (directory exists), offer to use existing directory
   - If remote add fails (already exists), skip or update URL

## Return Value

The command returns a summary of the setup and instructs the user to verify:

```
✓ Repository Setup Complete

Local path: $HOME/go/src/github.com/kubernetes/kubernetes
Current branch: feature-branch

Remotes configured:
  origin       git@github.com:<username>/kubernetes.git (your fork)
  upstream     git@github.com:kubernetes/kubernetes.git (upstream)
  openshift    git@github.com:openshift/kubernetes.git (downstream)

To verify the setup, run:
  git remote -v

Next steps:
  cd $HOME/go/src/github.com/kubernetes/kubernetes
  git fetch --all
  git branch -a  # View all branches
```

## Examples

### Example 1: Complete Setup for OpenShift Workflow with kubernetes/kubernetes

```
/git:setup
```

Interactive flow:
```
Where do you keep your code repositories? (default: $HOME/go/src)
> $HOME/go/src

✓ Changed to directory $HOME/go/src

Do you want to set up:
1. Upstream repository only
2. Upstream with downstream fork (Red Hat/OpenShift workflow)
3. Downstream repository only (e.g., OpenShift projects without upstream)
4. Create a branch in personal forked repository synced with upstream/downstream branch (for existing repos)
5. Rebase an existing branch with latest code from remote (for existing repos)
> 2

What is the upstream repository URL?
> https://github.com/kubernetes/kubernetes

Do you want to create a personal fork from upstream? (y/n)
> y

Creating fork...
✓ Fork created: <username>/kubernetes

Do you have a specific branch in your personal fork? (y/n)
> n

What is the downstream repository? (default: openshift/kubernetes)
> openshift/kubernetes

What should the downstream remote be named? (default: openshift)
> openshift

Where do you want to clone the repository?
Recommended: $HOME/go/src/github.com/kubernetes/kubernetes
> $HOME/go/src/github.com/kubernetes/kubernetes

Cloning repository...
✓ Cloned to $HOME/go/src/github.com/kubernetes/kubernetes
✓ Added upstream remote
✓ Added openshift remote
✓ Fetched all remotes

✓ Repository Setup Complete

Local path: $HOME/go/src/github.com/kubernetes/kubernetes
Current branch: master

Remotes configured:
  origin       git@github.com:<username>/kubernetes.git (your fork)
  upstream     git@github.com:kubernetes/kubernetes.git (upstream)
  openshift    git@github.com:openshift/kubernetes.git (downstream)

To verify the setup, run:
  git remote -v

Next steps:
  cd $HOME/go/src/github.com/kubernetes/kubernetes
  git fetch --all
  git branch -a  # View all branches

Setup complete!
```

### Example 2: Upstream Only Setup

```
/git:setup --upstream-only
```

or interactively select option 1.

### Example 2a: Upstream Only Setup with containerd/cgroups

```
/git:setup
```

Interactive flow:
```
Where do you keep your code repositories? (default: $HOME/go/src)
> $HOME/go/src

✓ Changed to directory $HOME/go/src

Do you want to set up:
1. Upstream repository only
2. Upstream with downstream fork (Red Hat/OpenShift workflow)
3. Downstream repository only (e.g., OpenShift projects without upstream)
4. Create a branch in personal forked repository synced with upstream/downstream branch (for existing repos)
5. Rebase an existing branch with latest code from remote (for existing repos)
> 1

What is the upstream repository URL?
> https://github.com/containerd/cgroups

Do you want to create a personal fork from upstream? (y/n)
> y

Creating fork...
✓ Fork created: <username>/cgroups

Do you have a specific branch in your personal fork? (y/n)
> n

Where do you want to clone the repository?
Recommended: $HOME/go/src/github.com/containerd/cgroups
> $HOME/go/src/github.com/containerd/cgroups

Cloning repository...
✓ Cloned to $HOME/go/src/github.com/containerd/cgroups
✓ Added upstream remote
✓ Fetched all remotes

✓ Repository Setup Complete

Local path: $HOME/go/src/github.com/containerd/cgroups
Current branch: main

Remotes configured:
  origin       git@github.com:<username>/cgroups.git (your fork)
  upstream     git@github.com:containerd/cgroups.git (upstream)

To verify the setup, run:
  git remote -v

Setup complete!
```

### Example 3: Downstream Only Setup (OpenShift Projects)

```
/git:setup --downstream-only
```

Interactive flow:
```
Where do you keep your code repositories? (default: $HOME/go/src)
> $HOME/go/src

✓ Changed to directory $HOME/go/src

Do you want to set up:
1. Upstream repository only
2. Upstream with downstream fork (Red Hat/OpenShift workflow)
3. Downstream repository only (e.g., OpenShift projects without upstream)
4. Create a branch in personal forked repository synced with upstream/downstream branch (for existing repos)
5. Rebase an existing branch with latest code from remote (for existing repos)
> 3

What is the downstream repository URL?
> https://github.com/openshift/machine-config-operator

Do you want to create a personal fork from downstream? (y/n)
> y

Creating fork...
✓ Fork created: <username>/machine-config-operator

Do you have a specific branch in your personal fork? (y/n)
> n

What should the downstream remote be named? (default: openshift)
> openshift

Where do you want to clone the repository?
Recommended: $HOME/go/src/github.com/openshift/machine-config-operator
> $HOME/go/src/github.com/openshift/machine-config-operator

Cloning repository...
✓ Cloned to $HOME/go/src/github.com/openshift/machine-config-operator
✓ Added openshift remote
✓ Fetched all remotes

To verify the setup, run:
  git remote -v

Setup complete!
```

### Example 4: Existing Directory - Create Branch from Upstream

```
/git:setup
```

```
The directory $HOME/go/src/github.com/kubernetes/kubernetes already exists.
What would you like to do?
1. Create a branch synced with upstream
2. Create a branch synced with downstream
3. Sync an existing personal fork branch with upstream
4. Just setup/verify remotes
> 1

Which upstream branch do you want to sync with? (default: main)
> main

Name for the new local branch:
> feature/my-new-feature

✓ Created branch 'feature/my-new-feature' tracking upstream/main
✓ Pushed to origin/feature/my-new-feature

To verify the setup, run:
  git remote -v
```

### Example 5: Sync Existing Branch with Upstream

```
/git:setup
```

```
The directory $HOME/go/src/github.com/openshift/origin already exists.
What would you like to do?
> 3

Which branch in your personal fork do you want to sync?
> my-feature-branch

Which upstream branch should it sync with? (default: main)
> main

Sync method (rebase/merge)? (default: rebase)
> rebase

✓ Rebased my-feature-branch onto upstream/main
Force push now? (y/n)
> y
✓ Force pushed to origin/my-feature-branch

To verify the setup, run:
  git remote -v
```

### Example 6: Setup Remotes for Existing Repository

```
/git:setup
```

```
The directory $HOME/go/src/github.com/openshift/kubernetes already exists.
What would you like to do?
> 4

Current remotes:
origin	git@github.com:<username>/kubernetes.git (fetch)
origin	git@github.com:<username>/kubernetes.git (push)

Verifying remotes...
✓ Origin remote exists
Upstream remote not found. Enter upstream URL:
> https://github.com/kubernetes/kubernetes
✓ Added upstream remote

Do you need a downstream remote? (y/n)
> y

Downstream remote name (default: openshift):
> openshift

Downstream repository:
> openshift/kubernetes
✓ Added openshift remote

Fetching all remotes...
✓ All remotes fetched

Final remote configuration:
origin     git@github.com:<username>/kubernetes.git (fetch)
origin     git@github.com:<username>/kubernetes.git (push)
upstream   git@github.com:kubernetes/kubernetes.git (fetch)
upstream   git@github.com:kubernetes/kubernetes.git (push)
openshift  git@github.com:openshift/kubernetes.git (fetch)
openshift  git@github.com:openshift/kubernetes.git (push)

To verify the setup, run:
  git remote -v
```

### Example 7: Create Branch in Existing Repository Synced with Remote

```
/git:setup
```

```
Where do you keep your code repositories? (default: $HOME/go/src)
> $HOME/go/src

✓ Changed to directory $HOME/go/src

Do you want to set up:
1. Upstream repository only
2. Upstream with downstream fork (Red Hat/OpenShift workflow)
3. Downstream repository only (e.g., OpenShift projects without upstream)
4. Create a branch in personal fork synced with upstream/downstream branch (for existing repos)
> 4

What is the local path to your existing repository?
> $HOME/go/src/github.com/kubernetes/kubernetes

Current remotes:
origin     git@github.com:<username>/kubernetes.git (fetch)
origin     git@github.com:<username>/kubernetes.git (push)
upstream   git@github.com:kubernetes/kubernetes.git (fetch)
upstream   git@github.com:kubernetes/kubernetes.git (push)
openshift  git@github.com:openshift/kubernetes.git (fetch)
openshift  git@github.com:openshift/kubernetes.git (push)

Which remote do you want to sync with?
Available remotes: origin, upstream, openshift
> upstream

Which branch from upstream do you want to sync with? (default: main)
> main

What should the new branch be named in your personal fork?
> sync-upstream-main

✓ Created branch 'sync-upstream-main' from upstream/main
✓ Pushed to origin/sync-upstream-main

✓ Branch Creation Complete

Local path: $HOME/go/src/github.com/kubernetes/kubernetes
New branch: sync-upstream-main
Synced with: upstream/main

To verify the setup, run:
  git remote -v
```

### Example 8: Rebase Existing Branch with Remote

```
/git:setup
```

```
Where do you keep your code repositories? (default: $HOME/go/src)
> $HOME/go/src

✓ Changed to directory $HOME/go/src

Do you want to set up:
1. Upstream repository only
2. Upstream with downstream fork (Red Hat/OpenShift workflow)
3. Downstream repository only (e.g., OpenShift projects without upstream)
4. Create a branch in personal forked repository synced with upstream/downstream branch (for existing repos)
5. Rebase an existing branch with latest code from remote (for existing repos)
> 5

What is the local path to your existing repository?
> $HOME/go/src/github.com/kubernetes/kubernetes

Which branch do you want to rebase?
> feature/my-feature

Current remotes:
origin     git@github.com:<username>/kubernetes.git (fetch)
origin     git@github.com:<username>/kubernetes.git (push)
upstream   git@github.com:kubernetes/kubernetes.git (fetch)
upstream   git@github.com:kubernetes/kubernetes.git (push)
openshift  git@github.com:openshift/kubernetes.git (fetch)
openshift  git@github.com:openshift/kubernetes.git (push)

Current tracking branch: upstream/master

Which remote do you want to rebase with?
Available remotes: origin, upstream, openshift
Current tracking remote: upstream
> upstream

Which branch from upstream do you want to rebase with?
Current tracking branch: master
> master

Warning: You have uncommitted changes.
Do you want to stash them? (y/n)
> y

✓ Stashed uncommitted changes
Fetching upstream...
Checking out feature/my-feature...
Rebasing feature/my-feature with upstream/master...
✓ Rebase completed successfully
Restoring stashed changes...
✓ Stashed changes restored

Do you want to force push to origin/feature/my-feature? (y/n)
> y

✓ Force pushed to origin/feature/my-feature

✓ Rebase Complete

Local path: $HOME/go/src/github.com/kubernetes/kubernetes
Branch: feature/my-feature
Rebased with: upstream/master

To verify the rebase, run:
  git log --oneline -10
```

## Arguments

- `--upstream-only`: Skip downstream setup, only configure upstream and personal fork
- `--downstream-only`: Skip upstream setup, only configure downstream (OpenShift/Red Hat fork) and personal fork. Useful for projects like openshift/machine-config-operator that don't have an upstream repository.
- `--ssh`: Use SSH URLs for git remotes (default)
- `--https`: Use HTTPS URLs for git remotes instead of SSH
- `--no-fork`: Don't create a fork, only clone upstream/downstream
- `--path <path>`: Specify the local clone path (skips prompt)

## Safety Considerations

1. **Backup Existing Work**: If directory exists and has uncommitted changes, warn user
2. **Verify Write Permissions**: Check if user has write access to personal fork before cloning
3. **SSH Key Check**: Verify SSH keys are configured before using SSH URLs
4. **Git Configuration**: Ensure user.name and user.email are configured
5. **Remote Conflicts**: If remote names conflict, ask user to choose different names
6. **Branch Conflicts**: If branch name exists, offer to use different name or force update

## Prerequisites

- Git installed and configured
- GitHub CLI (`gh`) installed and authenticated
- SSH keys configured for GitHub (if using SSH URLs)
- Write access to create forks (for fork creation)

## Notes

- This command is compatible with the `/openshift:rebase` workflow which requires three remotes: origin, openshift, and upstream
- Default behavior uses SSH URLs (git@github.com:...) for better authentication with SSH keys
- The recommended directory structure follows Go conventions: `$HOME/go/src/github.com/<org>/<repo>`
- For OpenShift projects, the downstream remote name "openshift" is recommended for compatibility with rebase scripts
