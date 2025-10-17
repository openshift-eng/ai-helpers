---
description: Analyze OpenShift must-gather bundles to identify root causes, bugs, and cluster health issues
argument-hint: [must-gather-path]
---

## Name
analyze-must-gather

## Synopsis
```
/analyze-must-gather [must-gather-path]
```

## Description

The `analyze-must-gather` command performs comprehensive AI-powered analysis of OpenShift must-gather bundles to identify:
- Root cause analysis (RCA) of cluster issues
- Critical bugs and anomalies
- Cluster health assessment
- Component-specific problems
- Actionable fix recommendations

This command leverages advanced pattern recognition and AI diagnostics to automatically detect common and complex issues in must-gather data, providing SRE teams with immediate insights and resolution paths.

## Key Capabilities

### Automated Analysis
- **Cluster Health Assessment**: Overall cluster status and health score
- **Anomaly Detection**: AI-powered identification of unusual patterns
- **Root Cause Analysis**: Deep dive into primary issues and their causes
- **Component Diagnostics**: Per-component health checks (API server, etcd, operators, nodes)
- **Log Analysis**: Automated parsing of component logs for errors and warnings
- **Configuration Review**: Validation of cluster configurations

### Output Includes
- **Primary Issue**: Main problem affecting the cluster
- **Root Cause Summary**: Explanation of why the issue occurred
- **Evidence**: Supporting data from logs and configurations
- **Severity Level**: Critical, high, medium, or low
- **Immediate Actions**: Step-by-step remediation steps
- **Affected Components**: List of impacted cluster components
- **SRE Diagnostic Report**: Comprehensive report for incident management

## How It Works

### Step 1: Bundle Validation
- Verifies must-gather bundle path exists
- Checks for required directory structure
- Validates bundle completeness

### Step 2: Data Extraction
- Scans cluster operator status
- Analyzes pod states across all namespaces
- Extracts node conditions and resource usage
- Parses component logs (API server, etcd, controller manager, scheduler)
- Reviews event logs for warnings and errors

### Step 3: AI-Powered Analysis
- Pattern matching against known issue signatures
- Anomaly detection using statistical analysis
- Log correlation across multiple components
- Timeline reconstruction of events leading to issues
- Impact assessment on cluster functionality

### Step 4: Root Cause Identification
- Identifies primary vs. secondary issues
- Traces issue propagation across components
- Determines root cause with supporting evidence
- Assesses severity and urgency

### Step 5: Remediation Recommendations
- Provides immediate action items
- Suggests configuration changes
- Recommends oc commands for fixes
- Links to relevant documentation
- Escalation criteria for Red Hat support

## Arguments

- **$1** (must-gather-path): Path to the must-gather bundle directory
  - Can be absolute path: `/path/to/must-gather.local.123456`
  - Can be relative path: `./must-gather.local.123456`
  - Can be compressed: `must-gather.tar.gz` (will be extracted)

## Usage Examples

### Example 1: Basic Analysis
```
/analyze-must-gather /path/to/must-gather.local.123456
```

**Expected Output:**
```
🔍 Analyzing must-gather bundle...

📊 Cluster Health Assessment:
Status: DEGRADED
Critical Issues: 3
Warnings: 7
Overall Health Score: 62/100

🚨 Primary Issue:
etcd cluster has lost quorum - 2 of 3 members unreachable

🔎 Root Cause Analysis:
Network connectivity issues between control plane nodes
caused etcd members to become isolated, leading to quorum loss.

📋 Evidence:
- etcd logs show "connection refused" errors
- Network policy changes detected 2 hours before issue
- Node-to-node connectivity test failures

⚠️ Severity: CRITICAL

✅ Immediate Actions:
1. Check network connectivity between control plane nodes
2. Review recent network policy changes
3. Verify firewall rules for etcd ports (2379, 2380)
4. Restart affected etcd members if connectivity restored

📦 Affected Components:
- etcd (critical)
- kube-apiserver (degraded)
- All cluster operators (waiting for API)
```

### Example 2: Detailed Analysis with Interactive Q&A
```
/analyze-must-gather ./must-gather.local.654321

User: What's causing the API server pods to crash?

AI: Based on the must-gather analysis:

🔍 API Server Crash Root Cause:
- OOM (Out of Memory) kills detected in API server pods
- Memory usage reached 8GB limit before crashes
- High request rate from cluster operators (500+ req/sec)

Evidence from logs:
- kernel: Out of memory: Killed process 1234 (kube-apiserver)
- API server was handling 100K+ watch requests
- Etcd database size: 12GB (very large)

Recommended Actions:
1. Increase API server memory limit to 16GB
2. Review and reduce watch requests from operators
3. Perform etcd defragmentation to reduce DB size
4. Consider scaling API server replicas

Would you like me to generate the exact oc commands to apply these fixes?
```

### Example 3: Focus on Specific Component
```
/analyze-must-gather /tmp/mg --component=operators

AI: Analyzing cluster operators...

📊 Cluster Operator Status:
Total: 32
Available: 28
Degraded: 3
Unavailable: 1

🚨 Degraded Operators:
1. authentication (degraded for 2h15m)
   - Reason: OAuth pods not ready
   - Error: Image pull backoff for oauth-openshift:v4.14

2. network (degraded for 45m)
   - Reason: OVN pods restarting frequently
   - Error: CNI config validation failed

3. monitoring (degraded for 1h30m)
   - Reason: Prometheus PVC full
   - Error: No space left on device

❌ Unavailable Operators:
1. console (unavailable for 3h)
   - Reason: Console route not accessible
   - Error: 502 Bad Gateway from router pods

✅ Recommendations:
1. Fix image pull issue for authentication operator
2. Validate and correct CNI configuration for network
3. Expand PVC or clean up Prometheus data for monitoring
4. Check router pod logs and route configuration for console
```

## Analysis Categories

### 1. Cluster Operators
- Operator status (Available, Degraded, Progressing, Unavailable)
- Operator version mismatches
- Operator logs with errors
- Operator reconciliation failures

### 2. Control Plane Components
- **API Server**: Crash loops, high latency, authentication issues
- **etcd**: Quorum status, database size, corruption, performance
- **Controller Manager**: Resource quota issues, failing controllers
- **Scheduler**: Pod scheduling failures, node affinity problems

### 3. Node Health
- Node status (Ready, NotReady, Unknown)
- Disk pressure, memory pressure, PID pressure
- Kubelet issues and restarts
- Container runtime problems

### 4. Pod and Container Issues
- CrashLoopBackOff pods
- ImagePullBackOff errors
- OOMKilled containers
- Pending pods and scheduling failures

### 5. Network Problems
- CNI failures
- Service connectivity issues
- DNS resolution failures
- Network policy misconfigurations

### 6. Storage Issues
- PVC binding failures
- Storage class problems
- Volume mount errors
- Disk space exhaustion

### 7. Authentication & Authorization
- OAuth configuration errors
- Certificate expiration
- RBAC permission denials
- Identity provider failures

## Common Issues Detected

### Critical Issues
1. **etcd Quorum Loss**: Detected via etcd member status
2. **API Server Down**: No running API server pods
3. **Certificate Expiration**: Certs expired or expiring soon
4. **Node Failure**: Multiple nodes NotReady
5. **Storage Full**: etcd or node disk at capacity

### High Priority Issues
1. **Operator Degradation**: Critical operators degraded
2. **Pod Crash Loops**: Control plane pods restarting
3. **Network Partitioning**: Node-to-node connectivity lost
4. **Resource Exhaustion**: CPU/Memory limits reached
5. **Database Corruption**: etcd consistency errors

### Medium Priority Issues
1. **Performance Degradation**: Slow API responses
2. **Log Volume**: Excessive logging causing disk pressure
3. **Image Pull Issues**: Registry connectivity problems
4. **Configuration Drift**: Unexpected config changes
5. **Version Skew**: Component version mismatches

## Interactive Capabilities

After initial analysis, you can ask follow-up questions:

### Root Cause Questions
```
"What caused the etcd failure?"
"Why are pods failing to schedule?"
"What's the root cause of the network issue?"
```

### Component-Specific Questions
```
"Tell me about the API server status"
"What's wrong with etcd?"
"Show me operator issues"
"Are there any node problems?"
```

### Fix Recommendations
```
"How do I fix this?"
"What should I do first?"
"Give me the oc commands to resolve this"
"What's the priority order of fixes?"
```

### Timeline Questions
```
"When did this issue start?"
"What changed before the failure?"
"Show me the event timeline"
```

## Output Format

### Standard Analysis Output
```
🔍 Must-Gather Analysis Report
=====================================

📅 Cluster Information:
- Version: 4.14.3
- Infrastructure: AWS
- Install Date: 2024-01-15
- Must-Gather Timestamp: 2024-10-17 14:30 UTC

📊 Cluster Health:
Overall Status: [HEALTHY|DEGRADED|CRITICAL]
Health Score: XX/100
Critical Issues: X
High Priority: X
Warnings: X

🚨 Primary Issue:
[Description of main problem]

🔎 Root Cause Analysis:
[Detailed explanation of root cause]

📋 Evidence:
- [Supporting evidence from logs]
- [Configuration issues found]
- [Timeline of events]

⚠️ Severity: [CRITICAL|HIGH|MEDIUM|LOW]
Impact: [Description of impact]

🔧 Immediate Actions:
1. [Action 1]
2. [Action 2]
3. [Action 3]

📦 Affected Components:
- [Component 1]: [Status/Impact]
- [Component 2]: [Status/Impact]

🔗 Related Issues:
- [Secondary issue 1]
- [Secondary issue 2]

📚 References:
- [Link to docs]
- [KB articles]
- [Bug tracker references]
```

### SRE Diagnostic Report
```
📋 SRE DIAGNOSTIC REPORT
=====================================

INCIDENT SUMMARY:
- Incident ID: [Auto-generated]
- Severity: [Level]
- Start Time: [Timestamp]
- Detection: [How detected]

IMPACT ASSESSMENT:
- User Impact: [Description]
- Affected Services: [List]
- Estimated Affected Users: [Count/Percentage]

ROOT CAUSE:
[Detailed technical root cause]

CONTRIBUTING FACTORS:
- [Factor 1]
- [Factor 2]

RESOLUTION STEPS:
1. [Immediate fix]
2. [Short-term fix]
3. [Long-term prevention]

PREVENTION MEASURES:
- [Recommendation 1]
- [Recommendation 2]

ESCALATION PATH:
[When to escalate to Red Hat support]
```

## Best Practices

### Before Running Analysis
1. **Collect fresh must-gather**: `oc adm must-gather`
2. **Ensure complete bundle**: Verify all expected files present
3. **Note symptoms**: Document observed issues before analysis

### During Analysis
1. **Review full output**: Don't skip sections
2. **Ask clarifying questions**: Use interactive Q&A
3. **Cross-reference**: Compare with cluster monitoring

### After Analysis
1. **Prioritize actions**: Follow recommended priority order
2. **Test fixes incrementally**: Apply one fix at a time
3. **Collect new must-gather**: After fixes for comparison
4. **Document findings**: Update incident reports

## Prerequisites

- Must-gather bundle collected from cluster
- Bundle extracted to local filesystem
- Read access to bundle directory
- (Optional) Network access to cluster for live validation

## Tips for Best Results

### Comprehensive Must-Gather
Collect with all required components:
```bash
oc adm must-gather \
  --image=registry.redhat.io/openshift4/ose-must-gather:latest \
  --dest-dir=/tmp/must-gather
```

### Include Additional Data
For specific issues, gather extra data:
```bash
# For network issues
oc adm must-gather -- /usr/bin/gather_network_logs

# For storage issues
oc adm must-gather -- /usr/bin/gather_storage_logs
```

### Specify Component Focus
If you know the problem area:
```
/analyze-must-gather /path/to/mg --focus=etcd
/analyze-must-gather /path/to/mg --focus=networking
/analyze-must-gather /path/to/mg --focus=operators
```

## Common Use Cases

### 1. Post-Incident Analysis
```
/analyze-must-gather ./incident-20241017/must-gather
"What caused the outage?"
"Show me the event timeline"
"What should we change to prevent this?"
```

### 2. Proactive Health Check
```
/analyze-must-gather ./weekly-mg
"Are there any potential issues?"
"Show me warnings that could become critical"
"What's the cluster health trend?"
```

### 3. Upgrade Validation
```
/analyze-must-gather ./pre-upgrade-mg
/analyze-must-gather ./post-upgrade-mg
"Compare the two must-gathers"
"What changed after the upgrade?"
```

### 4. Performance Investigation
```
/analyze-must-gather ./perf-issue-mg
"Why is the API slow?"
"Show me resource usage patterns"
"Are there any bottlenecks?"
```

## Advanced Features

### Automated Bug Detection
- Matches issues against known bug database
- Suggests relevant BZ (Bugzilla) references
- Identifies if issue has upstream fix

### Trend Analysis
- Compares multiple must-gathers over time
- Identifies degradation patterns
- Predicts potential failures

### Compliance Checking
- Validates best practice configurations
- Checks security postures
- Identifies deviations from standards

---

**Ready to analyze must-gather bundles!** Provide the path to your must-gather directory and get instant AI-powered diagnostics, root cause analysis, and actionable fix recommendations.
