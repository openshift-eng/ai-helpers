#!/bin/bash

set -e

# Setup script for OLM development repositories
# Usage: setup-repos.sh <target-directory> <github-username>

TARGET_DIR="$1"
GITHUB_USER="$2"

if [ -z "$TARGET_DIR" ] || [ -z "$GITHUB_USER" ]; then
  echo "Usage: $0 <target-directory> <github-username>"
  exit 1
fi

# Define repositories with metadata: "org/repo:type:version"
declare -a REPOS=(
  # OLM v0 - Upstream
  "operator-framework/operator-registry:upstream:olmv0"
  "operator-framework/operator-lifecycle-manager:upstream:olmv0"
  "operator-framework/api:upstream:olmv0"

  # OLM v0 - Downstream
  "openshift/operator-framework-olm:downstream:olmv0"
  "operator-framework/operator-marketplace:downstream:olmv0"

  # OLM v1 - Upstream
  "operator-framework/operator-controller:upstream:olmv1"

  # OLM v1 - Downstream
  "openshift/operator-framework-operator-controller:downstream:olmv1"
  "openshift/cluster-olm-operator:downstream:olmv1"

  # Documentation
  "openshift/openshift-docs:downstream:docs"
)

# Track successes and failures
declare -a SUCCESSFUL_REPOS=()
declare -a FAILED_REPOS=()

echo "Starting OLM repository setup..."
echo "Target directory: $TARGET_DIR"
echo "GitHub user: $GITHUB_USER"
echo ""

# Process each repository
for repo_entry in "${REPOS[@]}"; do
  # Parse repository metadata
  IFS=':' read -r repo_full type version <<< "$repo_entry"
  org=$(echo "$repo_full" | cut -d'/' -f1)
  repo_name=$(echo "$repo_full" | cut -d'/' -f2)

  echo "Processing: $repo_full ($type, $version)"

  # Check if fork already exists
  echo "  Checking for existing fork..."
  if gh repo view "$GITHUB_USER/$repo_name" &>/dev/null; then
    echo "  ✓ Fork already exists: $GITHUB_USER/$repo_name"
  else
    echo "  Creating fork of $repo_full..."
    if gh repo fork "$repo_full" --clone=false 2>&1; then
      echo "  ✓ Fork created: $GITHUB_USER/$repo_name"
    else
      echo "  ✗ Failed to fork $repo_full"
      FAILED_REPOS+=("$repo_full (fork failed)")
      echo ""
      continue
    fi
  fi

  # Determine clone directory
  clone_dir="$TARGET_DIR/$GITHUB_USER/$repo_name"

  # Ensure parent directory exists
  parent_dir="$TARGET_DIR/$GITHUB_USER"
  if [ ! -d "$parent_dir" ]; then
    echo "  Creating parent directory: $parent_dir"
    if ! mkdir -p "$parent_dir" 2>/dev/null; then
      echo "  ✗ Failed to create directory: $parent_dir"
      echo "    Check permissions for $TARGET_DIR"
      FAILED_REPOS+=("$repo_full (directory creation failed)")
      echo ""
      continue
    fi
  fi

  # Clone repository if not already cloned
  if [ -d "$clone_dir" ]; then
    echo "  ⊙ Repository already cloned at: $clone_dir"
    echo "  Skipping clone (directory exists)"
  else
    echo "  Cloning to: $clone_dir"
    # Capture git clone output and exit code
    clone_output=$(git clone "git@github.com:$GITHUB_USER/$repo_name.git" "$clone_dir" 2>&1)
    clone_exit=$?

    if [ $clone_exit -eq 0 ]; then
      # Filter out "Cloning into..." line and show remaining output if any
      filtered_output=$(echo "$clone_output" | grep -v "^Cloning")
      if [ -n "$filtered_output" ]; then
        echo "$filtered_output"
      fi
      echo "  ✓ Repository cloned"
    else
      echo "  ✗ Failed to clone $GITHUB_USER/$repo_name"
      # Show error output indented
      echo "$clone_output" | sed 's/^/    /'
      FAILED_REPOS+=("$repo_full (clone failed)")
      echo ""
      continue
    fi
  fi

  # Add upstream remote if not already added
  cd "$clone_dir"
  if git remote | grep -q "^upstream$"; then
    echo "  ⊙ Upstream remote already exists"
  else
    echo "  Adding upstream remote: $repo_full"
    if git remote add upstream "git@github.com:$repo_full.git" 2>&1; then
      echo "  ✓ Upstream remote added"
    else
      echo "  ✗ Failed to add upstream remote"
      FAILED_REPOS+=("$repo_full (upstream remote failed)")
      echo ""
      continue
    fi
  fi

  # Fetch upstream
  echo "  Fetching upstream..."
  if git fetch upstream >/dev/null 2>&1; then
    echo "  ✓ Upstream fetched"
  else
    echo "  ⚠ Warning: Failed to fetch upstream (may be temporary)"
  fi

  # Verify remote configuration
  echo "  Verifying remotes..."
  git remote -v | grep -E "^(origin|upstream)" | sed 's/^/    /'

  SUCCESSFUL_REPOS+=("$repo_full")
  echo "  ✓ Setup complete for $repo_name"
  echo ""
done

# Display summary
echo "======================================="
echo "Repository Setup Summary"
echo "======================================="
echo ""

if [ ${#SUCCESSFUL_REPOS[@]} -gt 0 ]; then
  echo "Successfully set up ${#SUCCESSFUL_REPOS[@]} repositories:"
  for repo in "${SUCCESSFUL_REPOS[@]}"; do
    echo "  ✓ $repo"
  done
  echo ""
fi

if [ ${#FAILED_REPOS[@]} -gt 0 ]; then
  echo "Failed to set up ${#FAILED_REPOS[@]} repositories:"
  for repo in "${FAILED_REPOS[@]}"; do
    echo "  ✗ $repo"
  done
  echo ""
  exit 1
fi

echo "All repositories set up successfully!"
exit 0
