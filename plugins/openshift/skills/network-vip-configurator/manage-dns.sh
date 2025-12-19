#!/usr/bin/env bash
# manage-dns.sh - Manage DNS records for OpenShift VIPs
# Supports both Route53 (automated) and manual DNS verification

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Usage function
usage() {
    cat <<EOF
Usage: $0 <command> [options]

Manage DNS records for OpenShift cluster VIPs.

Commands:
  create-route53              Create Route53 DNS records (api, api-int, *.apps)
  verify                      Verify DNS records resolve correctly
  get-zone-id                 Get Route53 hosted zone ID for domain

Options for 'create-route53':
  --cluster-name <name>       Cluster name (required)
  --base-domain <domain>      Base domain (required)
  --api-vip <ip>              API VIP address (required)
  --ingress-vip <ip>          Ingress VIP address (required)
  --zone-id <id>              Route53 hosted zone ID (auto-detected if not specified)
  --ttl <seconds>             DNS TTL in seconds (default: 300)

Options for 'verify':
  --cluster-name <name>       Cluster name (required)
  --base-domain <domain>      Base domain (required)
  --api-vip <ip>              Expected API VIP address (required)
  --ingress-vip <ip>          Expected Ingress VIP address (required)
  --timeout <seconds>         Verification timeout (default: 60)

Options for 'get-zone-id':
  --domain <domain>           Base domain (required)

Environment variables:
  AWS_PROFILE                 AWS profile to use (optional)
  AWS_REGION                  AWS region (optional)

Examples:
  # Get hosted zone ID
  $0 get-zone-id --domain example.com

  # Create Route53 DNS records
  $0 create-route53 \\
    --cluster-name mycluster \\
    --base-domain example.com \\
    --api-vip 10.0.0.100 \\
    --ingress-vip 10.0.0.101

  # Verify DNS records
  $0 verify \\
    --cluster-name mycluster \\
    --base-domain example.com \\
    --api-vip 10.0.0.100 \\
    --ingress-vip 10.0.0.101
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

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $*" >&2
}

# Check if AWS CLI is available
check_aws_cli() {
    if ! command -v aws &>/dev/null; then
        log_error "AWS CLI is not installed"
        log_error "Install it from: https://aws.amazon.com/cli/"
        exit 1
    fi

    # Test AWS credentials
    if ! aws sts get-caller-identity &>/dev/null; then
        log_error "AWS credentials not configured"
        log_error "Run: aws configure"
        exit 1
    fi
}

# Get Route53 hosted zone ID for domain
get_zone_id() {
    local domain="$1"

    log_info "Looking up hosted zone for domain: $domain"

    # Query Route53 for hosted zone
    local zone_id
    zone_id=$(aws route53 list-hosted-zones \
        --query "HostedZones[?Name=='${domain}.'].Id" \
        --output text | cut -d'/' -f3)

    if [ -z "$zone_id" ]; then
        log_error "No hosted zone found for domain: $domain"
        log_info "Available zones:"
        aws route53 list-hosted-zones \
            --query "HostedZones[].{Name:Name,ID:Id}" \
            --output table
        exit 1
    fi

    echo "$zone_id"
}

# Create Route53 DNS records
create_route53_records() {
    local cluster_name="$1"
    local base_domain="$2"
    local api_vip="$3"
    local ingress_vip="$4"
    local zone_id="${5:-}"
    local ttl="${6:-300}"

    log_info "Creating Route53 DNS records..."
    log_info "Cluster: $cluster_name.$base_domain"
    log_info "API VIP: $api_vip"
    log_info "Ingress VIP: $ingress_vip"

    # Get zone ID if not provided
    if [ -z "$zone_id" ]; then
        zone_id=$(get_zone_id "$base_domain")
        log_info "Detected hosted zone ID: $zone_id"
    fi

    # Create change batch JSON
    local change_batch_file="/tmp/route53-changes-$$.json"
    trap "rm -f $change_batch_file" EXIT

    cat > "$change_batch_file" <<EOF
{
  "Comment": "OpenShift cluster ${cluster_name} VIP records",
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "api.${cluster_name}.${base_domain}",
        "Type": "A",
        "TTL": ${ttl},
        "ResourceRecords": [{"Value": "${api_vip}"}]
      }
    },
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "api-int.${cluster_name}.${base_domain}",
        "Type": "A",
        "TTL": ${ttl},
        "ResourceRecords": [{"Value": "${api_vip}"}]
      }
    },
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "*.apps.${cluster_name}.${base_domain}",
        "Type": "A",
        "TTL": ${ttl},
        "ResourceRecords": [{"Value": "${ingress_vip}"}]
      }
    }
  ]
}
EOF

    log_debug "Change batch:"
    cat "$change_batch_file" >&2

    # Apply changes
    log_info "Applying DNS changes to Route53..."
    local change_id
    change_id=$(aws route53 change-resource-record-sets \
        --hosted-zone-id "$zone_id" \
        --change-batch "file://$change_batch_file" \
        --query 'ChangeInfo.Id' \
        --output text)

    log_info "✓ DNS records created"
    log_info "Change ID: $change_id"
    echo ""
    log_info "Created records:"
    log_info "  api.${cluster_name}.${base_domain} → ${api_vip}"
    log_info "  api-int.${cluster_name}.${base_domain} → ${api_vip}"
    log_info "  *.apps.${cluster_name}.${base_domain} → ${ingress_vip}"

    # Return zone ID for later use
    echo "$zone_id"
}

# Verify DNS records resolve correctly
verify_dns_records() {
    local cluster_name="$1"
    local base_domain="$2"
    local expected_api_vip="$3"
    local expected_ingress_vip="$4"
    local timeout="${5:-60}"

    log_info "Verifying DNS records..."

    local api_record="api.${cluster_name}.${base_domain}"
    local api_int_record="api-int.${cluster_name}.${base_domain}"
    local apps_record="test.apps.${cluster_name}.${base_domain}"

    local all_verified=true
    local start_time=$(date +%s)
    local end_time=$((start_time + timeout))

    # Wait for DNS propagation with timeout
    while [ $(date +%s) -lt $end_time ]; do
        all_verified=true

        # Check api record
        log_info "Checking $api_record..."
        local api_resolved
        api_resolved=$(dig +short "$api_record" | tail -n1)

        if [ "$api_resolved" = "$expected_api_vip" ]; then
            log_info "  ✓ $api_record → $api_resolved"
        else
            log_warn "  ✗ $api_record → $api_resolved (expected: $expected_api_vip)"
            all_verified=false
        fi

        # Check api-int record
        log_info "Checking $api_int_record..."
        local api_int_resolved
        api_int_resolved=$(dig +short "$api_int_record" | tail -n1)

        if [ "$api_int_resolved" = "$expected_api_vip" ]; then
            log_info "  ✓ $api_int_record → $api_int_resolved"
        else
            log_warn "  ✗ $api_int_record → $api_int_resolved (expected: $expected_api_vip)"
            all_verified=false
        fi

        # Check *.apps wildcard
        log_info "Checking $apps_record..."
        local apps_resolved
        apps_resolved=$(dig +short "$apps_record" | tail -n1)

        if [ "$apps_resolved" = "$expected_ingress_vip" ]; then
            log_info "  ✓ $apps_record → $apps_resolved"
        else
            log_warn "  ✗ $apps_record → $apps_resolved (expected: $expected_ingress_vip)"
            all_verified=false
        fi

        if [ "$all_verified" = true ]; then
            log_info "✓ All DNS records verified successfully"
            return 0
        fi

        # Wait before retrying
        local remaining=$((end_time - $(date +%s)))
        if [ $remaining -gt 0 ]; then
            log_info "DNS not fully propagated, waiting 5 seconds... ($remaining seconds remaining)"
            sleep 5
        fi
    done

    # Timeout reached
    if [ "$all_verified" = false ]; then
        log_error "DNS verification failed after ${timeout}s timeout"
        log_error "Some records did not resolve correctly"
        return 1
    fi

    return 0
}

# Main command dispatcher
main() {
    if [ $# -lt 1 ]; then
        usage
        exit 1
    fi

    local command="$1"
    shift

    case "$command" in
        get-zone-id)
            local domain=""

            while [ $# -gt 0 ]; do
                case "$1" in
                    --domain)
                        domain="$2"
                        shift 2
                        ;;
                    *)
                        log_error "Unknown option: $1"
                        exit 1
                        ;;
                esac
            done

            if [ -z "$domain" ]; then
                log_error "Missing required option: --domain"
                exit 1
            fi

            check_aws_cli
            get_zone_id "$domain"
            ;;

        create-route53)
            local cluster_name=""
            local base_domain=""
            local api_vip=""
            local ingress_vip=""
            local zone_id=""
            local ttl="300"

            while [ $# -gt 0 ]; do
                case "$1" in
                    --cluster-name)
                        cluster_name="$2"
                        shift 2
                        ;;
                    --base-domain)
                        base_domain="$2"
                        shift 2
                        ;;
                    --api-vip)
                        api_vip="$2"
                        shift 2
                        ;;
                    --ingress-vip)
                        ingress_vip="$2"
                        shift 2
                        ;;
                    --zone-id)
                        zone_id="$2"
                        shift 2
                        ;;
                    --ttl)
                        ttl="$2"
                        shift 2
                        ;;
                    *)
                        log_error "Unknown option: $1"
                        exit 1
                        ;;
                esac
            done

            if [ -z "$cluster_name" ] || [ -z "$base_domain" ] || [ -z "$api_vip" ] || [ -z "$ingress_vip" ]; then
                log_error "Missing required options: --cluster-name, --base-domain, --api-vip, --ingress-vip"
                exit 1
            fi

            check_aws_cli
            create_route53_records "$cluster_name" "$base_domain" "$api_vip" "$ingress_vip" "$zone_id" "$ttl"
            ;;

        verify)
            local cluster_name=""
            local base_domain=""
            local api_vip=""
            local ingress_vip=""
            local timeout="60"

            while [ $# -gt 0 ]; do
                case "$1" in
                    --cluster-name)
                        cluster_name="$2"
                        shift 2
                        ;;
                    --base-domain)
                        base_domain="$2"
                        shift 2
                        ;;
                    --api-vip)
                        api_vip="$2"
                        shift 2
                        ;;
                    --ingress-vip)
                        ingress_vip="$2"
                        shift 2
                        ;;
                    --timeout)
                        timeout="$2"
                        shift 2
                        ;;
                    *)
                        log_error "Unknown option: $1"
                        exit 1
                        ;;
                esac
            done

            if [ -z "$cluster_name" ] || [ -z "$base_domain" ] || [ -z "$api_vip" ] || [ -z "$ingress_vip" ]; then
                log_error "Missing required options: --cluster-name, --base-domain, --api-vip, --ingress-vip"
                exit 1
            fi

            if ! command -v dig &>/dev/null; then
                log_error "dig command not found (install bind-utils or dnsutils)"
                exit 1
            fi

            verify_dns_records "$cluster_name" "$base_domain" "$api_vip" "$ingress_vip" "$timeout"
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
