---
description: Check etcd cluster health, member status, and identify issues
argument-hint: "[--verbose]"
---

## Name
etcd:health-check

## Synopsis
```
/etcd:health-check [--verbose]
```

## Description

The `health-check` command performs a comprehensive health check of the etcd cluster in an OpenShift environment. It examines etcd member status, cluster health, leadership, connectivity, and identifies potential issues that could affect cluster stability.

Etcd is the critical key-value store that holds all cluster state for Kubernetes/OpenShift. Issues related to etcd can cause cluster-wide failures, so monitoring its health is essential.

This command is useful for:
- Diagnosing cluster control plane issues
- Verifying etcd cluster stability
- Identifying split-brain scenarios
- Checking member synchronization
- Detecting disk space issues
- Monitoring etcd performance

## Prerequisites

Before using this command, ensure you have:

1. **OpenShift CLI (oc)**
   - Install from: https://mirror.openshift.com/pub/openshift-v4/clients/ocp/
   - Verify with: `oc version`

2. **Active cluster connection**
   - Must be connected to an OpenShift cluster
   - Verify with: `oc whoami`

3. **Cluster admin permissions**
   - Required to access etcd pods and execute commands
   - Verify with: `oc auth can-i get pods -n openshift-etcd`

4. **Healthy etcd namespace**
   - The openshift-etcd namespace must exist
   - At least one etcd pod must be running

## Arguments

- **--verbose** (optional): Enable detailed output
  - Shows etcd member details
  - Displays performance metrics
  - Includes log snippets for errors
  - Provides additional diagnostic information

## Implementation

The command performs the following checks:

### 1. Verify Prerequisites

Check if oc CLI is available and cluster is accessible:

```bash
if ! command -v oc &> /dev/null; then
    echo "Error: oc CLI not found. Please install OpenShift CLI."
    exit 1
fi

if ! oc whoami &> /dev/null; then
    echo "Error: Not connected to an OpenShift cluster."
    exit 1
fi
```

### 2. Check Etcd Namespace and Pods

Verify the etcd namespace exists and get pod status:

```bash
echo "Checking etcd namespace and pods..."

if ! oc get namespace openshift-etcd &> /dev/null; then
    echo "CRITICAL: openshift-etcd namespace not found"
    exit 1
fi

# Get etcd pod status
ETCD_PODS=$(oc get pods -n openshift-etcd -l app=etcd -o json)
TOTAL_PODS=$(echo "$ETCD_PODS" | jq '.items | length')
RUNNING_PODS=$(echo "$ETCD_PODS" | jq '[.items[] | select(.status.phase == "Running")] | length')

echo "Etcd pods: $RUNNING_PODS/$TOTAL_PODS running"

if [ "$RUNNING_PODS" -eq 0 ]; then
    echo "CRITICAL: No etcd pods are running"
    exit 1
fi

# List all etcd pods with status
echo ""
echo "Etcd Pod Status:"
oc get pods -n openshift-etcd -l app=etcd -o custom-columns=NAME:.metadata.name,STATUS:.status.phase,READY:.status.containerStatuses[0].ready,RESTARTS:.status.containerStatuses[0].restartCount,NODE:.spec.nodeName
```

### 3. Check Etcd Cluster Health

Use etcdctl to check cluster health from each running etcd pod:

```bash
echo ""
echo "Checking etcd cluster health..."

# Get the first running etcd pod
ETCD_POD=$(oc get pods -n openshift-etcd -l app=etcd --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')

if [ -z "$ETCD_POD" ]; then
    echo "CRITICAL: No running etcd pod found"
    exit 1
fi

# Check cluster health
HEALTH_OUTPUT=$(oc exec -n openshift-etcd "$ETCD_POD" -c etcdctl -- etcdctl endpoint health --cluster -w table 2>&1)

if echo "$HEALTH_OUTPUT" | grep -q "is healthy"; then
    echo "Cluster Health Status:"
    echo "$HEALTH_OUTPUT"
else
    echo "CRITICAL: Etcd cluster health check failed"
    echo "$HEALTH_OUTPUT"
    exit 1
fi
```

### 4. Check Etcd Member List

List all etcd members and verify quorum:

```bash
echo ""
echo "Checking etcd member list..."

MEMBER_LIST=$(oc exec -n openshift-etcd "$ETCD_POD" -c etcdctl -- etcdctl member list -w table 2>&1)

echo "Etcd Members:"
echo "$MEMBER_LIST"

# Count members
MEMBER_COUNT=$(oc exec -n openshift-etcd "$ETCD_POD" -c etcdctl -- etcdctl member list -w json 2>/dev/null | jq '.members | length')

echo ""
echo "Total members: $MEMBER_COUNT"

if [ "$MEMBER_COUNT" -lt 3 ]; then
    echo "WARNING: Etcd cluster has less than 3 members (quorum at risk)"
fi

# Check for unstarted members
UNSTARTED=$(echo "$MEMBER_LIST" | grep "unstarted" | wc -l)
if [ "$UNSTARTED" -gt 0 ]; then
    echo "WARNING: $UNSTARTED member(s) in unstarted state"
fi
```

### 5. Check Etcd Leadership

Verify there is a healthy leader:

```bash
echo ""
echo "Checking etcd leadership..."

ENDPOINT_STATUS=$(oc exec -n openshift-etcd "$ETCD_POD" -c etcdctl -- etcdctl endpoint status --cluster -w table 2>&1)

echo "Endpoint Status:"
echo "$ENDPOINT_STATUS"

# Check if there's a leader
if echo "$ENDPOINT_STATUS" | grep -q "true"; then
    LEADER_ENDPOINT=$(echo "$ENDPOINT_STATUS" | grep "true" | awk '{print $2}')
    echo ""
    echo "Leader: $LEADER_ENDPOINT"
else
    echo "CRITICAL: No etcd leader elected"
    exit 1
fi
```

### 6. Check Etcd Database Size

Check database size and fragmentation:

```bash
echo ""
echo "Checking etcd database size..."

# Get database size from endpoint status
DB_SIZE=$(oc exec -n openshift-etcd "$ETCD_POD" -c etcdctl -- etcdctl endpoint status --cluster -w json 2>/dev/null)

echo "$DB_SIZE" | jq -r '.[] | "Endpoint: \(.Endpoint) | DB Size: \(.Status.dbSize) bytes | DB Size in Use: \(.Status.dbSizeInUse) bytes"'

# Calculate fragmentation percentage
echo "$DB_SIZE" | jq -r '.[] |
    if .Status.dbSize > 0 then
        "Fragmentation: \(((.Status.dbSize - .Status.dbSizeInUse) * 100 / .Status.dbSize) | floor)%"
    else
        "Fragmentation: N/A"
    end'

# Warn if database is too large
MAX_DB_SIZE=$((8 * 1024 * 1024 * 1024))  # 8GB threshold
CURRENT_SIZE=$(echo "$DB_SIZE" | jq -r '.[0].Status.dbSize')

if [ "$CURRENT_SIZE" -gt "$MAX_DB_SIZE" ]; then
    echo "WARNING: Etcd database size ($CURRENT_SIZE bytes) exceeds recommended maximum (8GB)"
    echo "Consider defragmentation or checking for excessive key growth"
fi
```

### 7. Check Disk Space on Etcd Nodes

Verify disk space on nodes running etcd:

```bash
echo ""
echo "Checking disk space on etcd nodes..."

for pod in $(oc get pods -n openshift-etcd -l app=etcd --field-selector=status.phase=Running -o jsonpath='{.items[*].metadata.name}'); do
    echo "Pod: $pod"
    oc exec -n openshift-etcd "$pod" -c etcd -- df -h /var/lib/etcd | tail -1

    # Get disk usage percentage
    DISK_USAGE=$(oc exec -n openshift-etcd "$pod" -c etcd -- df -h /var/lib/etcd | tail -1 | awk '{print $5}' | sed 's/%//')

    if [ "$DISK_USAGE" -gt 80 ]; then
        echo "WARNING: Disk usage on $pod is ${DISK_USAGE}% (threshold: 80%)"
    fi
    echo ""
done
```

### 8. Check for Recent Etcd Errors

Check recent logs for errors or warnings:

```bash
echo ""
echo "Checking recent etcd logs for errors..."

RECENT_ERRORS=$(oc logs -n openshift-etcd "$ETCD_POD" -c etcd --tail=100 | grep -i "error\|warn\|fatal" | tail -10)

if [ -n "$RECENT_ERRORS" ]; then
    echo "Recent errors/warnings found:"
    echo "$RECENT_ERRORS"
else
    echo "No recent errors in etcd logs"
fi
```

### 9. Check Etcd Performance Metrics (if --verbose)

If verbose mode is enabled, check performance metrics:

```bash
if [ "$VERBOSE" = "true" ]; then
    echo ""
    echo "Checking etcd performance metrics..."

    # Get metrics from etcd pod
    METRICS=$(oc exec -n openshift-etcd "$ETCD_POD" -c etcd -- curl -s http://localhost:2379/metrics 2>/dev/null)

    # Parse key metrics
    echo "Backend Commit Duration (p99):"
    echo "$METRICS" | grep "etcd_disk_backend_commit_duration_seconds" | grep "quantile=\"0.99\"" | head -1

    echo ""
    echo "WAL Fsync Duration (p99):"
    echo "$METRICS" | grep "etcd_disk_wal_fsync_duration_seconds" | grep "quantile=\"0.99\"" | head -1

    echo ""
    echo "Leader Changes:"
    echo "$METRICS" | grep "etcd_server_leader_changes_seen_total" | head -1
fi
```

### 10. Generate Summary Report

Create a summary of findings:

```bash
echo ""
echo "==============================================="
echo "Etcd Health Check Summary"
echo "==============================================="
echo "Check Time: $(date)"
echo "Cluster: $(oc whoami --show-server)"
echo ""
echo "Results:"
echo "  Etcd Pods Running: $RUNNING_PODS/$TOTAL_PODS"
echo "  Cluster Members: $MEMBER_COUNT"
echo "  Leader Elected: Yes"
echo "  Cluster Health: Healthy"
echo ""

if [ "$WARNINGS" -gt 0 ]; then
    echo "Status: WARNING - Found $WARNINGS warnings requiring attention"
    exit 0
else
    echo "Status: HEALTHY - All checks passed"
    exit 0
fi
```

## Return Value

The command returns different exit codes:

- **Exit 0**: Etcd cluster is healthy (may have warnings)
- **Exit 1**: Critical issues detected (no running pods, no leader, health check failed)

**Output Format**:
- Human-readable report with section headers
- Critical issues marked with "CRITICAL:"
- Warnings marked with "WARNING:"
- Success indicators for healthy checks

## Examples

### Example 1: Basic health check
```
/etcd:health-check
```

Output:
```
Checking etcd namespace and pods...
Etcd pods: 3/3 running

Etcd Pod Status:
NAME                                     STATUS    READY  RESTARTS  NODE
etcd-ip-10-0-21-125.us-east-2...        Running   true   0         ip-10-0-21-125
etcd-ip-10-0-43-249.us-east-2...        Running   true   0         ip-10-0-43-249
etcd-ip-10-0-68-109.us-east-2...        Running   true   0         ip-10-0-68-109

Checking etcd cluster health...
Cluster Health Status:
+------------------------------------------+--------+
|                ENDPOINT                  | HEALTH |
+------------------------------------------+--------+
| https://10.0.21.125:2379                | true   |
| https://10.0.43.249:2379                | true   |
| https://10.0.68.109:2379                | true   |
+------------------------------------------+--------+

Checking etcd member list...
Etcd Members:
+------------------+---------+------------------------+
|        ID        | STATUS  |          NAME          |
+------------------+---------+------------------------+
| 3a2b1c4d5e6f7890 | started | ip-10-0-21-125         |
| 4b3c2d5e6f708901 | started | ip-10-0-43-249         |
| 5c4d3e6f70890123 | started | ip-10-0-68-109         |
+------------------+---------+------------------------+

Total members: 3

Checking etcd leadership...
Leader: https://10.0.21.125:2379

===============================================
Etcd Health Check Summary
===============================================
Status: HEALTHY - All checks passed
```

### Example 2: Verbose health check with metrics
```
/etcd:health-check --verbose
```

## Common Issues and Remediation

### No Etcd Leader

**Symptoms**: Cluster shows no leader elected

**Investigation**:
```bash
oc logs -n openshift-etcd <etcd-pod> -c etcd | grep -i "leader"
oc get events -n openshift-etcd
```

**Remediation**:
- Check network connectivity between etcd members
- Verify etcd pods are running on different nodes
- Check for clock skew between nodes

### High Database Size

**Symptoms**: Database size exceeds 8GB

**Investigation**:
```bash
oc exec -n openshift-etcd <etcd-pod> -c etcdctl -- etcdctl endpoint status -w table
```

**Remediation**:
- Run defragmentation: `/etcd:defrag` (if command exists)
- Check for excessive key creation (e.g., many events)
- Review retention policies

### Disk Space Issues

**Symptoms**: Disk usage > 80% on etcd data directory

**Investigation**:
```bash
oc exec -n openshift-etcd <etcd-pod> -c etcd -- df -h /var/lib/etcd
```

**Remediation**:
- Clean up old snapshots
- Defragment database
- Increase disk size if needed

### Member Not Started

**Symptoms**: Member shows "unstarted" status

**Investigation**:
```bash
oc logs -n openshift-etcd <etcd-pod> -c etcd
oc describe pod -n openshift-etcd <etcd-pod>
```

**Remediation**:
- Check pod logs for errors
- Verify certificates are valid
- Check network policies and firewall rules

## Security Considerations

- Requires cluster-admin or equivalent permissions
- Access to etcd data allows viewing all cluster secrets
- Etcd metrics may contain sensitive information
- Always use secure connections when accessing etcd

## See Also

- Etcd documentation: https://etcd.io/docs/
- OpenShift etcd docs: https://docs.openshift.com/container-platform/latest/backup_and_restore/control_plane_backup_and_restore/
- Related commands: `/etcd:analyze-performance`

## Notes

- This command is read-only and does not modify etcd
- Checks are performed from within etcd pods using etcdctl
- Some checks require etcd to be running
- Performance may vary on large clusters with many keys
- Database size recommendations are based on upstream etcd guidance
