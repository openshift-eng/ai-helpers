#!/bin/bash

set -euo pipefail

setup_kubeconfig() {
  local kubeconfig_path="${1/#~/$HOME}"

  if [ ! -f "${kubeconfig_path}" ]; then
    echo "ERROR: KUBECONFIG file not found: ${kubeconfig_path}" >&2
    return 1
  fi

  export KUBECONFIG="${kubeconfig_path}"
  return 0
}

validate_cluster_connectivity() {
  local required="${1:-true}"

  if [ -z "${KUBECONFIG:-}" ]; then
    echo "ERROR: KUBECONFIG not set" >&2
    return 1
  fi

  if ! command -v oc &>/dev/null; then
    echo "ERROR: 'oc' command not found. Please install OpenShift CLI" >&2
    return 1
  fi

  echo "Validating cluster connectivity..." >&2

  if ! oc version --request-timeout=5s &>/dev/null; then
    if [ "${required}" == "true" ]; then
      echo "" >&2
      echo "ERROR: Cluster unreachable or unavailable" >&2
      echo "  KUBECONFIG: ${KUBECONFIG}" >&2
      echo "" >&2
      echo "Possible causes:" >&2
      echo "  - Cluster is down or network is unreachable" >&2
      echo "  - Invalid or expired credentials in kubeconfig" >&2
      echo "  - Firewall blocking connection to cluster API" >&2
      echo "" >&2
      echo "Troubleshooting:" >&2
      echo "  1. Verify cluster status: oc cluster-info" >&2
      echo "  2. Check kubeconfig: cat ${KUBECONFIG}" >&2
      echo "  3. Test connectivity: curl -k \$(oc whoami --show-server)" >&2
      return 1
    else
      echo "  ⚠ Cluster unreachable - running in offline mode" >&2
      return 2
    fi
  fi

  echo "  ✓ Cluster accessible" >&2
  return 0
}

locate_tool_script() {
  local script_name="$1"

  # Prefer installed plugin location
  local script_path=$(find ~/.claude/plugins -type f -path "*/dra-ocp-validator/tools/${script_name}" 2>/dev/null | sort | head -1)

  if [ -z "${script_path}" ] && [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
    script_path="${CLAUDE_PLUGIN_ROOT}/tools/${script_name}"
  fi

  if [ ! -f "${script_path}" ]; then
    echo "ERROR: ${script_name} not found. Plugin may not be installed correctly." >&2
    return 1
  fi

  echo "${script_path}"
}

setup_test_logging() {
  local feature_name="$1"
  local log_dir="./dra-${feature_name}-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "${log_dir}"

  echo "Test Date: $(date)"
  echo "Logs Directory: ${log_dir}"

  exec > >(tee -a "${log_dir}/test-output.log")
  exec 2>&1

  echo "${log_dir}"
}

get_script_dir() {
  cd "$(dirname "${BASH_SOURCE[1]}")" && pwd
}

get_tools_dir() {
  local script_dir="$1"
  dirname "${script_dir}"
}
