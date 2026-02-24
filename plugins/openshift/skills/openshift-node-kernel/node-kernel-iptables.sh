#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/kernel-helper.sh"

# Parse arguments
NODE=""
IMAGE=""
COMMAND=""
TABLE=""
FILTER_PARAMS=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --command)
      COMMAND="$2"
      shift 2
      ;;
    --table)
      TABLE="$2"
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
  echo "Usage: node-kernel-iptables.sh <node> <image> --command <cmd> [--table <table>] [--filter <params>]" >&2
  exit 1
fi

# Determine which command to use (iptables or ip6tables based on filter params)
IPTABLES_CMD="iptables"
if [[ "$FILTER_PARAMS" =~ (-6|--ipv6) ]]; then
  IPTABLES_CMD="ip6tables"
fi

# Check if iptables utility exists
if ! check_utility_exists "$NODE" "$IMAGE" "$IPTABLES_CMD"; then
  echo "Error: $IPTABLES_CMD utility not found in image" >&2
  exit 1
fi

# Build command arguments
CMD_ARGS=""
if [ -n "$TABLE" ]; then
  CMD_ARGS="-t $TABLE"
fi
CMD_ARGS="$CMD_ARGS $COMMAND $FILTER_PARAMS"

# Execute iptables command
execute_kernel_command "$NODE" "$IMAGE" $IPTABLES_CMD $CMD_ARGS
