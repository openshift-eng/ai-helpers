#!/bin/bash

# kernel-helper.sh
# Helper functions for OVN kernel debugging commands

set -euo pipefail

# Check if a utility exists in the debug image
# Args:
#   $1: node name
#   $2: image name
#   $3: utility name (e.g., "conntrack", "iptables", "nft", "ip")
# Returns:
#   0 if utility exists, 1 otherwise
check_utility_exists() {
  local node="$1"
  local image="$2"
  local utility="$3"

  # Try to execute 'which <utility>' in the debug container
  local output
  output=$(oc debug node/"${node}" \
    --image="${image}" \
    -- chroot /host which "${utility}" 2>&1 || true)

  if echo "${output}" | grep -q "^/"; then
    return 0
  else
    return 1
  fi
}

# Execute a command on a node via oc debug
# Args:
#   $1: node name
#   $2: image name
#   $3+: command and arguments to execute
# Returns:
#   Command output on stdout
execute_kernel_command() {
  local node="$1"
  local image="$2"
  shift 2

  # Build command array, splitting any arguments that contain spaces
  local cmd_array=()
  for arg in "$@"; do
    # If argument contains spaces, split it into separate arguments
    if [[ "$arg" =~ [[:space:]] ]]; then
      # Use read to split on whitespace
      read -ra words <<< "$arg"
      cmd_array+=("${words[@]}")
    else
      cmd_array+=("$arg")
    fi
  done

  # Create debug pod and execute command
  # Explicitly capture all output, filter warnings, and output to stdout
  local raw_output
  raw_output=$(oc debug node/"${node}" \
    --image="${image}" \
    -- chroot /host "${cmd_array[@]}" 2>&1)

  # Filter warnings and explicitly output the result
  printf '%s\n' "$raw_output" | filter_warnings
}

# Filter out common oc debug warnings
# Args:
#   stdin: input to filter
# Returns:
#   Filtered output on stdout
filter_warnings() {
  # Remove common warning lines that aren't relevant to output
  # Use grep -E with multiple patterns for efficiency and reliability
  # The || cat ensures output passes through even if grep finds no matches
  grep -Ev "^(Creating debugging pod|Waiting for pod to be running|Removing debug pod|If you don't see a command prompt|pod.*deleted|Starting pod/|Defaulting debug container name)" || cat
}

# Validate node name exists in cluster
# Args:
#   $1: node name
# Returns:
#   0 if node exists, 1 otherwise
validate_node_exists() {
  local node="$1"

  if ! oc get node "${node}" &>/dev/null; then
    echo "Error: Node '${node}' not found in cluster" >&2
    echo "Available nodes:" >&2
    oc get nodes -o name | sed 's|node/||' >&2
    return 1
  fi
  return 0
}

# Parse key-value arguments
# Args:
#   $@: arguments to parse
# Sets:
#   Global variables based on parsed arguments
parse_kv_args() {
  while [[ $# -gt 0 ]]; do
    case $1 in
      --*)
        local key="${1#--}"
        local value="${2:-}"
        if [[ -z "${value}" ]] || [[ "${value}" == --* ]]; then
          echo "Error: Missing value for --${key}" >&2
          return 1
        fi
        # Convert key to uppercase and replace - with _
        local var_name
        var_name=$(echo "${key}" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
        declare -g "${var_name}=${value}"
        shift 2
        ;;
      *)
        shift
        ;;
    esac
  done
}

# Build command array with conditional arguments
# Example:
#   cmd=$(build_cmd "nft" "list tables" "${FAMILY:+$FAMILY}")
build_cmd() {
  local -a cmd_array=()
  for arg in "$@"; do
    [[ -n "${arg}" ]] && cmd_array+=("${arg}")
  done
  echo "${cmd_array[@]}"
}

# Format output for better readability
# Args:
#   stdin: input to format
# Returns:
#   Formatted output on stdout
format_output() {
  # Remove empty lines and trim whitespace
  sed '/^[[:space:]]*$/d' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

# Detect and configure kubeconfig for OVN-Kubernetes cluster
# Uses detect-cluster.sh to find available clusters
# Sets KUBECONFIG environment variable
detect_and_set_kubeconfig() {
  # If KUBECONFIG is already set and kubectl works, use it
  if [ -n "${KUBECONFIG:-}" ] && kubectl cluster-info &>/dev/null; then
    echo "Using existing KUBECONFIG from environment" >&2

    # Try to detect OVN namespace from current cluster
    if kubectl get pods -n openshift-ovn-kubernetes --no-headers 2>/dev/null | head -1 | grep -q .; then
      export OVN_NAMESPACE="openshift-ovn-kubernetes"
      echo "Detected OVN namespace: openshift-ovn-kubernetes" >&2
    elif kubectl get pods -n ovn-kubernetes --no-headers 2>/dev/null | head -1 | grep -q .; then
      export OVN_NAMESPACE="ovn-kubernetes"
      echo "Detected OVN namespace: ovn-kubernetes" >&2
    fi

    return 0
  fi

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local detect_script="${script_dir}/../generating-ovn-topology/scripts/detect-cluster.sh"

  # Check if detect-cluster.sh exists
  if [ ! -f "${detect_script}" ]; then
    echo "Warning: detect-cluster.sh not found at ${detect_script}" >&2
    return 0  # Don't fail, just continue with current KUBECONFIG
  fi

  # Run detect-cluster.sh and capture output
  # Script outputs to stderr (diagnostics) and stdout (parseable results)
  local cluster_info
  cluster_info=$(bash "${detect_script}" 2>/dev/null | head -1)

  # Check if any cluster was found
  if [ -z "${cluster_info}" ]; then
    # If KUBECONFIG is already set, continue with it
    if [ -n "${KUBECONFIG:-}" ]; then
      echo "Note: Using existing KUBECONFIG: ${KUBECONFIG}" >&2
      return 0
    fi

    # No cluster found and no KUBECONFIG set
    echo "Error: No OVN-Kubernetes cluster found." >&2
    echo "Please set KUBECONFIG or start an OVN-Kubernetes cluster." >&2
    echo "Searched locations:" >&2
    echo "  - Current KUBECONFIG environment" >&2
    echo "  - ~/.kube/kind-config" >&2
    echo "  - ~/ovn.conf" >&2
    echo "  - ~/.kube/config" >&2
    return 1
  fi

  # Parse cluster info: index|kubeconfig|cluster_name|node_count|namespace
  IFS='|' read -r _ kubeconfig_path cluster_name _ ovn_namespace <<< "${cluster_info}"

  # Export KUBECONFIG
  export KUBECONFIG="${kubeconfig_path}"
  export OVN_NAMESPACE="${ovn_namespace}"

  echo "Detected OVN-Kubernetes cluster: ${cluster_name}" >&2
  echo "Using kubeconfig: ${kubeconfig_path}" >&2
  echo "OVN namespace: ${ovn_namespace}" >&2
  echo "" >&2

  return 0
}

# Check if oc is available and configured
check_oc_available() {
  if ! command -v oc &>/dev/null; then
    echo "Error: oc command not found. Please install OpenShift CLI (oc)." >&2
    return 1
  fi

  # Detect and set kubeconfig if not already configured
  if ! detect_and_set_kubeconfig; then
    return 1
  fi

  if ! oc cluster-info &>/dev/null; then
    echo "Error: Unable to connect to OpenShift cluster. Please check your configuration." >&2
    return 1
  fi
  return 0
}

# Print usage for a command
# Args:
#   $1: command name
#   $2: usage syntax
print_usage() {
  local cmd_name="$1"
  local usage_syntax="$2"

  cat >&2 <<EOF
Usage: ${cmd_name} ${usage_syntax}

For more information, see the command documentation.
EOF
}

# Validate that required parameters are set
# Args:
#   $@: list of parameter names to check
# Returns:
#   0 if all parameters are set, 1 otherwise
validate_required_params() {
  local missing=()
  for param in "$@"; do
    if [[ -z "${!param:-}" ]]; then
      missing+=("${param}")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Error: Missing required parameters: ${missing[*]}" >&2
    return 1
  fi
  return 0
}

# Execute command with timeout
# Args:
#   $1: timeout in seconds
#   $2+: command to execute
execute_with_timeout() {
  local timeout="$1"
  shift

  timeout "${timeout}s" "$@"
}

# Export functions for use in sourcing scripts
export -f check_utility_exists
export -f execute_kernel_command
export -f filter_warnings
export -f validate_node_exists
export -f parse_kv_args
export -f build_cmd
export -f format_output
export -f detect_and_set_kubeconfig
export -f check_oc_available
export -f print_usage
export -f validate_required_params
export -f execute_with_timeout
