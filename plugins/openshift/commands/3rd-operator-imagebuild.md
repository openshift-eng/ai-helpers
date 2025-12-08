---
description: Pull unmerged PR, build operator image with podman, and optionally push to Quay
argument-hint: <pr-url> [quay-repo]
---

## Name
openshift:3rd-operator-imagebuild

## Synopsis
```
/openshift:3rd-operator-imagebuild <pr-url> [quay-repo]
```

## Description
The `openshift:3rd-operator-imagebuild` command automates the workflow for building third-party operator images from unmerged pull requests. It fetches an unmerged PR, builds the operator image using podman with linux/amd64 platform, and optionally pushes the image to a Quay.io repository for deployment and testing.

This command is useful when you need to:
- Build operator images from open pull requests
- Create custom operator images for validation
- Deploy operator changes to a test cluster
- Test operator functionality before merge

## Implementation

### Step 1: Parse PR URL
- Extract repository owner, repository name, and PR number from the URL
- URL format: `https://github.com/<owner>/<repo>/pull/<pr-number>`
- Example: `https://github.com/openshift/gcp-filestore-csi-driver-operator/pull/124`
  - Owner: `openshift`
  - Repo: `gcp-filestore-csi-driver-operator`
  - PR number: `124`
- Validate URL format is correct

### Step 2: Validate Prerequisites
- Check if `podman` is installed and available
  ```bash
  which podman || echo "podman not found"
  ```
- Check if `git` is installed
  ```bash
  which git || echo "git not found"
  ```
- Check if `gh` (GitHub CLI) is installed
  ```bash
  which gh || echo "gh not found"
  ```
- If pushing to Quay (when `$2` is provided), verify `podman login` credentials:
  ```bash
  podman login quay.io --get-login
  ```

### Step 3: Clone or Navigate to Repository
- Check if repository already exists locally
  ```bash
  ls -d <repo-name> 2>/dev/null
  ```
- If not exists, clone the repository:
  ```bash
  gh repo clone <owner>/<repo>
  cd <repo>
  ```
- If exists, navigate to it and ensure it's up to date:
  ```bash
  cd <repo>
  git fetch origin
  ```

### Step 4: Fetch PR Information
- Use GitHub CLI to fetch PR details:
  ```bash
  gh pr view <pr-number> --json headRefName,headRepository,headRepositoryOwner
  ```
- Extract:
  - PR branch name
  - Fork repository URL
  - PR author username

### Step 5: Checkout PR Code
- Add the PR author's fork as a remote (if not already added):
  ```bash
  git remote add pr-<pr-number> <fork-url> 2>/dev/null || true
  ```
- Fetch the PR branch:
  ```bash
  git fetch pr-<pr-number> <branch-name>
  ```
- Checkout the PR branch (create new branch or use detached HEAD):
  ```bash
  git checkout -b test-pr-<pr-number> pr-<pr-number>/<branch-name>
  ```
  or if branch exists:
  ```bash
  git checkout test-pr-<pr-number>
  git reset --hard pr-<pr-number>/<branch-name>
  ```

### Step 6: Determine Dockerfile Location
- Look for Dockerfile in the following order:
  1. `Dockerfile.openshift` (preferred for OpenShift operators)
  2. `Dockerfile`
  3. `build/Dockerfile`
  4. `Dockerfile.rhel`
- Store the found Dockerfile path for use in build command

### Step 7: Build Operator Image with Podman
- Determine the image tag based on whether `$2` is provided:
  - If `$2` (quay-repo) is provided:
    ```bash
    IMG="quay.io/<quay-repo>:pr-<pr-number>"
    ```
  - If `$2` is NOT provided:
    ```bash
    IMG="<repo-name>:pr-<pr-number>"
    ```
- Build the image with platform flag:
  ```bash
  podman build --platform=linux/amd64 -f <dockerfile-path> -t $IMG .
  ```
- Example for PR 124 with quay repo:
  ```bash
  podman build --platform=linux/amd64 -f Dockerfile.openshift -t quay.io/myuser/gcp-filestore-csi-driver-operator:pr-124 .
  ```
- Verify the image was built successfully:
  ```bash
  podman images | grep <image-name>
  ```

### Step 8: Push to Quay.io (if quay-repo provided)
- Only execute if `$2` is provided
- Check if already logged in to Quay:
  ```bash
  podman login quay.io --get-login
  ```
- If not logged in, prompt user to login:
  ```bash
  podman login quay.io
  ```
- Push the image:
  ```bash
  podman push quay.io/<quay-repo>:pr-<pr-number>
  ```
- Verify push success and display image URL

### Step 9: Output Summary
- Display summary of actions taken:
  - Repository cloned/updated
  - PR number and branch fetched
  - Dockerfile used
  - Image name and tag
  - Build status
  - Push status (if applicable)
  - Next steps for deployment

## Return Value

**Format**: Text summary with command outputs

**Success Output (with Quay push)**:
```
✓ Parsed PR: openshift/gcp-filestore-csi-driver-operator#124
✓ Cloned repository to: ./gcp-filestore-csi-driver-operator
✓ Fetched PR #124 from fork
✓ Checked out branch: <branch-name>
✓ Found Dockerfile: Dockerfile.openshift
✓ Built image: quay.io/myuser/gcp-filestore-csi-driver-operator:pr-124
✓ Pushed to Quay.io

Image ready for testing: quay.io/myuser/gcp-filestore-csi-driver-operator:pr-124

Next steps:
1. Deploy operator using this image
2. Run operator test suite
3. Validate functionality
```

**Success Output (local build only)**:
```
✓ Parsed PR: openshift/gcp-filestore-csi-driver-operator#124
✓ Cloned repository to: ./gcp-filestore-csi-driver-operator
✓ Fetched PR #124 from fork
✓ Checked out branch: <branch-name>
✓ Found Dockerfile: Dockerfile.openshift
✓ Built image: gcp-filestore-csi-driver-operator:pr-124

Image built locally: gcp-filestore-csi-driver-operator:pr-124

To push to Quay, run:
podman tag gcp-filestore-csi-driver-operator:pr-124 quay.io/<your-repo>:pr-124
podman push quay.io/<your-repo>:pr-124
```

**Error Handling**:
- If PR URL format is invalid: Display error and expected format
- If PR not found: Display error with PR number and repository
- If no Dockerfile found: List expected Dockerfile locations
- If build fails: Show podman build output and error
- If push fails: Show authentication or network error
- If prerequisites missing: List missing tools with installation instructions

## Examples

1. **Build PR locally without pushing**:
   ```
   /openshift:3rd-operator-imagebuild https://github.com/openshift/gcp-filestore-csi-driver-operator/pull/124
   ```
   Executes:
   ```bash
   podman build --platform=linux/amd64 -f Dockerfile.openshift -t gcp-filestore-csi-driver-operator:pr-124 .
   ```

2. **Build and push to Quay**:
   ```
   /openshift:3rd-operator-imagebuild https://github.com/openshift/gcp-filestore-csi-driver-operator/pull/124 myuser/gcp-filestore-csi-driver-operator
   ```
   Executes:
   ```bash
   podman build --platform=linux/amd64 -f Dockerfile.openshift -t quay.io/myuser/gcp-filestore-csi-driver-operator:pr-124 .
   podman push quay.io/myuser/gcp-filestore-csi-driver-operator:pr-124
   ```

3. **Build from different operator PR**:
   ```
   /openshift:3rd-operator-imagebuild https://github.com/openshift/aws-efs-operator/pull/56 testuser/test-operator
   ```
   Executes:
   ```bash
   podman build --platform=linux/amd64 -f Dockerfile.openshift -t quay.io/testuser/test-operator:pr-56 .
   podman push quay.io/testuser/test-operator:pr-56
   ```

## Arguments

- **$1** (required): PR URL - Full GitHub pull request URL
  - Format: `https://github.com/<owner>/<repo>/pull/<pr-number>`
  - Example: `https://github.com/openshift/gcp-filestore-csi-driver-operator/pull/124`
- **$2** (optional): Quay repository path - Format: `<org>/<repo>` (e.g., `myuser/gcp-filestore-csi-driver-operator`)
  - If provided, the image will be built and tagged as `quay.io/<org>/<repo>:pr-<pr-number>` and pushed to Quay
  - If omitted, the image is only built locally as `<repo-name>:pr-<pr-number>`

## Notes

- Requires `gh` CLI to be installed and authenticated with GitHub
- Clones repository into current directory if not already present
- Uses `--platform=linux/amd64` for consistent cross-platform builds
- Prefers `Dockerfile.openshift` over other Dockerfile variants
- Image tags use format `pr-<number>` for easy identification
- Working directory will contain the cloned repository after command execution
- Preserves git history and allows switching back to original branch
