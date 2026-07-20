# Enable autoscaling configuration for clusters

**Project:** CNTRLPLANE
**Type:** Story
**Component:** HyperShift
**Version:** openshift-4.16
**Priority:** High

## User Story

As a cluster admin, I want to configure autoscaling for my HyperShift-managed clusters, so that I can automatically handle traffic spikes without manual intervention.

## Acceptance Criteria

- [ ] Node pools scale up when average CPU utilization exceeds 80% for 5 minutes
- [ ] Node pools scale down when average CPU utilization drops below 30% for 10 minutes
- [ ] Scaling operations respect configured min/max node limits
- [ ] Scaling events are logged and visible in cluster audit logs
- [ ] Autoscaling can be enabled/disabled per node pool via CLI and UI

## Context

Currently, cluster admins must manually scale node pools by adjusting replica counts. This leads to:
- Over-provisioning (wasted resources during low traffic)
- Under-provisioning (degraded performance during traffic spikes)
- Operational overhead (24/7 monitoring required)

Competitors (EKS, GKE, AKS) all provide native autoscaling. We need parity.

## Technical Notes

Implementation should use:
- Kubernetes Cluster Autoscaler for node-level scaling
- HorizontalPodAutoscaler for pod-level scaling
- Custom metrics from Prometheus for scaling decisions

Integration points:
- CNTRLPLANE-100 — Metrics collection pipeline must be deployed
- CNTRLPLANE-101 — IAM permissions for node provisioning required

## Testing Notes

Test scenarios:
1. Gradual load increase (5% CPU → 95% CPU over 30 minutes)
2. Sudden load spike (10% → 90% in 1 minute)
3. Scale-down behavior after traffic drop
4. Min/max limit enforcement
5. Multiple concurrent node pools with different configs
