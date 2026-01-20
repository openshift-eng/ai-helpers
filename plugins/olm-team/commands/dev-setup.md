---
description: Set up OLM development repositories and onboard to the team
argument-hint: "[target-directory]"
---

## Name
olm-team:dev-setup

## Synopsis
```
/olm-team:dev-setup [target-directory]
```

## Description
The `olm-team:dev-setup` command automates the onboarding process for new OLM team members by setting up all necessary development repositories. It forks repositories (if not already forked), clones them locally with proper remote configuration, and provides educational context about each repository to accelerate team onboarding.

This command helps new developers understand the OLM ecosystem by explaining:
- The difference between upstream (operator-framework) and downstream (openshift) organizations
- The distinction between OLM v0 (traditional) and OLM v1 (next-generation) architectures
- The purpose and relationship of each repository in the development workflow

## Implementation

### Step 1: Validate Prerequisites

Check for required tools and authentication:

1. **Verify GitHub CLI is installed**:
   ```bash
   which gh
   ```
   If not installed, provide installation instructions for the user's platform.

2. **Verify GitHub CLI authentication**:
   ```bash
   gh auth status
   ```
   If not authenticated, prompt user to run:
   ```bash
   gh auth login
   ```

3. **Verify git is installed**:
   ```bash
   which git
   ```

4. **Get GitHub username**:
   ```bash
   gh api user --jq '.login'
   ```
   Store this for later use when determining fork URLs.

### Step 2: Determine Target Directory

1. **If target directory is provided as argument**:
   - Use the provided directory path
   - Expand `~` to home directory if present
   - Create directory if it doesn't exist

2. **If no target directory provided**:
   - Ask user for preferred location using AskUserQuestion tool
   - Suggest common options:
     - `~/go/src/github.com/` (Go workspace convention)
     - `~/src/` (Simple source directory)
     - `~/code/olm/` (OLM-specific directory)
   - Create the chosen directory if it doesn't exist

3. **Verify directory is writable**:
   ```bash
   test -w <target-directory> && echo "writable" || echo "not writable"
   ```

### Step 3: Display Repository Overview

Before starting the setup process, display an educational overview to help the user understand the OLM ecosystem:

```
OLM Development Repository Structure
=====================================

The OLM project is split between upstream (operator-framework) and downstream (openshift) organizations:

**Upstream (operator-framework)**: Community-driven development and releases
**Downstream (openshift)**: OpenShift-specific customizations and productization

OLM v0 Repositories (Traditional Architecture)
-----------------------------------------------

UPSTREAM:
  • operator-framework/operator-registry
    Purpose: Catalog and bundle management for operators
    Description: Defines the format for storing operator metadata and provides
    tools (opm) for building and querying operator catalogs

  • operator-framework/operator-lifecycle-manager
    Purpose: Core OLM v0 runtime and controllers
    Description: Manages operator installation, upgrades, and lifecycle on Kubernetes.
    Includes controllers for CSV, Subscription, InstallPlan, and OperatorGroup resources

  • operator-framework/api
    Purpose: API definitions and CRD schemas
    Description: Defines the Kubernetes Custom Resource Definitions (CRDs) used by OLM,
    including ClusterServiceVersion, Subscription, InstallPlan, CatalogSource, etc.

DOWNSTREAM:
  • openshift/operator-framework-olm
    Purpose: OpenShift distribution of OLM v0
    Description: Downstream fork that includes OpenShift-specific patches, security
    enhancements, and integration points. This is what ships in OpenShift products

  • operator-framework/operator-marketplace
    Purpose: OperatorHub integration
    Description: Provides the OperatorHub UI integration and marketplace functionality
    for discovering and installing operators in OpenShift

OLM v1 Repositories (Next-Generation Architecture)
---------------------------------------------------

UPSTREAM:
  • operator-framework/operator-controller
    Purpose: Core OLM v1 runtime
    Description: New architecture using ClusterExtension and Catalog resources.
    Simplified design with better dependency resolution and cluster extensions

DOWNSTREAM:
  • openshift/operator-framework-operator-controller
    Purpose: OpenShift distribution of OLM v1 operator-controller
    Description: Downstream fork with OpenShift-specific modifications

  • openshift/cluster-olm-operator
    Purpose: OLM cluster operator for OpenShift
    Description: Manages the installation and lifecycle of OLM itself on OpenShift clusters.
    Handles upgrades and configuration of OLM components

Documentation Repository
-------------------------

  • openshift/openshift-docs
    Purpose: OpenShift product documentation
    Description: Official OpenShift documentation repository. Contains documentation for all
    OpenShift features including OLM, operators, and OperatorHub. Documentation team members contribute
    documentation updates for OLM-related features and improvements and work closely with engineering team members to ensure accurate content.
```

### Step 4: Run Repository Setup Script

Execute the automated repository setup script to fork, clone, and configure all OLM repositories:

```bash
bash plugins/olm-team/scripts/setup-repos.sh "$target_directory" "$github_username"
```

The script automates the following for each repository:

1. **Check if fork exists**: Uses `gh repo view` to check for existing fork
2. **Fork repository if needed**: Creates fork using `gh repo fork` if it doesn't exist
3. **Clone repository**: Clones the fork to `$target_directory/$github_username/$repo_name`
4. **Add upstream remote**: Adds the original repository as "upstream" remote
5. **Fetch upstream**: Fetches all upstream branches and tags
6. **Verify configuration**: Displays remote configuration for verification

The script processes these repositories:
- **OLM v0 Upstream**: operator-registry, operator-lifecycle-manager, api
- **OLM v0 Downstream**: operator-framework-olm, operator-marketplace
- **OLM v1 Upstream**: operator-controller
- **OLM v1 Downstream**: operator-framework-operator-controller, cluster-olm-operator
- **Documentation**: openshift-docs

The script will:
- Skip forking if fork already exists
- Skip cloning if directory already exists
- Display status messages for each operation
- Provide a summary of successful and failed operations at the end

### Step 5: Generate Summary Report

After processing all repositories, create a summary report:

1. **Show repository locations**:
   List all cloned repositories with their paths

2. **Provide next steps**:
   ```
   Next Steps for OLM Development
   ===============================

   1. Verify your setup:
      cd ~/go/src/github.com/<username>/operator-lifecycle-manager
      git remote -v

   2. Keep your fork in sync with upstream:
      git fetch upstream
      git checkout main
      git merge upstream/main
      git push origin main

   3. Create a feature branch for development:
      git checkout -b feature/my-feature

   4. Build and test (example for operator-lifecycle-manager):
      make build
      make test

   5. Useful resources:
      - OLM Documentation: https://olm.operatorframework.io/
      - OpenShift OLM Docs: https://docs.openshift.com/container-platform/latest/operators/
      - Confluence On-boarding Guide: https://spaces.redhat.com/pages/viewpage.action?pageId=467060465&spaceKey=OOLM&title=Onboarding
      - How We Work Team Process Guide: https://spaces.redhat.com/spaces/OOLM/pages/467060455/_How+We+Work
      - Contributing Guide: Check CONTRIBUTING.md in each repository
   ```

3. **Display repository reference table**:
   Create a quick reference table showing:
   - Repository name
   - Local path
   - Type (Upstream/Downstream)
   - Version (OLM v0/v1)
   - Purpose

### Step 6: Error Handling

Handle common issues:

1. **Fork creation fails**:
   - Check if user has permission to fork
   - Verify repository exists and is accessible
   - Provide manual fork instructions if needed

2. **Clone fails**:
   - Check SSH key configuration:
     ```bash
     ssh -T git@github.com
     ```
   - Suggest HTTPS alternative if SSH fails
   - Check disk space

3. **Remote configuration fails**:
   - Verify remote URL format
   - Check network connectivity
   - Provide manual remote add instructions

4. **Directory permission issues**:
   - Check directory is writable
   - Suggest alternative locations
   - Provide instructions for fixing permissions

## Return Value

- **Format**: Summary report with repository status

The command outputs a structured report containing:

1. **Repository Setup Status**: Success/failure for each repository operation
2. **Location Mapping**: Table showing repository paths and remote configurations
3. **Educational Context**: Explanation of each repository's role in the OLM ecosystem
4. **Next Steps**: Guidance for beginning development work
5. **Error Messages**: Detailed error information for any failures

## Examples

### 1. Basic usage with default directory prompt

```
/olm-team:dev-setup
```

The command will:
- Prompt for target directory selection
- Fork all OLM repositories (if not already forked)
- Clone repositories to chosen location
- Configure origin/upstream remotes
- Display educational overview and next steps

### 2. Specify target directory

```
/olm-team:dev-setup ~/go/src/github.com/
```

Clones all repositories to `~/go/src/github.com/<username>/` directory structure.

### 3. Use Go workspace convention

```
/olm-team:dev-setup ~/go/src/github.com/
```

Creates standard Go workspace layout:
```
~/go/src/github.com/
  <username>/
    operator-registry/
    operator-lifecycle-manager/
    api/
    operator-framework-olm/
    operator-marketplace/
    operator-controller/
    operator-framework-operator-controller/
    cluster-olm-operator/
    openshift-docs/
```

## Arguments

- `target-directory` (optional): Base directory where repositories will be cloned
  - If not provided, user will be prompted to choose or enter a custom path
  - Common choices: `~/go/src/github.com/`, `~/src/`, `~/code/olm/`
  - Will be created if it doesn't exist
  - Repositories will be cloned to: `<target-directory>/<github-username>/<repo-name>/`

## Notes

1. **Fork vs Clone Strategy**: The command uses the fork URL as "origin" and adds the original repository as "upstream". This follows the standard open-source contribution workflow where you push to your fork and create pull requests to upstream.

2. **Directory Structure**: Repositories are organized by username to support working with multiple GitHub accounts or collaborating with others who have different forks.

3. **SSH vs HTTPS**: The command uses SSH URLs (`git@github.com:`) for git operations. Ensure your SSH keys are configured with GitHub. If SSH is not available, the command will guide you through HTTPS setup.

4. **Selective Setup**: If you only need specific repositories, you can manually run the commands for individual repos after understanding the process from the overview.

5. **Keeping Forks Updated**: The command sets up remotes but doesn't automatically sync forks. Use the provided git commands in the summary to keep your forks up to date with upstream.

6. **Build Requirements**: Each repository may have specific build requirements (Go version, dependencies, etc.). Check each repository's README.md for detailed build instructions.
