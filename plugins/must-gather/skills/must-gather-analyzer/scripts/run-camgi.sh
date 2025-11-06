#!/bin/bash
# run-camgi.sh
#
# Runs okd-camgi (Cluster Autoscaler Must-Gather Inspector) with web browser UI
# camgi is a tool for examining must-gather records to investigate cluster autoscaler behavior
#
# Usage: ./run-camgi.sh <must-gather-path>
#
# Prerequisites:
#   - Python 3 and pip
#   - okd-camgi installed (pip3 install okd-camgi --user)
#   OR
#   - Podman/Docker (to run containerized version)

set -uo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to stop camgi containers
stop_camgi() {
    echo -e "${BLUE}Stopping camgi containers...${NC}"

    local stopped=0

    # Check for podman
    if command_exists podman; then
        local containers=$(podman ps -q --filter ancestor=quay.io/elmiko/okd-camgi)
        if [ -n "$containers" ]; then
            echo -e "${YELLOW}Found running camgi container(s)${NC}"
            echo "$containers" | while read container; do
                echo -e "${BLUE}Stopping container: $container${NC}"
                podman stop "$container"
                stopped=$((stopped + 1))
            done
            echo -e "${GREEN}Stopped $stopped camgi container(s)${NC}"
        else
            echo -e "${YELLOW}No running camgi containers found${NC}"
        fi
    fi

    # Check for docker
    if command_exists docker; then
        local containers=$(docker ps -q --filter ancestor=quay.io/elmiko/okd-camgi)
        if [ -n "$containers" ]; then
            echo -e "${YELLOW}Found running camgi container(s)${NC}"
            echo "$containers" | while read container; do
                echo -e "${BLUE}Stopping container: $container${NC}"
                docker stop "$container"
                stopped=$((stopped + 1))
            done
            echo -e "${GREEN}Stopped $stopped camgi container(s)${NC}"
        else
            echo -e "${YELLOW}No running camgi containers found${NC}"
        fi
    fi

    exit 0
}

# Parse arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <must-gather-path>"
    echo "       $0 stop|--stop"
    echo ""
    echo "Examples:"
    echo "  $0 /path/to/must-gather    # Start camgi"
    echo "  $0 stop                     # Stop running camgi containers"
    echo ""
    echo "This script runs okd-camgi to analyze cluster autoscaler behavior"
    echo "in your must-gather data via an interactive web browser interface."
    echo ""
    echo "Prerequisites:"
    echo "  Option 1 (Local): pip3 install okd-camgi --user"
    echo "  Option 2 (Container): podman or docker"
    exit 1
fi

# Check if user wants to stop camgi
if [ "$1" = "stop" ] || [ "$1" = "--stop" ]; then
    stop_camgi
fi

MG_PATH="$1"

# Validate must-gather path
if [ ! -d "$MG_PATH" ]; then
    echo -e "${RED}Error: Directory not found: $MG_PATH${NC}"
    exit 1
fi

# Check if we need to find the subdirectory with hash
ORIGINAL_PATH="$MG_PATH"
if [ ! -d "$MG_PATH/cluster-scoped-resources" ]; then
    echo -e "${YELLOW}Looking for must-gather subdirectory...${NC}"
    # Find subdirectory containing cluster-scoped-resources
    SUBDIR=$(find "$MG_PATH" -maxdepth 2 -type d -name "*sha256*" | head -n 1)
    if [ -n "$SUBDIR" ]; then
        echo -e "${GREEN}Found: $SUBDIR${NC}"
        MG_PATH="$SUBDIR"
    else
        echo -e "${YELLOW}Warning: Could not find standard must-gather structure${NC}"
        echo -e "${YELLOW}Attempting to run camgi anyway...${NC}"
    fi
fi

# Check and fix permissions if needed
echo -e "${BLUE}Checking file permissions...${NC}"
# Check for any files that don't have world-read permission
# Focus on common must-gather file locations that CAMGI needs to access
PERMISSION_ISSUES=0
if find "$MG_PATH" -type f ! -perm -004 2>/dev/null | head -n 1 | grep -q .; then
    PERMISSION_ISSUES=1
fi

if [ $PERMISSION_ISSUES -eq 1 ]; then
    echo -e "${YELLOW}Warning: Some files have restrictive permissions${NC}"
    echo -e "${YELLOW}CAMGI needs read access to all must-gather files${NC}"
    echo ""
    read -p "Fix permissions now? (Y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        echo -e "${BLUE}Fixing permissions...${NC}"
        chmod -R a+r "$MG_PATH" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Permissions updated successfully${NC}"
        else
            echo -e "${YELLOW}Note: Some permission updates may have failed${NC}"
            echo -e "${YELLOW}You may need to run: chmod -R a+r $MG_PATH${NC}"
        fi
    else
        echo -e "${YELLOW}Skipping permission fix. CAMGI may encounter errors.${NC}"
        echo -e "${YELLOW}To fix manually: chmod -R a+r $MG_PATH${NC}"
    fi
else
    echo -e "${GREEN}Permissions OK${NC}"
fi
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}OKD-CAMGI - Cluster Autoscaler Inspector${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Must-Gather Path: $MG_PATH"
echo ""

# Try to run camgi using available methods
run_camgi() {
    # Method 1: Check if okd-camgi is installed locally
    if command_exists okd-camgi; then
        echo -e "${GREEN}Found okd-camgi installed locally${NC}"
        echo -e "${BLUE}Starting camgi with web browser...${NC}"
        echo ""
        okd-camgi --webbrowser "$MG_PATH"
        return $?
    fi

    # Method 2: Try with python3 -m (in case it's installed but not in PATH)
    if command_exists python3; then
        if python3 -c "import okd_camgi" 2>/dev/null; then
            echo -e "${GREEN}Found okd-camgi Python module${NC}"
            echo -e "${BLUE}Starting camgi with web browser...${NC}"
            echo ""
            python3 -m okd_camgi --webbrowser "$MG_PATH"
            return $?
        fi
    fi

    # Method 3: Try containerized version
    if command_exists podman; then
        echo -e "${YELLOW}okd-camgi not found locally, using containerized version${NC}"
        echo -e "${BLUE}Starting camgi container on http://127.0.0.1:8080${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
        echo ""

        # Open browser in background
        (sleep 2 && xdg-open http://127.0.0.1:8080 2>/dev/null) &

        # Use :Z flag for SELinux relabeling (recommended by camgi documentation)
        podman run --rm -it -p 8080:8080 -v "$MG_PATH:/must-gather:Z" quay.io/elmiko/okd-camgi
        return $?
    fi

    if command_exists docker; then
        echo -e "${YELLOW}okd-camgi not found locally, using containerized version${NC}"
        echo -e "${BLUE}Starting camgi container on http://127.0.0.1:8080${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
        echo ""

        # Open browser in background
        (sleep 2 && xdg-open http://127.0.0.1:8080 2>/dev/null) &

        docker run --rm -it -p 8080:8080 -v "$MG_PATH:/must-gather" quay.io/elmiko/okd-camgi
        return $?
    fi

    # No method available
    echo -e "${RED}Error: okd-camgi is not installed and no container runtime found${NC}"
    echo ""
    echo "Please install okd-camgi using one of these methods:"
    echo ""
    echo "  Method 1 (Local installation - recommended):"
    echo -e "    ${GREEN}pip3 install okd-camgi --user${NC}"
    echo ""
    echo "  Method 2 (Container - requires podman/docker):"
    echo -e "    ${GREEN}podman run --rm -it -p 8080:8080 -v $MG_PATH:/must-gather:Z quay.io/elmiko/okd-camgi${NC}"
    echo ""
    echo "  For more information:"
    echo "    GitHub: https://github.com/elmiko/okd-camgi"
    echo "    README: $(dirname "$0")/README-CAMGI.md"
    return 1
}

# Run camgi
run_camgi
exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}CAMGI Session Ended${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}CAMGI encountered an error${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo -e "${YELLOW}Common fixes:${NC}"
    echo ""
    echo "  1. If you see Permission errors, fix must-gather permissions:"
    echo -e "     ${GREEN}chmod -R a+r \"$MG_PATH\"${NC}"
    echo ""
    echo "  2. For more details, see:"
    echo "     $(dirname "$0")/README-CAMGI.md"
fi

exit $exit_code
