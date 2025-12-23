---
name: Discover E2E Tests
description: Find e2e test directories in OpenShift repositories following common conventions
---

# Discover E2E Tests

This skill discovers e2e test directories in OpenShift repositories by searching common locations and validating the presence of test files.

## When to Use This Skill

Use this skill when you need to:

- Find e2e tests in an OpenShift repository
- Determine the correct test path for building/running e2e tests
- Validate that a repository has e2e tests before attempting to run them
- Identify the Go module path for the repository

## Prerequisites

1. **Go Module**
   - The repository should have a `go.mod` file
   - Check: `test -f go.mod`

2. **Test Files**
   - At least one `*_test.go` file in the e2e directory
   - Tests should use Go's testing framework

## Implementation Steps

### Step 1: Find Go Module Path

Extract the module path from `go.mod`:

```bash
MODULE_PATH=$(head -1 go.mod | awk '{print $2}')
echo "Go module: $MODULE_PATH"
```

### Step 2: Search Common E2E Test Locations

OpenShift repositories typically place e2e tests in these locations (in order of preference):

1. `test/e2e/` - Most common location
2. `tests/e2e/` - Alternative location
3. `e2e/` - Root-level e2e directory
4. `pkg/e2e/` - Package-based location
5. `test/e2e-test/` - Alternative naming

Search for these directories:

```bash
E2E_DIRS=("test/e2e" "tests/e2e" "e2e" "pkg/e2e" "test/e2e-test")

for dir in "${E2E_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        # Check if it contains test files
        if ls "$dir"/*_test.go 1>/dev/null 2>&1 || \
           find "$dir" -name "*_test.go" -type f | head -1 | grep -q .; then
            E2E_PATH="$dir"
            echo "Found e2e tests in: $E2E_PATH"
            break
        fi
    fi
done

if [ -z "$E2E_PATH" ]; then
    echo "Error: No e2e test directory found"
    exit 1
fi
```

### Step 3: Validate Test Structure

Once a directory is found, validate it has proper test files:

```bash
# Count test files
TEST_COUNT=$(find "$E2E_PATH" -name "*_test.go" -type f | wc -l)
echo "Found $TEST_COUNT test files"

if [ "$TEST_COUNT" -eq 0 ]; then
    echo "Warning: Directory exists but contains no test files"
fi
```

### Step 4: Detect Test Framework

Check for common e2e test frameworks:

```bash
# Check for Ginkgo (common in OpenShift)
if grep -r "github.com/onsi/ginkgo" "$E2E_PATH" --include="*.go" -q 2>/dev/null; then
    TEST_FRAMEWORK="ginkgo"
    echo "Test framework: Ginkgo"
# Check for standard Go testing
elif grep -r "testing.T" "$E2E_PATH" --include="*.go" -q 2>/dev/null; then
    TEST_FRAMEWORK="go-test"
    echo "Test framework: Go testing"
else
    TEST_FRAMEWORK="unknown"
    echo "Test framework: Unknown"
fi
```

## Output Variables

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `MODULE_PATH` | Go module path from go.mod | `github.com/openshift/my-operator` |
| `E2E_PATH` | Relative path to e2e test directory | `test/e2e` |
| `TEST_COUNT` | Number of test files found | `15` |
| `TEST_FRAMEWORK` | Detected test framework | `ginkgo` or `go-test` |

## Common E2E Test Patterns

### OpenShift Operators

Most OpenShift operators use this structure:

```
test/
└── e2e/
    ├── e2e_suite_test.go    # Ginkgo suite setup
    ├── e2e_test.go          # Main tests
    └── helpers/             # Test helpers
```

### Origin Repository

The OpenShift origin repository uses:

```
test/
└── e2e/
    ├── e2e.go               # Test definitions
    └── e2e_test.go          # Test runner
```

### Standalone E2E

Some repositories have root-level e2e:

```
e2e/
├── e2e_suite_test.go
├── basic_test.go
└── advanced_test.go
```

## Error Handling

### No go.mod Found

```
Error: No go.mod file found in current directory
Please ensure you are in the root of a Go module.
```

### No E2E Directory Found

```
Error: No e2e test directory found

Searched locations:
  - test/e2e/
  - tests/e2e/
  - e2e/
  - pkg/e2e/
  - test/e2e-test/

Please create e2e tests or verify the directory structure.
```

### No Test Files Found

```
Warning: E2E directory found at test/e2e/ but contains no *_test.go files

This might indicate:
  - Tests are in subdirectories (will still work with ./...)
  - Test files use non-standard naming
  - Directory is empty or contains only helpers
```

## Examples

### Example 1: Basic Discovery

```bash
#!/bin/bash
set -e

# Get module path
MODULE_PATH=$(head -1 go.mod | awk '{print $2}')
echo "Module: $MODULE_PATH"

# Search for e2e directory
E2E_DIRS=("test/e2e" "tests/e2e" "e2e" "pkg/e2e" "test/e2e-test")
E2E_PATH=""

for dir in "${E2E_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        if find "$dir" -name "*_test.go" -type f | head -1 | grep -q .; then
            E2E_PATH="$dir"
            break
        fi
    fi
done

if [ -z "$E2E_PATH" ]; then
    echo "Error: No e2e tests found"
    exit 1
fi

echo "E2E tests found at: $E2E_PATH"
```

### Example 2: Full Discovery with Validation

```bash
#!/bin/bash
set -e

# Verify go.mod exists
if [ ! -f "go.mod" ]; then
    echo "Error: No go.mod found"
    exit 1
fi

MODULE_PATH=$(head -1 go.mod | awk '{print $2}')
REPO_NAME=$(basename "$MODULE_PATH")

echo "Repository: $REPO_NAME"
echo "Module: $MODULE_PATH"

# Find e2e tests
E2E_DIRS=("test/e2e" "tests/e2e" "e2e" "pkg/e2e" "test/e2e-test")

for dir in "${E2E_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        TEST_COUNT=$(find "$dir" -name "*_test.go" -type f | wc -l)
        if [ "$TEST_COUNT" -gt 0 ]; then
            echo "Found $TEST_COUNT test files in $dir"
            E2E_PATH="$dir"
            break
        fi
    fi
done

if [ -z "$E2E_PATH" ]; then
    echo "No e2e tests found in common locations"
    exit 1
fi

# Detect framework
if grep -r "github.com/onsi/ginkgo" "$E2E_PATH" --include="*.go" -q 2>/dev/null; then
    echo "Framework: Ginkgo"
else
    echo "Framework: Standard Go testing"
fi

echo ""
echo "E2E Test Path: ./$E2E_PATH/..."
echo "Go Test Command: go test -v ./$E2E_PATH/..."
```

### Example 3: JSON Output for Scripting

```bash
#!/bin/bash

# Output discovery results as JSON
discover_e2e() {
    local module_path=""
    local e2e_path=""
    local test_count=0
    local framework="unknown"
    
    if [ -f "go.mod" ]; then
        module_path=$(head -1 go.mod | awk '{print $2}')
    fi
    
    for dir in test/e2e tests/e2e e2e pkg/e2e test/e2e-test; do
        if [ -d "$dir" ]; then
            local count=$(find "$dir" -name "*_test.go" -type f 2>/dev/null | wc -l)
            if [ "$count" -gt 0 ]; then
                e2e_path="$dir"
                test_count=$count
                
                if grep -r "github.com/onsi/ginkgo" "$dir" --include="*.go" -q 2>/dev/null; then
                    framework="ginkgo"
                else
                    framework="go-test"
                fi
                break
            fi
        fi
    done
    
    cat << EOF
{
  "module_path": "$module_path",
  "e2e_path": "$e2e_path",
  "test_count": $test_count,
  "framework": "$framework"
}
EOF
}

discover_e2e
```

## Integration with Other Skills

This skill is used by:

- `generate-e2e-dockerfile` - To create Dockerfile with correct test path
- `run-e2e-tests-in-container` command - Main e2e test execution

## Notes

- Always search directories in preference order (test/e2e first)
- The `./...` suffix allows Go to find tests in subdirectories
- Ginkgo tests require the ginkgo binary or `go test` with appropriate flags
- Some repositories may have multiple e2e directories for different test types
- Consider checking for `Makefile` targets like `test-e2e` or `e2e` as well

