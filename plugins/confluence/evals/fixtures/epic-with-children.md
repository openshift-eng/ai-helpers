## Issue

**Key:** PLAT-450
**Type:** Epic
**Status:** In Progress
**Priority:** High
**Summary:** Implement graceful shutdown for stateful workloads on SNO
**Reporter:** Engineering Lead
**Assignee:** Platform Team
**Created:** 2026-03-15
**Updated:** 2026-05-28
**Labels:** graceful-shutdown, sno, odf
**Components:** Platform, Storage

## Description

Single Node OpenShift (SNO) deployments with stateful workloads (ODF, databases) need a reliable graceful shutdown procedure. Currently, abrupt power loss or uncoordinated shutdown leads to:

- Ceph OSD corruption requiring manual recovery
- Database transaction log inconsistencies
- Extended recovery times (30+ minutes) on reboot

The goal is to implement a shutdown orchestration mechanism that:
1. Drains application workloads in dependency order
2. Flushes Ceph OSDs and marks them out
3. Stops ODF operators cleanly
4. Signals the OS to proceed with shutdown

### Success Criteria

- Shutdown completes within 5 minutes from signal to power-off
- Zero Ceph OSD corruption across 100 consecutive shutdown cycles
- Recovery time on reboot < 3 minutes
- Works with both planned shutdown (admin-initiated) and UPS-triggered shutdown

## Child Issues

### PLAT-451 — Design shutdown dependency graph (Story, Done)
Define the ordering of workload shutdown. Application pods first, then ODF consumers, then ODF operators, then Ceph. Document as a dependency DAG.

### PLAT-452 — Implement shutdown controller (Story, In Progress)
Kubernetes controller that watches for shutdown signal (node condition or custom resource) and orchestrates the drain sequence per the dependency graph from PLAT-451.

### PLAT-453 — Add Ceph OSD flush hook (Story, In Progress)
Pre-shutdown hook that calls `ceph osd set noout`, flushes journals, and waits for PG peering to complete before allowing OSD pods to terminate.

### PLAT-454 — Integration testing with power-cycle harness (Story, To Do)
Automated test suite using IPMI power-cycle to validate the shutdown sequence under realistic conditions. Must run 100 cycles and report OSD health.

### PLAT-455 — Documentation and runbook (Story, To Do)
Operator-facing documentation covering: configuration, troubleshooting stuck shutdowns, and manual recovery if automated shutdown fails.

## Linked Issues

- **Blocks:** NOKIA5GRAN-1050 (Nokia vCU graceful shutdown)
- **Related to:** ODF-890 (Ceph OSD recovery improvements)

## Comments

### Comment 1 — Storage Engineer (2026-04-10)
Tested the Ceph flush approach on a 3-node cluster first. The `noout` flag prevents rebalancing during planned shutdown. Key finding: we need to wait for all PGs to be `active+clean` before proceeding, not just check OSD status. Added a polling loop in PLAT-453.

### Comment 2 — Engineering Lead (2026-04-22)
Architecture review decision: the shutdown controller (PLAT-452) will use a CRD `ShutdownPlan` rather than annotations on the Node object. This keeps the dependency graph declarative and version-controlled. Updated the design doc in PLAT-451.

### Comment 3 — QA Lead (2026-05-15)
PLAT-454 needs access to the bare-metal lab for IPMI testing. I've requested the reservation for sprint 44 (June 9-20). We should have the controller and Ceph hooks merged by then.
