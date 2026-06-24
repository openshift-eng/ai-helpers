## Issue

**Key:** OPS-315
**Type:** Task
**Status:** Done
**Priority:** High
**Summary:** Procedure to rotate etcd encryption keys on production clusters
**Reporter:** SRE Lead
**Assignee:** Platform Engineer
**Created:** 2026-04-10
**Updated:** 2026-05-20
**Labels:** etcd, encryption, security
**Components:** Platform, Security

## Description

Production clusters require periodic rotation of etcd encryption keys per security policy (every 90 days). The current process is manual and undocumented, leading to inconsistent execution across teams. We need a validated, repeatable procedure.

## Comments

### Comment 1 — SRE Lead (2026-04-12)

Key constraints:
- Must be zero-downtime — API server stays available throughout
- Encryption config is a static pod resource, so changes require API server restart
- All existing secrets must be re-encrypted with the new key after rotation
- Rollback plan required in case of failed rotation

### Comment 2 — Platform Engineer (2026-04-20)

Tested and validated the following procedure on staging:

**Prerequisites:**
- `oc` CLI authenticated with cluster-admin
- Backup of etcd taken within last 24 hours
- Maintenance window communicated (no downtime, but reduced redundancy during rotation)

**Step 1 — Add new encryption key:**
```bash
oc get secret encryption-config -n openshift-config -o json | \
  jq '.data["encryption-config"] |= @base64d | fromjson' > /tmp/enc-config.json

# Add new aescbc key as first entry (becomes active for new writes)
# Keep old key as second entry (for reading existing data)
```

**Step 2 — Apply updated config:**
```bash
oc apply -f /tmp/enc-config-updated.json
```

**Step 3 — Wait for API server rollout:**
```bash
oc get kubeapiserver -o=jsonpath='{range .items[0].status.conditions[?(@.type=="Encrypted")]}{.type}{"\t"}{.status}{"\t"}{.message}{"\n"}{end}'
```
Wait until `Encrypted` condition shows `True`.

**Step 4 — Re-encrypt all secrets:**
```bash
oc adm migrate etcd-encryption --force
```
Monitor progress:
```bash
oc get secrets --all-namespaces -o json | jq '[.items[] | select(.metadata.annotations["encryption.apiserver.operator.openshift.io/migrated"] != "true")] | length'
```
Wait until count reaches 0.

**Step 5 — Remove old key:**
Once all secrets are re-encrypted, remove the old key from the encryption config and re-apply.

**Step 6 — Verify:**
```bash
# Confirm new secrets use new key
oc get secret test-secret -n default -o json | jq '.metadata.annotations'

# Confirm API server is healthy
oc get clusteroperator kube-apiserver
```

### Comment 3 — Security Lead (2026-05-01)

Reviewed the procedure. Two additions:
1. Step 0 should include verifying the current encryption status before starting
2. Add a rollback section — if Step 4 fails partway through, you need to keep both keys until migration completes

### Comment 4 — Platform Engineer (2026-05-10)

Added both. Also confirmed the procedure works on OCP 4.17 and 4.18.

**Rollback procedure:**
If rotation fails mid-migration:
1. Do NOT remove the old key
2. Check migration status
3. Re-run migration: `oc adm migrate etcd-encryption --force`
4. If API server is unhealthy, restore from etcd backup
