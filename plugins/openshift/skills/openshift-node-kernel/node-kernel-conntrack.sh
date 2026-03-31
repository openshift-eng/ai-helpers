#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/kernel-helper.sh"

# Parse arguments
NODE=""
IMAGE=""
COMMAND=""
FILTER_PARAMS=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --command)
      COMMAND="$2"
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
if [ -z "$NODE" ] || [ -z "$IMAGE" ]; then
  echo "Error: node and image are required" >&2
  echo "Usage: node-kernel-conntrack.sh <node> <image> [--command <cmd>] [--filter <params>]" >&2
  exit 1
fi

# Check if conntrack utility exists, if not fall back to reading /proc
CONNTRACK_CMD=""
if check_utility_exists "$NODE" "$IMAGE" "conntrack"; then
  CONNTRACK_CMD="conntrack"
  # Build command arguments
  CMD_ARGS=""
  if [ -n "$COMMAND" ]; then
    CMD_ARGS="$COMMAND"
  else
    CMD_ARGS="-L"  # Default to list
  fi
  CMD_ARGS="$CMD_ARGS $FILTER_PARAMS"

  # Execute conntrack command
  execute_kernel_command "$NODE" "$IMAGE" "$CONNTRACK_CMD" "$CMD_ARGS"
else
  # Fall back to reading /proc/net/nf_conntrack
  echo "Warning: conntrack utility not found, reading /proc/net/nf_conntrack" >&2

  # Build filter command if filter params provided
  FILTER_CMD="cat /proc/net/nf_conntrack"
  if [ -n "$FILTER_PARAMS" ]; then
    # Simple grep-based filtering for common params
    FILTER_CMD="cat /proc/net/nf_conntrack | grep -E \"$FILTER_PARAMS\""
  fi

  execute_kernel_command "$NODE" "$IMAGE" bash -c "$FILTER_CMD"
fi
