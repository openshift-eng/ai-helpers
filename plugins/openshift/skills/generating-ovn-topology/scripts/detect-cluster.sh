#!/bin/bash
# detect-cluster.sh - Discover OVN-Kubernetes clusters across all kubeconfig files and contexts
#
# Output format (to stdout):
#   index|kubeconfig|cluster_name|node_count|namespace
#
# Example output:
#   1|/home/user/.kube/kind-config|kind-ovn|3|ovn-kubernetes
#   2|/home/user/.kube/config|openshift-cluster|6|openshift-ovn-kubernetes
#
# Diagnostics and human-readable info go to stderr
# Exit codes: 0=success, 1=no cluster found

echo "🔍 Detecting OVN-Kubernetes clusters..." >&2
echo "" >&2

# Array to store discovered clusters
# Format: "kubeconfig_path|context_name|cluster_display_name|node_count|namespace"
declare -a CLUSTERS=()

# Associative array to track seen kubeconfig+context combinations (for deduplication)
declare -A SEEN_CONTEXTS=()

# Function to test a specific kubeconfig and context for OVN pods
test_context_for_ovn() {
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

    # Try both namespace types: upstream Kubernetes and OpenShift
    local ovn_pods
    local ovn_namespace=""

    # Try openshift-ovn-kubernetes first (OpenShift)
    ovn_pods=$(KUBECONFIG="$kc_file" kubectl --kubeconfig="$kc_file" --context="$context" get pods -n openshift-ovn-kubernetes -o name 2>/dev/null | head -3)
    if [ -n "$ovn_pods" ]; then
        ovn_namespace="openshift-ovn-kubernetes"
    else
        # Try ovn-kubernetes (upstream Kubernetes)
        ovn_pods=$(KUBECONFIG="$kc_file" kubectl --kubeconfig="$kc_file" --context="$context" get pods -n ovn-kubernetes -o name 2>/dev/null | head -3)
        if [ -n "$ovn_pods" ]; then
            ovn_namespace="ovn-kubernetes"
        fi
    fi

    if [ -n "$ovn_namespace" ]; then
        # Mark this combination as seen
        SEEN_CONTEXTS[$unique_key]=1

        # Get cluster info
        local cluster_name
        cluster_name=$(KUBECONFIG="$kc_file" kubectl --kubeconfig="$kc_file" --context="$context" config view --minify -o jsonpath='{.clusters[0].name}' 2>/dev/null || echo "$context")

        local node_count
        node_count=$(KUBECONFIG="$kc_file" kubectl --kubeconfig="$kc_file" --context="$context" get nodes --no-headers 2>/dev/null | wc -l)

        # Store cluster info including namespace
        CLUSTERS+=("$kc_file|$context|$cluster_name|$node_count|$ovn_namespace")
        return 0
    fi
    return 1
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
        if test_context_for_ovn "$kc_file" "$context"; then
            echo "  ✓ Found OVN cluster in context: $context" >&2
            found_count=$((found_count + 1))
        fi
    done <<< "$contexts"

    if [ $found_count -eq 0 ]; then
        echo "  ✗ No OVN clusters found in any context" >&2
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

# Priority 3: ~/ovn.conf (from ovn-kubernetes contrib/kind.sh)
if [ -f "$HOME/ovn.conf" ]; then
    scan_kubeconfig_file "$HOME/ovn.conf" "~/ovn.conf"
fi

# Priority 4: ~/.kube/config (default kubeconfig)
if [ -f "$HOME/.kube/config" ]; then
    scan_kubeconfig_file "$HOME/.kube/config" "~/.kube/config"
fi

# Phase 2: Output Results - non-interactive parseable format

if [ ${#CLUSTERS[@]} -eq 0 ]; then
    # No clusters found
    echo "❌ No OVN-Kubernetes clusters found" >&2
    echo "" >&2
    echo "Searched in:" >&2
    [ -n "$KUBECONFIG" ] && echo "  - Current KUBECONFIG environment ($KUBECONFIG)" >&2
    echo "  - ~/.kube/kind-config" >&2
    echo "  - ~/ovn.conf" >&2
    echo "  - ~/.kube/config" >&2
    echo "" >&2
    echo "Solutions:" >&2
    echo "  1. Start a KIND cluster with OVN: cd ovn-kubernetes/contrib && ./kind.sh" >&2
    echo "  2. Set KUBECONFIG to point to an OVN cluster: export KUBECONFIG=/path/to/config" >&2
    echo "  3. Switch to a context with OVN: kubectl config use-context <context-name>" >&2
    echo "  4. Verify OVN is deployed:" >&2
    echo "     - Upstream K8s: kubectl get pods -n ovn-kubernetes" >&2
    echo "     - OpenShift: kubectl get pods -n openshift-ovn-kubernetes" >&2
    exit 1
fi

# Output cluster list to stdout in parseable format
# Format: index|kubeconfig|cluster_name|node_count|namespace
echo "✅ Found ${#CLUSTERS[@]} OVN-Kubernetes cluster(s)" >&2
echo "" >&2

idx=1
for cluster_info in "${CLUSTERS[@]}"; do
    # Parse cluster info
    IFS='|' read -r kc_file context cluster_name node_count ovn_namespace <<< "$cluster_info"

    # Output parseable line to stdout
    echo "$idx|$kc_file|$cluster_name|$node_count|$ovn_namespace"

    # Output human-readable info to stderr
    echo "  $idx. $cluster_name" >&2
    echo "     Context: $context" >&2
    echo "     Nodes: $node_count" >&2
    echo "     Namespace: $ovn_namespace" >&2
    echo "     Kubeconfig: $kc_file" >&2
    echo "" >&2

    idx=$((idx + 1))
done

exit 0
