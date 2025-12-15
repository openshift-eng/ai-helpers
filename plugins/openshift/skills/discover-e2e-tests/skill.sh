#!/bin/bash
# Discover E2E Tests Skill
# Finds e2e test directories in OpenShift repositories

set -e

# Check for go.mod file
if [ ! -f "go.mod" ]; then
    echo "Error: No go.mod file found in current directory" >&2
    echo "Please ensure you are in the root of a Go module." >&2
    exit 1
fi

# Get module path and repository name
MODULE_PATH=$(head -1 go.mod | awk '{print $2}')
REPO_NAME=$(basename "$MODULE_PATH")

echo "Module: $MODULE_PATH"
echo "Repository: $REPO_NAME"
echo ""

# Search for e2e test directories in order of preference
E2E_DIRS=("test/e2e" "tests/e2e" "e2e" "pkg/e2e" "test/e2e-test")
E2E_PATH=""

for dir in "${E2E_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        # Check if directory contains test files
        TEST_COUNT=$(find "$dir" -name "*_test.go" -type f 2>/dev/null | wc -l | tr -d ' ')
        if [ "$TEST_COUNT" -gt 0 ]; then
            echo "Found $TEST_COUNT test files in $dir"
            E2E_PATH="$dir"

            # Detect test framework
            if grep -r "github.com/onsi/ginkgo" "$dir" --include="*.go" -q 2>/dev/null; then
                TEST_FRAMEWORK="ginkgo"
                echo "Framework: Ginkgo"
            else
                TEST_FRAMEWORK="go-test"
                echo "Framework: Standard Go testing"
            fi

            break
        fi
    fi
done

# Check if e2e tests were found
if [ -z "$E2E_PATH" ]; then
    echo "Error: No e2e test directory found" >&2
    echo "" >&2
    echo "Searched locations:" >&2
    for dir in "${E2E_DIRS[@]}"; do
        echo "  - $dir/" >&2
    done
    echo "" >&2
    echo "Please create e2e tests or verify the directory structure." >&2
    exit 1
fi

# Export variables for use by calling scripts
export MODULE_PATH
export REPO_NAME
export E2E_PATH
export TEST_FRAMEWORK

# Output results
echo ""
echo "E2E_PATH=$E2E_PATH"
echo "MODULE_PATH=$MODULE_PATH"
echo "REPO_NAME=$REPO_NAME"
echo "TEST_FRAMEWORK=$TEST_FRAMEWORK"
