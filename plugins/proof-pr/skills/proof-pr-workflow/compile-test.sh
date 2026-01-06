#!/bin/bash
# compile-test.sh - Test compilation for OpenShift repositories
#
# This script provides a consistent interface for testing compilation
# across different OpenShift repository types.
#
# Exit codes:
#   0 - Compilation successful
#   1 - Compilation failed
#   2 - Build system not detected

set -euo pipefail

# Configuration
VERBOSE=0
REPO_PATH="."
QUICK=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Usage
usage() {
    cat <<EOF
Usage: $0 [OPTIONS] [REPO_PATH]

Test compilation for OpenShift repositories.

Options:
    -v, --verbose       Enable verbose output
    -q, --quick         Quick test (skip some checks)
    -h, --help          Show this help message

Arguments:
    REPO_PATH           Path to repository (default: current directory)

Exit codes:
    0 - Compilation successful
    1 - Compilation failed
    2 - Build system not detected
EOF
}

# Logging functions
log() {
    if [ $VERBOSE -eq 1 ]; then
        echo -e "${GREEN}[compile-test]${NC} $*" >&2
    fi
}

log_warn() {
    echo -e "${YELLOW}[compile-test]${NC} WARNING: $*" >&2
}

log_error() {
    echo -e "${RED}[compile-test]${NC} ERROR: $*" >&2
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=1
            shift
            ;;
        -q|--quick)
            QUICK=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            usage
            exit 2
            ;;
        *)
            REPO_PATH="$1"
            shift
            ;;
    esac
done

# Change to repository directory
cd "$REPO_PATH"
REPO_PATH="$(pwd)"
log "Testing compilation in: $REPO_PATH"

# Detect Go module
GO_MODULE=""
if [ -f "go.mod" ]; then
    GO_MODULE=$(grep '^module ' go.mod | awk '{print $2}')
    log "Detected Go module: $GO_MODULE"
fi

# Function to test with Makefile
test_makefile() {
    local makefile="$1"

    log "Checking Makefile for build targets..."

    # Common build targets in order of preference
    local targets=("build" "all" "compile")

    for target in "${targets[@]}"; do
        if grep -q "^${target}:" "$makefile" || grep -q "^\.PHONY:.*${target}" "$makefile"; then
            log "Found Makefile target: $target"
            log "Running: make $target"

            if [ $VERBOSE -eq 1 ]; then
                make "$target"
            else
                make "$target" >/dev/null 2>&1
            fi

            local exit_code=$?
            if [ $exit_code -eq 0 ]; then
                log "make $target succeeded"
                return 0
            else
                log_error "make $target failed with exit code $exit_code"
                return 1
            fi
        fi
    done

    log_warn "No known build targets found in Makefile"
    return 2
}

# Function to test with go build
test_go_build() {
    if [ -z "$GO_MODULE" ]; then
        log_warn "No go.mod found, skipping go build test"
        return 2
    fi

    log "Running: go build ./..."

    local output
    local exit_code

    if [ $VERBOSE -eq 1 ]; then
        go build ./...
        exit_code=$?
    else
        output=$(go build ./... 2>&1)
        exit_code=$?
    fi

    if [ $exit_code -eq 0 ]; then
        log "go build ./... succeeded"
        return 0
    else
        log_error "go build ./... failed"
        if [ $VERBOSE -eq 0 ]; then
            echo "$output" >&2
        fi
        return 1
    fi
}

# Function to test with go test (compile only, no run)
test_go_test_compile() {
    if [ -z "$GO_MODULE" ]; then
        log_warn "No go.mod found, skipping go test compilation"
        return 2
    fi

    log "Running: go test -c ./..."

    local output
    local exit_code

    if [ $VERBOSE -eq 1 ]; then
        go test -c ./... >/dev/null
        exit_code=$?
    else
        output=$(go test -c ./... 2>&1)
        exit_code=$?
    fi

    # Clean up test binaries
    find . -name "*.test" -type f -delete 2>/dev/null || true

    if [ $exit_code -eq 0 ]; then
        log "go test -c ./... succeeded"
        return 0
    else
        log_error "go test -c ./... failed"
        if [ $VERBOSE -eq 0 ]; then
            echo "$output" >&2
        fi
        return 1
    fi
}

# Function to verify dependencies
verify_dependencies() {
    if [ -z "$GO_MODULE" ]; then
        return 0
    fi

    log "Verifying go.mod and go.sum..."

    local output
    local exit_code

    if [ $VERBOSE -eq 1 ]; then
        go mod verify
        exit_code=$?
    else
        output=$(go mod verify 2>&1)
        exit_code=$?
    fi

    if [ $exit_code -eq 0 ]; then
        log "go mod verify succeeded"
        return 0
    else
        log_warn "go mod verify failed"
        if [ $VERBOSE -eq 0 ]; then
            echo "$output" >&2
        fi
        return 1
    fi
}

# Main compilation test logic
main() {
    local compilation_success=0

    # Step 1: Verify dependencies (if not quick mode)
    if [ $QUICK -eq 0 ]; then
        verify_dependencies || log_warn "Dependency verification failed, continuing anyway"
    fi

    # Step 2: Try Makefile first (if exists)
    if [ -f "Makefile" ]; then
        log "Found Makefile"
        if test_makefile "Makefile"; then
            compilation_success=1
            log "Compilation via Makefile succeeded"
        fi
    fi

    # Step 3: If Makefile didn't work or doesn't exist, try go build
    if [ $compilation_success -eq 0 ] && [ -n "$GO_MODULE" ]; then
        log "Trying go build..."
        if test_go_build; then
            compilation_success=1
            log "Compilation via go build succeeded"
        fi
    fi

    # Step 4: If still no success and not quick mode, try test compilation
    if [ $compilation_success -eq 0 ] && [ $QUICK -eq 0 ] && [ -n "$GO_MODULE" ]; then
        log "Trying go test compilation..."
        if test_go_test_compile; then
            compilation_success=1
            log "Test compilation succeeded"
        fi
    fi

    # Final result
    if [ $compilation_success -eq 1 ]; then
        echo -e "${GREEN}✓${NC} Compilation successful"
        return 0
    else
        log_error "All compilation methods failed"
        echo -e "${RED}✗${NC} Compilation failed"

        # If we couldn't detect a build system at all
        if [ ! -f "Makefile" ] && [ -z "$GO_MODULE" ]; then
            log_error "No build system detected (no Makefile or go.mod)"
            return 2
        fi

        return 1
    fi
}

# Run main function
main
exit $?
