#!/bin/bash
# Validates that current directory is in correct Go workspace location for openshift/api
# Returns 0 if valid, 1 if invalid
# Prints diagnostic information and suggestions if invalid

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get GOPATH
GOPATH="${GOPATH:-$(go env GOPATH)}"
if [ -z "$GOPATH" ]; then
    echo -e "${RED}Error: GOPATH is not set and 'go env GOPATH' returned empty${NC}" >&2
    echo "Solution: Set GOPATH environment variable or ensure Go is properly installed" >&2
    exit 1
fi

# Expected location
EXPECTED_PATH="$GOPATH/src/github.com/openshift/api"
CURRENT_DIR="$(pwd)"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}Error: Not in a git repository${NC}" >&2
    echo "Current directory: $CURRENT_DIR" >&2
    exit 1
fi

# Check if this is the openshift/api repository
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
if [[ ! "$REMOTE_URL" =~ openshift/api ]]; then
    echo -e "${YELLOW}Warning: This doesn't appear to be the openshift/api repository${NC}" >&2
    echo "Remote URL: $REMOTE_URL" >&2
    echo "Expected: *openshift/api*" >&2
fi

# Check if current directory matches expected GOPATH structure
if [ "$CURRENT_DIR" = "$EXPECTED_PATH" ]; then
    echo -e "${GREEN}✓ Working directory is correct${NC}"
    echo "Location: $CURRENT_DIR"
    echo "GOPATH: $GOPATH"
    exit 0
fi

# Check if current directory is a symlink to the expected path
REAL_CURRENT_DIR="$(realpath "$CURRENT_DIR")"
REAL_EXPECTED_PATH="$(realpath "$EXPECTED_PATH" 2>/dev/null || echo "$EXPECTED_PATH")"
if [ "$REAL_CURRENT_DIR" = "$REAL_EXPECTED_PATH" ]; then
    echo -e "${GREEN}✓ Working directory is correct (via symlink)${NC}"
    echo "Location: $CURRENT_DIR"
    echo "Real path: $REAL_CURRENT_DIR"
    echo "GOPATH: $GOPATH"
    exit 0
fi

# Working directory is incorrect
echo -e "${RED}✗ Working directory is incorrect for code generation${NC}" >&2
echo "" >&2
echo "Current directory: $CURRENT_DIR" >&2
echo "Expected directory: $EXPECTED_PATH" >&2
echo "GOPATH: $GOPATH" >&2
echo "" >&2
echo -e "${YELLOW}Why this matters:${NC}" >&2
echo "Kubernetes code-generators use import path detection that requires repositories" >&2
echo "to be located at GOPATH/src/<import-path>. For openshift/api, the import path" >&2
echo "is 'github.com/openshift/api', so it must be at:" >&2
echo "  \$GOPATH/src/github.com/openshift/api" >&2
echo "" >&2
echo -e "${YELLOW}Suggested fixes:${NC}" >&2
echo "" >&2
echo "Option A - Clone to correct location:" >&2
echo "  mkdir -p $GOPATH/src/github.com/openshift" >&2
echo "  git clone https://github.com/openshift/api $EXPECTED_PATH" >&2
echo "  cd $EXPECTED_PATH" >&2
echo "" >&2
echo "Option B - Create symlink (preserves current work):" >&2
echo "  mkdir -p $GOPATH/src/github.com/openshift" >&2
echo "  ln -s $CURRENT_DIR $EXPECTED_PATH" >&2
echo "  cd $EXPECTED_PATH" >&2
echo "" >&2
echo "Option C - Adjust GOPATH (temporary solution):" >&2
# Try to infer what GOPATH should be
if [[ "$CURRENT_DIR" =~ (.*)/src/github.com/openshift/api$ ]]; then
    INFERRED_GOPATH="${BASH_REMATCH[1]}"
    echo "  export GOPATH=$INFERRED_GOPATH" >&2
    echo "  # This will make the current directory resolve correctly" >&2
else
    echo "  # Cannot infer GOPATH from current directory structure" >&2
    echo "  # Current directory doesn't follow the src/github.com/openshift/api pattern" >&2
fi

exit 1
