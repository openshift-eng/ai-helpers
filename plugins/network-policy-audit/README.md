# NetworkPolicy Audit Plugin

Automated NetworkPolicy review, optimization, and compliance analysis for OpenShift/Kubernetes clusters.

## Overview

This plugin provides AI-assisted NetworkPolicy analysis to detect security vulnerabilities, performance issues, and compliance violations **before** they cause production incidents.

## Features

- **Security Analysis** - Detect misconfigurations, overly permissive rules, public exposure
- **Performance Optimization** - Identify redundant policies, estimate OVN ACL impact
- **Compliance Checking** - Validate zero-trust architecture, baseline drift detection
- **Connectivity Testing** - Predict if traffic is allowed without deploying test pods
- **Visual Topology** - Generate network diagrams (Mermaid, DOT, ASCII)
- **Policy Optimization** - Suggest consolidation to reduce ACL complexity

## Installation

### Via Claude Code

```bash
# Add ai-helpers marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install plugin
/plugin install network-policy-audit
```

### Manual Installation

```bash
# Clone ai-helpers repository
git clone https://github.com/openshift-eng/ai-helpers.git
cd ai-helpers/plugins/network-policy-audit

# Install dependencies
pip install -r requirements.txt

# Set up kubeconfig
export KUBECONFIG=~/.kube/config
# or
oc login https://api.your-cluster.com:6443
```

## Commands

### 1. Analyze NetworkPolicies

Comprehensive health check for security, performance, and compliance.

```bash
# Security analysis (default)
/network-policy-audit:analyze production

# Performance analysis
/network-policy-audit:analyze production --mode=performance

# Compliance check
/network-policy-audit:analyze production --mode=compliance

# Cluster-wide analysis
/network-policy-audit:analyze --cluster-wide --mode=security
```

**Example Output:**

```
NetworkPolicy Security Audit - namespace: production

🔴 CRITICAL ISSUES (2)
  ├─ Missing default-deny ingress policy
  └─ Public internet ingress allowed (policy: allow-external)

⚠️  WARNINGS (3)
  ├─ Overly permissive egress (policy: backend-egress)
  ├─ Redundant policies detected
  └─ High ACL count (47 entries, threshold: 50)

✅ PASSED (5)
  ├─ Default-deny egress policy present
  └─ All policies have documentation annotations

📊 STATISTICS
  Total policies: 12
  Security score: 68/100
```

### 2. Test Connectivity

Predict if traffic is allowed between pods based on NetworkPolicy evaluation.

```bash
# Test pod-to-pod connectivity
/network-policy-audit:test-connectivity \
  pod/frontend-abc \
  pod/backend-xyz \
  --port=8080

# Test pod-to-service connectivity
/network-policy-audit:test-connectivity \
  pod/app-pod \
  svc/postgres-db \
  --port=5432 \
  --protocol=tcp
```

**Example Output:**

```
Testing Connectivity:
  Source: pod/frontend-abc (namespace: production)
  Dest:   pod/backend-xyz (namespace: production)
  Port:   8080/tcp

✅ ALLOWED

Policy Chain:
  1. Source egress: Allowed by 'frontend-egress'
  2. Dest ingress: Allowed by 'backend-ingress'
```

### 3. Visualize Network Topology

Generate visual diagrams showing allowed traffic flows.

```bash
# Mermaid diagram (for GitHub/GitLab)
/network-policy-audit:visualize production --format=mermaid

# ASCII diagram (for terminal)
/network-policy-audit:visualize production --format=ascii

# Graphviz DOT (for rendering)
/network-policy-audit:visualize production --format=dot
```

### 4. Optimize Policies

Suggest policy consolidation and ACL reduction.

```bash
# Preview optimization suggestions
/network-policy-audit:optimize production --dry-run

# Generate optimized YAML files
/network-policy-audit:optimize production --apply
```

### 5. Detect Drift

Compare NetworkPolicies against approved baseline.

```bash
# Compare against baseline template
/network-policy-audit:detect-drift production \
  --baseline=./security-templates/zero-trust-baseline.yaml
```

## Use Cases

### Pre-Deployment Validation

```bash
# Before deploying to production
kubectl apply -f new-policies.yaml -n staging
/network-policy-audit:analyze staging --mode=security

# If no critical issues, proceed to prod
kubectl apply -f new-policies.yaml -n production
```

### Troubleshooting Connectivity

```bash
# User reports: "Service A can't reach Service B"
/network-policy-audit:test-connectivity pod/service-a pod/service-b --port=443

# Output shows which policy is blocking and how to fix
```

### Quarterly Security Audits

```bash
# Generate compliance report
/network-policy-audit:analyze --cluster-wide --mode=compliance > audit-report.txt

# Check drift from approved baseline
for ns in prod staging; do
  /network-policy-audit:detect-drift $ns --baseline=approved-policies/$ns.yaml
done
```

### Performance Optimization

```bash
# Identify high-ACL namespaces
/network-policy-audit:analyze --cluster-wide --mode=performance

# Optimize problematic namespace
/network-policy-audit:optimize analytics --apply

# Result: 67 ACLs → 28 ACLs (58% reduction)
```

## Architecture

```
┌─────────────────────┐
│  Your Machine       │  ← Plugin runs here (client-side)
│  (laptop/bastion)   │
└──────────┬──────────┘
           │
           │ HTTPS API (via kubeconfig)
           │
           ↓
┌─────────────────────┐
│  Kubernetes Cluster │  ← Plugin analyzes this (remote)
│  (AWS/Azure/GCP/...)│
└─────────────────────┘
```

**Key Points:**
- **Client-side execution** (like kubectl/oc)
- **Read-only access** (no cluster changes)
- **Cloud-agnostic** (works with any Kubernetes cluster)
- **No cluster installation** required

## Cloud Compatibility

| Cloud Provider | Compatible |
|----------------|------------|
| AWS (ROSA, EKS, self-managed) | ✅ Yes |
| Azure (AKS, ARO) | ✅ Yes |
| GCP (GKE) | ✅ Yes |
| Bare-metal / On-prem | ✅ Yes |
| Hybrid / Multi-cloud | ✅ Yes |

## Required Permissions

Minimum RBAC permissions needed:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: network-policy-auditor
rules:
  - apiGroups: ["networking.k8s.io"]
    resources: ["networkpolicies"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["pods", "services", "namespaces"]
    verbs: ["get", "list"]
```

**Note:** Read-only access only. No write permissions required.

## CI/CD Integration

### GitHub Actions Example

```yaml
name: NetworkPolicy Audit

on:
  pull_request:
    paths:
      - 'k8s/networkpolicies/**'

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install plugin
        run: |
          pip install claude-code
          claude plugin install network-policy-audit
      
      - name: Run analysis
        run: |
          claude run "/network-policy-audit:analyze production --mode=security"
```

## Development

### Project Structure

```
network-policy-audit/
├── .claude-plugin/
│   └── plugin.json                 # Plugin metadata
├── commands/
│   ├── analyze.md                  # Analyze command spec
│   ├── test-connectivity.md        # Connectivity test spec
│   └── visualize.md                # Visualization spec
├── scripts/
│   ├── netpol_parser.py           # Kubernetes API client
│   ├── policy_analyzer.py         # Security analysis engine
│   └── netpol_analyzer_cli.py     # CLI entry point
├── templates/
│   └── default-deny-all.yaml      # Example templates
├── tests/
│   └── fixtures/                   # Test data
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

### Running Tests

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run tests
pytest tests/

# Run with coverage
pytest --cov=scripts tests/
```

### Testing Against Your Cluster

```bash
# Set kubeconfig
export KUBECONFIG=~/path/to/kubeconfig

# Run CLI directly
cd scripts/
python3 netpol_analyzer_cli.py --namespace=default --mode=security
```

## Troubleshooting

### "Kubernetes API connection failed"

**Solution:**
```bash
# Check kubeconfig
echo $KUBECONFIG

# Or login
oc login https://api.cluster.example.com:6443
```

### "Permission denied"

**Solution:**
```bash
# Check your permissions
oc auth can-i list networkpolicies --all-namespaces

# Request cluster role binding
oc create clusterrolebinding netpol-auditor \
  --clusterrole=network-policy-auditor \
  --user=$(oc whoami)
```

### "No NetworkPolicies found"

**Answer:** This is a valid finding! It indicates a security risk (no policies = all traffic allowed).

## Contributing

Contributions welcome! This plugin was created during Swift Week 2026.

**Author:** Shreyas Be <shbehera@redhat.com>

## Related Resources

- [Kubernetes NetworkPolicy Documentation](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [OpenShift NetworkPolicy Guide](https://docs.openshift.com/container-platform/latest/networking/network_policy/about-network-policy.html)
- [OVN-Kubernetes Architecture](https://ovn-kubernetes.io/design/architecture/)

## License

Apache License 2.0 (consistent with ai-helpers repository)
