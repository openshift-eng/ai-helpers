# Sprint 42 - Q3 Feature Development

**Project:** CNTRLPLANE

---

## Story: Add real-time metrics dashboard

**Type:** Story
**Component:** Console
**Priority:** High
**Labels:** ui, dashboard, metrics

### User Story

As a platform engineer, I want a real-time dashboard showing cluster health metrics, so that I can quickly identify and respond to performance issues.

### Acceptance Criteria

- [ ] Dashboard displays CPU, memory, disk, and network metrics
- [ ] Metrics update in real-time (refresh every 5 seconds)
- [ ] Historical data available for last 7 days
- [ ] Filtering by cluster, node pool, and namespace
- [ ] Exportable to CSV/JSON for reporting

### Technical Notes

Use Grafana embedded panels with Prometheus as data source. Dashboard should be accessible at `/console/metrics`.

---

## Bug: API returns 500 error on special characters in resource names

**Type:** Bug
**Component:** API Gateway
**Priority:** Critical
**Labels:** api, security

### Description

API server crashes when creating resources with special characters in names, returning HTTP 500 instead of validation error.

### Steps to Reproduce

1. Send POST request to `/api/v1/clusters` with payload:
   ```json
   {
     "name": "my-cluster<script>alert('xss')</script>",
     "region": "us-east-1"
   }
   ```
2. Observe 500 Internal Server Error response
3. Check API server logs — shows panic/crash

### Expected Behavior

API should return HTTP 400 with validation error:
```json
{
  "error": "Invalid cluster name: contains illegal characters",
  "allowed_pattern": "^[a-z0-9-]+$"
}
```

### Actual Behavior

Returns 500 error, crashes API server process, requires restart.

### Environment

- API version: v1.5.2
- Platform: OpenShift 4.15
- Affected endpoints: `/api/v1/clusters`, `/api/v1/nodepools`

---

## Task: Update API documentation for v2 endpoints

**Type:** Task
**Component:** Documentation
**Priority:** Medium
**Labels:** docs, api

### Description

Update API reference documentation to include new v2 endpoints introduced in Sprint 41.

### Definition of Done

- [ ] Swagger/OpenAPI spec updated with v2 endpoints
- [ ] Code examples added for all CRUD operations
- [ ] Authentication/authorization requirements documented
- [ ] Migration guide from v1 to v2 added
- [ ] Documentation published to developer portal

### Context

New v2 endpoints were added in CNTRLPLANE-500 but documentation was not updated. Customers are filing support tickets asking about v2 usage.

---

## Story: Implement cluster backup and restore

**Type:** Story
**Component:** Storage
**Priority:** High
**Version:** openshift-4.17
**Labels:** backup, disaster-recovery

### User Story

As a cluster admin, I want to backup and restore cluster state (including etcd, configs, and persistent volumes), so that I can recover from disasters or migrate clusters.

### Acceptance Criteria

- [ ] Automated daily backups of etcd snapshots
- [ ] Backup includes cluster configs, secrets, and RBAC policies
- [ ] Backup stored in object storage (S3-compatible)
- [ ] Restore operation validated in test environment
- [ ] Recovery Time Objective (RTO) < 1 hour
- [ ] Recovery Point Objective (RPO) < 24 hours

### Technical Notes

Use Velero for backup/restore orchestration. Integration with:
- AWS S3 for backup storage
- Encrypted backups with KMS keys
- Automated retention policy (keep 30 daily, 12 monthly)

### Dependencies

- CNTRLPLANE-200 — Object storage integration must be complete
- CNTRLPLANE-201 — Encryption key rotation implemented
