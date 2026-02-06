# Network VIP Configurator

Automate VIP selection and DNS configuration for OpenShift vSphere installations.

## Overview

This skill provides automated network VIP (Virtual IP) configuration for OpenShift clusters:
- **Subnet Scanning** - Find available IPs automatically
- **VIP Selection** - Present available IPs to user for API and Ingress VIPs
- **DNS Management** - Create and verify DNS records (Route53 or manual)
- **Validation** - Ensure IPs are available and DNS resolves correctly

## Quick Start

### Scan Subnet for Available IPs

```bash
# Scan subnet to find 10 available IP addresses
python3 plugins/openshift/skills/network-vip-configurator/scan-available-ips.py 10.0.0.0/24 --verbose

# Output: List of available IPs with ping/Route53 status
```

### Create Route53 DNS Records

```bash
# Automatically create DNS records in Route53
bash plugins/openshift/skills/network-vip-configurator/manage-dns.sh create-route53 \
  --cluster-name mycluster \
  --base-domain example.com \
  --api-vip 10.0.0.100 \
  --ingress-vip 10.0.0.101
```

### Verify DNS Records

```bash
# Verify DNS records resolve correctly
bash plugins/openshift/skills/network-vip-configurator/manage-dns.sh verify \
  --cluster-name mycluster \
  --base-domain example.com \
  --api-vip 10.0.0.100 \
  --ingress-vip 10.0.0.101
```

## Tools

### scan-available-ips.py

Scan subnet CIDR for available IP addresses using parallel ping and optional Route53 checking.

**Usage:**
```bash
scan-available-ips.py <cidr> [options]
```

**Options:**
- `--zone-id <id>` - Route53 hosted zone ID for DNS checking
- `--max-candidates <n>` - Max IPs to return (default: 10)
- `--skip-first <n>` - Skip first N IPs (default: 10)
- `--skip-last <n>` - Skip last N IPs (default: 10)
- `--max-workers <n>` - Parallel workers (default: 20)
- `--verbose` - Show progress
- `--pretty` - Pretty-print JSON

**Examples:**
```bash
# Basic scan
python3 scan-available-ips.py 10.0.0.0/24

# Scan with Route53 integration
python3 scan-available-ips.py 10.0.0.0/24 --zone-id Z1234567890ABC --verbose

# Scan with custom range
python3 scan-available-ips.py 172.16.0.0/16 --skip-first 100 --max-candidates 20
```

**Output:**
```json
[
  {
    "ip": "10.0.0.100",
    "available": true,
    "ping_response": false,
    "in_route53": false,
    "route53_record": null
  }
]
```

---

### manage-dns.sh

Manage DNS records for OpenShift clusters (Route53 or manual).

**Commands:**

#### get-zone-id
Get Route53 hosted zone ID for a domain.

```bash
manage-dns.sh get-zone-id --domain example.com
```

#### create-route53
Create Route53 DNS A records for cluster endpoints.

```bash
manage-dns.sh create-route53 \
  --cluster-name <name> \
  --base-domain <domain> \
  --api-vip <ip> \
  --ingress-vip <ip> \
  [--zone-id <id>] \
  [--ttl <seconds>]
```

**Example:**
```bash
bash manage-dns.sh create-route53 \
  --cluster-name prod \
  --base-domain example.com \
  --api-vip 10.0.0.100 \
  --ingress-vip 10.0.0.101
```

**Creates:**
- `api.prod.example.com` → 10.0.0.100
- `api-int.prod.example.com` → 10.0.0.100
- `*.apps.prod.example.com` → 10.0.0.101

#### verify
Verify DNS records resolve to expected IPs.

```bash
manage-dns.sh verify \
  --cluster-name <name> \
  --base-domain <domain> \
  --api-vip <ip> \
  --ingress-vip <ip> \
  [--timeout <seconds>]
```

**Example:**
```bash
bash manage-dns.sh verify \
  --cluster-name prod \
  --base-domain example.com \
  --api-vip 10.0.0.100 \
  --ingress-vip 10.0.0.101 \
  --timeout 60
```

## Requirements

### Python 3
- Pre-installed on most systems
- Used for subnet scanning

### dig (DNS lookup)
- **Linux**: `sudo yum install bind-utils` or `sudo apt-get install dnsutils`
- **macOS**: Pre-installed

### AWS CLI (Optional)
- Only required for Route53 automation
- Install: https://aws.amazon.com/cli/
- Configure: `aws configure`

## How It Works

### Subnet Scanning

1. **Parse CIDR**: Convert CIDR to IP range
2. **Parallel Ping**: Ping IPs concurrently (default: 20 workers)
3. **Route53 Check**: Query Route53 for existing A records (optional)
4. **Filter Available**: Return IPs that don't respond to ping and aren't in Route53
5. **Output JSON**: Structured data for easy parsing

**Performance:**
- /24 subnet (~254 IPs): ~10-15 seconds
- /23 subnet (~510 IPs): ~20-30 seconds
- Stops after finding enough candidates

### DNS Management

**Route53 Mode:**
1. Auto-detect or use provided hosted zone ID
2. Create UPSERT change batch for 3 records
3. Apply changes via AWS API
4. Return zone ID

**Manual Mode:**
1. Display DNS records user needs to create
2. Wait for user confirmation
3. Proceed to verification

**Verification:**
1. Query DNS using `dig` command
2. Compare resolved IP to expected IP
3. Retry every 5 seconds (up to timeout)
4. Report success or failure

## Use Cases

### 1. Fully Automated (Route53)

Best for AWS-based workflows with Route53 access.

```bash
# 1. Scan subnet
IPS=$(python3 scan-available-ips.py 10.0.0.0/24 --verbose)

# 2. User selects from available IPs
# (via UI or AskUserQuestion tool)

# 3. Create DNS automatically
bash manage-dns.sh create-route53 \
  --cluster-name mycluster \
  --base-domain example.com \
  --api-vip 10.0.0.100 \
  --ingress-vip 10.0.0.101

# 4. Verify
bash manage-dns.sh verify \
  --cluster-name mycluster \
  --base-domain example.com \
  --api-vip 10.0.0.100 \
  --ingress-vip 10.0.0.101
```

### 2. Manual DNS

Best for non-AWS environments or when Route53 access is not available.

```bash
# 1. Scan subnet
IPS=$(python3 scan-available-ips.py 10.0.0.0/24 --verbose)

# 2. User selects VIPs

# 3. Display instructions
echo "Create these DNS records:"
echo "  api.cluster.example.com → 10.0.0.100"
echo "  api-int.cluster.example.com → 10.0.0.100"
echo "  *.apps.cluster.example.com → 10.0.0.101"

# 4. User creates records manually

# 5. Verify once created
bash manage-dns.sh verify \
  --cluster-name cluster \
  --base-domain example.com \
  --api-vip 10.0.0.100 \
  --ingress-vip 10.0.0.101 \
  --timeout 300
```

### 3. Pre-existing DNS

When DNS records already exist:

```bash
# Just verify existing DNS
bash manage-dns.sh verify \
  --cluster-name existing \
  --base-domain example.com \
  --api-vip 10.0.0.100 \
  --ingress-vip 10.0.0.101
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `AWS_PROFILE` | AWS profile to use | No |
| `AWS_REGION` | AWS region | No |

## Examples

### Example 1: Basic Workflow

```bash
# Scan and select VIPs
python3 scan-available-ips.py 10.0.0.0/24 --pretty

# Create DNS
bash manage-dns.sh create-route53 \
  --cluster-name dev \
  --base-domain test.com \
  --api-vip 10.0.0.50 \
  --ingress-vip 10.0.0.51

# Verify
bash manage-dns.sh verify \
  --cluster-name dev \
  --base-domain test.com \
  --api-vip 10.0.0.50 \
  --ingress-vip 10.0.0.51
```

### Example 2: Large Subnet

```bash
# Scan /16 subnet with more workers
python3 scan-available-ips.py 172.16.0.0/16 \
  --max-workers 50 \
  --max-candidates 20 \
  --skip-first 100 \
  --verbose
```

### Example 3: Custom TTL

```bash
# Development cluster with low TTL
bash manage-dns.sh create-route53 \
  --cluster-name dev \
  --base-domain dev.example.com \
  --api-vip 10.0.0.100 \
  --ingress-vip 10.0.0.101 \
  --ttl 60
```

## Troubleshooting

### No Available IPs Found

**Problem**: Scanner finds 0 available IPs

**Solutions:**
- Subnet may be fully allocated
- Try different CIDR
- Reduce `--skip-first` and `--skip-last`
- Check firewall isn't blocking ping

### AWS Credentials Not Configured

**Problem**: `Error: AWS credentials not configured`

**Solution:**
```bash
aws configure
# Enter access key, secret key, region
```

### DNS Not Resolving

**Problem**: Verification fails after timeout

**Solutions:**
- Wait longer: `--timeout 300`
- Check DNS provider for propagation status
- Verify records were created correctly
- Flush local DNS cache

### Permission Denied

**Problem**: Route53 permission error

**Solution:**
- Verify IAM user has `route53:ChangeResourceRecordSets` permission
- Check AWS credentials are for correct account

## Integration

### With `/openshift:install-vsphere`

This skill is used in Phase 2, Step 5 (Network Configuration and VIP Selection).

### With install-config.yaml

Use the VIPs in your OpenShift install configuration:

```yaml
platform:
  vsphere:
    apiVIP: 10.0.0.100        # From this skill
    ingressVIP: 10.0.0.101    # From this skill

networking:
  machineNetwork:
  - cidr: 10.0.0.0/24         # Scanned subnet
```

## Performance

| Operation | Time |
|-----------|------|
| Scan /24 subnet | 10-15 seconds |
| Scan /16 subnet | 40-60 seconds |
| Route53 creation | 2-5 seconds |
| Route53 propagation | 5-30 seconds |
| DNS verification | <5 seconds |

## Files

```
network-vip-configurator/
├── scan-available-ips.py    # Subnet scanner (Python)
├── manage-dns.sh            # DNS management (Bash)
├── SKILL.md                 # AI skill instructions
└── README.md                # This file
```

## Related

- **Skills**: `plugins/openshift/skills/vsphere-discovery` - vSphere infrastructure discovery
- **Skills**: `plugins/openshift/skills/rhcos-template-manager` - RHCOS template management
- **Command**: `/openshift:install-vsphere` - Uses this skill for VIP configuration

## Benefits

✅ **Automated** - No manual IP hunting
✅ **Validated** - Ensures IPs are truly available
✅ **Fast** - Parallel scanning for quick results
✅ **Flexible** - Route53 or manual DNS
✅ **Reliable** - Verifies DNS before installation
✅ **Safe** - Prevents VIP conflicts
