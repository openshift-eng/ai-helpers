#!/bin/bash
# detect-cluster.sh - Discover OVN-Kubernetes clusters across all kubeconfig files and contexts
# Returns: kubeconfig path to stdout, diagnostics to stderr
# Exit codes: 0=success, 1=no cluster found, 2=user cancelled

echo "🔍 Detecting OVN-Kubernetes clusters..." >&2
echo "" >&2

# Array to store discovered clusters
# Format: "kubeconfig_path|context_name|cluster_display_name|node_count"
declare -a CLUSTERS=()

# Function to test a specific kubeconfig and context for OVN pods
test_context_for_ovn() {
    local kc_file="$1"
    local context="$2"

    # Try to get OVN pods from this context
    local ovn_pods
    ovn_pods=$(KUBECONFIG="$kc_file" kubectl --kubeconfig="$kc_file" --context="$context" get pods -n ovn-kubernetes -o name 2>/dev/null | head -3)

    if [ -n "$ovn_pods" ]; then
        # Get cluster info
        local cluster_name
        cluster_name=$(KUBECONFIG="$kc_file" kubectl --kubeconfig="$kc_file" --context="$context" config view --minify -o jsonpath='{.clusters[0].name}' 2>/dev/null || echo "$context")

        local node_count
        node_count=$(KUBECONFIG="$kc_file" kubectl --kubeconfig="$kc_file" --context="$context" get nodes --no-headers 2>/dev/null | wc -l)

        # Store cluster info
        CLUSTERS+=("$kc_file|$context|$cluster_name|$node_count")
        return 0
    fi
    return 1
}

# Function to display cluster information and switch context
display_cluster_info() {
    local kc_file="$1"
    local context="$2"
    local cluster_name="$3"
    local node_count="$4"

    echo "  Cluster: $cluster_name" >&2
    echo "  Context: $context" >&2
    echo "  Nodes: $node_count" >&2
    echo "  Kubeconfig: $kc_file" >&2
    echo "" >&2

    # Set this context as current-context in the kubeconfig
    KUBECONFIG="$kc_file" kubectl --kubeconfig="$kc_file" config use-context "$context" >/dev/null 2>&1

    # Show cluster info
    echo "Cluster nodes:" >&2
    KUBECONFIG="$kc_file" kubectl --kubeconfig="$kc_file" get nodes -o wide 2>&1 | head -5 >&2
    echo "" >&2
    echo "OVN pods:" >&2
    KUBECONFIG="$kc_file" kubectl --kubeconfig="$kc_file" get pods -n ovn-kubernetes 2>&1 | head -8 >&2
    echo "" >&2
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
    scan_kubeconfig_file "$KUBECONFIG" "Current KUBECONFIG environment ($KUBECONFIG)"
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

# Phase 2: Selection - choose cluster if multiple found

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
    echo "  4. Verify OVN is deployed: kubectl get pods -n ovn-kubernetes" >&2
    exit 1

elif [ ${#CLUSTERS[@]} -eq 1 ]; then
    # Single cluster found - use it automatically
    IFS='|' read -r kc_file context cluster_name node_count <<< "${CLUSTERS[0]}"

    echo "✅ Found OVN-Kubernetes cluster:" >&2
    echo "" >&2
    display_cluster_info "$kc_file" "$context" "$cluster_name" "$node_count"

    # Output kubeconfig path to stdout
    echo "$kc_file"
    exit 0

else
    # Multiple clusters found - ask user to choose
    echo "✨ Found ${#CLUSTERS[@]} OVN-Kubernetes clusters:" >&2
    echo "" >&2

    # Display clusters with numbers
    local idx=1
    for cluster_info in "${CLUSTERS[@]}"; do
        IFS='|' read -r kc_file context cluster_name node_count <<< "$cluster_info"
        echo "  $idx. $cluster_name" >&2
        echo "     Context: $context" >&2
        echo "     Nodes: $node_count" >&2
        echo "     Kubeconfig: $kc_file" >&2
        echo "" >&2
        idx=$((idx + 1))
    done

    # Prompt user for selection
    echo -n "Which cluster would you like to use? (1-${#CLUSTERS[@]}), or 'q' to quit: " >&2
    read -r choice

    # Validate input
    if [ "$choice" = "q" ] || [ "$choice" = "Q" ]; then
        echo "" >&2
        echo "❌ Operation cancelled by user" >&2
        exit 2
    fi

    if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt ${#CLUSTERS[@]} ]; then
        echo "" >&2
        echo "❌ Invalid selection: $choice" >&2
        echo "Please choose a number between 1 and ${#CLUSTERS[@]}" >&2
        exit 2
    fi

    # Get selected cluster (arrays are 0-indexed, user input is 1-indexed)
    selected_idx=$((choice - 1))
    IFS='|' read -r kc_file context cluster_name node_count <<< "${CLUSTERS[$selected_idx]}"

    echo "" >&2
    echo "✅ Selected cluster:" >&2
    echo "" >&2
    display_cluster_info "$kc_file" "$context" "$cluster_name" "$node_count"

    # Output kubeconfig path to stdout
    echo "$kc_file"
    exit 0
fi
