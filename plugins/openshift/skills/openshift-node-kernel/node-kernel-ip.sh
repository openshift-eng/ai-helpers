#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/kernel-helper.sh"

# Parse arguments
NODE=""
IMAGE=""
COMMAND=""
OPTIONS=""
FILTER_PARAMS=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --command)
      COMMAND="$2"
      shift 2
      ;;
    --options)
      OPTIONS="$2"
      shift 2
      ;;
    --filter)
      FILTER_PARAMS="$2"
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
  echo "Usage: node-kernel-ip.sh <node> <image> --command <cmd> [--options <opts>] [--filter <params>]" >&2
  exit 1
fi

# Check if ip utility exists
if ! check_utility_exists "$NODE" "$IMAGE" "ip"; then
  echo "Error: ip utility not found in image" >&2
  exit 1
fi

# Execute ip command
# Note: Passing OPTIONS, COMMAND, and FILTER_PARAMS separately so they get split properly
execute_kernel_command "$NODE" "$IMAGE" ip $OPTIONS $COMMAND $FILTER_PARAMS
