#!/bin/bash
# detect-gateway-cluster.sh - Discover clusters with Gateway API CRDs installed
#
# Output format (to stdout):
#   index|kubeconfig|cluster_name|gateway_count|installed_crds
#
# Example output:
#   1|/home/user/.kube/config|prod-cluster|5|gateways,httproutes,gatewayclasses
#   2|/home/user/.kube/kind-config|dev-cluster|2|gateways,httproutes
#
# Diagnostics and human-readable info go to stderr
# Exit codes: 0=success, 1=no cluster found

echo "🔍 Detecting clusters with Gateway API..." >&2
echo "" >&2

# Array to store discovered clusters
# Format: "kubeconfig_path|context_name|cluster_display_name|gateway_count|installed_crds"
declare -a CLUSTERS=()

# Associative array to track seen kubeconfig+context combinations (for deduplication)
declare -A SEEN_CONTEXTS=()

# Gateway API CRDs to check
GATEWAY_CRDS=(
    "gateways.gateway.networking.k8s.io"
    "gatewayclasses.gateway.networking.k8s.io"
    "httproutes.gateway.networking.k8s.io"
    "grpcroutes.gateway.networking.k8s.io"
    "tcproutes.gateway.networking.k8s.io"
    "tlsroutes.gateway.networking.k8s.io"
    "referencegrants.gateway.networking.k8s.io"
)

# Function to test a specific kubeconfig and context for Gateway API
test_context_for_gateway_api() {
    local kc_file="$1"
    local context="$2"

    # Resolve to absolute path for deduplication
    local resolved_kc
    resolved_kc=$(readlink -f "$kc_file" 2>/dev/null || echo "$kc_file")

    # Create unique key for deduplication
    local unique_key="${resolved_kc}::${context}"

    # Skip if we've already seen this kubeconfig+context combination
    if [ -n "${SEEN_CONTEXTS[$unique_key]}" ]; then
        return 1
    fi

    # Check if Gateway API CRDs are installed
    local installed_crds=""
    local crd_count=0

    for crd in "${GATEWAY_CRDS[@]}"; do
        if KUBECONFIG="$kc_file" kubectl --kubeconfig="$kc_file" --context="$context" \
            get crd "$crd" &>/dev/null; then
            if [ -n "$installed_crds" ]; then
                installed_crds="${installed_crds},${crd%%.*}"
            else
                installed_crds="${crd%%.*}"
            fi
            crd_count=$((crd_count + 1))
        fi
    done

    # Must have at least the core Gateway CRD
    if [ $crd_count -eq 0 ]; then
        return 1
    fi

    # Mark this combination as seen
    SEEN_CONTEXTS[$unique_key]=1

    # Get cluster info
    local cluster_name
    cluster_name=$(KUBECONFIG="$kc_file" kubectl --kubeconfig="$kc_file" --context="$context" \
        config view --minify -o jsonpath='{.clusters[0].name}' 2>/dev/null || echo "$context")

    # Count actual Gateway resources
    local gateway_count
    gateway_count=$(KUBECONFIG="$kc_file" kubectl --kubeconfig="$kc_file" --context="$context" \
        get gateways.gateway.networking.k8s.io -A --no-headers 2>/dev/null | wc -l || echo "0")
    gateway_count=$(echo "$gateway_count" | tr -d '[:space:]')

    # Store cluster info
    CLUSTERS+=("$kc_file|$context|$cluster_name|$gateway_count|$installed_crds")
    return 0
}

# Function to scan all contexts in a kubeconfig file
scan_kubeconfig_file() {
    local kc_file="$1"
    local file_label="$2"

    if [ ! -f "$kc_file" ]; then
        echo "  ✗ File not found" >&2
        return 1
    fi

    echo "Scanning: $file_label" >&2

    # Get all contexts from this kubeconfig
    local contexts
    contexts=$(KUBECONFIG="$kc_file" kubectl --kubeconfig="$kc_file" config get-contexts -o name 2>/dev/null || true)

    if [ -z "$contexts" ]; then
        echo "  ✗ No contexts found" >&2
        return 1
    fi

    local found_count=0
    while IFS= read -r context; do
        if test_context_for_gateway_api "$kc_file" "$context"; then
            echo "  ✓ Found Gateway API in context: $context" >&2
            found_count=$((found_count + 1))
        fi
    done <<< "$contexts"

    if [ $found_count -eq 0 ]; then
        echo "  ✗ No Gateway API clusters found in any context" >&2
    fi

    echo "" >&2
}

# Phase 1: Discovery - scan all kubeconfig files and contexts

# Priority 1: Current KUBECONFIG environment (if set)
if [ -n "$KUBECONFIG" ]; then
    IFS=':' read -r -a kubeconfig_paths <<< "$KUBECONFIG"
    for kubeconfig_path in "${kubeconfig_paths[@]}"; do
        [ -z "$kubeconfig_path" ] && continue
        display_label="$kubeconfig_path"
        case "$kubeconfig_path" in
            ~*)
                kubeconfig_path="${kubeconfig_path/#\~/$HOME}"
                display_label="$kubeconfig_path"
                ;;
        esac
        scan_kubeconfig_file "$kubeconfig_path" "Current KUBECONFIG environment ($display_label)"
    done
fi

# Priority 2: ~/.kube/kind-config (common for KIND clusters)
if [ -f "$HOME/.kube/kind-config" ]; then
    scan_kubeconfig_file "$HOME/.kube/kind-config" "~/.kube/kind-config"
fi

# Priority 3: ~/.kube/config (default kubeconfig)
if [ -f "$HOME/.kube/config" ]; then
    scan_kubeconfig_file "$HOME/.kube/config" "~/.kube/config"
fi

# Phase 2: Output Results - non-interactive parseable format

if [ ${#CLUSTERS[@]} -eq 0 ]; then
    # No clusters found
    echo "❌ No clusters with Gateway API found" >&2
    echo "" >&2
    echo "Searched in:" >&2
    [ -n "$KUBECONFIG" ] && echo "  - Current KUBECONFIG environment ($KUBECONFIG)" >&2
    echo "  - ~/.kube/kind-config" >&2
    echo "  - ~/.kube/config" >&2
    echo "" >&2
    echo "Solutions:" >&2
    echo "  1. Install Gateway API CRDs:" >&2
    echo "     kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.0.0/standard-install.yaml" >&2
    echo "  2. Set KUBECONFIG to point to a cluster with Gateway API:" >&2
    echo "     export KUBECONFIG=/path/to/config" >&2
    echo "  3. Verify Gateway API is installed:" >&2
    echo "     kubectl get crd gateways.gateway.networking.k8s.io" >&2
    exit 1
fi

# Output cluster list to stdout in parseable format
# Format: index|kubeconfig|cluster_name|gateway_count|installed_crds
echo "✅ Found ${#CLUSTERS[@]} cluster(s) with Gateway API" >&2
echo "" >&2

idx=1
for cluster_info in "${CLUSTERS[@]}"; do
    # Parse cluster info
    IFS='|' read -r kc_file context cluster_name gateway_count installed_crds <<< "$cluster_info"

    # Output parseable line to stdout
    echo "$idx|$kc_file|$cluster_name|$gateway_count|$installed_crds"

    # Output human-readable info to stderr
    echo "  $idx. $cluster_name" >&2
    echo "     Context: $context" >&2
    echo "     Gateways: $gateway_count" >&2
    echo "     CRDs: $installed_crds" >&2
    echo "     Kubeconfig: $kc_file" >&2
    echo "" >&2

    idx=$((idx + 1))
done

exit 0
