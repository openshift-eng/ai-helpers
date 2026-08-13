# Test Fixtures

This directory contains sample NetworkPolicy YAML files used for testing, documentation, and examples.

## Purpose

The fixtures serve multiple purposes:

1. **Documentation Examples** - Show real-world NetworkPolicy patterns
2. **Manual Testing** - Quick policy files for testing analyzer functionality
3. **CI/CD Testing** - Reference policies for automated tests
4. **Learning Resources** - Demonstrate valid and invalid patterns

## Directory Structure

```
fixtures/
├── valid/                  # Correctly configured policies
│   ├── default-deny-ingress.yaml
│   ├── namespace-isolation.yaml
│   ├── allow-dns.yaml
│   └── three-tier-app.yaml
└── invalid/                # Policies with security issues
    ├── overly-permissive-ingress.yaml
    ├── public-internet-exposure.yaml
    └── empty-pod-selector.yaml
```

---

## Valid Policies

### 1. default-deny-ingress.yaml

**Purpose:** Baseline security pattern - deny all ingress by default

**Pattern:**
```yaml
spec:
  podSelector: {}
  policyTypes:
  - Ingress
```

**Security Level:** ✅ High (best practice)

**When to Use:**
- First policy in any namespace
- Zero-trust baseline
- Compliance requirement

---

### 2. namespace-isolation.yaml

**Purpose:** Allow traffic from specific namespace with pod selector

**Pattern:**
```yaml
spec:
  podSelector:
    matchLabels:
      tier: backend
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          tier: frontend
      podSelector:
        matchLabels:
          tier: frontend
```

**Security Level:** ✅ High

**When to Use:**
- Multi-tier applications
- Cross-namespace communication
- Service mesh patterns

**Bug Fix Verification:** BUG-001 (false positives on valid namespace+pod selectors)

---

### 3. allow-dns.yaml

**Purpose:** Allow DNS resolution to kube-dns/coredns

**Pattern:**
```yaml
spec:
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
```

**Security Level:** ✅ High

**When to Use:**
- After applying default-deny egress
- DNS resolution needed
- Name-based service discovery

**Note:** Prevents the DNS blocking issue found in templates/default-deny-all.yaml

---

### 4. three-tier-app.yaml

**Purpose:** Backend tier isolation in three-tier architecture

**Pattern:**
```yaml
spec:
  podSelector:
    matchLabels:
      tier: backend
  ingress:
  - from:
    - podSelector:
        matchLabels:
          tier: frontend
```

**Security Level:** ✅ Medium-High

**When to Use:**
- Three-tier applications (frontend → backend → database)
- Microservices isolation
- Least privilege access

**Bug Fix Verification:** BUG-001 (correct pod selector handling)

---

## Invalid Policies

### 1. overly-permissive-ingress.yaml

**Issue:** Empty from[] list allows ALL traffic

**Problem:**
```yaml
ingress:
- from: []  # Allows ANY source
```

**Expected Finding:** CRITICAL - Overly permissive ingress rule

**Test Case:** TC-INV-002

**Security Impact:**
- Defeats purpose of NetworkPolicy
- Allows unauthorized access
- Violates zero-trust principles

---

### 2. public-internet-exposure.yaml

**Issue:** Allows egress to 0.0.0.0/0 (entire internet)

**Problem:**
```yaml
egress:
- to:
  - ipBlock:
      cidr: 0.0.0.0/0
```

**Expected Finding:** CRITICAL - Public internet egress exposure

**Test Cases:** TC-INV-003, TC-INV-004

**Bug Fix Verification:** BUG-002 (improved public exposure messages)

**Security Impact:**
- Data exfiltration risk
- Command & control channels
- Compliance violations

---

### 3. empty-pod-selector.yaml

**Issue:** Empty podSelector{} without documentation annotation

**Problem:**
```yaml
spec:
  podSelector: {}  # Applies to ALL pods
  # Missing annotation explaining why
```

**Expected Finding:** WARNING - Empty podSelector without documentation

**Bug Fix Verification:** BUG-003 (warn on missing annotation)

**Security Impact:**
- Unclear intent (mistake vs deliberate?)
- Maintenance confusion
- Audit trail gap

---

## Using Fixtures

### Manual Testing

```bash
# Analyze a valid policy
python3 scripts/netpol_analyzer_cli.py --file tests/fixtures/valid/default-deny-ingress.yaml

# Analyze an invalid policy (should find issues)
python3 scripts/netpol_analyzer_cli.py --file tests/fixtures/invalid/overly-permissive-ingress.yaml
```

### Apply to Test Cluster

```bash
# Create test namespace
oc create namespace test-fixtures

# Apply valid policy
oc apply -f tests/fixtures/valid/default-deny-ingress.yaml -n test-fixtures

# Analyze namespace
python3 scripts/netpol_analyzer_cli.py --namespace=test-fixtures --mode=security
```

### CI/CD Testing

```yaml
- name: Test analyzer on known-good policies
  run: |
    for file in tests/fixtures/valid/*.yaml; do
      python3 scripts/netpol_analyzer_cli.py --file "$file"
      # Should exit 0 (no critical findings)
    done

- name: Test analyzer on known-bad policies
  run: |
    for file in tests/fixtures/invalid/*.yaml; do
      python3 scripts/netpol_analyzer_cli.py --file "$file" || true
      # Should exit 1 (critical findings expected)
    done
```

---

## Adding New Fixtures

### For Valid Policies

1. **Create YAML file** in `valid/` with descriptive name
2. **Add annotations** explaining the pattern:
   ```yaml
   metadata:
     annotations:
       policy.kubernetes.io/description: "Purpose of this policy"
   ```
3. **Update this README** with pattern description
4. **Reference from tests** if verifying a bug fix

### For Invalid Policies

1. **Create YAML file** in `invalid/` with issue name
2. **Add comment** explaining the security flaw:
   ```yaml
   # INSECURE: Reason this is problematic
   ```
3. **Document expected finding** in this README
4. **Create integration test** to verify detection

---

## Pattern Categories

### Security Patterns (Valid)

- ✅ Default-deny baseline
- ✅ Namespace isolation
- ✅ Pod-to-pod restriction
- ✅ DNS egress allowlist
- ✅ External API allowlist

### Anti-Patterns (Invalid)

- ❌ Empty peer lists (from[] or to[])
- ❌ Public internet exposure (0.0.0.0/0)
- ❌ Undocumented empty selectors
- ❌ Missing default-deny baseline
- ❌ Overly broad selectors

---

## Verification

All fixtures are referenced by integration tests in `tests/integration/`:

**Valid Policy Tests:**
- TC-VNP-001: default-deny-ingress pattern
- TC-VNP-002: namespace-isolation pattern (BUG-001)
- TC-VNP-004: three-tier-app pattern (BUG-001)

**Invalid Policy Tests:**
- TC-INV-002: overly-permissive-ingress (empty from[])
- TC-INV-003: public-internet-exposure ingress (BUG-002)
- TC-INV-004: public-internet-exposure egress (BUG-002)
- TC-INV-007: empty-pod-selector (BUG-003)

---

## Quick Reference

| File | Type | Purpose | Test Case | Bug Fix |
|------|------|---------|-----------|---------|
| default-deny-ingress.yaml | Valid | Baseline security | TC-VNP-001 | - |
| namespace-isolation.yaml | Valid | Cross-NS communication | TC-VNP-002 | BUG-001 |
| allow-dns.yaml | Valid | DNS resolution | - | Template |
| three-tier-app.yaml | Valid | Tier isolation | TC-VNP-004 | BUG-001 |
| overly-permissive-ingress.yaml | Invalid | Empty from[] | TC-INV-002 | - |
| public-internet-exposure.yaml | Invalid | 0.0.0.0/0 egress | TC-INV-003/004 | BUG-002 |
| empty-pod-selector.yaml | Invalid | Missing annotation | TC-INV-007 | BUG-003 |

---

## Notes

- All fixtures use best-practice YAML formatting
- Comments explain the security implications
- Annotations provide policy descriptions
- Files are ready for kubectl/oc apply
- Fixtures are kept minimal (focused on one pattern each)

**Last Updated:** July 3, 2026  
**Maintained By:** NetworkPolicy Audit Plugin Team
