---
description: Analyze and compare disruption across one or more Prow CI job runs
argument-hint: <prowjob-url-1> [prowjob-url-2 ...] [--backends backend1,backend2,...]
---

## Name
ci:analyze-disruption

## Synopsis
Analyze disruption events across one or more CI job runs, comparing backends to identify root causes:
```text
/ci:analyze-disruption <prowjob-url-1> [prowjob-url-2 ...] [--backends backend1,backend2,...]
```

## Description
Analyze disruption recorded in Prow CI job runs by downloading interval/timeline data, audit logs, and pod logs, then comparing disruption events across backends and job runs to identify patterns and root causes.

The command accepts:
- One or more Prow job URLs (required, at least 1)
- An optional `--backends` flag with a comma-separated list of backend names to focus on

When multiple job runs are provided, the command compares and contrasts disruption patterns across runs to find commonalities that point to systemic issues vs one-off infrastructure problems.

### What It Does

1. **Downloads interval/timeline data** for each job run and locates the disruption section
2. **Identifies disruption intervals** by hovering-equivalent inspection of failed request messages
3. **Correlates with cluster activity** — what else was happening when disruption occurred
4. **Classifies disruption by backend type**:
   - **Cache backends** (e.g., `*-cache-*`) — implies etcd problems or global networking issues
   - **Non-cache backends** — implies the actual component or cluster networking had problems
   - **`ci-cluster-network-liveness`** — canary backend polling a static external endpoint from the test cluster; significant disruption here means the test infrastructure itself had network issues, making actual measured disruption much less valuable for that run
   - **Cloud network-liveness backends** — monitor connectivity from the test cluster to static cloud backends; used to detect cloud-provider-level issues
5. **Analyzes audit logs** for kube-api, oauth-api, and openshift-api samplers to determine if requests were received (issue inside cluster) or missing (issue between test cluster and load balancer)
6. **Reviews pod logs** for etcd-specific messages (leader changes, write delays)
7. **Checks for high CPU** correlation with mass disruption events
8. **Cross-run comparison** (when multiple runs provided) — identifies which disruption patterns are consistent vs isolated

### Backend Interpretation Guide

- **Cache backends disrupted** → likely etcd or global networking problem
- **Non-cache backends disrupted** → likely component-specific or cluster networking problem
- **ci-cluster-network-liveness disrupted** → test infrastructure network issues; discount disruption from that run
- **Cloud network-liveness disrupted** → cloud provider issues
- **All backends disrupted simultaneously** → likely node-level issue (high CPU, node shutdown)

### Responsibility Routing

Disruption responsibility spans multiple teams. The more detail tracked down, the better the routing:
- **Networking team** — network-related disruptions, any disruptions related to the network or connectivity
- **Workloads team** — pod lifecycle, readiness probe issues
- **API Server team** — API server disruption, audit log gaps
- **Node team** — node shutdown sequencing, kubelet behavior, high CPU

## Implementation
- Load the "Analyze Disruption" skill
- Proceed with the analysis by following the implementation steps from the skill

The skill handles all implementation details including:
- URL parsing and artifact downloading
- Interval file analysis for disruption events
- Audit log analysis for request gaps
- Pod log analysis for etcd issues
- High CPU correlation via PromQL queries
- Cross-run comparison and pattern detection

## Return Value

- **Format**: Structured Markdown report
- **Sections**:
  - **Per-Run Disruption Summary**: Disruption intervals per backend with timestamps and messages
  - **Backend Classification**: Cache vs non-cache vs canary analysis
  - **Audit Log Analysis**: Request gaps correlated with disruption windows
  - **Cluster Activity Correlation**: What was happening during disruption (etcd leader changes, node events, high CPU, operator progressing)
  - **Cross-Run Comparison** (multi-run): Patterns consistent across runs vs isolated incidents
  - **Root Cause Hypothesis**: Synthesized analysis with team routing recommendation
- **Deep links** per run: Prow job page, Sippy intervals view, GCS artifact browser
- **Artifacts**: Downloaded to `.work/disruption-analysis/{date}/{build_id}/`
- **Report**: Saved to `.work/disruption-analysis/{date}/{backend_names}-analysis.md`

## Arguments
- **$1+**: One or more Prow job URLs (required, at least 1)
- **Flags**:
  - `--backends <list>` — Comma-separated list of backend names to focus analysis on. If omitted, all backends with disruption are analyzed.

## Examples

1. **Analyze disruption in a single job run**:
   ```text
   /ci:analyze-disruption https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.21-e2e-aws-ovn/1983307151598161920
   ```

2. **Compare disruption across multiple runs**:
   ```text
   /ci:analyze-disruption https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.21-e2e-aws-ovn/1983307151598161920 https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.21-e2e-aws-ovn/1983307151598161921
   ```

3. **Focus on specific backends**:
   ```text
   /ci:analyze-disruption https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-release-master-ci-4.21-e2e-aws-ovn/1983307151598161920 --backends kube-api,oauth-api,openshift-api
   ```
