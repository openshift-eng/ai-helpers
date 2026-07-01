---
description: "Comprehensive NetworkPolicy health check for security, performance, and compliance"
argument-hint: "[namespace|--cluster-wide] [--mode=security|performance|compliance]"
---

## Name
network-policy-audit:analyze

## Synopsis
```
/network-policy-audit:analyze [namespace|--cluster-wide] [--mode=security|performance|compliance]
```

## Description

Performs comprehensive analysis of NetworkPolicy objects to detect security vulnerabilities, performance issues, and compliance violations.

## Arguments

- `namespace` - Target namespace to analyze (default: current namespace)
- `--cluster-wide` - Analyze all namespaces in the cluster
- `--mode` - Analysis mode:
  - `security` (default) - Security vulnerabilities and best practices
  - `performance` - OVN ACL optimization and performance impact
  - `compliance` - Zero-trust and regulatory compliance checks

## Implementation

This command executes the NetworkPolicy analysis by:

1. **Fetching NetworkPolicies** from the cluster using Kubernetes API
2. **Parsing policy specifications** including selectors, rules, and policy types
3. **Running analysis checks** based on the selected mode
4. **Generating a detailed report** with findings, recommendations, and remediation steps

### Security Analysis Checks

- Default-deny ingress/egress policy detection
- Overly permissive rules (empty selectors)
- Public internet exposure (0.0.0.0/0 CIDRs)
- Empty podSelectors (potential misconfigurations)
- Missing policyTypes specifications
- Shadow policies (redundant/conflicting rules)

### Performance Analysis Checks

- OVN ACL entry count estimation
- Redundant policy detection
- Complex label selector analysis
- Policy count per namespace (scaling limits)
- Wildcard namespace selector impact

### Compliance Analysis Checks

- Zero-trust architecture compliance
- Default-deny coverage percentage
- Egress control coverage
- Policy documentation (annotations)
- Naming convention adherence
- Label selector standards

## Execution Steps

```bash
# Step 1: Parse arguments
NAMESPACE=""
CLUSTER_WIDE=""
MODE="security"

# Scan all arguments
for arg in "$@"; do
    case "$arg" in
        --cluster-wide)
            CLUSTER_WIDE="--cluster-wide"
            ;;
        --mode=*)
            MODE="${arg#*=}"
            ;;
        -*)
            # Skip other flags
            ;;
        *)
            # First non-flag argument is namespace
            if [ -z "$NAMESPACE" ] && [ -z "$CLUSTER_WIDE" ]; then
                NAMESPACE="$arg"
            fi
            ;;
    esac
done

# Set defaults
if [ -z "$CLUSTER_WIDE" ] && [ -z "$NAMESPACE" ]; then
    NAMESPACE="$(oc project -q)"
fi

# Step 2: Set up Python environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/scripts"
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH}"

# Step 3: Execute analysis
if [ -n "$CLUSTER_WIDE" ]; then
    python3 "${SCRIPT_DIR}/netpol_analyzer_cli.py" \
        --cluster-wide \
        --mode="${MODE}"
else
    python3 "${SCRIPT_DIR}/netpol_analyzer_cli.py" \
        --namespace="${NAMESPACE}" \
        --mode="${MODE}"
fi
```

## Example Outputs

### Security Mode

```
NetworkPolicy Security Audit - namespace: production
Generated: 2026-06-29 15:30:00

🔴 CRITICAL ISSUES (2)
  ├─ Missing default-deny ingress policy
  └─ Public internet ingress allowed (policy: allow-external)

⚠️  WARNINGS (3)
  ├─ Overly permissive egress (policy: backend-egress)
  ├─ Redundant policies detected
  └─ High ACL count (47 entries, threshold: 50)

✅ PASSED (5)
  ├─ Default-deny egress policy present
  ├─ All policies have documentation annotations
  └─ ... (3 more)

📊 STATISTICS
  ├─ Total policies: 12
  ├─ Pods covered: 156/160 (4 unprotected)
  ├─ Estimated OVN ACL count: 47
  └─ Security score: 68/100

🔧 RECOMMENDED ACTIONS
  1. Add default-deny ingress policy (CRITICAL)
  2. Restrict allow-external to specific CIDRs
  3. Merge redundant policies
```

### Performance Mode

```
NetworkPolicy Performance Analysis - Cluster-Wide

🚀 PERFORMANCE FINDINGS

HIGH ACL NAMESPACES (>50 ACLs):
  ├─ analytics: 67 ACLs (12 policies)
  ├─ monitoring: 58 ACLs (9 policies)
  └─ data-pipeline: 54 ACLs (15 policies)

OPTIMIZATION OPPORTUNITIES:
  ├─ 23 redundant policies (can merge to 11)
  ├─ 8 policies with complex selectors
  └─ 5 namespaces with >15 policies

ESTIMATED CLUSTER IMPACT:
  ├─ Current ACL count: 1,247
  ├─ Optimized ACL count: 823 (34% reduction)
  └─ OVN processing overhead: MEDIUM
```

## Error Handling

The command handles common error scenarios:

- **No kubeconfig access**: Prompts user to set KUBECONFIG or run `oc login`
- **Insufficient permissions**: Reports required RBAC permissions
- **No NetworkPolicies found**: Reports as valid finding (security risk)
- **Invalid namespace**: Lists available namespaces

## Best Practices

1. **Run security mode before deployment** to catch misconfigurations
2. **Use performance mode on high-traffic namespaces** to prevent ACL bloat
3. **Schedule compliance mode monthly** for audit trails
4. **Combine with test-connectivity** to validate fixes

## Related Commands

- `/network-policy-audit:test-connectivity` - Test if specific traffic is allowed
- `/network-policy-audit:optimize` - Generate optimized policy YAML
- `/network-policy-audit:detect-drift` - Compare against baseline
