---
description: Predict if traffic is allowed between pods/services based on NetworkPolicy evaluation
argument-hint: <source-pod> <dest-pod> --port=<port> [--protocol=tcp|udp]
---

# NetworkPolicy Test Connectivity Command

Evaluates NetworkPolicy rules to predict whether traffic would be allowed or denied between two pods or services without actually sending traffic.

## Usage

```bash
/network-policy-audit:test-connectivity <source> <destination> --port=<port> [--protocol=PROTOCOL]
```

## Arguments

- `source` - Source pod (format: `pod/name` or `namespace/pod/name`)
- `destination` - Destination pod or service (format: `pod/name`, `svc/name`)
- `--port` - Destination port number (required)
- `--protocol` - Protocol (tcp or udp, default: tcp)

## Implementation

This command performs policy evaluation by:

1. **Resolving pod references** from names to actual Pod objects
2. **Extracting pod labels** for selector matching
3. **Fetching all relevant NetworkPolicies** in source and destination namespaces
4. **Evaluating egress rules** on source namespace policies
5. **Evaluating ingress rules** on destination namespace policies
6. **Determining verdict** (both must allow for traffic to flow)
7. **Generating policy chain explanation** with remediation steps

## Execution Steps

```bash
# Parse arguments
SOURCE_POD="$1"
DEST_POD="$2"
PORT=""
PROTOCOL="tcp"

for arg in "$@"; do
    if [[ $arg == --port=* ]]; then
        PORT="${arg#*=}"
    elif [[ $arg == --protocol=* ]]; then
        PROTOCOL="${arg#*=}"
    fi
done

# Validate required arguments
if [ -z "$SOURCE_POD" ] || [ -z "$DEST_POD" ] || [ -z "$PORT" ]; then
    echo "Error: Missing required arguments"
    echo "Usage: /network-policy-audit:test-connectivity <source> <dest> --port=<port>"
    exit 1
fi

# Execute connectivity test
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/scripts"
python3 "${SCRIPT_DIR}/connectivity_tester_cli.py" \
    --source="${SOURCE_POD}" \
    --dest="${DEST_POD}" \
    --port="${PORT}" \
    --protocol="${PROTOCOL}"
```

## Example Outputs

### Traffic Allowed

```
Testing Connectivity:
  Source: pod/frontend-7d4f (namespace: production, IP: 10.128.2.45)
  Dest:   pod/backend-3a2c (namespace: production, IP: 10.128.2.78)
  Port:   8080/tcp

✅ ALLOWED

Policy Evaluation Chain:
  
  1. SOURCE EGRESS CHECK
     Policy: frontend-egress (production)
     Rule: Allow egress to podSelector app=backend on port 8080
     Verdict: ✅ ALLOWED
  
  2. DESTINATION INGRESS CHECK
     Policy: backend-ingress (production)
     Rule: Allow ingress from podSelector app=frontend on port 8080
     Verdict: ✅ ALLOWED
  
  3. FINAL VERDICT: ✅ ALLOWED

OVN ACL Details:
  ├─ ACL ID: acl-12345 (ingress, priority 1000)
  ├─ Match: ip4.src==10.128.2.45 && tcp.dst==8080
  └─ Action: allow-related
```

### Traffic Denied

```
Testing Connectivity:
  Source: pod/external-app-abc (namespace: external, IP: 10.129.1.22)
  Dest:   pod/database-xyz (namespace: production, IP: 10.128.3.50)
  Port:   5432/tcp

❌ DENIED

Policy Evaluation Chain:
  
  1. SOURCE EGRESS CHECK
     Default policy: No egress restrictions in namespace 'external'
     Verdict: ✅ ALLOWED
  
  2. DESTINATION INGRESS CHECK
     Policy: database-ingress (production)
     Rule: Allow ingress ONLY from podSelector app=backend
     Source pod labels: app=external-app (does not match)
     Verdict: ❌ DENIED
  
  3. FINAL VERDICT: ❌ DENIED

Reason for Denial:
  The database-ingress policy only allows traffic from pods with label 
  "app=backend". The source pod has label "app=external-app".

How to Allow This Connection:
  
  Option 1 (RECOMMENDED): Create specific policy for external access
    Apply: kubectl apply -f /tmp/allow-external-to-db.yaml
  
  Option 2: Modify database-ingress policy
    Add the following to spec.ingress[0].from:
      - namespaceSelector:
          matchLabels:
            name: external
        podSelector:
          matchLabels:
            app: external-app
```

## Use Cases

### 1. Pre-Deployment Validation

```bash
# Before deploying new service, test if it can reach dependencies
/network-policy-audit:test-connectivity \
  pod/new-service-xyz \
  svc/postgres-db \
  --port=5432
```

### 2. Troubleshooting Connectivity Issues

```bash
# User reports "frontend can't reach backend"
/network-policy-audit:test-connectivity \
  pod/frontend-abc \
  pod/backend-xyz \
  --port=8080

# Command explains exactly which policy is blocking
```

### 3. Post-Policy-Change Verification

```bash
# After modifying NetworkPolicy, verify critical paths still work
/network-policy-audit:test-connectivity pod/app pod/db --port=5432
/network-policy-audit:test-connectivity pod/app svc/cache --port=6379
/network-policy-audit:test-connectivity pod/app svc/kube-dns --port=53 --protocol=udp
```

## Error Handling

- **Pod not found**: Lists available pods in namespace
- **Service has no endpoints**: Reports service configuration issue
- **Invalid port**: Validates port range (1-65535)
- **Ambiguous pod name**: Requires namespace prefix

## Related Commands

- `/network-policy-audit:analyze` - Overall policy health check
- `/network-policy-audit:visualize` - See all allowed connections graphically
