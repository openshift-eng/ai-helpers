#!/bin/bash
#
# Main orchestration script for Prow Job Resource Grep
#
# Usage: prow_job_resource_grep.sh <prowjob-url> <resource-spec1> [<resource-spec2> ...]
#
# Example: prow_job_resource_grep.sh \
#   "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/pr-logs/pull/30393/pull-ci-openshift-origin-main-okd-scos-e2e-aws-ovn/1978913325970362368/" \
#   pod/etcd-0
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}INFO:${NC} $1"
}

log_success() {
    echo -e "${GREEN}SUCCESS:${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

log_error() {
    echo -e "${RED}ERROR:${NC} $1" >&2
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check Python 3
    if ! command -v python3 &> /dev/null; then
        log_error "python3 is required but not installed"
        exit 1
    fi

    # Check gcloud
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI is required but not installed"
        log_error "Install from: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi

    # Check gcloud authentication
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        log_error "gcloud is not authenticated"
        log_error "Please run: gcloud auth login"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Parse and validate URL
parse_url() {
    local url="$1"
    log_info "Parsing Prow job URL..."

    local metadata_file="${WORK_DIR}/metadata.json"

    if ! python3 "${SCRIPT_DIR}/parse_url.py" "$url" > "$metadata_file"; then
        log_error "Failed to parse URL"
        exit 1
    fi

    # Extract values from metadata
    BUILD_ID=$(jq -r '.build_id' "$metadata_file")
    PROWJOB_NAME=$(jq -r '.prowjob_name' "$metadata_file")
    GCS_BASE_PATH=$(jq -r '.gcs_base_path' "$metadata_file")
    BUCKET_PATH=$(jq -r '.bucket_path' "$metadata_file")

    log_success "Build ID: $BUILD_ID"
    log_success "Prowjob: $PROWJOB_NAME"
}

# Create working directory
create_work_dir() {
    log_info "Creating working directory: ${BUILD_ID}/"

    mkdir -p "${BUILD_ID}/logs"
    WORK_DIR="${BUILD_ID}/logs"

    # Check if artifacts already exist
    if [ -d "${WORK_DIR}/artifacts" ] && [ "$(ls -A ${WORK_DIR}/artifacts)" ]; then
        read -p "Artifacts already exist for build ${BUILD_ID}. Re-download? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            SKIP_DOWNLOAD=true
            log_info "Skipping download, using existing artifacts"
        else
            SKIP_DOWNLOAD=false
        fi
    else
        SKIP_DOWNLOAD=false
    fi
}

# Download and validate prowjob.json
download_prowjob_json() {
    if [ "$SKIP_DOWNLOAD" = true ]; then
        return
    fi

    log_info "Downloading prowjob.json..."

    local prowjob_json="${WORK_DIR}/prowjob.json"
    local gcs_prowjob="${GCS_BASE_PATH}prowjob.json"

    if ! gcloud storage cp "$gcs_prowjob" "$prowjob_json" 2>/dev/null; then
        log_error "Failed to download prowjob.json from $gcs_prowjob"
        log_error "Verify the URL and check if the job completed"
        exit 1
    fi

    log_success "Downloaded prowjob.json"
}

# Extract target from prowjob.json
extract_target() {
    log_info "Extracting target from prowjob.json..."

    local prowjob_json="${WORK_DIR}/prowjob.json"

    # Search for --target=xxx pattern
    if ! TARGET=$(grep -oP -- '--target=\K[a-zA-Z0-9-]+' "$prowjob_json" | head -1); then
        log_error "This is not a ci-operator job (no --target found in prowjob.json)"
        log_error "Only ci-operator jobs can be analyzed by this tool"
        exit 1
    fi

    log_success "Target: $TARGET"
}

# Download artifacts
download_artifacts() {
    if [ "$SKIP_DOWNLOAD" = true ]; then
        return
    fi

    log_info "Downloading audit logs and pod logs..."

    local gcs_audit_logs="${GCS_BASE_PATH}artifacts/${TARGET}/gather-extra/artifacts/audit_logs/"
    local local_audit_logs="${WORK_DIR}/artifacts/${TARGET}/gather-extra/artifacts/audit_logs/"

    local gcs_pod_logs="${GCS_BASE_PATH}artifacts/${TARGET}/gather-extra/artifacts/pods/"
    local local_pod_logs="${WORK_DIR}/artifacts/${TARGET}/gather-extra/artifacts/pods/"

    # Download audit logs
    log_info "Downloading audit logs..."
    if gcloud storage cp -r "$gcs_audit_logs" "$local_audit_logs" 2>/dev/null; then
        log_success "Downloaded audit logs"
    else
        log_warn "No audit logs found (job may not have completed or audit logging disabled)"
    fi

    # Download pod logs
    log_info "Downloading pod logs..."
    if gcloud storage cp -r "$gcs_pod_logs" "$local_pod_logs" 2>/dev/null; then
        log_success "Downloaded pod logs"
    else
        log_warn "No pod logs found"
    fi
}

# Parse logs
parse_logs() {
    log_info "Parsing audit logs..."

    local audit_output="${WORK_DIR}/audit_entries.json"
    python3 "${SCRIPT_DIR}/parse_audit_logs.py" "${WORK_DIR}" "${RESOURCE_SPECS[@]}" > "$audit_output" 2>&1

    AUDIT_COUNT=$(jq '. | length' "$audit_output")
    log_success "Found $AUDIT_COUNT audit log entries"

    log_info "Parsing pod logs..."

    local pod_output="${WORK_DIR}/pod_entries.json"
    python3 "${SCRIPT_DIR}/parse_pod_logs.py" "${WORK_DIR}" "${RESOURCE_SPECS[@]}" > "$pod_output" 2>&1

    POD_COUNT=$(jq '. | length' "$pod_output")
    log_success "Found $POD_COUNT pod log entries"

    TOTAL_COUNT=$((AUDIT_COUNT + POD_COUNT))

    if [ "$TOTAL_COUNT" -eq 0 ]; then
        log_warn "No log entries found matching the specified resources"
        log_warn "Suggestions:"
        log_warn "  - Check resource names for typos"
        log_warn "  - Try searching without kind or namespace filters"
        log_warn "  - Verify resources existed during this job execution"
    fi
}

# Generate report
generate_report() {
    log_info "Generating HTML report..."

    # Build report filename
    local report_filename=""
    for spec in "${RESOURCE_SPECS[@]}"; do
        # Replace special characters
        local safe_spec="${spec//:/_}"
        safe_spec="${safe_spec//\//_}"

        if [ -z "$report_filename" ]; then
            report_filename="${safe_spec}"
        else
            report_filename="${report_filename}__${safe_spec}"
        fi
    done

    REPORT_PATH="${BUILD_ID}/${report_filename}.html"

    # Update metadata with additional fields
    local metadata_file="${WORK_DIR}/metadata.json"
    jq --arg target "$TARGET" \
       --argjson resources "$(printf '%s\n' "${RESOURCE_SPECS[@]}" | jq -R . | jq -s .)" \
       '. + {target: $target, resources: $resources}' \
       "$metadata_file" > "${metadata_file}.tmp"
    mv "${metadata_file}.tmp" "$metadata_file"

    # Generate report
    python3 "${SCRIPT_DIR}/generate_report.py" \
        "${SCRIPT_DIR}/report_template.html" \
        "$REPORT_PATH" \
        "$metadata_file" \
        "${WORK_DIR}/audit_entries.json" \
        "${WORK_DIR}/pod_entries.json"

    log_success "Report generated: $REPORT_PATH"
}

# Print summary
print_summary() {
    echo
    echo "=========================================="
    echo "Resource Lifecycle Analysis Complete"
    echo "=========================================="
    echo
    echo "Prow Job: $PROWJOB_NAME"
    echo "Build ID: $BUILD_ID"
    echo "Target: $TARGET"
    echo
    echo "Resources Analyzed:"
    for spec in "${RESOURCE_SPECS[@]}"; do
        echo "  - $spec"
    done
    echo
    echo "Artifacts downloaded to: ${WORK_DIR}/"
    echo
    echo "Results:"
    echo "  - Audit log entries: $AUDIT_COUNT"
    echo "  - Pod log entries: $POD_COUNT"
    echo "  - Total entries: $TOTAL_COUNT"
    echo
    echo "Report generated: $REPORT_PATH"
    echo
    echo "To open report:"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  open $REPORT_PATH"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "  xdg-open $REPORT_PATH"
    else
        echo "  Open $REPORT_PATH in your browser"
    fi
    echo
}

# Main function
main() {
    if [ $# -lt 2 ]; then
        echo "Usage: $0 <prowjob-url> <resource-spec1> [<resource-spec2> ...]"
        echo
        echo "Examples:"
        echo "  $0 'https://gcsweb-ci.../1978913325970362368/' pod/etcd-0"
        echo "  $0 'https://gcsweb-ci.../1978913325970362368/' openshift-etcd:pod/etcd-0 configmap/cluster-config"
        exit 1
    fi

    local url="$1"
    shift
    RESOURCE_SPECS=("$@")

    # Initialize variables
    SKIP_DOWNLOAD=false
    WORK_DIR=""
    BUILD_ID=""
    PROWJOB_NAME=""
    GCS_BASE_PATH=""
    BUCKET_PATH=""
    TARGET=""
    REPORT_PATH=""
    AUDIT_COUNT=0
    POD_COUNT=0
    TOTAL_COUNT=0

    # Execute workflow
    check_prerequisites
    parse_url "$url"
    create_work_dir
    download_prowjob_json
    extract_target
    download_artifacts
    parse_logs
    generate_report
    print_summary
}

# Run main function
main "$@"
