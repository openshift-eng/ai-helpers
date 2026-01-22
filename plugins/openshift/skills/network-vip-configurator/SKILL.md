---
name: Network VIP Configurator
description: Configure network VIPs and DNS records for OpenShift vSphere installations with automated subnet scanning and DNS verification
---

# Network VIP Configurator Skill

This skill manages network VIP (Virtual IP) configuration and DNS record setup for OpenShift vSphere installations. It handles subnet scanning, VIP selection, DNS record creation (Route53 or manual), and DNS verification.

## When to Use This Skill

Use this skill when you need to:
- Find available IP addresses in a subnet for API and Ingress VIPs
- Configure DNS records for OpenShift cluster endpoints
- Verify DNS resolution before installation
- Automate VIP selection from subnet CIDR
- Support both Route53 (automated) and manual DNS workflows

**Why use this skill?**
- **Automation**: Scans subnet to find available IPs automatically
- **Validation**: Verifies IPs are not in use (ping + Route53 check)
- **DNS Management**: Creates and verifies DNS records
- **Flexibility**: Supports Route53 or manual DNS setup
- **Error Prevention**: Reduces VIP conflicts and DNS issues

This skill is used by:
- `/openshift:install-vsphere` - For network and VIP configuration (Phase 2, step 5)
- `/openshift:create-cluster` - For automated cluster provisioning

## Prerequisites

Before starting, ensure these tools are available:

1. **Python 3**
   - Check if available: `which python3`
   - Required for subnet scanning
   - Usually pre-installed on Linux and macOS

2. **dig (DNS lookup)**
   - Check if available: `which dig`
   - Required for DNS verification
   - Install if missing:
     - Linux: `sudo yum install bind-utils` or `sudo apt-get install dnsutils`
     - macOS: Pre-installed

3. **AWS CLI** (Optional - for Route53 integration)
   - Check if available: `which aws`
   - Only required if using Route53 for DNS
   - Skip if using manual DNS setup
   - Install: https://aws.amazon.com/cli/

4. **Network Access**
   - Ability to ping IPs in the subnet
   - Access to Route53 (if using automated DNS)

## Input Format

The user will provide:

1. **Subnet CIDR** - e.g., "10.0.0.0/24", "172.16.10.0/24"
2. **Cluster name** - e.g., "mycluster"
3. **Base domain** - e.g., "example.com", "devcluster.openshift.com"
4. **DNS mode**:
   - `route53`: Automated DNS record creation using AWS Route53
   - `manual`: User creates DNS records manually, we verify
5. **Route53 hosted zone ID** (if using Route53 mode, optional - can be auto-detected)

## Output Format

Return a structured result containing VIP and DNS information:

```json
{
  "api_vip": "10.0.0.100",
  "ingress_vip": "10.0.0.101",
  "dns_mode": "route53",
  "dns_verified": true,
  "dns_records": [
    "api.mycluster.example.com → 10.0.0.100",
    "api-int.mycluster.example.com → 10.0.0.100",
    "*.apps.mycluster.example.com → 10.0.0.101"
  ],
  "zone_id": "Z1234567890ABC"
}
```

## Implementation Steps

### Step 1: Determine DNS Mode

Ask the user which DNS mode they want to use:

```
How would you like to configure DNS for the cluster?

1. Route53 (Automated) - Automatically create DNS records in AWS Route53
2. Manual - You will create DNS records manually, and we'll verify them

Recommended: Route53 if you have AWS access
```

**Set DNS_MODE based on user's choice:**
- `route53` - We will create DNS records automatically
- `manual` - User creates DNS records, we verify

### Step 2: Get Subnet CIDR

The subnet CIDR should be obtained from the user or from vSphere network discovery. This is the machine network CIDR associated with the port group.

Example: "10.0.0.0/24" or "172.16.10.0/24"

### Step 3: Scan Subnet for Available IPs

Use the Python scanner to find available IP addresses:

```bash
# Scan subnet for available IPs
# The script will:
# - Ping each IP to check if it responds
# - Check Route53 for existing A records (if zone ID provided)
# - Return list of available IPs

AVAILABLE_IPS=$(python3 plugins/openshift/skills/network-vip-configurator/scan-available-ips.py \
  "${SUBNET_CIDR}" \
  --max-candidates 10 \
  --skip-first 10 \
  --skip-last 10 \
  --verbose)

# Parse JSON to get list of available IPs
echo "$AVAILABLE_IPS" | jq -r '.[].ip'
```

**With Route53 Integration (optional):**
If Route53 zone ID is known, include it to check for existing DNS records:

```bash
ZONE_ID=$(bash plugins/openshift/skills/network-vip-configurator/manage-dns.sh get-zone-id --domain "${BASE_DOMAIN}")

AVAILABLE_IPS=$(python3 plugins/openshift/skills/network-vip-configurator/scan-available-ips.py \
  "${SUBNET_CIDR}" \
  --zone-id "${ZONE_ID}" \
  --max-candidates 10 \
  --verbose)
```

**Error Handling:**
- If no available IPs found: Suggest expanding CIDR or checking network
- If scan fails: Check network connectivity and permissions

### Step 4: Present Available IPs to User

Parse the JSON and present IPs in a user-friendly way:

```bash
# Parse available IPs
AVAILABLE_IPS_LIST=$(echo "$AVAILABLE_IPS" | jq -r '.[].ip')

# Count available IPs
AVAILABLE_COUNT=$(echo "$AVAILABLE_IPS" | jq 'length')

if [ "$AVAILABLE_COUNT" -lt 2 ]; then
  echo "Error: Need at least 2 available IPs (one for API, one for Ingress)"
  echo "Found only $AVAILABLE_COUNT available IP(s)"
  exit 1
fi

echo "Found $AVAILABLE_COUNT available IP addresses in subnet $SUBNET_CIDR:"
echo "$AVAILABLE_IPS_LIST"
```

Use `AskUserQuestion` tool to present dropdowns for:
1. **API VIP** - Select from available IPs
2. **Ingress VIP** - Select from remaining available IPs (different from API VIP)

**Important:** API VIP and Ingress VIP must be different IPs!

### Step 5: Configure DNS Records

Based on DNS_MODE, either create Route53 records or guide user to create manual DNS.

#### Option A: Route53 Mode (Automated)

```bash
# Create Route53 DNS records
# The script will:
# - Auto-detect or use provided hosted zone ID
# - Create/update A records for api, api-int, *.apps
# - Return zone ID for reference

ZONE_ID=$(bash plugins/openshift/skills/network-vip-configurator/manage-dns.sh create-route53 \
  --cluster-name "${CLUSTER_NAME}" \
  --base-domain "${BASE_DOMAIN}" \
  --api-vip "${API_VIP}" \
  --ingress-vip "${INGRESS_VIP}")

echo "DNS records created in Route53 zone: $ZONE_ID"
```

**What this creates:**
- `api.${CLUSTER_NAME}.${BASE_DOMAIN}` → API VIP
- `api-int.${CLUSTER_NAME}.${BASE_DOMAIN}` → API VIP
- `*.apps.${CLUSTER_NAME}.${BASE_DOMAIN}` → Ingress VIP

**Error Handling:**
- AWS credentials not configured: Guide user to run `aws configure`
- Zone not found: List available zones and ask user to select
- Permission denied: Verify IAM permissions for Route53

#### Option B: Manual Mode

Guide the user to create DNS records manually:

```
Please create the following DNS A records in your DNS provider:

  api.${CLUSTER_NAME}.${BASE_DOMAIN} → ${API_VIP}
  api-int.${CLUSTER_NAME}.${BASE_DOMAIN} → ${API_VIP}
  *.apps.${CLUSTER_NAME}.${BASE_DOMAIN} → ${INGRESS_VIP}

These records are required for the OpenShift installer to function correctly.

Press ENTER when you have created the DNS records and they have propagated...
```

Wait for user confirmation before proceeding to verification.

### Step 6: Verify DNS Records

Always verify DNS records resolve correctly, regardless of DNS mode:

```bash
# Verify DNS records using dig
# The script will:
# - Query each DNS record (api, api-int, *.apps)
# - Verify they resolve to expected VIPs
# - Wait for DNS propagation (up to timeout)
# - Return success if all records verified

bash plugins/openshift/skills/network-vip-configurator/manage-dns.sh verify \
  --cluster-name "${CLUSTER_NAME}" \
  --base-domain "${BASE_DOMAIN}" \
  --api-vip "${API_VIP}" \
  --ingress-vip "${INGRESS_VIP}" \
  --timeout 60

if [ $? -eq 0 ]; then
  echo "✓ All DNS records verified successfully"
else
  echo "✗ DNS verification failed"
  echo "Please check DNS records and wait for propagation"
  exit 1
fi
```

**What is verified:**
1. `api.${CLUSTER_NAME}.${BASE_DOMAIN}` resolves to API VIP
2. `api-int.${CLUSTER_NAME}.${BASE_DOMAIN}` resolves to API VIP
3. `test.apps.${CLUSTER_NAME}.${BASE_DOMAIN}` resolves to Ingress VIP (wildcard test)

**Timeout and Retry:**
- Default timeout: 60 seconds
- Checks every 5 seconds
- Displays progress to user
- If timeout reached, suggest waiting longer or checking DNS provider

**Error Handling:**
- DNS not resolving: Wait longer or check DNS provider
- Resolves to wrong IP: Verify DNS records are correct
- Wildcard not working: Check DNS provider supports wildcard records

### Step 7: Return Results

Compile all information and return as structured data:

```bash
# Create result JSON
cat > /tmp/network-vip-result.json <<EOF
{
  "api_vip": "${API_VIP}",
  "ingress_vip": "${INGRESS_VIP}",
  "machine_network_cidr": "${SUBNET_CIDR}",
  "dns_mode": "${DNS_MODE}",
  "dns_verified": true,
  "dns_records": [
    "api.${CLUSTER_NAME}.${BASE_DOMAIN} → ${API_VIP}",
    "api-int.${CLUSTER_NAME}.${BASE_DOMAIN} → ${API_VIP}",
    "*.apps.${CLUSTER_NAME}.${BASE_DOMAIN} → ${INGRESS_VIP}"
  ],
  "zone_id": "${ZONE_ID:-null}"
}
EOF

# Display summary to user
echo "=== Network and VIP Configuration Complete ==="
cat /tmp/network-vip-result.json | jq .

# Return result
cat /tmp/network-vip-result.json
```

## Advanced Features

### Custom IP Range Scanning

If the user wants to scan a specific IP range:

```bash
# Scan specific range with custom skip values
python3 scan-available-ips.py 10.0.0.0/24 \
  --skip-first 50 \
  --skip-last 5 \
  --max-candidates 20
```

### Parallel Scanning for Large Subnets

For large subnets (/16 or larger), increase max-workers:

```bash
# Faster scanning with more parallel workers
python3 scan-available-ips.py 10.0.0.0/16 \
  --max-workers 50 \
  --max-candidates 10
```

### Custom DNS TTL

For development/testing, use lower TTL:

```bash
# Create records with 60-second TTL
bash manage-dns.sh create-route53 \
  --cluster-name test \
  --base-domain example.com \
  --api-vip 10.0.0.100 \
  --ingress-vip 10.0.0.101 \
  --ttl 60
```

## Error Handling

### Subnet Scanning Errors

**No Available IPs Found**
```
Error: Found 0 available IP addresses
```

**Solution:**
- Subnet may be too small or fully allocated
- Try different subnet
- Reduce skip-first/skip-last values
- Check if network is correct

**Ping Permission Errors**
```
Warning: Some ping operations may have failed
```

**Solution:**
- User may not have ICMP permissions
- Results still valid (Route53 check still works)
- Firewall may block ping

### DNS Creation Errors (Route53)

**AWS Credentials Not Configured**
```
Error: AWS credentials not configured
```

**Solution:**
- Run `aws configure`
- Provide access key and secret key
- Or use IAM role if on EC2/ECS

**Hosted Zone Not Found**
```
Error: No hosted zone found for domain: example.com
```

**Solution:**
- Verify domain spelling
- Check if zone exists in Route53
- User may not have permission to list zones
- List available zones: `aws route53 list-hosted-zones`

**Permission Denied**
```
Error: User is not authorized to perform route53:ChangeResourceRecordSets
```

**Solution:**
- Verify IAM permissions
- User needs Route53 write access
- Required permission: `route53:ChangeResourceRecordSets`

### DNS Verification Errors

**DNS Not Resolving**
```
Error: DNS verification failed after 60s timeout
```

**Solution:**
- DNS may still be propagating (can take minutes to hours)
- Increase timeout: `--timeout 300`
- Check DNS provider for propagation status
- Verify records were created correctly

**Resolving to Wrong IP**
```
Warning: api.cluster.example.com → 10.0.0.200 (expected: 10.0.0.100)
```

**Solution:**
- DNS record may be incorrect
- Check for cached/stale DNS records
- Flush DNS cache: `sudo systemd-resolve --flush-caches` (Linux)
- Wait for TTL expiration
- Verify correct IP in DNS provider

**dig Command Not Found**
```
Error: dig command not found
```

**Solution:**
- Install bind-utils (RHEL/CentOS): `sudo yum install bind-utils`
- Install dnsutils (Debian/Ubuntu): `sudo apt-get install dnsutils`
- dig is pre-installed on macOS

## Integration with install-vsphere

The VIPs returned by this skill should be used in the install-config.yaml:

```yaml
platform:
  vsphere:
    apiVIP: 10.0.0.100        # ← API VIP from this skill
    ingressVIP: 10.0.0.101    # ← Ingress VIP from this skill

networking:
  machineNetwork:
  - cidr: 10.0.0.0/24         # ← Subnet CIDR from this skill
```

DNS records created/verified by this skill enable the installer to access the cluster API during installation.

## Example Workflows

### Workflow 1: Route53 (Fully Automated)

```bash
# 1. Scan subnet for available IPs
AVAILABLE_IPS=$(python3 scan-available-ips.py 10.0.0.0/24 --verbose)

# 2. User selects API VIP and Ingress VIP from available IPs
API_VIP="10.0.0.100"
INGRESS_VIP="10.0.0.101"

# 3. Create Route53 DNS records
bash manage-dns.sh create-route53 \
  --cluster-name mycluster \
  --base-domain example.com \
  --api-vip "$API_VIP" \
  --ingress-vip "$INGRESS_VIP"

# 4. Verify DNS records
bash manage-dns.sh verify \
  --cluster-name mycluster \
  --base-domain example.com \
  --api-vip "$API_VIP" \
  --ingress-vip "$INGRESS_VIP"

# 5. Success! VIPs configured and DNS verified
echo "VIPs ready: API=$API_VIP, Ingress=$INGRESS_VIP"
```

### Workflow 2: Manual DNS

```bash
# 1. Scan subnet for available IPs
AVAILABLE_IPS=$(python3 scan-available-ips.py 10.0.0.0/24 --verbose)

# 2. User selects VIPs
API_VIP="10.0.0.100"
INGRESS_VIP="10.0.0.101"

# 3. Guide user to create DNS records
echo "Please create these DNS A records in your DNS provider:"
echo "  api.mycluster.example.com → $API_VIP"
echo "  api-int.mycluster.example.com → $API_VIP"
echo "  *.apps.mycluster.example.com → $INGRESS_VIP"
read -p "Press ENTER when records are created..."

# 4. Verify DNS records
bash manage-dns.sh verify \
  --cluster-name mycluster \
  --base-domain example.com \
  --api-vip "$API_VIP" \
  --ingress-vip "$INGRESS_VIP" \
  --timeout 300  # Longer timeout for manual DNS

# 5. Success!
```

### Workflow 3: Pre-existing DNS Records

If the user already has DNS records created:

```bash
# 1. User provides VIPs (already in DNS)
API_VIP="10.0.0.100"
INGRESS_VIP="10.0.0.101"

# 2. Skip scanning and DNS creation, just verify
bash manage-dns.sh verify \
  --cluster-name mycluster \
  --base-domain example.com \
  --api-vip "$API_VIP" \
  --ingress-vip "$INGRESS_VIP"

# 3. If verification passes, use these VIPs
```

## Notes

- **IP Requirements**: Need exactly 2 IPs (API VIP and Ingress VIP)
- **Same Subnet**: Both VIPs must be in the same subnet
- **Different IPs**: API and Ingress VIPs must be different
- **DNS Propagation**: Can take 5 seconds to several minutes
- **Wildcard DNS**: Required for Ingress (*.apps.cluster.domain)
- **Security**: Never log AWS credentials

## Benefits

1. **Automation**: Eliminates manual IP hunting and ping testing
2. **Validation**: Ensures IPs are truly available before use
3. **Error Prevention**: Catches VIP conflicts before installation
4. **Flexibility**: Supports both Route53 and manual DNS
5. **Speed**: Parallel scanning for fast results
6. **Reliability**: Verifies DNS before proceeding to installation

## Performance

### Subnet Scanning

| Subnet Size | IPs to Scan | Time (20 workers) |
|-------------|-------------|-------------------|
| /24 (254 hosts) | 234 IPs | ~10-15 seconds |
| /23 (510 hosts) | 490 IPs | ~20-30 seconds |
| /22 (1022 hosts) | 1002 IPs | ~40-60 seconds |

**Note:** Scanning stops after finding enough candidates (default: 10)

### DNS Operations

| Operation | Time |
|-----------|------|
| Route53 record creation | 2-5 seconds |
| Route53 propagation | 5-30 seconds (usually instant) |
| Manual DNS propagation | Minutes to hours (varies by provider) |
| DNS verification (dig) | <1 second per record |

## Troubleshooting Tips

1. **Scan finds no IPs**: Check if network/CIDR is correct
2. **DNS creation fails**: Verify AWS credentials and permissions
3. **DNS verification fails**: Wait longer for propagation
4. **Wildcard doesn't work**: Some DNS providers require explicit wildcard setup
5. **VIP conflict after install**: Re-scan subnet, may have changed since initial scan
