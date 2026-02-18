#!/usr/bin/env bash
# manage-rhcos-template.sh - Download and upload RHCOS OVA template to vSphere
# This script handles the complete workflow for RHCOS template management

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE_DIR="${CACHE_DIR:-.work/openshift-vsphere-install/ova-cache}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Usage function
usage() {
    cat <<EOF
Usage: $0 <command> [options]

Manage RHCOS OVA templates for OpenShift vSphere installations.

Commands:
  download <version>              Download RHCOS OVA for OpenShift version
  upload <ova-file>               Upload OVA to vSphere as template
  install <version>               Download and upload in one step
  list                            List cached OVA files
  clean                           Remove cached OVA files

Options for 'upload' and 'install':
  --datacenter <name>             vSphere datacenter (required)
  --datastore <path>              vSphere datastore path (required)
  --cluster <path>                vSphere cluster path (required)
  --template-name <name>          Template name (auto-generated if not specified)
  --use-govc                      Use govc instead of vsphere-helper

Environment variables:
  VSPHERE_SERVER                  vCenter server (e.g., vcenter.example.com)
  VSPHERE_USERNAME                vCenter username
  VSPHERE_PASSWORD                vCenter password
  VSPHERE_INSECURE                Skip SSL verification (default: false)
  CACHE_DIR                       OVA cache directory (default: .work/openshift-vsphere-install/ova-cache)

Examples:
  # Download OVA for OpenShift 4.20
  $0 download 4.20

  # Upload OVA to vSphere
  $0 upload rhcos-4.20.ova --datacenter DC1 --datastore /DC1/datastore/ds1 --cluster /DC1/host/Cluster1

  # Download and upload in one step
  $0 install 4.20 --datacenter DC1 --datastore /DC1/datastore/ds1 --cluster /DC1/host/Cluster1

  # List cached OVAs
  $0 list

  # Clean cache
  $0 clean
EOF
}

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

# Check if required tools are available
check_prerequisites() {
    local required_tools=("python3" "curl")

    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &>/dev/null; then
            log_error "$tool is required but not installed"
            exit 1
        fi
    done
}

# Download RHCOS OVA
download_ova() {
    local version="$1"

    log_info "Fetching RHCOS metadata for OpenShift $version..."

    # Fetch metadata using Python script
    local metadata
    if ! metadata=$(python3 "$SCRIPT_DIR/fetch-rhcos-metadata.py" "$version"); then
        log_error "Failed to fetch RHCOS metadata"
        exit 1
    fi

    # Parse JSON
    local ova_url
    local rhcos_version
    local sha256
    ova_url=$(echo "$metadata" | python3 -c "import sys, json; print(json.load(sys.stdin)['url'])")
    rhcos_version=$(echo "$metadata" | python3 -c "import sys, json; print(json.load(sys.stdin)['rhcos_version'])")
    sha256=$(echo "$metadata" | python3 -c "import sys, json; print(json.load(sys.stdin)['sha256'])")

    log_info "RHCOS version: $rhcos_version"
    log_info "OVA URL: $ova_url"

    # Extract filename from URL
    local ova_filename
    ova_filename=$(basename "$ova_url")

    # Create cache directory
    mkdir -p "$CACHE_DIR"

    local ova_path="$CACHE_DIR/$ova_filename"

    # Check if already downloaded
    if [ -f "$ova_path" ]; then
        log_info "OVA already cached: $ova_path"

        # Verify checksum if available
        if [ -n "$sha256" ]; then
            log_info "Verifying SHA256 checksum..."
            if command -v sha256sum &>/dev/null; then
                local computed_sha
                computed_sha=$(sha256sum "$ova_path" | awk '{print $1}')
                if [ "$computed_sha" = "$sha256" ]; then
                    log_info "✓ Checksum verified"
                else
                    log_warn "Checksum mismatch! Re-downloading..."
                    rm -f "$ova_path"
                fi
            fi
        fi
    fi

    # Download if not cached or checksum failed
    if [ ! -f "$ova_path" ]; then
        log_info "Downloading RHCOS OVA (this may take several minutes)..."
        log_info "Downloading to: $ova_path"

        if ! curl -L --fail --progress-bar "$ova_url" -o "$ova_path"; then
            log_error "Download failed"
            rm -f "$ova_path"
            exit 1
        fi

        log_info "✓ Download complete"

        # Verify checksum after download
        if [ -n "$sha256" ] && command -v sha256sum &>/dev/null; then
            log_info "Verifying SHA256 checksum..."
            local computed_sha
            computed_sha=$(sha256sum "$ova_path" | awk '{print $1}')
            if [ "$computed_sha" = "$sha256" ]; then
                log_info "✓ Checksum verified"
            else
                log_error "Checksum verification failed!"
                log_error "Expected: $sha256"
                log_error "Got:      $computed_sha"
                exit 1
            fi
        fi
    fi

    # Output the OVA path and RHCOS version for use by caller
    echo "$ova_path"
    echo "$rhcos_version" > "$CACHE_DIR/.rhcos_version_${ova_filename}"
}

# Upload OVA to vSphere
upload_ova() {
    local ova_path="$1"
    local datacenter="$2"
    local datastore="$3"
    local cluster="$4"
    local template_name="${5:-}"
    local use_govc="${6:-false}"

    # Verify OVA file exists
    if [ ! -f "$ova_path" ]; then
        log_error "OVA file not found: $ova_path"
        exit 1
    fi

    # Generate template name if not provided
    if [ -z "$template_name" ]; then
        local ova_filename
        ova_filename=$(basename "$ova_path" .ova)

        # Try to get RHCOS version from cache
        local version_file="$CACHE_DIR/.rhcos_version_$(basename "$ova_path")"
        if [ -f "$version_file" ]; then
            local rhcos_version
            rhcos_version=$(cat "$version_file")
            template_name="rhcos-${rhcos_version}-template"
        else
            template_name="${ova_filename}-template"
        fi
    fi

    log_info "Template name: $template_name"

    # Check if vsphere-helper is available (preferred)
    local use_vsphere_helper=false
    if [ "$use_govc" = "false" ]; then
        if command -v vsphere-helper &>/dev/null || [ -f "plugins/openshift/skills/vsphere-discovery/vsphere-helper" ]; then
            use_vsphere_helper=true
            log_info "Using vsphere-helper for upload"
        else
            log_info "vsphere-helper not found, falling back to govc"
        fi
    fi

    # Check vSphere connection environment variables
    if [ -z "${VSPHERE_SERVER:-}" ] || [ -z "${VSPHERE_USERNAME:-}" ] || [ -z "${VSPHERE_PASSWORD:-}" ]; then
        log_error "vSphere connection environment variables not set"
        log_error "Required: VSPHERE_SERVER, VSPHERE_USERNAME, VSPHERE_PASSWORD"
        exit 1
    fi

    # Extract datastore name from path
    local datastore_name
    datastore_name=$(basename "$datastore")

    # Check if template already exists
    log_info "Checking if template already exists..."

    if [ "$use_vsphere_helper" = "true" ]; then
        # TODO: Add template check to vsphere-helper
        log_info "Skipping existence check (vsphere-helper doesn't support template queries yet)"
    else
        # Use govc to check
        export GOVC_URL="https://${VSPHERE_SERVER}/sdk"
        export GOVC_USERNAME="$VSPHERE_USERNAME"
        export GOVC_PASSWORD="$VSPHERE_PASSWORD"
        export GOVC_INSECURE="${VSPHERE_INSECURE:-false}"

        if govc vm.info "/${datacenter}/vm/${template_name}" &>/dev/null; then
            log_info "Template already exists: $template_name"
            log_info "Skipping upload"
            return 0
        fi
    fi

    # Upload OVA
    log_info "Uploading OVA to vSphere (this may take 10-30 minutes)..."

    if [ "$use_vsphere_helper" = "true" ]; then
        # TODO: Extend vsphere-helper to support OVA import
        log_error "vsphere-helper OVA import not yet implemented, falling back to govc"
        use_vsphere_helper=false
    fi

    # Use govc for upload
    export GOVC_URL="https://${VSPHERE_SERVER}/sdk"
    export GOVC_USERNAME="$VSPHERE_USERNAME"
    export GOVC_PASSWORD="$VSPHERE_PASSWORD"
    export GOVC_INSECURE="${VSPHERE_INSECURE:-false}"

    if ! command -v govc &>/dev/null; then
        log_error "govc is required for OVA upload but not installed"
        log_info "Install using: bash plugins/openshift/scripts/install-govc.sh"
        exit 1
    fi

    log_info "Importing OVA as VM..."
    if ! govc import.ova \
        -dc="$datacenter" \
        -ds="$datastore_name" \
        -pool="${cluster}/Resources" \
        -name="$template_name" \
        "$ova_path"; then
        log_error "OVA import failed"
        exit 1
    fi

    log_info "✓ OVA import complete"

    # Verify template was created
    log_info "Verifying template..."
    if govc vm.info "/${datacenter}/vm/${template_name}" &>/dev/null; then
        log_info "✓ Template created successfully: /${datacenter}/vm/${template_name}"
    else
        log_error "Template verification failed"
        exit 1
    fi

    echo "/${datacenter}/vm/${template_name}"
}

# List cached OVA files
list_cached() {
    if [ ! -d "$CACHE_DIR" ] || [ -z "$(ls -A "$CACHE_DIR" 2>/dev/null)" ]; then
        log_info "No cached OVA files found"
        return 0
    fi

    log_info "Cached OVA files in $CACHE_DIR:"
    echo ""

    local total_size=0
    for ova in "$CACHE_DIR"/*.ova; do
        if [ -f "$ova" ]; then
            local size
            size=$(du -h "$ova" | cut -f1)
            local name
            name=$(basename "$ova")

            # Try to get RHCOS version
            local version_file="$CACHE_DIR/.rhcos_version_$(basename "$ova")"
            if [ -f "$version_file" ]; then
                local rhcos_version
                rhcos_version=$(cat "$version_file")
                echo "  $name ($size) - RHCOS $rhcos_version"
            else
                echo "  $name ($size)"
            fi

            total_size=$((total_size + $(stat -c%s "$ova" 2>/dev/null || stat -f%z "$ova")))
        fi
    done

    echo ""
    log_info "Total cache size: $(numfmt --to=iec-i --suffix=B $total_size 2>/dev/null || echo "$total_size bytes")"
}

# Clean cached OVA files
clean_cache() {
    if [ ! -d "$CACHE_DIR" ] || [ -z "$(ls -A "$CACHE_DIR" 2>/dev/null)" ]; then
        log_info "Cache is already empty"
        return 0
    fi

    read -p "Remove all cached OVA files from $CACHE_DIR? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$CACHE_DIR"
        log_info "✓ Cache cleaned"
    else
        log_info "Cancelled"
    fi
}

# Main command dispatcher
main() {
    if [ $# -lt 1 ]; then
        usage
        exit 1
    fi

    check_prerequisites

    local command="$1"
    shift

    case "$command" in
        download)
            if [ $# -lt 1 ]; then
                log_error "Usage: $0 download <version>"
                exit 1
            fi
            download_ova "$1"
            ;;

        upload)
            if [ $# -lt 1 ]; then
                log_error "Usage: $0 upload <ova-file> --datacenter <name> --datastore <path> --cluster <path>"
                exit 1
            fi

            local ova_path="$1"
            shift

            local datacenter=""
            local datastore=""
            local cluster=""
            local template_name=""
            local use_govc="false"

            while [ $# -gt 0 ]; do
                case "$1" in
                    --datacenter)
                        datacenter="$2"
                        shift 2
                        ;;
                    --datastore)
                        datastore="$2"
                        shift 2
                        ;;
                    --cluster)
                        cluster="$2"
                        shift 2
                        ;;
                    --template-name)
                        template_name="$2"
                        shift 2
                        ;;
                    --use-govc)
                        use_govc="true"
                        shift
                        ;;
                    *)
                        log_error "Unknown option: $1"
                        exit 1
                        ;;
                esac
            done

            if [ -z "$datacenter" ] || [ -z "$datastore" ] || [ -z "$cluster" ]; then
                log_error "Missing required options: --datacenter, --datastore, --cluster"
                exit 1
            fi

            upload_ova "$ova_path" "$datacenter" "$datastore" "$cluster" "$template_name" "$use_govc"
            ;;

        install)
            if [ $# -lt 1 ]; then
                log_error "Usage: $0 install <version> --datacenter <name> --datastore <path> --cluster <path>"
                exit 1
            fi

            local version="$1"
            shift

            local datacenter=""
            local datastore=""
            local cluster=""
            local template_name=""
            local use_govc="false"

            while [ $# -gt 0 ]; do
                case "$1" in
                    --datacenter)
                        datacenter="$2"
                        shift 2
                        ;;
                    --datastore)
                        datastore="$2"
                        shift 2
                        ;;
                    --cluster)
                        cluster="$2"
                        shift 2
                        ;;
                    --template-name)
                        template_name="$2"
                        shift 2
                        ;;
                    --use-govc)
                        use_govc="true"
                        shift
                        ;;
                    *)
                        log_error "Unknown option: $1"
                        exit 1
                        ;;
                esac
            done

            if [ -z "$datacenter" ] || [ -z "$datastore" ] || [ -z "$cluster" ]; then
                log_error "Missing required options: --datacenter, --datastore, --cluster"
                exit 1
            fi

            # Download
            local ova_path
            ova_path=$(download_ova "$version")

            # Upload
            upload_ova "$ova_path" "$datacenter" "$datastore" "$cluster" "$template_name" "$use_govc"
            ;;

        list)
            list_cached
            ;;

        clean)
            clean_cache
            ;;

        help|--help|-h)
            usage
            exit 0
            ;;

        *)
            log_error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

main "$@"
