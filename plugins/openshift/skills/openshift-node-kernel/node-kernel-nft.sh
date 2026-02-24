#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/kernel-helper.sh"

# Parse arguments
NODE=""
IMAGE=""
COMMAND=""
FAMILY=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --command)
      COMMAND="$2"
      shift 2
      ;;
    --family)
      FAMILY="$2"
      shift 2
      ;;
    *)
      if [ -z "$NODE" ]; then
        NODE="$1"
      elif [ -z "$IMAGE" ]; then
        IMAGE="$1"
      else
        echo "Error: Unexpected argument: $1" >&2
        exit 1
      fi
      shift
      ;;
  esac
done

# Validate required parameters
if [ -z "$NODE" ] || [ -z "$IMAGE" ] || [ -z "$COMMAND" ]; then
  echo "Error: node, image, and command are required" >&2
  echo "Usage: node-kernel-nft.sh <node> <image> --command <cmd> [--family <family>]" >&2
  exit 1
fi

# Check if nft utility exists
if ! check_utility_exists "$NODE" "$IMAGE" "nft"; then
  echo "Error: nft utility not found in image" >&2
  exit 1
fi

# Build command arguments
CMD_ARGS=""
if [ -n "$FAMILY" ]; then
  CMD_ARGS="$FAMILY"
fi
CMD_ARGS="$CMD_ARGS $COMMAND"

# Execute nft command
execute_kernel_command "$NODE" "$IMAGE" nft $CMD_ARGS
