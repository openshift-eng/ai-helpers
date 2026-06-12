#!/usr/bin/env bash
# Feature Metadata Helper
# Provides functions to query DRA feature metadata from dra-features.yaml

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(dirname "${SCRIPT_DIR}")"
METADATA_FILE="${PLUGIN_ROOT}/dra-features.yaml"

# Check if yq is available (required for YAML parsing)
if ! command -v yq &> /dev/null; then
    echo "ERROR: yq is required but not installed" >&2
    echo "Install with: brew install yq (macOS) or dnf install yq (RHEL/Fedora)" >&2
    exit 1
fi

# Get feature name (human-readable)
get_feature_name() {
    local feature_key="$1"
    yq eval ".features.${feature_key}.name" "${METADATA_FILE}"
}

# Get minimum K8s version for a feature
get_min_k8s_version() {
    local feature_key="$1"
    yq eval ".features.${feature_key}.kubernetes.introduced" "${METADATA_FILE}"
}

# Get feature gate name
get_feature_gate() {
    local feature_key="$1"
    yq eval ".features.${feature_key}.feature_gate.name" "${METADATA_FILE}"
}

# Get graduation level of a feature for given K8s version
get_feature_graduation() {
    local feature_key="$1"
    local k8s_version="$2"  # e.g., "1.34"

    # Check if version is in GA range
    local ga_version
    ga_version=$(yq eval ".features.${feature_key}.kubernetes.ga" "${METADATA_FILE}" 2>/dev/null || echo "null")

    if [ "${ga_version}" != "null" ]; then
        local ga_minor
        ga_minor=$(echo "${ga_version}" | sed -E 's/1\.([0-9]+)/\1/')
        local current_minor
        current_minor=$(echo "${k8s_version}" | sed -E 's/1\.([0-9]+)/\1/')

        if [ "${current_minor}" -ge "${ga_minor}" ]; then
            echo "ga"
            return 0
        fi
    fi

    # Check if version is in Beta list
    local beta_count
    beta_count=$(yq eval ".features.${feature_key}.kubernetes.beta[]? | select(. == \"${k8s_version}\")" "${METADATA_FILE}" 2>/dev/null | wc -l)

    if [ "${beta_count}" -gt 0 ]; then
        echo "beta"
        return 0
    fi

    # Check if version is in Alpha list
    local alpha_count
    alpha_count=$(yq eval ".features.${feature_key}.kubernetes.alpha[]? | select(. == \"${k8s_version}\")" "${METADATA_FILE}" 2>/dev/null | wc -l)

    if [ "${alpha_count}" -gt 0 ]; then
        echo "alpha"
        return 0
    fi

    # Not available in this version
    echo "unavailable"
    return 1
}

# Check if feature gate is required for given K8s version
# Logic:
#   - Alpha: Feature gate REQUIRED (not enabled by default)
#   - Beta: Feature gate OPTIONAL (enabled by default in K8s, may need explicit enable in OCP)
#   - GA: Feature gate NOT required (always enabled, can't be disabled)
is_feature_gate_required() {
    local feature_key="$1"
    local k8s_version="$2"  # e.g., "1.34"

    local gate_name
    gate_name=$(get_feature_gate "${feature_key}")

    # If no feature gate defined, not required
    if [ "${gate_name}" == "null" ] || [ -z "${gate_name}" ]; then
        return 1
    fi

    # Determine graduation level
    local graduation
    graduation=$(get_feature_graduation "${feature_key}" "${k8s_version}")

    case "${graduation}" in
        alpha)
            # Alpha features ALWAYS require explicit enablement
            return 0
            ;;
        beta)
            # Beta features are enabled by default in K8s, but OCP may require CustomNoUpgrade
            # Return true to indicate it needs to be checked/enabled in OCP
            return 0
            ;;
        ga)
            # GA features are always enabled, gate not required
            return 1
            ;;
        unavailable)
            # Feature not available, gate not applicable
            return 1
            ;;
    esac
}

# Get setup flags for a feature
get_setup_flags() {
    local feature_key="$1"
    yq eval ".features.${feature_key}.setup.flags[]?" "${METADATA_FILE}" 2>/dev/null || echo ""
}

# Get test script path
get_test_script() {
    local feature_key="$1"
    local script_path
    script_path=$(yq eval ".features.${feature_key}.test.script" "${METADATA_FILE}")
    echo "${PLUGIN_ROOT}/${script_path}"
}

# Get cleanup pattern for a feature
get_cleanup_pattern() {
    local feature_key="$1"
    yq eval ".features.${feature_key}.test.cleanup_pattern" "${METADATA_FILE}"
}

# Get all cleanup patterns (for cleanup script)
get_all_cleanup_patterns() {
    yq eval ".cleanup.test_namespace_patterns[]" "${METADATA_FILE}"
}

# Get driver namespaces (should not be cleaned)
get_driver_namespaces() {
    yq eval ".cleanup.driver_namespaces[]" "${METADATA_FILE}"
}

# Get prerequisites for a feature
get_prerequisites() {
    local feature_key="$1"
    yq eval ".features.${feature_key}.prerequisites[]" "${METADATA_FILE}" -o json 2>/dev/null || echo "[]"
}

# Check if a feature is available for given K8s version
is_feature_available() {
    local feature_key="$1"
    local k8s_minor="$2"  # e.g., 34

    local min_version
    min_version=$(get_min_k8s_version "${feature_key}")

    if [ "${min_version}" == "null" ]; then
        return 1
    fi

    # Extract minor version from introduced version
    local min_minor
    min_minor=$(echo "${min_version}" | sed -E 's/1\.([0-9]+)/\1/')

    if [ "${k8s_minor}" -ge "${min_minor}" ]; then
        return 0
    else
        return 1
    fi
}

# Get driver configuration for a feature
get_driver_config() {
    local feature_key="$1"
    local driver_type="$2"  # nvidia or example

    yq eval ".features.${feature_key}.setup.driver_config.${driver_type}" "${METADATA_FILE}" -o json 2>/dev/null || echo "{}"
}

# List all features
list_all_features() {
    yq eval '.features | keys | .[]' "${METADATA_FILE}"
}

# Get feature description
get_feature_description() {
    local feature_key="$1"
    yq eval ".features.${feature_key}.description" "${METADATA_FILE}"
}

# Get check method implementation
get_check_method() {
    local method_name="$1"
    yq eval ".check_methods.${method_name}.implementation" "${METADATA_FILE}"
}

# Check if feature gate is currently enabled in the cluster
is_featuregate_currently_enabled() {
    local gate_name="$1"

    # Check CustomNoUpgrade first (OCP-specific granular control)
    local enabled
    enabled=$(oc get featuregate cluster -o json 2>/dev/null | \
        jq -r --arg fg "${gate_name}" '.spec.customNoUpgrade.enabled[]? | select(. == $fg)' || true)

    if [ -n "${enabled}" ]; then
        return 0
    fi

    # Check default FeatureSet
    enabled=$(oc get featuregate cluster -o json 2>/dev/null | \
        jq -r --arg fg "${gate_name}" '.status.featureGates[].enabled[]? | select(.name == $fg).name' || true)

    if [ -n "${enabled}" ]; then
        return 0
    fi

    return 1
}

# Get enablement command for a feature
get_enablement_command() {
    local feature_key="$1"
    # Try .command first (newer format)
    local cmd
    cmd=$(yq eval ".features.${feature_key}.feature_gate.enablement.command" "${METADATA_FILE}" 2>/dev/null)
    if [ "${cmd}" != "null" ] && [ -n "${cmd}" ]; then
        echo "${cmd}"
        return 0
    fi

    # Try .openshift (older format)
    cmd=$(yq eval ".features.${feature_key}.feature_gate.enablement.openshift" "${METADATA_FILE}" 2>/dev/null)
    if [ "${cmd}" != "null" ] && [ -n "${cmd}" ]; then
        echo "${cmd}"
        return 0
    fi

    echo "null"
    return 1
}

# Check and report feature gate status
check_feature_gate_status() {
    local feature_key="$1"
    local k8s_version="$2"  # e.g., "1.34"

    local gate_name
    gate_name=$(get_feature_gate "${feature_key}")

    if [ "${gate_name}" == "null" ] || [ -z "${gate_name}" ]; then
        echo "no_gate_required"
        return 0
    fi

    # Determine if gate is required based on graduation
    local graduation
    graduation=$(get_feature_graduation "${feature_key}" "${k8s_version}")

    case "${graduation}" in
        ga)
            echo "ga_always_enabled"
            return 0
            ;;
        alpha|beta)
            # Check if currently enabled
            if is_featuregate_currently_enabled "${gate_name}"; then
                echo "enabled"
                return 0
            else
                echo "not_enabled:${graduation}"
                return 1
            fi
            ;;
        unavailable)
            echo "feature_unavailable"
            return 1
            ;;
    esac
}

# Display feature info (for debugging/documentation)
show_feature_info() {
    local feature_key="$1"

    echo "Feature: ${feature_key}"
    echo "  Name: $(get_feature_name "${feature_key}")"
    echo "  Description: $(get_feature_description "${feature_key}")"
    echo "  Min K8s: $(get_min_k8s_version "${feature_key}")"

    local gate
    gate=$(get_feature_gate "${feature_key}")
    if [ "${gate}" != "null" ] && [ -n "${gate}" ]; then
        echo "  Feature Gate: ${gate}"
    fi

    local flags
    flags=$(get_setup_flags "${feature_key}")
    if [ -n "${flags}" ]; then
        echo "  Setup Flags: ${flags}"
    fi

    echo "  Test Script: $(get_test_script "${feature_key}")"
    echo "  Cleanup Pattern: $(get_cleanup_pattern "${feature_key}")"
}

# Export functions if sourced
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    # Script is being executed directly
    case "${1:-}" in
        list)
            list_all_features
            ;;
        info)
            if [ -z "${2:-}" ]; then
                echo "Usage: $0 info <feature-key>"
                exit 1
            fi
            show_feature_info "$2"
            ;;
        check-available)
            if [ -z "${2:-}" ] || [ -z "${3:-}" ]; then
                echo "Usage: $0 check-available <feature-key> <k8s-minor-version>"
                exit 1
            fi
            if is_feature_available "$2" "$3"; then
                echo "✓ Feature $2 is available on K8s 1.$3"
                exit 0
            else
                echo "✗ Feature $2 is NOT available on K8s 1.$3"
                exit 1
            fi
            ;;
        *)
            echo "DRA Feature Metadata Helper"
            echo ""
            echo "Usage:"
            echo "  $0 list                                    # List all features"
            echo "  $0 info <feature-key>                      # Show feature info"
            echo "  $0 check-available <feature-key> <k8s-minor>  # Check if feature is available"
            echo ""
            echo "Or source this script to use functions:"
            echo "  source $0"
            echo "  get_feature_name partitionable"
            exit 1
            ;;
    esac
fi
