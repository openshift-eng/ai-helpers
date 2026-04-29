# Tier 1 Ecosystem References

This document links to generic OpenShift/Kubernetes patterns in the Tier 1 ecosystem hub. The component inherits these platform-wide patterns and practices.

## Operator Patterns

**Location**: [ai-docs/platform/operator-patterns/](https://github.com/openshift/enhancements/tree/master/ai-docs/platform/operator-patterns)

- **Controller Runtime**: Reconciliation loops, event handling, client patterns
- **Status Conditions**: Available, Progressing, Degraded condition semantics
- **Webhooks**: Validation and mutation patterns
- **Finalizers**: Resource cleanup patterns
- **RBAC**: Service account and permissions

**Component Usage**:
- [Describe how this component uses these patterns]

## Testing Practices

**Location**: [ai-docs/practices/testing/](https://github.com/openshift/enhancements/tree/master/ai-docs/practices/testing)

- **Test Pyramid**: Unit > Integration > E2E ratio (60/30/10)
- **E2E Framework**: OpenShift E2E test patterns

**Component Usage**:
- See `[COMPONENT]_TESTING.md` for component-specific test suites

## Security Practices

**Location**: [ai-docs/practices/security/](https://github.com/openshift/enhancements/tree/master/ai-docs/practices/security)

- **STRIDE Threat Model**: Threat modeling framework
- **RBAC Guidelines**: Role and ClusterRole design

**Component Usage**:
- [Describe component-specific security considerations]

## Reliability Practices

**Location**: [ai-docs/practices/reliability/](https://github.com/openshift/enhancements/tree/master/ai-docs/practices/reliability)

- **SLO Framework**: Service Level Objectives and error budgets
- **Observability**: Metrics, logging, tracing patterns

**Component Usage**:
- [Describe component-specific reliability patterns]

## Kubernetes Fundamentals

**Location**: [ai-docs/domain/kubernetes/](https://github.com/openshift/enhancements/tree/master/ai-docs/domain/kubernetes)

- **Pod**: Pod lifecycle, container specs
- **CRDs**: CustomResourceDefinition patterns

**Component Usage**:
- [Describe how component uses Kubernetes fundamentals]

## OpenShift Fundamentals

**Location**: [ai-docs/domain/openshift/](https://github.com/openshift/enhancements/tree/master/ai-docs/domain/openshift)

- **ClusterOperator**: Cluster operator status reporting
- **ClusterVersion**: Platform upgrade orchestration

**Component Usage**:
- [Describe how component integrates with platform]

## Cross-Repository ADRs

**Location**: [ai-docs/decisions/](https://github.com/openshift/enhancements/tree/master/ai-docs/decisions)

Platform-wide architectural decisions:
- **etcd Backend**: Why etcd is used for Kubernetes state
- **CVO Orchestration**: Why CVO orchestrates upgrades
- **Immutable Nodes**: Why RHCOS + rpm-ostree

**Component-Specific ADRs**: See `ai-docs/decisions/` for component-specific decisions

---

**Note**: These links point to Tier 1 (ecosystem hub) documentation. Component-specific patterns and decisions are documented in the `ai-docs/` directory of this repository.

**Last Updated**: YYYY-MM-DD
